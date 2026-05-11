from decimal import Decimal

from web3 import Web3
from web3.exceptions import TimeExhausted

from wallet.network.provider import get_provider

def build_eth_tx(from_address: str, to_address: str, amount_eth: Decimal) -> dict:
    w3 = get_provider()
    
    from_checksum = w3.to_checksum_address(from_address)
    to_checksum = w3.to_checksum_address(to_address)
    
    nonce = w3.eth.get_transaction_count(from_checksum)
    gas_price = w3.eth.gas_price
    
    tx = {
        'nonce': nonce,
        'to': to_checksum,
        'value': w3.to_wei(amount_eth, 'ether'),
        'gasPrice': gas_price,
        'chainId': w3.eth.chain_id
    }

    # Dynamically estimate gas instead of hardcoding 21000.
    # For plain ETH transfers this will return 21000, but for
    # contract interactions it will compute the correct limit.
    tx['gas'] = w3.eth.estimate_gas(tx)

    return tx

def sign_and_send(tx_dict: dict, private_key: bytes) -> str:
    w3 = get_provider()
    
    signed_tx = w3.eth.account.sign_transaction(tx_dict, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    
    return w3.to_hex(tx_hash)

def estimate_fee(to_address: str, amount_eth: Decimal) -> Decimal:
    w3 = get_provider()
    
    to_checksum = w3.to_checksum_address(to_address)

    # Build a minimal tx to let estimate_gas determine the correct gas limit
    tx = {
        'to': to_checksum,
        'value': w3.to_wei(amount_eth, 'ether'),
    }
    gas_limit = w3.eth.estimate_gas(tx)
    gas_price = w3.eth.gas_price
    
    fee_wei = gas_limit * gas_price
    return Decimal(w3.from_wei(fee_wei, 'ether'))

def wait_for_receipt(tx_hash: str, timeout: int = 120):
    w3 = get_provider()
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
        return receipt
    except TimeExhausted:
        raise TimeoutError(f"Transaction {tx_hash} took longer than {timeout} seconds to confirm.")
