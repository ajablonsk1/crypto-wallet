import os
import time
import pytest
from decimal import Decimal
from pathlib import Path

from wallet.crypto.mnemonic import generate_mnemonic, mnemonic_to_seed
from wallet.crypto.keys import derive_private_key, private_key_to_address
from wallet.crypto.keystore import create_keystore, load_keystore
from wallet.network.provider import get_eth_balance, is_connected
from wallet.network.tx import build_eth_tx, sign_and_send, wait_for_receipt
from wallet.network.history import get_transaction_history
from wallet.network.tokens import add_custom_token, get_token_balance

# Skip all tests in this file if the required environment variables are not set in .env
pytestmark = pytest.mark.skipif(
    not os.getenv("E2E_FUNDED_MNEMONIC") or not os.getenv("ETHERSCAN_API_KEY"),
    reason="Missing E2E_FUNDED_MNEMONIC or ETHERSCAN_API_KEY in .env file"
)

# Constants for the Sepolia testnet environment
LINK_SEPOLIA_ADDRESS = "0x779877A7B0D9E8603169DdbD7836e478b4624789"
TEST_PASSWORD = "TestPassword123!"
KEYSTORE_PATH = Path("test_e2e_keystore.json")

class TestWalletE2E:    
    @classmethod
    def setup_class(cls):
        """
        Initial test setup: 
        1. Verify blockchain connection.
        2. Initialize the 'faucet' (funded) account used to send test ETH.
        """
        assert is_connected(), "No connection to the Sepolia network!"
        
        # Derive the funded account's keys from the mnemonic provided in .env
        funded_mnemonic = os.getenv("E2E_FUNDED_MNEMONIC").split()
        cls.funded_seed = mnemonic_to_seed(funded_mnemonic)
        cls.funded_pk = derive_private_key(cls.funded_seed)
        cls.funded_address = private_key_to_address(cls.funded_pk)
        
        # State variables to share data between test steps
        cls.new_seed = None
        cls.new_pk = None
        cls.new_address = None
        cls.tx_hash = None

    def test_1_create_and_encrypt_wallet(self):
        """
        STEP 1: Test the 'Create Wallet' flow.
        Generates a new mnemonic phrase, derives a seed, and encrypts it into a keystore file.
        """
        words = generate_mnemonic()
        self.__class__.new_seed = mnemonic_to_seed(words)
        
        # Encrypt the seed with Argon2id + AES-256-GCM
        create_keystore(self.new_seed, TEST_PASSWORD, KEYSTORE_PATH)
        assert KEYSTORE_PATH.exists()

    def test_2_unlock_wallet(self):
        """
        STEP 2: Test the 'Unlock Wallet' flow.
        Loads the encrypted keystore, verifies the password, and derives the primary Ethereum address.
        """
        recovered_seed = load_keystore(KEYSTORE_PATH, TEST_PASSWORD)
        assert recovered_seed == self.new_seed
        
        # Derive primary private key and address (Index 0)
        self.__class__.new_pk = derive_private_key(recovered_seed)
        self.__class__.new_address = private_key_to_address(self.new_pk)
        
        assert self.new_address.startswith("0x")

    def test_3_initial_empty_history(self):
        """
        STEP 3: Verify that a brand new wallet has no transaction history on Etherscan.
        """
        if not self.new_address:
            pytest.fail("Missing address for history check")

        history = get_transaction_history(self.new_address)
        
        assert isinstance(history, list)
        assert len(history) == 0    

    def test_4_check_faucet_balance(self):
        """
        STEP 4: Ensure the 'faucet' account has enough Sepolia ETH to perform the tests.
        """
        balance = get_eth_balance(self.funded_address)
        assert balance > Decimal("0.001"), f"The funding wallet {self.funded_address} is empty!"

    def test_5_send_eth_to_new_wallet(self):
        """
        STEP 5: Perform a live ETH transfer.
        1. Build, sign, and broadcast the transaction.
        2. Wait for block confirmation.
        3. Poll the node to verify the new wallet received the funds.
        """
        amount = Decimal("0.0005")
        
        # Build the raw transaction dict
        tx_dict = build_eth_tx(self.funded_address, self.new_address, amount)
        
        # Sign with private key and broadcast
        self.__class__.tx_hash = sign_and_send(tx_dict, self.funded_pk)
        assert self.tx_hash.startswith("0x")
        
        # Wait for the transaction to be included in a block
        receipt = wait_for_receipt(self.tx_hash, timeout=120)
        assert receipt["status"] == 1 

        # Polling: RPC nodes may take a few seconds to reflect the new balance after confirmation
        for _ in range(6):
            time.sleep(5)
            new_balance = get_eth_balance(self.new_address)
            if new_balance == amount:
                break
        assert new_balance == amount

    def test_6_check_history(self):
        """
        STEP 6: Verify the transaction appears in the Etherscan API history.
        Includes a delay as Etherscan indexing can take some time after block confirmation.
        """
        time.sleep(10)
        
        history = get_transaction_history(self.new_address)
        assert len(history) > 0, "No transactions found in history"
        
        # Verify the specific transaction hash and amount match our transfer
        found_tx = next((tx for tx in history if tx["hash"].lower() == self.tx_hash.lower()), None)
        assert found_tx is not None, "Transaction not found on Etherscan"
        assert found_tx["direction"] == "IN"
        assert found_tx["value"] == Decimal("0.0005")

    def test_7_add_erc20_token(self):
        """
        STEP 7: Test ERC-20 token integration.
        Adds the LINK token contract and fetches the balance for the funded account.
        """
        token_info = add_custom_token(LINK_SEPOLIA_ADDRESS)
        assert token_info["symbol"] == "LINK"
        
        # Fetch token balance using the ERC-20 'balanceOf' call
        balance = get_token_balance(self.funded_address, LINK_SEPOLIA_ADDRESS)
        assert isinstance(balance, Decimal)
        assert balance >= 0

    def test_8_add_and_switch_account(self):
        """
        STEP 8: Test HD Wallet (BIP-44) derivation.
        Generates a second account (Index 1) from the same seed and ensures it is unique.
        """
        if not self.new_seed:
            pytest.fail("Missing seed for account derivation")
            
        # Derive Account #1 (m/44'/60'/0'/0/1)
        pk_account_1 = derive_private_key(self.new_seed, index=1)
        address_account_1 = private_key_to_address(pk_account_1)
        
        assert address_account_1.startswith("0x")
        assert address_account_1 != self.new_address, "New address must be unique!"
        
        # New accounts derived from the HD tree should start with 0 balance
        balance_1 = get_eth_balance(address_account_1)
        assert balance_1 == Decimal("0")

    def test_9_verify_derivation_consistency(self):
        """
        STEP 9: Ensure the derivation logic is deterministic.
        Generating the same index twice must always yield the same Ethereum address.
        """
        pk_check = derive_private_key(self.new_seed, index=1)
        address_check = private_key_to_address(pk_check)
        
        # Verify that Account #1 derived again matches the previous derivation
        assert address_check == private_key_to_address(derive_private_key(self.new_seed, index=1))

    @classmethod
    def teardown_class(cls):
        """
        Cleanup: Delete the temporary test keystore file after the test session.
        """
        if KEYSTORE_PATH.exists():
            KEYSTORE_PATH.unlink()