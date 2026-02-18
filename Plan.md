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
│  Music           │  autobahn.mp3      320kbps   22:43           │
│  ├─ Kraftwerk    │  modell.mp3        320kbps    3:39           │
│  ├─ C64          │  nummern.mp3       256kbps    4:12           │
│  └─ Amiga        │                                               │
│                  │                                               │
├──────────────────┴───────────────────────────────────────────────┤
│  ▐▌▐▌▐▌ ▐▌▐▌ ▐▌▐▌▐▌▐▌ ▐▌ ▐▌▐▌▐▌ ▐▌▐▌  (Equalizer-Visualizer) │
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
| `←` / `→` | Vor- / Zurueckspulen |
| `↑` / `↓` | Navigation in der Liste |
| `Enter` | Song abspielen / Ordner oeffnen |
| `+` / `-` | Lautstaerke |
| `F` | Song zu Favoriten hinzufuegen |
| `P` | Playlist-Menue (erstellen / laden / hinzufuegen) |
| `T` | Theme wechseln |
| `L` | Log ein-/ausblenden |
| `Q` | Beenden |

Bindings nutzen `check_action()` — z.B. `N`/`B` nur sichtbar wenn Song geladen.

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

## Equalizer-Visualizer

- Rein visueller Effekt (kein echter EQ)
- ASCII/Unicode-Balken die zur Musik "tanzen"
- Passt sich dem aktiven Theme an (Farben aus TCSS)
- Animation via `set_interval()` Timer
- Zufaellige oder beat-basierte Animation

## Tech-Stack

| Komponente | Library |
|------------|---------|
| TUI-Framework | `textual >= 0.85` |
| Rich Text | `rich >= 13.0` |
| Validierung | `pydantic >= 2.0` |
| Audio-Playback | `pygame.mixer` (MOD-Support!) |
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
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── models.py        # AudioTrack, PlayerState, PlaylistEntry (dataclass)
│       │   │                    # AppConfig (pydantic)
│       │   └── protocols.py     # AudioPlayer(Protocol), PlaylistRepository(Protocol)
│       ├── services/
│       │   ├── __init__.py
│       │   ├── player_service.py    # Play/Pause/Next/Prev Logik
│       │   ├── playlist_service.py  # Playlist CRUD, Favoriten
│       │   └── metadata_service.py  # Audio-Metadaten lesen
│       ├── infrastructure/
│       │   ├── __init__.py
│       │   ├── audio_player.py      # pygame.mixer Implementation
│       │   ├── playlist_store.py    # Markdown-Datei I/O
│       │   ├── metadata_reader.py   # mutagen Wrapper
│       │   └── settings.py          # Settings JSON Persistence
│       ├── widgets/
│       │   ├── __init__.py
│       │   ├── folder_browser.py    # Tree-Widget (links)
│       │   ├── file_table.py        # DataTable-Widget (rechts)
│       │   ├── visualizer.py        # Equalizer-Balken
│       │   └── transport_bar.py     # Play/Pause/Progress/Volume
│       └── screens/
│           ├── __init__.py
│           ├── playlist_screen.py   # Playlist erstellen/laden/hinzufuegen
│           └── about_screen.py      # About-Dialog
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared Fixtures, Mock-Repos
│   ├── test_models.py
│   ├── test_player_service.py
│   ├── test_playlist_service.py
│   └── test_metadata_service.py
└── .github/
    └── workflows/
        └── release.yml          # Multi-Platform PyInstaller Build
```

## Meilensteine

### v0.1 — Grundgeruest
- [ ] Projektstruktur aus Template aufsetzen (pyproject.toml, src-Layout, setup.bat)
- [ ] Domain-Models: AudioTrack, PlayerState, AppConfig
- [ ] Protocols: AudioPlayer, PlaylistRepository
- [ ] Textual App mit Grundlayout (Tree links, DataTable rechts)
- [ ] Folder-Browser: Ordner navigieren, Audio-Dateien filtern
- [ ] Datei-Tabelle: Name, Format, Bitrate, Dauer (via mutagen)
- [ ] Audio-Playback: Play, Pause, Stop fuer MP3/OGG/FLAC/WAV (pygame.mixer)
- [ ] Basis-Tests fuer Domain-Models und Services

### v0.2 — Player-Funktionen
- [ ] Transport-Leiste mit Fortschrittsanzeige (render()-Pattern)
- [ ] Vor/Zurueck, Lautstaerke (+/-)
- [ ] Naechster/Vorheriger Song
- [ ] Tastenbelegung komplett mit check_action()
- [ ] Settings-Persistenz (~/.retro-amp/settings.json)

### v0.3 — Playlists & Favoriten
- [ ] PlaylistRepository Protocol + Markdown-Implementation
- [ ] Favoriten-System (Taste F → favorites.md)
- [ ] Playlist erstellen / laden / Songs hinzufuegen (ModalScreen)
- [ ] Playlist als Markdown lesen/schreiben
- [ ] Tests fuer Playlist-Service

### v0.4 — Retro-Vibes
- [ ] C64 Theme (TCSS)
- [ ] Amiga Workbench Theme (TCSS)
- [ ] Atari ST Theme (TCSS)
- [ ] Theme-Wechsel zur Laufzeit (watch_theme + Settings)
- [ ] Equalizer-Visualizer (set_interval + Unicode-Balken)

### v0.5 — Nostalgie-Formate
- [ ] SID-Playback (C64) — AudioPlayer Protocol erweitern
- [ ] MOD/XM/S3M-Playback (Amiga)

### v1.0 — Release
- [ ] Polishing, Bugfixes
- [ ] README mit Screenshots
- [ ] PyPI-Veroeffentlichung
- [ ] GitHub Actions Release-Workflow (PyInstaller, Multi-Platform)
- [ ] Optional: Umstieg auf SQLite fuer Playlists

## Referenz-Projekte

- `michaelblaess/sitemap-generator` — TUI-Crawler, gleiches Architektur-Pattern
- `michaelblaess/console-error-scanner` — TUI-Scanner, gleiches Architektur-Pattern
- `michaelblaess/claude-config/templates/python-tui` — Projekt-Template (Startpunkt)
- `michaelblaess/claude-config/skills/python-specialist` — Skill mit allen Konventionen
