"""Protocols (Interfaces) fuer retro-amp.

Definiert WAS, nicht WIE. Python-Aequivalent von C#-Interfaces.
Implementierungen leben in infrastructure/.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from .models import AudioTrack, HistoryEntry, Playlist


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

    def unload(self) -> None:
        """Entlaedt die aktuelle Datei und gibt den File-Handle frei."""
        ...

    def set_volume(self, volume: float) -> None:
        """Setzt die Lautstaerke (0.0 bis 1.0)."""
        ...

    def get_position(self) -> float:
        """Gibt die aktuelle Position in Sekunden zurueck."""
        ...

    def seek(self, position_seconds: float) -> None:
        """Springt zu einer bestimmten Position in Sekunden."""
        ...

    def is_busy(self) -> bool:
        """Prueft ob gerade abgespielt wird."""
        ...


class MetadataReader(Protocol):
    """Interface fuer Audio-Metadaten."""

    def read(self, path: Path) -> AudioTrack:
        """Liest Metadaten einer Audio-Datei."""
        ...

    def extract_cover_art(self, path: Path) -> bytes | None:
        """Extrahiert Cover-Art als Bilddaten (JPEG/PNG) oder None."""
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

    def update_path(self, old: Path, new: Path) -> int:
        """Ersetzt einen Track-Pfad in allen Playlists (nach Umbenennung).

        Gibt die Anzahl der geaenderten Eintraege zurueck.
        """
        ...


class HistoryRepository(Protocol):
    """Interface fuer Wiedergabeverlauf-Persistenz."""

    def add(self, path: Path) -> None:
        """Speichert einen Play-Eintrag mit aktuellem Zeitstempel."""
        ...

    def list_recent(self, limit: int = 1000) -> list[HistoryEntry]:
        """Liefert die letzten Eintraege (neuster zuerst)."""
        ...

    def clear(self) -> None:
        """Loescht den gesamten Verlauf."""
        ...

    def trim(self, max_entries: int) -> None:
        """Behaelt nur die letzten ``max_entries`` Eintraege."""
        ...

    def update_path(self, old: Path, new: Path) -> int:
        """Ersetzt einen Pfad im Verlauf (nach Umbenennung).

        Gibt die Anzahl der geaenderten Eintraege zurueck.
        """
        ...


class SearchHistoryRepository(Protocol):
    """Interface fuer Such-Verlauf-Persistenz."""

    def add(self, query: str) -> None:
        """Speichert eine Suchanfrage (UPSERT, aktualisiert Zeitstempel + Count)."""
        ...

    def list_recent(self, limit: int = 20) -> list[str]:
        """Liefert die letzten Suchanfragen (neueste zuerst)."""
        ...

    def delete(self, query: str) -> None:
        """Loescht eine einzelne Suchanfrage aus dem Verlauf."""
        ...

    def clear(self) -> None:
        """Loescht den gesamten Such-Verlauf."""
        ...

    def trim(self, max_entries: int) -> None:
        """Behaelt nur die letzten ``max_entries`` Eintraege."""
        ...


class SettingsStore(Protocol):
    """Interface fuer Settings-Persistenz."""

    def load(self) -> dict[str, object]:
        """Laedt Settings als Dictionary."""
        ...

    def save(self, data: dict[str, object]) -> None:
        """Speichert Settings."""
        ...


class TagIO(Protocol):
    """Interface zum Lesen eingebetteter Tags und Schreiben des Titels."""

    def read_embedded_title(self, path: Path) -> str:
        """Liest den eingebetteten Titel-Tag (leer wenn keiner)."""
        ...

    def read_embedded_artist(self, path: Path) -> str:
        """Liest den eingebetteten Artist-Tag (leer wenn keiner)."""
        ...

    def read_embedded_album(self, path: Path) -> str:
        """Liest den eingebetteten Album-Tag (leer wenn keiner)."""
        ...

    def read_track_number(self, path: Path) -> int:
        """Liest die Tracknummer aus den Tags (0 wenn keine)."""
        ...

    def write_title(self, path: Path, title: str) -> None:
        """Schreibt den Titel in die Tags.

        Wirft ``UnsupportedTagFormatError`` bei Formaten ohne Tag-Support.
        """
        ...


class TrackTitleLookup(Protocol):
    """Interface fuer eine Einzeltrack-Titelsuche per Audio-Fingerprint (AcoustID)."""

    def available(self) -> bool:
        """True wenn die Quelle einsatzbereit ist (Werkzeug + API-Key vorhanden)."""
        ...

    def lookup_title(self, path: Path, duration_seconds: float) -> str | None:
        """Erkennt den Titel einer Datei am Audio-Fingerprint.

        Gibt den Titel zurueck oder ``None``, wenn kein eindeutiger,
        abgesicherter Treffer vorliegt.
        """
        ...


class AlbumTitleLookup(Protocol):
    """Interface fuer eine Album-Trackliste-Suche (z.B. MusicBrainz)."""

    def lookup_tracklist(
        self,
        artist: str,
        album: str,
        track_count: int,
        durations: list[float] | None = None,
    ) -> list[str] | None:
        """Sucht die Titel eines Albums in Positionsreihenfolge.

        Gibt eine Liste der Laenge ``track_count`` zurueck (Titel je Position)
        oder ``None``, wenn kein eindeutiger, abgesicherter Treffer vorliegt.
        ``durations`` (Sekunden je Position) dient der Plausibilitaetspruefung.
        """
        ...


# Callback-Typen fuer entkoppelte Kommunikation
OnProgressCallback = Callable[[float], None]
OnFinishedCallback = Callable[[], None]
OnErrorCallback = Callable[[str], None]
OnTrackStartedCallback = Callable[[AudioTrack], None]
