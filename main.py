#!/usr/bin/env python3
"""LUMARIS — travel poster for a place that isn't there.

Pure Python standard library only (struct + zlib). Draws a 1024x1024
travel poster for LUMARIS, a floating salt-lagoon city, and writes it
as a PNG to $MAKEFUN_OUTPUT_DIR/entry.png (default /output/entry.png).
"""

import math
import os
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- palette
SKY_TOP = (24, 32, 84)        # deep indigo dusk
SKY_MID = (122, 90, 158)      # violet
SKY_LOW = (232, 138, 90)      # ember peach
SKY_HORIZON = (255, 217, 160)  # warm gold at the horizon
SUN_CORE = (255, 243, 196)
SUN_GLOW = (255, 205, 120)
MOUNTAIN_FAR = (74, 62, 118)
MOUNTAIN_NEAR = (48, 42, 92)
LAGOON_TOP = (46, 139, 139)   # teal shallows
LAGOON_DEEP = (13, 52, 70)    # deep lagoon
SALT = (244, 238, 222)        # pale salt flats
CITY = (250, 244, 228)        # warm white city
CITY_SHADE = (214, 196, 178)
WINDOW = (255, 190, 90)       # lantern-lit windows
INK = (28, 24, 58)            # type shadow / dark line
CREAM = (255, 246, 224)       # main type

HORIZON = 560


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def clamp(v, lo=0, hi=255):
    return lo if v < lo else hi if v > hi else v


def blend(dst, src, alpha):
    """Alpha-blend src over dst; alpha in 0..1."""
    return tuple(int(dst[i] + (src[i] - dst[i]) * alpha) for i in range(3))


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)

    def set(self, x, y, color, alpha=1.0):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            if alpha >= 1.0:
                self.px[i], self.px[i + 1], self.px[i + 2] = color
            else:
                old = (self.px[i], self.px[i + 1], self.px[i + 2])
                c = blend(old, color, alpha)
                self.px[i], self.px[i + 1], self.px[i + 2] = c

    def rect(self, x0, y0, x1, y1, color, alpha=1.0):
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(self.w, x1)
        y1 = min(self.h, y1)
        for y in range(y0, y1):
            base = (y * self.w + x0) * 3
            for x in range(x0, x1):
                i = base + (x - x0) * 3
                if alpha >= 1.0:
                    self.px[i], self.px[i + 1], self.px[i + 2] = color
                else:
                    old = (self.px[i], self.px[i + 1], self.px[i + 2])
                    c = blend(old, color, alpha)
                    self.px[i], self.px[i + 1], self.px[i + 2] = c

    def disc(self, cx, cy, r, color, alpha=1.0):
        r2 = r * r
        for y in range(cy - r, cy + r + 1):
            dy = y - cy
            dx = int(math.sqrt(max(0, r2 - dy * dy)))
            for x in range(cx - dx, cx + dx + 1):
                self.set(x, y, color, alpha)

    def line(self, x0, y0, x1, y1, color, width=1, alpha=1.0):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for s in range(steps + 1):
            t = s / steps
            x = int(x0 + (x1 - x0) * t)
            y = int(y0 + (y1 - y0) * t)
            half = width // 2
            for dy in range(-half, half + 1):
                for dx in range(-half, half + 1):
                    self.set(x + dx, y + dy, color, alpha)


# ------------------------------------------------------- tiny LCG for stars
def lcg(seed):
    while True:
        seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
        yield seed


