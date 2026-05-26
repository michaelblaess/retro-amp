"""Details Panel — zeigt Encoding-, Datei- und Tag-Details des aktuellen Tracks.

Lazy-Loading: Track-Wechsel meldet das Panel nur an (`set_pending`),
die App ruft `is_load_needed()` erst beim Aktivieren des Details-Tabs auf.
"""

from __future__ import annotations

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path

from rich.markup import escape
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from ..i18n import current_language, t
from ..services.details_service import DetailsResult


def _format_modified(iso_ts: str) -> str:
    """ISO-Timestamp → lokalisierter Datum-/Zeit-String."""
    if not iso_ts:
        return ""
    try:
        dt = datetime.fromisoformat(iso_ts).astimezone()
    except (ValueError, TypeError):
        return iso_ts
    if current_language() == "de":
        return dt.strftime("%d.%m.%Y %H:%M")
    return dt.strftime("%Y-%m-%d %H:%M")


def _format_size(num_bytes: int) -> str:
    """Bytes -> kompakter String (B/KB/MB/GB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    for unit, divisor in (("KB", 1024), ("MB", 1024**2), ("GB", 1024**3)):
        next_div = divisor * 1024
        if num_bytes < next_div:
            return f"{num_bytes / divisor:.2f} {unit}"
    return f"{num_bytes / (1024**4):.2f} TB"


def _format_duration(seconds: float) -> str:
    """Sekunden -> HH:MM:SS bzw. MM:SS."""
    if not seconds:
        return ""
    total = int(round(seconds))
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


def _format_channels(channels: int) -> str:
    return {0: "", 1: "Mono", 2: "Stereo"}.get(channels, f"{channels} ch")


class _PathLink(Static, can_focus=True):
    """Klickbarer Pfad — oeffnet im OS-Datei-Manager."""

    DEFAULT_CSS = """
    _PathLink {
        height: auto;
        color: $text;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._path: Path | None = None

    def set_path(self, path: Path | None) -> None:
        self._path = path
        if path is None:
            self.update("")
            return
        self.update(f"[@click=open_path][underline]{escape(str(path))}[/underline][/]")

    def action_open_path(self) -> None:
        if self._path is None:
            return
        path = self._path
        try:
            system = platform.system()
            if system == "Windows":
                if path.is_file():
                    subprocess.Popen(["explorer", "/select,", str(path)])  # noqa: S603,S607
                else:
                    os.startfile(str(path))  # noqa: S606
            elif system == "Darwin":
                subprocess.Popen(["open", "-R", str(path)])  # noqa: S603,S607
            else:
                subprocess.Popen(["xdg-open", str(path.parent)])  # noqa: S603,S607
        except Exception:
            pass


class DetailsPanel(Widget):
    """Scrollbares Panel mit allen technischen Track-Details (Lazy-Loaded)."""

    DEFAULT_CSS = """
    DetailsPanel {
        width: 100%;
        height: 1fr;
    }
    DetailsPanel VerticalScroll {
        height: 100%;
        padding: 0 1;
    }
    DetailsPanel .section-title {
        text-style: bold;
        color: $accent;
        margin: 1 0 0 0;
    }
    DetailsPanel .section-body {
        color: $text;
        margin-bottom: 1;
    }
    DetailsPanel #details-status {
        color: $text-muted;
        padding: 1 0;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        # Lazy-Loading: pending = vom App-Layer angeforderter Track,
        # loaded = aktuell im UI dargestellter Track.
        self._pending_path: Path | None = None
        self._loaded_path: Path | None = None

    _SECTION_IDS = (
        "details-status",
        "details-stream-title",
        "details-stream-body",
        "details-file-title",
        "details-file-path",
        "details-file-body",
        "details-tags-title",
        "details-tags-body",
        "details-rg-title",
        "details-rg-body",
        "details-mb-title",
        "details-mb-body",
        "details-pic-title",
        "details-pic-body",
    )

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="details-scroll"):
            yield Static("", id="details-status")
            yield Static("", id="details-stream-title", classes="section-title")
            yield Static("", id="details-stream-body", classes="section-body")
            yield Static("", id="details-file-title", classes="section-title")
            yield _PathLink(id="details-file-path")
            yield Static("", id="details-file-body", classes="section-body")
            yield Static("", id="details-tags-title", classes="section-title")
            yield Static("", id="details-tags-body", classes="section-body")
            yield Static("", id="details-rg-title", classes="section-title")
            yield Static("", id="details-rg-body", classes="section-body")
            yield Static("", id="details-mb-title", classes="section-title")
            yield Static("", id="details-mb-body", classes="section-body")
            yield Static("", id="details-pic-title", classes="section-title")
            yield Static("", id="details-pic-body", classes="section-body")

    def on_mount(self) -> None:
        # Per Default sind alle Sektionen ausgeblendet → kein Margin-Whitespace.
        for sid in self._SECTION_IDS:
            self.query_one(f"#{sid}").display = False

    def set_pending(self, path: Path | None) -> None:
        """App meldet einen neuen Track an — wird erst beim Tab-Aktiv geladen."""
        self._pending_path = path

    def is_load_needed(self) -> bool:
        """True wenn ein anderer Track als der zuletzt geladene wartet."""
        if self._pending_path is None:
            return False
        return self._pending_path != self._loaded_path

    def pending_path(self) -> Path | None:
        return self._pending_path

    def show_loading(self, path: Path) -> None:
        """Ladezustand fuer einen Track anzeigen."""
        self._hide_all()
        self._show_text("details-status", t("details.loading", name=path.name))

    def show_no_track(self) -> None:
        """Kein Track ausgewaehlt."""
        self._hide_all()
        self._show_text("details-status", t("details.no_track"))
        self._loaded_path = None
        self._pending_path = None

    def show_details(self, path: Path, result: DetailsResult) -> None:
        """Render-Ergebnis komplett ins Panel schreiben."""
        self._hide_all()
        if result.error:
            self._show_text("details-status", t("details.error", error=result.error))
            self._loaded_path = path
            return

        self._render_stream(result)
        self._render_file(result)
        self._render_tags(result)
        self._render_replay_gain(result)
        self._render_musicbrainz(result)
        self._render_pictures(result)
        self._loaded_path = path
        self.query_one("#details-scroll", VerticalScroll).scroll_home(animate=False)

    def clear(self) -> None:
        """Komplett leeren (Track entladen)."""
        self._hide_all()
        self._loaded_path = None
        self._pending_path = None

    # ---------- Render-Helfer ----------

    def _hide_all(self) -> None:
        """Alle Sektions-Widgets ausblenden (display=False) — kein Whitespace."""
        for sid in self._SECTION_IDS:
            widget = self.query_one(f"#{sid}")
            widget.display = False
            if isinstance(widget, Static):
                widget.update("")
        self.query_one("#details-file-path", _PathLink).set_path(None)

    def _show_text(self, sid: str, text: str | Text) -> None:
        """Inhalt setzen UND Widget einblenden."""
        if not text:
            return
        widget = self.query_one(f"#{sid}", Static)
        widget.update(text)
        widget.display = True

    def _render_stream(self, result: DetailsResult) -> None:
        s = result.stream
        rows: list[tuple[str, str]] = []
        if s.codec:
            rows.append((t("details.field.codec"), s.codec))
        if s.container:
            rows.append((t("details.field.container"), s.container.upper()))
        if s.bitrate_kbps:
            br = f"{s.bitrate_kbps} kbps"
            if s.bitrate_mode:
                br += f" ({s.bitrate_mode})"
            rows.append((t("details.field.bitrate"), br))
        if s.sample_rate:
            rows.append((t("details.field.sample_rate"), f"{s.sample_rate / 1000:.1f} kHz"))
        if s.channels:
            rows.append((t("details.field.channels"), _format_channels(s.channels)))
        if s.bit_depth:
            rows.append((t("details.field.bit_depth"), f"{s.bit_depth} bit"))
        if s.duration_seconds:
            rows.append((t("details.field.duration"), _format_duration(s.duration_seconds)))
        if s.encoder:
            rows.append((t("details.field.encoder"), s.encoder))

        if rows:
            self._show_text("details-stream-title", t("details.section.audio"))
            self._show_text("details-stream-body", self._render_table(rows))

    def _render_file(self, result: DetailsResult) -> None:
        f = result.file
        if f.path is None:
            return
        self._show_text("details-file-title", t("details.section.file"))
        path_link = self.query_one("#details-file-path", _PathLink)
        path_link.set_path(f.path)
        path_link.display = True
        rows: list[tuple[str, str]] = []
        if f.size_bytes:
            rows.append((t("details.field.size"), _format_size(f.size_bytes)))
        if f.modified_iso:
            rows.append((t("details.field.modified"), _format_modified(f.modified_iso)))
        if rows:
            self._show_text("details-file-body", self._render_table(rows))

    def _render_tags(self, result: DetailsResult) -> None:
        ti = result.tags
        if not ti.tags and not ti.format:
            return
        title = t("details.section.tags")
        if ti.format:
            title += f" ({ti.format})"
        self._show_text("details-tags-title", title)
        if ti.tags:
            self._show_text("details-tags-body", self._render_table(ti.tags))

    def _render_replay_gain(self, result: DetailsResult) -> None:
        rg = result.tags.replay_gain
        if not rg:
            return
        self._show_text("details-rg-title", t("details.section.rg"))
        self._show_text("details-rg-body", self._render_table(rg))

    def _render_musicbrainz(self, result: DetailsResult) -> None:
        mb = result.tags.musicbrainz
        if not mb:
            return
        self._show_text("details-mb-title", t("details.section.mb"))
        self._show_text("details-mb-body", self._render_table(mb))

    def _render_pictures(self, result: DetailsResult) -> None:
        pics = result.tags.pictures
        if not pics:
            return
        self._show_text("details-pic-title", t("details.section.pics"))
        rows: list[tuple[str, str]] = []
        for i, pic in enumerate(pics, start=1):
            label = t("details.field.picture_n", n=i) if len(pics) > 1 else t("details.field.picture")
            parts: list[str] = []
            if pic.mime:
                parts.append(pic.mime)
            if pic.width and pic.height:
                parts.append(f"{pic.width}x{pic.height}")
            parts.append(_format_size(pic.size_bytes))
            if pic.description:
                parts.append(pic.description)
            rows.append((label, " · ".join(parts)))
        self._show_text("details-pic-body", self._render_table(rows))

    @staticmethod
    def _render_table(rows: list[tuple[str, str]]) -> Text:
        """Linksbuendige Key/Value-Tabelle mit einheitlicher Label-Breite."""
        if not rows:
            return Text("")
        key_width = min(max(len(k) for k, _ in rows), 22)
        text = Text()
        for i, (key, value) in enumerate(rows):
            label = key if len(key) <= key_width else key[: key_width - 1] + "…"
            text.append(label.ljust(key_width + 2), style="dim")
            text.append(value)
            if i < len(rows) - 1:
                text.append("\n")
        return text
