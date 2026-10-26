"""Single source of truth for every number quoted in the TFT LCD, HUD-only plan.
Run directly to print the table; build.py imports V and substitutes {{key}} in the text.
Values marked ASSUMED are design assumptions, not measurements; the text tags them."""
import math

d = math.degrees
r = math.radians
V = {}

def fmt_int(x):
    return f"{x:,.0f}"

# ---- Windshield reflectance (Fresnel, n = 1.52) -------------------------
N_GLASS = 1.52
def fresnel(theta_i_deg, n=N_GLASS):
    ti = r(theta_i_deg)
    tt = math.asin(math.sin(ti) / n)
    ci, ct = math.cos(ti), math.cos(tt)
    rs = (ci - n * ct) / (ci + n * ct)
    rp = (n * ci - ct) / (n * ci + ct)
    return rs * rs, rp * rp
RS65, RP65 = fresnel(65)
V["rs65"] = f"{RS65*100:.1f}%"
V["rp65"] = f"{RP65*100:.1f}%"
V["rs65_x"] = f"{RS65/RP65:.0f}"                       # s over p ratio at 65 degrees
V["brewster"] = f"{d(math.atan(N_GLASS)):.1f}"
ANGLES = list(range(0, 86, 2))
CURVE = [(a,) + tuple(x * 100 for x in fresnel(a)) for a in ANGLES]
# Two-surface reflection when both images overlap at the eye (wedge glass or a broad patch)
RS65_TWO = RS65 + (1 - RS65) ** 2 * RS65
V["rs65_two"] = f"{RS65_TWO*100:.0f}%"
V["ghost_rel"] = f"{(1-RS65)**2*100:.0f}%"              # ghost brightness relative to the main image
R_WS = 0.24                                              # design figure, one surface, s-polarised
R_WS_TWO = 0.37                                          # both surfaces overlapping (wedge, or a patch wider than the ghost offset)

# ---- Ghost image geometry (plain laminate, parallel surfaces) ----------
T_GLASS = 2.1 + 0.76 + 2.1                               # ASSUMED typical windshield build, mm
THETA_I = 65.0
THETA_T = d(math.asin(math.sin(r(THETA_I)) / N_GLASS))
GHOST_SURF = 2 * T_GLASS * math.tan(r(THETA_T))          # separation along the surface, mm
GHOST_PERP = GHOST_SURF * math.cos(r(THETA_I))           # separation between the two parallel reflected rays, mm
V["t_glass"] = f"{T_GLASS:.2f} mm"
V["theta_t"] = f"{THETA_T:.1f}"
V["ghost_surf"] = f"{GHOST_SURF:.1f} mm"
V["ghost_perp"] = f"{GHOST_PERP:.1f} mm"
def ghost_arcmin(D_m):
    return d(math.atan(GHOST_PERP / 1000 / D_m)) * 60
for D_m in (2.0, 2.5, 7.5, 10.0):
    V[f"ghost_{D_m:g}".replace(".", "_")] = f"{ghost_arcmin(D_m):.1f}"
V["ghost_lum_check"] = f"{ghost_arcmin(2.75):.1f}"       # Lumetrics example: 2 m beyond the glass plus 0.75 m to the eye; they report 0.0643 degrees
V["ghost_lum_check_deg"] = f"{ghost_arcmin(2.75)/60:.4f}"
V["arcmin_mm_75"] = f"{7500*math.tan(r(1/60)):.1f}"      # one arcminute at 7.5 m, mm
GHOST_75 = ghost_arcmin(7.5)

# ---- Stage 1: Fresnel magnifier (unchanged) ----------------------------
F1, U1 = 300.0, 280.0
V1_mm = 1 / (1 / F1 - 1 / U1)
M1 = abs(V1_mm / U1)
V["s1_dist"] = f"{abs(V1_mm)/1000:.1f} m"
V["s1_M"] = f"{M1:.0f}"
V["s1_w"] = f"{80*M1/1000:.1f} m"
V["s1_h"] = f"{40*M1/1000:.1f} m"
V["s1_angw"] = f"{2*d(math.atan((80*M1/2)/abs(V1_mm))):.0f}"
V["s1_angh"] = f"{2*d(math.atan((40*M1/2)/abs(V1_mm))):.0f}"
PITCH_MM = 25.4 / 277
V["s1_ppd"] = f"{(80/PITCH_MM)/(2*d(math.atan((80*M1/2)/abs(V1_mm)))):.0f}"

