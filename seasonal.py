"""Cute hand-drawn seasonal doodles placed in empty areas of the image.

Each doodle draws inside a square box (x, y, s); shapes are defined in a 0..100 unit space.
The theme is picked from the date (holidays first, then season).
"""
import datetime
import math
from functools import partial

from PIL import Image

from sketch import (BLACK, WHITE, GREEN, BLUE, RED, YELLOW, ORANGE,
                    ellipse_pts, star_pts)


def _m(x, y, s):
    """Map 0..100 doodle units to image coordinates."""
    k = s / 100.0
    return lambda px, py: (x + px * k, y + py * k)


def _pts(m, pts):
    return [m(px, py) for px, py in pts]


def _ell(m, cx, cy, rx, ry, n=30, rot=0.0, start=0.0):
    return _pts(m, ellipse_pts(cx, cy, rx, ry, n=n, rot=rot, start=start))


def _face(sk, m, s, cx, cy, spread=8, smile=6):
    k = s / 100.0
    for dx in (-spread, spread):
        sk.dot(*m(cx + dx, cy), max(1.2, 2.6 * k))
    arc = [m(cx + smile * math.cos(a), cy + 4 + smile * 0.7 * math.sin(a))
           for a in [math.pi * (0.2 + 0.6 * i / 6) for i in range(7)]]
    sk.stroke(arc, width=1.5, amp=0)


# ---- autumn ----

def leaf(sk, x, y, s, color=ORANGE):
    m = _m(x, y, s)
    rot = sk.rng.uniform(-0.9, 0.9)
    c, sn = math.cos(rot), math.sin(rot)

    def r(px, py):  # rotate around the box centre
        px, py = px - 50, py - 50
        return m(50 + px * c - py * sn, 50 + px * sn + py * c)

    side_l, side_r = [], []
    for i in range(17):
        t = i / 16
        w = 26 * math.sin(math.pi * t) ** 0.8
        ax, ay = 22 + 60 * t, 78 - 60 * t  # axis from base (22,78) to tip (82,18)
        side_l.append(r(ax - w * 0.707, ay - w * 0.707))
        side_r.append(r(ax + w * 0.707, ay + w * 0.707))
    sk.shape(side_l + side_r[::-1], fill=color)
    sk.stroke([r(12, 88), r(22, 78), r(74, 26)], width=1.6, amp=0.3)
    for t in (0.3, 0.5, 0.7):
        ax, ay = 22 + 60 * t, 78 - 60 * t
        sk.line(r(ax, ay), r(ax - 6, ay - 14), width=1.2, amp=0)
        sk.line(r(ax, ay), r(ax + 14, ay + 6), width=1.2, amp=0)


def mushroom(sk, x, y, s):
    m = _m(x, y, s)
    sk.shape(_pts(m, [(38, 52), (62, 52), (65, 90), (35, 90)]), fill=WHITE)
    cap = [m(50 + 44 * math.cos(a), 56 + 40 * math.sin(a)) for a in [math.pi + math.pi * i / 20 for i in range(21)]]
    cap += [m(50 + 44 * (1 - 2 * i / 10), 56 + 4 * math.sin(math.pi * i / 10)) for i in range(1, 10)]
    sk.shape(cap, fill=RED)
    for cx, cy, r in ((30, 42, 6), (52, 28, 7), (72, 44, 5), (50, 46, 4)):
        sk.shape(_ell(m, cx, cy, r, r * 0.85, n=14), fill=WHITE, width=1.3, amp=0.2)
    for gx in (26, 74):
        sk.stroke(_pts(m, [(gx - 6, 86), (gx - 3, 92), (gx, 82), (gx + 3, 92), (gx + 6, 86)]), width=1.4, amp=0.2)


def apple(sk, x, y, s):
    m = _m(x, y, s)
    pts = []
    for i in range(40):
        a = -math.pi / 2 + 2 * math.pi * i / 40
        px, py = 50 + 36 * math.cos(a), 58 + 34 * math.sin(a)
        d = math.atan2(math.sin(a + math.pi / 2), math.cos(a + math.pi / 2))
        py += 9 * math.exp(-d * d / 0.08)  # dimple at the top
        pts.append(m(px, py))
    sk.shape(pts, fill=RED)
    sk.stroke(_pts(m, [(50, 32), (52, 22), (56, 14)]), width=2, amp=0.2)
    sk.shape(_ell(m, 67, 20, 11, 5, n=16, rot=-0.5), fill=GREEN, width=1.5, amp=0.2)
    sk.stroke(_ell(m, 34, 48, 6, 10, n=10, start=3.6)[:4], width=1.5, amp=0)  # shine


