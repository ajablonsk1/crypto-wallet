# wallet/gui/dashboard.py

import customtkinter as ctk
from typing import List, Tuple, Optional
from decimal import Decimal
import threading
import json
import os

# Backend imports
from wallet.crypto.keys import derive_private_key, private_key_to_address
from wallet.network.provider import get_eth_balance
from wallet.network.history import get_transaction_history, EtherscanAPIError
from wallet.network.tokens import get_tracked_tokens, get_token_balance, get_token_info, add_custom_token


class DashboardScreen(ctk.CTkFrame):
    """
    Main dashboard for the crypto wallet.
    Handles multiple accounts, balance updates, and transaction history.
    """

    # ── Color Palette ──────────────────────────────────────────────
    BG_COLOR = "#0A0B10"
    PANEL_COLOR = "#15161E"
    ACCENT_1 = "#00FFAA"
    ACCENT_2 = "#FF3377"
    LINK_COLOR = "#0077FF"
    TEXT_WHITE = "#FFFFFF"
    TEXT_SECONDARY = "#999999"
    STATUS_GREEN = "#00CC66"
    STATUS_YELLOW = "#FFAA00"
    STATUS_RED = "#FF3355"

    PAD_LARGE = 30
    PAD_SMALL = 20
    PAD_TINY = 10
    CORNER_RADIUS = 12

    def __init__(self, master, seed: Optional[bytes] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color=self.BG_COLOR)

        # Backend attributes
        self.seed = seed
        self.accounts = []             # List of dicts: {"address": ..., "private_key": ..., "index": ...}
        self.current_account_index = 0 
        self.private_key: Optional[bytes] = None
        self.address: Optional[str] = None
        self._active = True

        # UI Data
        self.eth_balance = Decimal("0")
        self.tokens_data: List[dict] = []
        self.transactions_data: List[dict] = []

        # Widget references
        self.balance_label: Optional[ctk.CTkLabel] = None
        self.address_label: Optional[ctk.CTkLabel] = None
        self.token_table_frame: Optional[ctk.CTkFrame] = None
        self.history_scroll: Optional[ctk.CTkScrollableFrame] = None
        self.accounts_scroll_frame: Optional[ctk.CTkScrollableFrame] = None

        # Navigation callbacks
        self.on_send_click = None
        self.on_logout_click = None

        # Grid layout
        self.grid_columnconfigure(0, weight=1, minsize=250)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content()

        if self.seed is not None:
            # Load settings from file
            settings = self._load_settings()
            
            # Generate all saved accounts
            saved_account_count = settings.get("account_count", 1)
            for i in range(saved_account_count):
                self._add_account_to_list(i)
                
            # Set the first account as active
            self._switch_account(0, initial=True)

            # Load saved tokens in the background to avoid freezing the UI
            saved_tokens = settings.get("tokens", [])
            if saved_tokens:
                threading.Thread(target=self._initialize_saved_tokens, args=(saved_tokens,), daemon=True).start()

    # ================================================================
    #  SETTINGS MANAGEMENT (PERSISTENCE)
    # ================================================================
    def _load_settings(self) -> dict:
        """Loads user settings (accounts and tokens) from a local file."""
        if os.path.exists("app_settings.json"):
            try:
                with open("app_settings.json", "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Dashboard] Error while reading settings: {e}")
        return {"account_count": 1, "tokens": []}

    def _save_setting(self, key: str, value: any):
        """Updates and saves a specific key in the settings file."""
        settings = self._load_settings()
        settings[key] = value
        try:
            with open("app_settings.json", "w") as f:
                json.dump(settings, f)
        except Exception as e:
            print(f"[Dashboard] Error while saving settings: {e}")

    # ================================================================
    #  ACCOUNT MANAGEMENT
    # ================================================================
    def _add_account_to_list(self, index: int):
        """Derives keys for a specific index and adds to the account list."""
        try:
            pk = derive_private_key(self.seed, index)
            addr = private_key_to_address(pk)
            self.accounts.append({
                "address": addr, 
                "private_key": pk, 
                "index": index,
                "name": "Main Wallet" if index == 0 else f"Account #{index}"
            })
        except Exception as e:
            print(f"[Dashboard] Error adding account #{index}: {e}")

    def _switch_account(self, index: int, initial: bool = False):
        """Switches the active wallet account and refreshes data."""
        if not initial and index == self.current_account_index:
            return

        self.current_account_index = index
        account = self.accounts[index]
        self.address = account["address"]
        self.private_key = account["private_key"]

        # Reset UI values before loading new data
        self.eth_balance = Decimal("0")
        self.tokens_data = []
        self.transactions_data = []
        self._update_ui()
        self._rebuild_accounts_list()

        # Start loading data for the new address in background
        threading.Thread(target=self._load_all_data, daemon=True).start()

    def _on_add_account(self):
        """Handler for the 'Add Account' button."""
        next_index = len(self.accounts)
        self._add_account_to_list(next_index)
        print(f"[Dashboard] Added Account #{next_index}")
        self._rebuild_accounts_list()
        
        # Save updated account count to settings
        self._save_setting("account_count", len(self.accounts))

    # ================================================================
    #  TOKEN MANAGEMENT
    # ================================================================
    def _initialize_saved_tokens(self, tokens: List[str]):
        """Loads saved token contracts into the backend."""
        for token_addr in tokens:
            try:
                add_custom_token(token_addr)
            except Exception as e:
                print(f"[Dashboard] Failed to initialize token {token_addr}: {e}")
        
        # Refresh the UI with the newly loaded tokens
        if self._active:
            self._load_all_data()

    def _on_add_token_click(self):
        """Displays a dialog to input an ERC-20 contract address."""
        dialog = ctk.CTkInputDialog(text="Enter ERC-20 Contract Address:", title="Add Custom Token")
        contract_address = dialog.get_input()
        
        if contract_address and contract_address.strip():
            addr = contract_address.strip()
            # Run network call in background to prevent UI freeze
            threading.Thread(target=self._add_token_background, args=(addr,), daemon=True).start()

    def _add_token_background(self, contract_address: str):
        """Handles fetching token info and saving it to settings in the background."""
        try:
            info = add_custom_token(contract_address)
            print(f"[Dashboard] Successfully added token: {info.get('symbol')}")
            
            # Save the new token address to settings
            settings = self._load_settings()
            tokens = settings.get("tokens", [])
            if contract_address not in tokens:
                tokens.append(contract_address)
                self._save_setting("tokens", tokens)
                
            # Refresh dashboard data to show the new token balance
            if self._active:
                self._load_all_data()
        except Exception as e:
            print(f"[Dashboard] Error adding token: {e}")

    # ================================================================
    #  DATA LOADING & UI UPDATES
    # ================================================================
    def _load_all_data(self):
        """Fetches balance, tokens, and history from the blockchain."""
        if not self.address: return
        
        try:
            # 1. ETH Balance
            self.eth_balance = get_eth_balance(self.address)

            # 2. ERC-20 Tokens
            tracked_tokens = get_tracked_tokens()
            new_tokens = []
            for contract in tracked_tokens:
                try:
                    balance = get_token_balance(self.address, contract)
                    info = get_token_info(contract)
                    new_tokens.append({
                        "symbol": info.get("symbol", "???"),
                        "name": info.get("name", "Unknown"),
                        "balance": format(balance, ".4f"),
                        "contract": contract
                    })
                except Exception: continue
            self.tokens_data = new_tokens

            # 3. Transaction History
            try:
                self.transactions_data = get_transaction_history(self.address, page=1, limit=15)
            except EtherscanAPIError:
                self.transactions_data = []

        except Exception as e:
            print(f"[Dashboard] Data loading error: {e}")

        self.after(0, self._update_ui)

    def _update_ui(self):
        """Updates UI components with fresh data."""
        if not self._active: return

        # Format ETH Balance
        eth_str = f"{self.eth_balance:.4f}".rstrip('0').rstrip('.')
        if eth_str.endswith('.'): eth_str = eth_str[:-1]
        if eth_str == "": eth_str = "0"
            
        if self.balance_label:
            self.balance_label.configure(text=f"{eth_str} ETH")

        if self.address_label and self.address:
            short_addr = f"{self.address[:10]}...{self.address[-8:]}"
            self.address_label.configure(text=short_addr)

        if self.token_table_frame:
            self._rebuild_token_table()

        if self.history_scroll:
            self._rebuild_transaction_history()

    # ================================================================
    #  SIDEBAR & CONTENT BUILDING
    # ================================================================
    def _build_sidebar(self):
        """Builds the left sidebar containing account list and actions."""
        sidebar = ctk.CTkFrame(
            self, fg_color=self.PANEL_COLOR, corner_radius=self.CORNER_RADIUS,
            border_width=1, border_color=self.ACCENT_1
        )
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(self.PAD_SMALL, self.PAD_TINY), pady=self.PAD_SMALL)
        sidebar.grid_rowconfigure(2, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            sidebar, text="💼 Accounts", text_color=self.ACCENT_1,
            font=ctk.CTkFont(family="Inter", size=24, weight="bold")
        ).grid(row=0, column=0, padx=self.PAD_LARGE, pady=(self.PAD_LARGE, self.PAD_SMALL), sticky="w")

        # Scrollable area for dynamic accounts list
        self.accounts_scroll_frame = ctk.CTkScrollableFrame(
            sidebar, fg_color="transparent", scrollbar_button_color=self.ACCENT_1
        )
        self.accounts_scroll_frame.grid(row=1, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_SMALL), sticky="nsew")

        # Action Buttons
        ctk.CTkButton(
            sidebar, text="✈️ Send", fg_color=self.ACCENT_2, hover_color="#CC2266",
            command=self._on_send_click
        ).grid(row=3, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_TINY), sticky="ew")

        ctk.CTkButton(
            sidebar, text="➕ Add Account", fg_color=self.LINK_COLOR, hover_color="#0055CC",
            command=self._on_add_account
        ).grid(row=4, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_TINY), sticky="ew")

        ctk.CTkButton(
            sidebar, text="🪙 Add Token", fg_color=self.LINK_COLOR, hover_color="#0055CC",
            command=self._on_add_token_click
        ).grid(row=5, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_TINY), sticky="ew")

        ctk.CTkButton(
            sidebar, text="🚪 Logout", fg_color=self.ACCENT_2, hover_color="#CC2266",
            command=self._on_logout
        ).grid(row=6, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_LARGE), sticky="ew")

    def _rebuild_accounts_list(self):
        """Refreshes the sidebar account list."""
        if not self.accounts_scroll_frame: return
            
        for widget in self.accounts_scroll_frame.winfo_children():
            widget.destroy()

        for i, acc in enumerate(self.accounts):
            is_active = (i == self.current_account_index)
            bg_color = "#2A2B36" if is_active else "transparent"
            
            row = ctk.CTkFrame(self.accounts_scroll_frame, fg_color=bg_color, corner_radius=8)
            row.pack(fill="x", padx=5, pady=4)
            row.bind("<Button-1>", lambda e, idx=i: self._switch_account(idx))
            
            avatar = acc["address"][2:4].upper()
            lbl_avatar = ctk.CTkLabel(row, text=avatar, fg_color=self.BG_COLOR, corner_radius=20, width=35, height=35)
            lbl_avatar.pack(side="left", padx=10, pady=5)
            lbl_avatar.bind("<Button-1>", lambda e, idx=i: self._switch_account(idx))

            short_addr = f"{acc['address'][:6]}...{acc['address'][-4:]}"
            lbl_info = ctk.CTkLabel(
                row, text=f"{acc['name']}\n{short_addr}", justify="left", anchor="w",
                font=ctk.CTkFont(family="Inter", size=12, weight="bold" if is_active else "normal")
            )
            lbl_info.pack(side="left", fill="x", expand=True)
            lbl_info.bind("<Button-1>", lambda e, idx=i: self._switch_account(idx))

    def _build_content(self):
            """Builds the right content panel."""
            content = ctk.CTkFrame(self, fg_color="transparent")
            content.grid(row=0, column=1, sticky="nsew", padx=(self.PAD_TINY, self.PAD_SMALL), pady=self.PAD_SMALL)
            content.grid_columnconfigure(0, weight=1)
                
            content.grid_rowconfigure(0, weight=0)
            content.grid_rowconfigure(1, weight=1)
            content.grid_rowconfigure(2, weight=1)

            self._build_top_cards(content)
            self._build_token_table(content)
            self._build_transaction_history(content)

    def _build_top_cards(self, parent):
        top_frame = ctk.CTkFrame(parent, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew", pady=(0, self.PAD_SMALL))
        top_frame.grid_columnconfigure((0, 1), weight=1)

        # Address Card
        addr_card = ctk.CTkFrame(top_frame, fg_color=self.PANEL_COLOR, border_width=1, border_color=self.ACCENT_1)
        addr_card.grid(row=0, column=0, sticky="nsew", padx=(0, self.PAD_TINY))
        ctk.CTkLabel(addr_card, text="📍 Address", text_color=self.ACCENT_1, font=("Inter", 16, "bold")).pack(anchor="w", padx=20, pady=(20, 5))
        self.address_label = ctk.CTkLabel(addr_card, text="Loading...", font=("SF Mono", 14))
        self.address_label.pack(anchor="w", padx=20, pady=(0, 20))
        ctk.CTkButton(addr_card, text="📋 Copy", fg_color=self.LINK_COLOR, command=self._on_copy_address).pack(side="left", padx=20, pady=(0, 20))

        # Balance Card
        bal_card = ctk.CTkFrame(top_frame, fg_color=self.PANEL_COLOR, border_width=1, border_color=self.ACCENT_2)
        bal_card.grid(row=0, column=1, sticky="nsew", padx=(self.PAD_TINY, 0))
        ctk.CTkLabel(bal_card, text="💰 Balance", text_color=self.ACCENT_2, font=("Inter", 16, "bold")).pack(anchor="w", padx=20, pady=(20, 5))
        self.balance_label = ctk.CTkLabel(bal_card, text="0 ETH", font=("SF Mono", 32, "bold"))
        self.balance_label.pack(anchor="w", padx=20, pady=(0, 20))

    def _build_token_table(self, parent):
            """Builds the token balance table with a scrollbar and complete border."""
            self.token_table_frame = ctk.CTkFrame(
                parent, fg_color=self.PANEL_COLOR, border_width=1, border_color=self.ACCENT_1,
                corner_radius=self.CORNER_RADIUS
            )
            self.token_table_frame.grid(row=1, column=0, sticky="nsew", pady=(0, self.PAD_SMALL))
            
            self.token_table_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="token_cols")
            self.token_table_frame.grid_rowconfigure(1, weight=1)

            for i, h in enumerate(["Symbol", "Name", "Balance"]):
                ctk.CTkLabel(
                    self.token_table_frame, text=h, text_color=self.ACCENT_2, 
                    font=ctk.CTkFont(family="Inter", size=14, weight="bold")
                ).grid(row=0, column=i, padx=20, pady=10, sticky="w")
                
            self._token_content_frame = ctk.CTkScrollableFrame(
                self.token_table_frame, fg_color="transparent", scrollbar_button_color=self.ACCENT_1
            )
            self._token_content_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=5, pady=(0, 10))

    def _rebuild_token_table(self):
            """Refreshes the token table data inside the scrollable container."""
            for w in self._token_content_frame.winfo_children(): 
                w.destroy()
                
            if not self.tokens_data:
                ctk.CTkLabel(
                    self._token_content_frame, text="No tokens found", 
                    text_color=self.TEXT_SECONDARY, font=ctk.CTkFont(family="Inter", size=13)
                ).pack(pady=20)
                return
                
            for t in self.tokens_data:
                row = ctk.CTkFrame(self._token_content_frame, fg_color="transparent")
                row.pack(fill="x", pady=2)
                
                # Use the same column configuration as the header for pixel-perfect alignment
                row.grid_columnconfigure((0, 1, 2), weight=1, uniform="token_cols")
                
                ctk.CTkLabel(row, text=t["symbol"], text_color=self.ACCENT_1, font=ctk.CTkFont(family="Inter", size=13, weight="bold"), anchor="w").grid(row=0, column=0, padx=20, sticky="ew")
                ctk.CTkLabel(row, text=t["name"], text_color=self.TEXT_WHITE, font=ctk.CTkFont(family="Inter", size=13), anchor="w").grid(row=0, column=1, padx=20, sticky="ew")
                ctk.CTkLabel(row, text=t["balance"], text_color=self.TEXT_WHITE, font=ctk.CTkFont(family="SF Mono", size=13), anchor="w").grid(row=0, column=2, padx=20, sticky="ew")

    def _build_transaction_history(self, parent):
        hist_frame = ctk.CTkFrame(parent, fg_color=self.PANEL_COLOR, border_width=1, border_color=self.ACCENT_2)
        hist_frame.grid(row=2, column=0, sticky="nsew")
        hist_frame.grid_columnconfigure(0, weight=1)
        hist_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(hist_frame, text="📜 History", text_color=self.ACCENT_2, font=("Inter", 18, "bold")).grid(row=0, column=0, padx=20, pady=10, sticky="w")
        self.history_scroll = ctk.CTkScrollableFrame(hist_frame, fg_color="transparent", scrollbar_button_color=self.ACCENT_2)
        self.history_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

    def _rebuild_transaction_history(self):
        for w in self.history_scroll.winfo_children(): 
            w.destroy()
            
        if not self.transactions_data:
            ctk.CTkLabel(
                self.history_scroll, text="No history found", 
                text_color=self.TEXT_SECONDARY, font=ctk.CTkFont(family="Inter", size=14)
            ).pack(pady=20)
            return
            
        for tx in self.transactions_data:
            row = ctk.CTkFrame(self.history_scroll, fg_color="transparent")
            row.pack(fill="x", pady=4, padx=5)
            
            # divide history for 2 identical parts
            row.grid_columnconfigure((0, 1), weight=1, uniform="history_cols")
            
            # transaction column
            dir_color = self.STATUS_GREEN if tx['direction'] == "IN" else self.STATUS_RED
            info_text = f"{tx['direction']} | {tx['value']} {tx['symbol']} | {tx['status']}"
            
            ctk.CTkLabel(
                row, text=info_text, font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
                text_color=dir_color, anchor="w"
            ).grid(row=0, column=0, sticky="w")
            
            # hash column
            full_hash = tx.get('hash', '')
            short_hash = f"{full_hash[:6]}...{full_hash[-4:]}" if full_hash else ""
            
            hash_label = ctk.CTkLabel(
                row, text=f"📄 {short_hash}", font=ctk.CTkFont(family="SF Mono", size=13),
                text_color=self.LINK_COLOR, cursor="hand2", anchor="w"
            )
            hash_label.grid(row=0, column=1, sticky="w")
            
            hash_label.bind("<Button-1>", lambda e, h=full_hash, lbl=hash_label: self._copy_tx_hash(h, lbl))

    def _copy_tx_hash(self, tx_hash: str, label: ctk.CTkLabel):
        if not tx_hash: 
            return
            
        self.clipboard_clear()
        self.clipboard_append(tx_hash)
        
        original_text = label.cget("text")
        
        label.configure(text="📋 Copied!", text_color=self.STATUS_GREEN)
        
        self.after(1500, lambda: label.configure(text=original_text, text_color=self.LINK_COLOR) if self._active and label.winfo_exists() else None)

    # ================================================================
    #  HANDLERS
    # ================================================================
    def _on_copy_address(self):
        if self.address:
            self.clipboard_clear()
            self.clipboard_append(self.address)

    def _on_logout(self):
        if self.on_logout_click: self.on_logout_click()

    def _on_send_click(self):
        if self.on_send_click: self.on_send_click()

    def destroy(self):
        self._active = False
        super().destroy()