# ---- The TFT panel and the active crop ---------------------------------
# Candidate PGU: a 5.5-inch 16:9 1920 x 1080 IPS panel with an HDMI driver board (Wisecoco kit, 450 cd/m2, $95, read 2026-10-21).
PANEL_W, PANEL_H = 121.8, 68.5                           # mm, 5.5-inch 16:9 active area (ASSUMED from the diagonal until the datasheet is read)
PANEL_PX_W, PANEL_PX_H = 1920, 1080
PITCH_5 = PANEL_W / PANEL_PX_W                           # mm per pixel
PGU_W, PGU_H = 60.0, 30.0                                # the active crop used as the PGU, mm
CROP_PX_W = PGU_W / PITCH_5
CROP_PX_H = PGU_H / PITCH_5
V["panel_w"] = f"{PANEL_W:.1f}"
V["panel_h"] = f"{PANEL_H:.1f}"
V["pitch_5"] = f"{PITCH_5*1000:.1f}"                     # micrometres
V["crop_px_w"] = f"{CROP_PX_W:,.0f}"
V["crop_px_h"] = f"{CROP_PX_H:,.0f}"
V["crop_frac"] = f"{(PGU_W*PGU_H)/(PANEL_W*PANEL_H)*100:.0f}%"

# ---- Stage 2: concave relay mirror (object inside f, virtual image) ----
F2 = 330.0
D_IMG = 7500.0
U2 = 1 / (1 / F2 + 1 / D_IMG)
M2 = D_IMG / U2
V["u2"] = f"{U2:.0f} mm"
V["f2"] = f"{F2:.0f} mm"
V["r2"] = f"{2*F2:.0f} mm"
V["m2"] = f"{M2:.1f}"
V["img2_w"] = f"{PGU_W*M2/1000:.2f} m"
V["img2_h"] = f"{PGU_H*M2/1000:.2f} m"
FOV_W = 2 * d(math.atan(PGU_W * M2 / 2 / D_IMG))
FOV_H = 2 * d(math.atan(PGU_H * M2 / 2 / D_IMG))
V["fov2_w"] = f"{FOV_W:.1f}"
V["fov2_h"] = f"{FOV_H:.1f}"
PPD2 = CROP_PX_W / FOV_W
V["ppd2"] = f"{PPD2:.0f}"
V["mm_per_px_75"] = f"{PGU_W*M2/CROP_PX_W:.2f}"          # mm per pixel at 7.5 m
V["px_arcmin"] = f"{60/PPD2:.2f}"                        # arcminutes per pixel
V["ghost_px"] = f"{GHOST_75/(60/PPD2):.1f}"              # ghost offset in pixels at 7.5 m
V["line_4px_arcmin"] = f"{4*60/PPD2:.1f}"
V["line_8px_arcmin"] = f"{8*60/PPD2:.1f}"

# PGU width table: what each crop or panel width implies for the same 10.8-degree window
def mirror_for_width(w_mm, pitch_mm):
    M = (PGU_W * M2) / w_mm                              # same image width at 7.5 m
    u = D_IMG / M
    f = 1 / (1 / u - 1 / D_IMG)                           # 1/u + 1/v = 1/f with v = -D (virtual image)
    ppd = (w_mm / pitch_mm) / FOV_W
    return M, u, f, ppd
PGU_TABLE = []
PITCH_720 = 62.1 / 720                                   # Waveshare 5.0-inch 720 x 1280 kit: 62.10 mm across 720 px (read 2026-10-21)
for label, w, pitch in (("40 mm crop of the 5.5-inch panel", 40.0, PITCH_5),
                        ("60 mm crop of the 5.5-inch panel (design)", 60.0, PITCH_5),
                        ("80 mm crop of the 5.5-inch panel", 80.0, PITCH_5),
                        ("full width of the 5.5-inch panel", PANEL_W, PITCH_5),
                        ("60 mm crop of the 5.0-inch 720 x 1280 panel", 60.0, PITCH_720)):
    M, u, f, ppd = mirror_for_width(w, pitch)
    PGU_TABLE.append((label, w, M, u, f, 2 * f, ppd))
for key, row in zip(("w40", "w60", "w80", "w110", "w720"), PGU_TABLE):
    _, w, M, u, f, R, ppd = row
    V[f"{key}_M"] = f"{M:.1f}"
    V[f"{key}_u"] = f"{u:.0f}"
    V[f"{key}_f"] = f"{f:.0f}"
    V[f"{key}_r"] = f"{R:,.0f}"
    V[f"{key}_ppd"] = f"{ppd:.0f}"

