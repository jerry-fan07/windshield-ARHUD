"""The plan's numbers, read from the single source of truth (docs/arhud-plan-tft-src/calc.py), and the few layout
values the 3-D simulator's ray trace adds (arhud_road/traced.json, written by tools/dump_traced.mjs).

Car frame used throughout this package (ISO 8855): x forward, y left, z up, metres; origin on the road under the
driver's nominal eye with the car at rest. The 3-D simulator's frame (X forward, Y up, Z right) maps as (X, -Z, Y).
The plan's own topic frame (x forward, y right, z down, origin at the ZED left lens) is produced only at the bus edge.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_SRC = os.path.normpath(os.path.join(HERE, "..", "..", "arhud-plan-tft-src"))
if PLAN_SRC not in sys.path:
    sys.path.insert(0, PLAN_SRC)
import calc  # noqa: E402  (the plan's numbers; importing it has no side effects)

DEG = math.pi / 180.0

with open(os.path.join(HERE, "traced.json")) as f:
    LAYOUT = json.load(f)


def _from_js(p):
    """3-D simulator frame (X fwd, Y up, Z right) -> this package's car frame (x fwd, y left, z up)."""
    return (p[0], -p[2], p[1])


# ---- PGU frame (the 60 x 30 mm crop of the 5.5-inch panel) ----------------------------------------------------
CROP_W = int(round(calc.CROP_PX_W))      # 946
CROP_H = int(round(calc.CROP_PX_H))      # 473
PPD = calc.PPD2                          # 87 px per degree

# ---- Eye, look-down and the virtual image -----------------------------------------------------------------------
EYE_H = calc.H_CAM                       # 1.22 m eye height (the plan's worked example)
LOOKDOWN = calc.LOOKDOWN * DEG           # 5 deg depression to the window centre (ASSUMED)
EYEBOX_W = calc.EYEBOX_W / 1000.0        # 0.130 m
EYEBOX_H = calc.EYEBOX_H / 1000.0        # 0.070 m
EYE_TO_MIRROR = LAYOUT["eyeToMirror"]    # 1.06 m: the 3-D simulator's layout (the plan's 1.00 m does not clear the glass)
MIRROR_W, MIRROR_H = LAYOUT["mirrorW"], LAYOUT["mirrorH"]

WINDOWS = {
    # The plan as written: 7.5 m from the eye, 10.8 x 5.4 deg.
    "spec": dict(label="Spec 7.5 m, 10.8 x 5.4 deg", dist=calc.D_IMG / 1000.0,
                 w=calc.PGU_W * calc.M2 / 1000.0, h=calc.PGU_H * calc.M2 / 1000.0),
    # The plan's hardware traced with the eye 1.06 m from the mirror (3-D simulator): 8.56 m, 8.7 x 4.6 deg.
    "traced": dict(label="Traced 8.56 m, 8.7 x 4.6 deg", dist=LAYOUT["traced"]["dist"],
                   w=LAYOUT["traced"]["w"], h=LAYOUT["traced"]["h"]),
    # Stage 1: 80 x 40 mm crop of the monitor, Fresnel f = 300 mm, virtual image 4.2 m, x15, 30% combiner.
    "stage1": dict(label="Stage 1 combiner 4.2 m, 16 x 8 deg", dist=abs(calc.V1_mm) / 1000.0,
                   w=0.080 * calc.M1, h=0.040 * calc.M1),
}
for _k, _w in WINDOWS.items():
    _w["fovW"] = 2 * math.atan(_w["w"] / 2 / _w["dist"]) / DEG
    _w["fovH"] = 2 * math.atan(_w["h"] / 2 / _w["dist"]) / DEG

# ---- Mounts in the car frame --------------------------------------------------------------------------------------
CAR_CENTER_Y = -LAYOUT["carCenterZ"]     # the car's centreline is 0.37 m to the driver's right (left-hand drive)
ROAD_CAM = _from_js(LAYOUT["roadCam"])   # ZED 2i left lens, high on the windshield near the mirror stalk
DRIVER_CAM = _from_js(LAYOUT["driverCam"])
EYE_TO_FRONT_BUMPER = 2.45               # m, as in the 3-D simulator
ROAD_CAM_FOV_H = 80.0                    # ZED 2i 4 mm lens, store page (datasheet says 72: CONFLICT in the plan)
ROAD_CAM_FOV_V = 52.0

