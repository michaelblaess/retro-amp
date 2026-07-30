"""Datei-Tabelle Widget — zeigt Audio-Dateien im aktuellen Ordner."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.text import Text
from textual import on
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Static
from textual.widgets.data_table import ColumnKey

from ..domain.models import AudioTrack
from ..i18n import t

# Sortier-Schluessel je Spaltenindex. Nur Spalten, die hier stehen,
# reagieren auf einen Klick auf den Spaltenkopf. Rueckgabetyp ist Any,
# weil die Schluessel je Spalte str, int oder float liefern.
SORT_KEYS: dict[int, Callable[[AudioTrack], Any]] = {
    0: lambda tr: tr.display_name.casefold(),
    1: lambda tr: tr.format_display,
    2: lambda tr: tr.bitrate_kbps,
    3: lambda tr: tr.duration_seconds,
    4: lambda tr: tr.modified_date,
    5: lambda tr: tr.file_size_bytes,
}

ARROW_ASC = "▲"
ARROW_DESC = "▼"


def sort_tracks(
    tracks: list[AudioTrack],
    column: int | None,
    descending: bool,
) -> list[AudioTrack]:
    """Sortiert Tracks nach Spaltenindex.

    Zweitschluessel ist immer der Anzeigename aufsteigend - deshalb wird
    zuerst nach Namen und danach stabil nach der Zielspalte sortiert.
    Unbekannte Spalten liefern die Eingabereihenfolge zurueck.
    """
    key = SORT_KEYS.get(column) if column is not None else None
    if key is None:
        return list(tracks)
    ordered = sorted(tracks, key=lambda tr: tr.display_name.casefold())
    ordered.sort(key=key, reverse=descending)
    return ordered


def _format_size(total_bytes: int) -> str:
    """Formatiert Bytes dynamisch als B/KB/MB/GB."""
    if total_bytes <= 0:
        return ""
    if total_bytes < 1024:
        return f"{total_bytes} B"
    if total_bytes < 1024 * 1024:
        return f"{total_bytes / 1024:.0f} KB"
    if total_bytes < 1024 * 1024 * 1024:
        return f"{total_bytes / (1024 * 1024):.0f} MB"
    return f"{total_bytes / (1024 * 1024 * 1024):.1f} GB"


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

    class OrderChanged(Message):
        """Wird gesendet wenn sich die Reihenfolge der Tabelle geaendert hat.

        Die App zieht damit ihre Abspiel-Reihenfolge nach, damit "naechster
        Track" der sichtbaren Sortierung folgt.
        """

        def __init__(self, tracks: list[AudioTrack]) -> None:
            super().__init__()
            self.tracks = tracks

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._tracks: list[AudioTrack] = []
        self._filtered_tracks: list[AudioTrack] = []
        self._playing_path: Path | None = None
        self._name_col_key: ColumnKey | None = None
        self._current_path: Path | None = None
        self._base_column_labels: list[str] = []
        self._col_keys: list[ColumnKey] = []
        self._sort_col: int | None = None
        self._sort_desc: bool = False

    def compose(self):  # type: ignore[override]
        yield Static("", id="file-info")
        yield DataTable(id="file-data", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Initialisiert die Tabellen-Spalten."""
        table = self.query_one("#file-data", DataTable)
        self._base_column_labels = [
            t("file_table.name"),
            t("file_table.format"),
            t("file_table.bitrate"),
            t("file_table.duration"),
            t("file_table.date"),
            t("file_table.size"),
        ]
        # Mit reserviertem Platz fuer den Pfeil anlegen, sonst springt die
        # Spaltenbreite beim Wechsel der Sortierspalte.
        self._col_keys = list(
            table.add_columns(*(self._column_label(idx) for idx in range(len(self._base_column_labels)))),
        )
        self._name_col_key = self._col_keys[0]

    @property
    def ordered_tracks(self) -> list[AudioTrack]:
        """Tracks in der aktuell sichtbaren Reihenfolge."""
        return list(self._filtered_tracks)

    def update_tracks(self, tracks: list[AudioTrack]) -> None:
        """Aktualisiert die Tabelle mit neuen Tracks."""
        self._tracks = tracks
        self._filtered_tracks = sort_tracks(tracks, self._sort_col, self._sort_desc)
        self._rebuild_table()

    def _rebuild_table(self, keep_track: AudioTrack | None = None) -> None:
        """Baut die Tabelle mit gefilterten Tracks auf.

        ``keep_track`` bewegt den Cursor nach dem Neuaufbau wieder auf
        diesen Track, damit eine Sortierung die Auswahl nicht verliert.
        """
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

        if keep_track is not None:
            self.highlight_track(keep_track)

        self._update_info_label()

    # --- Sortierung ---

    def _column_label(self, index: int) -> str:
        """Spaltentitel inkl. Sortier-Pfeil bzw. Platzhalter dafuer."""
        base = self._base_column_labels[index]
        if index != self._sort_col:
            return f"{base}  "
        return f"{base} {ARROW_DESC if self._sort_desc else ARROW_ASC}"

    def _update_sort_indicator(self) -> None:
        """Setzt den Pfeil am aktiven Spaltenkopf, entfernt ihn an den anderen."""
        table = self.query_one("#file-data", DataTable)
        for index, key in enumerate(self._col_keys):
            column = table.columns.get(key)
            if column is not None:
                column.label = Text(self._column_label(index))
        table.refresh()

    @on(DataTable.HeaderSelected, "#file-data")
    def _on_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Klick auf einen Spaltenkopf sortiert nach dieser Spalte."""
        col_index = event.column_index
        if col_index not in SORT_KEYS:
            return
        if col_index == self._sort_col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col_index
            self._sort_desc = False

        keep_track = self.highlighted_track
        self._filtered_tracks = sort_tracks(self._tracks, self._sort_col, self._sort_desc)
        self._rebuild_table(keep_track=keep_track)
        self._update_sort_indicator()
        self.post_message(FileTable.OrderChanged(self.ordered_tracks))

    def set_path(self, path: Path) -> None:
        """Setzt den aktuellen Ordner-Pfad."""
        self._current_path = path
        self._update_info_label()

    def _update_info_label(self) -> None:
        """Aktualisiert die kombinierte Pfad + Dateianzahl Zeile."""
        info = self.query_one("#file-info", Static)
        path_str = str(self._current_path) if self._current_path else ""
        total = len(self._tracks)
        if total == 0:
            count_str = t("file_table.empty")
        elif total == 1:
            count_str = t("file_table.count_one")
        else:
            count_str = t("file_table.count", count=total)
        if total > 0:
            total_bytes = sum(max(0, track.file_size_bytes) for track in self._tracks)
            size_str = _format_size(total_bytes)
            count_str = f"{count_str} \u00b7 {size_str}" if size_str else count_str
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
                    with contextlib.suppress(Exception):
                        table.update_cell(
                            str(old_path),
                            self._name_col_key,
                            track.display_name,
                        )
                    break

        # Neuen Marker setzen
        if path and self._name_col_key is not None:
            for track in self._filtered_tracks:
                if track.path == path:
                    styled = Text(f"\u25b6 {track.display_name}", style="bold green")
                    with contextlib.suppress(Exception):
                        table.update_cell(
                            str(path),
                            self._name_col_key,
                            styled,
                        )
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
        for idx, candidate in enumerate(self._filtered_tracks):
            if candidate.path == track.path:
                table.move_cursor(row=idx)
                break

    def _format_name(self, track: AudioTrack) -> str | Text:
        """Formatiert den Namen — mit Pfeil wenn gerade gespielt wird."""
        if self._playing_path and track.path == self._playing_path:
            return Text(f"\u25b6 {track.display_name}", style="bold green")
        return track.display_name
