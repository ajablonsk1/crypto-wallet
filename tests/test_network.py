import pytest
from web3 import Web3

from wallet.network.provider import get_provider, is_connected, get_eth_balance, get_gas_price

def test_get_provider():
    w3 = get_provider()
    assert isinstance(w3, Web3)

def test_is_connected():
    assert is_connected() is True

def test_get_eth_balance():
    # vitalik.eth public address, used as a safe read-only test vector
    address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    balance = get_eth_balance(address)
    assert isinstance(balance, float)
    assert balance >= 0

def test_get_gas_price():
    gas_price = get_gas_price()
    assert isinstance(gas_price, float)
    assert gas_price > 0
