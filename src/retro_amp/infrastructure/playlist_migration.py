"""Einmalige Migration der Markdown-Playlists nach SQLite.

Wird beim App-Start aufgerufen, wenn der alte ``playlists/``-Ordner mit
``*.md``-Dateien existiert. Nach erfolgreichem Import werden die MD-Dateien
und der Ordner geloescht, damit die Migration nicht erneut laeuft.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .playlist_store import MarkdownPlaylistStore
from .sqlite_playlist_repository import SqlitePlaylistRepository

logger = logging.getLogger(__name__)


def migrate_markdown_playlists(
    md_dir: Path,
    target_repo: SqlitePlaylistRepository,
) -> int:
    """Importiert alle Markdown-Playlists in die SQLite-DB.

    Fehlt der Ordner, passiert nichts. Nach erfolgreicher Migration werden
    MD-Dateien und Ordner geloescht. Gibt die Anzahl migrierter Playlists
    zurueck (0 wenn nichts zu tun).
    """
    if not md_dir.is_dir():
        return 0

    md_store = MarkdownPlaylistStore(md_dir)
    names = md_store.list_all()
    if not names:
        _cleanup_dir(md_dir)
        return 0

    migrated = 0
    for name in names:
        playlist = md_store.load(name)
        # file_path aus MD-Store leeren — SQLite braucht's nicht
        playlist.file_path = None
        try:
            target_repo.save(playlist)
            migrated += 1
        except Exception:
            logger.exception("Migration fehlgeschlagen fuer Playlist: %s", name)
            return migrated  # Ordner NICHT loeschen, Retry beim naechsten Start

    # Alle erfolgreich → MD-Dateien loeschen
    for name in names:
        md_file = md_dir / f"{name}.md"
        try:
            md_file.unlink(missing_ok=True)
        except Exception:
            logger.debug("Konnte MD-Datei nicht loeschen: %s", md_file)
    _cleanup_dir(md_dir)
    logger.info("Playlist-Migration: %d Playlists nach SQLite uebertragen", migrated)
    return migrated


def _cleanup_dir(md_dir: Path) -> None:
    """Entfernt den Playlist-Ordner wenn er leer ist."""
    try:
        if md_dir.is_dir() and not any(md_dir.iterdir()):
            md_dir.rmdir()
    except Exception:
        logger.debug("Playlist-Ordner konnte nicht entfernt werden: %s", md_dir)
