import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from wallet.network.tx import build_eth_tx, estimate_fee, sign_and_send, wait_for_receipt

VITALIK_ADDRESS = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
BURN_ADDRESS = "0x0000000000000000000000000000000000000000"

def test_build_eth_tx():
    # Test building an unsigned transaction dictionary
    # This calls the network for nonce and gasPrice
    tx = build_eth_tx(
        from_address=VITALIK_ADDRESS,
        to_address=BURN_ADDRESS,
        amount_eth=Decimal("0.01")
    )
    
    assert isinstance(tx, dict)
    assert "nonce" in tx
    assert "gasPrice" in tx
    assert tx["to"] == BURN_ADDRESS
    assert tx["value"] == 10000000000000000  # 0.01 ETH in Wei
    assert tx["gas"] > 0  # gas is now dynamically estimated
    assert tx["chainId"] in (1, 11155111)  # Mainnet or Sepolia

def test_estimate_fee():
    # Test fee estimation
    fee = estimate_fee(to_address=BURN_ADDRESS, amount_eth=Decimal("0.1"))
    
    assert isinstance(fee, Decimal)
    assert fee > 0

@patch("wallet.network.tx.get_provider")
def test_sign_and_send_mocked(mock_get_provider):
    # Mock the Web3 provider to avoid sending a real transaction
    mock_w3 = MagicMock()
    mock_get_provider.return_value = mock_w3
    
    mock_signed_tx = MagicMock()
    mock_signed_tx.raw_transaction = b"fake_raw_tx"
    mock_w3.eth.account.sign_transaction.return_value = mock_signed_tx
    
    mock_w3.eth.send_raw_transaction.return_value = b"fake_tx_hash"
    mock_w3.to_hex.return_value = "0xfake_tx_hash"
    
    dummy_tx = {"to": BURN_ADDRESS, "value": 100}
    dummy_pk = b"fake_private_key"
    
    tx_hash = sign_and_send(dummy_tx, dummy_pk)
    
    assert tx_hash == "0xfake_tx_hash"
    mock_w3.eth.account.sign_transaction.assert_called_once_with(dummy_tx, dummy_pk)
    mock_w3.eth.send_raw_transaction.assert_called_once_with(b"fake_raw_tx")

@patch("wallet.network.tx.get_provider")
def test_wait_for_receipt_mocked(mock_get_provider):
    mock_w3 = MagicMock()
    mock_get_provider.return_value = mock_w3
    
    mock_w3.eth.wait_for_transaction_receipt.return_value = {"status": 1}
    
    receipt = wait_for_receipt("0xfake", timeout=60)
    assert receipt["status"] == 1
    mock_w3.eth.wait_for_transaction_receipt.assert_called_once_with("0xfake", timeout=60)
