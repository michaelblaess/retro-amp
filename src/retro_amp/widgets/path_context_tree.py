"""Basisklasse fuer Path-Baeume mit Rechtsklick-Kontextmenue."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from textual.events import Click
from textual.message import Message
from textual.widgets import Tree
from textual.widgets._tree import TreeNode

TreeDataType = TypeVar("TreeDataType")


class PathContextTree(Tree[TreeDataType]):
    """``Tree`` mit Rechtsklick-Kontextmenue fuer Path-Blaetter.

    Gemeinsame Basis fuer Favoriten-, Verlaufs-, Such- und Playlist-Baum.
    Diese Baeume haben denselben Aufbau: Gruppen-Knoten ohne Pfad und
    Blaetter mit einem ``Path``. Generisch, weil der Playlist-Baum in seinen
    Gruppen-Knoten den Playlist-Namen als ``str`` ablegt.

    Das Widget baut das Menue nicht selbst — es meldet nur, welcher Knoten
    getroffen wurde. Favoriten-Status, Playlists und Bibliothekspfad liegen
    in der App.
    """

    class ContextMenuRequested(Message):
        """Rechtsklick auf einen Knoten.

        ``path`` ist ``None`` bei Gruppen- und Hinweis-Knoten. Unterklassen
        leiten davon eine eigene Klasse ab, damit Textual pro Baum einen
        eigenen Handler-Namen bildet (``handler_name`` kommt aus dem
        ``__qualname__`` der Message-Klasse).
        """

        def __init__(
            self,
            path: Path | None,
            is_expanded: bool,
            at: tuple[int, int],
        ) -> None:
            super().__init__()
            self.path = path
            self.is_expanded = is_expanded
            self.at = at

    def __init__(self, label: str, **kwargs: object) -> None:
        super().__init__(label, **kwargs)
        # Knoten des zuletzt geoeffneten Kontextmenues. Gruppen-Knoten haben
        # keinen Pfad, ueber den die App sie wiederfinden koennte — deshalb
        # bleibt die Knoten-Referenz hier im Widget.
        self._menu_node: TreeNode[TreeDataType] | None = None

    async def _on_click(self, event: Click) -> None:
        """Rechtsklick meldet den getroffenen Knoten statt ihn auszuwaehlen.

        Textuals ``Tree._on_click`` prueft die Maustaste nicht und liefe in
        ``select_cursor`` — ein Rechtsklick wuerde also die Wiedergabe starten.
        Ein Override genuegt dafuer nicht: Textual ruft JEDEN ``_on_click``
        entlang der MRO auf. Erst ``prevent_default()`` bricht die Kette ab,
        und aus demselben Grund darf hier kein ``super()``-Aufruf stehen.
        """
        if event.button != 3:
            return

        event.prevent_default()
        event.stop()
        line = event.style.meta.get("line")
        if line is None:
            return
        node = self.get_node_at_line(line)
        if node is None:
            return

        # Cursor auf den geklickten Knoten setzen — sonst wirkt die gewaehlte
        # Aktion auf einen anderen Knoten als den, auf den gezielt wurde.
        self.move_cursor(node)
        self._menu_node = node
        data = node.data
        self.post_message(
            type(self).ContextMenuRequested(
                path=data if isinstance(data, Path) else None,
                is_expanded=node.is_expanded,
                at=(event.screen_x, event.screen_y),
            )
        )

    def set_menu_node_expanded(self, expanded: bool) -> None:
        """Klappt den zuletzt per Rechtsklick getroffenen Knoten auf oder zu."""
        node = self._menu_node
        if node is None or not node.allow_expand:
            return
        if expanded:
            node.expand()
        else:
            node.collapse()

    def collapse_all(self) -> None:
        """Klappt den gesamten Baum zu — nur die Wurzel bleibt offen."""
        for child in self.root.children:
            child.collapse_all()
        self.root.expand()
        self.move_cursor(self.root)
        self.scroll_to_line(0, animate=False)
