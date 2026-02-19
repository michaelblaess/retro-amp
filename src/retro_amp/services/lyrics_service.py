"""Lyrics Service — Song-Texte von lrclib.net mit Uebersetzung.

Holt Lyrics per lrclib.net API und uebersetzt optional per MyMemory API.
Ergebnisse werden als Textdateien in ~/.retro-amp/lyrics/ gecached.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

_USER_AGENT = "retro-amp/0.6 (terminal-music-player; github.com/michaelblaess/retro-amp)"
_TIMEOUT = 8
# MyMemory: max 500 Zeichen pro Request, wir teilen in Bloecke
_TRANSLATE_CHUNK_SIZE = 450


def _safe_filename(name: str) -> str:
    """Erzeugt einen sicheren Dateinamen."""
    safe = re.sub(r'[<>:"/\\|?*]', "_", name)
    safe = safe.strip(". ")
    return safe[:120] if safe else "unknown"


class LyricsService:
    """Holt und cached Song-Lyrics mit optionaler Uebersetzung."""

    def __init__(self, lyrics_dir: Path | None = None) -> None:
        self._lyrics_dir = lyrics_dir or Path.home() / ".retro-amp" / "lyrics"
        self._lyrics_dir.mkdir(parents=True, exist_ok=True)

    def get_lyrics(
        self,
        artist: str,
        title: str,
        translate: bool = True,
    ) -> tuple[str, str]:
        """Gibt (original_lyrics, translated_lyrics) zurueck.

        Liest aus Cache oder holt von lrclib.net + MyMemory.
        Gibt ("", "") zurueck wenn nichts gefunden.
        """
        if not artist or not title:
            return "", ""

        artist = artist.strip()
        title = title.strip()

        # Cache pruefen
        cached = self._read_cache(artist, title)
        if cached is not None:
            return cached

        # Von lrclib.net holen
        original = self._fetch_lyrics(artist, title)
        if not original:
            # Leeren Cache schreiben (vermeidet wiederholte Abfragen)
            self._write_cache(artist, title, "", "")
            return "", ""

        # Uebersetzen
        translated = ""
        if translate:
            translated = self._translate(original)

        # Cache schreiben
        self._write_cache(artist, title, original, translated)

        return original, translated

    def _cache_path(self, artist: str, title: str) -> Path:
        """Pfad zur Cache-Datei."""
        filename = _safe_filename(f"{artist} - {title}")
        return self._lyrics_dir / f"{filename}.json"

    def _read_cache(self, artist: str, title: str) -> tuple[str, str] | None:
        """Liest Lyrics aus dem Cache."""
        path = self._cache_path(artist, title)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("original", ""), data.get("translated", "")
        except Exception:
            return None

    def _write_cache(
        self, artist: str, title: str, original: str, translated: str,
    ) -> None:
        """Schreibt Lyrics in den Cache."""
        try:
            path = self._cache_path(artist, title)
            data = {"artist": artist, "title": title,
                    "original": original, "translated": translated}
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        except Exception:
            logger.debug("Lyrics-Cache schreiben fehlgeschlagen: %s - %s", artist, title)

    def _fetch_lyrics(self, artist: str, title: str) -> str:
        """Holt Lyrics von lrclib.net."""
        try:
            params = urllib.parse.urlencode({
                "artist_name": artist,
                "track_name": title,
            })
            url = f"https://lrclib.net/api/search?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read())
                if data and isinstance(data, list):
                    # plainLyrics bevorzugen, syncedLyrics als Fallback
                    entry = data[0]
                    lyrics = entry.get("plainLyrics") or ""
                    if not lyrics:
                        synced = entry.get("syncedLyrics") or ""
                        # Timestamps entfernen: [MM:SS.xx] Text
                        lyrics = re.sub(r"\[\d{2}:\d{2}\.\d{2}\]\s*", "", synced)
                    return lyrics.strip()
        except Exception:
            logger.debug("Lyrics-Abfrage fehlgeschlagen: %s - %s", artist, title)
        return ""

    def _translate(self, text: str) -> str:
        """Uebersetzt Text per MyMemory API (EN → DE)."""
        if not text:
            return ""

        # In Bloecke aufteilen (MyMemory Limit: ~500 Zeichen)
        chunks = self._split_text(text, _TRANSLATE_CHUNK_SIZE)
        translated_parts: list[str] = []

        for chunk in chunks:
            translated = self._translate_chunk(chunk)
            if translated:
                translated_parts.append(translated)
            else:
                # Bei Fehler Original behalten
                translated_parts.append(chunk)

        return "\n".join(translated_parts)

    def _translate_chunk(self, text: str) -> str:
        """Uebersetzt einen einzelnen Text-Block."""
        try:
            params = urllib.parse.urlencode({
                "q": text,
                "langpair": "en|de",
            })
            url = f"https://api.mymemory.translated.net/get?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read())
                result = data.get("responseData", {}).get("translatedText", "")
                # MyMemory gibt UPPERCASE zurueck bei Fehlern → verwerfen
                if result and result != result.upper():
                    return result
                return ""
        except Exception:
            logger.debug("Uebersetzung fehlgeschlagen")
            return ""

    def _split_text(self, text: str, max_len: int) -> list[str]:
        """Teilt Text an Absatzgrenzen in Bloecke."""
        paragraphs = text.split("\n\n")
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for para in paragraphs:
            para_len = len(para)
            if current_len + para_len + 2 > max_len and current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            current.append(para)
            current_len += para_len + 2

        if current:
            chunks.append("\n\n".join(current))

        return chunks
