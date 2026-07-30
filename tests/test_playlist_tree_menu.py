"""Tests fuer den Rechtsklick im Playlist-Baum.

Der Playlist-Baum ist der einzige, der in seinen Gruppen-Knoten keinen Pfad,
sondern den Playlist-Namen als ``str`` ablegt - deshalb ein eigenes Testmodul.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.widgets._tree import TreeNode

from retro_amp.widgets.playlist_tree import PlaylistTree


class _HostApp(App[None]):
    """Minimal-App mit dem Playlist-Baum und Mitschnitt der Messages."""

    def __init__(self) -> None:
        super().__init__()
        self.menus: list[PlaylistTree.ContextMenuRequested] = []
        self.selected: list[tuple[Path, str]] = []

    def compose(self) -> ComposeResult:
        yield PlaylistTree(id="playlist-tree")

    def on_playlist_tree_context_menu_requested(self, event: PlaylistTree.ContextMenuRequested) -> None:
        self.menus.append(event)

    def on_playlist_tree_track_selected(self, event: PlaylistTree.TrackSelected) -> None:
        self.selected.append((event.path, event.playlist_name))


@pytest.fixture
def playlists(tmp_path: Path) -> dict[str, list[Path]]:
    songs = []
    for name in ("01-song.mp3", "02-song.mp3"):
        path = tmp_path / name
        path.write_bytes(b"")
        songs.append(path)
    return {"Abends": songs, "Morgens": songs[:1]}


def _line_of(tree: PlaylistTree, predicate: Callable[[TreeNode[Path | str | None]], bool]) -> int:
    for index in range(tree.last_line + 1):
        node = tree.get_node_at_line(index)
        if node is not None and predicate(node):
            return index
    raise AssertionError("kein passender Knoten im Baum")


class TestPlaylistTreeMenu:
    async def test_right_click_on_track_reports_path_and_playlist(
        self,
        playlists: dict[str, list[Path]],
    ) -> None:
        app = _HostApp()
        async with app.run_test(size=(70, 30)) as pilot:
            tree = app.query_one(PlaylistTree)
            tree.load_playlists(playlists)
            await pilot.pause()
            line = _line_of(tree, lambda n: isinstance(n.data, Path) and n.data.name == "02-song.mp3")

            await pilot.click(PlaylistTree, offset=(8, line), button=3)
            await pilot.pause()

            assert len(app.menus) == 1
            assert app.menus[0].path == playlists["Abends"][1]
            assert tree.menu_playlist_name == "Abends"
            # Entscheidend: der Rechtsklick darf keine Wiedergabe ausloesen
            assert app.selected == []

    async def test_right_click_on_playlist_node_reports_name_without_path(
        self,
        playlists: dict[str, list[Path]],
    ) -> None:
        app = _HostApp()
        async with app.run_test(size=(70, 30)) as pilot:
            tree = app.query_one(PlaylistTree)
            tree.load_playlists(playlists)
            await pilot.pause()
            line = _line_of(tree, lambda n: n.data == "Morgens")

            await pilot.click(PlaylistTree, offset=(8, line), button=3)
            await pilot.pause()

            assert app.menus[-1].path is None
            assert app.menus[-1].is_expanded is True
            assert tree.menu_playlist_name == "Morgens"

    async def test_root_reports_no_playlist(self, playlists: dict[str, list[Path]]) -> None:
        app = _HostApp()
        async with app.run_test(size=(70, 30)) as pilot:
            tree = app.query_one(PlaylistTree)
            tree.load_playlists(playlists)
            await pilot.pause()

            await pilot.click(PlaylistTree, offset=(2, 0), button=3)
            await pilot.pause()

            assert app.menus[-1].path is None
            assert tree.menu_playlist_name == ""

    async def test_collapse_all_leaves_only_root_expanded(self, playlists: dict[str, list[Path]]) -> None:
        app = _HostApp()
        async with app.run_test(size=(70, 30)) as pilot:
            tree = app.query_one(PlaylistTree)
            tree.load_playlists(playlists)
            await pilot.pause()
            before = tree.last_line
            assert before > 2, "Baum war nicht aufgeklappt - Test wertlos"

            tree.collapse_all()
            await pilot.pause()

            assert tree.root.is_expanded
            assert all(not child.is_expanded for child in tree.root.children)
            assert tree.last_line < before

    async def test_set_menu_node_expanded_on_playlist_node(self, playlists: dict[str, list[Path]]) -> None:
        app = _HostApp()
        async with app.run_test(size=(70, 30)) as pilot:
            tree = app.query_one(PlaylistTree)
            tree.load_playlists(playlists)
            await pilot.pause()
            line = _line_of(tree, lambda n: n.data == "Abends")
            node = tree.get_node_at_line(line)
            assert node is not None

            await pilot.click(PlaylistTree, offset=(8, line), button=3)
            await pilot.pause()

            tree.set_menu_node_expanded(False)
            await pilot.pause()
            assert not node.is_expanded

            tree.set_menu_node_expanded(True)
            await pilot.pause()
            assert node.is_expanded
