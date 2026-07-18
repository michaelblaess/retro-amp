"""Vorschau-Dialog fuer Auto-Titel - zeigt alle geplanten Umbenennungen.

Jede Zeile: Auswahl-Marker, alter Name, neuer Name, Quelle/Sicherheit.
Bestaetigte Treffer (ID3/AcoustID) sind vorausgewaehlt, heuristische
(MusicBrainz-Trackliste) nicht. Zeilen ohne Treffer sind grau und nicht
anwaehlbar. Gibt die akzeptierten Vorschlaege zurueck (oder None bei Abbruch).
"""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static
from textual.widgets.data_table import ColumnKey

from ..domain.models import MatchSource, TitleProposal
from ..i18n import t

# Farbe pro Quelle (Sicherheit signalisieren).
_SOURCE_STYLE: dict[MatchSource, str] = {
    MatchSource.ID3: "bold green",
    MatchSource.ACOUSTID: "bold green",
    MatchSource.MUSICBRAINZ: "yellow",
    MatchSource.FILENAME: "yellow",
    MatchSource.NONE: "dim",
}


class TagPreviewScreen(ModalScreen[list[TitleProposal] | None]):
    """Batch-Vorschau der Titel-Aenderungen mit Bestaetigen/Abbrechen."""

    DEFAULT_CSS = """
    TagPreviewScreen {
        align: center middle;
    }
    TagPreviewScreen #dialog {
        width: 90%;
        max-width: 120;
        height: auto;
        max-height: 90%;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    TagPreviewScreen #dialog-title {
        text-style: bold;
        color: $accent;
        width: 100%;
        content-align: center middle;
        padding-bottom: 1;
    }
    TagPreviewScreen #preview-table {
        height: auto;
        max-height: 24;
    }
    TagPreviewScreen #preview-hint {
        color: $text-muted;
        padding: 1 0 0 0;
    }
    TagPreviewScreen #button-row {
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    TagPreviewScreen #button-row Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "ESC"),
        Binding("space", "toggle_row", "Toggle"),
        Binding("ctrl+s", "confirm", "Bestaetigen"),
    ]

    def __init__(self, proposals: list[TitleProposal]) -> None:
        super().__init__()
        self._proposals = proposals
        self._col_keys: list[ColumnKey] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(t("tag_preview.title"), id="dialog-title")
            table: DataTable[Text] = DataTable(
                id="preview-table",
                cursor_type="row",
                zebra_stripes=True,
            )
            yield table
            yield Static("", id="preview-hint")
            with Horizontal(id="button-row"):
                yield Button(t("tag_preview.btn_confirm"), variant="primary", id="btn-confirm")
                yield Button(t("tag_preview.btn_toggle_all"), variant="default", id="btn-toggle-all")
                yield Button(t("tag_preview.btn_cancel"), variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        table = self.query_one("#preview-table", DataTable)
        self._col_keys = list(
            table.add_columns(
                t("tag_preview.col_sel"),
                t("tag_preview.col_old"),
                t("tag_preview.col_new"),
                t("tag_preview.col_source"),
            )
        )
        for index, proposal in enumerate(self._proposals):
            table.add_row(*self._row_cells(proposal), key=str(index))
        self._update_hint()

    def _row_cells(self, proposal: TitleProposal) -> tuple[Text, Text, Text, Text]:
        """Baut die vier Zellen einer Zeile."""
        sel = self._sel_cell(proposal)
        old = Text(proposal.current_name)
        if proposal.has_match:
            if proposal.renames:
                new = Text(proposal.proposed_name)
            else:
                # nur Tag setzen, Dateiname bleibt
                new = Text(t("tag_preview.tag_only", title=proposal.title), style="italic")
            source = Text(self._source_label(proposal.source), style=_SOURCE_STYLE[proposal.source])
        else:
            new = Text(t("tag_preview.no_match"), style="dim")
            source = Text("-", style="dim")
            old.stylize("dim")
        return sel, old, new, source

    def _sel_cell(self, proposal: TitleProposal) -> Text:
        """Auswahl-Marker: [x]/[ ] fuer Treffer, - fuer Nicht-Treffer."""
        if not proposal.has_match:
            return Text("-", style="dim")
        if proposal.selected:
            return Text("[x]", style=_SOURCE_STYLE[proposal.source])
        return Text("[ ]")

    @staticmethod
    def _source_label(source: MatchSource) -> str:
        return {
            MatchSource.ID3: t("tag_preview.source_id3"),
            MatchSource.ACOUSTID: t("tag_preview.source_acoustid"),
            MatchSource.MUSICBRAINZ: t("tag_preview.source_musicbrainz"),
            MatchSource.FILENAME: t("tag_preview.source_filename"),
        }.get(source, "")

    def _redraw_sel(self, index: int) -> None:
        """Aktualisiert nur die Auswahl-Zelle einer Zeile."""
        table = self.query_one("#preview-table", DataTable)
        table.update_cell(str(index), self._col_keys[0], self._sel_cell(self._proposals[index]))

    def _update_hint(self) -> None:
        matched = sum(1 for p in self._proposals if p.has_match)
        selected = sum(1 for p in self._proposals if p.has_match and p.selected)
        hint = self.query_one("#preview-hint", Static)
        hint.update(t("tag_preview.hint", selected=selected, matched=matched, total=len(self._proposals)))

    def action_toggle_row(self) -> None:
        """Schaltet die Auswahl der Zeile unter dem Cursor um."""
        table = self.query_one("#preview-table", DataTable)
        index = table.cursor_row
        if not (0 <= index < len(self._proposals)):
            return
        proposal = self._proposals[index]
        if not proposal.has_match:
            return
        proposal.selected = not proposal.selected
        self._redraw_sel(index)
        self._update_hint()

    @on(Button.Pressed, "#btn-toggle-all")
    def _on_toggle_all(self) -> None:
        """Alle Treffer an- oder abwaehlen (invertiert die aktuelle Mehrheit)."""
        matchable = [p for p in self._proposals if p.has_match]
        if not matchable:
            return
        target = not all(p.selected for p in matchable)
        for index, proposal in enumerate(self._proposals):
            if proposal.has_match and proposal.selected != target:
                proposal.selected = target
                self._redraw_sel(index)
        self._update_hint()

    @on(Button.Pressed, "#btn-confirm")
    def _on_confirm(self) -> None:
        self.action_confirm()

    @on(Button.Pressed, "#btn-cancel")
    def _on_cancel(self) -> None:
        self.action_cancel()

    def action_confirm(self) -> None:
        accepted = [p for p in self._proposals if p.has_match and p.selected]
        self.dismiss(accepted)

    def action_cancel(self) -> None:
        self.dismiss(None)
