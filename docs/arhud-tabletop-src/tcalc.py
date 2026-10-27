"""Numbers for the tabletop two-monitor design. Values shared with the plan are imported from
../arhud-plan-tft-src/calc.py (never copied); everything bench-specific is derived here.
Every value the document quotes is a V[...] entry, so the text cannot drift from the arithmetic.
Values marked ASSUMED in the comments must be replaced by the measurement the document names."""
import math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(DOCS, "arhud-plan-tft-src"))
import calc as P                      # noqa: E402  the plan's numbers

V = {}
r, d = math.radians, math.degrees


def fi(x):
    return f"{x:,.0f}"


def f1(x):
    return f"{x:.1f}"


def f2(x):
    return f"{x:.2f}"


# ---- The two monitors (YODOIT 16-inch 3840 x 2400; plan: 277 ppi, vendor 1,200 cd/m2) ----------------------------
MON_PX_W, MON_PX_H = 3840, 2400
PPI = 277.0                                               # plan's figure; a true 16.0-inch diagonal would be 282.8 ppi: MEASURE the active width
PITCH = 25.4 / PPI                                        # mm per pixel
MON_W, MON_H = MON_PX_W * PITCH, MON_PX_H * PITCH         # active area, mm
MON_DIAG_IN = math.hypot(MON_W, MON_H) / 25.4
L_MON = 1200.0                                            # vendor peak white, cd/m2 (plan SOURCES 'yod'); MEASURE
V["mon_px_w"], V["mon_px_h"] = fi(MON_PX_W), fi(MON_PX_H)
V["ppi"] = fi(PPI)
V["pitch_um"] = f1(PITCH * 1000)
V["mon_w"], V["mon_h"] = f1(MON_W), f1(MON_H)
V["mon_diag_in"] = f1(MON_DIAG_IN)
V["mon_w_283"], V["mon_h_283"] = f1(MON_PX_W * 25.4 / 282.8), f1(MON_PX_H * 25.4 / 282.8)
V["l_mon"] = fi(L_MON)

# ---- The glass (Neewer NA17: 315 x 315 x 2 mm, 70T/30R, one face anti-reflection coated; read 2026-10-27) ----------
GLASS_W, GLASS_T = 315.0, 2.0
G_T, G_R = 0.70, 0.30                                     # vendor split; MEASURE for the monitor's polarisation
TILT = 45.0
GLASS_FOOT = GLASS_W * math.cos(r(TILT))                  # the glass's footprint along the viewing axis and its height, mm
V["glass_w"], V["glass_t"] = fi(GLASS_W), f1(GLASS_T)
V["glass_foot"] = f1(GLASS_FOOT)
V["glass_short"] = f1(MON_W - GLASS_W)                    # how much narrower than the monitor
V["glass_px_w"] = fi(GLASS_W / PITCH)

# ---- Rig geometry (all distances from the glass's centre) --------------------------------------------------------
D_GLASS = 200.0                                           # glass centre to the PGU face below, and to the road monitor's face behind (coplanar)
D_EYE = 400.0                                             # eye (or the measuring camera) to the glass centre
D_IMG = D_EYE + D_GLASS                                   # eye to the image plane (= eye to the road monitor's face)
CLEAR_LOW = D_GLASS - GLASS_FOOT / 2                      # lowest glass edge above the PGU face
GLASS_TOP = D_GLASS + GLASS_FOOT / 2                      # highest glass edge above the PGU face
R_BOTTOM = D_GLASS - MON_H / 2                            # road monitor's lower edge above the PGU face level
V["d_glass"], V["d_eye"], V["d_img"] = fi(D_GLASS), fi(D_EYE), fi(D_IMG)
V["d_img_m"] = f2(D_IMG / 1000)
V["clear_low"], V["glass_top"], V["r_bottom"] = f1(CLEAR_LOW), f1(GLASS_TOP), f1(R_BOTTOM)
V["reflected_depth"] = f1(min(GLASS_FOOT, MON_H))         # how much of the PGU's short side the glass reflects
V["reflected_width"] = f1(min(GLASS_W, MON_W))
V["unreflected_side"] = f1(max(0.0, (MON_W - GLASS_W) / 2))
# Eye-to-glass-edge distances and the line of sight through the glass to the road monitor's corners
def cross(eye_x, px, pz):
    """Where the line from the eye (eye_x, 0) to the point (px, pz) crosses the glass plane z = -x. Returns (x, z)."""
    t = (-eye_x) / ((px - eye_x) + pz) if (px - eye_x) + pz else 0
    return eye_x + t * (px - eye_x), t * pz
