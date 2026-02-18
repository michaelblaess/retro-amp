"""Transport-Leiste Widget — Play/Pause, Fortschritt, Lautstaerke."""
from __future__ import annotations

from rich.text import Text

from textual.widget import Widget

from ..domain.models import PlayerState


class TransportBar(Widget):
    """Zeigt den aktuellen Player-Status mit Fortschrittsbalken."""

    DEFAULT_CSS = """
    TransportBar {
        height: 3;
        padding: 0 1;
        border-top: solid $accent;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._state = PlayerState()

    def update_state(self, state: PlayerState) -> None:
        """Aktualisiert den angezeigten Status."""
        self._state = state
        self.refresh()

    def render(self) -> Text:
        """Rendert die Transport-Leiste."""
        text = Text()
        state = self._state

        # Zeile 1: Status-Icon + Track-Info + Fortschrittsbalken + Zeit
        if state.is_playing:
            icon = " ▶  "
            icon_style = "bold green"
        elif state.is_paused:
            icon = " ▐▐ "
            icon_style = "bold yellow"
        else:
            icon = " ■  "
            icon_style = "dim"

        text.append(icon, style=icon_style)

        if state.current_track:
            track = state.current_track
            # Artist - Title oder Dateiname
            if track.artist and track.title:
                display = f"{track.artist} - {track.title}"
            else:
                display = track.display_name
            if len(display) > 40:
                display = display[:37] + "..."
            text.append(display, style="bold")

            # Format + Bitrate
            info_parts: list[str] = []
            if track.format_display:
                info_parts.append(track.format_display)
            if track.bitrate_display:
                info_parts.append(track.bitrate_display)
            if info_parts:
                text.append(f"  [{' | '.join(info_parts)}]", style="dim")

            text.append("\n")

            # Zeile 2: Fortschrittsbalken + Zeit + Lautstaerke
            text.append("     ")
            bar_width = 40
            filled = int(state.progress * bar_width)
            text.append("█" * filled, style="green")
            text.append("░" * (bar_width - filled), style="dim")
            text.append(
                f"  {state.position_display} / {track.duration_display}",
                style="dim",
            )

            # Lautstaerke rechts
            vol_pct = int(state.volume * 100)
            vol_bars = int(state.volume * 10)
            text.append("    Vol: ")
            text.append("█" * vol_bars, style="green")
            text.append("░" * (10 - vol_bars), style="dim")
            text.append(f" {vol_pct}%", style="dim")
        else:
            text.append("Kein Track geladen — [Space] zum Starten", style="dim")
            text.append("\n")
            vol_pct = int(state.volume * 100)
            vol_bars = int(state.volume * 10)
            text.append("     Vol: ")
            text.append("█" * vol_bars, style="green")
            text.append("░" * (10 - vol_bars), style="dim")
            text.append(f" {vol_pct}%", style="dim")

        return text
