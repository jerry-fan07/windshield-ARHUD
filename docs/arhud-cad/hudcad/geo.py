"""The installed layout in millimetres, read from layout.json (dumped from the simulator's geom.js and optics.js).

Frame: X forward, Y up, Z right (toward the car's centreline), origin on the road under the driver's nominal eye.
This is the simulator's frame scaled to millimetres, so every solid here drops into the simulation unchanged.

Everything the housing has to clear or hold comes from this file: the lid plane the shutter runs under, the traced
aperture, the fold and mirror frames, the panel, the windshield line, and the dash and cluster hood of the simulator's
car. The design choices this CAD adds on top of the layout are the constants in the second half.
"""
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
LAYOUT = json.loads((ROOT / "layout.json").read_text())


def mm(v):
    return np.array(v, dtype=float) * 1000.0


def unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


_lay = LAYOUT["layout"]

# ---- housing envelope from optics.housingLayout() -------------------------------------------------------------
XR = _lay["xR"] * 1000            # rear face of the housing (the shutter garage sets it)
XF = _lay["xF"] * 1000            # front face, just ahead of the mirror's top back corner
ZW = _lay["zW"] * 1000            # half width, outside
YF = _lay["yF"] * 1000            # lid underside at the front face
S = _lay["s"]                     # lid slope (rise per mm rearward)
LID_DIR = unit(_lay["lidDir"])    # along the lid, toward the front
LID_N = unit(_lay["lidN"])        # lid normal, up and slightly forward
AX0, AX1 = _lay["ax0"] * 1000, _lay["ax1"] * 1000   # traced aperture, fore-aft extent where it crosses the lid
AZ0, AZ1 = _lay["az0"] * 1000, _lay["az1"] * 1000   # traced aperture, lateral extent
AP_L, AP_W = _lay["L"] * 1000, _lay["W"] * 1000     # aperture length along the lid, width
AP_C = mm(_lay["apC"])            # aperture centre on the lid underside plane
X_GARAGE = _lay["xGarage"] * 1000


def lid_y(x):
    """Height of the lid underside (the plane the shutter leaves run under) at fore-aft x."""
    return YF + S * (XF - x)


# ---- windshield --------------------------------------------------------------------------------------------------
GLASS_G = mm(LAYOUT["glass"]["G"])
RAKE = math.radians(LAYOUT["glass"]["rakeDeg"])


def glass_y(x):
    """Height of the windshield's inner surface at fore-aft x (the plane the simulator traces)."""
    return GLASS_G[1] - (x - GLASS_G[0]) * math.tan(RAKE)


# ---- optics --------------------------------------------------------------------------------------------------------
_m = LAYOUT["mirror"]
MIRROR_C, MIRROR_N, MIRROR_U, MIRROR_V = mm(_m["C"]), unit(_m["N"]), unit(_m["U"]), unit(_m["V"])
MIRROR_W, MIRROR_H, MIRROR_BACK = _m["W"] * 1000, _m["H"] * 1000, _m["back"] * 1000
MIRROR_RT = {k: _m[k]["Rt"] * 1000 for k in ("toroid", "sphere")}
MIRROR_RS = {k: _m[k]["Rs"] * 1000 for k in ("toroid", "sphere")}

_f = LAYOUT["fold"]
FOLD_C, FOLD_N, FOLD_U, FOLD_V = mm(_f["C"]), unit(_f["N"]), unit(_f["fu"]), unit(_f["fv"])
FOLD_U0, FOLD_U1, FOLD_V0, FOLD_V1 = (_f[k] * 1000 for k in ("u0", "u1", "v0", "v1"))
FOLD_T = _f["thick"] * 1000

_p = LAYOUT["panel"]
PANEL_C = mm(_p["C"])             # centre of the crop on the front-polariser surface
PANEL_OUT_X, PANEL_OUT_Z = _p["outX"] * 1000, _p["outZ"] * 1000     # cell glass outline 73.5 x 125.5
TFT_LEDGE = 4.0                   # pgu.js: the TFT glass is 4 mm longer on the rear (-X) edge (driver chip, FPC bond)
CELL_T = 1.7                      # cell stack below the front surface (pgu.js cellLayers: -1.5 rear polariser)

