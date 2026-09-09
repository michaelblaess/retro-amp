"""Shared Fixtures und Mock-Implementierungen."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from retro_amp.domain.models import AudioTrack, Playlist
from retro_amp.infrastructure import playlist_store as playlist_modul
from retro_amp.infrastructure import session as session_modul
from retro_amp.infrastructure import settings as settings_modul
from retro_amp.infrastructure import single_instance as lock_modul


@pytest.fixture
def isolierte_ablage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Legt ``~/.retro-amp`` fuer die Dauer eines Tests in ein Temp-Verzeichnis.

    Vier Module berechnen ihren Pfad schon beim Import, die Datenbank fragt
    `Path.home()` erst beim Erzeugen - deshalb beides. Ohne das schriebe der
    Test in die echte Ablage des Anwenders.
    """

    heim = tmp_path / "heim"
    ablage = heim / ".retro-amp"
    ablage.mkdir(parents=True)
    musik = tmp_path / "Musik"
    musik.mkdir()
    # Zwei Unterordner, damit der Verzeichnisbaum ueberhaupt Zeilen hat - ohne
    # sie kann ein Navigationstest nichts bewegen und waere still gruen.
    (musik / "Alben").mkdir()
    (musik / "Singles").mkdir()
    (ablage / "settings.json").write_text(
        json.dumps({"music_library": str(musik), "last_path": str(musik)}),
        encoding="utf-8",
    )

    monkeypatch.setattr(Path, "home", staticmethod(lambda: heim))
    monkeypatch.setattr(settings_modul, "_SETTINGS_DIR", ablage)
    monkeypatch.setattr(settings_modul, "_SETTINGS_FILE", ablage / "settings.json")
    monkeypatch.setattr(session_modul, "_SESSION_DIR", ablage)
    monkeypatch.setattr(session_modul, "_SESSION_FILE", ablage / "session.json")
    monkeypatch.setattr(lock_modul, "_LOCK_DIR", ablage)
    monkeypatch.setattr(lock_modul, "_LOCK_FILE", ablage / "instance.lock")
    monkeypatch.setattr(lock_modul, "_PLAY_REQUEST", ablage / "play_request")
    monkeypatch.setattr(playlist_modul, "_PLAYLISTS_DIR", ablage / "playlists")
    yield heim


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

    def seek(self, position_seconds: float) -> None:
        self.position = max(0.0, position_seconds)

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
