"""A small drawing layer over OpenCV for the PGU frame and the panels.

The PGU frame is emitted light on black, so elements combine with a per-channel maximum ("lighten") instead of
alpha-over: a faded line over the ribbon never darkens it. Colours are given as RGB 0-255 and stored BGR, which is
also the byte order Panda3D expects for its textures. Text is Helvetica Neue, rendered once per string and size with
PIL and cached.
"""
import functools

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_FILE = "/System/Library/Fonts/HelveticaNeue.ttc"
FACES = {"regular": 0, "bold": 1, "medium": 10, "light": 7, "condensed": 4, "black": 9}


@functools.lru_cache(maxsize=64)
def font(size, face="bold"):
    try:
        return ImageFont.truetype(FONT_FILE, size, index=FACES.get(face, 1))
    except OSError:
        return ImageFont.load_default()


@functools.lru_cache(maxsize=2048)
def text_mask(text, size, face="bold"):
    """Coverage mask (uint8) of `text`, plus the row of its baseline in the mask."""
    f = font(size, face)
    l, t, r, b = f.getbbox(text or " ")
    w, h = max(1, r - l + 2), max(1, b - t + 2)
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).text((-l + 1, -t + 1), text, font=f, fill=255)
    asc, desc = f.getmetrics()
    return np.asarray(im), (-t + 1) + asc      # mask, baseline row


def text_size(text, size, face="bold"):
    m, _ = text_mask(text, size, face)
    return m.shape[1], m.shape[0]


