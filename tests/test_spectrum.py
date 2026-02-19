"""Tests fuer Spectrum-Analyzer (FFT und Band-Berechnung)."""
from __future__ import annotations

import math

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
        signal = [
            complex(math.sin(2 * math.pi * freq_bin * i / n), 0.0)
            for i in range(n)
        ]
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
