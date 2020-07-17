import datetime
import inspect
import logging
import re
import sys
import time

import sha3 as _sha3
from py_ecc.secp256k1 import privtopub, ecdsa_raw_sign, ecdsa_raw_recover
import rlp
from rlp.sedes import big_endian_int, BigEndianInt, Binary
from eth_utils import encode_hex as encode_hex_0x
from eth_utils import decode_hex, int_to_big_endian, big_endian_to_int
from rlp.utils import ALL_BYTES
import random
import coincurve

logger = logging.getLogger("utils")

# Assert functions
##################


def assert_fee_amount(fee, tx_size, fee_per_kB):
    """Assert the fee was in range"""
    target_fee = round(tx_size * fee_per_kB / 1000, 8)
    if fee < target_fee:
        raise AssertionError("Fee of %s BTC too low! (Should be %s BTC)" %
                             (str(fee), str(target_fee)))
    # allow the wallet's estimation to be at most 2 bytes off
    if fee > (tx_size + 2) * fee_per_kB / 1000:
        raise AssertionError("Fee of %s BTC too high! (Should be %s BTC)" %
                             (str(fee), str(target_fee)))


def assert_equal(thing1, thing2, *args):
    if thing1 != thing2 or any(thing1 != arg for arg in args):
        raise AssertionError("not(%s)" % " == ".join(
            str(arg) for arg in (thing1, thing2) + args))


def assert_greater_than(thing1, thing2):
    if thing1 <= thing2:
        raise AssertionError("%s <= %s" % (str(thing1), str(thing2)))


def assert_greater_than_or_equal(thing1, thing2):
    if thing1 < thing2:
        raise AssertionError("%s < %s" % (str(thing1), str(thing2)))


def assert_is_hex_string(string):
    try:
        int(string, 16)
    except Exception as e:
        raise AssertionError(
            "Couldn't interpret %r as hexadecimal; raised: %s" % (string, e))


def assert_is_hash_string(string, length=64):
    if not isinstance(string, str):
        raise AssertionError("Expected a string, got type %r" % type(string))

    if string.startswith("0x"):
        string = string[2:]

    if length and len(string) != length:
        raise AssertionError(
            "String of length %d expected; got %d" % (length, len(string)))

    if not re.match('[abcdef0-9]+$', string):
        raise AssertionError(
            "String %r contains invalid characters for a hash." % string)


def assert_array_result(object_array,
                        to_match,
                        expected,
                        should_not_find=False):
    """
        Pass in array of JSON objects, a dictionary with key/value pairs
        to match against, and another dictionary with expected key/value
        pairs.
        If the should_not_find flag is true, to_match should not be found
        in object_array
        """
    if should_not_find:
        assert_equal(expected, {})
    num_matched = 0
    for item in object_array:
        all_match = True
        for key, value in to_match.items():
            if item[key] != value:
                all_match = False
        if not all_match:
            continue
        elif should_not_find:
            num_matched = num_matched + 1
        for key, value in expected.items():
            if item[key] != value:
                raise AssertionError(
                    "%s : expected %s=%s" % (str(item), str(key), str(value)))
            num_matched = num_matched + 1
    if num_matched == 0 and not should_not_find:
        raise AssertionError("No objects matched %s" % (str(to_match)))
    if num_matched > 0 and should_not_find:
        raise AssertionError("Objects were found %s" % (str(to_match)))


def pubsub_url(host="127.0.0.1", port=12535):
    return "ws://%s:%d" % (host, int(port))


def http_rpc_url(host="127.0.0.1", port=12537):
    return "http://%s:%d" % (host, int(port))


def checktx(node, tx_hash):
    return node.cfx_getTransactionReceipt(tx_hash) is not None


