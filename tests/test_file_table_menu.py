"""Tests fuer den Rechtsklick in der Datei-Tabelle."""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.text import Text
from textual.app import App, ComposeResult

from retro_amp.domain.models import AudioFormat, AudioTrack
from retro_amp.widgets.file_table import FileDataTable, FileTable


class _HostApp(App[None]):
    """Minimal-App mit der Datei-Tabelle und Mitschnitt der Messages."""

    def __init__(self) -> None:
        super().__init__()
        self.menus: list[FileTable.ContextMenuRequested] = []
        self.selected: list[Path] = []

    def compose(self) -> ComposeResult:
        yield FileTable(id="file-table")

    def on_file_table_context_menu_requested(self, event: FileTable.ContextMenuRequested) -> None:
        self.menus.append(event)

    def on_file_table_track_selected(self, event: FileTable.TrackSelected) -> None:
        self.selected.append(event.track.path)


@pytest.fixture
def tracks() -> list[AudioTrack]:
    return [
        AudioTrack(path=Path(f"/music/{name}.mod"), format=AudioFormat.MOD, title=name)
        for name in ("alpha", "beta", "gamma")
    ]


# y=0 ist der Spaltenkopf, die Datenzeilen beginnen bei y=1
def _row_y(row_index: int) -> int:
    return row_index + 1


class TestRightClick:
    async def test_right_click_posts_menu_and_does_not_select(self, tracks: list[AudioTrack]) -> None:
        app = _HostApp()
        async with app.run_test(size=(90, 20)) as pilot:
            app.query_one(FileTable).update_tracks(tracks)
            await pilot.pause()

            await pilot.click(FileDataTable, offset=(5, _row_y(1)), button=3)
            await pilot.pause()

            assert len(app.menus) == 1
            assert app.menus[0].track.path == tracks[1].path
            # Entscheidend: der Rechtsklick darf keine Wiedergabe ausloesen
            assert app.selected == []

    async def test_right_click_moves_cursor_to_clicked_row(self, tracks: list[AudioTrack]) -> None:
        app = _HostApp()
        async with app.run_test(size=(90, 20)) as pilot:
            file_table = app.query_one(FileTable)
            file_table.update_tracks(tracks)
            await pilot.pause()
            assert file_table.highlighted_track is not None
            assert file_table.highlighted_track.path == tracks[0].path

            await pilot.click(FileDataTable, offset=(5, _row_y(2)), button=3)
            await pilot.pause()

            assert file_table.highlighted_track is not None
            assert file_table.highlighted_track.path == tracks[2].path

    async def test_left_click_still_selects_exactly_once(self, tracks: list[AudioTrack]) -> None:
        """Linksklick bleibt unveraendert - inklusive Textuals Zwei-Klick-Verhalten.

        ``DataTable`` sendet ``RowSelected`` erst beim Klick auf die bereits
        markierte Zeile (``highlight_click`` in ``DataTable._on_click``). Der
        erste Klick verschiebt also nur den Cursor.
        """
        app = _HostApp()
        async with app.run_test(size=(90, 20)) as pilot:
            app.query_one(FileTable).update_tracks(tracks)
            await pilot.pause()

            await pilot.click(FileDataTable, offset=(5, _row_y(1)))
            await pilot.pause()
            assert app.selected == []

            await pilot.click(FileDataTable, offset=(5, _row_y(1)))
            await pilot.pause()
            assert app.selected == [tracks[1].path]
            assert app.menus == []

    async def test_right_click_on_header_does_nothing(self, tracks: list[AudioTrack]) -> None:
        app = _HostApp()
        async with app.run_test(size=(90, 20)) as pilot:
            app.query_one(FileTable).update_tracks(tracks)
            await pilot.pause()

            await pilot.click(FileDataTable, offset=(5, 0), button=3)
            await pilot.pause()

            assert app.menus == []
            assert app.selected == []

    async def test_right_click_on_empty_table_does_nothing(self) -> None:
        app = _HostApp()
        async with app.run_test(size=(90, 20)) as pilot:
            app.query_one(FileTable).update_tracks([])
            await pilot.pause()

            await pilot.click(FileDataTable, offset=(5, _row_y(0)), button=3)
            await pilot.pause()

            assert app.menus == []

    async def test_menu_follows_sort_order(self, tracks: list[AudioTrack]) -> None:
        """Nach dem Umsortieren muss die Zeile den dort sichtbaren Track melden."""
        app = _HostApp()
        async with app.run_test(size=(90, 20)) as pilot:
            file_table = app.query_one(FileTable)
            file_table.update_tracks(tracks)
            await pilot.pause()

            table = file_table.query_one("#file-data", FileDataTable)
            column_key = list(table.columns)[0]
            table.post_message(FileDataTable.HeaderSelected(table, column_key, 0, Text("")))
            await pilot.pause()
            table.post_message(FileDataTable.HeaderSelected(table, column_key, 0, Text("")))
            await pilot.pause()
            assert [tr.display_name for tr in file_table.ordered_tracks] == ["gamma", "beta", "alpha"]

            await pilot.click(FileDataTable, offset=(5, _row_y(0)), button=3)
            await pilot.pause()

            assert app.menus[-1].track.display_name == "gamma"
