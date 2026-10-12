"""Hand-drawn style drawing primitives and weather icons.

Everything is drawn at SCALE x resolution on two layers:
  - ink:   greyscale layer for black line art and text (antialiased, thresholded on flatten)
  - color: RGB layer for flat fills using only the exact e-paper palette colors
On flatten the layers are downscaled and combined, so the result contains nothing
but pure palette colors and maps 1:1 to the 7-color panel without dithering.
"""
import math
import random
from PIL import Image, ImageDraw, ImageFont

SCALE = 2

# Waveshare 7.3" F palette (must match pil_to_waveshare_7in3f_raw in main.py)
BLACK  = (0, 0, 0)
WHITE  = (255, 255, 255)
GREEN  = (0, 255, 0)
BLUE   = (0, 0, 255)
RED    = (255, 0, 0)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
PALETTE = [BLACK, WHITE, GREEN, BLUE, RED, YELLOW, ORANGE]


class Font:
    """TrueType font loaded at SCALE x size; measurements are returned in 1x pixels."""
    def __init__(self, path, size):
        self.size = size
        self.pil = ImageFont.truetype(path, size * SCALE)

    def width(self, text):
        return self.pil.getlength(text) / SCALE


def ellipse_pts(cx, cy, rx, ry, n=32, start=0.0, rot=0.0):
    pts = []
    for i in range(n):
        a = start + 2 * math.pi * i / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        pts.append((cx + x * math.cos(rot) - y * math.sin(rot),
                    cy + x * math.sin(rot) + y * math.cos(rot)))
    return pts


def star_pts(cx, cy, r_out, r_in, points=5, rot=-math.pi / 2, squash=1.0):
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + math.pi * i / points
        pts.append((cx + r * math.cos(a), cy + r * squash * math.sin(a)))
    return pts


class Sketch:
    def __init__(self, w, h, seed=0):
        self.w, self.h = w, h
        self.ink = Image.new('L', (w * SCALE, h * SCALE), 255)
        self.color = Image.new('RGB', (w * SCALE, h * SCALE), WHITE)
        self.di = ImageDraw.Draw(self.ink)
        self.dc = ImageDraw.Draw(self.color)
        self.rng = random.Random(seed)
        # 1x occupancy mask: everything drawn is marked so doodles can find empty space
        self.occupied = Image.new('L', (w, h), 0)
        self.do = ImageDraw.Draw(self.occupied)

    # ---- bookkeeping ----
    def mark(self, box, pad=0):
        x0, y0, x1, y1 = box
        self.do.rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], fill=255)

    # ---- geometry helpers ----
    @staticmethod
    def _densify(pts, step=3.0):
        out = []
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step))
            for i in range(n):
                t = i / n
                out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
        out.append(pts[-1])
        return out

    def _jitter(self, pts, amp):
        """Offset points perpendicular to the path by smooth noise, like an unsteady hand."""
        if amp <= 0 or len(pts) < 2:
            return pts
        r = self.rng
        p1, p2 = r.uniform(0, 2 * math.pi), r.uniform(0, 2 * math.pi)
        f1, f2 = r.uniform(0.04, 0.08), r.uniform(0.14, 0.24)
        out, s = [], 0.0
        for i, (x, y) in enumerate(pts):
            if i:
                s += math.hypot(x - pts[i - 1][0], y - pts[i - 1][1])
            ax, ay = pts[max(i - 1, 0)]
            bx, by = pts[min(i + 1, len(pts) - 1)]
            dx, dy = bx - ax, by - ay
            ln = math.hypot(dx, dy) or 1.0
            o = amp * (0.65 * math.sin(f1 * s + p1) + 0.35 * math.sin(f2 * s + p2))
            out.append((x - dy / ln * o, y + dx / ln * o))
        return out

    @staticmethod
    def _scaled(pts, dx=0.0, dy=0.0):
        return [((x + dx) * SCALE, (y + dy) * SCALE) for x, y in pts]

    # ---- drawing ----
    def stroke(self, pts, width=2.0, amp=0.8, closed=False, color=None):
        """Wobbly pen stroke through pts. color=None draws black ink, else a palette color."""
        pts = list(pts)
        if closed:
            # Overshoot slightly past the start, like closing a shape by hand
            dense = self._densify(pts + [pts[0]])
            dense += dense[1:4]
        else:
            dense = self._densify(pts)
        dense = self._jitter(dense, amp)
        sp = self._scaled(dense)
        w = max(1, int(round(width * SCALE)))
        draw, fill = (self.di, 0) if color is None else (self.dc, color)
        draw.line(sp, fill=fill, width=w, joint='curve')
        r = w / 2
        for x, y in (sp[0], sp[-1]):
            draw.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def line(self, p0, p1, width=2.0, amp=0.8, color=None):
        self.stroke([p0, p1], width=width, amp=amp, color=color)

    def fill(self, pts, color, offset=(0.0, 0.0)):
        """Flat palette-color fill without outline."""
        self.dc.polygon(self._scaled(pts, *offset), fill=color)

    def shape(self, pts, fill=None, width=2.0, amp=0.7, opaque=True, outline=True):
        """Filled shape with a hand-drawn outline. opaque erases ink underneath (overlapping parts)."""
        if opaque:
            self.di.polygon(self._scaled(pts), fill=255)
        if fill is not None:
            # A tiny misregistration between fill and outline gives a coloured-pencil feel
            self.fill(pts, fill, offset=(self.rng.uniform(-0.6, 0.6), self.rng.uniform(-0.6, 0.6)))
        if outline:
            self.stroke(pts, width=width, amp=amp, closed=True)

    def ink_fill(self, pts):
        self.di.polygon(self._scaled(pts), fill=0)

    def dot(self, cx, cy, r, color=None):
        box = [(cx - r) * SCALE, (cy - r) * SCALE, (cx + r) * SCALE, (cy + r) * SCALE]
        if color is None:
            self.di.ellipse(box, fill=0)
        else:
            self.dc.ellipse(box, fill=color)

    def text(self, xy, text, font, anchor='ls', mark_pad=3):
        x, y = xy
        self.di.text((x * SCALE, y * SCALE), text, font=font.pil, fill=0, anchor=anchor)
        bx = self.di.textbbox((x * SCALE, y * SCALE), text, font=font.pil, anchor=anchor)
        box = tuple(v / SCALE for v in bx)
        self.mark(box, pad=mark_pad)
        return box

    def flatten(self):
        color = self.color.resize((self.w, self.h), Image.NEAREST)
        ink = self.ink.resize((self.w, self.h), Image.BOX)
        mask = ink.point(lambda v: 255 if v < 150 else 0)
        color.paste(BLACK, mask=mask)
        return color


