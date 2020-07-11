import os
import eth_utils
import rlp
from .utils import *

class RpcClient:
    def __init__(self, node=None):
        self.node = node

        # epoch definitions
        self.EPOCH_EARLIEST = "earliest"
        self.EPOCH_LATEST_MINED = "latest_mined"
        self.EPOCH_LATEST_STATE = "latest_state"
        self.EPOCH_LATEST_CONFIRMED = "latest_confirmed"

        # update node operations
        self.UPDATE_NODE_OP_FAILURE = "Failure"
        self.UPDATE_NODE_OP_DEMOTE = "Demotion"
        self.UPDATE_NODE_OP_REMOVE = "Remove"

        # hash/address definitions
        self.ZERO_HASH = eth_utils.encode_hex(b'\x00' * 32)

        # default tx values
        self.DEFAULT_TX_GAS_PRICE = 1
        self.DEFAULT_TX_GAS = 21000
        self.DEFAULT_TX_FEE = self.DEFAULT_TX_GAS_PRICE * self.DEFAULT_TX_GAS

    def EPOCH_NUM(self, num: int) -> str:
        return hex(num)

    def get_storage_at(self, addr: str, pos: str, epoch: str = None) -> str:
        assert_is_hash_string(addr, length=40)
        assert_is_hash_string(pos)

        if epoch is None:
            res = self.node.cfx_getStorageAt(addr, pos)
        else:
            res = self.node.cfx_getStorageAt(addr, pos, epoch)

        return res

    def get_storage_root(self, addr: str, epoch: str = None) -> str:
        assert_is_hash_string(addr, length=40)

        if epoch is None:
            res = self.node.cfx_getStorageRoot(addr)
        else:
            res = self.node.cfx_getStorageRoot(addr, epoch)

        return res

    def get_code(self, address: str, epoch: str = None) -> str:
        if epoch is None:
            code = self.node.cfx_getCode(address)
        else:
            code = self.node.cfx_getCode(address, epoch)
        assert_is_hex_string(code)
        return code

    def gas_price(self) -> int:
        return int(self.node.cfx_gasPrice(), 0)

    def get_block_reward_info(self, epoch: str):
        return self.node.cfx_getBlockRewardInfo(epoch)

    def epoch_number(self, epoch: str = None) -> int:
        if epoch is None:
            return int(self.node.cfx_epochNumber(), 0)
        else:
            return int(self.node.cfx_epochNumber(epoch), 0)

    def get_balance(self, addr: str, epoch: str = None) -> int:
        if epoch is None:
            return int(self.node.cfx_getBalance(addr), 0)
        else:
            return int(self.node.cfx_getBalance(addr, epoch), 0)

    def get_staking_balance(self, addr: str, epoch: str = None) -> int:
        if epoch is None:
            return int(self.node.cfx_getStakingBalance(addr), 0)
        else:
            return int(self.node.cfx_getStakingBalance(addr, epoch), 0)

    def get_collateral_for_storage(self, addr: str, epoch: str = None) -> int:
        if epoch is None:
            return int(self.node.cfx_getCollateralForStorage(addr), 0)
        else:
            return int(self.node.cfx_getCollateralForStorage(addr, epoch), 0)

    def get_sponsor_info(self, addr: str, epoch: str = None) -> dict:
        if epoch is None:
            return self.node.cfx_getSponsorInfo(addr)
        else:
            return self.node.cfx_getSponsorInfo(addr, epoch)

    def get_sponsor_for_gas(self, addr: str, epoch: str = None) -> str:
        return self.get_sponsor_info(addr, epoch)['sponsorForGas']

    def get_sponsor_for_collateral(self, addr: str, epoch: str = None) -> str:
        return self.get_sponsor_info(addr, epoch)['sponsorForCollateral']

    def get_sponsor_balance_for_collateral(self, addr: str, epoch: str = None) -> int:
        return int(self.get_sponsor_info(addr, epoch)['sponsorBalanceForCollateral'], 0)

    def get_sponsor_balance_for_gas(self, addr: str, epoch: str = None) -> int:
        return int(self.get_sponsor_info(addr, epoch)['sponsorBalanceForGas'], 0)

    def get_sponsor_gas_bound(self, addr: str, epoch: str = None) -> int:
        return int(self.get_sponsor_info(addr, epoch)['sponsorGasBound'], 0)

    def get_admin(self, addr: str, epoch: str = None) -> str:
        if epoch is None:
            return self.node.cfx_getAdmin(addr)
        else:
            return self.node.cfx_getAdmin(addr, epoch)

    ''' Ignore block_hash if epoch is not None '''
    def get_nonce(self, addr: str, epoch: str = None, block_hash: str = None) -> int:
        if epoch is None and block_hash is None:
            return int(self.node.cfx_getNextNonce(addr), 0)
        elif epoch is None:
            return int(self.node.cfx_getNextNonce(addr, "hash:"+block_hash), 0)
        else:
            return int(self.node.cfx_getNextNonce(addr, epoch), 0)

    def send_raw_tx(self, raw_tx: str, wait_for_catchup=True) -> str:
        # We wait for the node out of the catch up mode first
        if wait_for_catchup:
            self.node.wait_for_phase(["NormalSyncPhase"])
        tx_hash = self.node.cfx_sendRawTransaction(raw_tx)
        assert_is_hash_string(tx_hash)
        return tx_hash

    def clear_tx_pool(self):
        self.node.clear_tx_pool()

    def send_usable_genesis_accounts(self, account_start_index:int):
        self.node.test_sendUsableGenesisAccounts(account_start_index)

    def wait_for_receipt(self, tx_hash: str, num_txs=1, timeout=10, state_before_wait=True):
        if state_before_wait:
            self.generate_blocks_to_state(num_txs=num_txs)

        def check_tx():
            self.generate_block(num_txs)
            return checktx(self.node, tx_hash)
        wait_until(check_tx, timeout=timeout)

    def block_by_hash(self, block_hash: str, include_txs: bool = False) -> dict:
        return self.node.cfx_getBlockByHash(block_hash, include_txs)

    def block_by_epoch(self, epoch: str, include_txs: bool = False) -> dict:
        return self.node.cfx_getBlockByEpochNumber(epoch, include_txs)

    def best_block_hash(self) -> str:
        return self.node.cfx_getBestBlockHash()

    def get_tx(self, tx_hash: str) -> dict:
        return self.node.cfx_getTransactionByHash(tx_hash)

    def block_hashes_by_epoch(self, epoch: str) -> list:
        blocks = self.node.cfx_getBlocksByEpoch(epoch)
        for b in blocks:
            assert_is_hash_string(b)
        return blocks

    def get_peers(self) -> list:
        return self.node.getpeerinfo()

    def get_peer(self, node_id: str):
        for p in self.get_peers():
            if p["nodeid"] == node_id:
                return p

        return None

    def get_node(self, node_id: str):
        return self.node.net_node(node_id)

    def add_node(self, node_id: str, ip: str, port: int):
        self.node.addnode(node_id, "{}:{}".format(ip, port))

    def disconnect_peer(self, node_id: str, node_op:str=None) -> int:
        return self.node.net_disconnect_node(node_id, node_op)

    def chain(self) -> list:
        return self.node.cfx_getChain()

    def get_transaction_receipt(self, tx_hash: str) -> dict:
        assert_is_hash_string(tx_hash)
        return self.node.cfx_getTransactionReceipt(tx_hash)

    def txpool_status(self) -> (int, int):
        status = self.node.txpool_status()
        return (status["deferred"], status["ready"])

    def estimate_gas(self, contract_addr:str, data_hex:str, sender:str=None, nonce:int=None) -> int:
        tx = self.new_tx_for_call(contract_addr, data_hex, sender=sender, nonce=nonce)
        response = self.node.cfx_estimateGasAndCollateral(tx)
        return int(response['gasUsed'], 0)

    def estimate_collateral(self, contract_addr:str, data_hex:str, sender:str=None, nonce:int=None) -> int:
        tx = self.new_tx_for_call(contract_addr, data_hex, sender=sender, nonce=nonce)
        if contract_addr == "0x":
            del tx['to']
        if sender is None:
            del tx['from']
        response = self.node.cfx_estimateGasAndCollateral(tx)
        return response['storageCollateralized']

    def check_balance_against_transaction(self, account_addr: str, contract_addr: str, gas_limit: int, gas_price: int, storage_limit: int) -> dict:
        return self.node.cfx_checkBalanceAgainstTransaction(account_addr, contract_addr, hex(gas_limit), hex(gas_price), hex(storage_limit))

    def call(self, contract_addr:str, data_hex:str, nonce=None, epoch:str=None) -> str:
        tx = self.new_tx_for_call(contract_addr, data_hex, nonce=nonce)
        if epoch is None:
            return self.node.cfx_call(tx)
        else:
            return self.node.cfx_call(tx, epoch)
