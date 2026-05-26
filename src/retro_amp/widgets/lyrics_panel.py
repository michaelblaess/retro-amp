"""Lyrics Panel — zeigt Original-Songtexte mit optionalem Sync."""

from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.events import Click
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from ..i18n import t


class LyricLine(Static, can_focus=False):
    """Einzelne Lyrics-Zeile mit Timestamp fuer Click-to-Seek."""

    DEFAULT_CSS = """
    LyricLine {
        width: 100%;
        height: auto;
        padding: 0 1;
    }
    LyricLine.played {
        color: $text-muted;
    }
    LyricLine.current {
        color: $accent;
        text-style: bold;
    }
    LyricLine.upcoming {
        color: $text;
    }
    """

    class Clicked(Message):
        """Benutzer hat auf eine Lyrics-Zeile geklickt."""

        def __init__(self, timestamp: float) -> None:
            super().__init__()
            self.timestamp = timestamp

    def __init__(self, text: str, timestamp: float, **kwargs: object) -> None:
        super().__init__(text, **kwargs)
        self.timestamp = timestamp

    def on_click(self, event: Click) -> None:
        # Nur Links-Klick triggert Seek — Rechtsklick (Kontextmenue) bubbelt
        # zur App, ohne die Wiedergabeposition zu aendern.
        if event.button != 1:
            return
        self.post_message(self.Clicked(self.timestamp))


class LyricsScroll(VerticalScroll):
    """VerticalScroll mit Erkennung von manuellem Scrolling."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._last_manual_scroll: float = 0.0

    def on_mouse_scroll_down(self) -> None:
        self._last_manual_scroll = time.monotonic()

    def on_mouse_scroll_up(self) -> None:
        self._last_manual_scroll = time.monotonic()

    @property
    def auto_scroll_allowed(self) -> bool:
        """True wenn seit 3s kein manuelles Scrollen."""
        return time.monotonic() - self._last_manual_scroll > 3.0


class LyricsPanel(Widget):
    """Scrollbares Panel fuer Original-Lyrics mit optionalem Sync."""

    DEFAULT_CSS = """
    LyricsPanel {
        width: 100%;
        height: 1fr;
    }
    LyricsPanel LyricsScroll {
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

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._synced_lines: list[tuple[float, str]] = []
        self._current_line_index: int = -1
        self._is_synced: bool = False
        self._artist: str = ""
        self._title: str = ""
        self._plain_text: str = ""

    @property
    def artist(self) -> str:
        return self._artist

    @property
    def title(self) -> str:
        return self._title

    def get_lyrics_text(self) -> str:
        """Liefert die aktuell angezeigten Lyrics als Plain-Text (Copy/Save)."""
        if self._is_synced and self._synced_lines:
            return "\n".join(text for _, text in self._synced_lines)
        return self._plain_text

    def has_lyrics(self) -> bool:
        """True wenn Lyrics fuer den aktuellen Track verfuegbar sind."""
        return bool(self.get_lyrics_text().strip())

    def compose(self) -> ComposeResult:
        with LyricsScroll(id="lyrics-scroll"):
            yield Static("", id="lyrics-title")
            yield Static("", id="lyrics-text")

    def show_loading(self, artist: str, title: str) -> None:
        """Zeigt Ladezustand an."""
        self._is_synced = False
        self._synced_lines = []
        self._current_line_index = -1
        self._artist = artist
        self._title = title
        self._plain_text = ""
        self.query_one("#lyrics-title", Static).update(f"\u266a {artist} \u2014 {title}")
        # Alte Lyric-Zeilen entfernen
        for line in self.query(LyricLine):
            line.remove()
        self.query_one("#lyrics-text", Static).update(t("lyrics.loading"))

    def show_lyrics(
        self,
        artist: str,
        title: str,
        text: str,
        synced_lines: list[tuple[float, str]] | None = None,
    ) -> None:
        """Zeigt Lyrics an — synced wenn verfuegbar, sonst plain."""
        self._artist = artist
        self._title = title
        self._plain_text = text
        self.query_one("#lyrics-title", Static).update(f"\u266a {artist} \u2014 {title}")

        # Alte Lyric-Zeilen entfernen
        for line in self.query(LyricLine):
            line.remove()

        if synced_lines:
            self._is_synced = True
            self._synced_lines = synced_lines
            self._current_line_index = -1
            # Plain-Text-Widget verstecken
            self.query_one("#lyrics-text", Static).update("")
            # Einzelne Zeilen als klickbare Widgets
            scroll = self.query_one("#lyrics-scroll", LyricsScroll)
            for i, (ts, line_text) in enumerate(synced_lines):
                line = LyricLine(line_text, timestamp=ts, id=f"lyric-{i}")
                line.add_class("upcoming")
                scroll.mount(line)
        else:
            self._is_synced = False
            self._synced_lines = []
            self._current_line_index = -1
            self.query_one("#lyrics-text", Static).update(text if text else t("lyrics.not_found"))

        self.query_one("#lyrics-scroll", LyricsScroll).scroll_home(animate=False)

    def update_position(self, seconds: float) -> None:
        """Aktualisiert Highlighting basierend auf Playback-Position."""
        if not self._is_synced or not self._synced_lines:
            return

        # Aktuelle Zeile finden
        new_index = -1
        for i, (ts, _) in enumerate(self._synced_lines):
            if ts <= seconds:
                new_index = i
            else:
                break

        if new_index == self._current_line_index:
            return

        self._current_line_index = new_index

        # CSS-Klassen auf allen Zeilen aktualisieren
        for i, line in enumerate(self.query(LyricLine)):
            line.remove_class("played", "current", "upcoming")
            if i < new_index:
                line.add_class("played")
            elif i == new_index:
                line.add_class("current")
            else:
                line.add_class("upcoming")

        # Auto-Scroll wenn kein manuelles Scrollen
        scroll = self.query_one("#lyrics-scroll", LyricsScroll)
        if scroll.auto_scroll_allowed and new_index >= 0:
            try:
                current = self.query_one(f"#lyric-{new_index}", LyricLine)
                current.scroll_visible(animate=True)
            except Exception:
                pass

    def clear(self) -> None:
        """Leert das Panel."""
        self._is_synced = False
        self._synced_lines = []
        self._current_line_index = -1
        self._artist = ""
        self._title = ""
        self._plain_text = ""
        self.query_one("#lyrics-title", Static).update("")
        self.query_one("#lyrics-text", Static).update("")
        for line in self.query(LyricLine):
            line.remove()
