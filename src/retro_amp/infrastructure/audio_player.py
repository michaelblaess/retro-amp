"""Audio-Playback via pygame.mixer."""
from __future__ import annotations

import logging
from pathlib import Path

import pygame
import pygame.mixer

logger = logging.getLogger(__name__)

# Unterstuetzte Formate fuer pygame.mixer
_PYGAME_FORMATS = {".mp3", ".ogg", ".oga", ".flac", ".wav", ".mod", ".xm", ".s3m"}


class PygameAudioPlayer:
    """AudioPlayer-Implementation mit pygame.mixer.

    Implementiert das AudioPlayer-Protocol aus domain/protocols.py.
    """

    def __init__(self, frequency: int = 44100, buffer_size: int = 4096) -> None:
        self._initialized = False
        self._frequency = frequency
        self._buffer_size = buffer_size
        self._current_path: Path | None = None
        self._seek_offset: float = 0.0
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
