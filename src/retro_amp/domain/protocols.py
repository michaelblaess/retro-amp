"""Protocols (Interfaces) fuer retro-amp.

Definiert WAS, nicht WIE. Python-Aequivalent von C#-Interfaces.
Implementierungen leben in infrastructure/.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

from .models import AudioTrack, Playlist


class AudioPlayer(Protocol):
    """Interface fuer Audio-Playback."""

    def play(self, path: Path) -> None:
        """Spielt eine Audio-Datei ab."""
        ...

    def pause(self) -> None:
        """Pausiert die Wiedergabe."""
        ...

    def unpause(self) -> None:
        """Setzt die Wiedergabe fort."""
        ...

    def stop(self) -> None:
        """Stoppt die Wiedergabe."""
        ...

    def set_volume(self, volume: float) -> None:
        """Setzt die Lautstaerke (0.0 bis 1.0)."""
        ...

    def get_position(self) -> float:
        """Gibt die aktuelle Position in Sekunden zurueck."""
        ...

    def is_busy(self) -> bool:
        """Prueft ob gerade abgespielt wird."""
        ...


class MetadataReader(Protocol):
    """Interface fuer Audio-Metadaten."""

    def read(self, path: Path) -> AudioTrack:
        """Liest Metadaten einer Audio-Datei."""
        ...


class PlaylistRepository(Protocol):
    """Interface fuer Playlist-Persistenz."""

    def load(self, name: str) -> Playlist:
        """Laedt eine Playlist nach Name."""
        ...

    def save(self, playlist: Playlist) -> None:
        """Speichert eine Playlist."""
        ...

    def list_all(self) -> list[str]:
        """Gibt alle Playlist-Namen zurueck."""
        ...

    def delete(self, name: str) -> None:
        """Loescht eine Playlist."""
        ...


class SettingsStore(Protocol):
    """Interface fuer Settings-Persistenz."""

    def load(self) -> dict[str, object]:
        """Laedt Settings als Dictionary."""
        ...

    def save(self, data: dict[str, object]) -> None:
        """Speichert Settings."""
        ...


# Callback-Typen fuer entkoppelte Kommunikation
OnProgressCallback = Callable[[float], None]
OnFinishedCallback = Callable[[], None]
OnErrorCallback = Callable[[str], None]
