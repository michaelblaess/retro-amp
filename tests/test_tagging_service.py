"""Tests fuer TaggingService (Stufe 1: eingebettete Titel-Tags)."""

from __future__ import annotations

from pathlib import Path

from retro_amp.domain.models import AudioTrack, MatchSource
from retro_amp.services.tagging_service import TaggingService, sanitize_filename


class FakeTagIO:
    """In-Memory TagIO fuer Tests (implementiert das Protocol)."""

    def __init__(
        self,
        titles: dict[Path, str] | None = None,
        numbers: dict[Path, int] | None = None,
        artists: dict[Path, str] | None = None,
        albums: dict[Path, str] | None = None,
    ) -> None:
        self.titles = titles or {}
        self.numbers = numbers or {}
        self.artists = artists or {}
        self.albums = albums or {}
        self.written: dict[Path, str] = {}

    def read_embedded_title(self, path: Path) -> str:
        return self.titles.get(path, "")

    def read_embedded_artist(self, path: Path) -> str:
        return self.artists.get(path, "")

    def read_embedded_album(self, path: Path) -> str:
        return self.albums.get(path, "")

    def read_track_number(self, path: Path) -> int:
        return self.numbers.get(path, 0)

    def write_title(self, path: Path, title: str) -> None:
        self.written[path] = title


class FakeAlbumLookup:
    """In-Memory AlbumTitleLookup fuer Tests."""

    def __init__(self, titles: list[str] | None) -> None:
        self._titles = titles
        self.calls: list[tuple[str, str, int]] = []

    def lookup_tracklist(
        self,
        artist: str,
        album: str,
        track_count: int,
        durations: list[float] | None = None,
    ) -> list[str] | None:
        self.calls.append((artist, album, track_count))
        return self._titles


class FakeTrackLookup:
    """In-Memory TrackTitleLookup (AcoustID) fuer Tests."""

    def __init__(self, titles: dict[Path, str] | None = None, available: bool = True) -> None:
        self._titles = titles or {}
        self._available = available
        self.calls: list[Path] = []

    def available(self) -> bool:
        return self._available

    def lookup_title(self, path: Path, duration_seconds: float) -> str | None:
        self.calls.append(path)
        return self._titles.get(path)


def _track(path: str) -> AudioTrack:
    return AudioTrack(path=Path(path))


class TestSanitizeFilename:
    def test_removes_forbidden_chars(self) -> None:
        assert sanitize_filename("AC/DC: Live?") == "AC DC Live"

    def test_collapses_whitespace(self) -> None:
        assert sanitize_filename("  A   B  ") == "A B"

    def test_empty_falls_back(self) -> None:
        assert sanitize_filename("///") == "Unbenannt"


