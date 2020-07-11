import sqlite3
import time
from flask import Flask, request
from chain_data_fetcher import ChainDataFetcher
from utils.utils import setup_log

setup_log()
app = Flask(__name__)


class Block:
    def __init__(self):
        self.n = 0


def inc(b: Block):
    while True:
        b.n += 1
        time.sleep(1)


chain_data_fetcher = ChainDataFetcher()
chain_data_fetcher.start()


@app.route('/get-mined-block-timestamps', methods=['GET'])
def get_mined_block_timestamps():
    addr = request.args.get("address")
    return chain_data_fetcher.miner_block_timestamps(addr)


@app.route('/get-miner-list', methods=['GET'])
def get_miner_list():
    return chain_data_fetcher.miner_list()
