"""Audio-Playback via pygame.mixer.

OGG/Opus-Dateien werden per pyogg dekodiert und als WAV-Stream geladen,
da pygame's SDL_mixer nur Vorbis (nicht Opus) unterstuetzt.

SID-Dateien (C64) werden per sidplayfp Subprocess zu WAV dekodiert,
falls sidplayfp installiert ist.

M4A/AAC-Dateien werden per ffmpeg Subprocess zu WAV dekodiert,
da pygame's SDL_mixer keinen AAC-Decoder hat.
"""

from __future__ import annotations

import ctypes
import io
import logging
import shutil
import struct
import subprocess
import tempfile
import threading
from pathlib import Path

import pygame
import pygame.mixer

from ..i18n import t
from .cloud_files import is_cloud_placeholder

logger = logging.getLogger(__name__)

# Unterstuetzte Formate fuer pygame.mixer (nativ)
_PYGAME_FORMATS = {".mp3", ".ogg", ".oga", ".opus", ".flac", ".wav", ".mod", ".xm", ".s3m", ".m4a"}

# OGG-Endungen die Opus enthalten koennten
_OGG_EXTENSIONS = {".ogg", ".oga", ".opus"}

# Formate die ffmpeg-Dekodierung benoetigen
_FFMPEG_FORMATS = {".m4a", ".aac", ".wma", ".mpc", ".mp+"}


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
    wav.write(
        struct.pack(
            "<IHHIIHH",
            16,
            1,
            channels,
            sample_rate,
            sample_rate * channels * bits // 8,
            channels * bits // 8,
            bits,
        )
    )
    wav.write(b"data")
    wav.write(struct.pack("<I", data_size))
    wav.write(pcm)
    wav.seek(0)
    return wav


# SID startet zweistufig: erst ein kurzer Anfang (sidplayfp braucht dafuer gut eine
# Sekunde), die volle Laenge dekodiert ein Hintergrund-Thread und wird dann an der
# aktuellen Stelle eingewechselt. Volle 180 s dauern sonst rund 8 s, in denen nichts
# spielt (gemessen mit sidplayfp 3.2.1).
_SID_PREVIEW_SECONDS = 15
_SID_FULL_SECONDS = 180


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

    # sidplayfp kennt keine Ausgabe nach stdout: "--wav=-" legt eine Datei "=-.wav"
    # im Arbeitsordner an (belegt mit sidplayfp 3.2.1). Deshalb in eine temporaere
    # Datei schreiben, "-w<datei>" verstehen Version 2 und 3.
    with tempfile.TemporaryDirectory(prefix="retro-amp-sid-") as ordner:
        ziel = Path(ordner) / "sid.wav"
        return _run_sidplayfp(sid_bin, path, ziel, duration)


def _run_sidplayfp(sid_bin: str, path: Path, ziel: Path, duration: int) -> io.BytesIO | None:
    """Ruft sidplayfp auf und liest die erzeugte WAV-Datei.

    Args:
        sid_bin: Pfad zu sidplayfp
        path: Pfad zur SID-Datei
        ziel: Pfad der WAV-Datei, die sidplayfp schreiben soll
        duration: Maximale Spieldauer in Sekunden

    Returns:
        WAV-Stream oder None bei einem Fehler
    """
    try:
        result = subprocess.run(
            [
                sid_bin,
                f"-w{ziel}",  # WAV-Datei
                f"-t{duration}",  # Maximale Dauer
                "-f44100",  # Sample Rate
                str(path),
            ],
            capture_output=True,
            timeout=duration + 10,
        )
        if result.returncode != 0 or not ziel.is_file() or ziel.stat().st_size < 44:
            logger.warning("sidplayfp Fehler fuer %s: %s", path, result.stderr[:200])
            return None
        return io.BytesIO(ziel.read_bytes())
    except FileNotFoundError:
        logger.warning("sidplayfp nicht gefunden")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("sidplayfp Timeout fuer %s", path)
        return None
    except Exception:
        logger.exception("SID-Dekodierung fehlgeschlagen fuer %s", path)
        return None


