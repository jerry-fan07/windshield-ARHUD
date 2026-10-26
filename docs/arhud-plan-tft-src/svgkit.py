"""Tiny SVG toolkit. Every figure is a plain inline <svg>; text inherits the CSS font."""
from xml.sax.saxutils import escape
import math

INK = "#0b0b0b"; INK2 = "#52514e"; MUTED = "#898781"
GRID = "#e1e0d9"; AXIS = "#c3c2b7"; SURF = "#fcfcfb"
BLUE = "#2a78d6"; ORANGE = "#eb6834"; GREEN = "#008300"; CRIT = "#d03b3b"
BLUE_T = "#e8f1fc"; ORANGE_T = "#fdf0e9"; GREEN_T = "#e6f3e6"; GREY_T = "#f2f1ed"
FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"

REG = {}
def fig(name):
    def deco(fn):
        REG[name] = fn
        return fn
    return deco

class Svg:
    _uid = 0
    def __init__(self, w, h, label):
        Svg._uid += 1
        self.uid = Svg._uid
        self.w, self.h, self.label = w, h, label
        self.body = []
        self.markers = {}

    def _marker(self, color):
        if color not in self.markers:
            self.markers[color] = f"ah{self.uid}_{len(self.markers)}"
        return self.markers[color]

    def add(self, s):
        self.body.append(s)

    def text(self, x, y, s, size=12, weight=400, fill=INK, anchor="start", extra=""):
        self.body.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" {extra}>{escape(s)}</text>')

    def lines(self, x, y, items, size=12, weight=400, fill=INK, anchor="start", lh=None):
        lh = lh or size * 1.35
        for i, s in enumerate(items):
            self.text(x, y + i * lh, s, size, weight, fill, anchor)

    def rect(self, x, y, w, h, fill="none", stroke="none", sw=1, rx=0, extra=""):
        self.body.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')

    def line(self, x1, y1, x2, y2, stroke=INK, sw=1, extra=""):
        self.body.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" {extra}/>')

    def arrow(self, x1, y1, x2, y2, color=INK, sw=1.5):
        mid = self._marker(color)
        self.body.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" '
            f'stroke-width="{sw}" stroke-linecap="round" marker-end="url(#{mid})"/>')

    def path(self, d, fill="none", stroke="none", sw=1, extra=""):
        self.body.append(
            f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linejoin="round" stroke-linecap="round" {extra}/>')

    def poly(self, pts, fill="none", stroke="none", sw=1, extra=""):
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
        self.path(d, fill, stroke, sw, extra)

    def circle(self, cx, cy, r, fill=INK, stroke="none", sw=1):
        self.body.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def pill(self, x, y, s, size=11.5, fill=SURF, stroke=AXIS, anchor="start", weight=500):
        w = len(s) * size * 0.56 + 14
        x0 = x if anchor == "start" else (x - w / 2 if anchor == "middle" else x - w)
        self.rect(x0, y - size - 4, w, size + 9, fill=fill, stroke=stroke, sw=0.8, rx=4)
        self.text(x0 + 7, y + 1, s, size=size, weight=weight, fill=INK)
        return w

    def render(self):
        defs = []
        for color, mid in self.markers.items():
            defs.append(
                f'<marker id="{mid}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" '
                f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
                f'fill="{color}"/></marker>')
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
                f'width="100%" role="img" aria-label="{escape(self.label)}" '
                f'font-family="{FONT}">')
        defs_s = f"<defs>{''.join(defs)}</defs>" if defs else ""
        return head + f"<title>{escape(self.label)}</title>" + defs_s + "".join(self.body) + "</svg>"

def ticks(a, b, n):
    return [a + (b - a) * i / n for i in range(n + 1)]
