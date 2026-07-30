# Kontextmenüs in den linken Bäumen

Stand: 30.07.2026 - **vollständig umgesetzt**: Ordner-Baum, Favoriten, Verlauf, Suche,
Playlist-Baum und Datei-Tabelle. Entscheidungen und Umsetzung dokumentiert.

Rechtsklick auf einen Knoten öffnet ein Kontextmenü mit den Aktionen, die zu genau diesem
Knoten passen - Ordner anders als Datei, Gruppe anders als Eintrag. Wichtigster einzelner
Wunsch war **"Alles einklappen"**, um den Baum nach dem Wühlen wieder auf eine
übersichtliche Größe zu bringen.

Offen bleibt nur noch das Löschen einer kompletten Playlist - siehe unten.

## Getroffene Entscheidungen

| Frage | Entscheidung |
| --- | --- |
| "Ausklappen" eine Ebene oder rekursiv | **eine Ebene** - der `DirectoryTree` lädt faul von Platte, rekursiv würde ganze Diskografien einlesen |
| Reichweite "Alles einklappen" | **ganzer Baum**, Wurzel bleibt offen, Cursor springt auf die Wurzel |
| Favoriten für Ordner | **nein**, nur für Dateien - die Favoriten sind dateibasiert |
| "Im Explorer öffnen" | **nein** - keine OS-Integration in retro-amp |
| Tastatur-Trigger fürs Menü | **nein** - Rechtsklick genügt |
| Weitere Kontextmenüs (Tabelle, Favoriten-/Playlist-Baum) | schrittweise nachgezogen - Reihenfolge: Ordner-Baum, dann Favoriten/Verlauf/Suche, dann Playlist-Baum und Datei-Tabelle |

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

---

# Favoriten, Verlauf und Suche

Dieselbe Mechanik für die drei Listen-Bäume links. Alle drei sind `Tree[Path | None]` mit
demselben Aufbau - Gruppen-Knoten ohne Daten, Blätter mit einem Pfad -, deshalb steckt die
Rechtsklick-Logik in einer gemeinsamen Basisklasse `widgets/path_context_tree.py`.

## Menüs

**Favoriten** (Track): Abspielen · Aus Favoriten entfernen `DEL` · Zur Playlist hinzufügen ·
Im Ordner-Baum zeigen

**Verlauf** (Track): Abspielen · Zu Favoriten hinzufügen/entfernen `f` ·
Zur Playlist hinzufügen · Im Ordner-Baum zeigen · Verlauf löschen `DEL`

**Suche** (Datei): Abspielen · Zu Favoriten hinzufügen/entfernen `f` ·
Zur Playlist hinzufügen · Im Ordner-Baum zeigen
**Suche** (Ordner-Treffer): Ordner öffnen · Im Ordner-Baum zeigen

**Gruppen-Knoten** in allen dreien: Ausklappen/Einklappen · Alles einklappen. Im Verlauf
zusätzlich "Verlauf löschen".

Kein Umbenennen und kein Löschen in diesen Ansichten - `DEL` bedeutet dort "aus der Liste
entfernen", nicht "Datei löschen". Ein zweites, gegenläufiges Löschen im selben Menü wäre
eine Falle. Zeigt ein Eintrag auf eine verschwundene Datei, sind Abspielen, Playlist und
"Im Ordner-Baum zeigen" ausgegraut.

## Details

- Die Basisklasse hält den zuletzt per Rechtsklick getroffenen Knoten (`_menu_node`).
  Gruppen-Knoten haben keinen Pfad, über den die App sie wiederfinden könnte - deshalb
  bleibt die Knoten-Referenz im Widget, und die App ruft nur `set_menu_node_expanded()`
  bzw. `collapse_all()`.
- Jeder Baum leitet eine eigene `ContextMenuRequested`-Klasse ab. Textual bildet den
  Handler-Namen aus dem `__qualname__` der Message-Klasse, dadurch bekommt jeder Baum
  seinen eigenen Handler in der App statt eines gemeinsamen mit Typprüfung.
- **"Im Ordner-Baum zeigen"** war der einzige Punkt mit echter Tücke:
  `expand_to_path` klappt den Zielordner zwar auf, wartet aber nicht auf dessen Kinder -
  der `DirectoryTree` lädt sie erst danach nach. Ohne das Warten stand der Cursor auf dem
  Ordner statt auf der Datei. `FolderBrowser.reveal_path()` wartet deshalb explizit auf die
  Load-Queue des Zielknotens. Liegt der Pfad außerhalb der Baumwurzel, kommt eine Meldung.

## Nebenbefunde

- `_clear_history` gab es bereits als Callback des Settings-Dialogs (Rückgabe: Anzahl).
  Eine gleichnamige zweite Methode hätte sie stillschweigend überschrieben und die Meldung
  im Settings-Dialog beschädigt - mypy hat das gefunden, nicht die Tests. Die neue Methode
  heißt `_clear_history_and_notify`.
- Drei fast identische "navigieren und abspielen"-Handler (Favoriten, Verlauf, Playlist)
  sind jetzt `_play_existing_path`, ebenso `_open_folder` und `_remove_favorite`.

## Tests

