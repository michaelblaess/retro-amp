"""Control-Panel Widget — Keycap-Deck im Hi-Fi/Tape-Deck-Stil.

Statt einzelner Textual-``Button``-Widgets wird das Transport-Panel als ein
custom-gerendertes Widget gezeichnet: jede Funktion sitzt in einer per
Box-Drawing verbundenen Tastenkappe (wie eine echte Hardware-Tastenreihe).
Aktive Zustaende (Play/Pause, Shuffle, Repeat, Favorit) lassen die jeweilige
Taste invertiert "aufleuchten"; inaktive Mode-Tasten sind dezente Text-Labels
statt gedimmter Icons.

Klicks werden ueber die x/y-Position auf die Tasten-Regionen abgebildet
(gleiches Prinzip wie die Volume-/Seek-Bar in der ``TransportBar``). Die
oeffentliche API (``ButtonClicked``-Message + ``update_state``) bleibt
identisch zur frueheren Button-Variante, damit die App unveraendert bleibt.

Glyph-Wahl: bewusst nur einfach-breite BMP-Zeichen (◄ ► ▶ ■ ▐ ♥, Pipe), die
auf Windows/Segoe monochrom und mit fester Breite rendern. Echte Media-Symbole
(⏮ ⏯ ⏭) wuerden als doppelweite Farb-Emoji erscheinen und das Spalten-Raster
der Tastenkappen zerreissen.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import RenderResult
from textual.events import Click, Leave, MouseMove
from textual.message import Message
from textual.widget import Widget

from ..domain.models import RepeatMode
from ..palette import SurfacePalette
from .palette_source import PaletteSource

# Linker Innenabstand (CSS padding: 0 2) — muss beim Klick-Mapping abgezogen
# werden, weil ``event.offset.x`` das Padding mitzaehlt.
_PAD_LEFT = 2

# Luecke (Spalten) zwischen Transport- und Mode-Gruppe.
_GAP = 1

# Grundstil der nicht-leuchtenden Glyphen.
_BASE = ""


class ControlPanel(PaletteSource, Widget):
    """Keycap-Deck mit Transport- und Mode-Tasten.

    Layout (3 Zeilen hoch), jede Taste eine eigene, direkt anschliessende Box::

        ┌───┐┌───┐┌───┐┌───┐┌───┐┌───┐ ┌─────┐┌─────┐┌─────┐
        │|◄ ││◄◄ ││ ▶ ││►► ││►| ││ ■ │ │SHUF ││ RPT ││  ♥  │
        └───┘└───┘└───┘└───┘└───┘└───┘ └─────┘└─────┘└─────┘

    Aktive Tasten faerben ihr Glyph mit einer Farbe des eingestellten Themes
    (Handlung anhalten/weiter, eingeschalteter Umschalter, gesetzter Favorit).
    Beim Hover wird die GANZE Kachel dezent getoent (Rahmen + Hintergrund).
    Keine Farbe steht in diesem Modul - alle kommen aus `SurfacePalette`.
    """

    DEFAULT_CSS = """
    ControlPanel {
        height: 3;
        width: auto;
        border-right: solid $accent;
        padding: 0 2;
    }
    """

    class ButtonClicked(Message):
        """Wird gesendet wenn eine Taste geklickt wird."""

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
        # Klick-Regionen: (x_start, x_end, action) — in Content-Spalten
        # (nach Padding), in render() neu berechnet.
        self._regions: list[tuple[int, int, str]] = []
        # Action der Taste unter dem Mauszeiger (None = kein Hover).
        self._hover_action: str | None = None

    # --- Public API (unveraendert zur Button-Variante) ---

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
        """Aktualisiert den angezeigten Status und zeichnet neu."""
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
            self.refresh()

    # --- Rendering ---

    def render(self) -> RenderResult:
        """Zeichnet das dreizeilige Keycap-Deck und merkt sich die Klick-Regionen."""
        top = Text(no_wrap=True)
        mid = Text(no_wrap=True)
        bot = Text(no_wrap=True)
        regions: list[tuple[int, int, str]] = []

        colors = self.palette()
        hover_bg = colors.transport_hover
        frame = colors.divider

        x = 0
        x = self._emit_group(top, mid, bot, regions, self._transport_keys(colors), hover_bg, frame, x)

        gap = " " * _GAP
        top.append(gap)
        mid.append(gap)
        bot.append(gap)
        x += _GAP

        self._emit_group(top, mid, bot, regions, self._mode_keys(colors), hover_bg, frame, x)
        self._regions = regions

        result = Text(no_wrap=True)
        result.append_text(top)
        result.append("\n")
        result.append_text(mid)
        result.append("\n")
        result.append_text(bot)
        return result

    def _emit_group(
        self,
        top: Text,
        mid: Text,
        bot: Text,
        regions: list[tuple[int, int, str]],
        keys: list[tuple[str, str, str, str]],
        hover_bg: str,
        frame: str,
        start_x: int,
    ) -> int:
        """Haengt eine Tastengruppe als getrennte Boxen an die drei Zeilen an.

        ``keys`` ist eine Liste von (action, interior, mode, color). Jede Taste
        ist eine eigene Box (┌─┐│└┘), die direkt an die naechste anschliesst — so
        kann beim Hover die GANZE Kachel (Rahmen + Inneres, alle 3 Zeilen)
        eingefaerbt werden, ohne dass sich benachbarte Tasten einen Rahmen
        teilen. Alle Glyphen sind einfach-breit, daher ist ``len(interior)``
        gleich der Zell-Breite. Die Klick-/Hover-Region umfasst die ganze Box.
        Rueckgabe: die naechste freie Spalte.
        """
        x = start_x
        for action, interior, mode, color in keys:
            width = len(interior)
            box_width = width + 2
            border_style, glyph_style = self._styles_for(action, mode, color, hover_bg, frame)

            top.append("┌" + "─" * width + "┐", style=border_style)
            mid.append("│", style=border_style)
            mid.append(interior, style=glyph_style)
            mid.append("│", style=border_style)
            bot.append("└" + "─" * width + "┘", style=border_style)

            regions.append((x, x + box_width, action))
            x += box_width
        return x

    def _styles_for(self, action: str, mode: str, color: str, hover_bg: str, frame: str) -> tuple[str, str]:
        """Liefert (Rahmen-Stil, Glyph-Stil) je nach Zustand und Hover.

        - Hover: ganze Kachel dezent getoent (Rahmen + Inneres), Glyph fett.
        - Aktiv: nur farbiges, fettes Glyph (kein greller Voll-Kasten),
          Rahmen bleibt dezent.
        - Inaktiv/Muted: gedimmtes Glyph, dezenter Rahmen.
        """
        hovered = action == self._hover_action
        if hovered:
            tint = f"on {hover_bg}"
            glyph_color = color if mode == "active" else ""
            glyph = f"bold {glyph_color} {tint}".replace("  ", " ").strip()
            return tint, glyph
        if mode == "active":
            return frame, f"bold {color}"
        if mode == "muted":
            return frame, "dim"
        return frame, _BASE

    def _transport_keys(self, colors: SurfacePalette) -> list[tuple[str, str, str, str]]:
        """Transport-Tasten (Innenbreite 3): (action, interior, mode, color).

        ``mode`` ist "active" (farbiges Glyph), "muted" (gedimmt) oder "normal".
        """
        if self._is_playing:
            # Laeuft → Pause-Symbol (zwei zentrierte Vollbalken mit Luecke),
            # gelb. Kein Voll-Kasten mehr — nur das Glyph faerbt sich.
            play_pause = ("play_pause", "┃ ┃", "active", colors.accent_hold)
        elif self._is_paused:
            # Pausiert → Play-Symbol, gruen.
            play_pause = ("play_pause", " ▶ ", "active", colors.accent_on)
        else:
            play_pause = ("play_pause", " ▶ ", "normal", "")

        stop_mode = "normal" if (self._is_playing or self._is_paused) else "muted"

        return [
            ("prev", "|◄ ", "normal", ""),
            ("seek_back", "◄◄ ", "normal", ""),
            play_pause,
            ("seek_fwd", "►► ", "normal", ""),
            ("next", "►| ", "normal", ""),
            ("stop", " ■ ", stop_mode, ""),
        ]

    def _mode_keys(self, colors: SurfacePalette) -> list[tuple[str, str, str, str]]:
        """Mode-Tasten (Innenbreite 5): aktiv = farbiges Glyph, aus = dim-Label.

        Eingeschaltete Umschalter tragen dieselbe Akzentfarbe des Themes -
        was sie unterscheidet, steht als Beschriftung darin (SHUF, RPT, RPT1).
        Frueher waren es feste Farben der Terminal-Palette, in jedem Theme
        dieselben.
        """
        shuffle = (
            ("shuffle", "SHUF".center(5), "active", colors.accent_on)
            if self._shuffle_on
            else ("shuffle", "SHUF".center(5), "muted", "")
        )

        if self._repeat_mode == RepeatMode.ALL:
            repeat = ("repeat", "RPT".center(5), "active", colors.transport_active)
        elif self._repeat_mode == RepeatMode.ONE:
            # "RPT1" signalisiert Repeat-One (vs. Repeat-All).
            repeat = ("repeat", "RPT1".center(5), "active", colors.transport_active)
        else:
            repeat = ("repeat", "RPT".center(5), "muted", "")

        favorite = (
            ("favorite", "♥".center(5), "active", colors.accent_hot)
            if self._is_favorite
            else ("favorite", "♥".center(5), "muted", "")
        )

        return [shuffle, repeat, favorite]

    # --- Interaktion ---

    def on_click(self, event: Click) -> None:
        """Klick auf eine Tastenkappe → ``ButtonClicked`` mit passender Action."""
        action = self._action_at(event.offset.x)
        if action is not None:
            event.stop()
            self.post_message(self.ButtonClicked(action))

    def on_mouse_move(self, event: MouseMove) -> None:
        """Hover-Taste anhand der Mausposition ermitteln und ggf. neu zeichnen."""
        new_hover = self._action_at(event.offset.x)
        if new_hover != self._hover_action:
            self._hover_action = new_hover
            self.refresh()

    def on_leave(self, event: Leave) -> None:
        """Maus hat das Panel verlassen → Hover zuruecksetzen."""
        if self._hover_action is not None:
            self._hover_action = None
            self.refresh()

    def _action_at(self, offset_x: int) -> str | None:
        """Mappt eine x-Position (inkl. Padding) auf die getroffene Tasten-Action."""
        cx = offset_x - _PAD_LEFT
        for x0, x1, action in self._regions:
            if x0 <= cx < x1:
                return action
        return None
