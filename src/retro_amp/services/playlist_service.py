"""Playlist-Service — CRUD fuer Playlists und Favoriten."""
from __future__ import annotations

from pathlib import Path

from ..domain.models import Playlist
from ..domain.protocols import PlaylistRepository

FAVORITES_NAME = "Favoriten"


class PlaylistService:
    """Verwaltet Playlists und Favoriten.

    Kennt nur domain/, nie infrastructure/.
    Bekommt PlaylistRepository via Protocol-Typ im Konstruktor (DI).
    """

    def __init__(self, repository: PlaylistRepository) -> None:
        self._repo = repository

    def get_favorites(self) -> Playlist:
        """Laedt die Favoriten-Playlist."""
        return self._repo.load(FAVORITES_NAME)

    def add_to_favorites(self, path: Path) -> bool:
        """Fuegt einen Track zu den Favoriten hinzu.

        Returns:
            True wenn hinzugefuegt, False wenn bereits vorhanden.
        """
        playlist = self._repo.load(FAVORITES_NAME)
        if playlist.add(path):
            self._repo.save(playlist)
            return True
        return False

    def remove_from_favorites(self, path: Path) -> bool:
        """Entfernt einen Track aus den Favoriten.

        Returns:
            True wenn entfernt, False wenn nicht vorhanden.
        """
        playlist = self._repo.load(FAVORITES_NAME)
        if playlist.remove(path):
            self._repo.save(playlist)
            return True
        return False

    def is_favorite(self, path: Path) -> bool:
        """Prueft ob ein Track in den Favoriten ist."""
        playlist = self._repo.load(FAVORITES_NAME)
        return playlist.contains(path)

    def toggle_favorite(self, path: Path) -> bool:
        """Wechselt Favoriten-Status. Gibt True zurueck wenn jetzt Favorit."""
        playlist = self._repo.load(FAVORITES_NAME)
        if playlist.contains(path):
            playlist.remove(path)
            self._repo.save(playlist)
            return False
        else:
            playlist.add(path)
            self._repo.save(playlist)
            return True

    def get_playlist(self, name: str) -> Playlist:
        """Laedt eine Playlist nach Name."""
        return self._repo.load(name)

    def create_playlist(self, name: str) -> Playlist:
        """Erstellt eine neue leere Playlist."""
        playlist = Playlist(name=name)
        self._repo.save(playlist)
        return playlist

    def add_to_playlist(self, name: str, path: Path) -> bool:
        """Fuegt einen Track zu einer Playlist hinzu.

        Returns:
            True wenn hinzugefuegt, False wenn bereits vorhanden.
        """
        playlist = self._repo.load(name)
        if playlist.add(path):
            self._repo.save(playlist)
            return True
        return False

    def remove_from_playlist(self, name: str, path: Path) -> bool:
        """Entfernt einen Track aus einer Playlist.

        Returns:
            True wenn entfernt, False wenn nicht vorhanden.
        """
        playlist = self._repo.load(name)
        if playlist.remove(path):
            self._repo.save(playlist)
            return True
        return False

    def list_playlists(self) -> list[str]:
        """Gibt alle Playlist-Namen zurueck."""
        return self._repo.list_all()

    def delete_playlist(self, name: str) -> None:
        """Loescht eine Playlist."""
        self._repo.delete(name)

    def load_playlist_tracks(self, name: str) -> list[Path]:
        """Laedt alle Track-Pfade einer Playlist."""
        playlist = self._repo.load(name)
        return [entry.path for entry in playlist.entries]
