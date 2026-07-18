"""Bereitet die zwei Gold-Stereo-Renders als Web-Hero-Teaser auf.

- hero-receiver (7o9get): heller Hintergrund -> per Flood-Fill freigestellt
  (transparent), funktioniert auf hellem UND dunklem Grund.
- hero-stack (rmvhoh): dunkler Hintergrund -> eng zugeschnitten, Gemini-
  Wasserzeichen (unten rechts) weggeschnitten; bleibt auf seinem dunklen Grund.

Ausgabe (Breite 1000 px) nach assets/, Kopie in docs/ macht das Wiring.

Aufruf (aus dem Repo-Root):
    uv run --no-sync python assets/make_hero.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

_SRC = Path(__file__).resolve().parent / "source"
_OUT = Path(__file__).resolve().parent
_WIDTH = 1000


def _resize_w(img: Image.Image, w: int) -> Image.Image:
    return img.resize((w, int(img.height * w / img.width)), Image.Resampling.LANCZOS)


def free_receiver() -> Image.Image:
    """Stellt den Gold-Receiver (heller Grund) frei und trimmt auf den Inhalt."""
    src = Image.open(_SRC / "hero-receiver.png").convert("RGB")
    key = (255, 0, 255)
    fill = src.copy()
    w, h = fill.size
    for xy in ((1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2), (w // 2, 1)):
        ImageDraw.floodfill(fill, xy, key, thresh=40)
    rgba = src.convert("RGBA")
    fpx = fill.load()
    opx = rgba.load()
    assert fpx is not None and opx is not None
    for y in range(h):
        for x in range(w):
            if fpx[x, y] == key:
                opx[x, y] = (0, 0, 0, 0)
    eroded = rgba.split()[3].filter(ImageFilter.MinFilter(3))
    rgba.putalpha(eroded)
    bbox = rgba.getbbox()
    if bbox:
        rgba = rgba.crop(bbox)

    # Boden-Reflexion entfernen: nur den obersten zusammenhaengenden Zeilen-Run
    # (= das eigentliche Geraet) behalten, die gespiegelte Kopie darunter faellt weg
    rw, rh = rgba.size
    alpha = rgba.split()[3].load()
    assert alpha is not None
    row_cov = [sum(1 for x in range(rw) if alpha[x, y] > 24) for y in range(rh)]
    thr = rw * 0.06
    end = 0
    while end < rh and row_cov[end] > thr:
        end += 1
    if end > rh * 0.4:  # plausibler Geraete-Block gefunden
        rgba = rgba.crop((0, 0, rw, end))
    return _resize_w(rgba, _WIDTH)


def crop_stack() -> Image.Image:
    """Schneidet den dunklen Stereo-Stack eng zu und entfernt das Eck-Wasserzeichen."""
    src = Image.open(_SRC / "hero-stack.png").convert("RGB")
    w, h = src.size
    # Gleichmaessiger Rand; rechts/unten etwas mehr, damit das '+'-Wasserzeichen faellt
    crop = src.crop((int(w * 0.05), int(h * 0.05), int(w * 0.90), int(h * 0.90)))
    return _resize_w(crop, _WIDTH)


def main() -> None:
    recv = free_receiver()
    stack = crop_stack()
    recv.save(_OUT / "hero-receiver.png")
    stack.save(_OUT / "hero-stack.png")
    print(f"hero-receiver.png ({recv.width}x{recv.height}, transparent) geschrieben")
    print(f"hero-stack.png ({stack.width}x{stack.height}) geschrieben")


if __name__ == "__main__":
    main()
