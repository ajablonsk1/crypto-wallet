import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from wallet.network.tx import build_eth_tx, estimate_fee, sign_and_send, wait_for_receipt, build_token_tx, estimate_token_fee

VITALIK_ADDRESS = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
BURN_ADDRESS = "0x0000000000000000000000000000000000000000"
TOKEN_ADDRESS = "0x779877A7B0D9E8603169DdbD7836e478b4624789"

@patch("wallet.network.tx.get_provider")
def test_build_eth_tx(mock_get_provider):
    mock_w3 = MagicMock()
    mock_get_provider.return_value = mock_w3
    mock_w3.is_address.return_value = True
    mock_w3.to_checksum_address.side_effect = lambda x: x
    mock_w3.to_wei.return_value = 10000000000000000
    mock_w3.eth.get_balance.return_value = 20000000000000000 # 0.02 eth
    mock_w3.eth.get_transaction_count.return_value = 5
    mock_w3.eth.gas_price = 1000000000
    mock_w3.eth.chain_id = 11155111
    mock_w3.eth.estimate_gas.return_value = 21000
    
    tx = build_eth_tx(VITALIK_ADDRESS, BURN_ADDRESS, Decimal("0.01"))
    
    assert tx["gas"] == int(21000 * 1.2)
    assert tx["value"] == 10000000000000000

@patch("wallet.network.tx.get_provider")
def test_estimate_fee(mock_get_provider):
    mock_w3 = MagicMock()
    mock_get_provider.return_value = mock_w3
    mock_w3.is_address.return_value = True
    mock_w3.eth.estimate_gas.return_value = 21000
    mock_w3.eth.gas_price = 1000000000
    mock_w3.from_wei.return_value = Decimal("0.0000252")
    
    fee = estimate_fee(BURN_ADDRESS, Decimal("0.1"))
    assert fee > 0

@patch("wallet.network.tx.get_provider")
def test_sign_and_send_mocked(mock_get_provider):
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

@patch("wallet.network.tx.get_provider")
@patch("wallet.network.tx.get_token_contract")
def test_build_token_tx_mocked(mock_get_token_contract, mock_get_provider):
    mock_w3 = MagicMock()
    mock_get_provider.return_value = mock_w3
    mock_w3.is_address.return_value = True
    mock_w3.to_checksum_address.side_effect = lambda x: x 
    mock_w3.eth.get_transaction_count.return_value = 5
    mock_w3.eth.gas_price = 1000000000
    mock_w3.eth.chain_id = 11155111
    mock_w3.eth.get_balance.return_value = 20000000000000000
    
    mock_contract = MagicMock()
    mock_get_token_contract.return_value = mock_contract
    mock_contract.functions.decimals().call.return_value = 18
    mock_contract.functions.balanceOf().call.return_value = 20000000000000000000
    
    mock_transfer_func = MagicMock()
    mock_contract.functions.transfer.return_value = mock_transfer_func
    mock_transfer_func.build_transaction.return_value = {"to": TOKEN_ADDRESS, "data": "0x123", "gas": int(60000*1.2)}
    mock_transfer_func.estimate_gas.return_value = 60000
    
    tx = build_token_tx(VITALIK_ADDRESS, BURN_ADDRESS, TOKEN_ADDRESS, Decimal("10.5"))
    
    assert tx == {"to": TOKEN_ADDRESS, "data": "0x123", "gas": int(60000*1.2)}
    mock_contract.functions.transfer.assert_called_with(BURN_ADDRESS, 10500000000000000000)
    assert mock_contract.functions.transfer.call_count == 2

@patch("wallet.network.tx.get_provider")
@patch("wallet.network.tx.get_token_contract")
def test_estimate_token_fee_mocked(mock_get_token_contract, mock_get_provider):
    mock_w3 = MagicMock()
    mock_get_provider.return_value = mock_w3
    mock_w3.is_address.return_value = True
    mock_w3.to_checksum_address.side_effect = lambda x: x 
    mock_w3.eth.gas_price = 1000000000
    mock_w3.from_wei.side_effect = lambda val, unit: Decimal(val) / Decimal(10**18)
    
    mock_contract = MagicMock()
    mock_get_token_contract.return_value = mock_contract
    mock_contract.functions.decimals().call.return_value = 18
    
    mock_transfer_func = MagicMock()
    mock_contract.functions.transfer.return_value = mock_transfer_func
    # mock gas estimate
    mock_transfer_func.estimate_gas.return_value = 50000
    
    # 1. With from_address
    fee = estimate_token_fee(TOKEN_ADDRESS, BURN_ADDRESS, Decimal("10"), from_address=VITALIK_ADDRESS)
    assert fee == Decimal("0.00006") # 50000 * 1.2 * 1 gwei
    
    # 2. Without from_address
    fee2 = estimate_token_fee(TOKEN_ADDRESS, BURN_ADDRESS, Decimal("10"))
    assert fee2 == Decimal("0.00018") # 150000 * 1.2 * 1 gwei
