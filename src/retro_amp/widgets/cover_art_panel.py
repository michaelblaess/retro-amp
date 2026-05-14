"""Cover Art Panel — zeigt Album-Cover als Unicode Half-Blocks oder via Terminal-Grafik."""

from __future__ import annotations

import io
import logging
import os
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from ..i18n import t

logger = logging.getLogger(__name__)

_UPPER_HALF_BLOCK = "\u2580"


def _select_graphics_backend() -> str | None:
    """Ermittelt das beste Terminal-Grafik-Protokoll anhand des Terminals.

    Rueckgabe: "tgp" (Kitty-Protokoll), "sixel" oder None (kein Grafik-Protokoll,
    Fallback auf Halfblock). Detection ueber Environment-Variablen.
    """
    term = os.environ.get("TERM", "").lower()
    term_program = os.environ.get("TERM_PROGRAM", "").lower()

    if os.environ.get("KITTY_WINDOW_ID"):
        return "tgp"
    if "kitty" in term or "ghostty" in term:
        return "tgp"
    if term_program in ("wezterm", "ghostty"):
        return "tgp"
    if os.environ.get("KONSOLE_VERSION"):
        return "tgp"

    if os.environ.get("WT_SESSION"):
        return "sixel"
    if term in ("foot", "xterm", "mlterm", "mintty") or "foot" in term:
        return "sixel"
    if term_program in ("mintty", "iterm.app"):
        return "sixel"

    return None


def _render_half_blocks(
    image_data: bytes,
    max_width: int,
    max_height: int,
) -> list[Text]:
    """Rendert Bilddaten als Unicode Half-Block-Zeilen.

    Jedes Terminal-Zeichen kodiert 2 vertikale Pixel via Foreground/Background.
    max_height ist in Terminal-Zeilen (= 2x Pixel-Zeilen).
    """
    try:
        from PIL import Image as PILImage
    except ImportError:
        return [Text("(Pillow nicht installiert)", style="dim")]

    try:
        img = PILImage.open(io.BytesIO(image_data)).convert("RGB")
    except Exception:
        return [Text(t("cover.error"), style="dim")]

    orig_w, orig_h = img.size
    if orig_w <= 0 or orig_h <= 0:
        return []

    pixel_h = max_height * 2
    scale = min(max_width / orig_w, pixel_h / orig_h)
    new_w = max(1, int(orig_w * scale))
    new_h = max(2, int(orig_h * scale))
    if new_h % 2 != 0:
        new_h += 1

    img = img.resize((new_w, new_h), PILImage.LANCZOS)

    lines: list[Text] = []
    for y in range(0, new_h, 2):
        line = Text()
        for x in range(new_w):
            top_r, top_g, top_b = img.getpixel((x, y))
            bot_r, bot_g, bot_b = img.getpixel((x, y + 1))
            line.append(
                _UPPER_HALF_BLOCK,
                style=f"rgb({top_r},{top_g},{top_b}) on rgb({bot_r},{bot_g},{bot_b})",
            )
        lines.append(line)
    return lines


def _load_graphics_widget_class(backend: str) -> type[Widget] | None:
    """Laedt die passende textual-image Widget-Klasse.

    Rueckgabe: Widget-Klasse (SixelImage oder TGPImage) oder None wenn
    textual-image nicht installiert ist.
    """
    try:
        if backend == "tgp":
            from textual_image.widget import TGPImage

            return TGPImage
        if backend == "sixel":
            from textual_image.widget import SixelImage

            return SixelImage
    except ImportError:
        logger.debug("textual-image nicht installiert, Grafik-Rendering nicht verfuegbar")
        return None
    return None


