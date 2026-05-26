"""Details Service — liest Encoding-, Datei- und Tag-Details einer Audio-Datei.

Nutzt mutagen fuer Stream-/Tag-Info und Pillow fuer Bild-Dimensionen
eingebetteter Cover. Tracker- und SID-Formate werden nur sehr knapp
abgedeckt (mutagen kennt sie nicht).
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Tracker-/SID-Formate werden von mutagen nicht erkannt.
_NO_MUTAGEN_EXTENSIONS = {".mod", ".s3m", ".xm", ".sid"}

# ID3v2-Frame-IDs -> sprechende Bezeichnung
_ID3_LABELS: dict[str, str] = {
    "TIT2": "Title",
    "TPE1": "Artist",
    "TPE2": "Album Artist",
    "TALB": "Album",
    "TDRC": "Date",
    "TYER": "Year",
    "TCON": "Genre",
    "TRCK": "Track",
    "TPOS": "Disc",
    "TCOM": "Composer",
    "TBPM": "BPM",
    "TENC": "Encoded by",
    "TSSE": "Encoder Settings",
    "TPUB": "Publisher",
    "TCOP": "Copyright",
    "COMM": "Comment",
    "TLAN": "Language",
    "TSRC": "ISRC",
    "TPE3": "Conductor",
    "TPE4": "Remixed by",
    "TIT1": "Content Group",
    "TIT3": "Subtitle",
    "TKEY": "Initial Key",
    "TMED": "Media Type",
    "TOAL": "Original Album",
    "TOPE": "Original Artist",
}

# MP4/iTunes-Atom-Namen -> sprechende Bezeichnung
_MP4_LABELS: dict[str, str] = {
    "\xa9nam": "Title",
    "\xa9ART": "Artist",
    "aART": "Album Artist",
    "\xa9alb": "Album",
    "\xa9day": "Date",
    "\xa9gen": "Genre",
    "gnre": "Genre (ID)",
    "trkn": "Track",
    "disk": "Disc",
    "\xa9wrt": "Composer",
    "tmpo": "BPM",
    "\xa9too": "Encoder",
    "cprt": "Copyright",
    "\xa9cmt": "Comment",
    "\xa9grp": "Grouping",
}

# Vorbis-Comment-Keys (lower-case) -> sprechende Bezeichnung
_VORBIS_LABELS: dict[str, str] = {
    "title": "Title",
    "artist": "Artist",
    "albumartist": "Album Artist",
    "album": "Album",
    "date": "Date",
    "year": "Year",
    "genre": "Genre",
    "tracknumber": "Track",
    "tracktotal": "Track Total",
    "discnumber": "Disc",
    "disctotal": "Disc Total",
    "composer": "Composer",
    "bpm": "BPM",
    "encoder": "Encoder",
    "publisher": "Publisher",
    "copyright": "Copyright",
    "comment": "Comment",
    "isrc": "ISRC",
    "organization": "Publisher",
    "performer": "Performer",
}

# Tags, die in der Tag-Tabelle ausgeblendet werden
# (Cover-Art separat, Lyrics liegen im Lyrics-Tab).
_SKIP_TAG_KEYS = {
    "USLT",
    "\xa9lyr",
    "lyrics",
    "unsyncedlyrics",
}


@dataclass
class StreamInfo:
    """Audio-Stream-Eigenschaften."""

    codec: str = ""
    container: str = ""
    bitrate_kbps: int = 0
    bitrate_mode: str = ""  # "CBR" / "VBR" / "ABR" / ""
    sample_rate: int = 0
    channels: int = 0
    bit_depth: int = 0
    duration_seconds: float = 0.0
    encoder: str = ""


@dataclass
class FileInfo:
    """Dateisystem-Eigenschaften."""

    path: Path | None = None
    size_bytes: int = 0
    modified_iso: str = ""


@dataclass
class EmbeddedPicture:
    """Ein eingebettetes Cover-Bild."""

    mime: str = ""
    size_bytes: int = 0
    width: int = 0
    height: int = 0
    description: str = ""


@dataclass
class TagsInfo:
    """Tag-Daten (Format, Key/Value-Paare, ReplayGain, MB-IDs, Pictures)."""

    format: str = ""
    tags: list[tuple[str, str]] = field(default_factory=list)
    replay_gain: list[tuple[str, str]] = field(default_factory=list)
    musicbrainz: list[tuple[str, str]] = field(default_factory=list)
    pictures: list[EmbeddedPicture] = field(default_factory=list)


@dataclass
class DetailsResult:
    """Komplettes Ergebnis fuer das Details-Panel."""

    stream: StreamInfo = field(default_factory=StreamInfo)
    file: FileInfo = field(default_factory=FileInfo)
    tags: TagsInfo = field(default_factory=TagsInfo)
    error: str = ""


class DetailsService:
    """Liest Details-Daten einer Audio-Datei (synchron, evtl. langsam → Worker)."""

    def read_details(self, path: Path) -> DetailsResult:
        """Liest Stream-, Datei- und Tag-Daten."""
        result = DetailsResult()
        result.file.path = path
        result.stream.container = path.suffix.lower().lstrip(".") or "unknown"

        try:
            stat = path.stat()
            result.file.size_bytes = stat.st_size
            result.file.modified_iso = datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat()
        except OSError as exc:
            result.error = str(exc)
            return result

        # Formate ohne mutagen-Support: nur Container + Datei-Info.
        if path.suffix.lower() in _NO_MUTAGEN_EXTENSIONS:
            result.stream.codec = path.suffix.lower().lstrip(".").upper()
            return result

        try:
            import mutagen

            audio = mutagen.File(str(path))
            if audio is None:
                return result

            self._extract_stream(audio, result.stream)
            self._extract_tags(audio, result.tags)
            self._extract_pictures(audio, result.tags)
        except Exception as exc:
            logger.debug("Details fehlgeschlagen: %s", path, exc_info=True)
            result.error = str(exc)

        return result

    @staticmethod
    def _extract_stream(audio: Any, stream: StreamInfo) -> None:
        info = getattr(audio, "info", None)
        if info is None:
            return

        mime_list = getattr(audio, "mime", None) or []
        if mime_list:
            stream.codec = mime_list[0]
        else:
            stream.codec = audio.__class__.__name__

        length = getattr(info, "length", 0.0)
        if length:
            stream.duration_seconds = float(length)

        bitrate = getattr(info, "bitrate", 0) or 0
        if bitrate:
            stream.bitrate_kbps = bitrate // 1000 if bitrate > 1000 else bitrate

        # MP3: BitrateMode-Enum
        mode = getattr(info, "bitrate_mode", None)
        if mode is not None:
            try:
                from mutagen.mp3 import BitrateMode

                mode_map = {
                    BitrateMode.CBR: "CBR",
                    BitrateMode.VBR: "VBR",
                    BitrateMode.ABR: "ABR",
                }
                stream.bitrate_mode = mode_map.get(mode, "")
            except Exception:
                pass

        stream.sample_rate = getattr(info, "sample_rate", 0) or 0
        stream.channels = getattr(info, "channels", 0) or 0
        stream.bit_depth = getattr(info, "bits_per_sample", 0) or 0

        encoder = getattr(info, "encoder_info", "") or ""
        if not encoder:
            tags = getattr(audio, "tags", None)
            if tags is not None:
                for key in ("TSSE", "TENC", "\xa9too", "encoder", "ENCODER"):
                    try:
                        raw = tags.get(key)
                    except Exception:
                        raw = None
                    if not raw:
                        continue
                    encoder = DetailsService._stringify(raw)
                    if encoder:
                        break
        stream.encoder = encoder

    def _extract_tags(self, audio: Any, tags_info: TagsInfo) -> None:
        tags = getattr(audio, "tags", None)
        if tags is None:
            return

        cls_name = tags.__class__.__name__
        if cls_name == "ID3":
            version = getattr(tags, "version", (0, 0, 0))
            tags_info.format = f"ID3v{version[0]}.{version[1]}"
        elif cls_name in (
            "VComment",
            "VCFLACDict",
            "OggOpusVComment",
            "OggVCommentDict",
            "OggVorbisVComment",
            "FLACVCommentDict",
        ):
            tags_info.format = "Vorbis Comments"
        elif cls_name == "MP4Tags":
            tags_info.format = "MP4/iTunes"
        elif cls_name == "APEv2":
            tags_info.format = "APEv2"
        elif cls_name:
            tags_info.format = cls_name

        try:
            keys = list(tags.keys())
        except Exception:
            keys = []

        for key in keys:
            base_key = key.split(":")[0]
            if base_key in _SKIP_TAG_KEYS or key in _SKIP_TAG_KEYS:
                continue
            if key.startswith("APIC"):
                continue
            try:
                value = tags[key]
            except Exception:
                continue

            label, val_str = self._format_tag(key, value)
            if not val_str:
                continue

            key_lower = key.lower()
            if "replaygain" in key_lower:
                tags_info.replay_gain.append((label, val_str))
            elif "musicbrainz" in key_lower:
                tags_info.musicbrainz.append((label, val_str))
            else:
                tags_info.tags.append((label, val_str))

    @staticmethod
    def _format_tag(key: str, value: Any) -> tuple[str, str]:
        """Erzeugt (Label, Wert)-Paar fuer einen Tag."""
        # ID3 user-defined: "TXXX:replaygain_track_gain" → "replaygain_track_gain"
        if key.startswith("TXXX:") or key.startswith("WXXX:"):
            label = key.split(":", 1)[1]
        elif key.startswith("COMM:"):
            label = "Comment"
        else:
            base_key = key.split(":")[0]
            label = _ID3_LABELS.get(base_key) or _MP4_LABELS.get(key) or _VORBIS_LABELS.get(key.lower()) or key

        return label, DetailsService._stringify(value)

    @staticmethod
    def _stringify(value: Any) -> str:
        """Konvertiert beliebige Mutagen-Tag-Werte in Strings."""
        if value is None:
            return ""
        # ID3-Frame mit .text
        if hasattr(value, "text"):
            text = value.text
            if isinstance(text, list):
                return ", ".join(str(t) for t in text).strip()
            return str(text).strip()
        # MP4 trkn/disk: list[tuple[num, total]]
        if isinstance(value, list):
            if not value:
                return ""
            first = value[0]
            if isinstance(first, tuple) and len(first) == 2:
                num, total = first
                return f"{num}/{total}" if total else str(num)
            return ", ".join(str(v) for v in value).strip()
        return str(value).strip()

    @staticmethod
    def _extract_pictures(audio: Any, tags_info: TagsInfo) -> None:
        pictures: list[tuple[str, str, bytes]] = []

        tags = getattr(audio, "tags", None)
        if tags is not None:
            try:
                keys = list(tags.keys())
            except Exception:
                keys = []
            for key in keys:
                if key.startswith("APIC"):
                    try:
                        frame = tags[key]
                    except Exception:
                        continue
                    data = getattr(frame, "data", b"")
                    if data:
                        pictures.append(
                            (
                                getattr(frame, "mime", "") or "",
                                getattr(frame, "desc", "") or "",
                                data,
                            )
                        )

        # FLAC eingebettete Pictures
        flac_pics = getattr(audio, "pictures", None) or []
        for pic in flac_pics:
            if getattr(pic, "data", None):
                pictures.append(
                    (
                        getattr(pic, "mime", "") or "",
                        getattr(pic, "desc", "") or "",
                        pic.data,
                    )
                )

        # MP4 covr
        try:
            covr = audio.get("covr") if hasattr(audio, "get") else None
        except Exception:
            covr = None
        if covr:
            for cov in covr:
                fmt = getattr(cov, "imageformat", None)
                mime = "image/jpeg" if fmt == 13 else "image/png" if fmt == 14 else ""
                pictures.append((mime, "", bytes(cov)))

        for mime, desc, data in pictures:
            pic_info = EmbeddedPicture(
                mime=mime,
                size_bytes=len(data),
                description=desc,
            )
            try:
                from PIL import Image

                with Image.open(io.BytesIO(data)) as img:
                    pic_info.width = img.width
                    pic_info.height = img.height
            except Exception:
                pass
            tags_info.pictures.append(pic_info)
