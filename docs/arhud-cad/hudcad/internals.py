"""Everything inside the shell that holds an optic or a board, plus the small printed parts on the lid.

Frames used here (all built from layout.json):
  fold    local x = v (up the glass), y = w (along FOLD_N, the reflecting side), z = -u (car -z)
  mirror  local x = u (car z), y = v (up the mirror), z = w (along MIRROR_N, the reflecting side)
  lid     local x = s (along the lid, forward), y = n (lid normal), z = car z; origin at the aperture centre
"""
import math

import numpy as np
from build123d import Vector

from . import geo as g
from . import shell as sh
from .kit import (INSERT, Hardware, Part, aabb, basis_loc, clear_hole, csk_hole, cyl, from_local, insert_hole, lbox,
                  lcyl, lprism, union, cut, xy_prism)

PX, PY, PZ = g.PANEL_C

# ---------------------------------------------------------------------------------------------------------------
# PGU bay: a sealed, ventilated tub under the panel. Everything below the cell lives here: heat sink, fan, HDMI board.
# ---------------------------------------------------------------------------------------------------------------
BAY = dict(x0=g.STEP_X + g.T_WALL + 2.5, x1=732.0, z0=-95.0, z1=95.0, y0=g.FLOOR_TOP, y1=948.0, t=2.5, tf=3.0)
BAY_COL = 9.0                                         # corner columns that take the carrier and fold-bracket screws
BAY_HOLES = [(BAY["x0"] + BAY["t"] + BAY_COL / 2, sg * 88.0) for sg in (-1, 1)] + [(676.0, sg * 88.0) for sg in (-1, 1)]
# The mirror->fold beam passes low beside the panel's front corners (rays at |z| 75-80 come down to y 948 near x 724),
# so in front of BAY_FRONT_CUT and outboard of the cell the bay's walls slope down and the carrier stops.
BAY_FRONT_CUT, CELL_SIDE, BAY_SIDE = 705.0, 62.5, 58.0
BAY_FLOOR_SCREWS = [(662.0, sg * 99.0) for sg in (-1, 1)] + [(722.0, sg * 99.0) for sg in (-1, 1)]
HS_POSTS = [(PX + dx, dz) for dx in (-23.0, 23.0) for dz in (-35.75, 35.75)]   # between the heat sink's outer fins
DUCT = 46.0
# HDMI board (pgu.js hdmiBoard: 46 x 64 mm) stood on edge against the right wall, HDMI receptacle facing the floor
BOARD = dict(cx=PX - 4.0, cy=852.0, z_pcb=81.5, w=64.0, d=46.0, holes=[(dx, dy) for dx in (-22.0, 22.0) for dy in (-19.0, 19.0)])
HDMI_X = PX - 4.0 + 14.0
HDMI_Z = 81.5 - 2.9                    # receptacle centre, on the board's component side


