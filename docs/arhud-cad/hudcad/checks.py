"""Acceptance checks for the housing.

  beam         every traced ray (eye box x field, both mirror figures) that lands on the mirror must miss every part
               on its way glass -> mirror -> fold -> panel; shutter leaves are checked in their open position
  windshield   nothing within GLASS_CLEAR of the glass plane the simulator traces
  hood/dash    the housing clears the simulator car's cluster hood; only the feet touch the dash
  printer      every printed piece fits the build volume in its print orientation
  fits         no two solid parts overlap, and no part overlaps the optics and boards the simulator draws itself
"""
import itertools
import math

import numpy as np
from build123d import Vector

from . import geo as g
from . import internals as it
from . import shell as sh
from .kit import aabb, basis_loc, lbox, union, cyl
from .mesh import tessellate


def mesh_of(part, lin=0.25, ang=0.5):
    if "_mesh" not in part.extra:
        P, N, I = tessellate(part.solid, lin, ang)
        part.extra["_mesh"] = (P, I)
    return part.extra["_mesh"]


def seg_tri_hits(A, B, P, I):
    """For segments A->B (n,3) and triangles (P, I), return a boolean per segment: does it cross any triangle."""
    v0, v1, v2 = P[I[:, 0]], P[I[:, 1]], P[I[:, 2]]
    e1, e2 = v1 - v0, v2 - v0
    out = np.zeros(len(A), dtype=bool)
    for k in range(len(A)):
        d = B[k] - A[k]
        h = np.cross(d, e2)
        a = np.einsum("ij,ij->i", e1, h)
        ok = np.abs(a) > 1e-12
        f = np.zeros_like(a)
        f[ok] = 1.0 / a[ok]
        s = A[k] - v0
        u = f * np.einsum("ij,ij->i", s, h)
        q = np.cross(s, e1)
        v = f * (q @ d)
        t = f * np.einsum("ij,ij->i", e2, q)
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6) & (t < 1 - 1e-6)
        out[k] = hit.any()
    return out


def seg_point_dist(A, B, Q):
    """Minimum distance from each segment A->B to the point cloud Q."""
    d = B - A
    L2 = np.einsum("ij,ij->i", d, d)
    best = np.full(len(A), np.inf)
    for k in range(len(A)):
        t = np.clip(((Q - A[k]) @ d[k]) / L2[k], 0, 1)
        r = Q - (A[k] + t[:, None] * d[k])
        best[k] = np.sqrt(np.einsum("ij,ij->i", r, r).min())
    return best


def leaf_open_offset(part):
    """Translation that takes a leaf from closed to open (simulator kinematics)."""
    if part.id == "leafFront":
        return -g.LID_DIR * (it.SL + 6.0)
    if part.id == "leafRear":
        return -g.LID_DIR * (it.SL / 2 + 1.0)
    return np.zeros(3)


