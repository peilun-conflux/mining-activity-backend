import csv
import json

miner_to_period = {}
miner_list = json.load(open("miner_list.json", "r"))
for miner in miner_list:
    miner_to_period[miner["address"]] = miner["active_period"]
first = True
for row in csv.reader(open("miner.csv")):
    if first:
        first = False
        continue
    addr = row[3][2:].lower()
    if addr in miner_to_period:
        print(miner_to_period[addr] + 1)
    else:
        print(0)
