"""QuickJumpSidebar — Schnellzugriff auf Standardordner und Laufwerke.

Schmale Leiste oben im Dateien-Tab mit klickbaren Zeilen fuer Home, die
persistierte Musik-Library und die XDG-Standardordner. Auf Windows
zusaetzlich alle verfuegbaren Laufwerke (``os.listdrives``-Fallback auf
``A:`` .. ``Z:``-Probe). Auf Linux/macOS werden ``/mnt/*``, ``/media/*``
und ``/Volumes/*`` abgescannt.

Klick auf einen Eintrag emittiert ``QuickJumpSidebar.PathChosen``. Die App
entscheidet, was damit passiert — typisch: Tree-Root tempotaer wechseln,
ohne die persistierte Library zu beruehren.

Hinweis zur Wahl ``Static`` statt ``Button``: ein Textual-``Button`` ist
intern ein Composite mit Label-Child und Mindesthoehe 3; bei ``height: 1``
verschluckt er das Label komplett. Static-Zeilen sind dafuer das passende
Primitiv und brauchen kein eigenes Styling-Tuning.
"""

from __future__ import annotations

import os
import string
import sys
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.events import Click
from textual.message import Message
from textual.widgets import Static

from ..i18n import t


class QuickJumpItem(Static):
    """Klickbare Sidebar-Zeile — postet auf Click ``QuickJumpSidebar.PathChosen``.

    Bewusst nur Static, kein Button: bei einzeiliger Hoehe rendern Buttons in
    Textual ihr Label nicht (interne Mindesthoehe 3). Static-Zeilen mit
    Hover-CSS sehen aus wie eine schlanke Linkleiste und funktionieren.
    """

    DEFAULT_CSS = """
    QuickJumpItem {
        width: 100%;
        height: 1;
        padding: 0 1;
        color: $text;
    }
    QuickJumpItem:hover {
        background: $primary 30%;
        color: $text;
        text-style: bold;
    }
    """

    def __init__(self, label: str, path: Path) -> None:
        super().__init__(label, markup=False)
        self.path = path
        self.label_text = label

    def on_click(self, event: Click) -> None:
        """Linksklick → PathChosen am Parent (QuickJumpSidebar) aufsteigen lassen."""
        event.stop()
        self.post_message(QuickJumpSidebar.PathChosen(self.path, self.label_text))


class QuickJumpSection(Static):
    """Abschnitts-Ueberschrift in der Sidebar (z.B. 'Laufwerke')."""

    DEFAULT_CSS = """
    QuickJumpSection {
        color: $text-muted;
        padding: 0 1;
        text-style: italic;
        height: 1;
    }
    """


