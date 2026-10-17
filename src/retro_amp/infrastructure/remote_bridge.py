"""Bruecke nach aussen: Status-Datei und Steuer-Datei unter ``~/.retro-amp``.

Andere Programme (etwa der Turbo-MOD fuer Claude Code) lesen in
``now-playing.json``, was gerade laeuft, und schreiben einen Befehl nach
``control``. Gleiches Muster wie der Play-Request in ``single_instance``:
kein Port, kein Netzwerk, die laufende Instanz fragt per Timer nach.

Nach dem Beenden bleibt die Status-Datei mit ``running: false`` liegen,
damit ein Leser den zuletzt gespielten Titel anzeigen kann.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..domain.models import PlaybackState, PlayerState

logger = logging.getLogger(__name__)

_BRIDGE_DIR = Path.home() / ".retro-amp"
_STATUS_FILE = _BRIDGE_DIR / "now-playing.json"
_CONTROL_FILE = _BRIDGE_DIR / "control"

STATUS_VERSION = 1

# Was ein Leser schicken darf. Alles andere wird verworfen.
COMMANDS: tuple[str, ...] = ("play_pause", "play", "pause", "next", "previous", "stop")

_STATE_NAMES = {
    PlaybackState.PLAYING: "playing",
    PlaybackState.PAUSED: "paused",
    PlaybackState.STOPPED: "stopped",
}


@dataclass(frozen=True)
class BridgeStatus:
    """Momentaufnahme fuer die Status-Datei.

    Der Pfad der Datei fehlt mit Absicht: Ein Leser braucht nur Titel und
    Interpret, und der Ordner verraet mehr als noetig.
    """

    state: str
    title: str
    artist: str
    album: str
    display_name: str
    position_seconds: float
    duration_seconds: float
    running: bool = True

    def change_key(self) -> tuple[str, str, bool]:
        """Was einen sofortigen Schreibvorgang ausloest - die Position nicht."""
        return (self.state, self.display_name, self.running)

    def to_json(self, *, app_version: str, pid: int, updated: float) -> dict[str, Any]:
        """Inhalt der Status-Datei."""
        return {
            "version": STATUS_VERSION,
            "app": "retro-amp",
            "app_version": app_version,
            "pid": pid,
            "running": self.running,
            "state": self.state,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "display_name": self.display_name,
            "position_seconds": round(self.position_seconds, 1),
            "duration_seconds": round(self.duration_seconds, 1),
            "updated": round(updated, 3),
            "commands": list(COMMANDS),
        }


def status_from_state(state: PlayerState) -> BridgeStatus:
    """Baut die Momentaufnahme aus dem Player-State."""
    track = state.current_track
    return BridgeStatus(
        state=_STATE_NAMES.get(state.state, "stopped"),
        title=track.title if track else "",
        artist=track.artist if track else "",
        album=track.album if track else "",
        display_name=track.display_name if track else "",
        position_seconds=state.position_seconds if track else 0.0,
        duration_seconds=track.duration_seconds if track else 0.0,
    )


def parse_command(text: str) -> str | None:
    """Erstes Wort der Steuer-Datei, wenn es ein bekannter Befehl ist."""
    words = text.strip().lower().split()
    if not words:
        return None
    return words[0] if words[0] in COMMANDS else None


class RemoteBridge:
    """Schreibt den Status und liest Befehle, beides ohne Ausnahme nach aussen.

    Der Status wird bei jeder Aenderung von Zustand oder Titel sofort
    geschrieben, sonst alle ``heartbeat_seconds`` - daran erkennt ein Leser,
    dass die Instanz noch lebt, und rechnet die Position selbst weiter.
    """

    def __init__(
        self,
        app_version: str,
        status_file: Path | None = None,
        control_file: Path | None = None,
        heartbeat_seconds: float = 5.0,
    ) -> None:
        self._app_version = app_version
        self._status_file = status_file or _STATUS_FILE
        self._control_file = control_file or _CONTROL_FILE
        self._heartbeat = heartbeat_seconds
        self._last_key: tuple[str, str, bool] | None = None
        self._last_write = 0.0
        self._last_status: BridgeStatus | None = None

    def publish(self, status: BridgeStatus, *, now: float | None = None) -> bool:
        """Schreibt den Status, wenn er sich geaendert hat oder der Takt faellig ist.

        Returns True, wenn geschrieben wurde.
        """
        moment = time.time() if now is None else now
        due = moment - self._last_write >= self._heartbeat
        if status.change_key() == self._last_key and not due:
            return False
        if not self._write(status, moment):
            return False
        self._last_key = status.change_key()
        self._last_write = moment
        self._last_status = status
        return True

    def shutdown(self, *, now: float | None = None) -> None:
        """Letzter Stand beim Beenden: der Titel bleibt, ``running`` wird false."""
        last = self._last_status
        if last is None:
            return
        stopped = BridgeStatus(
            state="stopped",
            title=last.title,
            artist=last.artist,
            album=last.album,
            display_name=last.display_name,
            position_seconds=last.position_seconds,
            duration_seconds=last.duration_seconds,
            running=False,
        )
        self._write(stopped, time.time() if now is None else now)

    def take_command(self) -> str | None:
        """Liest und loescht die Steuer-Datei. Unbekannte Befehle werden geloggt und verworfen."""
        if not self._control_file.is_file():
            return None
        try:
            text = self._control_file.read_text(encoding="utf-8")
            self._control_file.unlink()
        except OSError:
            logger.debug("Steuer-Datei nicht lesbar", exc_info=True)
            return None
        command = parse_command(text)
        if command is None:
            logger.info("Unbekannter Befehl in %s verworfen: %r", self._control_file, text[:40])
        return command

    def _write(self, status: BridgeStatus, moment: float) -> bool:
        """Schreibt ueber eine Temp-Datei, damit ein Leser nie halbes JSON sieht."""
        payload = status.to_json(app_version=self._app_version, pid=os.getpid(), updated=moment)
        temp = self._status_file.with_name(f"{self._status_file.name}.tmp")
        try:
            self._status_file.parent.mkdir(parents=True, exist_ok=True)
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp, self._status_file)
        except OSError:
            # Unter Windows scheitert replace, solange ein Leser die Datei offen hat -
            # der naechste Takt versucht es wieder.
            logger.debug("Status-Datei nicht geschrieben", exc_info=True)
            with contextlib.suppress(OSError):
                temp.unlink()
            return False
        return True
