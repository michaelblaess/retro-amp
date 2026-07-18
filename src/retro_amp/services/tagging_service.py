"""Tagging-Service - baut Titel-Vorschlaege fuer Dateien mit fehlendem Titel.

Tier 0 (``MatchSource.ID3``): eingebetteter Titel-Tag - deterministisch, kein
Raten, vorausgewaehlt.
Tier 3 (``MatchSource.MUSICBRAINZ``): Album-Trackliste per Artist/Album +
Track-Anzahl - heuristisch, hart gegatet, NICHT vorausgewaehlt.
(AcoustID-Fingerprint kommt als weitere bestaetigte Quelle dazu.)

Der Service kennt nur ``domain/`` und delegiert Tag-Lesen/-Schreiben sowie die
Album-Suche an Protocols (DI). Namens- und Sanitize-Logik ist rein und testbar.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from ..domain.models import AudioTrack, MatchSource, TitleProposal
from ..domain.protocols import AlbumTitleLookup, TagIO, TrackTitleLookup

# Unter Windows/POSIX in Dateinamen verbotene Zeichen + Steuerzeichen.
_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
# Fuehrende Zahl im Dateinamen (z.B. "01", "Track 07").
_FILENAME_NUMBER = re.compile(r"\d{1,3}")
# Fuer den "Titel steckt schon im Dateinamen"-Vergleich: nur alphanumerisch.
_ALNUM = re.compile(r"[^a-z0-9]+")
# Abschliessende Klammergruppe im Ordnernamen (z.B. " (1998)", " (..., 1969)").
_TRAILING_PARENS = re.compile(r"\s*\([^()]*\)\s*$")
# Generische Platzhalter-Titel (z.B. "Track 01", "12", "Untitled") - kein echter Titel.
_GENERIC_TITLE = re.compile(
    r"^(?:track|title|titel|spur|untitled|audiotrack|audio track|unknown)\s*\d*$|^\d+$",
    re.IGNORECASE,
)
# Fuehrende Tracknummer im Dateinamen (z.B. "01 ", "01. ", "13 - ", "07_").
_LEADING_TRACKNUM = re.compile(r"^\s*\d{1,3}\s*[.\-_)]?\s+")


def sanitize_filename(title: str) -> str:
    """Macht einen Titel dateisystem-tauglich.

    Ersetzt verbotene Zeichen durch Leerzeichen, normalisiert Whitespace und
    entfernt fuehrende/abschliessende Punkte und Leerzeichen (Windows).
    """
    cleaned = _FORBIDDEN.sub(" ", title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or "Unbenannt"


def _normalize(text: str) -> str:
    """Reduziert einen String auf Kleinbuchstaben + Ziffern (fuer Vergleiche)."""
    return _ALNUM.sub("", text.lower())


class TaggingService:
    """Baut ``TitleProposal``-Objekte fuer eine Liste von Tracks."""

    def __init__(
        self,
        tag_io: TagIO,
        album_lookup: AlbumTitleLookup | None = None,
        track_lookup: TrackTitleLookup | None = None,
    ) -> None:
        self._tag_io = tag_io
        self._album_lookup = album_lookup
        self._track_lookup = track_lookup

    def build_proposals(
        self,
        tracks: list[AudioTrack],
        enable_acoustid: bool = False,
        enable_musicbrainz: bool = False,
        enable_filename_fallback: bool = False,
    ) -> list[TitleProposal]:
        """Erzeugt fuer jeden Track einen Vorschlag (ggf. ohne Treffer).

        Reihenfolge: Tier 0 (eingebetteter Titel) -> AcoustID-Fingerprint
        (bestaetigt) -> MusicBrainz-Trackliste (heuristisch) -> Dateiname-Fallback
        (nur Tag), jeweils nur fuer die noch offenen Tracks.
        """
        total = len(tracks)
        width = max(2, len(str(total))) if total else 2
        proposals = [self._build_tier0(track, index, width) for index, track in enumerate(tracks)]

        if enable_acoustid and self._track_lookup is not None:
            self._fill_from_acoustid(tracks, proposals, width)

        if enable_musicbrainz and self._album_lookup is not None:
            self._fill_from_musicbrainz(tracks, proposals, width)

        if enable_filename_fallback:
            self._fill_from_filename(tracks, proposals)

        return proposals

    def _build_tier0(self, track: AudioTrack, index: int, width: int) -> TitleProposal:
        """Vorschlag aus eingebettetem Titel-Tag (bestaetigt, vorausgewaehlt).

        Ein generischer Platzhalter-Tag ("Track 01") gilt als kein echter Titel
        und wird uebersprungen, damit AcoustID/MusicBrainz den echten Titel
        liefern koennen.
        """
        proposal = TitleProposal(track=track)
        title = self._tag_io.read_embedded_title(track.path)
        if not title or self._is_generic_title(title):
            return proposal
        if _normalize(title) in _normalize(track.path.stem):
            return proposal  # echter Tag steckt schon im Dateinamen -> nichts zu tun
        number = self._track_number(track, index, width)
        proposal.title = title
        proposal.source = MatchSource.ID3
        proposal.selected = True
        proposal.proposed_name = f"{number} - {sanitize_filename(title)}{track.path.suffix}"
        return proposal

    @staticmethod
    def _is_generic_title(title: str) -> bool:
        """True bei Platzhalter-Titeln wie "Track 01", "12", "Untitled"."""
        return bool(_GENERIC_TITLE.match(title.strip()))

    def _apply_found_title(
        self,
        proposal: TitleProposal,
        track: AudioTrack,
        index: int,
        width: int,
        title: str,
        source: MatchSource,
        selected: bool,
    ) -> None:
        """Setzt einen gefundenen Titel als Vorschlag.

        Steckt der Titel schon im Dateinamen, wird NUR der Tag gesetzt
        (``proposed_name`` bleibt leer); sonst wird zusaetzlich umbenannt.
        """
        proposal.title = title
        proposal.source = source
        proposal.selected = selected
        if _normalize(title) in _normalize(track.path.stem):
            proposal.proposed_name = ""  # Dateiname ok -> nur Tag setzen
        else:
            number = self._track_number(track, index, width)
            proposal.proposed_name = f"{number} - {sanitize_filename(title)}{track.path.suffix}"

    def _fill_from_acoustid(
        self,
        tracks: list[AudioTrack],
        proposals: list[TitleProposal],
        width: int,
    ) -> None:
        """Fuellt offene Vorschlaege per AcoustID-Fingerprint (bestaetigt)."""
        if self._track_lookup is None or not self._track_lookup.available():
            return
        for index, proposal in enumerate(proposals):
            if proposal.has_match:
                continue
            track = tracks[index]
            title = self._track_lookup.lookup_title(track.path, track.duration_seconds)
            if title is None or not title.strip():
                continue
            # bestaetigte Quelle -> vorausgewaehlt; Umbenennen nur wenn noetig.
            self._apply_found_title(proposal, track, index, width, title.strip(), MatchSource.ACOUSTID, selected=True)

    def _fill_from_musicbrainz(
        self,
        tracks: list[AudioTrack],
        proposals: list[TitleProposal],
        width: int,
    ) -> None:
        """Fuellt offene Vorschlaege aus der MusicBrainz-Trackliste (heuristisch)."""
        open_indices = [i for i, proposal in enumerate(proposals) if not proposal.has_match]
        if not open_indices or self._album_lookup is None:
            return

        artist, album = self._resolve_artist_album(tracks)
        durations = [track.duration_seconds for track in tracks]
        titles = self._album_lookup.lookup_tracklist(artist, album, len(tracks), durations)
        if titles is None or len(titles) != len(tracks):
            return

        for index in open_indices:
            title = titles[index].strip()
            track = tracks[index]
            if not title:
                continue
            # heuristisch -> nicht vorausgewaehlt; Umbenennen nur wenn noetig.
            self._apply_found_title(
                proposals[index], track, index, width, title, MatchSource.MUSICBRAINZ, selected=False
            )

    def _fill_from_filename(self, tracks: list[AudioTrack], proposals: list[TitleProposal]) -> None:
        """Letzte Option: Titel aus dem Dateinamen ableiten (nur Tag, kein Rename).

        Greift nur fuer noch offene Tracks, deren Dateiname einen verwertbaren
        Titel enthaelt (nicht nur eine Nummer). Nie vorausgewaehlt.
        """
        for index, proposal in enumerate(proposals):
            if proposal.has_match:
                continue
            title = self._title_from_filename(tracks[index].path.stem)
            if not title:
                continue
            proposal.title = title
            proposal.source = MatchSource.FILENAME
            proposal.selected = False  # Fallback -> nicht vorausgewaehlt
            proposal.proposed_name = ""  # Dateiname ist die Quelle -> nur Tag setzen

    def _title_from_filename(self, stem: str) -> str:
        """Leitet einen Titel aus dem Dateinamen ab (fuehrende Tracknummer weg)."""
        candidate = _LEADING_TRACKNUM.sub("", stem).strip()
        if not candidate or self._is_generic_title(candidate):
            return ""
        if not any(char.isalpha() for char in candidate):
            return ""  # nur Ziffern/Zeichen -> kein Titel
        return candidate

    def _resolve_artist_album(self, tracks: list[AudioTrack]) -> tuple[str, str]:
        """Ermittelt Artist + Album: eingebettete Tags, sonst Ordnernamen."""
        artist = self._first_nonempty(self._tag_io.read_embedded_artist(t.path) for t in tracks)
        album = self._first_nonempty(self._tag_io.read_embedded_album(t.path) for t in tracks)

        folder = tracks[0].path.parent if tracks else Path()
        if not album:
            album = _TRAILING_PARENS.sub("", folder.name).strip()
        if not artist:
            parent = _TRAILING_PARENS.sub("", folder.parent.name).strip()
            # "Udo Lindenberg - Diskographie" -> "Udo Lindenberg"
            artist = parent.split(" - ", 1)[0].strip() if " - " in parent else parent
        return artist, album

    @staticmethod
    def _first_nonempty(values: Iterable[str]) -> str:
        for value in values:
            text = value.strip()
            if text:
                return text
        return ""

    def _track_number(self, track: AudioTrack, index: int, width: int) -> str:
        """Ermittelt die Tracknummer: Tag -> Dateiname -> Position (1-basiert)."""
        number = self._tag_io.read_track_number(track.path)
        if number <= 0:
            match = _FILENAME_NUMBER.search(track.path.stem)
            number = int(match.group(0)) if match else 0
        if number <= 0:
            number = index + 1
        return str(number).zfill(width)