class Canvas:
    def __init__(self, w, h, channels=3, mode="max"):
        self.w, self.h, self.c = w, h, channels
        self.img = np.zeros((h, w, channels), np.uint8)
        self.mode = mode
        self._tmp = np.zeros_like(self.img)

    def clear(self, rgb=(0, 0, 0)):
        if rgb == (0, 0, 0):
            self.img.fill(0)
        else:
            self.img[:] = (rgb[2], rgb[1], rgb[0])[: self.c] if self.c >= 3 else rgb[0]
        self._batch = None

    # Batching: primitives drawn between begin() and end() go to the scratch layer and are composited once.
    def begin(self):
        self._batch = [1e9, 1e9, -1e9, -1e9]

    def end(self):
        b = self._batch
        self._batch = None
        if b is not None and b[2] >= b[0]:
            self._composite(*b)

    @staticmethod
    def bgr(rgb, a=1.0):
        return (float(rgb[2]) * a, float(rgb[1]) * a, float(rgb[0]) * a)

    def _composite(self, x0, y0, x1, y1):
        b = getattr(self, "_batch", None)
        if b is not None:
            b[0], b[1] = min(b[0], x0), min(b[1], y0)
            b[2], b[3] = max(b[2], x1), max(b[3], y1)
            return
        x0, y0 = max(0, int(x0)), max(0, int(y0))
        x1, y1 = min(self.w, int(x1) + 1), min(self.h, int(y1) + 1)
        if x1 <= x0 or y1 <= y0:
            return
        a = self.img[y0:y1, x0:x1]
        b = self._tmp[y0:y1, x0:x1]
        if self.mode == "max":
            cv2.max(a, b, dst=a)
        b.fill(0)

    # ---- primitives (all composited with lighten) --------------------------------------------------------------------
    def poly(self, pts, rgb, a=1.0):
        pts = np.asarray(pts, dtype=float)
        if len(pts) < 3 or not np.all(np.isfinite(pts)):
            return
        ip = np.round(pts * 16).astype(np.int32)
        cv2.fillPoly(self._tmp, [ip], self.bgr(rgb, a), cv2.LINE_AA, shift=4)
        self._composite(pts[:, 0].min() - 2, pts[:, 1].min() - 2, pts[:, 0].max() + 2, pts[:, 1].max() + 2)

    def poly_gradient(self, pts, rgb, a_bottom, a_top, y_bottom=None, y_top=None):
        """Filled polygon whose alpha runs linearly from a_bottom at y_bottom to a_top at y_top."""
        pts = np.asarray(pts, dtype=float)
        if len(pts) < 3 or not np.all(np.isfinite(pts)):
            return
        x0, y0 = max(0, int(pts[:, 0].min()) - 2), max(0, int(pts[:, 1].min()) - 2)
        x1, y1 = min(self.w, int(pts[:, 0].max()) + 3), min(self.h, int(pts[:, 1].max()) + 3)
        if x1 <= x0 or y1 <= y0:
            return
        key = (self.h, tuple(int(c) for c in rgb), round(a_bottom, 3), round(a_top, 3), y_bottom, y_top)
        if getattr(self, "_grad_key", None) != key:
            yb = self.h if y_bottom is None else y_bottom
            yt = 0 if y_top is None else y_top
            ys = np.arange(self.h, dtype=np.float32)
            f = np.clip((yb - ys) / max(1e-3, yb - yt), 0, 1)
            al = a_bottom + (a_top - a_bottom) * f
            col = np.array(self.bgr(rgb), np.float32)[: self.c]
            rows = (al[:, None] * col[None, :]).astype(np.uint8)          # H x C
            self._grad = np.ascontiguousarray(np.broadcast_to(rows[:, None, :], (self.h, self.w, self.c)))
            self._grad_key = key
        mask = self._tmp[y0:y1, x0:x1]
        ip = np.round((pts - [x0, y0]) * 16).astype(np.int32)
        cv2.fillPoly(mask, [ip], (255,) * self.c, cv2.LINE_AA, shift=4)
        layer = cv2.multiply(mask, self._grad[y0:y1, x0:x1], scale=1 / 255.0)
        cv2.max(self.img[y0:y1, x0:x1], layer, dst=self.img[y0:y1, x0:x1])
        mask.fill(0)

    def line(self, p0, p1, rgb, a=1.0, width=6):
        if not (np.all(np.isfinite(p0)) and np.all(np.isfinite(p1))):
            return
        w = max(1, int(round(width)))
        cv2.line(self._tmp, (int(round(p0[0] * 16)), int(round(p0[1] * 16))),
                 (int(round(p1[0] * 16)), int(round(p1[1] * 16))), self.bgr(rgb, a), w, cv2.LINE_AA, shift=4)
        self._composite(min(p0[0], p1[0]) - w, min(p0[1], p1[1]) - w, max(p0[0], p1[0]) + w, max(p0[1], p1[1]) + w)

    def polyline(self, pts, rgb, a=1.0, width=6, closed=False):
        pts = np.asarray(pts, dtype=float)
        pts = pts[np.all(np.isfinite(pts), axis=1)]
        if len(pts) < 2:
            return
        w = max(1, int(round(width)))
        cv2.polylines(self._tmp, [np.round(pts * 16).astype(np.int32)], closed, self.bgr(rgb, a), w, cv2.LINE_AA,
                      shift=4)
        self._composite(pts[:, 0].min() - w, pts[:, 1].min() - w, pts[:, 0].max() + w, pts[:, 1].max() + w)

    def circle(self, c, r, rgb, a=1.0, width=4, fill=False):
        cv2.circle(self._tmp, (int(round(c[0] * 16)), int(round(c[1] * 16))), int(round(r * 16)),
                   self.bgr(rgb, a), -1 if fill else max(1, int(width)), cv2.LINE_AA, shift=4)
        self._composite(c[0] - r - width, c[1] - r - width, c[0] + r + width, c[1] + r + width)

    def arc(self, c, r, a0, a1, rgb, a=1.0, width=4):
        cv2.ellipse(self._tmp, (int(round(c[0])), int(round(c[1]))), (int(r), int(r)), 0, a0, a1,
                    self.bgr(rgb, a), max(1, int(width)), cv2.LINE_AA)
        self._composite(c[0] - r - width, c[1] - r - width, c[0] + r + width, c[1] + r + width)

    def rrect(self, x0, y0, x1, y1, r, rgb, a=1.0, width=4, fill=False):
        r = int(max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2)))
        col = self.bgr(rgb, a)
        t = -1 if fill else max(1, int(width))
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        if fill:
            cv2.rectangle(self._tmp, (x0 + r, y0), (x1 - r, y1), col, -1)
            cv2.rectangle(self._tmp, (x0, y0 + r), (x1, y1 - r), col, -1)
            for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)):
                cv2.circle(self._tmp, (cx, cy), r, col, -1, cv2.LINE_AA)
        else:
            cv2.line(self._tmp, (x0 + r, y0), (x1 - r, y0), col, t, cv2.LINE_AA)
            cv2.line(self._tmp, (x0 + r, y1), (x1 - r, y1), col, t, cv2.LINE_AA)
            cv2.line(self._tmp, (x0, y0 + r), (x0, y1 - r), col, t, cv2.LINE_AA)
            cv2.line(self._tmp, (x1, y0 + r), (x1, y1 - r), col, t, cv2.LINE_AA)
            for (cx, cy, ang) in ((x0 + r, y0 + r, 180), (x1 - r, y0 + r, 270), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90)):
                cv2.ellipse(self._tmp, (cx, cy), (r, r), ang, 0, 90, col, t, cv2.LINE_AA)
        self._composite(x0 - width, y0 - width, x1 + width, y1 + width)

    def text(self, s, x, y, size, rgb, a=1.0, face="bold", anchor="lt"):
        """anchor: two letters, horizontal (l/c/r) then vertical (t/m/b for top, middle, baseline)."""
        m, base = text_mask(s, int(size), face)
        h, w = m.shape
        if anchor[0] == "c":
            x -= w / 2
        elif anchor[0] == "r":
            x -= w
        if anchor[1] == "m":
            y -= h / 2
        elif anchor[1] == "b":
            y -= base
        x, y = int(round(x)), int(round(y))
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return w, h
        mm = m[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32) / 255.0 * a
        col = np.array(self.bgr(rgb), np.float32)[: self.c]
        layer = (mm[:, :, None] * col[None, None, :]).astype(np.uint8)
        if self.mode == "max":
            np.maximum(self.img[y0:y1, x0:x1], layer, out=self.img[y0:y1, x0:x1])
        else:
            dst = self.img[y0:y1, x0:x1].astype(np.float32)
            self.img[y0:y1, x0:x1] = (dst * (1 - mm[:, :, None]) + layer).astype(np.uint8)
        return w, h


