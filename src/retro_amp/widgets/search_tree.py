"""Search-Tree Widget — Suchergebnisse als Baum, gruppiert nach Verzeichnis."""
from __future__ import annotations

import re
from pathlib import Path

from rich.text import Text

from textual.message import Message
from textual.widgets import Tree

from ..i18n import t


_SEPARATOR_RE = re.compile(r"[.\-_]")


def _normalize(s: str) -> str:
    """Trennzeichen durch Leerzeichen ersetzen — flexible Suche."""
    return _SEPARATOR_RE.sub(" ", s)


class SearchTree(Tree[Path | None]):
    """Baum-Ansicht fuer Suchergebnisse.

    Gruppiert die Treffer nach uebergeordnetem Verzeichnis (relativ zur
    Library-Wurzel) — dadurch erscheinen mehrere Treffer im selben Album-
    Ordner unter einem gemeinsamen Knoten und werden nicht als 30 fast
    identische Pfade aufgelistet.
    """

    DEFAULT_CSS = """
    SearchTree {
        width: 100%;
        height: 100%;
    }
    """

    ICON_FOLDER = "\U0001f4c1 "  # 📁
    ICON_MUSIC = "♪ "         # ♪

    class TrackSelected(Message):
        """Track-Treffer im Suchbaum ausgewaehlt."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    class FolderSelected(Message):
        """Ordner-Treffer im Suchbaum ausgewaehlt — soll geoeffnet werden."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def __init__(self, **kwargs: object) -> None:
        super().__init__(t("search.title"), **kwargs)

    def show_loading(self, query: str) -> None:
        """Zeigt einen Lade-Hinweis im leeren Baum."""
        self.clear()
        self.root.set_label(t("search.loading", query=query))
        self.root.expand()

    def load_results(
        self,
        query: str,
        results: list[tuple[Path, bool]],
        root: Path,
    ) -> None:
        """Befuellt den Baum mit den Suchergebnissen.

        Args:
            query: Suchbegriff (fuer Highlighting im Treffer-Label).
            results: Liste von ``(path, is_dir)``-Tuples.
            root: Library-Wurzel — fuer die Berechnung relativer Pfade.
        """
        self.clear()

        if not results:
            self.root.set_label(t("search.no_results", query=query))
            self.root.expand()
            return

        self.root.set_label(t("search.results", query=query, count=len(results)))

        # Nach uebergeordnetem (relativem) Verzeichnis gruppieren
        by_parent: dict[Path, list[tuple[Path, bool]]] = {}
        for path, is_dir in results:
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            parent = rel.parent
            by_parent.setdefault(parent, []).append((path, is_dir))

        accent = self.app.get_css_variables().get("accent", "yellow")

        for parent, items in sorted(by_parent.items(), key=lambda x: str(x[0])):
            parent_label = (
                str(parent) if str(parent) not in (".", "")
                else t("search.root_label")
            )
            group_label = f"{self.ICON_FOLDER}{parent_label}  ({len(items)})"
            group_node = self.root.add(group_label, data=None)

            for path, is_dir in items:
                if is_dir:
                    leaf_label = Text(f"{self.ICON_FOLDER}{path.name}/")
                    self._highlight(leaf_label, path.name, query, accent, offset=2)
                else:
                    leaf_label = Text(f"{self.ICON_MUSIC}{path.name}")
                    self._highlight(leaf_label, path.name, query, accent, offset=2)
                group_node.add_leaf(leaf_label, data=path)

            group_node.expand()

        self.root.expand()

    @staticmethod
    def _highlight(
        label: Text, name: str, query: str, accent: str, offset: int,
    ) -> None:
        """Markiert Treffer-Stellen im Datei-/Ordnername fett in Akzentfarbe."""
        norm_name = _normalize(name.lower())
        norm_query = _normalize(query.lower())
        if not norm_query:
            return
        start = 0
        while True:
            idx = norm_name.find(norm_query, start)
            if idx < 0:
                break
            label.stylize(f"bold {accent}", offset + idx, offset + idx + len(norm_query))
            start = idx + len(norm_query)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Treffer-Knoten ausgewaehlt — Path-Daten weitergeben."""
        path = event.node.data
        if not isinstance(path, Path):
            return
        if path.is_dir():
            self.post_message(self.FolderSelected(path))
        else:
            self.post_message(self.TrackSelected(path))

    def clear_results(self) -> None:
        """Leert den Baum komplett."""
        self.clear()
        self.root.set_label(t("search.title"))
        self.root.expand()
