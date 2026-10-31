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
from .scene import APPEAR, CONFIRM, FADE, LINE_HIDE
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
        self.f_label = HUD.font(cfg.get("label_px", 18), "SemiBold")
        self.f_note = HUD.font(cfg.get("note_px", 17), "SemiBold")
        self.stroke = cfg.get("stroke_px", 2.2)
        self.Hs = None
        self._lum = None
        self._last_i = None

    # ---- tracking -------------------------------------------------------------------------------------------
    def frames(self):
        return read_frames(self.sc.footage, self.sc.t0, self.t1, size=(self.W, self.H))

    def track(self, cache_dir):
        planes = [{"name": p["name"], "ref_frame": int(round(p["ref_t"] * self.fps)), "poly": p["poly"],
                   "range": [int(round(t * self.fps)) for t in p["t_range"]] if "t_range" in p else None}
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
        polys = {p["name"]: np.asarray(p["poly"], np.float64)[:4] for p in self.sc.cfg.get("planes", [])}
        self.Hs = {k: _fill_gaps(v, polys[k], self.cfg.get("max_gap_frames", 4)) for k, v in self.Hs.items()}
        self.vis = {k: _visibility(v) for k, v in self.Hs.items()}
        # ports read off a later frame ("at_t") are carried back to their plane's reference frame
        for name, p in self.sc.ports.items():
            if "at_t" in p:
                Hs = self.Hs[p["plane"]]
                i = min(len(Hs) - 1, int(round(p.pop("at_t") * self.fps)))
                if Hs[i] is None:
                    raise ValueError(f"port {name}: plane {p['plane']} is not tracked at its at_t frame {i}")
                p["quad"] = _warp(np.linalg.inv(Hs[i]), p["quad"])
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
            q_lag = q - self.latency * (q - qp)
            # the image moves over the whole exposure: central difference where the next pose is known
            if i + 1 < len(Hs) and Hs[i + 1] is not None:
                v = (_warp(Hs[i + 1], p["quad"]) - qp).mean(axis=0) / 2
            else:
                v = (q - qp).mean(axis=0)
            q = q_lag
        q = q + self.rng.normal(0, self.tremor, 2)
        return q, (float(v[0]), float(v[1]))

    def hud_layers(self, i):
        t = i / self.fps
        lines, targets = self.sc.state(t)
        world = HUD.Layer(self.W, self.H)
        head = HUD.Layer(self.W, self.H)
        vel = (0.0, 0.0)
        w = self.stroke
        for name, st in targets.items():
            plane = self.sc.ports[name]["plane"]
            vis = self.vis[plane][i] if i < len(self.vis[plane]) else 0.0
            q, v = self.port_quad(name, i)
            since, done = st["since"], st["done"]
            a_in = HUD.ease_out(since / APPEAR)
            lvl_in = HUD.smoothstep(0.0, 0.2, since)
            grow = 1.0 + 0.7 * (1.0 - a_in)
            mix = 0.0 if done is None else HUD.smoothstep(0.0, 0.25, done)
            fade = (1.0 if done is None else 1.0 - HUD.smoothstep(CONFIRM, CONFIRM + FADE, done)) * st["clear"]
            if q is None or vis <= 0.01:
                continue
            vel = v
            dw = world.draw(HUD.CYAN)
            dg = world.draw(HUD.GREEN)
            base = 0.95 * lvl_in * vis
            if mix < 1.0:
                HUD.quad_brackets(dw, q, base * (1 - mix), width=w, grow=grow)
            if mix > 0.0:
                # verified: the brackets close into an outline that tightens onto the port's own footprint
                HUD.quad_brackets(dg, q, base * mix * fade, width=w, leg=0.28 + 0.22 * mix, pad=0.22 - 0.16 * mix)
            c = q.mean(axis=0)
            pad = c + (q - c) * 1.22
            top = pad[:2].mean(axis=0)
            edge = float(np.linalg.norm(pad[1] - pad[0]))
            lab_at = (top[0], top[1] - max(8.0, 0.18 * edge))
            # the tag fades out before the check fades in, so the two never overlap
            tag = 1.0 if done is None else 1.0 - HUD.smoothstep(0.0, 0.15, done)
            if st["label"] and tag > 0.0:
                HUD.text(dw, lab_at, st["label"], self.f_label, 0.88 * lvl_in * vis * tag * a_in, anchor="mb",
                         spacing=0.02)
            if done is not None and done > 0.18:
                lvl = 0.92 * HUD.smoothstep(0.18, 0.4, done) * fade * vis
                note = st["note"]
                tw = HUD.text_width(note, self.f_note, 0.02) if note else 0.0
                ck = 11.0
                x = lab_at[0] - (tw + ck + 8) / 2 if note else lab_at[0] - ck / 2
                HUD.check(dg, (x + ck / 2, lab_at[1] - 8), ck, lvl, width=w)
                if note:
                    HUD.text(dg, (x + ck + 8, lab_at[1]), note, self.f_note, lvl, anchor="lb", spacing=0.02)
            if not self.disp.inside(c, margin=0.02) and done is None:
                at, ang = self.disp.edge_point(c)
                HUD.chevron(head.draw(HUD.CYAN), at, ang, 14.0, 0.75 * lvl_in * vis, width=w)
        x0, y0, x1, y1 = self.disp.rect
        ly = y0 + (y1 - y0) * self.cfg.get("line_y", 0.1)
        for ln in lines:
            level = ln["level"]
            if ln["target"] is not None:
                # once its target has been locked in view for a moment, the line steps aside: the brackets say it
                level *= 1.0 - 0.85 * HUD.smoothstep(LINE_HIDE, LINE_HIDE + 0.5, ln["since"]) * self.locked(ln["target"], i)
            self._line(head, ln["e"], level, ((x0 + x1) / 2, ly))
        return world, head, vel

    def locked(self, name, i, window=12):
        """Fraction of the last `window` frames in which a port was tracked and inside the display's field."""
        p = self.sc.ports[name]
        Hs = self.Hs[p["plane"]]
        n = 0
        for j in range(max(0, i - window + 1), i + 1):
            if j < len(Hs) and Hs[j] is not None and self.disp.inside(_warp(Hs[j], p["quad"]).mean(axis=0)):
                n += 1
        return n / window

    def _line(self, layer, e, a, at):
        if a <= 0.0:
            return
        d = layer.draw(HUD.CYAN)
        main = e["text"].replace("->", "\u2192")
        count = e.get("step", "") if self.cfg.get("step_counter", False) else ""
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
        layers = []
        for layer, is_world in ((world, True), (head, False)):
            if layer.inks:
                light = layer.light()
                layers.append((light, layer.bbox, is_world))
        out = self.disp.compose(lin, layers, vel, self.rng, g)
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


def _fill_gaps(Hs, poly, max_gap):
    """Bridge tracking dropouts of up to max_gap frames by interpolating the plane's corners, as a headset's IMU
    carries the pose through a short visual loss; longer losses stay None (content fades out)."""
    Hs = list(Hs)
    i = 0
    n = len(Hs)
    while i < n:
        if Hs[i] is not None:
            i += 1
            continue
        j = i
        while j < n and Hs[j] is None:
            j += 1
        if 0 < i and j < n and j - i <= max_gap:
            a, b = _warp(Hs[i - 1], poly), _warp(Hs[j], poly)
            for k in range(i, j):
                u = (k - i + 1) / (j - i + 1)
                Hs[k] = cv2.getPerspectiveTransform(poly.astype(np.float32), (a + (b - a) * u).astype(np.float32))
        i = j
    return Hs


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
