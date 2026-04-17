"""Wiedergabeverlauf-Persistenz in SQLite."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from ..domain.models import HistoryEntry


class SqliteHistoryRepository:
    """HistoryRepository-Implementation auf Basis einer sqlite3-Connection.

    Implementiert das HistoryRepository-Protocol aus domain/protocols.py.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, path: Path) -> None:
        """Speichert einen Play-Eintrag mit aktuellem Zeitstempel."""
        self._conn.execute(
            "INSERT INTO history (path, played_at) VALUES (?, ?)",
            (str(path), datetime.now().isoformat(timespec="seconds")),
        )
        self._conn.commit()

    def list_recent(self, limit: int = 1000) -> list[HistoryEntry]:
        """Liefert die letzten Eintraege (neuster zuerst)."""
        rows = self._conn.execute(
            """
            SELECT path, played_at FROM history
            ORDER BY played_at DESC, id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        result: list[HistoryEntry] = []
        for row in rows:
            try:
                played = datetime.fromisoformat(row["played_at"])
            except (ValueError, TypeError):
                continue
            result.append(HistoryEntry(path=Path(row["path"]), played_at=played))
        return result

    def clear(self) -> None:
        """Loescht den gesamten Verlauf."""
        self._conn.execute("DELETE FROM history")
        self._conn.commit()

    def trim(self, max_entries: int) -> None:
        """Behaelt nur die letzten ``max_entries`` Eintraege (nach played_at)."""
        if max_entries < 0:
            return
        self._conn.execute(
            """
            DELETE FROM history
            WHERE id NOT IN (
                SELECT id FROM history
                ORDER BY played_at DESC, id DESC
                LIMIT ?
            )
            """,
            (int(max_entries),),
        )
        self._conn.commit()