def build_bay(hw):
    b = BAY
    x0, x1, z0, z1, y0, y1, t, tf = b["x0"], b["x1"], b["z0"], b["z1"], b["y0"], b["y1"], b["t"], b["tf"]
    outer = aabb(x0, x1, y0, y1, z0, z1)
    inner = aabb(x0 + t, x1 - t, y0 + tf, y1 + 1, z0 + t, z1 - t)
    tub = outer.cut(inner)
    adds = []
    # corner columns
    for x, z in BAY_HOLES:
        adds.append(aabb(x - BAY_COL / 2, x + BAY_COL / 2, y0 + tf - 0.1, y1, z - BAY_COL / 2, z + BAY_COL / 2))
    # base flanges along the sides
    for sg in (-1, 1):
        adds.append(aabb(x0, x1, y0, y0 + 3.0, *(sorted((sg * 95.0, sg * 104.0)))))
    # heat-sink posts: 8 mm below the fins, 4.6 mm between them, M3 self-tapping from above through the sink base
    for x, z in HS_POSTS:
        adds.append(cyl((x, y0 + tf - 0.1, z), (0, 1, 0), 4.0, g.HS_FIN_BOT - 0.3 - (y0 + tf - 0.1)))
        adds.append(cyl((x, g.HS_FIN_BOT - 0.5, z), (0, 1, 0), 2.3, g.HS_BASE_BOT - (g.HS_FIN_BOT - 0.5)))
    # fan duct from the fan to the floor grille
    d = DUCT / 2
    duct = aabb(PX - d, PX + d, y0 + tf - 0.1, g.FAN_BOT - 0.5, -d, d).cut(aabb(PX - d + 2, PX + d - 2, y0, g.FAN_BOT, -d + 2, d - 2))
    adds.append(duct)
    # HDMI board standoffs on the right wall
    for dx, dy in BOARD["holes"]:
        adds.append(cyl((BOARD["cx"] + dx, BOARD["cy"] + dy, z1 - t + 0.1), (0, 0, -1), 3.0, (z1 - t) - (BOARD["z_pcb"] + 1.6) + 0.1))
    tub = union([tub] + adds)
    tools = []
    # exhaust grille inside the duct, intake slots fore and aft of it
    for i in range(5):
        x = PX - 16 + i * 8
        tools.append(aabb(x - 1.5, x + 1.5, y0 - 1, y0 + tf + 1, -17, 17))
    for xc in (x0 + t + 14.0, x1 - t - 6.0):
        for zc in np.linspace(-68, 68, 7):
            tools.append(aabb(xc - 1.5, xc + 1.5, y0 - 1, y0 + tf + 1, zc - 7, zc + 7))
    # cable slots: HDMI plug straight down at the board's lower edge; LED and fan leads; thermistor lead through the wall
    tools.append(aabb(HDMI_X - 12, HDMI_X + 12, y0 - 1, y0 + tf + 1, HDMI_Z - 7.0, HDMI_Z + 7.0))
    tools.append(cyl((PX + 10, y0 - 1, -70.0), (0, 1, 0), 4.0, tf + 2))
    tools.append(cyl((700.0, 900.0, z0 - 1), (0, 0, 1), 2.0, t + 2))
    # fixings
    for x, z in BAY_HOLES:
        tools.append(insert_hole((x, y1 + 0.01, z), (0, -1, 0), "M3"))
        hw.insert((x, y1, z), (0, -1, 0), note="bay top")
    for x, z in BAY_FLOOR_SCREWS:
        tools.append(clear_hole((x, y0 + 3.1, z), (0, -1, 0), 3.3))
        hw.screw((x, y0 + 3.0, z), (0, -1, 0), 8, note="bay to floor")
    for x, z in HS_POSTS:
        tools.append(cyl((x, g.HS_BASE_BOT + 0.01, z), (0, -1, 0), 1.25, 12.0))
        hw.screw((x, g.HS_BASE_TOP, z), (0, -1, 0), 10, note="heat sink to posts (self-tapping)")
    for dx, dy in BOARD["holes"]:
        tools.append(cyl((BOARD["cx"] + dx, BOARD["cy"] + dy, BOARD["z_pcb"] + 1.5), (0, 0, 1), 1.1, 6.0))
        hw.screw((BOARD["cx"] + dx, BOARD["cy"] + dy, BOARD["z_pcb"]), (0, 0, 1), 6, size="M3", note="HDMI board (M2.5 self-tapping)")
    tub = cut(tub, *tools)
    ch = 8.0
    tub = tub.cut(xy_prism([(x1 - ch, y1 + 1), (x1 + 1, y1 + 1), (x1 + 1, y1 - ch - 1)], z0 - 20, z1 + 20))
    wedge = [(BAY_FRONT_CUT, y1 + 1), (x1 + 1, y1 + 1), (x1 + 1, y1 - 1.1 * (x1 + 1 - BAY_FRONT_CUT))]
    for sg in (-1, 1):
        za, zb = (BAY_SIDE, z1 + 20) if sg > 0 else (z0 - 20, -BAY_SIDE)
        tub = tub.cut(xy_prism(wedge, za, zb))
    return tub


# ---------------------------------------------------------------------------------------------------------------
# Panel carrier (holds the cell by its edges at the traced height) and the mask that clamps it.
# ---------------------------------------------------------------------------------------------------------------
CELL_BOT = PY - 1.5                    # pgu.js: rear polariser 1.5 mm below the front surface
CARRIER_Y0, CARRIER_Y1 = BAY["y1"], PY + 0.07
CELL_X0 = PX - g.PANEL_OUT_X / 2 - g.TFT_LEDGE - 0.3
CELL_X1 = PX + g.PANEL_OUT_X / 2 + 0.3
CELL_Z = g.PANEL_OUT_Z / 2 + 0.3
MASK_T = 2.0
MASK_SCREWS = [(CELL_X0 - 2.6, sg * 67.5) for sg in (-1, 1)] + [(698.0, sg * 67.5) for sg in (-1, 1)]


def ray_box_on_panel(margin=3.0):
    lo, hi = np.full(3, 1e9), np.full(3, -1e9)
    for mode in ("toroid", "sphere"):
        P = g.rays(mode)[:, 4]
        lo, hi = np.minimum(lo, P.min(0)), np.maximum(hi, P.max(0))
    return lo - margin, hi + margin


