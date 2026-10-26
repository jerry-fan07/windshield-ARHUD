"""The application: MetaDrive drives the world; every frame (after physics, before rendering) the HUD software runs on
that frame's ground truth and the result is drawn into the driver's view.

Per frame (60 Hz sim time; the window runs in real time unless --fast):
  truth -> ego history -> (every 2nd frame) camera capture into the latency queue -> head tracker
  -> hudd (newest published message, compensation, projection, drawing rules, added features)
  -> controllerd (dimming, thermal, sun-watch, shutter) -> optics (texture, gain, ghost, vignette) -> panels
"""
import math
import os
import sys
import time

import numpy as np
from panda3d.core import KeyboardButton, PNMImage

from . import plan as PL
from .controllerd import Controller
from .driver import HeadMotion, SimDriver
from .features import Features
from .frames import CarRig, VirtualPlane, car_to_local
from .hudd import Hudd, default_settings
from .optics import Optics
from .perception import EgoHistory, HeadTracker, Perception, visible_face
from .scenarios import SCENARIOS, Scenarios
from .truth import Truth
from .ui import UI
from .world import apply_environment, make_env

DT = 1.0 / 60.0
ZOOMS = [("Wide", 60.0, 2.5), ("Normal", 35.0, 3.5), ("HUD", 16.0, 5.0)]   # label, horizontal FOV, look-down