def pumpkin(sk, x, y, s, face=False):
    m = _m(x, y, s)
    sk.shape(_pts(m, [(46, 30), (54, 30), (58, 16), (49, 14)]), fill=GREEN, width=1.6)
    sk.shape(_ell(m, 32, 62, 24, 30), fill=ORANGE)
    sk.shape(_ell(m, 68, 62, 24, 30), fill=ORANGE)
    sk.shape(_ell(m, 50, 62, 22, 32), fill=ORANGE)
    if face:
        sk.ink_fill(_pts(m, [(32, 58), (42, 58), (37, 48)]))
        sk.ink_fill(_pts(m, [(58, 58), (68, 58), (63, 48)]))
        sk.ink_fill(_pts(m, [(30, 68), (38, 74), (44, 69), (50, 75), (56, 69), (62, 74), (70, 68),
                             (64, 82), (36, 82)]))


def ghost(sk, x, y, s):
    m = _m(x, y, s)
    pts = [m(50 + 30 * math.cos(a), 42 + 30 * math.sin(a)) for a in [math.pi + math.pi * i / 16 for i in range(17)]]
    pts.append(m(80, 86))
    for i in range(1, 13):
        t = i / 12
        pts.append(m(80 - 60 * t, 86 + 5 * math.sin(t * 3 * 2 * math.pi + math.pi)))
    sk.shape(pts, fill=WHITE)
    sk.dot(*m(42, 44), s * 0.035)
    sk.dot(*m(58, 44), s * 0.035)
    sk.stroke(_ell(m, 50, 58, 4, 5, n=10), width=1.5, amp=0)


# ---- winter / christmas ----

def tree(sk, x, y, s):
    m = _m(x, y, s)
    sk.shape(_pts(m, [(44, 84), (56, 84), (56, 96), (44, 96)]), fill=ORANGE, width=1.6)
    sk.shape(_pts(m, [(50, 40), (86, 86), (14, 86)]), fill=GREEN)
    sk.shape(_pts(m, [(50, 24), (78, 64), (22, 64)]), fill=GREEN)
    sk.shape(_pts(m, [(50, 10), (70, 42), (30, 42)]), fill=GREEN)
    for (bx, by), c in zip([(40, 54), (62, 58), (50, 74), (32, 80), (70, 80), (54, 36)],
                           [RED, BLUE, RED, YELLOW, RED, YELLOW]):
        sk.shape(_ell(m, bx, by, 4.5, 4.5, n=12), fill=c, width=1.2, amp=0)
    sk.shape(_pts(m, star_pts(50, 10, 11, 5)), fill=YELLOW, width=1.6, amp=0.2)


def gift(sk, x, y, s, color=RED, ribbon=YELLOW):
    m = _m(x, y, s)
    sk.shape(_ell(m, 38, 24, 13, 7, n=16, rot=0.4), fill=ribbon, width=1.6)
    sk.shape(_ell(m, 62, 24, 13, 7, n=16, rot=-0.4), fill=ribbon, width=1.6)
    sk.shape(_pts(m, [(20, 44), (80, 44), (80, 92), (20, 92)]), fill=color)
    sk.shape(_pts(m, [(15, 32), (85, 32), (85, 46), (15, 46)]), fill=color)
    sk.shape(_pts(m, [(45, 32), (55, 32), (55, 92), (45, 92)]), fill=ribbon, width=1.6)


def star(sk, x, y, s):
    m = _m(x, y, s)
    sk.shape(_pts(m, star_pts(50, 54, 44, 20, rot=-math.pi / 2 + sk.rng.uniform(-0.2, 0.2))), fill=YELLOW)
    _face(sk, m, s, 50, 52, spread=7, smile=5)


def snowman(sk, x, y, s):
    m = _m(x, y, s)
    sk.stroke(_pts(m, [(28, 62), (14, 50), (8, 52)]), width=1.8, amp=0.3)
    sk.stroke(_pts(m, [(72, 62), (86, 50), (92, 52)]), width=1.8, amp=0.3)
    sk.shape(_ell(m, 50, 70, 27, 25), fill=WHITE)
    sk.shape(_ell(m, 50, 34, 18, 17), fill=WHITE)
    sk.shape(_pts(m, [(32, 47), (68, 47), (68, 54), (32, 54)]), fill=RED, width=1.6)
    sk.shape(_pts(m, [(56, 52), (64, 52), (66, 70), (58, 70)]), fill=RED, width=1.6)
    sk.dot(*m(44, 30), s * 0.03)
    sk.dot(*m(56, 30), s * 0.03)
    sk.shape(_pts(m, [(50, 35), (68, 39), (50, 41)]), fill=ORANGE, width=1.3, amp=0)
    for by in (64, 76):
        sk.dot(*m(50, by), s * 0.03)


