"""Info Panel — zeigt Liner Notes (Wikipedia-Info) zum aktuellen Artist."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static


class InfoPanel(Widget):
    """Scrollbares Panel fuer Artist-Informationen (Liner Notes)."""

    DEFAULT_CSS = """
    InfoPanel {
        width: 100%;
        height: 1fr;
    }
    InfoPanel #info-scroll {
        height: 100%;
        padding: 0 1;
    }
    InfoPanel #info-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    InfoPanel #info-body {
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="info-scroll"):
            yield Static("", id="info-title")
            yield Static("", id="info-body")

    def show_loading(self, artist: str) -> None:
        """Zeigt Ladezustand an."""
        title_widget = self.query_one("#info-title", Static)
        body_widget = self.query_one("#info-body", Static)

        title_widget.update(f"\u266a {artist}")
        body_widget.update("Suche Informationen...")

    def show_info(self, artist: str, note: str) -> None:
        """Zeigt Artist-Info an."""
        title_widget = self.query_one("#info-title", Static)
        body_widget = self.query_one("#info-body", Static)

        title_widget.update(f"\u266a {artist}")

        if note:
            body_widget.update(self._extract_body(note))
        else:
            body_widget.update(
                "Keine Informationen gefunden.\n\n"
                "Moegliche Gruende:\n"
                "- Kein Internet\n"
                "- Artist nicht auf Wikipedia\n"
                "- Kein Artist-Tag in der Datei"
            )

        # Zum Anfang scrollen
        scroll = self.query_one("#info-scroll", VerticalScroll)
        scroll.scroll_home(animate=False)

    def clear(self) -> None:
        """Leert das Panel."""
        title_widget = self.query_one("#info-title", Static)
        body_widget = self.query_one("#info-body", Static)
        title_widget.update("")
        body_widget.update("")

    @staticmethod
    def _extract_body(note: str) -> str:
        """Extrahiert den Body-Text aus der Markdown-Note."""
        lines = note.split("\n")
        body_lines: list[str] = []
        for line in lines:
            if line.startswith("# "):
                continue
            body_lines.append(line)
        return "\n".join(body_lines).strip()