CX_TOP = cross(-D_EYE, D_GLASS, MON_H / 2)
CX_BOT = cross(-D_EYE, D_GLASS, -MON_H / 2)
V["los_top_z"], V["los_bot_z"] = f1(CX_TOP[1]), f1(CX_BOT[1])
V["glass_half"] = f1(GLASS_FOOT / 2)
V["los_ok"] = "yes" if abs(CX_TOP[1]) <= GLASS_FOOT / 2 and abs(CX_BOT[1]) <= GLASS_FOOT / 2 else "no"

# ---- Angular scale at the eye ------------------------------------------------------------------------------------
FOV_W, FOV_H = P.FOV_W, P.FOV_H                           # the plan's window, degrees
HFOV_SHOWN = 2 * d(math.atan(MON_W / 2 / D_IMG))          # field of road the monitor shows at life size
VFOV_SHOWN = 2 * d(math.atan(MON_H / 2 / D_IMG))
WIN_W = 2 * D_IMG * math.tan(r(FOV_W / 2))                # the HUD window on the monitors at life size, mm
WIN_H = 2 * D_IMG * math.tan(r(FOV_H / 2))
WIN_PX_W, WIN_PX_H = WIN_W / PITCH, WIN_H / PITCH
PPD = WIN_PX_W / FOV_W
PX_ARCMIN = d(PITCH / D_IMG) * 60                         # one monitor pixel seen from the eye
V["fov_w"], V["fov_h"] = f1(FOV_W), f1(FOV_H)
V["hfov_shown"], V["vfov_shown"] = f1(HFOV_SHOWN), f1(VFOV_SHOWN)
V["win_w"], V["win_h"] = f1(WIN_W), f1(WIN_H)
V["win_px_w"], V["win_px_h"] = fi(WIN_PX_W), fi(WIN_PX_H)
V["ppd"] = fi(PPD)
V["ppd_plan"] = fi(P.PPD2)
V["crop_px_w_plan"], V["crop_px_h_plan"] = fi(P.CROP_PX_W), fi(P.CROP_PX_H)
V["px_arcmin"] = f2(PX_ARCMIN)
V["px_deg"] = f"{PX_ARCMIN/60:.4f}"
V["arcmin_01deg_px"] = f1(0.1 / (PX_ARCMIN / 60))         # pixels in 0.1 degree
V["px_05deg"] = fi(0.5 * PPD)
V["margin_side"] = f1((GLASS_W - WIN_W) / 2)              # glass beyond the window at each side
V["margin_depth"] = f1((GLASS_FOOT - WIN_H) / 2)          # glass footprint beyond the window front and back
V["px_03deg"] = fi(0.3 * PPD)

DIST_TABLE = []
for di in (450.0, 600.0, 750.0, 900.0):
    hf = 2 * d(math.atan(MON_W / 2 / di)); vf = 2 * d(math.atan(MON_H / 2 / di))
    ww = 2 * di * math.tan(r(FOV_W / 2)); wh = 2 * di * math.tan(r(FOV_H / 2))
    DIST_TABLE.append((di, di - D_GLASS, hf, vf, ww, wh, ww / PITCH, wh / PITCH, (ww / PITCH) / FOV_W))

