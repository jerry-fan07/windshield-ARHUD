"""The HUD's content, drawn as light (premultiplied linear RGB) at 2x and box-filtered down.

Two layers, because they move differently on the retina:
  world  - locked to the rack through the plane homographies: the target-port brackets, its label, the
           confirmation outline. Gets the camera's motion blur when the head moves.
  head   - fixed in the display: the one-line instruction and the edge chevron toward a target that is outside the
           display's field of view.

Visual language: one pale cyan for everything, green only for "done", Inter SemiBold, no panels, no backgrounds
(an optical see-through display cannot draw dark anyway), nothing over the hands' working area except the brackets.
"""
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SS = 2  # supersampling factor
FONT_DIRS = ["/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/inter", os.path.expanduser("~/.fonts")]
CYAN = (0.78, 0.94, 1.00)
GREEN = (0.50, 1.00, 0.62)
AMBER = (1.00, 0.78, 0.40)


def font(size, weight="SemiBold"):
    for d in FONT_DIRS:
        for name in (f"Inter-{weight}.otf", f"Inter-{weight}.ttf", "Inter-Medium.otf"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                return ImageFont.truetype(p, int(round(size * SS)))
    return ImageFont.truetype("DejaVuSans.ttf", int(round(size * SS)))


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0) if b != a else float(x >= b)
    return t * t * (3 - 2 * t)


class Layer:
    """One HUD layer: PIL coverage canvases per colour, merged into premultiplied linear light."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.inks = {}

    def draw(self, color):
        if color not in self.inks:
            im = Image.new("L", (self.w * SS, self.h * SS), 0)
            self.inks[color] = (im, ImageDraw.Draw(im))
        return self.inks[color][1]

    def light(self):
        """Full-frame light, filled only inside the drawn bounding box (self.bbox, display px, or None)."""
        out = np.zeros((self.h, self.w, 3), np.float32)
        self.bbox = None
        for color, (im, _) in self.inks.items():
            bb = im.getbbox()
            if bb is None:
                continue
            x0, y0 = (bb[0] // (2 * SS)) * 2, (bb[1] // (2 * SS)) * 2
            x1, y1 = min(self.w, -(-bb[2] // SS) + 1), min(self.h, -(-bb[3] // SS) + 1)
            a = np.asarray(im.crop((x0 * SS, y0 * SS, x1 * SS, y1 * SS)), np.float32) / 255.0
            a = cv2.resize(a, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
            out[y0:y1, x0:x1] += a[..., None] * np.array(color, np.float32)
            self.bbox = (x0, y0, x1, y1) if self.bbox is None else (
                min(self.bbox[0], x0), min(self.bbox[1], y0), max(self.bbox[2], x1), max(self.bbox[3], y1))
        return out


def _s(p):
    return (float(p[0]) * SS, float(p[1]) * SS)


def stroke(d, pts, width, level):
    """Polyline with round joints and caps; level 0..1 is the coverage (i.e. brightness) of this stroke."""
    v = int(round(255 * max(0.0, min(1.0, level))))
    if v <= 0:
        return
    P = [_s(p) for p in pts]
    d.line(P, fill=v, width=max(1, int(round(width * SS))), joint="curve")
    r = width * SS / 2
    for x, y in (P[0], P[-1]):
        d.ellipse([x - r, y - r, x + r, y + r], fill=v)


def text(d, xy, s, fnt, level, anchor="la", spacing=0.0):
    """Text at xy (display px). spacing adds tracking in em (the display wants slightly open letterforms)."""
    v = int(round(255 * max(0.0, min(1.0, level))))
    if v <= 0 or not s:
        return
    x, y = _s(xy)
    if spacing == 0.0:
        d.text((x, y), s, font=fnt, fill=v, anchor=anchor)
        return
    em = fnt.size * spacing
    widths = [fnt.getlength(c) + em for c in s]
    total = sum(widths) - em
    if anchor[0] == "m":
        x -= total / 2
    elif anchor[0] == "r":
        x -= total
    for c, wc in zip(s, widths):
        d.text((x, y), c, font=fnt, fill=v, anchor="l" + anchor[1])
        x += wc


def text_width(s, fnt, spacing=0.0):
    return (sum(fnt.getlength(c) for c in s) + fnt.size * spacing * (len(s) - 1)) / SS


def quad_brackets(d, q, level, width=2.2, leg=0.28, pad=0.22, grow=1.0):
    """Corner brackets on a perspective quad q (4x2: tl, tr, br, bl, display px), padded and scaled about its centre."""
    q = np.asarray(q, np.float64)
    c = q.mean(axis=0)
    q = c + (q - c) * (1 + pad) * grow
    for i in range(4):
        p = q[i]
        a = q[(i + 1) % 4]
        b = q[(i - 1) % 4]
        stroke(d, [p + (a - p) * leg, p, p + (b - p) * leg], width, level)


def quad_outline(d, q, level, width=2.2, pad=0.22):
    q = np.asarray(q, np.float64)
    c = q.mean(axis=0)
    q = c + (q - c) * (1 + pad)
    stroke(d, list(q) + [q[0]], width, level)


def check(d, at, size, level, width=2.4):
    x, y = at
    stroke(d, [(x - 0.45 * size, y), (x - 0.12 * size, y + 0.32 * size), (x + 0.5 * size, y - 0.38 * size)], width, level)


def chevron(d, at, angle, size, level, width=2.4):
    """A '>' pointing along angle (radians), centred at `at`."""
    x, y = at
    ca, sa = math.cos(angle), math.sin(angle)

    def r(u, v):
        return (x + u * ca - v * sa, y + u * sa + v * ca)
    stroke(d, [r(-0.35 * size, -0.6 * size), r(0.35 * size, 0.0), r(-0.35 * size, 0.6 * size)], width, level)
