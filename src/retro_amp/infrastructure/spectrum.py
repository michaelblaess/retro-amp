"""Spectrum-Analyzer — FFT-basierte Frequenzanalyse fuer Visualizer."""
from __future__ import annotations

import array
import cmath
import logging
import math
from pathlib import Path

import pygame
import pygame.mixer

logger = logging.getLogger(__name__)

# Konstanten
FFT_SIZE = 2048
NUM_BANDS = 32
MIN_FREQ = 20.0
MAX_FREQ = 18000.0
DB_FLOOR = -60.0  # Untergrenze in dB


def _fft(x: list[complex]) -> list[complex]:
    """Iterative Cooley-Tukey Radix-2 FFT (stdlib only)."""
    n = len(x)
    if n <= 1:
        return x

    bits = int(math.log2(n))
    result = [complex(0)] * n

    # Bit-reversal Permutation
    for i in range(n):
        j = 0
        for b in range(bits):
            if i & (1 << b):
                j |= 1 << (bits - 1 - b)
        result[j] = x[i]

    # Butterfly-Operationen
    size = 2
    while size <= n:
        half = size // 2
        w_base = -2.0 * math.pi / size
        for start in range(0, n, size):
            wk = complex(1.0, 0.0)
            w_step = cmath.exp(complex(0, w_base))
            for k in range(half):
                t = wk * result[start + k + half]
                result[start + k + half] = result[start + k] - t
                result[start + k] = result[start + k] + t
                wk *= w_step
        size *= 2

    return result


class SpectrumAnalyzer:
    """Analysiert Audio-PCM-Daten und liefert Frequenzband-Werte.

    Laedt Audio via pygame.mixer.Sound (separater Pfad von der Wiedergabe),
    extrahiert PCM-Rohdaten und berechnet per FFT die Frequenzverteilung.
    """

    def __init__(self) -> None:
        self._pcm: array.array[int] | None = None
        self._sample_rate: int = 44100
        self._channels: int = 2
        self._ready = False

        # Hann-Fenster vorberechnen
        self._hann = [
            0.5 * (1.0 - math.cos(2.0 * math.pi * i / (FFT_SIZE - 1)))
            for i in range(FFT_SIZE)
        ]

        # Log-skalierte Band-Grenzen (Bin-Indices)
        self._band_bins: list[tuple[int, int]] = []
        self._compute_band_bins(self._sample_rate)

    def _compute_band_bins(self, sample_rate: int) -> None:
        """Berechnet die FFT-Bin-Grenzen fuer log-skalierte Baender."""
        nyquist = sample_rate / 2.0
        max_freq = min(MAX_FREQ, nyquist)
        half_fft = FFT_SIZE // 2

        self._band_bins = []
        for i in range(NUM_BANDS):
            lo = MIN_FREQ * (max_freq / MIN_FREQ) ** (i / NUM_BANDS)
            hi = MIN_FREQ * (max_freq / MIN_FREQ) ** ((i + 1) / NUM_BANDS)
            lo_bin = max(1, int(lo * FFT_SIZE / sample_rate))
            hi_bin = min(half_fft - 1, int(hi * FFT_SIZE / sample_rate))
            if hi_bin < lo_bin:
                hi_bin = lo_bin
            self._band_bins.append((lo_bin, hi_bin))

    def load(self, path: Path) -> None:
        """Laedt PCM-Daten einer Audio-Datei (blocking, in Worker aufrufen).

        Nutzt pygame.mixer.Sound zum Dekodieren, extrahiert Raw-PCM
        und gibt den Sound sofort wieder frei.
        """
        self._ready = False
        self._pcm = None

        try:
            if not pygame.mixer.get_init():
                logger.warning("pygame.mixer nicht initialisiert")
                return

            init_info = pygame.mixer.get_init()
            if init_info:
                self._sample_rate = init_info[0]
                self._channels = init_info[2]
            self._compute_band_bins(self._sample_rate)

            sound = pygame.mixer.Sound(str(path))
            raw = sound.get_raw()
            del sound  # Speicher freigeben

            # Raw-Bytes in signed 16-bit Array
            pcm = array.array("h")
            pcm.frombytes(raw)

            # Stereo zu Mono mischen
            if self._channels == 2 and len(pcm) >= 2:
                mono = array.array("h")
                for j in range(0, len(pcm) - 1, 2):
                    mono.append((pcm[j] + pcm[j + 1]) // 2)
                self._pcm = mono
            else:
                self._pcm = pcm

            self._ready = True
        except Exception:
            logger.debug("Spectrum-Daten konnten nicht geladen werden", exc_info=True)
            self._pcm = None
            self._ready = False

    def unload(self) -> None:
        """Gibt PCM-Daten frei."""
        self._ready = False
        self._pcm = None

    @property
    def is_ready(self) -> bool:
        return self._ready

    def get_bands(self, position_seconds: float) -> list[float]:
        """Berechnet normalisierte Band-Werte (0.0–1.0) fuer eine Position.

        Returns:
            Liste mit NUM_BANDS float-Werten, oder leere Liste wenn nicht bereit.
        """
        if not self._ready or self._pcm is None:
            return []

        # Sample-Index fuer Position
        sample_idx = int(position_seconds * self._sample_rate)
        total_samples = len(self._pcm)

        if sample_idx < 0 or sample_idx >= total_samples:
            return [0.0] * NUM_BANDS

        # Fenster extrahieren
        start = max(0, sample_idx - FFT_SIZE // 2)
        end = min(total_samples, start + FFT_SIZE)
        if end - start < FFT_SIZE:
            start = max(0, end - FFT_SIZE)

        window = self._pcm[start:end]

        # Padding falls noetig
        if len(window) < FFT_SIZE:
            window.extend([0] * (FFT_SIZE - len(window)))

        # Hann-Fenster anwenden + in Complex umwandeln
        windowed = [
            complex(window[i] * self._hann[i] / 32768.0, 0.0)
            for i in range(FFT_SIZE)
        ]

        # FFT
        spectrum = _fft(windowed)

        # Magnitude berechnen (nur positive Frequenzen)
        half = FFT_SIZE // 2
        magnitudes = [abs(spectrum[k]) / half for k in range(half)]

        # Band-Werte berechnen (Durchschnitt pro Band)
        bands: list[float] = []
        for lo_bin, hi_bin in self._band_bins:
            if hi_bin >= lo_bin:
                count = hi_bin - lo_bin + 1
                avg = sum(magnitudes[lo_bin : hi_bin + 1]) / count
            else:
                avg = 0.0

            # In dB umrechnen und normalisieren
            if avg > 0:
                db = 20.0 * math.log10(avg + 1e-10)
            else:
                db = DB_FLOOR

            # Normalisieren: DB_FLOOR..0 -> 0.0..1.0
            normalized = max(0.0, min(1.0, (db - DB_FLOOR) / (-DB_FLOOR)))
            bands.append(normalized)

        return bands
