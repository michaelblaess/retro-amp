# retro-amp

Ein Terminal-Musikplayer mit Retro-Charme — geschrieben in Python mit Textual.

## Vision

Es gibt genug Musikplayer, aber keiner fühlt sich richtig an. retro-amp ist ein TUI-Musikplayer für Leute, die mit C64, Amiga und Atari ST aufgewachsen sind. Ordner durchstöbern, Musik hören, Lieblingssongs sammeln — alles im Terminal, alles mit der Tastatur.

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
│  📁 Music        │  ♪ autobahn.mp3      320kbps   22:43         │
│  ├─ 📁 Kraftwerk │  ♪ modell.mp3        320kbps    3:39         │
│  ├─ 📁 C64       │  ♪ nummern.mp3       256kbps    4:12         │
│  └─ 📁 Amiga     │                                               │
│                  │                                               │
├──────────────────┴───────────────────────────────────────────────┤
│  ▐▌▐▌▐▌ ▐▌▐▌ ▐▌▐▌▐▌▐▌ ▐▌ ▐▌▐▌▐▌ ▐▌▐▌  (Equalizer-Visualizer) │
├──────────────────────────────────────────────────────────────────┤
│  ► autobahn.mp3   advancement  ██████████░░░░░  14:22 / 22:43         │
│  [◄◄] [▶/▐▐] [►►] [🔀] [🔁]       Vol: ████████░░  80%         │
└──────────────────────────────────────────────────────────────────┘
```

## Themes

| Theme | Inspiration | Farben |
|-------|-------------|--------|
| **C64** | Commodore 64 | Blau (#4040E0) auf Hellblau (#7878FF), PETSCII-Rahmen |
| **Amiga** | Workbench 1.3 | Weiß/Orange auf Blau (#0055AA) |
| **Atari ST** | GEM Desktop | Weiß auf Grün, monochrome Akzente |

Theme-Wechsel per Tastenkürzel zur Laufzeit.

## Tastenbelegung

| Taste | Aktion |
|-------|--------|
| `Space` | Play / Pause |
| `N` | Nächster Song |
| `B` | Vorheriger Song |
| `←` / `→` | Vor- / Zurückspulen |
| `↑` / `↓` | Navigation in der Liste |
| `Enter` | Song abspielen / Ordner öffnen |
| `+` / `-` | Lautstärke |
| `F` | Song zu Favoriten hinzufügen |
| `P` | Playlist-Menü (erstellen / laden / hinzufügen) |
| `T` | Theme wechseln |
| `Q` | Beenden |

## Playlists

- Playlists werden als Markdown-Dateien gespeichert
- Standard-Playlist: `favorites.md` (Lieblingssongs)
- Taste `F` fügt aktuellen Song zu Favoriten hinzu
- Taste `P` öffnet Playlist-Menü (neue erstellen, bestehende laden, Song hinzufügen)
- Späterer Umstieg auf SQLite geplant

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
- Passt sich dem aktiven Theme an
- Zufällige oder beat-basierte Animation

## Tech-Stack

| Komponente | Library |
|------------|---------|
| TUI-Framework | `textual` |
| Audio-Playback | `pygame.mixer` (MOD-Support!) + `miniaudio` als Alternative |
| Audio-Metadaten | `mutagen` |
| SID-Playback | `libsidplayfp` oder `sidplayfp` als Subprocess |
| Playlists | Markdown-Dateien (später SQLite) |
| Config | TOML oder YAML |

## Projektstruktur

```
retro-amp/
├── retro_amp/
│   ├── __init__.py
│   ├── app.py              # Textual App, Hauptfenster
│   ├── player.py            # Audio-Engine (play, pause, next, prev)
│   ├── browser.py           # Folder-Browser Widget
│   ├── filelist.py          # Datei-Tabelle Widget
│   ├── visualizer.py        # Equalizer-Visualizer Widget
│   ├── transport.py         # Transport-Leiste Widget (Play/Pause/etc.)
│   ├── playlist.py          # Playlist-Management (Markdown I/O)
│   ├── metadata.py          # Audio-Metadaten lesen (mutagen)
│   ├── themes/
│   │   ├── c64.tcss         # C64 Theme
│   │   ├── amiga.tcss       # Amiga Workbench Theme
│   │   └── atari_st.tcss    # Atari ST GEM Theme
│   └── config.py            # Konfiguration laden/speichern
├── playlists/
│   └── favorites.md         # Standard-Playlist
├── pyproject.toml
├── Plan.md
└── README.md
```

## Meilensteine

### v0.1 — Grundgerüst
- [ ] Projektstruktur aufsetzen (pyproject.toml, Dependencies)
- [ ] Textual App mit Grundlayout (Tree links, Tabelle rechts)
- [ ] Folder-Browser: Ordner navigieren, Audio-Dateien anzeigen
- [ ] Datei-Tabelle: Name, Format, Bitrate, Dauer
- [ ] Audio-Playback: Play, Pause, Stop für MP3/OGG/FLAC/WAV

### v0.2 — Player-Funktionen
- [ ] Transport-Leiste mit Fortschrittsanzeige
- [ ] Vor/Zurück, Lautstärke
- [ ] Nächster/Vorheriger Song
- [ ] Tastenbelegung komplett

### v0.3 — Playlists & Favoriten
- [ ] Favoriten-System (Taste F → favorites.md)
- [ ] Playlist erstellen / laden / Songs hinzufügen
- [ ] Playlist als Markdown lesen/schreiben

### v0.4 — Retro-Vibes
- [ ] C64 Theme
- [ ] Amiga Workbench Theme
- [ ] Atari ST Theme
- [ ] Theme-Wechsel zur Laufzeit
- [ ] Equalizer-Visualizer

### v0.5 — Nostalgie-Formate
- [ ] SID-Playback (C64)
- [ ] MOD/XM/S3M-Playback (Amiga)

### v1.0 — Release
- [ ] Polishing, Bugfixes
- [ ] README mit Screenshots
- [ ] PyPI-Veröffentlichung
- [ ] Optional: Umstieg auf SQLite für Playlists
