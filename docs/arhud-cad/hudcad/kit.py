"""Small modelling kit: oriented boxes and cylinders in the car frame, fastener holes and hardware solids, and the
Part record every builder returns."""
from dataclasses import dataclass, field

import numpy as np
from build123d import (Axis, Box, Compound, Cylinder, Face, Location, Matrix, Plane, Solid, Vector, Wire, extrude,
                       Cone)

V = lambda *a: Vector(*[float(x) for x in (a[0] if len(a) == 1 else a)])


# ---- placement helpers ------------------------------------------------------------------------------------------
def frame(origin, x_dir, z_dir):
    """A build123d Plane (local frame) at origin with the given x and z directions (car frame, mm)."""
    return Plane(origin=V(origin), x_dir=V(x_dir), z_dir=V(z_dir))


def box_at(c, size, pl=None):
    """Box of size (sx, sy, sz) centred at c; axes of plane pl (default car axes)."""
    b = Box(*size)
    if pl is None:
        return b.moved(Location(V(c)))
    p = Plane(origin=V(c), x_dir=pl.x_dir, z_dir=pl.z_dir)
    return b.moved(p.location)


def aabb(x0, x1, y0, y1, z0, z1):
    """Axis-aligned box between bounds (car frame)."""
    return Box(x1 - x0, y1 - y0, z1 - z0).moved(Location(V((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)))


def cyl(p, axis, r, h, centered=False):
    """Cylinder of radius r and length h starting at p along axis (or centred on p)."""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    start = np.asarray(p, float) - (a * h / 2 if centered else 0)
    c = Cylinder(r, h, align=None)                         # base at origin, along +Z
    pl = Plane(origin=V(start), z_dir=V(a))
    return c.moved(pl.location)


def cone(p, axis, r0, r1, h):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    c = Cone(r0, r1, h, align=None)
    return c.moved(Plane(origin=V(p), z_dir=V(a)).location)


def prism(pts2, pl, h):
    """Extrude a polygon given in plane pl's 2-D coordinates by h along the plane normal."""
    w = Wire.make_polygon([pl.from_local_coords((x, y)) for x, y in pts2], close=True)
    return extrude(Face(w), amount=h, dir=pl.z_dir)


def xy_prism(pts, z0, z1):
    """Side profile (x, y) in the car's XY plane, extruded across z0..z1."""
    w = Wire.make_polygon([V(x, y, z0) for x, y in pts], close=True)
    return extrude(Face(w), amount=z1 - z0, dir=(0, 0, 1))


def union(shapes):
    shapes = [s for s in shapes if s is not None]
    if not shapes:
        return None
    out = shapes[0]
    for s in shapes[1:]:
        out = out.fuse(s)
    return out.clean()


def cut(a, *tools):
    for t in tools:
        if t is not None:
            a = a.cut(t)
    return a


# ---- fasteners -------------------------------------------------------------------------------------------------
# Heat-set inserts (brass, knurled): hole diameter and depth for printed ASA. M3 x 5.7 and M3 x 3 short, M4, M5.
INSERT = {
    "M3": dict(hole=4.0, depth=6.0, od=4.6, length=5.7),
    "M3s": dict(hole=4.0, depth=3.2, od=4.6, length=3.0),
    "M4": dict(hole=5.6, depth=8.5, od=6.0, length=8.1),
    "M5": dict(hole=6.4, depth=10.0, od=7.0, length=9.5),
}
CLEAR = {"M3": 3.4, "M4": 4.5, "M5": 5.5}
HEAD = {"M3": dict(d=5.7, k=1.7), "M4": dict(d=7.6, k=2.2), "M5": dict(d=9.5, k=2.8)}   # button heads (ISO 7380)


def insert_hole(p, axis, size="M3"):
    """Hole for a heat-set insert, entering at p and going along axis (into the material)."""
    s = INSERT[size]
    return cyl(p, axis, s["hole"] / 2, s["depth"])


def clear_hole(p, axis, length, size="M3"):
    return cyl(p, axis, CLEAR[size] / 2, length)


def csk_hole(p, axis, length, size="M3"):
    """Countersunk clearance hole entering at p (surface) along axis: 90-degree head seat plus shank."""
    d = {"M3": 6.4, "M4": 8.4, "M5": 10.4}[size]
    r = CLEAR[size] / 2
    head = cone(p, axis, d / 2, r, (d / 2 - r))
    return head.fuse(cyl(p, axis, r, length))


@dataclass
class Hardware:
    """Accumulates fastener solids for the GLB and the bill of materials."""
    items: list = field(default_factory=list)

    def screw(self, p, axis, length, size="M3", head="button", note=""):
        """Screw with its head at p, shank going along axis."""
        a = np.asarray(axis, float)
        a = a / np.linalg.norm(a)
        hd = HEAD[size]
        d = {"M3": 3.0, "M4": 4.0, "M5": 5.0}[size]
        if head == "csk":
            hs = cone(np.asarray(p) - a * 0.0, a, d * 1.0, d / 2, d / 2)
        elif head == "socket":
            hs = cyl(np.asarray(p) - a * d, a, d * 0.85, d)
        else:
            hs = cyl(np.asarray(p) - a * hd["k"], a, hd["d"] / 2, hd["k"])
        sh = cyl(p, a, d / 2 * 0.92, length)
        self.items.append(("screw", f"{size} x {length:g} {head}", hs.fuse(sh), note))

    def insert(self, p, axis, size="M3", note=""):
        s = INSERT[size]
        self.items.append(("insert", f"{size.rstrip('s')} x {s['length']:g} heat-set insert{' (short)' if size.endswith('s') else ''}",
                           cyl(p, axis, s["od"] / 2, s["length"]), note))

    def add(self, kind, spec, solid, note=""):
        self.items.append((kind, spec, solid, note))

    def compound(self, kinds=None):
        sel = [s for k, _, s, _ in self.items if kinds is None or k in kinds]
        return Compound(sel) if sel else None

    def bom(self):
        out = {}
        for k, spec, _, note in self.items:
            out.setdefault((k, spec), 0)
            out[(k, spec)] += 1
        return out


@dataclass
class Part:
    id: str
    name: str
    kind: str                   # printed | hardware | sheet | bought | reference
    solid: object               # build123d shape, car frame, mm
    material: str = "asa"       # asa | tpu | brass | steel | alu | glass | film | foam
    desc: str = ""
    step: str = ""              # housing assembly step id
    hud: str = ""               # hudUnit part group in the simulator
    explode: tuple = (0, 0, 0)  # metres, car frame
    down: tuple = None          # printed: car-frame direction that faces the bed
    supports: str = "none"
    qty: int = 1
    sim: bool = True            # shown by the simulator from this CAD (False: the simulator already draws it)
    spec: str = ""
    extra: dict = field(default_factory=dict)


# ---- arbitrary orthonormal frames ------------------------------------------------------------------------------
def basis_loc(origin, ex, ey):
    """Location whose local X, Y axes are ex, ey (Z = ex x ey) at origin (car frame, mm)."""
    from OCP.gp import gp_Trsf
    from build123d import Location
    ex = np.asarray(ex, float); ex = ex / np.linalg.norm(ex)
    ey = np.asarray(ey, float); ey = ey - ex * (ey @ ex); ey = ey / np.linalg.norm(ey)
    ez = np.cross(ex, ey)
    o = np.asarray(origin, float)
    tr = gp_Trsf()
    tr.SetValues(ex[0], ey[0], ez[0], o[0], ex[1], ey[1], ez[1], o[1], ex[2], ey[2], ez[2], o[2])
    return Location(tr)


def lbox(loc, x0, x1, y0, y1, z0, z1):
    """Box between local bounds, placed by loc."""
    return Box(x1 - x0, y1 - y0, z1 - z0).moved(Location(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))).moved(loc)


