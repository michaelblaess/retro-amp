"""Tests dafuer, dass der Visualizer seine Farben aus dem Theme bezieht.

Die tragende Zusicherung: **im Bild darf keine Farbe auftauchen, die nicht in
der Palette des eingestellten Themes steht.** Vor der Umstellung waren
Ampelrot, Warngelb und das unbeleuchtete LCD-Segment fest im Malcode - dann
sahen alle 40 Themes an diesen Stellen gleich aus, und dieser Test wird rot.

Ausgenommen sind die Modi BARS und SCOPE: sie faerben absichtlich mit einem
Regenbogen ueber die Baender, unabhaengig vom Theme. Das ist eine
Gestaltungsentscheidung und keine Nachlaessigkeit - deshalb steht sie hier
ausdruecklich als Ausnahme und nicht als stillschweigende Luecke.
"""

from __future__ import annotations

import dataclasses
from typing import cast

import pytest
from rich.text import Text

from retro_amp.domain.models import VisualizerMode
from retro_amp.palette import COLOR_FIELDS, PaletteOverride, SurfacePalette
from retro_amp.themes import surface_palette
from retro_amp.widgets.visualizer import Visualizer

# Nur diese Modi versprechen, ausschliesslich Theme-Farben zu verwenden.
THEMEN_TREUE_MODI = (VisualizerMode.BLOCKS, VisualizerMode.MATRIX, VisualizerMode.LCD)


def _farben(text: Text) -> set[str]:
    """Sammelt alle Hex-Farben aus den Stilangaben eines Rich-Textes."""
    gefunden: set[str] = set()
    for span in text.spans:
        for teil in str(span.style).split():
            if teil.startswith("#"):
                gefunden.add(teil.lower())
    return gefunden


def _palettenfarben(palette: SurfacePalette) -> set[str]:
    return {str(getattr(palette, feld)).lower() for feld in COLOR_FIELDS}


def _gefuellt(mode: VisualizerMode, palette: SurfacePalette, pegel: float = 0.85) -> Text:
    """Baut einen Visualizer mit fester Palette und faehrt ihn hoch."""
    widget = Visualizer(mode=mode)
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
        erlaubt = _palettenfarben(palette)
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
        erlaubt = _palettenfarben(erfunden)
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
        for _ in range(40):
            jetzt["t"] += 1 / 12
            widget._tick()

        assert not _farben(widget.render()), "die Ruhezeile bleibt aus, obwohl alles leer ist"
