"""Tests fuer Domain-Models."""
from __future__ import annotations

from pathlib import Path

from retro_amp.domain.models import (
    AudioFormat,
    AudioTrack,
    PlaybackState,
    PlayerState,
    Playlist,
    PlaylistEntry,
)


class TestAudioFormat:
    def test_from_extension_mp3(self) -> None:
        assert AudioFormat.from_extension(".mp3") == AudioFormat.MP3

    def test_from_extension_case_insensitive(self) -> None:
        assert AudioFormat.from_extension(".MP3") == AudioFormat.MP3

    def test_from_extension_unknown(self) -> None:
        assert AudioFormat.from_extension(".txt") == AudioFormat.UNKNOWN

    def test_supported_extensions_contains_common(self) -> None:
        exts = AudioFormat.supported_extensions()
        assert ".mp3" in exts
        assert ".ogg" in exts
        assert ".flac" in exts
        assert ".wav" in exts
        assert ".mod" in exts
        assert ".sid" in exts


class TestAudioTrack:
    def test_default_name_from_path(self) -> None:
        track = AudioTrack(path=Path("/music/song.mp3"))
        assert track.name == "song.mp3"

    def test_auto_format_from_extension(self) -> None:
        track = AudioTrack(path=Path("/music/song.flac"))
        assert track.format == AudioFormat.FLAC

    def test_display_name_uses_title(self) -> None:
        track = AudioTrack(path=Path("/music/song.mp3"), title="Mein Lied")
        assert track.display_name == "Mein Lied"

    def test_display_name_fallback_to_stem(self) -> None:
        track = AudioTrack(path=Path("/music/song.mp3"))
        assert track.display_name == "song"

    def test_duration_display_minutes(self) -> None:
        track = AudioTrack(path=Path("/x.mp3"), duration_seconds=185.0)
        assert track.duration_display == "3:05"

    def test_duration_display_hours(self) -> None:
        track = AudioTrack(path=Path("/x.mp3"), duration_seconds=3661.0)
        assert track.duration_display == "1:01:01"

    def test_duration_display_zero(self) -> None:
        track = AudioTrack(path=Path("/x.mp3"), duration_seconds=0.0)
        assert track.duration_display == "--:--"

    def test_bitrate_display(self) -> None:
        track = AudioTrack(path=Path("/x.mp3"), bitrate_kbps=320)
        assert track.bitrate_display == "320 kbps"

    def test_bitrate_display_empty(self) -> None:
        track = AudioTrack(path=Path("/x.mp3"))
        assert track.bitrate_display == ""

    def test_format_display_uppercase(self) -> None:
        track = AudioTrack(path=Path("/x.mp3"))
        assert track.format_display == "MP3"


class TestPlayerState:
    def test_default_state_is_stopped(self) -> None:
        state = PlayerState()
        assert state.is_stopped
        assert not state.is_playing
        assert not state.is_paused

    def test_has_next(self) -> None:
        tracks = [
            AudioTrack(path=Path("/a.mp3")),
            AudioTrack(path=Path("/b.mp3")),
        ]
        state = PlayerState(track_list=tracks, current_index=0)
        assert state.has_next

    def test_has_no_next_at_end(self) -> None:
        tracks = [
            AudioTrack(path=Path("/a.mp3")),
            AudioTrack(path=Path("/b.mp3")),
        ]
        state = PlayerState(track_list=tracks, current_index=1)
        assert not state.has_next

    def test_has_previous(self) -> None:
        tracks = [
            AudioTrack(path=Path("/a.mp3")),
            AudioTrack(path=Path("/b.mp3")),
        ]
        state = PlayerState(track_list=tracks, current_index=1)
        assert state.has_previous

    def test_has_no_previous_at_start(self) -> None:
        tracks = [AudioTrack(path=Path("/a.mp3"))]
        state = PlayerState(track_list=tracks, current_index=0)
        assert not state.has_previous

    def test_progress_calculation(self) -> None:
        track = AudioTrack(path=Path("/x.mp3"), duration_seconds=100.0)
        state = PlayerState(
            current_track=track,
            position_seconds=50.0,
            state=PlaybackState.PLAYING,
        )
        assert state.progress == 0.5

    def test_progress_zero_without_track(self) -> None:
        state = PlayerState()
        assert state.progress == 0.0

    def test_position_display(self) -> None:
        state = PlayerState(position_seconds=125.0)
        assert state.position_display == "2:05"


class TestPlaylist:
    def test_add_track(self) -> None:
        playlist = Playlist(name="test")
        assert playlist.add(Path("/music/song.mp3"))
        assert len(playlist.entries) == 1

    def test_add_duplicate_returns_false(self) -> None:
        playlist = Playlist(name="test")
        playlist.add(Path("/music/song.mp3"))
        assert not playlist.add(Path("/music/song.mp3"))
        assert len(playlist.entries) == 1

    def test_remove_track(self) -> None:
        playlist = Playlist(name="test")
        playlist.add(Path("/music/song.mp3"))
        assert playlist.remove(Path("/music/song.mp3"))
        assert len(playlist.entries) == 0

    def test_remove_nonexistent_returns_false(self) -> None:
        playlist = Playlist(name="test")
        assert not playlist.remove(Path("/music/nope.mp3"))

    def test_contains(self) -> None:
        playlist = Playlist(name="test")
        playlist.add(Path("/music/song.mp3"))
        assert playlist.contains(Path("/music/song.mp3"))
        assert not playlist.contains(Path("/music/other.mp3"))
