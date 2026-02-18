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
        layout: vertical;
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

        # Zeile 1: Status-Icon + Track-Name + Fortschrittsbalken + Zeit
        if state.is_playing:
            icon = "▶ "
        elif state.is_paused:
            icon = "▐▐ "
        else:
            icon = "■ "

        text.append(icon, style="bold")

        if state.current_track:
            name = state.current_track.display_name
            if len(name) > 30:
                name = name[:27] + "..."
            text.append(f"{name}  ", style="bold")

            # Fortschrittsbalken
            bar_width = 30
            filled = int(state.progress * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            text.append(bar, style="dim")
            text.append(
                f"  {state.position_display} / {state.current_track.duration_display}"
            )
        else:
            text.append("Kein Track geladen", style="dim")

        text.append("\n")

        # Zeile 2: Lautstaerke
        vol_pct = int(state.volume * 100)
        vol_bars = int(state.volume * 10)
        vol_display = "█" * vol_bars + "░" * (10 - vol_bars)
        text.append("  Vol: ", style="dim")
        text.append(vol_display)
        text.append(f"  {vol_pct}%", style="dim")

        return text