# ---------------------------------------------------------------------------
# Weather icons (black ink only), drawn into the square box (x, y, s)
# ---------------------------------------------------------------------------

def _sun(sk, cx, cy, r, rays=True):
    sk.shape(ellipse_pts(cx, cy, r, r, n=28, start=sk.rng.uniform(0, 6)), fill=None, width=2)
    if rays:
        for i in range(8):
            a = i * math.pi / 4 + sk.rng.uniform(-0.12, 0.12)
            r0, r1 = r * 1.45, r * (1.9 + sk.rng.uniform(-0.12, 0.12))
            sk.line((cx + r0 * math.cos(a), cy + r0 * math.sin(a)),
                    (cx + r1 * math.cos(a), cy + r1 * math.sin(a)), width=1.8, amp=0.3)


def _moon(sk, cx, cy, r):
    """Crescent: points of the outer disc outside a shifted disc, then back along the inner disc."""
    ox, oy, ir = cx + r * 0.55, cy - r * 0.35, r * 0.85
    n = 120
    outer = [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    inner = [(ox + ir * math.cos(2 * math.pi * i / n), oy + ir * math.sin(2 * math.pi * i / n)) for i in range(n)]
    out_keep = [math.hypot(x - ox, y - oy) > ir for x, y in outer]
    in_keep = [math.hypot(x - cx, y - cy) < r for x, y in inner]

    def run(pts, keep):
        # rotate so the kept run is contiguous
        start = next(i for i in range(n) if keep[i] and not keep[i - 1])
        seq = pts[start:] + pts[:start]
        k = keep[start:] + keep[:start]
        return [p for p, kk in zip(seq, k) if kk]

    a, b = run(outer, out_keep), run(inner, in_keep)
    if math.hypot(a[-1][0] - b[0][0], a[-1][1] - b[0][1]) > math.hypot(a[-1][0] - b[-1][0], a[-1][1] - b[-1][1]):
        b = b[::-1]
    sk.shape(a + b, fill=None, width=2)


def _cloud(sk, cx, cy, w, h):
    """Bumpy cloud with flat base; (cx, cy) is the centre of its bounding box."""
    base = cy + h / 2
    circles = [(cx - 0.27 * w, base - 0.23 * w, 0.23 * w),
               (cx + 0.02 * w, base - 0.34 * w, 0.32 * w),
               (cx + 0.29 * w, base - 0.20 * w, 0.20 * w)]
    pts = []
    for (ccx, ccy, r) in circles:
        for i in range(48):
            a = 2 * math.pi * i / 48
            x, y = ccx + r * math.cos(a), ccy + r * math.sin(a)
            if y > base:
                continue
            if any(math.hypot(x - ox, y - oy) < orr - 0.3 for (ox, oy, orr) in circles if (ox, oy, orr) != (ccx, ccy, r)):
                continue
            pts.append((x, y))
    x_left, x_right = circles[0][0], circles[2][0]
    for i in range(1, 12):
        pts.append((x_left + (x_right - x_left) * i / 12, base))
    ccx, ccy = cx, base - 0.2 * w
    pts.sort(key=lambda p: math.atan2(p[1] - ccy, p[0] - ccx))
    sk.shape(pts, fill=WHITE, width=2)


def _drops(sk, x0, x1, y, kind, count):
    step = (x1 - x0) / max(count, 1)
    for i in range(count):
        px = x0 + step * (i + 0.5) + sk.rng.uniform(-1, 1)
        py = y + (i % 2) * 4
        k = kind if kind != 'sleet' else ('rain' if i % 2 == 0 else 'snow')
        if k == 'rain':
            sk.line((px + 2, py), (px - 1.5, py + 8), width=2, amp=0.2)
        else:
            for a in (0, math.pi / 3, 2 * math.pi / 3):
                dx, dy = 3.6 * math.cos(a), 3.6 * math.sin(a)
                sk.line((px + 0.5 - dx, py + 4 - dy), (px + 0.5 + dx, py + 4 + dy), width=1.5, amp=0)


def _bolt(sk, x, y, s):
    pts = [(x + 0.55 * s, y), (x + 0.15 * s, y + 0.55 * s), (x + 0.45 * s, y + 0.55 * s),
           (x + 0.3 * s, y + s), (x + 0.85 * s, y + 0.38 * s), (x + 0.55 * s, y + 0.38 * s), (x + 0.75 * s, y)]
    sk.di.polygon(sk._scaled(pts), fill=255)
    sk.ink_fill(pts)


def weather_icon(sk, code, x, y, s):
    """Draw a hand-drawn icon for a Met.no symbol_code in the box (x, y, s, s)."""
    sk.mark((x, y, x + s, y + s), pad=2)
    code = code or 'cloudy'
    base, _, variant = code.partition('_')
    night = variant == 'night'
    cx, cy = x + s / 2, y + s / 2

    if base == 'clearsky':
        if night:
            _moon(sk, cx, cy, s * 0.32)
        else:
            _sun(sk, cx, cy, s * 0.22)
        return
    if base == 'fog':
        for i in range(3):
            yy = y + s * (0.3 + 0.2 * i)
            pts = [(x + s * (0.12 + 0.76 * t / 10), yy + 2.2 * math.sin(t * 1.3 + i)) for t in range(11)]
            sk.stroke(pts, width=2, amp=0.3)
        return
    if base in ('fair', 'partlycloudy'):
        r = s * (0.2 if base == 'fair' else 0.17)
        if night:
            _moon(sk, x + s * 0.36, y + s * 0.34, r * 1.25)
        else:
            _sun(sk, x + s * 0.36, y + s * 0.36, r)
        cw = s * (0.5 if base == 'fair' else 0.66)
        _cloud(sk, x + s * 0.62, y + s * 0.66, cw, cw * 0.55)
        return
    if base == 'cloudy':
        _cloud(sk, x + s * 0.62, y + s * 0.38, s * 0.5, s * 0.28)
        _cloud(sk, x + s * 0.44, y + s * 0.62, s * 0.78, s * 0.42)
        return

    # Precipitation: rain/sleet/snow, possibly showers and/or thunder
    kind = 'snow' if 'snow' in base else 'sleet' if 'sleet' in base else 'rain'
    intensity = 1 if base.startswith('light') else 3 if base.startswith('heavy') else 2
    if 'showers' in base:
        if night:
            _moon(sk, x + s * 0.26, y + s * 0.2, s * 0.19)
        else:
            _sun(sk, x + s * 0.24, y + s * 0.22, s * 0.14)
    _cloud(sk, x + s * 0.54, y + s * 0.38, s * 0.74, s * 0.4)
    if 'thunder' in base:
        _bolt(sk, x + s * 0.42, y + s * 0.6, s * 0.36)
        _drops(sk, x + s * 0.16, x + s * 0.42, y + s * 0.66, kind, 1 + intensity // 2)
    else:
        _drops(sk, x + s * 0.2, x + s * 0.88, y + s * 0.64, kind, intensity + 1)
