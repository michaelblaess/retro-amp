"""Tests fuer Rechtsklick-Kontextmenues in Favoriten-, Verlaufs- und Such-Baum."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.widgets._tree import TreeNode

from retro_amp.domain.models import HistoryEntry
from retro_amp.services.history_service import GROUP_TODAY, HistoryGroup
from retro_amp.widgets.favorites_tree import FavoritesTree
from retro_amp.widgets.history_tree import HistoryTree
from retro_amp.widgets.path_context_tree import PathContextTree
from retro_amp.widgets.search_tree import SearchTree

# Die drei konkreten Baeume - PathContextTree selbst verlangt ein label-Argument
_TreeType = type[FavoritesTree] | type[HistoryTree] | type[SearchTree]


class _HostApp(App[None]):
    """Minimal-App mit genau EINEM Baum und Mitschnitt der Messages.

    Nur ein Baum, weil drei gestapelte Baeume sich die Hoehe teilen und
    ``pilot.click`` dann auf unsichtbare Zeilen zielt (OutOfBounds).
    """

    def __init__(
        self,
        widget_type: _TreeType = FavoritesTree,
    ) -> None:
        super().__init__()
        self._widget_type = widget_type
        self.menus: list[tuple[str, PathContextTree.ContextMenuRequested]] = []
        self.selected: list[Path] = []

    def compose(self) -> ComposeResult:
        yield self._widget_type(id="tree")

    # Getrennte Handler pro Baum - beweist, dass jede Unterklasse einen
    # eigenen Handler-Namen bekommt und nicht alle im selben landen.
    def on_favorites_tree_context_menu_requested(
        self,
        event: FavoritesTree.ContextMenuRequested,
    ) -> None:
        self.menus.append(("favorites", event))

    def on_history_tree_context_menu_requested(
        self,
        event: HistoryTree.ContextMenuRequested,
    ) -> None:
        self.menus.append(("history", event))

    def on_search_tree_context_menu_requested(
        self,
        event: SearchTree.ContextMenuRequested,
    ) -> None:
        self.menus.append(("search", event))

    def on_favorites_tree_track_selected(self, event: FavoritesTree.TrackSelected) -> None:
        self.selected.append(event.path)

    def on_history_tree_track_selected(self, event: HistoryTree.TrackSelected) -> None:
        self.selected.append(event.path)

    def on_search_tree_track_selected(self, event: SearchTree.TrackSelected) -> None:
        self.selected.append(event.path)


@pytest.fixture
def tracks(tmp_path: Path) -> list[Path]:
    """Zwei Dateien in einem Album-Ordner unter der Wurzel."""
    album = tmp_path / "artist" / "album"
    album.mkdir(parents=True)
    paths = [album / "01-song.mp3", album / "02-song.mp3"]
    for path in paths:
        path.write_bytes(b"")
    return paths


def _line_of(tree: PathContextTree, predicate: Callable[[TreeNode[Path | None]], bool]) -> int:
    """Findet die Zeile des ersten Knotens, auf den predicate passt."""
    for index in range(tree.last_line + 1):
        node = tree.get_node_at_line(index)
        if node is not None and predicate(node):
            return index
    raise AssertionError("kein passender Knoten im Baum")


def _leaf_line(tree: PathContextTree, name: str) -> int:
    return _line_of(tree, lambda n: isinstance(n.data, Path) and n.data.name == name)


def _group_line(tree: PathContextTree) -> int:
    """Erster Gruppenknoten (Daten None, aufklappbar, nicht die Wurzel)."""
    return _line_of(tree, lambda n: n.data is None and n.allow_expand and not n.is_root)


async def _fill(app: _HostApp, tmp_path: Path, tracks: list[Path], pilot: object) -> None:
    """Befuellt den gemounteten Baum mit denselben Tracks."""
    tree = app.query_one(PathContextTree)
    if isinstance(tree, FavoritesTree):
        tree.load_favorites(tracks, tmp_path)
    elif isinstance(tree, HistoryTree):
        tree.load_groups(
            [
                HistoryGroup(
                    group_key=GROUP_TODAY,
                    entries=[HistoryEntry(path=p, played_at=datetime(2026, 7, 30, 12, 0)) for p in tracks],
                )
            ],
            enabled=True,
        )
    elif isinstance(tree, SearchTree):
        tree.load_results(
            "song",
            [(p, False) for p in tracks] + [(tracks[0].parent, True)],
            tmp_path,
        )
    await pilot.pause()  # type: ignore[attr-defined]


_TREES = [
    ("favorites", FavoritesTree),
    ("history", HistoryTree),
    ("search", SearchTree),
]


class TestRightClick:
    @pytest.mark.parametrize(("kind", "widget_type"), _TREES)
    async def test_right_click_on_leaf_posts_own_message_and_does_not_select(
        self,
        kind: str,
        widget_type: _TreeType,
        tmp_path: Path,
        tracks: list[Path],
    ) -> None:
        app = _HostApp(widget_type)
        async with app.run_test(size=(70, 40)) as pilot:
            await _fill(app, tmp_path, tracks, pilot)
            tree = app.query_one(widget_type)
            line = _leaf_line(tree, "01-song.mp3")

            await pilot.click(widget_type, offset=(6, line), button=3)
            await pilot.pause()

            assert len(app.menus) == 1
            sender, event = app.menus[0]
            assert sender == kind
            assert event.path == tracks[0]
            # Entscheidend: der Rechtsklick darf keine Wiedergabe ausloesen
            assert app.selected == []

    @pytest.mark.parametrize(("kind", "widget_type"), _TREES)
    async def test_right_click_on_group_reports_no_path(
        self,
        kind: str,
        widget_type: _TreeType,
        tmp_path: Path,
        tracks: list[Path],
    ) -> None:
        app = _HostApp(widget_type)
        async with app.run_test(size=(70, 40)) as pilot:
            await _fill(app, tmp_path, tracks, pilot)
            tree = app.query_one(widget_type)
            line = _group_line(tree)

            await pilot.click(widget_type, offset=(6, line), button=3)
            await pilot.pause()

            sender, event = app.menus[-1]
            assert sender == kind
            assert event.path is None
            assert event.is_expanded is True

    @pytest.mark.parametrize(("kind", "widget_type"), _TREES)
    async def test_left_click_still_selects_exactly_once(
        self,
        kind: str,
        widget_type: _TreeType,
        tmp_path: Path,
        tracks: list[Path],
    ) -> None:
        app = _HostApp(widget_type)
        async with app.run_test(size=(70, 40)) as pilot:
            await _fill(app, tmp_path, tracks, pilot)
            tree = app.query_one(widget_type)
            line = _leaf_line(tree, "02-song.mp3")

            await pilot.click(widget_type, offset=(6, line))
            await pilot.pause()

            assert app.selected == [tracks[1]]
            assert app.menus == []

    async def test_right_click_moves_cursor(self, tmp_path: Path, tracks: list[Path]) -> None:
        app = _HostApp()
        async with app.run_test(size=(70, 40)) as pilot:
            await _fill(app, tmp_path, tracks, pilot)
            tree = app.query_one(FavoritesTree)
            line = _leaf_line(tree, "02-song.mp3")

            await pilot.click(FavoritesTree, offset=(6, line), button=3)
            await pilot.pause()

            assert tree.cursor_line == line
            assert tree.cursor_node is not None
            assert tree.cursor_node.data == tracks[1]


class TestCollapse:
    @pytest.mark.parametrize(("kind", "widget_type"), _TREES)
    async def test_collapse_all_leaves_only_root_expanded(
        self,
        kind: str,
        widget_type: _TreeType,
        tmp_path: Path,
        tracks: list[Path],
    ) -> None:
        app = _HostApp(widget_type)
        async with app.run_test(size=(70, 40)) as pilot:
            await _fill(app, tmp_path, tracks, pilot)
            tree = app.query_one(widget_type)
            before = tree.last_line
            assert before > 1, "Baum war nicht aufgeklappt - Test wertlos"

            tree.collapse_all()
            await pilot.pause()

            assert tree.root.is_expanded
            assert all(not child.is_expanded for child in tree.root.children)
            assert tree.last_line < before
            assert tree.cursor_line == 0

    async def test_set_menu_node_expanded_uses_last_clicked_node(
        self,
        tmp_path: Path,
        tracks: list[Path],
    ) -> None:
        app = _HostApp()
        async with app.run_test(size=(70, 40)) as pilot:
            await _fill(app, tmp_path, tracks, pilot)
            tree = app.query_one(FavoritesTree)
            line = _group_line(tree)
            group = tree.get_node_at_line(line)
            assert group is not None

            await pilot.click(FavoritesTree, offset=(6, line), button=3)
            await pilot.pause()

            tree.set_menu_node_expanded(False)
            await pilot.pause()
            assert not group.is_expanded

            tree.set_menu_node_expanded(True)
            await pilot.pause()
            assert group.is_expanded

    async def test_set_menu_node_expanded_ignores_leaf(
        self,
        tmp_path: Path,
        tracks: list[Path],
    ) -> None:
        app = _HostApp()
        async with app.run_test(size=(70, 40)) as pilot:
            await _fill(app, tmp_path, tracks, pilot)
            tree = app.query_one(FavoritesTree)
            line = _leaf_line(tree, "01-song.mp3")
            leaf = tree.get_node_at_line(line)
            assert leaf is not None

            await pilot.click(FavoritesTree, offset=(6, line), button=3)
            await pilot.pause()

            # Darf nicht werfen und nichts veraendern
            tree.set_menu_node_expanded(True)
            await pilot.pause()
            assert not leaf.is_expanded

    async def test_set_menu_node_expanded_without_click_is_noop(self) -> None:
        app = _HostApp(HistoryTree)
        async with app.run_test(size=(70, 40)) as pilot:
            tree = app.query_one(HistoryTree)
            tree.set_menu_node_expanded(True)
            await pilot.pause()


class TestSearchFolderHits:
    async def test_folder_hit_reports_directory_path(self, tmp_path: Path, tracks: list[Path]) -> None:
        app = _HostApp(SearchTree)
        async with app.run_test(size=(70, 40)) as pilot:
            await _fill(app, tmp_path, tracks, pilot)
            tree = app.query_one(SearchTree)
            line = _leaf_line(tree, "album")

            await pilot.click(SearchTree, offset=(6, line), button=3)
            await pilot.pause()

            _, event = app.menus[-1]
            assert event.path == tracks[0].parent
            assert event.path is not None
            assert event.path.is_dir()
