import os
from decimal import Decimal
from typing import Optional

from web3 import Web3
from web3.exceptions import TimeExhausted

from wallet.network.provider import get_provider
from wallet.network.tokens import get_token_contract

def _get_gas_buffer() -> float:
    return float(os.getenv("GAS_BUFFER_PERCENT", "0.2")) + 1.0

def build_eth_tx(from_address: str, to_address: str, amount_eth: Decimal) -> dict:
    w3 = get_provider()
    
    if not all(w3.is_address(a) for a in (from_address, to_address)):
        raise ValueError("Invalid Ethereum address provided.")
        
    from_checksum = w3.to_checksum_address(from_address)
    to_checksum = w3.to_checksum_address(to_address)
    
    value_wei = w3.to_wei(amount_eth, 'ether')
    
    # Check balance
    balance = w3.eth.get_balance(from_checksum)
    if value_wei > balance:
        raise ValueError(f"Insufficient ETH balance. Required: {w3.from_wei(value_wei, 'ether')} ETH, Available: {w3.from_wei(balance, 'ether')} ETH")
        
    nonce = w3.eth.get_transaction_count(from_checksum, 'pending')
    gas_price = w3.eth.gas_price
    
    tx = {
        'from': from_checksum,
        'nonce': nonce,
        'to': to_checksum,
        'value': value_wei,
        'gasPrice': gas_price,
        'chainId': w3.eth.chain_id
    }
    
    try:
        gas_limit = w3.eth.estimate_gas(tx)
        tx['gas'] = int(gas_limit * _get_gas_buffer())
    except Exception as e:
        raise ValueError(f"Gas estimation failed: {e}")
        
    # Check if we have enough ETH for value + gas
    total_required = value_wei + (tx['gas'] * gas_price)
    if total_required > balance:
        raise ValueError(f"Insufficient ETH balance to cover value and gas fees. Required: {w3.from_wei(total_required, 'ether')} ETH, Available: {w3.from_wei(balance, 'ether')} ETH")
        
    return tx

def sign_and_send(tx_dict: dict, private_key: bytes) -> str:
    w3 = get_provider()
    signed_tx = w3.eth.account.sign_transaction(tx_dict, private_key)
    raw_tx = getattr(signed_tx, 'raw_transaction', getattr(signed_tx, 'rawTransaction', None))
    if raw_tx is None:
        raise RuntimeError("Unsupported web3 version: cannot find raw_transaction")
    tx_hash = w3.eth.send_raw_transaction(raw_tx)
    return w3.to_hex(tx_hash)

def estimate_fee(to_address: str, amount_eth: Decimal) -> Decimal:
    w3 = get_provider()
    
    if not w3.is_address(to_address):
        raise ValueError("Invalid Ethereum address")
        
    to_checksum = w3.to_checksum_address(to_address)
    tx = {
        'to': to_checksum,
        'value': w3.to_wei(amount_eth, 'ether'),
    }
    try:
        gas_limit = int(w3.eth.estimate_gas(tx) * _get_gas_buffer())
    except Exception as e:
        raise ValueError(f"Gas estimation failed: {e}")

    fee_wei = gas_limit * w3.eth.gas_price
    return Decimal(w3.from_wei(fee_wei, 'ether'))

def wait_for_receipt(tx_hash: str, timeout: Optional[int] = None):
    w3 = get_provider()

    if timeout is None:
        timeout = int(os.getenv("TX_TIMEOUT", "120"))
        
    try:
        return w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
    except TimeExhausted:
        raise TimeoutError(f"Transaction {tx_hash} took longer than {timeout} seconds to confirm.")

def build_token_tx(from_address: str, to_address: str, token_address: str, amount: Decimal) -> dict:
    w3 = get_provider()
    
    if not all(w3.is_address(a) for a in (from_address, to_address, token_address)):
        raise ValueError("Invalid Ethereum address provided.")
        
    from_checksum = w3.to_checksum_address(from_address)
    to_checksum = w3.to_checksum_address(to_address)
    token_checksum = w3.to_checksum_address(token_address)
    
    contract = get_token_contract(token_checksum)
    
    try:
        decimals = contract.functions.decimals().call()
    except Exception as e:
        raise ValueError(f"Cannot determine token decimals for contract {token_address}") from e
        
    raw_amount = int(amount * Decimal(10 ** decimals))
    if raw_amount <= 0:
        raise ValueError("Amount must be positive")
        
    # Check token balance
    token_balance = contract.functions.balanceOf(from_checksum).call()
    if raw_amount > token_balance:
        req_tokens = Decimal(raw_amount) / Decimal(10 ** decimals)
        avail_tokens = Decimal(token_balance) / Decimal(10 ** decimals)
        raise ValueError(f"Insufficient token balance. Required: {req_tokens}, Available: {avail_tokens}")
        
    nonce = w3.eth.get_transaction_count(from_checksum, 'pending')
    gas_price = w3.eth.gas_price
    
    try:
        gas_limit = contract.functions.transfer(to_checksum, raw_amount).estimate_gas({'from': from_checksum})
        gas_limit = int(gas_limit * _get_gas_buffer())
    except Exception as e:
        raise ValueError(f"Gas estimation failed: {e}")
        
    tx = contract.functions.transfer(to_checksum, raw_amount).build_transaction({
        'chainId': w3.eth.chain_id,
        'gasPrice': gas_price,
        'nonce': nonce,
        'from': from_checksum,
        'value': 0,
        'gas': gas_limit
    })
    
    eth_balance = w3.eth.get_balance(from_checksum)
    required_eth_for_gas = tx['gas'] * gas_price
    if required_eth_for_gas > eth_balance:
        raise ValueError(f"Insufficient ETH balance to cover gas fees. Required: {w3.from_wei(required_eth_for_gas, 'ether')} ETH, Available: {w3.from_wei(eth_balance, 'ether')} ETH")
        
    return tx

def estimate_token_fee(token_address: str, to_address: str, amount: Decimal, from_address: Optional[str] = None) -> Decimal:
    w3 = get_provider()
    
    if not all(w3.is_address(a) for a in filter(None, [token_address, to_address, from_address])):
        raise ValueError("Invalid Ethereum address provided.")
        
    token_checksum = w3.to_checksum_address(token_address)
    to_checksum = w3.to_checksum_address(to_address)
    contract = get_token_contract(token_checksum)
    
    try:
        decimals = contract.functions.decimals().call()
    except Exception as e:
        raise ValueError("Cannot determine token decimals") from e
        
    raw_amount = int(amount * Decimal(10 ** decimals))
    if raw_amount <= 0:
        raise ValueError("Amount must be positive")
        
    gas_price = w3.eth.gas_price
    
    if from_address:
        from_checksum = w3.to_checksum_address(from_address)
        try:
            gas_limit = contract.functions.transfer(to_checksum, raw_amount).estimate_gas({'from': from_checksum})
            gas_limit = int(gas_limit * _get_gas_buffer())
        except Exception as e:
            raise ValueError(f"Gas estimation failed: {e}")
    else:
        gas_limit = int(int(os.getenv("DEFAULT_TOKEN_GAS_LIMIT", "150000")) * _get_gas_buffer())
        
    fee_wei = gas_limit * gas_price
    return Decimal(w3.from_wei(fee_wei, 'ether'))
