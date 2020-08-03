import csv
import json

miner_to_period_and_count = {}
miner_list = json.load(open("miner_list.json", "r"))
for miner in miner_list:
    miner_to_period_and_count[miner["address"]] = (miner["active_period"], miner["block_count"])
first = True
active_periods = []
mined_blocks = []
for row in csv.reader(open("miner.csv")):
    if first:
        first = False
        continue
    raw_addr = row[14].lower()
    if raw_addr.startswith("0x"):
        addr = raw_addr[2:]
    else:
        addr = raw_addr
    if addr in miner_to_period_and_count:
        active_periods.append(miner_to_period_and_count[addr][0] + 1)
        mined_blocks.append(miner_to_period_and_count[addr][1])
    else:
        active_periods.append(0)
        mined_blocks.append(0)
print("active_periods:")
for i in active_periods:
    print(i)
print("mined_blocks")
for i in mined_blocks:
    print(i)
