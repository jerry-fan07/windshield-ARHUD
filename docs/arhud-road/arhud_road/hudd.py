"""hudd: the renderer. It takes the newest perception message, applies the plan's drawing rules (stale cutoffs, line
hysteresis, ribbon, lead chevron, hazards, speed block, clutter mode), compensates for the message's age with egod's
speed and yaw rate, projects everything from the eye point onto the virtual image plane and draws the 946 x 473 PGU
frame (the 60 x 30 mm crop) as emitted light on black.

A port of the 3-D simulator's hud.js (docs/arhud-sim/js/hud.js) with the same rules and numbers. Added features that
go beyond the plan live in features.py and are drawn only when content = 'plus'.
"""
import math

import numpy as np

from . import plan as PL
from .canvas import Canvas
from .perception import VEHICLE_KINDS, apply_delta, smoothstep, snoise

RIBBON = (70, 170, 255)
LINE_EGO = (225, 240, 255)
LINE_OTHER = (160, 190, 220)
CHEVRON = (255, 190, 90)
CHEVRON_TXT = (255, 214, 150)
HAZARD = (255, 140, 60)
WHITE = (255, 255, 255)


def default_settings():
    return dict(
        compensation="photon",     # 'photon' (predict to photon time), 'draw' (plan's formula, to draw time), 'off'
        lat=[(s["lo"] + s["hi"]) / 2 for s in PL.LAT_STAGES],
        camera_hz=30,
        head_tracking=True,
        tracker_latency=PL.TRACKER_LATENCY_MS,
        tracker_dropout=False,
        ghost="true",              # 'off', 'true' (3.1 mm), 'x20' (exaggerated)
        pgu="bl",
        both_surfaces=False,
        auto_dim=True,
        dim_steps=0,
        clutter_until=-1.0,
        window="spec",
        sun_watch=True,
        gnss_outage=False,
        plane="fit",
        content="plus",            # 'plan' (as written) or 'plus' (plan + added features)
        truth_overlay=False,       # debug: draw unnoised truth with zero latency (registration must read ~0)
        sunglasses=False,
        worn=[],
        show_window=False,         # faint outline of the window, for orientation (not part of the HUD)
        features=dict(nav=True, ldw=True, fcw=True, gap=True, curve=True, pedpath=True, overspeed=True,
                      eyebox=True, occlusion=True),
    )


