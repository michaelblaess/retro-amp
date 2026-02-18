"""Shared Fixtures und Mock-Implementierungen."""
from __future__ import annotations

from pathlib import Path

import pytest

from retro_amp.domain.models import AudioTrack, Playlist, PlaylistEntry


class MockAudioPlayer:
    """In-Memory AudioPlayer fuer Tests. Implementiert AudioPlayer Protocol."""

    def __init__(self) -> None:
        self.current_path: Path | None = None
        self.playing = False
        self.paused = False
        self.volume = 1.0
        self.position = 0.0

    def play(self, path: Path) -> None:
        self.current_path = path
        self.playing = True
        self.paused = False
        self.position = 0.0

    def pause(self) -> None:
        self.paused = True
        self.playing = False

    def unpause(self) -> None:
        self.paused = False
        self.playing = True

    def stop(self) -> None:
        self.playing = False
        self.paused = False
        self.position = 0.0

    def set_volume(self, volume: float) -> None:
        self.volume = volume

    def get_position(self) -> float:
        return self.position

    def is_busy(self) -> bool:
        return self.playing


class MockMetadataReader:
    """In-Memory MetadataReader fuer Tests. Implementiert MetadataReader Protocol."""

    def __init__(self) -> None:
        self.tracks: dict[Path, AudioTrack] = {}

    def read(self, path: Path) -> AudioTrack:
        if path in self.tracks:
            return self.tracks[path]
        return AudioTrack(path=path)


class MockPlaylistRepository:
    """In-Memory PlaylistRepository fuer Tests."""

    def __init__(self) -> None:
        self.playlists: dict[str, Playlist] = {}

    def load(self, name: str) -> Playlist:
        if name in self.playlists:
            return self.playlists[name]
        return Playlist(name=name)

    def save(self, playlist: Playlist) -> None:
        self.playlists[playlist.name] = playlist

    def list_all(self) -> list[str]:
        return sorted(self.playlists.keys())

    def delete(self, name: str) -> None:
        self.playlists.pop(name, None)


@pytest.fixture
def mock_player() -> MockAudioPlayer:
    return MockAudioPlayer()


@pytest.fixture
def mock_metadata_reader() -> MockMetadataReader:
    return MockMetadataReader()


@pytest.fixture
def mock_playlist_repo() -> MockPlaylistRepository:
    return MockPlaylistRepository()


@pytest.fixture
def sample_track() -> AudioTrack:
    return AudioTrack(
        path=Path("/music/test.mp3"),
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        duration_seconds=180.0,
        bitrate_kbps=320,
        sample_rate=44100,
    )


@pytest.fixture
def sample_tracks() -> list[AudioTrack]:
    return [
        AudioTrack(path=Path("/music/track1.mp3"), title="Track 1", duration_seconds=120.0),
        AudioTrack(path=Path("/music/track2.ogg"), title="Track 2", duration_seconds=200.0),
        AudioTrack(path=Path("/music/track3.flac"), title="Track 3", duration_seconds=300.0),
    ]
