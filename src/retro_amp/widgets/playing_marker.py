"""Kennzeichnung des laufenden Titels in den Listen-Baeumen."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.text import Text

if TYPE_CHECKING:
    from textual.widgets._tree import TreeNode


class PlayingMarkerMixin:
    """Zeigt am laufenden Titel ein ``▶`` statt der Note.

    Fuer Baeume, deren Blaetter einen ``Path`` tragen und ``♪ dateiname``
    heissen (Favoriten, Playlists). Der Cursor allein reicht dafuer nicht: er
    wandert weg, sobald der Benutzer durch den Baum blaettert.
    """

    ICON_MUSIC = "♪ "
    ICON_PLAYING = "▶ "

    _playing_path: Path | None = None

    if TYPE_CHECKING:
        root: TreeNode[Any]

    def track_label(self, path: Path) -> str | Text:
        """Beschriftung eines Titel-Blatts, mit ``▶`` wenn er gerade laeuft."""
        if path == self._playing_path:
            return Text(f"{self.ICON_PLAYING}{path.name}", style="bold")
        return f"{self.ICON_MUSIC}{path.name}"

    def track_leaves(self) -> list[tuple[TreeNode[Any], Path]]:
        """Alle Titel-Blaetter mit ihrem Pfad, von oben nach unten."""
        found: list[tuple[TreeNode[Any], Path]] = []
        for group in self.root.children:
            for leaf in group.children:
                if isinstance(leaf.data, Path):
                    found.append((leaf, leaf.data))
        return found

    def mark_playing(self, path: Path | None) -> None:
        """Setzt das ``▶`` auf den laufenden Titel und nimmt es vom vorigen."""
        previous = self._playing_path
        if path == previous:
            return
        self._playing_path = path
        for leaf, leaf_path in self.track_leaves():
            if leaf_path in (previous, path):
                leaf.set_label(self.track_label(leaf_path))