def build_carrier(hw):
    x0, x1, z0, z1 = BAY["x0"], BAY["x1"], BAY["z0"], BAY["z1"]
    c = aabb(x0, x1, CARRIER_Y0, CARRIER_Y1, z0, z1)
    tools = [aabb(PX - 22, PX + 22, CARRIER_Y0 - 1, CARRIER_Y1 + 1, -37, 37),            # backlight stack
             aabb(CELL_X0, CELL_X1, CELL_BOT, CARRIER_Y1 + 1, -CELL_Z, CELL_Z),           # cell pocket
             aabb(CELL_X0 - 3.5, CELL_X0 + 0.1, CARRIER_Y0 - 1, CARRIER_Y1 + 1, -20, 4),  # flex slot at the TFT ledge
             aabb(CELL_X1 - 0.01, BAY["x1"] + 1, CELL_BOT, CARRIER_Y1 + 1, BAY["z0"] - 1, BAY["z1"] + 1),
             xy_prism([(CELL_X1 + 0.5, CELL_BOT + 0.01), (BAY["x1"] + 1, CELL_BOT + 0.01), (BAY["x1"] + 1, CELL_BOT - 3.5)],
                      BAY["z0"] - 1, BAY["z1"] + 1),
             aabb(BAY_FRONT_CUT - 1, BAY["x1"] + 1, CARRIER_Y0 - 1, CARRIER_Y1 + 1, CELL_SIDE + 2, BAY["z1"] + 1),
             aabb(BAY_FRONT_CUT - 1, BAY["x1"] + 1, CARRIER_Y0 - 1, CARRIER_Y1 + 1, BAY["z0"] - 1, -CELL_SIDE - 2)]
    for x, z in BAY_HOLES:
        tools.append(clear_hole((x, CARRIER_Y1 + 0.01, z), (0, -1, 0), CARRIER_Y1 - CARRIER_Y0 + 0.1))
    for x, z in MASK_SCREWS:
        tools.append(insert_hole((x, CARRIER_Y1 + 0.01, z), (0, -1, 0), "M3"))
        hw.insert((x, CARRIER_Y1, z), (0, -1, 0), note="mask")
    return cut(c, *tools)


def build_mask(hw):
    lo, hi = ray_box_on_panel(3.0)
    m = aabb(CELL_X0 - 5.5, CELL_X1 + 1.0, CARRIER_Y1, CARRIER_Y1 + MASK_T, -70, 70)
    tools = [aabb(lo[0], hi[0], CARRIER_Y1 - 1, CARRIER_Y1 + MASK_T + 1, lo[2], hi[2])]
    for x, z in MASK_SCREWS:
        tools.append(clear_hole((x, CARRIER_Y1 + MASK_T + 0.01, z), (0, -1, 0), MASK_T + 0.2))
        hw.screw((x, CARRIER_Y1 + MASK_T, z), (0, -1, 0), 6, note="mask")
    return cut(m, *tools)


# ---------------------------------------------------------------------------------------------------------------
# Fold bracket: holds the cold mirror at the traced angle, 50 mm over the panel, and carries the IR absorber.
# Its cheeks stand on the carrier and share the bay's corner screws, so panel and fold are one rigid module.
# ---------------------------------------------------------------------------------------------------------------
FOLD_LOC = basis_loc(g.FOLD_C, g.FOLD_V, g.FOLD_N)       # local (v, w, -u)
GU = (g.FOLD_U1 - g.FOLD_U0) / 2                          # glass half width (u)
FV0, FV1 = g.FOLD_V0, g.FOLD_V1
CHEEK = (79.0, 85.0)


def fb(v0, v1, w0, w1, u0, u1):
    return lbox(FOLD_LOC, v0, v1, w0, w1, -u1, -u0)


def fold_xy(v, w):
    p = g.FOLD_C + g.FOLD_V * v + g.FOLD_N * w
    return float(p[0]), float(p[1])


