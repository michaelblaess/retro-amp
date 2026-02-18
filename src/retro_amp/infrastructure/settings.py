"""Settings-Persistenz in ~/.retro-amp/settings.json."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SETTINGS_DIR = Path.home() / ".retro-amp"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"

# Defaults
_DEFAULTS: dict[str, object] = {
    "theme": "textual-dark",
    "volume": 0.8,
    "last_path": "",
}


class JsonSettingsStore:
    """SettingsStore-Implementation mit JSON-Dateien.

    Implementiert das SettingsStore-Protocol aus domain/protocols.py.
    Fail-safe: bei korrupter Datei werden Defaults verwendet.
    """

    def __init__(self, settings_file: Path | None = None) -> None:
        self._file = settings_file or _SETTINGS_FILE
        self._dir = self._file.parent

    def load(self) -> dict[str, object]:
        """Laedt Settings. Gibt Defaults zurueck bei Fehler."""
        result = dict(_DEFAULTS)
        if not self._file.is_file():
            return result

        try:
            raw = self._file.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                result.update(data)
        except Exception:
            logger.debug("Settings konnten nicht geladen werden, verwende Defaults")

        return result

    def save(self, data: dict[str, object]) -> None:
        """Speichert Settings."""
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            self._file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            logger.debug("Settings konnten nicht gespeichert werden")
