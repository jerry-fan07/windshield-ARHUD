"""Car frame, eye and virtual-image geometry.

The rig node hangs off the ego vehicle's chassis node, offset so that its origin is on the road under the driver's
nominal eye with the car at rest. It therefore pitches and rolls with the body, as the real HUD, road camera and head
tracker do. Panda3D vehicle nodes have +Y forward, +X right, +Z up; this package's car frame is x forward, y left,
z up, so car (x, y, z) is rig-local (-y, x, z).
"""
import math

import numpy as np
from panda3d.core import LMatrix4f, NodePath

from . import plan as PL


def car_to_local(p):
    """Car-frame point -> rig-local Panda3D coordinates."""
    return (-p[1], p[0], p[2])


class VirtualPlane:
    """The virtual image: a rectangle w x h at `dist` from the nominal eye along the look-down ray, facing the eye."""

    def __init__(self, kind="spec"):
        self.set(kind)

    def set(self, kind):
        W = PL.WINDOWS[kind]
        self.kind = kind
        self.dist, self.w, self.h = W["dist"], W["w"], W["h"]
        self.fovW, self.fovH = W["fovW"], W["fovH"]
        self.eye0 = np.array([0.0, 0.0, PL.EYE_H])
        ld = PL.LOOKDOWN
        self.look = np.array([math.cos(ld), 0.0, -math.sin(ld)])
        self.normal = -self.look
        self.right = np.array([0.0, -1.0, 0.0])
        up = np.cross(self.right, self.look)
        self.up = up / np.linalg.norm(up)
        self.c = self.eye0 + self.look * self.dist
        # Where the window's edges meet a flat road (for the coverage overlay)
        top_dep = ld - math.radians(self.fovH / 2)
        bot_dep = ld + math.radians(self.fovH / 2)
        self.road_near = PL.EYE_H / math.tan(bot_dep)
        self.road_far = PL.EYE_H / math.tan(top_dep) if top_dep > 0 else float("inf")

    def project(self, P, eye):
        """Car-frame points (N x 3) seen from `eye` -> crop pixels (N x 2); rows behind the eye are NaN."""
        P = np.atleast_2d(np.asarray(P, dtype=float))
        d = P - eye
        den = d @ self.normal
        t = ((self.c - eye) @ self.normal) / np.where(np.abs(den) < 1e-9, -1e-9, den)
        q = eye + d * t[:, None] - self.c
        u = q @ self.right
        v = q @ self.up
        px = (u / self.w + 0.5) * PL.CROP_W
        py = (0.5 - v / self.h) * PL.CROP_H
        out = np.stack([px, py], axis=1)
        out[(den > -1e-6) | (t <= 0)] = np.nan
        return out

    def pixel_point(self, px, py):
        """Crop pixel -> car-frame point on the virtual plane."""
        u = (px / PL.CROP_W - 0.5) * self.w
        v = (0.5 - py / PL.CROP_H) * self.h
        return self.c + self.right * u + self.up * v

    def pixel_dir(self, px, py, eye):
        p = self.pixel_point(px, py) - eye
        return p / np.linalg.norm(p)

    def visible_box(self, eye_off, mirror_w=None, mirror_h=None):
        """The part of the image (in plane metres, u right / v up) that the mirror aperture lets an eye at `eye_off`
        (car-frame offset from the nominal eye) see. The aperture is treated as a window EYE_TO_MIRROR ahead on the
        unfolded path; an eye at lateral offset d sees plane positions d + (a - d) * D / d_m for aperture edges a."""
        mw = (mirror_w or PL.MIRROR_W) / 2
        mh = (mirror_h or PL.MIRROR_H * math.cos(math.radians(15.5))) / 2
        dm, D = PL.EYE_TO_MIRROR, self.dist
        du = float(np.dot(eye_off, self.right))
        dv = float(np.dot(eye_off, self.up))
        k = D / dm
        return (du + (-mw - du) * k, du + (mw - du) * k, dv + (-mh - dv) * k, dv + (mh - dv) * k)


class CarRig:
    """Car frame attached to the ego chassis, with world <-> car conversions."""

    def __init__(self, render):
        self.render = render
        self.np = NodePath("arhud-car-frame")
        self.vehicle = None
        self.z_rest = None

    def attach(self, vehicle, z_rest):
        """Hang the rig off `vehicle` (a MetaDrive vehicle) with the chassis origin `z_rest` above the road at rest."""
        self.vehicle = vehicle
        self.z_rest = z_rest
        eye_fwd = vehicle.LENGTH / 2 - PL.EYE_TO_FRONT_BUMPER     # eye position ahead of the chassis centre
        self.np.reparentTo(vehicle.origin)
        # car-frame origin: under the eye. The centreline is at car y = CAR_CENTER_Y (-0.37 m, to the eye's right),
        # so the eye is at rig-local X = CAR_CENTER_Y (rig-local X points right).
        self.np.setPos(PL.CAR_CENTER_Y, eye_fwd, -z_rest)
        self.np.setHpr(0, 0, 0)
        self.eye_fwd = eye_fwd

    def update(self):
        """Refresh the cached transforms (call once per frame after physics)."""
        m = self.np.getMat(self.render)                 # rig-local -> world (row-vector convention)
        M = np.array([[m.getCell(r, c) for c in range(4)] for r in range(4)], dtype=float)
        # Columns of the rotation in world coordinates for the car axes: x = rig +Y, y = rig -X, z = rig +Z
        rx, ry, rz = M[1, :3], -M[0, :3], M[2, :3]
        self.R = np.stack([rx, ry, rz], axis=1)          # world = R @ car + o
        self.o = M[3, :3].copy()
        self.heading = math.atan2(rx[1], rx[0])          # world yaw of the car's x axis
        self.pitch = math.asin(max(-1.0, min(1.0, rx[2])))   # nose up positive
        self.roll = math.asin(max(-1.0, min(1.0, -ry[2])))

    def world_to_car(self, P):
        P = np.atleast_2d(np.asarray(P, dtype=float))
        if P.shape[1] == 2:
            P = np.hstack([P, np.zeros((P.shape[0], 1))])
        return (P - self.o) @ self.R

    def car_to_world(self, P):
        P = np.atleast_2d(np.asarray(P, dtype=float))
        return P @ self.R.T + self.o

    def dir_world_to_car(self, v):
        v = np.asarray(v, dtype=float)
        if v.shape[-1] == 2:
            v = np.concatenate([v, [0.0]])
        return self.R.T @ v