def build_fold_bracket(hw):
    parts = []
    rail_u0, rail_u1 = GU - 2.0, GU + 6.4
    v_lo, v_top = FV0 - 6.0, FV1 - 6.0
    for sg in (-1, 1):
        u0, u1 = (rail_u0, rail_u1) if sg > 0 else (-rail_u1, -rail_u0)
        parts.append(fb(v_lo, v_top, -14.0, 2.0, u0, u1))                         # side rail
        a0, a1 = (67.2, rail_u0 + 0.1) if sg > 0 else (-rail_u0 - 0.1, -67.2)
        for v in (-30.0, 15.0):
            parts.append(fb(v - 5, v + 5, -14.0, -11.5, a0, a1))                   # absorber tabs
    parts.append(fb(v_lo, FV0 + 2.0, -8.0, 2.0, -rail_u1, rail_u1))                # bottom rail, clear of the absorber
    # cheeks: side plates from the rails down to the carrier
    cx = [fold_xy(v_lo, 2.0), fold_xy(v_lo, -14.0), fold_xy(v_top, -14.0), fold_xy(v_top, 2.0)]
    foot_y = CARRIER_Y1 + MASK_T * 0 + 0.0
    xa, xb = BAY["x0"] + 0.5, BAY_FRONT_CUT - 1.5
    poly = [(xa, foot_y), (xb, foot_y), cx[3], cx[2], cx[1]]
    if cx[1][0] > xa:
        poly.append((xa, cx[1][1]))
    for sg in (-1, 1):
        z0, z1 = (CHEEK[0], CHEEK[1]) if sg > 0 else (-CHEEK[1], -CHEEK[0])
        parts.append(xy_prism(poly, z0, z1))
        f0, f1 = (CHEEK[0], BAY["z1"]) if sg > 0 else (BAY["z0"], -CHEEK[0])
        parts.append(aabb(xa, xb, foot_y, foot_y + 4.0, f0, f1))                  # foot flange
    br = union(parts)
    tools = [fb(FV0 - 0.4, FV1 + 20, -3.2, 0.2, -GU - 0.6, GU + 0.6)]                # glass slot
    tools.append(fb(FV0 + 2.0, FV1 + 20, 0.19, 30.0, -GU + 2.0, GU - 2.0))          # clear face (lips stay 2 mm)
    tools.append(fb(FV0 - 30, FV1 + 30, -11.5, -2.0, -66.8, 66.8))                  # absorber pocket behind the glass
    for x, z in BAY_HOLES:
        tools.append(clear_hole((x, foot_y + 4.1, z), (0, -1, 0), 4.3))
        hw.screw((x, foot_y + 4.0, z), (0, -1, 0), 16, note="fold bracket and carrier to bay")
    for sg in (-1, 1):
        for v in (-30.0, 15.0):
            u = sg * 69.5
            p = from_local(g.FOLD_C, g.FOLD_V, g.FOLD_N, (v, -8.5, -u))
            tools.append(cyl(from_local(g.FOLD_C, g.FOLD_V, g.FOLD_N, (v, -15, -u)), g.FOLD_N, 1.7, 8))
            hw.screw(p, -g.FOLD_N, 8, note="absorber to bracket (with nut)")
    return cut(br, *tools)


# ---------------------------------------------------------------------------------------------------------------
# Mirror mount: bonded strongback on three bed-levelling adjusters, a stand on the floor, two edge clips.
# ---------------------------------------------------------------------------------------------------------------
MIR_LOC = basis_loc(g.MIRROR_C, g.MIRROR_U, g.MIRROR_V)  # local (u, v, w)
SB = dict(u=120.0, v=75.0, w0=-19.0, w1=-13.0, rib=-27.0)
ADJ = [(-95.0, -55.0), (95.0, -55.0), (0.0, 60.0)]
STAND_W = (-47.0, -39.0)
LEG_U = 118.0
STAND_FEET = [(dx, sg * LEG_U) for sg in (-1, 1) for dx in (-12.0, 12.0)]   # relative to the leg's x


def mloc(u, v, w):
    return from_local(g.MIRROR_C, g.MIRROR_U, g.MIRROR_V, (u, v, w))


def mb(u0, u1, v0, v1, w0, w1):
    return lbox(MIR_LOC, u0, u1, v0, v1, w0, w1)


def build_strongback(hw):
    u, v = SB["u"], SB["v"]
    parts = [mb(-u, u, -v, v, SB["w0"], SB["w1"])]
    for vv in (-55.0, 0.0, 55.0):
        parts.append(mb(-u + 3, u - 3, vv - 1.5, vv + 1.5, SB["rib"], SB["w0"] + 0.1))
    for uu in (-95.0, -40.0, 0.0, 40.0, 95.0):
        parts.append(mb(uu - 1.5, uu + 1.5, -v + 3, v - 3, SB["rib"], SB["w0"] + 0.1))
    for a in ADJ:
        parts.append(lcyl(MIR_LOC, (a[0], a[1], SB["rib"]), (0, 0, 1), 7.0, SB["w1"] - SB["rib"]))
    s = union(parts)
    tools = []
    for a in ADJ:
        tools.append(lcyl(MIR_LOC, (a[0], a[1], SB["rib"] - 0.01), (0, 0, 1), INSERT["M4"]["hole"] / 2, INSERT["M4"]["depth"]))
        hw.insert(mloc(a[0], a[1], SB["rib"]), g.MIRROR_N, "M4", note="mirror adjuster")
    for uu in (-80.0, 80.0):
        tools.append(lcyl(MIR_LOC, (uu, -68.0, SB["w0"] - 0.01), (0, 0, 1), 2.0, 6.0))
        hw.insert(mloc(uu, -68.0, SB["w0"]), g.MIRROR_N, note="mirror clip")
    # three RTV pads between the strongback and the mirror's back (bought: 1 mm silicone)
    for a in ADJ:
        hw.add("bought", "RTV silicone bonding pad, 25 mm x 1 mm",
               lcyl(MIR_LOC, (a[0] * 0.9, a[1] * 0.9, SB["w1"]), (0, 0, 1), 12.5, 1.0), "mirror bond")
    return cut(s, *tools)


