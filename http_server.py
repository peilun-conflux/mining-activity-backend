import logging
import time
from flask import Flask, request
from chain_data_fetcher import ChainDataFetcher
from utils.utils import setup_log, parse_date
from flask_cors import CORS

setup_log()
app = Flask(__name__)
CORS(app)
chain_data_fetcher = ChainDataFetcher()
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
