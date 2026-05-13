import os
import tempfile
from decimal import Decimal
from unittest.mock import patch, MagicMock

from wallet.crypto.mnemonic import generate_mnemonic, mnemonic_to_seed
from wallet.crypto.keys import derive_private_key, private_key_to_address
from wallet.crypto.keystore import create_keystore, load_keystore
from wallet.network.tx import build_eth_tx, sign_and_send

def test_full_backend_flow_mocked():
    """
    Simulates a complete user journey through the backend (without UI):
    1. Create wallet (mnemonic -> private key -> address)
    2. Encrypt and save to keystore
    3. Load from keystore and decrypt
    4. Build an Ethereum transaction
    5. Sign and broadcast
    """
    # 1. User creates a wallet
    mnemonic = generate_mnemonic()
    seed = mnemonic_to_seed(mnemonic)
    private_key = derive_private_key(seed)
    address = private_key_to_address(private_key)
    
    password = "SuperSecretPassword123!"
    
    # 2. Save to keystore
    with tempfile.TemporaryDirectory() as tmpdir:
        keystore_path = os.path.join(tmpdir, "keystore.json")
        create_keystore(seed, password, keystore_path)
        
        # 3. User logs in (loads keystore)
        loaded_seed = load_keystore(keystore_path, password)
        assert loaded_seed == seed
        loaded_pk = derive_private_key(loaded_seed)
        
    # 4. User wants to send ETH. 
    # We mock the network calls since we don't want to hit real node in CI.
    with patch("wallet.network.tx.get_provider") as mock_get_provider, \
         patch("wallet.network.tx._get_gas_buffer", return_value=1.2):
         
        mock_w3 = MagicMock()
        mock_get_provider.return_value = mock_w3
        
        # Setup mocks for balance and gas
        mock_w3.is_address.return_value = True
        mock_w3.to_checksum_address.side_effect = lambda x: x
        mock_w3.to_wei.return_value = 10000000000000000  # 0.01 ETH
        mock_w3.from_wei.side_effect = lambda val, unit: Decimal(val) / Decimal(10**18)
        mock_w3.eth.get_balance.return_value = 50000000000000000  # 0.05 ETH
        mock_w3.eth.get_transaction_count.return_value = 0
        mock_w3.eth.gas_price = 20000000000 # 20 gwei
        mock_w3.eth.estimate_gas.return_value = 21000
        mock_w3.eth.chain_id = 11155111 # Sepolia
        
        # Mock transaction signing and sending
        mock_signed_tx = MagicMock()
        mock_signed_tx.raw_transaction = b"signed_bytes"
        mock_w3.eth.account.sign_transaction.return_value = mock_signed_tx
        mock_w3.eth.send_raw_transaction.return_value = b"tx_hash_123"
        mock_w3.to_hex.return_value = "0xtx_hash_123"
        
        # 5. Build transaction
        tx_dict = build_eth_tx(
            from_address=address,
            to_address="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", # Vitalik
            amount_eth=Decimal("0.01")
        )
        
        assert tx_dict["to"] == "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
        assert tx_dict["value"] == 10000000000000000
        assert tx_dict["gas"] == int(21000 * 1.2)
        
        # 6. Sign and send
        tx_hash = sign_and_send(tx_dict, loaded_pk)
        
        assert tx_hash == "0xtx_hash_123"
        mock_w3.eth.send_raw_transaction.assert_called_once_with(b"signed_bytes")
