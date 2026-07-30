# Kontextmenüs im Ordner-Browser

Stand: 30.07.2026 - **umgesetzt**. Entscheidungen und Umsetzung dokumentiert.

Rechtsklick auf einen Knoten im linken Ordner-Baum (`FolderBrowser`) öffnet ein Kontextmenü
mit den Aktionen, die zu genau diesem Knoten passen - Ordner anders als Datei. Wichtigster
einzelner Wunsch war **"Alles einklappen"**, um den Baum nach dem Wühlen wieder auf eine
übersichtliche Größe zu bringen.

## Getroffene Entscheidungen

| Frage | Entscheidung |
| --- | --- |
| "Ausklappen" eine Ebene oder rekursiv | **eine Ebene** - der `DirectoryTree` lädt faul von Platte, rekursiv würde ganze Diskografien einlesen |
| Reichweite "Alles einklappen" | **ganzer Baum**, Wurzel bleibt offen, Cursor springt auf die Wurzel |
| Favoriten für Ordner | **nein**, nur für Dateien - die Favoriten sind dateibasiert |
| "Im Explorer öffnen" | **nein** - keine OS-Integration in retro-amp |
| Tastatur-Trigger fürs Menü | **nein** - Rechtsklick genügt |
| Weitere Kontextmenüs (Tabelle, Favoriten-/Playlist-Baum) | **später** - erst der Ordner-Baum |

## Menüs

**Ordner** (Reihenfolge wie implementiert):

```
Abspielen                       (nur aktiv wenn direkt Audio-Dateien drin sind)
────────────────────────────
Ausklappen  /  Einklappen       (nur der passende Eintrag, je nach Zustand)
Alles einklappen
────────────────────────────
Zur Playlist hinzufügen...      (nur aktiv wenn direkt Audio-Dateien drin sind)
Als Musikbibliothek setzen
────────────────────────────
Umbenennen                  u   (an der Baumwurzel deaktiviert)
Löschen                   DEL   (an der Baumwurzel deaktiviert)
```

**Audio-Datei:**

```
Abspielen
────────────────────────────
Zu Favoriten hinzufügen     f   (bzw. "Aus Favoriten entfernen", je nach Zustand)
Zur Playlist hinzufügen...  p
────────────────────────────
Titel automatisch ergänzen  g
Umbenennen                  u
Löschen                   DEL
```

"Abspielen" und "Zur Playlist hinzufügen" arbeiten bei Ordnern **nicht rekursiv** - sie
meinen genau die Titel, die die Datei-Tabelle für diesen Ordner zeigt. Ein reiner
Interpreten-Ordner ohne eigene Dateien hat die beiden Einträge deshalb ausgegraut statt
still nichts zu tun.

## Die Falle beim Rechtsklick

Textuals `Tree._on_click` prüft die Maustaste nicht - ein Rechtsklick lief bisher in
`select_cursor` und hätte auf einer Datei die Wiedergabe gestartet.

Ein Override von `_on_click` allein genügt **nicht**: Textual ruft jeden `_on_click`
entlang der MRO auf, `Tree._on_click` liefe also zusätzlich zum eigenen. Das war im
ersten Anlauf auch messbar - der Linksklick löste `FileSelected` doppelt aus.

Richtig ist `event.prevent_default()`: `MessagePump._get_dispatch_methods` prüft
`_no_default_action` vor jeder weiteren Klasse und bricht die Kette ab. Aus demselben
Grund darf im Override kein `super()`-Aufruf stehen - den Basis-Handler ruft Textual bei
Linksklick selbst auf. `event.stop()` allein reicht nicht, das verhindert nur das Bubbling
zum Elternwidget.

Die getroffene Zeile liefert Textual im Click-Event mit (`event.style.meta["line"]`),
dazu `get_node_at_line(line)` - keine eigene Offset-Rechnerei. Der Rechtsklick setzt
zuerst den Cursor auf den geklickten Knoten, sonst wirkt die Aktion auf einen anderen
Knoten als den, auf den gezielt wurde.

## Aufteilung im Code

- `widgets/folder_browser.py`: `_on_click`-Override, Message `ContextMenuRequested`,
  `collapse_all()`, `set_node_expanded()`. Das Widget entscheidet nicht, welche Aktionen
  es gibt - Favoriten-Status, Playlists und Bibliothekspfad liegen in der App.
- `app.py`: `on_folder_browser_context_menu_requested` baut die Items,
  `_on_tree_menu_action` führt aus. Menü-Ziel liegt in `_tree_menu_path` /
  `_tree_menu_is_dir`, weil `ContextMenuScreen` im Callback nur die Action-Id liefert.
- `screens/playlist_screen.py`: neuer Parameter `title_text`, damit der Dialog auch
  "Ordner: ..." statt "Track: ..." als Überschrift tragen kann.
- Ordner abspielen läuft über `_play_after_scan`: der Scan ist ein Worker-Thread, gespielt
  wird erst wenn `_apply_scan_result` die Titelliste hat.
- `_delete_target(path)` aus `action_delete_file` herausgezogen, damit Tastenkürzel und
  Menü dieselbe Rückfrage bauen.

## Tests

`tests/test_folder_browser_menu.py` (8 Tests, Widget-Ebene über `run_test`): Rechtsklick
postet die Message und löst **keine** Wiedergabe aus, Linksklick wählt weiterhin genau
einmal aus, der Cursor springt auf den geklickten Knoten, der Aufklapp-Zustand wird korrekt
gemeldet, "Alles einklappen" erwischt auch tiefere Ebenen und lässt die Wurzel offen,
`set_node_expanded` klappt nur eine Ebene auf und ignoriert Dateien.

Zusätzlich headless gegen die echte App geprüft (Sandbox-Home): Menü-Inhalte für Ordner,
Datei und Album, ausgegraute Einträge bei einem Ordner ohne eigene Dateien,
"Alles einklappen" (6 Zeilen -> 2), "Ordner abspielen" startet mit 2 Titeln in der Liste.
