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

import contextlib

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.widgets import (
    DirectoryTree,
    Footer,
    Header,
    Input,
    RichLog,
    TabbedContent,
    TabPane,
)
from textual_widgets import (
    ContextMenuItem,
    ContextMenuScreen,
    CrashGuard,
    HorizontalSplitter,
    SearchInputWithHistory,
    VerticalSplitter,
    set_terminal_title,
)

from . import __version__
from .domain.models import AudioFormat, AudioTrack, PlaybackState, RepeatMode, VisualizerMode
from .i18n import current_language, t
from .infrastructure.audio_player import PygameAudioPlayer
from .infrastructure.database import Database
from .infrastructure.metadata_reader import MutagenMetadataReader
from .infrastructure.playlist_migration import migrate_markdown_playlists
from .infrastructure.session import clear_session, load_session, save_session
from .infrastructure.settings import JsonSettingsStore
from .infrastructure.single_instance import acquire_lock, read_play_request, release_lock
from .infrastructure.spectrum import SpectrumAnalyzer
from .infrastructure.sqlite_history_repository import SqliteHistoryRepository
from .infrastructure.sqlite_playlist_repository import SqlitePlaylistRepository
from .infrastructure.sqlite_search_history_repository import SqliteSearchHistoryRepository
from .screens.library_picker_screen import LibraryPickerScreen
from .services.details_service import DetailsResult, DetailsService
from .services.history_service import DEFAULT_HISTORY_LIMIT, HistoryService
from .services.liner_notes_service import LinerNotesService
from .services.lyrics_service import LyricsService
from .services.metadata_service import MetadataService
from .services.player_service import PlayerService
from .services.playlist_service import PlaylistService
from .themes import (
    DEFAULT_THEME,
    RETRO_THEME_NAMES,
    RETRO_THEMES,
    THEME_DISPLAY_NAMES,
    migrate_theme_name,
)
from .widgets.control_panel import ControlPanel
from .widgets.cover_art_panel import CoverArtPanel
from .widgets.details_panel import DetailsPanel
from .widgets.favorites_tree import FavoritesTree
from .widgets.file_table import FileTable
from .widgets.folder_browser import FolderBrowser
from .widgets.history_tree import HistoryTree
from .widgets.info_panel import InfoPanel
from .widgets.lyrics_panel import LyricLine, LyricsPanel
from .widgets.playlist_tree import PlaylistTree
from .widgets.quick_jump_sidebar import QuickJumpSidebar
from .widgets.search_tree import SearchTree
from .widgets.translation_panel import TranslationPanel
from .widgets.transport_bar import TransportBar
from .widgets.visualizer import Visualizer
from .widgets.youtube_panel import YoutubePanel


def _sanitize_filename(name: str) -> str:
    """Erzeugt einen sicheren Dateinamen (keine Pfad-/Wildcard-Zeichen)."""
    safe = re.sub(r'[<>:"/\\|?*]', "_", name).strip(". ")
    return safe[:120]


