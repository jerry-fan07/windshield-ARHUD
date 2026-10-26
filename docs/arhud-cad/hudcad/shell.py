"""The printed shell: four body quarters and four lid pieces.

The shell is one closed solid first (side profile extruded across the width, minus the cavity), so every piece shares
exact faces with its neighbours. It is then split into a body and a cap at a plane parallel to the lid, SKIRT below
it, and each into quarters that fit the printer. The rear of the body steps up over the simulator car's cluster hood.

Joints:
  body seams     continuous internal flange strips with M3 screws into heat-set inserts; the strips also seal the
                 seam against light. The rear quarters' front strip is the stray-light baffle wall.
  cap seams      half-lap joints in the 6 mm lid (flush underside, so the shutter leaves run on a flat ceiling),
                 countersunk M3 screws from the top into M3 x 3 inserts.
  cap to body    spigot tabs on the cap skirts reach 12 mm into the body; M3 button screws through the body wall.
"""
import math

import numpy as np
from build123d import Keep, Plane, Vector, split

from . import geo as g
from .kit import (Hardware, Part, aabb, basis_loc, clear_hole, common, solidify, csk_hole, cyl, frame, insert_hole, lbox, prism, union, cut,
                  xy_prism, INSERT)

T, TF, TL = g.T_WALL, g.T_FLOOR, g.T_LID
Z_IN = g.ZW - T                                   # inner face of the side walls
COS_R = math.cos(g.RAKE)


def nose_in(x):
    return g.nose_y(x) - T / COS_R


def outer_profile():
    xn = g.x_nose()
    return [(g.XR, g.OVER_BOT), (g.STEP_X, g.OVER_BOT), (g.STEP_X, g.FLOOR_BOT), (g.XF, g.FLOOR_BOT),
            (g.XF, g.nose_y(g.XF)), (xn, g.lid_top(xn)), (g.XR, g.lid_top(g.XR))]


def inner_profile():
    # where the lid underside meets the inner nose facet
    t = math.tan(g.RAKE)
    xi = (g.GLASS_G[1] + g.GLASS_G[0] * t - g.GLASS_CLEAR - T / COS_R - g.YF - g.S * g.XF) / (t - g.S)
    xf_in = g.XF - T
    return [(g.XR + T, g.OVER_BOT + TF), (g.STEP_X + T, g.OVER_BOT + TF), (g.STEP_X + T, g.FLOOR_TOP),
            (xf_in, g.FLOOR_TOP), (xf_in, nose_in(xf_in)), (xi, g.lid_y(xi)), (g.XR + T, g.lid_y(g.XR + T))]


def split_plane(offset=0.0):
    """The body/cap joint plane (offset along the lid normal)."""
    p0 = Vector(800.0, g.split_y(800.0), 0.0) + Vector(*g.LID_N) * offset
    return Plane(origin=p0, z_dir=Vector(*g.LID_N))


def lid_frame():
    """Frame in the lid underside plane: x along the lid (forward), z_dir = lid normal, origin at the aperture centre."""
    return frame(g.AP_C, g.LID_DIR, g.LID_N)


LID_LOC = basis_loc(g.AP_C, g.LID_DIR, g.LID_N)


def lid_coords(p):
    """(s along the lid from the aperture centre, n above the lid underside, z) for a car point."""
    r = np.asarray(p, float) - g.AP_C
    return float(r @ g.LID_DIR), float(r @ g.LID_N), float(r[2])


def lid_point(s, n, z):
    return g.AP_C + g.LID_DIR * s + g.LID_N * n + np.array([0, 0, z])


def lid_box(s0, s1, n0, n1, z0, z1):
    """Box in lid coordinates (s along the lid, n along the lid normal, z across)."""
    return lbox(LID_LOC, s0, s1, n0, n1, z0, z1)


# The lid basis (s, n, z) must be right-handed for lid_box: s x n should be +z.
assert np.cross(g.LID_DIR, g.LID_N)[2] > 0.99


