from typing import List
from bip_utils import (
    Bip39MnemonicGenerator,
    Bip39SeedGenerator,
    Bip39WordsNum,
    Bip39MnemonicValidator
)

def generate_mnemonic(strength: int = 128) -> List[str]:
    if strength == 128:
        words_num = Bip39WordsNum.WORDS_NUM_12
    elif strength == 256:
        words_num = Bip39WordsNum.WORDS_NUM_24
    else:
        raise ValueError("Strength must be 128 or 256")
        
    mnemonic = Bip39MnemonicGenerator().FromWordsNumber(words_num)
    return mnemonic.ToStr().split()


def validate_mnemonic(words: List[str]) -> bool:
    mnemonic_str = " ".join(words)
    try:
        return Bip39MnemonicValidator().IsValid(mnemonic_str)
    except Exception:
        try:
            Bip39MnemonicValidator().Validate(mnemonic_str)
            return True
        except Exception:
            return False


def mnemonic_to_seed(words: List[str], passphrase: str = "") -> bytes:
    mnemonic_str = " ".join(words)
    seed_bytes = Bip39SeedGenerator(mnemonic_str).Generate(passphrase)
    return seed_bytes
