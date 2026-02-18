"""Metadata-Service — Audio-Metadaten lesen und Dateien filtern."""
from __future__ import annotations

from pathlib import Path

from ..domain.models import AudioFormat, AudioTrack
from ..domain.protocols import MetadataReader


class MetadataService:
    """Liest Audio-Metadaten und filtert Dateien.

    Kennt nur domain/, nie infrastructure/.
    Bekommt MetadataReader via Protocol-Typ im Konstruktor (DI).
    """

    def __init__(self, reader: MetadataReader) -> None:
        self._reader = reader

    def read_track(self, path: Path) -> AudioTrack:
        """Liest Metadaten eines einzelnen Tracks."""
        return self._reader.read(path)

    def scan_directory(self, directory: Path) -> list[AudioTrack]:
        """Scannt ein Verzeichnis nach Audio-Dateien und liest deren Metadaten."""
        if not directory.is_dir():
            return []

        tracks: list[AudioTrack] = []
        supported = AudioFormat.supported_extensions()

        try:
            for entry in sorted(directory.iterdir()):
                if entry.is_file() and entry.suffix.lower() in supported:
                    track = self._reader.read(entry)
                    tracks.append(track)
        except PermissionError:
            pass

        return tracks

    def is_audio_file(self, path: Path) -> bool:
        """Prueft ob eine Datei ein unterstuetztes Audio-Format ist."""
        return path.suffix.lower() in AudioFormat.supported_extensions()
