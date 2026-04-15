"""Now-Playing-Screen — Vollbild-Cover mit Track-Infos.

Absichtlich keine periodisch aktualisierten Widgets (TransportBar/Fortschritt),
da der TGP/Sixel-Image-Widget bei jedem Screen-Repaint das Bild ueber das
Terminal-Protokoll neu uebertraegt und dadurch flackert.

Der Now-Playing-Screen ist daher bewusst statisch: Cover + Artist/Title/Album.
Den dynamischen Transport-Status sieht der Nutzer im Hauptscreen (TAB wechselt).
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ..domain.models import PlayerState
from ..i18n import t
from ..widgets.cover_art_panel import CoverArtPanel


class NowPlayingScreen(Screen[None]):
    """Vollbild-Ansicht mit grossem Cover-Art und Track-Informationen."""

    DEFAULT_CSS = """
    NowPlayingScreen {
        layout: vertical;
        background: $primary-background;
    }
    NowPlayingScreen #now-playing-info {
        height: 3;
        content-align: center middle;
        color: $text;
        padding: 0 2;
    }
    NowPlayingScreen CoverArtPanel {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "ESC"),
        Binding("tab", "close", t("binding.cycle_view"), key_display="TAB", priority=True),
        Binding("q", "quit_app", t("binding.quit")),
    ]

    def __init__(self, renderer: str = "halfblock") -> None:
        super().__init__()
        self._renderer = renderer
        self._pending_cover: tuple[str, str, bytes | None] | None = None
        self._pending_state: PlayerState | None = None
        self._last_info_text: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="now-playing-info")
        yield CoverArtPanel(renderer=self._renderer, id="now-playing-cover")
        yield Footer()

    def on_mount(self) -> None:
        if self._pending_state is not None:
            self._update_info_line(self._pending_state)
        if self._pending_cover is not None:
            artist, title, data = self._pending_cover
            self.update_cover(artist, title, data)

    def set_initial(
        self,
        cover: tuple[str, str, bytes | None] | None,
        state: PlayerState | None,
    ) -> None:
        """Speichert Startzustand, wird in on_mount angewendet."""
        self._pending_cover = cover
        self._pending_state = state

    def update_cover(self, artist: str, title: str, data: bytes | None) -> None:
        """Aktualisiert Cover + Info-Zeile (wird beim Track-Wechsel aufgerufen)."""
        try:
            self.query_one("#now-playing-cover", CoverArtPanel).show_cover(
                artist, title, data,
            )
        except Exception:
            pass
        self._update_info_line(self.app._player_service.state)  # type: ignore[attr-defined]

    def _update_info_line(self, state: PlayerState) -> None:
        """Setzt die Info-Zeile (Artist/Titel/Album), nur wenn sich der Text aendert."""
        try:
            info_widget = self.query_one("#now-playing-info", Static)
        except Exception:
            return

        track = state.current_track
        if track:
            parts: list[str] = []
            if track.artist:
                parts.append(track.artist)
            title = track.title or track.display_name
            if title:
                parts.append(title)
            line1 = " \u2014 ".join(parts) if parts else track.display_name
            line2 = track.album if track.album else ""
            new_text = f"[bold]{line1}[/bold]\n[dim]{line2}[/dim]"
        else:
            new_text = t("transport.no_track")

        if new_text == self._last_info_text:
            return
        self._last_info_text = new_text
        info_widget.update(new_text)

    def action_close(self) -> None:
        """Schliesst den Now-Playing-Screen."""
        self.app.pop_screen()

    def action_quit_app(self) -> None:
        """Beendet die gesamte Anwendung."""
        self.app.exit()
