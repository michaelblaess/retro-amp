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
from collections.abc import Callable
from pathlib import Path

from ..i18n import t

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

    def __init__(
        self,
        lyrics_dir: Path | None = None,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        self._lyrics_dir = lyrics_dir or Path.home() / ".retro-amp" / "lyrics"
        self._lyrics_dir.mkdir(parents=True, exist_ok=True)
        self._on_log = on_log

    def _log(self, message: str) -> None:
        """Sendet eine Log-Nachricht ans LogPanel (sofern Callback gesetzt)."""
        if self._on_log is None:
            return
        try:
            self._on_log(message)
        except Exception:
            logger.debug("Lyrics-Log-Callback fehlgeschlagen", exc_info=True)

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
            original_cached, _translated_cached, synced_cached = cached
            lines = len(synced_cached) if synced_cached else (original_cached.count("\n") + 1 if original_cached else 0)
            self._log(t("log.lyrics_cache_hit", artist=artist, title=title, lines=lines))
            return cached

        self._log(t("log.lyrics_cache_miss", artist=artist, title=title))

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

    def invalidate_cache(self, artist: str, title: str) -> bool:
        """Loescht die Cache-Datei fuer einen Track. Gibt True zurueck wenn geloescht."""
        if not artist or not title:
            return False
        path = self._cache_path(artist.strip(), title.strip())
        try:
            if path.exists():
                path.unlink()
                self._log(t("log.lyrics_cache_invalidated", artist=artist, title=title))
                return True
        except OSError:
            logger.debug("Lyrics-Cache loeschen fehlgeschlagen: %s", path)
        return False

    def _read_cache(
        self,
        artist: str,
        title: str,
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
            data = {
                "artist": artist,
                "title": title,
                "original": original,
                "translated": translated,
                "synced_raw": synced_raw,
            }
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            logger.debug("Lyrics-Cache schreiben fehlgeschlagen: %s - %s", artist, title)

    def _fetch_lyrics(
        self,
        artist: str,
        title: str,
    ) -> tuple[str, list[tuple[float, str]]]:
        """Holt Lyrics von lrclib.net.

        Zwei-Stufen-Suche:
        1. Strict: artist_name + track_name (schnelles, exaktes Match)
        2. Fuzzy: q= mit gesaeubertem Freitext (Jahr raus, Track-Nummer raus)

        Gibt (plain_text, synced_lines) zurueck. syncedLyrics werden
        bevorzugt — der Plain-Text wird daraus extrahiert.
        """
        # Stufe 1: strict
        self._log(t("log.lyrics_search_strict", artist=artist, title=title))
        result = self._lrclib_query({"artist_name": artist, "track_name": title})
        if result[0]:
            self._log(t("log.lyrics_found", lines=self._count_lines(result)))
            return result

        # Stufe 2: fuzzy mit gesaeubertem Freitext
        clean_artist = self._clean_artist_for_search(artist)
        clean_title = self._clean_title_for_search(title)
        query = " ".join(part for part in (clean_artist, clean_title) if part).strip()
        if query and query.lower() != f"{artist} {title}".lower():
            self._log(t("log.lyrics_search_fuzzy", query=query))
            result = self._lrclib_query({"q": query})
            if result[0]:
                self._log(t("log.lyrics_found", lines=self._count_lines(result)))
                return result

        self._log(t("log.lyrics_not_found"))
        return "", []

    @staticmethod
    def _count_lines(result: tuple[str, list[tuple[float, str]]]) -> int:
        """Zaehlt Zeilen — synced bevorzugt, sonst plain."""
        plain, synced = result
        if synced:
            return len(synced)
        return plain.count("\n") + 1 if plain else 0

    def _lrclib_query(
        self,
        params: dict[str, str],
    ) -> tuple[str, list[tuple[float, str]]]:
        """Ruft lrclib.net/api/search mit den uebergebenen Params auf."""
        try:
            url = f"https://lrclib.net/api/search?{urllib.parse.urlencode(params)}"
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
                        if not plain:
                            plain = "\n".join(text for _, text in synced_lines)
                        return plain.strip(), synced_lines

                    return plain.strip(), []
        except Exception:
            logger.debug("Lyrics-Abfrage fehlgeschlagen: %s", params)
        return "", []

    @staticmethod
    def _clean_artist_for_search(artist: str) -> str:
        """Entfernt 4-stellige Jahresangaben und leere ' - '-Segmente."""
        # Jahre 19xx/20xx (oft Album-Jahre in Folder-Namen)
        cleaned = re.sub(r"\b(?:19|20)\d{2}\b", " ", artist)
        # Mehrfach-Spaces und uebrig gebliebene Dashes aufraeumen
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = re.sub(r"\s*-\s*-\s*", " - ", cleaned)  # " - - " → " - "
        cleaned = cleaned.strip(" -")
        return cleaned

    @staticmethod
    def _clean_title_for_search(title: str) -> str:
        """Entfernt Track-Nummer-Prefix ('01. ', '01 - ', '01.')."""
        cleaned = re.sub(r"^\d+\s*[.\-]\s*", "", title).strip()
        return cleaned or title

    def _parse_synced_lyrics(
        self,
        synced_text: str,
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
            params = urllib.parse.urlencode(
                {
                    "q": text,
                    "langpair": "autodetect|de",
                    "de": _MYMEMORY_EMAIL,
                }
            )
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
