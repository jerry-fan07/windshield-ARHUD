"""Panels drawn with OpenCV/PIL (Helvetica Neue) into textures on MetaDrive's 2-D layer.

Left: the controls, each with its key; click a row or press the key. Right: live numbers beside the plan's acceptance
criteria. Bottom: the PGU frame as drawn (the texture the virtual image shows), the road camera (ZED 2i left lens)
with what perception reported, and a top-down map of the truth, the detections and the road the window covers.
Tab hides everything; ? shows the keys.
"""
import math
import time

import cv2
import numpy as np
from panda3d.core import CardMaker, NodePath, Texture, TransparencyAttrib, PerspectiveLens

from . import plan as PL
from .canvas import Panel, text_size
from .features import Features
from .scenarios import SCENARIOS

BG = (15, 17, 21, 222)
FG = (232, 236, 242)
DIM = (150, 158, 170)
ACC = (110, 190, 255)
OK = (110, 220, 140)
BAD = (255, 110, 90)
WARN = (255, 190, 80)
HEAD = (130, 140, 155)


def app_env(app):
    return app.env_key


class TexCard:
    def __init__(self, parent, w, h, name):
        self.w, self.h = w, h
        self.panel = Panel(w, h)
        self.tex = Texture(name)
        self.tex.setup2dTexture(w, h, Texture.T_unsigned_byte, Texture.F_rgba8)
        self.tex.setMinfilter(Texture.FT_linear)
        self.tex.setMagfilter(Texture.FT_linear)
        cm = CardMaker(name)
        cm.setFrame(0, w, -h, 0)
        cm.setUvRange((0, 1), (1, 0))
        self.np = parent.attachNewNode(cm.generate())
        self.np.setTexture(self.tex)
        self.np.setTransparency(TransparencyAttrib.M_alpha)

    def upload(self):
        self.tex.setRamImage(self.panel.img.tobytes())

    def pos(self, x, y):
        self.np.setPos(x, 0, -y)

    def contains(self, px, py):
        if self.np.isHidden():
            return False
        p = self.np.getPos()
        return p[0] <= px <= p[0] + self.w and -p[2] <= py <= -p[2] + self.h


