import os
import requests
import time
from decimal import Decimal
from datetime import datetime
from typing import Optional

from wallet.network.provider import get_provider

ETHERSCAN_API_URL = os.getenv("ETHERSCAN_API_URL", "https://api-sepolia.etherscan.io/api")

if not ETHERSCAN_API_URL.startswith("https://"):
    raise ValueError("ETHERSCAN_API_URL must use HTTPS")

class EtherscanAPIError(Exception):
    pass

def get_transaction_history(address: str, page: int = 1, limit: int = 25, token_address: Optional[str] = None) -> list[dict]:
    """
    Fetch transaction history from Etherscan API for a given address.
    If token_address is provided, it fetches ERC-20 transfer events.
    Returns a list of transactions formatted as dictionaries.
    """
    w3 = get_provider()
    
    if not w3.is_address(address):
        raise ValueError("Invalid address")
    address_checksum = w3.to_checksum_address(address)
    addr_lower = address_checksum.lower()
    
    api_key = os.getenv("ETHERSCAN_API_KEY")
    if not api_key:
        raise ValueError("ETHERSCAN_API_KEY environment variable is missing")
        
    if token_address:
        if not w3.is_address(token_address):
            raise ValueError("Invalid token address")
        token_checksum = w3.to_checksum_address(token_address)
        
        params = {
            "module": "account",
            "action": "tokentx",
            "address": address_checksum,
            "contractaddress": token_checksum,
            "page": page,
            "offset": limit,
            "sort": "desc",
            "apikey": api_key
        }
    else:
        params = {
            "module": "account",
            "action": "txlist",
            "address": address_checksum,
            "page": page,
            "offset": limit,
            "sort": "desc",
            "apikey": api_key
        }
        
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(ETHERSCAN_API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            break
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise EtherscanAPIError(f"HTTP Error while calling Etherscan API after {max_retries} attempts: {e}")
            time.sleep(1) # simple backoff
    
    if data.get("status") == "0":
        msg = data.get("message", "")
        if msg == "No transactions found":
            return []
        raise EtherscanAPIError(f"Etherscan API Error: {msg} - {data.get('result', '')}")
        
    raw_txs = data.get("result", [])
    if not isinstance(raw_txs, list):
        raw_txs = []
        
    history = []
    
    for tx in raw_txs:
        # Determine value in natural units
        if token_address:
            token_decimals = int(tx.get("tokenDecimal", 18))
            value = Decimal(tx.get("value", "0")) / Decimal(10 ** token_decimals)
            token_symbol = tx.get("tokenSymbol", "")
        else:
            value = Decimal(tx.get("value", "0")) / Decimal(10 ** 18)
            token_symbol = "ETH"
            
        status = "Success" if tx.get("isError", "0") == "0" else "Failed"
        
        if tx.get("to", "").lower() == addr_lower:
            direction = "IN"
        elif tx.get("from", "").lower() == addr_lower:
            direction = "OUT"
        else:
            direction = "UNKNOWN"
            
        try:
            timestamp_int = int(tx.get("timeStamp", 0))
            dt = datetime.fromtimestamp(timestamp_int) if timestamp_int > 0 else None
            timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "N/A"
        except (ValueError, OverflowError):
            timestamp_str = "N/A"
            
        record = {
            "hash": tx.get("hash"),
            "from": tx.get("from"),
            "to": tx.get("to"),
            "value": value,
            "symbol": token_symbol,
            "gas_used": int(tx.get("gasUsed", 0)),
            "status": status,
            "timestamp": timestamp_str,
            "direction": direction
        }
        
        history.append(record)
        
    return history
