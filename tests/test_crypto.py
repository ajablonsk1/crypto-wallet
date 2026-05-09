import os
from pathlib import Path

import pytest

from wallet.crypto.mnemonic import generate_mnemonic, validate_mnemonic, mnemonic_to_seed
from wallet.crypto.keys import (
    derive_private_key,
    derive_multiple_keys,
    private_key_to_public_key,
    private_key_to_address,
)
from wallet.crypto.keystore import (
    create_keystore,
    load_keystore,
    change_password,
    InvalidPasswordError,
)


# Official Trezor BIP-39 test vectors (mnemonic -> seed with passphrase "TREZOR")
BIP39_TEST_VECTORS = [
    (
        "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about",
        "c55257c360c07c72029aebc1b53c05ed0362ada38ead3e3e9efa3708e53495531f09a6987599d18264c1e1c92f2cf141630c7a3c4ab7c81b2f001698e7463b04",
    ),
    (
        "zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo wrong",
        "ac27495480225222079d7be181583751e86f571027b0497b5b5d11218e0a8a13332572917f0f8e5a589620c6f15b11c61dee327651a14c34e18231052e48c069",
    ),
    (
        "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon art",
        "bda85446c68413707090a52022edd26a1c9462295029f2e60cd7c4f2bbd3097170af7a4d73245cafa9c3cca8d561a7c3de6f5d4a10be8ed2a5e608d68f92fcc8",
    ),
    (
        "ozone drill grab fiber curtain grace pudding thank cruise elder eight picnic",
        "274ddc525802f7c828d8ef7ddbcdc5304e87ac3535913611fbbfa986d0c9e5476c91689f9c8a54fd55bd38606aa6a8595ad213d4c9c9f9aca3fb217069a41028",
    ),
]


# Seed derived from first BIP-39 test vector, reused across key derivation tests
KNOWN_SEED = bytes.fromhex(
    "c55257c360c07c72029aebc1b53c05ed0362ada38ead3e3e9efa3708e53495531f09a6987599d18264c1e1c92f2cf141630c7a3c4ab7c81b2f001698e7463b04"
)


# BIP-39 mnemonic generation, validation, and seed derivation
class TestMnemonic:

    @pytest.mark.parametrize("strength,expected_len", [(128, 12), (256, 24)])
    def test_generate_mnemonic_length(self, strength, expected_len):
        words = generate_mnemonic(strength=strength)
        assert len(words) == expected_len
        assert all(isinstance(w, str) for w in words)
        assert validate_mnemonic(words) is True

    def test_generate_mnemonic_invalid_strength(self):
        with pytest.raises(ValueError):
            generate_mnemonic(strength=64)

    @pytest.mark.parametrize(
        "words,expected",
        [
            ("abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about".split(), True),
            ("abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon".split(), False),
            ("abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon xyzxyz".split(), False),
            ("abandon abandon abandon".split(), False),
        ],
    )
    def test_validate_mnemonic(self, words, expected):
        assert validate_mnemonic(words) is expected

    def test_mnemonic_to_seed_basics(self):
        words = generate_mnemonic(128)
        seed = mnemonic_to_seed(words)
        assert len(seed) == 64
        assert seed != mnemonic_to_seed(words, passphrase="some_pass")

    def test_mnemonic_to_seed_invalid(self):
        with pytest.raises(ValueError):
            mnemonic_to_seed(["invalid", "words", "here"])

    @pytest.mark.parametrize("mnemonic_str,expected_seed_hex", BIP39_TEST_VECTORS)
    def test_bip39_test_vectors(self, mnemonic_str, expected_seed_hex):
        seed = mnemonic_to_seed(mnemonic_str.split(), passphrase="TREZOR")
        assert seed.hex() == expected_seed_hex


