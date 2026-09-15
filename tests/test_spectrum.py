"""Tests fuer Spectrum-Analyzer (FFT und Band-Berechnung)."""

from __future__ import annotations

import array
import math
import wave
from pathlib import Path

from retro_amp.infrastructure.spectrum import (
    FFT_SIZE,
    NUM_BANDS,
    SpectrumAnalyzer,
    _fft,
)


class TestFFT:
    def test_fft_dc_signal(self) -> None:
        """Konstantes Signal hat nur DC-Komponente (Bin 0)."""
        n = 64
        signal = [complex(1.0, 0.0)] * n
        result = _fft(signal)
        # DC-Bin sollte n sein
        assert abs(result[0] - complex(n, 0)) < 1e-6
        # Alle anderen Bins sollten ~0 sein
        for k in range(1, n):
            assert abs(result[k]) < 1e-6

    def test_fft_pure_sine(self) -> None:
        """Reiner Sinus hat einen Peak bei der richtigen Frequenz."""
        n = 256
        freq_bin = 10
        signal = [complex(math.sin(2 * math.pi * freq_bin * i / n), 0.0) for i in range(n)]
        result = _fft(signal)
        magnitudes = [abs(result[k]) for k in range(n // 2)]
        peak_bin = magnitudes.index(max(magnitudes))
        assert peak_bin == freq_bin

    def test_fft_power_of_two(self) -> None:
        """FFT funktioniert mit verschiedenen Zweierpotenzen."""
        for size in [8, 16, 32, 64, 128]:
            signal = [complex(0.0)] * size
            signal[0] = complex(1.0)  # Impuls
            result = _fft(signal)
            assert len(result) == size
            # Impuls -> alle Bins gleich (flat spectrum)
            for val in result:
                assert abs(abs(val) - 1.0) < 1e-6


class TestSpectrumAnalyzer:
    def test_initial_state(self) -> None:
        analyzer = SpectrumAnalyzer()
        assert not analyzer.is_ready
        assert analyzer.get_bands(0.0) == []

    def test_unload(self) -> None:
        analyzer = SpectrumAnalyzer()
        analyzer.unload()
        assert not analyzer.is_ready

    def test_band_bins_computed(self) -> None:
        """Band-Grenzen muessen berechnet sein (32 Baender)."""
        analyzer = SpectrumAnalyzer()
        assert len(analyzer._band_bins) == NUM_BANDS
        # Alle Grenzen muessen aufsteigend sein
        for lo, hi in analyzer._band_bins:
            assert lo >= 1
            assert hi >= lo
            assert hi < FFT_SIZE // 2

    def test_get_bands_not_ready(self) -> None:
        """Ohne geladene Daten gibt get_bands leere Liste zurueck."""
        analyzer = SpectrumAnalyzer()
        assert analyzer.get_bands(5.0) == []


class TestDekodierenMitSonderzeichen:
    """Der Analysator darf nicht am Dateinamen scheitern.

    `miniaudio.decode_file()` reicht den Pfad an die C-Bibliothek durch und
    gibt unter Windows `DecodeError(-7)` zurueck, sobald darin ein Zeichen
    ausserhalb von ASCII steht. Aufgefallen an einem Album mit Akzent im
    Ordnernamen: der Visualizer zeigte Zufallswerte statt des Spektrums, und
    zu sehen war davon nichts - der Fehler landete nur im Debug-Log.
    """

    @staticmethod
    def _schreibe_wav(ziel: Path, sekunden: float = 0.5, rate: int = 44100) -> Path:
        """Legt eine kurze Stereo-Datei an - links Sinus, rechts Stille."""
        rahmen = int(rate * sekunden)
        daten = array.array("h")
        for i in range(rahmen):
            daten.append(int(12000 * math.sin(2.0 * math.pi * 440.0 * i / rate)))
            daten.append(0)
        with wave.open(str(ziel), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(daten.tobytes())
        return ziel

    def test_pfad_mit_akzent_wird_dekodiert(self, tmp_path: Path) -> None:
        """Derselbe Inhalt muss mit und ohne Akzent im Pfad ankommen."""
        ordner = tmp_path / "Oggi Le Canto Così"
        ordner.mkdir()
        mit_akzent = self._schreibe_wav(ordner / "17-Eternità.wav")
        ohne_akzent = self._schreibe_wav(tmp_path / "17-Eternita.wav")

        analysator = SpectrumAnalyzer()
        roh_a, rate_a, kanaele_a = analysator._decode_via_miniaudio(mit_akzent)
        roh_b, rate_b, kanaele_b = analysator._decode_via_miniaudio(ohne_akzent)

        assert roh_a is not None, "Akzent im Pfad darf die Dekodierung nicht verhindern"
        assert (rate_a, kanaele_a) == (rate_b, kanaele_b)
        assert roh_a == roh_b, "gleicher Inhalt muss gleiche Samples liefern"

    def test_downmix_liefert_mono(self, tmp_path: Path) -> None:
        """miniaudio mischt selbst auf einen Kanal - die Python-Schleife entfaellt."""
        datei = self._schreibe_wav(tmp_path / "stereo.wav", sekunden=0.2)
        roh, _rate, kanaele = SpectrumAnalyzer()._decode_via_miniaudio(datei)

        assert kanaele == 1, "der Downmix soll in C passieren, nicht in Python"
        assert roh is not None
        # Links Sinus, rechts Stille: der Mittelwert liegt bei der halben Amplitude.
        werte = array.array("h")
        werte.frombytes(roh)
        assert 4000 < max(werte) < 7000, f"unerwartete Amplitude: {max(werte)}"

    def test_load_meldet_erfolg_und_misserfolg(self, tmp_path: Path) -> None:
        """load() sagt dem Aufrufer, ob danach Bandwerte kommen."""
        gut = self._schreibe_wav(tmp_path / "Grüße.wav", sekunden=0.2)
        kaputt = tmp_path / "kaputt.flac"
        kaputt.write_bytes(b"das ist kein Audio")

        analysator = SpectrumAnalyzer()
        assert analysator.load(gut) is True
        assert analysator.is_ready is True
        assert analysator.load(kaputt) is False
        assert analysator.is_ready is False
