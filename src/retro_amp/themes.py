"""Re-Export der Themes aus textual-themes Paket.

Alle Themes kommen aus dem eigenstaendigen Paket textual-themes,
damit sie in anderen Projekten wiederverwendbar sind.

Siehe: https://github.com/michaelblaess/textual-themes

LEGACY_THEME_MAP haelt das Mapping von alten Theme-Slugs (vor dem
trademark-safety Rename in textual-themes 0.5) auf die aktuellen
Slugs. So koennen gespeicherte Settings aelterer retro-amp-Versionen
beim Laden migriert werden.
"""
from __future__ import annotations

from textual_themes import (
    RETRO_THEME_NAMES,
    RETRO_THEMES,
    THEME_DISPLAY_NAMES,
    register_all,
)

# ── Default-Theme ──────────────────────────────────────────────────────
DEFAULT_THEME: str = "brotkasten"

# ── Legacy-Slug Migration ─────────────────────────────────────────────
# Mapping fuer Settings-Files aelterer Versionen. Wird beim Laden in
# der App angewendet, sodass User mit gespeichertem "c64" auf das
# umbenannte "brotkasten" landen.
LEGACY_THEME_MAP: dict[str, str] = {
    "c64": "brotkasten",
    "amiga": "boing",
    "atari-st": "gemstone",
    "ibm-terminal": "classic-terminal",
    "nextstep": "next",
    "beos": "bebox",
    "ubuntu": "bunty",
    "macos": "cupertino",
    "windows-xp": "luna",
    "msdos": "commandr",
    "solaris-cde": "motif",
    "os2-warp": "warp",
    "opensuse": "geeko",
    "linux-mint": "minty",
    "red-hat": "crimson",
    "raspberry-pi": "razzy",
    "freebsd": "beastie",
    "tudor": "fifty-eight",
    "goldfinger": "goldfinder",
    "hulk": "hulkula",
    "batman": "flughund",
    "gameboy": "brick",
    "pan-am": "clipper",
    "miami-vice": "miami",
    "martini-racing": "racing",
    "superman": "metropolis",
    "spiderman": "spiderized",
    "gulf-racing": "brotkasten",  # entferntes Theme -> Default
}


def migrate_theme_name(name: str) -> str:
    """Migriert einen alten Theme-Slug auf den aktuellen Namen.

    Bekannte aktuelle Slugs werden unveraendert zurueckgegeben.
    Unbekannte Slugs ebenfalls (Caller entscheidet ueber Fallback).
    """
    if name in RETRO_THEME_NAMES:
        return name
    return LEGACY_THEME_MAP.get(name, name)


__all__ = [
    "DEFAULT_THEME",
    "LEGACY_THEME_MAP",
    "RETRO_THEMES",
    "RETRO_THEME_NAMES",
    "THEME_DISPLAY_NAMES",
    "migrate_theme_name",
    "register_all",
]
