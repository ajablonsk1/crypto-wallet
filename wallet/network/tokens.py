from web3 import Web3

from wallet.network.provider import get_provider

# Minimal ERC-20 ABI required for reading token info and balances
ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
]

_tracked_tokens = []

def get_token_contract(contract_address: str):
    w3 = get_provider()
    checksum_address = w3.to_checksum_address(contract_address)
    return w3.eth.contract(address=checksum_address, abi=ERC20_ABI)

def get_token_info(token_contract_address: str) -> dict:
    contract = get_token_contract(token_contract_address)
    try:
        name = contract.functions.name().call()
        symbol = contract.functions.symbol().call()
        decimals = contract.functions.decimals().call()
        return {
            "name": name,
            "symbol": symbol,
            "decimals": decimals
        }
    except Exception as e:
        raise ValueError(f"Failed to fetch token info. Is it a valid ERC-20? Error: {e}")

def get_token_balance(address: str, token_contract_address: str) -> float:
    w3 = get_provider()
    contract = get_token_contract(token_contract_address)
    
    checksum_address = w3.to_checksum_address(address)
    raw_balance = contract.functions.balanceOf(checksum_address).call()
    decimals = contract.functions.decimals().call()
    
    return raw_balance / (10 ** decimals)

def get_tracked_tokens() -> list[str]:
    return list(_tracked_tokens)

def add_custom_token(contract_address: str) -> dict:
    w3 = get_provider()
    checksum_address = w3.to_checksum_address(contract_address)
    
    info = get_token_info(checksum_address)
    
    if checksum_address not in _tracked_tokens:
        _tracked_tokens.append(checksum_address)
            
    return info