def _find_ffmpeg() -> str | None:
    """Sucht nach ffmpeg im PATH."""
    return shutil.which("ffmpeg")


def _decode_with_ffmpeg(path: Path) -> io.BytesIO | None:
    """Dekodiert eine Audio-Datei zu einem WAV-Stream per ffmpeg.

    Args:
        path: Pfad zur Audio-Datei (M4A, AAC, WMA etc.)

    Returns:
        WAV-Stream oder None wenn ffmpeg nicht verfuegbar
    """
    ffmpeg_bin = _find_ffmpeg()
    if not ffmpeg_bin:
        logger.warning(
            "ffmpeg nicht gefunden — M4A/AAC-Playback nicht verfuegbar. "
            "Installation: choco install ffmpeg (Windows), "
            "apt install ffmpeg (Linux), brew install ffmpeg (macOS)"
        )
        return None

    try:
        result = subprocess.run(
            [
                ffmpeg_bin,
                "-i",
                str(path),
                "-f",
                "wav",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "44100",
                "-ac",
                "2",
                "-",  # WAV nach stdout
            ],
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0 or len(result.stdout) < 44:
            stderr = result.stderr.decode("utf-8", errors="replace")[:200]
            logger.warning("ffmpeg Fehler fuer %s: %s", path, stderr)
            return None
        wav = io.BytesIO(result.stdout)
        return wav
    except FileNotFoundError:
        logger.warning("ffmpeg nicht gefunden")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg Timeout fuer %s", path)
        return None
    except Exception:
        logger.exception("ffmpeg-Dekodierung fehlgeschlagen fuer %s", path)
        return None


class PygameAudioPlayer:
    """AudioPlayer-Implementation mit pygame.mixer.

    Implementiert das AudioPlayer-Protocol aus domain/protocols.py.
    OGG/Opus-Dateien werden automatisch per pyogg dekodiert.
    SID-Dateien werden per sidplayfp Subprocess dekodiert (falls installiert).
    """

    # Zustand des zweistufigen SID-Starts. Als Klassenwerte, damit auch ein per
    # __new__ gebauter Player (Tests) sie hat. Es gibt genau einen Player je App,
    # das geteilte Lock ist deshalb unkritisch.
    _sid_generation: int = 0
    _sid_pending: bool = False
    _paused: bool = False
    _sid_lock = threading.Lock()

    def __init__(self, frequency: int = 44100, buffer_size: int = 8192) -> None:
        self._initialized = False
        self._frequency = frequency
        self._buffer_size = buffer_size
        self._current_path: Path | None = None
        self._seek_offset: float = 0.0
        self._opus_wav: io.BytesIO | None = None
        self._sid_wav: io.BytesIO | None = None
        self._ffmpeg_wav: io.BytesIO | None = None
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
            self._cancel_sid_upgrade()
            self._opus_wav = None
            self._sid_wav = None
            self._ffmpeg_wav = None
            self._paused = False
            ext = path.suffix.lower()

            if ext == ".sid":
                self._play_sid(path)
                return
            if ext in _OGG_EXTENSIONS and _is_opus(path):
                self._opus_wav = _decode_opus_to_wav(path)
                pygame.mixer.music.load(self._opus_wav)
            elif ext in _FFMPEG_FORMATS:
                self._ffmpeg_wav = _decode_with_ffmpeg(path)
                if self._ffmpeg_wav is None:
                    raise RuntimeError(
                        "ffmpeg nicht gefunden — M4A/AAC-Playback nicht verfuegbar. "
                        "Installation: choco install ffmpeg (Windows), "
                        "apt install ffmpeg (Linux), brew install ffmpeg (macOS)"
                    )
                pygame.mixer.music.load(self._ffmpeg_wav)
            else:
                pygame.mixer.music.load(str(path))
            pygame.mixer.music.play()
            self._current_path = path
            self._seek_offset = 0.0
        except RuntimeError as error:
            # pygame.error ist ein RuntimeError. Bei einem Cloud-Platzhalter ist die
            # Meldung "corrupt mp3" falsch - die Datei ist heil, nur nicht lokal da.
            if is_cloud_placeholder(path):
                raise RuntimeError(t("error.cloud_only", name=path.name)) from error
            raise
        except Exception:
            logger.exception("Fehler beim Abspielen von %s", path)

    def _play_sid(self, path: Path) -> None:
        """Startet eine SID-Datei mit kurzem Anfang und wechselt spaeter auf die volle Laenge.

        Args:
            path: Pfad zur SID-Datei

        Raises:
            RuntimeError: wenn sidplayfp fehlt oder nichts liefert
        """
        with self._sid_lock:
            self._sid_generation += 1
            generation = self._sid_generation
            self._sid_pending = True
        threading.Thread(
            target=self._upgrade_sid,
            args=(path, generation),
            name="retro-amp-sid-full",
            daemon=True,
        ).start()

        # Der Hintergrund-Thread wechselt erst, wenn der Anfang laeuft - das Lock
        # haelt ihn bis dahin auf, auch wenn er schneller fertig ist
        with self._sid_lock:
            preview = _decode_sid_to_wav(path, duration=_SID_PREVIEW_SECONDS)
            if preview is None:
                self._sid_generation += 1
                self._sid_pending = False
                raise RuntimeError("sidplayfp nicht gefunden - SID-Playback nicht verfuegbar")
            self._sid_wav = preview
            pygame.mixer.music.load(preview)
            pygame.mixer.music.play()
            self._current_path = path
            self._seek_offset = 0.0

    def _upgrade_sid(self, path: Path, generation: int) -> None:
        """Dekodiert die volle Laenge im Hintergrund und wechselt an der aktuellen Stelle.

        Args:
            path: Pfad zur SID-Datei
            generation: Zaehlerstand beim Start - ist er inzwischen weiter, wurde
                ein anderer Titel gestartet oder gestoppt und der Wechsel entfaellt
        """
        full = _decode_sid_to_wav(path, duration=_SID_FULL_SECONDS)
        with self._sid_lock:
            if generation != self._sid_generation:
                return
            self._sid_pending = False
            if full is None:
                logger.warning("Volle SID-Dekodierung fehlgeschlagen, es bleibt beim Anfang: %s", path)
                return
            try:
                # Ist der Anfang schon ausgelaufen, liefert pygame keine Position mehr
                ended = not pygame.mixer.music.get_busy() and not self._paused
                position = float(_SID_PREVIEW_SECONDS) if ended else self.get_position()
                self._sid_wav = full
                pygame.mixer.music.load(full)
                pygame.mixer.music.play(start=position)
                self._seek_offset = position
                if self._paused:
                    pygame.mixer.music.pause()
            except Exception:
                logger.exception("Wechsel auf die volle SID-Fassung fehlgeschlagen: %s", path)

    def _cancel_sid_upgrade(self) -> None:
        """Verwirft einen noch laufenden Wechsel auf die volle SID-Fassung."""
        with self._sid_lock:
            self._sid_generation += 1
            self._sid_pending = False

    def pause(self) -> None:
        """Pausiert die Wiedergabe."""
        if self._initialized:
            self._paused = True
            pygame.mixer.music.pause()

    def unpause(self) -> None:
        """Setzt die Wiedergabe fort."""
        if self._initialized:
            self._paused = False
            pygame.mixer.music.unpause()

    def stop(self) -> None:
        """Stoppt die Wiedergabe."""
        if self._initialized:
            self._cancel_sid_upgrade()
            pygame.mixer.music.stop()
            self._current_path = None

    def unload(self) -> None:
        """Entlaedt die aktuelle Datei und gibt den File-Handle frei."""
        if self._initialized:
            self._cancel_sid_upgrade()
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            self._current_path = None
            self._opus_wav = None
            self._sid_wav = None
            self._ffmpeg_wav = None

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
        # Waehrend die volle SID-Fassung noch dekodiert wird, ist der Titel nicht zu
        # Ende, auch wenn der kurze Anfang schon ausgelaufen ist
        return pygame.mixer.music.get_busy() or self._sid_pending

    def cleanup(self) -> None:
        """Raumt pygame.mixer auf."""
        if self._initialized:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            except Exception:
                pass
            self._initialized = False
