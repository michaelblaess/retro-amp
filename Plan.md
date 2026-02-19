# retro-amp

Ein Terminal-Musikplayer mit Retro-Charme — geschrieben in Python mit Textual.

## Vision

Es gibt genug Musikplayer, aber keiner fühlt sich richtig an. retro-amp ist ein TUI-Musikplayer für Leute, die mit C64, Amiga und Atari ST aufgewachsen sind. Ordner durchstöbern, Musik hören, Lieblingssongs sammeln — alles im Terminal, alles mit der Tastatur.

## Konventionen & Architektur

Basierend auf dem Python-Specialist-Skill und den bestehenden Projekten (sitemap-generator, console-error-scanner).

### Clean Architecture — Dependency Rule

```
domain/       → kennt NICHTS (pure Python, keine externen Imports)
services/     → importiert nur aus domain/, NIE aus infrastructure/
infrastructure/ → implementiert Protocols aus domain/
app.py / widgets/ / screens/ → Composition Root, verdrahtet alles
```

### Verbindliche Regeln

- **src-Layout**: `src/retro_amp/` (moderner Standard, verhindert Import-Konflikte)
- **Python >= 3.12**, `from __future__ import annotations` in jeder Datei
- **Absolute Imports in `__main__.py`** (PyInstaller-Regel), relative Imports ueberall sonst
- **pydantic** fuer externe/validierte Daten (Config, Playlist-Dateien)
- **dataclass** fuer internes (UI-State, Audio-State)
- **Protocol** statt ABC fuer Interfaces (strukturelles Typing)
- **mypy strict** muss durchlaufen
- **pytest** mit `asyncio_mode = "auto"`
- **Deutsche UI-Texte**, englische Variablen-/Klassennamen
- **Umlaute vermeiden** im Code (ue, ae, oe) — ASCII-sicher fuer Terminals
- **Niemals crashen** — graceful Fallbacks, `except Exception` mit sinnvollem Default

### Textual-Patterns (aus bestehenden Projekten)

- `CSS_PATH = "app.tcss"` fuer globales Layout
- `DEFAULT_CSS` auf Widgets fuer komponenten-spezifisches Styling
- CSS-Toggle: `display: block` default + `.hidden { display: none; }` + `toggle_class("hidden")`
- Custom `Message`-Klassen fuer Widget-zu-App-Kommunikation
- `@work(exclusive=True, group="...")` fuer Background-Tasks
- Dynamische Binding-Labels: `dataclasses.replace()` + `refresh_bindings()`
- `check_action()` fuer bedingte Bindings (ausblenden wenn nicht relevant)
- Lazy Imports fuer Screens (in action-Methoden importieren)
- `query_one()` mit Typ-Parameter fuer Widget-Lookup
- Spinner/Animation: Full Table Rebuild statt `update_cell()`
- `ModalScreen[T | None]` mit typed `dismiss()` + Callback
- `priority=True` auf App-Level Bindings um Widget-Key-Capture zu uebersteuern

### Callback-basierte Entkopplung

Der Audio-Player kennt kein Textual. Kommunikation ueber Callbacks:
```python
player.play(path, on_progress=callback, on_finished=callback, on_error=callback)
```

### Settings-Pattern

```python
~/.retro-amp/settings.json   # Theme, Lautstaerke, letzter Ordner
```
Fail-safe Loading: bei korrupter Datei → Defaults verwenden, nie crashen.

## Audio-Formate

| Format | Library | Notiz |
|--------|---------|-------|
| MP3 | `pygame.mixer` / `miniaudio` | Standard |
| OGG | `pygame.mixer` / `miniaudio` | Standard |
| FLAC | `pygame.mixer` / `miniaudio` | Standard |
| WAV | `pygame.mixer` / `miniaudio` | Standard |
| SID (C64) | `libsidplayfp` / Subprocess | Nostalgie! |
| MOD/XM/S3M (Amiga) | `pygame.mixer` | Nativer Support |

