"""Typisierter Zugang zu ``mutagen.File``.

mutagen exportiert ``File`` nicht explizit und die Funktion ist nicht
annotiert. Dieser Wrapper kapselt den Cast an einer Stelle.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast


def open_audio_file(path: str, *, easy: bool = False) -> Any:
    """Oeffnet eine Audiodatei mit ``mutagen.File``.

    Args:
        path: Pfad zur Audiodatei.
        easy: Easy-Schnittstelle von mutagen verwenden.

    Returns:
        Das mutagen-Dateiobjekt oder ``None``, wenn das Format unbekannt ist.
    """
    # Lazy Import wie an den bisherigen Aufrufstellen (Startzeit). Oeffentliche
    # Funktion statt mutagen._file, mutagen exportiert sie nur nicht explizit.
    from mutagen import File  # type: ignore[attr-defined]

    return cast("Callable[..., Any]", File)(path, easy=easy)
