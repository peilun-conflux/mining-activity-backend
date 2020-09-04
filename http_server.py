import logging
import time
import sys
import os
from flask import Flask, request
from utils.utils import setup_log
from flask_cors import CORS
from xmlrpc.client import ServerProxy

setup_log()
app = Flask(__name__)
CORS(app)
LOCAL_PORT = os.getenv('LOCAL_PORT')
chain_data_fetcher = ServerProxy(f'http://localhost:{LOCAL_PORT}')


@app.route('/get-mined-block-timestamps', methods=['GET'])
def get_mined_block_timestamps():
    addr = request.args.get("address")
    return {
        "block_timestamps": chain_data_fetcher.miner_block_timestamps("0x"+addr)
    }


@app.route('/get-miner-list', methods=['GET'])
def get_miner_list():
    return chain_data_fetcher.miner_list()