# ---- Road sources: what each camera gives, and the crop that shows at life size ----------------------------------
# (name, width px, height px, focal px, fps, note). Focal lengths from this checkout's common/transformations/camera.py
# (_neo_config 1164x874 f=910 for the EON used by comma2k19; _ar_ox_config 1928x1208 f=2648 for the comma three) and
# the plan's F_PX for the ZED 2i (80 degree store figure); the phone figure is ASSUMED.
SOURCES = [
    ("comma2k19 segment (comma EON camera)",        1164, 874,  910.0,  20, "MIT; video.hevc + processed_log (CAN speed, gyro, GNSS) + global_pos"),
    ("openpilot route (comma three, narrow camera)", 1928, 1208, 2648.0, 20, "demo route used by tools/clip; logs carry modelV2, liveCalibration, carState"),
    ("ZED 2i, 4 mm lens, 1080p (car camera; bench loop only)", 1920, 1080, P.F_PX, 30, "store page 80 degrees; datasheet 72 (conflict in the plan)"),
    ("phone dashcam clip, 4K (ASSUMED 70 degrees)", 3840, 2160, 1920 / math.tan(r(35.0)), 30, "no log; ego-motion from a GNSS app or none"),
    ("MetaDrive render (docs/arhud-road)",           3840, 2400, (MON_W / 2 / math.tan(r(HFOV_SHOWN / 2))) / PITCH, 60, "rendered at the monitor's own field; truth for every lane, car and pedestrian"),
]
SRC_TABLE = []
for name, w, h, f, fps, note in SOURCES:
    hfov = 2 * d(math.atan(w / 2 / f))
    crop = 2 * f * math.tan(r(HFOV_SHOWN / 2))            # source pixels across the shown field
    crop = min(crop, w)
    up = MON_PX_W / crop
    win = 2 * f * math.tan(r(FOV_W / 2))                  # source pixels across the HUD window
    SRC_TABLE.append((name, w, h, f, hfov, fps, crop, up, win, note))
V["c2k_f"], V["c2k_hfov"] = fi(910), f1(2 * d(math.atan(1164 / 2 / 910)))
V["c2k_crop"] = fi(SRC_TABLE[0][6]); V["c2k_up"] = f1(SRC_TABLE[0][7]); V["c2k_win"] = fi(SRC_TABLE[0][8])
V["c2k_px_mm"] = f2(SRC_TABLE[0][7] * PITCH)              # one source pixel on the monitor, mm
V["c2k_px_arcmin"] = f1(SRC_TABLE[0][7] * PX_ARCMIN)
V["c3_f"], V["c3_hfov"] = fi(2648), f1(2 * d(math.atan(1928 / 2 / 2648)))
V["c3_crop"] = fi(SRC_TABLE[1][6]); V["c3_up"] = f1(SRC_TABLE[1][7]); V["c3_win"] = fi(SRC_TABLE[1][8])
V["zed_f"] = fi(P.F_PX); V["zed_crop"] = fi(SRC_TABLE[2][6]); V["zed_up"] = f1(SRC_TABLE[2][7])
V["phone_crop"] = fi(SRC_TABLE[3][6]); V["phone_up"] = f1(SRC_TABLE[3][7])
V["md_f"] = fi(SRC_TABLE[4][3])

