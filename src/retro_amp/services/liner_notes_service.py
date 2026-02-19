"""Liner Notes Service — Wikipedia-Infos zu Artists und Alben.

Holt Kurzinfos aus der Wikipedia (deutsch + englisch Fallback)
und cached sie als Markdown-Dateien in ~/.retro-amp/notes/.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

_USER_AGENT = "retro-amp/0.5 (terminal-music-player; github.com/michaelblaess/retro-amp)"
_TIMEOUT = 5


def _safe_filename(name: str) -> str:
    """Erzeugt einen sicheren Dateinamen aus einem String."""
    safe = re.sub(r'[<>:"/\\|?*]', "_", name)
    safe = safe.strip(". ")
    return safe[:100] if safe else "unknown"


def _wiki_search(query: str, lang: str = "de") -> tuple[str, str]:
    """Sucht einen Wikipedia-Artikel und gibt (Titel, Extract) zurueck.

    Returns:
        Tuple (Titel, Extract-Text) oder ("", "") wenn nichts gefunden.
    """
    try:
        params = urllib.parse.urlencode({
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": "1",
        })
        url = f"https://{lang}.wikipedia.org/w/api.php?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read())
            results = data.get("query", {}).get("search", [])
            if not results:
                return "", ""
            title = results[0]["title"]

        # Summary holen
        summary_url = (
            f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
            f"{urllib.parse.quote(title)}"
        )
        req2 = urllib.request.Request(summary_url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req2, timeout=_TIMEOUT) as resp2:
            data2 = json.loads(resp2.read())
            extract = data2.get("extract", "")
            return title, extract

    except Exception:
        logger.debug("Wikipedia-Suche fehlgeschlagen: %s (%s)", query, lang)
        return "", ""


class LinerNotesService:
    """Holt und cached Artist-Infos aus Wikipedia."""

    def __init__(self, notes_dir: Path | None = None) -> None:
        self._notes_dir = notes_dir or Path.home() / ".retro-amp" / "notes"
        self._notes_dir.mkdir(parents=True, exist_ok=True)

    def get_note(self, artist: str) -> str:
        """Gibt die Liner Note fuer einen Artist zurueck.

        Liest aus Cache oder holt von Wikipedia.
        Gibt leeren String zurueck wenn nichts gefunden.
        """
        if not artist or not artist.strip():
            return ""

        artist = artist.strip()

        # Cache pruefen
        cached = self._read_cache(artist)
        if cached is not None:
            return cached

        # Von Wikipedia holen
        note = self._fetch_from_wikipedia(artist)

        # Cache schreiben (auch leere Ergebnisse, um wiederholte Abfragen zu vermeiden)
        self._write_cache(artist, note)

        return note

    def _cache_path(self, artist: str) -> Path:
        """Pfad zur Cache-Datei fuer einen Artist."""
        return self._notes_dir / f"{_safe_filename(artist)}.md"

    def _read_cache(self, artist: str) -> str | None:
        """Liest die Cache-Datei. Gibt None zurueck wenn nicht vorhanden."""
        path = self._cache_path(artist)
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return None

    def _write_cache(self, artist: str, content: str) -> None:
        """Schreibt die Cache-Datei."""
        try:
            path = self._cache_path(artist)
            path.write_text(content, encoding="utf-8")
        except Exception:
            logger.debug("Cache schreiben fehlgeschlagen: %s", artist)

    def _fetch_from_wikipedia(self, artist: str) -> str:
        """Holt Artist-Info aus Wikipedia (deutsch, dann englisch Fallback)."""
        # Suchstrategien: mit "Band"/"Musiker" Suffix fuer bessere Treffer
        queries_de = [f"{artist} Band", f"{artist} Musiker", artist]
        queries_en = [f"{artist} band", f"{artist} musician", artist]

        # Deutsch zuerst
        for query in queries_de:
            title, extract = _wiki_search(query, "de")
            if extract and self._is_music_related(title, extract, artist):
                return self._format_note(artist, title, extract, "de")

        # Englisch Fallback
        for query in queries_en:
            title, extract = _wiki_search(query, "en")
            if extract and self._is_music_related(title, extract, artist):
                return self._format_note(artist, title, extract, "en")

        return ""

    def _is_music_related(self, title: str, extract: str, artist: str) -> bool:
        """Prueft ob das Wikipedia-Ergebnis musikbezogen ist."""
        text = (title + " " + extract).lower()
        music_keywords = {
            "band", "musik", "music", "singer", "saenger", "sängerin",
            "album", "song", "record", "label", "genre", "pop", "rock",
            "electronic", "elektronisch", "hip-hop", "jazz", "synthie",
            "synth", "punk", "metal", "wave", "disco", "rapper",
            "gitarrist", "guitarist", "drummer", "pianist", "komponist",
            "composer", "producer", "produzent", "hit", "chart",
            "single", "lp", "ep", "tour", "konzert", "concert",
        }
        return any(kw in text for kw in music_keywords)

    def _format_note(
        self, artist: str, title: str, extract: str, lang: str,
    ) -> str:
        """Formatiert die Note als Markdown."""
        wiki_url = (
            f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title)}"
        )
        return f"# {artist}\n\n{extract}\n\n— [Wikipedia]({wiki_url})\n"
