import json
import logging
import threading
import asyncio
import bisect
import time
import traceback

import sqlitedict
from concurrent.futures.thread import ThreadPoolExecutor

from utils.pubsub import PubSubClient
from utils.rpc_client import RpcClient
from utils.simple_proxy import SimpleRpcProxy
from utils.utils import http_rpc_url, pubsub_url, setup_log
from xmlrpc.server import SimpleXMLRPCServer

MAX_ACTIVE_PERIOD = 3600 * 2  # 2h
TIMESTAMP_HIST_COUNT = 2000
MAX_TIMESTAMP = 1 << 63

logger = logging.getLogger("fetcher")
LATEST_EPOCH_KEY = "latest_epoch"


class Block:
    def __init__(self, miner, reward, timestamp, epoch):
        self.miner = miner
        self.reward = reward
        self.timestamp = timestamp
        self.epoch = epoch
        self.server_timestamp = int(time.time())

    def get_timestamp(self):
        return min(self.timestamp, self.server_timestamp)


class Miner:
    def __init__(self, addr, activated):
        # TODO Use byte representation instead of hex string.
        self.addr = addr
        self.reward = 0
        self.timestamps = []
        self.all_timestamps = []
        self.latest_mined_block = 0
        # This is None when we have not recovered all the blocks before we start.
        # It is initialized after we recovered those old blocks, and we assume we will not receive a new block
        # to "activate" a period when the node is inactive.
        if activated:
            self.active_period = 0
        else:
            self.active_period = None
        # logger.debug(f"add miner, addr={addr} activated={activated}")

    def add_block(self, block: Block, within_range: bool):
        assert self.addr == block.miner
        bisect.insort(self.all_timestamps, block.timestamp)
        if within_range:
            self.reward += block.reward
            if self.latest_mined_block < block.get_timestamp():
                self.latest_mined_block = block.get_timestamp()
            if len(self.timestamps) != 0:
                gap = block.timestamp - self.timestamps[-1]
                if self.active_period is not None and 0 < gap <= MAX_ACTIVE_PERIOD:
                    self.active_period += gap
            bisect.insort(self.timestamps, block.timestamp)
            logger.debug(f"add block, miner={block.miner} active_period={self.active_period}")

    def activate(self):
        logger.debug(f"activate {self.addr}")
        if len(self.timestamps) > 0:
            latest_ts = self.timestamps[0]
            self.active_period = 0
            for i in range(1, len(self.timestamps)):
                # self.timestamps is sorted, so latest_ts is always increasing
                gap = self.timestamps[i] - latest_ts
                if gap <= MAX_ACTIVE_PERIOD:
                    self.active_period += gap
                latest_ts = self.timestamps[i]
        else:
            self.active_period = 0
        logger.debug(f"end activate {self.addr}")


