import json
from utils.utils import priv_to_pub, encode_hex


def parse_pubkey_in_url(url: str):
    return url[10:138]


pri_key = "ab17c05f04dfbdf502f73fa1ec59c617e894d5c1af38f23689598d3f8fd3ed62"
pub_key = encode_hex(priv_to_pub(pri_key))
trusted_addr = []
trusted_nodes = json.load(open("net_config/trusted_nodes.json", "r"))
for node in trusted_nodes["nodes"]:
    node_pub_key = parse_pubkey_in_url(node["url"])
    if node_pub_key == pub_key:
        trusted_addr.append(pub_key)
print(trusted_addr)