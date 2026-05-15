"""Control-Panel Widget — WinAmp-Style Transport-Buttons mit Textual Buttons."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button

from ..domain.models import RepeatMode
from ..i18n import t

# Mapping: Button-ID -> Action-Name
_ACTION_MAP: dict[str, str] = {
    "btn-prev": "prev",
    "btn-seek-back": "seek_back",
    "btn-play-pause": "play_pause",
    "btn-seek-fwd": "seek_fwd",
    "btn-next": "next",
    "btn-stop": "stop",
    "btn-shuffle": "shuffle",
    "btn-repeat": "repeat",
    "btn-favorite": "favorite",
}


class ControlPanel(Widget):
    """Klickbare Transport-Buttons im WinAmp-Stil.

    Layout mit Textual Button-Widgets:
        [|◄][◄◄][▶ ][►►][►|][■ ] [⇄][↻][♥]

    Alle Buttons sind per Mausklick bedienbar und senden
    ButtonClicked-Messages an die App.
    """

    DEFAULT_CSS = """
    ControlPanel {
        height: 3;
        width: auto;
        layout: horizontal;
        border-right: solid $accent;
        padding: 0 1;
    }

    ControlPanel Button {
        min-width: 6;
        width: auto;
        height: 3;
        margin: 0;
        border: none;
        border-top: none;
        border-bottom: none;
        padding: 0 2;
    }

    /* Default-Button hat eigene -active-Regel mit border-top/border-bottom —
       muss explizit ueberschrieben werden, sonst wirkt der Pressed-State
       groesser als der Button. */
    ControlPanel Button.-active {
        border: none;
        border-top: none;
        border-bottom: none;
        background: $surface-darken-1;
        tint: $accent 20%;
    }

    /* Mode-Buttons mit Luecke zur Transport-Gruppe (gleiche Breite wie Transport) */
    ControlPanel #btn-shuffle {
        margin-left: 1;
    }

    /* Active States */
    ControlPanel Button.active-green {
        color: $success;
    }

    ControlPanel Button.active-yellow {
        color: $warning;
    }

    ControlPanel Button.active-cyan {
        color: $accent;
    }

    ControlPanel Button.active-magenta {
        color: magenta;
    }

    ControlPanel Button.active-red {
        color: $error;
    }

    ControlPanel Button.dim {
        opacity: 50%;
    }
    """

    class ButtonClicked(Message):
        """Wird gesendet wenn ein Button geklickt wird."""

        def __init__(self, action: str) -> None:
            super().__init__()
            self.action = action

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._is_playing = False
        self._is_paused = False
        self._shuffle_on = False
        self._repeat_mode = RepeatMode.OFF
        self._is_favorite = False
        self._has_track = False

    def compose(self) -> ComposeResult:
        """Transport- und Mode-Buttons rendern."""
        # Transport-Gruppe
        yield self._make_btn("|◄", "btn-prev", t("tooltip.prev"))
        yield self._make_btn("◄◄", "btn-seek-back", t("tooltip.seek_back"))
        yield self._make_btn("▶ ", "btn-play-pause", t("tooltip.play_pause"))
        yield self._make_btn("►►", "btn-seek-fwd", t("tooltip.seek_fwd"))
        yield self._make_btn("►|", "btn-next", t("tooltip.next"))
        yield self._make_btn("■ ", "btn-stop", t("tooltip.stop"))
        # Mode-Gruppe (Luecke durch margin-left in CSS)
        yield self._make_btn("⇄", "btn-shuffle", t("tooltip.shuffle"), classes="dim")
        yield self._make_btn("↻", "btn-repeat", t("tooltip.repeat"), classes="dim")
        yield self._make_btn("♥", "btn-favorite", t("tooltip.favorite"), classes="dim")

    @staticmethod
    def _make_btn(label: str, btn_id: str, tooltip: str, classes: str = "") -> Button:
        """Erzeugt einen Button mit Tooltip."""
        btn = Button(label, id=btn_id, classes=classes) if classes else Button(label, id=btn_id)
        btn.tooltip = tooltip
        # Textuals Button setzt line-pad:1. Bei schmalem Inhalt (z.B. "■ ",
        # Content-Bereich nur 2 Zellen) rechnet Textual width-line_pad*2 = 0
        # und stuerzt in chop_cells mit "range() arg 3 must not be zero" ab.
        # line_pad:0 verhindert die Null-Breite. Per CSS nicht moeglich, weil
        # Textuals Integer-Parser den Wert 0 generell ablehnt — daher inline.
        btn.styles.line_pad = 0
        return btn

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Button.Pressed abfangen und als ButtonClicked weiterleiten."""
        event.stop()
        action = _ACTION_MAP.get(event.button.id or "")
        if action:
            self.post_message(self.ButtonClicked(action))

    def update_state(
        self,
        *,
        is_playing: bool = False,
        is_paused: bool = False,
        shuffle_on: bool = False,
        repeat_mode: RepeatMode = RepeatMode.OFF,
        is_favorite: bool = False,
        has_track: bool = False,
    ) -> None:
        """Aktualisiert den angezeigten Status."""
        changed = (
            self._is_playing != is_playing
            or self._is_paused != is_paused
            or self._shuffle_on != shuffle_on
            or self._repeat_mode != repeat_mode
            or self._is_favorite != is_favorite
            or self._has_track != has_track
        )
        self._is_playing = is_playing
        self._is_paused = is_paused
        self._shuffle_on = shuffle_on
        self._repeat_mode = repeat_mode
        self._is_favorite = is_favorite
        self._has_track = has_track
        if changed:
            self._apply_styles()

    def _apply_styles(self) -> None:
        """CSS-Klassen auf Buttons anwenden basierend auf aktuellem State."""
        # Play/Pause — Label und Farbe anpassen
        btn_pp = self.query_one("#btn-play-pause", Button)
        btn_pp.label = "▐▐" if self._is_playing else "▶ "
        btn_pp.remove_class("active-yellow", "active-green")
        if self._is_playing:
            btn_pp.add_class("active-yellow")
        elif self._is_paused:
            btn_pp.add_class("active-green")

        # Stop — nur aktiv wenn Wiedergabe laeuft
        btn_stop = self.query_one("#btn-stop", Button)
        if self._is_playing or self._is_paused:
            btn_stop.remove_class("dim")
        else:
            btn_stop.add_class("dim")

        # Shuffle
        btn_shuf = self.query_one("#btn-shuffle", Button)
        btn_shuf.remove_class("active-green", "dim")
        if self._shuffle_on:
            btn_shuf.add_class("active-green")
        else:
            btn_shuf.add_class("dim")

        # Repeat
        btn_rep = self.query_one("#btn-repeat", Button)
        btn_rep.remove_class("active-cyan", "active-magenta", "dim")
        if self._repeat_mode == RepeatMode.ALL:
            btn_rep.add_class("active-cyan")
        elif self._repeat_mode == RepeatMode.ONE:
            btn_rep.add_class("active-magenta")
        else:
            btn_rep.add_class("dim")

        # Favorite
        btn_fav = self.query_one("#btn-favorite", Button)
        btn_fav.remove_class("active-red", "dim")
        if self._is_favorite:
            btn_fav.add_class("active-red")
        else:
            btn_fav.add_class("dim")