# Window geometry at 7.5 m
def span(deg, dist=7500.0):
    return 2 * dist * math.tan(r(deg / 2))
V["win_10x4_w"] = f"{span(10)/1000:.2f} m"
V["win_10x4_h"] = f"{span(4)/1000:.2f} m"
V["win_10x5_h"] = f"{span(5)/1000:.2f} m"
V["crop_10x4_w"] = f"{span(10)/M2:.0f}"
V["crop_10x4_h"] = f"{span(4)/M2:.0f}"
V["crop_10x5_w"] = f"{span(10)/M2:.0f}"
V["crop_10x5_h"] = f"{span(5)/M2:.0f}"

# ---- Mirror aperture from eye box and field --------------------------
EYEBOX_W, EYEBOX_H = 130.0, 70.0                         # mm, design eye box
L_EYE_MIRROR = 1000.0                                    # ASSUMED eye to mirror path length via the windshield, mm
MIR_W = EYEBOX_W + 2 * L_EYE_MIRROR * math.tan(r(FOV_W / 2))
MIR_H = EYEBOX_H + 2 * L_EYE_MIRROR * math.tan(r(FOV_H / 2))
V["mir_w"] = f"{MIR_W:.0f}"
V["mir_h"] = f"{MIR_H:.0f}"
# Emission cone the panel must fill so that every image point reaches the whole eye box
CONE_H_HALF = d(math.atan((EYEBOX_W / 2) / U2))
CONE_V_HALF = d(math.atan((EYEBOX_H / 2) / U2))
V["cone_h"] = f"{CONE_H_HALF:.1f}"
V["cone_v"] = f"{CONE_V_HALF:.1f}"
CONE_DESIGN = 15.0                                       # design half-angle with margin, degrees
LAMB_FRAC = math.sin(r(CONE_DESIGN)) ** 2                # share of a Lambertian emitter's flux inside the cone
V["cone_design"] = f"{CONE_DESIGN:.0f}"
V["lamb_frac"] = f"{LAMB_FRAC*100:.1f}%"
V["lamb_waste"] = f"{(1-LAMB_FRAC)*100:.0f}%"
V["collim_ideal"] = f"{1/LAMB_FRAC:.0f}"

