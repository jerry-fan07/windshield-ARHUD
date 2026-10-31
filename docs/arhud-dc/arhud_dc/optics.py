"""The display as the camera sees it: a waveguide's virtual image added to the world as light.

What a head-worn optical see-through display does to its own image, in the order applied here:
  field of view  - the image exists only inside the display's FOV, a rectangle much smaller than the camera's.
                   The edge is never drawn; content fades over the last ~1 deg and is cut.
  non-uniformity - waveguides tint across the field (broad magenta/cyan/green lobes) and dim toward the corners
                   (~70 % of the centre). A smooth per-channel gain field.
  focus          - the virtual image sits at ~2 m while the hands work at ~0.5 m, so with the camera focused on the
                   rack the HUD is a touch soft.
  dispersion     - lateral colour: red and blue land a fraction of a pixel apart, growing toward the field edge.
  ghost          - a faint second image ~0.6 deg off (reflections between the waveguide plates).
  halo           - scatter in the plates and the camera lens: a wide, low glow (~1 deg) around bright strokes.
  rainbow flare  - the gratings also diffract bright sources outside the line of sight (the overhead LED troffers)
                   into faint spectral streaks inside the field, fixed to the head, not the world.
  additive light - the world is never dimmed by the image; black is transparent. Against a white cold aisle the HUD
                   loses contrast, against a black switch face it pops. The visor itself lifts blacks ~1 % and
                   tints the world very slightly.
and then the camera: motion blur of world-locked content with the head's motion, the footage's own softness, shot
noise on the added light, and a soft shoulder so bright strokes clip toward white the way a sensor does.
"""
import math

import cv2
import numpy as np


def shoulder(x, k=0.78):
    """Identity below k, then an exponential roll-off that approaches 1."""
    over = np.maximum(x - k, 0.0)
    return np.where(x > k, k + (1 - k) * (1 - np.exp(-over / (1 - k))), x)


# wavelength samples (nm) and their approximate sRGB-linear colours, for the flare's spectral smear
SPECTRUM = [(450, (0.12, 0.05, 1.0)), (480, (0.0, 0.35, 1.0)), (510, (0.0, 1.0, 0.45)), (540, (0.35, 1.0, 0.0)),
            (570, (1.0, 0.85, 0.0)), (600, (1.0, 0.35, 0.0)), (630, (1.0, 0.05, 0.0))]