# ---- Luminance and contrast through the glass ---------------------------------------------------------------------
L_HUD_EYE = L_MON * G_R                                   # PGU white seen in the glass
L_ROAD_WHITE = L_MON * G_T                                # road monitor's white seen through the glass
ASPHALT_FRAC = 0.20                                       # ASSUMED: sunlit asphalt in a daytime clip is about 20% of the clip's white (linear)
L_ASPHALT = L_ROAD_WHITE * ASPHALT_FRAC
V["l_hud_eye"], V["l_road_white"], V["l_asphalt"] = fi(L_HUD_EYE), fi(L_ROAD_WHITE), fi(L_ASPHALT)
V["asphalt_pct"] = fi(ASPHALT_FRAC * 100)
V["cr_sky_max"] = f2(1 + L_HUD_EYE / L_ROAD_WHITE)
V["cr_asph_max"] = f2(1 + L_HUD_EYE / L_ASPHALT)
# Plan conditions to emulate (eye luminance over a 10,000 sky and a 5,000 road)
L_SKY, L_ROAD = 10000.0, 5000.0
PLAN_MIN = P.L_DAY_EYE                                    # 1,500 at the eye: ratio 1.15 against the sky
PLAN_BL = P.LUM["bl"]["ws"]                               # custom backlight through the windshield path
PLAN_STAGE1 = P.LUM["yod"]["comb"]                        # this monitor through a 30% combiner in the car
COND = [
    ("Plan minimum against a noon sky (1,500 at the eye)",      PLAN_MIN,    L_SKY,  L_ROAD_WHITE),
    ("Design backlight against the sky (10,000 cd/m2 panel)",   PLAN_BL,     L_SKY,  L_ROAD_WHITE),
    ("Design backlight against sunlit asphalt",                 PLAN_BL,     L_ROAD, L_ASPHALT),
    ("This monitor through the Stage 1 combiner, against the sky", PLAN_STAGE1, L_SKY, L_ROAD_WHITE),
    ("Production AR HUD (10,000 at the eye) against the sky",    10000.0,     L_SKY,  L_ROAD_WHITE),
]
COND_TABLE = []
for label, l_eye, l_bg, l_bench_bg in COND:
    ratio = 1 + l_eye / l_bg
    gain = (ratio - 1) * l_bench_bg / L_HUD_EYE           # share of the PGU's white that reproduces the ratio on the bench
    COND_TABLE.append((label, l_eye, l_bg, ratio, gain, "yes" if gain <= 1.0 else "no"))
V["cr_plan_min"] = f2(COND_TABLE[0][3]); V["g_plan_min"] = f2(COND_TABLE[0][4])
V["cr_bl_sky"] = f2(COND_TABLE[1][3]); V["g_bl_sky"] = f2(COND_TABLE[1][4])
V["cr_bl_road"] = f2(COND_TABLE[2][3]); V["g_bl_road"] = f2(COND_TABLE[2][4])
V["cr_s1_sky"] = f"{COND_TABLE[3][3]:.3f}"; V["g_s1_sky"] = f"{COND_TABLE[3][4]:.3f}"
V["cr_prod_sky"] = f2(COND_TABLE[4][3]); V["g_prod_sky"] = f2(COND_TABLE[4][4])
V["l_plan_bl_eye"] = fi(PLAN_BL); V["l_plan_s1_eye"] = fi(PLAN_STAGE1)
# Night: the monitor's black
CR_MON = 1200.0                                           # vendor contrast (listings say 1,200:1 or 2,000:1); MEASURE
V["cr_mon"] = fi(CR_MON)
V["l_black_eye"] = f2(L_MON / CR_MON * G_R)               # unlit window glow seen in the glass at full monitor brightness
V["l_night_plan"] = fi(P.L_NIGHT_EYE)

# ---- Polarisation: plain-glass Fresnel reflectances at 45 degrees (the coated face is unknown; measure) ------------
def fresnel_rs_rp(theta_i, n=P.N_GLASS):
    ti = r(theta_i); tt = math.asin(math.sin(ti) / n)
    rs = (math.sin(ti - tt) / math.sin(ti + tt)) ** 2
    rp = (math.tan(ti - tt) / math.tan(ti + tt)) ** 2
    return rs, rp, d(tt)
RS45, RP45, THETA_T45 = fresnel_rs_rp(TILT)
V["rs45"], V["rp45"] = f1(RS45 * 100), f2(RP45 * 100)
V["theta_t45"] = f1(THETA_T45)
V["sp_ratio45"] = f1(RS45 / RP45)

