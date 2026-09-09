"""Die Vim-Ebene fuer die navigierbaren Widgets dieser Anwendung.

`textual_widgets.keymap.VIM_NAVIGATION` beschreibt die Ebene fuer eine
`DataTable` - dort gibt es alle acht Aktionen fertig. Ein `Tree` hat sie nicht:
gemessen an Textual 8.2.6 kennt er `cursor_up`, `cursor_down`, `page_up` und
`page_down`, aber weder `cursor_left`/`cursor_right` noch
`scroll_top`/`scroll_bottom`. Die Tabelle unten uebersetzt deshalb auf das,
was ein Baum wirklich kann, und die Mischklasse ergaenzt die zwei fehlenden
Sprungaktionen.

Beides haengt am **Widget** und nicht an der App: die Ebene soll nur gelten,
solange das Widget den Fokus hat. Genau daraus folgt aber auch, dass sie
gleichnamige Aktionen der App verdeckt - `l` und `g` sind fuer die App weg,
solange die Vim-Ebene laeuft. `resolve_keymap()` meldet das ins Log.

Public API:
    - `TREE_VIM_BINDINGS` - Taste auf Aktionsname fuer einen `Tree`.
    - `VimTreeNavigation` - Mischklasse fuer Baum-Widgets.
    - `VimTableNavigation` - Mischklasse fuer `DataTable`-Widgets.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual_widgets.keymap import vim_navigation_bindings

TREE_VIM_BINDINGS: tuple[tuple[str, str], ...] = (
    ("k", "cursor_up"),
    ("j", "cursor_down"),
    # Im Baum ist "nach links" der Elternknoten und "nach rechts" das Aufklappen.
    ("h", "cursor_parent"),
    ("l", "toggle_node"),
    ("g", "cursor_first"),
    ("G", "cursor_last"),
    ("ctrl+u", "page_up"),
    ("ctrl+d", "page_down"),
)
"""Die Vim-Tasten eines Baums, uebersetzt auf seine tatsaechlichen Aktionen.

Die Pfeiltasten und `pageup`/`pagedown` fehlen bewusst - die hat Textual schon.
"""


class _VimBasis:
    """Gemeinsamer Teil: die Ebene nur einhaengen, wenn sie eingeschaltet ist."""

    def _vim_gewuenscht(self) -> bool:
        """Fragt die App, ob der Anwender die Vim-Navigation eingeschaltet hat.

        Returns:
            False auch dann, wenn das Widget in einer App ohne diese
            Eigenschaft haengt - die Tests bauen solche Apps.
        """

        return bool(getattr(self.app, "vim_navigation", False))  # type: ignore[attr-defined]


class VimTableNavigation(_VimBasis):
    """Vim-Ebene fuer ein `DataTable`-Widget.

    Alle acht Aktionen bringt die `DataTable` selbst mit, es genuegt also die
    Tabelle aus `textual_widgets`.
    """

    def _on_mount(self, event: Any) -> None:
        """Haengt die Vim-Navigation ein, wenn der Anwender sie will.

        Bewusst `_on_mount` und nicht `on_mount`: In Textual laeuft jeder
        `_on_*`-Haken der MRO, ein oeffentliches `on_mount` wuerde dagegen das
        einer Ableitung verdecken.

        Args:
            event: Das Mount-Ereignis, unbenutzt.
        """

        if not self._vim_gewuenscht():
            return
        for taste, aktion in vim_navigation_bindings():
            self._bindings.bind(taste, aktion, show=False)  # type: ignore[attr-defined]


class VimTreeNavigation(_VimBasis):
    """Vim-Ebene fuer ein `Tree`-Widget, samt der zwei fehlenden Aktionen."""

    if TYPE_CHECKING:
        # Kommt vom Tree, an den diese Mischklasse gehaengt wird. Nur fuer die
        # Typpruefung deklariert - zur Laufzeit gehoert das Attribut dem Tree.
        cursor_line: int
        last_line: int

    def _on_mount(self, event: Any) -> None:
        """Haengt die Vim-Navigation ein, wenn der Anwender sie will.

        Args:
            event: Das Mount-Ereignis, unbenutzt.
        """

        if not self._vim_gewuenscht():
            return
        for taste, aktion in TREE_VIM_BINDINGS:
            self._bindings.bind(taste, aktion, show=False)  # type: ignore[attr-defined]

    def action_cursor_first(self) -> None:
        """Setzt den Zeiger auf die erste Zeile.

        `Tree` hat dafuer nichts - `scroll_home` verschiebt nur die Ansicht und
        laesst den Zeiger stehen. In vim springt `gg` aber den Zeiger, nicht das
        Fenster.
        """

        self.cursor_line = 0

    def action_cursor_last(self) -> None:
        """Setzt den Zeiger auf die letzte Zeile."""

        self.cursor_line = max(self.last_line, 0)
