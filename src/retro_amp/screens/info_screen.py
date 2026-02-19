"""Info-Screen — zeigt Liner Notes (Wikipedia-Info) zum aktuellen Artist."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class InfoScreen(ModalScreen[None]):
    """Zeigt Artist-Info als Liner Notes an."""

    DEFAULT_CSS = """
    InfoScreen {
        align: center middle;
    }
    InfoScreen #info-container {
        width: 70;
        max-height: 80%;
        border: thick $accent;
        padding: 1 2;
        background: $surface;
    }
    InfoScreen #info-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    InfoScreen #info-body {
        overflow-y: auto;
    }
    InfoScreen #info-hint {
        margin-top: 1;
        color: $text-muted;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_screen", "Schliessen", key_display="ESC"),
        Binding("i", "dismiss_screen", "Schliessen"),
    ]

    def __init__(self, artist: str, note: str) -> None:
        super().__init__()
        self._artist = artist
        self._note = note

    def compose(self) -> ComposeResult:
        with Vertical(id="info-container"):
            yield Static(f"♪ {self._artist}", id="info-title")
            if self._note:
                # Note ist Markdown — wir zeigen den Text-Teil
                body = self._extract_body(self._note)
                yield Static(body, id="info-body")
            else:
                yield Static(
                    "Keine Informationen gefunden.\n\n"
                    "Moegliche Gruende:\n"
                    "- Kein Internet\n"
                    "- Artist nicht auf Wikipedia\n"
                    "- Kein Artist-Tag in der Datei",
                    id="info-body",
                )
            yield Static("ESC oder I zum Schliessen", id="info-hint")

    def action_dismiss_screen(self) -> None:
        """Screen schliessen."""
        self.dismiss(None)

    def _extract_body(self, note: str) -> str:
        """Extrahiert den Body-Text aus der Markdown-Note."""
        lines = note.split("\n")
        body_lines: list[str] = []
        for line in lines:
            # Titel-Zeile ueberspringen
            if line.startswith("# "):
                continue
            body_lines.append(line)
        return "\n".join(body_lines).strip()