def check_beam(parts):
    """Rays the housing blocks. Rays the panel's own cell glass already blocks (a layout matter, reported separately as
    'panel') are not charged to the housing."""
    res = {"rays": 0, "blocked": 0, "by": {}, "nearest": {}, "panel": 0, "panelRays": []}
    solids = [p for p in parts if p.kind in ("printed", "hardware", "sheet", "bought") and p.id not in ("coverGlass",)]
    from .kit import Part
    cell = Part(id="cell", name="cell", kind="reference", solid=reference_solids()["cell"])
    for mode in ("toroid", "sphere"):
        R = g.rays(mode)                                       # (n, 5, 3): eye, glass, mirror, fold, panel
        segs = [(R[:, 1], R[:, 2]), (R[:, 2], R[:, 3])]        # the fold -> panel leg ends on the cell itself
        res["rays"] += len(R)
        Pc, Ic = mesh_of(cell)
        layout = np.zeros(len(R), dtype=bool)
        for A, B in segs:
            layout |= seg_tri_hits(A, B, Pc, Ic)
        res["panel"] += int(layout.sum())
        if mode == "toroid":
            rs = [r for r in g.LAYOUT["rays"][mode] if r["inside"]]
            res["panelRays"] = sorted({(tuple(rs[k]["e"]), tuple(rs[k]["f"])) for k in np.where(layout)[0]})
        segs.append((R[:, 3], R[:, 4]))
        blocked = np.zeros(len(R), dtype=bool)
        for p in solids:
            P, I = mesh_of(p)
            if len(P) == 0:
                continue
            P = P + leaf_open_offset(p)
            lo, hi = P.min(0), P.max(0)
            hit_any = np.zeros(len(R), dtype=bool)
            dmin = np.inf
            for A, B in segs:
                # quick reject: segments whose bounding box misses the part
                sl, sh_ = np.minimum(A, B), np.maximum(A, B)
                cand = np.all((sh_ >= lo - 1) & (sl <= hi + 1), axis=1)
                if cand.any():
                    hits = np.zeros(len(R), dtype=bool)
                    hits[cand] = seg_tri_hits(A[cand], B[cand], P, I)
                    hit_any |= hits
                # clearance to the part's vertices (subsampled)
                Q = P[:: max(1, len(P) // 4000)]
                near = np.all((sh_ >= lo - 25) & (sl <= hi + 25), axis=1)
                if near.any():
                    dmin = min(dmin, seg_point_dist(A[near], B[near], Q).min())
            hit_any &= ~layout
            if hit_any.any():
                res["by"][p.id] = res["by"].get(p.id, 0) + int(hit_any.sum())
            blocked |= hit_any
            if np.isfinite(dmin):
                res["nearest"][p.id] = min(res["nearest"].get(p.id, np.inf), float(dmin))
        res["blocked"] += int(blocked.sum())
    res["nearest"] = dict(sorted(res["nearest"].items(), key=lambda kv: kv[1])[:8])
    return res


def check_envelope(parts):
    out = {}
    worst_glass, worst_hood, low = (np.inf, None), (np.inf, None), (np.inf, None)
    for p in parts:
        if p.kind == "reference":
            continue
        P, _ = mesh_of(p)
        if len(P) == 0:
            continue
        gl = (g.GLASS_G[1] - (P[:, 0] - g.GLASS_G[0]) * math.tan(g.RAKE)) - P[:, 1]
        k = int(np.argmin(gl))
        if gl[k] < worst_glass[0]:
            worst_glass = (float(gl[k]), p.id)
        m = (P[:, 0] < g.HOOD_X1) & (np.abs(P[:, 2]) < g.HOOD_Z)
        if m.any():
            c = float((P[m, 1] - g.HOOD_TOP).min())
            if c < worst_hood[0]:
                worst_hood = (c, p.id)
        if p.id != "feet":
            y = float(P[:, 1].min()) - g.DASH_Y
            if y < low[0]:
                low = (y, p.id)
    out["glassClearMm"], out["glassClearPart"] = round(worst_glass[0], 2), worst_glass[1]
    out["hoodClearMm"], out["hoodClearPart"] = round(worst_hood[0], 2), worst_hood[1]
    out["dashClearMm"], out["dashClearPart"] = round(low[0], 2), low[1]
    return out


def mirror_points(mode="toroid", n=(31, 21)):
    """Sample points on the mirror substrate: front surface, back face and edges."""
    pts = []
    for u in np.linspace(-g.MIRROR_W / 2, g.MIRROR_W / 2, n[0]):
        for v in np.linspace(-g.MIRROR_H / 2, g.MIRROR_H / 2, n[1]):
            pts.append(g.mirror_point(u, v, mode))
            pts.append(g.mirror_back(u, v))
    return np.array(pts)


def reference_solids():
    """The optics and boards the simulator draws itself, as solids, for the fit check."""
    ref = {}
    PX, PY = g.PANEL_C[0], g.PANEL_C[1]
    ref["cell"] = aabb(PX - g.PANEL_OUT_X / 2 - g.TFT_LEDGE, PX + g.PANEL_OUT_X / 2, PY - 1.5, PY, -g.PANEL_OUT_Z / 2, g.PANEL_OUT_Z / 2)
    ref["backlightStack"] = aabb(PX - 21, PX + 21, g.HS_BASE_TOP, PY - 2.0, -36, 36)
    ref["heatSink"] = aabb(PX - 25, PX + 25, g.HS_FIN_BOT, g.HS_BASE_TOP, -40, 40).cut(
        union([aabb(PX - 26, PX + 26, g.HS_FIN_BOT - 1, g.HS_BASE_BOT, z + 0.6, z + 5.9) for z in np.arange(-39, 39, 6.5)]))
    ref["fan"] = aabb(PX - 20, PX + 20, g.FAN_BOT, g.HS_FIN_BOT, -20, 20)
    b = it.BOARD
    ref["hdmiBoard"] = aabb(b["cx"] - b["w"] / 2, b["cx"] + b["w"] / 2, b["cy"] - b["d"] / 2, b["cy"] + b["d"] / 2, b["z_pcb"] - 7.0, b["z_pcb"] + 1.6)
    ref["foldGlass"] = it.fb(g.FOLD_V0, g.FOLD_V1, -g.FOLD_T, 0.0, g.FOLD_U0, g.FOLD_U1)
    ref["absorber"] = it.fb(g.FOLD_V0 - 2, g.FOLD_V1 - 22, -11.5, -8.5, -71.3, 71.3).fuse(
        it.fb(g.FOLD_V0 - 2, g.FOLD_V1 - 22, -23.5, -11.5, -66.94, 66.94))
    sg = it.SG
    bs, bn, bz = sg["body_s"], sg["body_n"], sg["pivot_z"]
    ref["servo"] = sh.lid_box(bs - 11.25, bs + 11.25, bn - 11.35, bn + 11.35, bz - 6.1, bz + 6.1)
    return ref


def check_fits(parts):
    out = {"pairs": [], "refHits": [], "mirror": {}}
    solid = [p for p in parts if p.kind in ("printed", "bought", "sheet")]
    for a, b in itertools.combinations(solid, 2):
        ba, bb = a.solid.bounding_box(), b.solid.bounding_box()
        if (ba.max.X < bb.min.X or bb.max.X < ba.min.X or ba.max.Y < bb.min.Y or bb.max.Y < ba.min.Y
                or ba.max.Z < bb.min.Z or bb.max.Z < ba.min.Z):
            continue
        try:
            c = a.solid.intersect(b.solid)
            v = sum(x.volume for x in c) if isinstance(c, list) or c.__class__.__name__ == "ShapeList" else (c.volume if c else 0)
        except Exception as e:
            v = -1
        if v is None or v > 0.5 or v < 0:
            out["pairs"].append((a.id, b.id, round(v, 2) if v else v))
    ref = reference_solids()
    for name, r in ref.items():
        rb = r.bounding_box()
        for p in solid:
            pb = p.solid.bounding_box()
            if (pb.max.X < rb.min.X or rb.max.X < pb.min.X or pb.max.Y < rb.min.Y or rb.max.Y < pb.min.Y
                    or pb.max.Z < rb.min.Z or rb.max.Z < pb.min.Z):
                continue
            c = p.solid.intersect(r)
            v = sum(x.volume for x in c) if c is not None and c.__class__.__name__ == "ShapeList" else (c.volume if c else 0)
            if v and v > 0.5:
                out["refHits"].append((name, p.id, round(v, 1)))
    # mirror substrate against every printed part (points inside a solid = interference)
    pts = mirror_points()
    for p in solid:
        if p.kind != "printed":
            continue
        bb = p.solid.bounding_box()
        near = pts[(pts[:, 0] > bb.min.X - 1) & (pts[:, 0] < bb.max.X + 1) & (pts[:, 1] > bb.min.Y - 1) &
                   (pts[:, 1] < bb.max.Y + 1) & (pts[:, 2] > bb.min.Z - 1) & (pts[:, 2] < bb.max.Z + 1)]
        bad = sum(1 for q in near if p.solid.is_inside(Vector(*q)))
        if bad:
            out["mirror"][p.id] = bad
    return out, ref


def print_orient(part, bed=g.BED):
    """Rotation (car -> printer, Z up) that puts part.down on the bed, yawed to fit; returns dict.
    A part made of several identical pieces (qty > 1, extra['one']) is oriented and checked as one piece."""
    if "one" in part.extra:
        from .kit import Part
        one = Part(id=part.id + "One", name="", kind="printed", solid=part.extra["one"], down=part.down)
        return print_orient(one, bed)
    P, _ = mesh_of(part)
    d = np.asarray(part.down, float)
    d /= np.linalg.norm(d)
    # rotation taking d to -Z
    z = -d
    a = np.array([1.0, 0, 0]) if abs(z[0]) < 0.9 else np.array([0, 1.0, 0])
    x = a - z * (a @ z); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    R0 = np.vstack([x, y, z])                                   # rows: printer axes in car coordinates
    Q = P @ R0.T
    best = None
    for deg in np.arange(0, 180, 1.0):
        c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        q = Q @ Rz.T
        size = q.max(0) - q.min(0)
        fits = size[0] <= bed[0] and size[1] <= bed[1] and size[2] <= bed[2]
        key = (not fits, size[0] * size[1], max(size[0], size[1]))
        if best is None or key < best[0]:
            best = (key, deg, Rz @ R0, size, fits)
    _, deg, R, size, fits = best
    q = P @ R.T
    return dict(R=R, offset=-q.min(0), size=[round(float(s), 1) for s in size], fits=bool(fits), yaw=float(deg))