class RetroAmpApp(CrashGuard, App):
    """retro-amp — Terminal-Musikplayer mit Retro-Charme."""

    CSS_PATH = "app.tcss"
    TITLE = f"retro-amp v{__version__}"

    def __init__(self, start_path: str = "", play_file: str = "") -> None:
        super().__init__()

        # Crash-Guard: Fehlerdialog statt Total-Absturz, Sprache aus i18n
        self.crash_guard_lang = current_language()

        # Bindings im Footer (sichtbar)
        self._bindings.bind("tab", "cycle_view", t("binding.cycle_view"), key_display="TAB", priority=True)
        self._bindings.bind("q", "quit", t("binding.quit"))
        self._bindings.bind("space", "toggle_pause", t("binding.play_pause"), key_display="SPC", priority=True)
        self._bindings.bind("plus,equal", "volume_up", "Vol+", key_display="+", priority=True)
        self._bindings.bind("minus", "volume_down", "Vol-", key_display="-", priority=True)
        self._bindings.bind("f", "toggle_favorite", t("binding.favorite"), priority=True)
        self._bindings.bind("p", "show_playlists", t("binding.playlists"), priority=True)
        self._bindings.bind("u", "rename_file", t("binding.rename"), priority=True)
        self._bindings.bind("delete", "delete_file", t("binding.delete"), key_display="DEL", priority=True)
        self._bindings.bind("t", "cycle_theme", t("binding.theme"), priority=True)
        self._bindings.bind("s", "show_settings", t("binding.settings"), priority=True)
        self._bindings.bind("i", "show_about", t("binding.info"), priority=True)
        self._bindings.bind("l", "toggle_log", t("binding.log"), priority=True)
        # Versteckte Bindings (nur Tastatur, nicht im Footer)
        self._bindings.bind("c", "copy_log", t("binding.copy_log"), show=False, priority=True)
        self._bindings.bind("x", "toggle_shuffle", t("binding.shuffle"), show=False, priority=True)
        self._bindings.bind("r", "cycle_repeat", t("binding.repeat"), show=False, priority=True)

        # Footer-Tooltips fuer alle Bindings setzen (Pflicht). BindingsMap.bind()
        # kennt keinen tooltip-Parameter, darum nachtraeglich per replace.
        self._apply_binding_tooltips()

        # Retro-Themes registrieren
        for retro_theme in RETRO_THEMES:
            self.register_theme(retro_theme)

        # Infrastructure (Composition Root — hier wird verdrahtet)
        self._audio_player = PygameAudioPlayer()
        self._metadata_reader = MutagenMetadataReader()
        self._settings_store = JsonSettingsStore()
        self._database = Database()
        self._database.open()
        self._playlist_store = SqlitePlaylistRepository(self._database.connection)
        # Einmalige Migration der alten ~/.retro-amp/playlists/*.md-Dateien.
        # Entfernt MD-Dateien nach erfolgreichem Import; spaetere Starts sind No-Ops.
        migrate_markdown_playlists(
            Path.home() / ".retro-amp" / "playlists",
            self._playlist_store,
        )
        self._spectrum_analyzer = SpectrumAnalyzer()

        # Services
        self._player_service = PlayerService(self._audio_player)
        self._metadata_service = MetadataService(self._metadata_reader)
        self._playlist_service = PlaylistService(self._playlist_store)
        self._history_repo = SqliteHistoryRepository(self._database.connection)
        self._search_history_repo = SqliteSearchHistoryRepository(self._database.connection)
        # Auf 100 Eintraege begrenzen — verhindert unbegrenztes Wachstum.
        self._search_history_repo.trim(100)
        self._history_service = HistoryService(
            self._history_repo,
            is_enabled=lambda: self._database.get_bool_setting("history_enabled", False),
            get_limit=lambda: self._database.get_int_setting(
                "history_limit",
                DEFAULT_HISTORY_LIMIT,
            ),
        )
        self._liner_notes_service = LinerNotesService()
        self._lyrics_service = LyricsService(on_log=self._lyrics_log_from_thread)
        self._details_service = DetailsService()

        # Generations-Counter fuer Lyrics-Thread-Cancellation
        self._lyrics_generation: int = 0
        # Generations-Counter fuer Details-Thread-Cancellation
        self._details_generation: int = 0

        # Settings laden
        settings = self._settings_store.load()
        self._player_service.set_volume(float(settings.get("volume", 0.8)))

        # Gespeichertes Theme anwenden — alte Slugs migrieren
        # (textual-themes 0.5 hat die meisten Themes umbenannt).
        saved_theme = str(settings.get("theme", DEFAULT_THEME))
        migrated = migrate_theme_name(saved_theme)
        if migrated != saved_theme:
            settings["theme"] = migrated
            self._settings_store.save(settings)
            saved_theme = migrated
        if saved_theme in RETRO_THEME_NAMES:
            self.theme = saved_theme
        else:
            self.theme = DEFAULT_THEME

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

        # Persistierte Musik-Bibliothek separat tracken — die Sidebar-"Musik"-Taste
        # springt immer hierhin, auch wenn _tree_root tempotaer auf einen anderen
        # Ordner (Downloads, Drive, ...) gesetzt wurde.
        self._music_library = self._tree_root

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

        # Repeat-Modus
        self._repeat_mode: RepeatMode = RepeatMode.OFF

        # Session-Save Throttling (alle 10 Ticks = 5 Sekunden)
        self._session_tick_counter: int = 0

        # Letztes Cover-Art-Ergebnis fuer Now-Playing-Screen
        self._last_cover: tuple[str, str, bytes | None] | None = None

        # Dedup-Fenster: verhindert, dass derselbe Track innerhalb kurzer
        # Zeit zweimal gestartet wird (eine Mausinteraktion kann ueber
        # mehrere Pfade _play_track triggern, z.B. Tree-Select + spaeter
        # eintreffender Scan-Apply).
        self._last_play_path: str | None = None
        self._last_play_time: float = 0.0

    def _apply_binding_tooltips(self) -> None:
        """Setzt fuer jedes App-Binding einen erklaerenden Footer-Tooltip.

        Der Footer zeigt den Tooltip beim Maus-Hover ueber der Taste. Da
        `BindingsMap.bind()` keinen tooltip-Parameter kennt und `Binding`
        frozen ist, wird der Tooltip nach dem Binden per `dataclasses.replace`
        gesetzt. Schluessel-Schema: ``tooltip.<action>`` in den Sprachdateien.
        """
        actions_with_tooltip = {
            "cycle_view",
            "quit",
            "toggle_pause",
            "volume_up",
            "volume_down",
            "toggle_favorite",
            "show_playlists",
            "rename_file",
            "delete_file",
            "cycle_theme",
            "show_settings",
            "show_about",
            "toggle_log",
            "copy_log",
            "toggle_shuffle",
            "cycle_repeat",
        }
        for key, bindings in self._bindings.key_to_bindings.items():
            for i, binding in enumerate(bindings):
                if binding.action in actions_with_tooltip:
                    self._bindings.key_to_bindings[key][i] = dataclasses.replace(
                        binding,
                        tooltip=t(f"tooltip.{binding.action}"),
                    )

    def compose(self) -> ComposeResult:
        yield Header()
        yield SearchInputWithHistory(
            icon="🔍",
            placeholder=t("search.placeholder"),
            entries=self._search_history_repo.list_recent(20),
            max_visible=10,
            input_id="global-search",
            dropdown_id="global-search-dropdown",
            id="global-search-wrapper",
        )
        with Horizontal(id="main-container"):
            with Vertical(id="left-panel"), TabbedContent(id="left-tabs"):
                with TabPane(t("tab.browser"), id="tab-browser"), Vertical(id="browser-pane"):
                    yield QuickJumpSidebar(self._music_library, id="quick-jump")
                    yield HorizontalSplitter(target_id="quick-jump", min_size=3, max_size=20)
                    yield FolderBrowser(str(self._tree_root), id="folder-browser")
                with TabPane(t("tab.favorites"), id="tab-favorites"):
                    yield FavoritesTree(id="favorites-tree")
                with TabPane(t("tab.playlists"), id="tab-playlists"):
                    yield PlaylistTree(id="playlist-tree")
                with TabPane(t("tab.history"), id="tab-history"):
                    yield HistoryTree(id="history-tree")
                with TabPane(t("tab.search"), id="tab-search"):
                    yield SearchTree(id="search-tree")
            yield VerticalSplitter(target_id="left-panel", min_size=20, max_size=80)
            with Vertical(id="right-panel"):
                yield FileTable(id="file-table")
                yield HorizontalSplitter(target_id="file-table", min_size=5)
                with TabbedContent(id="content-tabs"):
                    with TabPane(t("tab.lyrics"), id="tab-lyrics"):
                        yield LyricsPanel(id="lyrics-panel")
                    with TabPane(t("tab.translation"), id="tab-translation"):
                        yield TranslationPanel(id="translation-panel")
                    with TabPane(t("tab.info"), id="tab-info"):
                        yield InfoPanel(id="info-panel")
                    with TabPane(t("tab.cover"), id="tab-cover"):
                        yield CoverArtPanel(
                            renderer=str(self._settings_store.load().get("cover_renderer", "halfblock")),
                            id="cover-panel",
                        )
                    with TabPane(t("tab.youtube"), id="tab-youtube"):
                        yield YoutubePanel(id="youtube-panel")
                    with TabPane(t("tab.details"), id="tab-details"):
                        yield DetailsPanel(id="details-panel")
        with Horizontal(id="transport-row"):
            yield Visualizer(mode=self._load_visualizer_mode(), id="visualizer")
            yield ControlPanel(id="control-panel")
            yield TransportBar(id="transport")
        yield HorizontalSplitter(target_id="main-container", min_size=10, id="log-splitter")
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
            on_started=self._on_track_started,
        )
        # Theme-Name in Titelleiste (Idle-Anzeige bis ein Track laeuft)
        self.sub_title = self._idle_subtitle()

        # Gespeicherte Splitter-Groessen anwenden (linkes Panel + File-Table)
        self._restore_pane_sizes()

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
            else:
                # Session-Recovery: nach Crash letzten Track wiederherstellen
                self._restore_session()

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
        self._music_library = chosen
        self._initial_scan_path = chosen
        # Pfad persistieren
        settings = self._settings_store.load()
        settings["music_library"] = str(chosen)
        self._settings_store.save(settings)
        # Baum und Tabelle mit neuem Root aktualisieren — bei einer echten
        # Library-Aenderung wollen wir wieder den Default-Label (Pfadname),
        # also den Sidebar-Override loeschen.
        browser = self.query_one("#folder-browser", FolderBrowser)
        browser.set_root_label(None)
        browser.path = str(chosen)
        browser.reload()
        self._scan_directory(chosen)
        # Sidebar-"Musik"-Eintrag aktualisieren
        with contextlib.suppress(Exception):
            self.query_one("#quick-jump", QuickJumpSidebar).set_music_library(chosen)
        self.notify(t("notify.library_changed", path=chosen))
        self._write_log(t("log.library_changed", path=chosen))

    def on_quick_jump_sidebar_path_chosen(
        self,
        event: QuickJumpSidebar.PathChosen,
    ) -> None:
        """Sidebar-Klick → Tree-Root tempotaer auf den gewaehlten Pfad setzen.

        Aendert NICHT die persistierte Musik-Library (settings.music_library);
        der naechste Start landet wieder im Default-Verzeichnis. Wer den Default
        umstellen will, nutzt den Settings-Tab "Bibliothek".

        Das Sidebar-Label (z.B. "📁 Downloads", "💾 C:\\") wird als
        Beschriftung der Tree-Wurzel uebernommen, damit oben im Baum die
        freundliche Bezeichnung statt des Vollpfads steht.
        """
        chosen = event.path
        if not chosen.is_dir():
            self.notify(t("library.error_not_found", path=chosen), severity="warning")
            return
        self._tree_root = chosen
        self._initial_scan_path = chosen
        browser = self.query_one("#folder-browser", FolderBrowser)
        # Erst Override setzen, dann Pfad — so greift der Override auch im
        # initialen reset_node() durch Textual's internen Reload-Worker.
        browser.set_root_label(event.label)
        browser.path = str(chosen)
        browser.reload()
        self._scan_directory(chosen)
        self.notify(t("notify.tree_root_changed", path=chosen))
        self._write_log(t("log.tree_root_changed", path=chosen))

    @work
    async def _expand_tree_to_last_path(self) -> None:
        """Klappt den Baum zum zuletzt besuchten Verzeichnis auf."""
        browser = self.query_one("#folder-browser", FolderBrowser)
        # Warten bis der Root-Knoten geladen ist
        await browser._add_to_load_queue(browser.root)
        await browser.expand_to_path(self._initial_scan_path)

    # --- Event-Handler fuer Widget-Messages ---

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Ordner im Baum ausgewaehlt — rechtes Panel aktualisieren."""
        self._scan_directory(event.path)
        self._save_last_path(event.path)
        self._write_log(t("log.folder", path=event.path))

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Datei im Baum ausgewaehlt — Ordner aktualisieren und abspielen."""
        path = event.path
        if self._metadata_service.is_audio_file(path):
            # Rechtes Panel mit Ordner-Inhalt aktualisieren
            parent = path.parent
            self._scan_directory(parent)
            self._save_last_path(parent)
            track = self._metadata_service.read_track(path)
            self._play_track(track)

    def on_file_table_track_selected(self, event: FileTable.TrackSelected) -> None:
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

    def action_stop(self) -> None:
        """Wiedergabe stoppen und Position auf 0:00 zuruecksetzen."""
        state = self._player_service.state
        if state.is_playing or state.is_paused:
            self._player_service.stop()
            self._sync_visualizer()
            self._update_transport()
            self._write_log(t("log.stop"))

    def on_control_panel_button_clicked(
        self,
        event: ControlPanel.ButtonClicked,
    ) -> None:
        """Control-Panel Button geklickt — Action dispatchen."""
        actions = {
            "prev": self.action_previous_track,
            "seek_back": self.action_seek_backward,
            "play_pause": self.action_toggle_pause,
            "seek_fwd": self.action_seek_forward,
            "next": self.action_next_track,
            "stop": self.action_stop,
            "shuffle": self.action_toggle_shuffle,
            "repeat": self.action_cycle_repeat,
            "favorite": self.action_toggle_favorite,
        }
        handler = actions.get(event.action)
        if handler:
            handler()

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
                    binding,
                    description=label,
                )
                break
        self.refresh_bindings()

        if self._shuffle_mode:
            self.notify(t("notify.shuffle_on"))
            self._write_log(t("log.shuffle_on"))
        else:
            self.notify(t("notify.shuffle_off"))
            self._write_log(t("log.shuffle_off"))
        self._update_control_panel()

    def action_cycle_repeat(self) -> None:
        """Repeat-Modus durchschalten: Off → All → One → Off."""
        cycle = {
            RepeatMode.OFF: RepeatMode.ALL,
            RepeatMode.ALL: RepeatMode.ONE,
            RepeatMode.ONE: RepeatMode.OFF,
        }
        self._repeat_mode = cycle[self._repeat_mode]

        # Binding-Label aktualisieren
        labels = {
            RepeatMode.OFF: t("binding.repeat"),
            RepeatMode.ALL: t("binding.repeat_all"),
            RepeatMode.ONE: t("binding.repeat_one"),
        }
        label = labels[self._repeat_mode]
        bindings_list = self._bindings.key_to_bindings.get("r", [])
        for i, binding in enumerate(bindings_list):
            if binding.action == "cycle_repeat":
                self._bindings.key_to_bindings["r"][i] = dataclasses.replace(
                    binding,
                    description=label,
                )
                break
        self.refresh_bindings()

        notifications = {
            RepeatMode.OFF: t("notify.repeat_off"),
            RepeatMode.ALL: t("notify.repeat_all"),
            RepeatMode.ONE: t("notify.repeat_one"),
        }
        logs = {
            RepeatMode.OFF: t("log.repeat_off"),
            RepeatMode.ALL: t("log.repeat_all"),
            RepeatMode.ONE: t("log.repeat_one"),
        }
        self.notify(notifications[self._repeat_mode])
        self._write_log(logs[self._repeat_mode])
        self._update_control_panel()

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
        self._update_control_panel()

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

    def action_show_about(self) -> None:
        """About-Dialog anzeigen (standardisierter AboutScreen aus textual-widgets)."""
        from textual_widgets import AboutScreen

        from . import __author__, __year__
        from .i18n import current_language

        description = t("about.description") + t("about.subtitle") + "MP3 · OGG · FLAC · WAV · MOD · XM · S3M · SID"
        self.push_screen(
            AboutScreen(
                app_name="retro-amp",
                version=__version__,
                author=__author__,
                release=__year__,
                description=description,
                lang=current_language(),
                url="https://github.com/michaelblaess/retro-amp",
            )
        )

    def action_show_settings(self) -> None:
        """Settings-Dialog anzeigen."""
        from .screens.settings_screen import SettingsScreen  # Lazy import

        current = self._settings_store.load()
        db_settings: dict[str, object] = {
            "db_journal_mode": self._database.get_setting("db_journal_mode", "DELETE"),
            "history_enabled": self._database.get_bool_setting("history_enabled", False),
            "history_limit": self._database.get_int_setting(
                "history_limit",
                DEFAULT_HISTORY_LIMIT,
            ),
        }
        self.push_screen(
            SettingsScreen(
                current,
                db_settings,
                on_clear_history=self._clear_history,
                lang=current_language(),
            ),
            callback=self._on_settings_closed,
        )

    def _clear_history(self) -> int:
        """Callback fuer den "Verlauf loeschen"-Button im Settings-Dialog."""
        count = sum(len(g.entries) for g in self._history_service.list_grouped())
        self._history_service.clear_all()
        with contextlib.suppress(Exception):
            self._refresh_history_tree()
        return count

    # DB-Settings-Schluessel — beim Schliessen aus dem flachen Ergebnis-Dict
    # von BaseSettingsScreen herausgetrennt und in der DB statt settings.json
    # gespeichert.
    _DB_SETTING_KEYS = ("db_journal_mode", "history_enabled", "history_limit")

    def _on_settings_closed(
        self,
        result: dict[str, object] | None,
    ) -> None:
        """Callback nach Schliessen des Settings-Dialogs.

        BaseSettingsScreen liefert ein einzelnes flaches Dict. Die
        DB-Settings werden anhand von ``_DB_SETTING_KEYS`` herausgetrennt,
        der Rest landet in settings.json.
        """
        if result is None:
            return
        db_keys = set(self._DB_SETTING_KEYS)
        new_settings = {k: v for k, v in result.items() if k not in db_keys}
        new_db_settings = {k: result[k] for k in self._DB_SETTING_KEYS if k in result}

        current = self._settings_store.load()
        changed_renderer = current.get("cover_renderer") != new_settings.get("cover_renderer")
        changed_visualizer = current.get("visualizer_mode") != new_settings.get("visualizer_mode")
        old_lang = str(current.get("language", current_language()))
        new_lang = str(new_settings.get("language", old_lang))
        changed_language = old_lang != new_lang
        old_library = str(current.get("music_library", "") or "")
        new_library = str(new_settings.get("music_library", "") or "")
        changed_library = bool(new_library) and new_library != old_library
        current.update(new_settings)
        self._settings_store.save(current)

        # Library-Wechsel: Tree-Root, persistierten Anker und Sidebar nachziehen.
        if changed_library:
            chosen = Path(new_library)
            if chosen.is_dir():
                self._music_library = chosen
                self._tree_root = chosen
                self._initial_scan_path = chosen
                with contextlib.suppress(Exception):
                    browser = self.query_one("#folder-browser", FolderBrowser)
                    browser.set_root_label(None)
                    browser.path = str(chosen)
                    browser.reload()
                with contextlib.suppress(Exception):
                    self.query_one("#quick-jump", QuickJumpSidebar).set_music_library(chosen)
                self._scan_directory(chosen)
                self._write_log(t("log.library_changed", path=chosen))

        # Visualizer-Modus live anwenden (kein Neustart noetig)
        if changed_visualizer:
            try:
                new_mode = VisualizerMode(str(new_settings.get("visualizer_mode")))
                self.query_one("#visualizer", Visualizer).set_mode(new_mode)
            except (ValueError, Exception):
                pass

        # DB-Settings persistieren — journal_mode greift erst nach Neustart
        old_journal = self._database.get_setting("db_journal_mode", "DELETE")
        new_journal = str(new_db_settings.get("db_journal_mode", old_journal))
        changed_journal = old_journal.upper() != new_journal.upper()
        if changed_journal:
            self._database.set_setting("db_journal_mode", new_journal)

        # History-Settings: live wirksam, kein Neustart noetig
        if "history_enabled" in new_db_settings:
            self._database.set_bool_setting(
                "history_enabled",
                bool(new_db_settings["history_enabled"]),
            )
        if "history_limit" in new_db_settings:
            with contextlib.suppress(TypeError, ValueError):
                self._database.set_int_setting(
                    "history_limit",
                    int(new_db_settings["history_limit"]),
                )
        # Tab neu rendern (Hinweis/Eintraege umschalten)
        with contextlib.suppress(Exception):
            self._refresh_history_tree()

        needs_restart = changed_renderer or changed_journal or changed_language
        if needs_restart:
            self.notify(
                f"{t('settings.saved')} — {t('settings.restart_hint')}",
                severity="information",
            )
        else:
            self.notify(t("settings.saved"), severity="information")

    def action_focus_search(self) -> None:
        """Fokus auf Suchleiste setzen."""
        search_input = self.query_one("#global-search", Input)
        search_input.focus()

    def action_cycle_view(self) -> None:
        """Wechselt zwischen Dateien, Favoriten, Playlists, Verlauf und Suche."""
        tabs = self.query_one("#left-tabs", TabbedContent)
        tab_ids = [
            "tab-browser",
            "tab-favorites",
            "tab-playlists",
            "tab-history",
            "tab-search",
        ]
        try:
            idx = tab_ids.index(tabs.active)
        except ValueError:
            idx = 0
        next_idx = (idx + 1) % len(tab_ids)
        tabs.active = tab_ids[next_idx]

    def on_tabbed_content_tab_activated(
        self,
        event: TabbedContent.TabActivated,
    ) -> None:
        """Reagiert auf Tab-Wechsel (links UND rechts)."""
        if event.tabbed_content.id == "content-tabs":
            if event.pane.id == "tab-details":
                # Lazy: Details erst beim ersten Aktivieren laden.
                panel = self.query_one("#details-panel", DetailsPanel)
                pending = panel.pending_path()
                if pending is not None:
                    self._trigger_details_load(pending)
                elif self._player_service.state.current_track is None:
                    panel.show_no_track()
            return
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
        elif event.pane.id == "tab-history":
            self._refresh_history_tree()
            self.query_one("#history-tree", HistoryTree).focus()
            self._write_log(t("log.view_history"))

    def action_toggle_log(self) -> None:
        """Debug-Log ein-/ausblenden."""
        log_widget = self.query_one("#app-log", RichLog)
        splitter = self.query_one("#log-splitter", HorizontalSplitter)
        was_visible = log_widget.has_class("visible")
        log_widget.toggle_class("visible")
        splitter.toggle_class("visible")
        if was_visible:
            # Splitter-Drag setzt eine konkrete Hoehe auf main-container —
            # beim Ausblenden auf 4fr zuruecksetzen, sonst bleibt der
            # Hauptbereich klein und ein leerer Streifen entsteht.
            self.query_one("#main-container").styles.height = "4fr"

    def action_copy_log(self) -> None:
        """Gesamten Log-Inhalt in die Zwischenablage kopieren."""
        if not self._log_lines:
            self.notify(t("notify.log_empty"), severity="warning")
            return
        text = "\n".join(self._log_lines)
        self.copy_to_clipboard(text)
        self.notify(t("notify.log_copied", count=len(self._log_lines)))

    def _export_log(self) -> None:
        """Speichert den Log-Inhalt als Textdatei im Home-Verzeichnis."""
        if not self._log_lines:
            self.notify(t("notify.log_empty"), severity="warning")
            return
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_path = Path.home() / f"retro-amp-log-{timestamp}.txt"
        try:
            out_path.write_text("\n".join(self._log_lines) + "\n", encoding="utf-8")
        except OSError as exc:
            self.notify(t("notify.log_export_error", error=str(exc)), severity="error")
            return
        self.notify(t("notify.log_exported", path=str(out_path)))

    def on_click(self, event: Click) -> None:
        """Rechtsklick auf Log- oder Lyrics-Panel oeffnet das Kontextmenue."""
        if event.button != 3:
            return

        # Lyrics-Panel hat Vorrang (liegt ueber Log-Panel im Layout)
        try:
            lyrics_widget = self.query_one("#lyrics-panel", LyricsPanel)
        except Exception:
            lyrics_widget = None
        if (
            lyrics_widget is not None
            and lyrics_widget.display
            and lyrics_widget.region.contains(event.screen_x, event.screen_y)
        ):
            has_lyrics = lyrics_widget.has_lyrics()
            items = [
                ContextMenuItem("copy", t("lyricsmenu.copy"), enabled=has_lyrics),
                ContextMenuItem("save", t("lyricsmenu.save"), enabled=has_lyrics),
                ContextMenuItem.separator(),
                ContextMenuItem("reload", t("lyricsmenu.reload")),
                ContextMenuItem.separator(),
                ContextMenuItem("open_lrclib", t("lyricsmenu.open_lrclib")),
                ContextMenuItem("search_google", t("lyricsmenu.search_google")),
            ]
            self.push_screen(
                ContextMenuScreen(items, at=(event.screen_x, event.screen_y)),
                callback=self._on_lyrics_menu_action,
            )
            return

        # Translation-Panel: nur Copy + Save
        try:
            translation_widget = self.query_one("#translation-panel", TranslationPanel)
        except Exception:
            translation_widget = None
        if (
            translation_widget is not None
            and translation_widget.display
            and translation_widget.region.contains(event.screen_x, event.screen_y)
        ):
            has_text = translation_widget.has_translation()
            items = [
                ContextMenuItem("copy", t("translationmenu.copy"), enabled=has_text),
                ContextMenuItem("save", t("translationmenu.save"), enabled=has_text),
            ]
            self.push_screen(
                ContextMenuScreen(items, at=(event.screen_x, event.screen_y)),
                callback=self._on_translation_menu_action,
            )
            return

        log_widget = self.query_one("#app-log", RichLog)
        if not log_widget.has_class("visible"):
            return
        if not log_widget.region.contains(event.screen_x, event.screen_y):
            return
        items = [
            ContextMenuItem("copy", t("logmenu.copy")),
            ContextMenuItem("export", t("logmenu.export")),
            ContextMenuItem.separator(),
            ContextMenuItem("hide", t("logmenu.hide")),
        ]
        self.push_screen(
            ContextMenuScreen(items, at=(event.screen_x, event.screen_y)),
            callback=self._on_log_menu_action,
        )

    def _on_log_menu_action(self, action_id: str | None) -> None:
        """Verarbeitet die im Log-Kontextmenue gewaehlte Aktion."""
        if action_id == "copy":
            self.action_copy_log()
        elif action_id == "export":
            self._export_log()
        elif action_id == "hide":
            self.action_toggle_log()

    def _on_lyrics_menu_action(self, action_id: str | None) -> None:
        """Verarbeitet die im Lyrics-Kontextmenue gewaehlte Aktion."""
        if action_id == "copy":
            self._copy_lyrics()
        elif action_id == "save":
            self._save_lyrics()
        elif action_id == "reload":
            self._reload_lyrics()
        elif action_id == "open_lrclib":
            self._open_lyrics_at_lrclib()
        elif action_id == "search_google":
            self._search_lyrics_at_google()

    def _copy_lyrics(self) -> None:
        """Kopiert die aktuell angezeigten Lyrics in die Zwischenablage."""
        panel = self.query_one("#lyrics-panel", LyricsPanel)
        text = panel.get_lyrics_text().strip()
        if not text:
            self.notify(t("notify.lyrics_empty"), severity="warning")
            return
        self.copy_to_clipboard(text)
        line_count = text.count("\n") + 1
        self.notify(t("notify.lyrics_copied", count=line_count))

    def _save_lyrics(self) -> None:
        """Speichert die aktuell angezeigten Lyrics als .txt im Home-Verzeichnis."""
        panel = self.query_one("#lyrics-panel", LyricsPanel)
        text = panel.get_lyrics_text().strip()
        if not text:
            self.notify(t("notify.lyrics_empty"), severity="warning")
            return
        artist = _sanitize_filename(panel.artist) or "Unknown"
        title = _sanitize_filename(panel.title) or "Untitled"
        out_path = Path.home() / f"{artist} - {title}.txt"
        try:
            out_path.write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            self.notify(t("notify.lyrics_save_error", error=str(exc)), severity="error")
            return
        self.notify(t("notify.lyrics_saved", path=str(out_path)))

    def _reload_lyrics(self) -> None:
        """Loescht den Lyrics-Cache und holt die Lyrics neu."""
        panel = self.query_one("#lyrics-panel", LyricsPanel)
        artist = panel.artist
        title = panel.title
        if not artist or not title:
            self.notify(t("notify.lyrics_no_track"), severity="warning")
            return
        self._lyrics_service.invalidate_cache(artist, title)
        self._lyrics_generation += 1
        generation = self._lyrics_generation
        panel.show_loading(artist, title)
        self.query_one("#translation-panel", TranslationPanel).show_loading(artist, title)
        self._fetch_lyrics_async(artist, title, generation)
        self.notify(t("notify.lyrics_reloading"))

    def _lyrics_search_terms(self) -> tuple[str, str] | None:
        """Liefert (artist, title) fuer Lyrics-Websuchen mit aufgeraeumten Werten.

        Schneidet Track-Nummer-Prefixe ab ('01. ', '01 - ', '01-', '01 ').
        Gibt None zurueck wenn keine Lyrics geladen sind.
        """
        panel = self.query_one("#lyrics-panel", LyricsPanel)
        artist = panel.artist.strip()
        title = panel.title.strip()
        if not artist or not title:
            return None
        clean_title = re.sub(r"^\d+\s*[.\-]\s*", "", title).strip() or title
        return artist, clean_title

    def _open_lyrics_at_lrclib(self) -> None:
        """Oeffnet die lrclib.net-Suche fuer den aktuellen Track im Browser."""
        terms = self._lyrics_search_terms()
        if terms is None:
            self.notify(t("notify.lyrics_no_track"), severity="warning")
            return
        import urllib.parse
        import webbrowser

        artist, title = terms
        query = urllib.parse.quote(f"{artist} {title}")
        webbrowser.open(f"https://lrclib.net/search/{query}")

    def _search_lyrics_at_google(self) -> None:
        """Sucht den aktuellen Track bei Google im Browser."""
        terms = self._lyrics_search_terms()
        if terms is None:
            self.notify(t("notify.lyrics_no_track"), severity="warning")
            return
        import urllib.parse
        import webbrowser

        artist, title = terms
        query = urllib.parse.quote_plus(f"{artist} {title} lyrics")
        webbrowser.open(f"https://www.google.com/search?q={query}")

    def _on_translation_menu_action(self, action_id: str | None) -> None:
        """Verarbeitet die im Translation-Kontextmenue gewaehlte Aktion."""
        if action_id == "copy":
            self._copy_translation()
        elif action_id == "save":
            self._save_translation()

    def _copy_translation(self) -> None:
        """Kopiert die uebersetzten Lyrics in die Zwischenablage."""
        panel = self.query_one("#translation-panel", TranslationPanel)
        text = panel.get_translation_text().strip()
        if not text:
            self.notify(t("notify.lyrics_empty"), severity="warning")
            return
        self.copy_to_clipboard(text)
        line_count = text.count("\n") + 1
        self.notify(t("notify.translation_copied", count=line_count))

    def _save_translation(self) -> None:
        """Speichert die uebersetzten Lyrics als .txt im Home-Verzeichnis."""
        panel = self.query_one("#translation-panel", TranslationPanel)
        text = panel.get_translation_text().strip()
        if not text:
            self.notify(t("notify.lyrics_empty"), severity="warning")
            return
        artist = _sanitize_filename(panel.artist) or "Unknown"
        title = _sanitize_filename(panel.title) or "Untitled"
        lang = current_language()
        out_path = Path.home() / f"{artist} - {title} ({lang}).txt"
        try:
            out_path.write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            self.notify(t("notify.lyrics_save_error", error=str(exc)), severity="error")
            return
        self.notify(t("notify.lyrics_saved", path=str(out_path)))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Suchleiste: Enter gedrueckt → Suche starten."""
        if event.input.id != "global-search":
            return
        query = event.value.strip()
        if not query:
            return
        # Such-Verlauf aktualisieren (UPSERT) und Dropdown neu befuellen.
        self._search_history_repo.add(query)
        try:
            wrapper = self.query_one("#global-search-wrapper", SearchInputWithHistory)
            wrapper.set_entries(self._search_history_repo.list_recent(20))
            wrapper.hide_dropdown()
        except Exception:
            pass
        # Loading-Hinweis im Suchbaum, Tab links aktivieren
        search_tree = self.query_one("#search-tree", SearchTree)
        search_tree.show_loading(query)
        left_tabs = self.query_one("#left-tabs", TabbedContent)
        left_tabs.active = "tab-search"
        # Suche im Background-Thread starten
        self._run_global_search(query)

    def on_search_input_with_history_history_entry_delete_requested(
        self,
        event: SearchInputWithHistory.HistoryEntryDeleteRequested,
    ) -> None:
        """Eintrag aus Such-Verlauf loeschen (Delete-Taste im Dropdown)."""
        self._search_history_repo.delete(event.entry)
        try:
            wrapper = self.query_one("#global-search-wrapper", SearchInputWithHistory)
            wrapper.set_entries(self._search_history_repo.list_recent(20))
        except Exception:
            pass

    @work(exclusive=True, group="search", thread=True)
    def _run_global_search(self, query: str) -> None:
        """Globale Dateisuche im Background-Thread."""
        results = self._do_file_search(query, self._tree_root)
        self.call_from_thread(self._apply_search_results, query, results)

    _SEPARATOR_RE = re.compile(r"[.\-_]")

    def _do_file_search(
        self,
        query: str,
        root: Path,
    ) -> list[tuple[Path, bool]]:
        """Fuehrt die Dateisuche durch (Thread-safe, kein Widget-Zugriff).

        Returns:
            Liste von ``(absoluter Pfad, is_dir)``-Tuples — der SearchTree
            generiert daraus selbst die Anzeige (gruppiert nach Parent).
        """
        query_norm = self._SEPARATOR_RE.sub(" ", query.lower())
        results: list[tuple[Path, bool]] = []
        audio_exts = AudioFormat.supported_extensions()
        try:
            for p in sorted(root.rglob("*")):
                if query_norm in self._SEPARATOR_RE.sub(" ", p.name.lower()):
                    if p.is_dir():
                        results.append((p, True))
                    elif p.suffix.lower() in audio_exts:
                        results.append((p, False))
        except PermissionError:
            pass
        return results[:200]

    def _apply_search_results(
        self,
        query: str,
        results: list[tuple[Path, bool]],
    ) -> None:
        """Zeigt Suchergebnisse im Suchbaum an (Main-Thread)."""
        search_tree = self.query_one("#search-tree", SearchTree)
        search_tree.load_results(query, results, self._tree_root)
        self._write_log(t("log.search_results", query=query, count=len(results)))

    def on_search_tree_track_selected(
        self,
        event: SearchTree.TrackSelected,
    ) -> None:
        """Track im Suchbaum ausgewaehlt → abspielen."""
        path = event.path
        if not path.is_file():
            return
        parent = path.parent
        self._scan_directory(parent)
        self._save_last_path(parent)
        if self._metadata_service.is_audio_file(path):
            track = self._metadata_service.read_track(path)
            self._play_track(track)

    def on_search_tree_folder_selected(
        self,
        event: SearchTree.FolderSelected,
    ) -> None:
        """Ordner im Suchbaum ausgewaehlt → in der Datei-Tabelle oeffnen."""
        path = event.path
        if not path.is_dir():
            return
        self._scan_directory(path)
        self._save_last_path(path)
        self.notify(t("notify.folder", name=path.name))

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
                new_path,
                is_playing_target,
                resume_position,
                playing,
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
                old_track.path.relative_to(old_track.path)
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

        # Kontextabhaengig: Fokus auf Baum → Ordner/Datei im Baum loeschen
        folder_browser = self.query_one("#folder-browser", FolderBrowser)
        if folder_browser.has_focus or folder_browser.has_focus_within:
            node = folder_browser.cursor_node
            if node and node.data:
                target = node.data.path
                if target == self._tree_root:
                    self.notify(t("notify.cannot_delete_root"), severity="warning")
                    return
                if target.is_dir():
                    # Dateien im Ordner zaehlen
                    try:
                        count = sum(1 for _ in target.rglob("*") if _.is_file())
                    except PermissionError:
                        count = 0
                    msg = t(
                        "confirm.delete_folder_message",
                        name=target.name,
                        count=count,
                    )
                else:
                    msg = t("confirm.delete_file_message", name=target.name)
                self._delete_with_unload(msg, target)
                return

        # Fallback: markierte Datei in der Tabelle
        file_table = self.query_one("#file-table", FileTable)
        track = file_table.highlighted_track
        if not track:
            self.notify(t("notify.no_track"), severity="warning")
            return

        self._delete_with_unload(
            t("confirm.delete_file_message", name=track.name),
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
                deleted_path,
                is_playing_target,
                playing,
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
                tracks = [self._metadata_service.read_track(p) for p in track_paths if p.is_file()]
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

        # Input-Widget fokussiert → Delete deaktivieren
        if isinstance(self.focused, Input) and action == "delete_file":
            return None

        state = self._player_service.state
        has_track = state.current_track is not None

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
        self,
        event: FavoritesTree.TrackSelected,
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
        self,
        event: FavoritesTree.TrackRemoveRequested,
    ) -> None:
        """Track aus Favoriten entfernen."""
        removed = self._playlist_service.remove_from_favorites(event.path)
        if removed:
            self.notify(t("notify.favorite_tree_removed", name=event.path.name))
            self._refresh_favorites_tree()
            self._write_log(t("log.favorite_removed", name=event.path.name))

    def on_history_tree_track_selected(
        self,
        event: HistoryTree.TrackSelected,
    ) -> None:
        """Verlauf-Track ausgewaehlt — navigieren und abspielen."""
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

    def on_history_tree_clear_requested(
        self,
        event: HistoryTree.ClearRequested,
    ) -> None:
        """Verlauf auf Wunsch komplett loeschen."""
        self._history_service.clear_all()
        self._refresh_history_tree()
        self.notify(t("notify.history_cleared"))
        self._write_log(t("log.history_cleared"))

    def on_playlist_tree_track_selected(
        self,
        event: PlaylistTree.TrackSelected,
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
        self,
        event: PlaylistTree.TrackRemoveRequested,
    ) -> None:
        """Track aus Playlist entfernen."""
        removed = self._playlist_service.remove_from_playlist(
            event.playlist_name,
            event.path,
        )
        if removed:
            self.notify(t("notify.playlist_track_removed", playlist=event.playlist_name, name=event.path.name))
            self._refresh_playlist_tree()
            self._write_log(t("log.playlist_track_removed", playlist=event.playlist_name, name=event.path.name))

    def on_transport_bar_volume_clicked(
        self,
        event: TransportBar.VolumeClicked,
    ) -> None:
        """Lautstaerke per Mausklick aendern."""
        self._player_service.set_volume(event.volume)
        self._update_transport()
        self._save_volume()
        self._write_log(t("log.volume", pct=int(event.volume * 100)))

    def on_transport_bar_seek_clicked(
        self,
        event: TransportBar.SeekClicked,
    ) -> None:
        """Position per Mausklick im Fortschrittsbalken aendern."""
        self._player_service.seek_to(event.position)
        self._update_transport()

    def on_lyric_line_clicked(
        self,
        event: LyricLine.Clicked,
    ) -> None:
        """Position per Klick auf Lyrics-Zeile aendern."""
        self._player_service.seek_to(event.timestamp)
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
        # Dedup: gleicher Track innerhalb 2 s → Zweitaufruf ignorieren.
        path_key = str(track.path)
        now = time.monotonic()
        if self._last_play_path == path_key and (now - self._last_play_time) < 2.0:
            return
        self._last_play_path = path_key
        self._last_play_time = now

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
        log_name = f"{track.artist} – {track.title}" if track.artist and track.title else track.display_name
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
        # Synced Lyrics aktualisieren
        state = self._player_service.state
        if state.is_playing:
            self.query_one("#lyrics-panel", LyricsPanel).update_position(
                state.position_seconds,
            )
            # Session-State periodisch speichern (alle 5 Sekunden)
            self._session_tick_counter += 1
            if self._session_tick_counter >= 10 and state.current_track:
                self._session_tick_counter = 0
                save_session(
                    track_path=str(state.current_track.path),
                    position_seconds=state.position_seconds,
                    volume=state.volume,
                )

    def _load_visualizer_mode(self) -> VisualizerMode:
        """Liest den gespeicherten Visualizer-Modus aus den Settings."""
        raw = str(self._settings_store.load().get("visualizer_mode", VisualizerMode.BARS.value))
        try:
            return VisualizerMode(raw)
        except ValueError:
            return VisualizerMode.BARS

    def _restore_pane_sizes(self) -> None:
        """Setzt die Splitter-gesteuerten Panel-Groessen aus den Settings.

        Werte sind in `pane_sizes` als dict {target_id: size} abgelegt.
        Faellt graceful auf die CSS-Defaults zurueck wenn nichts gespeichert.
        """
        sizes = self._settings_store.load().get("pane_sizes", {})
        if not isinstance(sizes, dict):
            return
        for target_id, size in sizes.items():
            try:
                widget = self.query_one(f"#{target_id}")
            except Exception:
                continue
            try:
                value = int(size)
            except (TypeError, ValueError):
                continue
            if target_id == "left-panel":
                widget.styles.width = value
            elif target_id == "file-table":
                widget.styles.height = value

    def _save_pane_size(self, target_id: str, size: int) -> None:
        """Schreibt eine einzelne Panel-Groesse in die Settings."""
        settings = self._settings_store.load()
        sizes = settings.get("pane_sizes", {})
        if not isinstance(sizes, dict):
            sizes = {}
        sizes[target_id] = int(size)
        settings["pane_sizes"] = sizes
        self._settings_store.save(settings)

    def on_vertical_splitter_resized(
        self,
        event: VerticalSplitter.Resized,
    ) -> None:
        """Vertikaler Splitter wurde geloest — neue Breite persistieren."""
        self._save_pane_size(event.target_id, event.size)

    def on_horizontal_splitter_resized(
        self,
        event: HorizontalSplitter.Resized,
    ) -> None:
        """Horizontaler Splitter wurde geloest — neue Hoehe persistieren.

        Der Log-Splitter (target main-container) wird NICHT persistiert: das
        Log-Panel ist beim Start ausgeblendet, eine konkrete main-container-
        Hoehe wuerde dann einen leeren Streifen hinterlassen.
        """
        if event.target_id == "file-table":
            self._save_pane_size(event.target_id, event.size)

    def on_visualizer_mode_change_requested(
        self,
        event: Visualizer.ModeChangeRequested,
    ) -> None:
        """Visualizer-Modus per Kontextmenue gewechselt — anwenden + persistieren."""
        settings = self._settings_store.load()
        if settings.get("visualizer_mode") == event.mode.value:
            return  # Kein Change → kein unnoetiger Disk-Write
        settings["visualizer_mode"] = event.mode.value
        self._settings_store.save(settings)
        self.query_one("#visualizer", Visualizer).set_mode(event.mode)
        self.notify(
            t("notify.visualizer_mode", name=t(f"visualizer.mode_{event.mode.value}")),
            severity="information",
            timeout=2,
        )

    def _sync_visualizer(self) -> None:
        """Synchronisiert Visualizer mit Player-State."""
        vis = self.query_one("#visualizer", Visualizer)
        if self._player_service.state.is_playing:
            track = self._player_service.state.current_track
            if track:
                self._load_spectrum(track.path)
                vis.set_spectrum_source(
                    lambda: self._spectrum_analyzer.get_bands(self._player_service.state.position_seconds)
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
        """Transport-Leiste und Control-Panel mit aktuellem State aktualisieren."""
        transport = self.query_one("#transport", TransportBar)
        transport.update_state(self._player_service.state)
        self._update_control_panel()

    def _update_control_panel(self) -> None:
        """Control-Panel mit aktuellem State aktualisieren."""
        try:
            panel = self.query_one("#control-panel", ControlPanel)
        except Exception:
            return
        state = self._player_service.state
        track = state.current_track
        is_fav = self._playlist_service.is_favorite(track.path) if track else False
        panel.update_state(
            is_playing=state.is_playing,
            is_paused=state.is_paused,
            shuffle_on=self._shuffle_mode,
            repeat_mode=self._repeat_mode,
            is_favorite=is_fav,
            has_track=track is not None,
        )

    def _on_playback_error(self, error: str) -> None:
        """Callback bei Playback-Fehlern."""
        self._write_log(f"[bold red]{error}[/bold red]")
        self.notify(error, severity="warning", timeout=8)

    def _on_track_started(self, track: AudioTrack) -> None:
        """Callback wenn ein Track startet — Verlauf schreiben (wenn aktiviert)."""
        try:
            self._history_service.record_play(track.path)
        except Exception:
            logger.debug("Verlauf konnte nicht aktualisiert werden", exc_info=True)

    def _on_track_finished(self) -> None:
        """Callback wenn ein Track fertig ist."""
        state = self._player_service.state
        finished_track = state.current_track
        if finished_track:
            self._write_log(t("log.track_finished", name=finished_track.display_name))
        else:
            self._write_log(t("log.track_finished_unknown"))

        # Repeat One: gleichen Track nochmal abspielen
        if self._repeat_mode == RepeatMode.ONE and finished_track:
            self._play_track(finished_track)
            self._sync_visualizer()
            self._update_transport()
            return

        # Shuffle: zufaelligen naechsten Track waehlen
        if self._shuffle_mode:
            next_track = self._pick_shuffle_next()
            if next_track:
                self._play_track(next_track)
                self._write_log(t("log.shuffle_play", name=next_track.display_name))
            elif self._repeat_mode == RepeatMode.ALL:
                # Shuffle + Repeat All: History zuruecksetzen, neuer Durchlauf
                self._shuffle_history.clear()
                next_track = self._pick_shuffle_next()
                if next_track:
                    self._play_track(next_track)
                    self._write_log(t("log.shuffle_play", name=next_track.display_name))
            else:
                self._write_log(t("log.shuffle_all_played"))
                self.sub_title = self._idle_subtitle()
                self._clear_all_tabs()
                self._lyrics_generation += 1
            self._sync_visualizer()
            self._update_transport()
            return

        # Normal: sequenziell naechsten Track
        if state.has_next:
            self._player_service.next_track()
        elif self._repeat_mode == RepeatMode.ALL and state.track_list:
            # Repeat All: zurueck zum ersten Track
            self._player_service.play_track(0)
        else:
            # Kein naechster Track, kein Repeat
            self._player_service.state.state = PlaybackState.STOPPED

        self._sync_visualizer()
        if self._player_service.state.is_stopped:
            self.sub_title = self._idle_subtitle()
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
                next_name = f"{track.artist} – {track.title}" if track.artist and track.title else track.display_name
                self._write_log(t("log.play", name=f"{next_name} ({track.path.parent})"))
                self._load_tabs_for_track(track)
        self._update_transport()

    def _restore_session(self) -> None:
        """Stellt den letzten Track nach einem Crash wieder her (ohne Auto-Play)."""
        session = load_session()
        if not session:
            return

        track_path = Path(str(session.get("track_path", "")))
        if not track_path.is_file():
            clear_session()
            return

        position = float(session.get("position_seconds", 0.0))
        track = self._metadata_service.read_track(track_path)

        # Ordner laden und Baum aufklappen
        parent = track_path.parent
        self._scan_directory(parent)
        self._save_last_path(parent)

        # Track in UI anzeigen (NICHT abspielen)
        self.sub_title = track.display_name
        self._load_tabs_for_track(track)
        self._highlight_current_track()

        # Notification
        self.notify(
            t("notify.session_restored", name=track.display_name),
            timeout=5,
        )
        self._write_log(
            t("log.session_restored", name=track.display_name, pos=int(position)),
        )

        # Session aufraemen (einmalig restauriert)
        clear_session()

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

    def watch_theme(self, theme_name: str) -> None:
        """Persistiert jede Theme-Aenderung und aktualisiert die Titelzeile.

        Wenn gerade kein Track laeuft, zeigt sub_title den Theme-Namen
        an (Idle-Anzeige). Bei laufendem Track bleibt der Track-Name
        stehen — die Notification beim Theme-Wechsel reicht hier.
        """
        if not hasattr(self, "_settings_store"):
            return
        settings = self._settings_store.load()
        if settings.get("theme") != theme_name:
            settings["theme"] = theme_name
            self._settings_store.save(settings)
        # Idle-Anzeige aktualisieren wenn kein Track aktiv
        if not hasattr(self, "_player_service"):
            return
        if self._player_service.state.current_track is None:
            self.sub_title = self._idle_subtitle(theme_name)

    def watch_sub_title(self, sub_title: str) -> None:
        """Spiegelt den sub_title in den Terminal-Tab-Titel.

        Textual ruft watch_sub_title bei jeder Aenderung des sub_title-
        Reactives auf. Laeuft ein Track, zeigt der Tab dessen Namen, sonst
        die Versionsnummer.
        """
        if not hasattr(self, "_player_service"):
            return
        track = self._player_service.state.current_track
        if track is not None:
            set_terminal_title(f"♬ retro-amp - {track.display_name}")
        else:
            set_terminal_title(f"♬ retro-amp v{__version__}")

    def _idle_subtitle(self, theme_name: str | None = None) -> str:
        """Liefert den Idle-sub_title (Theme-Anzeige, kein Track aktiv)."""
        name = theme_name if theme_name is not None else self.theme
        display = THEME_DISPLAY_NAMES.get(name, name)
        return f"♪ {display}"

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
                artist,
                title,
            )
            self._fetch_lyrics_async(artist, title, generation)

            # Info (Wikipedia) laden
            self.query_one("#info-panel", InfoPanel).show_loading(artist)
            self._fetch_and_show_info(artist)

            # YouTube-Links
            self.query_one("#youtube-panel", YoutubePanel).show_links(artist, title)

        # Cover-Art (unabhaengig von Artist — direkt aus Datei)
        self.query_one("#cover-panel", CoverArtPanel).show_loading(
            artist or track.path.parent.name,
            title,
        )
        self._fetch_cover_art_async(track, artist or track.path.parent.name, title)

        # Details-Panel: NUR anmelden — Laden erst beim Tab-Aktivieren.
        details_panel = self.query_one("#details-panel", DetailsPanel)
        details_panel.set_pending(track.path)
        if self._is_details_tab_active():
            self._trigger_details_load(track.path)

        if not artist:
            # Nur die artist-abhaengigen Tabs leeren — Cover + Details laufen
            # auch ohne Artist (Datei-/Embed-Info).
            self.query_one("#lyrics-panel", LyricsPanel).clear()
            self.query_one("#translation-panel", TranslationPanel).clear()
            self.query_one("#info-panel", InfoPanel).clear()
            self.query_one("#youtube-panel", YoutubePanel).clear()

    def _clear_all_tabs(self) -> None:
        """Leert alle Tab-Panels."""
        self.query_one("#lyrics-panel", LyricsPanel).clear()
        self.query_one("#translation-panel", TranslationPanel).clear()
        self.query_one("#info-panel", InfoPanel).clear()
        self.query_one("#cover-panel", CoverArtPanel).clear()
        self.query_one("#youtube-panel", YoutubePanel).clear()
        self.query_one("#details-panel", DetailsPanel).show_no_track()
        self._details_generation += 1

    def _is_details_tab_active(self) -> bool:
        """True wenn der Details-Tab gerade sichtbar ist."""
        try:
            tabs = self.query_one("#content-tabs", TabbedContent)
            return tabs.active == "tab-details"
        except Exception:
            return False

    def _trigger_details_load(self, path: Path) -> None:
        """Startet (falls noetig) den Details-Worker fuer den uebergebenen Track."""
        panel = self.query_one("#details-panel", DetailsPanel)
        if not panel.is_load_needed():
            return
        self._details_generation += 1
        generation = self._details_generation
        panel.show_loading(path)
        self._load_details_async(path, generation)

    @work(exclusive=True, group="details", thread=True)
    def _load_details_async(self, path: Path, generation: int) -> None:
        """Liest Details im Background-Thread (mutagen ist blocking)."""
        result = self._details_service.read_details(path)
        if generation != self._details_generation:
            return
        self.call_from_thread(self._apply_details, path, result, generation)

    def _apply_details(
        self,
        path: Path,
        result: DetailsResult,
        generation: int,
    ) -> None:
        """Schreibt das Details-Ergebnis ins Panel (Main-Thread)."""
        if generation != self._details_generation:
            return
        self.query_one("#details-panel", DetailsPanel).show_details(path, result)

    @work(exclusive=True, group="lyrics", thread=True)
    def _fetch_lyrics_async(
        self,
        artist: str,
        title: str,
        generation: int,
    ) -> None:
        """Holt Lyrics im Background-Thread."""
        original, translated, synced_lines = self._lyrics_service.get_lyrics(
            artist,
            title,
        )

        if generation != self._lyrics_generation:
            return

        self.call_from_thread(
            self._apply_lyrics,
            artist,
            title,
            original,
            translated,
            synced_lines,
            generation,
        )

    def _apply_lyrics(
        self,
        artist: str,
        title: str,
        original: str,
        translated: str,
        synced_lines: list[tuple[float, str]],
        generation: int,
    ) -> None:
        """Wendet Lyrics auf die UI an (Main-Thread)."""
        if generation != self._lyrics_generation:
            return

        self.query_one("#lyrics-panel", LyricsPanel).show_lyrics(
            artist,
            title,
            original,
            synced_lines,
        )
        self.query_one("#translation-panel", TranslationPanel).show_translation(
            artist,
            title,
            translated,
        )

    @work(exclusive=True, group="cover", thread=True)
    def _fetch_cover_art_async(
        self,
        track: AudioTrack,
        artist: str,
        title: str,
    ) -> None:
        """Extrahiert Cover-Art im Background-Thread."""
        image_data = self._metadata_reader.extract_cover_art(track.path)
        self.call_from_thread(
            self._apply_cover_art,
            artist,
            title,
            image_data,
        )

    def _apply_cover_art(
        self,
        artist: str,
        title: str,
        image_data: bytes | None,
    ) -> None:
        """Zeigt Cover-Art in der UI an (Main-Thread)."""
        self._last_cover = (artist, title, image_data)
        self.query_one("#cover-panel", CoverArtPanel).show_cover(
            artist,
            title,
            image_data,
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

    def _refresh_history_tree(self) -> None:
        """Aktualisiert den Verlauf-Baum mit aktuellen Daten."""
        history_tree = self.query_one("#history-tree", HistoryTree)
        enabled = self._database.get_bool_setting("history_enabled", False)
        groups = self._history_service.list_grouped() if enabled else []
        history_tree.load_groups(groups, enabled)

    def _write_log(self, message: str) -> None:
        """Schreibt eine Nachricht ins Debug-Log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        try:
            log_widget = self.query_one("#app-log", RichLog)
            log_widget.write(f"[dim]{timestamp}[/dim] {message}")
            self._log_lines.append(f"{timestamp} {message}")
        except Exception:
            pass

    def _lyrics_log_from_thread(self, message: str) -> None:
        """Routet Log-Nachrichten des LyricsService ins LogPanel.

        Kann sowohl aus dem Main-Thread (Cache-Invalidate via Click)
        als auch aus einem Worker-Thread (Lyrics-Fetch) aufgerufen werden.
        """
        import threading

        if threading.current_thread() is threading.main_thread():
            self._write_log(message)
            return
        with contextlib.suppress(Exception):
            self.call_from_thread(self._write_log, message)

    def on_unmount(self) -> None:
        """Cleanup beim Beenden."""
        self._lyrics_generation += 1  # Offene Lyrics-Threads ignorieren
        self._spectrum_analyzer.unload()
        self._audio_player.cleanup()
        with contextlib.suppress(Exception):
            self._database.close()
        clear_session()  # Sauberer Exit → Session loeschen
        release_lock()
