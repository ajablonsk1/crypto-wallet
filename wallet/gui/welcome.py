# wallet/gui/welcome.py

import os

import customtkinter as ctk
from wallet.crypto.mnemonic import generate_mnemonic, validate_mnemonic, mnemonic_to_seed
from wallet.crypto.keystore import create_keystore, load_keystore, InvalidPasswordError

class WelcomeScreen(ctk.CTkFrame):

    # ── color palette ──────────────────────────────────────────────
    BG_COLOR = "#0A0B10"        
    PANEL_COLOR = "#15161E"     
    ACCENT_1 = "#00FFAA"        
    ACCENT_2 = "#FF3377"        
    LINK_COLOR = "#0077FF"
    TEXT_WHITE = "#FFFFFF"
    PLACEHOLDER_COLOR = "#666666"

    # ── size and padding ─────────────────────────────────────────
    PAD_LARGE = 30
    PAD_SMALL = 20
    PAD_TINY = 10
    CORNER_RADIUS = 15
    BORDER_WIDTH = 1

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.on_unlock_success = None
        self.on_create_wallet_success = None
        self.seed = None
        self._active = True

        # ── mainframe ──────────────────────────────
        self.configure(fg_color=self.BG_COLOR)
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        # ── interface ──────────────────────────────────────
        self._build_left_panel()
        self._build_right_panel()

        # generate mnemonic on starrt
        self._on_generate_click()

    # ================================================================
    #  Unlock Wallet
    # ================================================================
    def _build_left_panel(self):
        """Left panel with password field and Unlock button."""
        self.left_frame = ctk.CTkFrame(
            self,
            fg_color=self.PANEL_COLOR,
            corner_radius=self.CORNER_RADIUS,
            border_width=self.BORDER_WIDTH,
            border_color=self.ACCENT_1
        )
        self.left_frame.grid(
            row=0, column=0,
            sticky="nsew",
            padx=(self.PAD_SMALL, self.PAD_TINY),
            pady=self.PAD_SMALL
        )
        self.left_frame.grid_rowconfigure(0, weight=0)  # title
        self.left_frame.grid_rowconfigure(1, weight=0)  # entry
        self.left_frame.grid_rowconfigure(2, weight=0)  # unlock button
        self.left_frame.grid_rowconfigure(3, weight=0)  # show/hide toggle
        self.left_frame.grid_rowconfigure(4, weight=0)  # error label
        self.left_frame.grid_rowconfigure(5, weight=1)  # spacer
        self.left_frame.grid_rowconfigure(6, weight=0)  # separator
        self.left_frame.grid_rowconfigure(7, weight=0)  # import button
        self.left_frame.grid_columnconfigure(0, weight=1)

        # title
        ctk.CTkLabel(
            self.left_frame,
            text="🔓 Unlock Wallet",
            font=ctk.CTkFont(family="Inter", size=26, weight="bold"),
            text_color=self.ACCENT_1
        ).grid(row=0, column=0, padx=self.PAD_LARGE, pady=(self.PAD_LARGE, self.PAD_SMALL), sticky="w")

        # password
        self.password_entry = ctk.CTkEntry(
            self.left_frame,
            placeholder_text="Enter your password",
            show="*",
            font=ctk.CTkFont(family="Inter", size=16),
            fg_color=self.BG_COLOR,
            border_color=self.ACCENT_1,
            text_color=self.TEXT_WHITE,
            placeholder_text_color=self.PLACEHOLDER_COLOR
        )
        self.password_entry.grid(
            row=1, column=0,
            padx=self.PAD_LARGE, pady=(0, self.PAD_SMALL),
            sticky="ew"
        )

        # unlock
        ctk.CTkButton(
            self.left_frame,
            text="🚀 Unlock",
            font=ctk.CTkFont(family="Inter", size=16, weight="bold"),
            fg_color=self.ACCENT_1,
            text_color=self.BG_COLOR,
            hover_color="#00CC88",
            corner_radius=10,
            command=self._on_unlock_click
        ).grid(row=2, column=0, padx=self.PAD_LARGE, pady=(0, self.PAD_SMALL), sticky="ew")

        # show/hide password toggle
        self._unlock_show_password = False
        self.unlock_show_btn = ctk.CTkButton(
            self.left_frame,
            text="👁 Show password",
            font=ctk.CTkFont(family="Inter", size=12),
            fg_color="transparent",
            text_color=self.PLACEHOLDER_COLOR,
            hover_color=self.PANEL_COLOR,
            height=24,
            anchor="w",
            command=self._toggle_unlock_password,
        )
        self.unlock_show_btn.grid(row=3, column=0, padx=self.PAD_LARGE, pady=(0, 4), sticky="w")

        # error label
        self.unlock_error_label = ctk.CTkLabel(
            self.left_frame,
            text="",
            font=ctk.CTkFont(family="Inter", size=12),
            text_color="#FF3355",
            anchor="w"
        )
        self.unlock_error_label.grid(row=4, column=0, padx=self.PAD_LARGE, pady=(0, 4), sticky="w")
        self.unlock_error_label.grid_remove()  # hide on start

        # ── separator + import button ─────────────────────────────────
        separator = ctk.CTkFrame(self.left_frame, height=1, fg_color="#2A2B36")
        separator.grid(row=6, column=0, padx=self.PAD_LARGE, pady=(self.PAD_SMALL, self.PAD_TINY), sticky="ew")

        # subtle "import existing wallet" button - styled as a link so it
        # doesn't compete visually with the primary "Unlock" button
        ctk.CTkButton(
            self.left_frame,
            text="📥 Import existing wallet (from mnemonic)",
            font=ctk.CTkFont(family="Inter", size=13),
            fg_color="transparent",
            text_color=self.LINK_COLOR,
            hover_color=self.BG_COLOR,
            height=32,
            command=self._on_import_click,
        ).grid(row=7, column=0, padx=self.PAD_LARGE, pady=(0, self.PAD_LARGE), sticky="ew")

    # ================================================================
    # Create New Wallet
    # ================================================================
    def _build_right_panel(self):
        """Prawy panel z siatką mnemoniczną i przyciskami."""
        self.right_frame = ctk.CTkFrame(
            self,
            fg_color=self.PANEL_COLOR,
            corner_radius=self.CORNER_RADIUS,
            border_width=self.BORDER_WIDTH,
            border_color=self.ACCENT_2
        )
        self.right_frame.grid(
            row=0, column=1,
            sticky="nsew",
            padx=(self.PAD_TINY, self.PAD_SMALL),
            pady=self.PAD_SMALL
        )
        self.right_frame.grid_rowconfigure(0, weight=0)  # title
        self.right_frame.grid_rowconfigure(1, weight=1)  # grid
        self.right_frame.grid_rowconfigure(2, weight=0)  # buttons
        self.right_frame.grid_columnconfigure(0, weight=1)

        # title
        ctk.CTkLabel(
            self.right_frame,
            text="🪙 Create New Wallet",
            font=ctk.CTkFont(family="Inter", size=26, weight="bold"),
            text_color=self.ACCENT_2
        ).grid(row=0, column=0, padx=self.PAD_LARGE, pady=(self.PAD_LARGE, self.PAD_SMALL), sticky="w")
        self._build_mnemonic_grid()

        # ── buttons ────────────────────────────────────────
        self._build_action_buttons()

        # error label
        self.create_error_label = ctk.CTkLabel(
            self.right_frame,
            text="",
            font=ctk.CTkFont(family="Inter", size=12),
            text_color="#FF3355",
            anchor="w"
        )
        self.create_error_label.grid(row=3, column=0, padx=self.PAD_LARGE, pady=(0, self.PAD_LARGE), sticky="w")
        self.create_error_label.grid_remove()

    def _build_mnemonic_grid(self):
        grid_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        grid_frame.grid(row=1, column=0, padx=self.PAD_LARGE, pady=self.PAD_LARGE)

        self.mnemonic_labels = []
        
        sample_words = ["abandon", "ability", "able", "about", "above", "absent", 
                        "absorb", "abstract", "absurd", "abuse", "access", "accident"]

        for row in range(3):
            for col in range(4):
                index = row * 4 + col
                
                # cell frame
                cell_frame = ctk.CTkFrame(
                    grid_frame, 
                    width=120, 
                    height=45, 
                    fg_color="#0A1510",
                    border_width=1,
                    border_color="#005533",
                    corner_radius=8
                )
                cell_frame.grid(row=row, column=col, padx=8, pady=8)
                cell_frame.grid_propagate(False)
                
                num_label = ctk.CTkLabel(
                    cell_frame, 
                    text=str(index + 1), 
                    font=ctk.CTkFont(family="Inter", size=10), 
                    text_color="#666666"
                )
                num_label.place(x=6, y=2)
                
                word_label = ctk.CTkLabel(
                    cell_frame,
                    text=sample_words[index],
                    font=ctk.CTkFont(family="SF Mono", size=14, weight="bold"),
                    text_color=self.ACCENT_1
                )
                word_label.place(relx=0.5, rely=0.5, anchor="center")
                
                self.mnemonic_labels.append(word_label)

    def _build_action_buttons(self):
        btn_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, padx=self.PAD_LARGE, pady=(0, self.PAD_LARGE), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Copy
        ctk.CTkButton(
            btn_frame,
            text="📋 Copy",
            font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
            fg_color=self.LINK_COLOR,
            text_color=self.TEXT_WHITE,
            hover_color="#0055CC",
            corner_radius=10,
            command=self._on_copy_click
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")

        # Generate New
        self.generate_btn = ctk.CTkButton(
            btn_frame,
            text="🎲 Generate New",
            font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
            fg_color=self.LINK_COLOR,
            text_color=self.TEXT_WHITE,
            hover_color="#0055CC",
            corner_radius=10,
            command=self._on_generate_click
        )
        self.generate_btn.grid(row=0, column=1, padx=4, sticky="ew")

        # Create Wallet
        ctk.CTkButton(
            btn_frame,
            text="✨ Create Wallet",
            font=ctk.CTkFont(family="Inter", size=16, weight="bold"),
            fg_color=self.ACCENT_2,
            text_color=self.TEXT_WHITE,
            hover_color="#CC2266",
            corner_radius=10,
            command=self._on_create_wallet_click
        ).grid(row=0, column=2, padx=(4, 0), sticky="ew")

    # ================================================================
    #  CALLBACKS 
    # ================================================================
    def destroy(self):
        self._active = False
        super().destroy()

    def _on_unlock_click(self):
        password = self.password_entry.get()
        if not password:
            self._show_unlock_error("Password cannot be empty.")
            return

        self._clear_unlock_error()

        try:
            seed = load_keystore("wallet.json", password)
        except FileNotFoundError:
            self._show_unlock_error("Keystore file 'wallet.json' not found.")
            return
        except InvalidPasswordError:
            self._show_unlock_error("Invalid password.")
            return
        except Exception as e:
            self._show_unlock_error(f"Unexpected error: {str(e)}")
            return

        self.seed = seed
        print("[Unlock] Wallet unlocked successfully.")
        if self.on_unlock_success:
            self.on_unlock_success(self.seed)

    def _on_import_click(self):
        """Open the import-mnemonic modal and, on success, create a fresh
        keystore from the supplied recovery phrase + new password.

        This overwrites any existing wallet.json on disk - we ask the user
        to confirm inside the modal before that happens.
        """
        # Warn if an existing wallet would be overwritten. The modal also
        # has its own confirmation, but we want to surface this immediately.
        existing_keystore = os.path.exists("wallet.json")

        dialog = ImportMnemonicModal(self.winfo_toplevel(), warn_overwrite=existing_keystore)
        self.wait_window(dialog)

        result = dialog.get_result()
        if result is None:
            return  # user cancelled

        words, password = result

        try:
            seed = mnemonic_to_seed(words, passphrase="")
            create_keystore(seed, password, "wallet.json")
        except Exception as e:
            self._show_unlock_error(f"Import failed: {str(e)}")
            return

        self.seed = seed
        print("[Import] Wallet imported successfully from mnemonic.")
        if self.on_create_wallet_success:
            # Reuse the same downstream callback as Create Wallet - the
            # dashboard doesn't need to know whether the seed came from a
            # fresh generation or a recovery import.
            self.on_create_wallet_success(self.seed)

    def _toggle_unlock_password(self):
        self._unlock_show_password = not self._unlock_show_password
        self.password_entry.configure(show="" if self._unlock_show_password else "*")
        self.unlock_show_btn.configure(text="🙈 Hide password" if self._unlock_show_password else "👁 Show password")

    def _show_unlock_error(self, message: str):
        self.unlock_error_label.configure(text=message)
        self.unlock_error_label.grid()
        self.password_entry.configure(border_color="#FF3355")

    def _clear_unlock_error(self):
        self.unlock_error_label.grid_remove()
        self.password_entry.configure(border_color=self.ACCENT_1)

    def _on_copy_click(self):
        words = [label.cget("text") for label in self.mnemonic_labels]
        mnemonic = " ".join(words)
        self.clipboard_clear()
        self.clipboard_append(mnemonic)
        print(f"[Copy] Mnemonic phrase copied")

    def _on_generate_click(self):
        if hasattr(self, 'generate_btn'):
            self.generate_btn.configure(state="disabled")
        words = generate_mnemonic(strength=128)
        for i, label in enumerate(self.mnemonic_labels):
            label.configure(text=words[i])
        if hasattr(self, 'generate_btn'):
            self.generate_btn.configure(state="normal")

    def _on_create_wallet_click(self):
        words = [label.cget("text") for label in self.mnemonic_labels]
        if not validate_mnemonic(words):
            self._show_create_error("Invalid mnemonic phrase.")
            return

        self._clear_create_error()

        dialog = PasswordModal(self.winfo_toplevel())
        self.wait_window(dialog)
        password = dialog.get_password()
        
        if not password:
            return

        try:
            seed = mnemonic_to_seed(words, passphrase="")
            create_keystore(seed, password, "wallet.json")
        except Exception as e:
            self._show_create_error(f"Failed to create wallet: {str(e)}")
            return

        self.seed = seed
        print("[Create Wallet] Wallet created successfully.")
        if self.on_create_wallet_success:
            self.on_create_wallet_success(self.seed)

    def _show_create_error(self, message: str):
        self.create_error_label.configure(text=message)
        self.create_error_label.grid()

    def _clear_create_error(self):
        self.create_error_label.grid_remove()


class PasswordModal(ctk.CTkToplevel):

    # Super stylish neon style.
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._password = None
        
        self.title("Set Wallet Password")
        self.geometry("400x390")
        self.resizable(False, False)
        self.configure(fg_color="#0A0B10")
        self.transient(master)

        self.wait_visibility()
        self.grab_set()

        self._show_password = False

        main_frame = ctk.CTkFrame(self, fg_color="#15161E", corner_radius=15, border_width=1, border_color="#00FFAA")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_frame, text="🔒 Set Password", font=ctk.CTkFont(family="Inter", size=22, weight="bold"), text_color="#00FFAA").pack(pady=(20, 10))

        self.pass_entry = ctk.CTkEntry(main_frame, placeholder_text="Enter password", show="*", font=ctk.CTkFont(family="Inter", size=14), fg_color="#0A0B10", border_color="#00FFAA", text_color="#FFFFFF", height=40)
        self.pass_entry.pack(fill="x", padx=30, pady=(10, 4))

        self.confirm_entry = ctk.CTkEntry(main_frame, placeholder_text="Confirm password", show="*", font=ctk.CTkFont(family="Inter", size=14), fg_color="#0A0B10", border_color="#00FFAA", text_color="#FFFFFF", height=40)
        self.confirm_entry.pack(fill="x", padx=30, pady=(0, 4))

        self.show_btn = ctk.CTkButton(
            main_frame, text="👁 Show password",
            font=ctk.CTkFont(family="Inter", size=12),
            fg_color="transparent", text_color="#666666",
            hover_color="#1A1B24", height=24,
            command=self._toggle_show_password,
        )
        self.show_btn.pack(anchor="w", padx=26, pady=(0, 4))

        self.error_label = ctk.CTkLabel(main_frame, text="", font=ctk.CTkFont(family="Inter", size=12), text_color="#FF3355")
        self.error_label.pack(pady=(0, 6))

        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=(0, 20))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(btn_frame, text="❌ Cancel", font=ctk.CTkFont(family="Inter", size=14, weight="bold"), fg_color="#FF3377", text_color="#FFFFFF", hover_color="#CC2266", height=40, command=self._cancel).grid(row=0, column=0, padx=(0, 5), sticky="ew")
        ctk.CTkButton(btn_frame, text="✅ Confirm", font=ctk.CTkFont(family="Inter", size=14, weight="bold"), fg_color="#00FFAA", text_color="#0A0B10", hover_color="#00CC88", height=40, command=self._confirm).grid(row=0, column=1, padx=(5, 0), sticky="ew")

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _toggle_show_password(self):
        self._show_password = not self._show_password
        show_char = "" if self._show_password else "*"
        self.pass_entry.configure(show=show_char)
        self.confirm_entry.configure(show=show_char)
        self.show_btn.configure(text="🙈 Hide password" if self._show_password else "👁 Show password")

    def _confirm(self):
        p1 = self.pass_entry.get()
        p2 = self.confirm_entry.get()
        if not p1:
            self.error_label.configure(text="Password cannot be empty")
            return
        if p1 != p2:
            self.error_label.configure(text="Passwords do not match")
            return
        self._password = p1
        self.destroy()

    def _cancel(self):
        self._password = None
        self.destroy()

    def get_password(self):
        return self._password


