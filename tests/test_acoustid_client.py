"""Tests fuer AcoustIDClient - offline via injizierten Fingerprinter + Fetcher.

Prueft: Score-Schwelle, Mehrdeutigkeit -> None, kein Treffer -> None,
Nichtverfuegbarkeit (kein Key / kein fpcalc), Fingerprint-Fehler -> None.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from retro_amp.infrastructure.acoustid_client import AcoustIDClient


def _result(score: float, titles: list[str]) -> dict[str, Any]:
    return {"score": score, "recordings": [{"title": title} for title in titles]}


def _client(
    response: dict[str, Any],
    key: str = "KEY",
    fpcalc: str | None = "/fake/fpcalc",
    fingerprint: tuple[float, str] | None = (200.0, "FP"),
) -> AcoustIDClient:
    return AcoustIDClient(
        key_provider=lambda: key,
        fpcalc_path=fpcalc,
        rate_interval=0.0,
        fingerprinter=lambda _path: fingerprint,
        fetcher=lambda _url: response,
    )


_PATH = Path("/music/01.mp3")


class TestAcoustIDClient:
    def test_happy_path(self) -> None:
        client = _client({"results": [_result(0.95, ["Song One"])]})
        assert client.lookup_title(_PATH, 200.0) == "Song One"

    def test_below_threshold_returns_none(self) -> None:
        client = _client({"results": [_result(0.5, ["Song One"])]})
        assert client.lookup_title(_PATH, 200.0) is None

    def test_ambiguous_recordings_returns_none(self) -> None:
        client = _client({"results": [_result(0.95, ["Song One", "Different Title"])]})
        assert client.lookup_title(_PATH, 200.0) is None

    def test_same_title_recordings_ok(self) -> None:
        # Mehrere Recordings, aber identischer Titel -> eindeutig.
        client = _client({"results": [_result(0.95, ["Song One", "song one"])]})
        assert client.lookup_title(_PATH, 200.0) == "Song One"

    def test_no_results_returns_none(self) -> None:
        client = _client({"results": []})
        assert client.lookup_title(_PATH, 200.0) is None

    def test_picks_highest_score(self) -> None:
        response = {"results": [_result(0.6, ["Low"]), _result(0.92, ["High"])]}
        client = _client(response)
        assert client.lookup_title(_PATH, 200.0) == "High"

    def test_unavailable_without_key(self) -> None:
        client = _client({"results": [_result(0.95, ["Song"])]}, key="")
        assert client.available() is False
        assert client.lookup_title(_PATH, 200.0) is None

    def test_unavailable_without_fpcalc(self) -> None:
        client = _client({"results": [_result(0.95, ["Song"])]}, fpcalc=None)
        assert client.available() is False
        assert client.lookup_title(_PATH, 200.0) is None

    def test_fingerprint_failure_returns_none(self) -> None:
        client = _client({"results": [_result(0.95, ["Song"])]}, fingerprint=None)
        assert client.available() is True
        assert client.lookup_title(_PATH, 200.0) is None
