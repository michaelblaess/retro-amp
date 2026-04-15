"""Settings-Screen — Modal-Dialog fuer Einstellungen mit Tabs."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Label, Static, TabbedContent, TabPane

from ..i18n import t


class SettingsScreen(ModalScreen[dict[str, object] | None]):
    """Modal-Dialog fuer retro-amp Einstellungen.

    Gibt die geaenderten Settings zurueck (oder None bei Abbruch).
    Die App ist verantwortlich fuer das Speichern via JsonSettingsStore.
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

    def __init__(self, settings: dict[str, object]) -> None:
        super().__init__()
        self._settings = dict(settings)
        self._cover_renderer = str(settings.get("cover_renderer", "halfblock"))

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(t("settings.title"), id="title")

            with TabbedContent():
                with TabPane(t("settings.tab_cover"), id="tab-cover"):
                    with VerticalScroll():
                        yield from self._cover_fields()

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

    @on(Button.Pressed, "#btn-save")
    def _on_save(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#btn-cancel")
    def _on_cancel(self) -> None:
        self.action_cancel()

    def action_save(self) -> None:
        """Sammelt alle Werte und schliesst den Dialog mit dem neuen Settings-Dict."""
        graphics_enabled = self._get_checkbox("check-cover-graphics")
        self._settings["cover_renderer"] = "graphics" if graphics_enabled else "halfblock"
        self.dismiss(self._settings)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _get_checkbox(self, checkbox_id: str) -> bool:
        try:
            return self.query_one(f"#{checkbox_id}", Checkbox).value
        except Exception:
            return False
