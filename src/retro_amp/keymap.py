"""Tastenbelegung dieser Anwendung.

Die Mechanik - Stile, Vim-Ebene, Anwenderkorrekturen, Pruefer - liegt in
`textual_widgets.keymap`. Hier steht nur, was retro-amp ausmacht: seine
Aktionen im Bestandsstil, die Zuordnung zu den Beschriftungen aus dem
Sprachpaket und die Bruecke zu den Einstellungen.

Public API:
    - `CLASSIC` - die Belegung im Bestandsstil, so wie sie bis v0.33.0 galt.
    - `LABEL_KEYS` / `TOOLTIP_KEYS` - Aktion auf i18n-Schluessel.
    - `APP_FUNCTION_KEYS` / `FUNCTION_KEYS` - die F-Tasten dieser Anwendung.
    - `key_display()` - Tastenname auf seine Anzeige im Footer.
    - `style_from_settings()` - der gewaehlte oder vorgeschlagene Stil.
    - `resolve()` - die fertige Belegung aus den Einstellungen.

Die Schluessel sind die Aktionsnamen, nicht die Beschriftungen: `t()` laeuft
erst beim Binden, damit ein Sprachwechsel ohne Neustart wirkt.
"""

from __future__ import annotations

from collections.abc import Mapping

from textual_widgets.keymap import (
    COMMON_FUNCTION_KEYS,
    KeyBinding,
    KeymapStyle,
    ResolvedKeymap,
    default_style_for_platform,
    parse_overrides,
    resolve_keymap,
    sort_for_footer,
)

CLASSIC: dict[str, KeyBinding] = {
    "cycle_view": KeyBinding(("tab",), priority=True),
    "quit": KeyBinding(("q",)),
    "toggle_pause": KeyBinding(("space",), priority=True),
    "volume_up": KeyBinding(("plus", "equal"), priority=True),
    "volume_down": KeyBinding(("minus",), priority=True),
    "toggle_favorite": KeyBinding(("f",), priority=True),
    "show_playlists": KeyBinding(("p",), priority=True),
    "rename_file": KeyBinding(("u",), priority=True),
    "auto_title": KeyBinding(("g",), priority=True),
    "delete_file": KeyBinding(("delete",), priority=True),
    "cycle_theme": KeyBinding(("t",), priority=True),
    "show_settings": KeyBinding(("s",), priority=True),
    "show_about": KeyBinding(("i",), priority=True),
    "toggle_log": KeyBinding(("l",), priority=True),
    # Ab hier alles ohne Footer-Eintrag. Der Footer hat schon 14 Stueck.
    "copy_log": KeyBinding(("c",), show=False, priority=True),
    "toggle_shuffle": KeyBinding(("x",), show=False, priority=True),
    "cycle_repeat": KeyBinding(("r",), show=False, priority=True),
    # Transport: die Reihe von Winamp, dessen X und C hier schon belegt sind.
    # Das Bedienfeld zeigt dieselben Funktionen als Schaltflaechen.
    "previous_track": KeyBinding(("z",), show=False, priority=True),
    "stop": KeyBinding(("v",), show=False, priority=True),
    "next_track": KeyBinding(("b",), show=False, priority=True),
    "seek_backward": KeyBinding(("comma",), show=False, priority=True),
    "seek_forward": KeyBinding(("full_stop",), show=False, priority=True),
    "focus_search": KeyBinding(("slash",), show=False, priority=True),
    # Uebersicht der geltenden Belegung. Im Terminal die gelaeufige Taste dafuer.
    "keymap_overview": KeyBinding(("question_mark",), show=False, priority=True),
}
"""Der Bestandsstil - Stand v0.33.1, woertlich aus dem frueheren `app.py`.

Die Buchstaben stehen bewusst nur klein da. Das ist der gewachsene Bestand:
retro-amp hat noch nie auf die Grossschreibung reagiert, und das hier ist die
Bestandstabelle, kein Ort fuer stille Verbesserungen.
"""