def snowflake(sk, x, y, s, color=BLUE):
    m = _m(x, y, s)
    rot = sk.rng.uniform(0, math.pi / 3)
    for i in range(6):
        a = rot + i * math.pi / 3
        tip = m(50 + 42 * math.cos(a), 50 + 42 * math.sin(a))
        sk.line(m(50, 50), tip, width=2.4, amp=0.3, color=color)
        for d, ln in ((22, 12), (32, 8)):
            bx, by = 50 + d * math.cos(a), 50 + d * math.sin(a)
            for sgn in (-1, 1):
                b = a + sgn * 0.8
                sk.line(m(bx, by), m(bx + ln * math.cos(b), by + ln * math.sin(b)), width=2, amp=0, color=color)


def mitten(sk, x, y, s):
    m = _m(x, y, s)
    pts = [(32, 78), (28, 46), (32, 24), (50, 12), (66, 22), (70, 44), (78, 36), (88, 42),
           (80, 60), (70, 70), (68, 78)]
    sk.shape(_pts(m, pts), fill=RED)
    sk.shape(_pts(m, [(28, 76), (72, 76), (72, 94), (28, 94)]), fill=WHITE)
    for hx, hy in ((42, 40), (56, 50), (44, 60), (56, 30)):
        sk.shape(_pts(m, [(hx, hy - 4), (hx + 4, hy), (hx, hy + 4), (hx - 4, hy)]), fill=WHITE, width=1.1, amp=0)


def heart(sk, x, y, s, color=RED):
    m = _m(x, y, s)
    pts = []
    for i in range(40):
        t = 2 * math.pi * i / 40
        hx = 16 * math.sin(t) ** 3
        hy = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append(m(50 + hx * 2.6, 48 - hy * 2.6))
    sk.shape(pts, fill=color)


def firework(sk, x, y, s):
    m = _m(x, y, s)
    colors = [RED, BLUE, ORANGE, GREEN, YELLOW]
    rot = sk.rng.uniform(0, 1)
    for i in range(12):
        a = rot + i * math.pi / 6
        c = colors[i % len(colors)]
        sk.line(m(50 + 14 * math.cos(a), 50 + 14 * math.sin(a)),
                m(50 + 38 * math.cos(a), 50 + 38 * math.sin(a)), width=2.6, amp=0.4, color=c)
        sk.dot(*m(50 + 45 * math.cos(a), 50 + 45 * math.sin(a)), s * 0.025, color=c)


# ---- spring / easter / 17. mai ----

def egg(sk, x, y, s, color=YELLOW, band=RED):
    m = _m(x, y, s)
    pts = [m(50 + 30 * math.cos(a), 58 + (40 if math.sin(a) < 0 else 32) * math.sin(a))
           for a in [2 * math.pi * i / 36 for i in range(36)]]
    sk.shape(pts, fill=color)
    zig = [m(23 + 54 * i / 8, 54 + (6 if i % 2 else -6)) for i in range(9)]
    sk.stroke(zig, width=2.6, amp=0, color=band)
    for dx in (36, 50, 64):
        sk.dot(*m(dx, 74), s * 0.035, color=BLUE)


def chick(sk, x, y, s):
    m = _m(x, y, s)
    for lx in (42, 56):
        sk.line(m(lx, 84), m(lx, 94), width=2, amp=0, color=ORANGE)
        sk.line(m(lx, 94), m(lx + 6, 94), width=2, amp=0, color=ORANGE)
    sk.shape(_ell(m, 46, 64, 30, 24), fill=YELLOW)
    sk.shape(_ell(m, 64, 36, 18, 17), fill=YELLOW)
    sk.shape(_pts(m, [(80, 34), (92, 39), (80, 43)]), fill=ORANGE, width=1.4, amp=0)
    sk.dot(*m(68, 32), s * 0.03)
    sk.stroke(_pts(m, [(28, 60), (38, 72), (50, 66)]), width=1.6, amp=0.3)  # wing