## UI-Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  retro-amp v0.1                              ♪ C64 Theme        │
├──────────────────┬───────────────────────────────────────────────┤
│                  │                                               │
│  Folder-Browser  │  Dateiliste (Tabelle)                        │
│  (Tree-Widget)   │  Name | Format | Bitrate | Dauer             │
│                  │                                               │
│  Music           │  ▶ autobahn.mp3     320kbps   22:43          │
│  ├─ Kraftwerk    │  modell.mp3         320kbps    3:39          │
│  ├─ C64          │  nummern.mp3        256kbps    4:12          │
│  └─ Amiga        │                                               │
│                  │                                               │
├──────────────────┴───────────────────────────────────────────────┤
│  ▐▌▐▌▐▌ ▐▌▐▌ ▐▌▐▌▐▌▐▌ ▐▌ ▐▌▐▌▐▌ ▐▌▐▌  (Spektral-Visualizer)  │
├──────────────────────────────────────────────────────────────────┤
│  ► autobahn.mp3          ██████████░░░░░  14:22 / 22:43         │
│  [◄◄] [▶/▐▐] [►►] [🔀] [🔁]       Vol: ████████░░  80%        │
└──────────────────────────────────────────────────────────────────┘
```

## Themes

| Theme | Inspiration | Farben |
|-------|-------------|--------|
| **C64** | Commodore 64 | Blau (#4040E0) auf Hellblau (#7878FF), PETSCII-Rahmen |
| **Amiga** | Workbench 1.3 | Weiss/Orange auf Blau (#0055AA) |
| **Atari ST** | GEM Desktop | Weiss auf Gruen, monochrome Akzente |

Theme-Wechsel per Taste `T` zur Laufzeit. Theme wird in Settings persistiert (`watch_theme()`-Pattern).

## Tastenbelegung

| Taste | Aktion |
|-------|--------|
| `Space` | Play / Pause |
| `N` | Naechster Song |
| `B` | Vorheriger Song |
| `←` / `→` | Vor- / Zurueckspulen (5s) |
| `↑` / `↓` | Navigation in der Liste |
| `Enter` | Song abspielen / Ordner oeffnen |
| `+` / `-` | Lautstaerke |
| `F` | Song zu Favoriten hinzufuegen/entfernen |
| `P` | Playlist-Menue (erstellen / laden / hinzufuegen) |
| `U` | Datei umbenennen |
| `DEL` | Datei loeschen (mit Bestaetigung) |
| `T` | Theme wechseln |
| `L` | Log ein-/ausblenden |
| `Q` | Beenden |

Bindings nutzen `check_action()` — z.B. `N`/`B` nur sichtbar wenn Song geladen.
Alle App-Level Bindings mit `priority=True` um Widget-Key-Capture zu uebersteuern.

## Playlists

- Playlists werden als Markdown-Dateien gespeichert in `~/.retro-amp/playlists/`
- Standard-Playlist: `favorites.md` (Lieblingssongs)
- Taste `F` fuegt aktuellen Song zu Favoriten hinzu
- Taste `P` oeffnet Playlist-Menue (neue erstellen, bestehende laden, Song hinzufuegen)
- Spaeterer Umstieg auf SQLite geplant

### Playlist-Format (Markdown)

```markdown
# Lieblingssongs

