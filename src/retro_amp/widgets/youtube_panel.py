"""YouTube Panel — zeigt YouTube-Links zum aktuellen Track."""
from __future__ import annotations

import urllib.parse
import webbrowser

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static


class _YTLink(Static, can_focus=True):
    """Klickbarer YouTube-Link — oeffnet den Browser bei Klick oder Enter."""

    DEFAULT_CSS = """
    _YTLink {
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
        color: $text;
    }
    _YTLink:hover {
        text-style: bold underline;
        color: $accent;
    }
    _YTLink:focus {
        text-style: bold underline;
        color: $accent;
    }
    """

    BINDINGS = [
        ("enter", "open_link", "Oeffnen"),
    ]

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._url: str = ""

    def set_link(self, label: str, url: str) -> None:
        """Setzt Label und URL."""
        self._url = url
        self.update(label)

    def on_click(self) -> None:
        """Oeffnet den Link im Standard-Browser."""
        if self._url:
            webbrowser.open(self._url)

    def action_open_link(self) -> None:
        """Oeffnet den Link im Standard-Browser (Enter-Taste)."""
        if self._url:
            webbrowser.open(self._url)


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
    YoutubePanel #yt-hint {
        margin-top: 1;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="yt-scroll"):
            yield Static("", id="yt-title")
            yield _YTLink(id="yt-search")
            yield _YTLink(id="yt-video")
            yield _YTLink(id="yt-live")
            yield _YTLink(id="yt-artist")
            yield Static("", id="yt-hint")

    def show_links(self, artist: str, title: str) -> None:
        """Zeigt YouTube-Links fuer den aktuellen Track."""
        self.query_one("#yt-title", Static).update(
            f"\u266a {artist} \u2014 {title}"
        )

        query_full = f"{artist} {title}"
        query_video = f"{artist} {title} official video"
        query_live = f"{artist} {title} live"
        query_artist = f"{artist} music"

        self.query_one("#yt-search", _YTLink).set_link(
            f"\U0001f50d Suche: {query_full}",
            self._search_url(query_full),
        )
        self.query_one("#yt-video", _YTLink).set_link(
            f"\U0001f3ac Video: {query_video}",
            self._search_url(query_video),
        )
        self.query_one("#yt-live", _YTLink).set_link(
            f"\U0001f3a4 Live: {query_live}",
            self._search_url(query_live),
        )
        self.query_one("#yt-artist", _YTLink).set_link(
            f"\U0001f3b5 Artist: {query_artist}",
            self._search_url(query_artist),
        )

        self.query_one("#yt-hint", Static).update(
            "Anklicken um YouTube im Browser zu oeffnen"
        )
        self.query_one("#yt-scroll", VerticalScroll).scroll_home(animate=False)

    def clear(self) -> None:
        """Leert das Panel."""
        self.query_one("#yt-title", Static).update("")
        for link_id in ("#yt-search", "#yt-video", "#yt-live", "#yt-artist"):
            link = self.query_one(link_id, _YTLink)
            link._url = ""
            link.update("")
        self.query_one("#yt-hint", Static).update("")

    @staticmethod
    def _search_url(query: str) -> str:
        """Erzeugt eine YouTube-Such-URL."""
        return f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