# ---- Luminance budget (cd/m2 at the eye) -------------------------------
MIRROR_R = 0.90                                          # ASSUMED protected-aluminium reflectance per mirror
PATH_WS = MIRROR_R * MIRROR_R * R_WS                     # two relay mirrors and one windshield surface
PATH_WS_TWO = MIRROR_R * MIRROR_R * R_WS_TWO
PATH_COMB = 0.30                                         # Stage 0/1 combiner, teleprompter 70/30
V["path_ws"] = f"{PATH_WS*100:.1f}%"
V["path_ws_two"] = f"{PATH_WS_TWO*100:.1f}%"
L_DAY_EYE = 1500.0
L_NIGHT_EYE = 50.0
L_ROAD_EYE = 0.15 * 5000.0                               # overlay needed against a 5,000 cd/m2 sunlit road
V["l_road_eye"] = fmt_int(L_ROAD_EYE)
V["need_panel_day"] = fmt_int(L_DAY_EYE / PATH_WS)
V["need_panel_day_two"] = fmt_int(L_DAY_EYE / PATH_WS_TWO)
V["need_panel_road"] = fmt_int(L_ROAD_EYE / PATH_WS)
V["need_panel_night"] = fmt_int(L_NIGHT_EYE / PATH_WS)
L_PANEL_DESIGN = 10000.0                                 # custom-backlight design target at the panel
V["l_panel_design"] = fmt_int(L_PANEL_DESIGN)
SOURCES = [
    # key, label, panel luminance, note
    ("yod",   "YODOIT 16-inch monitor, 1,200 cd/m2 peak",          1200.0),
    ("stock", "5.5-inch HDMI panel, stock backlight, 450",        450.0),
    ("ind",   "industrial sunlight-readable panel, 1,600 (7-inch)", 1600.0),
    ("bl",    "5.5-inch panel with the custom backlight, 10,000",  L_PANEL_DESIGN),
    ("blc",   "same backlight collimated (gain 3, assumed), 30,000", L_PANEL_DESIGN * 3.0),
    ("hud",   "automotive HUD-grade TFT, 50,000 (Continental's figure)", 50000.0),
]
# Production virtual-image luminance (Continental EP3719561: 5,000 minimum, 10,000-15,000 preferred; TI DLPA057: up to 15,000)
PROD_EYE_LO, PROD_EYE_HI = 10000.0, 15000.0
V["prod_eye_lo"] = fmt_int(PROD_EYE_LO)
V["prod_eye_hi"] = fmt_int(PROD_EYE_HI)
V["need_panel_prod_lo"] = fmt_int(PROD_EYE_LO / PATH_WS)
V["need_panel_prod_hi"] = fmt_int(PROD_EYE_HI / PATH_WS)
V["prod_ratio_sky"] = f"{(PROD_EYE_LO + 10000) / 10000:.1f}"      # contrast ratio production reaches against a 10,000 sky
V["bl_ratio_sky"] = f"{(L_PANEL_DESIGN * PATH_WS + 10000) / 10000:.2f}"
V["blc_ratio_sky"] = f"{(L_PANEL_DESIGN * 3 * PATH_WS + 10000) / 10000:.2f}"
V["bl_share_prod"] = f"{L_PANEL_DESIGN * PATH_WS / PROD_EYE_LO * 100:.0f}%"
# Sunlit asphalt from the FHWA luminance coefficients (0.07-0.10 cd/m2 per lux) at 50,000 and 100,000 lux
V["asph_lo"] = fmt_int(0.07 * 50000)
V["asph_hi"] = fmt_int(0.10 * 100000)
LUM = {}
for key, label, lp in SOURCES:
    LUM[key] = {
        "panel": lp,
        "comb": lp * PATH_COMB,
        "ws": lp * PATH_WS,
        "ws_two": lp * PATH_WS_TWO,
    }
    V[f"{key}_panel"] = fmt_int(lp)
    V[f"{key}_comb"] = fmt_int(lp * PATH_COMB)
    V[f"{key}_ws"] = fmt_int(lp * PATH_WS)
    V[f"{key}_ws_two"] = fmt_int(lp * PATH_WS_TWO)
    V[f"{key}_amb"] = fmt_int(lp * PATH_WS / 0.15)        # ambient the overlay still beats at contrast 1.15
    V[f"{key}_amb_two"] = fmt_int(lp * PATH_WS_TWO / 0.15)
    V[f"{key}_pct"] = f"{lp*PATH_WS/L_DAY_EYE*100:.0f}%"
    V[f"{key}_pct_two"] = f"{lp*PATH_WS_TWO/L_DAY_EYE*100:.0f}%"
V["yod_comb_pct"] = f"{1200*PATH_COMB/L_DAY_EYE*100:.0f}%"
V["bl_headroom"] = f"{L_PANEL_DESIGN*PATH_WS/L_DAY_EYE:.1f}"
V["bl_headroom_two"] = f"{L_PANEL_DESIGN*PATH_WS_TWO/L_DAY_EYE:.1f}"
# Dimming and black level
V["dim_day_night"] = f"{L_DAY_EYE/L_NIGHT_EYE:.0f}:1"
V["dim_bl_night"] = f"{L_PANEL_DESIGN*PATH_WS/L_NIGHT_EYE:.0f}:1"
CR_PANEL = 1000.0                                        # ASSUMED native contrast of an IPS cell
V["cr_panel"] = f"{CR_PANEL:,.0f}:1"
V["black_day_eye"] = f"{L_PANEL_DESIGN/CR_PANEL*PATH_WS:.1f}"
V["black_night_eye"] = f"{(L_NIGHT_EYE/PATH_WS)/CR_PANEL*PATH_WS:.2f}"
V["night_panel"] = fmt_int(L_NIGHT_EYE / PATH_WS)