# The backlight stack under the cell, from pgu.js (BL, relative to the panel surface; the backlight sits 2 mm down)
BL_TOP = PANEL_C[1] - 2.0
HS_W_X, HS_W_Z = 50.0, 80.0       # heat-sink base
HS_BASE_TOP, HS_BASE_BOT = BL_TOP - 28.5, BL_TOP - 32.5
HS_FIN_BOT = BL_TOP - 48.5
FAN = 40.0
FAN_BOT = BL_TOP - 58.5
FAN_SCREW = 16.0                  # fan screw holes at +-16 mm


def mirror_point(u, v, mode="toroid"):
    """Point on the mirror's reflecting surface (biconic sag, as geom.js traces it), car frame mm."""
    rt, rs = MIRROR_RT[mode], MIRROR_RS[mode]
    w = u * u / (2 * rs) + v * v / (2 * rt)
    return MIRROR_C + MIRROR_U * u + MIRROR_V * v + MIRROR_N * w


def mirror_back(u, v):
    """Point on the substrate's flat back (12 mm behind the vertex)."""
    return MIRROR_C + MIRROR_U * u + MIRROR_V * v - MIRROR_N * MIRROR_BACK


def fold_point(u, v, w=0.0):
    return FOLD_C + FOLD_U * u + FOLD_V * v + FOLD_N * w


def rays(mode="toroid", inside_only=True):
    """Sampled rays eye -> glass -> mirror -> fold -> panel as an (n, 5, 3) array in mm."""
    rs = [r for r in LAYOUT["rays"][mode] if (r["inside"] or not inside_only)]
    return np.array([r["pts"] for r in rs]) * 1000.0


# ---- the simulator's car (car.js): what the housing stands on and must clear -----------------------------------
DASH_Y = 795.0                    # flat dash shelf from x 660 to 1405
HOOD_X1, HOOD_TOP, HOOD_Z = 635.0, 957.0, 210.0   # instrument-cluster hood: front face at x <= 635, top <= 957

# ---- design choices of this CAD ---------------------------------------------------------------------------------
BED = (250.0, 250.0, 250.0)       # printer build volume every printed piece must fit (Bambu X1/P1 class is 256)
MATERIAL = "ASA, matte black"     # dash tops pass 80 C in summer sun; PETG softens near 75 C, ASA holds about 95 C
T_WALL = 3.0                      # walls
T_FLOOR = 4.0                     # floor
T_LID = 6.0                       # lid: thick enough for a flush glass rebate and M3 x 3 inserts from below
FOOT_H = 14.0                     # dash to floor underside: room for the fan's exhaust and intake under the floor
FLOOR_BOT = DASH_Y + FOOT_H       # 809
FLOOR_TOP = FLOOR_BOT + T_FLOOR
HOOD_CLEAR = 5.0
STEP_X = HOOD_X1 + HOOD_CLEAR     # 640: the floor steps up here; the rear of the housing rides over the cluster hood
OVER_BOT = HOOD_TOP + HOOD_CLEAR  # 962: underside of the rear overhang
GLASS_CLEAR = 8.0                 # nose facet stays this far under the windshield
SKIRT = 50.0                      # cap skirt depth below the lid underside: the body/cap joint line
X_SEAM = 796.0                    # body front/rear seam, the stray-light baffle wall (lowest mirror->fold ray 902 here)
X_SEAM_CAP = 796.8                # cap front/rear seam: halves the lid's 470 mm slope length
Z_SEAM_CAP = 30.0                 # cap left/right seam, off centre so the light-sensor window is clear of it
BAFFLE_TOP = 895.9                # 6 mm under the lowest mirror->fold ray at the seam (optics.js used the same rule)


def split_y(x):
    """Body/cap joint line: parallel to the lid, SKIRT below its underside."""
    return lid_y(x) - SKIRT


def lid_top(x):
    return lid_y(x) + T_LID


def nose_y(x):
    """The nose facet: parallel to the windshield, GLASS_CLEAR under it."""
    return glass_y(x) - GLASS_CLEAR


def x_nose():
    """Fore-aft position where the lid top meets the nose facet."""
    # lid_top(x) = nose_y(x)  ->  YF + T + S (XF - x) = G_y - (x - G_x) tan(rake) - clr
    t = math.tan(RAKE)
    return (GLASS_G[1] + GLASS_G[0] * t - GLASS_CLEAR - YF - T_LID - S * XF) / (t - S)