# ---- Ghost from the glass's second face -------------------------------------------------------------------------
GHOST_MM = 2 * GLASS_T * math.tan(r(THETA_T45)) * math.cos(r(TILT))   # separation of the two parallel reflected rays, mm
GHOST_ARCMIN = d(GHOST_MM / D_IMG) * 60
GHOST_PX = GHOST_MM / PITCH
V["ghost_mm"] = f2(GHOST_MM)
V["ghost_arcmin"] = f1(GHOST_ARCMIN)
V["ghost_px"] = fi(GHOST_PX)
V["ghost_car_arcmin"] = f1(P.GHOST_75)
V["ghost_ratio_car"] = f1(GHOST_ARCMIN / P.GHOST_75)
AR_R = 0.005                                              # ASSUMED residual reflectance of the anti-reflection face
def ghost_rel(r2):
    return G_T * G_T * r2 / G_R                           # second-face ghost relative to the main reflection
V["ghost_rel_ar"] = f1(ghost_rel(AR_R) * 100)
V["ghost_rel_s"] = f1(ghost_rel(RS45) * 100)
V["ghost_rel_p"] = f1(ghost_rel(RP45) * 100)
V["ghost_rel_u"] = f1(ghost_rel((RS45 + RP45) / 2) * 100)
V["ghost_car_pct"] = fi(58)                               # plan: windshield ghost brightness share

# ---- Coplanarity check by parallax ---------------------------------------------------------------------------------
E_SHIFT = 100.0                                           # eye shift used in the check, mm
V["e_shift"] = fi(E_SHIFT)
V["cop_px_per_mm"] = f1(E_SHIFT / D_IMG / PITCH)          # pixels of separation per mm of plane error
COP_TOL_PX = 5.0
V["cop_tol_px"] = fi(COP_TOL_PX)
V["cop_tol_mm"] = f1(COP_TOL_PX * PITCH * D_IMG / E_SHIFT)

# ---- Parallax variant: road monitor slid back by DELTA -------------------------------------------------------------
SWAY = 75.0                                               # the plan's head-motion criterion, +-75 mm
D_VI = 7.5                                                # the car's virtual image, m
def delta_for(z_m):
    """Offset of the road monitor (mm) that reproduces the car's parallax between its 7.5 m image and a point at z."""
    k = (1 / D_VI - (0 if z_m == float("inf") else 1 / z_m))   # 1/m
    di = D_IMG / 1000
    return (1 / (1 / di - k) - di) * 1000
PAR_TABLE = []
for z in (10.0, 20.0, 30.0, 60.0, float("inf")):
    dl = delta_for(z)
    ang = d(SWAY / 1000 * (1 / (D_IMG / 1000) - 1 / ((D_IMG + dl) / 1000)))
    PAR_TABLE.append((z, dl, ang))
V["delta_20"] = f1(PAR_TABLE[1][1]); V["par_20"] = f2(PAR_TABLE[1][2])
V["delta_inf"] = f1(PAR_TABLE[4][1]); V["par_inf"] = f2(PAR_TABLE[4][2])
V["delta_10"] = f1(PAR_TABLE[0][1])
for dl in (100.0, 300.0):
    V[f"par_{int(dl)}"] = f2(d(SWAY / 1000 * (1 / (D_IMG / 1000) - 1 / ((D_IMG + dl) / 1000))))
V["sway"] = fi(SWAY)
V["par_crit"] = "0.3"
V["b_ce_cm"] = fi(P.B_CE * 100)                             # the plan's camera-to-eye baseline
TRK_TOL_MM = 5.0                                          # tracker accuracy tolerance at the eye point
V["trk_tol_mm"] = fi(TRK_TOL_MM)
V["par_tol_deg"] = f"{d(TRK_TOL_MM / 1000 * (1 / (D_IMG / 1000) - 1 / ((D_IMG + PAR_TABLE[1][1]) / 1000))):.3f}"

