import os
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

_w3_instance = None

def get_provider() -> Web3:
    global _w3_instance
    if _w3_instance is None:
        rpc_url = os.getenv("SEPOLIA_RPC_URL", "https://ethereum-sepolia-rpc.publicnode.com")
        _w3_instance = Web3(Web3.HTTPProvider(rpc_url))
    return _w3_instance

def is_connected() -> bool:
    return get_provider().is_connected()

def get_eth_balance(address: str) -> float:
    w3 = get_provider()
    checksum_address = w3.to_checksum_address(address)
    balance_wei = w3.eth.get_balance(checksum_address)
    return float(w3.from_wei(balance_wei, "ether"))

def get_gas_price() -> float:
    w3 = get_provider()
    gas_price_wei = w3.eth.gas_price
    return float(w3.from_wei(gas_price_wei, "gwei"))
