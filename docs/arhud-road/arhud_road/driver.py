"""The simulated human driver and head motion.

The plan has no self-driving: a person drives. In the simulator that person is either you (arrow keys) or this model,
which follows the route's lane with pure pursuit, keeps to the posted limit and a comfortable curve speed, follows
traffic with IDM, signals before lane changes, and can be told to drift (for the lane-departure demo) or to brake hard
(for the pitch demo). It reads ground truth, not the HUD: it stands in for a driver looking at the road.
"""
import math

import numpy as np

from . import plan as PL
from .perception import snoise


def curvature_speed(kappa, a_lat=2.4):
    return math.sqrt(a_lat / max(abs(kappa), 1e-4))


class SimDriver:
    def __init__(self):
        self.mode = "auto"              # 'auto' (model) or 'manual' (arrow keys)
        self.set_speed = 26.8           # m/s cap (60 mph)
        self.lat_target = 0.0           # lateral offset from the lane centre, m (left +)
        self.drift = None               # dict(start t, rate m/s, side) for the drift scenario
        self.brake_until = -1.0
        self.brake_from = -1.0
        self.ignore_until = -1.0          # the driver is looking away: does not react to vehicles ahead
        self.signal = 0                 # -1 left, +1 right, 0 off (left/right as the driver sees it)
        self.signal_until = -1.0
        self.lane_change = None
        self.integ = 0.0
        self.desired = 0.0
        self.limit_ms = None
        self.keys = dict(up=False, down=False, left=False, right=False)
        self.steer_state = 0.0

    def act(self, t, dt, ego, rig, chain_c, lines_c, objects_c, limit_mph, speed_cap):
        """Return the MetaDrive action [steer, throttle] (steer + is left)."""
        v = ego.speed
        if self.mode == "manual":
            return self.manual(dt, v)
        # ---- lateral: pure pursuit on the route lane centre, plus the target offset --------------------------------
        if self.drift is not None and t >= self.drift["start"]:
            self.lat_target = self.drift["side"] * min(self.drift["max"], (t - self.drift["start"]) * self.drift["rate"])
        if self.lane_change is not None:
            lc = self.lane_change
            if t >= lc["go"]:
                f = min(1.0, (t - lc["go"]) / lc["dur"])
                self.lat_target = lc["side"] * lc["width"] * (0.5 - 0.5 * math.cos(math.pi * f))
                if f >= 1.0:
                    self.lane_change = None
                    self.lat_target = 0.0
                    self.signal = 0
        wobble = 0.08 * float(snoise(t * 0.35, 5))
        ld = max(7.0, 0.9 * v + 4.0)
        C = chain_c                                 # N x 3 lane-centre points in the car frame (route)
        if C is None or len(C) < 3:
            return [0.0, -0.3]
        # offset the centre line laterally by the target (in the car frame this is close enough to a normal offset)
        tgt = C.copy()
        tgt[:, 1] += self.lat_target + wobble
        # the car frame's origin is under the eye, 0.37 m left of the centreline: steer the car's centre
        rear_axle = np.array([-1.35 + PL.EYE_TO_FRONT_BUMPER - 2.3, PL.CAR_CENTER_Y, 0.0])
        d = np.linalg.norm(tgt[:, :2] - rear_axle[:2], axis=1)
        ahead = tgt[:, 0] > rear_axle[0] + 1.0
        idx = np.nonzero(ahead & (d >= ld))[0]
        p = tgt[idx[0]] if len(idx) else tgt[-1]
        alpha = math.atan2(p[1] - rear_axle[1], p[0] - rear_axle[0])
        wheelbase = 2.8
        delta = math.atan2(2 * wheelbase * math.sin(alpha), max(ld, 1e-3))
        steer = max(-1.0, min(1.0, delta / math.radians(ego.max_steering)))
        self.steer_state += (steer - self.steer_state) * min(1.0, dt / 0.08)
        # ---- longitudinal ----------------------------------------------------------------------------------------
        des = self.set_speed
        if limit_mph:
            des = min(des, limit_mph / PL.MPH)
        if speed_cap:
            des = min(des, speed_cap)           # comfortable speed for the curves ahead on the route
        des = max(des, 4.0)
        # IDM against the nearest vehicle ahead in our path
        lead = None
        for o in objects_c:
            if t < self.ignore_until and o["kind"] not in ("person", "bicycle", "cone"):
                continue
            if o["kind"] in ("person", "bicycle", "cone"):
                if 0 < o["p"][0] < 40 and abs(o["p"][1] - (PL.CAR_CENTER_Y + self.lat_target)) < 1.6:
                    lead = o if lead is None or o["p"][0] < lead["p"][0] else lead
                continue
            if 0 < o["p"][0] < 90 and abs(o["p"][1] - (PL.CAR_CENTER_Y + self.lat_target)) < 1.5:
                lead = o if lead is None or o["p"][0] < lead["p"][0] else lead
        a_idm = 1.5 * (1 - (v / des) ** 4)
        if lead is not None:
            gap = max(0.5, lead["p"][0] - lead.get("length", 4.5) / 2 - (PL.EYE_TO_FRONT_BUMPER))
            vl = float(lead.get("vx", v))
            dv = v - vl
            s_star = 3.0 + v * 1.4 + v * dv / (2 * math.sqrt(1.5 * 2.5))
            a_idm = 1.5 * (1 - (v / des) ** 4 - (max(0.0, s_star) / gap) ** 2)
            if dv > 0.5 and gap / dv < 1.6:
                a_idm = min(a_idm, -8.0)          # emergency stop
        if self.brake_from <= t < self.brake_until:
            a_idm = -7.0
        self.desired = des
        # map acceleration to throttle/brake (MetaDrive: about 4 m/s2 at full throttle low down, 8 braking)
        err = a_idm
        thr = err / 3.0 if err > 0 else err / 6.0
        thr = max(-1.0, min(1.0, thr))
        return [self.steer_state, thr]

    def manual(self, dt, v):
        k = self.keys
        target = (1.0 if k["left"] else 0.0) - (1.0 if k["right"] else 0.0)
        rate = 2.2 if target != 0 else 3.5
        self.steer_state += max(-rate * dt, min(rate * dt, target * 0.45 - self.steer_state))
        thr = 0.8 if k["up"] else (-0.9 if k["down"] else 0.0)
        return [self.steer_state, thr]

    def start_lane_change(self, t, side, width=3.5):
        """side +1 = to the left (car-frame y), -1 = to the right; signal first, move after 2.5 s."""
        self.signal = 1 if side < 0 else -1
        self.lane_change = dict(go=t + 2.5, dur=4.0, side=side, width=width)


class HeadMotion:
    """True head offset from the nominal eye (car frame, m). Modes: still, natural (slow drift and ride bounce),
    sway (+/-75 mm side to side at 0.25 Hz, the plan's registration test), lean (60 mm step to the right)."""

    MODES = ("natural", "still", "sway", "lean")

    def __init__(self):
        self.mode = "natural"
        self.bounce = 0.0
        self.bv = 0.0

    def offset(self, t, accel_z=0.0, dt=1 / 60):
        # ride bounce: a damped spring driven by the body's vertical acceleration
        self.bv += (-40.0 * self.bounce - 6.0 * self.bv - 0.004 * accel_z) * dt
        self.bounce += self.bv * dt
        if self.mode == "still":
            return np.zeros(3)
        if self.mode == "sway":
            return np.array([0.0, 0.075 * math.sin(2 * math.pi * 0.25 * t), 0.004 * math.sin(2 * math.pi * 0.5 * t)])
        if self.mode == "lean":
            return np.array([0.0, -0.060, -0.010])
        return np.array([0.004 * float(snoise(t * 0.2, 1)), 0.012 * float(snoise(t * 0.13, 2)),
                         0.006 * float(snoise(t * 0.17, 3)) + self.bounce])
