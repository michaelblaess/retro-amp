# PLAN: DAW-Optik für retro-amp

Stand 08.09.2026. Ziel: retro-amp soll nicht nach Windows aussehen, sondern nach
einem Werkzeug für Musik. Als Vorlage dienen die Quellen von Audacity 4.0.0,
gelesen am 08.09.2026.

**Sperrvermerk:** Audacity und das darunterliegende muse-Framework von MuseScore
stehen unter GPLv3. retro-amp ist Apache-2.0. Aus diesen Quellen darf **keine
Zeile** übernommen werden, auch kein Ausschnitt und auch keine Theme-Datei.
Alles unten beschreibt ein Vorgehen, keine Vorlage.

---

## 1. Woraus der Look tatsächlich entsteht

Drei Entscheidungen, alle drei am Quelltext belegt. Nicht die Farbwahl macht den
Unterschied, sondern diese drei.

### 1.1 Kein natives Steuerelement überlebt

Das muse-Framework bringt 68 eigene Bausteine mit
(`muse/framework/uicomponents/qml/Muse/UiComponents/`), praktisch alle mit dem
Präfix `Styled`: eigener Rollbalken, eigene Reiterleiste, eigene Tabelle, eigener
Baum, eigenes Kurzinfo-Fenster, eigenes Menü. In `src/` stehen **drei**
QtWidgets-Includes gegen 356 QML-Dateien.

Das ist die eigentliche Antwort auf "weg vom Windows-Look": dorthin kommt man
nicht durch Nachfärben. Solange ein einziger nativer Rollbalken oder ein nativer
Aufklappfeil im Bild ist, sieht die Anwendung nach Betriebssystem aus. Der Satz
Steuerelemente muss ersetzt werden, nicht eingefärbt.

### 1.2 Die Zustände kommen aus Deckkraft, nicht aus Farben

`FlatButton.qml` hält genau **zwei** Farben (normal, überfahren/gedrückt) und
nimmt die drei Zustände über Deckkraftwerte aus dem Theme
(`buttonOpacityNormal`/`Hover`/`Hit`). Kein Zustand hat eine eigene Farbe.

Der Gewinn ist Wartbarkeit: derselbe Knopf funktioniert auf jedem Untergrund und
in jedem Theme, ohne dass ein Theme neun Knopffarben definieren muss. Bei 40
Themes ist das der Unterschied zwischen pflegbar und nicht pflegbar.

### 1.3 Ein Theme ist ein vollständiger, prüfbarer Satz

`src/app/configs/light.cfg`, `dark.cfg` und `high_contrast_black.cfg` tragen
**je genau 92 Schlüssel** - denselben Satz, dreimal. Ein Theme kann keinen
Schlüssel vergessen, weil die Sätze übereinstimmen müssen.

Der Satz ist zweigeteilt: rund 28 generische Schlüssel werden typisiert gelesen,
**jeder übrige Schlüssel wandert automatisch in einen offenen Kanal**
(`theme.extra`, `uiconfiguration.cpp:336-346`) und ist damit in der Oberfläche
verfügbar, ohne dass Code angefasst wird. So stehen fachliche Werte wie die
Farben von Spurkopf, Zeitlineal und Pegelverlauf gleichberechtigt neben den
generischen.

### 1.4 Nachtrag: der Look ist auch Verhalten

Der Pegelmesser (`src/audio/internal/audiometer.cpp`, 164 Zeilen) fällt in **dB
pro Sekunde** ab statt pro Bild, hält eine Spitze mindestens die Dauer eines
Audioblocks, und klingt nach dem Anhalten über rund 2,8 Sekunden aus, statt
einzufrieren. Genau das lässt eine Anzeige professionell wirken. Farbe allein
tut es nicht.

---

## 2. Wo retro-amp heute steht

Gemessen am Repo, 08.09.2026.

- Die 40 Themes kommen aus `textual-themes` und sind Objekte der Klasse
  `textual.theme.Theme`. Sie tragen **11 Farben** plus Flags
  (`primary`, `secondary`, `warning`, `error`, `success`, `accent`, `foreground`,
  `background`, `surface`, `panel`, `boost`).
