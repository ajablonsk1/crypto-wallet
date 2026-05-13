# main.py

import customtkinter as ctk
from wallet.gui.welcome import WelcomeScreen
from wallet.gui.dashboard import DashboardScreen
from wallet.gui.send import SendScreen


class WalletApp(ctk.CTk):
    """
    Główna aplikacja portfela kryptowalutowego.
    Zarządza cyklem życia ekranów i nawigacją.
    """

    def __init__(self):
        super().__init__()

        # ── Konfiguracja okna ──────────────────────────────────────
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.title("Crypto Wallet")
        self.geometry("1000x600")
        self.minsize(900, 500)

        # ── Zmienna do przechowywania aktualnego ekranu i danych ───
        self.current_screen = None
        self.seed = None

        # ── Start od ekranu powitalnego ────────────────────────────
        self.show_welcome()

    def _clear_screen(self):
        """Usuwa aktualny ekran, jeśli istnieje."""
        if self.current_screen is not None:
            self.current_screen.destroy()
            self.current_screen = None

    def show_welcome(self):
        """Pokazuje ekran powitalny."""
        self.seed = None
        self._clear_screen()
        self.geometry("1000x600")
        screen = WelcomeScreen(self)
        # Ustawienie callbacków nawigacyjnych
        screen.on_unlock_success = self.show_dashboard
        screen.on_create_wallet_success = self.show_dashboard
        screen.pack(fill="both", expand=True)
        self.current_screen = screen

    def show_dashboard(self, seed=None):
        """Pokazuje dashboard."""
        if seed:
            self.seed = seed
            
        self._clear_screen()
        self.geometry("1200x700")
        screen = DashboardScreen(self, seed=self.seed)
        # Ustawienie callbacków
        screen.on_send_click = self.show_send
        screen.on_logout_click = self.logout
        screen.pack(fill="both", expand=True)
        self.current_screen = screen

    def logout(self):
        """Czyści dane i wraca do ekranu powitalnego."""
        self.seed = None
        self.show_welcome()

    def show_send(self):
        """Pokazuje ekran wysyłania."""
        self._clear_screen()
        self.geometry("800x600")
        screen = SendScreen(self, seed=self.seed)
        # Ustawienie callbacka powrotu
        screen.on_back_to_dashboard = self.show_dashboard
        screen.pack(fill="both", expand=True)
        self.current_screen = screen


if __name__ == "__main__":
    app = WalletApp()
    app.mainloop()
