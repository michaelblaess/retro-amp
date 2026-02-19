"""Folder-Browser Widget — Verzeichnisbaum links."""
from __future__ import annotations

from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual.widgets import DirectoryTree
from textual.widgets._directory_tree import DirEntry
from textual.widgets._tree import TreeNode


class FolderBrowser(DirectoryTree):
    """Verzeichnisbaum der nur Ordner und Audio-Dateien zeigt."""

    DEFAULT_CSS = """
    FolderBrowser {
        width: 100%;
        height: 100%;
    }
    """

    _AUDIO_EXTENSIONS = {
        ".mp3", ".ogg", ".oga", ".opus", ".flac", ".wav",
        ".mod", ".xm", ".s3m", ".sid",
    }

    ICON_MUSIC = "\u266a "  # ♪

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
        self, node: TreeNode[DirEntry], base_style: Style, style: Style,
    ) -> Text:
        """Musiknoten-Icon fuer Audio-Dateien statt Standard-Dokument-Icon."""
        node_data = node.data
        if (
            node_data
            and not node._allow_expand
            and node_data.path.suffix.lower() in self._AUDIO_EXTENSIONS
        ):
            node_label = node._label.copy()
            node_label.stylize(style)
            if self.is_mounted:
                node_label.stylize_before(
                    self.get_component_rich_style(
                        "directory-tree--file", partial=True,
                    )
                )
                node_label.highlight_regex(
                    r"\..+$",
                    self.get_component_rich_style(
                        "directory-tree--extension", partial=True,
                    ),
                )
            prefix = (self.ICON_MUSIC, base_style)
            return Text.assemble(prefix, node_label)
        return super().render_label(node, base_style, style)

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
