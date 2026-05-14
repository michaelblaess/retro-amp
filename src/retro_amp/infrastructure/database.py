"""SQLite-basierte Datenhaltung fuer retro-amp.

Zentrale Database-Klasse verwaltet die Verbindung, das Schema und die
Key/Value-Settings. Favoriten/Playlists/History leben in eigenen
Repository-Klassen, die die Connection im Konstruktor erhalten.
"""

from __future__ import annotations

import getpass
import sqlite3
from datetime import datetime
from pathlib import Path

_ALLOWED_JOURNAL_MODES: frozenset[str] = frozenset({"DELETE", "WAL", "TRUNCATE", "PERSIST", "MEMORY", "OFF"})
_DEFAULT_JOURNAL_MODE = "DELETE"


def audit_now() -> str:
    """Aktueller Zeitstempel im ISO-Format fuer Audit-Felder."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def audit_user() -> str:
    """Name des aktuellen OS-Users fuer Audit-Felder."""
    try:
        return getpass.getuser()
    except Exception:
        return ""


class Database:
    """Verwaltet die retro-amp SQLite-Datenbank (~/.retro-amp/retro-amp.db).

    Nur die Verbindung, das Schema und die settings-Tabelle leben hier.
    Favoriten/Playlists/History sind in eigene Repository-Klassen
    ausgelagert, die die sqlite3-Connection ueber ``Database.connection``
    beziehen.
    """

    DB_FILENAME = "retro-amp.db"

    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or (Path.home() / ".retro-amp" / "retro-amp.db")
        self._conn: sqlite3.Connection | None = None

    @property
    def path(self) -> Path:
        """Pfad zur Datenbankdatei."""
        return self._path

    @property
    def is_open(self) -> bool:
        """Prueft ob die Datenbank geoeffnet ist."""
        return self._conn is not None

    @property
    def connection(self) -> sqlite3.Connection:
        """Gibt die aktive Verbindung zurueck oder wirft einen Fehler."""
        if self._conn is None:
            raise RuntimeError("Datenbank ist nicht geoeffnet")
        return self._conn

    def open(self) -> None:
        """Oeffnet die Datenbank und erstellt/migriert das Schema."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(self._path), timeout=10.0)
        self._conn.row_factory = sqlite3.Row
        # 10 Sekunden auf Locks warten, bevor "database is locked" kommt.
        # Hilft gegen kurzzeitig offene Reader (DB Browser o.ae.).
        self._conn.execute("PRAGMA busy_timeout=10000")
        self._conn.execute("PRAGMA foreign_keys=ON")
        # Schema muss vor dem Lesen des journal_mode-Settings existieren,
        # sonst gibt es die settings-Tabelle beim Erstkontakt noch nicht.
        self._init_schema()
        self._apply_journal_mode_setting()

    def close(self) -> None:
        """Schliesst die Datenbank."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _init_schema(self) -> None:
        """Erstellt die Datenbanktabellen falls sie noch nicht existieren."""
        conn = self.connection
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TEXT,
                created_by TEXT,
                changed_at TEXT,
                changed_by TEXT
            );

            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                changed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS playlist_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                path TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_entries_playlist
                ON playlist_entries(playlist_id, position);

            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                played_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_history_played_at
                ON history(played_at DESC);

            CREATE TABLE IF NOT EXISTS search_history (
                query TEXT PRIMARY KEY,
                last_used_at TEXT NOT NULL,
                use_count INTEGER NOT NULL DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_search_history_used
                ON search_history(last_used_at DESC);
            """
        )
        conn.commit()

    def _apply_journal_mode_setting(self) -> None:
        """Liest das gewuenschte journal_mode-Setting und setzt es ggf. um.

        Erlaubte Werte: DELETE (Default, Dropbox-sicher), WAL, TRUNCATE,
        PERSIST, MEMORY, OFF. Wird nur umgestellt, wenn der aktuelle Modus
        vom Wunsch abweicht — das vermeidet unnoetige Schreib-Locks beim
        Oeffnen.
        """
        conn = self.connection
        wanted = self.get_setting("db_journal_mode", _DEFAULT_JOURNAL_MODE).upper()
        if wanted not in _ALLOWED_JOURNAL_MODES:
            wanted = _DEFAULT_JOURNAL_MODE
        current_row = conn.execute("PRAGMA journal_mode").fetchone()
        current = str(current_row[0]).upper() if current_row else ""
        if current != wanted:
            conn.execute(f"PRAGMA journal_mode={wanted}")

    def get_setting(self, key: str, default: str = "") -> str:
        """Liest einen Einstellungswert aus der Datenbank."""
        conn = self.connection
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """Setzt einen Einstellungswert (upsert mit Audit-Spalten)."""
        conn = self.connection
        now = audit_now()
        user = audit_user()
        conn.execute(
            """
            INSERT INTO settings (key, value, created_at, created_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                changed_at = excluded.created_at,
                changed_by = excluded.created_by
            """,
            (key, value, now, user),
        )
        conn.commit()

    def get_bool_setting(self, key: str, default: bool = False) -> bool:
        """Liest ein Boolean-Setting (Speicherung als '1'/'0')."""
        raw = self.get_setting(key, "1" if default else "0")
        return raw.strip() == "1"

    def set_bool_setting(self, key: str, value: bool) -> None:
        """Setzt ein Boolean-Setting."""
        self.set_setting(key, "1" if value else "0")

    def get_int_setting(self, key: str, default: int) -> int:
        """Liest ein Integer-Setting."""
        raw = self.get_setting(key, str(default))
        try:
            return int(raw)
        except ValueError:
            return default

    def set_int_setting(self, key: str, value: int) -> None:
        """Setzt ein Integer-Setting."""
        self.set_setting(key, str(value))
