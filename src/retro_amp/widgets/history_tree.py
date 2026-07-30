"""History-Tree Widget — Baum mit Wiedergabeverlauf, gruppiert nach Tagen."""

from __future__ import annotations

from pathlib import Path

from textual.binding import Binding
from textual.message import Message
from textual.widgets import Tree

from ..i18n import t
from ..services.history_service import (
    GROUP_OLDER,
    GROUP_THIS_WEEK,
    GROUP_TODAY,
    GROUP_YESTERDAY,
    HistoryGroup,
)
from .path_context_tree import PathContextTree

_GROUP_I18N_KEYS: dict[str, str] = {
    GROUP_TODAY: "history.group_today",
    GROUP_YESTERDAY: "history.group_yesterday",
    GROUP_THIS_WEEK: "history.group_this_week",
    GROUP_OLDER: "history.group_older",
}


class HistoryTree(PathContextTree[Path | None]):
    """Baum-Ansicht fuer den Wiedergabeverlauf.

    Zeigt die Eintraege gruppiert nach Tagen (Heute/Gestern/Diese Woche/Aelter).
    Ist der Verlauf deaktiviert, zeigt der Baum nur einen Hinweis-Knoten.
    """

    DEFAULT_CSS = """
    HistoryTree {
        width: 100%;
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("delete", "clear_history", "DEL", key_display="DEL"),
    ]

    ICON_MUSIC = "\u266a "
    ICON_CLOCK = "\U0001f552 "

    class TrackSelected(Message):
        """Track im History-Baum ausgewaehlt."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    class ClearRequested(Message):
        """Komplettloeschung des Verlaufs angefordert."""

    class ContextMenuRequested(PathContextTree.ContextMenuRequested):
        """Rechtsklick im Verlauf-Baum — eigener Handler-Name pro Baum."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(t("history.title"), **kwargs)

    def load_groups(
        self,
        groups: list[HistoryGroup],
        enabled: bool,
    ) -> None:
        """Laedt die Verlauf-Gruppen in den Baum.

        Bei ``enabled=False`` wird nur ein Hinweis angezeigt, der den User
        an die Settings verweist. Die Tab bleibt damit sichtbar, hat aber
        keine Daten.
        """
        self.clear()

        if not enabled:
            self.root.set_label(t("history.title"))
            self.root.add_leaf(t("history.disabled_hint"), data=None)
            self.root.expand()
            return

        total = sum(len(g.entries) for g in groups)
        self.root.set_label(t("history.title_count", count=total) if total else t("history.title"))

        if total == 0:
            self.root.add_leaf(t("history.empty"), data=None)
            self.root.expand()
            return

        for group in groups:
            label_key = _GROUP_I18N_KEYS.get(group.group_key, "history.group_older")
            group_label = f"{self.ICON_CLOCK}{t(label_key)} ({len(group.entries)})"
            group_node = self.root.add(group_label, data=None)
            for entry in group.entries:
                timestamp = entry.played_at.strftime("%H:%M")
                group_node.add_leaf(
                    f"{self.ICON_MUSIC}{timestamp} — {entry.name}",
                    data=entry.path,
                )
            group_node.expand()

        self.root.expand()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Track-Node ausgewaehlt — abspielen."""
        if event.node.data and isinstance(event.node.data, Path):
            self.post_message(self.TrackSelected(event.node.data))

    def action_clear_history(self) -> None:
        """Verlauf komplett loeschen."""
        self.post_message(self.ClearRequested())
