"""About-Screen fuer retro-amp."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from .. import __author__, __version__, __year__
from ..i18n import t


class AboutScreen(ModalScreen[None]):
    """Modal-Dialog mit Informationen ueber die Anwendung."""

    DEFAULT_CSS = """
    AboutScreen {
        align: center middle;
    }

    AboutScreen > VerticalScroll {
        width: auto;
        height: auto;
        min-width: 50;
        max-width: 90;
        max-height: 90%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    AboutScreen #about-title {
        height: 3;
        content-align: center middle;
        text-style: bold;
        background: $accent;
        color: $text;
        margin-bottom: 1;
    }

    AboutScreen #about-content {
        height: auto;
        padding: 1 2;
    }

    AboutScreen #about-footer {
        height: 1;
        content-align: center middle;
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "ESC"),
        Binding("i", "close", "i"),
    ]

    def compose(self) -> ComposeResult:
        """Erstellt das Modal-Layout."""
        with VerticalScroll():
            yield Static("retro-amp", id="about-title")
            yield Static(self._build_content(), id="about-content")
            yield Static(t("about.footer"), id="about-footer")

    def _build_content(self) -> Text:
        """Baut den About-Text als Rich Text."""
        text = Text()
        text.append(f"v{__version__}", style="bold")
        text.append(" · ", style="dim")
        text.append(__author__, style="bold")
        text.append(" · ", style="dim")
        text.append(__year__, style="bold")
        text.append("\n\n")

        text.append(t("about.description"))
        text.append(t("about.subtitle"))

        text.append("MP3 · OGG · FLAC · WAV · MOD · XM · S3M · SID\n\n")

        text.append("─" * 44 + "\n\n", style="dim")

        text.append(
            t("about.quote") + "\n\n",
            style="italic",
        )
        text.append(" — Sammy Davis jr.", style="bold")

        return text

    def action_close(self) -> None:
        """Schliesst den Dialog."""
        self.dismiss(None)