def wait_until(predicate,
               *,
               attempts=float('inf'),
               timeout=float('inf'),
               lock=None):
    if attempts == float('inf') and timeout == float('inf'):
        timeout = 60
    attempt = 0
    time_end = time.time() + timeout

    while attempt < attempts and time.time() < time_end:
        if lock:
            with lock:
                if predicate():
                    return
        else:
            if predicate():
                return
        attempt += 1
        time.sleep(0.5)

    # Print the cause of the timeout
    predicate_source = inspect.getsourcelines(predicate)
    logger.error("wait_until() failed. Predicate: {}".format(predicate_source))
    if attempt >= attempts:
        raise AssertionError("Predicate {} not true after {} attempts".format(
            predicate_source, attempts))
    elif time.time() >= time_end:
        raise AssertionError("Predicate {} not true after {} seconds".format(
            predicate_source, timeout))
    raise RuntimeError('Unreachable')


def setup_log():
    fh = logging.FileHandler("server.log")
    ch = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt=
        '%(asctime)s.%(msecs)03dZ %(name)s %(process)d %(thread)d (%(levelname)s): %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    ch.setLevel("INFO")
    fh.setLevel("DEBUG")
    logging.root.addHandler(ch)
    logging.root.addHandler(fh)
    logging.root.setLevel("DEBUG")



def sha3_256(x): return _sha3.keccak_256(x).digest()


class Memoize:
    def __init__(self, fn):
        self.fn = fn
        self.memo = {}

    def __call__(self, *args):
        if args not in self.memo:
            self.memo[args] = self.fn(*args)
        return self.memo[args]


TT256 = 2 ** 256
TT256M1 = 2 ** 256 - 1
TT255 = 2 ** 255
SECP256K1P = 2 ** 256 - 4294968273


def is_numeric(x): return isinstance(x, int)


def is_string(x): return isinstance(x, bytes)


def to_string(value):
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return bytes(value, 'utf-8')
    if isinstance(value, int):
        return bytes(str(value), 'utf-8')


def int_to_bytes(value):
    if isinstance(value, bytes):
        return value
    return int_to_big_endian(value)


def to_string_for_regexp(value):
    return str(to_string(value), 'utf-8')


unicode = str


def bytearray_to_bytestr(value):
    return bytes(value)


def encode_int32(v):
    return v.to_bytes(32, byteorder='big')


def bytes_to_int(value):
    return int.from_bytes(value, byteorder='big')


def str_to_bytes(value):
    if isinstance(value, bytearray):
        value = bytes(value)
    if isinstance(value, bytes):
        return value
    return bytes(value, 'utf-8')


def ascii_chr(n):
    return ALL_BYTES[n]


def encode_hex(n):
    if isinstance(n, str):
        return encode_hex(n.encode('ascii'))
    return encode_hex_0x(n)[2:]


def ecrecover_to_pub(rawhash, v, r, s):
    if coincurve and hasattr(coincurve, "PublicKey"):
        try:
            pk = coincurve.PublicKey.from_signature_and_message(
                zpad(bytearray_to_bytestr(int_to_32bytearray(r)), 32) + zpad(
                    bytearray_to_bytestr(int_to_32bytearray(s)), 32) +
                ascii_chr(v - 27),
                rawhash,
                hasher=None,
            )
            pub = pk.format(compressed=False)[1:]
            x, y = pk.point()
        except BaseException:
            x, y = 0, 0
            pub = b"\x00" * 64
    else:
        result = ecdsa_raw_recover(rawhash, (v, r, s))
        if result:
            x, y = result
            pub = encode_int32(x) + encode_int32(y)
        else:
            raise ValueError('Invalid VRS')
    assert len(pub) == 64
    return pub, x, y


def ecsign(rawhash, key):
    if coincurve and hasattr(coincurve, 'PrivateKey'):
        pk = coincurve.PrivateKey(key)
        signature = pk.sign_recoverable(rawhash, hasher=None)
        v = safe_ord(signature[64]) + 27
        r = big_endian_to_int(signature[0:32])
        s = big_endian_to_int(signature[32:64])
    else:
        v, r, s = ecdsa_raw_sign(rawhash, key)
    return v, r, s


def ec_random_keys():
    priv_key = random.randint(0, 2 ** 256).to_bytes(32, "big")
    pub_key = privtopub(priv_key)
    return priv_key, pub_key


