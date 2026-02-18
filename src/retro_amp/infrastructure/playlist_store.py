"""Playlist-Persistenz als Markdown-Dateien."""
from __future__ import annotations

import logging
from pathlib import Path

from ..domain.models import Playlist, PlaylistEntry

logger = logging.getLogger(__name__)

_PLAYLISTS_DIR = Path.home() / ".retro-amp" / "playlists"


class MarkdownPlaylistStore:
    """PlaylistRepository-Implementation mit Markdown-Dateien.

    Implementiert das PlaylistRepository-Protocol aus domain/protocols.py.

    Format:
        # Playlistname
        - /pfad/zur/datei.mp3
        - /pfad/zur/datei2.ogg
    """

    def __init__(self, playlists_dir: Path | None = None) -> None:
        self._dir = playlists_dir or _PLAYLISTS_DIR

    def load(self, name: str) -> Playlist:
        """Laedt eine Playlist nach Name."""
        file_path = self._dir / f"{name}.md"
        playlist = Playlist(name=name, file_path=file_path)

        if not file_path.is_file():
            return playlist

        try:
            content = file_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("- "):
                    path_str = line[2:].strip()
                    if path_str:
                        playlist.entries.append(
                            PlaylistEntry(path=Path(path_str))
                        )
        except Exception:
            logger.debug("Playlist konnte nicht geladen werden: %s", name)

        return playlist

    def save(self, playlist: Playlist) -> None:
        """Speichert eine Playlist als Markdown."""
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            file_path = self._dir / f"{playlist.name}.md"
            lines = [f"# {playlist.name}", ""]
            for entry in playlist.entries:
                lines.append(f"- {entry.path}")
            lines.append("")  # Trailing newline

            file_path.write_text("\n".join(lines), encoding="utf-8")
            playlist.file_path = file_path
        except Exception:
            logger.debug("Playlist konnte nicht gespeichert werden: %s", playlist.name)

    def list_all(self) -> list[str]:
        """Gibt alle Playlist-Namen zurueck."""
        if not self._dir.is_dir():
            return []
        try:
            return [
                f.stem
                for f in sorted(self._dir.glob("*.md"))
                if f.is_file()
            ]
        except Exception:
            return []

    def delete(self, name: str) -> None:
        """Loescht eine Playlist."""
        file_path = self._dir / f"{name}.md"
        try:
            if file_path.is_file():
                file_path.unlink()
        except Exception:
            logger.debug("Playlist konnte nicht geloescht werden: %s", name)
