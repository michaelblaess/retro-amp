"""Tests fuer die Sortierung der Datei-Tabelle."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from retro_amp.domain.models import AudioFormat, AudioTrack
from retro_amp.widgets.file_table import ARROW_ASC, ARROW_DESC, SORT_KEYS, FileTable, sort_tracks


def _track(
    name: str,
    *,
    size: int = 0,
    duration: float = 0.0,
    bitrate: int = 0,
    date: str = "",
    fmt: AudioFormat = AudioFormat.MOD,
) -> AudioTrack:
    return AudioTrack(
        path=Path(f"/music/{name}.{fmt.value}"),
        format=fmt,
        title=name,
        file_size_bytes=size,
        duration_seconds=duration,
        bitrate_kbps=bitrate,
        modified_date=date,
    )


TRACKS = [
    _track("beta", size=200_000, duration=90.0, bitrate=192, date="1994-02-22T10:00:00", fmt=AudioFormat.MOD),
    _track("Alpha", size=500_000, duration=30.0, bitrate=320, date="1993-10-09T10:00:00", fmt=AudioFormat.S3M),
    _track("gamma", size=100_000, duration=200.0, bitrate=128, date="1995-02-11T10:00:00", fmt=AudioFormat.MOD),
]


def _names(tracks: list[AudioTrack]) -> list[str]:
    return [tr.display_name for tr in tracks]


class TestSortTracks:
    def test_none_column_keeps_input_order(self) -> None:
        assert _names(sort_tracks(TRACKS, None, False)) == ["beta", "Alpha", "gamma"]

    def test_unknown_column_keeps_input_order(self) -> None:
        assert _names(sort_tracks(TRACKS, 99, False)) == ["beta", "Alpha", "gamma"]

    def test_does_not_mutate_input(self) -> None:
        original = list(TRACKS)
        sort_tracks(TRACKS, 5, True)
        assert original == TRACKS

    def test_name_ascending_is_case_insensitive(self) -> None:
        assert _names(sort_tracks(TRACKS, 0, False)) == ["Alpha", "beta", "gamma"]

    def test_name_descending(self) -> None:
        assert _names(sort_tracks(TRACKS, 0, True)) == ["gamma", "beta", "Alpha"]

    def test_size_descending_biggest_first(self) -> None:
        assert _names(sort_tracks(TRACKS, 5, True)) == ["Alpha", "beta", "gamma"]

    def test_size_ascending_smallest_first(self) -> None:
        assert _names(sort_tracks(TRACKS, 5, False)) == ["gamma", "beta", "Alpha"]

    def test_duration_ascending(self) -> None:
        assert _names(sort_tracks(TRACKS, 3, False)) == ["Alpha", "beta", "gamma"]

    def test_bitrate_descending(self) -> None:
        assert _names(sort_tracks(TRACKS, 2, True)) == ["Alpha", "beta", "gamma"]

    def test_date_ascending_uses_iso_value_not_display(self) -> None:
        # Anzeige ist TT.MM.JJJJ - sortiert wird nach dem ISO-Wert
        assert _names(sort_tracks(TRACKS, 4, False)) == ["Alpha", "beta", "gamma"]

    def test_secondary_key_is_name_ascending(self) -> None:
        # Gleiche Groesse: Zweitschluessel Name, auch bei absteigender Sortierung
        same = [
            _track("zulu", size=1000),
            _track("alpha", size=1000),
            _track("mike", size=2000),
        ]
        assert _names(sort_tracks(same, 5, True)) == ["mike", "alpha", "zulu"]
        assert _names(sort_tracks(same, 5, False)) == ["alpha", "zulu", "mike"]

    def test_format_groups_by_format(self) -> None:
        ordered = sort_tracks(TRACKS, 1, False)
        assert [tr.format_display for tr in ordered] == ["MOD", "MOD", "S3M"]
        assert _names(ordered) == ["beta", "gamma", "Alpha"]

    def test_all_six_columns_are_sortable(self) -> None:
        assert sorted(SORT_KEYS) == [0, 1, 2, 3, 4, 5]


class _HostApp(App[None]):
    """Minimal-App, die nur die Datei-Tabelle haelt."""

    def compose(self) -> ComposeResult:
        yield FileTable(id="file-table")


def _click_header(table: DataTable[object], index: int) -> None:
    """Simuliert einen Klick auf den Spaltenkopf mit dem gegebenen Index."""
    column_key = list(table.columns)[index]
    table.post_message(DataTable.HeaderSelected(table, column_key, index, Text("")))


def _column_labels(table: DataTable[object]) -> list[str]:
    return [table.columns[key].label.plain for key in table.columns]


def _visible_names(table: DataTable[object]) -> list[str]:
    return [str(table.get_row_at(row)[0]) for row in range(table.row_count)]


class TestHeaderClick:
    async def test_click_sorts_and_toggles_direction_with_arrow(self) -> None:
        app = _HostApp()
        async with app.run_test() as pilot:
            file_table = app.query_one(FileTable)
            table = file_table.query_one("#file-data", DataTable)
            file_table.update_tracks(list(TRACKS))
            await pilot.pause()

            # Ausgangslage: keine Sortierung, kein Pfeil
            assert _visible_names(table) == ["beta", "Alpha", "gamma"]
            assert not any(ARROW_ASC in label or ARROW_DESC in label for label in _column_labels(table))

            # Erster Klick auf "Groesse" -> aufsteigend
            _click_header(table, 5)
            await pilot.pause()
            assert _visible_names(table) == ["gamma", "beta", "Alpha"]
            assert _column_labels(table)[5].endswith(ARROW_ASC)

            # Zweiter Klick auf dieselbe Spalte -> absteigend (gross nach klein)
            _click_header(table, 5)
            await pilot.pause()
            assert _visible_names(table) == ["Alpha", "beta", "gamma"]
            assert _column_labels(table)[5].endswith(ARROW_DESC)

            # Andere Spalte -> alter Pfeil verschwindet, neuer erscheint aufsteigend
            _click_header(table, 0)
            await pilot.pause()
            assert _visible_names(table) == ["Alpha", "beta", "gamma"]
            assert _column_labels(table)[0].endswith(ARROW_ASC)
            assert ARROW_DESC not in _column_labels(table)[5]

    async def test_column_widths_stay_stable(self) -> None:
        app = _HostApp()
        async with app.run_test() as pilot:
            file_table = app.query_one(FileTable)
            table = file_table.query_one("#file-data", DataTable)
            file_table.update_tracks(list(TRACKS))
            await pilot.pause()
            before = [len(label) for label in _column_labels(table)]

            _click_header(table, 5)
            await pilot.pause()
            assert [len(label) for label in _column_labels(table)] == before

    async def test_sort_survives_folder_change(self) -> None:
        app = _HostApp()
        async with app.run_test() as pilot:
            file_table = app.query_one(FileTable)
            table = file_table.query_one("#file-data", DataTable)
            file_table.update_tracks(list(TRACKS))
            await pilot.pause()
            _click_header(table, 5)
            await pilot.pause()

            # Neuer Ordner - Sortierung bleibt aktiv
            file_table.update_tracks(
                [_track("neu-gross", size=900_000), _track("neu-klein", size=10)],
            )
            await pilot.pause()
            assert _visible_names(table) == ["neu-klein", "neu-gross"]
            assert file_table.ordered_tracks[0].display_name == "neu-klein"

    async def test_cursor_stays_on_same_track(self) -> None:
        app = _HostApp()
        async with app.run_test() as pilot:
            file_table = app.query_one(FileTable)
            table = file_table.query_one("#file-data", DataTable)
            file_table.update_tracks(list(TRACKS))
            await pilot.pause()
            table.move_cursor(row=2)  # "gamma"
            await pilot.pause()
            assert file_table.highlighted_track is not None
            assert file_table.highlighted_track.display_name == "gamma"

            _click_header(table, 5)
            await pilot.pause()
            assert file_table.highlighted_track is not None
            assert file_table.highlighted_track.display_name == "gamma"