- `Theme.variables` ist der vorhandene offene Kanal - er entspricht genau
  Audacitys `extra`. Genutzt wird er von **6 der 40 Themes**. Der Satz ist damit
  weder vollständig noch verlässlich.
- Elf Farben reichen für eine Terminaloberfläche. Für Visualizer, Pegel,
  Transportleiste, Positionsleiste und Cover-Rahmen reichen sie nicht - dort
  entstehen sonst genau die abgeleiteten Zufallsfarben, die eine Anwendung
  billig aussehen lassen.
- Der Peak im Visualizer fällt pro Bild
  (`src/retro_amp/widgets/visualizer.py:283`), nicht in dB pro Sekunde. Bei
  geänderter Bildrate ändert sich damit die Optik.
- Der Takt liegt bei 12 Hz (`visualizer.py:246`). Am 08.09.2026 gemessen: die
  vorhandene FFT kostet bei 62 Hz rund ein Viertel des Bildbudgets, ohne
  ausgefallene Bilder. 12 Hz war also nie ein Rechenlimit.

**Der Engpass ist nicht Qt, sondern die Tiefe des Theme-Satzes.** Und der ist
unabhängig von der Oberfläche.

---

## 3. Der Weg

Die Reihenfolge ist absichtlich so gewählt, dass die ersten beiden Schritte der
bestehenden TUI sofort nützen und keine Wegwerfarbeit sind, egal wie die
Qt-Frage ausgeht.

### Schritt 1: den Theme-Satz vertiefen (im Repo textual-themes)

Die 11 Textual-Grundfarben bleiben. Dazu kommt ein benannter Satz
Player-Schlüssel in `Theme.variables`, mindestens:

- Visualizer: Balken unten/mitte/oben, Spitzenmarke, Untergrund, Raster
- LCD-Anzeige: Vordergrund, Hintergrund, gedimmte Ziffer
- Transport: Knopf normal, Knopf überfahren, Knopf aktiv, Aufnahme
- Positionsleiste: Rinne, gespielt, Griff, Puffer
- Flächen: Trennlinie, Kopfzeile, Auswahl, Fokusrahmen

Dazu die drei Deckkraftwerte aus Abschnitt 1.2 statt eigener Zustandsfarben.

**Der Test, der scheitern kann** (Muster aus Abschnitt 1.3): alle 40 Themes
tragen exakt denselben Schlüsselsatz. Fehlt einem Theme ein Schlüssel, ist der
Test rot. Die heutige Lage - 6 von 40 - wäre damit sofort sichtbar.

**Stand 08.09.2026 - umgesetzt, aber in retro-amp statt in textual-themes.**
Der Grund steht in Abschnitt 4: Audacitys 92-Schlüssel-Dateien liegen in der
Anwendung, nicht im Rahmenwerk. Der Satz ist `SurfacePalette` in
`src/retro_amp/palette.py` - 22 Werte, aus den elf Grundfarben abgeleitet,
Vollständigkeit über den Typ statt über eine Prüfung zur Laufzeit.

Er wird inzwischen überall dort gezogen, wo vorher feste Farben im Malcode
standen:

| Fläche | vorher | jetzt |
| --- | --- | --- |
| Visualizer, alle fünf Modi | fester Regenbogen, Ampelfarben | Bandverlauf aus dem Theme |
| Positions- und Lautstärkeleiste | `green` auf `dim` | `progress_played` auf `progress_trough` |
| Statusanzeige läuft/angehalten | `green` / `yellow` | `accent_on` / `accent_hold` |
| Tastenkappen, eingeschaltet | `green`/`cyan`/`magenta`/`red` | `accent_on`, `transport_active`, `accent_hot` |
| Tastenkappen, Rahmen und Hover | `dim` und eine eigene Rechnung | `divider` und `transport_hover` |
| Wiedergabemarke in der Dateiliste | `bold green` | `bold accent_on` |

