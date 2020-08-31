import threading

from flask import Flask, request
from utils.utils import setup_log, priv_to_pub, encode_hex
from flask_cors import CORS
import os
import json
import schedule

setup_log()
app = Flask(__name__)
CORS(app)


def parse_node_url(url: str):
    return url[10:138], url[139:].split(":")[0]


_lock = threading.Lock()
trusted_nodes_to_days = {}
trusted_nodes_to_ip = {}
nodes_dir = "trusted_nodes"


def update():
    _lock.acquire()
    for date_dir in os.listdir(nodes_dir):
        trusted_node_ids = set()
        for root, _, files in os.walk(os.path.join(nodes_dir, date_dir)):
            # In one day, a miner is regarded a trusted node if it appears at any node's trusted_nodes.
            for node_file in files:
                if node_file.endswith("trusted_nodes.json"):
                    with open(os.path.join(root, node_file), "r") as f:
                        trusted_nodes = json.load(f)
                        for node in trusted_nodes["nodes"]:
                            node_pub_key, ip = parse_node_url(node["url"])
                            trusted_node_ids.add(node_pub_key)
                            trusted_nodes_to_ip[node_pub_key] = ip
        # Count how many days these trusted_nodes have been
        for node_id in trusted_node_ids:
            trusted_nodes_to_days.setdefault(node_id, 0)
            trusted_nodes_to_days[node_id] += 1
    _lock.release()


update()
schedule.every().day.at("00:00").do(update)


@app.route('/node-status-from-net-key', methods=['GET'])
def node_status_from_net_key():
    prikey = request.args.get("key")
    try:
        node_id = encode_hex(priv_to_pub(prikey))
    except:
        print("Invalid key format: ", prikey)
        return []
    _lock.acquire()
    if node_id in trusted_nodes_to_days:
        r = json.dumps({
            "trusted_days": trusted_nodes_to_days[node_id],
            "address": trusted_nodes_to_ip[node_id],
        })
    else:
        r = json.dumps({
            "trusted_days": 0,
        })
    _lock.release()
    return r


@app.route('/trusted-node-ip-list', methods=['GET'])
def trusted_node_ip_list():
    _lock.acquire()
    ip_set = sorted(list(set(trusted_nodes_to_ip.values())))
    _lock.release()
    return json.dumps({
        "ip_list": ip_set
    })
