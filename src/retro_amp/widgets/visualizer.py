"""Equalizer-Visualizer Widget — rein visueller Effekt."""
from __future__ import annotations

import random

from rich.text import Text

from textual.widget import Widget


# Unicode-Blockzeichen fuer verschiedene Fuellhoehen
_BLOCKS = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


class Visualizer(Widget):
    """Fake-Equalizer mit animierten ASCII-Balken."""

    DEFAULT_CSS = """
    Visualizer {
        height: 3;
        padding: 0 1;
        border-top: solid $accent;
    }
    """

    NUM_BARS = 32
    MAX_HEIGHT = 8  # Entspricht den 8 Block-Stufen

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._bars: list[int] = [0] * self.NUM_BARS
        self._targets: list[int] = [0] * self.NUM_BARS
        self._active = False
        self._timer_handle: object | None = None

    def start(self) -> None:
        """Startet die Animation."""
        self._active = True
        if self._timer_handle is None:
            self._timer_handle = self.set_interval(1 / 12, self._tick)

    def stop(self) -> None:
        """Stoppt die Animation und setzt Balken zurueck."""
        self._active = False
        self._bars = [0] * self.NUM_BARS
        self._targets = [0] * self.NUM_BARS
        self.refresh()

    def _tick(self) -> None:
        """Animation-Tick: Balken bewegen sich zu Zielwerten."""
        if not self._active:
            # Timer laeuft weiter, ist aber No-Op wenn inaktiv
            return

        # Neue Zielwerte setzen (zufaellig, simuliert Musik)
        for i in range(self.NUM_BARS):
            if random.random() > 0.6:
                self._targets[i] = random.randint(1, self.MAX_HEIGHT)

        # Balken sanft zu Zielen bewegen
        for i in range(self.NUM_BARS):
            if self._bars[i] < self._targets[i]:
                self._bars[i] = min(self._bars[i] + 2, self._targets[i])
            elif self._bars[i] > self._targets[i]:
                self._bars[i] = max(self._bars[i] - 1, 0)

        self.refresh()

    def render(self) -> Text:
        """Rendert die Equalizer-Balken."""
        text = Text()

        if not self._active:
            # Leerer Zustand
            text.append("  " + "▁" * self.NUM_BARS + "  ", style="dim")
            return text

        # Balken rendern
        text.append("  ")
        for bar_value in self._bars:
            char = _BLOCKS[min(bar_value, len(_BLOCKS) - 1)]
            text.append(char, style="bold green" if bar_value > 5 else "green")
        text.append("  ")

        return text
