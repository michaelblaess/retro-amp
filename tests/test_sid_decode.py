"""Tests fuer die SID-Dekodierung per sidplayfp (ohne echtes sidplayfp)."""

from __future__ import annotations

import subprocess
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
