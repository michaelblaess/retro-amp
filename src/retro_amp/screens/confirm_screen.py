"""Confirm-Screen — Modal fuer Bestaetigungsdialoge."""
from __future__ import annotations

import logging
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

logger = logging.getLogger(__name__)


class ConfirmScreen(ModalScreen[Path | None]):
    """Modal-Dialog fuer Loeschbestaetigung.

    Gibt den geloeschten Path zurueck oder None bei Abbruch.
    """

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    ConfirmScreen #dialog {
        width: 50;
        height: auto;
        border: solid $error;
        background: $surface;
        padding: 1 2;
    }
    ConfirmScreen #dialog-title {
        text-style: bold;
        color: $error;
        width: 100%;
        content-align: center middle;
        padding-bottom: 1;
    }
    ConfirmScreen #message {
        width: 100%;
        padding-bottom: 1;
    }
    ConfirmScreen #button-row {
        layout: horizontal;
        height: 3;
        align: center middle;
    }
    ConfirmScreen #btn-confirm {
        margin-right: 2;
    }
    """

    BINDINGS = [
        Binding("escape,q", "close", "Abbrechen"),
        Binding("j", "confirm", "Ja"),
    ]

    def __init__(self, message: str, file_path: Path) -> None:
        super().__init__()
        self._message = message
        self._file_path = file_path

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Loeschen", id="dialog-title")
            yield Label(self._message, id="message")
            with Horizontal(id="button-row"):
                yield Button(
                    "Ja, loeschen (j)", id="btn-confirm", variant="error"
                )
                yield Button("Abbrechen (q)", id="btn-close", variant="default")

    @on(Button.Pressed, "#btn-confirm")
    def _on_confirm(self) -> None:
        self._delete()

    @on(Button.Pressed, "#btn-close")
    def _on_close(self) -> None:
        self.dismiss(None)

    def _delete(self) -> None:
        """Datei loeschen."""
        try:
            self._file_path.unlink()
            self.dismiss(self._file_path)
        except OSError as e:
            logger.exception("Fehler beim Loeschen")
            self.notify(f"Fehler: {e}", severity="error")

    def action_close(self) -> None:
        self.dismiss(None)

    def action_confirm(self) -> None:
        self._delete()
