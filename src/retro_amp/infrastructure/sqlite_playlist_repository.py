"""Playlist-Persistenz in SQLite (ersetzt MarkdownPlaylistStore).

Favoriten sind eine besondere Playlist mit festem Namen ``Favoriten``.
Die Struktur erlaubt, Favoriten spaeter wie andere Playlists zu
reordnen/umbenennen, ohne die Datenhaltung zu aendern.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..domain.models import Playlist, PlaylistEntry
from .database import audit_now


class SqlitePlaylistRepository:
    """PlaylistRepository-Implementation auf Basis einer sqlite3-Connection.

    Implementiert das PlaylistRepository-Protocol aus domain/protocols.py.
    Nicht-existierende Playlists werden als leere Playlist zurueckgegeben
    (identisch zum bisherigen Markdown-Verhalten).
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def load(self, name: str) -> Playlist:
        """Laedt eine Playlist nach Name. Leere Playlist wenn nicht vorhanden."""
        playlist = Playlist(name=name)
        row = self._conn.execute("SELECT id FROM playlists WHERE name = ?", (name,)).fetchone()
        if row is None:
            return playlist
        entries = self._conn.execute(
            """
            SELECT path FROM playlist_entries
            WHERE playlist_id = ?
            ORDER BY position
            """,
            (row["id"],),
        ).fetchall()
        for entry in entries:
            playlist.entries.append(PlaylistEntry(path=Path(entry["path"])))
        return playlist

    def save(self, playlist: Playlist) -> None:
        """Speichert eine Playlist (Upsert + Entries neu aufbauen)."""
        conn = self._conn
        now = audit_now()
        try:
            conn.execute("BEGIN")
            row = conn.execute("SELECT id FROM playlists WHERE name = ?", (playlist.name,)).fetchone()
            if row is None:
                cursor = conn.execute(
                    "INSERT INTO playlists (name, created_at) VALUES (?, ?)",
                    (playlist.name, now),
                )
                playlist_id = cursor.lastrowid
            else:
                playlist_id = row["id"]
                conn.execute(
                    "UPDATE playlists SET changed_at = ? WHERE id = ?",
                    (now, playlist_id),
                )
            conn.execute(
                "DELETE FROM playlist_entries WHERE playlist_id = ?",
                (playlist_id,),
            )
            for position, entry in enumerate(playlist.entries):
                conn.execute(
                    """
                    INSERT INTO playlist_entries (playlist_id, position, path)
                    VALUES (?, ?, ?)
                    """,
                    (playlist_id, position, str(entry.path)),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def list_all(self) -> list[str]:
        """Gibt alle Playlist-Namen alphabetisch sortiert zurueck."""
        rows = self._conn.execute("SELECT name FROM playlists ORDER BY name COLLATE NOCASE").fetchall()
        return [row["name"] for row in rows]

    def delete(self, name: str) -> None:
        """Loescht eine Playlist (Entries werden per CASCADE mitgeloescht)."""
        self._conn.execute("DELETE FROM playlists WHERE name = ?", (name,))
        self._conn.commit()