def build_stand(hw):
    w0, w1 = STAND_W
    parts = []
    for a in ADJ:
        parts.append(lcyl(MIR_LOC, (a[0], a[1], w0), (0, 0, 1), 7.5, w1 - w0))
    # triangle of bars between the three bosses
    def bar(p, q, width=10.0):
        p, q = np.array(p, float), np.array(q, float)
        d = q - p
        n = np.array([-d[1], d[0]]) / np.linalg.norm(d) * width / 2
        pts = [tuple(p + n), tuple(q + n), tuple(q - n), tuple(p - n)]
        return lprism(MIR_LOC, pts, w0, w1)
    A, B, C = ADJ
    parts += [bar(A, B), bar(A, C), bar(B, C)]
    # bottom bar runs out to the legs; legs stand beside the bosses so the adjuster heads stay reachable
    parts.append(bar((-LEG_U, A[1]), (LEG_U, B[1]), 10.0))
    feet = []
    for sg in (-1, 1):
        top = mloc(sg * LEG_U, A[1], (w0 + w1) / 2)
        x, y = top[0], top[1]
        parts.append(aabb(x - 7, x + 7, g.FLOOR_TOP, y + 4, sg * LEG_U - 6, sg * LEG_U + 6))
        parts.append(aabb(x - 18, x + 18, g.FLOOR_TOP, g.FLOOR_TOP + 4, sg * LEG_U - 9, sg * LEG_U + 9))
        for dx in (-12.0, 12.0):
            feet.append((x + dx, sg * LEG_U))
    s = union(parts)
    tools = []
    for a in ADJ:
        tools.append(lcyl(MIR_LOC, (a[0], a[1], w0 - 1), (0, 0, 1), 2.25, w1 - w0 + 2))
        head = mloc(a[0], a[1], w0)
        hw.screw(head, g.MIRROR_N, 30, size="M4", head="socket", note="mirror adjuster")
        hw.add("spring", "compression spring 9 x 15 mm, music wire",
               lcyl(MIR_LOC, (a[0], a[1], w1), (0, 0, 1), 4.5, SB["rib"] - w1).cut(
                   lcyl(MIR_LOC, (a[0], a[1], w1 - 1), (0, 0, 1), 3.6, SB["rib"] - w1 + 2)), "mirror adjuster")
    for x, z in feet:
        tools.append(clear_hole((x, g.FLOOR_TOP + 4.1, z), (0, -1, 0), 4.3))
        hw.screw((x, g.FLOOR_TOP + 4.0, z), (0, -1, 0), 8, note="mirror stand to floor")
    return cut(s, *tools), feet


def adjuster_access():
    """Lines from each adjuster head to the front wall: C on its axis, A and B 25 degrees up (ball-end key)."""
    out = []
    for i, a in enumerate(ADJ):
        head = mloc(a[0], a[1], STAND_W[0] - 4.0)
        d = -g.MIRROR_N.copy()
        if i < 2:
            ang = math.atan2(d[1], d[0]) + math.radians(25.0)
            d = np.array([math.cos(ang), math.sin(ang), 0.0])
        out.append((head, d))
    return out


def build_clips(hw):
    out = []
    for uc in (-80.0, 80.0):
        u0, u1 = uc - 8, uc + 8
        sag = max(u * u / (2 * g.MIRROR_RS["toroid"]) + (g.MIRROR_H / 2) ** 2 / (2 * g.MIRROR_RT["toroid"]) for u in (u0, u1))
        vb = -g.MIRROR_H / 2
        parts = [mb(u0, u1, vb - 4, -60.0, SB["w0"] - 3, SB["w0"]),                # back leg on the strongback
                 mb(u0, u1, vb - 4, vb - 0.3, SB["w0"] - 3, sag + 2.8),              # under the edge
                 mb(u0, u1, vb - 4, vb + 2.5, sag + 0.3, sag + 2.8)]                 # lip on the face, 2.5 mm
        c = union(parts)
        c = c.cut(lcyl(MIR_LOC, (uc, -68.0, SB["w0"] - 3.1), (0, 0, 1), 1.7, 3.3))
        hw.screw(mloc(uc, -68.0, SB["w0"] - 3.0), g.MIRROR_N, 8, note="mirror clip")
        out.append(c)
    return out