def convert_to_nodeid(signature, challenge):
    r = big_endian_to_int(signature[:32])
    s = big_endian_to_int(signature[32:64])
    v = big_endian_to_int(signature[64:]) + 27
    signed = int_to_bytes(challenge)
    h_signed = sha3_256(signed)
    return ecrecover_to_pub(h_signed, v, r, s)


def get_nodeid(node):
    challenge = random.randint(0, 2 ** 32 - 1)
    signature = node.getnodeid(list(int_to_bytes(challenge)))
    return convert_to_nodeid(signature, challenge)


def mk_contract_address(sender, nonce):
    return sha3(rlp.encode([normalize_address(sender), nonce]))[12:]


def mk_metropolis_contract_address(sender, initcode):
    return sha3(normalize_address(sender) + initcode)[12:]


def safe_ord(value):
    if isinstance(value, int):
        return value
    else:
        return ord(value)


# decorator


def debug(label):
    def deb(f):
        def inner(*args, **kwargs):
            i = random.randrange(1000000)
            print(label, i, 'start', args)
            x = f(*args, **kwargs)
            print(label, i, 'end', x)
            return x

        return inner

    return deb


def flatten(li):
    o = []
    for l in li:
        o.extend(l)
    return o


def bytearray_to_int(arr):
    o = 0
    for a in arr:
        o = (o << 8) + a
    return o


def int_to_32bytearray(i):
    o = [0] * 32
    for x in range(32):
        o[31 - x] = i & 0xff
        i >>= 8
    return o


# sha3_count = [0]


def sha3(seed):
    return sha3_256(to_string(seed))


assert encode_hex(sha3(b'')) == 'c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470'
assert encode_hex(sha3(b'\x00' * 256)) == 'd397b3b043d87fcd6fad1291ff0bfd16401c274896d8c63a923727f077b8e0b5'


@Memoize
def priv_to_addr(k):
    k = normalize_key(k)
    x, y = privtopub(k)
    addr = bytearray(sha3(encode_int32(x) + encode_int32(y))[12:])
    addr[0] &= 0x0f
    addr[0] |= 0x10
    return bytes(addr)


def priv_to_pub(k):
    k = normalize_key(k)
    x, y = privtopub(k)
    return bytes(encode_int32(x) + encode_int32(y))


def pub_to_addr(k):
    x = big_endian_to_int(decode_hex(k[2:34]))
    y = big_endian_to_int(decode_hex(k[34:66]))
    addr = sha3(encode_int32(x) + encode_int32(y))[12:]
    addr[0] &= 0x0f
    addr[0] |= 0x10
    return bytes(addr)


def checksum_encode(addr):  # Takes a 20-byte binary address as input
    addr = normalize_address(addr)
    o = ''
    v = big_endian_to_int(sha3(encode_hex(addr)))
    for i, c in enumerate(encode_hex(addr)):
        if c in '0123456789':
            o += c
        else:
            o += c.upper() if (v & (2 ** (255 - 4 * i))) else c.lower()
    return '0x' + o


def check_checksum(addr):
    return checksum_encode(normalize_address(addr)) == addr


def normalize_address(x, allow_blank=False):
    if is_numeric(x):
        return int_to_addr(x)
    if allow_blank and x in {'', b''}:
        return b''
    if len(x) in (42, 50) and x[:2] in {'0x', b'0x'}:
        x = x[2:]
    if len(x) in (40, 48):
        x = decode_hex(x)
    if len(x) == 24:
        assert len(x) == 24 and sha3(x[:20])[:4] == x[-4:]
        x = x[:20]
    if len(x) != 20:
        raise Exception("Invalid address format: %r" % x)
    return x


def normalize_key(key):
    if is_numeric(key):
        o = encode_int32(key)
    elif len(key) == 32:
        o = key
    elif len(key) == 64:
        o = decode_hex(key)
    elif len(key) == 66 and key[:2] == '0x':
        o = decode_hex(key[2:])
    else:
        raise Exception("Invalid key format: %r" % key)
    if o == b'\x00' * 32:
        raise Exception("Zero privkey invalid")
    return o


