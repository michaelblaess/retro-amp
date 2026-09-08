"""Tests dafuer, dass die Transportleiste ihre Farben aus dem Theme bezieht.

Dieselbe Zusicherung wie beim Visualizer, nur fuer den unteren Bereich des
Fensters: **im Bild darf keine Farbe auftauchen, die nicht in der Palette des
eingestellten Themes steht.** Vor der Umstellung waren Ampelgruen, Warngelb,
Cyan, Magenta und Rot fest im Malcode - dann sahen alle 40 Themes an diesen
Stellen gleich aus.

Der Farbbegriff ist hier weiter gefasst als beim Visualizer: geprueft werden
nicht nur Hex-Werte, sondern **alle** Stilangaben ausser den reinen
Auszeichnungen (bold, dim, ...). Sonst rutschte ausgerechnet der alte Fehler
durch - `green` faengt mit keinem Rautenzeichen an.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import cast

import pytest
from rich.text import Text
from textual.app import App, ComposeResult

from retro_amp.domain.models import AudioTrack, PlaybackState, PlayerState, RepeatMode
from retro_amp.palette import COLOR_FIELDS, PaletteOverride, SurfacePalette
from retro_amp.themes import RETRO_THEMES, surface_palette
from retro_amp.widgets.control_panel import ControlPanel
from retro_amp.widgets.file_table import FileTable
from retro_amp.widgets.transport_bar import TransportBar

# Auszeichnungen ohne eigene Farbe. `dim` ist bewusst erlaubt: es daempft die
# Vordergrundfarbe des Themes, bringt also keine eigene mit.
STIL_WOERTER = frozenset(
    {
        "bold",
        "dim",
        "italic",
        "underline",
        "strike",
        "reverse",
        "blink",
        "none",
        "not",
        "on",
    }
)

# Drei Themes mit deutlich verschiedener Handschrift.
THEMES = ("brotkasten", "classic-terminal", "hercules")


def _stil_farben(text: Text) -> set[str]:
    """Alle Farbangaben aus den Stilen eines Rich-Textes.

    Alles, was keine reine Auszeichnung ist, gilt als Farbe - auch benannte
    Terminalfarben wie `green`. Genau die sollen hier auffallen.
    """
    gefunden: set[str] = set()
    # Der Stil eines Rich-Textes steht entweder an einzelnen Abschnitten oder
    # am Text selbst - die Wiedergabemarke nutzt die zweite Form.
    stile = [str(span.style) for span in text.spans]
    stile.append(str(text.style))
    for stil in stile:
        for teil in stil.split():
            if teil.lower() not in STIL_WOERTER:
                gefunden.add(teil.lower())
    return gefunden


def _erlaubt(palette: SurfacePalette) -> set[str]:
    """Die Farbfelder der Palette - mehr darf im Bild nicht vorkommen."""
    return {str(getattr(palette, feld)).lower() for feld in COLOR_FIELDS}


def _mit_palette(widget: TransportBar | ControlPanel | FileTable, palette: SurfacePalette) -> None:
    """Haengt eine feste Palette an ein Widget ohne laufende Anwendung."""
    widget.palette = lambda: palette  # type: ignore[method-assign]


def _titel() -> AudioTrack:
    return AudioTrack(path=Path("/music/song.mp3"), title="Song", artist="Band", duration_seconds=180.0)


def _transportleiste(palette: SurfacePalette, zustand: PlaybackState) -> Text:
    """Baut eine Transportleiste mit laufendem Titel und zeichnet sie."""
    widget = TransportBar()
    _mit_palette(widget, palette)
    widget.update_state(PlayerState(state=zustand, current_track=_titel(), position_seconds=60.0, volume=0.6))
    return widget.render()


def _bedienfeld(palette: SurfacePalette, **zustand: object) -> Text:
    """Baut ein Bedienfeld in einem bestimmten Zustand und zeichnet es."""
    widget = ControlPanel()
    _mit_palette(widget, palette)
    widget.update_state(**zustand)  # type: ignore[arg-type]
    ergebnis = widget.render()
    assert isinstance(ergebnis, Text)
    return ergebnis


class TestTransportleiste:
    @pytest.mark.parametrize("theme", THEMES)
    @pytest.mark.parametrize("zustand", [PlaybackState.PLAYING, PlaybackState.PAUSED, PlaybackState.STOPPED])
    def test_keine_fremde_farbe(self, theme: str, zustand: PlaybackState) -> None:
        palette = surface_palette(theme)
        benutzt = _stil_farben(_transportleiste(palette, zustand))
        assert benutzt, "die Leiste zeichnet gar keine Farbe"
        fremd = benutzt - _erlaubt(palette)
        assert not fremd, f"Farben ausserhalb des Themes: {sorted(fremd)}"

    def test_zwei_themes_ergeben_zwei_bilder(self) -> None:
        eins = _stil_farben(_transportleiste(surface_palette("brotkasten"), PlaybackState.PLAYING))
        zwei = _stil_farben(_transportleiste(surface_palette("classic-terminal"), PlaybackState.PLAYING))
        assert eins != zwei, "die Leiste sieht in beiden Themes gleich aus"

    def test_laufend_und_angehalten_sind_unterscheidbar(self) -> None:
        palette = surface_palette("brotkasten")
        laeuft = _stil_farben(_transportleiste(palette, PlaybackState.PLAYING))
        pause = _stil_farben(_transportleiste(palette, PlaybackState.PAUSED))
        assert laeuft != pause, "laufende und angehaltene Wiedergabe sehen gleich aus"


class TestBedienfeld:
    """Alle Zustaende, die ueberhaupt eine Farbe setzen."""

    ZUSTAENDE: list[dict[str, object]] = [
        {"has_track": True},
        {"is_playing": True, "has_track": True},
        {"is_paused": True, "has_track": True},
        {"shuffle_on": True, "has_track": True},
        {"repeat_mode": RepeatMode.ALL, "has_track": True},
        {"repeat_mode": RepeatMode.ONE, "has_track": True},
        {"is_favorite": True, "has_track": True},
    ]

    @pytest.mark.parametrize("theme", THEMES)
    @pytest.mark.parametrize("zustand", ZUSTAENDE)
    def test_keine_fremde_farbe(self, theme: str, zustand: dict[str, object]) -> None:
        palette = surface_palette(theme)
        benutzt = _stil_farben(_bedienfeld(palette, **zustand))
        assert benutzt, "das Bedienfeld zeichnet gar keine Farbe"
        fremd = benutzt - _erlaubt(palette)
        assert not fremd, f"Farben ausserhalb des Themes: {sorted(fremd)}"

    def test_hover_faerbt_die_ganze_kachel_aus_dem_theme(self) -> None:
        palette = surface_palette("hercules")
        widget = ControlPanel()
        _mit_palette(widget, palette)
        widget._hover_action = "play_pause"
        ergebnis = widget.render()
        assert isinstance(ergebnis, Text)
        benutzt = _stil_farben(ergebnis)
        assert palette.transport_hover.lower() in benutzt, "der Hover-Ton kommt nicht aus der Palette"
        assert not benutzt - _erlaubt(palette)

    def test_zwei_themes_ergeben_zwei_bilder(self) -> None:
        eins = _stil_farben(_bedienfeld(surface_palette("brotkasten"), is_playing=True, has_track=True))
        zwei = _stil_farben(_bedienfeld(surface_palette("classic-terminal"), is_playing=True, has_track=True))
        assert eins != zwei, "das Bedienfeld sieht in beiden Themes gleich aus"


class TestWiedergabemarke:
    """Der Pfeil vor dem laufenden Titel in der Dateitabelle."""

    def test_marke_kommt_aus_dem_theme(self) -> None:
        palette = surface_palette("brotkasten")
        widget = FileTable()
        _mit_palette(widget, palette)
        titel = _titel()
        widget._playing_path = titel.path

        ergebnis = widget._format_name(titel)
        assert isinstance(ergebnis, Text), "der laufende Titel bekommt keine Marke"
        benutzt = _stil_farben(ergebnis)
        assert benutzt == {palette.accent_on.lower()}

    def test_ohne_wiedergabe_bleibt_es_ein_reiner_name(self) -> None:
        widget = FileTable()
        _mit_palette(widget, surface_palette("brotkasten"))
        assert widget._format_name(_titel()) == _titel().display_name


class TestKuenstlichePalette:
    """Die schaerfste Fassung: eine Palette aus lauter erfundenen Farben.

    Kommt danach noch irgendeine andere Farbe im Bild vor, stammt sie aus dem
    Malcode und nicht aus dem Theme.
    """

    def _erfunden(self) -> SurfacePalette:
        echte = surface_palette("brotkasten")
        ersatz = cast(
            "PaletteOverride",
            {feld: f"#{index * 7 + 16:02x}00{index * 11 + 32:02x}" for index, feld in enumerate(COLOR_FIELDS)},
        )
        return dataclasses.replace(echte, **ersatz)

    def test_transportleiste(self) -> None:
        palette = self._erfunden()
        for zustand in (PlaybackState.PLAYING, PlaybackState.PAUSED, PlaybackState.STOPPED):
            benutzt = _stil_farben(_transportleiste(palette, zustand))
            assert benutzt <= _erlaubt(palette), f"eigene Farben: {sorted(benutzt - _erlaubt(palette))}"

    def test_bedienfeld(self) -> None:
        palette = self._erfunden()
        for zustand in TestBedienfeld.ZUSTAENDE:
            benutzt = _stil_farben(_bedienfeld(palette, **zustand))
            assert benutzt <= _erlaubt(palette), f"eigene Farben: {sorted(benutzt - _erlaubt(palette))}"


class _MitzaehlendeLeiste(TransportBar):
    """Transportleiste, die mitzaehlt, wie oft sie gezeichnet wurde."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.bilder = 0

    def render(self) -> Text:
        self.bilder += 1
        return super().render()