# ---------------------------------------------------------------------------------------------------------------
# Shutter rails, servo bracket, spring anchor (under the lid), glass clamps and the light-sensor pod (on top)
# ---------------------------------------------------------------------------------------------------------------
RAIL_N = (-8.5, 0.0)
SLOT_REAR = (-5.5, -4.1)               # rear leaf (simulator: -4.8 mm under the lid)
SLOT_FRONT = (-7.5, -6.1)              # front leaf (-6.8 mm)
SLOT_Z = sh.SLOT_Z
SC, SL, SW = sh.AP_SC, sh.AP_LEN, sh.AP_WID    # the shutter's frame: aperture centre, length, width (as the sim builds it)
RAIL_S = (SC - SL - 10.0, -40.0, SC + SL / 2 + 9.0)   # rear stop, joint, front stop (lid coordinates)
LEAF_W = 2 * (SLOT_Z - 0.8)


def build_rails(hw):
    zin = sh.RAIL_Z_IN
    out = []
    for sg, zout in ((-1, SLOT_Z + 10.0), (1, SLOT_Z + 14.0)):
        for i, (s0, s1) in enumerate(((RAIL_S[0], RAIL_S[1]), (RAIL_S[1], RAIL_S[2]))):
            z0, z1 = (zin, zout) if sg > 0 else (-zout, -zin)
            r = sh.lid_box(s0, s1, RAIL_N[0], RAIL_N[1], z0, z1)
            sa = s0 + (2.0 if i == 0 else 0.0)
            sb = s1 - (1.0 if i == 1 else 0.0)
            sz0, sz1 = (zin - 1, SLOT_Z) if sg > 0 else (-SLOT_Z, -zin + 1)
            for n0, n1 in (SLOT_REAR, SLOT_FRONT):
                r = r.cut(sh.lid_box(sa, sb, n0, n1, sz0, sz1))
            for s in sh.RAIL_SCREW_S:
                if s0 + 4 < s < s1 - 4:
                    p = sh.lid_point(s, RAIL_N[0], sg * sh.RAIL_SCREW_Z)
                    r = r.cut(cyl(p - g.LID_N * 0.01, g.LID_N, 1.7, 9.0)).cut(cyl(p - g.LID_N * 0.01, g.LID_N, 3.1, 2.0))
                    hw.screw(p + g.LID_N * 0.0, g.LID_N, 10, note="shutter rail")
            if sg > 0 and i == 0:                                             # inserts for the servo bracket
                for s in SERVO_POSTS:
                    p = sh.lid_point(s, RAIL_N[0], SERVO_POST_Z)
                    r = r.cut(insert_hole(p - g.LID_N * 0.01, g.LID_N, "M3"))
                    hw.insert(p, g.LID_N, note="servo bracket")
            out.append(((("Left", "Right")[sg > 0], ("rear", "front")[i]), r))
    return out


def servo_geometry():
    """The servo as the simulator places it (optics.js buildShutter): pivot 2 mm inside the aperture's right edge so
    the Scotch-yoke pin stays on the front leaf at both ends of travel, lever under the leaves, body to the rear."""
    pivot_s = SC - SL / 2 + 3.5
    pivot_z = SW / 2 - 2.0
    plane_n = -6.0                       # shutter plane under the lid
    return dict(pivot_s=pivot_s, pivot_z=pivot_z, body_s=pivot_s - 6.0, body_n=plane_n - 23.5, body=(22.5, 22.7, 12.2),
                tab_n=plane_n - 15.5, tab=(32.0, 2.5, 12.2), shaft_n=(plane_n - 12.0, plane_n - 5.0),
                horn_n=plane_n - 4.0)


SG = servo_geometry()
SERVO_POSTS = (SG["body_s"] - 20.0, SG["body_s"] + 20.0)
SERVO_POST_Z = SLOT_Z + 9.5