LABEL_KEYS: dict[str, str] = {
    "cycle_view": "binding.cycle_view",
    "quit": "binding.quit",
    "toggle_pause": "binding.play_pause",
    "volume_up": "binding.volume_up",
    "volume_down": "binding.volume_down",
    "toggle_favorite": "binding.favorite",
    "show_playlists": "binding.playlists",
    "rename_file": "binding.rename",
    "auto_title": "binding.auto_title",
    "delete_file": "binding.delete",
    "cycle_theme": "binding.theme",
    "show_settings": "binding.settings",
    "show_about": "binding.info",
    "toggle_log": "binding.log",
    "copy_log": "binding.copy_log",
    "toggle_shuffle": "binding.shuffle",
    "cycle_repeat": "binding.repeat",
    "previous_track": "binding.previous",
    "stop": "binding.stop",
    "next_track": "binding.next",
    "seek_backward": "binding.seek_back",
    "seek_forward": "binding.seek_fwd",
    "focus_search": "binding.search",
    "keymap_overview": "binding.keymap_overview",
}
"""Aktion auf den i18n-Schluessel ihrer Footer-Beschriftung."""

TOOLTIP_KEYS: dict[str, str] = {
    "cycle_view": "tooltip.cycle_view",
    "quit": "tooltip.quit",
    "toggle_pause": "tooltip.toggle_pause",
    "volume_up": "tooltip.volume_up",
    "volume_down": "tooltip.volume_down",
    "toggle_favorite": "tooltip.toggle_favorite",
    "show_playlists": "tooltip.show_playlists",
    "rename_file": "tooltip.rename_file",
    "auto_title": "tooltip.auto_title",
    "delete_file": "tooltip.delete_file",
    "cycle_theme": "tooltip.cycle_theme",
    "show_settings": "tooltip.show_settings",
    "show_about": "tooltip.show_about",
    "toggle_log": "tooltip.toggle_log",
    "copy_log": "tooltip.copy_log",
    "toggle_shuffle": "tooltip.toggle_shuffle",
    "cycle_repeat": "tooltip.cycle_repeat",
    "previous_track": "tooltip.previous_track",
    "stop": "tooltip.stop",
    "next_track": "tooltip.next_track",
    "seek_backward": "tooltip.seek_backward",
    "seek_forward": "tooltip.seek_forward",
    "focus_search": "tooltip.focus_search",
    "keymap_overview": "tooltip.keymap_overview",
}
"""Aktion auf den i18n-Schluessel ihres Footer-Tooltips."""

# Die Anzeige der Taste im Footer. Ohne das stuende dort "full_stop" statt ">".
KEY_DISPLAY: dict[str, str] = {
    "tab": "TAB",
    "space": "SPC",
    "delete": "DEL",
    "plus": "+",
    "equal": "=",
    "minus": "-",
    "comma": "<",
    "full_stop": ">",
    "slash": "/",
    "question_mark": "?",
    "f1": "F1",
    "f2": "F2",
    "f3": "F3",
    "f4": "F4",
    "f7": "F7",
    "f8": "F8",
    "f9": "F9",
    "f10": "F10",
}


def key_display(key: str) -> str:
    """Uebersetzt einen Tastennamen in seine Anzeige im Footer.

    Args:
        key: Der Tastenname, so wie Textual ihn kennt.

    Returns:
        Der Text fuer den Footer.
    """

    return KEY_DISPLAY.get(key, key)


