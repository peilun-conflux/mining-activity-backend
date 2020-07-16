import csv
import json

from utils.utils import priv_to_pub, encode_hex


def parse_pubkey_in_url(url: str):
    return url[10:138]


trusted_addr = set()
trusted_nodes = json.load(open("net_config/trusted_nodes.json", "r"))
for node in trusted_nodes["nodes"]:
    node_pub_key = parse_pubkey_in_url(node["url"])
    trusted_addr.add(node_pub_key)
first = True
for row in csv.reader(open("miner.csv")):
    if first:
        first = False
        continue
    addr = row[5][2:]
    pubkey = row[6]
    try:
        if encode_hex(priv_to_pub(pubkey)) in trusted_addr:
            print(True)
        else:
            print(False)
    except Exception as _e:
        print(False)
