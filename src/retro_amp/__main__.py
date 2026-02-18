"""Haupteinstiegspunkt fuer retro-amp."""
from __future__ import annotations

import argparse
import sys

from retro_amp import __version__
from retro_amp.app import RetroAmpApp


def main() -> None:
    """CLI Entry Point."""
    parser = argparse.ArgumentParser(
        description="retro-amp — Terminal-Musikplayer mit Retro-Charme",
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
        help="Startverzeichnis fuer den Musik-Browser",
    )

    args = parser.parse_args()
    app = RetroAmpApp(start_path=args.path)
    app.run()


if __name__ == "__main__":
    main()
