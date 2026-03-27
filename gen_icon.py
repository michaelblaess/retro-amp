"""Generiert das retro-amp Icon (Jiji-Style Katze + Regenbogen-Spectrum)."""
from PIL import Image, ImageDraw

BG_DARK = (56, 56, 56)
BG_LIGHT = (80, 80, 80)
BG_EDGE = (42, 42, 42)

SPECTRUM = [
    (220, 30, 30),
    (240, 100, 20),
    (255, 200, 0),
    (100, 200, 50),
    (30, 160, 220),
    (80, 60, 200),
    (160, 50, 180),
]

BLACK = (20, 20, 25)
BLACK_LIGHT = (45, 45, 50)
EYE_WHITE = (245, 245, 240)
PUPIL = (15, 15, 15)

sizes = [16, 32, 48, 64, 128, 256]
images = []

for size in sizes:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    p = size / 256

    # --- Hintergrund ---
    margin = int(4 * p)
    radius = int(32 * p)
    draw.rounded_rectangle(
        [margin, margin, size - margin - 1, size - margin - 1],
        radius=radius, fill=BG_EDGE,
    )
    inner = int(8 * p)
    draw.rounded_rectangle(
        [inner, inner, size - inner - 1, size - inner - 1],
        radius=max(int(26 * p), 1), fill=BG_DARK,
    )
    hl = int(12 * p)
    draw.rounded_rectangle(
        [hl, hl, size - hl - 1, int(size * 0.48)],
        radius=max(int(22 * p), 1), fill=BG_LIGHT,
    )

    # --- Spectrum Bars (oberes Drittel) ---
    ba_left = int(24 * p)
    ba_right = size - int(24 * p)
    ba_top = int(20 * p)
    ba_bottom = int(105 * p)
    ba_total = ba_right - ba_left
    bar_w = int(ba_total / 7 * 0.74)
    step = int(ba_total / 7)

    heights = [0.50, 0.82, 1.0, 0.68, 0.90, 0.55, 0.40]
    ba_h = ba_bottom - ba_top

    for i, h in enumerate(heights):
        x = ba_left + i * step
        bh = int(ba_h * h)
        y_top = ba_bottom - bh
        color = SPECTRUM[i]

        segs = max(int(bh / (3 * p)), 4)
        seg_h = max(bh // segs, 1)
        for s in range(segs):
            ratio = s / max(segs - 1, 1)
            sy = ba_bottom - s * seg_h - seg_h
            if sy < y_top:
                sy = y_top
            bright = 0.7 + 0.3 * ratio
            cr = min(int(color[0] * bright), 255)
            cg = min(int(color[1] * bright), 255)
            cb = min(int(color[2] * bright), 255)
            draw.rectangle([x, sy, x + bar_w, sy + seg_h], fill=(cr, cg, cb))

        peak_y = y_top - int(6 * p)
        if peak_y > ba_top - int(10 * p):
            bp = tuple(min(int(c * 1.3), 255) for c in color)
            draw.rectangle(
                [x, peak_y, x + bar_w, peak_y + max(int(3 * p), 1)],
                fill=bp,
            )

    # --- Jiji-Katze (untere 2/3) ---
    cx = int(128 * p)
    base = int(244 * p)

    # Schwanz (geschwungen nach rechts oben, duenn und elegant)
    tw = max(int(6 * p), 2)
    tpts = [
        (cx + int(36 * p), base - int(15 * p)),
        (cx + int(55 * p), base - int(40 * p)),
        (cx + int(68 * p), base - int(68 * p)),
        (cx + int(62 * p), base - int(88 * p)),
        (cx + int(50 * p), base - int(98 * p)),
    ]
    for j in range(len(tpts) - 1):
        x1, y1 = tpts[j]
        x2, y2 = tpts[j + 1]
        w = tw + max(int((3 - j) * 1.5 * p), 1)
        draw.line([(x1, y1), (x2, y2)], fill=BLACK, width=w)

    # Koerper (schlank, aufrecht — Katze, nicht Eule!)
    body_w = int(38 * p)
    body_h = int(72 * p)
    draw.ellipse(
        [cx - body_w, base - body_h, cx + body_w, base + int(5 * p)],
        fill=BLACK,
    )

    # Brust (etwas heller, Tiefe andeuten)
    chest_w = int(22 * p)
    chest_h = int(25 * p)
    draw.ellipse(
        [cx - chest_w, base - int(50 * p), cx + chest_w, base - int(50 * p) + chest_h],
        fill=(30, 30, 35),
    )

    # Kopf (etwas breiter als hoch — Katze hat flacheren Kopf als Eule)
    head_rx = int(40 * p)   # breiter
    head_ry = int(35 * p)   # flacher
    hcy = base - body_h - head_ry + int(24 * p)
    draw.ellipse(
        [cx - head_rx, hcy - head_ry, cx + head_rx, hcy + head_ry],
        fill=BLACK,
    )

    # Ohren (hoch, spitz, weit auseinander — typisch Jiji)
    ear_h = int(40 * p)
    eby = hcy - head_ry + int(10 * p)

    # Linkes Ohr (spitz nach links-oben)
    draw.polygon([
        (cx - int(30 * p), eby),
        (cx - int(42 * p), eby - ear_h),
        (cx - int(10 * p), eby),
    ], fill=BLACK)
    ie = max(int(5 * p), 2)
    draw.polygon([
        (cx - int(30 * p) + ie, eby - ie),
        (cx - int(42 * p) + int(3 * p), eby - ear_h + ie * 2),
        (cx - int(10 * p) - ie, eby - ie),
    ], fill=(55, 35, 45))

    # Rechtes Ohr
    draw.polygon([
        (cx + int(10 * p), eby),
        (cx + int(42 * p), eby - ear_h),
        (cx + int(30 * p), eby),
    ], fill=BLACK)
    draw.polygon([
        (cx + int(10 * p) + ie, eby - ie),
        (cx + int(42 * p) - int(3 * p), eby - ear_h + ie * 2),
        (cx + int(30 * p) - ie, eby - ie),
    ], fill=(55, 35, 45))

    # Augen (oval, BREITER als hoch — DAS macht den Unterschied zur Eule!)
    eye_rx = max(int(12 * p), 3)   # breit
    eye_ry = max(int(9 * p), 2)    # flacher
    ey = hcy + int(2 * p)
    es = int(17 * p)

    # Weisse Augaepfel (oval)
    draw.ellipse([cx - es - eye_rx, ey - eye_ry, cx - es + eye_rx, ey + eye_ry], fill=EYE_WHITE)
    draw.ellipse([cx + es - eye_rx, ey - eye_ry, cx + es + eye_rx, ey + eye_ry], fill=EYE_WHITE)

    # Pupillen (gross, rund)
    pr = max(int(6 * p), 2)
    py2 = ey
    draw.ellipse([cx - es - pr, py2 - pr, cx - es + pr, py2 + pr], fill=PUPIL)
    draw.ellipse([cx + es - pr, py2 - pr, cx + es + pr, py2 + pr], fill=PUPIL)

    # Lichtreflexe
    gr = max(int(3 * p), 1)
    gx = int(3 * p)
    gy = int(-3 * p)
    draw.ellipse([cx - es + gx - gr, py2 + gy - gr, cx - es + gx + gr, py2 + gy + gr], fill=EYE_WHITE)
    draw.ellipse([cx + es + gx - gr, py2 + gy - gr, cx + es + gx + gr, py2 + gy + gr], fill=EYE_WHITE)

    # Nase (kleines Dreieck)
    ny = hcy + int(13 * p)
    ns = max(int(3.5 * p), 1)
    draw.polygon([
        (cx, ny + ns),
        (cx - ns - 1, ny - ns + 1),
        (cx + ns + 1, ny - ns + 1),
    ], fill=(130, 80, 85))

    # Mund (W-foermig unter der Nase)
    my = ny + ns + max(int(2 * p), 1)
    mw = max(int(9 * p), 2)
    mh = max(int(5 * p), 1)
    lw = max(int(2 * p), 1)
    draw.line([(cx, ny + ns), (cx, my + int(1 * p))], fill=BLACK_LIGHT, width=lw)
    draw.arc([cx - mw, my - mh // 2, cx, my + mh], 0, 180, fill=BLACK_LIGHT, width=lw)
    draw.arc([cx, my - mh // 2, cx + mw, my + mh], 0, 180, fill=BLACK_LIGHT, width=lw)

    # Schnurrhaare (6 Stueck, wichtig fuer Katzen-Erkennung!)
    wh_len = int(30 * p)
    wh_w = max(int(1.5 * p), 1)
    wh_base_y = ny + int(5 * p)
    wh_base_x = int(10 * p)
    # Links (3 Haare, leicht gefaechert)
    draw.line([(cx - wh_base_x, wh_base_y - int(3 * p)),
               (cx - wh_base_x - wh_len, wh_base_y - int(12 * p))],
              fill=BLACK_LIGHT, width=wh_w)
    draw.line([(cx - wh_base_x, wh_base_y),
               (cx - wh_base_x - wh_len, wh_base_y - int(2 * p))],
              fill=BLACK_LIGHT, width=wh_w)
    draw.line([(cx - wh_base_x, wh_base_y + int(3 * p)),
               (cx - wh_base_x - wh_len, wh_base_y + int(8 * p))],
              fill=BLACK_LIGHT, width=wh_w)
    # Rechts (3 Haare)
    draw.line([(cx + wh_base_x, wh_base_y - int(3 * p)),
               (cx + wh_base_x + wh_len, wh_base_y - int(12 * p))],
              fill=BLACK_LIGHT, width=wh_w)
    draw.line([(cx + wh_base_x, wh_base_y),
               (cx + wh_base_x + wh_len, wh_base_y - int(2 * p))],
              fill=BLACK_LIGHT, width=wh_w)
    draw.line([(cx + wh_base_x, wh_base_y + int(3 * p)),
               (cx + wh_base_x + wh_len, wh_base_y + int(8 * p))],
              fill=BLACK_LIGHT, width=wh_w)

    # Vorderpfoten (zwei kleine Ovale unten am Koerper)
    paw_y = base - int(5 * p)
    paw_rx = max(int(10 * p), 2)
    paw_ry = max(int(6 * p), 1)
    draw.ellipse([cx - int(20 * p) - paw_rx, paw_y - paw_ry,
                  cx - int(20 * p) + paw_rx, paw_y + paw_ry], fill=(30, 30, 35))
    draw.ellipse([cx + int(20 * p) - paw_rx, paw_y - paw_ry,
                  cx + int(20 * p) + paw_rx, paw_y + paw_ry], fill=(30, 30, 35))

    images.append(img)

images[-1].save(
    "C:/Users/Michael/Repos/retro-amp/retro-amp.ico",
    format="ICO",
    sizes=[(s, s) for s in sizes],
    append_images=images[:-1],
)
images[-1].save("C:/Users/Michael/Repos/retro-amp/retro-amp-preview.png", format="PNG")
print("Icon erstellt (Jiji v2)")