# ---- Timing on the bench (ms) ------------------------------------------------------------------------------------
LAG_MON = (10, 30)                                        # ASSUMED each monitor's input lag; MEASURE (T-F)
PERC_MAC = (15, 40)                                       # ASSUMED lanes + objects + tracking on the M4 (ORT CoreML / MPS); MEASURE in week 1
PERC_JET = (P.LAT[1][1], P.LAT[1][2])                     # the plan's Jetson estimate
PUB = (P.LAT[2][1], P.LAT[2][2])
REND = (P.LAT[3][1], P.LAT[3][2])
BENCH_LAT = [
    ("Road frame on the road monitor (its scan-out and input lag, hidden by scheduling)", 0, 0),
    ("Perception on the host (lanes, objects, tracking)", PERC_MAC[0], PERC_MAC[1]),
    ("Publish and pick-up by hudd", PUB[0], PUB[1]),
    ("hudd render (60 Hz, vsync)", REND[0], REND[1]),
    ("PGU monitor scan-out and input lag", LAG_MON[0], LAG_MON[1]),
]
V["lat_bench_min"] = fi(sum(a for _, a, _ in BENCH_LAT))
V["lat_bench_max"] = fi(sum(b for _, _, b in BENCH_LAT))
V["lat_plan_min"], V["lat_plan_max"] = fi(P.LAT_MIN), fi(P.LAT_MAX)
V["lag_mon_lo"], V["lag_mon_hi"] = fi(LAG_MON[0]), fi(LAG_MON[1])
V["perc_mac_lo"], V["perc_mac_hi"] = fi(PERC_MAC[0]), fi(PERC_MAC[1])
V["perc_jet_lo"], V["perc_jet_hi"] = fi(PERC_JET[0]), fi(PERC_JET[1])
V["slomo_ms"] = f1(1000 / 240)
V["vsync_ms"] = f2(1000 / 60)
# What a latency means on the road: a 10 m lane point at 30 m/s, eye 1.22 m up, seen from the camera (plan's worked case)
V["h_cam"] = f2(P.H_CAM)
for ms in (50, 90, 200):
    travel = 30.0 * ms / 1000
    shift = d(math.atan(P.H_CAM / (10 - travel)) - math.atan(P.H_CAM / 10))
    V[f"shift_{ms}"] = f2(shift)
    V[f"travel_{ms}"] = f1(travel)

# ---- Lifting a pixel to the ground (monocular, static plane) -------------------------------------------------------
def ground_range(v_px, f, cy, h, pitch_deg):
    """Range along the ground of the pixel row v for a camera h above the road pitched down by pitch_deg."""
    beta = r(pitch_deg) + math.atan((v_px - cy) / f)
    return h / math.tan(beta) if beta > 0 else float("inf")
H_C2K = 1.22                                              # ASSUMED EON camera height on comma2k19 cars (the plan's H_CAM)
V["h_c2k"] = f2(H_C2K)
# One pixel row at the horizon end: how far one row moves a ground point, comma2k19 and comma three
for key, f in (("c2k", 910.0), ("c3", 2648.0)):
    for z in (10.0, 20.0, 30.0):
        v_row = f * (H_C2K / z)                           # rows below the horizon
        z1 = H_C2K / math.tan(math.atan((v_row - 1) / f)) if v_row > 1 else float("inf")
        V[f"row_{key}_{int(z)}"] = f1(v_row)
        V[f"dz_{key}_{int(z)}"] = f1(z1 - z)
# A 1 degree pitch error at 20 m (plan's number) and 0.1 degree
Z0 = 20.0
for pe in (1.0, 0.1):
    z1 = H_C2K / math.tan(math.atan(H_C2K / Z0) + r(pe))
    V[f"pitch_dz_{str(pe).replace('.', '')}"] = f1(Z0 - z1)
