"""Lyrics Panel — zeigt Song-Texte mit Uebersetzung."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static


class LyricsPanel(Widget):
    """Scrollbares Panel fuer Lyrics mit Original und Uebersetzung."""

    DEFAULT_CSS = """
    LyricsPanel {
        width: 100%;
        height: 1fr;
        border: solid $error;
        display: none;
    }
    LyricsPanel.visible {
        display: block;
    }
    LyricsPanel #lyrics-scroll {
        height: 100%;
        padding: 0 1;
    }
    LyricsPanel #lyrics-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    LyricsPanel #lyrics-text {
        color: $text;
    }
    LyricsPanel #lyrics-translated {
        color: $text-muted;
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._artist: str = ""
        self._title: str = ""

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="lyrics-scroll"):
            yield Static("", id="lyrics-title")
            yield Static("", id="lyrics-text")
            yield Static("", id="lyrics-translated")

    def show_loading(self, artist: str, title: str) -> None:
        """Zeigt Ladezustand an."""
        self._artist = artist
        self._title = title
        self.add_class("visible")

        title_widget = self.query_one("#lyrics-title", Static)
        text_widget = self.query_one("#lyrics-text", Static)
        translated_widget = self.query_one("#lyrics-translated", Static)

        title_widget.update(f"♪ {artist} — {title}")
        text_widget.update("Lade Lyrics...")
        translated_widget.update("")

    def show_lyrics(
        self, artist: str, title: str, original: str, translated: str,
    ) -> None:
        """Zeigt Lyrics an."""
        self._artist = artist
        self._title = title
        self.add_class("visible")

        title_widget = self.query_one("#lyrics-title", Static)
        text_widget = self.query_one("#lyrics-text", Static)
        translated_widget = self.query_one("#lyrics-translated", Static)

        title_widget.update(f"♪ {artist} — {title}")

        if original:
            text_widget.update(original)
            if translated:
                translated_widget.update(f"— Uebersetzung —\n\n{translated}")
            else:
                translated_widget.update("")
        else:
            text_widget.update("Keine Lyrics gefunden.")
            translated_widget.update("")

        # Zum Anfang scrollen
        scroll = self.query_one("#lyrics-scroll", VerticalScroll)
        scroll.scroll_home(animate=False)

    def clear(self) -> None:
        """Versteckt das Panel."""
        self.remove_class("visible")
        title_widget = self.query_one("#lyrics-title", Static)
        text_widget = self.query_one("#lyrics-text", Static)
        translated_widget = self.query_one("#lyrics-translated", Static)
        title_widget.update("")
        text_widget.update("")
        translated_widget.update("")
