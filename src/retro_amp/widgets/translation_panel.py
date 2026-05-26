"""Translation Panel — zeigt uebersetzte Songtexte (deutsch)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from ..i18n import t


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

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._artist: str = ""
        self._title: str = ""
        self._text: str = ""

    @property
    def artist(self) -> str:
        return self._artist

    @property
    def title(self) -> str:
        return self._title

    def get_translation_text(self) -> str:
        """Liefert den aktuell angezeigten Uebersetzungstext (Copy/Save)."""
        return self._text

    def has_translation(self) -> bool:
        return bool(self._text.strip())

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="translation-scroll"):
            yield Static("", id="translation-title")
            yield Static("", id="translation-text")

    def show_loading(self, artist: str, title: str) -> None:
        """Zeigt Ladezustand an."""
        self._artist = artist
        self._title = title
        self._text = ""
        self.query_one("#translation-title", Static).update(f"\u266a {artist} \u2014 {title}")
        self.query_one("#translation-text", Static).update(t("translation.loading"))

    def show_translation(self, artist: str, title: str, text: str) -> None:
        """Zeigt uebersetzte Lyrics an."""
        self._artist = artist
        self._title = title
        self._text = text
        self.query_one("#translation-title", Static).update(f"\u266a {artist} \u2014 {title}")
        self.query_one("#translation-text", Static).update(text if text else t("translation.not_found"))
        self.query_one("#translation-scroll", VerticalScroll).scroll_home(
            animate=False,
        )

    def clear(self) -> None:
        """Leert das Panel."""
        self._artist = ""
        self._title = ""
        self._text = ""
        self.query_one("#translation-title", Static).update("")
        self.query_one("#translation-text", Static).update("")
