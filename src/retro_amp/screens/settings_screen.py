"""Settings-Screen — Modal-Dialog fuer Einstellungen.

Erbt von ``BaseSettingsScreen`` (textual-widgets): liefert Titel, Sprach-Tab,
Speicherort-Tab, Save/Cancel-Leiste und die Standard-Bindings. Die App-Tabs
(Cover, Visualizer, Datenbank, Verlauf) ergaenzt diese Klasse ueber den
``app_tabs()``-Hook; die Werte sammelt ``collect_app_settings()`` ein.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, Input, Label, Select, Static, TabPane
from textual_widgets import BaseSettingsScreen

from ..domain.models import VisualizerMode
from ..i18n import t

_JOURNAL_MODES: tuple[str, ...] = ("DELETE", "WAL", "TRUNCATE", "PERSIST", "MEMORY", "OFF")
_VISUALIZER_MODES: tuple[VisualizerMode, ...] = (
    VisualizerMode.BARS,
    VisualizerMode.BLOCKS,
    VisualizerMode.SCOPE,
    VisualizerMode.MATRIX,
    VisualizerMode.LCD,
)

# Verzeichnis, in dem retro-amp alle Nutzerdaten ablegt.
_DATA_DIR = Path.home() / ".retro-amp"


class SettingsScreen(BaseSettingsScreen):  # type: ignore[misc]
    """retro-amp Settings-Dialog auf Basis von ``BaseSettingsScreen``.

    Das uebergebene ``settings``-Dict (settings.json) wird mit den
    ``db_settings`` zu einem flachen Dict gemerged — die DB-Schluessel
    (``db_journal_mode``, ``history_enabled``, ``history_limit``) kollidieren
    nicht mit den settings.json-Schluesseln. Die App trennt das Ergebnis im
    Callback wieder auf und speichert in den jeweiligen Stores.
    """

    DEFAULT_CSS = """
    SettingsScreen .credit {
        color: $text-muted;
        padding: 0 2;
        margin-top: 1;
        text-align: center;
    }
    """

    def __init__(
        self,
        settings: dict[str, object],
        db_settings: dict[str, object] | None = None,
        on_clear_history: Callable[[], int] | None = None,
        lang: str = "de",
    ) -> None:
        merged = dict(settings)
        merged.update(db_settings or {})
        super().__init__(merged, lang=lang)
        self._on_clear_history = on_clear_history

        self._cover_renderer = str(merged.get("cover_renderer", "halfblock"))
        try:
            self._visualizer_mode = VisualizerMode(
                str(merged.get("visualizer_mode", VisualizerMode.BARS.value)),
            )
        except ValueError:
            self._visualizer_mode = VisualizerMode.BARS
        self._journal_mode = str(merged.get("db_journal_mode", "DELETE")).upper()
        if self._journal_mode not in _JOURNAL_MODES:
            self._journal_mode = "DELETE"
        self._history_enabled = bool(merged.get("history_enabled", False))
        try:
            self._history_limit = int(str(merged.get("history_limit", 1000)))
        except (TypeError, ValueError):
            self._history_limit = 1000

    # --- Hooks von BaseSettingsScreen ---

    def app_tabs(self) -> ComposeResult:
        """App-spezifische Tabs: Cover, Visualizer, Datenbank, Verlauf."""
        with TabPane(t("settings.tab_cover"), id="tab-cover"), VerticalScroll():
            yield from self._cover_fields()
        with TabPane(t("settings.tab_visualizer"), id="tab-visualizer"), VerticalScroll():
            yield from self._visualizer_fields()
        with TabPane(t("settings.tab_database"), id="tab-database"), VerticalScroll():
            yield from self._database_fields()
        with TabPane(t("settings.tab_history"), id="tab-history"), VerticalScroll():
            yield from self._history_fields()

    def collect_app_settings(self, settings: dict[str, object]) -> None:
        """Sammelt die Werte der App-Tabs ins Ergebnis-Dict."""
        graphics_enabled = self._get_checkbox("check-cover-graphics")
        settings["cover_renderer"] = "graphics" if graphics_enabled else "halfblock"

        visualizer_mode = self._get_select_value(
            "select-visualizer-mode",
            self._visualizer_mode.value,
        )
        try:
            VisualizerMode(visualizer_mode)
        except ValueError:
            visualizer_mode = VisualizerMode.BARS.value
        settings["visualizer_mode"] = visualizer_mode

        journal_mode = self._get_select_value("select-journal-mode", self._journal_mode)
        if journal_mode not in _JOURNAL_MODES:
            journal_mode = "DELETE"
        settings["db_journal_mode"] = journal_mode

        settings["history_enabled"] = self._get_checkbox("check-history-enabled")
        settings["history_limit"] = self._get_int_input(
            "input-history-limit",
            self._history_limit,
            minimum=10,
            maximum=1_000_000,
        )

    def storage_paths(self) -> list[tuple[str, Path]]:
        """Speicherorte fuer den Speicherort-Tab."""
        return [
            (t("settings.storage_settings"), _DATA_DIR / "settings.json"),
            (t("settings.storage_database"), _DATA_DIR / "retro-amp.db"),
            (t("settings.storage_lyrics"), _DATA_DIR / "lyrics"),
            (t("settings.storage_notes"), _DATA_DIR / "notes"),
        ]

    # --- Feld-Builder ---

    def _cover_fields(self) -> ComposeResult:
        """Felder fuer den Cover-Tab."""
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.cover_graphics_label"))
            yield Checkbox(
                t("settings.cover_graphics_checkbox"),
                value=(self._cover_renderer == "graphics"),
                id="check-cover-graphics",
            )
        yield Static(t("settings.cover_graphics_hint"), classes="settings-hint")
        yield Static(
            t("settings.cover_graphics_credit"),
            classes="credit",
            markup=True,
        )

    def _visualizer_fields(self) -> ComposeResult:
        """Felder fuer den Visualizer-Tab."""
        options: list[tuple[str, str]] = [
            (t(f"visualizer.mode_{mode.value}"), mode.value) for mode in _VISUALIZER_MODES
        ]
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.visualizer_mode_label"))
            yield Select[str](
                options=options,
                value=self._visualizer_mode.value,
                allow_blank=False,
                id="select-visualizer-mode",
            )
        yield Static(t("settings.visualizer_mode_hint"), classes="settings-hint")

    def _database_fields(self) -> ComposeResult:
        """Felder fuer den Datenbank-Tab."""
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.db_journal_label"))
            yield Select[str](
                options=[(mode, mode) for mode in _JOURNAL_MODES],
                value=self._journal_mode,
                allow_blank=False,
                id="select-journal-mode",
            )
        yield Static(t("settings.db_journal_hint"), classes="settings-hint")

    def _history_fields(self) -> ComposeResult:
        """Felder fuer den Verlauf-Tab."""
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.history_enable_label"))
            yield Checkbox(
                t("settings.history_enable_checkbox"),
                value=self._history_enabled,
                id="check-history-enabled",
            )
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.history_limit_label"))
            yield Input(
                value=str(self._history_limit),
                type="integer",
                id="input-history-limit",
            )
        with Horizontal(classes="settings-row"):
            yield Label("")
            yield Button(
                t("settings.history_clear_button"),
                variant="warning",
                id="btn-clear-history",
            )
        yield Static(t("settings.history_hint"), classes="settings-hint")

    # --- Button-Handling ---

    @on(Button.Pressed, "#btn-clear-history")
    def _on_clear_history_pressed(self) -> None:
        """Verlauf sofort loeschen (ohne Dialog zu schliessen).

        Eigener `@on`-Handler statt eines `on_button_pressed`-Overrides:
        Textual ruft `on_button_pressed` ueber die gesamte MRO auf, ein
        Override duerfte daher kein `super()` rufen. Die Basis ignoriert
        unbekannte Button-IDs (ab textual-widgets 0.25.0), sodass dieser
        Klick den Dialog nicht schliesst.
        """
        if self._on_clear_history is None:
            return
        try:
            count = self._on_clear_history()
        except Exception:
            count = 0
        self.app.notify(
            t("settings.history_cleared", count=count),
            severity="information",
        )

    # --- Widget-Wert-Helfer ---

    def _get_checkbox(self, checkbox_id: str) -> bool:
        try:
            return bool(self.query_one(f"#{checkbox_id}", Checkbox).value)
        except Exception:
            return False

    def _get_select_value(self, select_id: str, fallback: str) -> str:
        try:
            value = self.query_one(f"#{select_id}", Select).value
            return str(value) if value is not Select.BLANK else fallback
        except Exception:
            return fallback

    def _get_int_input(
        self,
        input_id: str,
        fallback: int,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            raw = self.query_one(f"#{input_id}", Input).value.strip()
            if not raw:
                return fallback
            value = int(raw)
        except (ValueError, Exception):
            return fallback
        return max(minimum, min(maximum, value))
