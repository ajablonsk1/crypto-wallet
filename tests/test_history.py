import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from wallet.network.history import get_transaction_history, EtherscanAPIError

@patch("wallet.network.history.requests.get")
@patch("wallet.network.history.os.getenv")
@patch("wallet.network.history.get_provider")
def test_get_transaction_history_success(mock_get_provider, mock_getenv, mock_get):
    mock_w3 = MagicMock()
    mock_get_provider.return_value = mock_w3
    mock_w3.is_address.return_value = True
    mock_w3.to_checksum_address.side_effect = lambda x: x
    
    mock_getenv.return_value = "fake_api_key"
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "1",
        "message": "OK",
        "result": [
            {
                "hash": "0x123",
                "from": "0xSender",
                "to": "0xTarget",
                "value": "1000000000000000000",
                "gasUsed": "21000",
                "isError": "0",
                "timeStamp": "1620000000"
            }
        ]
    }
    mock_get.return_value = mock_response
    
    history = get_transaction_history("0xTarget", page=1, limit=10)
    
    assert len(history) == 1
    assert history[0]["hash"] == "0x123"
    assert history[0]["value"] == Decimal("1")
    assert history[0]["status"] == "Success"
    assert history[0]["direction"] == "IN"
    assert isinstance(history[0]["timestamp"], str)
    assert "2021" in history[0]["timestamp"]
    assert history[0]["symbol"] == "ETH"

@patch("wallet.network.history.requests.get")
@patch("wallet.network.history.os.getenv")
@patch("wallet.network.history.get_provider")
def test_get_transaction_history_no_txs(mock_get_provider, mock_getenv, mock_get):
    mock_w3 = MagicMock()
    mock_get_provider.return_value = mock_w3
    mock_w3.is_address.return_value = True
    mock_w3.to_checksum_address.side_effect = lambda x: x
    
    mock_getenv.return_value = "fake_api_key"
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "0",
        "message": "No transactions found",
        "result": []
    }
    mock_get.return_value = mock_response
    
    history = get_transaction_history("0xTarget")
    assert history == []

@patch("wallet.network.history.requests.get")
@patch("wallet.network.history.os.getenv")
@patch("wallet.network.history.get_provider")
def test_get_transaction_history_error(mock_get_provider, mock_getenv, mock_get):
    mock_w3 = MagicMock()
    mock_get_provider.return_value = mock_w3
    mock_w3.is_address.return_value = True
    mock_w3.to_checksum_address.side_effect = lambda x: x
    
    mock_getenv.return_value = "fake_api_key"
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "0",
        "message": "NOTOK",
        "result": "Invalid API Key"
    }
    mock_get.return_value = mock_response
    
    with pytest.raises(EtherscanAPIError, match="Etherscan API Error: NOTOK - Invalid API Key"):
        get_transaction_history("0xTarget")
        
@patch("wallet.network.history.requests.get")
@patch("wallet.network.history.os.getenv")
@patch("wallet.network.history.get_provider")
def test_get_token_transaction_history(mock_get_provider, mock_getenv, mock_get):
    mock_w3 = MagicMock()
    mock_get_provider.return_value = mock_w3
    mock_w3.is_address.return_value = True
    mock_w3.to_checksum_address.side_effect = lambda x: x
    
    mock_getenv.return_value = "fake_api_key"
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "1",
        "message": "OK",
        "result": [
            {
                "hash": "0xabc",
                "from": "0xTarget",
                "to": "0xReceiver",
                "value": "5000000",
                "tokenDecimal": "6",
                "tokenSymbol": "USDC",
                "gasUsed": "55000",
                "isError": "0",
                "timeStamp": "1620000000"
            }
        ]
    }
    mock_get.return_value = mock_response
    
    history = get_transaction_history("0xTarget", token_address="0xToken")
    
    assert len(history) == 1
    assert history[0]["value"] == Decimal("5")
    assert history[0]["symbol"] == "USDC"
    assert history[0]["direction"] == "OUT"
