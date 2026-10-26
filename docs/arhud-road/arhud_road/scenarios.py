"""Scripted scenarios. Each one sets up a situation on the road that exercises part of the plan (or a defect it has)
and restores the defaults when another starts. F1-F11 start them; the panel lists them with what to watch for."""
import math

import numpy as np
from metadrive.component.vehicle.vehicle_type import MVehicle

from . import plan as PL
from .perception import EgoHistory

SCENARIOS = [
    ("cruise", "F1", "Cruise", "Defaults: noon, traffic, signs. The plan's content plus the added features."),
    ("lead_brake", "F2", "Lead car brakes",
     "A car pulls in 28 m ahead, then brakes hard. Gap and headway on the chevron; the forward-collision warning "
     "fires while the driver is looking away."),
    ("ped_crossing", "F3", "Pedestrian crossing",
     "Someone steps off the kerb 55 m ahead. Hazard outline once tracked for 3 frames (stereo range), predicted "
     "path turns red when it meets the ego lane."),
    ("lane_drift", "F4", "Lane drift",
     "The driver drifts right without signalling. The right line glows when the time to crossing drops below 1 s."),
    ("sun_patch", "F5", "Sun in the entry patch",
     "The sun is put behind the car, 51 deg up, where the HUD's mirror would focus it on the panel. Sun-watch "
     "closes the shutter and the image goes; turn sun-watch off (U) to see the cell heat."),
    ("night", "F6", "Night",
     "Night scene with auto-dimming. At the plan's 50 cd/m2 ceiling white is about 30x a headlit road: the window "
     "reads as a bright slab (a plan defect); the dimming curve needs a lower floor."),
    ("gnss_outage", "F7", "GNSS outage",
     "12 s without a fix: the speed shows a dash and prediction stops, so the ribbon lags in curves."),
    ("head_sway", "F8", "Head sway",
     "+/-75 mm side to side (the plan's registration test). Tracker on for 10 s, then off: far content swims."),
    ("hard_brake", "F9", "Hard braking, static plane",
     "Brakes hard with the ground plane fixed at its parked calibration. The nose dips and far lane points slide; "
     "the per-frame RANSAC fit (L) holds them."),
    ("worn_paint", "F10", "Worn paint",
     "80 m of worn lane paint ahead: line confidence drops, lines fade by the hysteresis rule, the ribbon goes "
     "one-sided and lighter."),
    ("turn", "F11", "Next junction",
     "Jumps to 130 m before the next junction on the route: turn arrows and distance. The window covers road "
     "only from about 9 to 31 m, so the arrows appear late."),
]
INFO = {k: dict(key=fk, title=t, desc=d) for (k, fk, t, d) in SCENARIOS}


