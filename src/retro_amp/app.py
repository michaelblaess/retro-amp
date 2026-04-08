"""retro-amp — Textual App (Composition Root)."""
from __future__ import annotations

import dataclasses
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    DirectoryTree, Footer, Header, Input, RichLog, Rule, TabbedContent, TabPane,
)

from textual import work

from . import __version__
from .domain.models import AudioTrack
from .themes import RETRO_THEMES, RETRO_THEME_NAMES, THEME_DISPLAY_NAMES
from .infrastructure.audio_player import PygameAudioPlayer
from .infrastructure.metadata_reader import MutagenMetadataReader
from .infrastructure.playlist_store import MarkdownPlaylistStore
from .infrastructure.settings import JsonSettingsStore
from .infrastructure.single_instance import acquire_lock, read_play_request, release_lock
from .infrastructure.spectrum import SpectrumAnalyzer
from .services.liner_notes_service import LinerNotesService
from .services.lyrics_service import LyricsService
from .services.metadata_service import MetadataService
from .services.player_service import PlayerService
from .services.playlist_service import PlaylistService
from .widgets.file_table import FileTable
from .widgets.favorites_tree import FavoritesTree
from .widgets.folder_browser import FolderBrowser
from .widgets.playlist_tree import PlaylistTree
from .widgets.info_panel import InfoPanel
from .widgets.lyrics_panel import LyricsPanel
from .widgets.search_panel import SearchPanel, _SearchResult
from .widgets.translation_panel import TranslationPanel
from .widgets.transport_bar import TransportBar
from .widgets.visualizer import Visualizer
from .i18n import t
from .screens.library_picker_screen import LibraryPickerScreen
from .widgets.youtube_panel import YoutubePanel


