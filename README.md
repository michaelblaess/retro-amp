# retro-amp

Terminal-Musikplayer mit Retro-Charme — geschrieben in Python mit [Textual](https://textual.textualize.io/).

A terminal music player with retro charm — built with Python and [Textual](https://textual.textualize.io/).

```
┌──────────────────────────────────────────────────────────────────┐
│  retro-amp v0.4                          ♪ C64 — Commodore 64   │
├──────────────────┬───────────────────────────────────────────────┤
│                  │                                               │
│  MUSIK           │  ▶ autobahn.mp3      MP3  320kbps   22:43    │
│  ├─ Kraftwerk    │    modell.mp3        MP3  320kbps    3:39    │
│  ├─ C64          │    nummern.mp3       MP3  256kbps    4:12    │
│  └─ Amiga        │    roboter.mp3       MP3  320kbps    6:11    │
│                  │                                               │
├──────────────────┴───────────────────────────────────────────────┤
│  ▅▇█▃▆█▅▂▇▅▃▆█▇▅▂▄▆▃▅▇█▅▃▆▇▅▂▄▆  (Spektral-Visualizer / FFT) │
├──────────────────────────────────────────────────────────────────┤
│  ▶  Kraftwerk - Autobahn  [MP3 | 320 kbps]                     │
│      ████████████████░░░░░░░░  14:22 / 22:43   Vol: ████░░ 80% │
└──────────────────────────────────────────────────────────────────┘
```

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
retro-amp --version           # Zeigt die Version / Show version
```

## Features

- **Ordner-Browser** — Linkes Panel mit Verzeichnisbaum, filtert Audio-Dateien automatisch
- **Datei-Tabelle** — Rechtes Panel mit Name, Format, Bitrate, Dauer (via mutagen)
- **Audio-Playback** — MP3, OGG, FLAC, WAV, MOD/XM/S3M (via pygame.mixer)
- **Spektral-Visualizer** — Echte FFT-Analyse, 32 Frequenzbaender, Spektralfarben, Peak-Hold-Effekt
- **Playlists** — Als Markdown-Dateien gespeichert, Standard-Playlist "Favoriten"
- **6 Retro-Themes** — C64, Amiga Workbench, Atari ST GEM, IBM Terminal, NeXTSTEP, BeOS
- **Dateiverwaltung** — Umbenennen (U) und Loeschen (DEL) direkt aus dem Player
- **Settings-Persistenz** — Lautstaerke, letzter Ordner, Theme werden gespeichert

## Tastenbelegung / Keybindings

| Taste / Key | Aktion / Action |
|-------------|-----------------|
| `Space` | Play / Pause |
| `N` | Naechster Song / Next track |
| `B` | Vorheriger Song / Previous track |
| `←` `→` | Vor- / Zurueckspulen (5s) / Seek forward/backward |
| `↑` `↓` | Navigation in der Liste / Navigate list |
| `Enter` | Song abspielen / Ordner oeffnen / Play track / Open folder |
| `+` `-` | Lautstaerke / Volume |
| `F` | Favorit hinzufuegen/entfernen / Toggle favorite |
| `P` | Playlist-Menue / Playlist menu |
| `U` | Datei umbenennen / Rename file |
| `DEL` | Datei loeschen / Delete file |
| `T` | Theme wechseln / Cycle theme |
| `Q` | Beenden / Quit |

## Themes

Mit `T` durch die Themes wechseln. / Press `T` to cycle through themes.

| Theme | Inspiration | Typ |
|-------|-------------|-----|
| **C64** | Commodore 64 (1982) | Dark — Blau/Hellblau |
| **Amiga** | Workbench 1.3 (1987) | Dark — Blau/Weiss/Orange |
| **Atari ST** | GEM Desktop (1985) | Light — Weiss/Schwarz/Gruen |
| **IBM Terminal** | IBM 3278 (1970er) | Dark — Phosphor-Gruen auf Schwarz |
| **NeXTSTEP** | NeXTSTEP (1989) | Dark — Grau mit Lila-Akzenten |
| **BeOS** | BeOS (1995) | Dark — Blau-Grau mit Gelb |

Die Themes sind als eigenstaendiges Paket verfuegbar: [textual-themes](https://github.com/michaelblaess/textual-themes)

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
│   ├── metadata_reader.py # MutagenMetadataReader
│   ├── playlist_store.py  # MarkdownPlaylistStore
│   └── settings.py        # JsonSettingsStore
├── widgets/          # Textual Widgets
├── screens/          # Textual ModalScreens
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
| Themes | [textual-themes](https://github.com/michaelblaess/textual-themes) >= 0.1 |
| Testing | pytest, pytest-asyncio, pytest-cov |
| Type-Checking | mypy (strict) |

## Lizenz / License

Apache License 2.0 — siehe [LICENSE](LICENSE).

## Autor / Author

Michael Blaess — [GitHub](https://github.com/michaelblaess)
