import logging
import time
from flask import Flask, request
from chain_data_fetcher import ChainDataFetcher
from utils.utils import setup_log, parse_date

setup_log()
app = Flask(__name__)
chain_data_fetcher = ChainDataFetcher(start_timestamp=parse_date("10:00-12/07/2020"),
                                      end_timestamp=parse_date("23:59-15/07/2020"))
chain_data_fetcher.start()


@app.route('/get-mined-block-timestamps', methods=['GET'])
def get_mined_block_timestamps():
    addr = request.args.get("address")
    return {
        "block_timestamps": chain_data_fetcher.miner_block_timestamps("0x"+addr)
    }


@app.route('/get-miner-list', methods=['GET'])
def get_miner_list():
    return chain_data_fetcher.miner_list()
