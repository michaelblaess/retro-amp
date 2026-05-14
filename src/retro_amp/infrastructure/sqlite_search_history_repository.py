"""Such-Verlauf-Persistenz in SQLite (Tabelle ``search_history``)."""

from __future__ import annotations

import sqlite3
from datetime import datetime


class SqliteSearchHistoryRepository:
    """SearchHistoryRepository-Implementation auf einer sqlite3-Connection.

    Implementiert das SearchHistoryRepository-Protocol aus
    ``domain/protocols.py``. Identische Suchstrings werden per UPSERT
    dedupliziert — nur ``last_used_at`` und ``use_count`` aktualisieren
    sich.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, query: str) -> None:
        """Speichert eine Suchanfrage (UPSERT)."""
        clean = (query or "").strip()
        if not clean:
            return
        now = datetime.now().isoformat(timespec="seconds")
        self._conn.execute(
            """
            INSERT INTO search_history (query, last_used_at, use_count)
            VALUES (?, ?, 1)
            ON CONFLICT(query) DO UPDATE SET
                last_used_at = excluded.last_used_at,
                use_count = use_count + 1
            """,
            (clean, now),
        )
        self._conn.commit()

    def list_recent(self, limit: int = 20) -> list[str]:
        """Liefert die letzten Suchanfragen (neueste zuerst)."""
        rows = self._conn.execute(
            """
            SELECT query FROM search_history
            ORDER BY last_used_at DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        return [str(row["query"]) for row in rows]

    def delete(self, query: str) -> None:
        """Loescht eine einzelne Suchanfrage."""
        self._conn.execute(
            "DELETE FROM search_history WHERE query = ?",
            (query,),
        )
        self._conn.commit()

    def clear(self) -> None:
        """Loescht den gesamten Such-Verlauf."""
        self._conn.execute("DELETE FROM search_history")
        self._conn.commit()

    def trim(self, max_entries: int) -> None:
        """Behaelt nur die letzten ``max_entries`` Eintraege (nach last_used_at)."""
        if max_entries < 0:
            return
        self._conn.execute(
            """
            DELETE FROM search_history
            WHERE query NOT IN (
                SELECT query FROM search_history
                ORDER BY last_used_at DESC
                LIMIT ?
            )
            """,
            (int(max_entries),),
        )
        self._conn.commit()
