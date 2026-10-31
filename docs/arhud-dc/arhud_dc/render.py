"""Per frame: tracked plane poses -> HUD state at t -> world and head layers -> optics -> composite.

World-locked content is drawn where the renderer *thinks* the port is when the photons leave the display: the
tracked pose, minus a little of the frame-to-frame motion (render-to-photon latency the pose predictor did not
cancel), plus sub-pixel tremor. Real headsets do the same; it reads as a faint swim during quick head turns and
nothing when the head is still.
"""
import hashlib
import json
import math
import os

import cv2
import numpy as np

from . import hud as HUD
from .optics import Display
from .scene import APPEAR, CONFIRM, FADE, LINE_DIM
from .track import track_planes
from .video import Writer, probe, read_frames, to_linear, to_srgb8


def _warp(H, q):
    return cv2.perspectiveTransform(np.asarray(q, np.float64).reshape(-1, 1, 2), H).reshape(-1, 2)


class Renderer:
    def __init__(self, scene, size=None, seed=0):
        self.sc = scene
        info = probe(scene.footage)
        if size is None:
            size = scene.cfg.get("output_size")
        if size is None:
            # the source's own shape, long side at most 1920 (vertical Shorts stay vertical), even dimensions
            k = min(1.0, 1920.0 / max(info["w"], info["h"]))
            size = (int(round(info["w"] * k / 2)) * 2, int(round(info["h"] * k / 2)) * 2)
        self.W, self.H = size
        self.fps = info["fps"]
        self.t1 = scene.t1 if scene.t1 is not None else info["duration"]
        cfg = scene.cfg.get("display", {})
        self.disp = Display(cfg, self.W, self.H)
        self.cfg = cfg
        self.latency = cfg.get("residual_latency_ms", 7.0) / 1000.0 * self.fps   # in frames
        self.tremor = cfg.get("tremor_px", 0.18)
        self.rng = np.random.default_rng(seed)
        self.f_line = HUD.font(cfg.get("line_px", 23), "SemiBold")
        self.f_count = HUD.font(cfg.get("count_px", 18), "Medium")
        self.f_label = HUD.font(cfg.get("label_px", 17), "SemiBold")
        self.f_note = HUD.font(cfg.get("note_px", 17), "SemiBold")
        self.Hs = None
        self._lum = None
        self._last_i = None

    # ---- tracking -------------------------------------------------------------------------------------------
    def frames(self):
        return read_frames(self.sc.footage, self.sc.t0, self.t1, size=(self.W, self.H))

    def track(self, cache_dir):
        planes = [{"name": p["name"], "ref_frame": int(round(p["ref_t"] * self.fps)), "poly": p["poly"]}
                  for p in self.sc.cfg.get("planes", [])]
        key = hashlib.sha1(json.dumps([planes, self.sc.t0, self.t1, self.W, self.H, self.sc.footage]).encode()).hexdigest()[:12]
        path = os.path.join(cache_dir, f"{self.sc.name}-{key}.npz")
        if os.path.exists(path):
            z = np.load(path, allow_pickle=True)
            self.Hs = z["Hs"].item()
            self.inliers = z["inl"].item()
        else:
            frames = list(self.frames())
            res = track_planes(frames, planes, self.W)
            self.Hs = {k: v[0] for k, v in res.items()}
            self.inliers = {k: v[1] for k, v in res.items()}
            os.makedirs(cache_dir, exist_ok=True)
            np.savez(path, Hs=np.array(self.Hs, dtype=object), inl=np.array(self.inliers, dtype=object))
        self.vis = {k: _visibility(v) for k, v in self.Hs.items()}
        n = len(next(iter(self.Hs.values()))) if self.Hs else 0
        return {k: f"{sum(h is not None for h in v)}/{n} frames tracked" for k, v in self.Hs.items()}

    # ---- per frame ------------------------------------------------------------------------------------------
    def port_quad(self, name, i):
        """Display-space quad of a port at frame i as drawn (with residual latency and tremor), and its velocity."""
        p = self.sc.ports[name]
        Hs = self.Hs[p["plane"]]
        if i >= len(Hs) or Hs[i] is None:
            return None, (0.0, 0.0)
        q = _warp(Hs[i], p["quad"])
        v = np.zeros(2)
        if i > 0 and Hs[i - 1] is not None:
            qp = _warp(Hs[i - 1], p["quad"])
            v = (q - qp).mean(axis=0)
            q = q - self.latency * (q - qp)
        q = q + self.rng.normal(0, self.tremor, 2)
        return q, (float(v[0]), float(v[1]))

    def hud_layers(self, i):
        t = i / self.fps
        lines, targets = self.sc.state(t)
        world = HUD.Layer(self.W, self.H)
        head = HUD.Layer(self.W, self.H)
        vel = (0.0, 0.0)
        for name, st in targets.items():
            plane = self.sc.ports[name]["plane"]
            vis = self.vis[plane][i] if i < len(self.vis[plane]) else 0.0
            q, v = self.port_quad(name, i)
            since, done = st["since"], st["done"]
            a_in = HUD.ease_out(since / APPEAR)
            lvl_in = HUD.smoothstep(0.0, 0.2, since)
            grow = 1.0 + 0.7 * (1.0 - a_in)
            mix = 0.0 if done is None else HUD.smoothstep(0.0, 0.25, done)
            fade = 1.0 if done is None else 1.0 - HUD.smoothstep(CONFIRM, CONFIRM + FADE, done)
            if q is None or vis <= 0.01:
                continue
            vel = v
            dw = world.draw(HUD.CYAN)
            dg = world.draw(HUD.GREEN)
            base = 0.95 * lvl_in * vis
            if mix < 1.0:
                HUD.quad_brackets(dw, q, base * (1 - mix), grow=grow)
            if mix > 0.0:
                # brackets close into a full outline as they turn green
                HUD.quad_brackets(dg, q, base * mix * fade, leg=0.28 + 0.22 * mix)
            c = q.mean(axis=0)
            pad = c + (q - c) * 1.22
            top = pad[:2].mean(axis=0)
            edge = float(np.linalg.norm(pad[1] - pad[0]))
            lab_at = (top[0], top[1] - max(8.0, 0.18 * edge))
            if st["label"] and mix < 1.0:
                HUD.text(dw, lab_at, st["label"], self.f_label, 0.88 * lvl_in * vis * (1 - mix) * a_in, anchor="mb",
                         spacing=0.02)
            if mix > 0.0:
                lvl = 0.92 * mix * fade * vis
                note = st["note"]
                tw = HUD.text_width(note, self.f_note, 0.02) if note else 0.0
                ck = 11.0
                x = lab_at[0] - (tw + ck + 8) / 2 if note else lab_at[0]
                HUD.check(dg, (x + ck / 2, lab_at[1] - 8), ck, lvl)
                if note:
                    HUD.text(dg, (x + ck + 8, lab_at[1]), note, self.f_note, lvl, anchor="lb", spacing=0.02)
            if not self.disp.inside(c, margin=0.02) and done is None:
                at, ang = self.disp.edge_point(c)
                HUD.chevron(head.draw(HUD.CYAN), at, ang, 14.0, 0.75 * lvl_in * vis)
        x0, y0, x1, y1 = self.disp.rect
        ly = y0 + (y1 - y0) * self.cfg.get("line_y", 0.84)
        for e, a in lines:
            dim = 1.0 - 0.45 * HUD.smoothstep(LINE_DIM, LINE_DIM + 1.0, t - e["t"])
            self._line(head, e, a * dim, ((x0 + x1) / 2, ly))
        return world, head, vel

    def _line(self, layer, e, a, at):
        d = layer.draw(HUD.CYAN)
        main = e["text"].replace("->", "→")
        count = e.get("step", "")
        gap = 16.0
        wm = HUD.text_width(main, self.f_line, 0.015)
        wc = HUD.text_width(count, self.f_count, 0.04) if count else 0.0
        x = at[0] - (wm + (wc + gap if count else 0)) / 2
        if count:
            HUD.text(d, (x, at[1]), count, self.f_count, 0.5 * a, anchor="ls", spacing=0.04)
            x += wc + gap
        HUD.text(d, (x, at[1]), main, self.f_line, 0.9 * a, anchor="ls", spacing=0.015)

    def exposure(self, i, lin):
        """How bright the HUD looks after the camera's auto-exposure.

        The display's luminance is fixed by its own ambient-light loop, but the camera re-exposes for the scene: in a
        dim hot aisle it opens up and the HUD reads brighter, panning onto a lit white cold aisle it stops down and the
        HUD fades. Modelled as (reference / scene luminance)^k on the display region's mean, with a ~0.4 s lag.
        """
        x0, y0, x1, y1 = (int(v) for v in self.disp.rect)
        y = lin[max(0, y0):y1:8, max(0, x0):x1:8] @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        lum = float(np.exp(np.log(y + 1e-3).mean()))
        a = 1.0 if self._last_i is None or i != self._last_i + 1 else 1.0 - math.exp(-1.0 / (0.4 * self.fps))
        self._lum = lum if self._lum is None else self._lum + a * (lum - self._lum)
        self._last_i = i
        ref, k = self.cfg.get("exposure_ref", 0.12), self.cfg.get("exposure_k", 0.35)
        return float(np.clip((ref / max(self._lum, 1e-3)) ** k, 0.6, 1.6))

    def composite(self, i, rgb):
        world, head, vel = self.hud_layers(i)
        lin = to_linear(rgb)
        g = self.exposure(i, lin)
        out = self.disp.compose(lin, world.light() if world.inks else None, head.light(), vel, self.rng, g)
        return to_srgb8(out)

    # ---- output ---------------------------------------------------------------------------------------------
    def render(self, out_path, audio=True, only=None, stills_dir=None, compare=False, crf=16):
        """Whole cut to out_path, or (only = set of frame indices) just those frames as PNG stills."""
        w = None
        if only is None:
            w = Writer(out_path, self.W, self.H, self.fps, audio=self.sc.footage if audio else None,
                       t0=self.sc.t0, t1=self.t1, crf=crf)
        n = 0
        for i, rgb in enumerate(self.frames()):
            if only is not None and i not in only:
                continue
            out = self.composite(i, rgb)
            if w:
                w.write(out)
            else:
                img = np.hstack([rgb, out]) if compare else out
                cv2.imwrite(os.path.join(stills_dir, f"{self.sc.name}-{i / self.fps:06.2f}s.png"),
                            cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            n += 1
            if only is not None and n >= len(only):
                break
        if w:
            w.close()
        return n


def _visibility(Hs, ramp=5):
    """0..1 per frame: tracked content fades in and out over `ramp` frames instead of popping."""
    ok = np.array([h is not None for h in Hs], np.float64)
    out = np.zeros_like(ok)
    lvl = 0.0
    for i, o in enumerate(ok):
        lvl = min(1.0, lvl + 1.0 / ramp) if o else 0.0
        out[i] = lvl
    # fade out ahead of a loss as well (offline we can look ahead)
    lvl = 1.0
    for i in range(len(ok) - 1, -1, -1):
        lvl = min(1.0, lvl + 1.0 / ramp) if ok[i] else 0.0
        out[i] = min(out[i], lvl)
    return out
