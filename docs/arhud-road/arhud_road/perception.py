"""The plan's sensing and perception in miniature: what roadd/laned/detectd (the ZED 2i and its networks), egod (ZED-F9R
GNSS + IMU) and headtrackd (OAK-D Pro) would publish, built from MetaDrive ground truth with the plan's error models.

Every message carries the capture time of the sensor frame it came from (plan 3.2). Messages become visible to hudd
only after the capture-to-publish part of the latency budget (camera + inference + publish), so the drawing rules,
age compensation and stale cutoffs all see realistic ages.

Ground plane (plan 5.1): lane points are rays from the road camera intersected with a plane. 'fit' is the per-frame
RANSAC fit on the depth map (true road plane plus a small fit error), 'static+imu' is the calibrated static plane
rotated by the IMU pitch, and 'static' is the calibrated plane alone, which is what the fallback becomes when the IMU
term is wrong: under braking the body pitches and far points slide.
"""
import math
from collections import deque

import numpy as np

from . import plan as PL


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, dtype=float) - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def snoise(x, seed):
    """Smooth deterministic noise in about [-1, 1] (as in the 3-D simulator)."""
    return (np.sin(x * 1.13 + seed * 7.1) * 0.5 + np.sin(x * 0.47 + seed * 3.3) * 0.35 +
            np.sin(x * 2.71 + seed * 1.7) * 0.15)


VEHICLE_KINDS = ("car", "suv", "truck", "bus", "motorcycle")


def _heading_car(o, rig):
    hd = rig.R.T @ np.array([math.cos(o["heading"]), math.sin(o["heading"]), 0.0])
    hd[2] = 0.0
    return hd / (np.linalg.norm(hd) + 1e-9)


def visible_face(pcen, o, rig, cam):
    """Car-frame ground point of the face of a vehicle that the road camera sees (centre for people and cones)."""
    if o["kind"] not in VEHICLE_KINDS:
        return pcen
    hd = _heading_car(o, rig)
    away = float(hd[:2] @ (pcen[:2] - np.asarray(cam)[:2])) > 0
    f = pcen.copy()
    f[:2] -= (1 if away else -1) * hd[:2] * o["length"] / 2
    return f


def visible_centre_off(face, o, rig):
    """Offset from the visible face back to the object's centre (for boxes and outlines)."""
    if o["kind"] not in VEHICLE_KINDS:
        return np.zeros(3)
    hd = _heading_car(o, rig)
    away = float(hd[0]) > 0
    return np.array([*((1 if away else -1) * hd[:2] * o["length"] / 2), 0.0])


class EgoHistory:
    """Per-frame ground truth of the ego (the source for egod and for capture-time transforms)."""

    def __init__(self, keep=4.0):
        self.keep = keep
        self.buf = deque()

    def push(self, st):
        self.buf.append(st)
        while len(self.buf) > 2 and self.buf[0]["t"] < st["t"] - self.keep:
            self.buf.popleft()

    def at(self, t):
        """Nearest frame at or before t."""
        best = self.buf[0]
        for st in self.buf:
            if st["t"] <= t + 1e-9:
                best = st
            else:
                break
        return best

    def between(self, t0, t1):
        return [st for st in self.buf if t0 - 1e-9 <= st["t"] <= t1 + 1e-9]