class UI:
    def __init__(self, app):
        self.app = app
        eng = app.engine
        self.eng = eng
        self.root = eng.pixel2d.attachNewNode("arhud-ui")
        self.W, self.H = eng.win.getXSize(), eng.win.getYSize()
        lw = 318
        rw = 340
        self.top = TexCard(self.root, self.W, 30, "ui-top")
        self.left = TexCard(self.root, lw, self.H - 40, "ui-left")
        self.right = TexCard(self.root, rw, self.H - 40, "ui-right")
        avail = self.W - lw - rw - 4 * 8
        self.inset_w = int(max(240, min(378, (avail - 10) / 2)))
        ms = int(max(170, min(250, self.H * 0.28)))
        self.mapc = TexCard(self.root, ms, ms, "ui-map")
        self.banner_w = int(max(360, min(760, avail)))
        self.banner_c = TexCard(self.root, self.banner_w, 74, "ui-banner")
        self.toast_c = TexCard(self.root, 520, 34, "ui-toast")
        self.help_c = TexCard(self.root, 820, 560, "ui-help")
        # PGU inset: the optics texture itself, with a frame label panel
        self.pgu_w = self.inset_w
        self.pgu_h = int(self.pgu_w * PL.CROP_H / PL.CROP_W)
        cm = CardMaker("ui-pgu")
        cm.setFrame(0, self.pgu_w, -self.pgu_h, 0)
        cm.setUvRange((0, 1), (1, 0))
        self.pgu = self.root.attachNewNode(cm.generate())
        self.pgu.setTexture(app.optics.tex)
        self.pgu_label = TexCard(self.root, self.pgu_w, 22, "ui-pgu-label")
        # road camera inset (ZED 2i left lens), an extra render of the scene into a texture
        self.cam_w, self.cam_h = self.inset_w, int(self.inset_w * 9 / 16)
        self.cam_on = not app.args.no_camera_inset
        self.cam_buf = None
        self.cam_card = None
        self.cam_over = TexCard(self.root, self.cam_w, self.cam_h + 22, "ui-cam-over")
        if self.cam_on:
            self._make_camera()
        self.rows = []
        self.panels_on = not app.args.no_panels
        self.help_on = False
        self.toast_msg, self.toast_t = None, -1
        self.banner_msg, self.banner_t = None, -1
        self.last = dict(left=-1, right=-1, top=-1, map=-1, cam=-1)
        self.layout()
        self.bind()
        self.help_c.np.hide()
        self.banner_c.np.hide()
        self.toast_c.np.hide()
        self.set_panels(self.panels_on)

    def bind(self):
        self.eng.accept("mouse1", self.on_click)
        self.eng.accept("window-event", self.on_window)

    # ---- layout --------------------------------------------------------------------------------------------------
    def on_window(self, win):
        try:
            W, H = win.getXSize(), win.getYSize()
        except Exception:
            return
        if (W, H) != (self.W, self.H) and W > 100 and H > 100:
            self.W, self.H = W, H
            self.layout()

    def layout(self):
        """Left and right panels full height; the two insets side by side along the bottom between them; the map at
        the top of the space between the panels."""
        W, H = self.W, self.H
        if self.top.w != W:
            self.top.np.removeNode()
            self.top = TexCard(self.root, W, 30, "ui-top")
        self.top.pos(0, 0)
        self.left.pos(8, 38)
        self.right.pos(W - self.right.w - 8, 38)
        x_mid0 = 8 + self.left.w + 8
        x_mid1 = W - self.right.w - 16
        bx = x_mid1 - self.pgu_w
        by = H - self.pgu_h - 8
        self.pgu.setPos(bx, 0, -by)
        self.pgu_label.pos(bx, by - 22)
        self.cam_pos = (bx - 10 - self.cam_w, H - self.cam_h - 8)
        self.cam_over.pos(self.cam_pos[0], self.cam_pos[1] - 22)
        if self.cam_card is not None:
            self.cam_card.setPos(self.cam_pos[0], 0, -self.cam_pos[1])
        self.mapc.pos(x_mid0, 38)
        self.banner_c.pos(x_mid0 + (x_mid1 - x_mid0 - self.banner_w) / 2, 40)
        self.toast_c.pos((W - 520) / 2, H - max(self.pgu_h, self.cam_h) - 70)
        self.help_c.pos((W - 820) / 2, (H - 560) / 2)

    def set_panels(self, on):
        self.panels_on = on
        for c in (self.left, self.right, self.mapc, self.pgu_label, self.cam_over):
            (c.np.show if on else c.np.hide)()
        (self.pgu.show if on else self.pgu.hide)()
        if self.cam_card is not None:
            (self.cam_card.show if on and self.cam_on else self.cam_card.hide)()
        if not self.cam_on:
            self.cam_over.np.hide()

    def toggle_panels(self):
        self.set_panels(not self.panels_on)

    def toggle_help(self):
        self.help_on = not self.help_on
        if self.help_on:
            self.draw_help()
            self.help_c.np.show()
        else:
            self.help_c.np.hide()

    def toggle_camera_inset(self):
        self.set_camera_inset(not self.cam_on)

    def set_camera_inset(self, on):
        self.cam_on = on
        if on and self.cam_buf is None:
            self._make_camera()
        if self.cam_buf is not None:
            self.cam_buf.setActive(on)
        if self.cam_card is not None:
            (self.cam_card.show if on and self.panels_on else self.cam_card.hide)()
        (self.cam_over.np.show if on and self.panels_on else self.cam_over.np.hide)()

    def _make_camera(self):
        from metadrive.constants import CameraTagStateKey, Semantics
        from metadrive.engine.core.terrain import Terrain
        eng, app = self.eng, self.app
        buf = eng.win.makeTextureBuffer("zed-left", 512, 288)
        buf.setSort(-10)
        buf.setClearColor((0.5, 0.6, 0.7, 1))
        cam = eng.makeCamera(buf)
        lens = PerspectiveLens()
        lens.setFov(PL.ROAD_CAM_FOV_H, PL.ROAD_CAM_FOV_H * 9 / 16 * 1.0)
        lens.setNear(0.1)
        lens.setFar(1500)
        cam.node().setLens(lens)
        cam.node().setTagStateKey(CameraTagStateKey.RGB)
        cam.node().setTagState(Semantics.TERRAIN.label, Terrain.make_render_state(eng, "terrain.vert.glsl",
                                                                                   "terrain.frag.glsl"))
        cam.reparentTo(app.rig.np)
        from .frames import car_to_local
        cam.setPos(*car_to_local(PL.ROAD_CAM))
        cam.setHpr(0, 0, 0)
        self.cam_np = cam
        self.cam_lens = lens
        self.cam_buf = buf
        tex = buf.getTexture()
        cm = CardMaker("ui-cam")
        cm.setFrame(0, self.cam_w, -self.cam_h, 0)
        self.cam_card = self.root.attachNewNode(cm.generate())
        self.cam_card.setTexture(tex)
        self.cam_card.setBin("fixed", 0)
        from .optics import flat_shader
        flat_shader(self.cam_card, textured=True)
        self.cam_card.setPos(self.cam_pos[0], 0, -self.cam_pos[1]) if hasattr(self, "cam_pos") else None
        self.cam_over.np.reparentTo(self.root)
        self.cam_over.np.setBin("fixed", 10)

    def reattach_camera(self):
        if self.cam_buf is not None:
            from .frames import car_to_local
            self.cam_np.reparentTo(self.app.rig.np)
            self.cam_np.setPos(*car_to_local(PL.ROAD_CAM))

    # ---- messages ----------------------------------------------------------------------------------------------
    def toast(self, msg):
        self.toast_msg, self.toast_t = msg, time.time()
        p = self.toast_c.panel
        p.clear((10, 12, 16, 0))
        w, _ = text_size(msg, 15, "medium")
        x0 = (p.w - w) / 2 - 14
        p.rrect_fill = None
        cv2.rectangle(p.img, (int(x0), 0), (int(p.w - x0), p.h - 1), (24, 21, 18, 230), -1)
        p.text(msg, p.w / 2, p.h / 2, 15, FG, 1.0, face="medium", anchor="cm")
        self.toast_c.upload()
        self.toast_c.np.show()

    def banner(self, title, desc):
        self.banner_msg, self.banner_t = (title, desc), time.time()
        p = self.banner_c.panel
        p.clear((14, 22, 34, 232))
        p.rect(0, 0, 4, p.h, ACC)
        p.text(title, 18, 10, 19, (255, 255, 255), 1.0, face="bold")
        self._wrap(p, desc, 18, 36, p.w - 30, 14, DIM, 2)
        self.banner_c.upload()
        self.banner_c.np.show()

    @staticmethod
    def _wrap(p, text, x, y, width, size, col, max_lines=9, face="regular", lh=None):
        words = text.split()
        line = ""
        n = 0
        lh = lh or int(size * 1.35)
        for wd in words:
            cand = (line + " " + wd).strip()
            if text_size(cand, size, face)[0] > width and line:
                p.text(line, x, y + n * lh, size, col, 1.0, face=face)
                n += 1
                line = wd
                if n >= max_lines:
                    return n
            else:
                line = cand
        if line:
            p.text(line, x, y + n * lh, size, col, 1.0, face=face)
            n += 1
        return n

    # ---- input -----------------------------------------------------------------------------------------------------
    def on_click(self):
        mw = self.eng.mouseWatcherNode
        if not mw.hasMouse():
            return
        m = mw.getMouse()
        px = (m[0] + 1) / 2 * self.W
        py = (1 - m[1]) / 2 * self.H
        if self.help_on:
            self.toggle_help()
            return
        if self.panels_on and self.left.contains(px, py):
            ly = py - 38
            for (y0, y1, fn) in self.rows:
                if y0 <= ly < y1 and fn is not None:
                    fn()
                    self.last["left"] = -1
                    return

    # ---- per frame ----------------------------------------------------------------------------------------------
    def update(self, t):
        now = time.time()
        # the road-camera inset renders every third frame (20 Hz): a full extra scene render is the costliest item
        if self.cam_buf is not None and self.cam_on:
            self._cam_n = getattr(self, "_cam_n", 0) + 1
            self.cam_buf.setActive(self._cam_n % 3 == 0)
        if self.toast_msg and now - self.toast_t > 2.6:
            self.toast_msg = None
            self.toast_c.np.hide()
        if self.banner_msg and now - self.banner_t > 9.0:
            self.banner_msg = None
            self.banner_c.np.hide()
        if now - self.last["top"] > 0.5:
            self.draw_top()
            self.last["top"] = now
        if not self.panels_on:
            return
        if now - self.last["left"] > 0.4:
            self.draw_left()
            self.last["left"] = now
        if now - self.last["right"] > 0.2:
            self.draw_right()
            self.last["right"] = now
        if now - self.last["map"] > 0.1:
            self.draw_map()
            self.last["map"] = now
        if self.cam_card is not None:
            E = PL.ENVIRONMENTS[app_env(self.app)]
            k = E["scene"]
            tint = (1.0, 1.0, 1.0) if self.app.env_key == "noon" else E["sky"]
            self.cam_card.setShaderInput("tint", (k * tint[0], k * tint[1], k * tint[2], 1.0), priority=10)
        if self.cam_on and now - self.last["cam"] > 0.1:
            self.draw_cam_overlay()
            self.last["cam"] = now

    # ---- top bar -------------------------------------------------------------------------------------------------
    def draw_top(self):
        app = self.app
        p = self.top.panel
        p.clear((12, 14, 18, 235))
        p.text("AR HUD road simulator", 14, 7, 15, (255, 255, 255), 1.0, face="bold")
        p.text("TFT edition on MetaDrive", 196, 8, 13, DIM, 1.0)
        x = 380
        for key, name in (("driver", "1 Driver"), ("chase", "2 Chase"), ("top", "3 Top")):
            on = app.view == key
            w, _ = text_size(name, 13, "medium")
            if on:
                cv2.rectangle(p.img, (x - 8, 4), (x + w + 8, 25), (60, 46, 30, 255), -1)
            p.text(name, x, 8, 13, (255, 255, 255) if on else DIM, 1.0, face="medium")
            x += w + 26
        content = "Plan + added features" if app.S["content"] == "plus" else "Plan as written"
        p.text(content, x + 10, 8, 13, ACC, 1.0, face="medium")
        info = app.scen.active
        from .scenarios import INFO
        sc = INFO.get(info, {}).get("title", info)
        right = (f"{sc}   ·   {PL.ENVIRONMENTS[app.env_key]['label']}   ·   "
                 f"{'You drive' if app.driver.mode == 'manual' else 'Simulated driver'}   ·   "
                 f"t {app.t:6.1f} s   ·   {app.fps:4.0f} fps   ·   Tab panels   ? keys")
        p.text(right, p.w - 14, 8, 13, DIM, 1.0, anchor="rt")
        self.top.upload()

    # ---- left: controls ----------------------------------------------------------------------------------------
    def draw_left(self):
        """Controls in folding sections (click a section title to fold it), each row with its key."""
        app, S = self.app, self.app.S
        p = self.left.panel
        p.clear(BG)
        self.rows = []
        y = 8
        win = PL.WINDOWS[S["window"]]
        src = next(s for s in PL.PGU_SOURCES if s["key"] == S["pgu"])
        if not hasattr(self, "fold"):
            self.fold = dict(drive=False, hud=False, features=True, scenarios=False, view=True)

        def head(key, txt, note=""):
            nonlocal y
            y += 4
            folded = self.fold[key]
            if folded:
                p.poly([(14, y + 2), (14, y + 12), (21, y + 7)], HEAD)
            else:
                p.poly([(12, y + 4), (22, y + 4), (17, y + 11)], HEAD)
            p.text(txt.upper(), 28, y + 1, 11, HEAD, 1.0, face="bold")
            if note:
                p.text(note, p.w - 12, y + 1, 11, DIM, 1.0, anchor="rt")

            def toggle(k=key):
                self.fold[k] = not self.fold[k]
            self.rows.append((y - 3, y + 17, toggle))
            y += 19
            return not folded

        def row(key, label, value, fn=None, on=None):
            nonlocal y
            p.text(key, 14, y + 2, 12, ACC, 1.0, face="bold")
            p.text(label, 66, y + 2, 13, FG, 1.0)
            col = FG if on is None else (OK if on else DIM)
            p.text(value, p.w - 12, y + 2, 13, col, 1.0, face="medium", anchor="rt")
            self.rows.append((y, y + 19, fn))
            y += 19

        A = app.actions()
        if head("drive", "Drive"):
            row("M", "Driver", "You (arrows)" if app.driver.mode == "manual" else "Simulated", A["m"])
            row("J", "Head motion", app.head.mode, A["j"])
            row("E", "Scene", PL.ENVIRONMENTS[app.env_key]["label"], A["e"])
            row("R [ ]", "Restart, map", f"seed {app.engine.current_seed}", A["r"])
        if head("hud", "HUD, as in the plan"):
            row("K", "Content", "Plan + added" if S["content"] == "plus" else "Plan as written", A["k"])
            row("W", "Window", {"spec": "Spec 7.5 m", "traced": "Traced 8.56 m", "stage1": "Stage 1 4.2 m"}[
                S["window"]], A["w"])
            row("P", "PGU", f"{src['panel']:,.0f} cd/m\u00b2", A["p"])
            row("D \u2212 =", "Auto-dim, offset", f"{'on' if S['auto_dim'] else 'off'}  {S['dim_steps']:+d}", A["d"])
            row("C", "Age compensation", {"photon": "to photon", "draw": "to draw", "off": "off"}[
                S["compensation"]], A["c"])
            row("T", "Head tracker", "on" if S["head_tracking"] else "off", A["t"], on=S["head_tracking"])
            row("L", "Ground plane", {"fit": "per-frame fit", "static+imu": "static + IMU", "static": "static"}[
                S["plane"]], A["l"])
            row("G", "Ghost image", {"true": "true size", "x20": "x20", "off": "off"}[S["ghost"]], A["g"])
            row("U", "Sun-watch", "on" if S["sun_watch"] else "off", A["u"], on=S["sun_watch"])
            row("N", "GNSS", "OUTAGE" if S["gnss_outage"] else "fix", A["n"], on=not S["gnss_outage"])
            row("O", "Polarised sunglasses", "on" if S["sunglasses"] else "off", A["o"])
            row("V", "Clutter mode", "10 s", A["v"])
            row("X", "Truth overlay", "on" if S["truth_overlay"] else "off", A["x"])
            row("B", "Window outline", "on" if S["show_window"] else "off", A["b"])
        n_on = sum(1 for v in S["features"].values() if v)
        note = f"{n_on} of {len(S['features'])} on" + ("" if S["content"] == "plus" else ", K to show")
        if head("features", "Added features", note):
            for i, (k, name) in enumerate(Features.NAMES.items()):
                row(f"\u21e7{i + 1}", name, "on" if S["features"][k] else "off", A[f"shift-{i + 1}"],
                    on=S["features"][k] and S["content"] == "plus")
        if head("scenarios", "Scenarios"):
            for (k, fk, title, _) in SCENARIOS:
                on = app.scen.active == k
                row(fk, title, "\u25cf" if on else "", (lambda kk=k: app.scen.start(kk)), on=True if on else None)
        if head("view", "View", app.view):
            row("1 2 3", "Driver, chase, top", app.view, None)
            row("Z", "Driver zoom", ["60\u00b0", "35\u00b0", "16\u00b0 (HUD)"][app.zoom], A["z"])
            row("F", "Road camera inset", "on" if self.cam_on else "off", A["f"])
            row("S", "Screenshot", "", A["s"])
            row("Tab", "Hide panels", "", self.toggle_panels)
        self.left_used = y
        self.left.upload()

    # ---- right: live numbers ----------------------------------------------------------------------------------
    def draw_right(self):
        app, S, h, c = self.app, self.app.S, self.app.hudd, self.app.ctrl
        p = self.right.panel
        p.clear(BG)
        y = 10

        def head(txt):
            nonlocal y
            y += 6
            p.text(txt.upper(), 14, y, 11, HEAD, 1.0, face="bold")
            y += 18

        def row(label, value, crit=None, ok=None, col=None):
            nonlocal y
            p.text(label, 14, y + 2, 13, FG if col is None else col, 1.0)
            vc = FG if ok is None else (OK if ok else BAD)
            x = p.w - 12
            if crit:
                w, _ = p.text(crit, x, y + 4, 11, DIM, 1.0, anchor="rt")
                x -= w + 10
            p.text(value, x, y + 2, 13, vc, 1.0, face="medium", anchor="rt")
            y += 20

        def fmt_deg(v):
            return "–" if v is None else f"{v:.2f}°"

        st = h.stats
        head("Registration, true eye, now")
        for xr in (10, 20, 30):
            v = st.get(f"res_lane{xr}")
            crit = "≤ 0.5° at 30 m" if xr == 30 else None
            row(f"Lane line at {xr} m", fmt_deg(v), crit, None if v is None else v <= (0.5 if xr == 30 else 0.5))
        v = st.get("res_lead")
        row("Lead chevron", fmt_deg(v), None, None if v is None else v <= 0.5)
        eo = app.eye_off * 1000
        tr = "nominal eye" if h.eye_nominal else "tracked"
        row("Head offset (y, z)", f"{eo[1]:+.0f}, {eo[2]:+.0f} mm", tr)
        vb = app.plane.visible_box(app.eye_off)
        vig = vb[0] > -app.plane.w / 2 or vb[1] < app.plane.w / 2 or vb[2] > -app.plane.h / 2 or vb[3] < app.plane.h / 2
        row("Mirror vignetting", "edge cut" if vig else "none", "300 mm mirror", not vig)
        head("Age and latency")
        L = S["lat"]
        row("Lanes, objects as drawn", f"{st['age_lanes'] * 1000:.0f} ms", "fade > 250 ms", st["age_lanes"] < 0.25)
        tot = sum(L)
        row("Motion to photon", f"{tot:.0f} ms", "≤ 90 ms", tot <= 90)
        row("Compensated to", {"photon": "photon time", "draw": "draw time", "off": "not compensated"}[
            S["compensation"]] if not S["gnss_outage"] else "off (no fix)")
        ea = st.get("age_eye")
        row("Eye pose age", "–" if ea is None or ea != ea else f"{ea * 1000:.0f} ms", "nominal > 500 ms")
        m = h.msg
        if m:
            pl = m["plane"]
            row("Body pitch / plane", f"{math.degrees(pl['pitch_true']):+.2f}° / "
                f"{math.degrees(pl['pitch_est']):+.2f}°", {"fit": "fit", "static+imu": "static+IMU",
                                                                  "static": "static"}[S["plane"]])
        head(f"Luminance, {PL.ENVIRONMENTS[app.env_key]['label'].lower()}")
        lum = c.lum
        row("Panel", f"{lum['Lpanel']:,.0f} cd/m²", f"duty {c.duty * 100:.0f}%")
        E = PL.ENVIRONMENTS[app.env_key]
        row("At the eye", f"{lum['Leye']:,.0f} cd/m²", f"path {lum['path'] * 100:.1f}%")
        row("Contrast vs sky", f"{lum['contrast_sky']:.2f}", "≥ 1.15", lum["contrast_sky"] >= 1.15)
        row("Contrast vs road", f"{lum['contrast_road']:.2f}", "≥ 1.15", lum["contrast_road"] >= 1.15)
        if app.env_key == "night":
            row("White vs headlit road", f"{lum['Leye'] / E['L_road']:.0f}x", "TI: < 3 cd/m²",
                lum["Leye"] < 3)
        row("Unlit window glow", f"{lum['black']:.2f} cd/m²", "≤ 0.1 at night" if app.env_key == "night"
            else None, (lum["black"] <= 0.1) if app.env_key == "night" else None)
        row("Cell temperature", f"{c.cell:.0f} °C", c.thermal, c.thermal == "ok")
        row("Shutter", "open" if c.shutter > 0.98 else "closed" if c.shutter < 0.02 else "moving",
            c.shutter_reason[:26] if c.shutter_reason else None, c.shutter > 0.5)
        sun = c.sun
        row("Sun vs entry patch", "inside" if sun["in_patch"] else f"{sun['d_az']:+.0f}°, {sun['d_el']:+.0f}°",
            f"elev {sun['elev']:.0f}°", not sun["in_patch"])
        if S["sunglasses"]:
            row("Polarised sunglasses", "image blocked", "demo rule", False)
        head("Window and speed")
        pl_ = app.plane
        row("Road covered", f"{pl_.road_near:.1f}–{pl_.road_far:.1f} m",
            f"{pl_.fovW:.1f}° × {pl_.fovH:.1f}°")
        vs = st.get("speed_shown")
        v = float(app.ego.speed)
        row("Speed shown / true", "–" if vs is None else f"{vs * PL.MPH:.0f} / {v * PL.MPH:.1f} mph",
            "± 1 m/s", None if vs is None else abs(vs - v) <= 1.0)
        lim = h.sign_value(app.t)
        posted = app.features.posted_limit()
        row("Limit read / posted", f"{lim or chr(8211)} / {posted or chr(8211)}")
        if S["content"] == "plus":
            F = app.features
            head("Added features")
            fc = F.fcw
            if fc.get("headway") is not None:
                ttc = f"{fc['ttc']:.1f} s" if fc.get("ttc") else "–"
                row("Lead headway / TTC", f"{fc['headway']:.1f} s / {ttc}", fc["state"],
                    fc["state"] == "none")
            else:
                row("Lead", "none in the ribbon")
            ld = F.ldw
            tl = lambda v: "–" if v is None else f"{v:.1f} s"
            row("Time to line L / R", f"{tl(ld.get('tlc_l'))} / {tl(ld.get('tlc_r'))}",
                "glow" if ld.get("left") or ld.get("right") else None)
            man = F.man
            if man:
                d = "left" if man["turn"] > 20 else "right" if man["turn"] < -20 else "straight"
                row("Next junction", f"{man['kind']}, {d}", f"{max(0, man['a_turn']):.0f} m")
            cv_ = F.curve
            if cv_.get("adv") is not None:
                row("Curve advisory", f"{cv_['adv'] * PL.MPH:.0f} mph", f"in {cv_['dist']:.0f} m")
        head("Performance")
        row("Frame rate", f"{app.fps:.0f} fps", f"hudd {app.timing['hud']:.1f} ms")
        self.right.upload()

    # ---- map --------------------------------------------------------------------------------------------------------
    def draw_map(self):
        app = self.app
        p = self.mapc.panel
        p.clear((12, 14, 18, 225))
        Wm, Hm = p.w, p.h
        ox, oy = Wm / 2 - PL.CAR_CENTER_Y * -3.0, Hm - 46
        k = 3.0                                            # px per m

        def to(P):
            P = np.atleast_2d(P)
            return np.stack([ox - P[:, 1] * k, oy - P[:, 0] * k], 1)

        tn = getattr(app, "truth_now", None)
        if tn is None:
            return
        for ln in tn["lines"]:
            pts = to(ln["pts"])
            col = (200, 200, 200) if ln["rel"] in (0, 1) else (120, 124, 130)
            p.polyline(pts, col, 0.9, 1)
        p.polyline(to(tn["centre"]), (110, 255, 205), 0.6, 1)
        # window coverage on the road and the camera field
        pl = app.plane
        near, far = pl.road_near, min(pl.road_far, 80)
        half = lambda x: x * math.tan(math.radians(pl.fovW / 2))
        cov = np.array([[near, half(near)], [far, half(far)], [far, -half(far)], [near, -half(near)]])
        p.poly(to(cov), (90, 255, 140), 0.25)
        p.polyline(to(cov), (90, 255, 140), 0.9, 1, closed=True)
        cam = np.array(PL.ROAD_CAM)
        for s in (-1, 1):
            a = math.radians(PL.ROAD_CAM_FOV_H / 2) * s
            p.line(to(cam[:2])[0], to(cam[:2] + 80 * np.array([math.cos(a), math.sin(a)]))[0], (255, 220, 120), 0.35, 1)
        # truth objects
        for o in tn["objects"]:
            c = o["p"][:2]
            hd = o["hd"][:2] / (np.linalg.norm(o["hd"][:2]) + 1e-9)
            nrm = np.array([-hd[1], hd[0]])
            L, Wd = max(o["length"], 0.5) / 2, max(o["width"], 0.5) / 2
            box = np.array([c + hd * L + nrm * Wd, c + hd * L - nrm * Wd, c - hd * L - nrm * Wd, c - hd * L + nrm * Wd])
            col = (255, 150, 80) if o["kind"] in ("person", "bicycle") else (170, 180, 200)
            p.poly(to(box), col, 0.85)
        # what hudd is drawing from: tracked objects and the lead
        for tk in getattr(app.hudd, "track_list", []):
            q = to(tk["p"][:2])[0]
            p.circle(q, 3, (110, 190, 255), 1.0, 1)
        if app.hudd.lead is not None:
            q = to(app.hudd.lead["p"][:2])[0]
            p.circle(q, 6, (255, 190, 90), 1.0, 2)
        # ego
        L = 4.6
        cx = PL.EYE_TO_FRONT_BUMPER - L / 2
        ego = np.array([[cx + L / 2, PL.CAR_CENTER_Y + 0.92], [cx + L / 2, PL.CAR_CENTER_Y - 0.92],
                        [cx - L / 2, PL.CAR_CENTER_Y - 0.92], [cx - L / 2, PL.CAR_CENTER_Y + 0.92]])
        p.poly(to(ego), (110, 190, 255), 1.0)
        # sun direction
        sc = getattr(app, "sun_car", None)
        if sc is not None and sc[2] > 0:
            d = sc[:2] / (np.linalg.norm(sc[:2]) + 1e-9)
            q0 = np.array([Wm - 26, 26])
            p.circle(q0, 14, DIM, 0.8, 1)
            q1 = q0 + np.array([-d[1], -d[0]]) * 12
            p.circle(q1, 4, (255, 220, 90), 1.0, fill=True)
        p.text("Top-down, truth", 10, 8, 11, HEAD, 1.0, face="bold")
        p.text("green: road the window covers", 10, Hm - 30, 10, DIM, 1.0)
        p.text("dots: tracks hudd draws from", 10, Hm - 16, 10, DIM, 1.0)
        self.mapc.upload()
        # PGU label
        q = self.pgu_label.panel
        q.clear((12, 14, 18, 225))
        q.text(f"PGU frame as drawn, {PL.CROP_W} × {PL.CROP_H} px (60 × 30 mm crop)", 8, 4, 11, DIM, 1.0)
        self.pgu_label.upload()

    def draw_cam_overlay(self):
        """Perception on the road-camera image: tracked boxes and the ego lines' points (the audience view)."""
        app = self.app
        p = self.cam_over.panel
        p.img[:] = 0
        p.rect(0, 0, p.w, 22, (12, 14, 18), 225 / 255)
        p.text("Road camera (ZED 2i left) + perception", 8, 4, 11, DIM, 1.0)
        m = app.hudd.msg
        if m is None:
            self.cam_over.upload()
            return
        cam = np.array(PL.ROAD_CAM)
        fx = (self.cam_w / 2) / math.tan(math.radians(PL.ROAD_CAM_FOV_H / 2))
        cx0, cy0 = self.cam_w / 2, self.cam_h / 2 + 22

        def pr(P):
            P = np.atleast_2d(P) - cam
            ok = P[:, 0] > 0.5
            u = cx0 - P[:, 1] / np.where(ok, P[:, 0], 1) * fx
            v = cy0 - P[:, 2] / np.where(ok, P[:, 0], 1) * fx
            out = np.stack([u, v], 1)
            out[~ok] = np.nan
            return out

        for ln in m["lanes"]:
            col = (110, 190, 255) if ln["type"] in ("egoLeft", "egoRight") else (160, 170, 190)
            q = pr(ln["pts"])
            for (u, v), cf in zip(q, ln["conf"]):
                if np.isfinite(u) and cf > 0.3 and 22 < v < p.h:
                    p.circle((u, v), 2, col, 0.9, fill=True)
        for o in m["objects"]:
            pc = o["truth"]
            hx, hy = max(o["length"], 0.4) / 2, max(o["width"], 0.4) / 2
            C = np.array([[pc[0] + dx, pc[1] + dy, pc[2] + z] for dx in (-hx, hx) for dy in (-hy, hy)
                          for z in (0, o["height"])])
            q = pr(C)
            if not np.all(np.isfinite(q)):
                continue
            x0, y0 = q[:, 0].min(), max(22, q[:, 1].min())
            x1, y1 = q[:, 0].max(), q[:, 1].max()
            col = (255, 150, 80) if o["kind"] in ("person", "bicycle") else (120, 230, 150)
            p.rect(x0, y0, x1, y1, col, 1.0, fill=False, width=1)
            p.text(f"{o['kind']} {o['range']:.0f} m", x0, max(22, y0 - 13), 10, col, 1.0)
        self.cam_over.upload()

    # ---- help ---------------------------------------------------------------------------------------------------
    def draw_help(self):
        p = self.help_c.panel
        p.clear((14, 16, 20, 245))
        p.text("Keys", 24, 18, 20, (255, 255, 255), 1.0, face="bold")
        cols = [
            [("1 2 3", "driver, chase, top view"), ("Z", "driver zoom 60/35/16 deg"), ("Tab", "hide panels"),
             ("M", "you drive (arrow keys) / simulated"), (", .", "turn signal left / right"),
             ("J", "head motion"), ("E", "scene"), ("Space", "pause"), ("R", "restart this map"),
             ("[ ]", "previous / next map"), ("S", "screenshot"), ("F", "road camera inset"),
             ("Esc", "quit")],
            [("K", "plan as written / plus added"), ("W", "window spec / traced / Stage 1"),
             ("P", "picture generator"), ("D, − =", "auto-dim, offset"), ("C", "age compensation"),
             ("T", "head tracker"), ("L", "ground plane"), ("G", "ghost"), ("U", "sun-watch"), ("N", "GNSS outage"),
             ("O", "polarised sunglasses"), ("V", "clutter mode"), ("X", "truth overlay"), ("B", "window outline")],
            [(f"⇧{i + 1}", n) for i, n in enumerate(Features.NAMES.values())] +
            [(fk, t) for (_, fk, t, _) in SCENARIOS],
        ]
        for ci, col in enumerate(cols):
            x = 24 + ci * 268
            y = 56
            for k, d in col:
                p.text(k, x, y, 13, ACC, 1.0, face="bold")
                p.text(d, x + 62, y, 13, FG, 1.0)
                y += 22
        p.text("Click a row in the left panel, or press its key. Click anywhere to close.", 24, p.h - 32, 12, DIM, 1.0)
        self.help_c.upload()
