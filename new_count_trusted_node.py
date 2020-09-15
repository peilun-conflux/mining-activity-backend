import csv
import json
import os

from utils.utils import priv_to_pub, encode_hex


def parse_pubkey_in_url(url: str):
    return url[10:138]


trusted_nodes_to_seconds = {}
nodes_file = "trusted_node_list.json"
with open(nodes_file, "r") as f:
    nodes = json.load(f)["data"]
    for node in nodes:
        trusted_nodes_to_seconds[node["pubkey"]] = float(node["active_period"])
first = True
final_trust_nodes = []
for row in csv.reader(open("miner.csv")):
    if first:
        first = False
        continue
    node_id = row[14][2:].lower()
    pubkey = row[15]
    try:
        node_id = encode_hex(priv_to_pub(pubkey))
        # print(node_id, pubkey)
        if node_id in trusted_nodes_to_seconds:
            final_trust_nodes.append(trusted_nodes_to_seconds[node_id])
        else:
            final_trust_nodes.append(0)
    except Exception as _e:
        final_trust_nodes.append(0)
for i in final_trust_nodes:
    print(i)
