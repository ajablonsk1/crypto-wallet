from typing import Literal
from bip_utils import (
    Bip39MnemonicGenerator,
    Bip39SeedGenerator,
    Bip39WordsNum,
    Bip39MnemonicValidator
)

STRENGTH_MAP = {
    128: Bip39WordsNum.WORDS_NUM_12,
    256: Bip39WordsNum.WORDS_NUM_24,
}


def generate_mnemonic(strength: Literal[128, 256] = 128) -> list[str]:
    if strength not in STRENGTH_MAP:
        raise ValueError(f"Strength must be one of {list(STRENGTH_MAP)}; got {strength!r}")
        
    mnemonic = Bip39MnemonicGenerator().FromWordsNumber(STRENGTH_MAP[strength])
    return mnemonic.ToStr().split()


def validate_mnemonic(words: list[str]) -> bool:
    mnemonic_str = " ".join(words)
    return Bip39MnemonicValidator().IsValid(mnemonic_str)


def mnemonic_to_seed(words: list[str], passphrase: str = "") -> bytes:
    if not validate_mnemonic(words):
        raise ValueError("Invalid mnemonic phrase")
        
    mnemonic_str = " ".join(words)
    seed_bytes = Bip39SeedGenerator(mnemonic_str).Generate(passphrase)
    return seed_bytes
