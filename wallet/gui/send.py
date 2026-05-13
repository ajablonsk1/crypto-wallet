# wallet/gui/send.py

import customtkinter as ctk
from typing import Optional, Callable, List, Dict
from decimal import Decimal
import threading
import time

# Backend imports
from wallet.crypto.keys import derive_private_key, private_key_to_address
from wallet.network.provider import get_eth_balance, get_gas_price
from wallet.network.tokens import get_tracked_tokens, get_token_balance
from wallet.network.tx import (
    build_eth_tx,
    sign_and_send,
    estimate_fee,
    build_token_tx,
    estimate_token_fee,
)


class SendScreen(ctk.CTkFrame):
    """
    Ekran wysyłania kryptowalut.
    Przyjmuje seed, oblicza adres i klucz prywatny.
    Ładuje dostępne tokeny, umożliwia wybór, podanie kwoty,
    szybkie procenty, estymację gazu i wysyłkę.
    """

    # ── Paleta kolorów ──────────────────────────────────────────────
    BG_COLOR = "#0A0B10"
    PANEL_COLOR = "#15161E"
    ACCENT_1 = "#00FFAA"
    ACCENT_2 = "#FF3377"
    LINK_COLOR = "#0077FF"
    TEXT_WHITE = "#FFFFFF"
    TEXT_SECONDARY = "#999999"
    GAS_COLOR = "#FFAA00"
    ERROR_COLOR = "#FF3355"
    SUCCESS_COLOR = "#00CC66"

    FORM_WIDTH = 560
    PAD_LARGE = 30
    PAD_SMALL = 20
    PAD_TINY = 10
    CORNER_RADIUS = 15
    ENTRY_HEIGHT = 45

    def __init__(self, master, seed: Optional[bytes] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color=self.BG_COLOR)

        # Atrybuty backendu
        self.seed = seed
        self.private_key: Optional[bytes] = None
        self.address: Optional[str] = None
        if self.seed is not None:
            self._init_keys()

        # Dane dynamiczne
        self.tokens: List[Dict] = []  # lista: {symbol, contract?, balance}
        self.eth_balance = Decimal("0")
        self.token_balances: Dict[str, Decimal] = {}  # symbol -> Decimal
        self.gas_fee_eth = Decimal("0.0021")  # domyślna placeholder

        # Referencje do widgetów
        self.recipient_entry: Optional[ctk.CTkEntry] = None
        self.amount_entry: Optional[ctk.CTkEntry] = None
        self.token_menu: Optional[ctk.CTkOptionMenu] = None
        self.gas_label: Optional[ctk.CTkLabel] = None
        self.send_button: Optional[ctk.CTkButton] = None
        self.error_label: Optional[ctk.CTkLabel] = None

        # State
        self._sending = False  # blokada przed wielokrotnym wysyłaniem
        self._active = True

        # Callbacki nawigacyjne
        self.on_back_to_dashboard: Optional[Callable] = None

        # Główny kontener
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_form()

        # Po zbudowaniu UI, załaduj tokeny w tle
        if self.address:
            threading.Thread(target=self._load_tokens_and_balance, daemon=True).start()

    def _init_keys(self):
        """Oblicza klucz prywatny i adres z seedu."""
        try:
            self.private_key = derive_private_key(self.seed, 0)
            self.address = private_key_to_address(self.private_key)
        except Exception as e:
            print(f"[Send] Key derivation error: {e}")
            self.address = "0x0000000000000000000000000000000000000000"

    def _load_tokens_and_balance(self):
        """Ładuje saldo ETH i listę tokenów."""
        try:
            # Saldo ETH
            self.eth_balance = get_eth_balance(self.address)
            self.token_balances["ETH"] = self.eth_balance

            # Tokeny ERC-20
            tracked = get_tracked_tokens()
            token_tmp = []
            for contract in tracked:
                try:
                    bal = get_token_balance(self.address, contract)
                    # Potrzebujemy symbol – zakładamy, że możemy użyć nazwy kontraktu
                    # W praktyce get_token_info, ale uproszczamy
                    symbol = contract[:4].upper()  # placeholder
                    token_tmp.append({
                        "symbol": symbol,
                        "contract": contract,
                        "balance": bal
                    })
                    self.token_balances[symbol] = bal
                except Exception as e:
                    print(f"[Send] Token load error {contract}: {e}")

            # Ustaw ETH jako pierwszy
            self.tokens = [{"symbol": "ETH", "contract": None, "balance": self.eth_balance}] + token_tmp

            # Aktualizacja UI w głównym wątku
            if self._active:
                self.after(0, self._update_token_menu)

        except Exception as e:
            print(f"[Send] Data loading error: {e}")

    def _update_token_menu(self):
        """Aktualizuje wartości w OptionMenu tokenów."""
        symbols = [t["symbol"] for t in self.tokens]
        if symbols:
            self.token_menu.configure(values=symbols)
            # Nie zmieniamy aktywnego wyboru – pozostaje "ETH" (pierwszy)
            # Odświeżamy widok gazu i kwoty
            self._update_gas_fee()

    def _build_form(self):
        """Tworzy centralny panel formularza."""
        form_frame = ctk.CTkFrame(
            self,
            fg_color=self.PANEL_COLOR,
            corner_radius=self.CORNER_RADIUS,
            border_width=1,
            border_color=self.ACCENT_1,
            width=self.FORM_WIDTH,
        )
        form_frame.grid(row=0, column=0, padx=self.PAD_LARGE, pady=self.PAD_LARGE)
        form_frame.grid_propagate(False)
        form_frame.grid_columnconfigure(0, weight=1)

        # ── Nagłówek + przycisk powrotu ──────────────────────────
        header_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=self.PAD_SMALL, pady=(self.PAD_LARGE, self.PAD_SMALL), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            header_frame,
            text="✈️ Send Crypto",
            font=ctk.CTkFont(family="Inter", size=28, weight="bold"),
            text_color=self.ACCENT_1
        ).grid(row=0, column=0, sticky="w")

        back_btn = ctk.CTkButton(
            header_frame,
            text="← Back to Dashboard",
            font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
            fg_color=self.LINK_COLOR,
            text_color=self.TEXT_WHITE,
            hover_color="#0055CC",
            corner_radius=8,
            command=self._on_back_click
        )
        back_btn.grid(row=0, column=1, sticky="e", padx=(10, 0))

        # ── Recipient Address ──────────────────────────────────────
        ctk.CTkLabel(
            form_frame,
            text="Recipient Address",
            font=ctk.CTkFont(family="Inter", size=14),
            text_color=self.TEXT_WHITE,
            anchor="w"
        ).grid(row=1, column=0, padx=self.PAD_SMALL, pady=(0, 4), sticky="w")

        self.recipient_entry = ctk.CTkEntry(
            form_frame,
            placeholder_text="0x... or ENS name",
            font=ctk.CTkFont(family="Inter", size=16),
            fg_color=self.BG_COLOR,
            border_color=self.LINK_COLOR,
            text_color=self.TEXT_WHITE,
            placeholder_text_color=self.TEXT_SECONDARY,
            height=self.ENTRY_HEIGHT
        )
        self.recipient_entry.grid(row=2, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_SMALL), sticky="ew")

        # ── Amount + Token Selector ────────────────────────────────
        amount_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        amount_frame.grid(row=3, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_TINY), sticky="ew")
        amount_frame.grid_columnconfigure(0, weight=3)
        amount_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            amount_frame,
            text="Amount",
            font=ctk.CTkFont(family="Inter", size=14),
            text_color=self.TEXT_WHITE,
            anchor="w"
        ).grid(row=0, column=0, padx=0, pady=(0, 4), sticky="w")

        self.amount_entry = ctk.CTkEntry(
            amount_frame,
            placeholder_text="0.00",
            font=ctk.CTkFont(family="Inter", size=16),
            fg_color=self.BG_COLOR,
            border_color=self.LINK_COLOR,
            text_color=self.TEXT_WHITE,
            placeholder_text_color=self.TEXT_SECONDARY,
            height=self.ENTRY_HEIGHT
        )
        self.amount_entry.grid(row=1, column=0, padx=(0, 8), sticky="ew")
        self.amount_entry.bind("<KeyRelease>", lambda e: self._schedule_gas_update())

        self.token_menu = ctk.CTkOptionMenu(
            amount_frame,
            values=["ETH"],  # tymczasowo
            font=ctk.CTkFont(family="Inter", size=16, weight="bold"),
            fg_color=self.BG_COLOR,
            button_color=self.ACCENT_2,
            button_hover_color="#CC2266",
            text_color=self.TEXT_WHITE,
            dropdown_fg_color=self.PANEL_COLOR,
            dropdown_text_color=self.TEXT_WHITE,
            dropdown_hover_color=self.ACCENT_2,
            corner_radius=8,
            height=self.ENTRY_HEIGHT,
            command=self._on_token_change
        )
        self.token_menu.set("ETH")
        self.token_menu.grid(row=1, column=1, sticky="ew")

        # ── Quick percentage buttons ──────────────────────────────
        quick_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        quick_frame.grid(row=4, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_SMALL), sticky="ew")
        quick_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        percentages = [("25%", 0.25), ("50%", 0.50), ("75%", 0.75), ("Max", 1.0)]
        for i, (label, value) in enumerate(percentages):
            btn = ctk.CTkButton(
                quick_frame,
                text=label,
                font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                fg_color=self.LINK_COLOR,
                text_color=self.TEXT_WHITE,
                hover_color="#0055CC",
                corner_radius=8,
                height=30,
                command=lambda v=value: self._quick_percent(v)
            )
            btn.grid(row=0, column=i, padx=2, sticky="ew")

        # ── Gas Fee ────────────────────────────────────────────────
        gas_frame = ctk.CTkFrame(form_frame, fg_color=self.BG_COLOR, corner_radius=8)
        gas_frame.grid(row=5, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_SMALL), sticky="ew")

        ctk.CTkLabel(
            gas_frame,
            text="⛽ Estimated Gas Fee",
            font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
            text_color=self.GAS_COLOR
        ).pack(side="left", padx=12, pady=8)

        self.gas_label = ctk.CTkLabel(
            gas_frame,
            text="Calculating...",
            font=ctk.CTkFont(family="Inter", size=13),
            text_color=self.TEXT_WHITE
        )
        self.gas_label.pack(side="right", padx=12, pady=8)

        # ── Error label ────────────────────────────────────────────
        self.error_label = ctk.CTkLabel(
            form_frame,
            text="",
            font=ctk.CTkFont(family="Inter", size=12),
            text_color=self.ERROR_COLOR,
            anchor="w"
        )
        self.error_label.grid(row=6, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_TINY), sticky="ew")

        # ── Send Button ────────────────────────────────────────────
        self.send_button = ctk.CTkButton(
            form_frame,
            text="🚀 Send",
            font=ctk.CTkFont(family="Inter", size=18, weight="bold"),
            fg_color=self.ACCENT_2,
            text_color=self.TEXT_WHITE,
            hover_color="#CC2266",
            corner_radius=10,
            height=50,
            command=self._on_send_click
        )
        self.send_button.grid(row=7, column=0, padx=self.PAD_SMALL, pady=(0, self.PAD_LARGE), sticky="ew")

    # ================================================================
    #  DYNAMICZNE AKTUALIZACJE
    # ================================================================
    def _schedule_gas_update(self):
        """Opóźnia aktualizację gazu (debounce)."""
        if hasattr(self, '_gas_timer') and self._gas_timer:
            self.after_cancel(self._gas_timer)
        self._gas_timer = self.after(500, self._update_gas_fee)

    def _update_gas_fee(self):
        """Oblicza szacunkową opłatę gazową dla aktualnego tokena i kwoty."""
        token = self.token_menu.get()
        amount_str = self.amount_entry.get().strip()
        if not amount_str:
            self.gas_label.configure(text="Enter amount to estimate")
            return

        try:
            amount = Decimal(amount_str)
        except:
            self.gas_label.configure(text="Invalid amount")
            return

        # Uruchom estymację w tle
        threading.Thread(target=self._estimate_gas_background, args=(token, amount), daemon=True).start()

    def _estimate_gas_background(self, token: str, amount: Decimal):
        """W tle oblicza opłatę gazową."""
        try:
            if token == "ETH":
                fee = estimate_fee(self.address, amount)  # zakładamy, że zwraca Decimal w ETH
            else:
                # Dla tokenów ERC-20 znajdź kontrakt
                contract = None
                for t in self.tokens:
                    if t["symbol"] == token:
                        contract = t.get("contract")
                        break
                if not contract:
                    self.after(0, lambda: self.gas_label.configure(text="Token not supported"))
                    return
                fee = estimate_token_fee(self.address, contract, amount)

            self.gas_fee_eth = fee
            fee_str = f"{fee:.6f} ETH"
            # Można dodać wartość w USD, ale na razie tylko ETH
            self.after(0, lambda: self._update_gas_label(fee_str))
        except Exception as e:
            print(f"[Gas] Estimation error: {e}")
            self.after(0, lambda: self._update_gas_label("Error estimating gas"))

    def _update_gas_label(self, text: str):
        if self._active:
            self.gas_label.configure(text=text)

    def _on_token_change(self, choice: str):
        """Callback zmiany tokena."""
        print(f"[Send] Token changed to: {choice}")
        # Odśwież estymację gazu
        self._schedule_gas_update()

    def _quick_percent(self, fraction: float):
        """Ustawia kwotę jako procent balansu wybranego tokena."""
        token = self.token_menu.get()
        balance = self.token_balances.get(token, Decimal("0"))
        amount = balance * Decimal(str(fraction))
        self.amount_entry.delete(0, "end")
        # Formatowanie: do 6 miejsc po przecinku
        formatted = f"{amount:.6f}".rstrip('0').rstrip('.')
        if formatted == "": formatted = "0"
        self.amount_entry.insert(0, formatted)
        # Odśwież gaz
        self._schedule_gas_update()

    # ================================================================
    #  WYSYŁKA TRANSAKCJI
    # ================================================================
    def _on_send_click(self):
        """Rozpoczęcie procesu wysyłania: najpierw estymacja, potem modal."""
        if self._sending:
            return  # blokada

        # Walidacja pól
        recipient = self.recipient_entry.get().strip()
        amount_str = self.amount_entry.get().strip()
        if not recipient or not amount_str:
            self.error_label.configure(text="Please fill all fields")
            return

        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError
        except:
            self.error_label.configure(text="Invalid amount")
            return

        token = self.token_menu.get()
        # Sprawdź czy saldo wystarczy
        balance = self.token_balances.get(token, Decimal("0"))
        if amount > balance:
            self.error_label.configure(text=f"Insufficient {token} balance")
            return

        # Wyczyść błąd
        self.error_label.configure(text="")

        # Wywołaj estymację w tle i po zakończeniu otwórz modal
        self._sending = True
        self.send_button.configure(state="disabled", text="⏳ Estimating...")
        threading.Thread(target=self._prepare_and_show_modal, args=(recipient, amount, token), daemon=True).start()

    def _prepare_and_show_modal(self, recipient: str, amount: Decimal, token: str):
        """Estymuje gaz, potem otwiera modal potwierdzenia."""
        try:
            if token == "ETH":
                fee = estimate_fee(self.address, amount)
            else:
                contract = None
                for t in self.tokens:
                    if t["symbol"] == token:
                        contract = t.get("contract")
                        break
                if not contract:
                    raise ValueError("Token contract not found")
                fee = estimate_token_fee(self.address, contract, amount)

            self.gas_fee_eth = fee

            # Po estymacji, otwórz modal w głównym wątku
            self.after(0, lambda: self._show_confirmation_modal(recipient, amount, token, fee))

        except Exception as e:
            print(f"[Send] Estimation error: {e}")
            self.after(0, lambda: self._reset_send_button())
            self.after(0, lambda: self.error_label.configure(text=f"Estimation failed: {str(e)[:50]}"))

    def _reset_send_button(self):
        """Przywraca przycisk do stanu początkowego."""
        self._sending = False
        self.send_button.configure(state="normal", text="🚀 Send")

    def _show_confirmation_modal(self, recipient: str, amount: Decimal, token: str, gas_fee: Decimal):
        """Tworzy i wyświetla modal potwierdzenia."""
        master_window = self.winfo_toplevel()
        total_str = f"{amount} {token} + {gas_fee:.6f} ETH"

        modal = ConfirmationModal(
            master_window,
            recipient=recipient,
            amount=f"{amount} {token}",
            token=token,
            gas_fee=f"{gas_fee:.6f} ETH",
            total=total_str,
            on_confirm=lambda: self._send_transaction(recipient, amount, token, gas_fee),
            on_cancel=self._reset_send_button
        )
        modal.grab_set()  # modalne

    def _send_transaction(self, recipient: str, amount: Decimal, token: str, gas_fee: Decimal):
        """Wykonuje transakcję w tle i aktualizuje UI."""
        # Zablokuj UI
        self.send_button.configure(state="disabled", text="⏳ Sending...")
        self._sending = True

        threading.Thread(target=self._send_background, args=(recipient, amount, token, gas_fee), daemon=True).start()

    def _send_background(self, recipient: str, amount: Decimal, token: str, gas_fee: Decimal):
        """W tle buduje, podpisuje i wysyła transakcję."""
        try:
            if token == "ETH":
                tx = build_eth_tx(self.address, recipient, amount)
            else:
                contract = None
                for t in self.tokens:
                    if t["symbol"] == token:
                        contract = t.get("contract")
                        break
                if not contract:
                    raise ValueError("Token contract not found")
                tx = build_token_tx(self.address, recipient, contract, amount)

            # Podpisz i wyślij
            tx_hash = sign_and_send(tx, self.private_key)

            # Sukces
            self.after(0, lambda: self._on_send_success(tx_hash))

        except Exception as e:
            print(f"[Send] Transaction error: {e}")
            self.after(0, lambda: self._on_send_error(str(e)))

    def _on_send_success(self, tx_hash: str):
        """Aktualizuje UI po pomyślnej transakcji."""
        if not self._active:
            return
        self.error_label.configure(text=f"✅ Transaction sent! Hash: {tx_hash[:10]}...", text_color=self.SUCCESS_COLOR)
        self._reset_send_button()
        # Czyścimy pola
        self.recipient_entry.delete(0, "end")
        self.amount_entry.delete(0, "end")
        # Odśwież balanse w tle
        threading.Thread(target=self._load_tokens_and_balance, daemon=True).start()

    def _on_send_error(self, error_msg: str):
        """Aktualizuje UI po błędzie."""
        if not self._active:
            return
        self.error_label.configure(text=f"❌ {error_msg}", text_color=self.ERROR_COLOR)
        self._reset_send_button()

    # ================================================================
    #  CALLBACKI NAWIGACJI
    # ================================================================
    def destroy(self):
        self._active = False
        super().destroy()

    def _on_back_click(self):
        if self.on_back_to_dashboard:
            self.on_back_to_dashboard()


