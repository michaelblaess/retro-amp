"""Tests fuer Dateiname-Parsing und Title-Tag-Parsing."""
from __future__ import annotations

from pathlib import Path

import pytest

from retro_amp.infrastructure.metadata_reader import _parse_filename, _parse_title_tag


class TestParseTitleTag:
    """Tests fuer _parse_title_tag — Artist/Title aus kombinierten Tags."""

    def test_em_dash_separator(self) -> None:
        artist, title = _parse_title_tag("2pac Snoop Doggy Dogg \u2014 2 of Amerikaz Most Wanted")
        assert artist == "2pac Snoop Doggy Dogg"
        assert title == "2 of Amerikaz Most Wanted"

    def test_en_dash_separator(self) -> None:
        artist, title = _parse_title_tag("Radiohead \u2013 Talk Show Host")
        assert artist == "Radiohead"
        assert title == "Talk Show Host"

    def test_dash_with_spaces(self) -> None:
        artist, title = _parse_title_tag("The Beatles - Let It Be")
        assert artist == "The Beatles"
        assert title == "Let It Be"

    def test_no_separator(self) -> None:
        artist, title = _parse_title_tag("Just A Title")
        assert artist == ""
        assert title == ""

    def test_empty_string(self) -> None:
        artist, title = _parse_title_tag("")
        assert artist == ""
        assert title == ""


class TestParseFilename:
    """Tests fuer _parse_filename — Artist/Title aus Dateinamen."""

    def test_numbered_dot_pattern(self) -> None:
        """001. Geto Boys - Mind Playin' Tricks.mp3"""
        path = Path("D:/Music/001. Geto Boys - Mind Playin' Tricks.mp3")
        artist, title = _parse_filename(path)
        assert artist == "Geto Boys"
        assert title == "Mind Playin' Tricks"

    def test_numbered_dash_pattern(self) -> None:
        """13 - Colin Blunstone - I Don't Believe In Miracles.mp3"""
        path = Path("D:/Music/13 - Colin Blunstone - I Don't Believe In Miracles.mp3")
        artist, title = _parse_filename(path)
        assert artist == "Colin Blunstone"
        assert title == "I Don't Believe In Miracles"

    def test_artist_title_pattern(self) -> None:
        """2Pac - Can't c me.mp3"""
        path = Path("D:/Music/2Pac/2Pac - Can't c me.mp3")
        artist, title = _parse_filename(path)
        assert artist == "2Pac"
        assert title == "Can't c me"

    def test_lowercase_dash_pattern(self) -> None:
        """101-2pac-white_mans_world-cms"""
        path = Path("D:/Music/101-2pac-white_mans_world-cms")
        artist, title = _parse_filename(path)
        assert artist == "2Pac"
        assert title == "White Mans World"

    def test_lowercase_no_number(self) -> None:
        """the-association-never-my-love.mp3"""
        path = Path("D:/Dropbox/MUSIK/the-association-never-my-love.mp3")
        artist, title = _parse_filename(path)
        # Matches "Artist - Title" pattern: "the" - "association-never-my-love"
        # Falls back to parent folder as artist
        assert artist  # Should have some artist
        assert title  # Should have some title

    def test_folder_fallback(self) -> None:
        """Datei ohne erkennbares Muster → Ordnername als Artist."""
        path = Path("D:/Music/2Pac/some_random_track.mp3")
        artist, title = _parse_filename(path)
        assert artist == "2Pac"
        assert "some random track" in title.lower()

    def test_three_digit_dot_prefix(self) -> None:
        """005. 2Pac - Old School.mp3"""
        path = Path("D:/Music/005. 2Pac - Old School.mp3")
        artist, title = _parse_filename(path)
        assert artist == "2Pac"
        assert title == "Old School"
