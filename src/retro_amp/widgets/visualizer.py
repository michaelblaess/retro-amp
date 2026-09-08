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
import time
from collections.abc import Callable

from rich.text import Text
from textual.events import Click
from textual.message import Message
from textual.widget import Widget
from textual_widgets import ContextMenuItem, ContextMenuScreen

from ..domain.models import VisualizerMode
from ..i18n import t
from ..meter import LevelMeter, MeterConfig, PeakTracker
from ..palette import SurfacePalette
from ..themes import surface_palette

# Unicode-Blockzeichen fuer verschiedene Fuellhoehen (0=leer, 8=voll)
_BLOCKS = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

# Peak-Marker (schwebendes Strichlein ueber dem Balken)
_PEAK_CHAR = "▔"

# Zeitverhalten der Anzeige. Die Werte stehen in Dezibel je Sekunde und
# Sekunden - NICHT in Stufen je Bild. Nur so bleibt das Bild gleich, wenn sich
# der Takt aendert. Die Vorgaben entsprechen dem frueheren Verhalten bei
# 12 Bildern je Sekunde (siehe meter.MeterConfig).
_TICK_SECONDS = 1 / 12

# Die LCD-Anzeige haelt ihre Spitze laenger und laesst sie langsamer fallen
# als das Balkenspektrum - ein Kassettendeck-Zeiger schwingt traeger.
_LCD_PEAK_DECAY_DB_PER_S = 30.0
_LCD_PEAK_HOLD_S = 0.5

# Render-Zeilen
_NUM_ROWS = 3
_STEPS_PER_ROW = len(_BLOCKS) - 1  # 8
_MAX_LEVEL = _NUM_ROWS * _STEPS_PER_ROW  # 24

# BLOCKS-Modus: 16 breitere Balken, je 2 Zellen, Farbe pro Zeile
_BLOCKS_NUM_BARS = 16
_BLOCKS_BAR_WIDTH = 2
# Farbe pro Zeile: oben laut, mittig mittel, unten leise - die drei Stufen
# kommen aus dem Theme (vis_high/vis_mid/vis_low), nicht aus dem Malcode.

# SCOPE-Modus: Punkt-Charakter
_SCOPE_DOT = "●"

# MATRIX-Modus: Farbschwellen pro Zeile (oben = hoehere Schwelle als unten)
_MATRIX_ROW_OFFSET = 0.18  # vorher 0.34 → top-row braucht jetzt weniger Pegel
_MATRIX_GAIN = 1.5  # Verstaerkung (analog LCD), damit Mitte/Top mehr zeigt

# LCD-Modus (Kassettendeck-VU): 2 horizontale Segment-Balken
# 14 Segmente, je 2 Zellen breit (Full-Block + Space) → klar diskrete LCD-Segmente.
_LCD_NUM_SEGMENTS = 14
_LCD_FILLED = "█"
_LCD_SEPARATOR = " "
# Die Farben der Segmente kommen aus dem Theme: der untere Bereich aus
# lcd_foreground, die beiden oberen aus vis_mid und vis_high, das
# unbeleuchtete Segment aus lcd_dim.
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