# ---- Backlight design -----------------------------------------------------
T_LCD = 0.06                                             # ASSUMED cell transmittance (polarisers, colour filters, aperture)
V["t_lcd"] = f"{T_LCD*100:.0f}%"
L_BL = L_PANEL_DESIGN / T_LCD                            # backlight luminance behind the cell
V["l_bl"] = fmt_int(L_BL)
A_CROP = (PGU_W / 1000) * (PGU_H / 1000)
PHI_OUT = math.pi * L_BL * A_CROP                        # Lambertian flux leaving the backlight over the crop
V["a_crop_cm2"] = f"{A_CROP*1e4:.0f}"
V["phi_out"] = fmt_int(PHI_OUT)
ETA_BL = 0.50                                            # ASSUMED backlight optical efficiency (cavity, diffuser, films)
LED_LMW = 150.0                                          # ASSUMED luminous efficacy at the drive current, lm/W
PHI_LED = PHI_OUT / ETA_BL
P_LED = PHI_LED / LED_LMW
V["eta_bl"] = f"{ETA_BL*100:.0f}%"
V["led_lmw"] = f"{LED_LMW:.0f}"
V["phi_led"] = fmt_int(PHI_LED)
V["p_led"] = f"{P_LED:.1f} W"
GAIN_FILM = 2.0                                          # ASSUMED on-axis gain of a crossed prism-film pair (3M: 1.53 per film; 2.8 for a DBEF plus two BEF stack)
V["gain_film"] = f"{GAIN_FILM:.1f}"
V["p_led_film"] = f"{P_LED/GAIN_FILM:.1f} W"
GAIN_COLLIM = 3.0                                        # ASSUMED practical gain of a collimated backlight
V["gain_collim"] = f"{GAIN_COLLIM:.0f}"
V["p_led_collim"] = f"{P_LED/GAIN_COLLIM:.1f} W"
LM_PER_W_RADIANT = 300.0                                 # ASSUMED lm per radiant watt for warm-neutral white light
P_ABS_CELL = PHI_OUT * (1 - T_LCD) / LM_PER_W_RADIANT
V["p_abs_cell"] = f"{P_ABS_CELL:.1f} W"
V["irr_cell"] = f"{P_ABS_CELL/A_CROP:,.0f}"              # W/m2 absorbed in the cell
# Full-panel comparison: lighting the whole 5-inch panel instead of the crop
A_PANEL = (PANEL_W / 1000) * (PANEL_H / 1000)
V["p_led_full"] = f"{P_LED*A_PANEL/A_CROP:.0f} W"
# Measured-transmittance method: stock luminance over stock backlight luminance
V["stock_bl_example"] = fmt_int(450.0 / T_LCD)

# ---- Latency budget (stage ranges, ms) ------------------------------------
LAT = [
    ("Camera exposure, readout, transfer",  10, 30),
    ("Perception inference (lanes, objects, depth)", 10, 25),
    ("Publish and pick-up by hudd",            1, 3),
    ("hudd render (60 Hz, vsync)",             8, 16),
    ("Panel scan-out via the HDMI board",      8, 25),
]
LAT_MIN = sum(a for _, a, _ in LAT)
LAT_MAX = sum(b for _, _, b in LAT)
V["lat_min"], V["lat_max"] = str(LAT_MIN), str(LAT_MAX)
V["lat_travel_min"] = f"{30*LAT_MIN/1000:.1f}"
V["lat_travel_max"] = f"{30*LAT_MAX/1000:.1f}"

# ---- Parallax from a 150 mm head shift ----------------------------------
PAR = [(d_m, d(math.atan(0.150 / d_m))) for d_m in (7.5, 10, 15, 20, 30)]
for d_m, a in PAR:
    V[f"par_{d_m:g}".replace(".", "_")] = f"{a:.2f}"

# ---- Motion compensation (point 10 m ahead, eye 1.22 m high) -----------
H_CAM = 1.22
V_EGO, T_AGE = 30.0, 0.100
TRAVEL = V_EGO * T_AGE
DEP0 = d(math.atan(H_CAM / 10))
DEP1 = d(math.atan(H_CAM / (10 - TRAVEL)))
V["travel"] = f"{TRAVEL:.1f} m"
V["dep0"] = f"{DEP0:.2f}"
V["dep1"] = f"{DEP1:.2f}"
V["uncomp"] = f"{DEP1-DEP0:.1f}"
DX = 0.5 * 1.0 * T_AGE * T_AGE
RES = abs(d(math.atan(H_CAM / (10 - DX)) - math.atan(H_CAM / 10)))
V["resid_mm"] = f"{DX*1000:.0f} mm"
V["resid_deg"] = f"{RES:.3f}"
# Speed error through the compensation: 1 m/s wrong over 100 ms
DXV = 1.0 * T_AGE
RESV = abs(d(math.atan(H_CAM / (10 - DXV)) - math.atan(H_CAM / 10)))
V["resid_speed_deg"] = f"{RESV:.2f}"