def build_servo_bracket(hw):
    s0, s1 = SG["body_s"] - 24.0, SG["body_s"] + 24.0
    tab_bot = SG["tab_n"] - SG["tab"][1] / 2
    zb0, zb1 = SG["pivot_z"] - SG["body"][2] / 2 - 0.3, SG["pivot_z"] + SG["body"][2] / 2 + 0.3
    shelf = sh.lid_box(s0, s1, tab_bot - 3.0, tab_bot, zb0 - 3.0, SLOT_Z + 13.0)
    shelf = shelf.cut(sh.lid_box(SG["body_s"] - SG["body"][0] / 2 - 0.4, SG["body_s"] + SG["body"][0] / 2 + 0.4,
                                 tab_bot - 4, tab_bot + 1, zb0, zb1))
    posts = [sh.lid_box(s - 4, s + 4, tab_bot - 3.0, RAIL_N[0], SLOT_Z + 6.0, SLOT_Z + 13.0) for s in SERVO_POSTS]
    b = union([shelf] + posts)
    for s in SERVO_POSTS:
        p = sh.lid_point(s, tab_bot - 3.0, SERVO_POST_Z)
        b = b.cut(cyl(p - g.LID_N * 0.01, g.LID_N, 1.7, 30)).cut(cyl(p - g.LID_N * 0.01, g.LID_N, 3.1, 2.0))
        hw.screw(p, g.LID_N, 20, note="servo bracket")
    for ds in (-13.8, 13.8):                                                   # SG90 tab holes
        p = sh.lid_point(SG["body_s"] + ds, tab_bot - 3.01, SG["pivot_z"])
        b = b.cut(cyl(p, g.LID_N, 0.9, 4.0))
        hw.screw(sh.lid_point(SG["body_s"] + ds, SG["tab_n"] + SG["tab"][1] / 2, SG["pivot_z"]), -g.LID_N, 8, note="servo tabs (M2 self-tapping)")
    return b


def build_spring_anchor(hw):
    s, z = SC + SL / 2 + 18.0, -(SW / 2 - 6.0)              # the spring's anchor block in optics.js
    a = sh.lid_box(s - 4, s + 4, -5.5, 0.0, z - 4, z + 4)
    p = sh.lid_point(s, -5.5, z)
    a = a.cut(cyl(p - g.LID_N * 0.01, g.LID_N, 1.7, 6.0)).cut(cyl(p - g.LID_N * 0.01, g.LID_N, 3.1, 2.0))
    hw.screw(p, g.LID_N, 8, note="spring anchor")
    hw.insert(sh.lid_point(s, 0.0, z), g.LID_N, "M3s", note="spring anchor")
    return a, (s, z)


def build_clamps(hw):
    out = []
    gr = sh.glass_rect()
    for c in sh.clamp_points():
        ds, dz = c["dir"]
        # clamp plate from 6 mm outside the screw to 4 mm over the glass edge
        if ds == 0:
            z_edge = gr["z1"] if dz > 0 else gr["z0"]
            za, zb = sorted((c["z"] + dz * 6.0, z_edge - dz * 4.0))
            box = sh.lid_box(c["s"] - 8, c["s"] + 8, sh.TL, sh.TL + 2.5, za, zb)
        else:
            sa, sb = sorted((c["s"] + ds * 6.0, gr["s1"] - ds * 4.0))
            box = sh.lid_box(sa, sb, sh.TL, sh.TL + 2.5, c["z"] - 8, c["z"] + 8)
        p = sh.lid_point(c["s"], sh.TL + 2.5, c["z"])
        box = box.cut(cyl(p + g.LID_N * 0.01, -g.LID_N, 1.7, 3.0))
        hw.screw(p, -g.LID_N, 6, note="glass clamp")
        out.append(box)
    return out


def build_als_pod(hw):
    s0, s1 = sh.AP["s0"] - 44.0, sh.AP["s0"] - 14.0
    z0, z1 = -181.0, -153.0
    pod = sh.lid_box(s0, s1, sh.TL, sh.TL + 11.0, z0, z1).cut(sh.lid_box(s0 + 2, s1 - 2, sh.TL - 1, sh.TL + 9.0, z0 + 2, z1 - 2))
    win = sh.lid_point((s0 + s1) / 2, sh.TL + 9.0, (z0 + z1) / 2)
    pod = pod.cut(cyl(win - g.LID_N * 1, g.LID_N, 3.0, 4.0))
    return pod


def pod_wire_hole():
    return sh.lid_point(sh.AP["s0"] - 29.0, 0.0, -179.5)


