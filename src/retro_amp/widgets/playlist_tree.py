"""Playlist-Tree Widget — Baum mit allen Playlists und deren Tracks."""
from __future__ import annotations

from pathlib import Path

from textual.binding import Binding
from textual.message import Message
from textual.widgets import Tree


class PlaylistTree(Tree[Path | str | None]):
    """Baum-Ansicht fuer Playlists, gruppiert nach Playlist-Name."""

    DEFAULT_CSS = """
    PlaylistTree {
        width: 100%;
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("delete", "remove_track", "Entfernen", key_display="DEL"),
    ]

    ICON_MUSIC = "\u266a "
    ICON_PLAYLIST = "\U0001f3b5 "

    class TrackSelected(Message):
        """Track in einer Playlist ausgewaehlt."""
        def __init__(self, path: Path, playlist_name: str) -> None:
            super().__init__()
            self.path = path
            self.playlist_name = playlist_name

    class TrackRemoveRequested(Message):
        """Track soll aus Playlist entfernt werden."""
        def __init__(self, path: Path, playlist_name: str) -> None:
            super().__init__()
            self.path = path
            self.playlist_name = playlist_name

    def __init__(self, **kwargs: object) -> None:
        super().__init__("\U0001f3b6 Playlists", **kwargs)

    def load_playlists(
        self,
        playlists: dict[str, list[Path]],
    ) -> None:
        """Laedt alle Playlists in den Baum.

        Args:
            playlists: Dict mit Playlist-Name → Liste von Track-Pfaden.
        """
        self.clear()

        count = len(playlists)
        self.root.set_label(
            f"\U0001f3b6 Playlists ({count})" if count else "\U0001f3b6 Playlists"
        )

        if not playlists:
            self.root.add_leaf("(keine Playlists)", data=None)
            self.root.expand()
            return

        for name in sorted(playlists.keys()):
            tracks = playlists[name]
            track_count = len(tracks)
            label = f"{self.ICON_PLAYLIST}{name} ({track_count})"
            # Playlist-Name als String-Data speichern
            playlist_node = self.root.add(label, data=name)
            for track in tracks:
                playlist_node.add_leaf(
                    f"{self.ICON_MUSIC}{track.name}", data=track,
                )
            playlist_node.expand()

        self.root.expand()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Track-Node ausgewaehlt — abspielen."""
        node = event.node
        if node.data and isinstance(node.data, Path):
            # Playlist-Name aus Parent-Node holen
            parent = node.parent
            playlist_name = parent.data if parent and isinstance(parent.data, str) else ""
            self.post_message(self.TrackSelected(node.data, playlist_name))

    def action_remove_track(self) -> None:
        """Ausgewaehlten Track aus Playlist entfernen."""
        node = self.cursor_node
        if node and node.data and isinstance(node.data, Path):
            parent = node.parent
            playlist_name = parent.data if parent and isinstance(parent.data, str) else ""
            if playlist_name:
                self.post_message(self.TrackRemoveRequested(node.data, playlist_name))