class CoverArtPanel(Widget):
    """Zeigt Album-Cover-Art als Unicode Half-Blocks oder via Terminal-Grafik."""

    DEFAULT_CSS = """
    CoverArtPanel {
        width: 100%;
        height: 1fr;
    }
    CoverArtPanel #cover-scroll {
        height: 100%;
        align-horizontal: center;
        padding: 1 2;
    }
    CoverArtPanel #cover-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    CoverArtPanel #cover-status {
        color: $text-muted;
        height: auto;
    }
    CoverArtPanel #cover-content {
        color: $text;
    }
    CoverArtPanel .graphics-image {
        width: auto;
        height: 1fr;
    }
    CoverArtPanel .-hidden {
        display: none;
    }
    """

    def __init__(self, renderer: str = "halfblock", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._renderer = renderer if renderer in ("halfblock", "graphics") else "halfblock"
        self._graphics_backend: str | None = None
        self._graphics_widget_cls: type[Widget] | None = None

        if self._renderer == "graphics":
            backend = _select_graphics_backend()
            if backend is not None:
                widget_cls = _load_graphics_widget_class(backend)
                if widget_cls is not None:
                    self._graphics_backend = backend
                    self._graphics_widget_cls = widget_cls
                else:
                    logger.debug("Grafik-Widget nicht ladbar, Fallback auf Halfblock")
            else:
                logger.debug("Terminal unterstuetzt kein Grafik-Protokoll, Fallback auf Halfblock")

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="cover-scroll"):
            yield Static("", id="cover-title")
            if self._graphics_widget_cls is not None:
                yield Static("", id="cover-status")
                yield self._graphics_widget_cls(
                    id="cover-content",
                    classes="graphics-image",
                )
            else:
                yield Static("", id="cover-content")

    def _set_title(self, artist: str, title: str) -> None:
        self.query_one("#cover-title", Static).update(f"\u266a {artist} \u2014 {title}")

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#cover-status", Static).update(text)
        except Exception:
            pass

    def _clear_graphics_image(self) -> None:
        if self._graphics_widget_cls is None:
            return
        try:
            widget = self.query_one("#cover-content", self._graphics_widget_cls)
            widget.image = None  # type: ignore[attr-defined]
        except Exception:
            logger.debug("Konnte Grafik-Widget nicht leeren", exc_info=True)

    def show_loading(self, artist: str, title: str) -> None:
        """Zeigt Ladezustand an."""
        self._set_title(artist, title)
        if self._graphics_widget_cls is not None:
            self._set_status(t("cover.loading"))
            self._clear_graphics_image()
        else:
            self.query_one("#cover-content", Static).update(t("cover.loading"))

    def show_cover(
        self,
        artist: str,
        title: str,
        image_data: bytes | None,
    ) -> None:
        """Rendert Cover-Art oder zeigt Fallback-Text."""
        self._set_title(artist, title)

        if self._graphics_widget_cls is not None:
            self._show_cover_graphics(image_data)
            return

        self._show_cover_halfblock(image_data)

    def _show_cover_graphics(self, image_data: bytes | None) -> None:
        """Zeigt Cover ueber ein textual-image Widget (TGP/Sixel)."""
        if not image_data:
            self._set_status(t("cover.not_found"))
            self._clear_graphics_image()
            return

        try:
            from PIL import Image as PILImage
        except ImportError:
            self._set_status(t("cover.error"))
            self._clear_graphics_image()
            return

        try:
            pil_img = PILImage.open(io.BytesIO(image_data)).convert("RGB")
        except Exception:
            self._set_status(t("cover.error"))
            self._clear_graphics_image()
            return

        try:
            assert self._graphics_widget_cls is not None
            widget = self.query_one("#cover-content", self._graphics_widget_cls)
            widget.image = pil_img  # type: ignore[attr-defined]
            self._set_status("")
        except Exception:
            logger.debug("Grafik-Widget Update fehlgeschlagen", exc_info=True)
            self._set_status(t("cover.error"))

    def _show_cover_halfblock(self, image_data: bytes | None) -> None:
        """Zeigt Cover ueber Unicode Half-Blocks in einem Static."""
        content = self.query_one("#cover-content", Static)
        if not image_data:
            content.update(t("cover.not_found"))
            return

        try:
            scroll = self.query_one("#cover-scroll")
            max_width = max(20, scroll.size.width - 4)
            max_height = max(10, scroll.size.height - 4)
        except Exception:
            max_width = 60
            max_height = 30

        lines = _render_half_blocks(image_data, max_width, max_height)
        if lines:
            combined = Text("\n").join(lines)
            content.update(combined)
        else:
            content.update(t("cover.not_found"))

    def clear(self) -> None:
        """Leert das Panel."""
        self.query_one("#cover-title", Static).update("")
        if self._graphics_widget_cls is not None:
            self._set_status("")
            self._clear_graphics_image()
        else:
            self.query_one("#cover-content", Static).update("")
