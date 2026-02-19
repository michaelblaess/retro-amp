"""Tests fuer Retro-Themes."""
from __future__ import annotations

from retro_amp.themes import (
    AMIGA_THEME,
    ATARI_ST_THEME,
    BEOS_THEME,
    C64_THEME,
    IBM_TERMINAL_THEME,
    NEXTSTEP_THEME,
    RETRO_THEME_NAMES,
    RETRO_THEMES,
    THEME_DISPLAY_NAMES,
)


class TestThemes:
    def test_six_themes_defined(self) -> None:
        assert len(RETRO_THEMES) == 6
        assert len(RETRO_THEME_NAMES) == 6

    def test_theme_names(self) -> None:
        assert RETRO_THEME_NAMES == [
            "c64", "amiga", "atari-st",
            "ibm-terminal", "nextstep", "beos",
        ]

    def test_c64_is_dark(self) -> None:
        assert C64_THEME.dark is True

    def test_amiga_is_dark(self) -> None:
        assert AMIGA_THEME.dark is True

    def test_atari_is_light(self) -> None:
        assert ATARI_ST_THEME.dark is False

    def test_ibm_terminal_is_dark(self) -> None:
        assert IBM_TERMINAL_THEME.dark is True

    def test_nextstep_is_dark(self) -> None:
        assert NEXTSTEP_THEME.dark is True

    def test_beos_is_dark(self) -> None:
        assert BEOS_THEME.dark is True

    def test_display_names_for_all(self) -> None:
        for name in RETRO_THEME_NAMES:
            assert name in THEME_DISPLAY_NAMES

    def test_themes_have_unique_backgrounds(self) -> None:
        backgrounds = [t.background for t in RETRO_THEMES]
        assert len(set(backgrounds)) == 6
