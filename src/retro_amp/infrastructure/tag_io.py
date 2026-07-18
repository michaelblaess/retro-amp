"""Eingebettete Tags lesen und den Titel schreiben - via mutagen.

Nutzt die Easy-Schnittstelle von mutagen, die ``title``/``tracknumber`` ueber
die Formate (MP3/FLAC/Vorbis/MP4) vereinheitlicht. Implementiert das
``TagIO``-Protocol aus domain/protocols.py.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Formate, in die der Titel-Tag zuverlaessig geschrieben werden kann.
_WRITABLE_EXTENSIONS = {".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".mp4"}

# Fuehrende Zahl aus einem "3/11"- oder "03"-Tracknummer-Tag.
_LEADING_NUMBER = re.compile(r"\s*(\d+)")


class UnsupportedTagFormatError(Exception):
    """Das Format unterstuetzt kein Schreiben des Titel-Tags."""


class MutagenTagIO:
    """TagIO-Implementation auf Basis von mutagen (Easy-Schnittstelle)."""

    def read_embedded_title(self, path: Path) -> str:
        """Liest den eingebetteten Titel-Tag (leer wenn keiner vorhanden)."""
        return self._read_easy_key(path, "title")

    def read_embedded_artist(self, path: Path) -> str:
        """Liest den eingebetteten Artist-Tag (leer wenn keiner vorhanden)."""
        return self._read_easy_key(path, "artist")

    def read_embedded_album(self, path: Path) -> str:
        """Liest den eingebetteten Album-Tag (leer wenn keiner vorhanden)."""
        return self._read_easy_key(path, "album")

    def read_track_number(self, path: Path) -> int:
        """Liest die Tracknummer aus den Tags (0 wenn keine)."""
        raw = self._read_easy_key(path, "tracknumber")
        match = _LEADING_NUMBER.match(raw)
        return int(match.group(1)) if match else 0

    def write_title(self, path: Path, title: str) -> None:
        """Schreibt den Titel in die Tags.

        Wirft ``UnsupportedTagFormatError`` bei Formaten ohne Tag-Support
        (WAV, Tracker/SID) oder wenn mutagen die Datei nicht oeffnen kann.
        """
        if path.suffix.lower() not in _WRITABLE_EXTENSIONS:
            raise UnsupportedTagFormatError(path.suffix)

        import mutagen

        audio = mutagen.File(str(path), easy=True)
        if audio is None:
            raise UnsupportedTagFormatError(path.suffix)
        if audio.tags is None:
            audio.add_tags()
        audio["title"] = [title]
        audio.save()

    @staticmethod
    def _read_easy_key(path: Path, key: str) -> str:
        """Liest einen Easy-Tag-Schluessel als String (leer bei Fehler/Fehlen)."""
        try:
            import mutagen

            audio = mutagen.File(str(path), easy=True)
            if audio is None:
                return ""
            value = audio.get(key)
            if not value:
                return ""
            if isinstance(value, list):
                return str(value[0]).strip() if value else ""
            return str(value).strip()
        except Exception:
            logger.debug("Tag '%s' nicht lesbar: %s", key, path)
            return ""
