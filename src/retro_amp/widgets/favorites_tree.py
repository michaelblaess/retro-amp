"""Favorites-Tree Widget — Baum mit Favoriten-Tracks."""
from __future__ import annotations

from pathlib import Path

from textual.binding import Binding
from textual.message import Message
from textual.widgets import Tree

from ..i18n import t


class FavoritesTree(Tree[Path | None]):
    """Baum-Ansicht fuer Favoriten, gruppiert nach Ordner."""

    DEFAULT_CSS = """
    FavoritesTree {
        width: 100%;
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("delete", "remove_favorite", "DEL", key_display="DEL"),
    ]

    ICON_MUSIC = "\u266a "
    ICON_FOLDER = "\U0001f4c1 "

    class TrackSelected(Message):
        """Track im Favoriten-Baum ausgewaehlt."""
        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    class TrackRemoveRequested(Message):
        """Track soll aus Favoriten entfernt werden."""
        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def __init__(self, **kwargs: object) -> None:
        super().__init__(t("favorites.title"), **kwargs)
        self._music_root: Path | None = None

    def load_favorites(
        self, paths: list[Path], music_root: Path | None = None,
    ) -> None:
        """Laedt Favoriten-Eintraege in den Baum."""
        self._music_root = music_root
        self.clear()

        count = len(paths)
        self.root.set_label(
            t("favorites.title_count", count=count) if count else t("favorites.title")
        )

        if not paths:
            self.root.add_leaf(t("favorites.empty"), data=None)
            self.root.expand()
            return

        # Nach Ordner gruppieren
        groups: dict[str, list[Path]] = {}
        for path in paths:
            parent = path.parent
            if music_root:
                try:
                    rel_parent = str(parent.relative_to(music_root))
                except ValueError:
                    rel_parent = str(parent)
            else:
                rel_parent = str(parent)
            if rel_parent not in groups:
                groups[rel_parent] = []
            groups[rel_parent].append(path)

        # Baum aufbauen
        for folder_name in sorted(groups.keys()):
            tracks = groups[folder_name]
            folder_node = self.root.add(
                f"{self.ICON_FOLDER}{folder_name}",
                data=None,
            )
            for track in sorted(tracks, key=lambda p: p.name.lower()):
                folder_node.add_leaf(
                    f"{self.ICON_MUSIC}{track.name}", data=track,
                )
            folder_node.expand()

        self.root.expand()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Track-Node ausgewaehlt — abspielen."""
        if event.node.data and isinstance(event.node.data, Path):
            self.post_message(self.TrackSelected(event.node.data))

    def action_remove_favorite(self) -> None:
        """Ausgewaehlten Track aus Favoriten entfernen."""
        node = self.cursor_node
        if node and node.data and isinstance(node.data, Path):
            self.post_message(self.TrackRemoveRequested(node.data))
