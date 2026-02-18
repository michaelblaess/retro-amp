"""Datei-Tabelle Widget — zeigt Audio-Dateien im aktuellen Ordner."""
from __future__ import annotations

from textual import on
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Static

from ..domain.models import AudioTrack


class FileTable(Widget):
    """Tabelle mit Audio-Dateien: Name, Format, Bitrate, Dauer."""

    DEFAULT_CSS = """
    FileTable {
        width: 100%;
        height: 1fr;
        layout: vertical;
    }
    FileTable #file-count {
        height: 1;
        padding: 0 1;
        color: $text-muted;
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

    def compose(self):  # type: ignore[override]
        yield Static("Keine Dateien", id="file-count")
        yield DataTable(id="file-data", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Initialisiert die Tabellen-Spalten."""
        table = self.query_one("#file-data", DataTable)
        table.add_columns("Name", "Format", "Bitrate", "Dauer")

    def update_tracks(self, tracks: list[AudioTrack]) -> None:
        """Aktualisiert die Tabelle mit neuen Tracks."""
        self._tracks = tracks
        table = self.query_one("#file-data", DataTable)
        table.clear()

        for track in tracks:
            table.add_row(
                track.display_name,
                track.format_display,
                track.bitrate_display,
                track.duration_display,
                key=str(track.path),
            )

        count_label = self.query_one("#file-count", Static)
        count = len(tracks)
        if count == 0:
            count_label.update("Keine Audio-Dateien")
        elif count == 1:
            count_label.update("1 Datei")
        else:
            count_label.update(f"{count} Dateien")

    @on(DataTable.RowSelected, "#file-data")
    def _on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Track wurde per Enter ausgewaehlt."""
        idx = event.cursor_row
        if 0 <= idx < len(self._tracks):
            self.post_message(FileTable.TrackSelected(self._tracks[idx]))

    @on(DataTable.RowHighlighted, "#file-data")
    def _on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Track wurde hervorgehoben (Cursor bewegt)."""
        idx = event.cursor_row
        if 0 <= idx < len(self._tracks):
            self.post_message(FileTable.TrackHighlighted(self._tracks[idx]))

    def highlight_track(self, track: AudioTrack) -> None:
        """Markiert den aktuell spielenden Track in der Tabelle."""
        table = self.query_one("#file-data", DataTable)
        for idx, t in enumerate(self._tracks):
            if t.path == track.path:
                table.move_cursor(row=idx)
                break