class ChainDataFetcher(threading.Thread):
    def __init__(self, server_ip="127.0.0.1", http_port=12537, pubsub_port=12535, initial_epoch=0, start_timestamp=0,
                 end_timestamp=MAX_TIMESTAMP):
        super().__init__(daemon=True)
        self.rpc_client = RpcClient(SimpleRpcProxy(http_rpc_url(server_ip, http_port), timeout=3600))
        self.pubsub_client = PubSubClient(pubsub_url(server_ip, pubsub_port))
        self.blocks_db = sqlitedict.SqliteDict("data.db", tablename="blocks", autocommit=True)
        self.metadata_db = sqlitedict.SqliteDict("data.db", tablename="metadata", autocommit=True)

        self.miners = {}

        self.initial_epoch = initial_epoch
        self.end_timestamp = end_timestamp
        self.start_timestamp = start_timestamp
        self.activated = False
        self._lock = threading.Lock()

    def run(self) -> None:
        last_epoch = self.recover()
        asyncio.run(self.start_async(last_epoch))

    async def start_async(self, last_epoch):
        log_fut = asyncio.create_task(self.log_progress())
        subscription = await self.pubsub_client.subscribe("epochs")
        # await self.sub(subscription)
        sub_fut = asyncio.create_task(self.sub(subscription))
        end_epoch_number = self.rpc_client.epoch_number()
        catch_up_fut = asyncio.create_task(self.catch_up(last_epoch, end_epoch_number))
        await asyncio.gather(sub_fut, catch_up_fut, log_fut)

    async def sub(self, subscription):
        while True:
            try:
                async for new_epoch_data in subscription.iter(3600):
                    epoch_number = int(new_epoch_data["epochNumber"], 16)
                    logger.debug(f"pubsub get epoch number {epoch_number}")
                    # epoch_hashes = new_epoch_data["epochHashesOrdered"]
                    # for new_hash in epoch_hashes:
                    #     if new_hash not in self.blocks:
                    #         new_block = self.rpc_client.block_by_hash(new_hash)
                    #         miner = new_block["author"]
                    #         timestamp = new_block["timestamp"]
                    #         self.blocks[new_hash] = Block(new_hash, miner, timestamp)
                    #         self.miners.setdefault(miner, set()).add(new_hash)
                    await self.update_epoch_number(epoch_number, catch_up=False)
            except Exception as e:
                logger.warning(e)
                traceback.print_exc()
                self.pubsub_client.ws = None
                subscription = await self.pubsub_client.subscribe("epochs")

    async def update_epoch_number(self, epoch_number, catch_up):
        logger.debug(f"update_epoch_number: epoch_number={epoch_number}, catch_up={catch_up}")
        while True:
            rewards = self.rpc_client.get_block_reward_info(self.rpc_client.EPOCH_NUM(epoch_number))
            if len(rewards) != 0:
                break
            else:
                logger.debug(f"{epoch_number} not executed, wait for 1 second")
                await asyncio.sleep(1)
        blocks = {}
        for reward_info in rewards:
            block_hash = reward_info["blockHash"]
            author = reward_info["author"]
            reward = int(reward_info["totalReward"], 16) / 10**18
            if block_hash not in self.blocks_db:
                timestamp = int(self.rpc_client.block_by_hash(block_hash)["timestamp"], 16)
                blocks[block_hash] = Block(author, reward, timestamp, epoch_number)
        self._lock.acquire()
        for block_hash, block in blocks.items():
            self.miners\
                .setdefault(block.miner, Miner(block.miner, self.activated))\
                .add_block(block, self.start_timestamp <= block.timestamp <= self.end_timestamp)
        self._lock.release()
        self.blocks_db.update(blocks)
        if catch_up or self.activated:
            self.metadata_db[LATEST_EPOCH_KEY] = epoch_number
        logger.debug(f"update_epoch_number end: epoch_number={epoch_number}")

    async def catch_up(self, start_epoch_number: int, end_epoch_number: int):
        start_epoch_number = max(1, start_epoch_number)
        logger.info(f"catch_up starts: start={start_epoch_number} end={end_epoch_number}")
        futures = []
        executor = ThreadPoolExecutor(max_workers=4)
        for epoch_number in range(start_epoch_number, end_epoch_number+1):
            futures.append(executor.submit(lambda e: asyncio.run(self.update_epoch_number(e, catch_up=True)),
                                           epoch_number))
        for f in futures:
            f.result()
        self._lock.acquire()
        for miner_addr in self.miners:
            self.miners[miner_addr].activate()
        self.activated = True
        self._lock.release()
        logger.info(f"catch_up ends: self.activated={self.activated}")

    async def log_progress(self):
        while True:
            logger.info(f"progress: {self.progress_string()}")
            await asyncio.sleep(1)

    def progress_string(self):
        self._lock.acquire()
        r = f"block_count: {len(self.blocks_db)}"
        self._lock.release()
        return r

    def recover(self):
        if LATEST_EPOCH_KEY in self.metadata_db:
            last_epoch = self.metadata_db[LATEST_EPOCH_KEY]
            for block in self.blocks_db.values():
                self._lock.acquire()
                self.miners\
                    .setdefault(block.miner, Miner(block.miner, self.activated))\
                    .add_block(block, block.epoch >= self.initial_epoch and self.start_timestamp <= block.timestamp <= self.end_timestamp)
                self._lock.release()
            return last_epoch
        else:
            return self.initial_epoch

    def miner_list(self):
        self._lock.acquire()
        miner_list = []
        for miner_addr in self.miners:
            miner = self.miners[miner_addr]
            active_period = 0
            if len(miner.timestamps) == 0:
                continue
            if miner.active_period is not None:
                active_period = miner.active_period
            miner_list.append({
                "address": miner_addr[2:],
                "block_count": len(miner.timestamps),
                "active_period": int(active_period/3600),
                "mining_reward": miner.reward,
                "latest_mined_block": miner.latest_mined_block,
            })
        self._lock.release()
        return json.dumps(miner_list)

    def miner_block_timestamps(self, miner):
        self._lock.acquire()
        if miner not in self.miners:
            self._lock.release()
            return []
        else:
            timestamps = self.miners[miner].all_timestamps
            # TODO This can be optimized if it's too slow.
            min_timestamp = timestamps[0]
            max_timestamp = timestamps[-1]
            hist = [0 for _ in range(TIMESTAMP_HIST_COUNT)]
            period = (max_timestamp - min_timestamp) / TIMESTAMP_HIST_COUNT
            if period != 0:
                for ts in timestamps:
                    index = int((ts - min_timestamp) / period)
                    if index < TIMESTAMP_HIST_COUNT:
                        hist[index] += 1
                    else:
                        hist[-1] += 1
            for i in range(TIMESTAMP_HIST_COUNT - 1):
                hist[i + 1] += hist[i]
        self._lock.release()
        return json.dumps({
            "min_timestamp": min_timestamp,
            "max_timestamp": max_timestamp,
            "accumulative_count": hist,
        })


def miner_list():
    return chain_data_fetcher.miner_list()


def miner_block_timestamps(miner):
    return chain_data_fetcher.miner_block_timestamps(miner)


def start_rpc_server():
    server = SimpleXMLRPCServer(('localhost', 9000), logRequests=True)
    server.register_function(miner_list)
    server.register_function(miner_block_timestamps)
    server.serve_forever()


if __name__ == "__main__":
    setup_log()
    chain_data_fetcher = ChainDataFetcher()
    chain_data_fetcher.start()
    start_rpc_server()
