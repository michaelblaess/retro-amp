"""Tests fuer die erweiterte Flaechenpalette.

Die drei Pruefungen, die wirklich etwas finden koennen, sind:

- `TestKontrast`      - eine abgeleitete Farbe ist auf ihrem Untergrund unlesbar
- `TestUnterscheidbar`- zwei Pegelstufen fallen im Bild zusammen
- `TestOhneTextual`   - das Palettenmodul hat sich an die Oberflaeche gebunden

Vollstaendigkeit selbst wird nicht zur Laufzeit geprueft, sondern vom Typ
garantiert: eine `SurfacePalette` ohne Feld gibt es nicht.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import fields

import pytest

from retro_amp.palette import (
    COLOR_FIELDS,
    OPACITY_FIELDS,
    OVERRIDES,
    PaletteOverride,
    SurfacePalette,
    blend,
    contrast_ratio,
    gradient,
    palette_for,
    relative_luminance,
)
from retro_amp.themes import RETRO_THEMES, base_palette, surface_palette

ALLE_PALETTEN: list[tuple[str, SurfacePalette]] = [
    (theme.name, palette_for(base_palette(theme))) for theme in RETRO_THEMES
]


class TestFarbrechnung:
    """Die Grundrechenarten zuerst - darauf steht alles andere."""

    def test_blend_endpunkte(self) -> None:
        assert blend("#000000", "#FFFFFF", 0.0) == "#000000"
        assert blend("#000000", "#FFFFFF", 1.0) == "#FFFFFF"
        assert blend("#000000", "#FFFFFF", 0.5) == "#808080"

    def test_blend_begrenzt_den_anteil(self) -> None:
        assert blend("#000000", "#FFFFFF", 5.0) == "#FFFFFF"
        assert blend("#000000", "#FFFFFF", -3.0) == "#000000"

    def test_ungueltiger_wert_faellt_auf(self) -> None:
        with pytest.raises(ValueError, match="RRGGBB"):
            blend("rot", "#FFFFFF", 0.5)

    def test_luminanz_gegen_bekannte_werte(self) -> None:
        # WCAG-Referenz: Schwarz 0.0, Weiss 1.0, reines Gruen 0.7152.
        assert relative_luminance("#000000") == pytest.approx(0.0)
        assert relative_luminance("#FFFFFF") == pytest.approx(1.0)
        assert relative_luminance("#00FF00") == pytest.approx(0.7152, abs=1e-4)

    def test_kontrast_gegen_bekannte_werte(self) -> None:
        # Schwarz auf Weiss ist der Hoechstwert 21:1, gleiche Farbe ergibt 1:1.
        assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0, abs=1e-6)
        assert contrast_ratio("#123456", "#123456") == pytest.approx(1.0)


class TestVerlauf:
    def test_endpunkte_sind_die_stuetzstellen(self) -> None:
        werte = gradient(("#000000", "#808080", "#FFFFFF"), 5)
        assert werte[0] == "#000000"
        assert werte[-1] == "#FFFFFF"
        assert werte[2] == "#808080"

    def test_laenge_stimmt(self) -> None:
        for anzahl in (1, 2, 3, 32, 33):
            assert len(gradient(("#000000", "#FFFFFF"), anzahl)) == anzahl

    def test_verlauf_ist_monoton(self) -> None:
        # Von Schwarz nach Weiss muss die Helligkeit durchgehend steigen.
        werte = gradient(("#000000", "#FFFFFF"), 16)
        helligkeiten = [relative_luminance(w) for w in werte]
        assert helligkeiten == sorted(helligkeiten)

    def test_eine_stuetzstelle_wiederholt_sich(self) -> None:
        assert gradient(("#123456",), 3) == ["#123456"] * 3

    def test_leere_anforderung_ist_leer(self) -> None:
        assert gradient(("#000000", "#FFFFFF"), 0) == []

    def test_ohne_stuetzstelle_faellt_es_auf(self) -> None:
        with pytest.raises(ValueError, match="Stuetzstelle"):
            gradient((), 4)


class TestVollstaendigkeit:
    def test_jedes_theme_liefert_eine_palette(self) -> None:
        assert len(ALLE_PALETTEN) == len(RETRO_THEMES)
        assert len(ALLE_PALETTEN) > 0

    def test_alle_farbfelder_sind_hexwerte(self) -> None:
        fehler: list[str] = []
        for name, palette in ALLE_PALETTEN:
            for feld in COLOR_FIELDS:
                wert = getattr(palette, feld)
                if not (isinstance(wert, str) and len(wert) == 7 and wert.startswith("#")):
                    fehler.append(f"{name}.{feld} = {wert!r}")
                    continue
                int(wert[1:], 16)
        assert not fehler, "keine gueltigen #RRGGBB-Werte:\n" + "\n".join(fehler)

    def test_deckkraft_liegt_zwischen_null_und_eins(self) -> None:
        for name, palette in ALLE_PALETTEN:
            for feld in OPACITY_FIELDS:
                wert = getattr(palette, feld)
                assert isinstance(wert, float), f"{name}.{feld} ist kein float"
                assert 0.0 <= wert <= 1.0, f"{name}.{feld} = {wert}"

    def test_feldliste_deckt_die_dataclass_ab(self) -> None:
        # Ein neu ergaenztes Feld darf nicht stillschweigend durch alle
        # Pruefungen fallen, weil es in keiner der beiden Listen steht.
        alle = {f.name for f in fields(SurfacePalette)}
        assert set(COLOR_FIELDS) | set(OPACITY_FIELDS) == alle

    def test_ausnahmetyp_kennt_dieselben_felder(self) -> None:
        # PaletteOverride wiederholt die Feldliste von SurfacePalette. Waechst
        # die Dataclass, muss der Ausnahmetyp mitwachsen - sonst laesst sich
        # das neue Feld je Theme nicht uebersteuern, ohne dass es auffaellt.
        aus_typeddict = set(PaletteOverride.__annotations__)
        aus_dataclass = {f.name for f in fields(SurfacePalette)}
        assert aus_typeddict == aus_dataclass, (
            f"nur in PaletteOverride: {sorted(aus_typeddict - aus_dataclass)}, "
            f"nur in SurfacePalette: {sorted(aus_dataclass - aus_typeddict)}"
        )

    def test_ausnahmen_nennen_nur_echte_felder(self) -> None:
        bekannte_themes = {theme.name for theme in RETRO_THEMES}
        alle_felder = {f.name for f in fields(SurfacePalette)}
        for theme_name, ausnahmen in OVERRIDES.items():
            assert theme_name in bekannte_themes, f"Ausnahme fuer unbekanntes Theme: {theme_name}"
            unbekannt = set(ausnahmen) - alle_felder
            assert not unbekannt, f"{theme_name} nennt unbekannte Felder: {sorted(unbekannt)}"


class TestKontrast:
    """Kann scheitern - und soll es, wenn eine Ableitung unlesbar wird."""

    # 3.0:1 ist die WCAG-Schwelle fuer grosse Schrift und grafische Elemente.
    # Fuer eine LCD-Anzeige ist das die untere Grenze des Ertraeglichen.
    LCD_MINDESTKONTRAST = 3.0
    # Der Griff muss sich von seiner Rinne abheben, sonst sieht man ihn nicht.
    GRIFF_MINDESTKONTRAST = 1.6
    # Farbige Glyphen (Transporttasten, Wiedergabemarke) auf dem Grund.
    GLYPH_MINDESTKONTRAST = 3.0
    # Der gefuellte Teil der Positions- und Lautstaerkeleiste.
    BALKEN_MINDESTKONTRAST = 2.0

    def test_lcd_ist_lesbar(self) -> None:
        schwach = [
            f"{name}: {contrast_ratio(p.lcd_foreground, p.lcd_background):.2f}:1"
            for name, p in ALLE_PALETTEN
            if contrast_ratio(p.lcd_foreground, p.lcd_background) < self.LCD_MINDESTKONTRAST
        ]
        assert not schwach, f"LCD unter {self.LCD_MINDESTKONTRAST}:1 - Ausnahme in OVERRIDES eintragen:\n" + "\n".join(
            schwach
        )

    def test_griff_hebt_sich_von_der_rinne_ab(self) -> None:
        schwach = [
            f"{name}: {contrast_ratio(p.progress_handle, p.progress_trough):.2f}:1"
            for name, p in ALLE_PALETTEN
            if contrast_ratio(p.progress_handle, p.progress_trough) < self.GRIFF_MINDESTKONTRAST
        ]
        assert not schwach, f"Griff unter {self.GRIFF_MINDESTKONTRAST}:1 gegen die Rinne:\n" + "\n".join(schwach)

    def test_zustandsfarben_sind_auf_dem_grund_lesbar(self) -> None:
        # Transporttasten und Wiedergabemarke zeichnen ohne eigene Flaeche,
        # also auf dem Grund des Bildschirms. 3.0:1 ist die WCAG-Schwelle fuer
        # grosse Schrift und grafische Elemente.
        schwach: list[str] = []
        for name, palette in ALLE_PALETTEN:
            theme = next(t for t in RETRO_THEMES if t.name == name)
            grund = base_palette(theme).background
            for feld in ("accent_on", "accent_hold", "accent_hot"):
                wert = contrast_ratio(getattr(palette, feld), grund)
                if wert < self.GLYPH_MINDESTKONTRAST:
                    schwach.append(f"{name}.{feld}: {wert:.2f}:1")
        assert not schwach, f"Zustandsfarbe unter {self.GLYPH_MINDESTKONTRAST}:1 gegen den Grund:\n" + "\n".join(
            schwach
        )

    def test_gefuellter_balken_ist_auf_dem_grund_sichtbar(self) -> None:
        schwach: list[str] = []
        for name, palette in ALLE_PALETTEN:
            theme = next(t for t in RETRO_THEMES if t.name == name)
            grund = base_palette(theme).background
            wert = contrast_ratio(palette.progress_played, grund)
            if wert < self.BALKEN_MINDESTKONTRAST:
                schwach.append(f"{name}: {wert:.2f}:1")
        assert not schwach, f"Balken unter {self.BALKEN_MINDESTKONTRAST}:1 gegen den Grund:\n" + "\n".join(schwach)

    def test_laufschiene_ist_sichtbar_aber_leiser_als_der_balken(self) -> None:
        # Die Laufschiene wird als Schraffur gezeichnet: man muss sie sehen,
        # aber sie darf dem gefuellten Teil nicht die Schau stehlen.
        for name, palette in ALLE_PALETTEN:
            theme = next(t for t in RETRO_THEMES if t.name == name)
            grund = base_palette(theme).background
            schiene = contrast_ratio(palette.progress_trough, grund)
            balken = contrast_ratio(palette.progress_played, grund)
            assert schiene > 1.05, f"{name}: Laufschiene unsichtbar ({schiene:.2f}:1)"
            assert schiene < balken, f"{name}: Laufschiene lauter als der Balken"

    def test_trennlinie_ist_sichtbar_aber_nicht_laut(self) -> None:
        # Eine Trennlinie soll man sehen und nicht lesen: genug Abstand zum
        # Untergrund, aber weniger als die Schrift.
        for name, palette in ALLE_PALETTEN:
            theme = next(t for t in RETRO_THEMES if t.name == name)
            grund = base_palette(theme)
            zur_flaeche = contrast_ratio(palette.divider, grund.background)
            zur_schrift = contrast_ratio(grund.foreground, grund.background)
            assert zur_flaeche > 1.05, f"{name}: Trennlinie unsichtbar ({zur_flaeche:.2f}:1)"
            assert zur_flaeche < zur_schrift, f"{name}: Trennlinie lauter als die Schrift"


class TestUnterscheidbar:
    """Kann scheitern - zwei Pegelstufen duerfen nicht zusammenfallen."""

    def test_pegelstufen_sind_verschieden(self) -> None:
        gleich = [
            f"{name}: low={p.vis_low} mid={p.vis_mid} high={p.vis_high}"
            for name, p in ALLE_PALETTEN
            if len({p.vis_low, p.vis_mid, p.vis_high}) < 3
        ]
        assert not gleich, "Pegelstufen fallen zusammen:\n" + "\n".join(gleich)

    def test_pegel_hebt_sich_vom_untergrund_ab(self) -> None:
        schwach = [
            f"{name}.{stufe}: {contrast_ratio(getattr(p, stufe), p.vis_background):.2f}:1"
            for name, p in ALLE_PALETTEN
            for stufe in ("vis_low", "vis_mid", "vis_high")
            if contrast_ratio(getattr(p, stufe), p.vis_background) < 1.5
        ]
        assert not schwach, "Pegelbalken verschwinden im Untergrund:\n" + "\n".join(schwach)

    # Ueber alle 40 Themes gemessen liegt die gedimmte Ziffer zwischen 1.37:1
    # (flughund) und 2.21:1 (bebox). 1.25 laesst Luft, ist aber weit genug von
    # 1.0 entfernt, dass ein Verschwinden auffaellt.
    DIM_MINDESTKONTRAST = 1.25

    def test_gedimmte_lcd_ziffer_liegt_dazwischen(self) -> None:
        # Die unbeleuchtete Ziffer muss sichtbar sein, aber schwaecher als die
        # beleuchtete - sonst ist der LCD-Effekt weg.
        for name, p in ALLE_PALETTEN:
            hell = contrast_ratio(p.lcd_foreground, p.lcd_background)
            dunkel = contrast_ratio(p.lcd_dim, p.lcd_background)
            assert dunkel < hell, f"{name}: gedimmte Ziffer nicht schwaecher als die helle"
            assert dunkel >= self.DIM_MINDESTKONTRAST, f"{name}: gedimmte Ziffer unsichtbar ({dunkel:.2f}:1)"


class TestAdapter:
    def test_surface_palette_ueber_den_namen(self) -> None:
        palette = surface_palette("brotkasten")
        assert palette.lcd_foreground.startswith("#")

    def test_alter_slug_wird_gehoben(self) -> None:
        # c64 -> brotkasten, siehe LEGACY_THEME_MAP.
        assert surface_palette("c64") == surface_palette("brotkasten")

    def test_unbekannter_name_faellt_auf_den_standard(self) -> None:
        assert surface_palette("gibt-es-nicht") == surface_palette("brotkasten")

    def test_basispalette_uebernimmt_die_themefarben(self) -> None:
        theme = next(t for t in RETRO_THEMES if t.name == "brotkasten")
        grund = base_palette(theme)
        assert grund.primary == theme.primary
        assert grund.dark == theme.dark


class TestOhneTextual:
    """Das Palettenmodul darf sich nicht an die Oberflaeche binden."""

    def test_palette_laedt_ohne_textual_im_speicher(self) -> None:
        skript = (
            "import sys\n"
            "import retro_amp.palette as p\n"
            "geladen = [n for n in sys.modules if n.split('.')[0] in ('textual', 'rich', 'pygame')]\n"
            "print(','.join(sorted(geladen)))\n"
        )
        ergebnis = subprocess.run(
            [sys.executable, "-c", skript],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=120,
            check=False,
        )
        assert ergebnis.returncode == 0, ergebnis.stderr
        assert not ergebnis.stdout.strip(), f"Oberflaeche mitgeladen: {ergebnis.stdout.strip()}"
