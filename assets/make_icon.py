"""Erzeugt das App-Icon fuer retro-amp.

Standard: die Teal-Katze mit Kopfhoerern (assets/source/icon-cat.png) - ein
fertiges, quadratisches Icon mit eigener dunkler Kachel und runden Ecken. Es
wird nur skaliert und in alle gebrauchten Formate exportiert.

Alternativ (--cassette): das Gold-Kassetten-Motiv aus
assets/source/cassette-sheet.png - die groesste Kassette wird freigestellt,
mittig auf ein dunkles Tile (Verlauf, runde Ecken) gelegt und zusaetzlich ein
transparentes Logo getrimmt. (Das Motiv bleibt erhalten, ist aber nicht mehr
der Standard.)

Hinweis: Beide Quellen sind Raster-Render (keine Vektorgeometrie) - es gibt
KEINE SVG-Varianten. Die kleinen Icon-Groessen (16/32 px) sind motivbedingt
weicher als ein reines Flat-Icon.

Erzeugt (beide Modi):
- assets/icon.ico   (16/32/48/64/128/256 px)  - --windows-icon-from-ico / Favicon
- assets/icon.icns  (1024 px, nativ)          - --macos-app-icon
- assets/icon.png   (512 px)                  - og:image / Apple-Touch / Social
Nur --cassette zusaetzlich:
- assets/icon-logo.png (transparent, getrimmt) - Kassetten-Logo

Aufruf (aus dem Repo-Root):
    uv run --no-sync python assets/make_icon.py             # Katze (Standard)
    uv run --no-sync python assets/make_icon.py --cassette  # Gold-Kassette
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

_TILE_RADIUS_FRAC = 0.22
_BG_TOP = (16, 28, 26)
_BG_BOTTOM = (9, 13, 17)

# Anteil der Tile-Breite, den die Kassette einnimmt (Rest = Rand)
_CASSETTE_WIDTH_FRAC = 0.82

_ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def _vgrad(size: int, top: tuple, bot: tuple) -> Image.Image:
    """Baut einen vertikalen Farbverlauf als RGBA-Bild."""
    grad = Image.new("RGBA", (size, size))
    px = grad.load()
    assert px is not None
    for y in range(size):
        f = y / (size - 1)
        c = tuple(int(top[i] + (bot[i] - top[i]) * f) for i in range(3)) + (255,)
        for x in range(size):
            px[x, y] = c
    return grad


def _tile_bg(size: int) -> Image.Image:
    """Dunkles Tile mit Verlauf und abgerundeten Ecken (App-Icon-Look)."""
    img = _vgrad(size, _BG_TOP, _BG_BOTTOM)
    mask = Image.new("L", (size, size), 0)
    radius = int(_TILE_RADIUS_FRAC * size)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    img.putalpha(mask)
    return img


def cat_master() -> Image.Image:
    """Laedt das fertige Katzen-Icon (eigene Kachel) als 1024er-Master."""
    src = Image.open(Path(__file__).resolve().parent / "source" / "icon-cat.png").convert("RGBA")
    if src.size != (1024, 1024):
        src = src.resize((1024, 1024), Image.Resampling.LANCZOS)
    return src


def free_cassette() -> Image.Image:
    """Stellt die groesste (linke) Kassette aus dem Quell-Sheet frei (transparent)."""
    src = Image.open(Path(__file__).resolve().parent / "source" / "cassette-sheet.png").convert("RGB")
    spx = src.load()
    assert spx is not None
    w, h = src.size

    # Gold-Region links lokalisieren (Bounding-Box ueber gesaettigte Warmtoene)
    xmin, ymin, xmax, ymax = w, h, 0, 0
    for y in range(0, h, 2):
        for x in range(0, min(w, 430), 2):
            r, g, b = spx[x, y]
            if r > 150 and (r - b) > 45 and g > 95:
                xmin, ymin = min(xmin, x), min(ymin, y)
                xmax, ymax = max(xmax, x), max(ymax, y)
    pad = 12
    crop = src.crop((max(0, xmin - pad), max(0, ymin - pad), min(w, xmax + pad), min(h, ymax + pad)))

    # Hintergrund (weiss/grau) per Flood-Fill vom Rand wegkeyen
    key = (255, 0, 255)
    fill = crop.copy()
    cw, ch = fill.size
    for xy in ((1, 1), (cw - 2, 1), (1, ch - 2), (cw - 2, ch - 2), (cw // 2, 1), (cw // 2, ch - 2)):
        ImageDraw.floodfill(fill, xy, key, thresh=42)
    rgba = crop.convert("RGBA")
    fpx = fill.load()
    opx = rgba.load()
    assert fpx is not None and opx is not None
    for y in range(ch):
        for x in range(cw):
            if fpx[x, y] == key:
                opx[x, y] = (0, 0, 0, 0)

    # Nachbar-Kassette ueber die Spalten-Luecke abschneiden, dann auf Inhalt trimmen
    alpha = rgba.split()[3].load()
    assert alpha is not None
    col_cov = [sum(1 for y in range(ch) if alpha[x, y] > 16) for x in range(cw)]
    thr = ch * 0.05
    runs = []
    start = None
    for x in range(cw):
        if col_cov[x] > thr and start is None:
            start = x
        elif col_cov[x] <= thr and start is not None:
            runs.append((start, x - 1))
            start = None
    if start is not None:
        runs.append((start, cw - 1))
    center = cw // 2
    main_run = next(
        (r for r in runs if r[0] <= center <= r[1]),
        max(runs, key=lambda r: r[1] - r[0]) if runs else (0, cw - 1),
    )
    rgba = rgba.crop((main_run[0], 0, main_run[1] + 1, ch))
    bbox = rgba.getbbox()
    if bbox:
        rgba = rgba.crop(bbox)

    # Anti-Aliasing-Saum (heller Rand) um 1px erodieren
    bands = rgba.split()
    eroded = bands[3].filter(ImageFilter.MinFilter(3))
    rgba.putalpha(eroded)
    return rgba


def build_tile(size: int, cassette: Image.Image) -> Image.Image:
    """Legt die freigestellte Kassette mittig auf ein dunkles Tile der Kantenlaenge size."""
    tile = _tile_bg(size)
    target_w = int(size * _CASSETTE_WIDTH_FRAC)
    scale = target_w / cassette.width
    cass = cassette.resize((target_w, max(1, int(cassette.height * scale))), Image.Resampling.LANCZOS)
    ox = (size - cass.width) // 2
    oy = (size - cass.height) // 2
    tile.paste(cass, (ox, oy), cass)
    return tile


def _write_formats(master: Image.Image, assets: Path) -> None:
    """Schreibt icon.ico (multi-res) + icon.png (512) + icon.icns (1024)."""
    master.resize((256, 256), Image.Resampling.LANCZOS).save(assets / "icon.ico", sizes=_ICO_SIZES)
    master.resize((512, 512), Image.Resampling.LANCZOS).save(assets / "icon.png")
    master.save(assets / "icon.icns")
    print(f"icon.ico ({', '.join(f'{w}x{h}' for w, h in _ICO_SIZES)}) / icon.png (512) / icon.icns (1024)")


def main() -> None:
    parser = argparse.ArgumentParser(description="App-Icon fuer retro-amp erzeugen")
    parser.add_argument(
        "--cassette",
        action="store_true",
        help="Gold-Kassetten-Motiv statt der Katze rendern (Standard: Katze)",
    )
    args = parser.parse_args()
    assets = Path(__file__).resolve().parent

    if args.cassette:
        cassette = free_cassette()
        _write_formats(build_tile(1024, cassette), assets)
        # Transparentes Logo (ohne Tile) fuer die Kassetten-Variante - getrimmt, Hoehe 320
        logo_h = 320
        logo = cassette.resize(
            (int(cassette.width * logo_h / cassette.height), logo_h),
            Image.Resampling.LANCZOS,
        )
        logo.save(assets / "icon-logo.png")
        print(f"Kassetten-Icon + icon-logo.png ({logo.width}x{logo.height}) geschrieben")
    else:
        _write_formats(cat_master(), assets)
        print("Katzen-Icon geschrieben (Quelle: source/icon-cat.png)")


if __name__ == "__main__":
    main()
