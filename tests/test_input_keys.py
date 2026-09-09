"""Tasten der App gegen ein fokussiertes Eingabefeld.

Zwei Dinge werden hier abgesichert:

1. Eine `priority`-Bindung der App faengt manche Zeichen ab, bevor ein
   fokussiertes `Input` sie sieht. Bis v0.33.0 traf das "-" und "+" (die
   Lautstaerke) - in das globale Suchfeld liessen sich diese beiden Zeichen
   nicht tippen, obwohl sie in Dateinamen sehr haeufig sind.
2. Der Transport (voriger Titel, Stop, naechster Titel, Sprung) hatte gar
   keine Taste und war nur ueber die Schaltflaechen des Bedienfelds erreichbar.

Der erste Test misst das Verhalten von Textual selbst und leitet daraus ab,
welche Aktionen in `INPUT_EIGENE_TASTEN` gehoeren - er wird also auch dann rot,
wenn spaeter eine neue Taste dazukommt, die dasselbe Problem hat.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input

from retro_amp import app as app_modul
from retro_amp.app import INPUT_EIGENE_TASTEN, RetroAmpApp
from retro_amp.infrastructure import playlist_store as playlist_modul
from retro_amp.infrastructure import session as session_modul
from retro_amp.infrastructure import settings as settings_modul
from retro_amp.infrastructure import single_instance as lock_modul


@pytest.fixture
def isolierte_ablage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Legt ``~/.retro-amp`` fuer die Dauer eines Tests in ein Temp-Verzeichnis.

    Vier Module berechnen ihren Pfad schon beim Import, die Datenbank fragt
    `Path.home()` erst beim Erzeugen - deshalb beides. Ohne das schriebe der
    Test in die echte Ablage des Anwenders.
    """

    heim = tmp_path / "heim"
    ablage = heim / ".retro-amp"
    ablage.mkdir(parents=True)
    musik = tmp_path / "Musik"
    musik.mkdir()
    (ablage / "settings.json").write_text(
        json.dumps({"music_library": str(musik), "last_path": str(musik)}),
        encoding="utf-8",
    )

    monkeypatch.setattr(Path, "home", staticmethod(lambda: heim))
    monkeypatch.setattr(settings_modul, "_SETTINGS_DIR", ablage)
    monkeypatch.setattr(settings_modul, "_SETTINGS_FILE", ablage / "settings.json")
    monkeypatch.setattr(session_modul, "_SESSION_DIR", ablage)
    monkeypatch.setattr(session_modul, "_SESSION_FILE", ablage / "session.json")
    monkeypatch.setattr(lock_modul, "_LOCK_DIR", ablage)
    monkeypatch.setattr(lock_modul, "_LOCK_FILE", ablage / "instance.lock")
    monkeypatch.setattr(lock_modul, "_PLAY_REQUEST", ablage / "play_request")
    monkeypatch.setattr(playlist_modul, "_PLAYLISTS_DIR", ablage / "playlists")
    yield heim


class TestIsolation:
    """Der Test darf die echte Ablage nicht anfassen."""

    def test_home_zeigt_ins_temp_verzeichnis(self, isolierte_ablage: Path) -> None:
        assert Path.home() == isolierte_ablage
        assert settings_modul._SETTINGS_FILE.is_relative_to(isolierte_ablage)


class _Sonde(App[None]):
    """Minimale App mit genau einer Bindung und einem Eingabefeld.

    Damit laesst sich pro Taste messen, ob Textual sie an das Feld durchreicht
    oder ob die Bindung sie vorher abfaengt.
    """

    def __init__(self, taste: str) -> None:
        super().__init__()
        self.ausgeloest = False
        self._bindings.bind(taste, "beweis", "X", priority=True)

    def compose(self) -> ComposeResult:
        yield Input(id="feld")

    def action_beweis(self) -> None:
        self.ausgeloest = True


# Die Tasten der App, die ein einzelnes Zeichen tragen, mit dem Zeichen dazu.
# Nur solche koennen mit einer Texteingabe kollidieren.
ZEICHENTASTEN: dict[str, tuple[str, str]] = {
    # Taste: (Zeichen, Aktion)
    "q": ("q", "quit"),
    "f": ("f", "toggle_favorite"),
    "p": ("p", "show_playlists"),
    "u": ("u", "rename_file"),
    "g": ("g", "auto_title"),
    "t": ("t", "cycle_theme"),
    "s": ("s", "show_settings"),
    "i": ("i", "show_about"),
    "l": ("l", "toggle_log"),
    "c": ("c", "copy_log"),
    "x": ("x", "toggle_shuffle"),
    "r": ("r", "cycle_repeat"),
    "z": ("z", "previous_track"),
    "v": ("v", "stop"),
    "b": ("b", "next_track"),
    "minus": ("-", "volume_down"),
    "plus": ("+", "volume_up"),
    "comma": (",", "seek_backward"),
    "full_stop": (".", "seek_forward"),
    "slash": ("/", "focus_search"),
}


