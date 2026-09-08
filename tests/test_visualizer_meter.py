"""Tests fuer die Verdrahtung des Pegelverhaltens im Visualizer-Widget.

Das Zeitverhalten selbst liegt in `retro_amp.meter` und wird dort geprueft.
Hier geht es um die Anschluesse, an denen beim Umbau Fehler entstehen: haelt
der Takt beim Anhalten wirklich durch, bis nichts mehr zu sehen ist, und wird
er danach auch wieder abgestellt?

Der Visualizer laesst sich fuer `_tick` ohne laufende Textual-App bauen. Nur
`start()` geht nicht, weil `set_interval` eine App braucht - deshalb wird der
Zeitgeber hier von Hand gesetzt.
"""

from __future__ import annotations

from retro_amp.widgets.visualizer import _MAX_LEVEL, Visualizer


class FakeTimer:
    """Ersatz fuer das Handle aus `set_interval`."""

    def __init__(self) -> None:
        self.gestoppt = False

    def stop(self) -> None:
        self.gestoppt = True


class Pruefstand:
    """Ein Visualizer mit gestellter Uhr und fester Datenquelle."""

    def __init__(self, pegel: float = 1.0) -> None:
        self.jetzt = 0.0
        self.timer = FakeTimer()
        self.widget = Visualizer()
        self.widget._clock = lambda: self.jetzt
        self.widget.set_spectrum_source(lambda: [pegel] * Visualizer.NUM_BARS)
        self.widget._timer_handle = self.timer
        self.widget._active = True

    def bilder(self, anzahl: int, takt: float = 1 / 12) -> None:
        for _ in range(anzahl):
            self.jetzt += takt
            self.widget._tick()

    @property
    def hoechster_balken(self) -> int:
        return max(self.widget._bars)

    @property
    def hoechste_spitze(self) -> int:
        return max(self.widget._peaks)


class TestAnzeigeLaeuft:
    def test_balken_steigen_bei_zufuhr(self) -> None:
        stand = Pruefstand()
        stand.bilder(20)
        assert stand.hoechster_balken > 0
        assert stand.hoechste_spitze >= stand.hoechster_balken

    def test_balken_bleiben_in_der_skala(self) -> None:
        stand = Pruefstand()
        stand.bilder(60)
        assert 0 <= stand.hoechster_balken <= _MAX_LEVEL
        assert 0 <= stand.hoechste_spitze <= _MAX_LEVEL


class TestAusklingen:
    """Beim Anhalten faellt die Anzeige ab - sie friert nicht ein."""

    def test_erstes_bild_nach_stop_ist_nicht_leer(self) -> None:
        stand = Pruefstand()
        stand.bilder(20)
        vorher = stand.hoechster_balken
        assert vorher > 0

        stand.widget.stop()
        stand.bilder(1)
        assert 0 < stand.hoechster_balken < vorher, "die Anzeige springt beim Anhalten auf Null, statt auszuklingen"

    def test_takt_laeuft_waehrend_des_ausklingens_weiter(self) -> None:
        stand = Pruefstand()
        stand.bilder(20)
        stand.widget.stop()
        stand.bilder(1)
        assert not stand.timer.gestoppt
        assert stand.widget._timer_handle is stand.timer

    def test_takt_endet_erst_wenn_nichts_mehr_zu_sehen_ist(self) -> None:
        stand = Pruefstand()
        stand.bilder(20)
        stand.widget.stop()
        stand.bilder(40)

        assert stand.hoechster_balken == 0
        assert stand.hoechste_spitze == 0
        assert stand.timer.gestoppt
        assert stand.widget._timer_handle is None

    def test_stop_ohne_laufenden_takt_stuerzt_nicht_ab(self) -> None:
        widget = Visualizer()
        widget.stop()
        assert widget._timer_handle is None


class TestReset:
    def test_reset_raeumt_sofort_und_haelt_den_takt_an(self) -> None:
        stand = Pruefstand()
        stand.bilder(20)
        assert stand.hoechster_balken > 0

        stand.widget.reset()
        assert stand.hoechster_balken == 0
        assert stand.hoechste_spitze == 0
        assert stand.timer.gestoppt
        assert stand.widget._timer_handle is None

    def test_nach_reset_bleibt_die_anzeige_leer(self) -> None:
        stand = Pruefstand()
        stand.bilder(20)
        stand.widget.reset()
        # Der Takt ist weg, aber ein verspaetetes Bild darf nichts wiederbeleben.
        stand.bilder(3)
        assert stand.hoechster_balken == 0


class TestBildratenUnabhaengig:
    """Dasselbe Bild bei 12 und bei 60 Bildern je Sekunde."""

    def test_stand_nach_gleicher_zeit_ist_gleich(self) -> None:
        staende: list[int] = []
        for bilder in (12, 60):
            stand = Pruefstand()
            stand.bilder(round(bilder * 2.0), takt=1 / bilder)  # zwei Sekunden Zufuhr
            stand.widget.stop()
            stand.bilder(round(bilder * 0.5), takt=1 / bilder)  # halbe Sekunde Abfall
            staende.append(stand.hoechster_balken)

        assert 0 < staende[0] < _MAX_LEVEL, f"Messpunkt taugt nicht: {staende[0]}"
        assert staende[0] == staende[1], f"12 Bilder ergeben Stufe {staende[0]}, 60 Bilder Stufe {staende[1]}"
