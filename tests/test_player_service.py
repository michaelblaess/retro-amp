"""Tests fuer PlayerService."""
from __future__ import annotations

from pathlib import Path

import pytest

from retro_amp.domain.models import AudioTrack, PlaybackState
from retro_amp.services.player_service import PlayerService


class TestPlayerService:
    def test_play_track(self, mock_player, sample_tracks) -> None:
        service = PlayerService(mock_player)
        service.load_tracks(sample_tracks)
        service.play_track(0)

        assert service.state.is_playing
        assert service.state.current_track == sample_tracks[0]
        assert service.state.current_index == 0
        assert mock_player.current_path == sample_tracks[0].path

    def test_toggle_pause(self, mock_player, sample_track) -> None:
        service = PlayerService(mock_player)
        service.play_file(sample_track)

        # Pause
        service.toggle_pause()
        assert service.state.is_paused
        assert mock_player.paused

        # Unpause
        service.toggle_pause()
        assert service.state.is_playing

    def test_stop(self, mock_player, sample_track) -> None:
        service = PlayerService(mock_player)
        service.play_file(sample_track)
        service.stop()

        assert service.state.is_stopped
        assert service.state.position_seconds == 0.0

    def test_next_track(self, mock_player, sample_tracks) -> None:
        service = PlayerService(mock_player)
        service.load_tracks(sample_tracks)
        service.play_track(0)
        service.next_track()

        assert service.state.current_index == 1
        assert service.state.current_track == sample_tracks[1]

    def test_next_track_at_end_does_nothing(self, mock_player, sample_tracks) -> None:
        service = PlayerService(mock_player)
        service.load_tracks(sample_tracks)
        service.play_track(2)
        service.next_track()

        assert service.state.current_index == 2

    def test_previous_track(self, mock_player, sample_tracks) -> None:
        service = PlayerService(mock_player)
        service.load_tracks(sample_tracks)
        service.play_track(1)
        service.previous_track()

        assert service.state.current_index == 0
        assert service.state.current_track == sample_tracks[0]

    def test_volume_up(self, mock_player) -> None:
        service = PlayerService(mock_player)
        service.set_volume(0.5)
        service.volume_up()

        assert service.state.volume == 0.55
        assert mock_player.volume == 0.55

    def test_volume_down(self, mock_player) -> None:
        service = PlayerService(mock_player)
        service.set_volume(0.5)
        service.volume_down()

        assert service.state.volume == 0.45
        assert mock_player.volume == 0.45

    def test_volume_clamped_at_max(self, mock_player) -> None:
        service = PlayerService(mock_player)
        service.set_volume(0.98)
        service.volume_up()

        assert service.state.volume == 1.0

    def test_volume_clamped_at_min(self, mock_player) -> None:
        service = PlayerService(mock_player)
        service.set_volume(0.02)
        service.volume_down()

        assert service.state.volume == 0.0

    def test_play_invalid_index_does_nothing(self, mock_player, sample_tracks) -> None:
        service = PlayerService(mock_player)
        service.load_tracks(sample_tracks)
        service.play_track(99)

        assert service.state.is_stopped

    def test_seek_forward(self, mock_player, sample_track) -> None:
        service = PlayerService(mock_player)
        service.play_file(sample_track)
        mock_player.position = 10.0
        service.update_position()

        service.seek_forward(5.0)
        assert service.state.position_seconds == 15.0
        assert mock_player.position == 15.0

    def test_seek_backward(self, mock_player, sample_track) -> None:
        service = PlayerService(mock_player)
        service.play_file(sample_track)
        mock_player.position = 10.0
        service.update_position()

        service.seek_backward(5.0)
        assert service.state.position_seconds == 5.0
        assert mock_player.position == 5.0

    def test_seek_backward_clamps_at_zero(self, mock_player, sample_track) -> None:
        service = PlayerService(mock_player)
        service.play_file(sample_track)
        mock_player.position = 2.0
        service.update_position()

        service.seek_backward(5.0)
        assert service.state.position_seconds == 0.0

    def test_seek_does_nothing_when_stopped(self, mock_player, sample_track) -> None:
        service = PlayerService(mock_player)
        # Nicht abspielen — stopped
        service.seek_forward(5.0)
        assert service.state.position_seconds == 0.0

    def test_on_finished_callback(self, mock_player, sample_track) -> None:
        finished_called = False

        def on_finished() -> None:
            nonlocal finished_called
            finished_called = True

        service = PlayerService(mock_player)
        service.set_callbacks(on_finished=on_finished)
        service.play_file(sample_track)

        # Simuliere: Track ist fertig
        mock_player.playing = False
        mock_player.position = 1.0
        service.update_position()

        assert finished_called
