import csv
import json

miner_to_period = {}
miner_list = json.load(open("miner_list.json", "r"))
for miner in miner_list:
    miner_to_period[miner["address"]] = miner["active_period"]
for row in csv.reader(open("miner.csv")):
    addr = row[5][2:]
    print(miner_to_period[addr])