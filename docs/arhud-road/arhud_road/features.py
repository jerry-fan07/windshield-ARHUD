"""Features beyond the plan as written (content = 'plus'). Each uses only what the plan's hardware already provides:
the road camera's lanes and tracks, egod's speed and yaw rate, the GNSS position against a map route, and the head
tracker. The plan lists lane-departure warnings and navigation arrows as stretch goals and excludes any drive path;
none of these draws a path the car will take, only the road, the route and the hazards.

  nav        turn-by-turn: chevrons on the route lane up to and through the next junction, glyph and distance
  ldw        lane-departure glow: the ego line the car will cross within 1 s, unsignalled, glows amber
  fcw        forward-collision warning: lead chevron amber under 1 s headway, red and a BRAKE bar under 2.6 s TTC
  gap        2-second gap marker: a bar across the ribbon at the 2 s following distance
  curve      curve-speed advisory: the comfortable speed for the next curve on the route, beside the limit
  pedpath    pedestrian and cyclist path prediction: 3 s ground path; red when it meets the ego lane in time
  overspeed  speed-limit compliance: speed turns amber above the limit + 3 mph, red above + 10
  eyebox     eye-box guide: arrows at the window edge when the tracked eye nears the edge of the eye box
  occlusion  ground graphics (ribbon, arrows, gap bar) end at the lead car's rear instead of painting over it
"""
import math

import numpy as np

from . import plan as PL
from .perception import VEHICLE_KINDS, snoise

NAV = (110, 255, 205)
AMBER = (255, 170, 40)
RED = (255, 64, 52)
WHITE = (255, 255, 255)
A_LAT = 2.4            # comfortable lateral acceleration for the curve advisory, m/s2 (ASSUMED)
B_DECEL = 2.0          # comfortable deceleration to reach the curve speed, m/s2 (ASSUMED)


