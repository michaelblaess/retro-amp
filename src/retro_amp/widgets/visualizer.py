"""Equalizer-Visualizer Widget — Spektralanalyse mit Retro-Charme.

Mehrere Darstellungs-Modi (siehe VisualizerMode):
- BARS:   32-Band-Spektrum mit Regenbogenfarben + Peak-Hold (Default)
- BLOCKS: 16 breite Balken im Winamp-Stil — Farbe pro Zeile (gruen/gelb/rot) + Peaks
- SCOPE:  Punkt pro Band an der Pegel-Position (geglaettet)
- MATRIX: Binaer-Digits, Farbe nach Band-Intensitaet (cliamp-inspiriert)
- LCD:    2 horizontale Segment-VU-Meter im Kassettendeck-Look (Bass + Treble)
"""
from __future__ import annotations

import random
from collections.abc import Callable

from rich.text import Text

from textual.events import Click
from textual.message import Message
from textual.widget import Widget
from textual_widgets import ContextMenuItem, ContextMenuScreen

from ..domain.models import VisualizerMode
from ..i18n import t


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

# BLOCKS-Modus: 16 breitere Balken, je 2 Zellen, Farbe pro Zeile
_BLOCKS_NUM_BARS = 16
_BLOCKS_BAR_WIDTH = 2
# Farbe pro Zeile: oben rot, mittig gelb, unten gruen — klassischer VU-Look
_BLOCKS_ROW_COLORS = ("#ff3333", "#ffcc00", "#00cc44")
_BLOCKS_PEAK_COLOR = "#ff5555"

# SCOPE-Modus: Punkt-Charakter
_SCOPE_DOT = "●"

# MATRIX-Modus: Farbschwellen pro Zeile (oben = hoehere Schwelle als unten)
_MATRIX_ROW_OFFSET = 0.18      # vorher 0.34 → top-row braucht jetzt weniger Pegel
_MATRIX_GAIN = 1.5             # Verstaerkung (analog LCD), damit Mitte/Top mehr zeigt
_MATRIX_DIM_FALLBACK = "#1a1a1a"

# LCD-Modus (Kassettendeck-VU): 2 horizontale Segment-Balken
# 14 Segmente, je 2 Zellen breit (Full-Block + Space) → klar diskrete LCD-Segmente.
_LCD_NUM_SEGMENTS = 14
_LCD_FILLED = "█"
_LCD_SEPARATOR = " "
# LCD-typisches Cyan-Blau (statt Gruen) fuer den unteren Pegelbereich
_LCD_BLUE = "#00aaee"
_LCD_YELLOW = "#ffcc00"
_LCD_RED = "#ff3333"
_LCD_DIM = "#2a2a2a"  # Dunkles "Off"-Segment, wirkt wie inaktive LCD-Zellen
_LCD_PEAK_HOLD_FRAMES = 6  # Peaks halten laenger als bei BARS
# Gain-Faktor: real existierende Musik erreicht selten den vollen Pegelausschlag.
# 1.6x Verstaerkung sorgt dafuer, dass auch normale Musik gelb/rot triggert.
_LCD_GAIN = 1.6
# Farbschwellen weiter nach unten verschoben, damit ueber den gesamten Pegelbereich
# Farbwechsel sichtbar werden — nicht nur bei voller Aussteuerung.
_LCD_THRESHOLD_YELLOW = 0.50
_LCD_THRESHOLD_RED = 0.75


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


def _traffic_light_color(level: int, max_level: int) -> str:
    """Ampel-Farbe abhaengig von der Pegelhoehe (klassisches VU-Schema)."""
    t = level / max(max_level, 1)
    if t < 0.6:
        return "#00cc44"   # Gruen
    if t < 0.85:
        return "#ffcc00"   # Gelb
    return "#ff3333"        # Rot