class App:
    def __init__(self, args):
        self.args = args
        self.env = make_env(args)
        self.S = default_settings()
        self.S["window"] = args.hud_window
        self.S["content"] = args.content
        self.plane = VirtualPlane(self.S["window"])
        self.hudd = Hudd(self.plane, self.S)
        self.ctrl = Controller(self.S)
        self.driver = SimDriver()
        self.head = HeadMotion()
        self.tracker = HeadTracker()
        self.hist = EgoHistory()
        self.perc = Perception(self.S)
        self.features = Features(self)
        self.hudd.features = self.features
        self.scen = Scenarios(self)
        self.env_key = args.env
        self.view = "driver"
        self.zoom = 1
        self.frame_i = 0
        self.t = 0.0
        self.ready = False
        self.fps = 0.0
        self._fps_t = time.time()
        self._fps_n = 0
        self.sun_override = None
        self.paused = False
        self.quit = False
        self.shots = []
        self.timing = dict(hud=0.0, total=0.0)
        self.speed_prev = 0.0
        self.vz_prev = 0.0
        self.last_truth = None
        self.reset(first=True, seed=args.seed)

    # ---- episode setup --------------------------------------------------------------------------------------------
    def reset(self, first=False, seed=None):
        if not first:
            # keep the car frame (and the camera, cockpit and explain geometry under it) out of the old vehicle's
            # node, which MetaDrive may destroy on reset; MetaDrive may reuse the vehicle as traffic, so show it
            self.hide_ego(False)
            self.engine.camera.reparentTo(self.engine.render)
            self.rig.np.detachNode()
        self.env.reset(seed=seed)
        eng = self.env.engine
        self.engine = eng
        # The chase camera task comes back with every reset; this app places the camera itself.
        if eng.task_manager.hasTaskNamed(eng.main_camera.CHASE_TASK_NAME):
            eng.task_manager.remove(eng.main_camera.CHASE_TASK_NAME)
        if eng.task_manager.hasTaskNamed(eng.main_camera.TOP_DOWN_TASK_NAME):
            eng.task_manager.remove(eng.main_camera.TOP_DOWN_TASK_NAME)
        for key in ("r", "c", "p", "b", "q", "]", "[", "h", "f", "1", "2", "3", "4", "5", "mouse1", "wheel_up",
                    "wheel_down", "+", "-", "=", "_"):
            eng.ignore(key)
        self.ego = self.env.agent
        self.own_ego_body()
        # settle the chassis to find its rest height, then hang the car frame off it
        z = []
        for _ in range(20):
            self.env.step([0.0, 0.0])
            z.append(self.ego.origin.getZ())
        if first:
            self.rig = CarRig(eng.render)
        self.rig.attach(self.ego, float(np.median(z[-8:])))
        self.rig.update()
        self.truth = Truth(eng, self.ego)
        self.truth.signs = getattr(eng, "arhud_signs", [])
        if first:
            self.optics = Optics(eng, self.rig, self.plane)
            self.optics.place_image(self.ghost_scale())
            self.ui = UI(self)
            eng.taskMgr.add(self.frame_task, "arhud-frame", sort=45)
            self.bind_keys()
        else:
            self.optics.cockpit.reparentTo(self.rig.np)
            self.optics.build_explain()
            # the ignore() loop above also dropped this app's own handlers for those keys: bind them again
            self.bind_keys()
            self.ui.bind()
            self.ui.reattach_camera()
        eng.force_fps.disable()            # MetaDrive sleeps a fixed interval per frame; run() paces to sim time
        self.hide_ego(self.view == "driver")
        self.set_view(self.view)
        self.sun_world = apply_environment(eng, self.env_key, self.sun_override)
        # the clock restarts at 0: drop everything keyed by time
        self.hist = EgoHistory()
        self.perc = Perception(self.S)
        self.tracker = HeadTracker()
        self.hudd.line_state.clear()
        self.hudd.tracks.clear()
        self.hudd.delta_cache.clear()
        self.hudd.msg = None
        self.hudd.sign.update(value=None, t=-1e9, cand=None, count=0, box=None, boxT=-1e9)
        self.scen.on_reset()
        self.frame_i = 0
        self.t = 0.0
        self.ready = True

    def own_ego_body(self):
        """MetaDrive instances one body model across every vehicle of a class, so hiding the ego's body node would
        hide that body on all traffic cars of the class. Give the ego a private copy of its body (the wheels stay:
        Bullet drives their nodes) and hide only the copy in the driver view."""
        from metadrive.component.vehicle.base_vehicle import BaseVehicle
        shared = {m.node() for m in BaseVehicle.model_collection.values()}
        o = self.ego.origin
        self.ego_body = []
        for ch in list(o.getChildren()):
            if ch.hasTag("arhud-body"):
                self.ego_body.append(ch)
            elif ch.node() in shared:
                cp = ch.copyTo(o)
                cp.setTag("arhud-body", "1")
                ch.detachNode()
                self.ego_body.append(cp)

    def hide_ego(self, hide):
        for n in getattr(self, "ego_body", []):
            (n.hide if hide else n.show)()

    def ghost_scale(self):
        return {"off": 0.0, "true": 1.0, "x20": 20.0}[self.S["ghost"]]

    # ---- views ----------------------------------------------------------------------------------------------------
    def set_view(self, view):
        self.view = view
        cam = self.engine.camera
        lens = self.engine.cam.node().getLens()
        if view == "driver":
            cam.reparentTo(self.rig.np)
            lens.setFov(ZOOMS[self.zoom][1])
            lens.setNear(0.05)
        else:
            cam.reparentTo(self.engine.render)
            lens.setFov(60 if view == "chase" else 50)
            lens.setNear(0.2)
        self.hide_ego(view == "driver")
        self.optics.set_view(view)

    def place_camera(self, eye_off):
        cam = self.engine.camera
        if self.view == "driver":
            e = self.plane.eye0 + eye_off
            cam.setPos(*car_to_local(e))
            cam.setHpr(0, -ZOOMS[self.zoom][2], 0)
        elif self.view == "chase":
            p = self.rig.car_to_world(np.array([[-7.5, PL.CAR_CENTER_Y + 2.2, 3.4]]))[0]
            look = self.rig.car_to_world(np.array([[14.0, PL.CAR_CENTER_Y, 0.4]]))[0]
            cam.setPos(*p)
            cam.lookAt(*look)
        else:
            p = self.rig.car_to_world(np.array([[22.0, PL.CAR_CENTER_Y, 75.0]]))[0]
            cam.setPos(*p)
            cam.setHpr(math.degrees(self.rig.heading) - 90, -90, 0)

    # ---- keys -----------------------------------------------------------------------------------------------------
    def bind_keys(self):
        eng = self.engine
        A = self.actions()
        for key, fn in A.items():
            eng.accept(key, fn)
        eng.accept("escape", self.request_quit)          # MetaDrive's own handler calls sys.exit without cleanup

    def actions(self):
        S = self.S

        def cyc(key, options):
            def f():
                i = options.index(S[key]) if S[key] in options else -1
                S[key] = options[(i + 1) % len(options)]
                self.ui.toast(f"{key.replace('_', ' ')}: {S[key]}")
                self.on_setting(key)
            return f

        def tog(key):
            def f():
                S[key] = not S[key]
                self.ui.toast(f"{key.replace('_', ' ')}: {'on' if S[key] else 'off'}")
                self.on_setting(key)
            return f

        def feat(name):
            def f():
                S["features"][name] = not S["features"][name]
                self.ui.toast(f"{Features.NAMES[name]}: {'on' if S['features'][name] else 'off'}")
            return f

        return {
            "1": lambda: self.set_view("driver"),
            "2": lambda: self.set_view("chase"),
            "3": lambda: self.set_view("top"),
            "z": self.cycle_zoom,
            "tab": self.ui.toggle_panels,
            "shift-/": self.ui.toggle_help,
            "/": self.ui.toggle_help,
            "m": self.toggle_manual,
            "k": cyc("content", ["plus", "plan"]),
            "w": cyc("window", ["spec", "traced", "stage1"]),
            "p": cyc("pgu", [s["key"] for s in PL.PGU_SOURCES]),
            "c": cyc("compensation", ["photon", "draw", "off"]),
            "t": tog("head_tracking"),
            "g": cyc("ghost", ["true", "x20", "off"]),
            "d": tog("auto_dim"),
            "l": cyc("plane", ["fit", "static+imu", "static"]),
            "o": tog("sunglasses"),
            "u": tog("sun_watch"),
            "n": tog("gnss_outage"),
            "v": self.clutter,
            "x": tog("truth_overlay"),
            "b": tog("show_window"),
            "j": self.cycle_head,
            "e": self.cycle_env,
            "f": self.ui.toggle_camera_inset,
            "r": lambda: self.request_reset(+0),
            "]": lambda: self.request_reset(+1),
            "[": lambda: self.request_reset(-1),
            "space": self.toggle_pause,
            ",": lambda: self.signal(-1),
            ".": lambda: self.signal(+1),
            "shift-1": feat("nav"), "shift-2": feat("ldw"), "shift-3": feat("fcw"), "shift-4": feat("gap"),
            "shift-5": feat("curve"), "shift-6": feat("pedpath"), "shift-7": feat("overspeed"),
            "shift-8": feat("eyebox"), "shift-9": feat("occlusion"),
            "f1": lambda: self.scen.start("cruise"), "f2": lambda: self.scen.start("lead_brake"),
            "f3": lambda: self.scen.start("ped_crossing"), "f4": lambda: self.scen.start("lane_drift"),
            "f5": lambda: self.scen.start("sun_patch"), "f6": lambda: self.scen.start("night"),
            "f7": lambda: self.scen.start("gnss_outage"), "f8": lambda: self.scen.start("head_sway"),
            "f9": lambda: self.scen.start("hard_brake"), "f10": lambda: self.scen.start("worn_paint"),
            "f11": lambda: self.scen.start("turn"), "f12": self.screenshot,
            "s": self.screenshot,
            "=": lambda: self.dim(+1), "-": lambda: self.dim(-1),
        }

    def on_setting(self, key):
        if key == "window":
            self.plane.set(self.S["window"])
            self.optics.place_image(self.ghost_scale())
        if key == "ghost":
            self.optics.place_image(self.ghost_scale())

    def cycle_zoom(self):
        self.zoom = (self.zoom + 1) % len(ZOOMS)
        if self.view == "driver":
            self.engine.cam.node().getLens().setFov(ZOOMS[self.zoom][1])
        self.ui.toast(f"Driver view: {ZOOMS[self.zoom][0]} ({ZOOMS[self.zoom][1]:.0f} deg)")

    def toggle_manual(self):
        self.driver.mode = "manual" if self.driver.mode == "auto" else "auto"
        self.driver.steer_state = 0.0
        self.ui.toast("You drive (arrow keys)" if self.driver.mode == "manual" else "Simulated driver")

    def cycle_head(self):
        m = HeadMotion.MODES
        self.head.mode = m[(m.index(self.head.mode) + 1) % len(m)]
        self.ui.toast(f"Head motion: {self.head.mode}")

    def cycle_env(self):
        keys = list(PL.ENVIRONMENTS)
        self.set_env(keys[(keys.index(self.env_key) + 1) % len(keys)])

    def set_env(self, key, sun=None):
        self.env_key = key
        self.sun_override = sun
        self.sun_world = apply_environment(self.engine, key, sun)
        self.ui.toast(f"Scene: {PL.ENVIRONMENTS[key]['label']}")

    def clutter(self):
        self.S["clutter_until"] = self.t + 10.0
        self.ui.toast("Clutter mode for 10 s (demo contrast)")

    def dim(self, step):
        self.S["dim_steps"] = max(-4, min(4, self.S["dim_steps"] + step))
        self.ui.toast(f"Brightness offset {self.S['dim_steps']:+d} step")

    def signal(self, side):
        self.driver.signal = 0 if self.driver.signal == side else side
        self.driver.signal_until = self.t + 6.0

    def request_quit(self):
        self.quit = True

    def toggle_pause(self):
        self.paused = not self.paused

    def request_reset(self, d):
        self._pending_reset = d

    def screenshot(self, path=None):
        out = path or os.path.join(self.args.out, f"arhud-road-{time.strftime('%Y%m%d-%H%M%S')}-{self.frame_i}.png")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        self.engine.win.saveScreenshot(out)
        if not self.args.shots:
            self.ui.toast(f"Saved {os.path.basename(out)}")
        return out

    # ---- the frame ----------------------------------------------------------------------------------------------
    def frame_task(self, task):
        if not self.ready:
            return task.cont
        t0 = time.perf_counter()
        self.frame_i += 1
        self.t = self.frame_i * DT
        t = self.t
        rig = self.rig
        rig.update()
        ego = self.ego
        # ---- ground truth --------------------------------------------------------------------------------------
        chain = self.truth.chain(behind=8.0, ahead=160.0)
        lines = self.truth.boundaries(chain)
        objs = self.truth.objects()
        self.chain, self.lines_w, self.objs_w = chain, lines, objs
        lines_c = []
        for b, L in lines.items():
            P = rig.world_to_car(np.hstack([L["pts"], np.zeros((len(L["pts"]), 1))]))
            lines_c.append(dict(id=f"b{b}", rel=L["rel"][min(len(L["rel"]) - 1, int(np.searchsorted(L["a"], 0)))],
                                pts=P, kind=L["kind"]))
        objs_c = []
        for o in objs:
            pc = rig.world_to_car(np.array([[o["pos"][0], o["pos"][1], 0.0]]))[0]
            hd = rig.R.T @ np.array([math.cos(o["heading"]), math.sin(o["heading"]), 0.0])
            vel = rig.R.T @ np.array([o["vel"][0], o["vel"][1], 0.0])
            q = dict(o)
            q.update(p=pc, hd=hd, vx=float(vel[0]), vy=float(vel[1]))
            q["face"] = visible_face(pc, o, rig, np.array(PL.ROAD_CAM))
            objs_c.append(q)
        centre_w, centre_a = self.truth.centreline(chain)
        centre_c = rig.world_to_car(np.hstack([centre_w, np.zeros((len(centre_w), 1))]))
        self.truth_now = dict(lines=lines_c, objects=objs_c, centre=centre_c, centre_a=centre_a)
        # ---- ego state (egod's truth source) -------------------------------------------------------------------
        v = float(ego.speed)
        fwd = rig.R[:, 0]
        yaw_rate = 0.0
        if len(self.hist.buf):
            prev = self.hist.buf[-1]
            dpsi = (rig.heading - prev["heading"] + math.pi) % (2 * math.pi) - math.pi
            yaw_rate = dpsi / DT
        vz = float(ego.origin.getZ())
        az = (vz - self.vz_prev) / DT if self.frame_i > 1 else 0.0
        self.vz_prev = vz
        accel = (v - self.speed_prev) / DT if self.frame_i > 1 else 0.0
        self.speed_prev = v
        self.hist.push(dict(t=t, speed=v, yaw_rate=yaw_rate, heading=rig.heading, accel=accel, pitch=rig.pitch))
        self.accel = accel
        self.yaw_rate = yaw_rate
        # ---- scenarios (scripted events) -----------------------------------------------------------------------
        self.scen.step(t)
        # ---- camera capture at 30 Hz ---------------------------------------------------------------------------
        if self.frame_i % 2 == 0:
            self.perc.capture(t, self.truth, chain, lines, objs, rig, self.env_key)
        # ---- head ------------------------------------------------------------------------------------------------
        eye_off = self.head.offset(t, az * 0.0, DT)
        self.eye_off = eye_off
        self.tracker.push(t, eye_off)
        self.place_camera(eye_off)
        # ---- hudd, controllerd -----------------------------------------------------------------------------------
        th = time.perf_counter()
        ctx = dict(perception=self.perc, hist=self.hist, tracker=self.tracker, eye_true_off=eye_off,
                   truth_now=self.truth_now, speed_true=v, rig=rig, chain=chain)
        self.ctx = ctx
        self.features.pre(t, ctx)
        self.hudd.update(t, ctx)
        sun_car = rig.R.T @ self.sun_world
        self.ctrl.update(DT, self.env_key, sun_car)
        self.sun_car = sun_car
        frame = self.hudd.frame
        frame = self.optics.apply_vignette(frame, eye_off)
        self.optics.upload(frame)
        self.timing["hud"] = (time.perf_counter() - th) * 1000
        E = PL.ENVIRONMENTS[self.env_key]
        self.optics.update(self.ctrl.overlay_gain(self.env_key), self.ctrl.black_gain(self.env_key), self.S["ghost"],
                           E["scene"], E["sky"] if self.env_key != "noon" else (1.0, 1.0, 1.0), self.S["show_window"],
                           bref=self.ctrl.background_lin(self.env_key))
        # ---- driver for the next physics step -------------------------------------------------------------------
        lim = self.features.posted_limit()
        self.action = self.driver.act(t, DT, ego, rig, centre_c, lines_c, objs_c, lim, self.features.route_cap)
        if self.driver.mode == "manual":
            mw = self.engine.mouseWatcherNode
            k = self.driver.keys
            k["up"] = mw.is_button_down(KeyboardButton.up())
            k["down"] = mw.is_button_down(KeyboardButton.down())
            k["left"] = mw.is_button_down(KeyboardButton.left())
            k["right"] = mw.is_button_down(KeyboardButton.right())
        # ---- panels --------------------------------------------------------------------------------------------
        self.ui.update(t)
        self._fps_n += 1
        now = time.time()
        if now - self._fps_t > 0.5:
            self.fps = self._fps_n / (now - self._fps_t)
            self._fps_t, self._fps_n = now, 0
        self.timing["total"] = (time.perf_counter() - t0) * 1000
        self.record(t, v)
        return task.cont

    # ---- logd, in miniature: per-frame numbers to CSV and a summary at exit ------------------------------------
    LOG_FIELDS = ("t", "scenario", "env", "window", "pgu", "speed_ms", "speed_shown_ms", "res_lane10", "res_lane20",
                  "res_lane30", "res_lead", "age_lanes_ms", "eye_dy_mm", "eye_dz_mm", "tracker", "pitch_true_deg",
                  "pitch_est_deg", "L_eye", "contrast_road", "contrast_sky", "shutter", "cell_C", "fcw", "ttc_s",
                  "ldw", "nav_dist_m")

    def record(self, t, v):
        st = self.hudd.stats
        if not hasattr(self, "metrics"):
            self.metrics = {}
            self._log = None
            if self.args.log:
                os.makedirs(os.path.dirname(os.path.abspath(self.args.log)), exist_ok=True)
                self._log = open(self.args.log, "w")
                self._log.write(",".join(self.LOG_FIELDS) + "\n")
        for k in ("res_lane10", "res_lane20", "res_lane30", "res_lead"):
            val = st.get(k + "_raw")
            if val is not None:
                label = getattr(self, "bench_label", None) or (self.scen.active + (f"/{self.scen.phase}" if
                                                                                    self.scen.phase else ""))
                self.metrics.setdefault((label, k), []).append(val)
        if self._log is not None and self.frame_i % 6 == 0:
            m = self.hudd.msg
            F = self.features
            row = dict(t=f"{t:.3f}", scenario=self.scen.active, env=self.env_key, window=self.S["window"],
                       pgu=self.S["pgu"], speed_ms=f"{v:.3f}",
                       speed_shown_ms="" if st.get("speed_shown") is None else f"{st['speed_shown']:.3f}",
                       age_lanes_ms=f"{st['age_lanes'] * 1000:.1f}", eye_dy_mm=f"{self.eye_off[1] * 1000:.1f}",
                       eye_dz_mm=f"{self.eye_off[2] * 1000:.1f}",
                       tracker="nominal" if self.hudd.eye_nominal else "tracked",
                       pitch_true_deg="" if m is None else f"{math.degrees(m['plane']['pitch_true']):.3f}",
                       pitch_est_deg="" if m is None else f"{math.degrees(m['plane']['pitch_est']):.3f}",
                       L_eye=f"{self.ctrl.lum['Leye']:.1f}", contrast_road=f"{self.ctrl.lum['contrast_road']:.3f}",
                       contrast_sky=f"{self.ctrl.lum['contrast_sky']:.3f}", shutter=f"{self.ctrl.shutter:.2f}",
                       cell_C=f"{self.ctrl.cell:.1f}", fcw=F.fcw.get("state", ""),
                       ttc_s="" if F.fcw.get("ttc") is None else f"{F.fcw['ttc']:.2f}",
                       ldw="L" if F.ldw.get("left") else "R" if F.ldw.get("right") else "",
                       nav_dist_m="" if F.man is None else f"{max(0.0, F.man['a_turn']):.1f}")
            for k in ("res_lane10", "res_lane20", "res_lane30", "res_lead"):
                val = st.get(k + "_raw")
                row[k] = "" if val is None else f"{val:.4f}"
            self._log.write(",".join(str(row.get(f, "")) for f in self.LOG_FIELDS) + "\n")

    def summary(self):
        """Registration residuals by scenario: median and 95th percentile, degrees, from the true eye."""
        if not getattr(self, "metrics", None):
            return ""
        lines = ["", "Registration residuals (deg, drawn vs true from the true eye; plan: <= 0.5 static at 30 m, "
                     "<= 0.3 under head motion with the tracker)",
                 f"{'condition':<32}{'element':<10}{'frames':>8}{'median':>9}{'95th':>9}"]
        for (sc, k), vals in sorted(self.metrics.items()):
            arr = np.array(vals)
            lines.append(f"{sc:<32}{k.replace('res_', ''):<10}{len(arr):>8}{np.median(arr):>9.3f}"
                         f"{np.percentile(arr, 95):>9.3f}")
        return "\n".join(lines)

    # ---- main loop ------------------------------------------------------------------------------------------------
    def run(self):
        self.action = [0.0, 0.0]
        self._pending_reset = None
        script = self.args.shots
        t_end = self.args.duration
        self.wall0, self.sim0 = time.perf_counter(), self.t
        n_frames, w_start = 0, time.perf_counter()
        while not self.quit:
            # real time: hold the loop back when the simulation runs ahead of the clock
            if not self.args.fast:
                ahead = (self.t - self.sim0) - (time.perf_counter() - self.wall0)
                if ahead > 0.002:
                    time.sleep(min(ahead, 0.05))
                elif ahead < -0.25:
                    self.wall0, self.sim0 = time.perf_counter(), self.t     # fell behind: do not try to catch up
            n_frames += 1
            if self.args.scenario and not getattr(self, "_scenario_started", False) and self.t >= 3.0:
                self._scenario_started = True
                self.scen.start(self.args.scenario)
            if self._pending_reset is not None:
                d = self._pending_reset
                self._pending_reset = None
                self.ready = False
                seed = None
                if d != 0:
                    cur = self.engine.current_seed
                    lo, hi = self.args.seed, self.args.seed + self.args.scenarios - 1
                    seed = min(hi, max(lo, cur + d))
                self.reset(seed=seed)
                self.wall0, self.sim0 = time.perf_counter(), self.t
                continue
            if self.paused:
                self.engine.taskMgr.step()
                continue
            _, _, term, trunc, info = self.env.step(self.action)
            if info.get("arrive_dest") or term:
                self.ready = False
                self.reset()
                self.wall0, self.sim0 = time.perf_counter(), self.t
                continue
            if script:
                while script and self.t >= script[0][0]:
                    ts, name, cmds = script.pop(0)
                    for c in cmds:
                        self.command(c)
                    if name:
                        self.engine.taskMgr.step()
                        self.screenshot(os.path.join(self.args.out, name))
                if not script and self.args.exit_after_shots:
                    break
            if t_end and self.t >= t_end:
                break
        wall = time.perf_counter() - w_start
        print(f"arhud-road: {n_frames} frames in {wall:.1f} s = {n_frames / max(wall, 1e-6):.1f} fps; "
              f"sim {self.t:.1f} s", flush=True)
        print(self.summary(), flush=True)
        if getattr(self, "_log", None) is not None:
            self._log.close()
            print(f"log: {self.args.log}", flush=True)
        self.env.close()

    # Each condition replays the same seeded drive from the start (traffic and noise are deterministic for a seed), so
    # the rows of the summary differ only in the condition.
    BENCH = [
        ("baseline", []),
        ("sway, tracker on", ["head:sway"]),
        ("sway, tracker off", ["head:sway", "set:head_tracking=off"]),
        ("compensate to draw time", ["set:compensation=draw"]),
        ("no compensation", ["set:compensation=off"]),
        ("GNSS outage", ["set:gnss_outage=on"]),
        ("brake 8 s, static plane", ["set:plane=static", "brake:8"]),
        ("brake 8 s, plane fit", ["set:plane=fit", "brake:8"]),
        ("traced window", ["set:window=traced"]),
        ("scripted lead brakes", ["scenario:lead_brake"]),
        ("lead brakes, no compensation", ["scenario:lead_brake", "set:compensation=off"]),
    ]

    def run_bench(self, duration=24.0):
        from .hudd import default_settings
        self.action = [0.0, 0.0]
        self._pending_reset = None
        self.ui.set_panels(False)
        self.ui.set_camera_inset(False)
        w0 = time.perf_counter()
        for label, cmds in self.BENCH:
            fresh = default_settings()
            self.S.clear()
            self.S.update(fresh)
            self.hudd.S = self.perc.S = self.ctrl.S = self.S
            self.head.mode = "natural"
            self.driver.__init__()
            self.plane.set("spec")
            self.optics.place_image(self.ghost_scale())
            self.ready = False
            self.reset(seed=self.args.seed)
            self.hudd.stats.update(res_lane10=None, res_lane20=None, res_lane30=None, res_lead=None)
            self.bench_label = label
            for c in cmds:
                if c.startswith("brake:"):
                    t0 = float(c.split(":")[1])
                    self.driver.brake_from, self.driver.brake_until = t0, t0 + 2.2
                else:
                    self.command(c)
            while self.t < duration and not self.quit:
                self.env.step(self.action)
            print(f"  {label}: {self.t:.0f} s simulated", flush=True)
        print(f"arhud-road bench: {len(self.BENCH)} conditions in {time.perf_counter() - w0:.0f} s", flush=True)
        print(self.summary(), flush=True)
        self.env.close()

    def command(self, c):
        """Scripted command, as from the keyboard: 'key:<k>', 'scenario:<name>', 'view:<v>', 'zoom:<i>',
        'set:<key>=<value>', 'feature:<name>=on|off', 'env:<key>', 'head:<mode>', 'panels:on|off'."""
        kind, _, arg = c.partition(":")
        if kind == "key":
            self.actions()[arg]()
        elif kind == "scenario":
            self.scen.start(arg)
        elif kind == "view":
            self.set_view(arg)
        elif kind == "zoom":
            self.zoom = int(arg)
            self.set_view(self.view)
        elif kind == "set":
            k, _, v = arg.partition("=")
            cur = self.S[k]
            self.S[k] = (v == "on") if isinstance(cur, bool) else type(cur)(v) if not isinstance(cur, list) else cur
            self.on_setting(k)
        elif kind == "feature":
            k, _, v = arg.partition("=")
            self.S["features"][k] = v == "on"
        elif kind == "env":
            self.set_env(arg)
        elif kind == "head":
            self.head.mode = arg
        elif kind == "panels":
            self.ui.set_panels(arg == "on")
        elif kind == "inset":
            self.ui.set_camera_inset(arg == "on")
        elif kind == "label":
            self.scen.active = arg               # a name for the metrics, without changing anything
            self.scen.phase = None
