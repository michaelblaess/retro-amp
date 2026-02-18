"""Playlist-Screen — Modal fuer Playlist-Verwaltung."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static


class PlaylistScreen(ModalScreen[str | None]):
    """Modal-Dialog fuer Playlist-Auswahl und -Erstellung.

    Gibt den gewaehlten Playlist-Namen zurueck oder None bei Abbruch.
    """

    DEFAULT_CSS = """
    PlaylistScreen {
        align: center middle;
    }
    PlaylistScreen #dialog {
        width: 60;
        height: auto;
        max-height: 80%;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    PlaylistScreen #dialog-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        padding-bottom: 1;
    }
    PlaylistScreen DataTable {
        height: auto;
        max-height: 15;
        margin-bottom: 1;
    }
    PlaylistScreen #new-playlist-row {
        layout: horizontal;
        height: 3;
        margin-bottom: 1;
    }
    PlaylistScreen #new-name {
        width: 1fr;
    }
    PlaylistScreen #btn-create {
        width: auto;
        min-width: 12;
    }
    PlaylistScreen #btn-close {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Schliessen"),
    ]

    def __init__(self, playlists: list[str], current_track_name: str = "") -> None:
        super().__init__()
        self._playlists = playlists
        self._current_track_name = current_track_name

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            if self._current_track_name:
                yield Label(
                    f"Track: {self._current_track_name}",
                    id="dialog-title",
                )
            else:
                yield Label("Playlists", id="dialog-title")

            yield DataTable(id="playlist-table", cursor_type="row")

            with Vertical(id="new-playlist-row"):
                yield Input(
                    placeholder="Neue Playlist erstellen...",
                    id="new-name",
                )

            yield Button("Schliessen [ESC]", id="btn-close", variant="default")

    def on_mount(self) -> None:
        """Tabelle mit Playlists fuellen."""
        table = self.query_one("#playlist-table", DataTable)
        table.add_columns("Playlist", "Aktion")
        for name in self._playlists:
            table.add_row(name, "Hinzufuegen", key=name)

    @on(DataTable.RowSelected, "#playlist-table")
    def _on_playlist_selected(self, event: DataTable.RowSelected) -> None:
        """Playlist ausgewaehlt — Name zurueckgeben."""
        if event.row_key and event.row_key.value:
            self.dismiss(event.row_key.value)

    @on(Input.Submitted, "#new-name")
    def _on_new_playlist(self, event: Input.Submitted) -> None:
        """Neue Playlist erstellen und auswaehlen."""
        name = event.value.strip()
        if name:
            self.dismiss(name)

    @on(Button.Pressed, "#btn-close")
    def _on_close(self) -> None:
        """Dialog schliessen."""
        self.dismiss(None)

    def action_close(self) -> None:
        """ESC gedrueckt."""
        self.dismiss(None)