def lcyl(loc, p, axis, r, h, centered=False):
    """Cylinder in local coordinates of loc."""
    return cyl(p, axis, r, h, centered).moved(loc)


def lprism(loc, pts, z0, z1):
    """Polygon in the local XY plane extruded from z0 to z1, placed by loc."""
    w = Wire.make_polygon([Vector(x, y, z0) for x, y in pts], close=True)
    return extrude(Face(w), amount=z1 - z0, dir=(0, 0, 1)).moved(loc)


def to_local(loc_origin, ex, ey, p):
    ex = np.asarray(ex, float); ey = np.asarray(ey, float); ez = np.cross(ex, ey)
    r = np.asarray(p, float) - np.asarray(loc_origin, float)
    return np.array([r @ ex, r @ ey, r @ ez])


def from_local(loc_origin, ex, ey, q):
    ex = np.asarray(ex, float); ey = np.asarray(ey, float); ez = np.cross(ex, ey)
    return np.asarray(loc_origin, float) + ex * q[0] + ey * q[1] + ez * q[2]


def solidify(r):
    """build123d boolean results can be a ShapeList; turn them back into one shape (a Compound if several)."""
    if r is None:
        return None
    if isinstance(r, (list, tuple)) or r.__class__.__name__ == "ShapeList":
        items = [x for x in r if x is not None]
        if not items:
            return None
        return items[0] if len(items) == 1 else Compound(items)
    return r


def common(a, *bs):
    for b in bs:
        a = solidify(a.intersect(b))
        if a is None:
            return None
    return a
