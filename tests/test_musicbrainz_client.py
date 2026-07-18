"""Tests fuer MusicBrainzClient - offline via httpx.MockTransport.

Prueft die harten Gates: exakte Track-Anzahl, Mehrdeutigkeit -> None,
Dauer-Plausibilitaet, kein Treffer -> None.
"""

from __future__ import annotations

from typing import Any

from retro_amp.infrastructure.musicbrainz_client import MusicBrainzClient


def _release(release_id: str, track_count: int, score: int) -> dict[str, Any]:
    return {"id": release_id, "track-count": track_count, "score": score}


def _tracklist(titles: list[str], lengths_ms: list[int] | None = None) -> dict[str, Any]:
    tracks = [{"title": title, "length": (lengths_ms[i] if lengths_ms else None)} for i, title in enumerate(titles)]
    return {"media": [{"tracks": tracks}]}


def _make_client(
    search: dict[str, Any],
    tracklists: dict[str, dict[str, Any]],
) -> MusicBrainzClient:
    def fetcher(url: str) -> dict[str, Any]:
        # tracklist:  .../ws/2/release/<id>?...   search:  .../ws/2/release?...
        if "/release/" in url:
            release_id = url.split("/release/", 1)[1].split("?", 1)[0]
            return tracklists.get(release_id, {"media": []})
        return search

    return MusicBrainzClient("test", rate_interval=0.0, fetcher=fetcher)


class TestMusicBrainzClient:
    def test_happy_path_returns_titles(self) -> None:
        search = {"releases": [_release("r1", 3, 100)]}
        tracklists = {"r1": _tracklist(["A", "B", "C"], [180000, 200000, 190000])}
        client = _make_client(search, tracklists)

        result = client.lookup_tracklist("Artist", "Album", 3, [180.0, 200.0, 190.0])

        assert result == ["A", "B", "C"]

    def test_track_count_mismatch_returns_none(self) -> None:
        # Release hat 5 Tracks, aber nur 3 Dateien -> kein Match.
        search = {"releases": [_release("r1", 5, 100)]}
        tracklists = {"r1": _tracklist(["A", "B", "C", "D", "E"])}
        client = _make_client(search, tracklists)

        assert client.lookup_tracklist("Artist", "Album", 3) is None

    def test_ambiguous_candidates_returns_none(self) -> None:
        # Zwei Releases mit passender Anzahl, aber abweichenden Titeln.
        search = {"releases": [_release("r1", 3, 100), _release("r2", 3, 90)]}
        tracklists = {
            "r1": _tracklist(["A", "B", "C"]),
            "r2": _tracklist(["A", "X", "C"]),
        }
        client = _make_client(search, tracklists)

        assert client.lookup_tracklist("Artist", "Album", 3) is None

    def test_agreeing_candidates_returns_titles(self) -> None:
        # Zwei Releases, identische Trackliste -> eindeutig genug.
        search = {"releases": [_release("r1", 3, 100), _release("r2", 3, 90)]}
        tracklists = {
            "r1": _tracklist(["A", "B", "C"]),
            "r2": _tracklist(["A", "B", "C"]),
        }
        client = _make_client(search, tracklists)

        assert client.lookup_tracklist("Artist", "Album", 3) == ["A", "B", "C"]

    def test_duration_mismatch_returns_none(self) -> None:
        search = {"releases": [_release("r1", 3, 100)]}
        tracklists = {"r1": _tracklist(["A", "B", "C"], [180000, 200000, 190000])}
        client = _make_client(search, tracklists)

        # Dateidauern weichen massiv ab -> unplausibel.
        assert client.lookup_tracklist("Artist", "Album", 3, [10.0, 12.0, 11.0]) is None

    def test_no_releases_returns_none(self) -> None:
        client = _make_client({"releases": []}, {})
        assert client.lookup_tracklist("Artist", "Album", 3) is None

    def test_empty_album_returns_none(self) -> None:
        client = _make_client({"releases": []}, {})
        assert client.lookup_tracklist("Artist", "", 3) is None
