"""Folder-Browser Widget — Verzeichnisbaum links."""

from __future__ import annotations

from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual.widgets import DirectoryTree
from textual.widgets._directory_tree import DirEntry
from textual.widgets._tree import TreeNode

from ..domain.models import AudioFormat


class FolderBrowser(DirectoryTree):
    """Verzeichnisbaum der nur Ordner und Audio-Dateien zeigt."""

    DEFAULT_CSS = """
    FolderBrowser {
        width: 100%;
        height: 100%;
    }
    """

    _AUDIO_EXTENSIONS = AudioFormat.supported_extensions()

    ICON_MUSIC = "\u266a "  # ♪

    # Optional uebersteuerter Root-Label-Text (z.B. fuer Sidebar-Schnellzugriffe).
    # None = Standardverhalten (Verzeichnisname).
    _root_label_override: str | None = None

    def set_root_label(self, label: str | None) -> None:
        """Setzt einen festen Root-Label-Text (z.B. "🏠 Home").

        Wird auch bei nachfolgenden internen Reloads (``DirectoryTree._reload``
        ruft ``reset_node`` auf) wieder angewendet — ohne diesen Override
        wuerde der Root-Label nach jedem Reload auf ``path.name`` zurueckfallen.
        ``None`` schaltet den Override ab.
        """
        self._root_label_override = label
        if label is not None:
            self.root.set_label(label)

    def reload_dir(self, directory: Path) -> None:
        """Laedt den Knoten eines bestimmten Ordners neu (Dateinamen aktualisieren).

        Haelt die restliche Baum-Position und Expansion, statt wie ``reload()``
        den ganzen Baum zu kollabieren. Faellt auf einen vollen Reload zurueck,
        wenn der Ordner-Knoten (noch) nicht geladen ist.
        """
        node = self._find_dir_node(directory, self.root)
        if node is not None:
            self.reload_node(node)
        else:
            self.reload()

    def _find_dir_node(
        self,
        directory: Path,
        node: TreeNode[DirEntry],
    ) -> TreeNode[DirEntry] | None:
        """Sucht rekursiv den geladenen Baum-Knoten zu einem Ordnerpfad."""
        data = node.data
        if data is not None and data.path == directory:
            return node
        for child in node.children:
            found = self._find_dir_node(directory, child)
            if found is not None:
                return found
        return None

    def reset_node(  # type: ignore[override]
        self,
        node: TreeNode[DirEntry],
        label: object,
        data: DirEntry | None = None,
    ) -> FolderBrowser:
        """``DirectoryTree``-Hook: setzt unsere Root-Label-Override durch."""
        if node is self.root and self._root_label_override is not None:
            label = self._root_label_override
        return super().reset_node(node, label, data)  # type: ignore[return-value]

    def filter_paths(self, paths: list[Path]) -> list[Path]:  # type: ignore[override]
        """Filtert: nur Ordner und Audio-Dateien anzeigen."""
        result: list[Path] = []
        for path in sorted(paths, key=lambda p: (not p.is_dir(), p.name.lower())):
            if path.is_dir():
                if not path.name.startswith("."):
                    result.append(path)
            elif path.suffix.lower() in self._AUDIO_EXTENSIONS:
                result.append(path)
        return result

    def render_label(
        self,
        node: TreeNode[DirEntry],
        base_style: Style,
        style: Style,
    ) -> Text:
        """Musiknoten-Icon fuer Audio-Dateien statt Standard-Dokument-Icon."""
        node_data = node.data
        if node_data and not node._allow_expand and node_data.path.suffix.lower() in self._AUDIO_EXTENSIONS:
            node_label = node._label.copy()
            node_label.stylize(style)
            if self.is_mounted:
                node_label.stylize_before(
                    self.get_component_rich_style(
                        "directory-tree--file",
                        partial=True,
                    )
                )
                node_label.highlight_regex(
                    r"\..+$",
                    self.get_component_rich_style(
                        "directory-tree--extension",
                        partial=True,
                    ),
                )
            prefix = (self.ICON_MUSIC, base_style)
            return Text.assemble(prefix, node_label)
        return super().render_label(node, base_style, style)

    async def expand_to_path(self, target: Path) -> None:
        """Klappt den Baum schrittweise bis zum Zielverzeichnis auf.

        Expandiert jede Ebene und wartet auf das Laden der Kinder,
        bevor die naechste Ebene geoeffnet wird.
        """
        try:
            rel = target.relative_to(Path(self.path))
        except ValueError:
            return

        parts = rel.parts
        if not parts:
            return

        current_node = self.root
        for part in parts:
            # Knoten expandieren und Kinder laden lassen
            if not current_node.is_expanded:
                current_node.expand()
            if current_node.data and not current_node.data.loaded:
                await self._add_to_load_queue(current_node)

            # Passenden Kind-Knoten finden
            found = None
            for child in current_node.children:
                if child.data and child.data.path.name == part:
                    found = child
                    break

            if found is None:
                break
            current_node = found

        # Letzten gefundenen Knoten expandieren (Zielverzeichnis)
        if current_node != self.root and current_node._allow_expand and not current_node.is_expanded:
            current_node.expand()

        self.move_cursor(current_node)
        self.scroll_to_node(current_node)

    def highlight_path(self, target: Path) -> None:
        """Markiert einen Pfad im Baum und scrollt dorthin.

        Verwendet move_cursor statt select_node, damit kein
        FileSelected-Event ausgeloest wird (verhindert Endlos-Schleife).
        """
        target_str = str(target)

        def _walk(node: TreeNode[DirEntry]) -> TreeNode[DirEntry] | None:
            if node.data and str(node.data.path) == target_str:
                return node
            for child in node.children:
                found = _walk(child)
                if found:
                    return found
            return None

        found = _walk(self.root)
        if found:
            # Nur Cursor bewegen — NICHT select_node (wuerde FileSelected feuern)
            self.move_cursor(found)
            self.scroll_to_node(found)
