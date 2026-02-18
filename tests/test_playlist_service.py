"""Tests fuer PlaylistService."""
from __future__ import annotations

from pathlib import Path

from retro_amp.services.playlist_service import PlaylistService, FAVORITES_NAME


class TestPlaylistServiceFavorites:
    def test_add_to_favorites(self, mock_playlist_repo) -> None:
        service = PlaylistService(mock_playlist_repo)
        assert service.add_to_favorites(Path("/music/song.mp3"))

    def test_add_duplicate_returns_false(self, mock_playlist_repo) -> None:
        service = PlaylistService(mock_playlist_repo)
        service.add_to_favorites(Path("/music/song.mp3"))
        assert not service.add_to_favorites(Path("/music/song.mp3"))

    def test_is_favorite(self, mock_playlist_repo) -> None:
        service = PlaylistService(mock_playlist_repo)
        path = Path("/music/song.mp3")
        assert not service.is_favorite(path)
        service.add_to_favorites(path)
        assert service.is_favorite(path)

    def test_remove_from_favorites(self, mock_playlist_repo) -> None:
        service = PlaylistService(mock_playlist_repo)
        path = Path("/music/song.mp3")
        service.add_to_favorites(path)
        assert service.remove_from_favorites(path)
        assert not service.is_favorite(path)

    def test_remove_nonexistent_returns_false(self, mock_playlist_repo) -> None:
        service = PlaylistService(mock_playlist_repo)
        assert not service.remove_from_favorites(Path("/music/nope.mp3"))

    def test_toggle_favorite_adds(self, mock_playlist_repo) -> None:
        service = PlaylistService(mock_playlist_repo)
        path = Path("/music/song.mp3")
        assert service.toggle_favorite(path) is True
        assert service.is_favorite(path)

    def test_toggle_favorite_removes(self, mock_playlist_repo) -> None:
        service = PlaylistService(mock_playlist_repo)
        path = Path("/music/song.mp3")
        service.add_to_favorites(path)
        assert service.toggle_favorite(path) is False
        assert not service.is_favorite(path)

    def test_get_favorites_persists(self, mock_playlist_repo) -> None:
        service = PlaylistService(mock_playlist_repo)
        service.add_to_favorites(Path("/music/a.mp3"))
        service.add_to_favorites(Path("/music/b.mp3"))
        favs = service.get_favorites()
        assert len(favs.entries) == 2


class TestPlaylistServicePlaylists:
    def test_create_playlist(self, mock_playlist_repo) -> None:
        service = PlaylistService(mock_playlist_repo)
        playlist = service.create_playlist("Rock")
        assert playlist.name == "Rock"
        assert len(playlist.entries) == 0

    def test_add_to_playlist(self, mock_playlist_repo) -> None:
        service = PlaylistService(mock_playlist_repo)
        service.create_playlist("Rock")
        assert service.add_to_playlist("Rock", Path("/music/song.mp3"))

    def test_add_duplicate_to_playlist(self, mock_playlist_repo) -> None:
        service = PlaylistService(mock_playlist_repo)
        service.create_playlist("Rock")
        service.add_to_playlist("Rock", Path("/music/song.mp3"))
        assert not service.add_to_playlist("Rock", Path("/music/song.mp3"))

    def test_remove_from_playlist(self, mock_playlist_repo) -> None:
        service = PlaylistService(mock_playlist_repo)
        service.create_playlist("Rock")
        service.add_to_playlist("Rock", Path("/music/song.mp3"))
        assert service.remove_from_playlist("Rock", Path("/music/song.mp3"))

    def test_list_playlists(self, mock_playlist_repo) -> None:
        service = PlaylistService(mock_playlist_repo)
        service.create_playlist("Rock")
        service.create_playlist("Jazz")
        names = service.list_playlists()
        assert "Rock" in names
        assert "Jazz" in names

    def test_delete_playlist(self, mock_playlist_repo) -> None:
        service = PlaylistService(mock_playlist_repo)
        service.create_playlist("Rock")
        service.delete_playlist("Rock")
        assert "Rock" not in service.list_playlists()

    def test_load_playlist_tracks(self, mock_playlist_repo) -> None:
        service = PlaylistService(mock_playlist_repo)
        service.create_playlist("Mix")
        service.add_to_playlist("Mix", Path("/music/a.mp3"))
        service.add_to_playlist("Mix", Path("/music/b.ogg"))
        tracks = service.load_playlist_tracks("Mix")
        assert len(tracks) == 2
        assert Path("/music/a.mp3") in tracks
        assert Path("/music/b.ogg") in tracks