def tulip(sk, x, y, s, color=RED):
    m = _m(x, y, s)
    sk.stroke(_pts(m, [(50, 52), (49, 74), (50, 96)]), width=3, amp=0.4, color=GREEN)
    sk.shape(_pts(m, [(50, 92), (30, 64), (36, 60), (50, 84)]), fill=GREEN, width=1.5)
    cup = [(28, 18), (39, 32), (50, 14), (61, 32), (72, 18), (72, 40)]
    cup += [(50 + 22 * math.cos(a), 40 + 20 * math.sin(a)) for a in [math.pi * i / 10 for i in range(1, 10)]]
    sk.shape(_pts(m, cup + [(28, 40)]), fill=color)


def flower(sk, x, y, s, color=BLUE):
    m = _m(x, y, s)
    sk.stroke(_pts(m, [(50, 52), (52, 74), (50, 96)]), width=3, amp=0.4, color=GREEN)
    sk.shape(_ell(m, 64, 78, 12, 5, n=14, rot=-0.5), fill=GREEN, width=1.4)
    for i in range(5):
        a = -math.pi / 2 + i * 2 * math.pi / 5
        sk.shape(_ell(m, 50 + 17 * math.cos(a), 36 + 17 * math.sin(a), 13, 13, n=16), fill=color, width=1.6)
    sk.shape(_ell(m, 50, 36, 10, 10, n=16), fill=YELLOW, width=1.6)


def flag(sk, x, y, s):
    m = _m(x, y, s)
    sk.line(m(20, 8), m(20, 96), width=2.4, amp=0.3)
    x0, y0, u = 20, 12, 3.0  # Norwegian flag: 22 x 16 units
    sk.fill(_pts(m, [(x0, y0), (x0 + 22 * u, y0), (x0 + 22 * u, y0 + 16 * u), (x0, y0 + 16 * u)]), RED)
    for (a0, a1, c) in ((6, 10, WHITE), (7, 9, BLUE)):
        sk.fill(_pts(m, [(x0 + a0 * u, y0), (x0 + a1 * u, y0), (x0 + a1 * u, y0 + 16 * u), (x0 + a0 * u, y0 + 16 * u)]), c)
        sk.fill(_pts(m, [(x0, y0 + a0 * u), (x0 + 22 * u, y0 + a0 * u), (x0 + 22 * u, y0 + a1 * u), (x0, y0 + a1 * u)]), c)
    sk.fill(_pts(m, [(x0 + 7 * u, y0 + 7 * u), (x0 + 9 * u, y0 + 7 * u), (x0 + 9 * u, y0 + 9 * u), (x0 + 7 * u, y0 + 9 * u)]), BLUE)
    sk.shape(_pts(m, [(x0, y0), (x0 + 22 * u, y0), (x0 + 22 * u, y0 + 16 * u), (x0, y0 + 16 * u)]),
             fill=None, opaque=False)


def balloon(sk, x, y, s, color=RED):
    m = _m(x, y, s)
    sk.stroke(_pts(m, [(50, 74), (54, 82), (46, 90), (50, 98)]), width=1.4, amp=0.3)
    sk.shape(_pts(m, [(46, 76), (54, 76), (50, 70)]), fill=color, width=1.4, amp=0)
    sk.shape(_ell(m, 50, 40, 26, 32), fill=color)
    sk.stroke(_ell(m, 40, 28, 7, 12, n=12, start=3.4)[:4], width=1.5, amp=0)


# ---- summer ----

def sun(sk, x, y, s):
    m = _m(x, y, s)
    for i in range(10):
        a = i * math.pi / 5 + sk.rng.uniform(-0.1, 0.1)
        sk.line(m(50 + 32 * math.cos(a), 50 + 32 * math.sin(a)),
                m(50 + 46 * math.cos(a), 50 + 46 * math.sin(a)), width=3, amp=0.3, color=ORANGE)
    sk.shape(_ell(m, 50, 50, 26, 26), fill=YELLOW)
    _face(sk, m, s, 50, 48, spread=8, smile=7)
    for cx in (36, 64):
        sk.dot(*m(cx, 58), s * 0.035, color=ORANGE)


