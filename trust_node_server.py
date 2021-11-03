import logging
import threading
from xmlrpc.client import ServerProxy

from flask import Flask, request
from utils.utils import setup_log, priv_to_pub, encode_hex
from flask_cors import CORS
import os


setup_log()
app = Flask(__name__)
CORS(app)
LOCAL_PORT = os.getenv('LOCAL_PORT')
node_status_fetcher = ServerProxy(f'http://localhost:{LOCAL_PORT}')


@app.route('/node-status-from-net-key', methods=['GET'])
def node_status_from_net_key():
    prikey = request.args.get("key")
    try:
        node_id = encode_hex(priv_to_pub(prikey))
    except:
        print("Invalid key format: ", prikey)
        return "{}"
    return node_status_fetcher.node_status_from_net_key(node_id)


@app.route('/trusted-node-ip-list', methods=['GET'])
def trusted_node_ip_list():
    return node_status_fetcher.trusted_node_ip_list()


@app.route('/trusted-node-list', methods=['GET'])
def trusted_node_list():
    return node_status_fetcher.trusted_node_list()


@app.route('/alive-node-ip-list', methods=['GET'])
def alive_node_ip_list():
    return node_status_fetcher.alive_node_ip_list()