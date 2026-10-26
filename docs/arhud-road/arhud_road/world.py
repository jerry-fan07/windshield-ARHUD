"""The MetaDrive world: an environment subclass with a manager for what MetaDrive does not have out of the box
(speed-limit signs along the route, pedestrians and cyclists placed for the scenarios), and the scene presets
(noon, overcast, dusk, night) that set the light and the luminance numbers the HUD is judged against.
"""
import functools
import math

import numpy as np
from metadrive.component.traffic_participants.cyclist import Cyclist
from metadrive.component.traffic_participants.pedestrian import Pedestrian
from metadrive.envs.metadrive_env import MetaDriveEnv
from metadrive.manager.base_manager import BaseManager
from panda3d.core import CardMaker, NodePath, Texture, TransparencyAttrib
from PIL import Image, ImageDraw

from . import plan as PL
from .canvas import font
from .truth import block_kind

# Posted limits (mph) by PG block type: straight, curve, ramps, junctions, roundabout.
LIMITS = {"S": 55, "C": 45, "r": 45, "R": 40, "X": 35, "T": 35, "O": 25, "y": 45, "Y": 45, "$": 40, ">": 45}


@functools.lru_cache(maxsize=16)
def sign_texture(value):
    W, H = 240, 300
    im = Image.new("RGB", (W, H), (245, 245, 240))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((8, 8, W - 9, H - 9), 18, outline=(10, 10, 10), width=8)
    d.text((W / 2, 70), "SPEED", font=font(44, "bold"), fill=(10, 10, 10), anchor="mm")
    d.text((W / 2, 118), "LIMIT", font=font(44, "bold"), fill=(10, 10, 10), anchor="mm")
    d.text((W / 2, 210), str(value), font=font(120, "bold"), fill=(10, 10, 10), anchor="mm")
    tex = Texture(f"sign{value}")
    tex.setup2dTexture(W, H, Texture.T_unsigned_byte, Texture.F_rgb8)
    arr = np.asarray(im)[::-1, :, ::-1].copy()
    tex.setRamImage(arr.tobytes())
    tex.setMinfilter(Texture.FT_linear_mipmap_linear)
    tex.setAnisotropicDegree(8)
    return tex


class ArhudManager(BaseManager):
    """Signs, pedestrians and cyclists for the AR HUD scenarios."""
    PRIORITY = 11              # after the agent manager, so the ego's route exists

    def __init__(self):
        super().__init__()
        self.signs = []
        self.sign_root = None
        self.peds = []          # dict(obj, path [(x,y),...], speed, t0, kind)
        self.zones = []         # (a_start along the route, limit)

    def reset(self):
        super().reset()
        self.peds = []

    def after_reset(self):
        super().after_reset()
        self._build_signs()
        return {}

    def before_reset(self):
        super().before_reset()
        if self.sign_root is not None:
            self.sign_root.removeNode()
            self.sign_root = None
        self.signs = []
        self.peds = []

    def _build_signs(self):
        eng = self.engine
        ego = next(iter(eng.agents.values()))
        nav = ego.navigation
        cps = nav.checkpoints
        graph = eng.current_map.road_network.graph
        self.sign_root = NodePath("arhud-signs")
        if eng.render is not None and eng.mode != "none":
            self.sign_root.reparentTo(eng.render)
        prev = None
        sid = 0
        self.zones = []
        a = 0.0
        for f, t in zip(cps[:-1], cps[1:]):
            lanes = graph.get(f, {}).get(t)
            if not lanes:
                continue
            kind = block_kind(t) or ">"
            lim = LIMITS.get(kind, 45)
            lane = lanes[-1]
            if lim != prev and lane.length > 25:
                s = min(12.0, lane.length * 0.3)
                pos = lane.position(s, lane.width / 2 + 1.8)
                h = lane.heading_theta_at(s)
                self.signs.append(dict(id=f"sign{sid}", value=lim, pos=np.array(pos, float), heading=h, h=2.1,
                                       a=a + s))
                self.zones.append((a + s, lim))
                sid += 1
                self._sign_node(pos, h, lim)
                prev = lim
            a += lane.length
        eng.arhud_signs = self.signs

    def _sign_node(self, pos, heading, value):
        if self.sign_root is None:
            return
        node = self.sign_root.attachNewNode("sign")
        node.setPos(pos[0], pos[1], 0)
        node.setH(math.degrees(heading) - 90)
        post = CardMaker("post")
        post.setFrame(-0.04, 0.04, 0, 2.1)
        for ang in (0, 90, 180, 270):
            p = node.attachNewNode(post.generate())
            p.setH(ang)
            p.setY(0.02 if ang == 0 else 0)
            p.setColor(0.55, 0.56, 0.58, 1)
        cm = CardMaker("plate")
        cm.setFrame(-0.3, 0.3, 2.1, 2.85)
        plate = node.attachNewNode(cm.generate())
        plate.setY(-0.03)
        plate.setTexture(sign_texture(value))
        back = node.attachNewNode(cm.generate())
        back.setH(180)
        back.setColor(0.5, 0.5, 0.52, 1)
        node.setLightOff(1)
        from .optics import flat_shader
        flat_shader(node)
        plate.setShaderInput("textured", 1.0, priority=11)

    # ---- pedestrians and cyclists --------------------------------------------------------------------------------
    def spawn_walker(self, kind, path, speed, start_delay=0.0):
        cls = Pedestrian if kind == "person" else Cyclist
        p0, p1 = np.array(path[0], float), np.array(path[1], float)
        h = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        obj = self.spawn_object(cls, position=list(p0), heading_theta=h)
        self.peds.append(dict(obj=obj, path=[np.array(p, float) for p in path], speed=speed, seg=0, s=0.0,
                              wait=start_delay, kind=kind))
        return obj

    def after_step(self, *args, **kwargs):
        dt = self.engine.global_config["physics_world_step_size"] * self.engine.global_config["decision_repeat"]
        for w in self.peds:
            obj = w["obj"]
            if w["wait"] > 0:
                w["wait"] -= dt
                obj.set_velocity([1.0, 0.0], 0.0)
                continue
            if w["seg"] >= len(w["path"]) - 1:
                obj.set_velocity([1.0, 0.0], 0.0)
                continue
            a, b = w["path"][w["seg"]], w["path"][w["seg"] + 1]
            seg = b - a
            L = float(np.linalg.norm(seg))
            w["s"] += w["speed"] * dt
            if w["s"] >= L:
                w["s"] -= L
                w["seg"] += 1
                if w["seg"] >= len(w["path"]) - 1:
                    continue
                a, b = w["path"][w["seg"]], w["path"][w["seg"] + 1]
                seg = b - a
                L = float(np.linalg.norm(seg))
            d = seg / max(L, 1e-6)
            pos = a + d * w["s"]
            h = math.atan2(d[1], d[0])
            z = Pedestrian.HEIGHT / 2 if w["kind"] == "person" else 0.9
            obj.set_position([float(pos[0]), float(pos[1])], z)
            obj.set_heading_theta(h)
            obj.set_velocity([float(d[0]), float(d[1])], w["speed"])
        return {}


