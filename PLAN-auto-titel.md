# Feature-Plan: Auto-Titel (fehlende Dateinamen ergaenzen)

Status: Stufe 1-3 umgesetzt am 18.07.2026 (noch nicht committet).

## Umsetzungsstand (18.07.2026)

- **Stufe 1 (ID3):** fertig, am echten Terminal getestet (Ordner ohne Titel-Tags
  meldet korrekt "kein sicherer Treffer").
- **Stufe 3 (MusicBrainz):** fertig. `infrastructure/musicbrainz_client.py`
  (Stdlib-urllib, KEIN httpx - httpx ist keine Repo-Dependency). Gates: exakte
  Track-Anzahl, Mehrdeutigkeit -> None, Dauer-Plausibilitaet. Nicht vorausgewaehlt.
- **Edge-Case "Dateiname gut, Tag fehlt/generisch":** generische Tags
  ("Track 01") gelten als fehlend; steckt der gefundene Titel schon im
  Dateinamen, wird NUR der Tag gesetzt (kein Rename, `proposed_name==""`).
  Zusaetzlich Tier "Dateiname-Fallback": letzte Option, Titel aus dem Dateinamen
  in den Tag (nur Tag), nicht vorausgewaehlt, per Settings abschaltbar.
- **Panel-Refresh:** nach dem Anwenden werden rechte Tabelle (immer) und linker
  Baum (`reload_dir`, nur bei Umbenennung, ohne Kollaps) aktualisiert.
- **Stufe 2 (AcoustID):** Code fertig. `infrastructure/acoustid_client.py`
  (fpcalc via Subprocess + AcoustID-API via urllib, injizierbar fuer Tests).
  Vorausgewaehlt (bestaetigt). Reihenfolge im Service: ID3 -> AcoustID -> MB.
- **Settings-Tab "Auto-Titel":** MusicBrainz-Schalter (Default an), AcoustID-
  Schalter (Default aus) + maskiertes API-Key-Feld (`auto_title_acoustid_key`).
- **fpcalc-Bundling:** in alle drei compile-Skripte (kopiert fpcalc neben die
  Binary, konditional). Runtime-Detection: PATH oder neben der Executable.
- **Verifiziert:** ruff sauber, mypy-Baseline unveraendert, 158 Tests; echte
  MP3-/MB-/AcoustID-Integration + Settings-Tab headless bestaetigt.
- **Fuer AcoustID LIVE noch noetig (Michael):** fpcalc (Chromaprint) auf PATH
  bzw. installiert + kostenloser API-Key von acoustid.org im Settings-Tab.

---


## Ziel

Audio-Dateien, deren Titel im Dateinamen fehlt (`01.mp3`, `Track 01.mp3`, ...),
automatisch mit dem echten Titel versehen - **umbenennen UND** den Titel in den
ID3-Tag (`TIT2`) schreiben. Auf einem ganzen Ordner/Album als Batch. Ein
Vorschau-Dialog zeigt alle Aenderungen; der Nutzer bestaetigt oder bricht ab.

## Grundregel: "100% abgesichert, kein Gerate"

Nur zwei Wege raten wirklich nicht:

1. **Eingebettete Tags** (`TIT2` etc.) - deterministisch.
2. **Audio-Fingerprint** (AcoustID + Chromaprint/`fpcalc`) - matcht das echte
   Audio gegen die AcoustID-Datenbank.

Ordnername=Album + Dateinummer=Track -> MusicBrainz-Trackliste ist eine
**Heuristik** (mehrere Releases mit abweichenden Tracklisten moeglich). Sie ist
als 2. Stufe zugelassen, aber im Vorschau-Dialog klar gekennzeichnet und
**nicht vorausgewaehlt** - der Nutzer muss sie aktiv anhaken.

Ehrliche Erwartung: obskure Soundtracks (z.B. Franco Micalizzi, 1969) sind oft
nicht in AcoustID -> dann kommt korrekt "kein sicherer Treffer" zurueck.

## Confidence-Tiers

| Tier | Quelle | Bedingung | Vorschau |
| ---- | ------ | --------- | -------- |
| 0 | `ID3` | `TIT2`/Title-Tag vorhanden | bestaetigt, vorausgewaehlt |
| 1 | `AcoustID` | Fingerprint-Score >= 0.85, eindeutiger Recording-Titel | bestaetigt, vorausgewaehlt |
| 2 | `MusicBrainz (Trackliste)` | genau ein Release matcht Artist+Album, Track-Anzahl == Dateianzahl, Dauern innerhalb Toleranz | hohe Wahrscheinlichkeit, **nicht** vorausgewaehlt |
| - | (kein Treffer) | - | grau, nicht anwaehlbar, Datei bleibt |