# ------------------------------------------------------------------- font
# Authored 5x7 bitmap letterforms ('#' = ink, '.' = empty).
FONT = {
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "N": ("#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"),
    "G": (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
}


def text_width(text, scale):
    return sum(5 * scale + 2 * scale for _ in text) - 2 * scale


def draw_text(cv, text, cx, y, scale, color, shadow=None):
    """Draw text centered on cx, top edge at y."""
    total = text_width(text, scale)
    x = cx - total // 2
    for ch in text:
        glyph = FONT.get(ch, FONT[" "])
        for row in range(7):
            for col in range(5):
                if glyph[row][col] == "#":
                    if shadow is not None:
                        cv.rect(x + col * scale + 3, y + row * scale + 4,
                                x + (col + 1) * scale + 3,
                                y + (row + 1) * scale + 4, shadow)
                    cv.rect(x + col * scale, y + row * scale,
                            x + (col + 1) * scale, y + (row + 1) * scale,
                            color)
        x += 7 * scale


# ------------------------------------------------------------------- scene
def draw_sky(cv):
    for y in range(0, HORIZON):
        t = y / HORIZON
        if t < 0.45:
            c = lerp(SKY_TOP, SKY_MID, t / 0.45)
        elif t < 0.8:
            c = lerp(SKY_MID, SKY_LOW, (t - 0.45) / 0.35)
        else:
            c = lerp(SKY_LOW, SKY_HORIZON, (t - 0.8) / 0.2)
        cv.rect(0, y, W, y + 1, c)


def draw_stars(cv):
    rng = lcg(20261121)
    for _ in range(140):
        x = next(rng) % W
        y = next(rng) % 300
        r = next(rng) % 2 + 1
        a = 0.35 + (next(rng) % 100) / 200.0
        cv.disc(x, y, r, (255, 250, 230), a * (1 - y / 420.0))


def draw_sun(cv):
    cx, cy, r = 712, 348, 74
    for k in range(8, 0, -1):
        cv.disc(cx, cy, r + k * 18, SUN_GLOW, 0.055)
    cv.disc(cx, cy, r + 10, (255, 214, 140), 0.55)
    cv.disc(cx, cy, r, SUN_CORE)
    cv.disc(cx, cy, r - 12, (255, 226, 150))


def draw_mountains(cv):
    # Far ridge, violet silhouette.
    for x in range(W):
        h = (26 * math.sin(x * 0.011 + 1.2)
             + 14 * math.sin(x * 0.031 + 4.0)
             + 8 * math.sin(x * 0.057))
        top = int(HORIZON - 58 + h)
        cv.rect(x, top, x + 1, HORIZON, MOUNTAIN_FAR)
    # Near ridge, darker, lower.
    for x in range(W):
        h = (18 * math.sin(x * 0.017 + 3.1)
             + 10 * math.sin(x * 0.043 + 0.6))
        top = int(HORIZON - 26 + h)
        cv.rect(x, top, x + 1, HORIZON, MOUNTAIN_NEAR)


def draw_lagoon(cv):
    for y in range(HORIZON, H):
        t = (y - HORIZON) / (H - HORIZON)
        c = lerp(LAGOON_TOP, LAGOON_DEEP, t * t)
        cv.rect(0, y, W, y + 1, c)
    # Sun path: shimmering column of light under the sun.
    rng = lcg(777)
    for y in range(HORIZON + 4, H - 30):
        spread = 26 + (y - HORIZON) * 0.22
        for _ in range(9):
            x = int(712 + (next(rng) % 1000 / 1000.0 - 0.5) * 2 * spread)
            w = 4 + next(rng) % 14
            a = 0.10 + (next(rng) % 100) / 400.0
            cv.rect(x, y, x + w, y + 2, SUN_CORE, a)
    # Gentle wave lines.
    for k in range(26):
        y = HORIZON + 24 + k * 17
        x0 = (k * 173) % W
        cv.line(x0, y, x0 + 60, y, (255, 255, 255), 1, 0.10)


def draw_salt_flats(cv):
    # Pale salt pans creeping in from both bottom corners.
    for x in range(W):
        left = int(180 * math.sin(x * 0.006 + 0.8) ** 2)
        right = int(150 * math.sin(x * 0.008 + 2.4) ** 2)
        top_l = H - 150 - left
        top_r = H - 130 - right
        if x < 330:
            cv.rect(x, top_l, x + 1, H, SALT, 0.92)
        if x > 700:
            cv.rect(x, top_r, x + 1, H, SALT, 0.92)


def draw_city(cv):
    """The landmark: LUMARIS, a floating city of domes and spires."""
    base = HORIZON - 6
    # Stilts down into the water.
    for x in range(392, 640, 26):
        cv.rect(x, base, x + 3, base + 34, CITY_SHADE)
    # Main platform.
    cv.rect(372, base - 16, 652, base, CITY)
    cv.rect(372, base - 16, 652, base - 10, CITY_SHADE)
    # Domes of different sizes along the platform.
    for cx, r in ((420, 34), (478, 46), (540, 30), (596, 40)):
        for dy in range(r):
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            cv.rect(cx - dx, base - 16 - r + dy, cx + dx + 1,
                    base - 16 - r + dy + 1, CITY)
        cv.rect(cx - 2, base - 16 - r - 14, cx + 2, base - 16 - r, CITY_SHADE)
    # Tall central spire — the city's unmistakable needle.
    cv.line(512, base - 16, 512, base - 178, CITY, 5)
    cv.line(512, base - 178, 486, base - 96, CITY, 3)
    cv.line(512, base - 178, 538, base - 96, CITY, 3)
    cv.disc(512, base - 186, 9, WINDOW)
    # Smaller spires.
    for cx, h in ((448, 92), (576, 108)):
        cv.line(cx, base - 16, cx, base - h, CITY, 4)
        cv.line(cx, base - h, cx - 16, base - h + 34, CITY, 2)
        cv.line(cx, base - h, cx + 16, base - h + 34, CITY, 2)
        cv.disc(cx, base - h - 4, 5, WINDOW)
    # Lantern-lit windows across the facades.
    rng = lcg(4242)
    for _ in range(46):
        x = 380 + next(rng) % 264
        y = base - 14 + next(rng) % 12
        cv.rect(x, y, x + 4, y + 5, WINDOW, 0.9)
    # A string of lanterns glowing along the platform edge.
    for x in range(384, 644, 18):
        cv.disc(x, base - 20, 3, WINDOW)
        cv.disc(x, base - 20, 6, SUN_GLOW, 0.25)
    # Faint reflection of the city in the lagoon.
    for y in range(base + 34, base + 96):
        a = 0.16 * (1 - (y - base - 34) / 62.0)
        cv.rect(400, y, 624, y + 1, CITY, a)


def draw_boats(cv):
    for cx, cy, s in ((250, 700, 1.0), (800, 830, 1.4)):
        w = int(64 * s)
        h = int(14 * s)
        for dy in range(h):
            t = dy / h
            half = int(w / 2 * (1 - t * 0.55))
            cv.rect(cx - half, cy + dy, cx + half, cy + dy + 1, INK)
        cv.line(cx, cy - int(34 * s), cx, cy, CREAM, 2)
        cv.line(cx, cy - int(34 * s), cx + int(26 * s), cy - 4, CREAM, 2)
        cv.line(cx, cy - int(34 * s), cx - int(20 * s), cy - 4, SUN_GLOW, 2)


def draw_birds(cv):
    for cx, cy, s in ((180, 210, 12), (240, 180, 9), (880, 240, 11),
                      (830, 190, 8), (320, 260, 9)):
        cv.line(cx - s, cy, cx, cy - 5, INK, 2)
        cv.line(cx, cy - 5, cx + s, cy, INK, 2)


def draw_type(cv):
    draw_text(cv, "LUMARIS", W // 2, 92, 17, CREAM, shadow=INK)
    # Thin gold rule under the name, echoing the horizon line.
    rule_w = text_width("LUMARIS", 17) - 60
    cv.rect(W // 2 - rule_w // 2, 218, W // 2 + rule_w // 2, 222, SUN_GLOW)
    cv.rect(W // 2 - rule_w // 2, 222, W // 2 + rule_w // 2, 223, INK, 0.35)
    draw_text(cv, "THE FLOATING SALT LAGOON", W // 2, 238, 4, CREAM,
              shadow=INK)


# --------------------------------------------------------------------- png
def encode_png(cv):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)  # filter: none
        start = y * stride
        raw += cv.px[start:start + stride]
    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    cv = Canvas(W, H)
    draw_sky(cv)
    draw_stars(cv)
    draw_sun(cv)
    draw_mountains(cv)
    draw_lagoon(cv)
    draw_salt_flats(cv)
    draw_city(cv)
    draw_boats(cv)
    draw_birds(cv)
    draw_type(cv)
    data = encode_png(cv)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {path}: {len(data)} bytes, {W}x{H}")


if __name__ == "__main__":
    main()
