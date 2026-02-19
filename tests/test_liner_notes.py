"""Tests fuer LinerNotesService."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from retro_amp.services.liner_notes_service import (
    LinerNotesService,
    _safe_filename,
    _wiki_search,
)


class TestSafeFilename:
    """Tests fuer _safe_filename."""

    def test_normal_name(self) -> None:
        assert _safe_filename("Kraftwerk") == "Kraftwerk"

    def test_special_chars(self) -> None:
        result = _safe_filename('AC/DC: "Back in Black"')
        assert "/" not in result
        assert ":" not in result
        assert '"' not in result

    def test_empty_string(self) -> None:
        assert _safe_filename("") == "unknown"

    def test_long_name_truncated(self) -> None:
        result = _safe_filename("A" * 200)
        assert len(result) <= 100


class TestLinerNotesService:
    """Tests fuer LinerNotesService (mit Cache-Mocking)."""

    def test_empty_artist_returns_empty(self, tmp_path: Path) -> None:
        svc = LinerNotesService(notes_dir=tmp_path)
        assert svc.get_note("") == ""
        assert svc.get_note("   ") == ""

    def test_cache_write_and_read(self, tmp_path: Path) -> None:
        """get_note cached Ergebnisse als Markdown-Dateien."""
        svc = LinerNotesService(notes_dir=tmp_path)

        # Manuell Cache schreiben
        cache_file = tmp_path / "Test_Artist.md"
        cache_file.write_text("# Test Artist\n\nTest content.\n", encoding="utf-8")

        # Sollte aus Cache lesen (kein Netzwerk noetig)
        result = svc.get_note("Test_Artist")
        assert "Test content" in result

    def test_cache_prevents_duplicate_fetch(self, tmp_path: Path) -> None:
        """Zweiter Aufruf liest aus Cache, nicht aus Wikipedia."""
        svc = LinerNotesService(notes_dir=tmp_path)

        # Cache pre-fill
        svc._write_cache("Kraftwerk", "# Kraftwerk\n\nCached.\n")

        with patch.object(svc, "_fetch_from_wikipedia") as mock_fetch:
            result = svc.get_note("Kraftwerk")
            mock_fetch.assert_not_called()
            assert "Cached" in result

    def test_is_relevant_detects_band(self, tmp_path: Path) -> None:
        svc = LinerNotesService(notes_dir=tmp_path)
        assert svc._is_relevant("Kraftwerk (Band)", "Eine deutsche Band", "Kraftwerk")

    def test_is_relevant_rejects_non_music(self, tmp_path: Path) -> None:
        svc = LinerNotesService(notes_dir=tmp_path)
        assert not svc._is_relevant("Kraftwerk", "Technische Anlage zur Stromerzeugung", "Kraftwerk")

    def test_format_note(self, tmp_path: Path) -> None:
        svc = LinerNotesService(notes_dir=tmp_path)
        result = svc._format_note("Kraftwerk", "Kraftwerk (Band)", "Eine Band.", "de")
        assert result.startswith("# Kraftwerk")
        assert "Eine Band." in result
        assert "wikipedia.org" in result

    def test_notes_dir_created(self) -> None:
        """Notes-Verzeichnis wird bei Initialisierung erstellt."""
        with tempfile.TemporaryDirectory() as td:
            notes_path = Path(td) / "subdir" / "notes"
            svc = LinerNotesService(notes_dir=notes_path)
            assert notes_path.is_dir()
