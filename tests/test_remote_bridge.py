"""Tests fuer die Bruecke nach aussen (Status-Datei und Steuer-Datei)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from retro_amp.app import RetroAmpApp
from retro_amp.domain.models import AudioTrack, PlaybackState, PlayerState
from retro_amp.infrastructure.remote_bridge import (
    BridgeStatus,
    RemoteBridge,
    parse_command,
    status_from_state,
)


def _bridge(tmp_path: Path) -> RemoteBridge:
    return RemoteBridge("9.9.9", tmp_path / "now-playing.json", tmp_path / "control", heartbeat_seconds=5.0)


def _status(state: str = "playing", name: str = "Song", position: float = 1.0) -> BridgeStatus:
    return BridgeStatus(
        state=state,
        title=name,
        artist="Artist",
        album="Album",
        display_name=f"Artist - {name}",
        position_seconds=position,
        duration_seconds=200.0,
    )


def _read(tmp_path: Path) -> dict[str, object]:
    data: dict[str, object] = json.loads((tmp_path / "now-playing.json").read_text(encoding="utf-8"))
    return data


def test_status_from_state_without_track_is_stopped() -> None:
    status = status_from_state(PlayerState())
    assert status.state == "stopped"
    assert status.display_name == ""
    assert status.position_seconds == 0.0


def test_status_from_state_takes_track_fields() -> None:
    track = AudioTrack(path=Path("/musik/a.mp3"), title="Space Oddity", artist="David Bowie", duration_seconds=315.0)
    state = PlayerState(state=PlaybackState.PAUSED, current_track=track, position_seconds=42.0)
    status = status_from_state(state)
    assert (status.state, status.title, status.artist) == ("paused", "Space Oddity", "David Bowie")
    assert (status.position_seconds, status.duration_seconds) == (42.0, 315.0)


def test_status_file_has_no_path(tmp_path: Path) -> None:
    track = AudioTrack(path=tmp_path / "geheim" / "a.mp3", title="T")
    bridge = _bridge(tmp_path)
    bridge.publish(status_from_state(PlayerState(state=PlaybackState.PLAYING, current_track=track)), now=100.0)
    assert "geheim" not in (tmp_path / "now-playing.json").read_text(encoding="utf-8")


def test_publish_writes_json_with_version_and_commands(tmp_path: Path) -> None:
    assert _bridge(tmp_path).publish(_status(), now=100.0)
    data = _read(tmp_path)
    assert data["version"] == 1
    assert data["app_version"] == "9.9.9"
    assert data["running"] is True
    assert data["state"] == "playing"
    assert data["updated"] == 100.0
    assert "next" in data["commands"]  # type: ignore[operator]
    assert not (tmp_path / "now-playing.json.tmp").exists()


def test_publish_skips_unchanged_until_heartbeat(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    assert bridge.publish(_status(position=1.0), now=100.0)
    # Nur die Position ist anders - noch kein neuer Schreibvorgang
    assert not bridge.publish(_status(position=2.0), now=101.0)
    # Nach dem Takt wird mit der neuen Position geschrieben
    assert bridge.publish(_status(position=6.0), now=105.0)
    assert _read(tmp_path)["position_seconds"] == 6.0


def test_publish_writes_at_once_on_state_or_track_change(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    bridge.publish(_status(), now=100.0)
    assert bridge.publish(_status(state="paused"), now=100.5)
    assert bridge.publish(_status(state="paused", name="Anderer"), now=101.0)
    assert _read(tmp_path)["title"] == "Anderer"


def test_shutdown_keeps_last_track_and_marks_not_running(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    bridge.publish(_status(name="Letzter"), now=100.0)
    bridge.shutdown(now=110.0)
    data = _read(tmp_path)
    assert (data["running"], data["state"], data["title"]) == (False, "stopped", "Letzter")


def test_shutdown_without_publish_writes_nothing(tmp_path: Path) -> None:
    _bridge(tmp_path).shutdown()
    assert not (tmp_path / "now-playing.json").exists()


def test_parse_command_accepts_known_words_only() -> None:
    assert parse_command(" NEXT\n") == "next"
    assert parse_command("play_pause extra") == "play_pause"
    assert parse_command("rm -rf") is None
    assert parse_command("") is None


def test_take_command_reads_and_deletes(tmp_path: Path) -> None:
    control = tmp_path / "control"
    control.write_text("previous", encoding="utf-8")
    bridge = _bridge(tmp_path)
    assert bridge.take_command() == "previous"
    assert not control.exists()
    assert bridge.take_command() is None


def test_take_command_drops_unknown_command(tmp_path: Path) -> None:
    control = tmp_path / "control"
    control.write_text("format c:", encoding="utf-8")
    assert _bridge(tmp_path).take_command() is None
    assert not control.exists()


class TestInDerApp:
    """Die App fuehrt Befehle aus der Steuer-Datei aus und schreibt den Status."""

    async def test_befehl_und_status(self, isolierte_ablage: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        ablage = isolierte_ablage / ".retro-amp"
        anwendung = RetroAmpApp()
        aufrufe: list[str] = []
        monkeypatch.setattr(anwendung, "action_next_track", lambda: aufrufe.append("next"))
        monkeypatch.setattr(anwendung, "action_toggle_pause", lambda: aufrufe.append("toggle"))
        async with anwendung.run_test():
            (ablage / "control").write_text("next", encoding="utf-8")
            anwendung._sync_remote_bridge()
            # Pause ohne laufenden Titel waere ein Start - also nichts tun
            (ablage / "control").write_text("pause", encoding="utf-8")
            anwendung._sync_remote_bridge()
            status = json.loads((ablage / "now-playing.json").read_text(encoding="utf-8"))
            assert (status["running"], status["state"]) == (True, "stopped")
        assert aufrufe == ["next"]
        nachher = json.loads((ablage / "now-playing.json").read_text(encoding="utf-8"))
        assert nachher["running"] is False
