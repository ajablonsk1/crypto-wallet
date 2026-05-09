import os
from pathlib import Path
import pytest
from unittest.mock import patch

from wallet.network.tokens import (
    get_token_info,
    get_token_balance,
    add_custom_token,
    get_tracked_tokens,
)

# LINK Token on Sepolia
LINK_SEPOLIA = "0x779877A7B0D9E8603169DdbD7836e478b4624789"
# vitalik.eth public address, used as a safe read-only test vector
VITALIK_ADDRESS = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

@pytest.fixture(autouse=True)
def clear_tracked_tokens():
    import wallet.network.tokens as tokens_module
    tokens_module._tracked_tokens.clear()
    yield

def test_get_token_info():
    info = get_token_info(LINK_SEPOLIA)
    assert info["name"] == "ChainLink Token"
    assert info["symbol"] == "LINK"
    assert info["decimals"] == 18

def test_get_token_balance():
    balance = get_token_balance(VITALIK_ADDRESS, LINK_SEPOLIA)
    assert isinstance(balance, float)
    assert balance >= 0

def test_add_custom_token():
    assert len(get_tracked_tokens()) == 0
    info = add_custom_token(LINK_SEPOLIA)
    assert info["symbol"] == "LINK"
    
    tokens = get_tracked_tokens()
    assert len(tokens) == 1
    assert tokens[0] == "0x779877A7B0D9E8603169DdbD7836e478b4624789"
    
    add_custom_token(LINK_SEPOLIA)
    assert len(get_tracked_tokens()) == 1

def test_invalid_token():
    with pytest.raises(ValueError, match="Failed to fetch"):
        get_token_info(VITALIK_ADDRESS)
