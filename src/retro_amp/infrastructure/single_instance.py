"""Single-Instance-Mechanismus via Lock-Datei und Play-Request-Datei.

Verhindert mehrere gleichzeitige Instanzen von retro-amp.
Neue Instanzen schreiben den Dateipfad in eine Request-Datei,
die laufende Instanz prueft diese periodisch per Timer.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_LOCK_DIR = Path.home() / ".retro-amp"
_LOCK_FILE = _LOCK_DIR / "instance.lock"
_PLAY_REQUEST = _LOCK_DIR / "play_request"


def _is_process_alive(pid: int) -> bool:
    """Prueft ob ein Prozess mit der gegebenen PID noch laeuft."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        # Windows: OpenProcess allein reicht nicht — gibt auch fuer beendete
        # Prozesse ein Handle zurueck wenn das Kernel-Objekt noch existiert.
        # WaitForSingleObject(handle, 0) ist zuverlaessig:
        # WAIT_TIMEOUT (258) = Prozess laeuft, WAIT_OBJECT_0 (0) = beendet.
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        SYNCHRONIZE = 0x00100000
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            return False
        WAIT_TIMEOUT = 258
        result = kernel32.WaitForSingleObject(handle, 0)
        kernel32.CloseHandle(handle)
        return result == WAIT_TIMEOUT
    # Unix: Signal 0 prueft nur ob der Prozess existiert
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except (ProcessLookupError, OSError):
        return False


def is_already_running() -> bool:
    """Prueft ob eine Instanz laeuft (Lock-Datei + PID-Check)."""
    if not _LOCK_FILE.is_file():
        return False
    try:
        pid = int(_LOCK_FILE.read_text(encoding="utf-8").strip())
        return _is_process_alive(pid)
    except (ValueError, OSError):
        return False


def send_play_request(file_path: str) -> bool:
    """Schreibt einen Play-Request fuer die laufende Instanz.

    Returns True wenn eine Instanz laeuft und der Request geschrieben wurde.
    """
    if not is_already_running():
        return False
    try:
        _LOCK_DIR.mkdir(parents=True, exist_ok=True)
        _PLAY_REQUEST.write_text(file_path, encoding="utf-8")
        return True
    except OSError:
        return False


def acquire_lock() -> None:
    """Schreibt die Lock-Datei mit der aktuellen PID.

    Registriert atexit-Handler als Fallback, falls on_unmount
    nicht aufgerufen wird (z.B. Terminal geschlossen).
    """
    import atexit
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    _LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    atexit.register(release_lock)


def release_lock() -> None:
    """Entfernt Lock-Datei und ggf. offene Play-Requests."""
    for f in (_LOCK_FILE, _PLAY_REQUEST):
        try:
            f.unlink()
        except OSError:
            pass


def read_play_request() -> str | None:
    """Liest und loescht einen Play-Request.

    Returns den Dateipfad oder None wenn kein Request vorhanden.
    """
    if not _PLAY_REQUEST.is_file():
        return None
    try:
        path = _PLAY_REQUEST.read_text(encoding="utf-8").strip()
        _PLAY_REQUEST.unlink()
        return path if path else None
    except OSError:
        return None