class TestSchluckendeTasten:
    """Welche Tasten Textual dem Eingabefeld vorenthaelt."""

    @pytest.mark.parametrize(("taste", "paar"), sorted(ZEICHENTASTEN.items()))
    async def test_geschluckte_taste_ist_freigegeben(self, taste: str, paar: tuple[str, str]) -> None:
        """Jede Taste, die das Feld nicht erreicht, braucht einen Eintrag.

        Der Test misst erst das Verhalten von Textual und prueft dann die
        Freigabeliste dagegen. Kommt spaeter eine Bindung dazu, die dasselbe
        Problem hat, wird er von selbst rot.
        """

        zeichen, aktion = paar
        sonde = _Sonde(taste)
        async with sonde.run_test() as pilot:
            sonde.query_one("#feld", Input).focus()
            await pilot.pause()
            await pilot.press(zeichen)
            await pilot.pause()
            angekommen = sonde.query_one("#feld", Input).value == zeichen

        if angekommen:
            return
        assert aktion in INPUT_EIGENE_TASTEN, (
            f"Textual reicht {zeichen!r} nicht an das Eingabefeld durch, "
            f"also gehoert {aktion!r} in INPUT_EIGENE_TASTEN."
        )

    async def test_die_sonde_kann_ueberhaupt_schlucken(self) -> None:
        """Gegenprobe: die Messung oben ist nur dann etwas wert, wenn sie
        wenigstens eine geschluckte Taste findet."""

        geschluckt = []
        for taste, (zeichen, _aktion) in ZEICHENTASTEN.items():
            sonde = _Sonde(taste)
            async with sonde.run_test() as pilot:
                sonde.query_one("#feld", Input).focus()
                await pilot.pause()
                await pilot.press(zeichen)
                await pilot.pause()
                if sonde.query_one("#feld", Input).value != zeichen:
                    geschluckt.append(taste)
        assert geschluckt, "Keine einzige Taste wurde abgefangen - die Messung prueft nichts."


class TestSuchfeld:
    """Tippen im globalen Suchfeld der echten Anwendung."""

    GETIPPT = "a-b+c/d.e,f g"

    async def test_alle_zeichen_kommen_an(self, isolierte_ablage: Path) -> None:
        """Bis v0.33.0 fehlten hier '-' und '+'."""

        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            feld = anwendung.query_one("#global-search", Input)
            feld.focus()
            await pilot.pause()
            for zeichen in self.GETIPPT:
                await pilot.press(zeichen)
            await pilot.pause()
            assert feld.value == self.GETIPPT


class TestTransporttasten:
    """Die Tasten fuer Titelwechsel, Stop und Sprung."""

    ERWARTET = {
        "z": "action_previous_track",
        "v": "action_stop",
        "b": "action_next_track",
        ",": "action_seek_backward",
        ".": "action_seek_forward",
    }

    @pytest.mark.parametrize(("zeichen", "methode"), sorted(ERWARTET.items()))
    async def test_taste_loest_die_aktion_aus(
        self,
        zeichen: str,
        methode: str,
        isolierte_ablage: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        anwendung = RetroAmpApp()
        gelaufen: list[str] = []
        monkeypatch.setattr(anwendung, methode, lambda: gelaufen.append(methode))
        async with anwendung.run_test() as pilot:
            anwendung.query_one("#file-table").focus()
            await pilot.pause()
            await pilot.press(zeichen)
            await pilot.pause()
        assert gelaufen == [methode]

    async def test_schraegstrich_springt_ins_suchfeld(self, isolierte_ablage: Path) -> None:
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            anwendung.query_one("#file-table").focus()
            await pilot.pause()
            assert anwendung.focused is not None
            assert anwendung.focused.id != "global-search"
            await pilot.press("/")
            await pilot.pause()
            assert anwendung.focused is not None
            assert anwendung.focused.id == "global-search"


class TestSprachpaket:
    """Die neuen Bindungen brauchen ihre Beschriftungen."""

    @pytest.mark.parametrize("sprache", ["de", "en"])
    def test_beschriftungen_vorhanden(self, sprache: str) -> None:
        pfad = Path(app_modul.__file__).parent / "locale" / f"{sprache}.json"
        texte = json.loads(pfad.read_text(encoding="utf-8"))
        for schluessel in (
            "binding.stop",
            "binding.seek_back",
            "binding.seek_fwd",
            "binding.previous",
            "binding.next",
            "binding.search",
            "tooltip.previous_track",
            "tooltip.next_track",
            "tooltip.seek_backward",
            "tooltip.seek_forward",
            "tooltip.stop",
            "tooltip.focus_search",
        ):
            assert texte.get(schluessel), f"{schluessel} fehlt in {sprache}.json"