def zpad(x, l):
    """ Left zero pad value `x` at least to length `l`.

    >>> zpad('', 1)
    '\x00'
    >>> zpad('\xca\xfe', 4)
    '\x00\x00\xca\xfe'
    >>> zpad('\xff', 1)
    '\xff'
    >>> zpad('\xca\xfe', 2)
    '\xca\xfe'
    """
    return b'\x00' * max(0, l - len(x)) + x


def rzpad(value, total_length):
    """ Right zero pad value `x` at least to length `l`.

    >>> zpad('', 1)
    '\x00'
    >>> zpad('\xca\xfe', 4)
    '\xca\xfe\x00\x00'
    >>> zpad('\xff', 1)
    '\xff'
    >>> zpad('\xca\xfe', 2)
    '\xca\xfe'
    """
    return value + b'\x00' * max(0, total_length - len(value))


def int_to_addr(x):
    o = [b''] * 20
    for i in range(20):
        o[19 - i] = ascii_chr(x & 0xff)
        x >>= 8
    return b''.join(o)


def coerce_addr_to_bin(x):
    if is_numeric(x):
        return encode_hex(zpad(big_endian_int.serialize(x), 20))
    elif len(x) == 40 or len(x) == 0:
        return decode_hex(x)
    else:
        return zpad(x, 20)[-20:]


def coerce_addr_to_hex(x):
    if is_numeric(x):
        return encode_hex(zpad(big_endian_int.serialize(x), 20))
    elif len(x) == 40 or len(x) == 0:
        return x
    else:
        return encode_hex(zpad(x, 20)[-20:])


def coerce_to_int(x):
    if is_numeric(x):
        return x
    elif len(x) == 40:
        return big_endian_to_int(decode_hex(x))
    else:
        return big_endian_to_int(x)


def coerce_to_bytes(x):
    if is_numeric(x):
        return big_endian_int.serialize(x)
    elif len(x) == 40:
        return decode_hex(x)
    else:
        return x


def parse_int_or_hex(s):
    if is_numeric(s):
        return s
    elif s[:2] in (b'0x', '0x'):
        s = to_string(s)
        tail = (b'0' if len(s) % 2 else b'') + s[2:]
        return big_endian_to_int(decode_hex(tail))
    else:
        return int(s)


def ceil32(x):
    return x if x % 32 == 0 else x + 32 - (x % 32)


def to_signed(i):
    return i if i < TT255 else i - TT256


def sha3rlp(x):
    return sha3(rlp.encode(x))


# Format encoders/decoders for bin, addr, int


def decode_bin(v):
    """decodes a bytearray from serialization"""
    if not is_string(v):
        raise Exception("Value must be binary, not RLP array")
    return v


def decode_addr(v):
    """decodes an address from serialization"""
    if len(v) not in [0, 20]:
        raise Exception("Serialized addresses must be empty or 20 bytes long!")
    return encode_hex(v)


def decode_int(v):
    """decodes and integer from serialization"""
    if len(v) > 0 and (v[0] == b'\x00' or v[0] == 0):
        raise Exception("No leading zero bytes allowed for integers")
    return big_endian_to_int(v)


def decode_int256(v):
    return big_endian_to_int(v)


def encode_bin(v):
    """encodes a bytearray into serialization"""
    return v


def encode_root(v):
    """encodes a trie root into serialization"""
    return v


def encode_int(v):
    """encodes an integer into serialization"""
    if not is_numeric(v) or v < 0 or v >= TT256:
        raise Exception("Integer invalid or out of range: %r" % v)
    return int_to_big_endian(v)


def encode_int256(v):
    return zpad(int_to_big_endian(v), 256)


def scan_bin(v):
    if v[:2] in ('0x', b'0x'):
        return decode_hex(v[2:])
    else:
        return decode_hex(v)


def scan_int(v):
    if v[:2] in ('0x', b'0x'):
        return big_endian_to_int(decode_hex(v[2:]))
    else:
        return int(v)


