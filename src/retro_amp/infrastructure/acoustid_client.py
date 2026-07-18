"""AcoustID-Titelerkennung per Audio-Fingerprint (Stufe 2 / bestaetigt).

Implementiert das ``TrackTitleLookup``-Protocol. Fingerprintet die Datei mit
``fpcalc`` (Chromaprint) und fragt die AcoustID-Web-API ab. Ein Treffer wird
nur zurueckgegeben, wenn der Score ueber der Schwelle liegt UND die Recordings
des Top-Treffers eindeutig denselben Titel tragen - sonst None (kein Raten).

HTTP ueber die Stdlib (urllib), Fingerprint ueber ``fpcalc`` als Subprocess -
keine zusaetzliche Python-Dependency. ``fpcalc`` (Chromaprint) und ein
kostenloser AcoustID-API-Key sind Voraussetzung; fehlt eines, liefert die
Quelle sauber None.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_API_URL = "https://api.acoustid.org/v2/lookup"
_ALNUM = re.compile(r"[^a-z0-9]+")

# (Dauer in Sekunden, Fingerprint) oder None.
Fingerprint = tuple[float, str]
Fingerprinter = Callable[[Path], "Fingerprint | None"]
JsonFetcher = Callable[[str], dict[str, Any]]


def _normalize(text: str) -> str:
    return _ALNUM.sub("", text.lower())


class AcoustIDClient:
    """TrackTitleLookup-Implementation gegen AcoustID + fpcalc."""

    def __init__(
        self,
        key_provider: Callable[[], str],
        fpcalc_path: str | None = None,
        on_log: Callable[[str], None] | None = None,
        score_threshold: float = 0.8,
        rate_interval: float = 0.34,
        timeout: float = 20.0,
        fingerprinter: Fingerprinter | None = None,
        fetcher: JsonFetcher | None = None,
    ) -> None:
        self._key_provider = key_provider
        self._fpcalc = fpcalc_path if fpcalc_path is not None else self._detect_fpcalc()
        self._on_log = on_log
        self._threshold = score_threshold
        self._rate_interval = rate_interval
        self._timeout = timeout
        self._fingerprint = fingerprinter or self._run_fpcalc  # Injektion fuer Tests
        self._fetch = fetcher or self._http_get_json
        self._last_request = 0.0
        self._warned = False

    def available(self) -> bool:
        """True wenn fpcalc gefunden wurde und ein API-Key gesetzt ist."""
        return bool(self._fpcalc) and bool(self._key_provider().strip())

    def lookup_title(self, path: Path, duration_seconds: float) -> str | None:
        """Erkennt den Titel per Fingerprint (siehe Protocol-Doku)."""
        key = self._key_provider().strip()
        if not self._fpcalc or not key:
            self._warn_unavailable()
            return None
        try:
            fingerprint = self._fingerprint(path)
            if fingerprint is None:
                return None
            duration, code = fingerprint
            data = self._query(key, duration, code)
            return self._best_title(data)
        except Exception:
            logger.debug("AcoustID-Lookup fehlgeschlagen: %s", path, exc_info=True)
            return None

    def _query(self, key: str, duration: float, fingerprint: str) -> dict[str, Any]:
        params = urllib.parse.urlencode(
            {
                "client": key,
                "meta": "recordings",
                "duration": int(round(duration)),
                "fingerprint": fingerprint,
            }
        )
        return self._fetch(f"{_API_URL}?{params}")

    def _best_title(self, data: dict[str, Any]) -> str | None:
        """Waehlt den Titel des besten Treffers - nur wenn eindeutig."""
        results = list(data.get("results", []))
        if not results:
            return None
        results.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        top = results[0]
        if float(top.get("score", 0.0)) < self._threshold:
            return None

        titles = [
            (recording.get("title") or "").strip()
            for recording in top.get("recordings", [])
            if (recording.get("title") or "").strip()
        ]
        if not titles:
            return None
        # Mehrdeutig (Fingerprint mappt auf mehrere Titel) -> nicht raten.
        if len({_normalize(title) for title in titles}) != 1:
            return None
        return titles[0]

    def _run_fpcalc(self, path: Path) -> Fingerprint | None:
        """Ruft fpcalc auf und liefert (Dauer, Fingerprint)."""
        if not self._fpcalc:
            return None
        try:
            proc = subprocess.run(  # noqa: S603 (fester fpcalc-Pfad, kein Shell)
                [self._fpcalc, "-json", str(path)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            logger.debug("fpcalc-Aufruf fehlgeschlagen: %s", path, exc_info=True)
            return None
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        try:
            data = json.loads(proc.stdout)
            duration = float(data["duration"])
            code = str(data["fingerprint"])
        except (ValueError, KeyError, TypeError):
            return None
        return (duration, code) if code else None

    def _http_get_json(self, url: str) -> dict[str, Any]:
        """Echter HTTP-GET via urllib mit Rate-Limit."""
        self._rate_limit()
        request = urllib.request.Request(url, headers={"Accept": "application/json"})  # noqa: S310
        with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else {}

    def _rate_limit(self) -> None:
        wait = self._rate_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    @staticmethod
    def _detect_fpcalc() -> str | None:
        """Sucht fpcalc auf dem PATH oder neben der (Nuitka-)Executable."""
        found = shutil.which("fpcalc")
        if found:
            return found
        exe_dir = Path(sys.executable).parent
        for candidate in (exe_dir / "fpcalc.exe", exe_dir / "fpcalc", exe_dir / "bin" / "fpcalc.exe"):
            if candidate.is_file():
                return str(candidate)
        return None

    def _warn_unavailable(self) -> None:
        """Loggt einmalig, wenn fpcalc oder der API-Key fehlt."""
        if self._warned or self._on_log is None:
            return
        self._warned = True
        if not self._fpcalc:
            self._on_log("AcoustID: fpcalc (Chromaprint) nicht gefunden - Fingerprint uebersprungen")
        else:
            self._on_log("AcoustID: kein API-Key gesetzt - Fingerprint uebersprungen")