- /home/michael/music/kraftwerk/autobahn.mp3
- /home/michael/music/c64/last_ninja.sid
- /home/michael/music/amiga/stardust_memories.mod
```

## Spektral-Visualizer

- **Echte FFT-basierte Spektralanalyse** (stdlib cmath, kein numpy)
- 2048-Punkt-FFT mit Hann-Fenster, PCM via `pygame.mixer.Sound.get_raw()`
- 32 log-skalierte Frequenzbaender (20 Hz – 18 kHz)
- 3-zeilige Multi-Row-Darstellung (24 diskrete Hoehenstufen via Unicode-Bloecke)
- **Spektralfarben** pro Band: Rot (Bass) → Gelb → Gruen → Cyan → Blau (Hoehen)
- **Peak-Hold mit Falleffekt**: Peaks halten kurz, dann sanft fallen
- PCM-Laden im Background-Thread (`@work(thread=True)`)
- Fallback auf simulierte Zufallswerte waehrend PCM laedt
- Animation via `set_interval(1/12)` Timer (12 fps)

## Dateiverwaltung

- `U` — Datei umbenennen (RenameScreen, Input mit aktuellem Namen)
- `DEL` — Datei loeschen (ConfirmScreen mit Sicherheitsabfrage)
- Nach Umbenennen/Loeschen wird das Verzeichnis automatisch neu gescannt
- Wenn die geloeschte Datei gerade spielt → naechster Track oder Stop

## Tech-Stack

| Komponente | Library |
|------------|---------|
| TUI-Framework | `textual >= 0.85` |
| Rich Text | `rich >= 13.0` |
| Validierung | `pydantic >= 2.0` |
| Audio-Playback | `pygame.mixer` (Buffer 4096, MOD-Support!) |
| Audio-Metadaten | `mutagen` |
| SID-Playback | `libsidplayfp` oder `sidplayfp` (Subprocess) |
| HTTP (optional) | `httpx >= 0.25` |
| Testing | `pytest >= 8.0`, `pytest-asyncio`, `pytest-cov` |
| Type-Checking | `mypy >= 1.8` (strict) |

## Projektstruktur (Clean Architecture + src-Layout)

```
retro-amp/
├── pyproject.toml
├── setup.bat                    # Automatisches Setup (.venv + deps)
├── run.bat / run.ps1            # Start-Skripte
├── .gitignore
├── Plan.md
├── README.md
├── src/
│   └── retro_amp/
│       ├── __init__.py          # __version__, __author__, __year__
│       ├── __main__.py          # CLI Entry Point (argparse, absolute Imports!)
│       ├── app.py               # Textual App — Composition Root
│       ├── app.tcss             # Globales Layout-CSS
│       ├── themes.py            # Retro-Themes (C64, Amiga, Atari ST)
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── models.py        # AudioTrack, PlayerState, PlaylistEntry (dataclass)
│       │   │                    # AppConfig (pydantic)
│       │   └── protocols.py     # AudioPlayer, MetadataReader, PlaylistRepository, SettingsStore
│       ├── services/
│       │   ├── __init__.py
│       │   ├── player_service.py    # Play/Pause/Next/Prev/Seek Logik
│       │   ├── playlist_service.py  # Playlist CRUD, Favoriten
│       │   └── metadata_service.py  # Audio-Metadaten lesen + Verzeichnis scannen
│       ├── infrastructure/
│       │   ├── __init__.py
│       │   ├── audio_player.py      # PygameAudioPlayer (pygame.mixer)
│       │   ├── spectrum.py          # SpectrumAnalyzer (FFT, PCM, Frequenzbaender)
│       │   ├── playlist_store.py    # MarkdownPlaylistStore (Markdown I/O)
│       │   ├── metadata_reader.py   # MutagenMetadataReader (mutagen Wrapper)
│       │   └── settings.py          # JsonSettingsStore (JSON Persistence)
│       ├── widgets/
│       │   ├── __init__.py
│       │   ├── folder_browser.py    # FolderBrowser (DirectoryTree, Audio-Filter)
│       │   ├── file_table.py        # FileTable (DataTable, Playing-Marker)
│       │   ├── visualizer.py        # Visualizer (Spektral-FFT, Peaks, Farben)
│       │   └── transport_bar.py     # TransportBar (Status, Fortschritt, Volume)
│       └── screens/
│           ├── __init__.py
│           ├── playlist_screen.py   # PlaylistScreen (erstellen/laden/hinzufuegen)
│           ├── rename_screen.py     # RenameScreen (Datei umbenennen)
│           └── confirm_screen.py    # ConfirmScreen (Loeschbestaetigung)
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared Fixtures, Mock-Repos
│   ├── test_models.py           # 27 Tests: AudioFormat, AudioTrack, PlayerState, Playlist
│   ├── test_player_service.py   # 16 Tests: Play, Pause, Seek, Next/Prev, Volume, Callbacks
│   ├── test_playlist_service.py # 15 Tests: Favoriten, Playlist CRUD
│   ├── test_metadata_service.py #  4 Tests: Metadata lesen, Verzeichnis scannen
│   ├── test_spectrum.py         #  7 Tests: FFT, SpectrumAnalyzer
│   └── test_themes.py           #  7 Tests: Theme-Definitionen
└── .github/
    └── workflows/
        └── release.yml          # Multi-Platform PyInstaller Build
