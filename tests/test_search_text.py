"""Tests fuer den akzent- und sonderzeichenfesten Suchvergleich."""

from __future__ import annotations

import pytest

from retro_amp.domain.search_text import find_spans, fold, matches


class TestMatches:
    @pytest.mark.parametrize(
        ("name", "query"),
        [
            ("03 - Eternità.mp3", "Eternita"),  # der gemeldete Fall
            ("03 - Eternita.mp3", "Eternità"),  # und umgekehrt
            ("Ornella Vanoni - Oggi Le Canto Così Vol.1", "cosi vol 1"),
            ("Grüner Blitz.flac", "gruner"),
            ("Grüner Blitz.flac", "gruener"),
            ("Grüner Blitz.flac", "GRÜNER"),
            ("Straße.mp3", "strasse"),
            ("Mötley Crüe", "motley crue"),
            ("Don't Stop Me Now.mp3", "dont stop"),
            ("Don’t Stop Me Now.mp3", "don't stop"),
            ("AC/DC - Thunderstruck.mp3", "ac dc"),
            ("Guns_N_Roses-Paradise.City.mp3", "paradise city"),
            ("Sigur Rós - Hoppípolla", "hoppipolla"),
            ("Beyoncé - Halo", "beyonce  halo"),
        ],
    )
    def test_finds(self, name: str, query: str) -> None:
        assert matches(name, query)

    @pytest.mark.parametrize(
        ("name", "query"),
        [
            ("Eternità.mp3", "eterno"),
            ("Grüner Blitz.flac", "gruenr"),
            ("Irgendwas.mp3", "!!!"),  # nur Satzzeichen trifft nichts
            ("Irgendwas.mp3", ""),
        ],
    )
    def test_does_not_find(self, name: str, query: str) -> None:
        assert not matches(name, query)


class TestFindSpans:
    def test_span_points_at_accented_original(self) -> None:
        name = "03 - Eternità.mp3"
        spans = find_spans(name, "eternita")
        assert [name[a:b] for a, b in spans] == ["Eternità"]

    def test_span_survives_length_change(self) -> None:
        # "ß" wird zu "ss" - der Treffer muss trotzdem genau "Straße" markieren.
        name = "Die Straße.mp3"
        assert [name[a:b] for a, b in find_spans(name, "strasse")] == ["Straße"]

    def test_german_spelling_marks_umlaut(self) -> None:
        name = "Grüner Blitz"
        assert [name[a:b] for a, b in find_spans(name, "gruen")] == ["Grün"]

    def test_all_occurrences(self) -> None:
        name = "Là là land"
        assert [name[a:b] for a, b in find_spans(name, "la")] == ["Là", "là", "la"]


class TestFold:
    def test_collapses_separators(self) -> None:
        assert fold("  A.-_B  ").text == "a b"

    def test_origins_match_length(self) -> None:
        folded = fold("Straße")
        assert len(folded.text) == len(folded.origins)
