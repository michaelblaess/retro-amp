"""Lyrics Panel — zeigt Original-Songtexte."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static


class LyricsPanel(Widget):
    """Scrollbares Panel fuer Original-Lyrics."""

    DEFAULT_CSS = """
    LyricsPanel {
        width: 100%;
        height: 1fr;
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
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="lyrics-scroll"):
            yield Static("", id="lyrics-title")
            yield Static("", id="lyrics-text")

    def show_loading(self, artist: str, title: str) -> None:
        """Zeigt Ladezustand an."""
        self.query_one("#lyrics-title", Static).update(
            f"\u266a {artist} \u2014 {title}"
        )
        self.query_one("#lyrics-text", Static).update("Lade Lyrics...")

    def show_lyrics(self, artist: str, title: str, text: str) -> None:
        """Zeigt Original-Lyrics an."""
        self.query_one("#lyrics-title", Static).update(
            f"\u266a {artist} \u2014 {title}"
        )
        self.query_one("#lyrics-text", Static).update(
            text if text else "Keine Lyrics gefunden."
        )
        self.query_one("#lyrics-scroll", VerticalScroll).scroll_home(animate=False)

    def clear(self) -> None:
        """Leert das Panel."""
        self.query_one("#lyrics-title", Static).update("")
        self.query_one("#lyrics-text", Static).update("")