APP_FUNCTION_KEYS: dict[str, KeyBinding] = {
    # Die gemeinsame Konvention nennt diese Aktion `focus_filter`, weil sie in
    # den anderen Anwendungen eine Tabelle filtert. Hier durchsucht sie die
    # Bibliothek - der Name bleibt deshalb `focus_search`, und die F3 wird von
    # Hand nachgetragen statt ueber COMMON_FUNCTION_KEYS.
    "focus_search": KeyBinding(("f3", "slash")),
    "show_playlists": KeyBinding(("f7", "p")),
    "rename_file": KeyBinding(("f8", "u")),
    # Der einzige Eintrag, der einen Buchstaben WEGNIMMT: "g" ist in der
    # Vim-Ebene "an den Anfang", und eine Widget-Bindung verdeckt die
    # gleichnamige an der App lautlos. Ersatz ist alt+g, so wie das Log auf
    # alt+l ausweicht.
    "auto_title": KeyBinding(("f9", "alt+g")),
    "toggle_favorite": KeyBinding(("f10", "f")),
}
"""Die F-Tasten, die diese Anwendung selbst vergibt.

`f1`, `f2` und `f4` kommen aus der gemeinsamen Konvention (Info, Einstellungen,
Log). `f5` und `f6` bleiben frei: dort liegen familienweit Aktualisieren und
Details, und retro-amp hat beides nicht - eine andere Aktion daraufzulegen
wuerde die gemeinsame Bedeutung zerstoeren.

Ab `f7` vergibt die Anwendung selbst. Gewaehlt sind die vier haeufigsten
fachlichen Aktionen: Playlists, Umbenennen, Titel ergaenzen, Favorit. `f11` und
`f12` bleiben frei, viele Terminals belegen sie mit Vollbild.

Ohne F-Taste bleiben bewusst: `tab` Ansicht wechseln, `space` Play/Pause und
`q` Beenden (alle drei eindeutig genug), `t` Theme, `x` Shuffle, `r` Repeat und
`c` Log kopieren (selten), sowie der ganze Transport - der hat mit `z`, `v`,
`b`, `<` und `>` schon seine eigene Reihe.
"""

FUNCTION_KEYS: dict[str, KeyBinding] = {**COMMON_FUNCTION_KEYS, **APP_FUNCTION_KEYS}
"""Die gemeinsame Konvention plus die Ergaenzungen dieser Anwendung.

`resolve_keymap()` uebergeht dabei jeden Eintrag, den `CLASSIC` nicht kennt -
`refresh`, `show_details` und `show_history` gibt es in retro-amp nicht.
"""


def style_from_settings(settings: Mapping[str, object]) -> KeymapStyle:
    """Ermittelt den Stil aus den Einstellungen.

    Ein leerer Wert heisst "noch nicht entschieden" - dann entscheidet die
    Plattform, damit eine frische Installation auf dem Mac nicht mit F-Tasten
    startet, die das Betriebssystem selbst abfaengt.

    Args:
        settings: Die geladenen Einstellungen.

    Returns:
        Der anzuwendende Stil.
    """

    gewaehlt = str(settings.get("keymap_style", "") or "").strip().lower()
    for stil in KeymapStyle:
        if gewaehlt == stil.value:
            return stil
    return default_style_for_platform()


def resolve(settings: Mapping[str, object]) -> ResolvedKeymap:
    """Baut die fertige Belegung aus den Einstellungen.

    Im F-Tasten-Stil steht das Ergebnis in der Reihenfolge fuer den Footer:
    erst alles mit F-Taste, aufsteigend nach Nummer, danach der Rest. Ohne das
    stuende dort `F10` vor `F1`, weil die Bestandstabelle die Reihenfolge
    vorgibt.

    Im Bestandsstil wird NICHT sortiert. Dort hat gar keine Aktion eine
    F-Taste, es gaebe also nichts nach vorn zu ziehen.

    Args:
        settings: Die geladenen Einstellungen.

    Returns:
        Die Belegung samt Beanstandungen. Die Beanstandungen gehoeren ins Log,
        nicht in einen Dialog - sie betreffen die Einstellungsdatei, nicht den
        laufenden Vorgang.
    """

    stil = style_from_settings(settings)
    overrides, probleme = parse_overrides(settings.get("keymap_custom"))
    ergebnis = resolve_keymap(
        stil,
        CLASSIC,
        function_keys=FUNCTION_KEYS,
        overrides=overrides,
        vim_navigation=bool(settings.get("keymap_vim", False)),
    )
    if stil is not KeymapStyle.FUNCTION_KEYS:
        return ResolvedKeymap(bindings=ergebnis.bindings, problems=probleme + ergebnis.problems)
    return ResolvedKeymap(
        bindings=sort_for_footer(ergebnis.bindings),
        problems=probleme + ergebnis.problems,
    )
