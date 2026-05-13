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
    Główny dashboard portfela kryptowalutowego.
    Przyjmuje seed, oblicza adres, ładuje dane z blockchaina.
    """

    # ── Paleta kolorów ──────────────────────────────────────────────
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

        # Atrybuty backendu
        self.seed = seed
        self.private_key: Optional[bytes] = None
        self.address: Optional[str] = None
        self._active = True

        # Dane UI (aktualizowane asynchronicznie)
        self.eth_balance = Decimal("0")
        self.tokens_data: List[dict] = []
        self.transactions_data: List[dict] = []

        # Referencje do widgetów (do późniejszej aktualizacji)
        self.balance_label: Optional[ctk.CTkLabel] = None
        self.address_label: Optional[ctk.CTkLabel] = None
        self.token_table_frame: Optional[ctk.CTkFrame] = None
        self.history_scroll: Optional[ctk.CTkScrollableFrame] = None
        self.sidebar_balance_label: Optional[ctk.CTkLabel] = None
        self.avatar_label: Optional[ctk.CTkLabel] = None

        # Callbacki nawigacyjne
        self.on_send_click = None
        self.on_logout_click = None

        # Główny layout
        self.grid_columnconfigure(0, weight=1, minsize=250)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content()

        # Jeśli mamy seed – oblicz klucze i uruchom ładowanie danych
        if self.seed is not None:
            self._init_keys_and_address()
            # Rozpocznij ładowanie w tle
            threading.Thread(target=self._load_all_data, daemon=True).start()

    # ================================================================
    #  INICJALIZACJA BACKENDU
    # ================================================================
    def _init_keys_and_address(self):
        """Oblicza klucz prywatny i adres z seedu."""
        try:
            self.private_key = derive_private_key(self.seed, 0)
            self.address = private_key_to_address(self.private_key)
        except Exception as e:
            print(f"[Dashboard] Key derivation error: {e}")
            # W przypadku błędu zostawiamy placeholder
            self.address = "0x0000000000000000000000000000000000000000"

    def _load_all_data(self):
        """Ładuje saldo, tokeny i historię w tle."""
        try:
            # 1. Saldo ETH
            if self.address:
                bal = get_eth_balance(self.address)
                self.eth_balance = bal

            # 2. Tokeny ERC-20
            tracked_tokens = get_tracked_tokens()
            self.tokens_data = []
            for contract in tracked_tokens:
                try:
                    balance = get_token_balance(self.address, contract)
                    info = get_token_info(contract)
                    self.tokens_data.append({
                        "symbol": info.get("symbol", "???"),
                        "name": info.get("name", "Unknown"),
                        "balance": format(balance, ".4f"),
                        "contract": contract
                    })
                except Exception as e:
                    print(f"[Tokens] Error loading {contract}: {e}")

            # 3. Historia transakcji
            self.transactions_data = []
            try:
                txns = get_transaction_history(self.address, page=1, limit=15)
                for tx in txns:
                    self.transactions_data.append({
                        "hash": tx.get("hash", ""),
                        "from": tx.get("from", ""),
                        "to": tx.get("to", ""),
                        "value": tx.get("value", "0"),
                        "symbol": tx.get("symbol", "ETH"),
                        "status": tx.get("status", "pending"),
                        "timestamp": tx.get("timestamp", ""),
                        "direction": tx.get("direction", "OUT")
                    })
            except EtherscanAPIError as e:
                print(f"[History] Etherscan error: {e}")

        except Exception as e:
            print(f"[Dashboard] Data loading error: {e}")

        # Po zakończeniu – aktualizacja UI w głównym wątku
        self.after(0, self._update_ui)

    def _update_ui(self):
        """Aktualizuje widżety po załadowaniu danych."""
        if not self._active:
            return

        eth_str = f"{self.eth_balance:.4f}".rstrip('0').rstrip('.')
        if eth_str.endswith('.'):
            eth_str = eth_str[:-1]
        if eth_str == "":
            eth_str = "0"
            
        # Aktualizacja salda
        if self.balance_label:
            self.balance_label.configure(text=f"{eth_str} ETH")
            
        # Aktualizacja w sidebarze
        if hasattr(self, 'sidebar_balance_label') and self.sidebar_balance_label:
            self.sidebar_balance_label.configure(text=f"{eth_str} ETH")

        # Adres (jeśli nie był wcześniej ustawiony)
        if self.address_label and self.address:
            short_addr = f"{self.address[:10]}...{self.address[-8:]}"
            self.address_label.configure(text=short_addr)

        if hasattr(self, 'avatar_label') and self.avatar_label and self.address:
            self.avatar_label.configure(text=self.address[2:4].upper())

        # Tokeny – odbuduj tabelkę
        if self.token_table_frame and self.tokens_data:
            self._rebuild_token_table()

        # Historia transakcji
        if self.history_scroll and self.transactions_data:
            self._rebuild_transaction_history()

    # ================================================================
    #  SIDEBAR – Accounts
    # ================================================================
    def _build_sidebar(self):
        """Lewy panel z listą kont i przyciskami."""
        sidebar = ctk.CTkFrame(
            self,
            fg_color=self.PANEL_COLOR,
            corner_radius=self.CORNER_RADIUS,
            border_width=1,
            border_color=self.ACCENT_1
        )
        sidebar.grid(row=0, column=0, sticky="nsew",
                     padx=(self.PAD_SMALL, self.PAD_TINY),
                     pady=self.PAD_SMALL)
        sidebar.grid_rowconfigure(2, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)

        # Nagłówek
        ctk.CTkLabel(
            sidebar,
            text="💼 Accounts",
            font=ctk.CTkFont(family="Inter", size=24, weight="bold"),
            text_color=self.ACCENT_1
        ).grid(row=0, column=0, padx=self.PAD_LARGE, pady=(self.PAD_LARGE, self.PAD_SMALL), sticky="w")

        # Lista kont – tylko jedno konto (główne)
        accounts_frame = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent",
            scrollbar_button_color=self.ACCENT_1,
            scrollbar_button_hover_color="#00CC88"
        )
        accounts_frame.grid(row=1, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_SMALL), sticky="nsew")

        # Główne konto – jeśli mamy adres, użyj pierwszych 2 liter jako awatar
        avatar_letter = (self.address or "0x")[2:4].upper() if self.address else "MW"
        self._create_account_row(accounts_frame, avatar_letter, "Main Wallet", "Loading...")

        # Przycisk Send
        ctk.CTkButton(
            sidebar,
            text="✈️ Send",
            font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
            fg_color=self.ACCENT_2,
            text_color=self.TEXT_WHITE,
            hover_color="#CC2266",
            corner_radius=10,
            command=self._on_send_click
        ).grid(row=2, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_TINY), sticky="ew")

        # Dodaj konto (placeholder)
        ctk.CTkButton(
            sidebar,
            text="➕ Add Account",
            font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
            fg_color=self.LINK_COLOR,
            text_color=self.TEXT_WHITE,
            hover_color="#0055CC",
            corner_radius=10,
            command=self._on_add_account
        ).grid(row=3, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_TINY), sticky="ew")

        # Logout
        ctk.CTkButton(
            sidebar,
            text="🚪 Logout",
            font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
            fg_color=self.ACCENT_2,
            text_color=self.TEXT_WHITE,
            hover_color="#CC2266",
            corner_radius=10,
            command=self._on_logout
        ).grid(row=4, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_LARGE), sticky="ew")

    def _create_account_row(self, parent, avatar, name, balance):
        """Pojedynczy wiersz konta."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=5, pady=4)

        self.avatar_label = ctk.CTkLabel(
            row,
            text=avatar,
            font=ctk.CTkFont(family="Inter", size=16, weight="bold"),
            text_color=self.ACCENT_1,
            fg_color=self.BG_COLOR,
            corner_radius=20,
            width=40,
            height=40
        )
        self.avatar_label.pack(side="left", padx=(0, 10))

        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            text_frame,
            text=name,
            font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
            text_color=self.TEXT_WHITE,
            anchor="w"
        ).pack(fill="x")

        # Saldo – będzie aktualizowane później
        if balance == "Loading...":
            self.sidebar_balance_label = ctk.CTkLabel(
                text_frame,
                text="Loading...",
                font=ctk.CTkFont(family="SF Mono", size=12),
                text_color=self.TEXT_SECONDARY,
                anchor="w"
            )
            self.sidebar_balance_label.pack(fill="x")

    # ================================================================
    #  CONTENT PANEL
    # ================================================================
    def _build_content(self):
        """Prawy panel z kartami, tokenami i historią."""
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=0, column=1, sticky="nsew",
                     padx=(self.PAD_TINY, self.PAD_SMALL),
                     pady=self.PAD_SMALL)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=0)
        content.grid_rowconfigure(1, weight=0)
        content.grid_rowconfigure(2, weight=1)

        self._build_top_cards(content)
        self._build_token_table(content)
        self._build_transaction_history(content)

    def _build_top_cards(self, parent):
        """Górne karty – adres i saldo."""
        top_frame = ctk.CTkFrame(parent, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew", pady=(0, self.PAD_SMALL))
        top_frame.grid_columnconfigure(0, weight=1)
        top_frame.grid_columnconfigure(1, weight=1)

        # ── Address Card ──────────────────────────────────────────
        address_frame = ctk.CTkFrame(
            top_frame,
            fg_color=self.PANEL_COLOR,
            corner_radius=self.CORNER_RADIUS,
            border_width=1,
            border_color=self.ACCENT_1
        )
        address_frame.grid(row=0, column=0, sticky="nsew", padx=(0, self.PAD_TINY))

        ctk.CTkLabel(
            address_frame,
            text="📍 Address",
            font=ctk.CTkFont(family="Inter", size=16, weight="bold"),
            text_color=self.ACCENT_1
        ).pack(anchor="w", padx=self.PAD_LARGE, pady=(self.PAD_LARGE, 5))

        short_addr = (self.address or "Loading...")[:42]
        if self.address:
            short_addr = f"{self.address[:10]}...{self.address[-8:]}"

        self.address_label = ctk.CTkLabel(
            address_frame,
            text=short_addr,
            font=ctk.CTkFont(family="SF Mono", size=14),
            text_color=self.TEXT_WHITE,
            justify="left",
            wraplength=250,
        )
        self.address_label.pack(anchor="w", padx=self.PAD_LARGE, pady=(0, self.PAD_SMALL))

        ctk.CTkButton(
            address_frame,
            text="📋 Copy",
            font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
            fg_color=self.LINK_COLOR,
            text_color=self.TEXT_WHITE,
            hover_color="#0055CC",
            corner_radius=8,
            command=self._on_copy_address
        ).pack(side="left", padx=self.PAD_LARGE, pady=(0, self.PAD_LARGE))

        # ── Balance Card ──────────────────────────────────────────
        balance_frame = ctk.CTkFrame(
            top_frame,
            fg_color=self.PANEL_COLOR,
            corner_radius=self.CORNER_RADIUS,
            border_width=1,
            border_color=self.ACCENT_2
        )
        balance_frame.grid(row=0, column=1, sticky="nsew", padx=(self.PAD_TINY, 0))

        ctk.CTkLabel(
            balance_frame,
            text="💰 Balance",
            font=ctk.CTkFont(family="Inter", size=16, weight="bold"),
            text_color=self.ACCENT_2
        ).pack(anchor="w", padx=self.PAD_LARGE, pady=(self.PAD_LARGE, 5))

        self.balance_label = ctk.CTkLabel(
            balance_frame,
            text="Loading...",
            font=ctk.CTkFont(family="SF Mono", size=36, weight="bold"),
            text_color=self.TEXT_WHITE
        )
        self.balance_label.pack(anchor="w", padx=self.PAD_LARGE, pady=(0, 5))

        ctk.CTkLabel(
            balance_frame,
            text="USD value coming soon",
            font=ctk.CTkFont(family="Inter", size=14),
            text_color=self.TEXT_SECONDARY
        ).pack(anchor="w", padx=self.PAD_LARGE, pady=(0, 5))

        btns_balance = ctk.CTkFrame(balance_frame, fg_color="transparent")
        btns_balance.pack(anchor="w", padx=self.PAD_LARGE, pady=(0, self.PAD_LARGE))

        ctk.CTkButton(
            btns_balance,
            text="💳 Buy",
            font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
            fg_color=self.ACCENT_2,
            text_color=self.TEXT_WHITE,
            hover_color="#CC2266",
            corner_radius=8,
            width=90,
            command=self._on_buy
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btns_balance,
            text="📥 Deposit",
            font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
            fg_color=self.LINK_COLOR,
            text_color=self.TEXT_WHITE,
            hover_color="#0055CC",
            corner_radius=8,
            width=90,
            command=self._on_deposit
        ).pack(side="left")

    def _build_token_table(self, parent):
        """Sekcja tokenów ERC-20 – początkowa ramka, później odświeżana."""
        token_frame = ctk.CTkFrame(
            parent,
            fg_color=self.PANEL_COLOR,
            corner_radius=self.CORNER_RADIUS,
            border_width=1,
            border_color=self.ACCENT_1
        )
        token_frame.grid(row=1, column=0, sticky="ew", pady=(0, self.PAD_SMALL))
        token_frame.grid_columnconfigure(0, weight=1)
        token_frame.grid_columnconfigure(1, weight=2)
        token_frame.grid_columnconfigure(2, weight=1)

        # Nagłówek
        header_font = ctk.CTkFont(family="Inter", size=14, weight="bold")
        for col, text in enumerate(["Symbol", "Name", "Balance"]):
            ctk.CTkLabel(
                token_frame,
                text=text,
                font=header_font,
                text_color=self.ACCENT_2,
                anchor="w"
            ).grid(row=0, column=col, padx=self.PAD_LARGE, pady=(self.PAD_LARGE, 10), sticky="w")

        # Tymczasowy placeholder
        self.token_table_frame = token_frame
        self._token_content_frame = ctk.CTkScrollableFrame(token_frame, fg_color="transparent")
        self._token_content_frame.grid(row=1, column=0, columnspan=3, sticky="ew")

        # Placeholder
        ctk.CTkLabel(
            self._token_content_frame,
            text="Loading tokens...",
            font=ctk.CTkFont(family="Inter", size=14),
            text_color=self.TEXT_SECONDARY,
            anchor="w"
        ).pack(padx=self.PAD_LARGE, pady=10)

    def _rebuild_token_table(self):
        """Odświeża tabelkę tokenów po załadowaniu danych."""
        # Usuń starą zawartość
        for widget in self._token_content_frame.winfo_children():
            widget.destroy()

        if not self.tokens_data:
            ctk.CTkLabel(
                self._token_content_frame,
                text="No ERC-20 tokens found",
                font=ctk.CTkFont(family="Inter", size=14),
                text_color=self.TEXT_SECONDARY,
                anchor="w"
            ).pack(padx=self.PAD_LARGE, pady=10)
            return

        for idx, token in enumerate(self.tokens_data):
            row_color = self.PANEL_COLOR if idx % 2 == 1 else "#1C1D28"
            row_frame = ctk.CTkFrame(self._token_content_frame, fg_color=row_color)
            row_frame.pack(fill="x", padx=0, pady=0)
            
            row_frame.grid_columnconfigure(0, weight=1)
            row_frame.grid_columnconfigure(1, weight=2)
            row_frame.grid_columnconfigure(2, weight=1)

            ctk.CTkLabel(
                row_frame,
                text=token["symbol"],
                font=ctk.CTkFont(family="SF Mono", size=14, weight="bold"),
                text_color=self.ACCENT_1,
                anchor="w"
            ).grid(row=0, column=0, padx=self.PAD_LARGE, pady=6, sticky="w")

            ctk.CTkLabel(
                row_frame,
                text=token["name"],
                font=ctk.CTkFont(family="Inter", size=14),
                text_color=self.TEXT_WHITE,
                anchor="w"
            ).grid(row=0, column=1, padx=self.PAD_LARGE, pady=6, sticky="w")

            ctk.CTkLabel(
                row_frame,
                text=token["balance"],
                font=ctk.CTkFont(family="SF Mono", size=14),
                text_color=self.TEXT_WHITE,
                anchor="w"
            ).grid(row=0, column=2, padx=self.PAD_LARGE, pady=6, sticky="w")

    def _build_transaction_history(self, parent):
        """Sekcja historii transakcji – scrollowalna lista."""
        hist_frame = ctk.CTkFrame(
            parent,
            fg_color=self.PANEL_COLOR,
            corner_radius=self.CORNER_RADIUS,
            border_width=1,
            border_color=self.ACCENT_2
        )
        hist_frame.grid(row=2, column=0, sticky="nsew")
        hist_frame.grid_rowconfigure(1, weight=1)
        hist_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hist_frame,
            text="📜 Transaction History",
            font=ctk.CTkFont(family="Inter", size=18, weight="bold"),
            text_color=self.ACCENT_2
        ).grid(row=0, column=0, padx=self.PAD_LARGE, pady=(self.PAD_LARGE, self.PAD_TINY), sticky="w")

        scroll_frame = ctk.CTkScrollableFrame(
            hist_frame,
            fg_color="transparent",
            scrollbar_button_color=self.ACCENT_2,
            scrollbar_button_hover_color="#CC2266"
        )
        scroll_frame.grid(row=1, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_SMALL), sticky="nsew")
        scroll_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.history_scroll = scroll_frame

        # Nagłówki
        col_headers = ["From / To", "Value", "Status", "Timestamp"]
        for col, text in enumerate(col_headers):
            ctk.CTkLabel(
                scroll_frame,
                text=text,
                font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                text_color=self.ACCENT_2,
                anchor="w"
            ).grid(row=0, column=col, padx=8, pady=(0, 8), sticky="w")

        # Placeholder
        ctk.CTkLabel(
            scroll_frame,
            text="Loading transactions...",
            font=ctk.CTkFont(family="Inter", size=12),
            text_color=self.TEXT_SECONDARY,
            anchor="w"
        ).grid(row=1, column=0, padx=8, pady=4, sticky="w")

    def _rebuild_transaction_history(self):
        """Odświeża listę transakcji po załadowaniu danych."""
        # Usuń wszystkie wiersze po nagłówku (indeks 0)
        children = self.history_scroll.winfo_children()
        for widget in children[4:]: # We have 4 headers, we should destroy after headers. Actually, headers are placed in the scroll_frame, so we should clear them properly. 
            # In the original, headers were placed in `scroll_frame` directly, so there are 4 labels at indices 0,1,2,3.
            # Then the loading label was at index 4.
            widget.destroy()

        if not self.transactions_data:
            ctk.CTkLabel(
                self.history_scroll,
                text="No transactions found",
                font=ctk.CTkFont(family="Inter", size=12),
                text_color=self.TEXT_SECONDARY,
                anchor="w"
            ).grid(row=1, column=0, padx=8, pady=4, sticky="w")
            return

        for idx, tx in enumerate(self.transactions_data, start=1):
            row_color = self.PANEL_COLOR if idx % 2 == 1 else "#1C1D28"
            row_frame = ctk.CTkFrame(self.history_scroll, fg_color=row_color)
            row_frame.grid(row=idx, column=0, columnspan=4, sticky="ew", padx=0, pady=1)
            for c in range(4):
                row_frame.grid_columnconfigure(c, weight=1)

            # Formatowanie adresów
            addr_from = tx["from"]
            addr_to = tx["to"]
            if len(addr_from) > 10:
                addr_from = f"{addr_from[:6]}...{addr_from[-4:]}"
            if len(addr_to) > 10:
                addr_to = f"{addr_to[:6]}...{addr_to[-4:]}"

            # Kierunek – pokaż "From" lub "To"
            if tx["direction"] == "OUT":
                direction_text = f"→ {addr_to}"
            else:
                direction_text = f"← {addr_from}"

            ctk.CTkLabel(
                row_frame,
                text=direction_text,
                font=ctk.CTkFont(family="SF Mono", size=12),
                text_color=self.TEXT_WHITE,
                anchor="w"
            ).grid(row=0, column=0, padx=8, pady=4, sticky="w")

            # Kwota
            value_str = f"{tx['value']:.4f}".rstrip('0').rstrip('.')
            if value_str == "": value_str = "0"
            value_text = f"{value_str} {tx['symbol']}"
            ctk.CTkLabel(
                row_frame,
                text=value_text,
                font=ctk.CTkFont(family="SF Mono", size=12),
                text_color=self.TEXT_WHITE,
                anchor="w"
            ).grid(row=0, column=1, padx=8, pady=4, sticky="w")

            # Status
            status = tx["status"].lower()
            if status == "success" or status == "completed":
                status_color = self.STATUS_GREEN
                status_text = "✅ Success"
            elif status == "pending":
                status_color = self.STATUS_YELLOW
                status_text = "⏳ Pending"
            else:
                status_color = self.STATUS_RED
                status_text = "❌ Failed"

            ctk.CTkLabel(
                row_frame,
                text=status_text,
                font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                text_color=status_color,
                anchor="w"
            ).grid(row=0, column=2, padx=8, pady=4, sticky="w")

            # Timestamp (skrócony)
            timestamp = tx["timestamp"][:10] if len(tx["timestamp"]) > 10 else tx["timestamp"]
            ctk.CTkLabel(
                row_frame,
                text=timestamp,
                font=ctk.CTkFont(family="Inter", size=12),
                text_color=self.TEXT_SECONDARY,
                anchor="w"
            ).grid(row=0, column=3, padx=8, pady=4, sticky="w")

    # ================================================================
    #  CALLBACKI
    # ================================================================
    def destroy(self):
        self._active = False
        super().destroy()

    def _on_add_account(self):
        print("[Dashboard] Add Account clicked (not implemented)")

    def _on_logout(self):
        print("[Dashboard] Logout clicked")
        if self.on_logout_click:
            self.on_logout_click()

    def _on_copy_address(self):
        if self.address:
            try:
                # Kopiowanie do schowka
                self.clipboard_clear()
                self.clipboard_append(self.address)
                print(f"[Dashboard] Address copied: {self.address}")
            except Exception as e:
                print(f"[Dashboard] Clipboard error: {e}")
        else:
            print("[Dashboard] No address to copy")

    def _on_buy(self):
        print("[Dashboard] Buy clicked")

    def _on_deposit(self):
        print("[Dashboard] Deposit clicked")

    def _on_send_click(self):
        if self.on_send_click:
            self.on_send_click()