# BIP-32/44 key derivation (m/44'/60'/0'/0/{index}) and Ethereum address generation
class TestKeys:

    def test_derive_private_key(self):
        pk = derive_private_key(KNOWN_SEED, index=0)
        assert len(pk) == 32
        assert pk == derive_private_key(KNOWN_SEED, index=0)
        assert pk != derive_private_key(KNOWN_SEED, index=1)

    def test_derive_private_key_negative_index(self):
        with pytest.raises(ValueError):
            derive_private_key(KNOWN_SEED, index=-1)

    def test_derive_multiple_keys(self):
        keys = derive_multiple_keys(KNOWN_SEED, count=3)
        assert len(keys) == 3
        for i, k in enumerate(keys):
            assert k == derive_private_key(KNOWN_SEED, index=i)

    def test_derive_multiple_keys_invalid_count(self):
        with pytest.raises(ValueError):
            derive_multiple_keys(KNOWN_SEED, count=0)

    def test_public_key_and_address(self):
        pk = derive_private_key(KNOWN_SEED, index=0)
        pub = private_key_to_public_key(pk)
        assert len(pub) == 64

        addr = private_key_to_address(pk)
        assert addr.startswith("0x")
        assert len(addr) == 42
        assert addr == private_key_to_address(pk)

    @pytest.mark.parametrize("bad_key", [b"\x01" * 16, b"\x01" * 31])
    def test_invalid_key_length(self, bad_key):
        with pytest.raises(ValueError):
            private_key_to_public_key(bad_key)
        with pytest.raises(ValueError):
            private_key_to_address(bad_key)

    def test_known_seed_to_address(self):
        # Derived from official BIP-39 test vector seed, index 0
        pk = derive_private_key(KNOWN_SEED, index=0)
        addr = private_key_to_address(pk)
        assert addr.startswith("0x") and len(addr) == 42
        assert addr == private_key_to_address(pk)


# Keystore encryption (Argon2id + AES-256-GCM) roundtrip and error handling
class TestKeystore:

    @pytest.fixture
    def seed(self):
        return os.urandom(64)

    @pytest.fixture
    def ks_path(self, tmp_path):
        return tmp_path / "test_keystore.json"

    def test_roundtrip(self, seed, ks_path):
        create_keystore(seed, "password123", ks_path)
        assert ks_path.exists()
        assert load_keystore(ks_path, "password123") == seed

    def test_wrong_password(self, seed, ks_path):
        create_keystore(seed, "correct", ks_path)
        with pytest.raises(InvalidPasswordError):
            load_keystore(ks_path, "wrong")

    def test_empty_password(self, seed, ks_path):
        with pytest.raises(ValueError):
            create_keystore(seed, "", ks_path)

    def test_change_password(self, seed, ks_path):
        create_keystore(seed, "old_pass", ks_path)
        change_password(ks_path, "old_pass", "new_pass")
        assert load_keystore(ks_path, "new_pass") == seed
        with pytest.raises(InvalidPasswordError):
            load_keystore(ks_path, "old_pass")

    def test_json_structure(self, seed, ks_path):
        import json
        create_keystore(seed, "password", ks_path)
        data = json.loads(ks_path.read_text())
        assert data["version"] == 1
        assert data["crypto"]["cipher"] == "aes-256-gcm"
        assert data["crypto"]["kdf"] == "argon2id"
        for field in ("ciphertext", "nonce", "tag"):
            assert field in data["crypto"]
        for param in ("salt", "time_cost", "memory_cost", "parallelism"):
            assert param in data["crypto"]["kdf_params"]


# End-to-end: mnemonic -> seed -> keys -> address -> keystore -> recovery
class TestFullPipeline:

    def test_mnemonic_to_keystore_roundtrip(self, tmp_path):
        words = generate_mnemonic(128)
        seed = mnemonic_to_seed(words)
        pk = derive_private_key(seed, index=0)
        addr = private_key_to_address(pk)

        ks_file = tmp_path / "wallet.json"
        create_keystore(seed, "test_pass", ks_file)

        recovered = load_keystore(ks_file, "test_pass")
        assert private_key_to_address(derive_private_key(recovered, index=0)) == addr

    def test_multiple_unique_accounts(self):
        seed = mnemonic_to_seed(generate_mnemonic(128))
        addresses = [private_key_to_address(k) for k in derive_multiple_keys(seed, 5)]
        assert len(set(addresses)) == 5
