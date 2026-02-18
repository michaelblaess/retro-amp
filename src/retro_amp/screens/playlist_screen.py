"""Playlist-Screen — Modal fuer Playlist-Verwaltung."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
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
    PlaylistScreen #new-name {
        width: 1fr;
        margin-bottom: 1;
    }
    PlaylistScreen #button-row {
        layout: horizontal;
        height: 3;
        align: center middle;
    }
    PlaylistScreen #btn-save {
        margin-right: 2;
    }
    """

    BINDINGS = [
        Binding("escape,q", "close", "Abbrechen"),
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

            if self._playlists:
                yield DataTable(id="playlist-table", cursor_type="row")

            yield Input(
                placeholder="Neue Playlist erstellen...",
                id="new-name",
            )

            with Horizontal(id="button-row"):
                yield Button("Speichern (Enter)", id="btn-save", variant="primary")
                yield Button("Abbrechen (q)", id="btn-close", variant="default")

    def on_mount(self) -> None:
        """Tabelle mit Playlists fuellen."""
        try:
            table = self.query_one("#playlist-table", DataTable)
            table.add_columns("Playlist")
            for name in self._playlists:
                table.add_row(name, key=name)
        except Exception:
            pass  # Keine Tabelle wenn keine Playlists

    @on(DataTable.RowSelected, "#playlist-table")
    def _on_playlist_selected(self, event: DataTable.RowSelected) -> None:
        """Bestehende Playlist ausgewaehlt."""
        if event.row_key and event.row_key.value:
            self.dismiss(event.row_key.value)

    @on(Input.Submitted, "#new-name")
    def _on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter im Input-Feld — neue Playlist erstellen."""
        self._save()

    @on(Button.Pressed, "#btn-save")
    def _on_save(self) -> None:
        """Speichern-Button gedrueckt."""
        self._save()

    @on(Button.Pressed, "#btn-close")
    def _on_close(self) -> None:
        """Abbrechen-Button gedrueckt."""
        self.dismiss(None)

    def _save(self) -> None:
        """Neue Playlist erstellen oder ausgewaehlte verwenden."""
        name_input = self.query_one("#new-name", Input)
        name = name_input.value.strip()
        if name:
            self.dismiss(name)
        else:
            self.notify("Bitte einen Namen eingeben", severity="warning")

    def action_close(self) -> None:
        """ESC oder q gedrueckt."""
        self.dismiss(None)
