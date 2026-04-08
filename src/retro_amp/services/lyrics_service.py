"""Lyrics Service — Song-Texte von lrclib.net mit Uebersetzung.

Holt Lyrics per lrclib.net API und uebersetzt optional per MyMemory API.
Ergebnisse werden als Textdateien in ~/.retro-amp/lyrics/ gecached.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

_USER_AGENT = "retro-amp/0.7 (terminal-music-player; github.com/michaelblaess/retro-amp)"
_TIMEOUT = 8
# MyMemory: max 500 Zeichen pro Request, wir teilen in Bloecke
_TRANSLATE_CHUNK_SIZE = 450
# MyMemory: Email-Parameter gibt 50.000 Zeichen/Tag (statt 5.000 anonym)
_MYMEMORY_EMAIL = "retro-amp@michaelblaess.de"


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
    ) -> tuple[str, str, list[tuple[float, str]]]:
        """Gibt (original_lyrics, translated_lyrics, synced_lines) zurueck.

        synced_lines ist eine Liste von (timestamp_seconds, text) Tupeln,
        oder leer wenn keine zeitgestempelten Lyrics verfuegbar.
        Liest aus Cache oder holt von lrclib.net + MyMemory.
        Gibt ("", "", []) zurueck wenn nichts gefunden.
        """
        if not artist or not title:
            return "", "", []

        artist = artist.strip()
        title = title.strip()

        # Cache pruefen
        cached = self._read_cache(artist, title)
        if cached is not None:
            return cached

        # Von lrclib.net holen
        original, synced_lines = self._fetch_lyrics(artist, title)
        if not original:
            # NICHT cachen — naechster Versuch probiert es erneut
            return "", "", []

        # Uebersetzen
        translated = ""
        if translate:
            translated = self._translate(original)

        # Cache schreiben
        self._write_cache(artist, title, original, translated, synced_lines)

        return original, translated, synced_lines

    def _cache_path(self, artist: str, title: str) -> Path:
        """Pfad zur Cache-Datei."""
        filename = _safe_filename(f"{artist} - {title}")
        return self._lyrics_dir / f"{filename}.json"

    def _read_cache(
        self, artist: str, title: str,
    ) -> tuple[str, str, list[tuple[float, str]]] | None:
        """Liest Lyrics aus dem Cache."""
        path = self._cache_path(artist, title)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            synced_raw = data.get("synced_raw", "")
            synced_lines = self._parse_synced_lyrics(synced_raw) if synced_raw else []
            return data.get("original", ""), data.get("translated", ""), synced_lines
        except Exception:
            return None

    def _write_cache(
        self,
        artist: str,
        title: str,
        original: str,
        translated: str,
        synced_lines: list[tuple[float, str]],
    ) -> None:
        """Schreibt Lyrics in den Cache."""
        try:
            path = self._cache_path(artist, title)
            # Synced-Rohdaten rekonstruieren fuer Cache
            synced_raw = ""
            if synced_lines:
                parts: list[str] = []
                for ts, text in synced_lines:
                    minutes = int(ts // 60)
                    seconds = ts - minutes * 60
                    parts.append(f"[{minutes:02d}:{seconds:05.2f}] {text}")
                synced_raw = "\n".join(parts)
            data = {"artist": artist, "title": title,
                    "original": original, "translated": translated,
                    "synced_raw": synced_raw}
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        except Exception:
            logger.debug("Lyrics-Cache schreiben fehlgeschlagen: %s - %s", artist, title)

    def _fetch_lyrics(
        self, artist: str, title: str,
    ) -> tuple[str, list[tuple[float, str]]]:
        """Holt Lyrics von lrclib.net.

        Gibt (plain_text, synced_lines) zurueck. syncedLyrics werden
        bevorzugt — der Plain-Text wird daraus extrahiert.
        """
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
                    entry = data[0]
                    synced_raw = entry.get("syncedLyrics") or ""
                    plain = entry.get("plainLyrics") or ""

                    # syncedLyrics bevorzugen
                    synced_lines = self._parse_synced_lyrics(synced_raw)
                    if synced_lines:
                        # Plain-Text aus Synced extrahieren
                        if not plain:
                            plain = "\n".join(text for _, text in synced_lines)
                        return plain.strip(), synced_lines

                    # Fallback: nur plainLyrics
                    return plain.strip(), []
        except Exception:
            logger.debug("Lyrics-Abfrage fehlgeschlagen: %s - %s", artist, title)
        return "", []

    def _parse_synced_lyrics(
        self, synced_text: str,
    ) -> list[tuple[float, str]]:
        """Parst [MM:SS.xx] Format in (seconds, text) Tupel."""
        if not synced_text:
            return []
        lines: list[tuple[float, str]] = []
        for line in synced_text.strip().splitlines():
            match = re.match(r"\[(\d{2}):(\d{2})\.(\d{2})\]\s*(.*)", line)
            if match:
                minutes = int(match.group(1))
                secs = int(match.group(2))
                hundredths = int(match.group(3))
                time_secs = minutes * 60 + secs + hundredths / 100.0
                text = match.group(4).strip()
                if text:
                    lines.append((time_secs, text))
        return lines

    def _translate(self, text: str) -> str:
        """Uebersetzt Text per MyMemory API (Autodetect → DE)."""
        if not text:
            return ""

        # In Bloecke aufteilen (MyMemory Limit: ~500 Zeichen)
        chunks = self._split_text(text, _TRANSLATE_CHUNK_SIZE)
        translated_parts: list[str] = []
        any_success = False

        for chunk in chunks:
            translated = self._translate_chunk(chunk)
            if translated:
                translated_parts.append(translated)
                any_success = True
            elif self._rate_limited:
                # Rate Limit → sofort abbrechen, nicht weiter versuchen
                break
            else:
                translated_parts.append("")

        if not any_success:
            return ""
        return "\n".join(translated_parts)

    _rate_limited: bool = False

    def _translate_chunk(self, text: str) -> str:
        """Uebersetzt einen einzelnen Text-Block."""
        if self._rate_limited:
            return ""
        try:
            params = urllib.parse.urlencode({
                "q": text,
                "langpair": "autodetect|de",
                "de": _MYMEMORY_EMAIL,
            })
            url = f"https://api.mymemory.translated.net/get?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read())
                status = data.get("responseStatus", 0)
                result = data.get("responseData", {}).get("translatedText", "")

                # 429 als responseStatus (innerhalb JSON)
                if status == 429:
                    self._rate_limited = True
                    logger.debug("MyMemory Rate Limit erreicht (JSON)")
                    return ""
                if status != 200 or not result:
                    return ""
                # MyMemory gibt UPPERCASE zurueck bei Fehlern → verwerfen
                if result == result.upper():
                    return ""
                # Bekannte Fehlermeldungen filtern
                error_markers = [
                    "nicht übersetzt",
                    "not translated",
                    "mymemory warning",
                    "no translation",
                    "please use",
                ]
                result_lower = result.lower()
                if any(m in result_lower for m in error_markers):
                    return ""
                return result
        except urllib.error.HTTPError as e:
            if e.code == 429:
                self._rate_limited = True
                logger.debug("MyMemory Rate Limit erreicht (HTTP 429)")
            else:
                logger.debug("Uebersetzung HTTP-Fehler: %s", e.code)
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