class Perception:
    def __init__(self, settings, rng_seed=7):
        self.S = settings
        self.rng = np.random.default_rng(rng_seed)
        self.queue = deque()             # (available_at, msg) for camera topics
        self.gnss_bias = 0.0
        self.k = 0
        self.last_capture_t = -1e9

    # ---- roadd / laned / detectd ----------------------------------------------------------------------------------
    def capture(self, t, truth, chain, lines, objects, rig, env):
        """Make one camera-frame message at capture time t from the current ground truth."""
        S = self.S
        r = self.rng
        self.k += 1
        k = self.k
        night = env == "night"
        dusk = env == "dusk"
        rs = 0.62 if night else 0.85 if dusk else 1.0
        cam = np.array(PL.ROAD_CAM)
        # True road plane in the car frame: n . x = c
        n_true = rig.R[2, :].copy()
        c_true = -rig.o[2]
        n_est, c_est = self.plane_estimate(n_true, c_true, rig, t)

        def lift(P):
            """Re-intersect the camera rays through true points P with the estimated plane."""
            d = P - cam
            den = d @ n_est
            tt = (c_est - cam @ n_est) / np.where(np.abs(den) < 1e-9, 1e-9, den)
            out = cam + d * tt[:, None]
            out[(tt <= 0) | (tt > 20)] = np.nan
            return out

        lanes = []
        for b, L in lines.items():
            rel = L["rel"][min(len(L["rel"]) - 1, int(np.searchsorted(L["a"], 0.0)))]
            if rel not in (-1, 0, 1, 2):
                continue
            Pw = np.hstack([L["pts"], np.zeros((len(L["pts"]), 1))])
            Pc = rig.world_to_car(Pw)
            sel = (Pc[:, 0] >= 3.0) & (Pc[:, 0] <= 72.0)
            if sel.sum() < 2:
                continue
            Pc = Pc[sel]
            kinds = [L["kind"][i] for i in np.nonzero(sel)[0]]
            x = Pc[:, 0]
            # bearing inside the camera's field
            brg = np.degrees(np.arctan2(Pc[:, 1] - cam[1], x - cam[0]))
            infov = np.abs(brg) < PL.ROAD_CAM_FOV_H / 2 - 2
            painted = np.array([kd is not None for kd in kinds])
            worn = np.zeros(len(x), bool)
            for (a0, a1) in S.get("worn", []):
                a_abs = L["a"][sel] + S.get("route_pos", 0.0)        # worn stretches are in route metres
                worn |= (a_abs >= a0) & (a_abs <= a1) & (rel in (0, 1))
            conf = np.where(worn, 0.22, 0.93) * (1 - smoothstep(38 * rs, 68 * rs, x))
            conf = np.where(painted, conf, 0.0)
            dashed = np.array([kd is not None and kd.startswith("dashed") for kd in kinds])
            conf = np.where(dashed, conf * 0.97, conf)
            conf = np.clip(conf + 0.04 * r.standard_normal(len(x)), 0, 1) * infov
            # lateral error grows with range (plan 5.7 gate: 0.15 m at 10 m, 0.3 at 20, 0.5 at 30)
            sig = 0.02 + 0.004 * x
            lat = sig * (0.65 * snoise(t * 0.9 + x * 0.05, b + 1) + 0.35 * r.standard_normal(len(x)))
            Pm = Pc.copy()
            Pm[:, 1] += lat
            Pm = lift(Pm)
            ok = ~np.isnan(Pm[:, 0])
            if ok.sum() < 2:
                continue
            Pm, conf, Pt = Pm[ok], conf[ok], Pc[ok]
            near = (Pm[:, 0] >= 6) & (Pm[:, 0] <= 25)
            line_conf = float(conf[near].mean()) if near.any() else 0.0
            last = 0.0
            for xi, ci in zip(Pm[:, 0], conf):
                if ci > 0.5:
                    last = xi
                elif xi > 8:
                    break
            typ = {0: "egoLeft", 1: "egoRight"}.get(rel, "other")
            edge = kinds[0] == "edge" or (kinds[0] or "").endswith("yellow")
            lanes.append(dict(id=f"b{b}", type=typ, edge=edge, kind=kinds[len(kinds) // 2], pts=Pm, truth=Pt,
                              conf=conf, line_conf=line_conf, last=last))

        objs = []
        cands = []
        for o in objects:
            Pw = np.array([[o["pos"][0], o["pos"][1], 0.0]])
            pcen = rig.world_to_car(Pw)[0]
            # stereo range comes from the lower part of the box, i.e. the face the camera sees: the rear bumper of a
            # car driving away, the front of one coming the other way
            pc = visible_face(pcen, o, rig, cam)
            if pc[0] < 2 or pc[0] > 90:
                continue
            rel = pc - cam
            rel[2] = 0
            brg = math.atan2(rel[1], rel[0])
            if abs(brg) > math.radians(PL.ROAD_CAM_FOV_H / 2 - 4):
                continue
            rng_ = float(np.hypot(rel[0], rel[1]))
            half = math.atan2(max(o["width"], 0.5) / 2, rng_)
            cands.append((rng_, brg, half, o, pc))
        cands.sort(key=lambda c: c[0])
        for idx, (rng_, brg, half, o, pc) in enumerate(cands):
            # occlusion: a nearer, taller object covering most of this one's bearing span
            occl = 0.0
            for (r2, b2, h2, o2, _) in cands[:idx]:
                if o2["kind"] in ("cone",) or r2 > rng_ - 1.0:
                    continue
                lo, hi = max(brg - half, b2 - h2), min(brg + half, b2 + h2)
                if hi > lo:
                    cover = (hi - lo) / (2 * half)
                    if o2["height"] >= o["height"] * 0.8:
                        occl = max(occl, cover)
            if occl > 0.75:
                continue
            person = o["kind"] in ("person", "bicycle")
            pdet = (0.9 if rng_ < 30 * rs else 0.4) if person else (0.97 if rng_ < 50 * rs else 0.75)
            if o["kind"] == "cone":
                pdet = 0.85 if rng_ < 35 * rs else 0.2
            if r.random() > pdet * (1 - 0.5 * occl):
                continue
            # range: stereo inside 35 m, else the ground plane at the box base (plan 5.3)
            if rng_ < PL.STEREO_MAX:
                dz = rng_ * rng_ * PL.D_DISP / (PL.F_PX * PL.B_ST)
                z_meas = rng_ + dz * r.standard_normal() * 0.8
                meas = cam.copy()
                meas[:2] += (pc[:2] - cam[:2]) * (z_meas / rng_)
                meas[2] = pc[2]
            else:
                meas = lift(pc[None, :] + np.array([[0, 0, 0.0]]))[0]
                if np.isnan(meas[0]):
                    continue
                meas[:2] += (pc[:2] - cam[:2]) / rng_ * rng_ * 0.03 * r.standard_normal()
            hd_w = np.array([math.cos(o["heading"]), math.sin(o["heading"]), 0.0])
            hd_c = rig.R.T @ hd_w
            hd_c[2] = 0
            vel_c = rig.R.T @ np.array([o["vel"][0], o["vel"][1], 0.0])
            objs.append(dict(id=o["id"], kind=o["kind"], p=meas, truth=pc, center_off=visible_centre_off(pc, o, rig),
                             length=o["length"], width=o["width"],
                             height=o["height"], heading=hd_c / (np.linalg.norm(hd_c) + 1e-9),
                             speed=float(np.hypot(*o["vel"])), vel=vel_c, conf=0.6 + 0.35 * r.random(),
                             range=rng_, occl=occl))

        sign = None
        for sg in truth.signs:
            pc = rig.world_to_car(np.array([[sg["pos"][0], sg["pos"][1], 0.0]]))[0]
            if 6 < pc[0] < 45 * rs and abs(math.atan2(pc[1], pc[0])) < math.radians(35):
                if r.random() < 0.8:
                    sign = dict(value=sg["value"], id=sg["id"], p=pc, h=sg.get("h", 2.1), w=0.6)

        msg = dict(k=k, tc=t, lanes=lanes, objects=objs, sign=sign,
                   plane=dict(n=n_est, c=c_est, mode=S["plane"], pitch_true=rig.pitch,
                              pitch_est=math.asin(max(-1, min(1, n_est[0])))))
        avail = t + self.age_capture()
        self.queue.append((avail, msg))
        self.last_capture_t = t
        return msg

    def plane_estimate(self, n_true, c_true, rig, t):
        mode = self.S["plane"]
        r = self.rng
        if mode == "fit":
            # RANSAC on the depth map's road region: about 0.05 deg and 1 cm of fit noise
            e = np.radians(0.05) * r.standard_normal(2)
            n = n_true + np.array([e[0], e[1], 0.0])
            return n / np.linalg.norm(n), c_true + 0.01 * r.standard_normal()
        if mode == "static+imu":
            # static calibration rotated by the IMU's pitch and roll (gyro-integrated, slight lag and 0.1 deg noise)
            e = np.radians(0.1) * r.standard_normal(2)
            n = n_true + np.array([e[0], e[1], 0.0])
            return n / np.linalg.norm(n), c_true
        # 'static': the plane measured with the car parked (z = 0 in the car frame), whatever the body is doing now
        return np.array([0.0, 0.0, 1.0]), 0.0

    def age_capture(self):
        L = self.S["lat"]
        return (L[0] + L[1] + L[2]) / 1000.0

    def latest(self, t_draw):
        """Newest camera message whose publish time is at or before t_draw."""
        best = None
        while self.queue and self.queue[0][0] <= t_draw:
            best = self.queue.popleft()[1]
            self._last = best
        return best

    # ---- egod ----------------------------------------------------------------------------------------------------
    def ego_delta(self, hist, t0, t1, outage=False):
        """Dead-reckon from t0 to t1 with egod's speed (GNSS Doppler, 0.05 m/s) and yaw rate (IMU gyro).
        Returns (dx, dy, dpsi) in the car frame at t0."""
        if t1 <= t0:
            return 0.0, 0.0, 0.0
        r = self.rng
        frames = hist.between(t0, t1)
        if len(frames) < 1:
            return 0.0, 0.0, 0.0
        bias = 0.03 * float(snoise(t0 * 0.2, 3))
        psi = dx = dy = 0.0
        tprev = t0
        for st in frames[1:] + [dict(t=t1, speed=frames[-1]["speed"], yaw_rate=frames[-1]["yaw_rate"])]:
            dt = st["t"] - tprev
            if dt <= 0:
                continue
            v = st["speed"] + bias + 0.05 * r.standard_normal()
            w = st["yaw_rate"] + 0.002 * r.standard_normal()
            psi += w * dt
            dx += v * math.cos(psi) * dt
            dy += v * math.sin(psi) * dt
            tprev = st["t"]
        return dx, dy, psi


def apply_delta(P, delta):
    """Points captured at t0 (car frame) -> car frame at t1, given the ego motion (dx, dy, dpsi) between them:
    p_now = Rz(-dpsi) (p_capture - [dx, dy, 0]) (plan 6)."""
    dx, dy, dpsi = delta
    c, s = math.cos(dpsi), math.sin(dpsi)
    P = np.atleast_2d(P)
    x = P[:, 0] - dx
    y = P[:, 1] - dy
    out = P.copy()
    out[:, 0] = x * c + y * s
    out[:, 1] = -x * s + y * c
    return out


class HeadTracker:
    """headtrackd: the OAK-D Pro reports the eye midpoint `latency` late with about 3 mm of noise; hudd falls back to
    the nominal eye point when the report is older than 500 ms (plan 6, stale rules)."""

    def __init__(self):
        self.hist = deque()
        self.rng = np.random.default_rng(11)

    def push(self, t, offset):
        self.hist.append((t, np.array(offset, dtype=float)))
        while len(self.hist) > 2 and self.hist[0][0] < t - 2.0:
            self.hist.popleft()

    def report(self, t_draw, latency_s, dropout=False):
        if dropout:
            return None, 9.9
        tl = t_draw - latency_s
        val = self.hist[0][1]
        for (t, o) in self.hist:
            if t <= tl:
                val = o
            else:
                break
        noise = np.array([0.0, 0.003, 0.002]) * self.rng.standard_normal(3)
        return val + noise, latency_s
