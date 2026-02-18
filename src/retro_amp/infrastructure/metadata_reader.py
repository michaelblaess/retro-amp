"""Audio-Metadaten lesen via mutagen."""
from __future__ import annotations

import logging
from pathlib import Path

from ..domain.models import AudioFormat, AudioTrack

logger = logging.getLogger(__name__)


class MutagenMetadataReader:
    """MetadataReader-Implementation mit mutagen.

    Implementiert das MetadataReader-Protocol aus domain/protocols.py.
    """

    def read(self, path: Path) -> AudioTrack:
        """Liest Metadaten einer Audio-Datei."""
        track = AudioTrack(path=path)

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