def _darken_hex(color: str, factor: float = 0.15) -> str:
    """Erzeugt eine sehr dunkle Variante einer Hex-Farbe.

    Multipliziert die RGB-Komponenten mit factor (Default 0.15 = 15% Helligkeit).
    Wird fuer den 'aus'-Zustand der Matrix-Zellen verwendet — gibt einen
    subtilen Theme-Tint im Hintergrund statt einem neutralen Grau.
    """
    if not color or not color.startswith("#") or len(color) != 7:
        return _MATRIX_DIM_FALLBACK
    try:
        r = max(0, min(255, int(int(color[1:3], 16) * factor)))
        g = max(0, min(255, int(int(color[3:5], 16) * factor)))
        b = max(0, min(255, int(int(color[5:7], 16) * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"
    except ValueError:
        return _MATRIX_DIM_FALLBACK


def _lcd_segment_color(seg_idx: int, total: int, safe_color: str) -> str:
    """Farbe eines LCD-Segments basierend auf seiner Position im Balken.

    safe_color: Farbe fuer den unteren ("Safe Zone") Pegelbereich — kommt vom
    aktuellen Theme. Yellow/Red bleiben fest, weil sie als Warnfarben
    semantische Bedeutung haben (Headroom-Warnung, Clipping).
    """
    t = seg_idx / max(total - 1, 1)
    if t < _LCD_THRESHOLD_YELLOW:
        return safe_color
    if t < _LCD_THRESHOLD_RED:
        return _LCD_YELLOW
    return _LCD_RED


class Visualizer(Widget):
    """Equalizer-Visualizer mit konfigurierbarem Darstellungs-Modus.

    Nutzt entweder echte FFT-Daten (via spectrum_source Callback)
    oder simulierte Zufallswerte als Fallback.
    """

    DEFAULT_CSS = """
    Visualizer {
        height: 3;
        width: 38;
        padding: 0 2;
        border-right: solid $accent;
    }
    """

    NUM_BARS = 32

    class ModeChangeRequested(Message):
        """Wird gesendet, wenn der User per Kontextmenue einen anderen Modus waehlt.

        Die App ist verantwortlich, den Modus tatsaechlich anzuwenden und in den
        Settings zu persistieren — der Visualizer kennt weder Storage noch Theme.
        """

        def __init__(self, mode: VisualizerMode) -> None:
            super().__init__()
            self.mode = mode

    def __init__(
        self,
        mode: VisualizerMode = VisualizerMode.BARS,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._bars: list[int] = [0] * self.NUM_BARS
        self._peaks: list[int] = [0] * self.NUM_BARS
        self._peak_hold: list[int] = [0] * self.NUM_BARS
        self._active = False
        self._timer_handle: object | None = None
        self._spectrum_source: Callable[[], list[float]] | None = None
        self._mode = mode

        # LCD-Modus: getrennte Peaks fuer Bass- und Treble-Haelfte
        self._lcd_peak_l: int = 0
        self._lcd_peak_r: int = 0
        self._lcd_hold_l: int = 0
        self._lcd_hold_r: int = 0

        # Farben vorberechnen
        self._colors = [
            _spectral_color(i, self.NUM_BARS) for i in range(self.NUM_BARS)
        ]

    @property
    def mode(self) -> VisualizerMode:
        return self._mode

    def set_mode(self, mode: VisualizerMode) -> None:
        """Wechselt den Darstellungs-Modus zur Laufzeit."""
        if mode == self._mode:
            return
        self._mode = mode
        self.refresh()

    def on_click(self, event: Click) -> None:
        """Right-Click oeffnet ein Kontextmenue mit den verfuegbaren Modi."""
        if event.button != 3:  # nur Rechtsklick
            return
        items = [
            ContextMenuItem(
                id=mode.value,
                label=t(f"visualizer.mode_{mode.value}"),
                icon="✓" if mode == self._mode else " ",  # Space haelt Spalten ausgerichtet
            )
            for mode in VisualizerMode
        ]
        self.app.push_screen(
            ContextMenuScreen(items, at=(event.screen_x, event.screen_y)),
            callback=self._on_mode_picked,
        )

    def _on_mode_picked(self, action_id: str | None) -> None:
        """Callback fuer das Kontextmenue — schickt die Auswahl an die App."""
        if action_id is None:
            return
        try:
            new_mode = VisualizerMode(action_id)
        except ValueError:
            return
        self.post_message(self.ModeChangeRequested(new_mode))

    def set_spectrum_source(
        self, source: Callable[[], list[float]] | None,
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
        self._lcd_peak_l = 0
        self._lcd_peak_r = 0
        self._lcd_hold_l = 0
        self._lcd_hold_r = 0
        self.refresh()

    def _tick(self) -> None:
        """Animation-Tick: Balken bewegen sich zu Zielwerten."""
        if not self._active:
            return

        band_values = self._get_band_values()

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

        # LCD-Modus: getrennte Peaks fuer Bass-/Treble-Haelfte
        half = self.NUM_BARS // 2
        bass = sum(self._bars[:half]) // half if half else 0
        treble = sum(self._bars[half:]) // (self.NUM_BARS - half) if self.NUM_BARS > half else 0
        if bass >= self._lcd_peak_l:
            self._lcd_peak_l = bass
            self._lcd_hold_l = _LCD_PEAK_HOLD_FRAMES
        elif self._lcd_hold_l > 0:
            self._lcd_hold_l -= 1
        else:
            self._lcd_peak_l = max(self._lcd_peak_l - 1, 0)
        if treble >= self._lcd_peak_r:
            self._lcd_peak_r = treble
            self._lcd_hold_r = _LCD_PEAK_HOLD_FRAMES
        elif self._lcd_hold_r > 0:
            self._lcd_hold_r -= 1
        else:
            self._lcd_peak_r = max(self._lcd_peak_r - 1, 0)

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
        """Rendert die Multi-Row Equalizer-Balken im aktuellen Modus."""
        if not self._active:
            bar_str = "▁" * self.NUM_BARS
            text = Text()
            text.append("  " + bar_str + "  ", style="dim")
            return text

        if self._mode == VisualizerMode.BLOCKS:
            return self._render_blocks()
        if self._mode == VisualizerMode.SCOPE:
            return self._render_scope()
        if self._mode == VisualizerMode.MATRIX:
            return self._render_matrix()
        if self._mode == VisualizerMode.LCD:
            return self._render_lcd()
        return self._render_bars()

    def _render_bars(self) -> Text:
        """BARS-Modus: 32-Band Regenbogen mit Peak-Markern."""
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
                    line.append(_BLOCKS[_STEPS_PER_ROW], style=color)
                elif bar_in_row > 0:
                    line.append(_BLOCKS[bar_in_row], style=color)
                elif 0 < peak_in_row <= _STEPS_PER_ROW and peak_val > bar_val:
                    line.append(_PEAK_CHAR, style=f"bold {color}")
                else:
                    line.append(" ")

            line.append("  ")
            lines.append(line)

        return self._join_lines(lines)

    def _render_blocks(self) -> Text:
        """BLOCKS-Modus: Winamp-Look — 16 breite Balken, Farbe PRO ZEILE + Peak-Marker.

        Damit jeder aktive Balken ueber gruen-gelb-rot gradiert (statt nur die hoechsten
        in der Spitze rot zu sein). Peak-Marker oben drueber in rot.
        """
        # 32 Bands auf 16 Balken zusammenfassen (Mittelwert je Paar)
        block_levels: list[int] = []
        block_peaks: list[int] = []
        for i in range(_BLOCKS_NUM_BARS):
            j = i * 2
            a = self._bars[j]
            b = self._bars[j + 1] if j + 1 < self.NUM_BARS else a
            block_levels.append((a + b) // 2)
            pa = self._peaks[j]
            pb = self._peaks[j + 1] if j + 1 < self.NUM_BARS else pa
            block_peaks.append((pa + pb) // 2)

        lines: list[Text] = []

        for row in range(_NUM_ROWS):
            line = Text()
            line.append("  ")
            row_base = (_NUM_ROWS - 1 - row) * _STEPS_PER_ROW
            row_color = _BLOCKS_ROW_COLORS[row]

            for idx, level in enumerate(block_levels):
                in_row = level - row_base
                peak = block_peaks[idx]
                peak_in_row = peak - row_base

                if in_row >= _STEPS_PER_ROW:
                    line.append(_BLOCKS[_STEPS_PER_ROW] * _BLOCKS_BAR_WIDTH, style=row_color)
                elif in_row > 0:
                    line.append(_BLOCKS[in_row] * _BLOCKS_BAR_WIDTH, style=row_color)
                elif 0 < peak_in_row <= _STEPS_PER_ROW and peak > level:
                    # Peak-Marker schwebend ueber dem Balken
                    line.append(_PEAK_CHAR * _BLOCKS_BAR_WIDTH, style=f"bold {_BLOCKS_PEAK_COLOR}")
                else:
                    line.append(" " * _BLOCKS_BAR_WIDTH)

            line.append("  ")
            lines.append(line)

        return self._join_lines(lines)

    def _render_scope(self) -> Text:
        """SCOPE-Modus: Spektralkurve — Punkt pro Band an Pegel-Position.

        Spatiales Smoothing zwischen Nachbarbaendern fuer fluessigeren Kurvenverlauf.
        """
        # Smoothing: Mittelwert ueber 3-Nachbarn-Fenster
        smoothed: list[float] = []
        for i in range(self.NUM_BARS):
            lo = max(0, i - 1)
            hi = min(self.NUM_BARS - 1, i + 1)
            window = self._bars[lo : hi + 1]
            smoothed.append(sum(window) / len(window))

        # Fuer jedes Band: in welcher Zeile sitzt der Punkt?
        # row 0 = oben (hohe Pegel), row 2 = unten (niedrige Pegel)
        dot_rows: list[int] = []
        for value in smoothed:
            if value <= 0:
                dot_rows.append(-1)  # Kein Punkt sichtbar
                continue
            normalized = min(value / _MAX_LEVEL, 1.0)
            row_idx = _NUM_ROWS - 1 - int(normalized * (_NUM_ROWS - 1) + 0.5)
            dot_rows.append(max(0, min(_NUM_ROWS - 1, row_idx)))

        lines: list[Text] = []

        for row in range(_NUM_ROWS):
            line = Text()
            line.append("  ")
            for i in range(self.NUM_BARS):
                if dot_rows[i] == row:
                    line.append(_SCOPE_DOT, style=self._colors[i])
                else:
                    line.append(" ")
            line.append("  ")
            lines.append(line)

        return self._join_lines(lines)

    def _render_matrix(self) -> Text:
        """MATRIX-Modus: Binaer-Digits, Farbe nach Band-Intensitaet (cliamp-Style).

        Safe-Zone-Farbe kommt vom aktuellen Theme. Yellow/Red bleiben fest als
        Warn-/Clipping-Semantik. Dim-Hintergrund ist eine sehr dunkle Variante
        des Theme-Accents — gibt einen subtilen Theme-Tint im Hintergrund.

        no_wrap=True verhindert dass Ueberlauf-Zeichen auf eine neue Zeile
        umbrechen (sonst sieht man verirrte Digits zwischen den Zeilen).
        """
        safe_color = self._theme_safe_color()
        dim_color = _darken_hex(safe_color, 0.15)
        lines: list[Text] = []

        for row in range(_NUM_ROWS):
            line = Text(no_wrap=True)
            # Schwellen pro Zeile: oben braucht hoeheren Pegel, unten reicht jeder
            row_threshold = (_NUM_ROWS - 1 - row) * _MATRIX_ROW_OFFSET

            for i in range(self.NUM_BARS):
                level = self._bars[i]
                raw = level / _MAX_LEVEL if _MAX_LEVEL > 0 else 0.0
                intensity = min(raw * _MATRIX_GAIN, 1.0)

                # Digit IMMER zeichnen — nur Farbe haengt vom Pegel ab
                digit = "1" if random.random() > 0.5 else "0"

                if intensity >= row_threshold + 0.40:
                    color = "#ff3333"      # Rot — sehr aktiv (Clipping-Warnung)
                elif intensity >= row_threshold + 0.20:
                    color = "#ffcc00"      # Gelb — aktiv (Headroom-Warnung)
                elif intensity >= row_threshold + 0.05:
                    color = safe_color     # Theme-Accent — leicht aktiv
                else:
                    color = dim_color      # Sehr dunkler Theme-Tint

                line.append(digit, style=color)
            lines.append(line)

        return self._join_lines(lines)

    def _render_lcd(self) -> Text:
        """LCD-Modus: 2 horizontale Segment-VU-Meter im Kassettendeck-Look.

        Oben = Bass-Haelfte (Bands 0..15), unten = Treble-Haelfte (Bands 16..31).
        Jede Spur hat eigenen Peak-Marker. Farb-Schema: Theme-Accent fuer den
        unteren Pegelbereich (LCD "an"-Farbe), Gelb/Rot bleiben fest fuer das
        Headroom-/Clipping-Warning-Schema.
        """
        half = self.NUM_BARS // 2
        bass = sum(self._bars[:half]) / half if half else 0.0
        treble = sum(self._bars[half:]) / (self.NUM_BARS - half) if self.NUM_BARS > half else 0.0

        def gained(value: float) -> float:
            return min(value / _MAX_LEVEL * _LCD_GAIN, 1.0) if _MAX_LEVEL else 0.0

        bass_norm = gained(bass)
        treble_norm = gained(treble)
        peak_l_norm = gained(self._lcd_peak_l)
        peak_r_norm = gained(self._lcd_peak_r)

        safe_color = self._theme_safe_color()

        def build_bar(level: float, peak: float) -> Text:
            active = int(level * _LCD_NUM_SEGMENTS + 0.5)
            peak_idx = int(peak * _LCD_NUM_SEGMENTS + 0.5) - 1
            line = Text()
            for seg in range(_LCD_NUM_SEGMENTS):
                seg_color = _lcd_segment_color(seg, _LCD_NUM_SEGMENTS, safe_color)
                if seg < active:
                    line.append(_LCD_FILLED, style=seg_color)
                elif seg == peak_idx and peak_idx >= active:
                    line.append(_LCD_FILLED, style=f"bold {seg_color}")
                else:
                    line.append(_LCD_FILLED, style=_LCD_DIM)
                # Separator-Zelle als Luecke zwischen den Segmenten
                line.append(_LCD_SEPARATOR)
            return line

        line_top = Text()
        line_top.append(" L ", style="bold dim")
        line_top.append_text(build_bar(bass_norm, peak_l_norm))

        line_mid = Text()  # Trennzeile leer fuer Atmen-Optik

        line_bot = Text()
        line_bot.append(" R ", style="bold dim")
        line_bot.append_text(build_bar(treble_norm, peak_r_norm))

        return self._join_lines([line_top, line_mid, line_bot])

    def _theme_safe_color(self) -> str:
        """Liest die LCD-Safe-Zone-Farbe aus dem aktuellen Theme.

        Bevorzugte Quelle ist `accent`, dann `primary` als Fallback. Wenn das
        Theme keine passende Farbe liefert (z.B. waehrend des App-Starts oder
        bei Tests ohne App), wird der Default-LCD-Blauton verwendet.
        """
        try:
            theme = self.app.current_theme
        except Exception:
            return _LCD_BLUE
        if theme is None:
            return _LCD_BLUE
        for attr in ("accent", "primary"):
            color = getattr(theme, attr, None)
            if color:
                return str(color)
        return _LCD_BLUE

    @staticmethod
    def _join_lines(lines: list[Text]) -> Text:
        """Fuegt mehrere Zeilen mit Newlines zu einem Text-Objekt zusammen."""
        result = Text()
        for idx, line in enumerate(lines):
            result.append_text(line)
            if idx < len(lines) - 1:
                result.append("\n")
        return result
