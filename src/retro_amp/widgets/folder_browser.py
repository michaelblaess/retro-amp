"""Folder-Browser Widget — Verzeichnisbaum links."""
from __future__ import annotations

from pathlib import Path

from textual.message import Message
from textual.widgets import DirectoryTree


class FolderBrowser(DirectoryTree):
    """Verzeichnisbaum der nur Ordner und Audio-Dateien zeigt."""

    DEFAULT_CSS = """
    FolderBrowser {
        width: 100%;
        height: 100%;
    }
    """

    _AUDIO_EXTENSIONS = {
        ".mp3", ".ogg", ".oga", ".flac", ".wav",
        ".mod", ".xm", ".s3m", ".sid",
    }

    class DirectorySelected(Message):
        """Wird gesendet wenn ein Verzeichnis ausgewaehlt wird."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def filter_paths(self, paths: list[Path]) -> list[Path]:  # type: ignore[override]
        """Filtert: nur Ordner und Audio-Dateien anzeigen."""
        result: list[Path] = []
        for path in sorted(paths, key=lambda p: (not p.is_dir(), p.name.lower())):
            if path.is_dir():
                # Versteckte Ordner ausblenden
                if not path.name.startswith("."):
                    result.append(path)
            elif path.suffix.lower() in self._AUDIO_EXTENSIONS:
                result.append(path)
        return result

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        """Leitet Directory-Selection als eigene Message weiter."""
        self.post_message(FolderBrowser.DirectorySelected(event.path))