class Hudd:
    def __init__(self, plane, settings=None):
        self.plane = plane
        self.S = settings or default_settings()
        self.cv = Canvas(PL.CROP_W, PL.CROP_H)
        self.frame = self.cv.img
        self.line_state = {}
        self.tracks = {}
        self.sign = dict(value=None, t=-1e9, cand=None, count=0, box=None, boxT=-1e9)
        self.msg = None
        self.ribbon = None
        self.lead = None
        self.eye_used = plane.eye0.copy()
        self.eye_nominal = False
        self.stats = dict(age_lanes=0.0, age_objects=0.0, age_ego=0.01, age_eye=0.0, render_ms=0.0,
                          res_lane10=None, res_lane20=None, res_lane30=None, res_lead=None, dropped=0,
                          speed_shown=None)
        self.features = None        # set by the app (features.Features)
        self.delta_cache = {}

    # ---- message intake -------------------------------------------------------------------------------------------
    def ingest(self, m):
        for ln in m["lanes"]:
            st = self.line_state.get(ln["id"]) or dict(shown=False, above=0, alpha=0.0)
            c = ln["line_conf"]
            if not st["shown"]:
                st["above"] = st["above"] + 1 if c > 0.6 else 0
                if st["above"] >= 3:
                    st["shown"] = True
            elif c < 0.3:
                st["shown"] = False
                st["above"] = 0
            st["alpha"] = float(smoothstep(0.3, 0.8, c)) if st["shown"] else 0.0
            self.line_state[ln["id"]] = st
        seen = set()
        for o in m["objects"]:
            seen.add(o["id"])
            tr = self.tracks.get(o["id"]) or dict(id=o["id"], count=0, last=-1e9, first=m["tc"])
            if o["conf"] > 0.5:
                tr["count"] += 1
            tr["last"] = m["tc"]
            tr["obj"] = o
            tr["k"] = m["k"]
            self.tracks[o["id"]] = tr
        for tid in list(self.tracks):
            tr = self.tracks[tid]
            if tid not in seen:
                if m["tc"] - tr["last"] > 0.4:
                    tr["count"] = 0
                if m["tc"] - tr["last"] > 2.0:
                    del self.tracks[tid]
        if m["sign"]:
            s = self.sign
            if s["cand"] == m["sign"]["value"]:
                s["count"] += 1
            else:
                s["cand"], s["count"] = m["sign"]["value"], 1
            if s["count"] >= 2:
                s["value"], s["t"] = m["sign"]["value"], m["tc"]
            s["box"], s["boxT"] = m["sign"], m["tc"]
        self.msg = m

    # ---- per frame ------------------------------------------------------------------------------------------------
    def update(self, t, ctx):
        """t: sim time now (photon time of the frame on the panel). ctx: dict with perception, hist, tracker,
        eye_true_off, truth_now (car frame), speed_true, rig."""
        S = self.S
        lat = S["lat"]
        d_display = (lat[3] + lat[4]) / 1000.0
        t_draw = t - d_display
        P = ctx["perception"]
        msgs = []
        while P.queue and P.queue[0][0] <= t_draw:
            msgs.append(P.queue.popleft()[1])
        self.stats["dropped"] += max(0, len(msgs) - 1)
        for m in msgs:
            self.ingest(m)
        # head tracker
        if S["head_tracking"]:
            off, age = ctx["tracker"].report(t_draw, S["tracker_latency"] / 1000.0, dropout=S["tracker_dropout"])
            stale = off is None or age > 0.5
            self.eye_nominal = stale
            self.eye_used = self.plane.eye0 + (np.zeros(3) if stale else off)
            self.stats["age_eye"] = (age if off is not None else 9.9) + d_display
        else:
            self.eye_nominal = True
            self.eye_used = self.plane.eye0.copy()
            self.stats["age_eye"] = float("nan")
        self.t, self.t_draw = t, t_draw
        self.draw(t_draw, t, ctx)

    def _delta(self, P, hist, tc, t_target, outage):
        key = (round(tc, 5), round(t_target, 5), bool(outage))
        d = self.delta_cache.get(key)
        if d is None:
            d = (0.0, 0.0, 0.0) if outage else P.ego_delta(hist, tc, t_target)
            if len(self.delta_cache) > 64:
                self.delta_cache.clear()
            self.delta_cache[key] = d
        return d

    def ground_z(self, x, y):
        pl = self.msg["plane"] if self.msg else None
        if pl is None:
            return np.zeros_like(np.asarray(x, dtype=float))
        n, c = pl["n"], pl["c"]
        return (c - n[0] * np.asarray(x) - n[1] * np.asarray(y)) / n[2]

    def draw(self, t_draw, t_now, ctx):
        S = self.S
        cv = self.cv
        cv.clear()
        self.ribbon = None
        self.lead = None
        self.occl_x = None
        self.drawn = dict(lanes=[], lead=None)
        m = self.msg
        if S["truth_overlay"]:
            self.draw_truth(ctx)
            self.speed_block(t_now, ctx)
            return
        if m is None:
            self.speed_block(t_now, ctx)
            return
        clutter = S["clutter_until"] > t_now
        age = t_draw - m["tc"]
        self.stats["age_lanes"] = self.stats["age_objects"] = age
        stale_a = 1.0 if age < 0.25 else 0.0 if age > 0.6 else 1.0 - float(smoothstep(0.25, 0.55, age))
        outage = S["gnss_outage"]
        t_target = t_now if S["compensation"] == "photon" else t_draw
        comp_on = S["compensation"] != "off" and not outage      # no fix: no prediction (plan 5.5)
        P, hist = ctx["perception"], ctx["hist"]
        delta = self._delta(P, hist, m["tc"], t_target, not comp_on)
        eye = self.eye_used
        proj = lambda X: self.plane.project(X, eye)
        self.comp = lambda X: apply_delta(X, delta)
        self.proj = proj

        # lanes, compensated
        lanes = []
        for ln in m["lanes"]:
            q = dict(ln)
            q["pts"] = apply_delta(ln["pts"], delta)
            lanes.append(q)
        egoL = next((l for l in lanes if l["type"] == "egoLeft"), None)
        egoR = next((l for l in lanes if l["type"] == "egoRight"), None)
        stL = egoL and self.line_state.get(egoL["id"])
        stR = egoR and self.line_state.get(egoR["id"])
        drawnL = bool(egoL and (clutter or (stL and stL["shown"])))
        drawnR = bool(egoR and (clutter or (stR and stR["shown"])))

        # ribbon geometry: between the two ego lines where both are drawn; one missing: 3.7 m from the other
        rib = None
        if (drawnL or drawnR) and stale_a > 0:
            far = min(egoL["last"] if drawnL else 99, egoR["last"] if drawnR else 99, 60.0)
            xs = np.arange(4.0, far + 1e-6, 1.5)

            def interp(ln, x):
                p = ln["pts"]
                o = np.argsort(p[:, 0])
                return np.interp(x, p[o, 0], p[o, 1], left=np.nan, right=np.nan)

            yl = interp(egoL, xs) if drawnL else np.full(len(xs), np.nan)
            yr = interp(egoR, xs) if drawnR else np.full(len(xs), np.nan)
            yl = np.where(np.isnan(yl), yr + 3.7, yl)
            yr = np.where(np.isnan(yr), yl - 3.7, yr)
            ok = ~(np.isnan(yl) | np.isnan(yr))
            if ok.sum() > 1:
                xs, yl, yr = xs[ok], yl[ok], yr[ok]
                left = np.stack([xs, yl, self.ground_z(xs, yl)], 1)
                right = np.stack([xs, yr, self.ground_z(xs, yr)], 1)
                rib = dict(left=left, right=right, both=drawnL and drawnR, far=float(xs[-1]))
        self.ribbon = rib

        # tracked objects: 3 consecutive detections; persist 400 ms, fading over the last 200 ms
        tracks = []
        for tr in self.tracks.values():
            since = m["tc"] - tr["last"]
            if since > 0.4:
                continue
            vis = 1.0 if clutter else ((1.0 if since < 0.2 else 1 - (since - 0.2) / 0.2) if tr["count"] >= 3 else 0.0)
            if vis <= 0:
                continue
            o = tr["obj"]
            d_tr = self._delta(P, hist, tr["last"], t_target, not comp_on)
            adv = o["heading"] * (o["speed"] * (t_target - tr["last"]) if comp_on else 0.0)
            p = apply_delta((o["p"] + adv)[None, :], d_tr)[0]
            tracks.append(dict(tr=tr, o=o, p=p, vis=vis * stale_a))
        self.track_list = tracks

        # lead: nearest vehicle whose base is inside the ribbon, within 80 m
        lead = None
        rb = self.ribbon
        if rb is not None:
            for tk in tracks:
                if tk["o"]["kind"] not in VEHICLE_KINDS:
                    continue
                x = tk["p"][0]
                if x > 80 or x < 3 or x > rb["far"] + 25:
                    continue
                i = int(np.searchsorted(rb["left"][:, 0], x))
                i = min(i, len(rb["left"]) - 1)
                yl, yr = rb["left"][i, 1], rb["right"][i, 1]
                y = tk["p"][1]
                if yr - 0.2 < y < yl + 0.2 and (lead is None or x < lead["p"][0]):
                    lead = tk
        self.lead = lead
        # occlusion (added feature): ground graphics end at the lead car's rear instead of being painted over it
        self.occl_x = None
        plus = self.features is not None and S["content"] == "plus"
        if plus and S["features"].get("occlusion") and lead is not None and rib is not None:
            xc = lead["p"][0] - 0.4
            keep = rib["left"][:, 0] <= xc
            if keep.sum() >= 2:
                rib["left"], rib["right"] = rib["left"][keep], rib["right"][keep]
                rib["far"] = float(rib["left"][-1, 0])
            self.occl_x = xc
        # ribbon: translucent fill, lighter when one line is inferred
        if rib is not None:
            poly = np.vstack([proj(rib["left"]), proj(rib["right"])[::-1]])
            poly = poly[np.all(np.isfinite(poly), axis=1)]
            if len(poly) > 3:
                a = (0.32 if rib["both"] else 0.2) * stale_a
                rib_col = self.features.ribbon_colour(RIBBON, t_now) if plus else RIBBON
                cv.poly_gradient(poly, rib_col, a, a * 0.5)

        # lane lines and road edges, faded by confidence
        for ln in lanes:
            st = self.line_state.get(ln["id"])
            base = 1.0 if clutter else (st["alpha"] if st and st["shown"] else 0.0)
            if base <= 0.01 or stale_a <= 0:
                continue
            ego_line = ln["type"] != "other"
            pp = proj(ln["pts"])
            c = np.ones(len(pp)) if clutter else smoothstep(0.3, 0.8, ln["conf"])
            cv.begin()
            for i in range(1, len(pp)):
                ci = min(c[i - 1], c[i])
                if ci <= 0.02:
                    continue
                col = LINE_EGO if ego_line else LINE_OTHER
                a = (0.95 if ego_line else 0.6) * base * ci * stale_a
                x = ln["pts"][i - 1, 0]
                w = max(6.0, (0.18 if ego_line else 0.12) * 1000.0 / max(4.0, x) * 0.9)
                cv.line(pp[i - 1], pp[i], col, a, w)
            cv.end()
            if ego_line:
                self.drawn["lanes"].append(ln)

        # ground graphics of the added features (lane-departure glow, gap bar, turn arrows, pedestrian paths)
        if plus:
            self.features.draw_ground(self, ctx, t_now)
        # occlusion (added feature): erase conformal graphics where a nearer tracked vehicle stands in front of them
        if plus and S["features"].get("occlusion"):
            self.occlude(tracks)
        v = ctx["speed_true"]
        if lead is not None:
            self.chevron(lead, True, v, t_now)
            self.drawn["lead"] = lead
        if clutter:
            for tk in tracks:
                if tk is not lead and tk["o"]["kind"] in VEHICLE_KINDS:
                    self.chevron(tk, True, v, t_now)

        # hazards: pedestrians and cyclists (every track in clutter mode)
        for tk in tracks:
            haz = tk["o"]["kind"] in ("person", "bicycle")
            if (not haz and not clutter) or tk is lead:
                continue
            box = self.proj_box(tk["p"], tk["o"])
            if box is None:
                continue
            col = HAZARD if haz else (200, 220, 255)
            if haz and self.features is not None and S["content"] == "plus":
                col = self.features.hazard_colour(tk, col, t_now)
            cv.rrect(box[0] - 6, box[1] - 6, box[2] + 6, box[3] + 6, 8, col, tk["vis"] * (1 if haz else 0.7), 6)

        # speed-limit sign outline (informational)
        sb = self.sign["box"]
        if sb is not None and m["tc"] - self.sign["boxT"] < 0.4:
            c = self.comp(sb["p"][None, :])[0]
            z0 = sb["h"]
            tl = proj(np.array([[c[0], c[1] + sb["w"] / 2, z0 + 0.75]]))[0]
            br = proj(np.array([[c[0], c[1] - sb["w"] / 2, z0]]))[0]
            if np.all(np.isfinite(tl)) and np.all(np.isfinite(br)):
                cv.rrect(tl[0] - 6, tl[1] - 6, br[0] + 6, br[1] + 6, 6, (200, 230, 255), 0.75, 6)

        if plus:
            self.features.draw_overlay(self, ctx, t_now)
        self.speed_block(t_now, ctx)
        if clutter:
            cv.text("CLUTTER MODE (demo)", PL.CROP_W - 16, 12, 22, WHITE, 0.8, anchor="rt")
        self.residuals(ctx)

    def occlude(self, tracks):
        """A HUD cannot hide behind a car: its light lies over everything. hudd can still leave out what a nearer
        tracked vehicle would cover: clear the frame inside each vehicle's projected box, above its nearest base
        corner (ground graphics nearer than the vehicle project below that row and are kept)."""
        for tk in tracks:
            if tk["o"]["kind"] not in VEHICLE_KINDS or tk["vis"] < 0.3:
                continue
            box = self.proj_box(tk["p"], tk["o"])
            if box is None:
                continue
            x0, y0, x1, y1 = (int(max(0, box[0])), int(max(0, box[1])), int(min(PL.CROP_W, box[2])),
                              int(min(PL.CROP_H, box[3] - 3)))
            if x1 > x0 and y1 > y0:
                self.cv.img[y0:y1, x0:x1] = 0

    # ---- elements --------------------------------------------------------------------------------------------------
    def chevron(self, tk, with_text, v, t_now):
        # anchored at the visible face (the lead's rear bumper): tip 0.4 m behind it
        x, y = tk["p"][0], tk["p"][1]
        pts = np.array([[x - 2.0, y - 0.95], [x - 0.4, y], [x - 2.0, y + 0.95], [x - 2.7, y + 0.95], [x - 1.3, y],
                        [x - 2.7, y - 0.95]])
        P3 = np.hstack([pts, self.ground_z(pts[:, 0], pts[:, 1])[:, None]])
        pp = self.proj(P3)
        if not np.all(np.isfinite(pp)):
            return
        col = CHEVRON
        txt_col = CHEVRON_TXT
        if self.features is not None and self.S["content"] == "plus":
            col, txt_col = self.features.lead_colours(tk, col, txt_col, t_now)
        self.cv.poly(pp, col, 0.95 * tk["vis"])
        if with_text:
            gap = max(0.0, x - PL.EYE_TO_FRONT_BUMPER)
            txt = f"{gap:.0f} m · {gap / v:.1f} s" if v > 3 else f"{gap:.0f} m"
            base = self.proj(np.array([[x - 3.0, y, float(self.ground_z(x - 3.0, y))]]))[0]
            if np.all(np.isfinite(base)):
                self.cv.text(txt, base[0], min(PL.CROP_H - 34, base[1] + 4), 30, txt_col, tk["vis"], anchor="ct")

    def proj_box(self, p, o):
        p = p + o.get("center_off", np.zeros(3))
        hx = 0.3 if o["kind"] == "person" else 0.9 if o["kind"] == "bicycle" else o["length"] / 2
        hy = (o["width"] or 0.6) / 2
        h = o["height"] or 1.7
        z0 = float(self.ground_z(p[0], p[1]))
        C = np.array([[p[0] + dx, p[1] + dy, z0 + z] for dx in (-hx, hx) for dy in (-hy, hy) for z in (0, h)])
        pp = self.proj(C)
        if not np.all(np.isfinite(pp)):
            return None
        return pp[:, 0].min(), pp[:, 1].min(), pp[:, 0].max(), pp[:, 1].max()

    def speed_block(self, t_now, ctx):
        """Fixed, non-conformal, low in the window: GNSS speed + fix glyph, last speed-limit sign, status glyphs."""
        S, cv, H = self.S, self.cv, PL.CROP_H
        x, y = 26, H - 112
        fix = not S["gnss_outage"]
        v = ctx["speed_true"]
        meas = max(0.0, v + 0.05 * float(snoise(t_now * 3, 9))) if fix else None
        self.stats["speed_shown"] = meas
        txt = "–" if meas is None else ("0" if meas < 1 else str(int(round(meas * PL.MPH))))
        col = WHITE
        if self.features is not None and S["content"] == "plus" and meas is not None:
            col = self.features.speed_colour(meas, self.sign_value(t_now), col)
        tw, _ = cv.text(txt, x, y + 66, 64, col, 0.97, face="bold", anchor="lb")
        cv.text("mph", x + tw + 8, y + 40, 20, WHITE, 0.97, anchor="lb")
        gx, gy = x + tw + 22, y + 60
        gcol = (160, 255, 200) if fix else (255, 160, 120)
        cv.circle((gx, gy), 4, gcol, 0.95, 4)
        cv.arc((gx, gy), 12, 205, 310, gcol, 0.95, 4)
        if not fix:
            cv.line((gx - 12, gy + 8), (gx + 12, gy - 16), gcol, 0.95, 4)
        lim = self.sign_value(t_now)
        lx, ly = x + tw + 70, y + 6
        cv.rrect(lx, ly, lx + 62, ly + 72, 8, WHITE, 0.95, 4)
        cv.text("SPEED", lx + 31, ly + 6, 11, WHITE, 0.95, anchor="ct")
        cv.text("LIMIT", lx + 31, ly + 19, 11, WHITE, 0.95, anchor="ct")
        cv.text(str(lim) if lim else "–", lx + 31, ly + 64, 30, WHITE, 0.95, anchor="cb")
        self.block_right = lx + 62
        if self.eye_nominal or not S["head_tracking"]:
            ex, ey = lx + 94, ly + 36
            c = (255, 200, 120)
            import cv2
            cv2.ellipse(cv._tmp, (ex, ey), (16, 9), 0, 0, 360, cv.bgr(c, 0.95), 4, cv2.LINE_AA)
            cv._composite(ex - 20, ey - 13, ex + 20, ey + 13)
            cv.circle((ex, ey), 4, c, 0.95, 4)
            cv.line((ex - 18, ey + 14), (ex + 18, ey - 14), c, 0.95, 4)
            self.block_right = ex + 20
        # added feature: the curve-speed chip sits beside the speed block
        if self.features is not None and S["content"] == "plus" and S["features"]["curve"] and not S["truth_overlay"]:
            self.features.draw_curve_chip(self, self.block_right + 18, v)

    def sign_value(self, t_now):
        s = self.sign
        return s["value"] if s["value"] and t_now - s["t"] < 600 else None

    def draw_truth(self, ctx):
        """Debug overlay: unnoised ground truth now, from the true eye, no latency. Registration must read ~0."""
        eye = self.plane.eye0 + ctx["eye_true_off"]
        proj = lambda X: self.plane.project(X, eye)
        self.proj = proj
        for ln in ctx["truth_now"]["lines"]:
            P = ln["pts"]
            P = P[(P[:, 0] > 2) & (P[:, 0] < 80)]
            if len(P) > 1:
                self.cv.polyline(proj(P), (120, 255, 160), 0.9, 6)
        for o in ctx["truth_now"]["objects"]:
            if 3 < o["p"][0] < 80:
                box = self.proj_box(o["p"], o)
                if box:
                    self.cv.rrect(box[0], box[1], box[2], box[3], 4, (255, 120, 220), 0.9, 4)
        self.cv.text("TRUTH OVERLAY (debug)", PL.CROP_W - 16, 12, 22, WHITE, 0.8, anchor="rt")
        self.residuals(ctx)

    # ---- registration: drawn vs true, seen from the true eye now ------------------------------------------------
    def residuals(self, ctx):
        eye_true = self.plane.eye0 + ctx["eye_true_off"]
        truth = ctx["truth_now"]
        out = {}

        def ang_to_curve(dd, curve):
            d = curve - eye_true
            d = d / np.linalg.norm(d, axis=1)[:, None]
            cosang = np.clip(d @ dd, -1, 1)
            return math.degrees(math.acos(cosang.max()))

        if self.S["truth_overlay"]:
            tl = [ln for ln in truth["lines"] if ln["rel"] == 1]
            if tl:
                P = tl[0]["pts"]
                for xr in (10, 20, 30):
                    j = int(np.argmin(np.abs(P[:, 0] - xr)))
                    px = self.proj(P[j:j + 1])[0]
                    if np.all(np.isfinite(px)):
                        dd = self.plane.pixel_dir(px[0], px[1], eye_true)
                        dense = self._densify(P)
                        out[f"lane{xr}"] = ang_to_curve(dd, dense)
        else:
            for ln in self.drawn["lanes"]:
                if ln["type"] != "egoRight":
                    continue
                rel = 1
                tl = [q for q in truth["lines"] if q["rel"] == rel]
                if not tl:
                    continue
                dense = self._densify(tl[0]["pts"])
                for xr in (10, 20, 30):
                    j = int(np.argmin(np.abs(ln["pts"][:, 0] - xr)))
                    if abs(ln["pts"][j, 0] - xr) > 3 or ln["conf"][j] < 0.3:
                        continue
                    px = self.proj(ln["pts"][j:j + 1])[0]
                    if not np.all(np.isfinite(px)):
                        continue
                    dd = self.plane.pixel_dir(px[0], px[1], eye_true)
                    out[f"lane{xr}"] = ang_to_curve(dd, dense)
            ld = self.drawn["lead"]
            if ld is not None:
                o = next((q for q in truth["objects"] if q["id"] == ld["o"]["id"]), None)
                if o is not None:
                    px = self.proj(np.array([[ld["p"][0], ld["p"][1], float(self.ground_z(ld["p"][0], ld["p"][1]))]]))[0]
                    if np.all(np.isfinite(px)):
                        dd = self.plane.pixel_dir(px[0], px[1], eye_true)
                        tp = np.array(o.get("face", o["p"]), float) - eye_true
                        out["lead"] = math.degrees(math.acos(np.clip(dd @ (tp / np.linalg.norm(tp)), -1, 1)))
        k = 0.2
        for key in ("lane10", "lane20", "lane30", "lead"):
            sk = "res_" + key
            if key in out:
                prev = self.stats.get(sk)
                self.stats[sk] = out[key] if prev is None else prev + (out[key] - prev) * k
                self.stats[sk + "_raw"] = out[key]
            else:
                self.stats[sk + "_raw"] = None
        self.res_now = out

    @staticmethod
    def _densify(P, step=0.25):
        """Resample a polyline every `step` metres (for the angular distance to a true line)."""
        P = P[(P[:, 0] > 1.0) & (P[:, 0] < 90.0)]
        if len(P) < 2:
            return P
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
        q = np.arange(0.0, s[-1], step)
        return np.stack([np.interp(q, s, P[:, k]) for k in range(3)], 1)