`tests/test_path_context_tree.py` (17 Tests, über alle drei Bäume parametrisiert):
Rechtsklick postet die baum-eigene Message und löst keine Wiedergabe aus, Linksklick wählt
genau einmal aus, Gruppen-Knoten melden `path=None`, Cursor springt auf den geklickten
Knoten, "Alles einklappen" lässt nur die Wurzel offen, `set_menu_node_expanded` wirkt auf
den zuletzt geklickten Knoten und ignoriert Blätter, Ordner-Treffer der Suche melden ein
Verzeichnis.

Headless gegen die echte App: alle sechs Menü-Varianten, "Im Ordner-Baum zeigen" landet mit
Tab-Wechsel auf der Datei, "Alles einklappen" im Verlauf, "Ordner öffnen" aus der Suche
füllt die Tabelle, Favorit-Umschalten aus dem Verlauf.

**Test-Stolperstein:** Ein programmatischer `tabs.active = ...` springt sofort zurück,
solange der Fokus in der alten TabPane sitzt - Textual aktiviert die Pane des fokussierten
Widgets wieder. Im Test vorher `app.set_focus(None)`.

---

# Playlist-Baum und Datei-Tabelle

## Menüs

**Playlist-Baum**, Playlist-Knoten: Playlist abspielen · Ausklappen/Einklappen ·
Alles einklappen
**Playlist-Baum**, Track: Abspielen · Aus Playlist entfernen `DEL` ·
Zu Favoriten hinzufügen/entfernen `f` · Im Ordner-Baum zeigen

**Datei-Tabelle** (rechtes Panel): Abspielen · Zu Favoriten hinzufügen/entfernen `f` ·
Zur Playlist hinzufügen `p` · Titel automatisch ergänzen `g` · Umbenennen `u` ·
Löschen `DEL` · Im Ordner-Baum zeigen

Hier sind Umbenennen und Löschen richtig - die Tabelle zeigt den Ordnerinhalt, und
`u`/`DEL` wirken dort ohnehin schon auf den markierten Track. In den Listen-Ansichten
(Favoriten, Verlauf, Playlist) bleiben sie draußen, weil `DEL` dort "aus der Liste
entfernen" bedeutet.

"Titel automatisch ergänzen" arbeitet aus dem Menü heraus auf **genau dieser Datei**,
während die Taste `g` weiter den ganzen Ordner durchgeht.

## Details

- Die Basisklasse `PathContextTree` ist jetzt generisch (`Tree[TreeDataType]`). Der
  Playlist-Baum legt in seinen Gruppen-Knoten den Playlist-Namen als `str` ab, die
  anderen drei nur `Path | None`. Die Message meldet weiter nur den Pfad, den
  Playlist-Namen liefert `PlaylistTree.menu_playlist_name` aus dem gemerkten Knoten.
- Die Datei-Tabelle ist ein `DataTable`, kein `Tree`. `FileDataTable` fängt den
  Rechtsklick mit demselben `prevent_default()`-Muster ab und meldet den Zeilenindex
  aus `event.style.meta["row"]` - das liefert Textual selbst, robuster als `screen_y`
  in Zellen umzurechnen. Die Zeile wird über `_filtered_tracks` aufgelöst, folgt also
  automatisch der aktiven Spaltensortierung.
- `FileDataTable.RightClicked` braucht eine `control`-Property, sonst lehnt der
  `@on`-Dekorator den Selektor ab (`OnDecoratorError: The message class must have a
  'control' to match with the on decorator`).

## Bewusst nicht umgesetzt: Playlist löschen

Eine ganze Playlist zu löschen geht heute gar nicht - `PlaylistService.delete_playlist`
existiert, wird aber von keiner Stelle der Oberfläche aufgerufen. Der naheliegende
Menüeintrag scheitert am Bestätigungsdialog: `ConfirmScreen` ist auf Dateien
zugeschnitten und **löscht selbst** (`unlink`/`rmtree`), statt nur ja/nein
zurückzugeben. Das sauber zu lösen heißt, den Dialog zu verallgemeinern - das ist ein
eigener Schritt und keine Beigabe zum Kontextmenü. Ohne Rückfrage wollte ich eine
destruktive Aktion nicht einbauen.

## Tests

`tests/test_file_table_menu.py` (6) und `tests/test_playlist_tree_menu.py` (5).
Abgedeckt: Rechtsklick meldet den richtigen Track bzw. die richtige Playlist und löst
keine Wiedergabe aus, der Cursor springt auf die geklickte Zeile, Klick auf den
Spaltenkopf und auf die leere Tabelle tun nichts, und nach dem Umsortieren meldet eine
Zeile den dort **sichtbaren** Track.

Nebenbefund im Test: `DataTable` sendet `RowSelected` erst beim Klick auf die bereits
markierte Zeile (`highlight_click` in `DataTable._on_click`) - der erste Klick
verschiebt nur den Cursor. Der Test bildet das jetzt ab, statt eine falsche Erwartung
zu formulieren.

Headless gegen die echte App: beide Menüs, "Im Ordner-Baum zeigen" aus der Tabelle,
"Aus Playlist entfernen" (2 Titel -> 1) und "Playlist abspielen".
