"""Domain-Models fuer retro-amp."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class PlaybackState(Enum):
    """Aktueller Zustand des Players."""

    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class AudioFormat(Enum):
    """Unterstuetzte Audio-Formate."""

    MP3 = "mp3"
    OGG = "ogg"
    OPUS = "opus"
    FLAC = "flac"
    WAV = "wav"
    MOD = "mod"
    XM = "xm"
    S3M = "s3m"
    SID = "sid"
    UNKNOWN = "unknown"

    @classmethod
    def from_extension(cls, ext: str) -> AudioFormat:
        """Bestimmt das Format anhand der Dateiendung."""
        mapping: dict[str, AudioFormat] = {
            ".mp3": cls.MP3,
            ".ogg": cls.OGG,
            ".oga": cls.OGG,
            ".opus": cls.OPUS,
            ".flac": cls.FLAC,
            ".wav": cls.WAV,
            ".mod": cls.MOD,
            ".xm": cls.XM,
            ".s3m": cls.S3M,
            ".sid": cls.SID,
        }
        return mapping.get(ext.lower(), cls.UNKNOWN)

    @classmethod
    def supported_extensions(cls) -> set[str]:
        """Alle unterstuetzten Dateiendungen."""
        return {".mp3", ".ogg", ".oga", ".opus", ".flac", ".wav", ".mod", ".xm", ".s3m", ".sid"}


@dataclass
class AudioTrack:
    """Metadaten eines Audio-Tracks."""

    path: Path
    name: str = ""
    format: AudioFormat = AudioFormat.UNKNOWN
    duration_seconds: float = 0.0
    bitrate_kbps: int = 0
    sample_rate: int = 0
    artist: str = ""
    album: str = ""
    title: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.path.name
        if self.format == AudioFormat.UNKNOWN:
            self.format = AudioFormat.from_extension(self.path.suffix)

    @property
    def display_name(self) -> str:
        """Anzeigename: Titel aus Tags oder Dateiname."""
        if self.title:
            return self.title
        return self.path.stem

    @property
    def duration_display(self) -> str:
        """Formatierte Dauer als MM:SS oder HH:MM:SS."""
        total = int(self.duration_seconds)
        if total <= 0:
            return "--:--"
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    @property
    def bitrate_display(self) -> str:
        """Formatierte Bitrate."""
        if self.bitrate_kbps <= 0:
            return ""
        return f"{self.bitrate_kbps} kbps"

    @property
    def format_display(self) -> str:
        """Format als Grossbuchstaben."""
        return self.format.value.upper()


@dataclass
class PlayerState:
    """Aktueller Zustand des Audio-Players."""

    state: PlaybackState = PlaybackState.STOPPED
    current_track: AudioTrack | None = None
    position_seconds: float = 0.0
    volume: float = 0.8
    track_list: list[AudioTrack] = field(default_factory=list)
    current_index: int = -1

    @property
    def is_playing(self) -> bool:
        return self.state == PlaybackState.PLAYING

    @property
    def is_paused(self) -> bool:
        return self.state == PlaybackState.PAUSED

    @property
    def is_stopped(self) -> bool:
        return self.state == PlaybackState.STOPPED

    @property
    def has_next(self) -> bool:
        return self.current_index < len(self.track_list) - 1

    @property
    def has_previous(self) -> bool:
        return self.current_index > 0

    @property
    def progress(self) -> float:
        """Fortschritt als Wert zwischen 0.0 und 1.0."""
        if not self.current_track or self.current_track.duration_seconds <= 0:
            return 0.0
        return min(self.position_seconds / self.current_track.duration_seconds, 1.0)

    @property
    def position_display(self) -> str:
        """Aktuelle Position als MM:SS."""
        total = int(self.position_seconds)
        minutes, seconds = divmod(total, 60)
        return f"{minutes}:{seconds:02d}"


@dataclass
class PlaylistEntry:
    """Ein Eintrag in einer Playlist."""

    path: Path
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.path.name


@dataclass
class Playlist:
    """Eine Playlist mit Eintraegen."""

    name: str
    entries: list[PlaylistEntry] = field(default_factory=list)
    file_path: Path | None = None

    def add(self, path: Path) -> bool:
        """Fuegt einen Track hinzu. Gibt False zurueck wenn bereits vorhanden."""
        if any(e.path == path for e in self.entries):
            return False
        self.entries.append(PlaylistEntry(path=path))
        return True

    def remove(self, path: Path) -> bool:
        """Entfernt einen Track. Gibt False zurueck wenn nicht vorhanden."""
        for i, entry in enumerate(self.entries):
            if entry.path == path:
                self.entries.pop(i)
                return True
        return False

    def contains(self, path: Path) -> bool:
        """Prueft ob ein Track in der Playlist ist."""
        return any(e.path == path for e in self.entries)
