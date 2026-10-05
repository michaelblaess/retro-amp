"""Tests fuer die SID-Dekodierung per sidplayfp (ohne echtes sidplayfp)."""

from __future__ import annotations

import io
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from retro_amp.infrastructure import audio_player


def _fake_run(schreibt: bytes | None) -> Any:
    """Ersetzt subprocess.run: legt die Datei aus dem -w-Argument an, wie sidplayfp."""

    def run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        ziel = next(a[2:] for a in args if a.startswith("-w"))
        if schreibt is not None:
            Path(ziel).write_bytes(schreibt)
        return subprocess.CompletedProcess(args, 0, stdout=b"SIDPLAYFP Konsole", stderr=b"")

    return run


def test_sid_wird_in_eine_datei_dekodiert(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """sidplayfp schreibt nicht nach stdout, gelesen wird die WAV-Datei aus -w<datei>."""
    wav = b"RIFF" + b"\0" * 60
    aufrufe: list[list[str]] = []
    echt = _fake_run(wav)

    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        aufrufe.append(args)
        return echt(args, **kwargs)

    monkeypatch.setattr(audio_player, "_find_sidplayfp", lambda: "sidplayfp")
    monkeypatch.setattr(audio_player.subprocess, "run", run)

    ergebnis = audio_player._decode_sid_to_wav(tmp_path / "tune.sid", duration=5)

    assert ergebnis is not None
    assert ergebnis.getvalue() == wav
    assert not any(a.startswith("--wav=") for a in aufrufe[0])


def test_ohne_wav_datei_kein_ergebnis(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Legt sidplayfp keine Datei an, kommt None zurueck statt der Konsolenausgabe."""
    monkeypatch.setattr(audio_player, "_find_sidplayfp", lambda: "sidplayfp")
    monkeypatch.setattr(audio_player.subprocess, "run", _fake_run(None))

    assert audio_player._decode_sid_to_wav(tmp_path / "tune.sid", duration=5) is None


class _FakeMusic:
    """Ersetzt pygame.mixer.music und protokolliert die Aufrufe."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.busy = False
        self.pos_ms = 0

    def load(self, source: object) -> None:
        self.calls.append(("load", source))

    def play(self, start: float = 0.0) -> None:
        self.calls.append(("play", start))
        self.busy = True

    def pause(self) -> None:
        self.calls.append(("pause", None))

    def stop(self) -> None:
        self.calls.append(("stop", None))
        self.busy = False

    def get_busy(self) -> bool:
        return self.busy

    def get_pos(self) -> int:
        return self.pos_ms if self.busy else -1


class TestZweistufigerSidStart:
    """Erst ein kurzer Anfang, die volle Laenge kommt im Hintergrund nach."""

    @pytest.fixture
    def umgebung(self, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, _FakeMusic, dict[int, threading.Event]]:
        music = _FakeMusic()
        monkeypatch.setattr(audio_player.pygame.mixer, "music", music)
        freigabe: dict[int, threading.Event] = {}

        def dekodieren(path: Path, duration: int = 180) -> io.BytesIO:
            # Die volle Fassung wartet, bis der Test sie freigibt
            if duration == audio_player._SID_FULL_SECONDS:
                freigabe.setdefault(duration, threading.Event()).wait(5)
            return io.BytesIO(f"{path.name}:{duration}".encode())

        monkeypatch.setattr(audio_player, "_decode_sid_to_wav", dekodieren)
        player = audio_player.PygameAudioPlayer.__new__(audio_player.PygameAudioPlayer)
        player._initialized = True
        player._seek_offset = 0.0
        player._sid_lock = threading.Lock()
        freigabe[audio_player._SID_FULL_SECONDS] = threading.Event()
        return player, music, freigabe

    @staticmethod
    def _geladen(music: _FakeMusic) -> list[bytes]:
        return [src.getvalue() for name, src in music.calls if name == "load" and isinstance(src, io.BytesIO)]

    @staticmethod
    def _warten_bis(bedingung: Any) -> None:
        for _ in range(200):
            if bedingung():
                return
            time.sleep(0.01)
        raise AssertionError("Bedingung nicht erreicht")

    def test_anfang_zuerst_dann_volle_fassung_an_der_stelle(self, umgebung: Any) -> None:
        player, music, freigabe = umgebung
        player.play(Path("tune.sid"))

        assert self._geladen(music) == [f"tune.sid:{audio_player._SID_PREVIEW_SECONDS}".encode()]
        assert player.is_busy()

        music.pos_ms = 4200
        freigabe[audio_player._SID_FULL_SECONDS].set()
        self._warten_bis(lambda: len(self._geladen(music)) == 2)

        assert self._geladen(music)[1] == f"tune.sid:{audio_player._SID_FULL_SECONDS}".encode()
        assert music.calls[-1] == ("play", pytest.approx(4.2))
        assert player._seek_offset == pytest.approx(4.2)

    def test_neuer_titel_verwirft_den_wechsel(self, umgebung: Any) -> None:
        player, music, freigabe = umgebung
        player.play(Path("alt.sid"))
        player.stop()
        freigabe[audio_player._SID_FULL_SECONDS].set()
        time.sleep(0.2)

        assert all(src != b"alt.sid:180" for src in self._geladen(music))
        assert not player._sid_pending

    def test_ausgelaufener_anfang_gilt_nicht_als_ende(self, umgebung: Any) -> None:
        player, music, freigabe = umgebung
        player.play(Path("tune.sid"))
        music.busy = False  # Anfang ist ausgelaufen, volle Fassung fehlt noch

        assert player.is_busy()

        freigabe[audio_player._SID_FULL_SECONDS].set()
        self._warten_bis(lambda: len(self._geladen(music)) == 2)
        assert music.calls[-1] == ("play", float(audio_player._SID_PREVIEW_SECONDS))
