"""Transport-Leiste Widget — Play/Pause, Fortschritt, Lautstaerke."""

from __future__ import annotations

from rich.text import Text
from textual.events import Click
from textual.message import Message
from textual.widget import Widget

from ..domain.models import PlayerState
from ..i18n import t

_VOL_BAR_WIDTH = 10
_PADDING_LEFT = 2


class TransportBar(Widget):
    """Zeigt den aktuellen Player-Status mit Fortschrittsbalken."""

    DEFAULT_CSS = """
    TransportBar {
        height: 3;
        width: 1fr;
        padding: 0 2;
    }
    """

    class VolumeClicked(Message):
        """Wird gesendet wenn die Lautstaerke per Mausklick geaendert wird."""

        def __init__(self, volume: float) -> None:
            super().__init__()
            self.volume = volume

    class SeekClicked(Message):
        """Wird gesendet wenn per Mausklick im Fortschrittsbalken geseekt wird."""

        def __init__(self, position: float) -> None:
            super().__init__()
            self.position = position

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._state = PlayerState()
        self._vol_line: int = -1
        self._vol_col: int = -1
        self._bar_line: int = -1
        self._bar_col: int = 0
        self._bar_width: int = 30

    def update_state(self, state: PlayerState) -> None:
        """Aktualisiert den angezeigten Status."""
        self._state = state
        self.refresh()

    def render(self) -> Text:
        """Rendert die Transport-Leiste."""
        # Innere Breite (ohne Padding) bestimmt, wie viel Platz fuer den Titel
        # bleibt. Sonst wrappt der Text auf Zeile 2 und der Klick-Handler trifft
        # Volume/Seek-Bar nicht mehr.
        outer = self.size.width if self.size.width else 60
        inner_width = max(20, outer - _PADDING_LEFT * 2)

        # no_wrap + overflow=ellipsis als Sicherheitsnetz, falls die Truncierung
        # die Breite leicht ueberschiesst (z.B. wegen Wide-Chars im Titel).
        text = Text(no_wrap=True, overflow="ellipsis")
        state = self._state

        # Zeile 1: Status-Icon + Track-Info
        if state.is_playing:
            icon = "▶ "
            icon_style = "bold green"
        elif state.is_paused:
            icon = "▐▐"
            icon_style = "bold yellow"
        else:
            icon = "■ "
            icon_style = "dim"

        text.append(icon, style=icon_style)
        text.append(" ")

        if state.current_track:
            track = state.current_track
            if track.artist and track.title:
                display = f"{track.artist} \u2013 {track.title}"
            else:
                display = track.display_name

            info_parts: list[str] = []
            if track.format_display:
                info_parts.append(track.format_display)
            if track.bitrate_display:
                info_parts.append(track.bitrate_display)
            format_suffix = f"  [{' | '.join(info_parts)}]" if info_parts else ""

            # Verfuegbare Breite fuer den Titel: inner - icon (3) - format - 1 Puffer
            title_max = max(10, inner_width - 3 - len(format_suffix) - 1)
            if len(display) > title_max:
                display = display[: max(title_max - 3, 5)] + "..."

            text.append(display, style="bold")
            if format_suffix:
                text.append(format_suffix, style="dim")

            text.append("\n")

            # Zeile 2: Fortschrittsbalken + Zeit + Lautstaerke
            self._bar_line = 1
            self._bar_col = 0
            self._bar_width = 30
            filled = int(state.progress * self._bar_width)
            text.append("\u2588" * filled, style="green")
            text.append("\u2591" * (self._bar_width - filled), style="dim")

            time_str = f"  {state.position_display} / {track.duration_display}"
            text.append(time_str, style="dim")

            # Lautstaerke
            vol_prefix = "    Vol: "
            text.append(vol_prefix)
            self._vol_line = 1
            self._vol_col = self._bar_width + len(time_str) + len(vol_prefix)

            vol_pct = int(state.volume * 100)
            vol_bars = int(state.volume * _VOL_BAR_WIDTH)
            text.append("\u2588" * vol_bars, style="green")
            text.append("\u2591" * (_VOL_BAR_WIDTH - vol_bars), style="dim")
            text.append(f" {vol_pct}%", style="dim")
        else:
            text.append(t("transport.no_track"), style="dim")
            text.append("\n")

            # Lautstaerke
            vol_prefix = "Vol: "
            text.append(vol_prefix)
            self._vol_line = 1
            self._vol_col = len(vol_prefix)

            vol_pct = int(state.volume * 100)
            vol_bars = int(state.volume * _VOL_BAR_WIDTH)
            text.append("\u2588" * vol_bars, style="green")
            text.append("\u2591" * (_VOL_BAR_WIDTH - vol_bars), style="dim")
            text.append(f" {vol_pct}%", style="dim")

        return text

    def on_click(self, event: Click) -> None:
        """Mausklick auf Volume-Bar oder Fortschrittsbalken verarbeiten."""
        cx = event.offset.x - _PADDING_LEFT
        cy = event.offset.y

        # Volume-Bar
        if self._vol_line >= 0 and cy == self._vol_line and self._vol_col <= cx < self._vol_col + _VOL_BAR_WIDTH:
            vol = (cx - self._vol_col + 0.5) / _VOL_BAR_WIDTH
            vol = max(0.0, min(1.0, vol))
            self.post_message(self.VolumeClicked(vol))

        # Fortschrittsbalken (Seek)
        elif (
            self._bar_line >= 0
            and cy == self._bar_line
            and self._bar_col <= cx < self._bar_col + self._bar_width
            and self._state.current_track
            and self._state.current_track.duration_seconds > 0
        ):
            ratio = (cx - self._bar_col + 0.5) / self._bar_width
            ratio = max(0.0, min(1.0, ratio))
            position = ratio * self._state.current_track.duration_seconds
            self.post_message(self.SeekClicked(position))
