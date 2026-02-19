"""Re-Export der Themes aus textual-themes Paket.

Alle Themes kommen aus dem eigenstaendigen Paket textual-themes,
damit sie in anderen Projekten wiederverwendbar sind.

Siehe: https://github.com/michaelblaess/textual-themes
"""
from __future__ import annotations

from textual_themes import (
    AMIGA_THEME,
    ATARI_ST_THEME,
    BEOS_THEME,
    C64_THEME,
    IBM_TERMINAL_THEME,
    NEXTSTEP_THEME,
    RETRO_THEME_NAMES,
    RETRO_THEMES,
    THEME_DISPLAY_NAMES,
    register_all,
)

__all__ = [
    "C64_THEME",
    "AMIGA_THEME",
    "ATARI_ST_THEME",
    "IBM_TERMINAL_THEME",
    "NEXTSTEP_THEME",
    "BEOS_THEME",
    "RETRO_THEMES",
    "RETRO_THEME_NAMES",
    "THEME_DISPLAY_NAMES",
    "register_all",
]
