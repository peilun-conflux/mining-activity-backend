import csv
import json
import os

from utils.utils import priv_to_pub, encode_hex


def parse_pubkey_in_url(url: str):
    return url[10:138]


trusted_nodes_to_days = {}
nodes_dir = "trusted_nodes"
for date_dir in os.listdir(nodes_dir):
    trusted_node_ids = set()
    for root, _, files in os.walk(os.path.join(nodes_dir, date_dir)):
        # In one day, a miner is regarded a trusted node if it appears at any node's trusted_nodes.
        for node_file in files:
            if node_file.endswith("trusted_nodes.json"):
                with open(os.path.join(root, node_file), "r") as f:
                    trusted_nodes = json.load(f)
                    for node in trusted_nodes["nodes"]:
                        node_pub_key = parse_pubkey_in_url(node["url"])
                        trusted_node_ids.add(node_pub_key)
    # Count how many days these trusted_nodes have been
    for node_id in trusted_node_ids:
        trusted_nodes_to_days.setdefault(node_id, 0)
        trusted_nodes_to_days[node_id] += 1
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
        print(node_id, pubkey)
        if node_id in trusted_nodes_to_days:
            final_trust_nodes.append(trusted_nodes_to_days[node_id])
        else:
            final_trust_nodes.append(0)
    except Exception as _e:
        final_trust_nodes.append(0)
for i in final_trust_nodes:
    print(i)