def aperture():
    """The lid opening, from the rays where they cross the lid's top, its underside and the rails' bottom (+3 mm),
    in lid coordinates."""
    s_lo, s_hi, z_lo, z_hi = 1e9, -1e9, 1e9, -1e9
    for mode in ("toroid", "sphere"):
        R = g.rays(mode)
        A, B = R[:, 1], R[:, 2]                                    # glass -> mirror leg
        for n in (-9.0, 0.0, TL):                                   # rail bottom (width only), lid underside, lid top
            fa = (A - g.AP_C) @ g.LID_N - n
            fb = (B - g.AP_C) @ g.LID_N - n
            ok = fa * fb < 0
            t = fa[ok] / (fa[ok] - fb[ok])
            P = A[ok] + (B[ok] - A[ok]) * t[:, None]
            s = (P - g.AP_C) @ g.LID_DIR
            if n >= 0:
                s_lo, s_hi = min(s_lo, s.min()), max(s_hi, s.max())
            z_lo, z_hi = min(z_lo, P[:, 2].min()), max(z_hi, P[:, 2].max())
    m = 3.0
    return dict(s0=s_lo - m, s1=s_hi + m, z0=z_lo - m, z1=z_hi + m)


AP = aperture()
AP_SC = (AP["s0"] + AP["s1"]) / 2          # aperture centre along the lid (the shutter's origin)
AP_LEN, AP_WID = AP["s1"] - AP["s0"], AP["z1"] - AP["z0"]
RAIL_Z_IN = AP["z1"] + 0.5                 # shutter rails: inner face, leaf slot depth, screw line
SLOT_Z = RAIL_Z_IN + 8.0
GLASS_OVERLAP, GLASS_GAP, GLASS_T, GASKET = 4.0, 0.5, 3.0, 0.5
REBATE_D = GLASS_T + GASKET + 0.1


def glass_rect():
    o = GLASS_OVERLAP
    return dict(s0=AP["s0"] - o, s1=AP["s1"] + o, z0=AP["z0"] - o, z1=AP["z1"] + o)


# ---------------------------------------------------------------------------------------------------------------
def shell_solid():
    out = xy_prism(outer_profile(), -g.ZW, g.ZW)
    try:
        out = out.fillet(3.0, out.edges().filter_by(lambda e: abs(e.tangent_at(0).Z) > 0.99))
    except Exception as e:                                          # keep sharp if OCC refuses
        print("  shell: outer corner fillet skipped:", e)
    cav = xy_prism(inner_profile(), -Z_IN, Z_IN)
    return out.cut(cav)


def build_shell(keepouts, hw: Hardware):
    """Returns (body_parts, cap_parts) as lists of Part, and fills hw with the joint fasteners."""
    sh = shell_solid()
    body = split(sh, bisect_by=split_plane(), keep=Keep.BOTTOM)
    cap = split(sh, bisect_by=split_plane(), keep=Keep.TOP)
    body = add_body_features(body, keepouts, hw)
    cap = add_cap_features(cap, hw)
    return body, cap


# ---------------------------------------------------------------------------------------------------------------
# body
# ---------------------------------------------------------------------------------------------------------------
STRIP_H = 10.0             # how far a seam strip stands off the wall or floor
A_T, B_T = 6.0, 4.0        # strip thickness: insert side, screw side


