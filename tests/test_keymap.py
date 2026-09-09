"""Die umschaltbare Tastenbelegung.

Geprueft wird dreierlei: dass die Bestandstabelle zur Anwendung passt (jede
Aktion existiert, jede hat ihre Texte), dass der F-Tasten-Stil genau das tut,
was die Familienkonvention verspricht, und dass die Meldung verdeckter Aktionen
anschlaegt - die ist der eigentliche Sinn der Uebung, denn eine verdeckte Taste
tut lautlos nichts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual_widgets.keymap import KeymapStyle

from retro_amp import app as app_modul
from retro_amp import keymap
from retro_amp.app import RetroAmpApp

SPRACHEN = ("de", "en")


def _texte(sprache: str) -> dict[str, str]:
    """Laedt ein Sprachpaket."""

    pfad = Path(app_modul.__file__).parent / "locale" / f"{sprache}.json"
    daten: dict[str, str] = json.loads(pfad.read_text(encoding="utf-8"))
    return daten


class TestBestandstabelle:
    """Die Tabelle muss zu dem passen, was die Anwendung kann."""

    @pytest.mark.parametrize("action", sorted(keymap.CLASSIC))
    def test_aktion_existiert(self, action: str) -> None:
        """Ein Tippfehler im Aktionsnamen faellt sonst erst am Bildschirm auf."""

        assert hasattr(RetroAmpApp, f"action_{action}"), f"RetroAmpApp hat kein action_{action}"

    @pytest.mark.parametrize("action", sorted(keymap.CLASSIC))
    def test_beschriftung_und_tooltip_vorhanden(self, action: str) -> None:
        assert action in keymap.LABEL_KEYS
        assert action in keymap.TOOLTIP_KEYS

    @pytest.mark.parametrize("sprache", SPRACHEN)
    def test_alle_texte_uebersetzt(self, sprache: str) -> None:
        texte = _texte(sprache)
        fehlend = [
            schluessel
            for tabelle in (keymap.LABEL_KEYS, keymap.TOOLTIP_KEYS)
            for action, schluessel in tabelle.items()
            if action in keymap.CLASSIC and not texte.get(schluessel)
        ]
        assert not fehlend, f"{sprache}.json fehlen: {fehlend}"

    def test_keine_doppelt_belegte_taste(self) -> None:
        """Zwei Aktionen auf derselben Taste waeren ein Auslieferungsfehler."""

        belegt: dict[str, str] = {}
        for action, binding in keymap.CLASSIC.items():
            for taste in binding.keys:
                assert taste not in belegt, f"{taste} liegt auf {belegt[taste]} und auf {action}"
                belegt[taste] = action

    def test_transport_und_suche_sind_noch_da(self) -> None:
        """Regression auf Schritt 1: die Tasten von v0.33.1 bleiben."""

        erwartet = {
            "previous_track": ("z",),
            "stop": ("v",),
            "next_track": ("b",),
            "seek_backward": ("comma",),
            "seek_forward": ("full_stop",),
            "focus_search": ("slash",),
        }
        for action, tasten in erwartet.items():
            assert keymap.CLASSIC[action].keys == tasten


class TestFTastenStil:
    """Was der F-Tasten-Stil aendert - und was er nicht anfassen darf."""

    def test_konvention_wird_eingehalten(self) -> None:
        """F1 Info, F2 Einstellungen, F3 Suche, F4 Log - familienweit gleich."""

        belegung = keymap.resolve({"keymap_style": "function_keys"}).bindings
        assert belegung["show_about"].keys[0] == "f1"
        assert belegung["show_settings"].keys[0] == "f2"
        assert belegung["focus_search"].keys[0] == "f3"
        assert belegung["toggle_log"].keys[0] == "f4"

    def test_f5_und_f6_bleiben_frei(self) -> None:
        """Dort liegen familienweit Aktualisieren und Details, beides fehlt hier."""

        belegung = keymap.resolve({"keymap_style": "function_keys"}).bindings
        vergeben = {taste for binding in belegung.values() for taste in binding.keys}
        assert "f5" not in vergeben
        assert "f6" not in vergeben

    def test_kollidierende_buchstaben_geben_nach(self) -> None:
        """l und g gehoeren der Vim-Ebene, also duerfen sie hier nicht stehen."""

        belegung = keymap.resolve({"keymap_style": "function_keys"}).bindings
        assert "l" not in belegung["toggle_log"].keys
        assert "g" not in belegung["auto_title"].keys
        assert "alt+l" in belegung["toggle_log"].keys
        assert "alt+g" in belegung["auto_title"].keys

    def test_buchstaben_treten_sonst_nur_hinzu(self) -> None:
        """Die F-Taste ersetzt den Buchstaben nicht, ausser er kollidiert."""

        belegung = keymap.resolve({"keymap_style": "function_keys"}).bindings
        for action, buchstabe in (("show_about", "i"), ("show_settings", "s"), ("show_playlists", "p")):
            assert buchstabe in belegung[action].keys

    def test_footer_ist_nach_f_nummer_sortiert(self) -> None:
        belegung = keymap.resolve({"keymap_style": "function_keys"}).bindings
        nummern = [
            int(taste[1:])
            for binding in belegung.values()
            for taste in binding.keys[:1]
            if taste.startswith("f") and taste[1:].isdigit()
        ]
        assert nummern == sorted(nummern)
        assert nummern, "Kein einziger F-Tasten-Eintrag - der Test prueft nichts."

    def test_bestandsstil_bleibt_unangetastet(self) -> None:
        belegung = keymap.resolve({"keymap_style": "classic"}).bindings
        assert belegung["toggle_log"].keys == ("l",)
        assert belegung["auto_title"].keys == ("g",)
        assert all(not taste.startswith("f") or len(taste) == 1 for taste in belegung["show_about"].keys)


class TestVerdeckteAktionen:
    """Die Meldung, um die es eigentlich geht."""

    def test_bestandsstil_mit_vim_meldet_beide_kollisionen(self) -> None:
        probleme = keymap.resolve({"keymap_style": "classic", "keymap_vim": True}).problems
        betroffen = {problem.action for problem in probleme}
        assert "toggle_log" in betroffen
        assert "auto_title" in betroffen

    def test_ftasten_stil_mit_vim_ist_sauber(self) -> None:
        probleme = keymap.resolve({"keymap_style": "function_keys", "keymap_vim": True}).problems
        assert probleme == ()

    def test_ohne_vim_keine_meldung(self) -> None:
        """Gegenprobe: der Vim-Schalter ist wirklich die Ursache."""

        probleme = keymap.resolve({"keymap_style": "classic", "keymap_vim": False}).problems
        assert probleme == ()


class TestEigeneBelegung:
    """keymap_custom aus der Einstellungsdatei."""

    def test_eigene_taste_gewinnt(self) -> None:
        belegung = keymap.resolve({"keymap_style": "classic", "keymap_custom": {"cycle_theme": ["alt+t"]}}).bindings
        assert belegung["cycle_theme"].keys == ("alt+t",)

    def test_unbekannte_aktion_wird_gemeldet(self) -> None:
        ergebnis = keymap.resolve({"keymap_style": "classic", "keymap_custom": {"gibtesnicht": ["z"]}})
        assert any("gibtesnicht" in problem.message for problem in ergebnis.problems)

    def test_quit_kann_nicht_verwaist_werden(self) -> None:
        """Wer q wegnimmt, haengt ohne Ausweg fest - das wird verworfen."""

        ergebnis = keymap.resolve({"keymap_style": "classic", "keymap_custom": {"cycle_theme": ["q"]}})
        assert ergebnis.bindings["quit"].keys == ("q",)
        assert ergebnis.problems


class TestStilVorgabe:
    """Welcher Stil ohne Einstellung gilt."""

    def test_leerer_wert_folgt_der_plattform(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import textual_widgets.keymap as bibliothek

        monkeypatch.setattr(bibliothek.sys, "platform", "darwin")
        assert keymap.style_from_settings({"keymap_style": ""}) is KeymapStyle.CLASSIC
        monkeypatch.setattr(bibliothek.sys, "platform", "win32")
        assert keymap.style_from_settings({"keymap_style": ""}) is KeymapStyle.FUNCTION_KEYS

    def test_unsinniger_wert_faellt_zurueck(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import textual_widgets.keymap as bibliothek

        monkeypatch.setattr(bibliothek.sys, "platform", "win32")
        assert keymap.style_from_settings({"keymap_style": "quatsch"}) is KeymapStyle.FUNCTION_KEYS
