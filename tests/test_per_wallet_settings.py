"""
Tests for per-wallet settings isolation.

These tests verify the fix for the bug where creating a new wallet
inherited the account count and token list from a previously-used wallet
on the same machine.

We test the pure logic (_wallet_id, _load_settings, _save_setting) without
spinning up the GUI - we just instantiate a minimal stand-in that pulls in
the same methods from DashboardScreen.
"""

import hashlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from wallet.gui.dashboard import DashboardScreen


class _SettingsHarness:
    """Minimal stand-in that borrows the settings methods from DashboardScreen.

    We don't want to instantiate the full Tk-based DashboardScreen in tests,
    so we just attach the methods we care about and provide a `seed` attribute.
    """

    SETTINGS_FILE = DashboardScreen.SETTINGS_FILE
    DEFAULT_WALLET_SETTINGS = DashboardScreen.DEFAULT_WALLET_SETTINGS

    _wallet_id = DashboardScreen._wallet_id
    _read_all_settings = DashboardScreen._read_all_settings
    _load_settings = DashboardScreen._load_settings
    _save_setting = DashboardScreen._save_setting

    def __init__(self, seed):
        self.seed = seed


class PerWalletSettingsTests(unittest.TestCase):
    def setUp(self):
        # Each test runs in its own temp dir so SETTINGS_FILE is isolated
        self._tmp = tempfile.TemporaryDirectory()
        self._old_cwd = os.getcwd()
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._old_cwd)
        self._tmp.cleanup()

    # ── wallet_id ────────────────────────────────────────────────────

    def test_wallet_id_is_stable_for_same_seed(self):
        seed = b"\x01" * 64
        a = _SettingsHarness(seed)
        b = _SettingsHarness(seed)
        self.assertEqual(a._wallet_id(), b._wallet_id())

    def test_wallet_id_differs_for_different_seeds(self):
        a = _SettingsHarness(b"\x01" * 64)
        b = _SettingsHarness(b"\x02" * 64)
        self.assertNotEqual(a._wallet_id(), b._wallet_id())

    def test_wallet_id_is_none_without_seed(self):
        self.assertIsNone(_SettingsHarness(None)._wallet_id())

    def test_wallet_id_does_not_leak_raw_seed(self):
        seed = b"super-secret-seed-bytes-do-not-leak"
        wid = _SettingsHarness(seed)._wallet_id()
        # The ID must not contain any contiguous chunk of the seed
        self.assertNotIn("secret", wid)
        self.assertNotIn("seed", wid)
        # And it should be exactly 16 hex chars
        self.assertEqual(len(wid), 16)
        int(wid, 16)  # raises ValueError if not hex

    # ── isolation: the actual bug ─────────────────────────────────────

    def test_new_wallet_does_not_inherit_old_account_count(self):
        """The original bug: wallet A has 4 accounts, wallet B should start with 1."""
        wallet_a = _SettingsHarness(b"A" * 64)
        wallet_b = _SettingsHarness(b"B" * 64)

        # Wallet A grows to 4 accounts
        wallet_a._save_setting("account_count", 4)

        # Wallet B logs in for the first time - should see defaults
        self.assertEqual(wallet_b._load_settings()["account_count"], 1)

    def test_new_wallet_does_not_inherit_old_tokens(self):
        """Same bug, applied to the tracked-tokens list."""
        wallet_a = _SettingsHarness(b"A" * 64)
        wallet_b = _SettingsHarness(b"B" * 64)

        wallet_a._save_setting("tokens", ["0xDEADBEEF", "0xCAFEBABE"])

        self.assertEqual(wallet_b._load_settings()["tokens"], [])

    def test_existing_wallet_still_loads_its_own_state(self):
        """Make sure we didn't break the happy path - re-logging in restores state."""
        wallet = _SettingsHarness(b"A" * 64)
        wallet._save_setting("account_count", 3)
        wallet._save_setting("tokens", ["0xTOKEN"])

        # Simulate "logout + login" by creating a fresh harness with same seed
        same_wallet = _SettingsHarness(b"A" * 64)
        settings = same_wallet._load_settings()
        self.assertEqual(settings["account_count"], 3)
        self.assertEqual(settings["tokens"], ["0xTOKEN"])

    def test_multiple_wallets_coexist_in_one_file(self):
        """Saving from wallet A must not clobber wallet B's data."""
        a = _SettingsHarness(b"A" * 64)
        b = _SettingsHarness(b"B" * 64)

        a._save_setting("account_count", 2)
        b._save_setting("account_count", 5)
        a._save_setting("tokens", ["0xA"])

        self.assertEqual(a._load_settings()["account_count"], 2)
        self.assertEqual(a._load_settings()["tokens"], ["0xA"])
        self.assertEqual(b._load_settings()["account_count"], 5)
        self.assertEqual(b._load_settings()["tokens"], [])

    # ── robustness ────────────────────────────────────────────────────

    def test_missing_settings_file_returns_defaults(self):
        self.assertFalse(os.path.exists("app_settings.json"))
        settings = _SettingsHarness(b"A" * 64)._load_settings()
        self.assertEqual(settings, {"account_count": 1, "tokens": []})

    def test_corrupted_settings_file_returns_defaults(self):
        with open("app_settings.json", "w") as f:
            f.write("not valid json {{{")
        settings = _SettingsHarness(b"A" * 64)._load_settings()
        self.assertEqual(settings, {"account_count": 1, "tokens": []})

    def test_save_without_seed_is_a_noop(self):
        """We should never write to disk if no wallet is loaded."""
        _SettingsHarness(None)._save_setting("account_count", 99)
        self.assertFalse(os.path.exists("app_settings.json"))

    def test_settings_file_does_not_contain_raw_seed(self):
        """Defence-in-depth: even after saving, the seed bytes must not be in the file."""
        seed = b"recognizable-seed-pattern-1234567890"
        wallet = _SettingsHarness(seed)
        wallet._save_setting("account_count", 2)

        with open("app_settings.json", "rb") as f:
            contents = f.read()
        self.assertNotIn(seed, contents)
        self.assertNotIn(b"recognizable", contents)


if __name__ == "__main__":
    unittest.main()