class TestBuildProposals:
    def test_proposal_from_embedded_title(self) -> None:
        path = Path("/music/album/01.mp3")
        tag_io = FakeTagIO(titles={path: "Zeitmaschine"}, numbers={path: 1})
        service = TaggingService(tag_io)

        proposals = service.build_proposals([_track(str(path))])

        assert len(proposals) == 1
        prop = proposals[0]
        assert prop.has_match
        assert prop.source is MatchSource.ID3
        assert prop.selected is True
        assert prop.title == "Zeitmaschine"
        assert prop.proposed_name == "01 - Zeitmaschine.mp3"

    def test_no_tag_no_match(self) -> None:
        path = Path("/music/album/01.mp3")
        service = TaggingService(FakeTagIO())

        prop = service.build_proposals([_track(str(path))])[0]

        assert not prop.has_match
        assert prop.proposed_name == ""
        assert prop.source is MatchSource.NONE

    def test_title_already_in_filename_is_skipped(self) -> None:
        path = Path("/music/album/01 - Zeitmaschine.mp3")
        tag_io = FakeTagIO(titles={path: "Zeitmaschine"}, numbers={path: 1})
        service = TaggingService(tag_io)

        prop = service.build_proposals([_track(str(path))])[0]

        assert not prop.has_match

    def test_track_number_from_filename(self) -> None:
        path = Path("/music/album/Track 07.mp3")
        tag_io = FakeTagIO(titles={path: "Cello"})  # keine Tracknummer im Tag
        service = TaggingService(tag_io)

        prop = service.build_proposals([_track(str(path))])[0]

        assert prop.proposed_name == "07 - Cello.mp3"

    def test_track_number_from_position_when_unknown(self) -> None:
        # Ziffernlose Stems: keine Nummer aus Tag/Dateiname ableitbar.
        stems = ["alpha", "beta", "gamma"]
        names = ["Lied Eins", "Lied Zwei", "Lied Drei"]  # echte, nicht-generische Titel
        paths = [Path(f"/music/album/{stem}.mp3") for stem in stems]
        tag_io = FakeTagIO(titles=dict(zip(paths, names, strict=True)))
        service = TaggingService(tag_io)

        proposals = service.build_proposals([_track(str(p)) for p in paths])

        # Fallback: 1-basierte Position, auf 2 Stellen aufgefuellt.
        assert proposals[0].proposed_name == "01 - Lied Eins.mp3"
        assert proposals[2].proposed_name == "03 - Lied Drei.mp3"


class TestMusicBrainzFill:
    def _paths(self) -> list[Path]:
        base = "/music/Franco Micalizzi/Lo Chiamavano Trinita (Die rechte Hand, 1969)"
        return [Path(f"{base}/0{i}.mp3") for i in range(1, 4)]

    def test_fills_open_tracks_not_preselected(self) -> None:
        paths = self._paths()
        lookup = FakeAlbumLookup(["Titolo Uno", "Titolo Due", "Titolo Tre"])
        service = TaggingService(FakeTagIO(), lookup)

        proposals = service.build_proposals(
            [_track(str(p)) for p in paths],
            enable_musicbrainz=True,
        )

        assert [p.source for p in proposals] == [MatchSource.MUSICBRAINZ] * 3
        assert all(not p.selected for p in proposals)  # heuristisch -> nicht vorausgewaehlt
        assert proposals[0].proposed_name == "01 - Titolo Uno.mp3"
        # Artist/Album aus den Ordnernamen geparst
        assert lookup.calls == [("Franco Micalizzi", "Lo Chiamavano Trinita", 3)]

    def test_disabled_does_not_call_lookup(self) -> None:
        paths = self._paths()
        lookup = FakeAlbumLookup(["A", "B", "C"])
        service = TaggingService(FakeTagIO(), lookup)

        proposals = service.build_proposals([_track(str(p)) for p in paths])

        assert lookup.calls == []
        assert all(not p.has_match for p in proposals)

    def test_embedded_title_wins_over_musicbrainz(self) -> None:
        paths = self._paths()
        # Track 2 hat einen echten Titel-Tag -> Tier 0 bleibt, MB fuellt nur 1+3.
        tag_io = FakeTagIO(titles={paths[1]: "Echt Getaggt"})
        lookup = FakeAlbumLookup(["MB Eins", "MB Zwei", "MB Drei"])
        service = TaggingService(tag_io, lookup)

        proposals = service.build_proposals(
            [_track(str(p)) for p in paths],
            enable_musicbrainz=True,
        )

        assert proposals[1].source is MatchSource.ID3
        assert proposals[1].title == "Echt Getaggt"
        assert proposals[0].source is MatchSource.MUSICBRAINZ
        assert proposals[2].title == "MB Drei"

    def test_lookup_none_leaves_no_match(self) -> None:
        paths = self._paths()
        service = TaggingService(FakeTagIO(), FakeAlbumLookup(None))

        proposals = service.build_proposals(
            [_track(str(p)) for p in paths],
            enable_musicbrainz=True,
        )

        assert all(not p.has_match for p in proposals)