Drei Felder kamen dabei hinzu, die beim Entwurf noch fehlten: `accent_on`,
`accent_hold` und `accent_hot` für Glyphen und Marken. Sie sind bewusst nicht
dieselben Felder wie die Pegelfarben des Visualizers - eine Ausnahme am
Visualizer soll die Transportleiste nicht mitziehen.

Der Zugriff liegt einmal in `widgets/palette_source.py` (Mischklasse
`PaletteSource`) statt in jedem Widget erneut. Ein Test hält fest, dass ein
Themewechsel von allein bis in die Leiste durchschlägt - die zeichnet, anders
als der Visualizer, nur auf Anlass.

**Nachtrag: der Satz steht auch in Textuals Stylesheets.** Selbstgezeichnete
Flächen holen ihre Farben aus dem Malcode, alles andere beschreibt CSS - und das
kannte nur die elf Grundfarben. `RetroAmpApp.get_css_variables` ergänzt die
abgeleiteten Werte, jedes Feld als `$ra-...`, die Namen mechanisch aus den
Feldnamen gebildet. Damit ist `SurfacePalette` die einzige Stelle, an der eine
Farbe entsteht, egal ob sie später gezeichnet oder beschrieben wird.

Die Widgets behalten in ihrem `DEFAULT_CSS` Textuals Grundfarben, damit sie ohne
diese Anwendung lauffähig bleiben. Übersteuert wird in `app.tcss` - dort stehen
die Trennlinien (`$ra-divider` statt voller Akzentfarbe), die Titelzeile der
Dateiliste (`$ra-header` statt eines hellen Akzentbalkens) und die Auswahl der
Schnellwahl (`$ra-selection`).

Zwei Punkte aus Abschnitt 1.4 sind damit ebenfalls erledigt:

- Die **Spitzenmarke** fällt mit 16 dB/s statt im Gleichlauf mit dem Balken.
  Erst dadurch steht sie sichtbar über dem Pegel, statt nur während der
  Haltezeit aufzutauchen. Der Takt läuft nach dem Anhalten entsprechend länger
  nach, sichtbar ist in dieser Zeit nur noch die fallende Marke.
- Die Positions- und die Lautstärkeleiste haben einen **Griff** an der
  Abspielstelle (`$ra-progress-handle`), gezeichnet als schmaler Strich, der
  eine Zelle der Laufschiene ersetzt. Die Leiste wird dadurch nicht breiter -
  ein Test hält das fest, weil `on_click` aus der Breite die Position rechnet.

### Schritt 2: den Satz aus Textual lösen (ebenfalls textual-themes)

Solange die Themedaten `textual.theme.Theme`-Objekte **sind**, kann eine
Qt-Fassung sie nicht lesen, ohne Textual mitzuinstallieren. Das ist genau die
Abhängigkeitsfalle aus dem Skill `qt-specialist`: Textual landet dann in der
Qt-Binary.

Also: die Themedaten als neutrale Struktur im Paket (dataclass oder JSON, wie
Audacitys `.cfg`), und `textual.theme.Theme` daraus **erzeugen**. Ein Adapter je
Oberfläche, die Daten in der Mitte.

Prüfbar über denselben Weg wie der Kern-ohne-Qt-Test: ein frischer Prozess
importiert die Themedaten und darf danach kein `textual` in `sys.modules` haben.

### Schritt 3: erst dann die Qt-Fassung

- **Fusion als Basis behalten** (die einzige plattformgleiche Basis), aber mit
  eigener Palette UND einem vollständigen QSS darüber. Nicht das dünne
  Struktur-QSS aus Entscheidung E1 im Skill - das war für nüchterne
  Enterprise-Werkzeuge gedacht und ist hier ausdrücklich nicht das Ziel.
