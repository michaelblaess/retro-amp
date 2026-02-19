"""YouTube Panel — zeigt YouTube-Links zum aktuellen Track."""
from __future__ import annotations

import urllib.parse

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static


class YoutubePanel(Widget):
    """Panel mit YouTube-Links zum aktuellen Track."""

    DEFAULT_CSS = """
    YoutubePanel {
        width: 100%;
        height: 1fr;
    }
    YoutubePanel #yt-scroll {
        height: 100%;
        padding: 0 1;
    }
    YoutubePanel #yt-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    YoutubePanel #yt-links {
        color: $text;
    }
    YoutubePanel #yt-hint {
        margin-top: 1;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="yt-scroll"):
            yield Static("", id="yt-title")
            yield Static("", id="yt-links")
            yield Static("", id="yt-hint")

    def show_links(self, artist: str, title: str) -> None:
        """Zeigt YouTube-Links fuer den aktuellen Track."""
        title_widget = self.query_one("#yt-title", Static)
        links_widget = self.query_one("#yt-links", Static)
        hint_widget = self.query_one("#yt-hint", Static)

        title_widget.update(f"\u266a {artist} \u2014 {title}")

        # Such-URLs generieren
        query_full = f"{artist} {title}"
        query_video = f"{artist} {title} official video"
        query_live = f"{artist} {title} live"
        query_artist = f"{artist} music"

        url_full = self._search_url(query_full)
        url_video = self._search_url(query_video)
        url_live = self._search_url(query_live)
        url_artist = self._search_url(query_artist)

        self._urls = [url_full, url_video, url_live, url_artist]

        # Rich Text-Objekte verwenden (kein Markup-Parser, keine URL-Probleme)
        text = Text()
        text.append("\U0001f50d Suche: ")
        text.append(query_full, style=f"link {url_full}")
        text.append("\n\n")
        text.append("\U0001f3ac Video: ")
        text.append(query_video, style=f"link {url_video}")
        text.append("\n\n")
        text.append("\U0001f3a4 Live: ")
        text.append(query_live, style=f"link {url_live}")
        text.append("\n\n")
        text.append("\U0001f3b5 Artist: ")
        text.append(query_artist, style=f"link {url_artist}")

        links_widget.update(text)
        hint_widget.update("Links anklicken um YouTube im Browser zu oeffnen")

        self.query_one("#yt-scroll", VerticalScroll).scroll_home(animate=False)

    def clear(self) -> None:
        """Leert das Panel."""
        self.query_one("#yt-title", Static).update("")
        self.query_one("#yt-links", Static).update("")
        self.query_one("#yt-hint", Static).update("")

    @staticmethod
    def _search_url(query: str) -> str:
        """Erzeugt eine YouTube-Such-URL."""
        return f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
