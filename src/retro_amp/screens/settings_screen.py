"""Settings-Screen — Modal-Dialog fuer Einstellungen mit Tabs."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Label, Select, Static, TabbedContent, TabPane

from ..i18n import t


# Resultat-Typ des Dialogs: enthaelt beide Dicts (settings.json + DB-Settings)
SettingsResult = dict[str, dict[str, object]]

_JOURNAL_MODES: tuple[str, ...] = ("DELETE", "WAL", "TRUNCATE", "PERSIST", "MEMORY", "OFF")


class SettingsScreen(ModalScreen[SettingsResult | None]):
    """Modal-Dialog fuer retro-amp Einstellungen.

    Gibt ein Dict mit zwei Keys zurueck (oder None bei Abbruch):
      - ``settings``: Werte fuer settings.json (Theme, Cover-Renderer, ...)
      - ``db_settings``: Werte fuer die DB-settings-Tabelle (journal_mode, ...)

    Die App ist verantwortlich fuer das Speichern in den jeweiligen Stores.
    """

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }
    SettingsScreen > Vertical {
        width: 90%;
        max-width: 100;
        height: 80%;
        max-height: 30;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    SettingsScreen #title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    SettingsScreen TabbedContent {
        height: 1fr;
    }
    SettingsScreen .form-row {
        height: auto;
        margin-bottom: 1;
    }
    SettingsScreen .form-row Label {
        width: 22;
        padding: 0 1;
    }
    SettingsScreen .hint {
        color: $text-muted;
        padding: 1 2;
        margin-top: 1;
        border: round $surface-lighten-2;
    }
    SettingsScreen .credit {
        color: $text-muted;
        padding: 0 2;
        margin-top: 1;
        text-align: center;
    }
    SettingsScreen .button-row {
        height: 3;
        margin-top: 1;
        align: center middle;
        dock: bottom;
    }
    SettingsScreen Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(
        self,
        settings: dict[str, object],
        db_settings: dict[str, object] | None = None,
    ) -> None:
        super().__init__()
        self._settings = dict(settings)
        self._db_settings = dict(db_settings or {})
        self._cover_renderer = str(settings.get("cover_renderer", "halfblock"))
        self._journal_mode = str(self._db_settings.get("db_journal_mode", "DELETE")).upper()
        if self._journal_mode not in _JOURNAL_MODES:
            self._journal_mode = "DELETE"

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(t("settings.title"), id="title")

            with TabbedContent():
                with TabPane(t("settings.tab_cover"), id="tab-cover"):
                    with VerticalScroll():
                        yield from self._cover_fields()
                with TabPane(t("settings.tab_database"), id="tab-database"):
                    with VerticalScroll():
                        yield from self._database_fields()

            with Horizontal(classes="button-row"):
                yield Button(
                    t("settings.btn_save"),
                    variant="primary",
                    id="btn-save",
                )
                yield Button(
                    t("settings.btn_cancel"),
                    variant="default",
                    id="btn-cancel",
                )

    def _cover_fields(self) -> ComposeResult:
        """Felder fuer den Cover-Tab."""
        with Horizontal(classes="form-row"):
            yield Label(t("settings.cover_graphics_label"))
            yield Checkbox(
                t("settings.cover_graphics_checkbox"),
                value=(self._cover_renderer == "graphics"),
                id="check-cover-graphics",
            )
        yield Static(t("settings.cover_graphics_hint"), classes="hint")
        yield Static(
            t("settings.cover_graphics_credit"),
            classes="credit",
            markup=True,
        )

    def _database_fields(self) -> ComposeResult:
        """Felder fuer den Datenbank-Tab."""
        with Horizontal(classes="form-row"):
            yield Label(t("settings.db_journal_label"))
            yield Select[str](
                options=[(mode, mode) for mode in _JOURNAL_MODES],
                value=self._journal_mode,
                allow_blank=False,
                id="select-journal-mode",
            )
        yield Static(t("settings.db_journal_hint"), classes="hint")

    @on(Button.Pressed, "#btn-save")
    def _on_save(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#btn-cancel")
    def _on_cancel(self) -> None:
        self.action_cancel()

    def action_save(self) -> None:
        """Sammelt alle Werte und schliesst den Dialog mit beiden Settings-Dicts."""
        graphics_enabled = self._get_checkbox("check-cover-graphics")
        self._settings["cover_renderer"] = "graphics" if graphics_enabled else "halfblock"

        journal_mode = self._get_select_value("select-journal-mode", self._journal_mode)
        if journal_mode not in _JOURNAL_MODES:
            journal_mode = "DELETE"
        self._db_settings["db_journal_mode"] = journal_mode

        self.dismiss({"settings": self._settings, "db_settings": self._db_settings})

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _get_checkbox(self, checkbox_id: str) -> bool:
        try:
            return self.query_one(f"#{checkbox_id}", Checkbox).value
        except Exception:
            return False

    def _get_select_value(self, select_id: str, fallback: str) -> str:
        try:
            value = self.query_one(f"#{select_id}", Select).value
            return str(value) if value is not Select.BLANK else fallback
        except Exception:
            return fallback
