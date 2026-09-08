"""Pegelverhalten fuer Visualizer und VU-Anzeigen.

Ein Pegelmesser sieht nicht deshalb professionell aus, weil er die richtige
Farbe hat, sondern weil er sich richtig bewegt: der Balken faellt mit einer
festen Geschwindigkeit in Dezibel pro Sekunde, eine Spitze bleibt eine
Mindestzeit stehen, und nach dem Anhalten klingt die Anzeige aus, statt
einzufrieren.

Genau das leistet dieses Modul. Es ist bewusst frei von Zeitgebern: die
Uhrzeit kommt bei jedem Aufruf von aussen herein (`now`, in Sekunden). Damit
laesst sich das Verhalten ohne laufende Oberflaeche pruefen - eine Sekunde
Ausklingen dauert im Test kein bisschen.

WICHTIG: oberflaechenfrei. Weder `textual` noch `pygame` noch Qt. Ein Test
haelt das fest (`tests/test_meter.py`).

Warum in Dezibel und nicht in Anzeigestufen
-------------------------------------------
Ein Abfall "zwei Stufen je Bild" haengt an der Bildrate: dieselbe Anzeige
faellt bei 12 Bildern je Sekunde fuenfmal langsamer als bei 60. Ein Abfall in
Dezibel je Sekunde ist von der Bildrate unabhaengig - und nur so bleibt das
Bild gleich, wenn der Takt sich aendert.

Die Bandwerte aus `infrastructure.spectrum` sind bereits eine Dezibelskala:
`get_bands()` bildet DB_FLOOR..0 dB auf 0.0..1.0 ab. Ein Wert von 1.0
entspricht damit genau `-DB_FLOOR` Dezibel, und die Umrechnung ist eine
Division.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

# Muss mit `infrastructure.spectrum.DB_FLOOR` uebereinstimmen. Bewusst
# dupliziert, damit dieses Modul oberflaechen- und pygame-frei bleibt - der
# Abgleich passiert im Test.
DB_FLOOR = -60.0

# Dauer eines Analysefensters (FFT_SIZE / Abtastrate). Eine Spitze haelt
# mindestens so lange, sonst zeigt die Anzeige einen Wert kuerzer an, als er
# ueberhaupt gemessen wurde. Entspricht Audacitys "hangover".
DEFAULT_WINDOW_S = 2048 / 44100.0


def _db_to_scale(db_per_second: float) -> float:
    """Rechnet Dezibel je Sekunde in Anzeigeanteile je Sekunde um."""
    return db_per_second / abs(DB_FLOOR)


@dataclass(frozen=True, slots=True)
class MeterConfig:
    """Zeitverhalten der Anzeige.

    Die Vorgabewerte entsprechen genau dem frueheren bildbasierten Verhalten
    bei 12 Bildern je Sekunde, damit der Umbau die Optik nicht veraendert:
    plus drei Stufen von 24 je Bild sind 90 dB/s, minus zwei Stufen sind
    60 dB/s, drei Bilder Haltezeit sind 0,25 Sekunden.
    """

    attack_db_per_s: float = 90.0
    bar_decay_db_per_s: float = 60.0
    # Deutlich langsamer als der Balken, wie bei einer echten Spitzenanzeige
    # (ueblich sind 12 bis 20 dB/s). Damit steht die Marke sichtbar ueber dem
    # Balken, statt mit ihm zu fallen und nur waehrend der Haltezeit
    # aufzutauchen. Der Bestandswert waren 60 dB/s, also Gleichlauf.
    #
    # Folge fuers Ausklingen: `ring_out_seconds` richtet sich nach der
    # langsameren der beiden Raten, der Takt laeuft nach dem Anhalten also
    # laenger weiter (rund vier statt gut einer Sekunde). Sichtbar ist in
    # dieser Zeit nur noch die fallende Marke.
    peak_decay_db_per_s: float = 16.0
    peak_hold_s: float = 0.25
    window_s: float = DEFAULT_WINDOW_S

    @property
    def effective_hold_s(self) -> float:
        """Tatsaechliche Haltezeit einer Spitze."""
        return max(self.peak_hold_s, self.window_s)


class PeakTracker:
    """Haelt eine Spitze und laesst sie danach mit fester Rate fallen."""

    __slots__ = ("_decay", "_hold_s", "_hold_until", "_value")

    def __init__(self, decay_db_per_s: float, hold_s: float) -> None:
        self._decay = _db_to_scale(decay_db_per_s)
        self._hold_s = hold_s
        self._value = 0.0
        self._hold_until = 0.0

    @property
    def value(self) -> float:
        """Aktuelle Spitze als Anzeigeanteil 0.0 bis 1.0."""
        return self._value

    def reset(self) -> None:
        self._value = 0.0
        self._hold_until = 0.0

    def advance(self, now: float, elapsed: float) -> None:
        """Laesst die Spitze fallen, sofern die Haltezeit abgelaufen ist."""
        if now < self._hold_until:
            return
        self._value = max(0.0, self._value - self._decay * elapsed)

    def bump(self, level: float, now: float) -> None:
        """Hebt die Spitze an, wenn der Pegel sie erreicht, und haelt sie."""
        if level >= self._value:
            self._value = level
            self._hold_until = now + self._hold_s


class LevelMeter:
    """Zeitverhalten fuer eine Reihe von Frequenzbaendern.

    Ablauf je Bild: `update(werte, jetzt)` solange Ton laeuft, danach
    `advance(jetzt)` bis `is_idle` wahr wird. Erst dann darf der Aufrufer
    seinen Zeitgeber anhalten - so klingt die Anzeige aus, statt zu
    erstarren.
    """

    __slots__ = ("_bars", "_config", "_last", "_peaks")

    def __init__(self, bands: int, config: MeterConfig | None = None) -> None:
        if bands <= 0:
            raise ValueError(f"Mindestens ein Band noetig, nicht {bands}")
        self._config = config or MeterConfig()
        self._bars = [0.0] * bands
        self._peaks = [
            PeakTracker(self._config.peak_decay_db_per_s, self._config.effective_hold_s) for _ in range(bands)
        ]
        self._last: float | None = None

    # ── Abfrage ──────────────────────────────────────────────────────

    @property
    def config(self) -> MeterConfig:
        return self._config

    @property
    def bands(self) -> int:
        return len(self._bars)

    @property
    def levels(self) -> list[float]:
        """Balkenhoehen als Anzeigeanteile 0.0 bis 1.0."""
        return list(self._bars)

    @property
    def peaks(self) -> list[float]:
        """Spitzenmarken als Anzeigeanteile 0.0 bis 1.0."""
        return [p.value for p in self._peaks]

    @property
    def is_idle(self) -> bool:
        """Wahr, sobald alles auf dem Boden liegt - dann darf der Takt enden."""
        return not any(self._bars) and not any(p.value for p in self._peaks)

    @property
    def ring_out_seconds(self) -> float:
        """Wie lange das Ausklingen aus dem Vollausschlag hoechstens dauert.

        Dieselbe Rechnung wie bei Audacity: der Weg von oben bis zum Boden,
        geteilt durch die langsamere der beiden Abfallraten, plus die
        Haltezeit der Spitze.
        """
        langsamste = min(self._config.bar_decay_db_per_s, self._config.peak_decay_db_per_s)
        return abs(DB_FLOOR) / langsamste + self._config.effective_hold_s

    # ── Fortschreiben ────────────────────────────────────────────────

    def reset(self) -> None:
        """Setzt alles sofort auf Null - fuer einen Titelwechsel."""
        self._bars = [0.0] * len(self._bars)
        for peak in self._peaks:
            peak.reset()
        self._last = None

    def advance(self, now: float) -> None:
        """Einen Schritt ohne neue Werte - die Anzeige klingt aus."""
        elapsed = self._elapsed(now)
        if elapsed <= 0.0:
            return
        fall = _db_to_scale(self._config.bar_decay_db_per_s) * elapsed
        self._bars = [max(0.0, wert - fall) for wert in self._bars]
        for peak in self._peaks:
            peak.advance(now, elapsed)

    def update(self, values: Sequence[float], now: float) -> None:
        """Einen Schritt mit neuen Bandwerten.

        Kuerzere Eingaben werden mit Null aufgefuellt, laengere abgeschnitten -
        eine Datenquelle, die gerade nichts liefert, darf die Anzeige nicht
        zum Absturz bringen.
        """
        elapsed = self._elapsed(now)
        anstieg = _db_to_scale(self._config.attack_db_per_s) * elapsed
        fall = _db_to_scale(self._config.bar_decay_db_per_s) * elapsed

        for i in range(len(self._bars)):
            ziel = values[i] if i < len(values) else 0.0
            ziel = max(0.0, min(1.0, ziel))
            aktuell = self._bars[i]
            # Schnell hoch, langsamer runter - das macht den Ausschlag lesbar.
            aktuell = min(ziel, aktuell + anstieg) if ziel > aktuell else max(ziel, aktuell - fall)
            self._bars[i] = aktuell

            peak = self._peaks[i]
            peak.advance(now, elapsed)
            peak.bump(aktuell, now)

    # ── Intern ───────────────────────────────────────────────────────

    def _elapsed(self, now: float) -> float:
        """Zeit seit dem letzten Schritt, in Sekunden.

        Der erste Aufruf liefert 0.0 und setzt nur den Bezugspunkt. Eine
        rueckwaerts laufende Uhr ergibt ebenfalls 0.0 statt eines Sprungs.
        Eine lange Pause wird NICHT gedeckelt: war die Anwendung eine Weile
        im Hintergrund, gehoert die Anzeige auf den Boden und nicht auf den
        Stand von vorhin.
        """
        if self._last is None:
            self._last = now
            return 0.0
        elapsed = now - self._last
        self._last = now
        return max(0.0, elapsed)
