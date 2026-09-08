"""Tests fuer die abgeleiteten Farben in Textuals Stylesheets.

Die selbstgezeichneten Flaechen holen ihre Farben aus `SurfacePalette`. Alles
andere - Rahmen, Titelzeilen, Auswahl - beschreibt Textual-CSS, und das kannte
bisher nur die elf Grundfarben des Themes. `css_variables` schlaegt die
Bruecke: jedes Feld der Palette wird als `$ra-...` verfuegbar.

Zwei Dinge muessen dafuer stimmen, und beide koennen unbemerkt kaputtgehen:

- Die Namen im Stylesheet und die erzeugten Namen muessen zueinander passen.
  Ein Tippfehler in `app.tcss` faellt sonst erst beim Start auf.
- Das App-Stylesheet muss das `DEFAULT_CSS` eines Widgets uebersteuern. Sonst
  behalten die Widgets ihre Grundfarben, und die Ableitung wirkt nirgends.

Nicht abgedeckt: die Verdrahtung in `RetroAmpApp.get_css_variables` selbst.
Deren Konstruktor oeffnet die echte Datenbank und schreibt Einstellungen, eine
Testinstanz wuerde also Michaels Daten anfassen. Geprueft wird hier dieselbe
Funktion mit demselben Stylesheet in einer eigenen Anwendung.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult

import retro_amp
from retro_amp.app import RetroAmpApp
from retro_amp.palette import COLOR_FIELDS, OPACITY_FIELDS
from retro_amp.themes import CSS_PRAEFIX, RETRO_THEMES, css_variables, surface_palette
from retro_amp.widgets.control_panel import ControlPanel
from retro_amp.widgets.file_table import FileTable

APP_TCSS = Path(retro_amp.__file__).parent / "app.tcss"


class TestErzeugteVariablen:
    def test_jedes_feld_wird_angeboten(self) -> None:
        werte = css_variables(surface_palette("brotkasten"))
        fehlend = [feld for feld in COLOR_FIELDS + OPACITY_FIELDS if CSS_PRAEFIX + feld.replace("_", "-") not in werte]
        assert not fehlend, f"nicht als CSS-Variable angeboten: {fehlend}"

    def test_namen_entstehen_mechanisch(self) -> None:
        # Kein von Hand gepflegtes Verzeichnis - sonst fehlt beim naechsten
        # neuen Feld genau der Eintrag, den niemand vermisst.
        werte = css_variables(surface_palette("brotkasten"))
        assert werte["ra-vis-low"].startswith("#")
        assert werte["ra-lcd-foreground"].startswith("#")
        assert len(werte) == len(COLOR_FIELDS) + len(OPACITY_FIELDS)

    def test_deckkraft_kommt_als_prozent(self) -> None:
        # Textual erwartet die Deckkraft hinter einer Farbe als Prozentwert.
        werte = css_variables(surface_palette("brotkasten"))
        assert werte["ra-opacity-hover"].endswith("%")
        assert werte["ra-opacity-normal"] == "100%"

    @pytest.mark.parametrize("theme", [t.name for t in RETRO_THEMES[:5]])
    def test_werte_folgen_dem_theme(self, theme: str) -> None:
        palette = surface_palette(theme)
        werte = css_variables(palette)
        assert werte["ra-divider"] == palette.divider
        assert werte["ra-header"] == palette.header


class _Probe(App[None]):
    """Anwendung mit dem echten Stylesheet und den echten Variablen."""

    CSS_PATH = APP_TCSS

    def __init__(self) -> None:
        super().__init__()
        for theme in RETRO_THEMES:
            self.register_theme(theme)

    def get_css_variables(self) -> dict[str, str]:
        return {**super().get_css_variables(), **css_variables(surface_palette(str(self.theme)))}

    def compose(self) -> ComposeResult:
        yield ControlPanel(id="bedienfeld")
        yield FileTable(id="dateien")


class _OhneAufbau(RetroAmpApp):
    """RetroAmpApp ohne ihren Konstruktor.

    Der echte oeffnet die Datenbank, wandert alte Playlists ein und schreibt
    Einstellungen - in einem Test hiesse das, an Michaels Daten zu ruehren.
    Hier wird nur `App.__init__` aufgerufen. Das reicht fuer die eine Frage,
    um die es geht: greift die Ueberschreibung von `get_css_variables`, und
    liefert sie die abgeleiteten Werte mit?
    """

    def __init__(self) -> None:
        App.__init__(self)


class TestAppVerdrahtung:
    def test_die_anwendung_reicht_die_abgeleiteten_werte_durch(self) -> None:
        app = _OhneAufbau()
        werte = app.get_css_variables()
        # Textuals eigene sind weiter da ...
        assert "accent" in werte
        # ... und die abgeleiteten kommen dazu.
        assert werte["ra-divider"] == surface_palette(str(app.theme)).divider


class TestStylesheet:
    """Das Stylesheet muss die Variablen kennen und die Widgets uebersteuern."""

    # Bewusst NICHT brotkasten: das ist das Standard-Theme, auf das
    # `surface_palette` bei jedem unbekannten Namen zurueckfaellt. Eine
    # Zusicherung dagegen waere auch dann gruen, wenn gar kein Theme greift.
    PRUEFTHEMA = "classic-terminal"

    async def test_rahmen_nimmt_die_trennlinienfarbe(self) -> None:
        app = _Probe()
        async with app.run_test() as pilot:
            app.theme = self.PRUEFTHEMA
            await pilot.pause()
            palette = surface_palette(self.PRUEFTHEMA)
            bedienfeld = app.query_one("#bedienfeld", ControlPanel)
            _, farbe = bedienfeld.styles.border_right
            assert farbe.hex.lower() == palette.divider.lower(), (
                "der Rahmen steht noch auf der Akzentfarbe - app.tcss uebersteuert das DEFAULT_CSS nicht"
            )

    async def test_titelzeile_der_dateiliste_nimmt_den_flaechenton(self) -> None:
        app = _Probe()
        async with app.run_test() as pilot:
            app.theme = self.PRUEFTHEMA
            await pilot.pause()
            palette = surface_palette(self.PRUEFTHEMA)
            zeile = app.query_one("#file-info")
            assert zeile.styles.background.hex.lower() == palette.header.lower()

    async def test_themewechsel_zieht_die_variablen_nach(self) -> None:
        # Textual erneuert das Stylesheet erst im naechsten Durchlauf der
        # Nachrichtenschleife (`call_next(refresh_css)`), deshalb `pause()`.
        app = _Probe()
        async with app.run_test() as pilot:
            app.theme = "brotkasten"
            await pilot.pause()
            bedienfeld = app.query_one("#bedienfeld", ControlPanel)
            _, eins = bedienfeld.styles.border_right

            app.theme = self.PRUEFTHEMA
            await pilot.pause()
            _, zwei = bedienfeld.styles.border_right

        assert eins != zwei, "der Rahmen behaelt nach dem Themewechsel seine Farbe"
        assert zwei.hex.lower() == surface_palette(self.PRUEFTHEMA).divider.lower()
