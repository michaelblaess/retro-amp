# retro-amp

[![Stars](https://img.shields.io/github/stars/michaelblaess/retro-amp?logo=github&color=fbbf24)](https://github.com/michaelblaess/retro-amp/stargazers)
[![Forks](https://img.shields.io/github/forks/michaelblaess/retro-amp?logo=github&color=34d399)](https://github.com/michaelblaess/retro-amp/network/members)
[![Issues](https://img.shields.io/github/issues/michaelblaess/retro-amp?logo=github&color=f87171)](https://github.com/michaelblaess/retro-amp/issues)
[![Pull Requests](https://img.shields.io/github/issues-pr/michaelblaess/retro-amp?logo=github&color=a78bfa)](https://github.com/michaelblaess/retro-amp/pulls)

[![Last Commit](https://img.shields.io/github/last-commit/michaelblaess/retro-amp?logo=git&color=3b82f6)](https://github.com/michaelblaess/retro-amp/commits/main)
[![License](https://img.shields.io/badge/license-Apache_2.0-3b82f6)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-3b82f6?logo=python)](https://www.python.org/)
[![Themes](https://img.shields.io/badge/themes-31-fbbf24)](https://github.com/michaelblaess/textual-themes)

Terminal-Musikplayer mit Retro-Charme — geschrieben in Python mit [Textual](https://textual.textualize.io/).

A terminal music player with retro charm — built with Python and [Textual](https://textual.textualize.io/).

![retro-amp v0.17.0 — Pixel-perfektes Cover-Rendering](docs/screenshots/00-cover-rendering.png)
*Pixel-perfektes Cover-Rendering via TGP / Sixel — im Terminal. / Pixel-perfect cover rendering via TGP / Sixel — in the terminal.*

![BeBox Theme](docs/screenshots/01-main.png)
*BeBox Theme — Ordner-Browser, Datei-Tabelle, Lyrics, Spektral-Visualizer*

| | |
|---|---|
| ![Classic Terminal](docs/screenshots/02-ibm-theme.png) | ![Boing](docs/screenshots/09-amiga-theme.png) |
| *Classic Terminal — Phosphor-Gruen* | *Boing — Blau/Orange* |

| | |
|---|---|
| ![Brotkasten Theme](docs/screenshots/05-c64-theme.png) | ![Lyrics](docs/screenshots/04-lyrics.png) |
| *Brotkasten — YouTube-Links* | *Lyrics — Original (Englisch)* |

## Installation

### One-Click Installer

Keine Abhaengigkeiten noetig — kein Python, kein Git. / No dependencies needed — no Python, no Git.

**Linux / macOS:**

```bash
curl -fsSL https://github.com/michaelblaess/retro-amp/releases/latest/download/install.sh | bash
```

**Windows (PowerShell als Administrator):**

```powershell
irm https://github.com/michaelblaess/retro-amp/releases/latest/download/install.ps1 | iex
```

### Installationspfade / Installation Paths

| Platform | Path |
|----------|------|
| Linux | `~/.local/bin/retro-amp` |
| macOS | `/usr/local/bin/retro-amp` |
| Windows | `C:\Program Files\retro-amp\retro-amp.exe` |

### Optionale Abhaengigkeit / Optional Dependency

Fuer M4A/AAC-Playback wird **ffmpeg** benoetigt. Ohne ffmpeg werden alle anderen Formate normal abgespielt — nur M4A/AAC wird uebersprungen (mit Log-Hinweis). / For M4A/AAC playback, **ffmpeg** is required. Without ffmpeg, all other formats play normally — only M4A/AAC is skipped (with log message).

```bash
# Windows
choco install ffmpeg        # oder: scoop install ffmpeg / winget install ffmpeg

# Linux
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

### Manuell / Manual (Python >= 3.12)

```bash
pip install git+https://github.com/michaelblaess/retro-amp.git
retro-amp
```

### Aus Quellcode / From Source

```bash
git clone https://github.com/michaelblaess/retro-amp.git
cd retro-amp
python -m venv .venv
.venv/Scripts/activate      # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -e ".[dev]"
retro-amp
```

## Benutzung / Usage

```bash
retro-amp                     # Startet mit Standard-Musikordner / Start with default music folder
retro-amp /pfad/zur/musik     # Startet in einem bestimmten Ordner / Start in specific folder
retro-amp song.mp3            # Spielt eine Datei direkt ab / Play a file directly
retro-amp --lang en           # Startet mit englischer Oberflaeche / Start with English UI
retro-amp --version           # Zeigt die Version / Show version
```

## Features

- **Ordner-Browser** — Linkes Panel mit Verzeichnisbaum, filtert Audio-Dateien automatisch
- **Favoriten-Ansicht** — Alle Favoriten als Baumstruktur, mit TAB umschalten
- **Playlist-Ansicht** — Playlists als Baumstruktur, Songs direkt abspielen oder entfernen
- **Datei-Tabelle** — Rechtes Panel mit Name, Format, Bitrate, Dauer (via mutagen)
- **Audio-Playback** — MP3, M4A/AAC, OGG/Opus, FLAC, WAV, MOD/XM/S3M, SID (via pygame.mixer + pyogg + ffmpeg)
- **Spektral-Visualizer** — Echte FFT-Analyse, 5 Darstellungs-Modi (Bars, Blocks, Scope, Matrix, LCD VU-Meter im Kassettendeck-Style), Theme-bewusste Farben. Modus per Right-Click auf den Visualizer wechseln oder im Settings-Tab "Visualizer" konfigurieren.
- **Synced Lyrics** — Zeitgestempelte Lyrics von [lrclib.net](https://lrclib.net), farbig synchronisiert (gespielt/aktuell/kommend), Click-to-Seek auf jede Zeile, Auto-Scroll mit 3s Timeout nach manuellem Scrollen
- **Liner Notes** — Wikipedia-Info zum aktuellen Artist (Taste I), automatisch gecached
- **Album Cover Art** — Eingebettete Cover aus Audio-Tags (ID3, FLAC, MP4) oder Bilddateien im Ordner (cover.jpg, folder.jpg, etc.), gerendert als Unicode Half-Blocks via [Pillow](https://pillow.readthedocs.io/)
- **Globale Suche mit Verlauf** — Dateien in der gesamten Bibliothek suchen; Klick ins Suchfeld zeigt die letzten 20 Suchanfragen, beim Tippen werden passende Eintraege gefiltert und Treffer hervorgehoben (Persistenz in SQLite). Treffer erscheinen im Tab "Suche" links als Baum, gruppiert nach uebergeordnetem Verzeichnis — bei mehreren Treffern im selben Album-Ordner steht der Pfad nur einmal.
- **Playlists** — Als Markdown-Dateien gespeichert, Standard-Playlist "Favoriten"
- **Shuffle & Repeat** — Shuffle-Modus (X) und Repeat Off/All/One (R), kombinierbar
- **31 Retro-Themes** — vintage 8-bit, terminal, Unix workstation, watch, comic-pulp und 80s-pastel Palettes (siehe [textual-themes](https://github.com/michaelblaess/textual-themes))
- **Mehrsprachig** — Deutsch (Standard) und Englisch, umschaltbar via `--lang`
- **Session-Recovery** — Nach einem Crash wird der letzte Track und Ordner wiederhergestellt (ohne Auto-Play)
- **Debug-Log** — Ausfuehrliches Log mit Artist/Titel, Pfaden, Events (Taste O)
- **Dateiverwaltung** — Umbenennen (U) und Loeschen (DEL) direkt aus dem Player
- **Settings-Persistenz** — Lautstaerke, letzter Ordner, Theme, Sprache werden gespeichert
- **Anpassbare Panels** — Mit der Maus kann die Groesse zwischen Datei-Browser links und Datei-Tabelle/Lyrics rechts (vertikaler Splitter) sowie zwischen Datei-Tabelle und Lyrics (horizontaler Splitter) frei eingestellt werden. Layout wird in Settings persistiert.
- **Datei-Verknuepfung** — Doppelklick auf Audio-Datei oeffnet retro-amp direkt
- **Single-Instance** — Zweiter Doppelklick sendet den Track an die laufende Instanz

## Tastenbelegung / Keybindings

| Taste / Key | Aktion / Action |
|-------------|-----------------|
| `Space` | Play / Pause |
| `+` `-` | Lautstaerke / Volume |
| `TAB` | Ansicht wechseln: Dateien → Favoriten → Playlists → Verlauf / Cycle view |
| `↑` `↓` | Navigation in der Liste / Navigate list |
| `Enter` | Song abspielen / Ordner oeffnen / Play track / Open folder |
| `F` | Favorit hinzufuegen/entfernen / Toggle favorite |
| `P` | Playlist-Menue / Playlist menu |
| `U` | Datei umbenennen / Rename file |
| `DEL` | Datei loeschen / Delete file |
| `T` | Theme wechseln / Cycle theme |
| `S` | Einstellungen / Settings |
| `I` | Info / About |
| `L` | Debug-Log ein-/ausblenden / Toggle debug log |
| `C` | Debug-Log kopieren / Copy debug log |
| `X` | Shuffle ein/aus / Toggle shuffle |
| `R` | Repeat: Off → All → One / Cycle repeat mode |
| `Q` | Beenden / Quit |

Naechster/Vorheriger Track, Seek (5 s) und Globale Suche sind ueber die Steuerleiste und die Suchleiste per Maus erreichbar. / Next/previous track, seeking (5 s) and global search are available via the control bar and search field (mouse).

## Dateiverknuepfung / File Association

retro-amp kann als Standard-Player fuer Audio-Dateien registriert werden. / retro-amp can be registered as default player for audio files.

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy Bypass -File register-file-types.ps1
```

**Windows (CMD):**

```batch
register-file-types.bat
```

**Linux:**

```bash
./register-file-types.sh
```

Doppelklick auf eine Audio-Datei startet retro-amp. Bei laufender Instanz wird der neue Track automatisch uebernommen (Single-Instance).

Double-click an audio file to start retro-amp. If already running, the new track is sent to the existing instance (single-instance).

## Themes

Mit `T` durch die Themes wechseln, oder per Theme-Picker (`Ctrl+P` →
"theme"). / Press `T` to cycle, or open the theme picker.

retro-amp registriert alle Themes aus dem
[textual-themes](https://github.com/michaelblaess/textual-themes) Paket
(31 Themes — Dark + Light, von 8-bit ueber Terminal-Phosphor bis zu
80s-Pastel und Comic-Pulp). Die komplette Galerie mit Live-Carousel:
**[michaelblaess.github.io/textual-themes](https://michaelblaess.github.io/textual-themes/)**.

> **Migration aus aelteren Versionen:** retro-amp 0.16+ migriert
> gespeicherte Theme-Slugs automatisch beim Laden — wer vorher z.B.
> `c64` als Lieblings-Theme hatte, landet auf dem umbenannten
> `brotkasten` ohne dass etwas zu tun ist.

## Spektral-Visualizer

- Echte FFT-basierte Analyse (stdlib `cmath`, kein numpy)
- 2048-Punkt-FFT mit Hann-Fenster
- 32 log-skalierte Frequenzbaender (20 Hz – 18 kHz)
- Spektralfarben: Rot (Bass) → Gelb → Gruen → Cyan → Blau (Hoehen)
- Peak-Hold mit fallendem Effekt
- 3-zeilige Multi-Row-Darstellung (24 Hoehenstufen)
- PCM-Laden im Hintergrund-Thread

## Playlists

Playlists werden als Markdown-Dateien in `~/.retro-amp/playlists/` gespeichert:

```markdown
# Favoriten

- D:\Dropbox\MUSIK\Kraftwerk\autobahn.mp3
- D:\Dropbox\MUSIK\C64\last_ninja.sid
```

- `F` — Song zu Favoriten hinzufuegen/entfernen
- `P` — Playlist-Menue: neue erstellen, bestehende laden, Song hinzufuegen

## Architektur / Architecture

Clean Architecture mit strikter Dependency Rule:

```
src/retro_amp/
├── domain/           # Models, Protocols — keine externen Imports
│   ├── models.py     #   AudioTrack, PlayerState, Playlist
│   └── protocols.py  #   AudioPlayer, MetadataReader, PlaylistRepository
├── services/         # Business-Logik — importiert nur domain/
│   ├── player_service.py
│   ├── playlist_service.py
│   └── metadata_service.py
├── infrastructure/   # Implementierungen — pygame, mutagen, JSON
│   ├── audio_player.py   # PygameAudioPlayer
│   ├── spectrum.py        # SpectrumAnalyzer (FFT)
│   ├── metadata_reader.py # MutagenMetadataReader + Cover-Art-Extraktion
│   ├── playlist_store.py  # MarkdownPlaylistStore
│   ├── settings.py        # JsonSettingsStore
│   ├── session.py         # Crash-Recovery (session.json)
│   └── single_instance.py # Single-Instance Lock + Play-Request
├── widgets/          # Textual Widgets
├── screens/          # Textual ModalScreens
├── i18n.py           # Internationalisierung (de/en)
├── locale/           # JSON-Sprachpakete (de.json, en.json)
├── themes.py         # Re-Export aus textual-themes
└── app.py            # Composition Root
```

## Entwicklung / Development

```bash
# Setup
git clone https://github.com/michaelblaess/retro-amp.git
cd retro-amp
python -m venv .venv
.venv/Scripts/activate      # Windows
pip install -e ".[dev]"

# Tests
pytest

# Type-Check
mypy src/

# Lokaler Build / Local Build (Standalone EXE)
pip install pyinstaller
pyinstaller retro-amp.spec --noconfirm
```

### Release erstellen / Create Release

```bash
git tag v0.4.0
git push origin v0.4.0
# GitHub Actions baut automatisch Windows/macOS/Linux Installer
```

## Tech-Stack

| Komponente / Component | Library |
|------------------------|---------|
| TUI-Framework | [Textual](https://textual.textualize.io/) >= 0.85 |
| Rich Text | [Rich](https://rich.readthedocs.io/) >= 13.0 |
| Audio-Playback | [pygame.mixer](https://www.pygame.org/) >= 2.5 |
| Audio-Metadaten | [mutagen](https://mutagen.readthedocs.io/) >= 1.47 |
| Album Cover Art | [Pillow](https://pillow.readthedocs.io/) >= 10.0 |
| Cover-Rendering (TGP/Sixel) | [textual-image](https://github.com/lnqs/textual-image) >= 0.12 |
| Themes | [textual-themes](https://github.com/michaelblaess/textual-themes) >= 0.5 |
| UI-Widgets (Such-Verlauf, Kontextmenue, Splitter) | [textual-widgets](https://github.com/michaelblaess/textual-widgets) >= 0.5.2 |
| Lyrics-API | [lrclib.net](https://lrclib.net/) (synced + plain) |
| Testing | pytest, pytest-asyncio, pytest-cov |
| Type-Checking | mypy (strict) |

## Inspiration & Dank / Credits

Synced Lyrics, Album Art Rendering und Session-Recovery wurden inspiriert von [ytm-player](https://github.com/peternaame-boop/ytm-player) — einem YouTube-Music-Player in Textual.

Mehrere Visualizer-Modi und das UX-Konzept "Player-First, Fokus auf Tastatur" wurden inspiriert von [cliamp](https://github.com/bjarneo/cliamp) ([cliamp.stream](https://www.cliamp.stream/)) von **[@bjarneo](https://github.com/bjarneo)** — einem Winamp-inspirierten Terminal-Player in Go.

Pixelgenaues Cover-Rendering via TGP (Kitty-Protokoll) und Sixel basiert auf der grossartigen [textual-image](https://github.com/lnqs/textual-image) von **[@lnqs](https://github.com/lnqs)** — herzlichen Dank!

Synced lyrics, album art rendering, and session recovery were inspired by [ytm-player](https://github.com/peternaame-boop/ytm-player) — a YouTube Music player built with Textual.

Multiple visualizer modes and the "player-first, keyboard-driven" UX approach were inspired by [cliamp](https://github.com/bjarneo/cliamp) ([cliamp.stream](https://www.cliamp.stream/)) by **[@bjarneo](https://github.com/bjarneo)** — a Winamp-inspired terminal player written in Go.

Pixel-perfect cover rendering via TGP (Kitty protocol) and Sixel is powered by the wonderful [textual-image](https://github.com/lnqs/textual-image) library by **[@lnqs](https://github.com/lnqs)** — many thanks!

## Lizenz / License

Apache License 2.0 — siehe [LICENSE](LICENSE).

## Autor / Author

Michael Blaess — [GitHub](https://github.com/michaelblaess)