def strawberry(sk, x, y, s):
    m = _m(x, y, s)
    right, left = [], []
    for i in range(17):
        t = i / 16
        w = 30 * (1 - t ** 1.6) ** 0.7 * (0.75 + 0.25 * min(1, t * 4))
        right.append(m(50 + w, 28 + 64 * t))
        left.append(m(50 - w, 28 + 64 * t))
    sk.shape(right + left[::-1], fill=RED)
    for sx, sy in ((40, 42), (58, 40), (50, 54), (36, 60), (62, 60), (46, 72), (56, 78)):
        sk.dot(*m(sx, sy), s * 0.02, color=YELLOW)
    sk.shape(_pts(m, star_pts(50, 28, 18, 6, squash=0.5)), fill=GREEN, width=1.5, amp=0.2)
    sk.line(m(50, 24), m(53, 12), width=2, amp=0.2)


def icecream(sk, x, y, s):
    m = _m(x, y, s)
    sk.shape(_pts(m, [(30, 50), (70, 50), (50, 97)]), fill=ORANGE)
    for d in (0, 12):
        sk.line(m(36 + d, 54), m(56 + d * 0.3, 80), width=1.1, amp=0)
        sk.line(m(64 - d, 54), m(44 - d * 0.3, 80), width=1.1, amp=0)
    sk.shape(_ell(m, 50, 40, 22, 20), fill=YELLOW)
    sk.shape(_ell(m, 52, 16, 6, 6, n=12), fill=RED, width=1.5)


# ---- themes ----

def easter_sunday(year):
    """Anonymous Gregorian algorithm."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    mm = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * mm + 114) // 31
    day = ((h + l - 7 * mm + 114) % 31) + 1
    return datetime.date(year, month, day)


def theme_for(d):
    m, day = d.month, d.day
    easter = easter_sunday(d.year)
    if (m == 12 and day >= 27) or (m == 1 and day <= 2):
        return [firework, star, partial(firework), heart]
    if m == 12:
        return [tree, gift, star, snowman, partial(gift, color=BLUE, ribbon=RED), snowflake]
    if easter - datetime.timedelta(days=7) <= d <= easter + datetime.timedelta(days=1):
        return [egg, chick, partial(egg, color=ORANGE, band=BLUE), partial(tulip, color=YELLOW), chick]
    if m == 5 and 10 <= day <= 17:
        return [flag, balloon, partial(balloon, color=BLUE), icecream, flag]
    if m == 2 and 10 <= day <= 14:
        return [heart, partial(heart, color=ORANGE), flower, heart]
    if (m == 10 and day >= 24) or (m == 11 and day == 1):
        return [partial(pumpkin, face=True), ghost, pumpkin, leaf, partial(leaf, color=RED)]
    if m in (1, 2) or (m == 11 and day >= 20):
        return [snowman, snowflake, mitten, partial(snowflake, color=BLUE), star]
    if m in (3, 4, 5):
        return [tulip, partial(flower, color=BLUE), partial(tulip, color=ORANGE), chick, partial(flower, color=RED)]
    if m in (6, 7, 8):
        return [sun, strawberry, icecream, partial(flower, color=RED), strawberry]
    return [leaf, mushroom, partial(leaf, color=RED), apple, pumpkin, partial(leaf, color=YELLOW)]


# ---- placement in empty space ----

CELL = 4  # px per occupancy cell


def _free_squares(sk, size, margin):
    """All top-left positions (on the cell grid) where a size x size square is free."""
    gw, gh = sk.w // CELL, sk.h // CELL
    grid = sk.occupied.resize((gw, gh), resample=Image.BOX).load()
    # summed-area table of occupied cells
    sat = [[0] * (gw + 1) for _ in range(gh + 1)]
    for j in range(gh):
        row = 0
        for i in range(gw):
            row += 1 if grid[i, j] else 0
            sat[j + 1][i + 1] = sat[j][i + 1] + row
    n = size // CELL
    m0 = margin // CELL
    out = []
    for j in range(m0, gh - n - m0 + 1):
        for i in range(m0, gw - n - m0 + 1):
            if sat[j + n][i + n] - sat[j][i + n] - sat[j + n][i] + sat[j][i] == 0:
                out.append((i * CELL, j * CELL))
    return out


def decorate(sk, date, max_doodles=5, sizes=(76, 64, 52, 44), margin=8, gap=14):
    """Fill empty white areas with seasonal doodles. Returns the number placed."""
    doodles = theme_for(date)
    rng = sk.rng
    placed = 0
    for size in sizes:
        while placed < max_doodles:
            spots = _free_squares(sk, size + 2 * gap, margin)
            if not spots:
                break
            fx, fy = rng.choice(spots)
            x, y = fx + gap, fy + gap
            doodles[placed % len(doodles)](sk, x, y, size)
            sk.mark((x, y, x + size, y + size), pad=gap)
            placed += 1
    return placed