class RetroAmpApp(App):
    """retro-amp — Terminal-Musikplayer mit Retro-Charme."""

    CSS_PATH = "app.tcss"
    TITLE = f"retro-amp v{__version__}"

    def __init__(self, start_path: str = "", play_file: str = "") -> None:
        super().__init__()

        # Bindings mit uebersetzten Labels
        self._bindings.bind("q", "quit", t("binding.quit"))
        self._bindings.bind("space", "toggle_pause", t("binding.play_pause"), key_display="SPC", priority=True)
        self._bindings.bind("n", "next_track", t("binding.next"), priority=True)
        self._bindings.bind("b", "previous_track", t("binding.previous"), priority=True)
        self._bindings.bind("right", "seek_forward", ">>", key_display="→", priority=True)
        self._bindings.bind("left", "seek_backward", "<<", key_display="←", priority=True)
        self._bindings.bind("plus,equal", "volume_up", "Vol+", key_display="+", priority=True)
        self._bindings.bind("minus", "volume_down", "Vol-", key_display="-", priority=True)
        self._bindings.bind("f", "toggle_favorite", t("binding.favorite"), priority=True)
        self._bindings.bind("p", "show_playlists", t("binding.playlists"), priority=True)
        self._bindings.bind("u", "rename_file", t("binding.rename"), priority=True)
        self._bindings.bind("delete", "delete_file", t("binding.delete"), key_display="DEL", priority=True)
        self._bindings.bind("t", "cycle_theme", t("binding.theme"), priority=True)
        self._bindings.bind("i", "show_about", t("binding.info"), priority=True)
        self._bindings.bind("s", "focus_search", t("binding.search"), priority=True)
        self._bindings.bind("l", "pick_library", t("binding.library"), priority=True)
        self._bindings.bind("o", "toggle_log", t("binding.log"), priority=True)
        self._bindings.bind("c", "copy_log", t("binding.copy_log"), priority=True)
        self._bindings.bind("x", "toggle_shuffle", t("binding.shuffle"), priority=True)
        self._bindings.bind("tab", "cycle_view", t("binding.cycle_view"), key_display="TAB", priority=True)

        # Retro-Themes registrieren
        for retro_theme in RETRO_THEMES:
            self.register_theme(retro_theme)

        # Infrastructure (Composition Root — hier wird verdrahtet)
        self._audio_player = PygameAudioPlayer()
        self._metadata_reader = MutagenMetadataReader()
        self._settings_store = JsonSettingsStore()
        self._playlist_store = MarkdownPlaylistStore()
        self._spectrum_analyzer = SpectrumAnalyzer()

        # Services
        self._player_service = PlayerService(self._audio_player)
        self._metadata_service = MetadataService(self._metadata_reader)
        self._playlist_service = PlaylistService(self._playlist_store)
        self._liner_notes_service = LinerNotesService()
        self._lyrics_service = LyricsService()

        # Generations-Counter fuer Lyrics-Thread-Cancellation
        self._lyrics_generation: int = 0

        # Settings laden
        settings = self._settings_store.load()
        self._player_service.set_volume(float(settings.get("volume", 0.8)))

        # Gespeichertes Theme anwenden (Default: C64)
        saved_theme = str(settings.get("theme", "c64"))
        if saved_theme in RETRO_THEME_NAMES:
            self.theme = saved_theme
        else:
            self.theme = "c64"

        # Baumwurzel bestimmen (immer der Musik-Root, nicht der letzte Ordner)
        self._needs_library_picker = False
        if start_path:
            self._tree_root = Path(start_path).expanduser().resolve()
            # CLI-Pfad als music_library persistieren
            settings["music_library"] = str(self._tree_root)
            self._settings_store.save(settings)
        else:
            saved_library = str(settings.get("music_library", ""))
            if saved_library and Path(saved_library).is_dir():
                self._tree_root = Path(saved_library)
            else:
                # Kein gespeicherter Pfad — Picker beim Start zeigen
                self._needs_library_picker = True
                self._tree_root = Path.home() / "Music" if (Path.home() / "Music").is_dir() else Path.home()

        if not self._tree_root.is_dir():
            self._tree_root = Path.home()

        # Autoplay-Datei (z.B. Doppelklick auf MP3)
        self._autoplay_file: Path | None = None
        if play_file:
            pf = Path(play_file).expanduser().resolve()
            if pf.is_file():
                self._autoplay_file = pf
                parent = pf.parent
                self._needs_library_picker = False
                # Datei ausserhalb der Library: Tree-Root temporaer anpassen
                try:
                    parent.relative_to(self._tree_root)
                except ValueError:
                    self._tree_root = parent

        # Letzter besuchter Ordner (fuer rechte Tabelle beim Start)
        if self._autoplay_file:
            self._initial_scan_path = self._autoplay_file.parent
        else:
            last_path_str = str(settings.get("last_path", ""))
            self._initial_scan_path = Path(last_path_str) if last_path_str else self._tree_root
            if not self._initial_scan_path.is_dir():
                self._initial_scan_path = self._tree_root

        # Log-Zeilen fuer Copy-Funktion
        self._log_lines: list[str] = []

        # Timer-Handle fuer Position-Updates
        self._position_timer: object | None = None

        # Aktuelle Tracks im rechten Panel
        self._current_tracks: list[AudioTrack] = []

        # Shuffle-Modus
        self._shuffle_mode: bool = False
        # Shuffle-History pro Ordner: dir_path -> (gespielte Pfade, letzter Zugriff)
        self._shuffle_history: dict[str, tuple[set[str], float]] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(
            placeholder=t("search.placeholder"),
            id="global-search",
        )
        with Horizontal(id="main-container"):
            with Vertical(id="left-panel"):
                with TabbedContent(id="left-tabs"):
                    with TabPane(t("tab.browser"), id="tab-browser"):
                        yield FolderBrowser(str(self._tree_root), id="folder-browser")
                    with TabPane(t("tab.favorites"), id="tab-favorites"):
                        yield FavoritesTree(id="favorites-tree")
                    with TabPane(t("tab.playlists"), id="tab-playlists"):
                        yield PlaylistTree(id="playlist-tree")
            with Vertical(id="right-panel"):
                yield FileTable(id="file-table")
                yield Rule(id="tab-separator")
                with TabbedContent(id="content-tabs"):
                    with TabPane(t("tab.lyrics"), id="tab-lyrics"):
                        yield LyricsPanel(id="lyrics-panel")
                    with TabPane(t("tab.translation"), id="tab-translation"):
                        yield TranslationPanel(id="translation-panel")
                    with TabPane(t("tab.info"), id="tab-info"):
                        yield InfoPanel(id="info-panel")
                    with TabPane(t("tab.youtube"), id="tab-youtube"):
                        yield YoutubePanel(id="youtube-panel")
                    with TabPane(t("tab.search"), id="tab-search"):
                        yield SearchPanel(id="search-panel")
        with Horizontal(id="transport-row"):
            yield Visualizer(id="visualizer")
            yield TransportBar(id="transport")
        yield RichLog(id="app-log", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        """App ist bereit — Timer starten, Callbacks setzen."""
        acquire_lock()
        self._position_timer = self.set_interval(0.5, self._tick_position)
        self.set_interval(0.5, self._check_play_request)
        self._player_service.set_callbacks(
            on_finished=self._on_track_finished,
            on_error=self._on_playback_error,
        )
        # Theme-Name in Titelleiste
        display = THEME_DISPLAY_NAMES.get(self.theme, self.theme)
        self.sub_title = f"♪ {display}"

        # Fokus auf Verzeichnisbaum statt Suchfeld (zeigt alle Bindings im Footer)
        self.query_one("#folder-browser", FolderBrowser).focus()

        if self._needs_library_picker:
            self._show_library_picker()
        else:
            # Initial: letzten Ordner in Tabelle laden
            self._scan_directory(self._initial_scan_path)
            # Baum zum letzten Verzeichnis aufklappen
            if self._initial_scan_path != self._tree_root:
                self._expand_tree_to_last_path()
            # Auto-Play: Datei per CLI uebergeben (z.B. Doppelklick auf MP3)
            if self._autoplay_file and self._autoplay_file.is_file():
                track = self._metadata_service.read_track(self._autoplay_file)
                self._play_track(track)

    def _show_library_picker(self) -> None:
        """Zeigt den Library-Picker-Dialog."""
        candidates: list[Path] = []
        music_dir = Path.home() / "Music"
        if music_dir.is_dir():
            candidates.append(music_dir)
        cwd = Path.cwd().resolve()
        if cwd != Path.home() and cwd not in candidates:
            candidates.append(cwd)
        self.push_screen(
            LibraryPickerScreen(candidates),
            callback=self._on_library_picked,
        )

    def _on_library_picked(self, chosen: Path | None) -> None:
        """Callback vom Library-Picker — Pfad speichern und Baum aktualisieren."""
        if chosen is None:
            return
        self._tree_root = chosen
        self._initial_scan_path = chosen
        # Pfad persistieren
        settings = self._settings_store.load()
        settings["music_library"] = str(chosen)
        self._settings_store.save(settings)
        # Baum und Tabelle mit neuem Root aktualisieren
        browser = self.query_one("#folder-browser", FolderBrowser)
        browser.path = str(chosen)
        browser.reload()
        self._scan_directory(chosen)

    @work
    async def _expand_tree_to_last_path(self) -> None:
        """Klappt den Baum zum zuletzt besuchten Verzeichnis auf."""
        browser = self.query_one("#folder-browser", FolderBrowser)
        # Warten bis der Root-Knoten geladen ist
        await browser._add_to_load_queue(browser.root)
        await browser.expand_to_path(self._initial_scan_path)

    # --- Event-Handler fuer Widget-Messages ---

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        """Ordner im Baum ausgewaehlt — rechtes Panel aktualisieren."""
        self._scan_directory(event.path)
        self._save_last_path(event.path)
        self._write_log(t("log.folder", path=event.path))

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Datei im Baum ausgewaehlt — Ordner aktualisieren und abspielen."""
        path = event.path
        if self._metadata_service.is_audio_file(path):
            # Rechtes Panel mit Ordner-Inhalt aktualisieren
            parent = path.parent
            self._scan_directory(parent)
            self._save_last_path(parent)
            track = self._metadata_service.read_track(path)
            self._play_track(track)

    def on_file_table_track_selected(
        self, event: FileTable.TrackSelected
    ) -> None:
        """Track per Enter ausgewaehlt — abspielen."""
        self._play_track(event.track)

    # --- Actions (Keybindings) ---

    def action_toggle_pause(self) -> None:
        """Play/Pause umschalten."""
        state = self._player_service.state
        if state.is_stopped and self._current_tracks:
            # Nichts laeuft — ersten Track starten
            self._player_service.load_tracks(self._current_tracks)
            self._player_service.play_track(0)
        else:
            self._player_service.toggle_pause()
        self._sync_visualizer()
        self._update_transport()

    def action_next_track(self) -> None:
        """Naechster Track (Shuffle-aware)."""
        if self._shuffle_mode:
            next_track = self._pick_shuffle_next()
            if next_track:
                self._play_track(next_track)
                self._write_log(t("log.shuffle_play", name=next_track.display_name))
            return
        self._player_service.next_track()
        self._sync_visualizer()
        self._update_transport()
        self._highlight_current_track()

    def action_previous_track(self) -> None:
        """Vorheriger Track."""
        self._player_service.previous_track()
        self._sync_visualizer()
        self._update_transport()
        self._highlight_current_track()

    def action_toggle_shuffle(self) -> None:
        """Shuffle-Modus umschalten."""
        self._shuffle_mode = not self._shuffle_mode

        # Binding-Label aktualisieren (frozen → dataclasses.replace)
        label = t("binding.shuffle_on") if self._shuffle_mode else t("binding.shuffle")
        bindings_list = self._bindings.key_to_bindings.get("x", [])
        for i, binding in enumerate(bindings_list):
            if binding.action == "toggle_shuffle":
                self._bindings.key_to_bindings["x"][i] = dataclasses.replace(
                    binding, description=label,
                )
                break
        self.refresh_bindings()

        if self._shuffle_mode:
            self.notify(t("notify.shuffle_on"))
            self._write_log(t("log.shuffle_on"))
        else:
            self.notify(t("notify.shuffle_off"))
            self._write_log(t("log.shuffle_off"))

    def action_seek_forward(self) -> None:
        """5 Sekunden vorwaerts springen."""
        self._player_service.seek_forward(5.0)
        self._update_transport()

    def action_seek_backward(self) -> None:
        """5 Sekunden zurueck springen."""
        self._player_service.seek_backward(5.0)
        self._update_transport()

    def action_volume_up(self) -> None:
        """Lautstaerke erhoehen."""
        self._player_service.volume_up()
        self._update_transport()
        self._save_volume()

    def action_volume_down(self) -> None:
        """Lautstaerke verringern."""
        self._player_service.volume_down()
        self._update_transport()
        self._save_volume()

    def action_toggle_favorite(self) -> None:
        """Aktuellen Track als Favorit toggeln."""
        track = self._player_service.state.current_track
        if not track:
            self.notify(t("notify.no_track"), severity="warning")
            return

        is_fav = self._playlist_service.toggle_favorite(track.path)
        if is_fav:
            self.notify(t("notify.favorite_added", name=track.display_name))
        else:
            self.notify(t("notify.favorite_removed", name=track.display_name))

        # Favoriten-Baum aktualisieren wenn sichtbar
        left_tabs = self.query_one("#left-tabs", TabbedContent)
        if left_tabs.active == "tab-favorites":
            self._refresh_favorites_tree()

    def action_show_playlists(self) -> None:
        """Playlist-Dialog oeffnen."""
        from .screens.playlist_screen import PlaylistScreen  # Lazy import

        track = self._player_service.state.current_track
        track_name = track.display_name if track else ""
        playlists = self._playlist_service.list_playlists()

        self.push_screen(
            PlaylistScreen(playlists, current_track_name=track_name),
            callback=self._on_playlist_selected,
        )

    def action_cycle_theme(self) -> None:
        """Wechselt zum naechsten Retro-Theme."""
        current = self.theme
        try:
            idx = RETRO_THEME_NAMES.index(current)
        except ValueError:
            idx = -1
        next_idx = (idx + 1) % len(RETRO_THEME_NAMES)
        next_theme = RETRO_THEME_NAMES[next_idx]
        self.theme = next_theme
        display = THEME_DISPLAY_NAMES.get(next_theme, next_theme)
        self.notify(t("notify.theme", name=display))
        self._save_theme(next_theme)

    def action_show_about(self) -> None:
        """About-Dialog anzeigen."""
        from .screens.about_screen import AboutScreen  # Lazy import
        self.push_screen(AboutScreen())

    def action_pick_library(self) -> None:
        """Library-Picker-Dialog oeffnen."""
        self._show_library_picker()

    def action_focus_search(self) -> None:
        """Fokus auf Suchleiste setzen."""
        search_input = self.query_one("#global-search", Input)
        search_input.focus()

    def action_cycle_view(self) -> None:
        """Wechselt zwischen Datei-Explorer, Favoriten und Playlists."""
        tabs = self.query_one("#left-tabs", TabbedContent)
        tab_ids = ["tab-browser", "tab-favorites", "tab-playlists"]
        idx = tab_ids.index(tabs.active)
        tabs.active = tab_ids[(idx + 1) % len(tab_ids)]

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated,
    ) -> None:
        """Reagiert auf Tab-Wechsel im linken Panel."""
        if event.tabbed_content.id != "left-tabs":
            return
        if event.pane.id == "tab-browser":
            self.query_one("#folder-browser", FolderBrowser).focus()
            self._write_log(t("log.view_explorer"))
        elif event.pane.id == "tab-favorites":
            self._refresh_favorites_tree()
            self.query_one("#favorites-tree", FavoritesTree).focus()
            self._write_log(t("log.view_favorites"))
        elif event.pane.id == "tab-playlists":
            self._refresh_playlist_tree()
            self.query_one("#playlist-tree", PlaylistTree).focus()
            self._write_log(t("log.view_playlists"))

    def action_toggle_log(self) -> None:
        """Debug-Log ein-/ausblenden."""
        log_widget = self.query_one("#app-log", RichLog)
        log_widget.toggle_class("visible")

    def action_copy_log(self) -> None:
        """Gesamten Log-Inhalt in die Zwischenablage kopieren."""
        if not self._log_lines:
            self.notify(t("notify.log_empty"), severity="warning")
            return
        text = "\n".join(self._log_lines)
        self.copy_to_clipboard(text)
        self.notify(t("notify.log_copied", count=len(self._log_lines)))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Suchleiste: Enter gedrueckt → Suche starten."""
        if event.input.id != "global-search":
            return
        query = event.value.strip()
        if not query:
            return
        # Loading-Indikator sofort anzeigen
        search_panel = self.query_one("#search-panel", SearchPanel)
        search_panel.show_loading(query)
        tabs = self.query_one("#content-tabs", TabbedContent)
        tabs.active = "tab-search"
        # Suche im Background-Thread starten
        self._run_global_search(query)

    @work(exclusive=True, group="search", thread=True)
    def _run_global_search(self, query: str) -> None:
        """Globale Dateisuche im Background-Thread."""
        results = self._do_file_search(query, self._tree_root)
        self.call_from_thread(self._apply_search_results, query, results)

    _SEPARATOR_RE = re.compile(r"[.\-_]")

    def _do_file_search(
        self, query: str, root: Path,
    ) -> list[tuple[Path, str]]:
        """Fuehrt die Dateisuche durch (Thread-safe, kein Widget-Zugriff)."""
        query_norm = self._SEPARATOR_RE.sub(" ", query.lower())
        results: list[tuple[Path, str]] = []
        audio_exts = {
            ".mp3", ".ogg", ".oga", ".opus", ".flac", ".wav",
            ".mod", ".xm", ".s3m", ".sid",
        }
        try:
            for p in sorted(root.rglob("*")):
                if query_norm in self._SEPARATOR_RE.sub(" ", p.name.lower()):
                    try:
                        rel = p.relative_to(root)
                    except ValueError:
                        rel = p
                    if p.is_dir():
                        results.append((p, f"\U0001f4c1 {rel}"))
                    elif p.suffix.lower() in audio_exts:
                        results.append((p, f"\u266a {rel}"))
        except PermissionError:
            pass
        return results[:200]

    def _apply_search_results(
        self, query: str, results: list[tuple[Path, str]],
    ) -> None:
        """Zeigt Suchergebnisse an (Main-Thread)."""
        search_panel = self.query_one("#search-panel", SearchPanel)
        search_panel.display_results(query, results)
        self._write_log(t("log.search_results", query=query, count=len(results)))

    def on__search_result_selected(
        self, event: _SearchResult.Selected,
    ) -> None:
        """Suchergebnis angeklickt → navigieren."""
        path = event.path
        if path.is_dir():
            self._scan_directory(path)
            self._save_last_path(path)
            self.notify(t("notify.folder", name=path.name))
        elif path.is_file():
            parent = path.parent
            self._scan_directory(parent)
            self._save_last_path(parent)
            if self._metadata_service.is_audio_file(path):
                track = self._metadata_service.read_track(path)
                self._play_track(track)

    @work(exclusive=True, group="liner-notes", thread=True)
    def _fetch_and_show_info(self, artist: str) -> None:
        """Holt Liner Notes im Background-Thread."""
        note = self._liner_notes_service.get_note(artist)
        self.call_from_thread(self._apply_info, artist, note)

    def _apply_info(self, artist: str, note: str) -> None:
        """Zeigt Info im InfoPanel (Main-Thread)."""
        info_panel = self.query_one("#info-panel", InfoPanel)
        info_panel.show_info(artist, note)

    def action_rename_file(self) -> None:
        """Datei oder Ordner umbenennen — Dialog oeffnen."""
        from .screens.rename_screen import RenameScreen  # Lazy import

        # Kontextabhaengig: Fokus auf Baum → Element im Baum umbenennen
        folder_browser = self.query_one("#folder-browser", FolderBrowser)
        if folder_browser.has_focus or folder_browser.has_focus_within:
            node = folder_browser.cursor_node
            if node and node.data:
                target = node.data.path
                if target == self._tree_root:
                    self.notify(
                        t("notify.cannot_rename_root"),
                        severity="warning",
                    )
                    return
                self._rename_with_unload(target)
                return

        # Fallback: markierte Datei in der Tabelle
        file_table = self.query_one("#file-table", FileTable)
        track = file_table.highlighted_track
        if not track:
            self.notify(t("notify.no_track"), severity="warning")
            return

        self._rename_with_unload(track.path)

    def _rename_with_unload(self, target: Path) -> None:
        """Player entladen falls noetig, dann Rename-Dialog oeffnen."""
        from .screens.rename_screen import RenameScreen  # Lazy import

        playing = self._player_service.state.current_track
        # Pruefen ob der gespielte Track von der Umbenennung betroffen ist
        is_playing_target = (
            playing
            and not self._player_service.state.is_stopped
            and (playing.path == target or str(playing.path).startswith(f"{target}\\"))
        )

        resume_position = 0.0
        if is_playing_target:
            resume_position = self._player_service.state.position_seconds
            self._player_service.unload()

        self.push_screen(
            RenameScreen(target),
            callback=lambda new_path: self._on_rename_result(
                new_path, is_playing_target, resume_position, playing,
            ),
        )

    def _on_rename_result(
        self,
        new_path: Path | None,
        was_playing: bool,
        resume_position: float,
        old_track: AudioTrack | None,
    ) -> None:
        """Callback nach Umbenennen-Dialog."""
        if not new_path:
            # Abbruch — falls Player entladen wurde, weiterspielen
            if was_playing and old_track:
                self._player_service.play_file(old_track)
                if resume_position > 0:
                    self._player_service._player.seek(resume_position)
                    self._player_service.state.position_seconds = resume_position
            return

        # Verzeichnis neu scannen
        directory = new_path.parent
        self._scan_directory(directory)

        # Baum aktualisieren (noetig bei Ordner-Umbenennung)
        folder_browser = self.query_one("#folder-browser", FolderBrowser)
        folder_browser.reload()

        # Track mit neuem Pfad weiterspielen
        if was_playing and old_track:
            # Neuen Pfad berechnen (Datei oder Datei in umbenanntem Ordner)
            if old_track.path == new_path or new_path.is_file():
                new_track_path = new_path
            else:
                # Ordner umbenannt — relativen Pfad auf neuen Ordner umrechnen
                rel = old_track.path.relative_to(old_track.path)
                new_track_path = new_path / old_track.path.name
            new_track = self._metadata_service.read_track(new_track_path)
            self._player_service.play_file(new_track)
            if resume_position > 0:
                self._player_service._player.seek(resume_position)
                self._player_service.state.position_seconds = resume_position

        self.notify(t("notify.renamed", name=new_path.name))
        self._write_log(t("log.renamed", path=new_path))

    def action_delete_file(self) -> None:
        """Datei oder Ordner loeschen — Bestaetigungsdialog oeffnen."""
        from .screens.confirm_screen import ConfirmScreen  # Lazy import

        # Kontextabhaengig: Fokus auf Baum → Ordner/Datei im Baum loeschen
        folder_browser = self.query_one("#folder-browser", FolderBrowser)
        if folder_browser.has_focus or folder_browser.has_focus_within:
            node = folder_browser.cursor_node
            if node and node.data:
                target = node.data.path
                if target == self._tree_root:
                    self.notify(t("notify.cannot_delete_root"),
                                severity="warning")
                    return
                if target.is_dir():
                    # Dateien im Ordner zaehlen
                    try:
                        count = sum(1 for _ in target.rglob("*") if _.is_file())
                    except PermissionError:
                        count = 0
                    msg = (
                        f"Ordner wirklich loeschen?\n\n"
                        f"{target.name}\n"
                        f"({count} Dateien)"
                    )
                else:
                    msg = f"Datei wirklich loeschen?\n\n{target.name}"
                self._delete_with_unload(msg, target)
                return

        # Fallback: markierte Datei in der Tabelle
        file_table = self.query_one("#file-table", FileTable)
        track = file_table.highlighted_track
        if not track:
            self.notify(t("notify.no_track"), severity="warning")
            return

        self._delete_with_unload(
            f"Datei wirklich loeschen?\n\n{track.name}",
            track.path,
        )

    def _delete_with_unload(self, msg: str, target: Path) -> None:
        """Player entladen falls noetig, dann Loeschen-Dialog oeffnen."""
        from .screens.confirm_screen import ConfirmScreen  # Lazy import

        playing = self._player_service.state.current_track
        is_playing_target = (
            playing
            and not self._player_service.state.is_stopped
            and (playing.path == target or str(playing.path).startswith(f"{target}\\"))
        )

        if is_playing_target:
            self._player_service.unload()

        self.push_screen(
            ConfirmScreen(msg, file_path=target),
            callback=lambda deleted_path: self._on_delete_result(
                deleted_path, is_playing_target, playing,
            ),
        )

    def _on_delete_result(
        self,
        deleted_path: Path | None,
        was_playing: bool,
        old_track: AudioTrack | None,
    ) -> None:
        """Callback nach Loeschen-Bestaetigung."""
        if not deleted_path:
            # Abbruch — falls Player entladen wurde, weiterspielen
            if was_playing and old_track:
                self._player_service.play_file(old_track)
            return

        was_dir = not deleted_path.exists() or deleted_path.is_dir()

        # Falls der Track gespielt wurde: zum naechsten oder stoppen
        if was_playing:
            if self._player_service.state.has_next:
                self._player_service.next_track()
            self._sync_visualizer()
            self._highlight_current_track()
            self._update_transport()

        # Verzeichnis neu scannen
        directory = deleted_path.parent
        self._scan_directory(directory)

        # Baum aktualisieren
        folder_browser = self.query_one("#folder-browser", FolderBrowser)
        folder_browser.reload()

        label = t("confirm.title_dir").split()[0] if was_dir else t("confirm.title_file").split()[0]
        self.notify(t("notify.deleted", label=label, name=deleted_path.name))
        self._write_log(t("log.deleted", path=deleted_path))

    def _on_playlist_selected(self, playlist_name: str | None) -> None:
        """Callback wenn eine Playlist im Dialog gewaehlt wurde."""
        if not playlist_name:
            return

        track = self._player_service.state.current_track
        if track:
            # Track zur gewaehlten Playlist hinzufuegen
            added = self._playlist_service.add_to_playlist(playlist_name, track.path)
            if added:
                self.notify(t("notify.added_to_playlist", track=track.display_name, playlist=playlist_name))
            else:
                self.notify(t("notify.already_in_playlist", playlist=playlist_name), severity="information")
        else:
            # Keine Wiedergabe — Playlist laden und abspielen
            track_paths = self._playlist_service.load_playlist_tracks(playlist_name)
            if track_paths:
                tracks = [
                    self._metadata_service.read_track(p)
                    for p in track_paths
                    if p.is_file()
                ]
                if tracks:
                    self._current_tracks = tracks
                    file_table = self.query_one("#file-table", FileTable)
                    file_table.update_tracks(tracks)
                    self._player_service.load_tracks(tracks)
                    self._player_service.play_track(0)
                    self._sync_visualizer()
                    self._update_transport()
                    self.notify(t("notify.playlist_loaded", name=playlist_name, count=len(tracks)))
                else:
                    self.notify(t("notify.playlist_empty_files"), severity="warning")
            else:
                self.notify(t("notify.playlist_empty", name=playlist_name), severity="information")

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Bindings bedingt ein-/ausblenden."""
        # ModalScreen aktiv → alle App-Bindings deaktivieren
        if len(self.screen_stack) > 1:
            return None

        # Input-Widget fokussiert → Priority-Bindings deaktivieren,
        # damit Cursor-Navigation und Textbearbeitung funktionieren
        if isinstance(self.focused, Input):
            if action in ("seek_forward", "seek_backward", "delete_file"):
                return None

        state = self._player_service.state
        has_track = state.current_track is not None

        if action == "next_track":
            if self._shuffle_mode and has_track:
                return True
            return True if state.has_next else None
        if action == "previous_track":
            return True if state.has_previous else None
        if action in ("seek_forward", "seek_backward"):
            return True if has_track and not state.is_stopped else None
        if action == "toggle_favorite":
            return True if has_track else None
        if action == "copy_log":
            log_widget = self.query_one("#app-log", RichLog)
            return True if log_widget.has_class("visible") else None
        if action in ("rename_file", "delete_file"):
            # In Favoriten/Playlist-Ansicht: App-Delete/Rename ausblenden
            # (Tree-Widgets haben eigene DEL-Bindings zum Entfernen)
            left_tabs = self.query_one("#left-tabs", TabbedContent)
            if left_tabs.active != "tab-browser":
                return None
            folder_browser = self.query_one("#folder-browser", FolderBrowser)
            if folder_browser.has_focus or folder_browser.has_focus_within:
                node = folder_browser.cursor_node
                return True if (node and node.data) else None
            file_table = self.query_one("#file-table", FileTable)
            return True if file_table.highlighted_track else None
        return True

    def on_favorites_tree_track_selected(
        self, event: FavoritesTree.TrackSelected,
    ) -> None:
        """Favoriten-Track ausgewaehlt — navigieren und abspielen."""
        path = event.path
        if path.is_file():
            parent = path.parent
            self._scan_directory(parent)
            self._save_last_path(parent)
            if self._metadata_service.is_audio_file(path):
                track = self._metadata_service.read_track(path)
                self._play_track(track)
        else:
            self.notify(t("notify.file_not_found"), severity="warning")

    def on_favorites_tree_track_remove_requested(
        self, event: FavoritesTree.TrackRemoveRequested,
    ) -> None:
        """Track aus Favoriten entfernen."""
        removed = self._playlist_service.remove_from_favorites(event.path)
        if removed:
            self.notify(t("notify.favorite_tree_removed", name=event.path.name))
            self._refresh_favorites_tree()
            self._write_log(t("log.favorite_removed", name=event.path.name))

    def on_playlist_tree_track_selected(
        self, event: PlaylistTree.TrackSelected,
    ) -> None:
        """Playlist-Track ausgewaehlt — navigieren und abspielen."""
        path = event.path
        if path.is_file():
            parent = path.parent
            self._scan_directory(parent)
            self._save_last_path(parent)
            if self._metadata_service.is_audio_file(path):
                track = self._metadata_service.read_track(path)
                self._play_track(track)
        else:
            self.notify(t("notify.file_not_found"), severity="warning")

    def on_playlist_tree_track_remove_requested(
        self, event: PlaylistTree.TrackRemoveRequested,
    ) -> None:
        """Track aus Playlist entfernen."""
        removed = self._playlist_service.remove_from_playlist(
            event.playlist_name, event.path,
        )
        if removed:
            self.notify(t("notify.playlist_track_removed", playlist=event.playlist_name, name=event.path.name))
            self._refresh_playlist_tree()
            self._write_log(t("log.playlist_track_removed", playlist=event.playlist_name, name=event.path.name))

    def on_transport_bar_volume_clicked(
        self, event: TransportBar.VolumeClicked,
    ) -> None:
        """Lautstaerke per Mausklick aendern."""
        self._player_service.set_volume(event.volume)
        self._update_transport()
        self._save_volume()
        self._write_log(t("log.volume", pct=int(event.volume * 100)))

    def on_transport_bar_seek_clicked(
        self, event: TransportBar.SeekClicked,
    ) -> None:
        """Position per Mausklick im Fortschrittsbalken aendern."""
        self._player_service.seek_to(event.position)
        self._update_transport()

    # --- Interne Methoden ---

    @work(exclusive=True, group="scan", thread=True)
    def _scan_directory(self, directory: Path) -> None:
        """Scannt ein Verzeichnis im Background-Thread."""
        tracks = self._metadata_service.scan_directory(directory)
        self.call_from_thread(self._apply_scan_result, tracks, directory)

    def _apply_scan_result(self, tracks: list[AudioTrack], directory: Path) -> None:
        """Wendet Scan-Ergebnis auf die UI an (im Main-Thread)."""
        self._current_tracks = tracks
        file_table = self.query_one("#file-table", FileTable)
        file_table.set_path(directory)
        file_table.update_tracks(self._current_tracks)
        self._write_log(t("log.directory", path=directory, count=len(tracks)))

        # Tracklist im Player synchronisieren wenn der aktuelle Track enthalten ist
        playing = self._player_service.state.current_track
        if playing and tracks:
            for idx, t_ in enumerate(tracks):
                if t_.path == playing.path:
                    self._player_service.state.track_list = tracks
                    self._player_service.state.current_index = idx
                    self._player_service.state.current_track = t_
                    self._highlight_current_track()
                    break

    def _pick_shuffle_next(self) -> AudioTrack | None:
        """Waehlt einen zufaelligen ungespielten Track aus dem aktuellen Ordner."""
        state = self._player_service.state
        tracks = state.track_list
        if not tracks:
            return None

        current_track = state.current_track
        if not current_track:
            return None

        dir_key = str(current_track.path.parent)
        now = time.monotonic()

        # History laden oder erstellen, abgelaufen nach 20 Minuten
        if dir_key in self._shuffle_history:
            played, last_access = self._shuffle_history[dir_key]
            if now - last_access > 20 * 60:
                played = set()
        else:
            played = set()

        # Aktuellen Track als gespielt markieren
        played.add(str(current_track.path))

        # Ungespielte Tracks finden
        unplayed = [t_ for t_ in tracks if str(t_.path) not in played]

        if not unplayed:
            # Alles gespielt — History leeren, stoppen
            self._shuffle_history[dir_key] = (set(), now)
            return None

        next_track = random.choice(unplayed)
        played.add(str(next_track.path))
        self._shuffle_history[dir_key] = (played, now)
        return next_track

    def _check_play_request(self) -> None:
        """Timer: prueft ob eine andere Instanz eine Datei gesendet hat."""
        path_str = read_play_request()
        if not path_str:
            return
        path = Path(path_str)
        if not path.is_file() or not self._metadata_service.is_audio_file(path):
            return
        parent = path.parent
        self._scan_directory(parent)
        self._save_last_path(parent)
        track = self._metadata_service.read_track(path)
        self._play_track(track)

    def _play_track(self, track: AudioTrack) -> None:
        """Spielt einen Track ab und aktualisiert UI."""
        # Tracklist laden falls noetig
        if track in self._current_tracks:
            idx = self._current_tracks.index(track)
            self._player_service.load_tracks(self._current_tracks)
            self._player_service.play_track(idx)
        else:
            self._player_service.play_file(track)

        self._sync_visualizer()
        self._update_transport()
        self._highlight_current_track()
        self.sub_title = track.display_name
        if track.artist and track.title:
            log_name = f"{track.artist} \u2013 {track.title}"
        else:
            log_name = track.display_name
        self._write_log(t("log.play", name=f"{log_name} ({track.path.parent})"))

        # Alle Tabs asynchron laden
        self._load_tabs_for_track(track)

    def _highlight_current_track(self) -> None:
        """Markiert den aktuellen Track in der Tabelle und im Baum."""
        track = self._player_service.state.current_track
        file_table = self.query_one("#file-table", FileTable)
        file_table.mark_playing(track.path if track else None)
        if track:
            file_table.highlight_track(track)
            folder_browser = self.query_one("#folder-browser", FolderBrowser)
            folder_browser.highlight_path(track.path)

    def _tick_position(self) -> None:
        """Timer-Callback: Position aktualisieren."""
        self._player_service.update_position()
        self._update_transport()

    def _sync_visualizer(self) -> None:
        """Synchronisiert Visualizer mit Player-State."""
        vis = self.query_one("#visualizer", Visualizer)
        if self._player_service.state.is_playing:
            track = self._player_service.state.current_track
            if track:
                self._load_spectrum(track.path)
                vis.set_spectrum_source(
                    lambda: self._spectrum_analyzer.get_bands(
                        self._player_service.state.position_seconds
                    )
                )
            vis.start()
        else:
            vis.set_spectrum_source(None)
            vis.stop()

    @work(exclusive=True, group="spectrum", thread=True)
    def _load_spectrum(self, path: Path) -> None:
        """Laedt Spektrum-Daten im Hintergrund-Thread."""
        self._spectrum_analyzer.load(path)

    def _update_transport(self) -> None:
        """Transport-Leiste mit aktuellem State aktualisieren."""
        transport = self.query_one("#transport", TransportBar)
        transport.update_state(self._player_service.state)

    def _on_playback_error(self, error: str) -> None:
        """Callback bei Playback-Fehlern."""
        self._write_log(f"[bold red]{error}[/bold red]")
        self.notify(error, severity="warning", timeout=8)

    def _on_track_finished(self) -> None:
        """Callback wenn ein Track fertig ist."""
        state = self._player_service.state
        finished_track = state.current_track
        if finished_track:
            self._write_log(t("log.track_finished", name=finished_track.display_name))
        else:
            self._write_log(t("log.track_finished_unknown"))

        # Shuffle: zufaelligen naechsten Track waehlen
        if self._shuffle_mode:
            next_track = self._pick_shuffle_next()
            if next_track:
                self._play_track(next_track)
                self._write_log(t("log.shuffle_play", name=next_track.display_name))
            else:
                self._write_log(t("log.shuffle_all_played"))
                self.sub_title = ""
                self._clear_all_tabs()
                self._lyrics_generation += 1
            self._sync_visualizer()
            self._update_transport()
            return

        # Normal: sequenziell naechsten Track
        self._player_service.check_auto_next()
        self._sync_visualizer()
        if self._player_service.state.is_stopped:
            self.sub_title = ""
            self._clear_all_tabs()
            self._lyrics_generation += 1
        else:
            track = self._player_service.state.current_track
            if track:
                # Rechte Tabelle synchronisieren wenn Track in anderem Verzeichnis
                file_table = self.query_one("#file-table", FileTable)
                if file_table._current_path != track.path.parent:
                    self._scan_directory(track.path.parent)
                    self._save_last_path(track.path.parent)
                self._highlight_current_track()
                self.sub_title = track.display_name
                if track.artist and track.title:
                    next_name = f"{track.artist} \u2013 {track.title}"
                else:
                    next_name = track.display_name
                self._write_log(t("log.play", name=f"{next_name} ({track.path.parent})"))
                self._load_tabs_for_track(track)
        self._update_transport()

    def _save_last_path(self, path: Path) -> None:
        """Speichert den letzten Ordner in Settings."""
        settings = self._settings_store.load()
        settings["last_path"] = str(path)
        self._settings_store.save(settings)

    def _save_volume(self) -> None:
        """Speichert die Lautstaerke in Settings."""
        settings = self._settings_store.load()
        settings["volume"] = self._player_service.state.volume
        self._settings_store.save(settings)

    def _save_theme(self, theme_name: str) -> None:
        """Speichert das gewaehlte Theme in Settings."""
        settings = self._settings_store.load()
        settings["theme"] = theme_name
        self._settings_store.save(settings)

    def _load_tabs_for_track(self, track: AudioTrack) -> None:
        """Laedt Inhalte fuer alle Tabs asynchron."""
        artist = track.artist
        title = track.title or track.path.stem

        # Generation erhoehen → alte Threads ignorieren ihr Ergebnis
        self._lyrics_generation += 1
        generation = self._lyrics_generation

        if artist:
            # Lyrics + Uebersetzung laden
            self.query_one("#lyrics-panel", LyricsPanel).show_loading(artist, title)
            self.query_one("#translation-panel", TranslationPanel).show_loading(
                artist, title,
            )
            self._fetch_lyrics_async(artist, title, generation)

            # Info (Wikipedia) laden
            self.query_one("#info-panel", InfoPanel).show_loading(artist)
            self._fetch_and_show_info(artist)

            # YouTube-Links
            self.query_one("#youtube-panel", YoutubePanel).show_links(artist, title)
        else:
            self._clear_all_tabs()

    def _clear_all_tabs(self) -> None:
        """Leert alle Tab-Panels."""
        self.query_one("#lyrics-panel", LyricsPanel).clear()
        self.query_one("#translation-panel", TranslationPanel).clear()
        self.query_one("#info-panel", InfoPanel).clear()
        self.query_one("#youtube-panel", YoutubePanel).clear()

    @work(exclusive=True, group="lyrics", thread=True)
    def _fetch_lyrics_async(
        self, artist: str, title: str, generation: int,
    ) -> None:
        """Holt Lyrics im Background-Thread."""
        original, translated = self._lyrics_service.get_lyrics(artist, title)

        if generation != self._lyrics_generation:
            return

        self.call_from_thread(
            self._apply_lyrics, artist, title, original, translated, generation,
        )

    def _apply_lyrics(
        self,
        artist: str,
        title: str,
        original: str,
        translated: str,
        generation: int,
    ) -> None:
        """Wendet Lyrics auf die UI an (Main-Thread)."""
        if generation != self._lyrics_generation:
            return

        self.query_one("#lyrics-panel", LyricsPanel).show_lyrics(
            artist, title, original,
        )
        self.query_one("#translation-panel", TranslationPanel).show_translation(
            artist, title, translated,
        )

    def _refresh_favorites_tree(self) -> None:
        """Aktualisiert den Favoriten-Baum mit aktuellen Daten."""
        fav_tree = self.query_one("#favorites-tree", FavoritesTree)
        favorites = self._playlist_service.get_favorites()
        paths = [entry.path for entry in favorites.entries]
        fav_tree.load_favorites(paths, self._tree_root)

    def _refresh_playlist_tree(self) -> None:
        """Aktualisiert den Playlist-Baum mit allen Playlists."""
        pl_tree = self.query_one("#playlist-tree", PlaylistTree)
        names = self._playlist_service.list_playlists()
        playlists: dict[str, list[Path]] = {}
        for name in names:
            tracks = self._playlist_service.load_playlist_tracks(name)
            playlists[name] = tracks
        pl_tree.load_playlists(playlists)

    def _write_log(self, message: str) -> None:
        """Schreibt eine Nachricht ins Debug-Log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        try:
            log_widget = self.query_one("#app-log", RichLog)
            log_widget.write(f"[dim]{timestamp}[/dim] {message}")
            self._log_lines.append(f"{timestamp} {message}")
        except Exception:
            pass

    def on_unmount(self) -> None:
        """Cleanup beim Beenden."""
        self._lyrics_generation += 1  # Offene Lyrics-Threads ignorieren
        self._spectrum_analyzer.unload()
        self._audio_player.cleanup()
        release_lock()