class Features:
    NAMES = dict(nav="Turn-by-turn arrows", ldw="Lane-departure glow", fcw="Forward-collision warning",
                 gap="2-second gap marker", curve="Curve-speed advisory", pedpath="Pedestrian path prediction",
                 overspeed="Speed-limit compliance", eyebox="Eye-box guide", occlusion="Lead occludes ground")
    KEYS = dict(nav="Shift+1", ldw="Shift+2", fcw="Shift+3", gap="Shift+4", curve="Shift+5", pedpath="Shift+6",
                overspeed="Shift+7", eyebox="Shift+8", occlusion="Shift+9")

    def __init__(self, app):
        self.app = app
        self.route_kappa = None
        self.route_cap = None
        self.man = None
        self.ldw = dict(left=False, right=False, tlc_l=None, tlc_r=None)
        self.fcw = dict(state="none", ttc=None, headway=None)
        self.curve = dict(adv=None, dist=None)
        self.ped_conflict = set()
        self.stats = {}

    @property
    def on(self):
        return self.app.S["features"]

    # ---- per frame, before hudd draws ----------------------------------------------------------------------------
    def pre(self, t, ctx):
        app = self.app
        chain = ctx["chain"]
        self.man = app.truth.next_manoeuvre(chain)
        # route curvature: heading change per metre along the route lane, smoothed over 10 m
        if len(chain) > 8:
            a = np.array([cs.a for cs in chain])
            h = np.unwrap(np.array([cs.lane.heading_theta_at(cs.s) for cs in chain]))
            k = np.abs(np.gradient(h, a))
            k = np.convolve(k, np.ones(5) / 5, mode="same")
            vc = np.sqrt(A_LAT / np.maximum(k, 1e-4))
            ahead = a > 0
            cap = np.sqrt(vc ** 2 + 2 * B_DECEL * np.maximum(0, a - 5.0))
            self.route_cap = float(cap[ahead].min()) if ahead.any() else None
            # advisory: the slowest curve within 160 m whose speed is below the current speed or the limit
            sel = ahead & (k > 1 / 400.0)
            if sel.any():
                j = np.nonzero(sel)[0][np.argmin(vc[sel])]
                self.curve = dict(adv=float(vc[j]), dist=float(a[j]), kappa=float(k[j]))
            else:
                self.curve = dict(adv=None, dist=None, kappa=0.0)
        self.route_kappa = None

    def posted_limit(self):
        """The limit the simulated driver obeys: the last sign passed on the route (ground truth, not the HUD's read)."""
        mgr = getattr(self.app.engine, "arhud_manager", None)
        if mgr is None or not mgr.zones:
            return None
        pos = self.app.ego.navigation.travelled_length
        lim = None
        for a0, v in mgr.zones:
            if a0 <= pos + 2.0:
                lim = v
        return lim

    # ---- colours used by hudd's core elements -----------------------------------------------------------------
    def ribbon_colour(self, col, t):
        return col

    def lead_colours(self, tk, col, txt, t):
        if not self.on["fcw"]:
            return col, txt
        st = self.fcw["state"]
        if st == "warn":
            pulse = 0.75 + 0.25 * math.sin(t * 2 * math.pi * 4)
            return tuple(c * pulse for c in RED), (255, 150, 140)
        if st == "close":
            return AMBER, (255, 200, 130)
        return col, txt

    def hazard_colour(self, tk, col, t):
        if self.on["pedpath"] and tk["o"]["id"] in self.ped_conflict:
            pulse = 0.7 + 0.3 * math.sin(t * 2 * math.pi * 3)
            return tuple(c * pulse for c in RED)
        return col

    def speed_colour(self, v, limit, col):
        if not self.on["overspeed"] or not limit:
            return col
        mph = v * PL.MPH
        if mph > limit + 10:
            return (255, 90, 70)
        if mph > limit + 3:
            return (255, 190, 60)
        return col

    # ---- drawing ------------------------------------------------------------------------------------------------
    def draw_ground(self, h, ctx, t):
        """Conformal pieces, drawn before occlusion: lane-departure glow, gap bar, turn arrows, pedestrian paths."""
        on = self.on
        v = ctx["speed_true"]
        if on["ldw"]:
            self.draw_ldw(h, ctx, t)
        else:
            self.ldw = dict(left=False, right=False, tlc_l=None, tlc_r=None)
        if on["gap"]:
            self.draw_gap(h, v)
        if on["pedpath"]:
            self.draw_pedpath(h, ctx, v, t)
        else:
            self.ped_conflict = set()
        if on["nav"]:
            self.draw_nav_arrows(h, ctx, t)

    def draw_overlay(self, h, ctx, t):
        """Fixed pieces, drawn last: the collision warning, the turn glyph, the curve chip, the eye-box guide."""
        on = self.on
        v = ctx["speed_true"]
        if on["fcw"]:
            self.analyse_fcw(h, v, t)
        else:
            self.fcw = dict(state="none", ttc=None, headway=None)
        if on["nav"]:
            self.draw_nav_glyph(h)
        if on["eyebox"]:
            self.draw_eyebox(h)

    def draw_ldw(self, h, ctx, t):
        """Time to line crossing from the perceived ego lines: lateral distance from the front wheel to the line,
        and the line's slope in the car frame (the car's heading relative to the lane)."""
        app = self.app
        v = ctx["speed_true"]
        self.ldw = dict(left=False, right=False, tlc_l=None, tlc_r=None)
        m = h.msg
        if m is None:
            return
        wheel_x = PL.EYE_TO_FRONT_BUMPER - 0.9
        half = 0.80
        sig = app.driver.signal
        for ln in h.drawn["lanes"]:
            P = ln["pts"]
            sel = (P[:, 0] > 3) & (P[:, 0] < 14) & (ln["conf"] > 0.4)
            if sel.sum() < 3:
                continue
            b, a0 = np.polyfit(P[sel, 0], P[sel, 1], 1)
            y_line = a0 + b * wheel_x
            if ln["type"] == "egoLeft":
                dist = y_line - (PL.CAR_CENTER_Y + half)
                rate = -b * v
                tlc = dist / rate if rate > 0.05 else (0.0 if dist < 0 else None)
                self.ldw["tlc_l"] = tlc
                side, suppress = "left", sig == -1
            elif ln["type"] == "egoRight":
                dist = (PL.CAR_CENTER_Y - half) - y_line
                rate = b * v
                tlc = dist / rate if rate > 0.05 else (0.0 if dist < 0 else None)
                self.ldw["tlc_r"] = tlc
                side, suppress = "right", sig == +1
            else:
                continue
            warn = v > 12.0 and tlc is not None and tlc < 1.0 and dist > -0.9 and not suppress
            self.ldw[side] = warn
            if warn:
                pulse = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(t * 2 * math.pi * 3))
                pp = h.proj(P[P[:, 0] < 40])
                h.cv.begin()
                for i in range(1, len(pp)):
                    x = P[i - 1, 0]
                    w = max(14.0, 0.5 * 1000.0 / max(4.0, x))
                    h.cv.line(pp[i - 1], pp[i], AMBER, pulse, w)
                h.cv.end()

    def draw_gap(self, h, v):
        rb = h.ribbon
        if rb is None or v < 3:
            return
        x = PL.EYE_TO_FRONT_BUMPER + 2.0 * v
        if x > rb["far"] or x < rb["left"][0, 0] or (h.occl_x is not None and x > h.occl_x):
            self.stats["gap_visible"] = False
            return
        self.stats["gap_visible"] = True
        yl = np.interp(x, rb["left"][:, 0], rb["left"][:, 1])
        yr = np.interp(x, rb["right"][:, 0], rb["right"][:, 1])
        P = np.array([[x, yl, float(h.ground_z(x, yl))], [x, yr, float(h.ground_z(x, yr))]])
        pp = h.proj(P)
        h.cv.line(pp[0], pp[1], WHITE, 0.55, 6)
        h.cv.text("2 s", pp[1][0] + 8, pp[1][1], 18, WHITE, 0.7, anchor="lm")

    def analyse_fcw(self, h, v, t):
        lead = h.lead
        st = dict(state="none", ttc=None, headway=None)
        if lead is not None and v > 2.0:
            gap = max(0.1, lead["p"][0] - PL.EYE_TO_FRONT_BUMPER)
            vl = float(lead["o"]["vel"][0]) if "vel" in lead["o"] else v
            closing = v - vl
            st["headway"] = gap / v
            st["ttc"] = gap / closing if closing > 0.5 else None
            if st["ttc"] is not None and st["ttc"] < 2.6:
                st["state"] = "warn"
            elif st["headway"] < 1.0:
                st["state"] = "close"
        self.fcw = st
        if st["state"] == "warn" and h.ribbon is not None:
            pulse = 0.6 + 0.4 * math.sin(t * 2 * math.pi * 4)
            W, H = PL.CROP_W, PL.CROP_H
            h.cv.rrect(W / 2 - 150, 14, W / 2 + 150, 66, 12, RED, 0.9 * pulse, 0, fill=True)
            h.cv.text("BRAKE", W / 2, 40, 40, WHITE, 1.0, anchor="cm")

    def draw_pedpath(self, h, ctx, v, t):
        self.ped_conflict = set()
        rb = h.ribbon
        for tk in getattr(h, "track_list", []):
            o = tk["o"]
            if o["kind"] not in ("person", "bicycle"):
                continue
            vel = o.get("vel")
            if vel is None or np.hypot(vel[0], vel[1]) < 0.3:
                continue
            p = tk["p"]
            taus = np.linspace(0, 3.0, 13)
            path = np.array([[p[0] + vel[0] * s, p[1] + vel[1] * s, 0.0] for s in taus])
            path[:, 2] = h.ground_z(path[:, 0], path[:, 1])
            # conflict: will it be in the ego lane when the car gets there?
            conflict = False
            if v > 1.0:
                tau_e = max(0.0, (p[0] - PL.EYE_TO_FRONT_BUMPER) / v)
                if tau_e < 4.0:
                    y_then = p[1] + vel[1] * tau_e
                    if rb is not None:
                        yl = np.interp(p[0], rb["left"][:, 0], rb["left"][:, 1])
                        yr = np.interp(p[0], rb["right"][:, 0], rb["right"][:, 1])
                    else:
                        yl, yr = PL.CAR_CENTER_Y + 1.8, PL.CAR_CENTER_Y - 1.8
                    conflict = yr - 0.6 < y_then < yl + 0.6
            if conflict:
                self.ped_conflict.add(o["id"])
            pp = h.proj(path)
            col = RED if conflict else (255, 160, 80)
            for i in range(1, len(pp), 2):
                h.cv.line(pp[i - 1], pp[i], col, 0.85 * tk["vis"], 6)
            if len(pp) >= 2 and np.all(np.isfinite(pp[-1])) and np.all(np.isfinite(pp[-2])):
                d = pp[-1] - pp[-2]
                n = np.linalg.norm(d)
                if n > 1e-3:
                    d /= n
                    nrm = np.array([-d[1], d[0]])
                    tip = pp[-1] + d * 10
                    h.cv.poly([tip, pp[-1] - d * 6 + nrm * 9, pp[-1] - d * 6 - nrm * 9], col, 0.85 * tk["vis"])

    def draw_nav_arrows(self, h, ctx, t):
        """Conformal chevrons along the route lane (map route + GNSS, so it carries a small map/position error)."""
        man = self.man
        W, H = PL.CROP_W, PL.CROP_H
        C = ctx["truth_now"]["centre"]
        A = ctx["truth_now"]["centre_a"]
        if man is None or man["a_turn"] > 400:
            return
        # chevrons from 6 m to 25 m past the start of the turn, every 5 m, on the route lane
        a_end = man["a_turn"] + 25
        err_lat = 0.25 * float(snoise(t * 0.15, 21))
        err_lon = 0.8 * float(snoise(t * 0.11, 22))
        stride = 5.0
        start = math.ceil(6.0 / stride) * stride
        for a in np.arange(start, min(a_end, A[-1] - 2), stride):
            i = int(np.searchsorted(A, a + err_lon))
            if i <= 0 or i >= len(C) - 1:
                continue
            p = C[i]
            d = C[i + 1] - C[i - 1]
            d = d / (np.linalg.norm(d) + 1e-9)
            nrm = np.array([-d[1], d[0], 0.0])
            base = p + nrm * err_lat
            pts = np.array([base + d * 1.0, base - d * 0.4 + nrm * 0.9, base - d * 0.4 + nrm * 0.45,
                            base + d * 0.35, base - d * 0.4 - nrm * 0.45, base - d * 0.4 - nrm * 0.9])
            pts[:, 2] = h.ground_z(pts[:, 0], pts[:, 1])
            if h.occl_x is not None and pts[:, 0].max() > h.occl_x:
                continue
            pp = h.proj(pts)
            if np.all(np.isfinite(pp)):
                fade = 1.0 if a < man["a_turn"] + 5 else 0.75
                h.cv.poly(pp, NAV, 0.85 * fade)
    def draw_nav_glyph(self, h):
        """The manoeuvre glyph and distance, bottom right (non-conformal)."""
        man = self.man
        W, H = PL.CROP_W, PL.CROP_H
        if man is None or man["a_turn"] > 400:
            return
        dist = max(0.0, man["a_turn"])
        feet = dist * 3.28084
        txt = f"{feet:.0f} ft" if feet < 1000 else f"{dist / 1609.34:.1f} mi"
        gx, gy = W - 120, H - 40
        turn = man["turn"]
        h.cv.line((gx, gy), (gx, gy - 34), NAV, 0.95, 8)
        if abs(turn) < 20:
            tip = np.array([gx, gy - 62])
            h.cv.line((gx, gy - 34), tip, NAV, 0.95, 8)
            ang = -math.pi / 2
        else:
            ang = -math.pi / 2 - math.radians(max(-150, min(150, turn)))
            tip = np.array([gx, gy - 34]) + 30 * np.array([math.cos(ang), math.sin(ang)])
            h.cv.line((gx, gy - 34), tip, NAV, 0.95, 8)
        dv = np.array([math.cos(ang), math.sin(ang)])
        nv = np.array([-dv[1], dv[0]])
        h.cv.poly([tip + dv * 14, tip + nv * 13, tip - nv * 13], NAV, 0.95)
        if man["block"] == "O":
            h.cv.circle((gx, gy - 34), 13, NAV, 0.95, 4)
        h.cv.text(txt, gx + 30, gy - 10, 28, NAV, 0.95, anchor="lb")
        h.cv.text(man["kind"], gx + 30, gy - 44, 16, NAV, 0.8, face="medium", anchor="lb")
        self.stats["nav_dist"] = dist

    def draw_curve_chip(self, h, x, v):
        c = self.curve
        if c.get("adv") is None:
            return x
        adv_mph = c["adv"] * PL.MPH
        lim = h.sign_value(self.app.t)
        if not ((lim and adv_mph < lim - 4) or c["adv"] < v - 1.0):
            return x
        if c["dist"] > 160:
            return x
        val = int(5 * round(adv_mph / 5))
        y = PL.CROP_H - 106
        h.cv.rrect(x, y, x + 74, y + 72, 8, (255, 210, 90), 0.95, 4)
        # curve glyph
        pts = np.array([[x + 22, y + 30], [x + 30, y + 20], [x + 44, y + 15], [x + 54, y + 18]])
        h.cv.polyline(pts, (255, 210, 90), 0.95, 4)
        h.cv.poly([[x + 60, y + 21], [x + 50, y + 12], [x + 52, y + 26]], (255, 210, 90), 0.95)
        h.cv.text(str(val), x + 37, y + 66, 28, (255, 210, 90), 0.95, anchor="cb")
        return x + 90

    def draw_eyebox(self, h):
        if h.eye_nominal:
            return
        off = h.eye_used - h.plane.eye0
        dy, dz = off[1], off[2]
        hw, hh = PL.EYEBOX_W / 2, PL.EYEBOX_H / 2
        W, H = PL.CROP_W, PL.CROP_H
        col = (200, 220, 255)
        # head too far left (y > 0) -> arrow on the right edge pointing right, and so on
        if dy > hw * 0.75:
            self._arrow(h, (W - 30, H / 2), (1, 0), col, min(1.0, dy / hw))
        if dy < -hw * 0.75:
            self._arrow(h, (30, H / 2), (-1, 0), col, min(1.0, -dy / hw))
        if dz > hh * 0.75:
            self._arrow(h, (W / 2, H - 30), (0, 1), col, min(1.0, dz / hh))
        if dz < -hh * 0.75:
            self._arrow(h, (W / 2, 30), (0, -1), col, min(1.0, -dz / hh))

    @staticmethod
    def _arrow(h, c, d, col, a):
        c, d = np.array(c, float), np.array(d, float)
        n = np.array([-d[1], d[0]])
        h.cv.poly([c + d * 16, c - d * 10 + n * 14, c - d * 10 - n * 14], col, 0.8 * a)