V["plan_pitch_dz"] = P.V["pitch_dz"]
V["plan_pitch_reg"] = P.V["pitch_reg"]
# Registration on the bench is measured in the camera's own frame: a lateral error e (m) at range z is seen as atan(e/z)
for z, e in ((10.0, 0.15), (20.0, 0.30), (30.0, 0.50)):
    V[f"lat_{int(z)}_deg"] = f2(d(math.atan(e / z)))
    V[f"lat_{int(z)}_px"] = f1(d(math.atan(e / z)) * PPD)

# ---- Compute budgets (ASSUMED; measure in the first week) ----------------------------------------------------------
GPU_MAC = [
    ("Lane network, UFLDv2 (CULane, 1600 x 320 input), ORT CoreML or MPS", 8, 15),
    ("Object detector, YOLO11s at 640 px, CoreML FP16", 12, 25),
    ("ByteTrack association (CPU)", 1, 2),
    ("Lifting, tracking bookkeeping, publish", 1, 2),
    ("hudd draw (two passes, 1,237 x 617 window)", 2, 4),
]
V["gpu_mac_min"] = fi(sum(a for _, a, _ in GPU_MAC)); V["gpu_mac_max"] = fi(sum(b for _, _, b in GPU_MAC))
V["gpu_mac_hz_min"] = fi(1000 / sum(b for _, _, b in GPU_MAC)); V["gpu_mac_hz_max"] = fi(1000 / sum(a for _, a, _ in GPU_MAC))

# ---- Bench bill of materials (USD, read 2026-10-27 unless noted) ----------------------------------------------------
BOM = [
    ("YODOIT 16-inch 3840 x 2400 monitor, unit 1 (PGU, face up)",        0,   0,   "owned"),
    ("YODOIT 16-inch 3840 x 2400 monitor, unit 2 (road, upright)",       0,   0,   "owned"),
    ("MacBook Pro M4 (drives both monitors, runs everything until the Jetson is back)", 0, 0, "owned"),
    ("Neewer NA17 beamsplitter glass, 315 x 315 x 2 mm, 70T/30R, AR coat", 53, 53, "neewer.com; the plan's cheap teleprompter glass"),
    ("Enclosure: 6 mm plywood or black foam board, flock paper, glue",    25,  45,  "estimate"),
    ("Slide for the road monitor: 300 mm drawer slide or macro rail, with a mm scale", 15, 45, "range"),
    ("Chin rest or camera tripod with a quick-release at the eye point",  0,   40,  "owned tripod or a cheap chin rest"),
    ("Latency probe: Pico, two BPW34 photodiodes, LM393, resistors",      10,  25,  "B6.1 parts, one photodiode more"),
    ("Chessboard and ArUco prints on card, 1 mm ruler, angle gauge",      5,   15,  "estimate"),
    ("Webcam, 1080p 30 fps, for the head tracker on the bench",           25,  80,  "or the OAK-D Pro when it arrives"),
    ("Half-wave retarder film sheet, only if the polarisation test calls for it", 0, 150, "plan BOM; optional"),
    ("USB-C PD charger for each monitor (the Mac's ports may not hold 1,200 nits)", 0, 40, "verify what the monitors draw"),
]
V["bom_lo"] = fi(sum(a for _, a, _, _ in BOM)); V["bom_hi"] = fi(sum(b for _, _, b, _ in BOM))

# ---- Acceptance table ------------------------------------------------------------------------------------------------
V["t_cal_px"] = "2"
V["t_cal_deg"] = f"{2 / PPD:.3f}"
V["t_reg_deg"] = "0.10"
V["t_reg_px"] = fi(0.10 * PPD)
V["t_lat"] = "90"

if __name__ == "__main__":
    for k in sorted(V):
        print(f"{k:22s} {V[k]}")
