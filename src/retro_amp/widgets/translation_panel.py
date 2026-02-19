"""Translation Panel — zeigt uebersetzte Songtexte (deutsch)."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static


class TranslationPanel(Widget):
    """Scrollbares Panel fuer uebersetzte Lyrics."""

    DEFAULT_CSS = """
    TranslationPanel {
        width: 100%;
        height: 1fr;
    }
    TranslationPanel #translation-scroll {
        height: 100%;
        padding: 0 1;
    }
    TranslationPanel #translation-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    TranslationPanel #translation-text {
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="translation-scroll"):
            yield Static("", id="translation-title")
            yield Static("", id="translation-text")

    def show_loading(self, artist: str, title: str) -> None:
        """Zeigt Ladezustand an."""
        self.query_one("#translation-title", Static).update(
            f"\u266a {artist} \u2014 {title}"
        )
        self.query_one("#translation-text", Static).update("Uebersetze...")

    def show_translation(self, artist: str, title: str, text: str) -> None:
        """Zeigt uebersetzte Lyrics an."""
        self.query_one("#translation-title", Static).update(
            f"\u266a {artist} \u2014 {title}"
        )
        self.query_one("#translation-text", Static).update(
            text if text else
            "Keine Uebersetzung verfuegbar.\n\n"
            "Moegliche Gruende:\n"
            "- API Rate Limit erreicht (max. 50.000 Zeichen/Tag)\n"
            "- Kein Internet\n"
            "- Lyrics nicht auf Englisch"
        )
        self.query_one("#translation-scroll", VerticalScroll).scroll_home(
            animate=False,
        )

    def clear(self) -> None:
        """Leert das Panel."""
        self.query_one("#translation-title", Static).update("")
        self.query_one("#translation-text", Static).update("")
