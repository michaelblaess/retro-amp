"""Wiedergabe aus Favoriten und Playlists laeuft in der jeweiligen Liste weiter.

Vorher uebernahm der Ordner des gewaehlten Titels die Abspiel-Reihenfolge:
nach einem Favoriten kam der naechste Titel aus dessen Album statt der
naechste Favorit. Fuer Playlists galt dasselbe.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.pilot import Pilot

from retro_amp.app import RetroAmpApp
from retro_amp.domain.models import AudioTrack, PlaybackState
from retro_amp.i18n import t
from retro_amp.widgets.favorites_tree import FavoritesTree
from retro_amp.widgets.file_table import FileTable
from retro_amp.widgets.playlist_tree import PlaylistTree
from retro_amp.widgets.transport_bar import TransportBar

from .conftest import MockAudioPlayer


@pytest.fixture
def musik(isolierte_ablage: Path) -> Path:
    """Zwei Alben mit je zwei Titeln, je einer davon wird Favorit."""
    wurzel = isolierte_ablage.parent / "Musik"
    for name in ("Alben/a-favorit.mp3", "Alben/b-album.mp3", "Singles/c-favorit.mp3", "Singles/d-album.mp3"):
        (wurzel / name).write_bytes(b"")
    return wurzel


SCANS: list[str] = []
"""Mitschnitt der angewandten Ordner-Scans des laufenden Tests, fuer die Fehlermeldung."""


def _vorbereiten(anwendung: RetroAmpApp) -> None:
    """Macht die App testbar: kein Ton, kein Netz, und die Scans werden mitgeschrieben."""
    anwendung._player_service._player = MockAudioPlayer()
    # Lyrics, Cover und Begleittext gingen sonst ins Netz
    anwendung._load_tabs_for_track = lambda track: None  # type: ignore[method-assign]

    SCANS.clear()
    original = anwendung._apply_scan_result

    def mitschreiben(tracks: list[AudioTrack], directory: Path) -> None:
        SCANS.append(f"{directory.name}:{len(tracks)}")
        original(tracks, directory)

    anwendung._apply_scan_result = mitschreiben  # type: ignore[method-assign]


def _lage(anwendung: RetroAmpApp) -> str:
    """Zustand der App in einer Zeile - steht in jeder Fehlermeldung dieser Datei."""
    titel = anwendung._player_service.state.current_track
    tabelle = anwendung.query_one("#file-table", FileTable)
    arbeiter = [f"{w.name}/{w.group}/{w.state.name}" for w in anwendung.workers if w.group == "scan"]
    return (
        f"laeuft={titel.path.name if titel else None} "
        f"tabelle={tabelle._current_path.name if tabelle._current_path else None} "
        f"titel_in_tabelle={[t_.path.name for t_ in anwendung._current_tracks]} "
        f"scans={SCANS} arbeiter={arbeiter}"
    )


async def _starte_favorit(anwendung: RetroAmpApp, pilot: Pilot[None], favoriten: list[Path], start: Path) -> None:
    """Traegt Favoriten ein und waehlt einen davon im Favoriten-Baum."""
    _vorbereiten(anwendung)
    for pfad in favoriten:
        anwendung._playlist_service.add_to_favorites(pfad)
    anwendung._refresh_favorites_tree()
    baum = anwendung.query_one("#favorites-tree", FavoritesTree)
    baum.post_message(FavoritesTree.TrackSelected(start))
    await _setzen_lassen(anwendung, pilot, laeuft=start)


async def _setzen_lassen(anwendung: RetroAmpApp, pilot: Pilot[None], laeuft: Path | None = None) -> None:
    """Wartet, bis Wiedergabe und Ordner-Scan angekommen sind.

    Der Scan laeuft in einem Thread und kippte frueher die Reihenfolge - erst
    danach sagt ein Test etwas aus. Gewartet wird auf einen Zustand, nicht auf
    eine Zeitspanne: die Datei-Tabelle zeigt den Ordner des laufenden Titels,
    und kein Scan laeuft mehr. ``laeuft`` nennt den erwarteten Titel, wenn der
    Start ueber eine Message kommt und deshalb noch gar nicht verarbeitet ist.
    Ohne das kehrte die Hilfe auf dem Windows-Runner zurueck, bevor der Scan
    ueberhaupt begonnen hatte.

    Nicht ``workers.wait_for_complete()``: der Lader des Ordner-Baums ist ein
    Worker, der nie endet.
    """
    tabelle = anwendung.query_one("#file-table", FileTable)
    for _ in range(1000):
        await pilot.pause(0.01)
        titel = anwendung._player_service.state.current_track
        if laeuft is not None and (titel is None or titel.path != laeuft):
            continue
        if any(worker.group == "scan" and not worker.is_finished for worker in anwendung.workers):
            continue
        if titel is not None and tabelle._current_path != titel.path.parent:
            continue
        return
    raise AssertionError(f"Wiedergabe oder Ordner-Scan kamen nicht an: {_lage(anwendung)}")


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
            assert set(album) == {"a-favorit.mp3", "b-album.mp3"}, _lage(anwendung)

            # Derselbe Titel waere binnen 2 s ein Dedup - also den anderen waehlen
            anwendung._play_track(album["b-album.mp3"])
            await _setzen_lassen(anwendung, pilot)
            anwendung._play_track(album["a-favorit.mp3"])
            await _setzen_lassen(anwendung, pilot)

            await _titel_zu_ende(anwendung, pilot)

            assert _laeuft(anwendung) == "b-album.mp3"


def _beschriftungen(baum: FavoritesTree | PlaylistTree) -> dict[str, str]:
    """Dateiname auf das Zeichen, das im Baum davorsteht."""
    return {pfad.name: str(blatt.label)[0] for blatt, pfad in baum.track_leaves()}


class TestLaufenderTitelIstGekennzeichnet:
    async def test_zeichen_steht_am_laufenden_titel_und_wandert_mit(self, musik: Path) -> None:
        erster = musik / "Alben" / "a-favorit.mp3"
        zweiter = musik / "Singles" / "c-favorit.mp3"
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            await _starte_favorit(anwendung, pilot, [erster, zweiter], erster)
            baum = anwendung.query_one("#favorites-tree", FavoritesTree)
            assert _beschriftungen(baum) == {"a-favorit.mp3": "▶", "c-favorit.mp3": "♪"}

            await _titel_zu_ende(anwendung, pilot)

            assert _beschriftungen(baum) == {"a-favorit.mp3": "♪", "c-favorit.mp3": "▶"}

    async def test_zeichen_ueberlebt_das_neuladen(self, musik: Path) -> None:
        erster = musik / "Alben" / "a-favorit.mp3"
        zweiter = musik / "Singles" / "c-favorit.mp3"
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            await _starte_favorit(anwendung, pilot, [erster, zweiter], zweiter)
            baum = anwendung.query_one("#favorites-tree", FavoritesTree)

            anwendung._refresh_favorites_tree()
            await pilot.pause()

            assert _beschriftungen(baum) == {"a-favorit.mp3": "♪", "c-favorit.mp3": "▶"}


class TestFavoritenGruppeAbspielen:
    """ "Abspielen" im Kontextmenue der Wurzel und einer Gruppe."""

    async def _menue_abspielen(self, anwendung: RetroAmpApp, pilot: Pilot[None], gruppe: str | None) -> None:
        baum = anwendung.query_one("#favorites-tree", FavoritesTree)
        knoten = baum.root if gruppe is None else next(k for k in baum.root.children if gruppe in str(k.label))
        # So hinterlaesst es der Rechtsklick: Knoten gemerkt, kein Pfad
        baum._menu_node = knoten
        anwendung._list_menu_path = None
        anwendung._on_favorites_menu_action("play")
        await _setzen_lassen(anwendung, pilot)

    async def test_gruppe_spielt_nur_ihren_ordner(self, musik: Path) -> None:
        favoriten = [
            musik / "Alben" / "a-favorit.mp3",
            musik / "Alben" / "b-album.mp3",
            musik / "Singles" / "c-favorit.mp3",
        ]
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            await _starte_favorit(anwendung, pilot, favoriten, favoriten[2])

            await self._menue_abspielen(anwendung, pilot, "Alben")
            assert _laeuft(anwendung) == "a-favorit.mp3"

            await _titel_zu_ende(anwendung, pilot)
            assert _laeuft(anwendung) == "b-album.mp3"

            # Die Gruppe ist zu Ende - c-favorit.mp3 aus der naechsten Gruppe kommt nicht
            await _titel_zu_ende(anwendung, pilot)
            assert _laeuft(anwendung) == "b-album.mp3"
            assert anwendung._player_service.state.is_stopped

    async def test_wurzel_spielt_alle_von_oben(self, musik: Path) -> None:
        favoriten = [musik / "Alben" / "a-favorit.mp3", musik / "Singles" / "c-favorit.mp3"]
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            await _starte_favorit(anwendung, pilot, favoriten, favoriten[1])

            await self._menue_abspielen(anwendung, pilot, None)
            assert _laeuft(anwendung) == "a-favorit.mp3"

            await _titel_zu_ende(anwendung, pilot)
            assert _laeuft(anwendung) == "c-favorit.mp3"


class TestPlaylistReihenfolge:
    async def _starte_playlist(
        self,
        anwendung: RetroAmpApp,
        pilot: Pilot[None],
        titel: list[Path],
        name: str = "Abends",
    ) -> PlaylistTree:
        _vorbereiten(anwendung)
        for pfad in titel:
            anwendung._playlist_service.add_to_playlist(name, pfad)
        anwendung._refresh_playlist_tree()
        baum = anwendung.query_one("#playlist-tree", PlaylistTree)
        baum.post_message(PlaylistTree.TrackSelected(titel[0], name))
        await _setzen_lassen(anwendung, pilot, laeuft=titel[0])
        return baum

    async def test_nach_einem_playlist_titel_kommt_der_naechste_der_playlist(self, musik: Path) -> None:
        # Bewusst nicht alphabetisch: die Playlist hat ihre eigene Reihenfolge
        titel = [musik / "Singles" / "c-favorit.mp3", musik / "Alben" / "a-favorit.mp3"]
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            baum = await self._starte_playlist(anwendung, pilot, titel)
            assert _laeuft(anwendung) == "c-favorit.mp3"

            await _titel_zu_ende(anwendung, pilot)

            # Nicht d-album.mp3 aus demselben Ordner
            assert _laeuft(anwendung) == "a-favorit.mp3"
            assert baum.cursor_node is not None and baum.cursor_node.data == titel[1]
            assert _beschriftungen(baum) == {"c-favorit.mp3": "♪", "a-favorit.mp3": "▶"}

    async def test_am_ende_der_playlist_ist_schluss(self, musik: Path) -> None:
        titel = [musik / "Singles" / "c-favorit.mp3"]
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            await self._starte_playlist(anwendung, pilot, titel)

            await _titel_zu_ende(anwendung, pilot)

            assert _laeuft(anwendung) == "c-favorit.mp3"
            assert anwendung._player_service.state.is_stopped


# Bei 200 Spalten ist die Transportleiste breit genug fuer die lange Form,
# bei den ueblichen 80 des Testlaufs nicht einmal fuer die kurze.
BREIT = (200, 40)
MITTEL = (150, 40)


def _leiste(anwendung: RetroAmpApp) -> str:
    """Erste Zeile der Transportleiste als Klartext."""
    return anwendung.query_one("#transport", TransportBar).render().plain.splitlines()[0]


class TestHinweisInDerTransportleiste:
    """Ohne den Hinweis ist nicht zu sehen, warum als Naechstes kein Album-Titel kommt."""

    async def test_favoriten_mit_stelle_in_der_liste(self, musik: Path) -> None:
        favoriten = [musik / "Alben" / "a-favorit.mp3", musik / "Singles" / "c-favorit.mp3"]
        anwendung = RetroAmpApp()
        async with anwendung.run_test(size=BREIT) as pilot:
            await _starte_favorit(anwendung, pilot, favoriten, favoriten[0])
            assert _leiste(anwendung).endswith(f"  {t('favorites.title')} 1/2")

            await _titel_zu_ende(anwendung, pilot)

            assert _leiste(anwendung).endswith(f"  {t('favorites.title')} 2/2")

    async def test_gruppe_traegt_den_ordnernamen(self, musik: Path) -> None:
        favoriten = [
            musik / "Alben" / "a-favorit.mp3",
            musik / "Alben" / "b-album.mp3",
            musik / "Singles" / "c-favorit.mp3",
        ]
        anwendung = RetroAmpApp()
        async with anwendung.run_test(size=BREIT) as pilot:
            await _starte_favorit(anwendung, pilot, favoriten, favoriten[2])
            await TestFavoritenGruppeAbspielen()._menue_abspielen(anwendung, pilot, "Alben")

            assert _leiste(anwendung).endswith("  \u2605 Alben 1/2")

    async def test_playlist_traegt_ihren_namen(self, musik: Path) -> None:
        titel = [musik / "Singles" / "c-favorit.mp3", musik / "Alben" / "a-favorit.mp3"]
        anwendung = RetroAmpApp()
        async with anwendung.run_test(size=BREIT) as pilot:
            await TestPlaylistReihenfolge()._starte_playlist(anwendung, pilot, titel)

            assert _leiste(anwendung).endswith("  \u266b Abends 1/2")

    async def test_kein_hinweis_bei_wiedergabe_aus_dem_ordner(self, musik: Path) -> None:
        favoriten = [musik / "Alben" / "a-favorit.mp3", musik / "Singles" / "c-favorit.mp3"]
        anwendung = RetroAmpApp()
        async with anwendung.run_test(size=BREIT) as pilot:
            await _starte_favorit(anwendung, pilot, favoriten, favoriten[0])
            assert "1/2" in _leiste(anwendung)
            album = {titel.path.name: titel for titel in anwendung._current_tracks}

            anwendung._play_track(album["b-album.mp3"])
            await _setzen_lassen(anwendung, pilot)

            assert _leiste(anwendung).endswith("]")

    async def test_mittlere_breite_zeigt_die_kurzform(self, musik: Path) -> None:
        titel = [musik / "Singles" / "c-favorit.mp3", musik / "Alben" / "a-favorit.mp3"]
        anwendung = RetroAmpApp()
        async with anwendung.run_test(size=MITTEL) as pilot:
            # Ein langer Playlist-Name passt hier nicht mehr neben den Titel
            await TestPlaylistReihenfolge()._starte_playlist(
                anwendung, pilot, titel, name="Abends am Kamin mit Rotwein"
            )

            assert _leiste(anwendung).endswith("  \u266b 1/2")

    async def test_schmales_fenster_laesst_den_hinweis_weg_statt_den_titel(self, musik: Path) -> None:
        favoriten = [musik / "Alben" / "a-favorit.mp3", musik / "Singles" / "c-favorit.mp3"]
        anwendung = RetroAmpApp()
        async with anwendung.run_test(size=(120, 40)) as pilot:
            await _starte_favorit(anwendung, pilot, favoriten, favoriten[0])

            mit_liste = _leiste(anwendung)
            assert anwendung._queue_hint() != ("", "")
            assert "1/2" not in mit_liste

            # Der Titel ist genauso lang wie ohne Liste - der Hinweis nimmt ihm nichts weg
            leiste = anwendung.query_one("#transport", TransportBar)
            leiste.update_state(anwendung._player_service.state)
            assert _leiste(anwendung) == mit_liste

    async def test_hinweis_steht_wirklich_im_bild(self, musik: Path) -> None:
        """``render()`` allein beweist es nicht: eine umbrochene Zeile faellt unten heraus."""
        favoriten = [musik / "Alben" / "a-favorit.mp3", musik / "Singles" / "c-favorit.mp3"]
        anwendung = RetroAmpApp()
        async with anwendung.run_test(size=BREIT) as pilot:
            await _starte_favorit(anwendung, pilot, favoriten, favoriten[0])
            await pilot.pause(0.2)
            leiste = anwendung.query_one("#transport", TransportBar)
            streifen = anwendung.screen._compositor.render_strips()[leiste.region.y]
            zeile = "".join(segment.text for segment in streifen._segments)

            assert f"{t('favorites.title')} 1/2" in zeile