class QuickJumpSidebar(VerticalScroll):
    """Sidebar-Container mit Schnellzugriff-Zeilen.

    Der Konstruktor erhaelt den aktuellen Library-Pfad; der "Musik"-Eintrag
    springt immer dorthin. Aenderungen der Default-Library zur Laufzeit
    werden ueber ``set_music_library()`` reingereicht.
    """

    DEFAULT_CSS = """
    QuickJumpSidebar {
        height: auto;
        max-height: 14;
        padding: 0;
        scrollbar-size: 1 1;
        background: $surface;
    }
    """

    class PathChosen(Message):
        """Wird gefeuert, wenn der Nutzer einen Sidebar-Eintrag waehlt.

        ``label`` ist die im Sidebar gezeigte Beschriftung (inkl. Icon) und
        wird in der App als Root-Label des FolderBrowser verwendet — so
        steht oben im Baum "📁 Downloads" statt des langen Vollpfads.
        """

        def __init__(self, path: Path, label: str) -> None:
            super().__init__()
            self.path = path
            self.label = label

    def __init__(self, music_library: Path, id: str | None = None) -> None:
        super().__init__(id=id)
        self._music_library = music_library

    # --- Compose ---

    def compose(self) -> ComposeResult:
        """Baut die Eintraege auf: Home, Musik, XDG-Ordner, Laufwerke.

        Alle Icons sind bewusst doppelt-breite Emoji aus dem Unicode-6.0-Kern
        (Segoe UI Emoji liefert sie auf Windows zuverlaessig) — so sitzen
        die Labels einheitlich an Spalte 3. Mischen von einfach- und
        doppelweiten Glyphen wuerde die Spalte zerreissen.
        """
        home = Path.home()

        yield QuickJumpItem(f"🏠 {t('sidebar.home')}", home)
        yield QuickJumpItem(f"🎶 {t('sidebar.music')}", self._music_library)

        # XDG-Standardordner — nur wenn vorhanden. Wir pruefen unter
        # Home/<englischer-Name>, weil die Anzeige uebersetzt wird, die
        # Verzeichnisnamen auf Disk aber sprachunabhaengig englisch sind.
        # Icon-Auswahl: bewusst Emoji, die Segoe UI Emoji *ohne* Variation
        # Selector als doppelweite Glyphe liefert (🖥 wuerde sonst als
        # einfach-breite Textform rendern und die Spaltenausrichtung
        # zerreissen).
        for key, sub, icon in (
            ("downloads", "Downloads", "📁"),
            ("desktop", "Desktop", "💻"),
            ("documents", "Documents", "📄"),
            ("pictures", "Pictures", "🌅"),
            ("videos", "Videos", "🎥"),
        ):
            candidate = home / sub
            if candidate.is_dir():
                yield QuickJumpItem(f"{icon} {t(f'sidebar.{key}')}", candidate)

        # Laufwerke / Mount-Points
        drives = self._discover_drives()
        if drives:
            yield QuickJumpSection(t("sidebar.drives"))
            for drive in drives:
                yield QuickJumpItem(f"💾 {drive}", drive)

    # --- Public API ---

    def set_music_library(self, library: Path) -> None:
        """Aktualisiert den Library-Pfad, auf den der 'Musik'-Eintrag springt.

        Findet den vorhandenen "Musik"-Eintrag (der zweite QuickJumpItem) und
        setzt dessen ``path`` neu. So muss der Compose-Baum nicht neu gebaut
        werden.
        """
        self._music_library = library
        items = list(self.query(QuickJumpItem))
        # Der "Musik"-Eintrag ist immer der zweite (Index 1, nach Home).
        if len(items) >= 2:
            items[1].path = library

    # --- Helpers ---

    def _discover_drives(self) -> list[Path]:
        """Findet zugaengliche Laufwerke (Windows) oder Mount-Points (Unix).

        ``os.listdrives()`` listet auch leere Card-Reader oder DVD-Slots
        ohne Medium — der Filter ``_is_accessible`` wirft die raus, indem
        er einen billigen Probe-Zugriff macht.
        """
        drives: list[Path] = []
        if sys.platform == "win32":
            list_drives = getattr(os, "listdrives", None)
            if callable(list_drives):
                try:
                    drives = [Path(d) for d in list_drives()]
                except OSError:
                    drives = []
            if not drives:
                # Fallback fuer aeltere Python-Versionen: Buchstaben durchprobieren
                drives = [Path(f"{letter}:\\") for letter in string.ascii_uppercase]
        else:
            for parent in (Path("/mnt"), Path("/media"), Path("/Volumes")):
                if parent.is_dir():
                    try:
                        drives.extend(sorted(p for p in parent.iterdir() if p.is_dir()))
                    except OSError:
                        continue
        return [d for d in drives if self._is_accessible(d)]

    @staticmethod
    def _is_accessible(path: Path) -> bool:
        """Pruefen ob ein Pfad tatsaechlich lesbar ist (verhindert tote Drive-Eintraege)."""
        try:
            # is_dir() alleine reicht nicht: Windows liefert fuer leere
            # Card-Reader True. Ein Stat-Probe-Call wirft dort OSError 21
            # (drive not ready) bzw. PermissionError.
            return path.is_dir() and os.access(str(path), os.R_OK)
        except OSError:
            return False