- **Jedes native Steuerelement anfassen**, das im Bild ist: Rollbalken,
  Aufklappfeil, Ankreuzfeld, Kopfzeile, Reiter, Kurzinfo. Der Skill hat die
  Stolpersteine dazu schon (eigene Pfeilbilder je Erscheinungsbild, weil QSS
  kein `currentColor` kennt, und der Test, der jede `url()` gegen das
  Dateisystem prüft).
- **Die interessanten Flächen selbst zeichnen**: Visualizer, Pegel,
  Positionsleiste, Cover-Rahmen. Regel aus Abschnitt 1.2 übernehmen - **kein
  Malcode kennt eine Farbe**, alle Farben kommen als Eigenschaft von außen.
- **Docking mit `QDockWidget`.** Audacity nutzt KDDockWidgets (KDAB), das ist
  GPL beziehungsweise kostenpflichtig und für Apache-2.0 nicht nutzbar.
  `QDockWidget` gehört zu Qt, ist LGPL, und seine Titelzeile lässt sich per QSS
  (`QDockWidget::title`) einfärben - am 08.09.2026 in PySide6 6.11.2 gesetzt,
  ohne Fehler.
- **Eigene Titelleiste ohne Win32.** Audacity zahlt dafür 487 Zeilen
  Windows-API je Plattform (`winwindowscontroller.cpp`, mit `WM_NCCALCSIZE`,
  `WM_NCHITTEST` und `DwmExtendFrameIntoClientArea`), weil das Framework aus
  einer Zeit stammt, in der Qt die Aufrufe noch nicht hatte. Heute gibt es
  `QWindow.startSystemMove()` und `startSystemResize()` - beide in PySide6
  6.11.2 vorhanden (geprüft). Damit sollte `FramelessWindowHint` plus eine
  selbstgezeichnete Titelzeile genügen, inklusive Andocken am Bildschirmrand.
  **Noch nicht verifiziert**, weil sich Ziehen und Andocken nur von Hand prüfen
  lassen - das ist der erste Handgriff in Schritt 3.

### Schritt 4: das Verhalten nachziehen

Unabhängig von der Oberfläche, gilt für TUI und Qt:

- Peak-Abfall in dB pro Sekunde statt pro Bild.
- Spitze mindestens die Dauer eines Analysefensters halten.
- Nach dem Anhalten ausklingen lassen statt einfrieren.
- Den Zeitgeber über ein Interface hereinreichen, damit die Animation ohne
  laufende Oberfläche prüfbar ist.

---

## 4. Was ausdrücklich NICHT gemacht wird

- **Kein QML.** Audacity braucht es für Wellenform-Zoom, GPU und tausende Clips
  und zahlt mit 50.717 Zeilen QML plus 14.853 Zeilen im Framework. Ein Player
  aus Panels, Listen und ein paar gezeichneten Flächen braucht das nicht, und
  weder mypy noch ruff sehen QML.
- **Keine IoC-Modularchitektur.** `src/app/appfactory.cpp` verdrahtet rund 45
  Module. Bei 167k Zeilen trägt das, bei retro-amps 12.522 Zeilen ist es Gerüst
  ohne Gegenwert.
- **Kein KDDockWidgets.** Lizenz, siehe oben.
- **Keine Farbwerte aus Audacity.** Lizenz, siehe Sperrvermerk.

---

## 5. Offene Punkte

- Ziehen und Andocken eines rahmenlosen Fensters über `startSystemMove` und
  `startSystemResize` ist **nicht** verifiziert (nur die Verfügbarkeit der
  Aufrufe). Braucht eine Probe von Hand.
- Die Repo-Frage aus dem Memory `project_shared_core_tui_gui`: ein Repo mit
  gemeinsamem Kern und zwei Oberflächen als Extras, statt eines zweiten Repos
  neben der TUI. Bei retro-amp hieße das ein Umbau des bestehenden Repos auf
  `src/retro_amp/{tui,gui}`, nicht Neuanlage. Noch nicht entschieden.
- Wie viele Player-Schlüssel es am Ende werden, ergibt sich erst beim Zeichnen
  der ersten Fläche. Die Liste in Schritt 1 ist ein Anfang, keine Festlegung.
