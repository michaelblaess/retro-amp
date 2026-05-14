"""Haupteinstiegspunkt fuer retro-amp."""

from __future__ import annotations

import argparse
import os
import sys

from retro_amp import __version__
from retro_amp.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, load_locale
from retro_amp.infrastructure.settings import JsonSettingsStore


def main() -> None:
    """CLI Entry Point."""
    # Settings vorab laden um gespeicherte Sprache zu kennen
    settings_store = JsonSettingsStore()
    settings = settings_store.load()
    saved_lang = str(settings.get("language", DEFAULT_LANGUAGE))

    parser = argparse.ArgumentParser(
        description="retro-amp — Terminal music player with retro charm",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"retro-amp {__version__}",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="",
        help="Music directory or audio file to play",
    )
    parser.add_argument(
        "--lang",
        default=saved_lang,
        choices=SUPPORTED_LANGUAGES,
        help=f"Language ({', '.join(SUPPORTED_LANGUAGES)})",
    )

    args = parser.parse_args()

    # Sprache laden (CLI > Settings > Default)
    lang = args.lang
    load_locale(lang)

    # Sprache persistent speichern wenn per CLI geaendert
    if lang != saved_lang:
        settings["language"] = lang
        settings_store.save(settings)

    # Pruefen ob der Pfad eine Datei ist (z.B. Doppelklick auf MP3)
    start_path = args.path
    play_file = ""
    if start_path and os.path.isfile(start_path):
        play_file = start_path
        start_path = ""

    # Single-Instance: Datei an laufende Instanz senden
    if play_file:
        from retro_amp.infrastructure.single_instance import send_play_request

        if send_play_request(os.path.abspath(play_file)):
            sys.exit(0)

    # Grafik-Backend BEVOR Textual stdin kapert initialisieren, sonst
    # bleeden DA1/Cell-Size-Query-Antworten von textual-image in Input-Widgets.
    if str(settings.get("cover_renderer", "halfblock")) == "graphics":
        _preinit_graphics_backend()

    from retro_amp.app import RetroAmpApp

    app = RetroAmpApp(start_path=start_path, play_file=play_file)
    app.run()


def _preinit_graphics_backend() -> None:
    """Eager-Import der textual-image Widgets und Cell-Size-Query.

    textual-image sendet beim Import DA1- und Cell-Size-Escape-Sequenzen an
    das Terminal. Wenn das nach `App.run()` passiert, landen die Antworten
    als Muell in der Textual-Eingabe. Darum: vor dem App-Start einmal
    anstossen und die Queries abarbeiten lassen.
    """
    try:
        import textual_image.renderable  # noqa: F401
        import textual_image.widget  # noqa: F401
        from textual_image._terminal import get_cell_size

        get_cell_size()
    except Exception:
        pass


if __name__ == "__main__":
    main()
