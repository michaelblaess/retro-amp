"""Info Panel — zeigt Liner Notes (Wikipedia-Info) zum aktuellen Artist."""
from __future__ import annotations

import re
import webbrowser

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static


class _SourceLink(Static, can_focus=True):
    """Klickbarer Quellen-Link (Wikipedia etc.)."""

    DEFAULT_CSS = """
    _SourceLink {
        height: auto;
        margin-top: 1;
        padding: 0 1;
        color: $text-muted;
    }
    _SourceLink:hover {
        text-style: underline;
        color: $accent;
    }
    _SourceLink:focus {
        text-style: underline;
        color: $accent;
    }
    """

    BINDINGS = [("enter", "open_link", "Oeffnen")]

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._url: str = ""

    def set_source(self, label: str, url: str) -> None:
        """Setzt Label und URL."""
        self._url = url
        self.update(label)

    def on_click(self) -> None:
        if self._url:
            webbrowser.open(self._url)

    def action_open_link(self) -> None:
        if self._url:
            webbrowser.open(self._url)


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
            yield _SourceLink(id="info-source")

    def show_loading(self, artist: str) -> None:
        """Zeigt Ladezustand an."""
        self.query_one("#info-title", Static).update(f"\u266a {artist}")
        self.query_one("#info-body", Static).update("Suche Informationen...")
        source = self.query_one("#info-source", _SourceLink)
        source._url = ""
        source.update("")

    def show_info(self, artist: str, note: str) -> None:
        """Zeigt Artist-Info an."""
        self.query_one("#info-title", Static).update(f"\u266a {artist}")

        if note:
            body_text, source_label, source_url = self._parse_note(note)
            self.query_one("#info-body", Static).update(body_text)
            source = self.query_one("#info-source", _SourceLink)
            if source_url:
                source.set_source(source_label, source_url)
            else:
                source._url = ""
                source.update("")
        else:
            self.query_one("#info-body", Static).update(
                "Keine Informationen gefunden.\n\n"
                "Moegliche Gruende:\n"
                "- Kein Internet\n"
                "- Artist nicht auf Wikipedia\n"
                "- Kein Artist-Tag in der Datei"
            )
            source = self.query_one("#info-source", _SourceLink)
            source._url = ""
            source.update("")

        self.query_one("#info-scroll", VerticalScroll).scroll_home(animate=False)

    def clear(self) -> None:
        """Leert das Panel."""
        self.query_one("#info-title", Static).update("")
        self.query_one("#info-body", Static).update("")
        source = self.query_one("#info-source", _SourceLink)
        source._url = ""
        source.update("")

    @staticmethod
    def _parse_note(note: str) -> tuple[str, str, str]:
        """Extrahiert Body, Source-Label und Source-URL aus der Markdown-Note."""
        lines = note.split("\n")
        body_lines: list[str] = []
        source_label = ""
        source_url = ""

        for line in lines:
            if line.startswith("# "):
                continue
            # Markdown-Link erkennen: — [Wikipedia](URL)
            m = re.match(r"^.*\[([^\]]+)\]\(([^)]+)\)\s*$", line)
            if m:
                source_label = f"\u2014 {m.group(1)} (anklicken zum Oeffnen)"
                source_url = m.group(2)
                continue
            body_lines.append(line)

        return "\n".join(body_lines).strip(), source_label, source_url
