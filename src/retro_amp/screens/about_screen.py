"""About-Screen fuer retro-amp."""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult, RenderResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Static

from .. import __author__, __version__, __year__


class AboutContent(Widget):
    """Rendert den About-Inhalt als Rich Text."""

    DEFAULT_CSS = """
    AboutContent {
        height: auto;
        padding: 1 2;
    }
    """

    def render(self) -> RenderResult:
        """Erstellt den About-Text."""
        text = Text()
        text.append(f"v{__version__}", style="bold")
        text.append(" \u00b7 ", style="dim")
        text.append(__author__, style="bold")
        text.append(" \u00b7 ", style="dim")
        text.append(__year__, style="bold")
        text.append("\n\n")

        text.append("Terminal-Musikplayer mit Retro-Charme.\n")
        text.append("C64, Amiga, Atari ST \u2014 alles im Terminal.\n\n")

        text.append("MP3 \u00b7 OGG \u00b7 FLAC \u00b7 WAV \u00b7 MOD \u00b7 XM \u00b7 S3M \u00b7 SID\n\n")

        text.append("\u2500" * 44 + "\n\n", style="dim")

        text.append(
            "\u201eMusik drueckt das aus, was nicht gesagt\n"
            "werden kann und worueber zu schweigen\n"
            "unmoeglich ist.\u201c\n\n",
            style="italic",
        )
        text.append(" \u2014 Victor Hugo", style="bold")

        return text


class AboutScreen(ModalScreen[None]):
    """Modal-Dialog mit Informationen ueber die Anwendung."""

    DEFAULT_CSS = """
    AboutScreen {
        align: center middle;
    }

    AboutScreen > VerticalScroll {
        width: 60;
        height: 24;
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

    AboutScreen #about-footer {
        height: 1;
        content-align: center middle;
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Schliessen"),
        Binding("i", "close", "Schliessen"),
    ]

    def compose(self) -> ComposeResult:
        """Erstellt das Modal-Layout."""
        with VerticalScroll():
            yield Static("retro-amp", id="about-title")
            yield AboutContent()
            yield Static("ESC = Schliessen", id="about-footer")

    def action_close(self) -> None:
        """Schliesst den Dialog."""
        self.dismiss(None)