```

## Meilensteine

### v0.1 — Grundgeruest ✅

- [x] Projektstruktur aus Template aufsetzen (pyproject.toml, src-Layout, setup.bat)
- [x] Domain-Models: AudioTrack, PlayerState, Playlist, PlaylistEntry
- [x] Protocols: AudioPlayer, MetadataReader, PlaylistRepository, SettingsStore
- [x] Textual App mit Grundlayout (Tree links, DataTable rechts)
- [x] Folder-Browser: Ordner navigieren, Audio-Dateien filtern
- [x] Datei-Tabelle: Name, Format, Bitrate, Dauer (via mutagen)
- [x] Audio-Playback: Play, Pause, Stop fuer MP3/OGG/FLAC/WAV (pygame.mixer)
- [x] Basis-Tests fuer Domain-Models und Services

### v0.2 — Player-Funktionen ✅

- [x] Transport-Leiste mit Fortschrittsanzeige (render()-Pattern)
- [x] Vor/Zurueck (Seek ±5s), Lautstaerke (+/-)
- [x] Naechster/Vorheriger Song, Auto-Next
- [x] Tastenbelegung komplett mit check_action()
- [x] Settings-Persistenz (~/.retro-amp/settings.json)
- [x] Polished Transport: Artist-Title, Format, Bitrate, farbige Icons

### v0.3 — Playlists & Favoriten ✅

- [x] PlaylistRepository Protocol + Markdown-Implementation
- [x] Favoriten-System (Taste F → favorites.md)
- [x] Playlist erstellen / laden / Songs hinzufuegen (PlaylistScreen)
- [x] Playlist als Markdown lesen/schreiben
- [x] Tests fuer Playlist-Service (15 Tests)

### v0.3.1 — Bugfixes & Spectrum-Analyzer ✅

- [x] BUG: N/B Tasten gingen nicht im Baum/Liste → priority=True auf alle Bindings
- [x] BUG: Visualizer lief weiter nach Track-Ende → _sync_visualizer() Methode
- [x] Echte FFT-basierte Spektralanalyse (stdlib cmath, kein numpy)
- [x] Multi-Row Visualizer mit Spektralfarben und Peak-Hold-Falleffekt
- [x] ▶ Playing-Indikator in der Dateiliste (gruen + bold)
- [x] Datei umbenennen mit U (RenameScreen)
- [x] Datei loeschen mit DEL (ConfirmScreen mit Sicherheitsabfrage)
- [x] 69 Tests alle gruen

### v0.4 — Retro-Vibes ✅

- [x] C64 Theme — Blau auf Hellblau (#40318D / #7878FF), der Klassiker
- [x] Amiga Workbench Theme — Blau/Weiss/Orange (#0055AA / #FF8800)
- [x] Atari ST GEM Theme — Weiss/Schwarz/Gruen (light theme)
- [x] Theme-Wechsel zur Laufzeit mit T-Taste (zyklisch: C64 → Amiga → Atari)
- [x] Theme wird in Settings persistiert, beim Start geladen
- [x] Theme-Name in der Titelleiste
- [x] 76 Tests alle gruen

### v0.5 — Nostalgie-Formate ✅

- [x] MOD/XM/S3M-Playback (Amiga) — funktioniert nativ via pygame.mixer
- [x] Tracker-Metadaten: Titel aus MOD/S3M/XM-Header gelesen
- [x] SID-Playback (C64) — per sidplayfp Subprocess (optional, braucht sidplayfp)
- [x] SID-Metadaten: Titel + Artist aus PSID/RSID-Header gelesen
- [x] OGG/Opus-Playback via pyogg (pygame's SDL_mixer kann nur Vorbis)

### v0.6 — Liner Notes (Wikipedia-Info) ✅

- [x] Wikipedia-API abfragen (deutsch + englisch Fallback)
- [x] Smarte Suche: "{artist} Band"/"Musiker" mit Musik-Relevanz-Check
- [x] Ergebnisse als Markdown gecached in `~/.retro-amp/notes/{artist}.md`
- [x] Cache: nur einmal pro Artist abfragen, nicht bei jedem Play
- [x] Info-Screen per Taste `I` (ModalScreen, ESC zum Schliessen)
- [x] Daten aus ID3-Tags als Suchbegriffe (Artist, Fallback: display_name)
- [x] Graceful: kein Internet → "Keine Informationen gefunden"
- [x] 99 Tests alle gruen

### v1.0 — Release

- [ ] Polishing, Bugfixes
- [ ] README mit Screenshots
- [ ] PyPI-Veroeffentlichung
- [x] GitHub Actions Release-Workflow (PyInstaller, Multi-Platform)
- [ ] Optional: Umstieg auf SQLite fuer Playlists

## Referenz-Projekte

- `michaelblaess/sitemap-generator` — TUI-Crawler, gleiches Architektur-Pattern
- `michaelblaess/console-error-scanner` — TUI-Scanner, gleiches Architektur-Pattern
- `michaelblaess/claude-config/templates/python-tui` — Projekt-Template (Startpunkt)
- `michaelblaess/claude-config/skills/python-specialist` — Skill mit allen Konventionen
