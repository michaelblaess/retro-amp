"""History-Service — Wiedergabeverlauf mit Gruppierung nach Tagen.

Liest Enable-Flag und Limit aus der DB-Settings-Tabelle; schreibt nur wenn
aktiviert. Gruppiert Eintraege in ``Heute / Gestern / Diese Woche / Aelter``
fuer die Anzeige im History-Tab.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import NamedTuple

from ..domain.models import HistoryEntry
from ..domain.protocols import HistoryRepository


# Gruppen-Labels (i18n-Keys werden vom Widget aufgeloest, hier bleibt es
# sprachneutral). Die Reihenfolge entspricht der Anzeige-Reihenfolge.
GROUP_TODAY = "today"
GROUP_YESTERDAY = "yesterday"
GROUP_THIS_WEEK = "this_week"
GROUP_OLDER = "older"

DEFAULT_HISTORY_LIMIT = 1000


class HistoryGroup(NamedTuple):
    """Eine Tages-Gruppe mit ihren Eintraegen."""

    group_key: str
    entries: list[HistoryEntry]


class HistoryService:
    """Business-Logik rund um den Wiedergabeverlauf.

    Die App gibt Enable-Flag und Limit als Callables rein — so kann das
    Service jederzeit den aktuellen Zustand aus der DB-Settings-Tabelle
    lesen, ohne die Database-Klasse direkt zu kennen.
    """

    def __init__(
        self,
        repository: HistoryRepository,
        is_enabled: Callable[[], bool],
        get_limit: Callable[[], int],
    ) -> None:
        self._repo = repository
        self._is_enabled = is_enabled
        self._get_limit = get_limit

    def record_play(self, path: Path) -> None:
        """Fuegt einen Track zum Verlauf hinzu (nur wenn aktiviert)."""
        if not self._is_enabled():
            return
        self._repo.add(path)
        limit = max(0, int(self._get_limit()))
        if limit > 0:
            self._repo.trim(limit)

    def list_grouped(self) -> list[HistoryGroup]:
        """Liefert die Eintraege gruppiert nach Tagen (neuster zuerst)."""
        limit = max(0, int(self._get_limit()))
        if limit <= 0:
            limit = DEFAULT_HISTORY_LIMIT
        entries = self._repo.list_recent(limit)
        if not entries:
            return []

        today = date.today()
        yesterday = today - timedelta(days=1)
        week_start = today - timedelta(days=today.weekday())

        buckets: dict[str, list[HistoryEntry]] = {
            GROUP_TODAY: [],
            GROUP_YESTERDAY: [],
            GROUP_THIS_WEEK: [],
            GROUP_OLDER: [],
        }
        for entry in entries:
            day = entry.played_at.date()
            if day == today:
                buckets[GROUP_TODAY].append(entry)
            elif day == yesterday:
                buckets[GROUP_YESTERDAY].append(entry)
            elif day >= week_start:
                buckets[GROUP_THIS_WEEK].append(entry)
            else:
                buckets[GROUP_OLDER].append(entry)

        return [
            HistoryGroup(group_key=key, entries=items)
            for key, items in buckets.items()
            if items
        ]

    def clear_all(self) -> None:
        """Loescht den gesamten Verlauf."""
        self._repo.clear()
