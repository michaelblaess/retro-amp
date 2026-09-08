"""Tests dafuer, dass der Visualizer seine Farben aus dem Theme bezieht.

Die tragende Zusicherung: **im Bild darf keine Farbe auftauchen, die sich
nicht aus der Palette des eingestellten Themes ableiten laesst.** Das sind die
Palettenfelder selbst plus der Verlauf, den BARS und SCOPE zwischen den drei
Pegelstufen aufspannen. Vor der Umstellung waren
Ampelrot, Warngelb und das unbeleuchtete LCD-Segment fest im Malcode - dann
sahen alle 40 Themes an diesen Stellen gleich aus, und dieser Test wird rot.

BARS und SCOPE koennen wahlweise einen Regenbogen ueber die Baender legen.
Das ist die einzige Ausnahme, sie ist abschaltbar und steht in den
Einstellungen - `TestRegenbogen` haelt beide Seiten fest.
"""

from __future__ import annotations

import dataclasses
from typing import cast

import pytest
from rich.text import Text

from retro_amp.domain.models import VisualizerMode
from retro_amp.palette import COLOR_FIELDS, PaletteOverride, SurfacePalette, gradient
from retro_amp.themes import surface_palette
from retro_amp.widgets.visualizer import Visualizer

# Mit ausgeschaltetem Regenbogen versprechen ALLE Modi, ausschliesslich
# Theme-Farben zu verwenden.
THEMEN_TREUE_MODI = tuple(VisualizerMode)
# Nur diese beiden kennen ueberhaupt einen Regenbogen.
REGENBOGEN_MODI = (VisualizerMode.BARS, VisualizerMode.SCOPE)


def _farben(text: Text) -> set[str]:
    """Sammelt alle Hex-Farben aus den Stilangaben eines Rich-Textes."""
    gefunden: set[str] = set()
    for span in text.spans:
        for teil in str(span.style).split():
            if teil.startswith("#"):
                gefunden.add(teil.lower())
    return gefunden


def _palettenfarben(palette: SurfacePalette) -> set[str]:
    """Die Felder der Palette selbst."""
    return {str(getattr(palette, feld)).lower() for feld in COLOR_FIELDS}


def _erlaubte_farben(palette: SurfacePalette) -> set[str]:
    """Alle Farben, die aus dieser Palette ableitbar sind.

    Das sind die Palettenfelder plus der Bandverlauf, den BARS und SCOPE
    zwischen den drei Pegelstufen aufspannen. Die Zwischenwerte des Verlaufs
    stehen in keinem Feld, stammen aber ausschliesslich aus der Palette -
    eine fest verdrahtete Farbe faellt trotzdem auf.
    """
    verlauf = gradient((palette.vis_low, palette.vis_mid, palette.vis_high), Visualizer.NUM_BARS)
    return _palettenfarben(palette) | {farbe.lower() for farbe in verlauf}


def _gefuellt(
    mode: VisualizerMode,
    palette: SurfacePalette,
    pegel: float = 0.85,
    rainbow: bool = False,
) -> Text:
    """Baut einen Visualizer mit fester Palette und faehrt ihn hoch."""
    widget = Visualizer(mode=mode, rainbow=rainbow)
    widget._palette = palette
    widget._rebuild_band_colors()
    widget.palette = lambda: palette  # type: ignore[method-assign]
    widget.set_spectrum_source(lambda: [pegel] * Visualizer.NUM_BARS)

    jetzt = {"t": 0.0}
    widget._clock = lambda: jetzt["t"]
    widget._active = True
    for _ in range(30):
        jetzt["t"] += 1 / 12
        widget._tick()
    return widget.render()


class TestFarbenKommenAusDemTheme:
    @pytest.mark.parametrize("mode", THEMEN_TREUE_MODI)
    def test_keine_fremde_farbe_im_bild(self, mode: VisualizerMode) -> None:
        palette = surface_palette("brotkasten")
        erlaubt = _erlaubte_farben(palette)
        benutzt = _farben(_gefuellt(mode, palette))

        assert benutzt, f"{mode.value} zeichnet gar keine Farbe"
        fremd = benutzt - erlaubt
        assert not fremd, f"{mode.value} verwendet Farben ausserhalb der Theme-Palette: {sorted(fremd)}"

    @pytest.mark.parametrize("mode", THEMEN_TREUE_MODI)
    def test_zwei_themes_ergeben_zwei_bilder(self, mode: VisualizerMode) -> None:
        # brotkasten ist blau-violett, classic-terminal phosphorgruen. Wenn die
        # Farben aus dem Malcode kaemen, waeren beide Mengen identisch.
        eins = _farben(_gefuellt(mode, surface_palette("brotkasten")))
        zwei = _farben(_gefuellt(mode, surface_palette("classic-terminal")))
        assert eins != zwei, f"{mode.value} sieht in beiden Themes gleich aus"

    def test_kuenstliche_palette_schlaegt_voll_durch(self) -> None:
        # Die schaerfste Fassung der Zusicherung: eine Palette aus lauter
        # erfundenen Farben. Jede Farbe im Bild muss aus ihr stammen.
        echte = surface_palette("brotkasten")
        # Ueber den getypten Ausnahmetyp, damit mypy die Feldnamen und die
        # Werttypen mitprueft statt einen losen Splat durchzuwinken.
        ersatz = cast(
            "PaletteOverride",
            {feld: f"#{index * 7 + 16:02x}00{index * 11 + 32:02x}" for index, feld in enumerate(COLOR_FIELDS)},
        )
        erfunden = dataclasses.replace(echte, **ersatz)
        erlaubt = _erlaubte_farben(erfunden)
        for mode in THEMEN_TREUE_MODI:
            benutzt = _farben(_gefuellt(mode, erfunden))
            assert benutzt <= erlaubt, f"{mode.value} bringt eigene Farben mit: {sorted(benutzt - erlaubt)}"


