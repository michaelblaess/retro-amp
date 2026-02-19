"""Tests fuer MetadataReader — Tracker-Header-Parsing."""
from __future__ import annotations

import struct
import tempfile
from pathlib import Path

import pytest

from retro_amp.infrastructure.metadata_reader import (
    MutagenMetadataReader,
    _read_header_title,
    _read_sid_artist,
)


class TestTrackerHeaders:
    """Tests fuer MOD/S3M/XM Header-Parsing."""

    def test_mod_title(self, tmp_path: Path) -> None:
        """MOD: Titel in Bytes 0-19."""
        mod_file = tmp_path / "test.mod"
        title = b"Hello Module\x00\x00\x00\x00\x00\x00\x00\x00"
        mod_file.write_bytes(title + b"\x00" * 1064)
        assert _read_header_title(mod_file) == "Hello Module"

    def test_s3m_title(self, tmp_path: Path) -> None:
        """S3M: Titel in Bytes 0-27."""
        s3m_file = tmp_path / "test.s3m"
        title = b"The Muppet Show Theme\x00\x00\x00\x00\x00\x00\x00"
        s3m_file.write_bytes(title + b"\x00" * 100)
        assert _read_header_title(s3m_file) == "The Muppet Show Theme"

    def test_xm_title(self, tmp_path: Path) -> None:
        """XM: Titel in Bytes 17-36 (nach 'Extended Module: ')."""
        xm_file = tmp_path / "test.xm"
        header = b"Extended Module: "
        title = b"Cool XM Track\x00\x00\x00\x00\x00\x00\x00"
        xm_file.write_bytes(header + title + b"\x00" * 100)
        assert _read_header_title(xm_file) == "Cool XM Track"

    def test_empty_mod_title(self, tmp_path: Path) -> None:
        """MOD mit leerem Titel."""
        mod_file = tmp_path / "test.mod"
        mod_file.write_bytes(b"\x00" * 1084)
        assert _read_header_title(mod_file) == ""

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Nicht existierende Datei gibt leeren String."""
        assert _read_header_title(tmp_path / "nope.mod") == ""


class TestSidHeaders:
    """Tests fuer SID Header-Parsing."""

    def test_sid_title(self, tmp_path: Path) -> None:
        """SID: Name in Bytes 0x16-0x35."""
        sid_file = tmp_path / "test.sid"
        header = b"PSID" + b"\x00" * 18  # 0x00-0x15 (22 Bytes)
        name = b"Last Ninja\x00" + b"\x00" * 21  # 0x16-0x35 (32 Bytes)
        author = b"Ben Daglish\x00" + b"\x00" * 20  # 0x36-0x55 (32 Bytes)
        sid_file.write_bytes(header + name + author + b"\x00" * 100)
        assert _read_header_title(sid_file) == "Last Ninja"

    def test_sid_artist(self, tmp_path: Path) -> None:
        """SID: Author in Bytes 0x36-0x55."""
        sid_file = tmp_path / "test.sid"
        header = b"PSID" + b"\x00" * 18  # 0x00-0x15
        name = b"Last Ninja\x00" + b"\x00" * 21  # 0x16-0x35
        author = b"Ben Daglish\x00" + b"\x00" * 20  # 0x36-0x55
        sid_file.write_bytes(header + name + author + b"\x00" * 100)
        assert _read_sid_artist(sid_file) == "Ben Daglish"


class TestMutagenReaderTrackerFormats:
    """Tests fuer MutagenMetadataReader mit Tracker-Formaten."""

    def test_mod_returns_track_with_title(self, tmp_path: Path) -> None:
        """MutagenMetadataReader liest MOD-Titel."""
        mod_file = tmp_path / "test.mod"
        title = b"acid jazz\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        mod_file.write_bytes(title + b"\x00" * 1064)

        reader = MutagenMetadataReader()
        track = reader.read(mod_file)
        assert track.title == "acid jazz"
        assert track.path == mod_file

    def test_sid_returns_title_and_artist(self, tmp_path: Path) -> None:
        """MutagenMetadataReader liest SID-Titel und Artist."""
        sid_file = tmp_path / "test.sid"
        header = b"PSID" + b"\x00" * 18
        name = b"Commando\x00" + b"\x00" * 23
        author = b"Rob Hubbard\x00" + b"\x00" * 20
        sid_file.write_bytes(header + name + author + b"\x00" * 100)

        reader = MutagenMetadataReader()
        track = reader.read(sid_file)
        assert track.title == "Commando"
        assert track.artist == "Rob Hubbard"
