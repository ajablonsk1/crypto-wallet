from typing import List
from bip_utils import (
    Bip39MnemonicGenerator,
    Bip39SeedGenerator,
    Bip39WordsNum,
    Bip39MnemonicValidator
)

def generate_mnemonic(strength: int = 128) -> List[str]:
    """
    Generates a BIP-39 mnemonic phrase.
    
    Args:
        strength (int): 128 for 12 words (128 bit), 256 for 24 words (256 bit).
        
    Returns:
        List[str]: A list of mnemonic words.
    """
    if strength == 128:
        words_num = Bip39WordsNum.WORDS_NUM_12
    elif strength == 256:
        words_num = Bip39WordsNum.WORDS_NUM_24
    else:
        raise ValueError("Strength must be 128 or 256")
        
    mnemonic = Bip39MnemonicGenerator().FromWordsNumber(words_num)
    return mnemonic.ToStr().split()

def validate_mnemonic(words: List[str]) -> bool:
    """
    Validates a BIP-39 mnemonic phrase.
    
    Args:
        words (List[str]): List of mnemonic words.
        
    Returns:
        bool: True if the mnemonic is valid, False otherwise.
    """
    mnemonic_str = " ".join(words)
    try:
        return Bip39MnemonicValidator().IsValid(mnemonic_str)
    except Exception:
        # In case the bip_utils library version doesn't support IsValid directly
        # and instead we must use Validate which raises exceptions on invalid mnemonics
        try:
            Bip39MnemonicValidator().Validate(mnemonic_str)
            return True
        except Exception:
            return False

def mnemonic_to_seed(words: List[str], passphrase: str = "") -> bytes:
    """
    Converts a BIP-39 mnemonic into a 64-byte seed.
    
    Args:
        words (List[str]): List of mnemonic words.
        passphrase (str): Optional passphrase for seed generation.
        
    Returns:
        bytes: 64-byte seed generated using PBKDF2 with 2048 iterations.
    """
    mnemonic_str = " ".join(words)
    seed_bytes = Bip39SeedGenerator(mnemonic_str).Generate(passphrase)
    return seed_bytes
