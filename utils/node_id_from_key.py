import sys
from utils import priv_to_pub, encode_hex

key = sys.argv[1]
print(encode_hex(priv_to_pub(key)))