# Decoding from RLP serialization
decoders = {
    "bin": decode_bin,
    "addr": decode_addr,
    "int": decode_int,
    "int256b": decode_int256,
}

# Encoding to RLP serialization
encoders = {
    "bin": encode_bin,
    "int": encode_int,
    "trie_root": encode_root,
    "int256b": encode_int256,
}

# Encoding to printable format
printers = {
    "bin": lambda v: '0x' + encode_hex(v),
    "addr": lambda v: v,
    "int": lambda v: to_string(v),
    "trie_root": lambda v: encode_hex(v),
    "int256b": lambda x: encode_hex(zpad(encode_int256(x), 256))
}

# Decoding from printable format
scanners = {
    "bin": scan_bin,
    "addr": lambda x: x[2:] if x[:2] in (b'0x', '0x') else x,
    "int": scan_int,
    "trie_root": lambda x: scan_bin,
    "int256b": lambda x: big_endian_to_int(decode_hex(x))
}


def int_to_hex(x):
    o = encode_hex(encode_int(x))
    return '0x' + (o[1:] if (len(o) > 0 and o[0] == b'0') else o)


def remove_0x_head(s):
    return s[2:] if s[:2] in (b'0x', '0x') else s


def parse_as_bin(s):
    return decode_hex(s[2:] if s[:2] == '0x' else s)


def parse_as_int(s):
    return s if is_numeric(s) else int(
        '0' + s[2:], 16) if s[:2] == '0x' else int(s)


def print_func_call(ignore_first_arg=False, max_call_number=100):
    """ utility function to facilitate debug, it will print input args before
    function call, and print return value after function call

    usage:

        @print_func_call
        def some_func_to_be_debu():
            pass

    :param ignore_first_arg: whether print the first arg or not.
    useful when ignore the `self` parameter of an object method call
    """
    from functools import wraps

    def display(x):
        x = to_string(x)
        try:
            x.decode('ascii')
        except BaseException:
            return 'NON_PRINTABLE'
        return x

    local = {'call_number': 0}

    def inner(f):

        @wraps(f)
        def wrapper(*args, **kwargs):
            local['call_number'] += 1
            tmp_args = args[1:] if ignore_first_arg and len(args) else args
            this_call_number = local['call_number']
            print(('{0}#{1} args: {2}, {3}'.format(
                f.__name__,
                this_call_number,
                ', '.join([display(x) for x in tmp_args]),
                ', '.join(display(key) + '=' + to_string(value)
                          for key, value in kwargs.items())
            )))
            res = f(*args, **kwargs)
            print(('{0}#{1} return: {2}'.format(
                f.__name__,
                this_call_number,
                display(res))))

            if local['call_number'] > 100:
                raise Exception("Touch max call number!")
            return res

        return wrapper

    return inner


def dump_state(trie):
    res = ''
    for k, v in list(trie.to_dict().items()):
        res += '%r:%r\n' % (encode_hex(k), encode_hex(v))
    return res


class Denoms():

    def __init__(self):
        self.wei = 1
        self.babbage = 10 ** 3
        self.ada = 10 ** 3
        self.kwei = 10 ** 3
        self.lovelace = 10 ** 6
        self.mwei = 10 ** 6
        self.shannon = 10 ** 9
        self.gwei = 10 ** 9
        self.szabo = 10 ** 12
        self.finney = 10 ** 15
        self.mether = 10 ** 15
        self.ether = 10 ** 18
        self.turing = 2 ** 256 - 1


denoms = Denoms()

address = Binary.fixed_length(20, allow_empty=True)
int20 = BigEndianInt(20)
int32 = BigEndianInt(32)
int256 = BigEndianInt(256)
hash32 = Binary.fixed_length(32)
hash20 = Binary.fixed_length(20)
trie_root = Binary.fixed_length(32, allow_empty=True)


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[91m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def parse_date(s):
    return time.mktime(datetime.datetime.strptime(s, "%H:%M-%d/%m/%Y").timetuple())
