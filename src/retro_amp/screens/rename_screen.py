"""Rename-Screen — Modal zum Umbenennen einer Datei."""
from __future__ import annotations

import logging
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

logger = logging.getLogger(__name__)


class RenameScreen(ModalScreen[Path | None]):
    """Modal-Dialog zum Umbenennen einer Audio-Datei.

    Gibt den neuen Path zurueck oder None bei Abbruch.
    """

    DEFAULT_CSS = """
    RenameScreen {
        align: center middle;
    }
    RenameScreen #dialog {
        width: 60;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    RenameScreen #dialog-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        padding-bottom: 1;
    }
    RenameScreen #new-name {
        width: 1fr;
        margin-bottom: 1;
    }
    RenameScreen #button-row {
        layout: horizontal;
        height: 3;
        align: center middle;
    }
    RenameScreen #btn-save {
        margin-right: 2;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Abbrechen"),
    ]

    def __init__(self, file_path: Path) -> None:
        super().__init__()
        self._file_path = file_path

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Datei umbenennen", id="dialog-title")
            yield Input(
                value=self._file_path.name,
                placeholder="Neuer Dateiname...",
                id="new-name",
            )
            with Horizontal(id="button-row"):
                yield Button(
                    "Umbenennen (Enter)", id="btn-save", variant="primary"
                )
                yield Button("Abbrechen (Esc)", id="btn-close", variant="default")

    def on_mount(self) -> None:
        """Input fokussieren und Text selektieren."""
        name_input = self.query_one("#new-name", Input)
        name_input.focus()
        # Nur den Dateinamen ohne Extension selektieren
        stem = self._file_path.stem
        name_input.selection = (0, len(stem))

    @on(Input.Submitted, "#new-name")
    def _on_input_submitted(self, event: Input.Submitted) -> None:
        self._save()

    @on(Button.Pressed, "#btn-save")
    def _on_save(self) -> None:
        self._save()

    @on(Button.Pressed, "#btn-close")
    def _on_close(self) -> None:
        self.dismiss(None)

    def _save(self) -> None:
        """Datei umbenennen."""
        name_input = self.query_one("#new-name", Input)
        new_name = name_input.value.strip()

        if not new_name:
            self.notify("Bitte einen Namen eingeben", severity="warning")
            return

        if new_name == self._file_path.name:
            self.dismiss(None)
            return

        new_path = self._file_path.parent / new_name

        if new_path.exists():
            self.notify(
                f"Datei '{new_name}' existiert bereits", severity="error"
            )
            return

        try:
            self._file_path.rename(new_path)
            self.dismiss(new_path)
        except OSError as e:
            logger.exception("Fehler beim Umbenennen")
            self.notify(f"Fehler: {e}", severity="error")

    def action_close(self) -> None:
        self.dismiss(None)