def _seam_strips_z(keepouts):
    """Strips along the z = 0 seam: insert side (left, z < 0) and screw side (right). Returns (left, right, screws)."""
    segs = []   # (kind, x0, x1, y0, y1) boxes against floor / walls, extent along the seam
    # floor, rear bay (between the PGU bay and the baffle) and front bay
    segs.append(("floor", 739.5, 789.0, g.FLOOR_TOP, g.FLOOR_TOP + STRIP_H))
    segs.append(("floor", 800.0, 1022.0, g.FLOOR_TOP, g.FLOOR_TOP + STRIP_H))
    # overhang floor and rear wall
    segs.append(("floor", g.XR + T, g.STEP_X, g.OVER_BOT + TF, g.OVER_BOT + TF + STRIP_H))
    segs.append(("wall", g.XR + T, g.XR + T + STRIP_H, g.OVER_BOT + TF, g.split_y(g.XR) - 1.0))
    # front wall, up to the mirror stand's top adjuster
    segs.append(("wall", g.XF - T - STRIP_H, g.XF - T, g.FLOOR_TOP, 900.0))
    # baffle wall (rear face)
    segs.append(("wall", 790.0 - STRIP_H, 790.0, g.FLOOR_TOP + STRIP_H, g.BAFFLE_TOP))
    left, right, screws = [], [], []
    for kind, x0, x1, y0, y1 in segs:
        left.append(aabb(x0, x1, y0, y1, -A_T, 0.0))
        right.append(aabb(x0, x1, y0, y1, 0.0, B_T))
        # screws every ~45 mm along the long axis, in the middle of the strip
        if kind == "floor":
            n = max(1, int((x1 - x0) // 45))
            for i in range(n):
                x = x0 + (x1 - x0) * (i + 0.5) / n
                screws.append(np.array([x, (y0 + y1) / 2 + 1.0, 0.0]))
        else:
            n = max(1, int((y1 - y0) // 45))
            for i in range(n):
                y = y0 + (y1 - y0) * (i + 0.5) / n
                screws.append(np.array([(x0 + x1) / 2, y, 0.0]))
    L = union(left).cut(keepouts.solid)
    Rr = union(right).cut(keepouts.solid)
    screws = [p for p in screws if not keepouts.contains(p, 6.0)]
    return L, Rr, screws


def _seam_strips_x(hw_points):
    """Strips at the x = X_SEAM seam: the rear quarters' baffle wall (insert side), the front quarters' flange."""
    xs = g.X_SEAM
    # rear: baffle wall full width from the floor to BAFFLE_TOP, side strips above it to the joint line
    baffle = aabb(xs - A_T, xs, g.FLOOR_TOP, g.BAFFLE_TOP, -Z_IN, Z_IN)
    ytop = g.split_y(xs) - 1.0
    rear_sides = [aabb(xs - A_T, xs, g.BAFFLE_TOP - 1, ytop, sg * Z_IN - (STRIP_H if sg > 0 else 0),
                       sg * Z_IN + (0 if sg > 0 else STRIP_H)) for sg in (-1, 1)]
    rear = union([baffle] + rear_sides)
    # front: floor strip and side strips
    front = [aabb(xs, xs + B_T, g.FLOOR_TOP, g.FLOOR_TOP + 14.0, -Z_IN, Z_IN)]
    for sg in (-1, 1):
        z0, z1 = (Z_IN - STRIP_H, Z_IN) if sg > 0 else (-Z_IN, -Z_IN + STRIP_H)
        front.append(aabb(xs, xs + B_T, g.FLOOR_TOP, ytop, z0, z1))
    front = union(front)
    pts = []
    for z in (-150, -100, -50, 50, 100, 150):
        pts.append(np.array([xs, g.FLOOR_TOP + 7.0, float(z)]))
    for sg in (-1, 1):
        for y in np.linspace(g.FLOOR_TOP + 30, ytop - 12, 4):
            pts.append(np.array([xs, float(y), sg * (Z_IN - STRIP_H / 2)]))
    return rear, front, pts


def add_body_features(body, keepouts, hw):
    xs = g.X_SEAM
    zl, zr, zscrews = _seam_strips_z(keepouts)
    xr, xf, xscrews = _seam_strips_x(None)
    adds = [zl, zr, xr, xf]

    # floor bosses: feet (M5 insert from below), cap tabs are on the cap
    feet = [(668.0, -150.0), (668.0, 150.0), (1000.0, -150.0), (1000.0, 150.0)]
    for x, z in feet:
        adds.append(cyl((x, g.FLOOR_TOP - 0.5, z), (0, 1, 0), 8.0, 10.5))
    # PGU bay and mirror stand bosses: from the internals' declared mount points
    for p in keepouts.mount_points:
        adds.append(cyl((p[0], g.FLOOR_BOT - 3.0, p[2]), (0, 1, 0), 5.0, 3.5))
    # internal stiffening ribs on the side walls (also break up reflections) every ~75 mm
    for sg in (-1, 1):
        for x in (690.0, 740.0):
            if x < xs:
                y1 = g.split_y(x) - 4
            else:
                y1 = g.split_y(x) - 4
            z0, z1 = (Z_IN - 5.0, Z_IN) if sg > 0 else (-Z_IN, -Z_IN + 5.0)
            adds.append(aabb(x - 1.2, x + 1.2, g.FLOOR_TOP, y1, z0, z1))
    body = union([body] + adds)

    # holes ---------------------------------------------------------------------------------------------------------
    tools = []
    for x, z in feet:
        tools.append(insert_hole((x, g.FLOOR_BOT - 0.01, z), (0, 1, 0), "M5"))
    for p in keepouts.mount_points:
        tools.append(insert_hole((p[0], g.FLOOR_TOP + 4.0, p[2]), (0, -1, 0), "M3"))
        hw.insert((p[0], g.FLOOR_TOP, p[2]), (0, -1, 0), note="floor mounts")
    for p in zscrews:                       # insert in the left strip from the seam face, screw from the right
        tools.append(insert_hole((p[0], p[1], 0.0), (0, 0, -1), "M3"))
        tools.append(clear_hole((p[0], p[1], 0.0), (0, 0, 1), B_T + 0.1))
        hw.screw((p[0], p[1], B_T), (0, 0, -1), 10, note="body z seam")
        hw.insert((p[0], p[1], 0.0), (0, 0, -1), note="body z seam")
    for p in xscrews:                       # insert in the rear (baffle) side, screw from the front flange
        tools.append(insert_hole((xs, p[1], p[2]), (-1, 0, 0), "M3"))
        tools.append(clear_hole((xs, p[1], p[2]), (1, 0, 0), B_T + 0.1))
        hw.screw((xs + B_T, p[1], p[2]), (-1, 0, 0), 10, note="body x seam")
        hw.insert((xs, p[1], p[2]), (-1, 0, 0), note="body x seam")
    # floor openings under the PGU bay (exhaust and intake pass the bay's own floor)
    b = keepouts.bay
    tools.append(aabb(b["x0"] + 7, b["x1"] - 7, g.FLOOR_BOT - 1, g.FLOOR_TOP + 1, b["z0"] + 7, b["z1"] - 7))
    # cable port in the left wall for the servo, light-sensor and thermistor leads to the HUD controller
    tools.append(cyl((760.0, 848.0, -g.ZW - 1), (0, 0, 1), 7.0, T + 2))
    # cap screws through the body walls
    for t in CAP_TABS:
        p, nrm = np.array(t["screw"]), np.array(t["normal"])
        tools.append(clear_hole(p - nrm * 0.5, -nrm, T + 1.0))
    body = cut(body, *tools)

    # split into quarters -----------------------------------------------------------------------------------------
    rear = split(body, bisect_by=Plane(origin=(xs, 0, 0), z_dir=(1, 0, 0)), keep=Keep.BOTTOM)
    front = split(body, bisect_by=Plane(origin=(xs, 0, 0), z_dir=(1, 0, 0)), keep=Keep.TOP)
    out = []
    zp = Plane(origin=(0, 0, 0), z_dir=(0, 0, 1))
    for nm, half in (("Rear", rear), ("Front", front)):
        for side, keep in (("left", Keep.BOTTOM), ("right", Keep.TOP)):
            q = split(half, bisect_by=zp, keep=keep)
            out.append((f"body{nm}{side.capitalize()}", f"Body, {nm.lower()} {side} quarter", q))
    return out


# ---------------------------------------------------------------------------------------------------------------
# cap
# ---------------------------------------------------------------------------------------------------------------
LAP_W = 12.0
RAIL_SCREW_S = (-262.0, -200.0, -150.0, -52.0, -28.0, 40.0, 128.0)   # clear of the clamps and the rail joint
RAIL_SCREW_Z = SLOT_Z + 4.5


def _cap_tabs():
    """Spigot tabs on the cap skirts and the matching screws through the body walls."""
    tabs = []
    def side(x, sg):
        ys = g.split_y(x)
        return dict(c=(x, ys - 2, sg * (Z_IN - 3.0)), size=(20.0, 20.0, 6.0), screw=(x, ys - 6.0, sg * g.ZW),
                    normal=(0, 0, sg))
    for x in (650.0, 760.0, 860.0, 955.0):
        for sg in (-1, 1):
            tabs.append(side(x, sg))
    for z in (-100.0, 100.0):
        ys = g.split_y(g.XR)
        tabs.append(dict(c=(g.XR + T + 3.0, ys - 2, z), size=(6.0, 20.0, 20.0), screw=(g.XR, ys - 6.0, z), normal=(-1, 0, 0)))
    for z in (-140.0, 140.0):
        ys = g.split_y(g.XF)
        tabs.append(dict(c=(g.XF - T - 3.0, ys - 2, z), size=(6.0, 20.0, 20.0), screw=(g.XF, ys - 6.0, z), normal=(1, 0, 0)))
    return tabs


CAP_TABS = _cap_tabs()


def rail_screw_points():
    """Where the shutter rails screw to the lid from below (lid coordinates s, z)."""
    return [(s, sg * RAIL_SCREW_Z) for sg in (-1, 1) for s in RAIL_SCREW_S]


def clamp_points():
    """Dust-cover glass clamps on the lid top (lid coordinates s, z): three per side, two at the front."""
    gr = glass_rect()
    pts = []
    for sg in (-1, 1):
        for s in np.linspace(gr["s0"] + 40, gr["s1"] - 40, 3):
            pts.append(dict(s=float(s), z=sg * (gr["z1"] + 5.0), dir=(0, sg)))
    for z in (-90.0, 90.0):
        pts.append(dict(s=gr["s1"] + 5.0, z=z, dir=(1, 0)))
    return pts


def add_cap_features(cap, hw):
    # opening, glass rebate --------------------------------------------------------------------------------------
    a, gr = AP, glass_rect()
    cap = cap.cut(lid_box(a["s0"], a["s1"], -5, TL + 5, a["z0"], a["z1"]))
    gp = GLASS_GAP
    cap = cap.cut(lid_box(gr["s0"] - gp, gr["s1"] + gp, TL - REBATE_D, TL + 5, gr["z0"] - gp, gr["z1"] + gp))
    # spigot tabs ---------------------------------------------------------------------------------------------------
    tabs = []
    for t in CAP_TABS:
        cx, cy, cz = t["c"]
        sx, sy, sz = t["size"]
        tabs.append(aabb(cx - sx / 2, cx + sx / 2, cy - 12.0, g.split_y(cx) + 8.0, cz - sz / 2, cz + sz / 2))
    cap = union([cap] + tabs)
    tools = []
    for t in CAP_TABS:
        p, nrm = np.array(t["screw"]), np.array(t["normal"], float)
        tools.append(insert_hole(p - nrm * T, -nrm, "M3"))
        hw.screw(p, -nrm, 8, note="cap to body")
        hw.insert(p - nrm * T, -nrm, note="cap to body")
    # rail and clamp inserts in the lid -------------------------------------------------------------------------------
    for s, z in rail_screw_points():
        p = lid_point(s, 0.0, z)
        tools.append(insert_hole(p, g.LID_N, "M3s"))
        hw.insert(p, g.LID_N, "M3s", note="shutter rail")
    for c in clamp_points():
        p = lid_point(c["s"], TL, c["z"])
        tools.append(insert_hole(p, -g.LID_N, "M3s"))
        hw.insert(p, -g.LID_N, "M3s", note="glass clamp")
    cap = cut(cap, *tools)

    # split into four, with half laps in the lid --------------------------------------------------------------------
    xs, zs = g.X_SEAM_CAP, g.Z_SEAM_CAP
    big = 2000.0
    rear = split(cap, bisect_by=Plane(origin=(xs, 0, 0), z_dir=(1, 0, 0)), keep=Keep.BOTTOM)
    front = split(cap, bisect_by=Plane(origin=(xs, 0, 0), z_dir=(1, 0, 0)), keep=Keep.TOP)
    # lap at the x seam (side rims): the rear piece carries the upper half 12 mm forward
    lap_x = common(cap, aabb(xs, xs + LAP_W, 0, big, -big, big), lid_box(-big, big, TL / 2, TL + 1, -big, big))
    rear, front = rear.fuse(lap_x).clean(), front.cut(lap_x).clean()
    pieces = []
    for nm, half in (("Rear", rear), ("Front", front)):
        left = split(half, bisect_by=Plane(origin=(0, 0, zs), z_dir=(0, 0, 1)), keep=Keep.BOTTOM)
        right = split(half, bisect_by=Plane(origin=(0, 0, zs), z_dir=(0, 0, 1)), keep=Keep.TOP)
        lap_z = common(half, aabb(-big, big, 0, big, zs, zs + LAP_W), lid_box(-big, big, TL / 2, TL + 1, -big, big))
        left, right = left.fuse(lap_z).clean(), right.cut(lap_z).clean()
        pieces.append([f"cap{nm}Left", f"Lid, {nm.lower()} left", left])
        pieces.append([f"cap{nm}Right", f"Lid, {nm.lower()} right", right])
    # lap screws: countersunk from the top through the upper lap into M3 x 3 inserts in the lower lap
    lap_pts = []
    for x in (585.0, 625.0, 665.0, 700.0, 985.0):
        lap_pts.append(("z", np.array([x, 0, zs + LAP_W / 2])))
    for sg in (-1, 1):
        lap_pts.append(("x", np.array([xs + LAP_W / 2, 0, sg * 179.0])))
    for kind, p in lap_pts:
        s, _, z = lid_coords([p[0], g.lid_y(p[0]), p[2]])
        top = lid_point(s, TL, z)
        mid = lid_point(s, TL / 2, z)
        for pc in pieces:
            pc[2] = pc[2].cut(csk_hole(top + g.LID_N * 0.01, -g.LID_N, TL / 2 + 0.2))
            pc[2] = pc[2].cut(insert_hole(mid + g.LID_N * 0.01, -g.LID_N, "M3s"))
        hw.screw(top, -g.LID_N, 6, head="csk", note="lid lap")
        hw.insert(mid, -g.LID_N, "M3s", note="lid lap")
    return [tuple(p) for p in pieces]
