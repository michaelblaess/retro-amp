"""Erweiterte Farbpalette fuer selbstgezeichnete Flaechen.

Die 40 Themes aus `textual-themes` tragen elf Grundfarben. Fuer Visualizer,
LCD-Anzeige, Transportleiste und Positionsleiste reicht das nicht - dort
entstehen sonst abgeleitete Zufallsfarben, die je Theme anders danebenliegen.

Dieses Modul leitet aus den elf Grundfarben einen vollstaendigen Satz
Flaechenfarben ab und laesst je Theme gezielte Ausnahmen zu.

WICHTIG: Dieses Modul ist oberflaechenfrei. Es importiert weder `textual` noch
sonst ein UI-Paket und arbeitet ausschliesslich auf Hex-Strings. Der Adapter
von einem `textual.theme.Theme` auf `BasePalette` steht in `themes.py`. Ein
Test haelt die Freiheit fest (`tests/test_palette.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import TypedDict

# ── Hilfsfunktionen fuer Farben (bewusst ohne Fremdpaket) ─────────────


def _to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Zerlegt '#RRGGBB' in drei Kanaele 0..255."""
    value = hex_color.strip()
    if not value.startswith("#") or len(value) != 7:
        raise ValueError(f"Kein #RRGGBB-Wert: {hex_color!r}")
    return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))


