"""Player-Service — Play/Pause/Next/Prev Logik."""
from __future__ import annotations

from pathlib import Path

from ..domain.models import AudioTrack, PlaybackState, PlayerState
from ..domain.protocols import AudioPlayer, OnErrorCallback, OnFinishedCallback


class PlayerService:
    """Steuert die Audio-Wiedergabe.

    Kennt nur domain/, nie infrastructure/.
    Bekommt AudioPlayer via Protocol-Typ im Konstruktor (DI).
    """

    def __init__(self, audio_player: AudioPlayer) -> None:
        self._player = audio_player
        self._state = PlayerState()
        self._on_finished: OnFinishedCallback | None = None
        self._on_error: OnErrorCallback | None = None

    @property
    def state(self) -> PlayerState:
        return self._state

    def set_callbacks(
        self,
        on_finished: OnFinishedCallback | None = None,
        on_error: OnErrorCallback | None = None,
    ) -> None:
        """Setzt Callbacks fuer Events."""
        self._on_finished = on_finished
        self._on_error = on_error

    def load_tracks(self, tracks: list[AudioTrack]) -> None:
        """Laedt eine Liste von Tracks in den Player."""
        self._state.track_list = tracks
        self._state.current_index = -1
        self._state.current_track = None

    def play_track(self, index: int) -> None:
        """Spielt einen bestimmten Track ab."""
        if index < 0 or index >= len(self._state.track_list):
            return

        track = self._state.track_list[index]
        try:
            self._player.play(track.path)
            self._state.current_track = track
            self._state.current_index = index
            self._state.state = PlaybackState.PLAYING
            self._state.position_seconds = 0.0
        except Exception as e:
            self._state.state = PlaybackState.STOPPED
            if self._on_error:
                self._on_error(str(e))

    def play_file(self, track: AudioTrack) -> None:
        """Spielt einen einzelnen Track ab (ohne Tracklist-Kontext)."""
        try:
            self._player.play(track.path)
            self._state.current_track = track
            self._state.state = PlaybackState.PLAYING
            self._state.position_seconds = 0.0
        except Exception as e:
            self._state.state = PlaybackState.STOPPED
            if self._on_error:
                self._on_error(str(e))

    def toggle_pause(self) -> None:
        """Wechselt zwischen Play und Pause."""
        if self._state.is_playing:
            self._player.pause()
            self._state.state = PlaybackState.PAUSED
        elif self._state.is_paused:
            self._player.unpause()
            self._state.state = PlaybackState.PLAYING

    def stop(self) -> None:
        """Stoppt die Wiedergabe."""
        self._player.stop()
        self._state.state = PlaybackState.STOPPED
        self._state.position_seconds = 0.0

    def next_track(self) -> None:
        """Spielt den naechsten Track."""
        if self._state.has_next:
            self.play_track(self._state.current_index + 1)

    def previous_track(self) -> None:
        """Spielt den vorherigen Track."""
        if self._state.has_previous:
            self.play_track(self._state.current_index - 1)

    def set_volume(self, volume: float) -> None:
        """Setzt die Lautstaerke (0.0 bis 1.0)."""
        self._state.volume = max(0.0, min(1.0, volume))
        self._player.set_volume(self._state.volume)

    def seek_forward(self, seconds: float = 5.0) -> None:
        """Springt vorwaerts."""
        if self._state.current_track and not self._state.is_stopped:
            new_pos = min(
                self._state.position_seconds + seconds,
                self._state.current_track.duration_seconds,
            )
            self._player.seek(new_pos)
            self._state.position_seconds = new_pos

    def seek_backward(self, seconds: float = 5.0) -> None:
        """Springt zurueck."""
        if self._state.current_track and not self._state.is_stopped:
            new_pos = max(self._state.position_seconds - seconds, 0.0)
            self._player.seek(new_pos)
            self._state.position_seconds = new_pos

    def volume_up(self, step: float = 0.05) -> None:
        """Erhoet die Lautstaerke."""
        self.set_volume(self._state.volume + step)

    def volume_down(self, step: float = 0.05) -> None:
        """Verringert die Lautstaerke."""
        self.set_volume(self._state.volume - step)

    def update_position(self) -> None:
        """Aktualisiert die Position vom Player. Aufgerufen per Timer."""
        if self._state.is_playing:
            pos = self._player.get_position()
            # Nur aktualisieren wenn valide (>0), sonst alten Wert behalten
            if pos > 0:
                self._state.position_seconds = pos

            # Pruefe ob Track fertig ist:
            # is_busy() == False UND wir haben schon etwas gespielt (> 1s)
            if not self._player.is_busy() and self._state.position_seconds >= 1.0:
                self._state.state = PlaybackState.STOPPED
                if self._on_finished:
                    self._on_finished()

    def check_auto_next(self) -> None:
        """Prueft ob automatisch zum naechsten Track gewechselt werden soll."""
        if self._state.is_stopped and self._state.has_next:
            self.next_track()
