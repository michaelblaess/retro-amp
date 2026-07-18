"""Domain-Models fuer retro-amp."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class PlaybackState(Enum):
    """Aktueller Zustand des Players."""

    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class RepeatMode(Enum):
    """Wiederholungs-Modus."""

    OFF = "off"
    ALL = "all"
    ONE = "one"


class VisualizerMode(Enum):
    """Darstellungs-Modus des Visualizers."""

    BARS = "bars"  # 32-Band-Spektrum, Regenbogen, Peak-Hold (Default)
    BLOCKS = "blocks"  # Winamp-Style: 16 breite Balken, Ampelfarben pro Zeile + Peaks
    SCOPE = "scope"  # Punkt pro Band an Pegel-Position (Spektralkurve)
    MATRIX = "matrix"  # Binaer-Digits, Farbe nach Band-Intensitaet (cliamp-Style)
    LCD = "lcd"  # 2 horizontale Segment-VU-Meter (Kassettendeck-Style)


class MatchSource(Enum):
    """Herkunft eines Titel-Vorschlags - bestimmt die Sicherheit.

    ``is_confirmed`` unterscheidet bewiesene Quellen (eingebettete Tags,
    Audio-Fingerprint) von der heuristischen MusicBrainz-Trackliste.
    """

    NONE = "none"  # kein Treffer
    ID3 = "id3"  # eingebetteter Tag - bestaetigt
    ACOUSTID = "acoustid"  # Audio-Fingerprint - bestaetigt
    MUSICBRAINZ = "musicbrainz"  # Trackliste (Ordner/Nummer) - heuristisch
    FILENAME = "filename"  # aus dem Dateinamen abgeleitet - Fallback, nur Tag

    @property
    def is_confirmed(self) -> bool:
        """True wenn die Quelle als sicher gilt (nicht geraten)."""
        return self in (MatchSource.ID3, MatchSource.ACOUSTID)


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
    M4A = "m4a"
    MPC = "mpc"
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
            ".m4a": cls.M4A,
            ".mpc": cls.MPC,
            ".mp+": cls.MPC,
        }
        return mapping.get(ext.lower(), cls.UNKNOWN)

    @classmethod
    def supported_extensions(cls) -> set[str]:
        """Alle unterstuetzten Dateiendungen."""
        return {
            ".mp3",
            ".ogg",
            ".oga",
            ".opus",
            ".flac",
            ".wav",
            ".mod",
            ".xm",
            ".s3m",
            ".sid",
            ".m4a",
            ".mpc",
            ".mp+",
        }


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
    file_size_bytes: int = 0
    modified_date: str = ""

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

    @property
    def size_display(self) -> str:
        """Formatierte Dateigroesse als KB oder MB."""
        if self.file_size_bytes <= 0:
            return ""
        if self.file_size_bytes < 1024 * 1024:
            return f"{self.file_size_bytes / 1024:.0f} KB"
        return f"{self.file_size_bytes / (1024 * 1024):.1f} MB"

    @property
    def date_display(self) -> str:
        """Kurzes Datum (DD.MM.YYYY)."""
        if not self.modified_date:
            return ""
        try:
            dt = datetime.fromisoformat(self.modified_date)
            return dt.strftime("%d.%m.%Y")
        except (ValueError, TypeError):
            return self.modified_date


@dataclass
class TitleProposal:
    """Vorschlag, einen fehlenden Titel fuer eine Datei zu ergaenzen.

    ``title``/``proposed_name`` sind leer, wenn kein sicherer Treffer vorliegt.
    ``selected`` steuert die Vorauswahl im Vorschau-Dialog (bestaetigte Quellen
    vorausgewaehlt, heuristische nicht).
    """

    track: AudioTrack
    title: str = ""  # vorgeschlagener Titel ("" = kein Treffer)
    proposed_name: str = ""  # neuer Dateiname inkl. Endung ("" = nur Tag, keine Umbenennung)
    source: MatchSource = MatchSource.NONE
    selected: bool = False  # Vorauswahl im Vorschau-Dialog

    @property
    def has_match(self) -> bool:
        """True wenn ein verwertbarer Titel vorliegt (Umbenennen ODER nur Tag)."""
        return bool(self.title) and self.source is not MatchSource.NONE

    @property
    def renames(self) -> bool:
        """True wenn die Datei umbenannt wird (sonst wird nur der Tag gesetzt)."""
        return bool(self.proposed_name)

    @property
    def current_name(self) -> str:
        """Aktueller Dateiname."""
        return self.track.path.name


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
class HistoryEntry:
    """Ein Eintrag im Wiedergabeverlauf."""

    path: Path
    played_at: datetime
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