# ---- Camera-to-eye baseline: how depth error turns into registration error ---
B_CE = 0.45                                              # ASSUMED camera-to-eye offset, m (camera high on the windshield centre)
V["b_ce"] = f"{B_CE*100:.0f} cm"
def reg_err_deg(z, dz, b=B_CE):
    return d(b * dz / (z * z))
V["reg_10_10pct"] = f"{reg_err_deg(10, 1.0):.2f}"
V["reg_20_10pct"] = f"{reg_err_deg(20, 2.0):.2f}"
V["reg_30_10pct"] = f"{reg_err_deg(30, 3.0):.2f}"
V["reg_10_1m"] = f"{reg_err_deg(10, 1.0):.2f}"
V["reg_30_3m5"] = f"{reg_err_deg(30, 3.5):.2f}"
# Stereo depth error: dz = z^2 * d_disp / (f_px * B)
F_PX = 960.0 / math.tan(r(40.0))                         # ZED 2i 4 mm lens at 1080p: 80 degrees horizontal (store page; the datasheet says 72, which would be better)
B_ST = 0.12                                              # ZED 2i baseline, m
D_DISP = 0.25                                            # ASSUMED disparity error, px
def stereo_dz(z):
    return z * z * D_DISP / (F_PX * B_ST)
for z in (10, 20, 30, 50):
    V[f"sdz_{z}"] = f"{stereo_dz(z):.2f}"
    V[f"sdz_{z}_pct"] = f"{stereo_dz(z)/z*100:.0f}%"
V["sreg_30"] = f"{reg_err_deg(30, stereo_dz(30)):.3f}"
V["sreg_10"] = f"{reg_err_deg(10, stereo_dz(10)):.3f}"
# Ground-plane pitch sensitivity: a 1 degree pitch error moves a 20 m lane point to
H_ROAD_CAM = 1.30                                        # ASSUMED road camera height, m
Z0 = 20.0
Z1 = H_ROAD_CAM / math.tan(math.atan(H_ROAD_CAM / Z0) + r(1.0))
V["pitch_z1"] = f"{Z1:.1f}"
V["pitch_dz"] = f"{Z0-Z1:.1f}"
V["pitch_reg"] = f"{reg_err_deg(Z0, Z0-Z1):.2f}"

# ---- Sun focus: on-axis ray trace of the concave mirror -----------------
R_SPH = 2 * F2
def trace_spot(z_plane, n=220):
    hits = []
    for i in range(n):
        for j in range(n):
            x = -150 + 300 * (i + 0.5) / n
            y = -100 + 200 * (j + 0.5) / n
            zc = R_SPH - math.sqrt(R_SPH**2 - x*x - y*y)
            P = (x, y, zc)
            nrm = ((0 - P[0]) / R_SPH, (0 - P[1]) / R_SPH, (R_SPH - P[2]) / R_SPH)
            D = (0.0, 0.0, -1.0)
            dn = D[0]*nrm[0] + D[1]*nrm[1] + D[2]*nrm[2]
            Dr = (D[0]-2*dn*nrm[0], D[1]-2*dn*nrm[1], D[2]-2*dn*nrm[2])
            t = (z_plane - P[2]) / Dr[2]
            hits.append((P[0] + t*Dr[0], P[1] + t*Dr[1]))
    rad = sorted(math.hypot(x, y) for x, y in hits)
    return rad[int(0.9 * len(rad))]
