"""Tests fuer LyricsService."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from retro_amp.services.lyrics_service import LyricsService, _safe_filename


class TestSafeFilename:
    """Tests fuer _safe_filename."""

    def test_normal(self) -> None:
        assert _safe_filename("Depeche Mode - Enjoy the Silence") == "Depeche Mode - Enjoy the Silence"

    def test_special_chars(self) -> None:
        result = _safe_filename('AC/DC - "TNT"')
        assert "/" not in result
        assert '"' not in result

    def test_empty(self) -> None:
        assert _safe_filename("") == "unknown"

    def test_truncated(self) -> None:
        result = _safe_filename("X" * 200)
        assert len(result) <= 120


class TestLyricsService:
    """Tests fuer LyricsService (offline, Cache-basiert)."""

    def test_empty_params(self, tmp_path: Path) -> None:
        svc = LyricsService(lyrics_dir=tmp_path)
        assert svc.get_lyrics("", "test") == ("", "", [])
        assert svc.get_lyrics("test", "") == ("", "", [])

    def test_cache_roundtrip(self, tmp_path: Path) -> None:
        """Cache schreiben und lesen."""
        svc = LyricsService(lyrics_dir=tmp_path)
        svc._write_cache("Test", "Song", "Hello world", "Hallo Welt", [])
        result = svc._read_cache("Test", "Song")
        assert result == ("Hello world", "Hallo Welt", [])

    def test_cache_prevents_refetch(self, tmp_path: Path) -> None:
        """Zweiter Aufruf liest aus Cache."""
        svc = LyricsService(lyrics_dir=tmp_path)
        svc._write_cache("Artist", "Title", "Lyrics here", "Lyrics hier", [])

        with patch.object(svc, "_fetch_lyrics") as mock:
            original, translated, synced = svc.get_lyrics("Artist", "Title", translate=False)
            mock.assert_not_called()
            assert original == "Lyrics here"

    def test_empty_result_not_cached(self, tmp_path: Path) -> None:
        """Leere Ergebnisse werden NICHT gecached (Retry bei naechstem Versuch)."""
        svc = LyricsService(lyrics_dir=tmp_path)

        with patch.object(svc, "_fetch_lyrics", return_value=("", [])):
            svc.get_lyrics("Nobody", "Nothing", translate=False)

        # Cache-Datei sollte NICHT existieren
        cached = svc._read_cache("Nobody", "Nothing")
        assert cached is None

    def test_split_text(self, tmp_path: Path) -> None:
        """Text wird an Absatzgrenzen geteilt."""
        svc = LyricsService(lyrics_dir=tmp_path)
        text = "Para1\n\nPara2\n\nPara3"
        chunks = svc._split_text(text, max_len=15)
        assert len(chunks) >= 2
        # Alle Chunks zusammen ergeben den Originaltext
        rejoined = "\n\n".join(chunks)
        assert rejoined == text

    def test_lyrics_dir_created(self) -> None:
        """Lyrics-Verzeichnis wird erstellt."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sub" / "lyrics"
            svc = LyricsService(lyrics_dir=path)
            assert path.is_dir()

    def test_cache_json_format(self, tmp_path: Path) -> None:
        """Cache-Datei ist valides JSON."""
        svc = LyricsService(lyrics_dir=tmp_path)
        svc._write_cache("A", "B", "original", "uebersetzt", [])
        cache_file = svc._cache_path("A", "B")
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        assert data["artist"] == "A"
        assert data["title"] == "B"
        assert data["original"] == "original"
        assert data["translated"] == "uebersetzt"

    def test_synced_lyrics_cache_roundtrip(self, tmp_path: Path) -> None:
        """Synced Lyrics werden korrekt gecached und gelesen."""
        svc = LyricsService(lyrics_dir=tmp_path)
        synced = [(12.34, "Line one"), (18.50, "Line two")]
        svc._write_cache("A", "B", "Line one\nLine two", "Zeile eins", synced)
        result = svc._read_cache("A", "B")
        assert result is not None
        original, translated, cached_synced = result
        assert len(cached_synced) == 2
        assert abs(cached_synced[0][0] - 12.34) < 0.02
        assert cached_synced[0][1] == "Line one"
        assert abs(cached_synced[1][0] - 18.50) < 0.02

    def test_parse_synced_lyrics(self, tmp_path: Path) -> None:
        """Parst [MM:SS.xx] Format korrekt."""
        svc = LyricsService(lyrics_dir=tmp_path)
        raw = "[00:12.34] Hello world\n[01:05.00] Second line\n[02:30.99] Last"
        lines = svc._parse_synced_lyrics(raw)
        assert len(lines) == 3
        assert abs(lines[0][0] - 12.34) < 0.01
        assert lines[0][1] == "Hello world"
        assert abs(lines[1][0] - 65.00) < 0.01
        assert abs(lines[2][0] - 150.99) < 0.01

    def test_parse_synced_lyrics_empty_lines_skipped(self, tmp_path: Path) -> None:
        """Leere Zeilen in Synced Lyrics werden uebersprungen."""
        svc = LyricsService(lyrics_dir=tmp_path)
        raw = "[00:05.00] Hello\n[00:10.00] \n[00:15.00] World"
        lines = svc._parse_synced_lyrics(raw)
        assert len(lines) == 2
        assert lines[0][1] == "Hello"
        assert lines[1][1] == "World"
