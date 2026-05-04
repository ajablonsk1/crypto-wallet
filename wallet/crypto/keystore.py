import base64
import json
import os
from pathlib import Path

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


KEYSTORE_VERSION = 1
KDF_NAME = "argon2id"
CIPHER_NAME = "aes-256-gcm"

KEY_LEN = 32
NONCE_LEN = 12
SALT_LEN = 16
TAG_LEN = 16

ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536
ARGON2_PARALLELISM = 4


class InvalidPasswordError(Exception):
    pass


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def _derive_key(password: str, salt: bytes, time_cost: int, memory_cost: int, parallelism: int) -> bytes:
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
        hash_len=KEY_LEN,
        type=Type.ID,
    )


def create_keystore(seed: bytes, password: str, filepath: str | Path) -> None:
    if not password:
        raise ValueError("Password must not be empty")

    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)

    key = _derive_key(password, salt, ARGON2_TIME_COST, ARGON2_MEMORY_COST, ARGON2_PARALLELISM)

    aesgcm = AESGCM(key)
    encrypted = aesgcm.encrypt(nonce, seed, None)
    ciphertext, tag = encrypted[:-TAG_LEN], encrypted[-TAG_LEN:]

    keystore = {
        "version": KEYSTORE_VERSION,
        "crypto": {
            "cipher": CIPHER_NAME,
            "ciphertext": _b64e(ciphertext),
            "nonce": _b64e(nonce),
            "tag": _b64e(tag),
            "kdf": KDF_NAME,
            "kdf_params": {
                "time_cost": ARGON2_TIME_COST,
                "memory_cost": ARGON2_MEMORY_COST,
                "parallelism": ARGON2_PARALLELISM,
                "salt": _b64e(salt),
            },
        },
    }

    Path(filepath).write_text(json.dumps(keystore, indent=2))


def load_keystore(filepath: str | Path, password: str) -> bytes:
    keystore = json.loads(Path(filepath).read_text())

    if keystore.get("version") != KEYSTORE_VERSION:
        raise ValueError(f"Unsupported keystore version: {keystore.get('version')}")

    crypto = keystore["crypto"]
    if crypto["cipher"] != CIPHER_NAME:
        raise ValueError(f"Unsupported cipher: {crypto['cipher']}")
    if crypto["kdf"] != KDF_NAME:
        raise ValueError(f"Unsupported KDF: {crypto['kdf']}")

    kdf_params = crypto["kdf_params"]
    salt = _b64d(kdf_params["salt"])
    nonce = _b64d(crypto["nonce"])
    ciphertext = _b64d(crypto["ciphertext"])
    tag = _b64d(crypto["tag"])

    key = _derive_key(
        password,
        salt,
        kdf_params["time_cost"],
        kdf_params["memory_cost"],
        kdf_params["parallelism"],
    )

    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ciphertext + tag, None)
    except InvalidTag:
        raise InvalidPasswordError("Invalid password or corrupted keystore")


def change_password(filepath: str | Path, old_password: str, new_password: str) -> None:
    seed = load_keystore(filepath, old_password)
    create_keystore(seed, new_password, filepath)
