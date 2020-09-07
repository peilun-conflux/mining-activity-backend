import json
import logging
import os
import subprocess
import threading
import time
import traceback
from xmlrpc.server import SimpleXMLRPCServer

import schedule
import sqlitedict
from flask import request

from utils.utils import encode_hex, priv_to_pub, setup_log
UPDATE_INTERVAL_HOUR = 4

class NodeEndpoint:
    def __init__(self, node_id, ip, tcp_port, udp_port):
        self.node_id = node_id
        self.ip = ip
        self.tcp_port = tcp_port
        self.udp_port = udp_port

    @classmethod
    def from_url(cls, url: str):
        node_id = url[10:138]
        ip_port = url[139:].split(":")
        ip = ip_port[0]
        ports = ip_port[1].split("+")
        if len(ports) == 1:
            return cls(node_id, ip, ports[0], ports[0])
        else:
            return cls(node_id, ip, ports[0], ports[1])


def recover():
    if len(alive_node_db) == 0:
        return update()
    else:
        last_ts = min([float(i) for i in alive_node_db.keys()])
        for ts, alive_nodes in alive_node_db.items():
            ts = float(ts)
            _lock.acquire()
            nodes_map.update(alive_nodes)
            # Count how many days these trusted_nodes have been
            gap = max(0, ts - last_ts)
            for node_id in alive_nodes:
                trusted_nodes_time.setdefault(node_id, 0)
                trusted_nodes_time[node_id] += gap
            last_ts = ts
            _lock.release()
        return last_ts


def update():
    now = time.time()
    gap = now - global_last_ts
    nodes = get_node_set()
    node_db[now] = nodes
    alive_nodes = check_node_status(nodes)
    alive_node_db[now] = alive_nodes
    _lock.acquire()
    nodes_map.update(alive_nodes)
    # Count how many days these trusted_nodes have been
    for node_id in alive_nodes:
        trusted_nodes_time.setdefault(node_id, 0)
        trusted_nodes_time[node_id] += gap
    _lock.release()
    return now


def get_node_set():
    nodes = {}  # Map from id to NodeEndpoint
    for date_dir in os.listdir(nodes_dir):
        for root, _, files in os.walk(os.path.join(nodes_dir, date_dir)):
            # In one day, a miner is regarded a trusted node if it appears at any node's trusted_nodes.
            for node_file in files:
                if node_file.endswith("trusted_nodes.json"):
                    with open(os.path.join(root, node_file), "r") as f:
                        try:
                            trusted_nodes = json.load(f)
                        except Exception as e:
                            logger.warning(f"json load error: {root}, {node_file}")
                            continue
                        for node in trusted_nodes["nodes"]:
                            endpoint = NodeEndpoint.from_url(node["url"])
                            nodes[endpoint.node_id] = endpoint
    return nodes


def check_node_status(nodes):
    alive_nodes = {}
    for node in nodes.values():
        try:
            tcp_out = subprocess.run(["nc", "-vz", str(node.ip), str(node.tcp_port)],
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=3, text=True).stdout
        except Exception:
            logger.info(f"node {node.node_id} {node.ip} {node.tcp_port} error")
            logger.info(traceback.format_exc())
            continue
        if "succeeded" not in tcp_out:
            logger.info(f"node {node.node_id} {node.ip} {node.tcp_port} fail: {tcp_out}")
            continue
        ''' UDP check is inaccurate for now.
        udp_out = subprocess.check_output(["nc", "-vzu", str(node.ip), str(node.udp_port)],
                                          stderr=subprocess.STDOUT, timeout=5)
        if "success" not in udp_out:
            continue
        '''
        alive_nodes[node.node_id] = node
    return alive_nodes


def node_status_from_net_key(node_id):
    _lock.acquire()
    if node_id in trusted_nodes_time:
        r = json.dumps({
            "trusted_days": int(trusted_nodes_time[node_id] / 3600 / 24),
            "address": f"{nodes_map[node_id].ip}:{nodes_map[node_id].tpc_port}",
        })
    else:
        r = json.dumps({
            "trusted_days": 0,
        })
    _lock.release()
    return r


def trusted_node_ip_list():
    _lock.acquire()
    ip_set = set()
    for node in nodes_map.values():
        ip_set.add(node.ip)
    ip_list = sorted(list(ip_set))
    _lock.release()
    return json.dumps({
        "ip_list": ip_list
    })


def trusted_node_list():
    _lock.acquire()
    data = []
    for node_id in trusted_nodes_time:
        data.append({
            "pubkey": node_id,
            "ip": nodes_map[node_id].ip,
            "active_period": trusted_nodes_time[node_id],
        })
    _lock.release()
    return json.dumps({
        "data": data,
    })


def start_rpc_server():
    server = SimpleXMLRPCServer(('localhost', LOCAL_PORT), logRequests=True)
    server.register_function(node_status_from_net_key)
    server.register_function(trusted_node_ip_list)
    server.register_function(trusted_node_list)
    server.serve_forever()


def periodic_run():
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    setup_log()
    nodes_dir = "trusted_nodes"
    logger = logging.getLogger("node_server")
    # Map from timestamp to all trusted_nodes
    node_db = sqlitedict.SqliteDict("node.db", tablename="all", autocommit=True)
    alive_node_db = sqlitedict.SqliteDict("node.db", tablename="alive", autocommit=True)

    trusted_nodes_time = {}
    nodes_map = {}
    _lock = threading.Lock()

    global_last_ts = time.time()
    global_last_ts = recover()
    schedule.every(UPDATE_INTERVAL_HOUR).hours.do(update)
    threading.Thread(target=periodic_run, daemon=True).start()

    LOCAL_PORT = 9002
    PUBLIC_PORT = 4002
    os.environ["LOCAL_PORT"] = str(LOCAL_PORT)
    subprocess.Popen(["uwsgi", "--http", f"0.0.0.0:{PUBLIC_PORT}", "--module", "trust_node_server:app"])
    start_rpc_server()