R90_FOCUS_PLANE = trace_spot(F2)
R90_PGU = trace_spot(U2)
A_MIRROR = 300.0 * 200.0
SUN_DIAM_RAD = r(0.53)
SUN_FOCAL_MM = F2 * SUN_DIAM_RAD
V["r90_pgu"] = f"{R90_PGU:.1f}"
V["r90_focus"] = f"{R90_FOCUS_PLANE:.1f}"
V["sun_focal"] = f"{SUN_FOCAL_MM:.1f}"
V["conc_pgu"] = f"{A_MIRROR/(math.pi*R90_PGU**2):,.0f}"
V["focus_gap"] = f"{F2 - U2:.0f} mm"
SUN_IRR = 1000.0
WS_T_SUN = 0.70                                          # ASSUMED windshield transmission for sunlight
SUN_W = A_MIRROR / 1e6 * SUN_IRR * WS_T_SUN
V["sun_w"] = f"{SUN_W:.0f} W"
V["ws_t_sun"] = f"{WS_T_SUN*100:.0f}%"
V["sun_spot_mm"] = f"{2*R90_PGU:.0f}"
SPOT_AREA_CM2 = math.pi * (R90_PGU / 10) ** 2
V["sun_wcm2"] = f"{SUN_W/SPOT_AREA_CM2:.0f}"
# Defence in depth: cold-mirror fold passes infrared; an s-pass polariser at the aperture halves the rest
VIS_FRAC = 0.48                                          # ASSUMED share of solar power below 700 nm (visible plus UV), passed by a cold mirror alone
FILT_FRAC = 325.0 / 1050.0                               # TI DLPA096: spectral filtering (hot and cold mirrors) leaves 325 of 1,050 W/m2
POL_T_UNPOL = 0.42                                       # ASSUMED sheet polariser transmission for unpolarised light
SUN_AFTER_COLD = SUN_W * VIS_FRAC
SUN_AFTER_FILT = SUN_W * FILT_FRAC
SUN_AFTER_POL = SUN_AFTER_FILT * POL_T_UNPOL
V["vis_frac"] = f"{VIS_FRAC*100:.0f}%"
V["filt_frac"] = f"{FILT_FRAC*100:.0f}%"
V["pol_t"] = f"{POL_T_UNPOL*100:.0f}%"
V["sun_after_cold"] = f"{SUN_AFTER_COLD:.0f} W"
V["sun_after_filt"] = f"{SUN_AFTER_FILT:.0f} W"
V["sun_after_pol"] = f"{SUN_AFTER_POL:.1f} W"
V["sun_after_pol_wcm2"] = f"{SUN_AFTER_POL/SPOT_AREA_CM2:.0f}"
V["sun_suns"] = f"{SUN_AFTER_POL/SPOT_AREA_CM2/0.1:.0f}"  # multiples of direct sunlight (0.1 W/cm2)
V["sun_min_to_damage"] = "4"
V["sun_after_pol_kwm2"] = f"{SUN_AFTER_POL/SPOT_AREA_CM2*10:.0f}"   # kW/m2 after the filters
TI_IMAGER_PEAK = 40.0                                                 # TI DLPA096: peak irradiance on the imager, kW/m2, 7 m virtual image
V["ti_peak"] = f"{TI_IMAGER_PEAK:.0f}"
V["sun_vs_ti"] = f"{SUN_AFTER_POL/SPOT_AREA_CM2*10/TI_IMAGER_PEAK:.0f}"
V["sun_vs_ti_tft"] = f"{SUN_AFTER_POL/SPOT_AREA_CM2*10/12.0:.0f}"    # against the 12 kW/m2 at which TI measured a 45 degree rise on a BMW HUD TFT                               # NS International US12699266B2: over four minutes to LCD damage with its filter set (their geometry, not ours)

# ---- Sun entry direction from the windshield geometry -------------------
RAKE = 28.0                                              # ASSUMED windshield angle above horizontal
LOOKDOWN = 5.0                                           # eye ray depression to the HUD patch, degrees
# Direction of the reversed eye ray after reflection: angle = lookdown - 2*rake (negative: forward and down)
MIRROR_DIR = LOOKDOWN - 2 * RAKE
SUN_ELEV = 180.0 + MIRROR_DIR                            # the sun must sit opposite that direction: behind and above
V["rake"] = f"{RAKE:.0f}"
V["lookdown"] = f"{LOOKDOWN:.0f}"
V["mirror_dir"] = f"{-MIRROR_DIR:.0f}"
V["sun_elev"] = f"{180 - SUN_ELEV:.0f}"                  # elevation above the horizon, behind the car
for rk in (25, 28, 32, 35):
    V[f"sun_elev_{rk}"] = f"{180 - (180 + LOOKDOWN - 2*rk):.0f}"
# Incidence check for the assumed rake and look-down
n_out = (math.sin(r(RAKE)), math.cos(r(RAKE)))            # outward normal, (forward, up)
v_eye = (math.cos(r(-LOOKDOWN)), math.sin(r(-LOOKDOWN)))
V["inc_check"] = f"{d(math.acos(n_out[0]*v_eye[0] + n_out[1]*v_eye[1])):.0f}"
# Angular size of the sky patch that can reach the PGU: eye box as seen from the glass, plus the field
L_EYE_GLASS = 750.0                                      # ASSUMED eye to windshield distance, mm
PATCH_W = 2 * d(math.atan(EYEBOX_W / 2 / L_EYE_GLASS)) + FOV_W
PATCH_H = 2 * d(math.atan(EYEBOX_H / 2 / L_EYE_GLASS)) + FOV_H
V["patch_w"] = f"{PATCH_W:.0f}"
V["patch_h"] = f"{PATCH_H:.0f}"
V["patch_minutes"] = f"{PATCH_W/15*60:.0f}"              # minutes for the sun to cross the patch at 15 degrees per hour