class Display:
    def __init__(self, cfg, w, h):
        self.w, self.h = w, h
        cam_hfov = math.radians(cfg.get("camera_hfov_deg", 90.0))
        self.f = (w / 2) / math.tan(cam_hfov / 2)
        self.ppd = self.f * math.pi / 180          # px per degree at the centre
        hf = math.radians(cfg.get("hfov_deg", 44.0))
        vf = math.radians(cfg.get("vfov_deg", 30.0))
        cx = w * cfg.get("center", [0.5, 0.5])[0]
        cy = h * cfg.get("center", [0.5, 0.5])[1]
        hw, hh = self.f * math.tan(hf / 2), self.f * math.tan(vf / 2)
        self.rect = (cx - hw, cy - hh, cx + hw, cy + hh)
        self.c = (cx, cy)
        self.gain = cfg.get("gain", 1.1)
        gx, gy, gg = cfg.get("ghost_deg", [0.45, 0.35, 0.035])
        self.ghost = (gx * self.ppd, gy * self.ppd, gg)
        self.dispersion = cfg.get("dispersion", 0.0016)
        self.defocus = cfg.get("defocus_px", 0.6)
        self.halo = [(s * self.ppd, k) for s, k in cfg.get("halo_deg", [[0.12, 0.10], [0.9, 0.05]])]
        self.soften = cfg.get("match_softness_px", 0.0)
        self.noise = cfg.get("shot_noise", 0.012)
        self.shutter = cfg.get("shutter", 0.5)
        self.lift = np.array(cfg.get("visor_lift", [0.006, 0.007, 0.009]), np.float32)
        self.trans = np.array(cfg.get("visor_transmission", [0.985, 0.99, 1.0]), np.float32)
        self.flare = cfg.get("flare", {"gain": 0.05, "offset_deg": 17.0, "direction": [0.18, 1.0],
                                       "spread": 0.16, "threshold": 0.93})
        self._fields(cfg)

    def _fields(self, cfg):
        """Soft FOV mask and the tint field, both over the full frame."""
        x0, y0, x1, y1 = self.rect
        xs = np.arange(self.w, dtype=np.float32)
        ys = np.arange(self.h, dtype=np.float32)
        u = (xs - x0) / (x1 - x0)
        v = (ys - y0) / (y1 - y0)
        fu = cfg.get("edge_feather_deg", 0.9) * self.ppd / (x1 - x0)
        fv = cfg.get("edge_feather_deg", 0.9) * self.ppd / (y1 - y0)

        def edge(t, fe):
            a = np.clip(t / fe, 0, 1)
            b = np.clip((1 - t) / fe, 0, 1)
            return (a * a * (3 - 2 * a)) * (b * b * (3 - 2 * b))
        du, dv = (u - 0.5) * 2, (v - 0.5) * 2
        r2 = np.clip(du[None, :] ** 2 * 0.55 + dv[:, None] ** 2 * 0.45, 0, 1)
        fall = 1 - cfg.get("corner_falloff", 0.3) * r2
        self.mask = (edge(v, fv)[:, None] * edge(u, fu)[None, :] * fall).astype(np.float32)
        a = cfg.get("tint", 0.10)
        U, V = du[None, :], dv[:, None]
        # broad lobes: magenta toward one side, cyan toward the other, a green cast low in the field
        r = 1 + a * (0.7 * U - 0.5 * V ** 2)
        g = 1 + a * (-0.35 * U ** 2 + 0.25 * V)
        b = 1 + a * (-0.9 * U + 0.4 * (U * V))
        self.tint = np.stack(np.broadcast_arrays(r, g, b), -1).astype(np.float32)

    def inside(self, p, margin=0.0):
        x0, y0, x1, y1 = self.rect
        mw, mh = (x1 - x0) * margin, (y1 - y0) * margin
        return x0 + mw <= p[0] <= x1 - mw and y0 + mh <= p[1] <= y1 - mh

    def edge_point(self, p, inset=26.0):
        """Where the line from the display centre toward p leaves the display (inset px), and its direction."""
        cx, cy = self.c
        dx, dy = p[0] - cx, p[1] - cy
        x0, y0, x1, y1 = self.rect
        sx = ((x1 - cx - inset) / abs(dx)) if dx else np.inf
        sy = ((y1 - cy - inset) / abs(dy)) if dy else np.inf
        s = min(sx, sy)
        return (cx + dx * s, cy + dy * s), math.atan2(dy, dx)

    def compose(self, frame_lin, layers, velocity, rng, exposure=1.0):
        """frame_lin: HxWx3 linear world. layers: [(light HxWx3, bbox or None, world-locked?)]. velocity: px/frame
        of the world-locked layer. exposure scales the HUD light for the camera's auto-exposure."""
        plate = frame_lin * self.trans + self.lift
        out = plate.copy()
        E, box = None, None
        blur = math.hypot(*velocity) * self.shutter
        for light, bb, world in layers:
            if bb is None:
                continue
            if world:
                light = motion_blur(light, velocity, self.shutter)
                g = int(blur) + 2
                bb = (bb[0] - g, bb[1] - g, bb[2] + g, bb[3] + g)
            E = light if E is None else E + light
            box = bb if box is None else (min(box[0], bb[0]), min(box[1], bb[1]), max(box[2], bb[2]), max(box[3], bb[3]))
        regions = []
        if E is not None:
            m = int(3 * max(s for s, _ in self.halo)) + 8
            x0, y0 = max(0, box[0] - m), max(0, box[1] - m)
            x1, y1 = min(self.w, box[2] + m), min(self.h, box[3] + m)
            e = E[y0:y1, x0:x1] * self.mask[y0:y1, x0:x1, None] * self.tint[y0:y1, x0:x1]
            if self.defocus > 0:
                e = cv2.GaussianBlur(e, (0, 0), self.defocus)
            e = self._disperse(e, x0, y0)
            gx, gy, gg = self.ghost
            if gg > 0:
                M = np.float32([[1, 0, gx], [0, 1, gy]])
                e = e + gg * cv2.warpAffine(e, M, (e.shape[1], e.shape[0]))
            glow = np.zeros_like(e)
            for sigma, k in self.halo:
                glow += k * cv2.GaussianBlur(e, (0, 0), sigma)
            e = e + glow
            if self.soften > 0:
                e = cv2.GaussianBlur(e, (0, 0), self.soften)
            e *= self.gain * exposure
            if self.noise > 0:
                e += rng.normal(0, 1, e.shape).astype(np.float32) * np.sqrt(np.maximum(e, 0)) * self.noise
            regions.append(((x0, y0, x1, y1), np.maximum(e, 0)))
        if self.flare and self.flare.get("gain", 0) > 0:
            fl = self._rainbow(frame_lin)
            if fl is not None:
                regions.append((fl[0], fl[1] * exposure))
        # the sensor clips what the display adds on top of the plate; the plate itself is left as it was
        for (x0, y0, x1, y1), a in regions:
            p = out[y0:y1, x0:x1]
            out[y0:y1, x0:x1] = p + shoulder(p + a) - shoulder(p)
        return out

    def _disperse(self, e, x0, y0):
        if self.dispersion <= 0:
            return e
        cx, cy = self.c[0] - x0, self.c[1] - y0
        out = e.copy()
        for ch, k in ((0, 1 + self.dispersion), (2, 1 - self.dispersion)):
            M = np.float32([[k, 0, cx * (1 - k)], [0, k, cy * (1 - k)]])
            out[..., ch] = cv2.warpAffine(e[..., ch], M, (e.shape[1], e.shape[0]), flags=cv2.INTER_LINEAR)
        return out

    def _rainbow(self, lin):
        """Spectral streaks from bright sources: each source reappears displaced along the grating direction, the
        displacement growing with wavelength, inside the display's field only."""
        F = self.flare
        s = 4
        small = cv2.resize(lin, (self.w // s, self.h // s), interpolation=cv2.INTER_AREA)
        lum = small @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        src = np.clip((lum - F["threshold"]) / (1 - F["threshold"]), 0, 1)
        if src.max() <= 0:
            return None
        src = cv2.GaussianBlur(src, (0, 0), 1.5)
        d = np.array(F["direction"], np.float64)
        d /= np.linalg.norm(d)
        off = F["offset_deg"] * self.ppd / s
        out = np.zeros(small.shape, np.float32)
        for lam, rgb in SPECTRUM:
            k = off * (lam / 540.0)
            # streak: the source smeared a little along the grating direction at this wavelength
            M = np.float32([[1, 0, d[0] * k], [0, 1, d[1] * k]])
            sh = cv2.warpAffine(src, M, (src.shape[1], src.shape[0]))
            out += sh[..., None] * np.array(rgb, np.float32)
        ln = max(3, int(off * F.get("spread", 0.16)))
        kern = np.zeros((2 * ln + 1, 2 * ln + 1), np.float32)
        for t in np.linspace(-ln, ln, 4 * ln + 1):
            kern[int(round(ln + t * d[1])), int(round(ln + t * d[0]))] += 1
        out = cv2.filter2D(out, -1, kern / kern.sum())
        out = cv2.resize(out, (self.w, self.h), interpolation=cv2.INTER_LINEAR)
        x0, y0, x1, y1 = (int(v) for v in self.rect)
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(self.w, x1 + 1), min(self.h, y1 + 1)
        k = F["gain"] / len(SPECTRUM) * 2.0
        return (x0, y0, x1, y1), out[y0:y1, x0:x1] * k * self.mask[y0:y1, x0:x1, None]


def motion_blur(img, v, shutter):
    """Box blur along v (px/frame) over the shutter fraction of the frame interval."""
    L = math.hypot(v[0], v[1]) * shutter
    if L < 0.75:
        return img
    n = int(math.ceil(L)) | 1
    k = np.zeros((n, n), np.float32)
    c = n // 2
    a = math.atan2(v[1], v[0])
    for t in np.linspace(-L / 2, L / 2, 4 * n):
        x, y = c + t * math.cos(a), c + t * math.sin(a)
        xi, yi = int(round(x)), int(round(y))
        if 0 <= xi < n and 0 <= yi < n:
            k[yi, xi] += 1
    k /= k.sum()
    return cv2.filter2D(img, -1, k, borderType=cv2.BORDER_CONSTANT)
