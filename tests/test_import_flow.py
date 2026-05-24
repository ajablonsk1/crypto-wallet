"""
Tests for mnemonic-import end-to-end logic.

We can't easily drive the Tk modal in headless tests, but we CAN verify
the underlying flow: given a valid mnemonic + password, do we get back
the same seed via load_keystore that we'd derive directly via
mnemonic_to_seed? That's the import contract.

We also test the validation rules that the modal enforces (invalid words,
checksum failures, empty input) by calling the same `validate_mnemonic`
function the modal uses.
"""

import os
import tempfile
import unittest

from wallet.crypto.mnemonic import (
    generate_mnemonic,
    mnemonic_to_seed,
    validate_mnemonic,
)
from wallet.crypto.keystore import create_keystore, load_keystore


class ImportFlowTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_cwd = os.getcwd()
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._old_cwd)
        self._tmp.cleanup()

    def test_round_trip_create_then_load(self):
        """The core import contract: same mnemonic + password = same seed."""
        words = generate_mnemonic(strength=128)
        password = "TestPassword123!"

        # Simulate the modal's final action: derive seed, write keystore
        original_seed = mnemonic_to_seed(words, passphrase="")
        create_keystore(original_seed, password, "wallet.json")

        # Simulate next session: unlock with same password
        recovered_seed = load_keystore("wallet.json", password)

        self.assertEqual(original_seed, recovered_seed)

    def test_two_imports_of_same_mnemonic_yield_same_seed(self):
        """Importing the same phrase twice (e.g. on two machines) gives
        identical seeds - this is what makes mnemonic backups work."""
        words = generate_mnemonic(strength=128)

        seed_a = mnemonic_to_seed(words, passphrase="")
        seed_b = mnemonic_to_seed(words, passphrase="")

        self.assertEqual(seed_a, seed_b)

    def test_known_test_vector(self):
        """BIP-39 test vector - sanity check that our derivation matches
        the official spec, not just internally-consistent."""
        # From github.com/trezor/python-mnemonic test_vectors.json
        words = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about".split()
        expected_seed_hex = (
            "5eb00bbddcf069084889a8ab9155568165f5c453ccb85e70811aaed6f6da5fc1"
            "9a5ac40b389cd370d086206dec8aa6c43daea6690f20ad3d8d48b2d2ce9e38e4"
        )
        seed = mnemonic_to_seed(words, passphrase="")
        self.assertEqual(seed.hex(), expected_seed_hex)

    # ── modal's validation gates ─────────────────────────────────────

    def test_rejects_phrase_with_wrong_word(self):
        """Modal's _confirm calls validate_mnemonic; we verify it catches
        a single-word typo (a word that exists in the BIP-39 list but
        breaks the checksum)."""
        good = generate_mnemonic(strength=128)
        # Swap the first word for another BIP-39 word - phrase becomes
        # well-formed but checksum-invalid
        bad = good.copy()
        bad[0] = "zoo" if good[0] != "zoo" else "abandon"
        # Statistically near-certain to fail the checksum
        self.assertFalse(validate_mnemonic(bad))

    def test_rejects_phrase_with_invalid_word(self):
        """Modal's validation should also reject made-up words."""
        bad = ["notaword"] * 12
        self.assertFalse(validate_mnemonic(bad))

    def test_rejects_wrong_length(self):
        """11 or 13 words isn't BIP-39."""
        eleven = generate_mnemonic(strength=128)[:11]
        thirteen = generate_mnemonic(strength=128) + ["abandon"]
        self.assertFalse(validate_mnemonic(eleven))
        self.assertFalse(validate_mnemonic(thirteen))

    def test_paste_phrase_lowercase_handling(self):
        """The modal lowercases pasted words. BIP-39 wordlist is all
        lowercase, so an uppercase paste must still validate."""
        words = generate_mnemonic(strength=128)
        uppercased = [w.upper() for w in words]
        # The modal does: words = clipboard.lower().split()
        normalized = [w.lower() for w in uppercased]
        self.assertTrue(validate_mnemonic(normalized))


if __name__ == "__main__":
    unittest.main()