class ConfirmationModal(ctk.CTkToplevel):
    """
    Modal potwierdzenia transakcji.
    Wyświetla szczegóły: odbiorca, kwota, opłata gazowa, całkowity koszt.
    Przyciski: Cancel i Confirm.
    """

    def __init__(self, master, recipient: str, amount: str, token: str,
                 gas_fee: str, total: str,
                 on_confirm: Optional[Callable] = None,
                 on_cancel: Optional[Callable] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self._action_taken = False

        # Konfiguracja okna
        self.title("Confirm Transaction")
        self.geometry("480x360")
        self.resizable(False, False)
        self.configure(fg_color="#0A0B10")
        self.transient(master)
        self.grab_set()

        # Główna ramka
        main_frame = ctk.CTkFrame(
            self,
            fg_color="#15161E",
            corner_radius=15,
            border_width=1,
            border_color="#00FFAA"
        )
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Nagłówek
        ctk.CTkLabel(
            main_frame,
            text="🔐 Confirm Transaction",
            font=ctk.CTkFont(family="Inter", size=22, weight="bold"),
            text_color="#00FFAA"
        ).pack(pady=(20, 10))

        # Szczegóły
        details_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        details_frame.pack(fill="x", padx=30, pady=10)

        def add_detail(label, value, value_color="#FFFFFF"):
            row = ctk.CTkFrame(details_frame, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(
                row,
                text=label,
                font=ctk.CTkFont(family="Inter", size=14),
                text_color="#999999",
                anchor="w"
            ).pack(side="left")
            ctk.CTkLabel(
                row,
                text=value,
                font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
                text_color=value_color,
                anchor="e"
            ).pack(side="right")

        short_rec = f"{recipient[:10]}...{recipient[-4:]}" if len(recipient) > 14 else recipient
        add_detail("To:", short_rec)
        add_detail("Amount:", amount, value_color="#00FFAA")
        add_detail("Gas Fee:", gas_fee, value_color="#FFAA00")
        add_detail("Total:", total, value_color="#FFFFFF")

        # Przyciski
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=(20, 20))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        self.cancel_btn = ctk.CTkButton(
            btn_frame,
            text="❌ Cancel",
            font=ctk.CTkFont(family="Inter", size=15, weight="bold"),
            fg_color="#FF3377",
            text_color="#FFFFFF",
            hover_color="#CC2266",
            corner_radius=10,
            height=40,
            command=self._cancel
        )
        self.cancel_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.confirm_btn = ctk.CTkButton(
            btn_frame,
            text="✅ Confirm",
            font=ctk.CTkFont(family="Inter", size=15, weight="bold"),
            fg_color="#00FFAA",
            text_color="#0A0B10",
            hover_color="#00CC88",
            corner_radius=10,
            height=40,
            command=self._confirm
        )
        self.confirm_btn.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())

    def _confirm(self):
        if self._action_taken:
            return
        self._action_taken = True
        self.confirm_btn.configure(state="disabled", text="⏳ Processing...")
        self.cancel_btn.configure(state="disabled")
        
        if self.on_confirm:
            self.on_confirm()
        self.destroy()

    def _cancel(self):
        if self._action_taken:
            return
        self._action_taken = True
        
        if self.on_cancel:
            self.on_cancel()
        self.destroy()


# ── Test uruchomieniowy ─────────────────────────────────────────────
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")

    root = ctk.CTk()
    root.title("Crypto Wallet – Send")
    root.geometry("800x600")
    root.minsize(700, 500)

    # Do testów – wygeneruj fałszywy seed
    fake_seed = bytes(32)
    app = SendScreen(root, seed=fake_seed)
    app.pack(fill="both", expand=True)

    root.mainloop()
