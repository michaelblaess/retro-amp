"""Search Panel — globale Dateisuche mit klickbaren Ergebnissen."""
from __future__ import annotations

import webbrowser
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import LoadingIndicator, Static


_AUDIO_EXTENSIONS = {".mp3", ".ogg", ".opus", ".flac", ".wav"}


class _SearchResult(Static, can_focus=True):
    """Klickbares Suchergebnis."""

    DEFAULT_CSS = """
    _SearchResult {
        height: auto;
        padding: 0 1;
        color: $text;
    }
    _SearchResult:hover {
        text-style: bold;
        color: $accent;
    }
    _SearchResult:focus {
        text-style: bold;
        color: $accent;
    }
    """

    BINDINGS = [("enter", "select_result", "Oeffnen")]

    class Selected(Message):
        """Wird gesendet wenn ein Suchergebnis gewaehlt wird."""
        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def __init__(self, path: Path, display: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._path = path
        self._display = display

    def on_mount(self) -> None:
        self.update(self._display)

    def on_click(self) -> None:
        self.post_message(self.Selected(self._path))

    def action_select_result(self) -> None:
        self.post_message(self.Selected(self._path))


class SearchPanel(Widget):
    """Panel fuer Suchergebnisse."""

    DEFAULT_CSS = """
    SearchPanel {
        width: 100%;
        height: 1fr;
    }
    SearchPanel #search-scroll {
        height: 100%;
        padding: 0 1;
    }
    SearchPanel #search-status {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    SearchPanel #search-loading {
        height: 3;
        display: none;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="search-scroll"):
            yield Static("", id="search-status")
            yield LoadingIndicator(id="search-loading")

    def show_loading(self, query: str) -> None:
        """Zeigt Lade-Zustand an."""
        for old in list(self.query("_SearchResult")):
            old.remove()
        self.query_one("#search-status", Static).update(
            f"\U0001f50d Suche nach \"{query}\" ..."
        )
        self.query_one("#search-loading", LoadingIndicator).display = True

    def display_results(
        self, query: str, results: list[tuple[Path, str]],
    ) -> None:
        """Zeigt vorberechnete Suchergebnisse an."""
        self.query_one("#search-loading", LoadingIndicator).display = False
        status = self.query_one("#search-status", Static)
        scroll = self.query_one("#search-scroll", VerticalScroll)

        if results:
            status.update(
                f"\U0001f50d \"{query}\" \u2014 {len(results)} Treffer"
            )
            for path, display in results:
                scroll.mount(_SearchResult(path, display))
        else:
            status.update(f"\U0001f50d \"{query}\" \u2014 keine Treffer")

    def show_results(self, query: str, root: Path) -> None:
        """Sucht rekursiv und zeigt Ergebnisse an."""
        status = self.query_one("#search-status", Static)
        scroll = self.query_one("#search-scroll", VerticalScroll)

        # Alte Ergebnisse entfernen
        for old in list(self.query("_SearchResult")):
            old.remove()

        status.update(f"Suche nach \"{query}\" ...")

        # Rekursive Suche (case-insensitive)
        query_lower = query.lower()
        results: list[tuple[Path, str]] = []

        try:
            for p in sorted(root.rglob("*")):
                if query_lower in p.name.lower():
                    # Relativen Pfad zum Root berechnen
                    try:
                        rel = p.relative_to(root)
                    except ValueError:
                        rel = p
                    if p.is_dir():
                        icon = "\U0001f4c1"  # folder
                        display = f"{icon} {rel}"
                    elif p.suffix.lower() in _AUDIO_EXTENSIONS:
                        icon = "\u266a"  # music note
                        display = f"{icon} {rel}"
                    else:
                        continue  # Nur Ordner und Audio-Dateien zeigen
                    results.append((p, display))
        except PermissionError:
            pass

        if results:
            status.update(
                f"\U0001f50d \"{query}\" — {len(results)} Treffer"
            )
            for path, display in results[:200]:  # Max 200 Ergebnisse
                scroll.mount(_SearchResult(path, display))
        else:
            status.update(f"\U0001f50d \"{query}\" — keine Treffer")

    def clear(self) -> None:
        """Leert das Panel."""
        self.query_one("#search-loading", LoadingIndicator).display = False
        self.query_one("#search-status", Static).update("")
        for old in list(self.query("_SearchResult")):
            old.remove()
