"""Cover Art Panel — zeigt Album-Cover als Unicode Half-Blocks."""
from __future__ import annotations

import io
import logging

from rich.text import Text

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from ..i18n import t

logger = logging.getLogger(__name__)

_UPPER_HALF_BLOCK = "\u2580"


def _render_half_blocks(
    image_data: bytes, max_width: int, max_height: int,
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

    # Skalierung: Terminale Zeichen sind ca. 2:1 (hoch:breit)
    # Half-Blocks verdoppeln vertikale Aufloesung
    pixel_h = max_height * 2
    scale = min(max_width / orig_w, pixel_h / orig_h)
    new_w = max(1, int(orig_w * scale))
    new_h = max(2, int(orig_h * scale))
    # Auf gerade Hoehe runden (fuer Half-Block-Paare)
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


class CoverArtPanel(Widget):
    """Zeigt Album-Cover-Art als Unicode Half-Blocks."""

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
    CoverArtPanel #cover-content {
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="cover-scroll"):
            yield Static("", id="cover-title")
            yield Static("", id="cover-content")

    def show_loading(self, artist: str, title: str) -> None:
        """Zeigt Ladezustand an."""
        self.query_one("#cover-title", Static).update(
            f"\u266a {artist} \u2014 {title}"
        )
        self.query_one("#cover-content", Static).update(t("cover.loading"))

    def show_cover(
        self, artist: str, title: str, image_data: bytes | None,
    ) -> None:
        """Rendert Cover-Art oder zeigt Fallback-Text."""
        self.query_one("#cover-title", Static).update(
            f"\u266a {artist} \u2014 {title}"
        )
        if not image_data:
            self.query_one("#cover-content", Static).update(t("cover.not_found"))
            return

        # Verfuegbare Breite/Hoehe schaetzen
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
            self.query_one("#cover-content", Static).update(combined)
        else:
            self.query_one("#cover-content", Static).update(t("cover.not_found"))

    def clear(self) -> None:
        """Leert das Panel."""
        self.query_one("#cover-title", Static).update("")
        self.query_one("#cover-content", Static).update("")
