"""Camera models, the car frame, plane intersection, homographies, the rig frame and the life-size crop S.

Every convention of the package is fixed here, once:

* Car frame (spec section 6): x forward, y right, z down, metres, origin at the source camera. A source's mount gives
  the camera's height above the road (the ground is the plane z = +height_m when the car is level), its pitch
  (positive = the camera looks DOWN), its yaw (positive = the camera looks RIGHT) and its lateral offset from the
  car's centreline (metadata; the origin stays at the camera).
* docs/arhud-road uses x forward, y left, z up with the origin on the road under the eye: `from_arhud_road` converts.
* Yaw rate (ego topic): rotation rate about the car frame's +z (down) axis, so POSITIVE = TURNING RIGHT. Sources whose
  native convention is "positive left" (openpilot carState, MetaDrive heading) negate it at the boundary through
  `yaw_rate_from_left_positive`.
* Pixel coordinates are pixel-CENTRE coordinates: pixel (i, j) is centred on (i, j) and a W-wide image spans
  -0.5 .. W - 0.5. raylib / GL rectangles use EDGE coordinates: edge = centre + 0.5. Both monitors, the road monitor
  (u, v) and the PGU (x, y), are 3840 x 2400 in this convention.
* The window (the plan's 10.8 x 5.4 deg) is a fixed integer pixel rectangle centred on the road monitor, which is the
  glass centre: columns 1299 .. 2540 and rows 889 .. 1509 (1242 x 621). Everything that lights, draws or detects the
  window (hudd, testcard, calib_rig, scored) reads `Bench.window`.
* The source's horizon row (cy - f tan pitch) lands on road-monitor row `Bench.horizon_row` = 1200 - 575 = 625, the
  plan's 5 deg look-down above the window centre. view_from_eye is the identity on the bench: the bench eye sits at
  the recording's camera, and the crop offset does the look-down.
* The mirror: `flip_matrix("vertical")` maps road-monitor (u, v) to PGU (u, H - 1 - v). calibration.yaml's
  warp.homography_pr is the WHOLE mapping road-monitor px -> PGU px with that flip already inside it (the chain's
  H_PR . F stored pre-multiplied); warp.flip names the mirror it contains.

Bench chain for a car-frame point p:  PGU px = D . S . K_source . camera_from_car . p,  D = homography_pr.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

DEG = math.pi / 180.0


# ---- cameras -------------------------------------------------------------------------------------------------------
@dataclass
class Camera:
    """Pinhole camera, pixel-centre coordinates. distortion: OpenCV coefficients or None."""
    f: float
    cx: float
    cy: float
    w: int
    h: int
    distortion: list | None = None

    @property
    def K(self):
        return np.array([[self.f, 0.0, self.cx], [0.0, self.f, self.cy], [0.0, 0.0, 1.0]])

    @property
    def hfov_deg(self):
        return 2 * math.degrees(math.atan(self.w / 2 / self.f))

    def to_dict(self):
        return dict(f=self.f, cx=self.cx, cy=self.cy, w=self.w, h=self.h, distortion=self.distortion)

    @classmethod
    def from_dict(cls, d):
        if "size" in d and "w" not in d:
            w, h = d["size"]
        else:
            w, h = d["w"], d["h"]
        f = d.get("f", d.get("f_px"))
        if f is None and d.get("hfov_deg"):
            f = (w / 2) / math.tan(math.radians(d["hfov_deg"]) / 2)
        cx = d.get("cx")
        cy = d.get("cy")
        return cls(f=float(f), cx=float((w - 1) / 2 if cx is None else cx), cy=float((h - 1) / 2 if cy is None else cy),
                   w=int(w), h=int(h), distortion=d.get("distortion"))

    def scaled(self, k):
        """The same camera for an image resized by k (pixel-centre convention kept)."""
        return Camera(self.f * k, (self.cx + 0.5) * k - 0.5, (self.cy + 0.5) * k - 0.5, int(round(self.w * k)),
                      int(round(self.h * k)), self.distortion)


@dataclass
class Mount:
    """Camera mount relative to the road and the car. pitch_deg > 0: looks down; yaw_deg > 0: looks right."""
    height_m: float = 1.22
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0
    lateral_m: float = 0.0

    def to_dict(self):
        return dict(height_m=self.height_m, pitch_deg=self.pitch_deg, yaw_deg=self.yaw_deg, lateral_m=self.lateral_m)

    @classmethod
    def from_dict(cls, d):
        d = d or {}

        def val(k, default):
            v = d.get(k)
            return default if v is None else float(v)
        return cls(val("height_m", 1.22), val("pitch_deg", 0.0), val("yaw_deg", 0.0), val("lateral_m", 0.0))


def camera_from_car(pitch_deg=0.0, yaw_deg=0.0):
    """Rotation taking car-frame vectors (x fwd, y right, z down) to OpenCV camera vectors (x right, y down, z fwd)
    for a camera at the car-frame origin, yawed by yaw_deg (right positive) and then pitched down by pitch_deg."""
    th, ps = pitch_deg * DEG, yaw_deg * DEG
    c, s = math.cos(ps), math.sin(ps)
    Ryaw = np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])        # car -> yawed car
    ct, st = math.cos(th), math.sin(th)
    Rcam = np.array([[0.0, 1.0, 0.0], [-st, 0.0, ct], [ct, 0.0, st]])    # yawed car -> camera (rows: right, down, fwd)
    return Rcam @ Ryaw


def project(P, cam: Camera, mount: Mount):
    """Car-frame points (N x 3) -> source pixels (N x 2); points behind the camera are NaN."""
    P = np.atleast_2d(np.asarray(P, dtype=float))
    C = P @ camera_from_car(mount.pitch_deg, mount.yaw_deg).T
    z = C[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        u = cam.cx + cam.f * C[:, 0] / z
        v = cam.cy + cam.f * C[:, 1] / z
    out = np.stack([u, v], axis=1)
    out[~(z > 1e-6)] = np.nan
    return out


def pixel_ray(uv, cam: Camera, mount: Mount):
    """Source pixels (N x 2) -> unit ray directions in the car frame."""
    uv = np.atleast_2d(np.asarray(uv, dtype=float))
    d = np.stack([(uv[:, 0] - cam.cx) / cam.f, (uv[:, 1] - cam.cy) / cam.f, np.ones(len(uv))], axis=1)
    d = d @ camera_from_car(mount.pitch_deg, mount.yaw_deg)          # camera -> car (R^T applied to row vectors)
    return d / np.linalg.norm(d, axis=1)[:, None]


def ground_normal(plane_pitch_deg=0.0):
    """Unit normal (pointing down, into the road) of a road plane pitched by plane_pitch_deg relative to the car
    frame (positive: the road ahead rises relative to the car, i.e. the car's nose is pitched down)."""
    a = plane_pitch_deg * DEG
    return np.array([-math.sin(a), 0.0, math.cos(a)])


def lift_to_ground(uv, cam: Camera, mount: Mount, height_m=None, plane_pitch_deg=0.0):
    """Lifting (appendix A): intersect pixel rays with the road plane n . p = height. Returns N x 3; NaN above the
    horizon."""
    h = mount.height_m if height_m is None else height_m
    n = ground_normal(plane_pitch_deg)
    d = pixel_ray(uv, cam, mount)
    den = d @ n
    with np.errstate(divide="ignore", invalid="ignore"):
        t = h / den
    out = d * t[:, None]
    out[~(den > 1e-9)] = np.nan
    return out


def horizon_row(cam: Camera, mount: Mount):
    """Source row of the horizon (where the lane lines vanish) for a camera pitched down by mount.pitch_deg."""
    return cam.cy - cam.f * math.tan(mount.pitch_deg * DEG)


def pitch_yaw_from_vanishing_point(u, v, cam: Camera):
    """Inverse of the above for a straight road's vanishing point (u, v): (pitch_deg down-positive, yaw_deg
    right-positive). Exact for this package's camera_from_car (yaw applied before pitch)."""
    pitch = math.atan((cam.cy - v) / cam.f)
    yaw = math.atan((cam.cx - u) * math.cos(pitch) / cam.f)
    return math.degrees(pitch), math.degrees(yaw)


# ---- frame conversions -------------------------------------------------------------------------------------------
def from_arhud_road(P, cam_pos=(0.0, 0.0, 1.22)):
    """docs/arhud-road car frame (x fwd, y left, z up; origin on the road under the eye) -> this package's car frame
    (x fwd, y right, z down; origin at a camera placed at cam_pos in arhud-road's frame)."""
    P = np.atleast_2d(np.asarray(P, dtype=float))
    c = np.asarray(cam_pos, dtype=float)
    return np.stack([P[:, 0] - c[0], -(P[:, 1] - c[1]), -(P[:, 2] - c[2])], axis=1)


def from_arhud_road_vec(V):
    """Vectors (velocities, headings) from arhud-road's frame to this package's (no origin shift)."""
    V = np.atleast_2d(np.asarray(V, dtype=float))
    if V.shape[1] == 2:
        V = np.hstack([V, np.zeros((len(V), 1))])
    return np.stack([V[:, 0], -V[:, 1], -V[:, 2]], axis=1)


def yaw_rate_from_left_positive(r):
    """Yaw rate in a z-up / positive-left convention (openpilot carState, MetaDrive) -> this package's z-down
    convention (positive right)."""
    return -r


# ---- homographies ------------------------------------------------------------------------------------------------
def flip_matrix(kind="vertical", w=3840, h=2400):
    """Road-monitor px -> PGU px for a perfect rig with the given mirror (pixel-centre coordinates)."""
    if kind == "vertical":
        return np.array([[1.0, 0.0, 0.0], [0.0, -1.0, h - 1.0], [0.0, 0.0, 1.0]])
    if kind == "horizontal":
        return np.array([[-1.0, 0.0, w - 1.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    if kind in ("both", "rotate180"):
        return np.array([[-1.0, 0.0, w - 1.0], [0.0, -1.0, h - 1.0], [0.0, 0.0, 1.0]])
    if kind in ("none", None, "identity"):
        return np.eye(3)
    raise ValueError(f"unknown flip {kind!r}")


def apply_h(H, pts):
    """Apply a 3 x 3 homography to N x 2 points (NaN rows stay NaN)."""
    pts = np.atleast_2d(np.asarray(pts, dtype=float))
    q = np.hstack([pts, np.ones((len(pts), 1))]) @ np.asarray(H, dtype=float).T
    with np.errstate(divide="ignore", invalid="ignore"):
        return q[:, :2] / q[:, 2:3]


def unflip(D, kind="vertical", w=3840, h=2400):
    """The mapping with its mirror removed (what --no-flip draws): flip^-1 . D. A flip is its own inverse."""
    return flip_matrix(kind, w, h) @ np.asarray(D, dtype=float)


# ---- the rig frame (appendix A) -----------------------------------------------------------------------------------
def rig_mirror(P):
    """Image of a rig-frame point in the glass (x along the viewing axis, eye negative; y right; z up; origin at the
    glass centre; glass in the plane z = -x): (x, y, z) -> (-z, y, -x)."""
    P = np.atleast_2d(np.asarray(P, dtype=float))
    return np.stack([-P[:, 2], P[:, 1], -P[:, 0]], axis=1)


# ---- the bench --------------------------------------------------------------------------------------------------
@dataclass
class Rect:
    """Integer pixel rectangle: first column x0, first row y0, size w x h (pixels x0 .. x0 + w - 1)."""
    x0: int
    y0: int
    w: int
    h: int

    @property
    def x1(self):          # last column
        return self.x0 + self.w - 1

    @property
    def y1(self):
        return self.y0 + self.h - 1

    @property
    def centre(self):      # pixel-centre coordinates
        return ((self.x0 + self.x1) / 2.0, (self.y0 + self.y1) / 2.0)

    def edges(self):
        """(left, top, right, bottom) in pixel-centre coordinates of the outer edges."""
        return (self.x0 - 0.5, self.y0 - 0.5, self.x1 + 0.5, self.y1 + 0.5)

    def contains(self, pts):
        pts = np.atleast_2d(pts)
        l, t, r, b = self.edges()
        return (pts[:, 0] >= l) & (pts[:, 0] <= r) & (pts[:, 1] >= t) & (pts[:, 1] <= b)


@dataclass
class Crop:
    """The life-size crop of a source onto the road monitor: monitor px = S . source px."""
    s: float                    # monitor px per source px
    S: np.ndarray               # 3 x 3
    src_rect: tuple             # (x, y, w, h) in source EDGE coordinates (the texture rectangle raylib draws from)
    horizon_src: float          # the source's horizon row

    def to_monitor(self, uv):
        return apply_h(self.S, uv)

    def to_source(self, uv):
        return apply_h(np.linalg.inv(self.S), uv)

    def to_dict(self):
        return dict(s=self.s, S=self.S.tolist(), src_rect=list(self.src_rect), horizon_src=self.horizon_src)


@dataclass
class Bench:
    """The bench numbers, from calibration.yaml and bench.yaml (generated from tcalc.py; see config/)."""
    W: int = 3840
    H: int = 2400
    pitch_mm: float = 25.4 / 277.0
    d_img_mm: float = 600.0
    fov_deg: tuple = (10.8, 5.4)
    win_px: tuple = (1242, 621)
    lookdown_px: int = 575
    content_scale: int = 2
    window: Rect = field(init=False)

    def __post_init__(self):
        ww, wh = int(self.win_px[0]), int(self.win_px[1])
        self.window = Rect((self.W - ww) // 2, (self.H - wh) // 2, ww, wh)

    @classmethod
    def from_config(cls, calib, bench=None):
        mon = calib["monitors"]["road"]
        W, H = mon["px"]
        win = calib["window"]
        d_img = None
        if bench is not None:
            d_img = bench.get("d_img_mm")
        if d_img is None:
            d_img = calib["rig"]["d_eye_mm"] + calib["rig"]["d_glass_mm"]
        cs = 2 if bench is None else int((bench.get("hudd") or {}).get("content_scale", 2))
        return cls(W=int(W), H=int(H), pitch_mm=float(mon["pitch_mm"]), d_img_mm=float(d_img),
                   fov_deg=tuple(win["fov_deg"]), win_px=tuple(win["px"]), lookdown_px=int(win["lookdown_px"]),
                   content_scale=cs)

    # life size
    @property
    def f_mon(self):
        """Focal length of the bench eye in road-monitor px: the monitor at d_img shown at life size."""
        return self.d_img_mm / self.pitch_mm

    @property
    def ppd(self):
        return self.win_px[0] / self.fov_deg[0]

    @property
    def horizon_row(self):
        """Road-monitor row of every source's horizon: the monitor's middle (H / 2) less the 5 deg look-down."""
        return self.H / 2.0 - self.lookdown_px

    @property
    def centre(self):
        return ((self.W - 1) / 2.0, (self.H - 1) / 2.0)

    def bench_camera(self):
        """The pinhole the road monitor itself is, seen from the eye (also the synthetic and MetaDrive camera)."""
        return Camera(self.f_mon, (self.W - 1) / 2.0, (self.H - 1) / 2.0, self.W, self.H)

    def bench_pitch_deg(self):
        """Pitch that puts the bench camera's horizon on horizon_row (5.02 deg)."""
        c = self.bench_camera()
        return math.degrees(math.atan((c.cy - self.horizon_row) / c.f))

    def crop(self, cam: Camera, mount: Mount) -> Crop:
        """S for a source: scale f_mon / f, the principal point's column on the monitor's centre column, the source
        horizon on horizon_row."""
        s = self.f_mon / cam.f
        hs = horizon_row(cam, mount)
        cxm = (self.W - 1) / 2.0
        S = np.array([[s, 0.0, cxm - s * cam.cx], [0.0, s, self.horizon_row - s * hs], [0.0, 0.0, 1.0]])
        # monitor edges -0.5 .. W-0.5 back to source centre coords, then to edge coords (+0.5)
        x0 = (-0.5 - S[0, 2]) / s + 0.5
        y0 = (-0.5 - S[1, 2]) / s + 0.5
        return Crop(s=s, S=S, src_rect=(x0, y0, self.W / s, self.H / s), horizon_src=hs)

    # the window and the content texture
    def content_size(self):
        return (self.window.w * self.content_scale, self.window.h * self.content_scale)

    def road_to_content(self, uv):
        """Road-monitor px -> content-texture px (pixel-centre coordinates, content_scale x the window)."""
        uv = np.atleast_2d(np.asarray(uv, dtype=float))
        k = self.content_scale
        l, t, _, _ = self.window.edges()
        return np.stack([(uv[:, 0] - l) * k - 0.5, (uv[:, 1] - t) * k - 0.5], axis=1)

    def content_to_road(self, xy):
        xy = np.atleast_2d(np.asarray(xy, dtype=float))
        k = self.content_scale
        l, t, _, _ = self.window.edges()
        return np.stack([(xy[:, 0] + 0.5) / k + l, (xy[:, 1] + 0.5) / k + t], axis=1)

    def deg_per_px(self):
        return math.degrees(math.atan(1.0 / self.f_mon))


@dataclass
class Chain:
    """The bench projection chain for one source: car-frame point -> road-monitor px -> PGU px."""
    bench: Bench
    cam: Camera
    mount: Mount
    D: np.ndarray                 # road-monitor px -> PGU px (homography_pr, flip inside)
    crop: Crop = field(init=False)

    def __post_init__(self):
        self.crop = self.bench.crop(self.cam, self.mount)
        self.D = np.asarray(self.D, dtype=float)
        self.D_inv = np.linalg.inv(self.D)

    @property
    def K_eye(self):
        """K_eye = S . K_source (view_from_eye is the identity on the bench)."""
        return self.crop.S @ self.cam.K

    def to_source(self, P):
        return project(P, self.cam, self.mount)

    def to_road(self, P):
        return apply_h(self.crop.S, self.to_source(P))

    def to_content(self, P):
        return self.bench.road_to_content(self.to_road(P))

    def to_pgu(self, P):
        return apply_h(self.D, self.to_road(P))

    def pgu_to_road(self, xy):
        return apply_h(self.D_inv, xy)

    def angle_deg(self, uv_a, uv_b):
        """Angle at the eye between road-monitor px a and b (N x 2 each)."""
        a = np.atleast_2d(uv_a) - np.array(self.bench.centre)
        b = np.atleast_2d(uv_b) - np.array(self.bench.centre)
        f = self.bench.f_mon
        da = np.hstack([a, np.full((len(a), 1), f)])
        db = np.hstack([b, np.full((len(b), 1), f)])
        da /= np.linalg.norm(da, axis=1)[:, None]
        db /= np.linalg.norm(db, axis=1)[:, None]
        return np.degrees(np.arccos(np.clip(np.sum(da * db, axis=1), -1, 1)))
