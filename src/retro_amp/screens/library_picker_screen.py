"""Library-Picker-Screen — fragt beim ersten Start nach dem Musik-Verzeichnis."""
from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ..i18n import t


class LibraryPickerScreen(ModalScreen[Path | None]):
    """Modal-Dialog zur Auswahl des Musik-Verzeichnisses.

    Wird beim ersten Start angezeigt, wenn kein music_library gespeichert ist
    und kein CLI-Pfad uebergeben wurde. Gibt den gewaehlten Path zurueck.
    """

    DEFAULT_CSS = """
    LibraryPickerScreen {
        align: center middle;
    }
    LibraryPickerScreen #dialog {
        width: 70;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    LibraryPickerScreen #dialog-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        padding-bottom: 1;
    }
    LibraryPickerScreen #dialog-hint {
        color: $text-muted;
        padding-bottom: 1;
    }
    LibraryPickerScreen .pick-button {
        width: 100%;
        margin-bottom: 1;
    }
    LibraryPickerScreen #separator {
        color: $text-muted;
        content-align: center middle;
        padding: 0 0 1 0;
    }
    LibraryPickerScreen #custom-path {
        margin-bottom: 1;
    }
    LibraryPickerScreen #error-label {
        color: $error;
        height: auto;
        display: none;
    }
    LibraryPickerScreen #error-label.visible {
        display: block;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "ESC"),
    ]

    def __init__(self, candidates: list[Path]) -> None:
        super().__init__()
        self._candidates = candidates

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(t("library.title"), id="dialog-title")
            yield Label(
                t("library.hint"),
                id="dialog-hint",
            )
            for idx, path in enumerate(self._candidates):
                yield Button(
                    str(path),
                    id=f"btn-candidate-{idx}",
                    variant="primary",
                    classes="pick-button",
                )
            yield Static(t("library.separator"), id="separator")
            yield Input(
                placeholder=t("library.placeholder"),
                id="custom-path",
            )
            yield Button(
                t("library.btn_accept"),
                id="btn-custom",
                variant="success",
                classes="pick-button",
            )
            yield Label("", id="error-label")

    @on(Button.Pressed, ".pick-button")
    def _on_button(self, event: Button.Pressed) -> None:
        """Kandidaten-Button oder Uebernehmen-Button gedrueckt."""
        if event.button.id == "btn-custom":
            self._accept_custom()
            return
        # Kandidaten-Button: Index aus ID extrahieren
        idx_str = (event.button.id or "").replace("btn-candidate-", "")
        if idx_str.isdigit():
            idx = int(idx_str)
            if 0 <= idx < len(self._candidates):
                self.dismiss(self._candidates[idx])

    @on(Input.Submitted, "#custom-path")
    def _on_input_submitted(self) -> None:
        """Enter im Textfeld — Pfad uebernehmen."""
        self._accept_custom()

    def _accept_custom(self) -> None:
        """Prueft und uebernimmt den eingegebenen Pfad."""
        raw = self.query_one("#custom-path", Input).value.strip()
        error_label = self.query_one("#error-label", Label)

        if not raw:
            error_label.update(t("library.error_empty"))
            error_label.add_class("visible")
            return

        path = Path(raw).expanduser().resolve()
        if not path.is_dir():
            error_label.update(t("library.error_not_found", path=path))
            error_label.add_class("visible")
            return

        self.dismiss(path)

    def action_cancel(self) -> None:
        """Dialog abbrechen ohne Aenderung."""
        self.dismiss(None)
