# wallet/gui/dashboard.py

import customtkinter as ctk
from typing import List, Tuple, Optional
from decimal import Decimal
import threading

# Backend imports
from wallet.crypto.keys import derive_private_key, private_key_to_address
from wallet.network.provider import get_eth_balance
from wallet.network.history import get_transaction_history, EtherscanAPIError
from wallet.network.tokens import get_tracked_tokens, get_token_balance, get_token_info


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
            # Generate first account (index 0) on startup
            self._add_account_to_list(0)
            # Set the first account as active
            self._switch_account(0, initial=True)

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
            sidebar, text="🚪 Logout", fg_color=self.ACCENT_2, hover_color="#CC2266",
            command=self._on_logout
        ).grid(row=5, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_LARGE), sticky="ew")

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
        token_frame = ctk.CTkFrame(parent, fg_color=self.PANEL_COLOR, border_width=1, border_color=self.ACCENT_1)
        token_frame.grid(row=1, column=0, sticky="ew", pady=(0, self.PAD_SMALL))
        token_frame.grid_columnconfigure((0, 1, 2), weight=1)
        for i, h in enumerate(["Symbol", "Name", "Balance"]):
            ctk.CTkLabel(token_frame, text=h, text_color=self.ACCENT_2, font=("Inter", 14, "bold")).grid(row=0, column=i, padx=20, pady=10, sticky="w")
        self._token_content_frame = ctk.CTkFrame(token_frame, fg_color="transparent")
        self._token_content_frame.grid(row=1, column=0, columnspan=3, sticky="ew")

    def _rebuild_token_table(self):
        for w in self._token_content_frame.winfo_children(): w.destroy()
        if not self.tokens_data:
            ctk.CTkLabel(self._token_content_frame, text="No tokens found", text_color=self.TEXT_SECONDARY).pack(pady=10)
            return
        for t in self.tokens_data:
            row = ctk.CTkFrame(self._token_content_frame, fg_color="transparent")
            row.pack(fill="x")
            ctk.CTkLabel(row, text=t["symbol"], text_color=self.ACCENT_1, width=100).pack(side="left", padx=20)
            ctk.CTkLabel(row, text=t["name"], width=200).pack(side="left", padx=20)
            ctk.CTkLabel(row, text=t["balance"], width=100).pack(side="left", padx=20)

    def _build_transaction_history(self, parent):
        hist_frame = ctk.CTkFrame(parent, fg_color=self.PANEL_COLOR, border_width=1, border_color=self.ACCENT_2)
        hist_frame.grid(row=2, column=0, sticky="nsew")
        hist_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(hist_frame, text="📜 History", text_color=self.ACCENT_2, font=("Inter", 18, "bold")).grid(row=0, column=0, padx=20, pady=10, sticky="w")
        self.history_scroll = ctk.CTkScrollableFrame(hist_frame, fg_color="transparent", scrollbar_button_color=self.ACCENT_2)
        self.history_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

    def _rebuild_transaction_history(self):
        for w in self.history_scroll.winfo_children(): w.destroy()
        if not self.transactions_data:
            ctk.CTkLabel(self.history_scroll, text="No history").pack()
            return
        for tx in self.transactions_data:
            ctk.CTkLabel(self.history_scroll, text=f"{tx['direction']} | {tx['value']} {tx['symbol']} | {tx['status']}").pack(fill="x", pady=2)

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