class ImportMnemonicModal(ctk.CTkToplevel):
    """Modal for importing a wallet from a BIP-39 mnemonic phrase.

    Asks for:
      - 12 words (one entry per word)
      - new password (twice, with confirmation)

    On confirm, validates the mnemonic via Bip39MnemonicValidator (the same
    one used during Create Wallet) and returns (words, password) to the caller.
    The caller is responsible for actually creating the keystore - we just
    collect input.

    A warning is shown when warn_overwrite=True so the user knows their
    current wallet.json will be replaced.
    """

    BG = "#0A0B10"
    PANEL = "#15161E"
    ACCENT = "#00FFAA"
    DANGER = "#FF3355"
    TEXT_SECONDARY = "#999999"
    PLACEHOLDER = "#666666"

    def __init__(self, master, warn_overwrite: bool = False, **kwargs):
        super().__init__(master, **kwargs)
        self._words = None
        self._password = None

        self.title("Import Wallet from Mnemonic")
        self.geometry("560x640")
        self.resizable(False, False)
        self.configure(fg_color=self.BG)
        self.transient(master)

        self.wait_visibility()
        self.grab_set()

        main = ctk.CTkFrame(self, fg_color=self.PANEL, corner_radius=15, border_width=1, border_color=self.ACCENT)
        main.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            main, text="📥 Import Wallet",
            font=ctk.CTkFont(family="Inter", size=22, weight="bold"),
            text_color=self.ACCENT,
        ).pack(pady=(20, 4))

        ctk.CTkLabel(
            main, text="Enter your 12-word recovery phrase",
            font=ctk.CTkFont(family="Inter", size=12),
            text_color=self.TEXT_SECONDARY,
        ).pack(pady=(0, 10))

        # ── 12-word grid ──────────────────────────────────────────────
        grid_frame = ctk.CTkFrame(main, fg_color="transparent")
        grid_frame.pack(padx=20, pady=(0, 10))

        self.word_entries = []
        for row in range(3):
            for col in range(4):
                idx = row * 4 + col

                cell = ctk.CTkFrame(grid_frame, fg_color="transparent")
                cell.grid(row=row, column=col, padx=4, pady=4)

                ctk.CTkLabel(
                    cell, text=str(idx + 1),
                    font=ctk.CTkFont(family="Inter", size=10),
                    text_color=self.PLACEHOLDER, width=18,
                ).pack(side="left", padx=(0, 4))

                entry = ctk.CTkEntry(
                    cell, width=90, height=30,
                    font=ctk.CTkFont(family="Inter", size=12),
                    fg_color=self.BG, border_color="#005533",
                    text_color="#FFFFFF",
                )
                entry.pack(side="left")
                self.word_entries.append(entry)

        # ── paste-all helper ──────────────────────────────────────────
        # Recovery phrases are usually stored as a single line - typing
        # them word-by-word is tedious and error-prone. This button lets
        # the user paste the whole phrase at once and we split it for them.
        ctk.CTkButton(
            main, text="📋 Paste full phrase",
            font=ctk.CTkFont(family="Inter", size=12),
            fg_color="transparent", text_color="#0077FF",
            hover_color=self.BG, height=24,
            command=self._paste_phrase,
        ).pack(pady=(0, 10))

        # ── password fields ───────────────────────────────────────────
        ctk.CTkLabel(
            main, text="Set a password for this imported wallet",
            font=ctk.CTkFont(family="Inter", size=12),
            text_color=self.TEXT_SECONDARY,
        ).pack(pady=(4, 6))

        self.pass_entry = ctk.CTkEntry(
            main, placeholder_text="Password", show="*",
            font=ctk.CTkFont(family="Inter", size=14),
            fg_color=self.BG, border_color=self.ACCENT,
            text_color="#FFFFFF", height=36,
        )
        self.pass_entry.pack(fill="x", padx=30, pady=(0, 4))

        self.confirm_entry = ctk.CTkEntry(
            main, placeholder_text="Confirm password", show="*",
            font=ctk.CTkFont(family="Inter", size=14),
            fg_color=self.BG, border_color=self.ACCENT,
            text_color="#FFFFFF", height=36,
        )
        self.confirm_entry.pack(fill="x", padx=30, pady=(0, 4))

        self._show_password = False
        self.show_btn = ctk.CTkButton(
            main, text="👁 Show password",
            font=ctk.CTkFont(family="Inter", size=11),
            fg_color="transparent", text_color=self.PLACEHOLDER,
            hover_color=self.BG, height=22,
            command=self._toggle_show_password,
        )
        self.show_btn.pack(anchor="w", padx=26, pady=(0, 4))

        # ── overwrite warning (only when wallet.json already exists) ──
        if warn_overwrite:
            ctk.CTkLabel(
                main,
                text="⚠ This will replace your existing wallet.json",
                font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
                text_color=self.DANGER,
            ).pack(pady=(4, 0))

        # ── error label ───────────────────────────────────────────────
        self.error_label = ctk.CTkLabel(
            main, text="",
            font=ctk.CTkFont(family="Inter", size=12),
            text_color=self.DANGER,
        )
        self.error_label.pack(pady=(4, 4))

        # ── buttons ───────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=(4, 20))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            btn_frame, text="❌ Cancel",
            font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
            fg_color="#FF3377", text_color="#FFFFFF",
            hover_color="#CC2266", height=40,
            command=self._cancel,
        ).grid(row=0, column=0, padx=(0, 5), sticky="ew")

        ctk.CTkButton(
            btn_frame, text="✅ Import",
            font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
            fg_color=self.ACCENT, text_color=self.BG,
            hover_color="#00CC88", height=40,
            command=self._confirm,
        ).grid(row=0, column=1, padx=(5, 0), sticky="ew")

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _paste_phrase(self):
        """Read the clipboard and distribute words across the 12 entries.

        Accepts any whitespace-separated phrase. If the user pastes more
        than 12 words, the extras are ignored; if fewer, the remaining
        entries are left untouched. Validation happens in _confirm.
        """
        try:
            clipboard_text = self.clipboard_get()
        except Exception:
            self.error_label.configure(text="Clipboard is empty or unreadable")
            return

        words = clipboard_text.strip().lower().split()
        for entry, word in zip(self.word_entries, words):
            entry.delete(0, "end")
            entry.insert(0, word)

    def _toggle_show_password(self):
        self._show_password = not self._show_password
        show_char = "" if self._show_password else "*"
        self.pass_entry.configure(show=show_char)
        self.confirm_entry.configure(show=show_char)
        self.show_btn.configure(text="🙈 Hide password" if self._show_password else "👁 Show password")

    def _confirm(self):
        # ── collect & validate words ──────────────────────────────────
        words = [e.get().strip().lower() for e in self.word_entries]

        if any(not w for w in words):
            self.error_label.configure(text="All 12 words are required")
            return

        if not validate_mnemonic(words):
            # validate_mnemonic checks both the wordlist membership and
            # the checksum bits, so this catches typos as well as random
            # made-up phrases.
            self.error_label.configure(text="Invalid mnemonic (wrong words or checksum)")
            return

        # ── validate password ─────────────────────────────────────────
        p1 = self.pass_entry.get()
        p2 = self.confirm_entry.get()
        if not p1:
            self.error_label.configure(text="Password cannot be empty")
            return
        if p1 != p2:
            self.error_label.configure(text="Passwords do not match")
            return

        self._words = words
        self._password = p1
        self.destroy()

    def _cancel(self):
        self._words = None
        self._password = None
        self.destroy()

    def get_result(self):
        """Returns (words, password) on success, or None if cancelled."""
        if self._words is None or self._password is None:
            return None
        return self._words, self._password


# ── Tests
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")

    root = ctk.CTk()
    root.title("Crypto Wallet – Welcome")
    root.geometry("1000x600")
    root.minsize(800, 500)

    app = WelcomeScreen(root)
    app.pack(fill="both", expand=True)

    root.mainloop()
