"""Zugriff auf die Flaechenfarben des eingestellten Themes.

Jedes selbstgezeichnete Widget braucht dieselbe Handreichung: die Palette zum
aktuellen Theme holen, das Ergebnis behalten, bis das Theme wechselt, und ohne
laufende Anwendung nicht abstuerzen. Das steht hier einmal statt in jedem
Widget erneut.

Der Grund fuers Zwischenspeichern ist messbar: `derive` rechnet je Aufruf
Kontrastverhaeltnisse aus, und der Visualizer zeichnet zwoelfmal je Sekunde.
"""

from __future__ import annotations

from ..palette import SurfacePalette
from ..themes import surface_palette

# Rueckfall ohne laufende Anwendung - das Standard-Theme. Ein eingefrorener
# Datensatz, das Teilen zwischen allen Widgets ist deshalb unbedenklich.
_FALLBACK = surface_palette("")


class PaletteSource:
    """Mischklasse: liefert `palette()` und zieht bei Themewechsel nach.

    Vor `Widget` in die Basisklassenliste schreiben. Eigene `__init__` braucht
    es nicht - die Felder unten sind Klassenvorgaben und werden erst beim
    ersten Wechsel je Instanz ueberschrieben.
    """

    _palette_name: str = ""
    _palette: SurfacePalette = _FALLBACK

    def palette(self) -> SurfacePalette:
        """Flaechenfarben des aktuell eingestellten Themes."""
        try:
            name = str(self.app.theme)  # type: ignore[attr-defined]
        except Exception:
            name = ""
        if name != self._palette_name:
            self._palette_name = name
            self._palette = surface_palette(name)
            self._palette_changed()
        return self._palette

    def _palette_changed(self) -> None:
        """Haken fuer Ableitungen, die auf einen Themewechsel reagieren.

        Der Visualizer baut hier seinen Bandverlauf neu auf. Die Vorgabe tut
        nichts - wer nur Farben liest, braucht nichts zu tun.
        """