class TestAcoustIDFill:
    def _paths(self) -> list[Path]:
        return [Path(f"/music/album/0{i}.mp3") for i in range(1, 4)]

    def test_fills_open_tracks_preselected(self) -> None:
        paths = self._paths()
        lookup = FakeTrackLookup({p: f"Fingerprint {i}" for i, p in enumerate(paths)})
        service = TaggingService(FakeTagIO(), track_lookup=lookup)

        proposals = service.build_proposals(
            [_track(str(p)) for p in paths],
            enable_acoustid=True,
        )

        assert [p.source for p in proposals] == [MatchSource.ACOUSTID] * 3
        assert all(p.selected for p in proposals)  # bestaetigt -> vorausgewaehlt
        assert proposals[0].proposed_name == "01 - Fingerprint 0.mp3"

    def test_acoustid_wins_over_musicbrainz(self) -> None:
        paths = self._paths()
        # AcoustID trifft nur Track 1; MB fuellt den Rest.
        track_lookup = FakeTrackLookup({paths[0]: "AID Titel"})
        album_lookup = FakeAlbumLookup(["MB Eins", "MB Zwei", "MB Drei"])
        service = TaggingService(FakeTagIO(), album_lookup, track_lookup)

        proposals = service.build_proposals(
            [_track(str(p)) for p in paths],
            enable_acoustid=True,
            enable_musicbrainz=True,
        )

        assert proposals[0].source is MatchSource.ACOUSTID
        assert proposals[0].title == "AID Titel"
        assert proposals[0].selected is True
        assert proposals[1].source is MatchSource.MUSICBRAINZ
        assert proposals[1].selected is False

    def test_unavailable_skips_lookup(self) -> None:
        paths = self._paths()
        lookup = FakeTrackLookup(dict.fromkeys(paths, "X"), available=False)
        service = TaggingService(FakeTagIO(), track_lookup=lookup)

        proposals = service.build_proposals(
            [_track(str(p)) for p in paths],
            enable_acoustid=True,
        )

        assert lookup.calls == []
        assert all(not p.has_match for p in proposals)


class TestGenericTagAndFilenameFallback:
    _PATH = Path("/music/Udo/Ball Pompös (1974)/01 Jonny Controletti.mp3")

    def test_generic_tag_ignored(self) -> None:
        # Tag "Track 01" ist generisch -> kein Tier-0-Rename.
        tag_io = FakeTagIO(titles={self._PATH: "Track 01"})
        prop = TaggingService(tag_io).build_proposals([_track(str(self._PATH))])[0]
        assert not prop.has_match

    def test_filename_fallback_tag_only(self) -> None:
        tag_io = FakeTagIO(titles={self._PATH: "Track 01"})  # generisch
        prop = TaggingService(tag_io).build_proposals(
            [_track(str(self._PATH))],
            enable_filename_fallback=True,
        )[0]
        assert prop.has_match
        assert prop.source is MatchSource.FILENAME
        assert prop.title == "Jonny Controletti"
        assert prop.renames is False  # nur Tag setzen
        assert prop.proposed_name == ""
        assert prop.selected is False

    def test_filename_fallback_needs_real_title(self) -> None:
        path = Path("/music/album/01.mp3")  # nur Nummer -> kein Titel ableitbar
        prop = TaggingService(FakeTagIO()).build_proposals(
            [_track(str(path))],
            enable_filename_fallback=True,
        )[0]
        assert not prop.has_match

    def test_musicbrainz_tag_only_when_title_in_filename(self) -> None:
        lookup = FakeAlbumLookup(["Jonny Controletti"])
        prop = TaggingService(FakeTagIO(), lookup).build_proposals(
            [_track(str(self._PATH))],
            enable_musicbrainz=True,
        )[0]
        assert prop.source is MatchSource.MUSICBRAINZ
        assert prop.renames is False  # Titel schon im Dateinamen -> nur Tag
        assert prop.title == "Jonny Controletti"
