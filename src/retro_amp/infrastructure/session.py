"""Session-Recovery — speichert Playback-State fuer Crash-Recovery.

Bei sauberem Shutdown wird die Session-Datei geloescht.
Existiert sie beim Start noch, war der letzte Exit ein Crash.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SESSION_DIR = Path.home() / ".retro-amp"
_SESSION_FILE = _SESSION_DIR / "session.json"


def save_session(
    track_path: str,
    position_seconds: float,
    volume: float,
) -> None:
    """Speichert den aktuellen Playback-State."""
    try:
        _SESSION_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "track_path": track_path,
            "position_seconds": position_seconds,
            "volume": volume,
        }
        _SESSION_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        logger.debug("Session konnte nicht gespeichert werden")


def load_session() -> dict[str, object] | None:
    """Liest die Session-Datei. Gibt None zurueck wenn keine existiert."""
    if not _SESSION_FILE.is_file():
        return None
    try:
        raw = _SESSION_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("track_path"):
            return data
    except Exception:
        logger.debug("Session konnte nicht gelesen werden")
    return None


def clear_session() -> None:
    """Loescht die Session-Datei (sauberer Shutdown)."""
    try:
        if _SESSION_FILE.is_file():
            _SESSION_FILE.unlink()
    except Exception:
        logger.debug("Session konnte nicht geloescht werden")
