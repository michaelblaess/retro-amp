"""Der einklappbare Schnellzugriff im Dateien-Tab."""

from __future__ import annotations

import json
from pathlib import Path

from retro_amp.app import RetroAmpApp
from retro_amp.widgets.folder_browser import FolderBrowser
from retro_amp.widgets.quick_jump_sidebar import QuickJumpHeader, QuickJumpSidebar


def _gespeichert(ablage: Path) -> object:
    datei = ablage / ".retro-amp" / "settings.json"
    return json.loads(datei.read_text(encoding="utf-8")).get("quick_jump_collapsed")


class TestSchnellzugriff:
    async def test_startet_eingeklappt(self, isolierte_ablage: Path) -> None:
        anwendung = RetroAmpApp()
        async with anwendung.run_test():
            assert not anwendung.query_one("#quick-jump", QuickJumpSidebar).display
            assert not anwendung.query_one("#quick-jump-splitter").display
            assert "▸" in str(anwendung.query_one("#quick-jump-header", QuickJumpHeader).render())

    async def test_klick_klappt_auf_und_merkt_es(self, isolierte_ablage: Path) -> None:
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            await pilot.click("#quick-jump-header")
            await pilot.pause()
            assert anwendung.query_one("#quick-jump", QuickJumpSidebar).display
            assert anwendung.query_one("#quick-jump-splitter").display
            assert "▾" in str(anwendung.query_one("#quick-jump-header", QuickJumpHeader).render())
            assert _gespeichert(isolierte_ablage) is False

        # Neuer Start liest den gemerkten Zustand.
        anwendung = RetroAmpApp()
        async with anwendung.run_test():
            assert anwendung.query_one("#quick-jump", QuickJumpSidebar).display

    async def test_taste_schaltet_um(self, isolierte_ablage: Path) -> None:
        anwendung = RetroAmpApp()
        async with anwendung.run_test() as pilot:
            anwendung.query_one("#folder-browser", FolderBrowser).focus()
            await pilot.press("o")
            await pilot.pause()
            assert anwendung.query_one("#quick-jump", QuickJumpSidebar).display
            await pilot.press("o")
            await pilot.pause()
            assert not anwendung.query_one("#quick-jump", QuickJumpSidebar).display
            assert _gespeichert(isolierte_ablage) is True
