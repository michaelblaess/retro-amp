"""Tests fuer Rechtsklick und Baum-Operationen im Ordner-Browser."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult

from retro_amp.widgets.folder_browser import FolderBrowser


class _HostApp(App[None]):
    """Minimal-App, die nur den Ordner-Baum haelt."""

    def __init__(self, root: Path) -> None:
        super().__init__()
        self._root = root
        self.menu_events: list[FolderBrowser.ContextMenuRequested] = []
        self.selected_files: list[Path] = []

    def compose(self) -> ComposeResult:
        yield FolderBrowser(str(self._root), id="folder-browser")

    def on_folder_browser_context_menu_requested(
        self,
        event: FolderBrowser.ContextMenuRequested,
    ) -> None:
        self.menu_events.append(event)

    def on_directory_tree_file_selected(self, event: object) -> None:
        self.selected_files.append(event.path)  # type: ignore[attr-defined]


@pytest.fixture
def music_root(tmp_path: Path) -> Path:
    """Baut einen kleinen Baum: root/artist/album/song.mp3 plus root/lose.mp3."""
    album = tmp_path / "artist" / "album"
    album.mkdir(parents=True)
    (album / "song.mp3").write_bytes(b"")
    (tmp_path / "artist" / "b-seiten").mkdir()
    (tmp_path / "lose.mp3").write_bytes(b"")
    return tmp_path


async def _expand_all_levels(browser: FolderBrowser, pilot: object) -> None:
    """Klappt Wurzel, artist und album auf und wartet auf das Nachladen."""
    for _ in range(6):
        for node in (browser.root, *browser.root.children):
            if node.allow_expand and not node.is_expanded:
                node.expand()
            for grandchild in node.children:
                if grandchild.allow_expand and not grandchild.is_expanded:
                    grandchild.expand()
        await pilot.pause()  # type: ignore[attr-defined]


class TestRightClick:
    async def test_right_click_on_file_posts_menu_and_does_not_play(self, music_root: Path) -> None:
        app = _HostApp(music_root)
        async with app.run_test(size=(60, 24)) as pilot:
            browser = app.query_one(FolderBrowser)
            browser.root.expand()
            await pilot.pause()
            await pilot.pause()

            # Zeile der Datei "lose.mp3" im aufgeklappten Baum suchen
            line = next(
                index
                for index in range(browser.last_line + 1)
                if (node := browser.get_node_at_line(index)) is not None
                and node.data is not None
                and node.data.path.name == "lose.mp3"
            )
            await pilot.click(FolderBrowser, offset=(4, line), button=3)
            await pilot.pause()

            assert len(app.menu_events) == 1
            event = app.menu_events[0]
            assert event.path.name == "lose.mp3"
            assert event.is_dir is False
            # Entscheidend: der Rechtsklick darf keine Wiedergabe ausloesen
            assert app.selected_files == []

    async def test_right_click_moves_cursor_to_clicked_node(self, music_root: Path) -> None:
        app = _HostApp(music_root)
        async with app.run_test(size=(60, 24)) as pilot:
            browser = app.query_one(FolderBrowser)
            browser.root.expand()
            await pilot.pause()
            await pilot.pause()
            assert browser.cursor_line == 0

            await pilot.click(FolderBrowser, offset=(4, 1), button=3)
            await pilot.pause()

            assert browser.cursor_line == 1
            assert app.menu_events[0].path == browser.cursor_node.data.path  # type: ignore[union-attr]

    async def test_right_click_on_folder_reports_expansion_state(self, music_root: Path) -> None:
        app = _HostApp(music_root)
        async with app.run_test(size=(60, 24)) as pilot:
            browser = app.query_one(FolderBrowser)
            browser.root.expand()
            await pilot.pause()
            await pilot.pause()

            line = next(
                index
                for index in range(browser.last_line + 1)
                if (node := browser.get_node_at_line(index)) is not None
                and node.data is not None
                and node.data.path.name == "artist"
            )
            await pilot.click(FolderBrowser, offset=(4, line), button=3)
            await pilot.pause()
            assert app.menu_events[-1].is_dir is True
            assert app.menu_events[-1].is_expanded is False

            browser.set_node_expanded(music_root / "artist", True)
            await pilot.pause()
            await pilot.click(FolderBrowser, offset=(4, line), button=3)
            await pilot.pause()
            assert app.menu_events[-1].is_expanded is True

    async def test_left_click_still_selects(self, music_root: Path) -> None:
        app = _HostApp(music_root)
        async with app.run_test(size=(60, 24)) as pilot:
            browser = app.query_one(FolderBrowser)
            browser.root.expand()
            await pilot.pause()
            await pilot.pause()

            line = next(
                index
                for index in range(browser.last_line + 1)
                if (node := browser.get_node_at_line(index)) is not None
                and node.data is not None
                and node.data.path.name == "lose.mp3"
            )
            await pilot.click(FolderBrowser, offset=(4, line))
            await pilot.pause()

            assert [p.name for p in app.selected_files] == ["lose.mp3"]
            assert app.menu_events == []


class TestCollapse:
    async def test_collapse_all_leaves_only_root_expanded(self, music_root: Path) -> None:
        app = _HostApp(music_root)
        async with app.run_test(size=(60, 24)) as pilot:
            browser = app.query_one(FolderBrowser)
            await _expand_all_levels(browser, pilot)
            assert browser.last_line > 2, "Baum war nicht aufgeklappt - Test wertlos"

            browser.collapse_all()
            await pilot.pause()

            assert browser.root.is_expanded
            assert all(not child.is_expanded for child in browser.root.children)
            assert browser.cursor_line == 0

    async def test_collapse_all_reaches_deeper_levels(self, music_root: Path) -> None:
        app = _HostApp(music_root)
        async with app.run_test(size=(60, 24)) as pilot:
            browser = app.query_one(FolderBrowser)
            await _expand_all_levels(browser, pilot)
            artist = next(c for c in browser.root.children if c.data and c.data.path.name == "artist")
            assert any(grandchild.is_expanded for grandchild in artist.children), "album war nicht offen"

            browser.collapse_all()
            await pilot.pause()

            assert all(not grandchild.is_expanded for grandchild in artist.children)

    async def test_set_node_expanded_toggles_single_level(self, music_root: Path) -> None:
        app = _HostApp(music_root)
        async with app.run_test(size=(60, 24)) as pilot:
            browser = app.query_one(FolderBrowser)
            browser.root.expand()
            await pilot.pause()
            await pilot.pause()
            artist_path = music_root / "artist"

            browser.set_node_expanded(artist_path, True)
            await pilot.pause()
            artist = next(c for c in browser.root.children if c.data and c.data.path == artist_path)
            assert artist.is_expanded
            # Nur eine Ebene: die Unterordner bleiben zu
            assert all(not grandchild.is_expanded for grandchild in artist.children)

            browser.set_node_expanded(artist_path, False)
            await pilot.pause()
            assert not artist.is_expanded

    async def test_set_node_expanded_ignores_files(self, music_root: Path) -> None:
        app = _HostApp(music_root)
        async with app.run_test(size=(60, 24)) as pilot:
            browser = app.query_one(FolderBrowser)
            browser.root.expand()
            await pilot.pause()
            await pilot.pause()
            # Darf nicht werfen und nichts veraendern
            browser.set_node_expanded(music_root / "lose.mp3", True)
            await pilot.pause()
            node = next(c for c in browser.root.children if c.data and c.data.path.name == "lose.mp3")
            assert not node.is_expanded
