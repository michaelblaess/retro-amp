"""Textvergleich fuer die Suche - unempfindlich gegen Akzente und Sonderzeichen.

"Eternita" findet "Eternità", "Grun" und "Gruen" finden "Grün", "dont stop"
findet "Don't Stop", "ac dc" findet "AC/DC". Suchbegriff und Dateiname werden
dafuer auf dieselbe Grundform gefaltet: Kleinbuchstaben ohne Akzente, jedes
Satz- und Trennzeichen als ein Leerzeichen, Apostrophe ganz weg.

Die Faltung merkt sich zu jedem Zeichen die Stelle im Original. Nur so laesst
sich ein Treffer in der gefalteten Form wieder im angezeigten Namen markieren,
denn die Laengen stimmen nicht ueberein ("ß" wird zu "ss", "'" verschwindet).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

# Zeichen, die NFKD nicht zerlegt - ohne Tabelle blieben sie unfindbar.
_SPECIAL_LETTERS: dict[str, str] = {
    "ß": "ss",
    "æ": "ae",
    "œ": "oe",
    "ø": "o",
    "đ": "d",
    "ł": "l",
    "þ": "th",
}

# Deutsche Ersatzschreibung - nur fuer den zweiten Vergleich, siehe find_spans.
_GERMAN_LETTERS: dict[str, str] = {"ä": "ae", "ö": "oe", "ü": "ue"}

# Apostrophe verschwinden ersatzlos, damit "dont" auch "Don't" findet.
_APOSTROPHES = frozenset("'\u2019\u2018\u00b4`")


@dataclass(frozen=True)
class FoldedText:
    """Gefaltete Suchform eines Textes samt Rueckverweis ins Original."""

    text: str
    origins: tuple[int, ...]


def _fold_char(char: str, german: bool) -> str:
    lowered = char.lower()
    if german and lowered in _GERMAN_LETTERS:
        return _GERMAN_LETTERS[lowered]
    if lowered in _SPECIAL_LETTERS:
        return _SPECIAL_LETTERS[lowered]
    if char in _APOSTROPHES:
        return ""
    decomposed = unicodedata.normalize("NFKD", lowered)
    base = "".join(c for c in decomposed if not unicodedata.combining(c))
    return "".join(c if c.isalnum() else " " for c in base)


def fold(text: str, *, german: bool = False) -> FoldedText:
    """Faltet einen Text in die Suchform.

    Leerraum wird zusammengefasst und an den Raendern entfernt.
    """
    chars: list[str] = []
    origins: list[int] = []
    for index, char in enumerate(text):
        for folded in _fold_char(char, german):
            if folded == " " and (not chars or chars[-1] == " "):
                continue
            chars.append(folded)
            origins.append(index)
    if chars and chars[-1] == " ":
        chars.pop()
        origins.pop()
    return FoldedText("".join(chars), tuple(origins))


def find_spans(name: str, query: str) -> list[tuple[int, int]]:
    """Sucht den Begriff im Namen und liefert die Trefferstellen im Original.

    Der Name wird zweimal gefaltet: einmal mit "ü" als "u", einmal als "ue".
    Damit finden sowohl "Grun" als auch "Gruen" den Namen "Grün". Der
    Suchbegriff selbst wird nur einfach gefaltet, "Grün" im Suchfeld wird also
    zu "grun" und trifft die erste Form.
    """
    needle = fold(query).text
    if not needle:
        return []
    for german in (False, True):
        haystack = fold(name, german=german)
        spans: list[tuple[int, int]] = []
        start = 0
        while True:
            index = haystack.text.find(needle, start)
            if index < 0:
                break
            end = index + len(needle)
            spans.append((haystack.origins[index], haystack.origins[end - 1] + 1))
            start = end
        if spans:
            return spans
    return []


def matches(name: str, query: str) -> bool:
    """Prueft, ob der Suchbegriff im Namen vorkommt.

    Ein Begriff, der nach dem Falten leer ist (nur Satzzeichen), trifft nichts.
    """
    return bool(find_spans(name, query))
