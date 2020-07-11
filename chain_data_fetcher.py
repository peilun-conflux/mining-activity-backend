import logging
import threading
import asyncio
import bisect
from concurrent.futures.thread import ThreadPoolExecutor

from utils.pubsub import PubSubClient
from utils.rpc_client import RpcClient
from utils.simple_proxy import SimpleRpcProxy
from utils.utils import http_rpc_url, pubsub_url

MAX_ACTIVE_PERIOD = 3600 * 2  # 2h
BLOCK_COUNT = 0

logger = logging.getLogger("fetcher")


class Block:
    def __init__(self, miner, reward, timestamp):
        self.miner = miner
        self.reward = reward
        self.timestamp = timestamp


class Miner:
    def __init__(self, addr, activated):
        # TODO Use byte representation instead of hex string.
        self.addr = addr
        self.reward = 0
        self.blocks = set()
        self.timestamps = []
        # This is None when we have not recovered all the blocks before we start.
        # It is initialized after we recovered those old blocks, and we assume we will not receive a new block
        # to "activate" a period when the node is inactive.
        if activated:
            self.active_period = 0
        else:
            self.active_period = None

    def add_block(self, block_hash, block: Block):
        assert self.addr == block.miner
        if block_hash not in self.blocks:
            self.blocks.add(block_hash)
            self.reward += block.reward
            bisect.insort(self.timestamps, block.timestamp)
            gap = block.timestamp - self.timestamps[-1]
            if self.active_period is not None and 0 < gap <= MAX_ACTIVE_PERIOD:
                self.active_period += gap

    def activate(self):
        latest_ts = self.timestamps[0]
        self.active_period = 0
        for i in range(1, len(self.timestamps)):
            # self.timestamps is sorted, so latest_ts is always increasing
            gap = self.timestamps[i] - latest_ts
            if gap <= MAX_ACTIVE_PERIOD:
                self.active_period += gap
            latest_ts = self.timestamps[i]


class ChainDataFetcher(threading.Thread):
    def __init__(self, server_ip="127.0.0.1", http_port=12537, pubsub_port=12535):
        super().__init__(daemon=True)
        self.rpc_client = RpcClient(SimpleRpcProxy(http_rpc_url(server_ip, http_port), timeout=30))
        self.pubsub_client = PubSubClient(pubsub_url(server_ip, pubsub_port))

        self.miners = {}

        self.activated = False
        self._lock = threading.Lock()

    def run(self) -> None:
        asyncio.run(self.start_async())

    async def start_async(self):
        log_fut = asyncio.create_task(self.log_progress())
        subscription = await self.pubsub_client.subscribe("epochs")
        # await self.sub(subscription)
        sub_fut = asyncio.create_task(self.sub(subscription))
        # FIXME If we get `start_epoch_number` later than subscribing epochs, we will not miss any block,
        # but this assumption is not always true, so we just get more epochs in catch-up to avoid problems.
        start_epoch_number = self.rpc_client.epoch_number() + 10
        catch_up_fut = asyncio.create_task(self.catch_up(start_epoch_number))
        await asyncio.gather(sub_fut, catch_up_fut, log_fut)

    async def sub(self, subscription):
        async for new_epoch_data in subscription.iter(60):
            epoch_number = int(new_epoch_data["epochNumber"], 16)
            # epoch_hashes = new_epoch_data["epochHashesOrdered"]
            # for new_hash in epoch_hashes:
            #     if new_hash not in self.blocks:
            #         new_block = self.rpc_client.block_by_hash(new_hash)
            #         miner = new_block["author"]
            #         timestamp = new_block["timestamp"]
            #         self.blocks[new_hash] = Block(new_hash, miner, timestamp)
            #         self.miners.setdefault(miner, set()).add(new_hash)
            await self.update_epoch_number(epoch_number)
        print("pubsub exits")
        exit()

    async def update_epoch_number(self, epoch_number):
        logger.info(self.progress_string())
        rewards = self.rpc_client.get_block_reward_info(self.rpc_client.EPOCH_NUM(epoch_number))
        blocks = {}
        for reward_info in rewards:
            block_hash = reward_info["blockHash"]
            author = reward_info["author"]
            reward = int(reward_info["totalReward"], 16) / 10**18
            timestamp = int(self.rpc_client.block_by_hash(block_hash)["timestamp"], 16)
            blocks[block_hash] = Block(author, reward, timestamp)
        self._lock.acquire()
        for block_hash, block in blocks.items():
            self.miners.setdefault(block.miner, Miner(block.miner, self.activated)).add_block(block_hash, block)
        self._lock.release()

    async def catch_up(self, start_epoch_number: int):
        executor = ThreadPoolExecutor()
        for epoch_number in range(start_epoch_number + 1):
            # TODO Batch?
            await self.update_epoch_number(epoch_number)
        self._lock.acquire()
        for miner_addr in self.miners:
            self.miners[miner_addr].activate()
        self.activated = True
        self._lock.release()

    async def log_progress(self):
        while True:
            print("progress", self.progress_string())
            await asyncio.sleep(1)

    def progress_string(self):
        self._lock.acquire()
        r = f"block_count: {sum([len(self.miners[addr].blocks) for addr in self.miners])}"
        self._lock.release()
        return r

    def miner_list(self):
        self._lock.acquire()
        miner_list = []
        for miner_addr in self.miners:
            miner = self.miners[miner_addr]
            miner_list.append({
                # FIXME: Remove "0x" prefix.
                "address": miner_addr,
                "block_count": len(miner.timestamps),
                "active_period": miner.active_period,
                "mining_reward": miner.reward,
                "latest_mined_block": miner.timestamps[-1],
            })
        self._lock.release()
        return str(miner_list)

    def miner_block_timestamps(self, miner):
        self._lock.acquire()
        r = str(self.miners[miner].timestamps)
        self._lock.release()
        return r

