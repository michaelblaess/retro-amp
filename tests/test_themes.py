"""Tests fuer Retro-Themes Re-Export + Legacy-Slug-Migration."""
from __future__ import annotations

from retro_amp.themes import (
    DEFAULT_THEME,
    LEGACY_THEME_MAP,
    RETRO_THEMES,
    RETRO_THEME_NAMES,
    THEME_DISPLAY_NAMES,
    migrate_theme_name,
)


class TestThemes:
    def test_themes_present(self) -> None:
        assert len(RETRO_THEMES) > 0
        assert len(RETRO_THEME_NAMES) == len(RETRO_THEMES)

    def test_default_theme_is_registered(self) -> None:
        assert DEFAULT_THEME in RETRO_THEME_NAMES

    def test_display_names_for_all(self) -> None:
        for name in RETRO_THEME_NAMES:
            assert name in THEME_DISPLAY_NAMES

    def test_themes_have_unique_backgrounds(self) -> None:
        backgrounds = [t.background for t in RETRO_THEMES]
        assert len(set(backgrounds)) == len(RETRO_THEMES)

    def test_at_least_one_dark_and_one_light(self) -> None:
        dark = [t for t in RETRO_THEMES if t.dark]
        light = [t for t in RETRO_THEMES if not t.dark]
        assert len(dark) >= 1
        assert len(light) >= 1


class TestLegacyMigration:
    def test_current_slug_passes_through(self) -> None:
        assert migrate_theme_name(DEFAULT_THEME) == DEFAULT_THEME

    def test_old_c64_maps_to_brotkasten(self) -> None:
        assert migrate_theme_name("c64") == "brotkasten"

    def test_old_amiga_maps_to_boing(self) -> None:
        assert migrate_theme_name("amiga") == "boing"

    def test_old_ibm_terminal_maps_to_classic_terminal(self) -> None:
        assert migrate_theme_name("ibm-terminal") == "classic-terminal"

    def test_unknown_slug_passes_through(self) -> None:
        # Caller entscheidet ueber Fallback — Migration gibt Input zurueck
        assert migrate_theme_name("not-a-theme") == "not-a-theme"

    def test_all_legacy_targets_are_valid(self) -> None:
        for old, new in LEGACY_THEME_MAP.items():
            assert new in RETRO_THEME_NAMES, (
                f"Legacy mapping {old!r} -> {new!r}: target not registered"
            )

    def test_legacy_keys_disjoint_from_current_slugs(self) -> None:
        # Alte Slugs sollten nicht (mehr) in der aktuellen Liste sein —
        # sonst wuerde migrate_theme_name sie unveraendert durchlassen.
        overlap = set(LEGACY_THEME_MAP.keys()) & set(RETRO_THEME_NAMES)
        assert not overlap, f"Legacy slugs still active: {overlap}"
