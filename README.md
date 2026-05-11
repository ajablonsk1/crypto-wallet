# Crypto Wallet

## 📦 Installation

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd crypto-wallet
   ```

2. **Set up virtual environment** (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**:
   Create a `.env` file in the project root and specify your Sepolia RPC URL. By default, it will fall back to a public node, but for better stability, you should use your own provider like Infura or Alchemy (the URL will contain your API key).
   ```env
   # You can use a public node:
   SEPOLIA_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com
   
   # OR your own Infura/Alchemy node:
   # SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/YOUR_INFURA_API_KEY
   ```
   > **Note:** The `.env` file is included in `.gitignore`, so your API keys will not be committed to the repository.

## 🛠️ Dependencies

Each requirement in the project serves a specific purpose:

- **[web3](https://pypi.org/project/web3/)**: An interface for interacting with the Ethereum blockchain (RPC, balances, transactions).
- **[cryptography](https://pypi.org/project/cryptography/)**: AES-256-GCM encryption for secure keystore storage.
- **[argon2-cffi](https://pypi.org/project/argon2-cffi/)**: Argon2id password-based key derivation.
- **[bip-utils](https://pypi.org/project/bip-utils/)**: BIP-39 mnemonic phrases and BIP-32/44 HD wallet derivation.
- **[eth-keys](https://pypi.org/project/eth-keys/)**: Ethereum-specific key and address manipulation.
- **[customtkinter](https://pypi.org/project/customtkinter/)**: Modern, themed UI components for the desktop app.
- **[requests](https://pypi.org/project/requests/)**: HTTP client for interacting with Etherscan API.
- **[pytest](https://pypi.org/project/pytest/)**: Testing framework for unit and integration tests.
- **[python-dotenv](https://pypi.org/project/python-dotenv/)**: Loads environment variables from a `.env` file (used for RPC configurations).