class Scenarios:
    def __init__(self, app):
        self.app = app
        self.active = "cruise"
        self.t0 = 0.0
        self.lead = None
        self.phase = None

    def on_reset(self):
        """A new map: the scripted lead went with the old one; undo whatever the running scenario changed."""
        self.lead = None
        if self.active != "cruise":
            self.restore()
        self.active = "cruise"
        self.phase = None

    def restore(self):
        app = self.app
        S = app.S
        S["gnss_outage"] = False
        S["plane"] = "fit"
        S["worn"] = []
        S["head_tracking"] = True
        S["sun_watch"] = True
        app.head.mode = "natural"
        d = app.driver
        d.drift = None
        d.lat_target = 0.0
        d.brake_until = -1.0
        d.ignore_until = -1.0
        d.set_speed = 26.8
        if app.env_key != "noon" or app.sun_override is not None:
            app.set_env("noon")
        self._drop_lead()

    def _drop_lead(self):
        if self.lead is not None:
            mgr = self.app.engine.arhud_manager
            try:
                mgr.clear_objects([self.lead["obj"].id])
            except Exception:
                pass
            self.lead = None

    def start(self, name):
        app = self.app
        self.restore()
        self.active = name
        self.t0 = app.t
        self.phase = None
        t = app.t
        info = INFO[name]
        app.ui.banner(info["title"], info["desc"])
        if name == "lead_brake":
            self._spawn_lead(28.0)
        elif name == "ped_crossing":
            self._spawn_ped(55.0)
        elif name == "lane_drift":
            app.driver.drift = dict(start=t + 2.0, rate=0.22, side=-1, max=1.7)
        elif name == "sun_patch":
            sun_world = app.rig.R @ np.array(PL.ENTRY_DIR, float)
            app.set_env("noon", sun=sun_world)
        elif name == "night":
            app.set_env("night")
            app.S["auto_dim"] = True
        elif name == "gnss_outage":
            app.S["gnss_outage"] = True
        elif name == "head_sway":
            app.head.mode = "sway"
        elif name == "hard_brake":
            app.S["plane"] = "static"
            app.driver.brake_until = t + 1.0 + 2.2
            app.driver.brake_from = t + 1.0
        elif name == "worn_paint":
            pos = app.ego.navigation.travelled_length
            app.S["worn"] = [(pos + 25.0, pos + 105.0)]
        elif name == "turn":
            self._jump_to_junction()

    def step(self, t):
        app = self.app
        app.S["route_pos"] = app.ego.navigation.travelled_length
        el = t - self.t0
        name = self.active
        if self.lead is not None:
            self._drive_lead(t)
        if self.lead is not None and int(t * 4) != int((t - 1 / 60) * 4):
            # keep random traffic out of the gap between the ego and the scripted car (4 times a second)
            p = app.rig.world_to_car(np.array([[*self.lead["obj"].position, 0.0]]))[0]
            self.clear_lane(x0=-8.0, x1=max(5.0, p[0] - 3.0))
        if name == "gnss_outage" and el > 12.0:
            app.S["gnss_outage"] = False
            self.active = "cruise"
            app.ui.toast("GNSS fix back")
        elif name == "head_sway":
            if el > 10.0 and self.phase is None:
                app.S["head_tracking"] = False
                self.phase = "tracker off"
                app.ui.toast("Head tracker OFF: hudd uses the nominal eye")
            if el > 20.0 and self.phase == "tracker off":
                app.S["head_tracking"] = True
                app.head.mode = "natural"
                self.phase = None
                self.active = "cruise"
                app.ui.toast("Head tracker on, sway stopped")
        elif name == "hard_brake" and el > 8.0:
            app.S["plane"] = "fit"
            self.active = "cruise"
            app.ui.toast("Ground plane: per-frame fit again")
        elif name == "lane_drift" and el > 11.0:
            app.driver.drift = None
            app.driver.lat_target = 0.0
            self.active = "cruise"

    # ---- traffic ------------------------------------------------------------------------------------------------
    def clear_lane(self, x0=-12.0, x1=110.0, half=2.2, centre=None):
        """Remove MetaDrive traffic from the ego lane between x0 and x1 m (car frame), so a scripted event is not
        hidden behind a random truck. Uses the traffic manager's own lists so it keeps running."""
        app = self.app
        eng = app.engine
        tm = getattr(eng, "traffic_manager", None)
        if tm is None:
            return 0
        rig = app.rig
        cy = PL.CAR_CENTER_Y if centre is None else centre
        ids = []
        for v in list(getattr(tm, "_traffic_vehicles", [])) + [eng.get_objects().get(i) for bv in
                                                               getattr(tm, "block_triggered_vehicles", [])
                                                               for i in bv.vehicles]:
            if v is None or v is app.ego:
                continue
            p = rig.world_to_car(np.array([[v.position[0], v.position[1], 0.0]]))[0]
            if x0 <= p[0] <= x1 and abs(p[1] - cy) < half:
                ids.append(v.id)
        if not ids:
            return 0
        tm._traffic_vehicles = [v for v in tm._traffic_vehicles if v.id not in ids]
        for bv in getattr(tm, "block_triggered_vehicles", []):
            bv.vehicles[:] = [i for i in bv.vehicles if i not in ids]     # a namedtuple: edit the list in place
        tm.clear_objects(ids)          # through the manager, so its own record of spawned objects stays consistent
        return len(ids)

    # ---- scripted lead -----------------------------------------------------------------------------------------
    def _spawn_lead(self, ahead):
        app = self.app
        self._drop_lead()
        self.clear_lane()
        chain = app.truth.chain(ahead=ahead + 10)
        cs = min(chain, key=lambda c: abs(c.a - ahead))
        mgr = app.engine.arhud_manager
        obj = mgr.spawn_object(MVehicle, vehicle_config=dict(spawn_lane_index=cs.lane.index,
                                                             spawn_longitude=float(cs.s), enable_reverse=False))
        v0 = max(8.0, float(app.ego.speed))
        self.lead = dict(obj=obj, lane=cs.lane, s=float(cs.s), v=v0, t0=app.t, phase="follow")
        app.driver.lead_override = None
        self._place_lead()

    def _place_lead(self):
        L = self.lead
        lane, s = L["lane"], L["s"]
        pos = lane.position(s, 0.0)
        h = lane.heading_theta_at(s)
        o = L["obj"]
        o.set_position([float(pos[0]), float(pos[1])])
        o.set_heading_theta(h)
        o.set_velocity([math.cos(h), math.sin(h)], L["v"])

    def _drive_lead(self, t):
        app = self.app
        L = self.lead
        dt = 1 / 60
        el = t - L["t0"]
        if L["phase"] == "follow" and el > 4.0:
            L["phase"] = "brake"
            L["tb"] = t
            app.driver.ignore_until = t + 1.4          # the driver is looking away when the brake lights come on
        if L["phase"] == "brake":
            L["v"] = max(0.0, L["v"] - 6.5 * dt)
            if L["v"] <= 0 and t - L["tb"] > 3.0:
                L["phase"] = "hold"
                L["th"] = t
        if L["phase"] == "hold" and t - L["th"] > 2.5:
            L["phase"] = "go"
        if L["phase"] == "go":
            L["v"] = min(22.0, L["v"] + 2.0 * dt)
            if t - L["th"] > 25:
                self._drop_lead()
                return
        L["s"] += L["v"] * dt
        while L["lane"] is not None and L["s"] > L["lane"].length:
            L["s"] -= L["lane"].length
            L["lane"] = app.truth._next_lane(L["lane"])
        if L["lane"] is None:
            self._drop_lead()
            return
        self._place_lead()

    # ---- pedestrian -----------------------------------------------------------------------------------------------
    def _spawn_ped(self, ahead):
        """A pedestrian steps off the right kerb timed to be in the ego lane when the car is about 22 m away
        (if the driver kept speed)."""
        app = self.app
        self.clear_lane(x1=150.0)
        v = max(6.0, float(app.ego.speed))
        walk = 1.4
        cs0 = app.truth.chain(ahead=10.0)[0]
        lat_kerb0 = (cs0.n - cs0.i - 0.5) * cs0.w + 1.2
        ahead = max(ahead, v * lat_kerb0 / walk + 22.0 + PL.EYE_TO_FRONT_BUMPER)
        chain = app.truth.chain(ahead=ahead + 10)
        cs = min(chain, key=lambda c: abs(c.a - ahead))
        w = cs.w
        lat_kerb = (cs.n - cs.i - 0.5) * w + 1.2
        lat_far = (-cs.i - 0.5) * w - 1.0
        p0 = cs.lane.position(cs.s, lat_kerb)
        p1 = cs.lane.position(cs.s, lat_far)
        reach = (ahead - 22.0 - PL.EYE_TO_FRONT_BUMPER) / v
        delay = max(0.0, reach - lat_kerb / walk)
        self.ped_eta = app.t + reach
        app.engine.arhud_manager.spawn_walker("person", [p0, p1], walk, start_delay=delay)

    # ---- jump to the next junction -----------------------------------------------------------------------------
    def _jump_to_junction(self):
        app = self.app
        chain = app.truth.chain(ahead=1500.0)
        man = app.truth.next_manoeuvre(chain, min_a=150.0)      # a junction far enough ahead to jump back from
        if man is None:
            app.ui.toast("No junction ahead on this route")
            return
        a_target = max(0.0, man["a_turn"] - 130.0)
        cs = min(chain, key=lambda c: abs(c.a - a_target))
        pos = cs.lane.position(cs.s, 0.0)
        h = cs.lane.heading_theta_at(cs.s)
        ego = app.ego
        ego.set_position([float(pos[0]), float(pos[1])])
        ego.set_heading_theta(h)
        ego.set_velocity([math.cos(h), math.sin(h)], 13.4)
        app.rig.update()
        self.clear_lane(-20.0, 140.0, half=6.0)
        app.hist = EgoHistory()
        app.perc.queue.clear()
        app.hudd.delta_cache.clear()
        app.hudd.tracks.clear()
        app.hudd.line_state.clear()
        app.hudd.msg = None
