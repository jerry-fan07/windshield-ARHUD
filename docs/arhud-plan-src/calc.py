"""Single source of truth for every number quoted in the PDF plan.
Run directly to print the table; build.py imports V and substitutes {{key}} in the text."""
import math

d = math.degrees
r = math.radians
V = {}

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
V["brewster"] = f"{d(math.atan(N_GLASS)):.1f}"
ANGLES = list(range(0, 86, 2))
CURVE = [(a,) + tuple(x*100 for x in fresnel(a)) for a in ANGLES]

# ---- Stage 1: Fresnel magnifier ----------------------------------------
F1, U1 = 300.0, 280.0
V1_mm = 1 / (1 / F1 - 1 / U1)              # negative = virtual, same side
M1 = abs(V1_mm / U1)
V["s1_dist"] = f"{abs(V1_mm)/1000:.1f} m"
V["s1_M"] = f"{M1:.0f}"
V["s1_w"] = f"{80*M1/1000:.1f} m"
V["s1_h"] = f"{40*M1/1000:.1f} m"
V["s1_angw"] = f"{2*d(math.atan((80*M1/2)/abs(V1_mm))):.0f}"
V["s1_angh"] = f"{2*d(math.atan((40*M1/2)/abs(V1_mm))):.0f}"
PITCH_MM = 25.4 / 277
V["s1_ppd"] = f"{(80/PITCH_MM)/(2*d(math.atan((80*M1/2)/abs(V1_mm)))):.0f}"

# ---- Stage 2: concave relay mirror (corrected) --------------------------
# Object (PGU) must sit INSIDE the focal length for a virtual image.
F2 = 330.0
D_IMG = 7500.0                              # virtual image distance behind mirror, mm
U2 = 1 / (1 / F2 + 1 / D_IMG)               # object distance giving that image
M2 = D_IMG / U2
PGU_W, PGU_H = 60.0, 30.0
V["u2"] = f"{U2:.0f} mm"
V["f2"] = f"{F2:.0f} mm"
V["m2"] = f"{M2:.1f}"
V["img2_w"] = f"{PGU_W*M2/1000:.2f} m"
V["img2_h"] = f"{PGU_H*M2/1000:.2f} m"
V["fov2_w"] = f"{2*d(math.atan(PGU_W*M2/2/D_IMG)):.1f}"
V["fov2_h"] = f"{2*d(math.atan(PGU_H*M2/2/D_IMG)):.1f}"
# What the plan's own numbers (u = 346 mm) actually produce:
V_PLAN = 1 / (1 / F2 - 1 / 346.0)          # positive = real
V["plan_v"] = f"{V_PLAN/1000:.1f} m"
V["plan_M"] = f"{abs(V_PLAN/346.0):.1f}"

# Window geometry at 7.5 m
def span(deg, dist=7500.0):
    return 2 * dist * math.tan(r(deg / 2))
V["win_10x4_w"] = f"{span(10)/1000:.2f} m"
V["win_10x4_h"] = f"{span(4)/1000:.2f} m"
V["win_10x5_h"] = f"{span(5)/1000:.2f} m"
V["win_10x4_Mh"] = f"{span(4)/PGU_H:.1f}"

# ---- Luminance budget (cd/m2 at the eye, normal incidence chain) --------
A_DIFF = (PGU_W/1000) * (PGU_H/1000)       # m2
L_DLP = 2000 * 0.5 / (math.pi * A_DIFF)     # Lambertian: L = Phi*eta/(pi*A)
MIRROR_R = 0.90                             # ASSUMED protected-aluminium reflectance per mirror
POL_T = 0.42                                # ASSUMED sheet-polariser transmission for unpolarised light
LUM = {
    "yod_peak_comb": 1200 * 0.30,
    "yod_peak_ws":   1200 * 0.24,
    "yod_sust_comb": 600 * 0.30,
    "yod_sust_ws":   600 * 0.24,
    "dlp_comb":      L_DLP * 0.30,
    "dlp_ws":        L_DLP * 0.24,
    "dlp_ws_mirr":   L_DLP * MIRROR_R * MIRROR_R * 0.24,
    "dlp_ws_mirr_pol": L_DLP * MIRROR_R * MIRROR_R * 0.24 * POL_T,
}
for k, v in LUM.items():
    V[k] = f"{v:,.0f}"
V["L_DLP"] = f"{L_DLP:,.0f}"
V["pol_t"] = f"{POL_T*100:.0f}%"
V["dlp_headroom"] = f"{LUM['dlp_ws']/1500:.0f}"
V["dlp_headroom_mirr"] = f"{LUM['dlp_ws_mirr']/1500:.0f}"
V["dlp_headroom_pol"] = f"{LUM['dlp_ws_mirr_pol']/1500:.0f}"
V["dlp_day_frac_raw"] = f"{1500/LUM['dlp_ws']*100:.1f}%"
V["dlp_day_frac"] = f"{1500/LUM['dlp_ws_mirr_pol']*100:.0f}%"
V["yod_pct"] = f"{LUM['yod_peak_ws']/1500*100:.0f}%"
V["dim_day_night"] = f"{1500/50:.0f}:1"
V["dim_full_night"] = f"{42441/50:.0f}:1"
# Two-surface windshield reflection with the wedge overlapping both images at the eye point
RS65_TWO = RS65 + (1 - RS65) ** 2 * RS65
V["rs65_two"] = f"{RS65_TWO*100:.0f}%"

