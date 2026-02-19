"""Equalizer-Visualizer Widget — Spektralanalyse mit Retro-Charme."""
from __future__ import annotations

import random
from collections.abc import Callable

from rich.text import Text

from textual.widget import Widget


# Unicode-Blockzeichen fuer verschiedene Fuellhoehen (0=leer, 8=voll)
_BLOCKS = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

# Peak-Marker (schwebendes Strichlein ueber dem Balken)
_PEAK_CHAR = "▔"

# Anzahl Frames die ein Peak oben haelt bevor er faellt
_PEAK_HOLD_FRAMES = 3
_PEAK_DECAY = 2  # Stufen pro Tick beim Fallen

# Render-Zeilen
_NUM_ROWS = 3
_STEPS_PER_ROW = len(_BLOCKS) - 1  # 8
_MAX_LEVEL = _NUM_ROWS * _STEPS_PER_ROW  # 24


def _spectral_color(band_index: int, num_bands: int) -> str:
    """Gibt eine RGB-Farbe fuer ein Frequenzband zurueck (Spektralverlauf).

    Niedrig (Bass) = Rot → Orange → Gelb → Gruen → Cyan → Blau (Hoehen).
    """
    t = band_index / max(num_bands - 1, 1)

    if t < 0.25:
        # Rot → Gelb
        r, g, b = 255, int(255 * (t / 0.25)), 0
    elif t < 0.5:
        # Gelb → Gruen
        r, g, b = int(255 * (1.0 - (t - 0.25) / 0.25)), 255, 0
    elif t < 0.75:
        # Gruen → Cyan
        r, g, b = 0, 255, int(255 * ((t - 0.5) / 0.25))
    else:
        # Cyan → Blau
        r, g, b = 0, int(255 * (1.0 - (t - 0.75) / 0.25)), 255

    return f"#{r:02x}{g:02x}{b:02x}"


class Visualizer(Widget):
    """Equalizer-Visualizer mit Spektralfarben und Peak-Hold-Effekt.

    Nutzt entweder echte FFT-Daten (via spectrum_source Callback)
    oder simulierte Zufallswerte als Fallback.
    """

    DEFAULT_CSS = """
    Visualizer {
        height: 3;
        padding: 0 1;
        border-top: solid $accent;
    }
    """

    NUM_BARS = 32

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._bars: list[int] = [0] * self.NUM_BARS
        self._peaks: list[int] = [0] * self.NUM_BARS
        self._peak_hold: list[int] = [0] * self.NUM_BARS
        self._active = False
        self._timer_handle: object | None = None
        self._spectrum_source: Callable[[], list[float]] | None = None

        # Farben vorberechnen
        self._colors = [
            _spectral_color(i, self.NUM_BARS) for i in range(self.NUM_BARS)
        ]

    def set_spectrum_source(
        self, source: Callable[[], list[float]] | None
    ) -> None:
        """Setzt die Datenquelle fuer echte Spektraldaten.

        Die Callback-Funktion gibt eine Liste mit NUM_BARS float-Werten
        (0.0–1.0) zurueck. Wenn None, werden Zufallswerte verwendet.
        """
        self._spectrum_source = source

    def start(self) -> None:
        """Startet die Animation."""
        self._active = True
        if self._timer_handle is None:
            self._timer_handle = self.set_interval(1 / 12, self._tick)

    def stop(self) -> None:
        """Stoppt die Animation und setzt Balken zurueck."""
        self._active = False
        self._bars = [0] * self.NUM_BARS
        self._peaks = [0] * self.NUM_BARS
        self._peak_hold = [0] * self.NUM_BARS
        self.refresh()

    def _tick(self) -> None:
        """Animation-Tick: Balken bewegen sich zu Zielwerten."""
        if not self._active:
            return

        # Band-Werte holen (echt oder fake)
        band_values = self._get_band_values()

        # Balken und Peaks aktualisieren
        for i in range(self.NUM_BARS):
            target = int(band_values[i] * _MAX_LEVEL)

            # Balken: schnell hoch, mittel runter
            if target > self._bars[i]:
                self._bars[i] = min(self._bars[i] + 3, target)
            else:
                self._bars[i] = max(self._bars[i] - 2, 0)

            # Peaks: halten, dann langsam fallen
            if self._bars[i] >= self._peaks[i]:
                self._peaks[i] = self._bars[i]
                self._peak_hold[i] = _PEAK_HOLD_FRAMES
            elif self._peak_hold[i] > 0:
                self._peak_hold[i] -= 1
            else:
                self._peaks[i] = max(self._peaks[i] - _PEAK_DECAY, 0)

        self.refresh()

    def _get_band_values(self) -> list[float]:
        """Holt Band-Werte aus der Datenquelle oder generiert Fake-Werte."""
        if self._spectrum_source:
            try:
                bands = self._spectrum_source()
                if bands and len(bands) >= self.NUM_BARS:
                    return bands[:self.NUM_BARS]
            except Exception:
                pass

        # Fallback: simulierte Werte
        return self._fake_bands()

    def _fake_bands(self) -> list[float]:
        """Generiert simulierte Zufalls-Band-Werte."""
        values: list[float] = []
        for i in range(self.NUM_BARS):
            if random.random() > 0.5:
                # Niedrige Frequenzen staerker
                weight = 1.0 - (i / self.NUM_BARS) * 0.4
                values.append(random.random() * weight)
            else:
                values.append(0.0)
        return values

    def render(self) -> Text:
        """Rendert die Multi-Row Equalizer-Balken mit Spektralfarben."""
        if not self._active:
            bar_str = "▁" * self.NUM_BARS
            text = Text()
            text.append("  " + bar_str + "  ", style="dim")
            return text

        lines: list[Text] = []

        for row in range(_NUM_ROWS):
            line = Text()
            line.append("  ")
            # row 0 = oben (Stufen 17–24), row 2 = unten (Stufen 1–8)
            row_base = (_NUM_ROWS - 1 - row) * _STEPS_PER_ROW

            for i in range(self.NUM_BARS):
                bar_val = self._bars[i]
                peak_val = self._peaks[i]
                color = self._colors[i]

                bar_in_row = bar_val - row_base
                peak_in_row = peak_val - row_base

                if bar_in_row >= _STEPS_PER_ROW:
                    # Volle Zelle
                    line.append(_BLOCKS[_STEPS_PER_ROW], style=color)
                elif bar_in_row > 0:
                    # Teilweise gefuellt
                    line.append(_BLOCKS[bar_in_row], style=color)
                elif 0 < peak_in_row <= _STEPS_PER_ROW and peak_val > bar_val:
                    # Peak-Marker (schwebt ueber dem Balken)
                    line.append(_PEAK_CHAR, style=f"bold {color}")
                else:
                    line.append(" ")

            line.append("  ")
            lines.append(line)

        # Zeilen zusammenfuegen
        result = Text()
        for idx, line in enumerate(lines):
            result.append_text(line)
            if idx < len(lines) - 1:
                result.append("\n")

        return result