def _to_hex(rgb: tuple[int, int, int]) -> str:
    """Setzt drei Kanaele wieder zu '#RRGGBB' zusammen."""
    r, g, b = (max(0, min(255, round(c))) for c in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def blend(base: str, other: str, amount: float) -> str:
    """Mischt `amount` (0..1) von `other` in `base`."""
    weight = max(0.0, min(1.0, amount))
    a = _to_rgb(base)
    b = _to_rgb(other)
    return _to_hex(tuple(a[i] + (b[i] - a[i]) * weight for i in range(3)))  # type: ignore[arg-type]


def relative_luminance(hex_color: str) -> float:
    """Relative Helligkeit nach WCAG 2.1 (0.0 schwarz bis 1.0 weiss)."""
    channels = []
    for raw in _to_rgb(hex_color):
        c = raw / 255.0
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(first: str, second: str) -> float:
    """Kontrastverhaeltnis nach WCAG 2.1, zwischen 1.0 und 21.0."""
    a = relative_luminance(first)
    b = relative_luminance(second)
    heller, dunkler = (a, b) if a >= b else (b, a)
    return (heller + 0.05) / (dunkler + 0.05)


def ensure_contrast(color: str, background: str, minimum: float, *, steps: int = 24) -> str:
    """Hellt oder dunkelt `color`, bis der Kontrast zu `background` reicht.

    Gemischt wird zum hellen oder dunklen Ende, je nachdem, wo mehr Luft ist.
    Der Farbton bleibt dabei weitgehend erhalten. Ist das Ziel selbst mit
    reinem Weiss oder Schwarz nicht erreichbar, kommt der bestmoegliche Wert
    zurueck - dann stimmt der Untergrund nicht, und das soll ein Test finden.
    """
    if contrast_ratio(color, background) >= minimum:
        return color
    ziel = "#FFFFFF" if relative_luminance(background) < 0.5 else "#000000"
    kandidat = ziel
    for schritt in range(1, steps + 1):
        kandidat = blend(color, ziel, schritt / steps)
        if contrast_ratio(kandidat, background) >= minimum:
            return kandidat
    return kandidat


# ── Eingang: die elf Grundfarben eines Themes ─────────────────────────


@dataclass(frozen=True, slots=True)
class BasePalette:
    """Die elf Grundfarben eines Themes plus die Hell-Dunkel-Angabe.

    Bewusst als eigener Typ und nicht als `textual.theme.Theme`, damit dieses
    Modul ohne Textual auskommt und eine spaetere Qt-Fassung dieselbe
    Ableitung nutzen kann.
    """

    name: str
    primary: str
    secondary: str
    accent: str
    foreground: str
    background: str
    surface: str
    panel: str
    boost: str
    warning: str
    error: str
    success: str
    dark: bool


# ── Ausgang: die abgeleiteten Flaechenfarben ──────────────────────────


@dataclass(frozen=True, slots=True)
class SurfacePalette:
    """Vollstaendiger Satz Farben fuer selbstgezeichnete Flaechen.

    Vollstaendigkeit ist hier durch den Typ garantiert und nicht durch eine
    Pruefung zur Laufzeit: eine Instanz ohne Feld gibt es nicht. Das ist die
    Python-Entsprechung zu Audacitys Regel, dass alle Theme-Dateien denselben
    Schluesselsatz tragen muessen.
    """

    # Visualizer
    vis_low: str
    vis_mid: str
    vis_high: str
    vis_peak: str
    vis_background: str
    vis_grid: str

    # LCD-artige Anzeigen (Spielzeit, Bitrate, Frequenz)
    lcd_foreground: str
    lcd_background: str
    lcd_dim: str

    # Transportknoepfe
    transport_normal: str
    transport_hover: str
    transport_active: str

    # Positions- und Fortschrittsleiste
    progress_trough: str
    progress_played: str
    progress_handle: str

    # Allgemeine Flaechen
    divider: str
    header: str
    selection: str
    focus_ring: str

    # Zustaende ueber Deckkraft statt ueber eigene Farben (Muster aus
    # Audacitys FlatButton: zwei Farben, drei Deckkraftwerte).
    opacity_normal: float
    opacity_hover: float
    opacity_active: float


COLOR_FIELDS: tuple[str, ...] = tuple(f.name for f in fields(SurfacePalette) if not f.name.startswith("opacity_"))
OPACITY_FIELDS: tuple[str, ...] = tuple(f.name for f in fields(SurfacePalette) if f.name.startswith("opacity_"))


# ── Ableitung ─────────────────────────────────────────────────────────

# Zielkontrast der beleuchteten LCD-Ziffer gegen ihren Untergrund. 4.5:1 ist
# die WCAG-Schwelle fuer Fliesstext.
LCD_ZIELKONTRAST = 4.5


def derive(base: BasePalette) -> SurfacePalette:
    """Leitet die Flaechenfarben aus den elf Grundfarben ab.

    Die Regeln folgen der Absicht des Themes statt einer festen DAW-Optik:
    ein Bernstein-Monitor bekommt einen Bernstein-Pegel, weil `success`,
    `warning` und `error` dort bernsteinfarben sind. Wo eine Regel danebenliegt,
    greift `OVERRIDES`.
    """
    # Auf dunklem Grund vertieft man mit Schwarz, auf hellem mit der Schrift.
    vertiefung = "#000000" if base.dark else base.foreground
    vertiefungsanteil = 0.30 if base.dark else 0.08

    lcd_background = blend(base.background, vertiefung, vertiefungsanteil)

    # Die Signaturfarbe vieler Themes ist dunkel (beastie, flughund, luna) und
    # verschwindet auf dem vertieften Untergrund. Eine beleuchtete Ziffer wird
    # deshalb so weit aufgehellt, bis sie lesbar ist. Das Ziel liegt bewusst
    # ueber der Schwelle, gegen die der Test prueft - so bleibt der Test eine
    # unabhaengige Pruefung und nicht die Wiederholung dieser Konstante.
    lcd_foreground = ensure_contrast(base.primary, lcd_background, LCD_ZIELKONTRAST)

    return SurfacePalette(
        vis_low=base.success,
        vis_mid=base.warning,
        vis_high=base.error,
        vis_peak=base.boost,
        vis_background=base.panel,
        vis_grid=blend(base.panel, base.foreground, 0.15),
        lcd_foreground=lcd_foreground,
        lcd_background=lcd_background,
        # Die unbeleuchtete Ziffer ist eine gedaempfte Fassung der beleuchteten,
        # nicht eine eigene Farbe - so verhaelt sich ein echtes Display.
        lcd_dim=blend(lcd_background, lcd_foreground, 0.30),
        transport_normal=base.surface,
        transport_hover=blend(base.surface, base.foreground, 0.12),
        transport_active=base.accent,
        progress_trough=blend(base.panel, base.foreground, 0.10),
        progress_played=base.accent,
        progress_handle=base.boost,
        divider=blend(base.background, base.foreground, 0.20),
        header=base.panel,
        selection=blend(base.background, base.primary, 0.30),
        focus_ring=base.accent,
        opacity_normal=1.0,
        opacity_hover=0.75,
        opacity_active=0.55,
    )


# ── Ausnahmen je Theme ────────────────────────────────────────────────
#
# Nur eintragen, was die Regel nachweislich falsch macht - belegt durch einen
# fehlgeschlagenen Test in tests/test_palette.py, nicht nach Gefuehl. Der
# Schluessel ist der Theme-Name, der Wert ein Teilsatz der Felder.


class PaletteOverride(TypedDict, total=False):
    """Teilsatz von `SurfacePalette` fuer eine Ausnahme.

    Bewusst als TypedDict und nicht als lose Abbildung: so faellt ein
    Tippfehler im Feldnamen oder ein falscher Werttyp schon bei mypy auf und
    nicht erst zur Laufzeit. Die Feldliste wird von einem Test gegen
    `SurfacePalette` gehalten, damit sie nicht auseinanderlaeuft.
    """

    vis_low: str
    vis_mid: str
    vis_high: str
    vis_peak: str
    vis_background: str
    vis_grid: str
    lcd_foreground: str
    lcd_background: str
    lcd_dim: str
    transport_normal: str
    transport_hover: str
    transport_active: str
    progress_trough: str
    progress_played: str
    progress_handle: str
    divider: str
    header: str
    selection: str
    focus_ring: str
    opacity_normal: float
    opacity_hover: float
    opacity_active: float


OVERRIDES: dict[str, PaletteOverride] = {}


def palette_for(base: BasePalette) -> SurfacePalette:
    """Liefert die Flaechenfarben eines Themes inklusive seiner Ausnahmen."""
    abgeleitet = derive(base)
    ausnahmen = OVERRIDES.get(base.name)
    return replace(abgeleitet, **ausnahmen) if ausnahmen else abgeleitet
