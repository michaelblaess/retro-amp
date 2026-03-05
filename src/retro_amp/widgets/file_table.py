"""Datei-Tabelle Widget — zeigt Audio-Dateien im aktuellen Ordner."""
from __future__ import annotations

from pathlib import Path

from rich.text import Text

from textual import on
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Static

from ..domain.models import AudioTrack


class FileTable(Widget):
    """Tabelle mit Audio-Dateien: Name, Format, Bitrate, Dauer, Datum, Groesse."""

    DEFAULT_CSS = """
    FileTable {
        width: 100%;
        height: 1fr;
        layout: vertical;
    }
    FileTable #file-info {
        height: 1;
        padding: 0 1;
        background: $accent;
        color: $text;
        text-style: bold;
    }
    FileTable DataTable {
        height: 1fr;
    }
    """

    class TrackSelected(Message):
        """Wird gesendet wenn ein Track per Enter ausgewaehlt wird."""

        def __init__(self, track: AudioTrack) -> None:
            super().__init__()
            self.track = track

    class TrackHighlighted(Message):
        """Wird gesendet wenn ein Track hervorgehoben wird."""

        def __init__(self, track: AudioTrack) -> None:
            super().__init__()
            self.track = track

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._tracks: list[AudioTrack] = []
        self._filtered_tracks: list[AudioTrack] = []
        self._playing_path: Path | None = None
        self._name_col_key: object | None = None
        self._current_path: Path | None = None

    def compose(self):  # type: ignore[override]
        yield Static("", id="file-info")
        yield DataTable(id="file-data", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Initialisiert die Tabellen-Spalten."""
        table = self.query_one("#file-data", DataTable)
        col_keys = table.add_columns(
            "Name", "Format", "Bitrate", "Dauer", "Datum", "Groesse",
        )
        self._name_col_key = col_keys[0]

    def update_tracks(self, tracks: list[AudioTrack]) -> None:
        """Aktualisiert die Tabelle mit neuen Tracks."""
        self._tracks = tracks
        self._filtered_tracks = list(tracks)
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        """Baut die Tabelle mit gefilterten Tracks auf."""
        table = self.query_one("#file-data", DataTable)
        table.clear()

        for track in self._filtered_tracks:
            name_cell = self._format_name(track)
            table.add_row(
                name_cell,
                track.format_display,
                track.bitrate_display,
                track.duration_display,
                track.date_display,
                track.size_display,
                key=str(track.path),
            )

        self._update_info_label()

    def set_path(self, path: Path) -> None:
        """Setzt den aktuellen Ordner-Pfad."""
        self._current_path = path
        self._update_info_label()

    def _update_info_label(self) -> None:
        """Aktualisiert die kombinierte Pfad + Dateianzahl Zeile."""
        info = self.query_one("#file-info", Static)
        path_str = str(self._current_path) if self._current_path else ""
        total = len(self._tracks)
        count_str = f"{total} Dateien" if total != 1 else "1 Datei"
        if total == 0:
            count_str = "Keine Audio-Dateien"
        if path_str:
            info.update(f"{path_str}  [{count_str}]")
        else:
            info.update(count_str)

    def mark_playing(self, path: Path | None) -> None:
        """Markiert den aktuell spielenden Track visuell."""
        table = self.query_one("#file-data", DataTable)
        old_path = self._playing_path
        self._playing_path = path

        # Alten Marker entfernen
        if old_path and self._name_col_key is not None:
            for track in self._filtered_tracks:
                if track.path == old_path:
                    try:
                        table.update_cell(
                            str(old_path), self._name_col_key, track.display_name,
                        )
                    except Exception:
                        pass
                    break

        # Neuen Marker setzen
        if path and self._name_col_key is not None:
            for track in self._filtered_tracks:
                if track.path == path:
                    styled = Text(f"\u25b6 {track.display_name}", style="bold green")
                    try:
                        table.update_cell(
                            str(path), self._name_col_key, styled,
                        )
                    except Exception:
                        pass
                    break

    @property
    def highlighted_track(self) -> AudioTrack | None:
        """Gibt den aktuell hervorgehobenen (Cursor) Track zurueck."""
        table = self.query_one("#file-data", DataTable)
        idx = table.cursor_row
        if 0 <= idx < len(self._filtered_tracks):
            return self._filtered_tracks[idx]
        return None

    @on(DataTable.RowSelected, "#file-data")
    def _on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Track wurde per Enter ausgewaehlt."""
        idx = event.cursor_row
        if 0 <= idx < len(self._filtered_tracks):
            self.post_message(FileTable.TrackSelected(self._filtered_tracks[idx]))

    @on(DataTable.RowHighlighted, "#file-data")
    def _on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Track wurde hervorgehoben (Cursor bewegt)."""
        idx = event.cursor_row
        if 0 <= idx < len(self._filtered_tracks):
            self.post_message(FileTable.TrackHighlighted(self._filtered_tracks[idx]))

    def highlight_track(self, track: AudioTrack) -> None:
        """Bewegt den Cursor zum angegebenen Track."""
        table = self.query_one("#file-data", DataTable)
        for idx, t in enumerate(self._filtered_tracks):
            if t.path == track.path:
                table.move_cursor(row=idx)
                break

    def _format_name(self, track: AudioTrack) -> str | Text:
        """Formatiert den Namen — mit Pfeil wenn gerade gespielt wird."""
        if self._playing_path and track.path == self._playing_path:
            return Text(f"\u25b6 {track.display_name}", style="bold green")
        return track.display_name