class Panel(Canvas):
    """Opaque UI panel (alpha-over compositing on a dark background)."""

    def __init__(self, w, h):
        super().__init__(w, h, channels=4, mode="over")

    def clear(self, rgba=(16, 18, 22, 215)):
        self.img[:] = (rgba[2], rgba[1], rgba[0], rgba[3])

    def _composite(self, *a):
        # draw straight into the panel: _tmp is unused in 'over' mode
        pass

    @staticmethod
    def bgr(rgb, a=1.0):
        return (float(rgb[2]), float(rgb[1]), float(rgb[0]), 255.0 * a)

    def poly(self, pts, rgb, a=1.0):
        pts = np.asarray(pts, dtype=float)
        if len(pts) >= 3 and np.all(np.isfinite(pts)):
            cv2.fillPoly(self.img, [np.round(pts * 16).astype(np.int32)], self.bgr(rgb, a), cv2.LINE_AA, shift=4)

    def line(self, p0, p1, rgb, a=1.0, width=2):
        if np.all(np.isfinite(p0)) and np.all(np.isfinite(p1)):
            cv2.line(self.img, (int(round(p0[0] * 16)), int(round(p0[1] * 16))),
                     (int(round(p1[0] * 16)), int(round(p1[1] * 16))), self.bgr(rgb, a), max(1, int(width)),
                     cv2.LINE_AA, shift=4)

    def polyline(self, pts, rgb, a=1.0, width=2, closed=False):
        pts = np.asarray(pts, dtype=float)
        pts = pts[np.all(np.isfinite(pts), axis=1)]
        if len(pts) >= 2:
            cv2.polylines(self.img, [np.round(pts * 16).astype(np.int32)], closed, self.bgr(rgb, a), max(1, int(width)),
                          cv2.LINE_AA, shift=4)

    def circle(self, c, r, rgb, a=1.0, width=2, fill=False):
        cv2.circle(self.img, (int(round(c[0] * 16)), int(round(c[1] * 16))), int(round(r * 16)), self.bgr(rgb, a),
                   -1 if fill else max(1, int(width)), cv2.LINE_AA, shift=4)

    def rect(self, x0, y0, x1, y1, rgb, a=1.0, fill=True, width=1):
        cv2.rectangle(self.img, (int(x0), int(y0)), (int(x1), int(y1)), self.bgr(rgb, a), -1 if fill else width)

    def text(self, s, x, y, size, rgb, a=1.0, face="regular", anchor="lt"):
        m, base = text_mask(s, int(size), face)
        h, w = m.shape
        if anchor[0] == "c":
            x -= w / 2
        elif anchor[0] == "r":
            x -= w
        if anchor[1] == "m":
            y -= h / 2
        elif anchor[1] == "b":
            y -= base
        x, y = int(round(x)), int(round(y))
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return w, h
        mm = m[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32) / 255.0 * a
        dst = self.img[y0:y1, x0:x1].astype(np.float32)
        col = np.array([rgb[2], rgb[1], rgb[0], 255], np.float32)
        out = dst * (1 - mm[:, :, None]) + col[None, None, :] * mm[:, :, None]
        out[:, :, 3] = np.maximum(dst[:, :, 3], mm * 255)
        self.img[y0:y1, x0:x1] = out.astype(np.uint8)
        return w, h
