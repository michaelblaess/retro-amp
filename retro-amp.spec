# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller Spec fuer retro-amp.

Baut eine Standalone-EXE (--onedir) mit allen Abhaengigkeiten.
pygame-Binaries und Textual/Rich werden eingebettet.

Ausfuehren: pyinstaller retro-amp.spec --noconfirm
"""

import os

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

src_pkg = os.path.join("src", "retro_amp")

a = Analysis(
    [os.path.join(src_pkg, "__main__.py")],
    pathex=["src"],
    binaries=[],
    datas=[
        # App TCSS
        (os.path.join(src_pkg, "app.tcss"), "retro_amp"),
    ],
    hiddenimports=[
        "retro_amp",
        "retro_amp.__main__",
        "retro_amp.app",
        "retro_amp.themes",
        # Domain
        "retro_amp.domain",
        "retro_amp.domain.models",
        "retro_amp.domain.protocols",
        # Services
        "retro_amp.services",
        "retro_amp.services.player_service",
        "retro_amp.services.playlist_service",
        "retro_amp.services.metadata_service",
        # Infrastructure
        "retro_amp.infrastructure",
        "retro_amp.infrastructure.audio_player",
        "retro_amp.infrastructure.metadata_reader",
        "retro_amp.infrastructure.playlist_store",
        "retro_amp.infrastructure.settings",
        "retro_amp.infrastructure.spectrum",
        # Widgets
        "retro_amp.widgets",
        "retro_amp.widgets.file_table",
        "retro_amp.widgets.folder_browser",
        "retro_amp.widgets.transport_bar",
        "retro_amp.widgets.visualizer",
        # Screens
        "retro_amp.screens",
        "retro_amp.screens.confirm_screen",
        "retro_amp.screens.playlist_screen",
        "retro_amp.screens.rename_screen",
        # Textual
        "textual",
        "textual.app",
        "textual.widgets",
        "textual.widgets._data_table",
        "textual.widgets._header",
        "textual.widgets._footer",
        "textual.widgets._input",
        "textual.widgets._static",
        "textual.widgets._tree",
        "textual.widgets._directory_tree",
        "textual.containers",
        "textual.screen",
        "textual.binding",
        "textual.css",
        "textual.css.query",
        "textual._xterm_parser",
        "textual._win_sleep",
        # Rich
        "rich",
        "rich.text",
        "rich.markup",
        "rich.highlighter",
    ] + collect_submodules("rich._unicode_data") + [
        # Textual Themes
        "textual_themes",
        # Pydantic
        "pydantic",
        # Pygame
        "pygame",
        "pygame.mixer",
        # Mutagen
        "mutagen",
        "mutagen.mp3",
        "mutagen.ogg",
        "mutagen.flac",
        "mutagen.wave",
        "mutagen.id3",
    ] + collect_submodules("mutagen"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pydoc",
        "doctest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="retro-amp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="retro-amp",
)
