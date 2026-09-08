"""Tests fuer das Zeitverhalten der Pegelanzeige.

Die Uhr kommt bei jedem Aufruf von aussen herein. Deshalb laufen auch die
Tests ueber mehrere Sekunden Ausklingen in Millisekunden durch, und deshalb
sind sie ueberhaupt moeglich - mit einem eingebauten Zeitgeber liesse sich
nichts davon ohne laufende Oberflaeche pruefen.

Die Pruefungen, die wirklich etwas finden koennen:

- `TestBildratenUnabhaengig` - genau die Eigenschaft, um derentwillen der
  Umbau stattfand. Mit dem alten bildbasierten Abfall ist sie verletzt.
- `TestAusklingen`           - die Anzeige friert beim Anhalten nicht ein
- `TestAbgleich`             - Konstanten laufen nicht gegen `spectrum` weg
- `TestOhneOberflaeche`      - der Baustein bindet sich nicht an eine UI
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from retro_amp.meter import (
    DB_FLOOR,
    DEFAULT_WINDOW_S,
    LevelMeter,
    MeterConfig,
    PeakTracker,
)


def _voll(meter: LevelMeter, start: float = 0.0) -> float:
    """Faehrt die Anzeige auf Vollausschlag und gibt die Endzeit zurueck."""
    jetzt = start
    meter.update([1.0] * meter.bands, jetzt)
    for _ in range(30):
        jetzt += 0.05
        meter.update([1.0] * meter.bands, jetzt)
    return jetzt


class TestBildratenUnabhaengig:
    """Der Grund fuer den ganzen Umbau: der Abfall haengt an der Zeit."""

    # Eine halbe Sekunde ist mit Bedacht gewaehlt: sie geht bei 12 und bei 60
    # Bildern je Sekunde glatt auf (6 beziehungsweise 30 Bilder), und die
    # Anzeige steht danach bei der Haelfte - also mitten im Fall. Nach einer
    # vollen Sekunde laegen beide auf dem Boden, und der Vergleich waere
    # immer gruen, auch mit dem alten bildbasierten Abfall.
    MESSDAUER_S = 0.5

    def test_gleiche_zeit_gleicher_stand_egal_wie_viele_bilder(self) -> None:
        staende: list[float] = []
        for bilder in (12, 60):
            meter = LevelMeter(4)
            jetzt = _voll(meter)
            schritt = 1.0 / bilder
            for _ in range(round(bilder * self.MESSDAUER_S)):
                jetzt += schritt
                meter.advance(jetzt)
            staende.append(meter.levels[0])

        # Mitten im Fall, nicht am Boden - sonst prueft der Vergleich nichts.
        assert 0.05 < staende[0] < 0.95, f"Messpunkt taugt nicht: {staende[0]:.4f}"
        assert staende[0] == pytest.approx(staende[1], abs=1e-9), (
            f"12 Bilder ergeben {staende[0]:.6f}, 60 Bilder {staende[1]:.6f} - der Abfall haengt an der Bildrate"
        )

    def test_ein_grosser_schritt_wie_viele_kleine(self) -> None:
        grob = LevelMeter(1)
        fein = LevelMeter(1)
        _voll(grob)
        _voll(fein)

        grob.advance(1.5 + 0.5)  # _voll endet bei 1.5
        jetzt = 1.5
        for _ in range(50):
            jetzt += 0.01
            fein.advance(jetzt)

        assert grob.levels[0] == pytest.approx(fein.levels[0], abs=1e-9)

    def test_abfall_entspricht_der_angegebenen_rate(self) -> None:
        # 60 dB/s ueber eine halbe Sekunde sind 30 dB, also die halbe Skala.
        meter = LevelMeter(1, MeterConfig(bar_decay_db_per_s=60.0))
        jetzt = _voll(meter)
        meter.advance(jetzt + 0.5)
        assert meter.levels[0] == pytest.approx(0.5, abs=1e-9)


class TestSpitzen:
    def test_spitze_haelt_die_haltezeit(self) -> None:
        config = MeterConfig(peak_hold_s=0.4)
        meter = LevelMeter(1, config)
        jetzt = _voll(meter)
        oben = meter.peaks[0]

        # Kurz vor Ablauf der Haltezeit steht die Marke noch.
        meter.advance(jetzt + config.effective_hold_s - 0.01)
        assert meter.peaks[0] == pytest.approx(oben)

        # Danach faellt sie.
        meter.advance(jetzt + config.effective_hold_s + 0.2)
        assert meter.peaks[0] < oben

    def test_haltezeit_ist_mindestens_ein_analysefenster(self) -> None:
        # Auch wenn jemand die Haltezeit auf Null setzt, muss eine Spitze so
        # lange stehen bleiben, wie das Fenster gemessen hat. Sonst zeigt die
        # Anzeige einen Wert kuerzer, als er ueberhaupt erfasst wurde.
        config = MeterConfig(peak_hold_s=0.0, window_s=0.05)
        assert config.effective_hold_s == pytest.approx(0.05)

        meter = LevelMeter(1, config)
        jetzt = _voll(meter)
        oben = meter.peaks[0]
        meter.advance(jetzt + 0.04)
        assert meter.peaks[0] == pytest.approx(oben)

    def test_spitze_liegt_nie_unter_dem_balken(self) -> None:
        meter = LevelMeter(8)
        jetzt = 0.0
        werte = [0.9, 0.1, 0.7, 0.2, 1.0, 0.0, 0.5, 0.3]
        for schritt in range(40):
            jetzt += 1 / 30
            gedreht = werte[schritt % len(werte) :] + werte[: schritt % len(werte)]
            meter.update(gedreht, jetzt)
            for balken, spitze in zip(meter.levels, meter.peaks, strict=True):
                assert spitze >= balken - 1e-9

    def test_verfolger_faellt_erst_nach_der_haltezeit(self) -> None:
        verfolger = PeakTracker(decay_db_per_s=60.0, hold_s=0.2)
        verfolger.bump(1.0, 0.0)
        verfolger.advance(0.1, 0.1)
        assert verfolger.value == pytest.approx(1.0)
        verfolger.advance(0.3, 0.1)
        assert verfolger.value < 1.0


class TestAusklingen:
    """Beim Anhalten faellt die Anzeige ab, statt zu erstarren."""

    def test_nicht_sofort_leer(self) -> None:
        meter = LevelMeter(4)
        jetzt = _voll(meter)
        meter.advance(jetzt + 0.05)
        assert not meter.is_idle
        assert meter.levels[0] > 0.0

    def test_am_ende_leer(self) -> None:
        meter = LevelMeter(4)
        jetzt = _voll(meter)
        # Mit Reserve ueber die berechnete Ausklingdauer hinaus.
        meter.advance(jetzt + meter.ring_out_seconds + 0.1)
        assert meter.is_idle
        assert meter.levels == [0.0] * 4

    def test_ausklingdauer_passt_zur_rate(self) -> None:
        # 60 dB Weg bei 60 dB/s ist eine Sekunde, plus die Haltezeit.
        config = MeterConfig(bar_decay_db_per_s=60.0, peak_decay_db_per_s=60.0, peak_hold_s=0.25)
        meter = LevelMeter(1, config)
        assert meter.ring_out_seconds == pytest.approx(1.25)

    def test_langsamere_rate_klingt_laenger_aus(self) -> None:
        schnell = LevelMeter(1, MeterConfig(bar_decay_db_per_s=120.0, peak_decay_db_per_s=120.0))
        langsam = LevelMeter(1, MeterConfig(bar_decay_db_per_s=30.0, peak_decay_db_per_s=30.0))
        assert langsam.ring_out_seconds > schnell.ring_out_seconds

    def test_reset_raeumt_sofort(self) -> None:
        meter = LevelMeter(4)
        _voll(meter)
        meter.reset()
        assert meter.is_idle


class TestRobust:
    def test_erster_aufruf_bewegt_nichts(self) -> None:
        # Ohne Bezugspunkt gibt es keine verstrichene Zeit, also auch keinen
        # Sprung - sonst haenge das erste Bild von der Systemuhr ab.
        meter = LevelMeter(2)
        meter.update([1.0, 1.0], 12345.0)
        assert meter.levels == [0.0, 0.0]

    def test_rueckwaerts_laufende_uhr_bewegt_nichts(self) -> None:
        meter = LevelMeter(1)
        jetzt = _voll(meter)
        vorher = meter.levels[0]
        meter.advance(jetzt - 5.0)
        assert meter.levels[0] == pytest.approx(vorher)

    def test_lange_pause_faellt_auf_null(self) -> None:
        # War die Anwendung im Hintergrund, gehoert die Anzeige auf den Boden
        # und nicht auf den Stand von vorhin.
        meter = LevelMeter(2)
        jetzt = _voll(meter)
        meter.advance(jetzt + 3600.0)
        assert meter.is_idle

    def test_zu_kurze_eingabe_wird_aufgefuellt(self) -> None:
        meter = LevelMeter(4)
        meter.update([1.0], 0.0)
        meter.update([1.0], 1.0)
        assert meter.levels[0] > 0.0
        assert meter.levels[3] == 0.0

    def test_leere_eingabe_stuerzt_nicht_ab(self) -> None:
        meter = LevelMeter(4)
        _voll(meter)
        meter.update([], 2.0)
        assert len(meter.levels) == 4

    def test_werte_ausserhalb_werden_begrenzt(self) -> None:
        meter = LevelMeter(1)
        jetzt = 0.0
        for _ in range(60):
            jetzt += 0.05
            meter.update([9.0], jetzt)
        assert meter.levels[0] <= 1.0
        meter.update([-4.0], jetzt + 5.0)
        assert meter.levels[0] >= 0.0

    def test_null_baender_werden_abgelehnt(self) -> None:
        with pytest.raises(ValueError, match="Mindestens ein Band"):
            LevelMeter(0)


class TestAbgleich:
    """Konstanten, die zu einem anderen Modul passen muessen."""

    def test_db_floor_passt_zur_spektralanalyse(self) -> None:
        from retro_amp.infrastructure import spectrum

        assert DB_FLOOR == spectrum.DB_FLOOR, (
            "meter.DB_FLOOR und spectrum.DB_FLOOR sind auseinandergelaufen - "
            "dann stimmt die Umrechnung von Dezibel auf Anzeigeanteile nicht mehr"
        )

    def test_analysefenster_passt_zur_fft(self) -> None:
        from retro_amp.infrastructure import spectrum

        fenster = DEFAULT_WINDOW_S
        assert fenster == pytest.approx(spectrum.FFT_SIZE / 44100.0)


class TestOhneOberflaeche:
    def test_meter_laedt_ohne_ui_im_speicher(self) -> None:
        skript = (
            "import sys\n"
            "import retro_amp.meter as m\n"
            "verboten = ('textual', 'rich', 'pygame', 'PySide6')\n"
            "print(','.join(sorted(n for n in sys.modules if n.split('.')[0] in verboten)))\n"
        )
        ergebnis = subprocess.run(
            [sys.executable, "-c", skript],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=120,
            check=False,
        )
        assert ergebnis.returncode == 0, ergebnis.stderr
        assert not ergebnis.stdout.strip(), f"Oberflaeche mitgeladen: {ergebnis.stdout.strip()}"