# ---- Latency budget (stage ranges from the plan, ms) ---------------------
LAT = [
    ("Camera exposure to modelV2 publish", 50, 80),
    ("bridge over Ethernet",               1, 3),
    ("hudd render (60 Hz, vsync)",          8, 16),
    ("Display scan-out",                    8, 40),
]
LAT_MIN = sum(a for _, a, _ in LAT)
LAT_MAX = sum(b for _, _, b in LAT)
V["lat_min"], V["lat_max"] = str(LAT_MIN), str(LAT_MAX)

# ---- Parallax from a 150 mm head shift ----------------------------------
PAR = [(d_m, d(math.atan(0.150 / d_m))) for d_m in (7.5, 10, 15, 20, 30)]
for d_m, a in PAR:
    V[f"par_{d_m:g}".replace(".", "_")] = f"{a:.2f}"   # keys without dots for the template

# ---- Motion compensation (point 10 m ahead, camera 1.22 m high) ---------
H_CAM = 1.22
V_EGO, T_AGE = 30.0, 0.100
TRAVEL = V_EGO * T_AGE
DEP0 = d(math.atan(H_CAM / 10))
DEP1 = d(math.atan(H_CAM / (10 - TRAVEL)))
V["travel"] = f"{TRAVEL:.1f} m"
V["dep0"] = f"{DEP0:.2f}"
V["dep1"] = f"{DEP1:.2f}"
V["uncomp"] = f"{DEP1-DEP0:.1f}"
DX = 0.5 * 1.0 * T_AGE * T_AGE              # 1 m/s^2 unmodelled over 100 ms
RES = abs(d(math.atan(H_CAM / (10 - DX)) - math.atan(H_CAM / 10)))
V["resid_mm"] = f"{DX*1000:.0f} mm"
V["resid_deg"] = f"{RES:.3f}"
V["lat_sum_ms_uncomp"] = f"{TRAVEL*1000/1000:.0f}"

# ---- Acquisition costs (USD low/high, from the plan's table) -----------
COST = [
    ("comma four + harness",                1098, 1098, "firm"),
    ("OEM HUD windshield, installed",        600, 1500, "per car"),
    ("Laser DLP projector ≥ 2,000 lm",      1500, 3000, "range"),
    ("Concave mirror, 300×200 mm (quote)",  1000, 4000, "estimate"),
    ("Diffuser film, cold mirror, polariser", 200, 400, "range"),
    ("Teleprompter beamsplitters ×2",        150, 300, "range"),
    ("Fresnel lenses ×2",                    60, 150, "range"),
    ("OAK-D Pro",                           595, 595, "firm"),
    ("AR0234 GMSL kit",                     300, 600, "unverified"),
    ("DC-DC converter with ignition sense",  89, 89, "firm"),
    ("USB-C Ethernet, switch, Cat6",        80, 80, "range"),
    ("USB-C PD chargers ×2",                80, 80, "firm"),
    ("Luminance meter",                    2500, 4000, "range"),
    ("Latency probe, rangefinder, target",  300, 300, "range"),
]
V["cost_low"] = f"{sum(c[1] for c in COST):,}"
V["cost_high"] = f"{sum(c[2] for c in COST):,}"

# ---- Sun focus: on-axis ray trace of the concave mirror -----------------
# Mirror: sphere radius 2*F2, aperture 300 x 200 mm, concave toward incoming light.
# Sun modelled as parallel on-axis rays (no windshield, no sun disk): the
# geometric concentration the plan must guard against.
import random
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
    r90 = rad[int(0.9 * len(rad))]
    return r90
R90_FOCUS_PLANE = trace_spot(F2)
R90_PGU = trace_spot(U2)
A_MIRROR = 300.0 * 200.0
SUN_DIAM_RAD = r(0.53)
SUN_FOCAL_MM = F2 * SUN_DIAM_RAD             # sun's own image at the focal plane
V["r90_pgu"] = f"{R90_PGU:.1f}"
V["r90_focus"] = f"{R90_FOCUS_PLANE:.1f}"
V["sun_focal"] = f"{SUN_FOCAL_MM:.1f}"
V["conc_pgu"] = f"{A_MIRROR/(math.pi*R90_PGU**2):,.0f}"
V["conc_focus"] = f"{A_MIRROR/(math.pi*R90_FOCUS_PLANE**2):,.0f}"
V["focus_gap"] = f"{F2 - U2:.0f} mm"
# Collected sun power: aperture x direct irradiance x ASSUMED windshield transmission for sunlight
SUN_IRR = 1000.0                             # W/m2, direct normal, clear sky
WS_T_SUN = 0.70                              # ASSUMED two-surface transmission plus interlayer absorption
SUN_W = A_MIRROR / 1e6 * SUN_IRR * WS_T_SUN
V["sun_w"] = f"{SUN_W:.0f} W"
V["ws_t_sun"] = f"{WS_T_SUN*100:.0f}%"
V["sun_spot_mm"] = f"{2*R90_PGU:.0f}"

if __name__ == "__main__":
    for k in sorted(V):
        print(f"{k:18s} {V[k]}")
    print("LAT sum", LAT_MIN, LAT_MAX)
    print("COST sum", V["cost_low"], V["cost_high"])
    print("Fresnel curve points:", len(CURVE))