# ---- Acquisition costs (USD low/high; last seen, not quotes) -----------
COST = [
    ("Stereolabs ZED 2i, 4 mm lens",                       499,  499, "firm"),
    ("Luxonis OAK-D Pro (driver camera)",                  349,  429, "range"),
    ("u-blox ZED-F9R board (SparkFun) + antenna",          300,  380, "range"),
    ("Panels: 5.5-inch 1080p kits x2, 5-inch 1,100-nit module", 190, 265, "range"),
    ("Backlight: LEDs, driver, films, heat sink, fan",     150,  300, "estimate"),
    ("Half-wave retarder and polariser sheets",            150,  450, "range"),
    ("Cold mirror (fold) and IR-cut glass",                150,  400, "estimate"),
    ("Concave mirror, 300 x 200 mm (quote)",              1000, 4000, "estimate"),
    ("Teleprompter beamsplitters x2",                      110, 1030, "range"),
    ("Fresnel lenses 300 mm x2",                           160,  320, "range"),
    ("HUD controller: RP2040, sensors, shutter servo",      40,   80, "range"),
    ("DC-DC converter with ignition sense",                 89,   89, "firm"),
    ("USB-C PD charger, Ethernet switch, cables",           90,  120, "range"),
    ("Housing: printing, dust cover, mounts",              150,  300, "estimate"),
    ("Luminance meter (spot meter to lab meter)",          690, 4000, "range"),
    ("Latency probe, rangefinder, target board",           300,  300, "estimate"),
]
V["cost_low"] = f"{sum(c[1] for c in COST):,}"
V["cost_high"] = f"{sum(c[2] for c in COST):,}"
COST_OPT = [
    ("Wedge-PVB windshield, installed (if the ghost is objectionable)", 600, 1500),
    ("Automotive HUD-grade TFT module (if one can be bought)",          200,  800),
]
V["cost_opt_low"] = f"{sum(c[1] for c in COST_OPT):,}"
V["cost_opt_high"] = f"{sum(c[2] for c in COST_OPT):,}"
V["cost_removed"] = f"{1098 + 1500 + 600:,}"            # comma four + harness, projector low, windshield low (previous plan)

# ---- GPU budget on the Orin NX (ASSUMED per-frame costs, to be measured) --
GPU = [
    ("ZED depth, NEURAL_LIGHT to NEURAL",   8, 20),
    ("Lane network, FP16 (assumed)",        4,  8),
    ("Object detector, YOLO11s FP16, 640",  6, 10),
    ("Face landmarks, only if on the Jetson", 4,  8),
    ("hudd render pass, 4 draws + warp",   2,  4),
]
GPU_MIN = sum(a for _, a, _ in GPU)
GPU_MAX = sum(b for _, _, b in GPU)
V["gpu_min"], V["gpu_max"] = str(GPU_MIN), str(GPU_MAX)
V["gpu_load_30"] = f"{GPU_MAX*30/1000*100:.0f}%"        # share of GPU time at 30 Hz, worst case
V["gpu_load_30_min"] = f"{GPU_MIN*30/1000*100:.0f}%"
V["gpu_load_20"] = f"{GPU_MAX*20/1000*100:.0f}%"
V["gpu_load_20_min"] = f"{GPU_MIN*20/1000*100:.0f}%"
V["gpu_frame_30"] = f"{1000/30:.0f}"
V["gpu_frame_20"] = f"{1000/20:.0f}"

if __name__ == "__main__":
    for k in sorted(V):
        print(f"{k:20s} {V[k]}")
    print("LAT sum", LAT_MIN, LAT_MAX)
    print("COST sum", V["cost_low"], V["cost_high"])
    print("PGU table:")
    for row in PGU_TABLE:
        print(f"  {row[0]:48s} w={row[1]:6.1f}  M={row[2]:5.1f}  u={row[3]:6.0f}  f={row[4]:6.0f}  R={row[5]:6.0f}  px/deg={row[6]:5.0f}")