Artist/Album fuer Tier 2: bevorzugt aus vorhandenen `TPE1`/`TALB`-Tags (oft
gesetzt, obwohl `TIT2` fehlt), sonst aus dem Ordnernamen (Heuristik -> weiterer
Grund fuer "nicht vorausgewaehlt").

MusicBrainz-Lookup: **einmal pro Album** (nicht pro Datei), Zuordnung ueber
Tracknummer. Respektiert das 1-req/sec-Limit, braucht einen User-Agent.

## Entscheidungen (abgestimmt)

- Lookup-Quelle: **Fingerprint (AcoustID) + MB-Trackliste** als 2. Stufe.
- Schreibziel: **Umbenennen + ID3-Tag** (`TIT2` fuellen).
- Namensschema: **`01 - Titel.mp3`** (Tracknummer nullbewahrt, Bindestrich).

## Architektur / neue Dateien

- `domain/models.py`: `TitleProposal`-Dataclass (path, current_name,
  proposed_title, proposed_name, source, confidence, selected_default) +
  Enums `MatchSource` / `MatchConfidence`.
- `services/tagging_service.py`: Orchestriert Tier 0 -> 1 -> 2 pro Datei,
  liefert `list[TitleProposal]`. Kennt nur `domain/` (DI via Protocol).
- `infrastructure/acoustid_client.py`: `fpcalc`-Aufruf (Chromaprint) +
  AcoustID-Web-API (httpx). Erkennt `fpcalc` (gebündelt/PATH). API-Key
  gebündelt (app-spezifischer AcoustID-Key).
- `infrastructure/musicbrainz_client.py`: MB WS/2 via httpx, Album->Trackliste,
  harte Gates fuer Tier 2.
- `screens/tag_preview_screen.py`: Batch-Vorschau `ModalScreen`, `DataTable`
  (Checkbox-Spalte, Alt -> Neu, Quelle/Sicherheit), Buttons `Bestaetigen` /
  `Abbrechen`. Gibt die akzeptierten Proposals zurueck.
- `app.py`: Binding `g` = "Titel holen" (`action_auto_title`), Worker holt
  Proposals (Semaphore + Timer-Progress), oeffnet Vorschau, wendet bei Bestaetigung
  an.
- `screens/settings_screen.py`: neuer Tab (AcoustID an/aus, MB-Trackliste an/aus,
  optional Namensschema). Via `app_tabs()` / `collect_app_settings()`.
- i18n: neue Keys in `locale/de.json` + `locale/en.json`.

## Anwenden (bei Bestaetigung)

1. **ID3-Tag schreiben** (`TIT2` via mutagen), auch `TPE1`/`TALB` falls aus MB
   sicher vorhanden.
2. **Umbenennen** nach `01 - Titel.mp3`:
   - Titel filesystem-sanitizen (`\ / : * ? " < > |` entfernen/ersetzen).
   - Zieldatei existiert bereits -> Zeile ueberspringen (nie ueberschreiben).
   - Laufenden Track/Playlist-/History-Pfade beachten: die vorhandene
     `_rename_with_unload`-Logik wiederverwenden; nach Batch die betroffenen
     Playlist-/History-Eintraege auf die neuen Pfade aktualisieren.

## Abhaengigkeiten / Build

- `pyproject.toml`: `pyacoustid` (ruft `fpcalc`), `musicbrainzngs` optional oder
  MB direkt via httpx.
- `fpcalc`-Binary: im Nuitka-Build bündeln (Muster wie Playwright-Chromium:
  ins `dist/<tool>/`-Verzeichnis kopieren, zur Laufzeit ueber Env/PATH finden).
  `bootstrap` zieht `fpcalc` fuer die Dev-Umgebung.
- `uv.lock` mit den neuen Deps aktualisieren.

## Risiken / offen

- **Playlist-/History-Integritaet**: Batch-Rename kann Playlist-Pfade
  verwaisen lassen -> Update-Schritt Pflicht, sonst Tote-Links.
- **Undo** (optional): einfacher In-Session-Undo-Stack fuer den letzten Batch
  (Politur, nicht Kern).
- **fpcalc fehlt**: sauber degradieren (Tier 1 ueberspringen, Hinweis-Toast).
- **AcoustID/MB offline oder Rate-Limit**: pro Datei/Album abfangen, Zeile als
  "kein Treffer" markieren, nie blockieren.
- **mypy strict**: neue Clients/Service voll typisieren, keine nackten Generics.

## Verifikation

- Unit-Tests fuer `tagging_service` mit Mock-Clients (Tier-Logik, Gates).
- Headless-Test fuer `tag_preview_screen` (Auswahl, Bestaetigen/Abbrechen).
- Manuell an den echten Beispielordnern (Udo Lindenberg / Franco Micalizzi):
  belegen, dass der Soundtrack korrekt "kein Treffer" liefert und das
  Lindenberg-Album ueber Tier 1/2 auffuellt.
- `ruff` + `mypy src` sauber, `pytest` gruen.
