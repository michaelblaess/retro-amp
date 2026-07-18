"""MusicBrainz-Trackliste-Suche (Stufe 3 / heuristisch, aber hart gegatet).

Implementiert das ``AlbumTitleLookup``-Protocol. Sucht ein Release nach
Artist + Album, akzeptiert nur Releases mit EXAKT passender Track-Anzahl,
verwirft mehrdeutige Faelle (mehrere Releases mit abweichenden Tracklisten)
und prueft optional die Track-Dauern gegen die echten Dateien.

Wichtig: Diese Quelle raet nicht - liefert ein Match nur, wenn Track-Anzahl
passt, die Kandidaten sich einig sind und die Dauern grob stimmen. Sonst None.

HTTP ueber die Stdlib (urllib) - keine zusaetzliche Dependency (wie lyrics_service).
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

_BASE_URL = "https://musicbrainz.org/ws/2"
# Nur alphanumerisch fuer den Titel-Vergleich zwischen Kandidaten.
_ALNUM = re.compile(r"[^a-z0-9]+")
# Lucene-Sonderzeichen, die im Query maskiert werden muessen.
_LUCENE_SPECIAL = re.compile(r'([\\"])')

# Testbarkeit: eine Funktion, die eine URL holt und JSON (dict) zurueckgibt.
JsonFetcher = Callable[[str], dict[str, Any]]


def _normalize(text: str) -> str:
    return _ALNUM.sub("", text.lower())


class MusicBrainzClient:
    """AlbumTitleLookup-Implementation gegen die MusicBrainz-Web-API."""

    def __init__(
        self,
        app_version: str,
        on_log: Callable[[str], None] | None = None,
        max_candidates: int = 5,
        rate_interval: float = 1.1,
        timeout: float = 20.0,
        fetcher: JsonFetcher | None = None,
    ) -> None:
        # MusicBrainz verlangt einen aussagekraeftigen User-Agent mit Kontakt.
        self._user_agent = f"retro-amp/{app_version} ( https://github.com/michaelblaess/retro-amp )"
        self._on_log = on_log
        self._max_candidates = max_candidates
        self._rate_interval = rate_interval
        self._timeout = timeout
        self._fetch = fetcher or self._http_get_json  # fetcher nur fuer Tests
        self._last_request = 0.0

    def lookup_tracklist(
        self,
        artist: str,
        album: str,
        track_count: int,
        durations: list[float] | None = None,
    ) -> list[str] | None:
        """Sucht die Titel eines Albums (siehe Protocol-Doku)."""
        album = album.strip()
        if not album or track_count <= 0:
            return None

        try:
            candidates = self._search_releases(artist, album, track_count)
            if not candidates:
                self._log_no_match(album)
                return None

            tracklists: list[list[tuple[str, int]]] = []
            for release_id in candidates[: self._max_candidates]:
                tracks = self._fetch_tracklist(release_id)
                if len(tracks) == track_count and all(title for title, _ in tracks):
                    tracklists.append(tracks)

            if not tracklists:
                self._log_no_match(album)
                return None

            primary = tracklists[0]
            # Mehrdeutigkeit: verschiedene Kandidaten mit abweichenden Titeln.
            for other in tracklists[1:]:
                if not self._titles_agree(primary, other):
                    self._log(f"MusicBrainz: mehrdeutig fuer '{album}' - uebersprungen")
                    return None

            # Dauer-Plausibilitaet (falls Dateidauern + MB-Laengen vorliegen).
            lengths = [length for _, length in primary]
            if durations is not None and not self._durations_plausible(lengths, durations):
                self._log(f"MusicBrainz: Dauern passen nicht fuer '{album}' - uebersprungen")
                return None

            titles = [title for title, _ in primary]
            self._log(f"MusicBrainz: Trackliste gefunden fuer '{album}' ({track_count} Titel)")
            return titles
        except Exception:
            logger.debug("MusicBrainz-Lookup fehlgeschlagen", exc_info=True)
            self._log(f"MusicBrainz: Suche fehlgeschlagen fuer '{album}'")
            return None

    def _search_releases(self, artist: str, album: str, track_count: int) -> list[str]:
        """Sucht Releases und filtert auf exakt passende Track-Anzahl."""
        query = f'release:"{_LUCENE_SPECIAL.sub(r"\\\1", album)}"'
        if artist.strip():
            query += f' AND artist:"{_LUCENE_SPECIAL.sub(r"\\\1", artist.strip())}"'
        params = urllib.parse.urlencode({"query": query, "fmt": "json", "limit": 25})
        data = self._fetch(f"{_BASE_URL}/release?{params}")

        scored: list[tuple[int, str]] = []
        for release in data.get("releases", []):
            count = release.get("track-count")
            if count is None:
                count = sum(medium.get("track-count", 0) for medium in release.get("media", []))
            if count == track_count:
                release_id = release.get("id", "")
                if release_id:
                    scored.append((int(release.get("score", 0)), release_id))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [release_id for _, release_id in scored]

    def _fetch_tracklist(self, release_id: str) -> list[tuple[str, int]]:
        """Laedt die Trackliste eines Releases als (Titel, Laenge in ms)."""
        params = urllib.parse.urlencode({"inc": "recordings", "fmt": "json"})
        data = self._fetch(f"{_BASE_URL}/release/{release_id}?{params}")

        tracks: list[tuple[str, int]] = []
        for medium in data.get("media", []):
            for track in medium.get("tracks", []):
                title = (track.get("title") or "").strip()
                length = track.get("length") or 0
                tracks.append((title, int(length) if length else 0))
        return tracks

    def _http_get_json(self, url: str) -> dict[str, Any]:
        """Echter HTTP-GET via urllib mit Rate-Limit und User-Agent."""
        self._rate_limit()
        request = urllib.request.Request(  # noqa: S310 (feste https-URL)
            url,
            headers={"User-Agent": self._user_agent, "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _titles_agree(a: list[tuple[str, int]], b: list[tuple[str, int]]) -> bool:
        """True wenn beide Tracklisten positionsweise dieselben Titel haben."""
        if len(a) != len(b):
            return False
        return all(_normalize(title_a) == _normalize(title_b) for (title_a, _), (title_b, _) in zip(a, b, strict=False))

    @staticmethod
    def _durations_plausible(lengths_ms: list[int], durations_s: list[float]) -> bool:
        """Prueft, ob die MB-Track-Laengen zu den Dateidauern passen.

        Vergleicht nur Positionen, an denen beide Werte bekannt sind. Sind zu
        wenige MB-Laengen vorhanden, wird nicht blockiert (kann nicht widerlegen).
        Toleranz pro Track: max(12s, 20 %).
        """
        pairs = [
            (length / 1000.0, dur)
            for length, dur in zip(lengths_ms, durations_s, strict=False)
            if length > 0 and dur > 0
        ]
        if len(pairs) < max(1, len(durations_s) // 2):
            return True  # zu wenig Datenbasis -> nicht widerlegbar
        ok = 0
        for mb_seconds, file_seconds in pairs:
            tolerance = max(12.0, 0.2 * mb_seconds)
            if abs(mb_seconds - file_seconds) <= tolerance:
                ok += 1
        return ok >= 0.7 * len(pairs)

    def _rate_limit(self) -> None:
        """Haelt das MusicBrainz-Limit von ~1 Anfrage/Sekunde ein."""
        wait = self._rate_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def _log(self, message: str) -> None:
        if self._on_log is not None:
            self._on_log(message)

    def _log_no_match(self, album: str) -> None:
        self._log(f"MusicBrainz: kein passendes Release fuer '{album}'")
