"""Wiedergabe aus den Favoriten laeuft in den Favoriten weiter.

Vorher uebernahm der Ordner des gewaehlten Titels die Abspiel-Reihenfolge:
nach einem Favoriten kam der naechste Titel aus dessen Album statt der
naechste Favorit.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.pilot import Pilot

from retro_amp.app import RetroAmpApp
from retro_amp.domain.models import PlaybackState
from retro_amp.widgets.favorites_tree import FavoritesTree

from .conftest import MockAudioPlayer


@pytest.fixture
def musik(isolierte_ablage: Path) -> Path:
    """Zwei Alben mit je zwei Titeln, je einer davon wird Favorit."""
    wurzel = isolierte_ablage.parent / "Musik"
    for name in ("Alben/a-favorit.mp3", "Alben/b-album.mp3", "Singles/c-favorit.mp3", "Singles/d-album.mp3"):
        (wurzel / name).write_bytes(b"")
    return wurzel


async def _starte_favorit(anwendung: RetroAmpApp, pilot: Pilot[None], favoriten: list[Path], start: Path) -> None:
    """Traegt Favoriten ein und waehlt einen davon im Favoriten-Baum."""
    anwendung._player_service._player = MockAudioPlayer()
    # Lyrics, Cover und Begleittext gingen sonst ins Netz
    anwendung._load_tabs_for_track = lambda track: None  # type: ignore[method-assign]
    for pfad in favoriten:
        anwendung._playlist_service.add_to_favorites(pfad)
    anwendung._refresh_favorites_tree()
    baum = anwendung.query_one("#favorites-tree", FavoritesTree)
    baum.post_message(FavoritesTree.TrackSelected(start))
    await _setzen_lassen(anwendung, pilot)


async def _setzen_lassen(anwendung: RetroAmpApp, pilot: Pilot[None]) -> None:
    """Wartet, bis der Ordner-Scan durch ist - erst er kippte frueher die Reihenfolge.

    Nicht ``workers.wait_for_complete()``: der Lader des Ordner-Baums ist ein
    Worker, der nie endet.
    """
    for _ in range(300):
        await pilot.pause(0.01)
        if not any(worker.group == "scan" and not worker.is_finished for worker in anwendung.workers):
            # Das Ergebnis kommt per call_from_thread - noch einmal Luft holen
            await pilot.pause(0.05)
            return
    raise AssertionError("Ordner-Scan wurde nicht fertig")


async def _titel_zu_ende(anwendung: RetroAmpApp, pilot: Pilot[None]) -> None:
    """Meldet das Ende des laufenden Titels, wie es der Positions-Timer tut."""
    anwendung._player_service.state.state = PlaybackState.STOPPED
    anwendung._on_track_finished()
    await _setzen_lassen(anwendung, pilot)


def _laeuft(anwendung: RetroAmpApp) -> str | None:
    titel = anwendung._player_service.state.current_track
    return titel.path.name if titel else None


class TestFavoritenReihenfolge:
    async def test_nach_einem_favoriten_kommt_der_naechste_favorit(self, musik: Path) -> None:
        erster = musik / "Alben" / "a-favorit.mp3"
        zweiter = musik / "Singles" / "c-favorit.mp3"
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            await _starte_favorit(anwendung, pilot, [erster, zweiter], erster)
            assert _laeuft(anwendung) == "a-favorit.mp3"

            await _titel_zu_ende(anwendung, pilot)

            # Nicht b-album.mp3 aus demselben Ordner
            assert _laeuft(anwendung) == "c-favorit.mp3"
            assert anwendung._player_service.state.is_playing

    async def test_cursor_im_favoriten_baum_wandert_mit(self, musik: Path) -> None:
        """Sonst bleibt die Markierung auf dem Titel stehen, der angeklickt wurde."""
        erster = musik / "Alben" / "a-favorit.mp3"
        zweiter = musik / "Singles" / "c-favorit.mp3"
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            await _starte_favorit(anwendung, pilot, [erster, zweiter], erster)
            baum = anwendung.query_one("#favorites-tree", FavoritesTree)
            assert baum.cursor_node is not None and baum.cursor_node.data == erster

            await _titel_zu_ende(anwendung, pilot)

            assert baum.cursor_node is not None and baum.cursor_node.data == zweiter

    async def test_cursor_bleibt_nach_neuladen_auf_dem_laufenden_titel(self, musik: Path) -> None:
        erster = musik / "Alben" / "a-favorit.mp3"
        zweiter = musik / "Singles" / "c-favorit.mp3"
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            await _starte_favorit(anwendung, pilot, [erster, zweiter], zweiter)
            baum = anwendung.query_one("#favorites-tree", FavoritesTree)

            anwendung._refresh_favorites_tree()
            await pilot.pause()

            assert baum.cursor_node is not None and baum.cursor_node.data == zweiter

    async def test_am_ende_der_favoriten_ist_schluss(self, musik: Path) -> None:
        erster = musik / "Alben" / "a-favorit.mp3"
        zweiter = musik / "Singles" / "c-favorit.mp3"
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            await _starte_favorit(anwendung, pilot, [erster, zweiter], zweiter)

            await _titel_zu_ende(anwendung, pilot)

            # Nicht d-album.mp3, der im Ordner auf den letzten Favoriten folgt
            assert _laeuft(anwendung) == "c-favorit.mp3"
            assert anwendung._player_service.state.is_stopped

    async def test_tasten_weiter_und_zurueck_bleiben_in_den_favoriten(self, musik: Path) -> None:
        erster = musik / "Alben" / "a-favorit.mp3"
        zweiter = musik / "Singles" / "c-favorit.mp3"
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            await _starte_favorit(anwendung, pilot, [erster, zweiter], erster)

            anwendung.action_next_track()
            await _setzen_lassen(anwendung, pilot)
            assert _laeuft(anwendung) == "c-favorit.mp3"

            anwendung.action_previous_track()
            await _setzen_lassen(anwendung, pilot)
            assert _laeuft(anwendung) == "a-favorit.mp3"

    async def test_entfernter_favorit_kommt_nicht_mehr_dran(self, musik: Path) -> None:
        erster = musik / "Alben" / "a-favorit.mp3"
        mitte = musik / "Alben" / "b-album.mp3"
        letzter = musik / "Singles" / "c-favorit.mp3"
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            await _starte_favorit(anwendung, pilot, [erster, mitte, letzter], erster)
            anwendung._remove_favorite(mitte)

            await _titel_zu_ende(anwendung, pilot)

            assert _laeuft(anwendung) == "c-favorit.mp3"

    async def test_start_aus_der_datei_tabelle_beendet_die_favoriten(self, musik: Path) -> None:
        """Wer danach im Album etwas anwaehlt, will im Album weiterhoeren."""
        favorit = musik / "Singles" / "c-favorit.mp3"
        weiterer = musik / "Alben" / "a-favorit.mp3"
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            await _starte_favorit(anwendung, pilot, [weiterer, favorit], weiterer)
            album = {titel.path.name: titel for titel in anwendung._current_tracks}
            assert set(album) == {"a-favorit.mp3", "b-album.mp3"}

            # Derselbe Titel waere binnen 2 s ein Dedup - also den anderen waehlen
            anwendung._play_track(album["b-album.mp3"])
            await _setzen_lassen(anwendung, pilot)
            anwendung._play_track(album["a-favorit.mp3"])
            await _setzen_lassen(anwendung, pilot)

            await _titel_zu_ende(anwendung, pilot)

            assert _laeuft(anwendung) == "b-album.mp3"
