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

from textual.theme import Theme
from textual_themes import (
    RETRO_THEME_NAMES,
    RETRO_THEMES,
    THEME_DISPLAY_NAMES,
    register_all,
)

from retro_amp.palette import COLOR_FIELDS, OPACITY_FIELDS, BasePalette, SurfacePalette, palette_for

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


# ── Bruecke zur oberflaechenfreien Palette ────────────────────────────


def base_palette(theme: Theme) -> BasePalette:
    """Uebersetzt ein Textual-Theme in die oberflaechenfreie Grundpalette.

    Das ist der einzige Ort, an dem Textual-Typen auf die eigene Palette
    treffen. `retro_amp.palette` selbst kennt Textual nicht.
    """
    return BasePalette(
        name=theme.name,
        primary=theme.primary,
        secondary=theme.secondary or theme.primary,
        accent=theme.accent or theme.primary,
        foreground=theme.foreground or "#FFFFFF",
        background=theme.background or "#000000",
        surface=theme.surface or theme.background or "#000000",
        panel=theme.panel or theme.surface or "#000000",
        boost=theme.boost or theme.accent or theme.primary,
        warning=theme.warning or theme.primary,
        error=theme.error or theme.primary,
        success=theme.success or theme.primary,
        dark=theme.dark,
    )


def surface_palette(name: str) -> SurfacePalette:
    """Liefert die Flaechenfarben zu einem Theme-Namen.

    Unbekannte Namen werden ueber `migrate_theme_name` gehoben und fallen
    sonst auf das Standard-Theme zurueck - eine Oberflaeche darf an einer
    verirrten Einstellung nicht scheitern.
    """
    gehoben = migrate_theme_name(name)
    theme = _THEMES_BY_NAME.get(gehoben) or _THEMES_BY_NAME[DEFAULT_THEME]
    return palette_for(base_palette(theme))


_THEMES_BY_NAME: dict[str, Theme] = {theme.name: theme for theme in RETRO_THEMES}

# ── Bruecke in Textuals Stylesheets ───────────────────────────────────

# Praefix aller eigenen CSS-Variablen. Textuals eigene heissen $accent,
# $panel, $text-muted und so weiter - das Praefix haelt die abgeleiteten
# Werte davon getrennt und macht im Stylesheet sofort sichtbar, woher eine
# Farbe kommt.
CSS_PRAEFIX = "ra-"


def css_variables(palette: SurfacePalette) -> dict[str, str]:
    """Alle Felder der Flaechenpalette als CSS-Variablen.

    Die Namen entstehen mechanisch aus den Feldnamen (`vis_low` wird zu
    `ra-vis-low`), damit kein Feld beim Ergaenzen vergessen werden kann.
    Deckkraftwerte kommen als Prozentangabe heraus, weil Textual sie in
    dieser Form hinter einer Farbe erwartet (`background: $ra-selection 75%`).
    """
    werte: dict[str, str] = {}
    for feld in COLOR_FIELDS:
        werte[CSS_PRAEFIX + feld.replace("_", "-")] = str(getattr(palette, feld))
    for feld in OPACITY_FIELDS:
        anteil = float(getattr(palette, feld))
        werte[CSS_PRAEFIX + feld.replace("_", "-")] = f"{round(anteil * 100)}%"
    return werte


__all__ = [
    "DEFAULT_THEME",
    "LEGACY_THEME_MAP",
    "RETRO_THEMES",
    "RETRO_THEME_NAMES",
    "THEME_DISPLAY_NAMES",
    "CSS_PRAEFIX",
    "base_palette",
    "css_variables",
    "migrate_theme_name",
    "register_all",
    "surface_palette",
]
