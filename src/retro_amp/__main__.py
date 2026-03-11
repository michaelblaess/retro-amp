"""Haupteinstiegspunkt fuer retro-amp."""
from __future__ import annotations

import argparse
import sys

from retro_amp import __version__
from retro_amp.i18n import load_locale, t, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
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
        help="Start directory for the music browser",
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

    from retro_amp.app import RetroAmpApp
    app = RetroAmpApp(start_path=args.path)
    app.run()


if __name__ == "__main__":
    main()
