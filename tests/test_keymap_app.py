"""Die Tastenbelegung am laufenden Programm.

`test_keymap.py` prueft die Tabellen. Hier wird gedrueckt: baut die App die
Belegung wirklich so, wechselt sie mit der Einstellung, haengt die Vim-Ebene
tatsaechlich am Widget, und geht die Uebersicht auf.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from retro_amp.app import RetroAmpApp
from retro_amp.screens.keymap_screen import KeymapScreen
from retro_amp.widgets.file_table import FileDataTable
from retro_amp.widgets.folder_browser import FolderBrowser


def _mit_stil(ablage: Path, **werte: Any) -> None:
    """Schreibt Einstellungen in die isolierte Ablage.

    Args:
        ablage: Das Heimverzeichnis aus der Fixture.
        werte: Die zu setzenden Schluessel.
    """

    datei = ablage / ".retro-amp" / "settings.json"
    daten = json.loads(datei.read_text(encoding="utf-8"))
    daten.update(werte)
    datei.write_text(json.dumps(daten), encoding="utf-8")


def _tasten(anwendung: RetroAmpApp, action: str) -> set[str]:
    """Sammelt alle Tasten, die an dieser Aktion haengen."""

    return {
        taste
        for taste, bindungen in anwendung._bindings.key_to_bindings.items()
        for bindung in bindungen
        if bindung.action == action
    }


class TestStilWirktImProgramm:
    """Der Schalter in den Einstellungen aendert die echten Bindungen."""

    async def test_bestandsstil(self, isolierte_ablage: Path) -> None:
        _mit_stil(isolierte_ablage, keymap_style="classic")
        anwendung = RetroAmpApp()
        async with anwendung.run_test():
            assert _tasten(anwendung, "toggle_log") == {"l"}
            assert _tasten(anwendung, "auto_title") == {"g"}

    async def test_ftasten_stil(self, isolierte_ablage: Path) -> None:
        _mit_stil(isolierte_ablage, keymap_style="function_keys")
        anwendung = RetroAmpApp()
        async with anwendung.run_test():
            assert _tasten(anwendung, "toggle_log") == {"f4", "alt+l"}
            assert _tasten(anwendung, "auto_title") == {"f9", "alt+g"}
            assert _tasten(anwendung, "show_about") == {"f1", "i", "I"}

    async def test_f9_loest_die_aktion_aus(
        self,
        isolierte_ablage: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Gebunden ist nicht dasselbe wie wirksam."""

        _mit_stil(isolierte_ablage, keymap_style="function_keys")
        anwendung = RetroAmpApp()
        gelaufen: list[str] = []
        monkeypatch.setattr(anwendung, "action_auto_title", lambda: gelaufen.append("f9"))
        async with anwendung.run_test() as pilot:
            anwendung.query_one("#file-table").focus()
            await pilot.pause()
            await pilot.press("f9")
            await pilot.pause()
        assert gelaufen == ["f9"]

    async def test_eigene_belegung_schlaegt_durch(
        self,
        isolierte_ablage: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _mit_stil(isolierte_ablage, keymap_style="classic", keymap_custom={"cycle_theme": ["alt+t"]})
        anwendung = RetroAmpApp()
        gelaufen: list[str] = []
        monkeypatch.setattr(anwendung, "action_cycle_theme", lambda: gelaufen.append("alt+t"))
        async with anwendung.run_test() as pilot:
            assert _tasten(anwendung, "cycle_theme") == {"alt+t"}
            await pilot.press("alt+t")
            await pilot.pause()
        assert gelaufen == ["alt+t"]


class TestVimEbene:
    """Die Vim-Navigation haengt am Widget, nicht an der App."""

    async def test_aus_bedeutet_keine_bindung(self, isolierte_ablage: Path) -> None:
        _mit_stil(isolierte_ablage, keymap_vim=False)
        anwendung = RetroAmpApp()
        async with anwendung.run_test():
            baum = anwendung.query_one("#folder-browser", FolderBrowser)
            tabelle = anwendung.query_one("#file-data", FileDataTable)
            assert "j" not in baum._bindings.key_to_bindings
            assert "j" not in tabelle._bindings.key_to_bindings

    async def test_an_bindet_baum_und_tabelle(self, isolierte_ablage: Path) -> None:
        _mit_stil(isolierte_ablage, keymap_vim=True)
        anwendung = RetroAmpApp()
        async with anwendung.run_test():
            baum = anwendung.query_one("#folder-browser", FolderBrowser)
            tabelle = anwendung.query_one("#file-data", FileDataTable)
            for taste in ("j", "k", "g", "G", "ctrl+u", "ctrl+d"):
                assert taste in baum._bindings.key_to_bindings, f"Baum: {taste} fehlt"
                assert taste in tabelle._bindings.key_to_bindings, f"Tabelle: {taste} fehlt"

    async def test_baum_bekommt_seine_eigenen_aktionen(self, isolierte_ablage: Path) -> None:
        """Ein Tree kennt weder cursor_left noch scroll_top - er braucht andere.

        Ohne diese Uebersetzung liefe die Taste in eine Aktion, die es gar nicht
        gibt.
        """

        _mit_stil(isolierte_ablage, keymap_vim=True)
        anwendung = RetroAmpApp()
        async with anwendung.run_test():
            baum = anwendung.query_one("#folder-browser", FolderBrowser)
            for taste in ("h", "l", "g", "G"):
                for bindung in baum._bindings.key_to_bindings[taste]:
                    assert hasattr(baum, f"action_{bindung.action}"), (
                        f"{taste} zeigt auf action_{bindung.action}, das der Baum nicht hat"
                    )

    async def test_g_springt_im_baum_an_den_anfang(self, isolierte_ablage: Path) -> None:
        _mit_stil(isolierte_ablage, keymap_vim=True)
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            baum = anwendung.query_one("#folder-browser", FolderBrowser)
            baum.focus()
            await pilot.pause()
            await pilot.press("j", "j")
            await pilot.pause()
            vorher = baum.cursor_line
            await pilot.press("g")
            await pilot.pause()
            assert vorher > 0, "Der Zeiger stand schon oben - der Test prueft nichts."
            assert baum.cursor_line == 0


class TestUebersicht:
    """Die Seite hinter dem Fragezeichen."""

    async def test_fragezeichen_oeffnet_die_uebersicht(self, isolierte_ablage: Path) -> None:
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            anwendung.query_one("#file-table").focus()
            await pilot.pause()
            await pilot.press("question_mark")
            await pilot.pause()
            assert isinstance(anwendung.screen, KeymapScreen)

    async def test_uebersicht_zeigt_jede_aktion(self, isolierte_ablage: Path) -> None:
        from textual.widgets import DataTable

        _mit_stil(isolierte_ablage, keymap_style="function_keys")
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            anwendung.query_one("#file-table").focus()
            await pilot.pause()
            await pilot.press("question_mark")
            await pilot.pause()
            tabelle = anwendung.screen.query_one("#keymap-table", DataTable)
            assert tabelle.row_count == len(anwendung._keymap)


class TestProblemeImLog:
    """Verdeckte Aktionen muessen im Log stehen, nicht nur im Ergebnisobjekt."""

    async def test_vim_kollision_wird_gemeldet(self, isolierte_ablage: Path) -> None:
        _mit_stil(isolierte_ablage, keymap_style="classic", keymap_vim=True)
        anwendung = RetroAmpApp()
        gemeldet: list[str] = []
        async with anwendung.run_test() as pilot:
            anwendung._write_log = lambda message: gemeldet.append(message)  # type: ignore[method-assign]
            anwendung._log_keymap_problems()
            await pilot.pause()
        assert any("toggle_log" in zeile for zeile in gemeldet)
        assert any("auto_title" in zeile for zeile in gemeldet)


class TestEinstellungsdialog:
    """Der Schalter, mit dem der Anwender den Stil wechselt."""

    async def test_reiter_zeigt_den_gespeicherten_stil(self, isolierte_ablage: Path) -> None:
        from textual.widgets import Checkbox, Select

        _mit_stil(isolierte_ablage, keymap_style="classic", keymap_vim=True)
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            anwendung.action_show_settings()
            await pilot.pause()
            auswahl = anwendung.screen.query_one("#select-keymap-style", Select)
            schalter = anwendung.screen.query_one("#check-keymap-vim", Checkbox)
            assert auswahl.value == "classic"
            assert schalter.value is True

    async def test_umschalten_wird_gespeichert(self, isolierte_ablage: Path) -> None:
        from textual.widgets import Button, Select

        _mit_stil(isolierte_ablage, keymap_style="classic", keymap_vim=False)
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            anwendung.action_show_settings()
            await pilot.pause()
            anwendung.screen.query_one("#select-keymap-style", Select).value = "function_keys"
            await pilot.pause()
            anwendung.screen.query_one("#settings-save", Button).press()
            await pilot.pause()
        gespeichert = json.loads((isolierte_ablage / ".retro-amp" / "settings.json").read_text(encoding="utf-8"))
        assert gespeichert["keymap_style"] == "function_keys"
