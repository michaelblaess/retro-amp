"""Audio-Metadaten lesen via mutagen.

Tracker-Formate (MOD, S3M, XM) und SID-Dateien werden nicht von mutagen
unterstuetzt. Deren Metadaten werden direkt aus dem Datei-Header gelesen.
"""
from __future__ import annotations

import logging
from pathlib import Path

from ..domain.models import AudioFormat, AudioTrack

logger = logging.getLogger(__name__)

# Formate mit Header-Metadaten (kein mutagen-Support)
_TRACKER_EXTENSIONS = {".mod", ".s3m", ".xm"}
_HEADER_EXTENSIONS = {".mod", ".s3m", ".xm", ".sid"}


def _read_header_title(path: Path) -> str:
    """Liest den Song-Titel aus dem Header einer Tracker-/SID-Datei."""
    try:
        ext = path.suffix.lower()
        with open(path, "rb") as f:
            if ext == ".mod":
                # MOD: Bytes 0-19 = Song-Titel (ASCII, null-padded)
                raw = f.read(20)
            elif ext == ".s3m":
                # S3M: Bytes 0-27 = Song-Name (ASCII, null-padded)
                raw = f.read(28)
            elif ext == ".xm":
                # XM: Bytes 17-36 = Modul-Name (nach "Extended Module: " Header)
                header = f.read(37)
                raw = header[17:37] if len(header) >= 37 else b""
            elif ext == ".sid":
                # PSID/RSID: Bytes 0x16-0x35 = Name (32 Bytes, ASCII)
                header = f.read(0x36)
                raw = header[0x16:0x36] if len(header) >= 0x36 else b""
            else:
                return ""
            return raw.decode("ascii", errors="replace").strip("\x00").strip()
    except Exception:
        return ""


def _read_sid_artist(path: Path) -> str:
    """Liest den Artist aus dem SID-Header."""
    try:
        with open(path, "rb") as f:
            header = f.read(0x56)
            # PSID/RSID: Bytes 0x36-0x55 = Author (32 Bytes, ASCII)
            if len(header) >= 0x56:
                return header[0x36:0x56].decode("ascii", errors="replace").strip("\x00").strip()
    except Exception:
        pass
    return ""


class MutagenMetadataReader:
    """MetadataReader-Implementation mit mutagen.

    Implementiert das MetadataReader-Protocol aus domain/protocols.py.
    Tracker-Formate (MOD/S3M/XM) liest es direkt aus dem Header.
    """

    def read(self, path: Path) -> AudioTrack:
        """Liest Metadaten einer Audio-Datei."""
        track = AudioTrack(path=path)

        # Tracker/SID-Formate: mutagen unterstuetzt diese nicht
        if path.suffix.lower() in _HEADER_EXTENSIONS:
            title = _read_header_title(path)
            if title:
                track.title = title
            if path.suffix.lower() == ".sid":
                artist = _read_sid_artist(path)
                if artist:
                    track.artist = artist
            return track

        try:
            import mutagen

            audio = mutagen.File(str(path))
            if audio is None:
                return track

            # Dauer
            if hasattr(audio, "info") and hasattr(audio.info, "length"):
                track.duration_seconds = audio.info.length or 0.0

            # Bitrate
            if hasattr(audio, "info") and hasattr(audio.info, "bitrate"):
                bitrate = audio.info.bitrate or 0
                track.bitrate_kbps = bitrate // 1000 if bitrate > 1000 else bitrate

            # Sample Rate
            if hasattr(audio, "info") and hasattr(audio.info, "sample_rate"):
                track.sample_rate = audio.info.sample_rate or 0

            # Tags lesen (verschiedene Formate)
            track.title = self._read_tag(audio, "title", "TIT2")
            track.artist = self._read_tag(audio, "artist", "TPE1")
            track.album = self._read_tag(audio, "album", "TALB")

        except Exception:
            logger.debug("Metadaten konnten nicht gelesen werden: %s", path)

        return track

    def _read_tag(self, audio: object, *tag_names: str) -> str:
        """Versucht einen Tag unter verschiedenen Namen zu lesen."""
        # Versuch ueber get() (Vorbis, FLAC, MP4)
        if hasattr(audio, "get"):
            for name in tag_names:
                value = audio.get(name)  # type: ignore[union-attr]
                if value:
                    if isinstance(value, list):
                        return str(value[0]) if value else ""
                    return str(value)

        # Versuch ueber tags (ID3)
        if hasattr(audio, "tags") and audio.tags is not None:  # type: ignore[union-attr]
            for name in tag_names:
                tag = audio.tags.get(name)  # type: ignore[union-attr]
                if tag:
                    if hasattr(tag, "text") and tag.text:
                        return str(tag.text[0])
                    return str(tag)

        return ""
