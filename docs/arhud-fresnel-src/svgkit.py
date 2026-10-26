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

# ---- Additions for the Fresnel document ---------------------------------------------------
PURPLE = "#7b4fc9"; RED = "#d03b3b"; TEAL = "#0b7a5c"; TEAL_T = "#e8f3ef"
RGB = ("#d23c3c", "#1f9d3a", "#2a5fd6")   # red, green, blue primaries for colour figures
ACRYLIC = "#dcebf7"; ACRYLIC_S = "#5f8fbf"

def _pl(pts):
    return "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts)

def polyline(s, pts, stroke=INK, sw=1, extra="", fill="none"):
    s.add(f'<path d="{_pl(pts)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
          f'stroke-linejoin="round" stroke-linecap="round" {extra}/>')

def dim(s, x1, y1, x2, y2, label, off=0, size=11, color=INK2, sw=0.9, text_off=None, anchor="middle", weight=500, ext=True):
    """Dimension line between two points, offset perpendicular by off, with end ticks and a label."""
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L
    ax1, ay1 = x1 + nx * off, y1 + ny * off
    ax2, ay2 = x2 + nx * off, y2 + ny * off
    if ext and off:
        s.line(x1 + nx * (2 if off > 0 else -2), y1 + ny * (2 if off > 0 else -2), ax1 + nx * (3 if off > 0 else -3), ay1 + ny * (3 if off > 0 else -3), stroke=color, sw=0.6)
        s.line(x2 + nx * (2 if off > 0 else -2), y2 + ny * (2 if off > 0 else -2), ax2 + nx * (3 if off > 0 else -3), ay2 + ny * (3 if off > 0 else -3), stroke=color, sw=0.6)
    s.line(ax1, ay1, ax2, ay2, stroke=color, sw=sw)
    for (px, py) in ((ax1, ay1), (ax2, ay2)):
        s.line(px - nx * 4 - dx / L * 0, py - ny * 4, px + nx * 4, py + ny * 4, stroke=color, sw=sw)
    to = (8 + size * 0.2) if text_off is None else text_off
    mx, my = (ax1 + ax2) / 2 + nx * to, (ay1 + ay2) / 2 + ny * to
    ang = math.degrees(math.atan2(dy, dx))
    if ang > 90 or ang < -90:
        ang += 180
    if abs(ang) < 0.01:
        s.text(mx, my + size * 0.35, label, size=size, fill=color, anchor=anchor, weight=weight)
    else:
        s.text(mx, my + size * 0.35, label, size=size, fill=color, anchor=anchor, weight=weight,
               extra=f'transform="rotate({ang:.2f} {mx:.2f} {my + size*0.35:.2f})"')

def arc(s, cx, cy, r, a0, a1, color=INK, sw=1, label=None, size=11, lr=None, weight=500, fill=None):
    """Angle arc in SVG coordinates; angles in degrees measured counter-clockwise from +x on screen (y up)."""
    def pt(a):
        return cx + r * math.cos(math.radians(a)), cy - r * math.sin(math.radians(a))
    x0, y0 = pt(a0); x1, y1 = pt(a1)
    large = 1 if abs(a1 - a0) > 180 else 0
    sweep = 0 if a1 > a0 else 1
    s.path(f"M{x0:.2f},{y0:.2f} A{r},{r} 0 {large} {sweep} {x1:.2f},{y1:.2f}", stroke=color, sw=sw)
    if label:
        am = (a0 + a1) / 2; rr = lr or r + 12
        lx, ly = cx + rr * math.cos(math.radians(am)), cy - rr * math.sin(math.radians(am))
        s.text(lx, ly + size * 0.35, label, size=size, fill=fill or color, anchor="middle", weight=weight)

class Axes:
    """Linear plot frame: data -> pixels, with grid, ticks and labels."""
    def __init__(self, s, x, y, w, h, xr, yr, xlog=False, ylog=False):
        self.s, self.x, self.y, self.w, self.h = s, x, y, w, h
        self.xr, self.yr, self.xlog, self.ylog = xr, yr, xlog, ylog
    def _t(self, v, r, log):
        if log:
            return (math.log10(v) - math.log10(r[0])) / (math.log10(r[1]) - math.log10(r[0]))
        return (v - r[0]) / (r[1] - r[0])
    def X(self, v):
        return self.x + self._t(v, self.xr, self.xlog) * self.w
    def Y(self, v):
        return self.y + self.h - self._t(v, self.yr, self.ylog) * self.h
    def P(self, x, y):
        return self.X(x), self.Y(y)
    def frame(self, xt, yt, xfmt="{:g}", yfmt="{:g}", xlabel="", ylabel="", size=11, grid=True):
        s = self.s
        s.rect(self.x, self.y, self.w, self.h, fill="#ffffff", stroke=AXIS, sw=1)
        for v in xt:
            px = self.X(v)
            if grid:
                s.line(px, self.y, px, self.y + self.h, stroke=GRID, sw=0.8)
            s.text(px, self.y + self.h + 15, xfmt.format(v), size=size, fill=INK2, anchor="middle")
        for v in yt:
            py = self.Y(v)
            if grid:
                s.line(self.x, py, self.x + self.w, py, stroke=GRID, sw=0.8)
            s.text(self.x - 6, py + 4, yfmt.format(v), size=size, fill=INK2, anchor="end")
        s.rect(self.x, self.y, self.w, self.h, fill="none", stroke=AXIS, sw=1)
        if xlabel:
            s.text(self.x + self.w / 2, self.y + self.h + 33, xlabel, size=size + 0.5, fill=INK, anchor="middle", weight=500)
        if ylabel:
            cx, cy = self.x - 44, self.y + self.h / 2
            s.text(cx, cy, ylabel, size=size + 0.5, fill=INK, anchor="middle", weight=500,
                   extra=f'transform="rotate(-90 {cx:.1f} {cy:.1f})"')
    def curve(self, pts, stroke=BLUE, sw=2, extra=""):
        polyline(self.s, [self.P(x, y) for x, y in pts], stroke=stroke, sw=sw, extra=extra)
    def clip_curve(self, pts, stroke=BLUE, sw=2, extra=""):
        seg = []
        for x, y in pts:
            if self.yr[0] <= y <= self.yr[1] and self.xr[0] <= x <= self.xr[1]:
                seg.append(self.P(x, y))
            else:
                if len(seg) > 1:
                    polyline(self.s, seg, stroke=stroke, sw=sw, extra=extra)
                seg = []
        if len(seg) > 1:
            polyline(self.s, seg, stroke=stroke, sw=sw, extra=extra)

def legend(s, x, y, items, size=11, dy=18, sw=2.4):
    for i, (label, color) in enumerate(items):
        yy = y + i * dy
        s.line(x, yy - 4, x + 22, yy - 4, stroke=color, sw=sw)
        s.text(x + 28, yy, label, size=size, fill=INK)

def note(s, x, y, lines_, size=11, fill=INK2, lh=None, weight=400, anchor="start"):
    s.lines(x, y, lines_, size=size, fill=fill, lh=lh, weight=weight, anchor=anchor)

def step(s, x, y, label, title, size=13, sub=None):
    """Panel heading: a teal letter chip and a bold title (y is the text baseline)."""
    s.rect(x, y - size - 1, size + 9, size + 7, fill=TEAL, rx=3)
    s.text(x + (size + 9) / 2, y + 1, label, size=size - 1, weight=700, fill="#ffffff", anchor="middle")
    s.text(x + size + 16, y, title, size=size, weight=700)
    if sub:
        s.text(x + size + 16, y + 17, sub, size=10.5, fill=INK2)
