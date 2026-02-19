"""Audio-Playback via pygame.mixer.

OGG/Opus-Dateien werden per pyogg dekodiert und als WAV-Stream geladen,
da pygame's SDL_mixer nur Vorbis (nicht Opus) unterstuetzt.

SID-Dateien (C64) werden per sidplayfp Subprocess zu WAV dekodiert,
falls sidplayfp installiert ist.
"""
from __future__ import annotations

import ctypes
import io
import logging
import shutil
import struct
import subprocess
from pathlib import Path

import pygame
import pygame.mixer

logger = logging.getLogger(__name__)

# Unterstuetzte Formate fuer pygame.mixer
_PYGAME_FORMATS = {".mp3", ".ogg", ".oga", ".opus", ".flac", ".wav", ".mod", ".xm", ".s3m"}

# OGG-Endungen die Opus enthalten koennten
_OGG_EXTENSIONS = {".ogg", ".oga", ".opus"}


def _is_opus(path: Path) -> bool:
    """Prueft ob eine OGG-Datei Opus-kodiert ist (Header-Check)."""
    try:
        with open(path, "rb") as f:
            header = f.read(40)
            # OGG/Opus hat 'OpusHead' im ersten OGG-Segment
            return b"OpusHead" in header
    except Exception:
        return False


def _decode_opus_to_wav(path: Path) -> io.BytesIO:
    """Dekodiert eine OGG/Opus-Datei zu einem WAV-Stream im Speicher."""
    import pyogg

    opus = pyogg.OpusFile(str(path))
    pcm = ctypes.cast(
        opus.buffer,
        ctypes.POINTER(ctypes.c_char * opus.buffer_length),
    ).contents.raw

    channels: int = opus.channels
    sample_rate: int = opus.frequency
    bits = 16
    data_size = len(pcm)

    wav = io.BytesIO()
    wav.write(b"RIFF")
    wav.write(struct.pack("<I", 36 + data_size))
    wav.write(b"WAVE")
    wav.write(b"fmt ")
    wav.write(struct.pack(
        "<IHHIIHH", 16, 1, channels, sample_rate,
        sample_rate * channels * bits // 8,
        channels * bits // 8, bits,
    ))
    wav.write(b"data")
    wav.write(struct.pack("<I", data_size))
    wav.write(pcm)
    wav.seek(0)
    return wav


def _find_sidplayfp() -> str | None:
    """Sucht nach sidplayfp im PATH."""
    return shutil.which("sidplayfp") or shutil.which("sidplay2")


def _decode_sid_to_wav(path: Path, duration: int = 180) -> io.BytesIO | None:
    """Dekodiert eine SID-Datei zu einem WAV-Stream per sidplayfp.

    Args:
        path: Pfad zur SID-Datei
        duration: Maximale Spieldauer in Sekunden (Default: 3 Minuten)

    Returns:
        WAV-Stream oder None wenn sidplayfp nicht verfuegbar
    """
    sid_bin = _find_sidplayfp()
    if not sid_bin:
        logger.warning("sidplayfp nicht gefunden — SID-Playback nicht verfuegbar")
        return None

    try:
        result = subprocess.run(
            [
                sid_bin,
                "--wav=-",       # WAV nach stdout
                f"-t{duration}",  # Maximale Dauer
                "-f44100",        # Sample Rate
                str(path),
            ],
            capture_output=True,
            timeout=duration + 10,
        )
        if result.returncode != 0 or len(result.stdout) < 44:
            logger.warning("sidplayfp Fehler fuer %s: %s", path, result.stderr[:200])
            return None
        wav = io.BytesIO(result.stdout)
        return wav
    except FileNotFoundError:
        logger.warning("sidplayfp nicht gefunden")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("sidplayfp Timeout fuer %s", path)
        return None
    except Exception:
        logger.exception("SID-Dekodierung fehlgeschlagen fuer %s", path)
        return None


class PygameAudioPlayer:
    """AudioPlayer-Implementation mit pygame.mixer.

    Implementiert das AudioPlayer-Protocol aus domain/protocols.py.
    OGG/Opus-Dateien werden automatisch per pyogg dekodiert.
    SID-Dateien werden per sidplayfp Subprocess dekodiert (falls installiert).
    """

    def __init__(self, frequency: int = 44100, buffer_size: int = 8192) -> None:
        self._initialized = False
        self._frequency = frequency
        self._buffer_size = buffer_size
        self._current_path: Path | None = None
        self._seek_offset: float = 0.0
        self._opus_wav: io.BytesIO | None = None
        self._sid_wav: io.BytesIO | None = None
        self._init_mixer()

    def _init_mixer(self) -> None:
        """Initialisiert pygame.mixer."""
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(
                    frequency=self._frequency,
                    size=-16,
                    channels=2,
                    buffer=self._buffer_size,
                )
            self._initialized = True
        except Exception:
            logger.exception("pygame.mixer konnte nicht initialisiert werden")
            self._initialized = False

    def play(self, path: Path) -> None:
        """Spielt eine Audio-Datei ab."""
        if not self._initialized:
            self._init_mixer()
        if not self._initialized:
            return

        try:
            self._opus_wav = None
            self._sid_wav = None
            ext = path.suffix.lower()

            if ext == ".sid":
                self._sid_wav = _decode_sid_to_wav(path)
                if self._sid_wav is None:
                    logger.warning("SID-Playback nicht moeglich: %s", path)
                    return
                pygame.mixer.music.load(self._sid_wav)
            elif ext in _OGG_EXTENSIONS and _is_opus(path):
                self._opus_wav = _decode_opus_to_wav(path)
                pygame.mixer.music.load(self._opus_wav)
            else:
                pygame.mixer.music.load(str(path))
            pygame.mixer.music.play()
            self._current_path = path
            self._seek_offset = 0.0
        except Exception:
            logger.exception("Fehler beim Abspielen von %s", path)

    def pause(self) -> None:
        """Pausiert die Wiedergabe."""
        if self._initialized:
            pygame.mixer.music.pause()

    def unpause(self) -> None:
        """Setzt die Wiedergabe fort."""
        if self._initialized:
            pygame.mixer.music.unpause()

    def stop(self) -> None:
        """Stoppt die Wiedergabe."""
        if self._initialized:
            pygame.mixer.music.stop()
            self._current_path = None

    def set_volume(self, volume: float) -> None:
        """Setzt die Lautstaerke (0.0 bis 1.0)."""
        if self._initialized:
            pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))

    def get_position(self) -> float:
        """Gibt die aktuelle Position in Sekunden zurueck."""
        if not self._initialized:
            return 0.0
        pos_ms = pygame.mixer.music.get_pos()
        if pos_ms < 0:
            return 0.0
        return self._seek_offset + pos_ms / 1000.0

    def seek(self, position_seconds: float) -> None:
        """Springt zu einer bestimmten Position in Sekunden."""
        if not self._initialized:
            return
        try:
            pos = max(0.0, position_seconds)
            pygame.mixer.music.set_pos(pos)
            self._seek_offset = pos
        except Exception:
            logger.debug("Seek nicht unterstuetzt fuer dieses Format")

    def is_busy(self) -> bool:
        """Prueft ob gerade abgespielt wird."""
        if not self._initialized:
            return False
        return pygame.mixer.music.get_busy()

    def cleanup(self) -> None:
        """Raumt pygame.mixer auf."""
        if self._initialized:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            except Exception:
                pass
            self._initialized = False
