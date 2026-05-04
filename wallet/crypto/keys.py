from bip_utils import Bip44, Bip44Coins, Bip44Changes
from eth_keys import keys as eth_keys


def derive_private_key(seed: bytes, index: int = 0) -> bytes:
    if index < 0:
        raise ValueError(f"Index must be non-negative; got {index}")

    bip44 = Bip44.FromSeed(seed, Bip44Coins.ETHEREUM)
    account = (
        bip44.Purpose()
        .Coin()
        .Account(0)
        .Change(Bip44Changes.CHAIN_EXT)
        .AddressIndex(index)
    )
    return account.PrivateKey().Raw().ToBytes()


def derive_multiple_keys(seed: bytes, count: int) -> list[bytes]:
    if count < 1:
        raise ValueError(f"Count must be positive; got {count}")

    return [derive_private_key(seed, i) for i in range(count)]


def private_key_to_public_key(private_key: bytes) -> bytes:
    if len(private_key) != 32:
        raise ValueError(f"Private key must be 32 bytes; got {len(private_key)}")

    return eth_keys.PrivateKey(private_key).public_key.to_bytes()


def private_key_to_address(private_key: bytes) -> str:
    if len(private_key) != 32:
        raise ValueError(f"Private key must be 32 bytes; got {len(private_key)}")

    return eth_keys.PrivateKey(private_key).public_key.to_checksum_address()
