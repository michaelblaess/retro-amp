"""Uebersicht der aktuell geltenden Tastenbelegung.

Die Seite fuehrt keine eigene Liste - sie stellt dar, was `keymap.resolve()`
aus Stil, Vim-Schalter und eigenen Belegungen gemacht hat. Damit stimmt sie
zwangslaeufig mit dem ueberein, was die Anwendung tatsaechlich gebunden hat.
Eine gepflegte Liste danebenzustellen wuerde frueher oder spaeter abweichen,
und niemand merkte es.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static
from textual_widgets.keymap import KeymapStyle, ResolvedKeymap

from ..i18n import t
from ..keymap import LABEL_KEYS, key_display


class KeymapScreen(ModalScreen[None]):
    """Zeigt Taste und Aktion der aktiven Belegung."""

    DEFAULT_CSS = """
    KeymapScreen {
        align: center middle;
    }

    KeymapScreen > Vertical {
        width: 72;
        max-width: 90%;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    KeymapScreen #keymap-title {
        text-align: center;
        text-style: bold;
        color: $primary;
    }

    KeymapScreen #keymap-mode {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    KeymapScreen DataTable {
        height: auto;
        max-height: 20;
    }

    KeymapScreen #keymap-close {
        margin-top: 1;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Esc"),
        Binding("q", "dismiss", "q", show=False),
    ]

    def __init__(self, resolved: ResolvedKeymap, style: KeymapStyle, vim: bool) -> None:
        super().__init__()
        self._resolved = resolved
        self._style = style
        self._vim = vim

    def compose(self) -> ComposeResult:
        """Baut Titel, Modus-Zeile, Tabelle und den Schliessen-Knopf."""
        stil_text = t(f"keymap.style_{self._style.value}")
        vim_text = t("keymap.vim_on") if self._vim else t("keymap.vim_off")

        with Vertical():
            yield Static(t("keymap.title"), id="keymap-title")
            yield Static(f"{stil_text} - {vim_text}", id="keymap-mode")
            with VerticalScroll():
                yield DataTable(id="keymap-table", cursor_type="row", zebra_stripes=True)
            yield Button(t("keymap.close"), variant="primary", id="keymap-close")

    def on_mount(self) -> None:
        """Fuellt die Tabelle aus der aufgeloesten Belegung."""
        tabelle = self.query_one("#keymap-table", DataTable)
        tabelle.add_column(t("keymap.column_keys"), width=22)
        tabelle.add_column(t("keymap.column_action"))

        for action, binding in self._resolved.bindings.items():
            tasten = " / ".join(key_display(taste) for taste in binding.keys)
            beschriftung = t(LABEL_KEYS.get(action, action))
            if not binding.show:
                beschriftung = f"{beschriftung}  ({t('keymap.hidden')})"
            tabelle.add_row(tasten, beschriftung)

        self.set_focus(self.query_one("#keymap-close", Button))

    @on(Button.Pressed, "#keymap-close")
    def _on_close(self) -> None:
        """Schliesst die Uebersicht."""
        self.dismiss(None)