# ---------------------------------------------------------------------------------------------------------------
# Light-trap vanes, grommets, access plugs, feet
# ---------------------------------------------------------------------------------------------------------------
def build_vanes():
    out = []
    x0, x1, y0, y1 = 806.0, 1012.0, g.FLOOR_TOP + 10.0, 935.0
    zi = g.ZW - g.T_WALL
    pitch, depth = 6.0, 5.0
    for sg in (-1, 1):
        # sawtooth in the (y, z) plane: each tooth slopes down toward the wall so sunlight is trapped
        pts = []
        y = y0
        pts.append((y0, 0.0))
        pts = [(y0, 0.0)]
        while y + pitch <= y1:
            pts += [(y + pitch * 0.15, depth), (y + pitch, 0.0)]
            y += pitch
        pts = [(py, d + 1.5) for py, d in pts] + [(y, 0.0), (y0, 0.0)]
        # build as an extrusion along x of the profile (local: X = y, Y = depth inward), then place
        from build123d import Face, Wire, Vector, extrude, Location
        w = Wire.make_polygon([Vector(py, d, 0) for py, d in pts], close=True)
        prof = extrude(Face(w), amount=x1 - x0, dir=(0, 0, 1))
        # local X -> car y, local Y -> inward (-sg z), local Z -> car x
        loc = basis_loc((x0 if sg < 0 else x1, 0.0, sg * zi), (0, 1, 0), (0, 0, -sg))
        v = prof.moved(loc)
        out.append(v)
    return out


def build_grommets():
    out = {}
    # left wall: servo, light sensor and thermistor leads
    p = np.array([760.0, 848.0, -g.ZW])
    gr = cyl(p + np.array([0, 0, -1.5]), (0, 0, 1), 10.0, 1.5).fuse(cyl(p, (0, 0, 1), 6.9, g.T_WALL)).fuse(
        cyl(p + np.array([0, 0, g.T_WALL]), (0, 0, 1), 10.0, 1.5))
    gr = gr.cut(cyl(p + np.array([0, 0, -2]), (0, 0, 1), 3.0, 8.0)).cut(aabb(p[0] - 0.4, p[0] + 0.4, p[1], p[1] + 12, p[2] - 3, p[2] + 6))
    out["grommetWall"] = gr
    # bay floor: HDMI right-angle plug passes down here
    y0 = BAY["y0"]
    hz = HDMI_Z
    g2 = aabb(HDMI_X - 11.8, HDMI_X + 11.8, y0, y0 + BAY["tf"], hz - 6.8, hz + 6.8).fuse(
        aabb(HDMI_X - 13, HDMI_X + 13, y0 + BAY["tf"], y0 + BAY["tf"] + 1.5, hz - 9.0, BAY["z1"] - BAY["t"] - 0.2))
    g2 = g2.cut(cyl((HDMI_X, y0 - 1, hz), (0, 1, 0), 3.8, 8.0)).cut(aabb(HDMI_X - 0.4, HDMI_X + 0.4, y0 - 1, y0 + 6, hz, hz + 12))
    out["grommetHdmi"] = g2
    # LED and fan leads
    q = np.array([PX + 10, y0, -70.0])
    g3 = cyl(q, (0, 1, 0), 3.9, BAY["tf"]).fuse(cyl(q + np.array([0, BAY["tf"], 0]), (0, 1, 0), 6.0, 1.5))
    g3 = g3.cut(cyl(q - np.array([0, 1, 0]), (0, 1, 0), 1.8, 8.0))
    out["grommetLed"] = g3
    return out


def build_plugs(access):
    out = []
    for k, (head, d) in enumerate(access):
        r = (5.0 if k < 2 else 4.0) - 0.15
        # where the line crosses the front wall's outer face
        t = (g.XF - head[0]) / d[0]
        p = head + d * t
        plug = cyl(p - d * g.T_WALL / d[0], d, r, g.T_WALL / d[0] + 0.0).fuse(cyl(p, (1, 0, 0), r / abs(d[0]) + 1.6, 1.2))
        out.append((p, d, plug))
    return out


def build_feet(hw):
    out = []
    for x, z in FEET:
        f = cyl((x, g.DASH_Y, z), (0, 1, 0), 10.0, 4.0).fuse(cyl((x, g.DASH_Y + 4, z), (0, 1, 0), 6.0, 5.0)).fuse(
            cyl((x, g.DASH_Y + 9, z), (0, 1, 0), 2.4, g.FOOT_H - 9 + 9.0))
        out.append(f)
        hw.insert((x, g.FLOOR_BOT, z), (0, 1, 0), "M5", note="foot")
    return out


FEET = [(668.0, -150.0), (668.0, 150.0), (1000.0, -150.0), (1000.0, 150.0)]


# ---------------------------------------------------------------------------------------------------------------
class Keepouts:
    """Regions the body's seam strips must avoid, and where the floor needs insert bosses."""

    def __init__(self, solid, mount_points, bay):
        self.solid, self.mount_points, self.bay = solid, mount_points, bay

    def contains(self, p, margin=0.0):
        bb = self.solid.bounding_box()
        for s in self.solid.solids():
            b = s.bounding_box()
            if (b.min.X - margin <= p[0] <= b.max.X + margin and b.min.Y - margin <= p[1] <= b.max.Y + margin
                    and b.min.Z - margin <= p[2] <= b.max.Z + margin):
                return True
        return False