class TestAusklingenIstSichtbar:
    """Der Abfall nach dem Anhalten muss auch gezeichnet werden."""

    def test_bild_zeigt_waehrend_des_ausklingens_noch_balken(self) -> None:
        palette = surface_palette("brotkasten")
        widget = Visualizer(mode=VisualizerMode.BLOCKS)
        widget.palette = lambda: palette  # type: ignore[method-assign]
        widget.set_spectrum_source(lambda: [1.0] * Visualizer.NUM_BARS)

        jetzt = {"t": 0.0}
        widget._clock = lambda: jetzt["t"]
        widget._active = True
        for _ in range(30):
            jetzt["t"] += 1 / 12
            widget._tick()

        widget.stop()
        jetzt["t"] += 1 / 12
        widget._tick()

        assert _farben(widget.render()), (
            "nach dem Anhalten wird sofort die Ruhezeile gezeigt, der Pegel klingt unsichtbar aus"
        )

    def test_ruhezeile_erst_wenn_nichts_mehr_da_ist(self) -> None:
        palette = surface_palette("brotkasten")
        widget = Visualizer(mode=VisualizerMode.BLOCKS)
        widget.palette = lambda: palette  # type: ignore[method-assign]
        widget.set_spectrum_source(lambda: [1.0] * Visualizer.NUM_BARS)

        jetzt = {"t": 0.0}
        widget._clock = lambda: jetzt["t"]
        widget._active = True
        for _ in range(30):
            jetzt["t"] += 1 / 12
            widget._tick()

        widget.stop()
        # Bilderzahl aus der Ausklingdauer, nicht geraten - sie haengt an der
        # langsamsten Abfallrate und aendert sich mit ihr.
        for _ in range(int(widget._meter.ring_out_seconds * 12) + 2):
            jetzt["t"] += 1 / 12
            widget._tick()

        assert not _farben(widget.render()), "die Ruhezeile bleibt aus, obwohl alles leer ist"


class TestRegenbogen:
    """Die einzige Ausnahme von der Theme-Treue - und sie ist abschaltbar."""

    @pytest.mark.parametrize("mode", REGENBOGEN_MODI)
    def test_eingeschaltet_bringt_fremde_farben(self, mode: VisualizerMode) -> None:
        palette = surface_palette("hercules")
        erlaubt = _erlaubte_farben(palette)
        benutzt = _farben(_gefuellt(mode, palette, rainbow=True))
        assert benutzt - erlaubt, (
            f"{mode.value} zeigt mit eingeschaltetem Regenbogen nur Theme-Farben - dann greift der Schalter nicht"
        )

    @pytest.mark.parametrize("mode", REGENBOGEN_MODI)
    def test_ausgeschaltet_bleibt_beim_theme(self, mode: VisualizerMode) -> None:
        palette = surface_palette("hercules")
        erlaubt = _erlaubte_farben(palette)
        benutzt = _farben(_gefuellt(mode, palette, rainbow=False))
        assert benutzt <= erlaubt, f"fremde Farben: {sorted(benutzt - erlaubt)}"

    def test_schalter_wirkt_zur_laufzeit(self) -> None:
        widget = Visualizer(mode=VisualizerMode.BARS)
        widget._palette = surface_palette("hercules")
        widget._rebuild_band_colors()
        theme_farben = list(widget._colors)

        widget.set_rainbow(True)
        assert widget._colors != theme_farben

        widget.set_rainbow(False)
        assert widget._colors == theme_farben

    def test_ohne_regenbogen_verlaufen_die_baender(self) -> None:
        # Erstes und letztes Band sind die beiden aeusseren Pegelfarben.
        palette = surface_palette("hercules")
        widget = Visualizer(mode=VisualizerMode.BARS)
        widget._palette = palette
        widget._rebuild_band_colors()
        assert widget._colors[0].lower() == palette.vis_low.lower()
        assert widget._colors[-1].lower() == palette.vis_high.lower()