class ArhudEnv(MetaDriveEnv):
    def setup_engine(self):
        super().setup_engine()
        self.engine.register_manager("arhud_manager", ArhudManager())


def make_env(args):
    from panda3d.core import loadPrcFileData
    # The app paces itself to sim time; vsync would round the frame rate down to 60/n.
    loadPrcFileData("", "sync-video 0")
    from metadrive.component.map.base_map import BaseMap
    from metadrive.component.map.pg_map import MapGenerateMethod
    m = int(args.map) if str(args.map).isdigit() else args.map
    cfg = dict(
        use_render=True,
        start_seed=args.seed,
        num_scenarios=args.scenarios,
        traffic_density=args.traffic,
        need_inverse_traffic=args.oncoming,
        window_size=tuple(args.window),
        show_interface=False,
        show_logo=False,
        show_fps=False,
        show_mouse=True,
        log_level=50,
        horizon=None,
        decision_repeat=1,
        physics_world_step_size=1 / 60,
        force_render_fps=None if args.fast else 60,
        camera_fov=60,
        out_of_road_done=False,
        on_continuous_line_done=False,
        crash_vehicle_done=False,
        crash_object_done=False,
        crash_human_done=False,
        random_lane_width=False,
        # MetaDrive refuses the short map= form together with a custom map_config, so set the sequence here
        map_config={BaseMap.GENERATE_TYPE: MapGenerateMethod.BIG_BLOCK_NUM if isinstance(m, int)
                    else MapGenerateMethod.BIG_BLOCK_SEQUENCE, BaseMap.GENERATE_CONFIG: m,
                    BaseMap.LANE_WIDTH: 3.6, BaseMap.LANE_NUM: args.lanes, "exit_length": 60},
        vehicle_config=dict(vehicle_model="m", show_navi_mark=False, show_navigation_arrow=False,
                            show_dest_mark=False, show_line_to_dest=False),
        multi_thread_render=not args.single_thread,
    )
    return ArhudEnv(cfg)


def apply_environment(engine, env_key, sun_dir_world=None):
    """Light the scene for an environment preset. Returns the sun direction in world coordinates (unit, toward
    the sun)."""
    E = PL.ENVIRONMENTS[env_key]
    wl = engine.world_light
    el, az = math.radians(E["sun_elev"]), math.radians(E["sun_az"])
    sun = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    if sun_dir_world is not None:
        sun = np.asarray(sun_dir_world, float)
        sun = sun / np.linalg.norm(sun)
    if wl is not None:
        k = max(0.0, min(1.0, math.sin(max(el, 0.0)) * 1.6)) if sun_dir_world is None else 1.0
        col = {"noon": (1.0, 1.0, 1.0), "overcast": (0.55, 0.57, 0.6), "dusk": (0.9, 0.55, 0.32),
               "night": (0.05, 0.06, 0.1)}[env_key]
        wl.direction_np.node().setColor((col[0] * k + 0.02, col[1] * k + 0.02, col[2] * k + 0.02, 1))
        amb = {"noon": 0.25, "overcast": 0.42, "dusk": 0.22, "night": 0.05}[env_key]
        wl.ambient_np.node().setColor((amb, amb, amb * (1.15 if env_key == "night" else 1.0), 1))
        if sun[2] > 0.05:
            wl.direction_np.setPos(sun[0] * 100, sun[1] * 100, sun[2] * 100)
            wl.direction_np.lookAt(0, 0, 0)
    if engine.sky_box is not None:
        engine.sky_box.origin.setColorScale(*E["sky"], 1)
    return sun
