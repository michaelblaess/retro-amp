"""Tests fuer MetadataService."""
from __future__ import annotations

from pathlib import Path

import pytest

from retro_amp.domain.models import AudioFormat, AudioTrack
from retro_amp.services.metadata_service import MetadataService


class TestMetadataService:
    def test_read_track(self, mock_metadata_reader) -> None:
        path = Path("/music/song.mp3")
        expected = AudioTrack(path=path, title="Testsong", bitrate_kbps=320)
        mock_metadata_reader.tracks[path] = expected

        service = MetadataService(mock_metadata_reader)
        result = service.read_track(path)

        assert result.title == "Testsong"
        assert result.bitrate_kbps == 320

    def test_read_unknown_track_returns_default(self, mock_metadata_reader) -> None:
        service = MetadataService(mock_metadata_reader)
        result = service.read_track(Path("/music/unknown.mp3"))

        assert result.title == ""
        assert result.bitrate_kbps == 0

    def test_is_audio_file(self, mock_metadata_reader) -> None:
        service = MetadataService(mock_metadata_reader)
        assert service.is_audio_file(Path("/music/song.mp3"))
        assert service.is_audio_file(Path("/music/song.flac"))
        assert service.is_audio_file(Path("/music/song.mod"))
        assert not service.is_audio_file(Path("/music/readme.txt"))
        assert not service.is_audio_file(Path("/music/image.png"))

    def test_scan_nonexistent_directory(self, mock_metadata_reader) -> None:
        service = MetadataService(mock_metadata_reader)
        result = service.scan_directory(Path("/nonexistent"))
        assert result == []