def _lcd_segment_color(seg_idx: int, total: int, palette: SurfacePalette) -> str:
    """Farbe eines LCD-Segments nach seiner Position im Balken.

    Alle drei Zonen kommen aus dem Theme: der untere Bereich aus der
    beleuchteten LCD-Farbe, die Warnzone aus vis_mid, der Uebersteuerungs-
    bereich aus vis_high.
    """
    t = seg_idx / max(total - 1, 1)
    if t < _LCD_THRESHOLD_YELLOW:
        return palette.lcd_foreground
    if t < _LCD_THRESHOLD_RED:
        return palette.vis_mid
    return palette.vis_high


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
        # Anzeigewerte in Stufen 0.._MAX_LEVEL - nur fuers Zeichnen. Das
        # Zeitverhalten selbst liegt im oberflaechenfreien LevelMeter.
        self._bars: list[int] = [0] * self.NUM_BARS
        self._peaks: list[int] = [0] * self.NUM_BARS
        self._active = False
        self._timer_handle: object | None = None
        self._spectrum_source: Callable[[], list[float]] | None = None
        self._mode = mode

        self._meter = LevelMeter(self.NUM_BARS, MeterConfig())
        self._clock: Callable[[], float] = time.monotonic

        # Flaechenfarben des aktuellen Themes. Wird beim Zeichnen nachgezogen,
        # sobald sich der Theme-Name aendert - kein Malcode kennt eine Farbe.
        self._palette_name = ""
        self._palette: SurfacePalette = surface_palette("")

        # LCD-Modus: getrennte Spitzen fuer Bass- und Treble-Haelfte
        self._lcd_peak_tracker_l = PeakTracker(_LCD_PEAK_DECAY_DB_PER_S, _LCD_PEAK_HOLD_S)
        self._lcd_peak_tracker_r = PeakTracker(_LCD_PEAK_DECAY_DB_PER_S, _LCD_PEAK_HOLD_S)
        self._lcd_peak_l: int = 0
        self._lcd_peak_r: int = 0
        self._lcd_last: float | None = None

        # Farben vorberechnen
        self._colors = [_spectral_color(i, self.NUM_BARS) for i in range(self.NUM_BARS)]

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
        self,
        source: Callable[[], list[float]] | None,
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
            self._timer_handle = self.set_interval(_TICK_SECONDS, self._tick)

    def stop(self) -> None:
        """Beendet die Zufuhr - die Anzeige klingt aus, statt einzufrieren.

        Der Zeitgeber laeuft absichtlich weiter, bis alles auf dem Boden liegt
        (`_tick` haelt ihn dann selbst an). Ein Pegel, der beim Pausieren
        abrupt auf Null springt, sieht nach Absturz aus statt nach Anhalten.
        """
        self._active = False

    def reset(self) -> None:
        """Setzt die Anzeige sofort auf Null - fuer einen Titelwechsel."""
        self._active = False
        self._meter.reset()
        self._lcd_peak_tracker_l.reset()
        self._lcd_peak_tracker_r.reset()
        self._lcd_last = None
        self._bars = [0] * self.NUM_BARS
        self._peaks = [0] * self.NUM_BARS
        self._lcd_peak_l = 0
        self._lcd_peak_r = 0
        self._stop_timer()
        self.refresh()

    def _stop_timer(self) -> None:
        """Haelt den Takt an, sofern einer laeuft."""
        handle = self._timer_handle
        self._timer_handle = None
        if handle is not None and hasattr(handle, "stop"):
            handle.stop()

    def _tick(self) -> None:
        """Ein Bild: neue Werte holen oder ausklingen lassen."""
        now = self._clock()

        if self._active:
            self._meter.update(self._get_band_values(), now)
        else:
            self._meter.advance(now)

        self._bars = [round(v * _MAX_LEVEL) for v in self._meter.levels]
        self._peaks = [round(v * _MAX_LEVEL) for v in self._meter.peaks]
        self._advance_lcd_peaks(now)
        self.refresh()

        # Erst wenn nichts mehr zu sehen ist, darf der Takt enden. Solange
        # gespielt wird, laeuft er ohnehin weiter.
        if not self._active and self._meter.is_idle:
            self._stop_timer()

    def _advance_lcd_peaks(self, now: float) -> None:
        """Fuehrt die beiden Spitzen der LCD-Anzeige nach.

        Bass und Treble sind Mittelwerte ueber je eine Haelfte der Baender.
        Sie bekommen eigene Spitzenverfolger, weil ein Kassettendeck-Zeiger
        traeger schwingt als ein Balkenspektrum.
        """
        vergangen = 0.0 if self._lcd_last is None else max(0.0, now - self._lcd_last)
        self._lcd_last = now

        pegel = self._meter.levels
        half = self.NUM_BARS // 2
        bass = sum(pegel[:half]) / half if half else 0.0
        treble = sum(pegel[half:]) / (self.NUM_BARS - half) if half < self.NUM_BARS else 0.0

        for verfolger, wert in (
            (self._lcd_peak_tracker_l, bass),
            (self._lcd_peak_tracker_r, treble),
        ):
            verfolger.advance(now, vergangen)
            verfolger.bump(wert, now)

        self._lcd_peak_l = round(self._lcd_peak_tracker_l.value * _MAX_LEVEL)
        self._lcd_peak_r = round(self._lcd_peak_tracker_r.value * _MAX_LEVEL)

    def _get_band_values(self) -> list[float]:
        """Holt Band-Werte aus der Datenquelle oder generiert Fake-Werte."""
        if self._spectrum_source:
            try:
                bands = self._spectrum_source()
                if bands and len(bands) >= self.NUM_BARS:
                    return bands[: self.NUM_BARS]
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
        # Die Ruhezeile erst zeigen, wenn wirklich nichts mehr da ist. Beim
        # Anhalten laeuft der Pegel noch aus - dieser Abfall soll auch zu
        # sehen sein und nicht hinter dem Platzhalter verschwinden.
        if not self._active and self._meter.is_idle:
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
        """BLOCKS-Modus: 16 breite Balken, Farbe PRO ZEILE plus Spitzenmarke.

        Jeder aktive Balken gradiert ueber die drei Pegelstufen des Themes
        (unten leise, oben laut), statt nur in der Spitze die laute Farbe zu
        zeigen. Die Spitzenmarke schwebt in vis_peak darueber.
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

        palette = self.palette()
        lines: list[Text] = []

        for row in range(_NUM_ROWS):
            line = Text()
            line.append("  ")
            row_base = (_NUM_ROWS - 1 - row) * _STEPS_PER_ROW
            # Zeile 0 ist oben (lauteste Stufe), Zeile 2 unten.
            row_color = (palette.vis_high, palette.vis_mid, palette.vis_low)[row]

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
                    line.append(_PEAK_CHAR * _BLOCKS_BAR_WIDTH, style=f"bold {palette.vis_peak}")
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
        palette = self.palette()
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
                    color = palette.vis_high  # sehr aktiv
                elif intensity >= row_threshold + 0.20:
                    color = palette.vis_mid  # aktiv
                elif intensity >= row_threshold + 0.05:
                    color = palette.lcd_foreground  # leicht aktiv
                else:
                    color = palette.vis_grid  # ruhender Untergrund

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
        treble = sum(self._bars[half:]) / (self.NUM_BARS - half) if half < self.NUM_BARS else 0.0

        def gained(value: float) -> float:
            return min(value / _MAX_LEVEL * _LCD_GAIN, 1.0) if _MAX_LEVEL else 0.0

        bass_norm = gained(bass)
        treble_norm = gained(treble)
        peak_l_norm = gained(self._lcd_peak_l)
        peak_r_norm = gained(self._lcd_peak_r)

        palette = self.palette()

        def build_bar(level: float, peak: float) -> Text:
            active = int(level * _LCD_NUM_SEGMENTS + 0.5)
            peak_idx = int(peak * _LCD_NUM_SEGMENTS + 0.5) - 1
            line = Text()
            for seg in range(_LCD_NUM_SEGMENTS):
                seg_color = _lcd_segment_color(seg, _LCD_NUM_SEGMENTS, palette)
                if seg < active:
                    line.append(_LCD_FILLED, style=seg_color)
                elif seg == peak_idx and peak_idx >= active:
                    line.append(_LCD_FILLED, style=f"bold {seg_color}")
                else:
                    line.append(_LCD_FILLED, style=palette.lcd_dim)
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

    def palette(self) -> SurfacePalette:
        """Flaechenfarben des aktuell eingestellten Themes.

        Wird nach dem Theme-Namen zwischengespeichert, damit die Ableitung
        nicht bei jedem Bild erneut laeuft. Ohne laufende App - beim Start
        oder in Tests - liefert `surface_palette` das Standard-Theme.
        """
        try:
            name = str(self.app.theme)
        except Exception:
            name = ""
        if name != self._palette_name:
            self._palette_name = name
            self._palette = surface_palette(name)
        return self._palette

    @staticmethod
    def _join_lines(lines: list[Text]) -> Text:
        """Fuegt mehrere Zeilen mit Newlines zu einem Text-Objekt zusammen."""
        result = Text()
        for idx, line in enumerate(lines):
            result.append_text(line)
            if idx < len(lines) - 1:
                result.append("\n")
        return result