# ---- Glass, ghost and the sun-entry patch ---------------------------------------------------------------------------
GHOST_PERP_M = calc.GHOST_PERP / 1000.0  # 3.1 mm between the two reflected rays (plain laminate, ASSUMED 4.96 mm)
GHOST_REL = 0.58                         # ghost brightness relative to the main image (plan 7.3)
ENTRY_DIR = _from_js(LAYOUT["entry"])    # the HUD ray continued through the glass: behind the car, 51 deg up
PATCH_W, PATCH_H = calc.PATCH_W, calc.PATCH_H

# ---- Luminance ------------------------------------------------------------------------------------------------------
PATH_WS = calc.PATH_WS                   # 19.4%: two 90% mirrors and one windshield surface
PATH_WS_TWO = calc.PATH_WS_TWO
PATH_COMB = calc.PATH_COMB               # Stage 0/1 combiner
L_DAY_EYE = calc.L_DAY_EYE               # 1,500 cd/m2 against the noon sky
L_ROAD_EYE = calc.L_ROAD_EYE             # 750 against sunlit road
L_NIGHT_EYE = calc.L_NIGHT_EYE           # 50 night ceiling
CR_PANEL = calc.CR_PANEL                 # IPS 1,000:1 (ASSUMED)
PGU_SOURCES = [
    dict(key="stock", label="5.5-inch kit, stock backlight", panel=450.0),
    dict(key="ind", label="Industrial sunlight-readable", panel=1600.0),
    dict(key="bl", label="Custom backlight (design)", panel=calc.L_PANEL_DESIGN),
    dict(key="blc", label="Collimated backlight (ASSUMED gain)", panel=calc.L_PANEL_DESIGN * calc.GAIN_COLLIM),
    dict(key="hud", label="HUD-grade TFT (UNVERIFIED)", panel=50000.0),
]

# Scene luminances (cd/m2), as in the 3-D simulator's environments, plus the ambient lux the dash sensor would read.
ENVIRONMENTS = {
    "noon": dict(label="Noon", L_sky=10000.0, L_road=5000.0, L_adapt=5000.0, lux=60000.0, scene=1.0,
                 sky=(1.0, 1.0, 1.0), sun_elev=55.0, sun_az=-40.0),
    "overcast": dict(label="Overcast", L_sky=1000.0, L_road=700.0, L_adapt=700.0, lux=8000.0, scene=0.78,
                     sky=(0.82, 0.84, 0.88), sun_elev=40.0, sun_az=-40.0),
    "dusk": dict(label="Dusk", L_sky=100.0, L_road=20.0, L_adapt=40.0, lux=200.0, scene=0.42,
                 sky=(1.0, 0.72, 0.55), sun_elev=3.0, sun_az=-60.0),
    "night": dict(label="Night", L_sky=0.005, L_road=1.5, L_adapt=1.5, lux=5.0, scene=0.10,
                  sky=(0.35, 0.42, 0.75), sun_elev=-20.0, sun_az=0.0),
}

# ---- Latency budget (plan 10): stage name, min, max ms ------------------------------------------------------------
LAT_STAGES = [dict(name=n, lo=lo, hi=hi) for (n, lo, hi) in calc.LAT]
TRACKER_LATENCY_MS = 40.0                # head tracker, 30-50 ms (parallax only)

# ---- Perception error model (plan 5.4) --------------------------------------------------------------------------------
F_PX = calc.F_PX                         # ZED 2i focal length at 1080p, px
B_ST = calc.B_ST                         # stereo baseline, m
D_DISP = calc.D_DISP                     # disparity error, px (ASSUMED)
STEREO_MAX = 35.0                        # stereo range of the 4 mm lens, m

# ---- Acceptance criteria shown beside the live numbers (plan 1) ------------------------------------------------------
CRITERIA = dict(
    static_30m_deg=0.5,                  # static registration at 30 m
    head_motion_deg=0.3,                 # under +/-75 mm head motion, tracker on
    chain_ms=90.0,                       # motion-to-photon
    predicted_deg=0.3,                   # compensated error
    speed_ms=1.0,                        # speed shown vs reference
    contrast=1.15,                       # (overlay + background) / background
)

MPH = 2.236936