class _Probe(App[None]):
    """Kleinstmoegliche Anwendung mit den echten Themes."""

    def __init__(self) -> None:
        super().__init__()
        for theme in RETRO_THEMES:
            self.register_theme(theme)

    def compose(self) -> ComposeResult:
        yield _MitzaehlendeLeiste(id="leiste")


class TestThemewechsel:
    """Der Wechsel muss von allein bis in die Leiste durchschlagen.

    Der Visualizer zeichnet zwoelfmal je Sekunde und holt sich die neue Farbe
    dabei ohnehin. Die Transportleiste zeichnet nur auf Anlass - wenn Textual
    beim Themewechsel kein neues Bild anfordert, bliebe sie in der alten Farbe
    stehen. Deshalb wird hier NICHT von Hand `render()` gerufen, sondern
    gezaehlt, ob es von selbst passiert.
    """

    async def test_leiste_zieht_von_allein_nach(self) -> None:
        app = _Probe()
        async with app.run_test() as pilot:
            leiste = app.query_one("#leiste", _MitzaehlendeLeiste)
            leiste.update_state(PlayerState(state=PlaybackState.PLAYING, current_track=_titel(), position_seconds=60.0))
            app.theme = "brotkasten"
            await pilot.pause()
            vorher = leiste.bilder
            eins = _stil_farben(leiste.render())

            app.theme = "classic-terminal"
            await pilot.pause()
            nachher = leiste.bilder
            zwei = _stil_farben(leiste.render())

        # Das zweite `render()` oben zaehlt selbst mit, deshalb der Abstand > 1.
        assert nachher - vorher > 1, "nach dem Themewechsel wurde die Leiste nicht neu gezeichnet"
        assert eins != zwei, "die Leiste zeigt nach dem Themewechsel dieselben Farben"
