"""Erkennung von Cloud-Platzhaltern und die Meldung beim Abspielen."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pygame
import pytest

from retro_amp.i18n import load_locale
from retro_amp.infrastructure import audio_player as player_modul
from retro_amp.infrastructure.cloud_files import is_cloud_placeholder

_RECALL_ON_DATA_ACCESS = 0x400000
_ARCHIVE = 0x20


def _stat_mit(monkeypatch: pytest.MonkeyPatch, attribute: int) -> None:
    monkeypatch.setattr(os, "stat", lambda _p: SimpleNamespace(st_file_attributes=attribute))


class TestIsCloudPlaceholder:
    def test_nur_online(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stat_mit(monkeypatch, _ARCHIVE | _RECALL_ON_DATA_ACCESS)
        assert is_cloud_placeholder(Path("x.mp3"))

    def test_lokal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stat_mit(monkeypatch, _ARCHIVE)
        assert not is_cloud_placeholder(Path("x.mp3"))

    def test_ohne_attribute_ausserhalb_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(os, "stat", lambda _p: SimpleNamespace())
        assert not is_cloud_placeholder(Path("x.mp3"))

    def test_fehlende_datei(self, tmp_path: Path) -> None:
        assert not is_cloud_placeholder(tmp_path / "gibt-es-nicht.mp3")

    def test_echte_lokale_datei(self, tmp_path: Path) -> None:
        datei = tmp_path / "a.mp3"
        datei.write_bytes(b"x")
        assert os.path.exists(datei)
        assert not is_cloud_placeholder(datei)


class TestPlayerMeldung:
    """pygame meldet "corrupt mp3" - bei einem Platzhalter muss die echte Ursache kommen."""

    def _player(self, monkeypatch: pytest.MonkeyPatch, platzhalter: bool) -> player_modul.PygameAudioPlayer:
        def laden(_pfad: str) -> None:
            raise pygame.error("music_drmp3: corrupt mp3 file (bad tags).")

        monkeypatch.setattr(pygame.mixer.music, "load", laden)
        monkeypatch.setattr(player_modul, "is_cloud_placeholder", lambda _p: platzhalter)
        player = player_modul.PygameAudioPlayer.__new__(player_modul.PygameAudioPlayer)
        player._initialized = True
        return player

    def test_platzhalter_nennt_die_cloud(self, monkeypatch: pytest.MonkeyPatch) -> None:
        load_locale("de")
        player = self._player(monkeypatch, platzhalter=True)
        with pytest.raises(RuntimeError) as fehler:
            player.play(Path("01-Azimut.mp3"))
        assert "01-Azimut.mp3" in str(fehler.value)
        assert "Cloud" in str(fehler.value)
        assert "corrupt" not in str(fehler.value)

    def test_echte_kaputte_datei_behaelt_meldung(self, monkeypatch: pytest.MonkeyPatch) -> None:
        player = self._player(monkeypatch, platzhalter=False)
        with pytest.raises(RuntimeError, match="corrupt mp3"):
            player.play(Path("kaputt.mp3"))
