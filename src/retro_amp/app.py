"""retro-amp — Textual App (Composition Root)."""
from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header

from . import __version__
from .domain.models import AudioTrack, PlaybackState
from .infrastructure.audio_player import PygameAudioPlayer
from .infrastructure.metadata_reader import MutagenMetadataReader
from .infrastructure.settings import JsonSettingsStore
from .services.metadata_service import MetadataService
from .services.player_service import PlayerService
from .widgets.file_table import FileTable
from .widgets.folder_browser import FolderBrowser
from .widgets.transport_bar import TransportBar
from .widgets.visualizer import Visualizer


class RetroAmpApp(App):
    """retro-amp — Terminal-Musikplayer mit Retro-Charme."""

    CSS_PATH = "app.tcss"
    TITLE = f"retro-amp v{__version__}"

    BINDINGS = [
        Binding("q", "quit", "Beenden"),
        Binding("space", "toggle_pause", "Play/Pause"),
        Binding("n", "next_track", "Naechster", show=False),
        Binding("b", "previous_track", "Vorheriger", show=False),
        Binding("plus,equal", "volume_up", "Vol +", show=False),
        Binding("minus", "volume_down", "Vol -", show=False),
    ]

    def __init__(self, start_path: str = "") -> None:
        super().__init__()

        # Infrastructure (Composition Root — hier wird verdrahtet)
        self._audio_player = PygameAudioPlayer()
        self._metadata_reader = MutagenMetadataReader()
        self._settings_store = JsonSettingsStore()

        # Services
        self._player_service = PlayerService(self._audio_player)
        self._metadata_service = MetadataService(self._metadata_reader)

        # Settings laden
        settings = self._settings_store.load()
        self._player_service.set_volume(float(settings.get("volume", 0.8)))

        # Startpfad bestimmen
        if start_path:
            self._start_path = Path(start_path).expanduser().resolve()
        elif settings.get("last_path"):
            self._start_path = Path(str(settings["last_path"]))
        else:
            self._start_path = Path.home() / "Music"

        if not self._start_path.is_dir():
            self._start_path = Path.home()

        # Timer-Handle fuer Position-Updates
        self._position_timer: object | None = None

        # Aktuelle Tracks im rechten Panel
        self._current_tracks: list[AudioTrack] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            with Vertical(id="left-panel"):
                yield FolderBrowser(str(self._start_path), id="folder-browser")
            with Vertical(id="right-panel"):
                yield FileTable(id="file-table")
        yield Visualizer(id="visualizer")
        yield TransportBar(id="transport")
        yield Footer()

    def on_mount(self) -> None:
        """App ist bereit — Timer starten, Callbacks setzen."""
        self._position_timer = self.set_interval(0.5, self._tick_position)
        self._player_service.set_callbacks(
            on_finished=self._on_track_finished,
        )
        # Initial: Startverzeichnis scannen
        self._scan_directory(self._start_path)

    # --- Event-Handler fuer Widget-Messages ---

    def on_folder_browser_directory_selected(
        self, event: FolderBrowser.DirectorySelected
    ) -> None:
        """Ordner im Baum ausgewaehlt — rechtes Panel aktualisieren."""
        self._scan_directory(event.path)
        self._save_last_path(event.path)

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
            self.query_one("#visualizer", Visualizer).start()
        else:
            self._player_service.toggle_pause()
            if state.is_paused:
                self.query_one("#visualizer", Visualizer).stop()
            else:
                self.query_one("#visualizer", Visualizer).start()
        self._update_transport()

    def action_next_track(self) -> None:
        """Naechster Track."""
        self._player_service.next_track()
        self._update_transport()

    def action_previous_track(self) -> None:
        """Vorheriger Track."""
        self._player_service.previous_track()
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

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Bindings bedingt ein-/ausblenden."""
        state = self._player_service.state
        if action == "next_track":
            return True if state.has_next else None
        if action == "previous_track":
            return True if state.has_previous else None
        if action == "toggle_pause":
            return True
        return True

    # --- Interne Methoden ---

    def _scan_directory(self, directory: Path) -> None:
        """Scannt ein Verzeichnis und zeigt Dateien in der Tabelle."""
        self._current_tracks = self._metadata_service.scan_directory(directory)
        file_table = self.query_one("#file-table", FileTable)
        file_table.update_tracks(self._current_tracks)

    def _play_track(self, track: AudioTrack) -> None:
        """Spielt einen Track ab und aktualisiert UI."""
        # Tracklist laden falls noetig
        if track in self._current_tracks:
            idx = self._current_tracks.index(track)
            self._player_service.load_tracks(self._current_tracks)
            self._player_service.play_track(idx)
        else:
            self._player_service.play_file(track)

        self.query_one("#visualizer", Visualizer).start()
        self._update_transport()

    def _tick_position(self) -> None:
        """Timer-Callback: Position aktualisieren."""
        self._player_service.update_position()
        self._update_transport()

    def _update_transport(self) -> None:
        """Transport-Leiste mit aktuellem State aktualisieren."""
        transport = self.query_one("#transport", TransportBar)
        transport.update_state(self._player_service.state)

    def _on_track_finished(self) -> None:
        """Callback wenn ein Track fertig ist."""
        self._player_service.check_auto_next()
        if self._player_service.state.is_stopped:
            self.query_one("#visualizer", Visualizer).stop()
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

    def on_unmount(self) -> None:
        """Cleanup beim Beenden."""
        self._audio_player.cleanup()
