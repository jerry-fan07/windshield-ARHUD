"""Every number quoted in the Fresnel-stage document. build.py substitutes {{key}} from V; the
figures read the arrays in D. Stage 1's lens and panel distance come from the TFT plan's calc.py
(docs/arhud-plan-tft-src/calc.py, F1 and U1); everything else is computed here by optics.py.
Values marked ASSUMED are not in the plan or a datasheet; the text tags them."""
import importlib.util, math, os
import numpy as np
import optics as O
np.seterr(all="ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("plancalc", os.path.join(HERE, "..", "arhud-plan-tft-src", "calc.py"))
PC = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(PC)
assert (PC.F1, PC.U1) == (O.F, O.U), "optics.py F/U must match the plan's Stage 1 numbers"

V, D = {}, {}
deg = math.degrees; rad = math.radians
f0 = lambda x: f"{x:,.0f}"
f1 = lambda x: f"{x:,.1f}"
f2 = lambda x: f"{x:,.2f}"

# ---- Basics -------------------------------------------------------------------------------
V["f"] = f0(O.F); V["u"] = f0(O.U); V["t"] = f1(O.T); V["pitch"] = f1(O.PITCH)
V["n_d"] = f"{O.N_D:.3f}"
V["eye_z"] = f0(O.EYE_Z)
V["zh"] = f2(O.T / O.N_D)                                 # principal plane H lies this far inside the flat face, mm
V["u_flat"] = f1(O.U - O.T / O.N_D)                       # panel to the flat face, mm
V["half"] = f0(O.HALF)
V["fnum_edge"] = f2(O.F / (2 * O.HALF))
V["fnum_corner"] = f2(O.F / (2 * O.HALF * math.sqrt(2)))
V_PAR = O.paraxial_v()
V["v"] = f0(abs(V_PAR)); V["v_m"] = f1(abs(V_PAR) / 1000)
M = abs(V_PAR) / O.U
V["M"] = f0(M)
CROP_W, CROP_H = 80.0, 40.0                               # plan: Stage 1 crop, mm
V["crop_w"] = f0(CROP_W); V["crop_h"] = f0(CROP_H)
V["img_w"] = f1(CROP_W * M / 1000); V["img_h"] = f1(CROP_H * M / 1000)
V["d_eye_img"] = f1((abs(V_PAR) + O.EYE_Z) / 1000)
V["fov_lens_w"] = f1(2 * deg(math.atan(CROP_W * M / 2 / abs(V_PAR))))
V["fov_lens_h"] = f1(2 * deg(math.atan(CROP_H * M / 2 / abs(V_PAR))))

# ---- Equivalent bulk lens: why a Fresnel ------------------------------------------------
R_PCX = O.F * (O.N_D - 1)                                 # plano-convex sphere with the same focal length
V["r_pcx"] = f0(R_PCX)
V["pcx_max_d"] = f0(2 * R_PCX)
# continuous asphere the facets replace: integrate the slope
r_ = O.R_TAB; sag = -np.concatenate([[0], np.cumsum(np.tan(O.G_TAB[1:]) * np.diff(r_))])
D["asphere_r"] = r_; D["asphere_sag"] = sag
V["asph_sag_edge"] = f0(-np.interp(O.HALF, r_, sag))
V["asph_sag_corner"] = f0(-np.interp(O.HALF * math.sqrt(2), r_, sag))
RHO_PMMA = 1.18                                           # g/cm3
vol = np.trapezoid(2 * np.pi * r_[r_ <= O.HALF] * (-sag[r_ <= O.HALF] + sag[r_ <= O.HALF][-1] * 0 + 0), r_[r_ <= O.HALF])
V["bulk_kg"] = f1((-np.interp(O.HALF, r_, sag) * math.pi * O.HALF ** 2 - vol) / 1e6 * RHO_PMMA + 0)  # placeholder, replaced below
# solid of revolution under the sag curve, out to r = 150 mm, plus nothing else (lower bound)
inner = np.trapezoid(2 * np.pi * r_[r_ <= O.HALF] * (sag[r_ <= O.HALF] - np.interp(O.HALF, r_, sag)), r_[r_ <= O.HALF])
V["bulk_kg"] = f1(inner / 1e3 * RHO_PMMA / 1e3)
V["sheet_g"] = f0(300 * 300 * O.T / 1e3 * RHO_PMMA)

# facet geometry table at sample radii
FACET_R = [10, 50, 100, 150, 212]
D["facet_rows"] = [(r, float(O.facet_angle_deg(r)), float(O.groove_depth(r)), int(r / O.PITCH)) for r in FACET_R]
for r, a, h, k in D["facet_rows"]:
    V[f"fa_{r}"] = f1(a); V[f"fd_{r}"] = f"{h:.2f}"; V[f"fk_{r}"] = f0(k)
V["n_grooves_edge"] = f0(O.HALF / O.PITCH)
V["n_grooves_corner"] = f0(O.HALF * math.sqrt(2) / O.PITCH)
D["facet_curve"] = [(r, float(O.facet_angle_deg(r)), float(O.groove_depth(r))) for r in np.linspace(0, 212, 107)]

# one-facet worked example at r = 100 mm, Stage 1 direction (panel to eye)
def facet_example(r=100.0):
    """Chief-like ray from the panel axis point through radius r, then out through the facet."""
    P = np.array([[0.0, 0.0, O.Z_PANEL]])
    # aim at r on the flat face
    d = O.unit(np.array([[r, 0.0, O.Z_PANEL * -1 - O.T]]))
    fw = O.trace_forward(P, d)
    a_air = deg(math.atan2(d[0, 0], d[0, 2]))
    inside = O.unit(fw["P2"] - fw["P1"])[0]
    a_in = deg(math.atan2(inside[0], inside[2]))
    a_out = deg(math.atan2(fw["d"][0, 0], fw["d"][0, 2]))
    g = float(O.facet_angle_deg(np.hypot(fw["P2"][0, 0], fw["P2"][0, 1])))
    return dict(a_air=a_air, a_in=a_in, a_out=a_out, g=g, i_fac=fw["inc2"][0], r_fac=fw["inc2"][0],
                T=float(fw["T"][0]), r_exit=float(fw["P2"][0, 0]))
FX = facet_example()
D["facet_example"] = FX
V["fx_air"] = f1(FX["a_air"]); V["fx_in"] = f1(FX["a_in"]); V["fx_out"] = f2(FX["a_out"]); V["fx_g"] = f1(FX["g"])
V["fx_dev"] = f1(FX["a_air"] - FX["a_out"])
V["fx_T"] = f"{FX['T']*100:.1f}%"
# angle of incidence on the facet from inside, and exit angle to the facet normal
V["fx_i"] = f1(FX["g"] - FX["a_in"]); V["fx_e"] = f1(FX["g"] - FX["a_out"])
V["crit"] = f1(deg(math.asin(1 / O.N_D)))

# ---- Field of view, as seen from the eye (traced) ------------------------------------------
def field_for_panel(x_target, axis=0, eye=(0, 0, O.EYE_Z)):
    lo, hi = 0.0, 20.0
    for _ in range(50):
        m = 0.5 * (lo + hi)
        ax, ay = (m, 0.0) if axis == 0 else (0.0, m)
        b = O.panel_point(np.array([ax]), np.array([ay]), eye)
        x = abs(b["P3"][0, axis])
        lo, hi = (m, hi) if x < x_target else (lo, m)
    return 0.5 * (lo + hi)
HFW = field_for_panel(CROP_W / 2, 0); HFH = field_for_panel(CROP_H / 2, 1)
V["fov_eye_w"] = f1(2 * HFW); V["fov_eye_h"] = f1(2 * HFH)
V["hfw"] = f1(HFW); V["hfh"] = f1(HFH)
PITCH_MON = 25.4 / 277                                    # plan: YODOIT 16-inch 4K, 277 ppi
PITCH_55 = PC.PITCH_5                                     # plan: 5.5-inch kit pitch
V["px_mon"] = f0(CROP_W / PITCH_MON); V["px_55"] = f0(CROP_W / PITCH_55)
V["ppd_mon_eye"] = f0(CROP_W / PITCH_MON / (2 * HFW)); V["ppd_55_eye"] = f0(CROP_W / PITCH_55 / (2 * HFW))
V["ppd_mon_lens"] = f0(CROP_W / PITCH_MON / (2 * deg(math.atan(CROP_W * M / 2 / abs(V_PAR)))))
V["arcmin_px_55"] = f2(60 / (CROP_W / PITCH_55 / (2 * HFW)))
V["arcmin_px_mon"] = f2(60 / (CROP_W / PITCH_MON / (2 * HFW)))
# eye-distance table (ASSUMED 700 mm; 600 and 800 for comparison)
rows = []
for ez in (600.0, 700.0, 800.0):
    w = field_for_panel(CROP_W / 2, 0, (0, 0, ez)); h = field_for_panel(CROP_H / 2, 1, (0, 0, ez))
    ebx = O.HALF - ez * math.tan(rad(w)); eby = O.HALF - ez * math.tan(rad(h))
    rows.append((ez, 2 * w, 2 * h, (abs(V_PAR) + ez) / 1000, CROP_W / PITCH_MON / (2 * w), 2 * ebx, 2 * eby))
D["eye_rows"] = rows
V["eyebox_w"] = f0(rows[1][5]); V["eyebox_h"] = f0(rows[1][6])
V["chief_h_edge"] = f0(O.EYE_Z * math.tan(rad(HFW)))
V["chief_v_edge"] = f0(O.EYE_Z * math.tan(rad(HFH)))

# ---- Image distance: sensitivity, tolerance, temperature ----------------------------------
us = np.linspace(255, 299, 221)
D["v_of_u"] = [(u, abs(O.paraxial_v(O.F, u))) for u in us]
V["dvdu"] = f0(M ** 2)
V["diopt_per_mm"] = f"{1000 / O.U ** 2:.4f}"
V["diopt_eye"] = f2(1000 / (abs(V_PAR) + O.EYE_Z))
tol = []
for p in (-5, -2, 0, 2, 5):
    f = O.F * (1 + p / 100)
    v = abs(O.paraxial_v(f, O.U)) if f > O.U else float("inf")
    u_set = f * abs(V_PAR) / (abs(V_PAR) + f)           # panel distance that restores v = 4.2 m
    tol.append((p, f, v, u_set))
D["tol"] = tol
for p, f, v, u_set in tol:
    k = {-5: "m5", -2: "m2", 0: "0", 2: "p2", 5: "p5"}[p]
    V[f"tol_f_{k}"] = f0(f); V[f"tol_v_{k}"] = f1(v / 1000); V[f"tol_u_{k}"] = f1(u_set)
    V[f"tol_d_{k}"] = f2(1000 / (v + O.EYE_Z))
ALPHA, DNDT = 70e-6, -1.05e-4                            # PMMA expansion and thermo-optic coefficient (approx.)
V["alpha"] = f0(ALPHA * 1e6); V["dndt"] = f"{DNDT*1e4:.2f}"
therm = []
for dT in range(-20, 61, 2):
    f = O.F * (1 + ALPHA * dT) * (O.N_D - 1) / (O.N_D - 1 + DNDT * dT)
    therm.append((dT, f, abs(O.paraxial_v(f, O.U * (1 + ALPHA * 0)))))
D["therm"] = therm
for dT in (10, 20, 40):
    f = O.F * (1 + ALPHA * dT) * (O.N_D - 1) / (O.N_D - 1 + DNDT * dT)
    V[f"th_f_{dT}"] = f1(f); V[f"th_v_{dT}"] = f2(abs(O.paraxial_v(f)) / 1000)
# registration consequences: parallax error per 50 mm of head offset when the assumed image distance is wrong
HEAD = 50.0
def parallax_err_deg(d_true, d_assumed, e=HEAD):
    return deg(e * abs(1 / d_true - 1 / d_assumed))
V["par_tol_p2"] = f2(parallax_err_deg(abs(O.paraxial_v(O.F * 1.02)) + O.EYE_Z, abs(V_PAR) + O.EYE_Z))
V["par_tol_m2"] = f2(parallax_err_deg(abs(O.paraxial_v(O.F * 0.98)) + O.EYE_Z, abs(V_PAR) + O.EYE_Z))
f40 = O.F * (1 + ALPHA * 40) * (O.N_D - 1) / (O.N_D - 1 + DNDT * 40)
V["par_th_40"] = f2(parallax_err_deg(abs(O.paraxial_v(f40)) + O.EYE_Z, abs(V_PAR) + O.EYE_Z))
V["par_30m"] = f2(parallax_err_deg(abs(V_PAR) + O.EYE_Z, 30000.0))
V["head"] = f0(HEAD)
# angular scale change per mm of panel distance
def ang_scale(f, u, ez=O.EYE_Z):
    v = abs(O.paraxial_v(f, u)); return v / (u * (v + ez))
V["scale_per_mm"] = f2((ang_scale(O.F, O.U - 1) / ang_scale(O.F, O.U) - 1) * 100)
V["scale_p2"] = f1((ang_scale(O.F * 1.02, O.U) / ang_scale(O.F, O.U) - 1) * 100)

# ---- Image surface across the field (exact trace) ----------------------------------------
gx = np.linspace(-HFW, HFW, 15); gy = np.linspace(-HFH, HFH, 9)
AX, AY = np.meshgrid(gx, gy)
ip = O.image_point(AX.ravel(), AY.ravel())
D["surf"] = dict(ax=AX, ay=AY, dt=ip["dt"].reshape(AX.shape), ds=ip["ds"].reshape(AX.shape))
ipc = O.image_point(np.array([0.0, HFW, 0.0, HFW]), np.array([0.0, 0.0, HFH, HFH]))
V["isurf_c"] = f1(ipc["dt"][0] / 1000)
V["isurf_w_t"] = f1(ipc["dt"][1] / 1000); V["isurf_w_s"] = f1(ipc["ds"][1] / 1000)
V["isurf_h_t"] = f1(ipc["dt"][2] / 1000); V["isurf_h_s"] = f1(ipc["ds"][2] / 1000)
V["isurf_k_t"] = f1(ipc["dt"][3] / 1000); V["isurf_k_s"] = f1(ipc["ds"][3] / 1000)
V["isurf_c_D"] = f2(1000 / ipc["dt"][0])
V["isurf_k_D_t"] = f2(1000 / ipc["dt"][3]); V["isurf_k_D_s"] = f2(1000 / ipc["ds"][3])
V["astig_D"] = f"{abs(1000/ipc['dt'][3] - 1000/ipc['ds'][3]):.3f}"
fl = np.linspace(0, HFW, 29)
ipr = O.image_point(fl, np.zeros_like(fl))
D["surf_line"] = list(zip(fl, ipr["dt"], ipr["ds"]))

# ---- Distortion (exact trace): field grid -> panel points ---------------------------------
gx = np.linspace(-HFW, HFW, 13); gy = np.linspace(-HFH, HFH, 7)
AX, AY = np.meshgrid(gx, gy)
b = O.panel_point(AX.ravel(), AY.ravel())
PX = b["P3"][:, 0].reshape(AX.shape); PY = b["P3"][:, 1].reshape(AX.shape)
# paraxial scale at the centre: panel mm per tan(field)
eps = 0.05
bc = O.panel_point(np.array([eps]), np.array([0.0]))
K = bc["P3"][0, 0] / math.tan(rad(eps))
D["dist"] = dict(ax=AX, ay=AY, px=PX, py=PY, K=K)
corner_ideal = K * math.tan(rad(HFW)), K * math.tan(rad(HFH))
bk = O.panel_point(np.array([HFW]), np.array([HFH]))
rad_ideal = math.hypot(*corner_ideal); rad_act = math.hypot(bk["P3"][0, 0], bk["P3"][0, 1])
V["dist_corner"] = f1((rad_act / rad_ideal - 1) * 100)
bw = O.panel_point(np.array([HFW]), np.array([0.0]))
V["dist_edge"] = f1((bw["P3"][0, 0] / corner_ideal[0] - 1) * 100)
V["dist_corner_mm"] = f1(rad_act - rad_ideal)
V["K"] = f1(K)

# ---- Lateral colour (exact trace for PMMA; paraxial for the comparison) --------------------
cols = []
for a in np.linspace(0, HFW, 15):
    xs = []
    for lam in O.LAM_RGB:
        bb = O.panel_point(np.array([a]), np.array([0.0]), lam=lam)
        xs.append(bb["P3"][0, 0])
    # angular spread: panel offset divided by the local panel mm per degree
    bb1 = O.panel_point(np.array([a + 0.01]), np.array([0.0]))
    bb0 = O.panel_point(np.array([a]), np.array([0.0]))
    mm_per_deg = (bb1["P3"][0, 0] - bb0["P3"][0, 0]) / 0.01
    cols.append((a, (xs[2] - xs[0]) / mm_per_deg, (xs[1] - xs[0]) / mm_per_deg, xs))
D["lat_col"] = cols
V["lc_edge"] = f2(abs(cols[-1][1])); V["lc_half"] = f2(abs(cols[7][1]))
V["lc_edge_px"] = f0(abs(cols[-1][1]) * CROP_W / PITCH_55 / (2 * HFW))
V["lc_edge_px_mon"] = f0(abs(cols[-1][1]) * CROP_W / PITCH_MON / (2 * HFW))
V["lc_edge_arcmin"] = f0(abs(cols[-1][1]) * 60)
def paraxial_lc(nfun, a_deg, ez=O.EYE_Z):
    h = ez * math.tan(rad(a_deg)); dev = h / O.F
    nb, ng, nr = float(nfun(0.45)), float(nfun(0.53)), float(nfun(0.62))
    return deg(dev * (nb - nr) / (ng - 1))
D["lc_mat"] = {name: [(a, paraxial_lc(fn, a)) for a in np.linspace(0, HFW, 15)]
               for name, fn in (("PMMA", O.n_pmma), ("BK7 glass", O.n_bk7), ("Polycarbonate", O.n_pc))}
def abbe(fn):
    return (float(fn(0.5876)) - 1) / (float(fn(0.4861)) - float(fn(0.6563)))
V["abbe_pmma"] = f0(abbe(O.n_pmma)); V["abbe_bk7"] = f0(abbe(O.n_bk7)); V["abbe_pc"] = f0(abbe(O.n_pc))
V["lc_par_pmma"] = f2(paraxial_lc(O.n_pmma, HFW)); V["lc_par_bk7"] = f2(paraxial_lc(O.n_bk7, HFW)); V["lc_par_pc"] = f2(paraxial_lc(O.n_pc, HFW))
for lam, k in zip(O.LAM_RGB, "rgb"):
    V[f"n_{k}"] = f"{float(O.n_pmma(lam)):.4f}"

# ---- Pupil footprint, groove blur, diffraction --------------------------------------------
def footprint(pupil, ez=O.EYE_Z, d_img=abs(V_PAR)):
    return pupil * d_img / (d_img + ez)
V["fp_3"] = f1(footprint(3)); V["fp_4"] = f1(footprint(4)); V["fp_6"] = f1(footprint(6))
V["fp_g_4"] = f0(footprint(4) / O.PITCH); V["fp_g_6"] = f0(footprint(6) / O.PITCH)
V["groove_arcmin"] = f1(deg(O.PITCH / O.EYE_Z) * 60)
V["defocus_D"] = f2(1000 / O.EYE_Z - 1000 / (abs(V_PAR) + O.EYE_Z))
V["blur_arcmin_4"] = f0(deg(0.004 * (1 / 0.7 - 1 / ((abs(V_PAR) + O.EYE_Z) / 1000))) * 60)
def j1(x):
    t = np.linspace(0, np.pi, 2001)
    return np.trapezoid(np.cos(t - x * np.sin(t)), t) / np.pi
def disk_mtf(freq_cyc_per_mm, blur_d_mm):
    x = np.pi * freq_cyc_per_mm * blur_d_mm
    return 1.0 if x == 0 else abs(2 * j1(x) / x)
def diff_fwhm_arcmin(pitch, lam_um=0.53):
    return deg(0.886 * lam_um * 1e-3 / pitch) * 60
pitches = np.linspace(0.1, 1.5, 57)
D["pitch_trade"] = [(p, diff_fwhm_arcmin(p), disk_mtf(1 / p, footprint(4)), disk_mtf(1 / p, footprint(6))) for p in pitches]
for p, k in ((0.25, "025"), (0.5, "05"), (1.0, "1")):
    V[f"diff_{k}"] = f1(diff_fwhm_arcmin(p)); V[f"mtf4_{k}"] = f"{disk_mtf(1/p, footprint(4))*100:.1f}%"
    V[f"mtf6_{k}"] = f"{disk_mtf(1/p, footprint(6))*100:.1f}%"
V["diff_05_px"] = f1(diff_fwhm_arcmin(0.5) / (60 / (CROP_W / PITCH_55 / (2 * HFW))))
V["eye_limit"] = "1"

# ---- Groove orientation: transmission and incidence across the aperture --------------------
orient = {}
for flipped in (False, True):
    rows = []
    for r in np.linspace(1, 212, 106):
        # ray from the panel axis point through radius r on the panel-side face
        P = np.array([[0.0, 0.0, O.Z_PANEL]])
        d = O.unit(np.array([[r, 0.0, -O.Z_PANEL - O.T]]))
        fw = O.trace_forward(P, d, flipped=flipped)
        rows.append((r, float(fw["T"][0]) if not fw["tir"][0] else 0.0, float(fw["inc1"][0]), float(fw["inc2"][0]),
                     bool(fw["tir"][0]), deg(math.atan2(fw["d"][0, 0], fw["d"][0, 2]))))
    orient["flipped" if flipped else "correct"] = rows
D["orient"] = orient
def at(rows, r):
    return min(rows, key=lambda q: abs(q[0] - r))
V["or_c_T100"] = f"{at(orient['correct'], 100)[1]*100:.1f}%"; V["or_f_T100"] = f"{at(orient['flipped'], 100)[1]*100:.1f}%"
V["or_c_T150"] = f"{at(orient['correct'], 150)[1]*100:.1f}%"; V["or_f_T150"] = f"{at(orient['flipped'], 150)[1]*100:.1f}%"
V["or_c_i150"] = f0(max(at(orient['correct'], 150)[2:4])); V["or_f_i150"] = f0(max(at(orient['flipped'], 150)[2:4]))
V["T_axis"] = f"{at(orient['correct'], 1)[1]*100:.1f}%"
# flipped lens: the on-axis image distance and off-axis behaviour
ipf = O.image_point(np.array([0.0, HFW]), np.array([0.0, 0.0]), flipped=True)
V["flip_c"] = f1(ipf["dt"][0] / 1000); V["flip_w_t"] = f1(ipf["dt"][1] / 1000); V["flip_w_s"] = f1(ipf["ds"][1] / 1000)
first_tir = [q[0] for q in orient["flipped"] if q[4]]
V["flip_tir_r"] = f0(first_tir[0]) if first_tir else "none"

# ---- Combiner ---------------------------------------------------------------------------
R_COMB, T_COMB = 0.30, 0.70                               # plan: teleprompter 70/30
LOOKDOWN = 5.0                                            # plan: look-down angle to the image centre
I_COMB = (180 - (90 - LOOKDOWN)) / 2                      # light arrives vertically, leaves toward the eye
V["i_comb"] = f1(I_COMB)
V["lookdown"] = f0(LOOKDOWN)
N_GL = 1.52
def ghost(tmm, i_deg=I_COMB, n=N_GL, dist=abs(V_PAR) + O.EYE_Z):
    tt = math.asin(math.sin(rad(i_deg)) / n)
    off = 2 * tmm * math.tan(tt) * math.cos(rad(i_deg))
    return off, deg(off / dist) * 60
for tmm in (3, 6):
    off, am = ghost(tmm); V[f"gh_off_{tmm}"] = f1(off); V[f"gh_am_{tmm}"] = f1(am)
# back-surface reflection of the uncoated side (unpolarised, internal angle)
tt = math.asin(math.sin(rad(I_COMB)) / N_GL)
rs = (math.sin(rad(I_COMB) - tt) / math.sin(rad(I_COMB) + tt)) ** 2
rp = (math.tan(rad(I_COMB) - tt) / math.tan(rad(I_COMB) + tt)) ** 2
R_BACK = 0.5 * (rs + rp)
GHOST_REL = T_COMB * R_BACK * T_COMB / R_COMB
V["r_back"] = f1(R_BACK * 100); V["ghost_rel"] = f0(GHOST_REL * 100)
V["rs_comb"] = f1(rs * 100); V["rp_comb"] = f1(rp * 100)
V["brewster"] = f1(deg(math.atan(N_GL)))

# ---- Luminance -----------------------------------------------------------------------------
T_LENS = at(orient["correct"], 1)[1]
DRAFT_LOSS = 0.05                                         # ASSUMED loss to draft facets and groove tips near the centre
PATH1 = T_LENS * (1 - DRAFT_LOSS) * R_COMB
V["path1"] = f0(PATH1 * 100) + "%"
V["draft_loss"] = f0(DRAFT_LOSS * 100) + "%"
lum = []
for name, lp in (("16-inch 4K monitor (plan Stage 0/1 panel)", 1200.0), ("5.5-inch kit, stock backlight", 450.0),
                 ("5.5-inch kit, custom backlight (design)", PC.L_PANEL_DESIGN)):
    lum.append((name, lp, lp * PATH1))
D["lum"] = lum
for i, (_, lp, le) in enumerate(lum):
    V[f"lum_{i}"] = f0(le)
SCENES = [("Night, headlit road", 1.0), ("Dusk", 100.0), ("Overcast day", 1000.0), ("Sunlit road", 5000.0), ("Bright sky / snow", 10000.0)]
D["scenes"] = SCENES
D["contrast"] = [[(lp * PATH1 + T_COMB * L) / (T_COMB * L) for _, L in SCENES] for _, lp, _ in lum]
V["night_dim"] = f0(lum[2][2] / 50.0)                     # plan: night ceiling 50 cd/m2 at the eye

# ---- Sun through the Stage 1 lens ---------------------------------------------------------
T_WS = 0.70                                               # plan: windshield transmission (ASSUMED)
SUN = 1000.0                                              # W/m2, clear sky
SUN_HALF = rad(0.2665)
def sun_spot(off_deg=0.0, n=241, through_comb=True):
    """Trace sunlight (a disk of directions) through the lens to the panel plane."""
    xs = np.linspace(-O.HALF, O.HALF, n)
    X, Y = np.meshgrid(xs, xs)
    X = X.ravel(); Y = Y.ravel()
    rng = np.random.default_rng(1)
    ph = rng.uniform(0, 2 * np.pi, X.size); rr = SUN_HALF * np.sqrt(rng.uniform(0, 1, X.size))
    a = rad(off_deg) + rr * np.cos(ph); b = rr * np.sin(ph)
    Dd = O.unit(np.stack([-np.tan(a), -np.tan(b), -np.ones_like(a)], -1))
    E = np.stack([X - Dd[:, 0] / Dd[:, 2] * 10, Y - Dd[:, 1] / Dd[:, 2] * 10, np.full_like(X, 10.0)], -1)
    E = np.stack([X, Y, np.zeros_like(X)], -1) - 10 * Dd
    tr = O.trace_backward(E, Dd)
    ok = ~tr["tir"]
    cell = (xs[1] - xs[0]) ** 2 * 1e-6                     # m2 per ray at normal incidence
    w = SUN * math.cos(rad(off_deg)) * cell * T_WS * (T_COMB if through_comb else 1.0) * tr["T"] * (1 - DRAFT_LOSS)
    return tr["P3"][ok, :2], w[ok]
def spot_stats(pts, w, bin_mm=1.0):
    c = np.average(pts, axis=0, weights=w)
    rr = np.hypot(pts[:, 0] - c[0], pts[:, 1] - c[1])
    order = np.argsort(rr); cw = np.cumsum(w[order]) / w.sum()
    r90 = rr[order][np.searchsorted(cw, 0.9)]
    H, xe, ye = np.histogram2d(pts[:, 0], pts[:, 1], bins=int(80 / bin_mm), range=[[c[0] - 40, c[0] + 40], [c[1] - 40, c[1] + 40]], weights=w)
    peak = H.max() / (bin_mm * 1e-3) ** 2
    return dict(c=c, r90=r90, peak=peak, total=w.sum(), H=H)
pts, w = sun_spot(0.0)
S0 = spot_stats(pts, w)
D["sun0"] = dict(pts=pts[::7], w=w[::7], stats=S0)
V["sun_W"] = f0(S0["total"]); V["sun_W_nocomb"] = f0(S0["total"] / T_COMB)
V["sun_r90"] = f0(S0["r90"]); V["sun_peak"] = f0(S0["peak"] / 1000)
V["sun_peak_suns"] = f0(S0["peak"] / SUN)
V["sun_focus_beyond"] = f0(O.F - O.U)
sun_off = []
for off in np.linspace(0, 40, 21):
    p_, w_ = sun_spot(off, n=121)
    st = spot_stats(p_, w_)
    sun_off.append((off, st["c"][0], st["r90"], st["peak"] / 1000, st["total"]))
D["sun_off"] = sun_off
V["sun_x_10"] = f0(abs(min(sun_off, key=lambda q: abs(q[0] - 10))[1]))
V["sun_x_20"] = f0(abs(min(sun_off, key=lambda q: abs(q[0] - 20))[1]))
V["sun_peak_20"] = f0(min(sun_off, key=lambda q: abs(q[0] - 20))[3])
V["sun_peak_30"] = f0(min(sun_off, key=lambda q: abs(q[0] - 30))[3])
V["tw_peak"] = "40"; V["bmw_peak"] = "12"                 # plan: TI production peak, BMW TFT test

# ---- In-car layout (ASSUMED, for the figures) ------------------------------------------------
EYE_COMB = 550.0                                          # eye to combiner centre
COMB_LENS = O.EYE_Z - EYE_COMB                            # combiner to lens, vertical
V["eye_comb"] = f0(EYE_COMB); V["comb_lens"] = f0(COMB_LENS)
CAR = dict(eye=(0.0, 0.0), comb=(EYE_COMB * math.cos(rad(LOOKDOWN)), -EYE_COMB * math.sin(rad(LOOKDOWN))),
           dash_z=-300.0, cowl=(1400.0, -360.0), rake=28.0, road_z=-1200.0)
CAR["lens"] = (CAR["comb"][0], CAR["comb"][1] - COMB_LENS)
CAR["panel_unfolded"] = (CAR["comb"][0], CAR["lens"][1] - O.U)
D["car"] = CAR
V["lens_below_dash"] = f0(-(CAR["panel_unfolded"][1] - CAR["dash_z"]))
V["lens_above_dash"] = f0(CAR["lens"][1] - CAR["dash_z"])
V["img_above_road"] = f2((-(abs(V_PAR) + O.EYE_Z) * math.sin(rad(LOOKDOWN)) - CAR["road_z"]) / 1000)
V["img_ahead"] = f1((abs(V_PAR) + O.EYE_Z) * math.cos(rad(LOOKDOWN)) / 1000)

if __name__ == "__main__":
    for k in sorted(V):
        print(f"{k:18s} {V[k]}")

# ---- Exact eye box (bisection with the traced edge rays) -------------------------------------
def _edge_angle(e, target, axis):
    lo, hi = -25.0, 25.0
    for _ in range(50):
        m = 0.5 * (lo + hi)
        eye = (e, 0, O.EYE_Z) if axis == 0 else (0, e, O.EYE_Z)
        ax_, ay_ = (np.array([m]), np.array([0.0])) if axis == 0 else (np.array([0.0]), np.array([m]))
        b = O.panel_point(ax_, ay_, eye)
        x = b["P3"][0, axis]
        lo, hi = (m, hi) if x < target else (lo, m)
    return 0.5 * (lo + hi), b
def eyebox_half(axis, half_crop):
    lo, hi = 0.0, 200.0
    for _ in range(40):
        m = 0.5 * (lo + hi)
        a, b = _edge_angle(m, half_crop, axis)
        hit = b["P1"][0, axis]
        lo, hi = (m, hi) if abs(hit) <= O.HALF else (lo, m)
    return 0.5 * (lo + hi)
EBX = eyebox_half(0, CROP_W / 2); EBY = eyebox_half(1, CROP_H / 2)
V["eyebox_w"] = f0(2 * EBX); V["eyebox_h"] = f0(2 * EBY)
D["eyebox"] = (EBX, EBY)

# ---- Groove-level trace numbers (teeth.py) -----------------------------------------------------
import teeth as TT
def _eye_stats(r, n=2000):
    _, rays = TT.eye_fan(float(r), nrays=n)
    clean = [x for x in rays if not x["walls"]]
    x0 = float(np.median([x["land"] for x in clean if x["land"] is not None]))
    far = sum(1 for x in rays if x["walls"] and x["land"] is not None and abs(x["land"] - x0) >= 2) / n
    lost = sum(1 for x in rays if x["walls"] and (x["land"] is None or abs(x["land"] - x0) < 2)) / n
    return len(clean) / n, far, lost, x0
EYE_STATS = [(r, math.degrees(math.atan(r / O.EYE_Z))) + _eye_stats(r) for r in range(10, 131, 5)]
D["eye_stats"] = EYE_STATS
for r, a, cl, far, lost, x0 in EYE_STATS:
    if r in (30, 60, 90):
        V[f"eyeclean_{r}"] = f"{cl*100:.0f}%"; V[f"eyefar_{r}"] = f"{far*100:.0f}%"; V[f"eyelost_{r}"] = f"{lost*100:.0f}%"
        V[f"eyeang_{r}"] = f1(a)
FWD = {fl: TT.survey(fl, radii=np.arange(10, 211, 10), nrays=300) for fl in (False, True)}
D["fwd_survey"] = FWD
def _fw(fl, r):
    return min(FWD[fl], key=lambda q: abs(q[0] - r))
V["fw_c_100"] = f"{_fw(False,100)[1]*100:.0f}%"; V["fw_f_100"] = f"{_fw(True,100)[1]*100:.0f}%"
V["fw_c_150"] = f"{_fw(False,150)[1]*100:.0f}%"; V["fw_f_150"] = f"{_fw(True,150)[1]*100:.0f}%"
V["fw_c_200"] = f"{_fw(False,200)[1]*100:.0f}%"; V["fw_f_200"] = f"{_fw(True,200)[1]*100:.0f}%"
V["flip_astig_D"] = f2(abs(1000 / (float(V["flip_w_t"]) * 1000) - 1000 / (float(V["flip_w_s"]) * 1000)))

# ---- The custom backlight's 60 x 30 mm crop in Stage 1 (plan 7.5 lights only that area) -----------
HFW60 = field_for_panel(30.0, 0); HFH60 = field_for_panel(15.0, 1)
V["fov60_w"] = f1(2 * HFW60); V["fov60_h"] = f1(2 * HFH60)
V["bl_area_ratio"] = f2((80 * 40) / (60 * 30))
# eye-distance table as text values
for ez, fw, fh, dist, ppd, ebw, ebh in D["eye_rows"]:
    k = f"{ez:.0f}"
    V[f"er_fov_{k}"] = f"{fw:.1f}° × {fh:.1f}°"; V[f"er_d_{k}"] = f1(dist); V[f"er_ppd_{k}"] = f0(ppd)
    V[f"er_eb_{k}"] = f"{ebw:.0f} × {ebh:.0f}"
V["v_295"] = f1(abs(O.paraxial_v(O.F, 295.0)) / 1000)
V["edge_extra_m"] = f1(float(V["isurf_k_s"]) - float(V["isurf_c"]))

# ---- Flat (conical) facets versus curved facets: the image sawtooth across each groove ---------------
def _sawtooth(nfacet, r0=50.0):
    orig = TT.profile
    TT.profile = lambda ra, rb, pitch=O.PITCH, draft_deg=0.0, nfacet_=nfacet: orig(ra, rb, pitch, draft_deg, nfacet_)
    try:
        _, rays = TT.eye_fan(r0, width=2.0, nrays=161, margin=6)
    finally:
        TT.profile = orig
    a = np.array([q["aim"] for q in rays if not q["walls"] and q["land"] is not None])
    l = np.array([q["land"] for q in rays if not q["walls"] and q["land"] is not None])
    res = l - np.polyval(np.polyfit(a, l, 1), a)
    return math.degrees((res.max() - res.min()) / K) * 60
FLAT_BLUR = _sawtooth(2); CURVED_RES = _sawtooth(40)
V["flat_blur"] = f1(FLAT_BLUR); V["curved_res"] = f1(CURVED_RES)
V["flat_blur_px"] = f0(FLAT_BLUR / float(V["arcmin_px_55"]))
V["p_over_f"] = f1(math.degrees(O.PITCH / O.F) * 60)
D["pitch_flat"] = [(p, FLAT_BLUR * p / O.PITCH) for p, *_ in D["pitch_trade"]]
pp = np.linspace(0.1, 1.5, 1401)
best = pp[np.argmin(np.maximum([diff_fwhm_arcmin(p) for p in pp], FLAT_BLUR * pp / O.PITCH))]
V["p_best_flat"] = f2(best); V["blur_best_flat"] = f1(FLAT_BLUR * best / O.PITCH)

# ---- Distortion in angle, and the colour left after per-channel correction ----------------------------
_a, _b = None, None
def _seen_corner():
    """Field angle at which the centred eye sees the crop corner (Newton on the backward trace)."""
    ax, ay = math.degrees(math.atan(40 / K)), math.degrees(math.atan(20 / K))
    for _ in range(12):
        b0 = O.panel_point(np.array([ax]), np.array([ay]))
        ex, ey = b0["P3"][0, 0] - 40, b0["P3"][0, 1] - 20
        h = 1e-3
        bx = O.panel_point(np.array([ax + h]), np.array([ay])); by = O.panel_point(np.array([ax]), np.array([ay + h]))
        j = np.array([[(bx["P3"][0, 0] - b0["P3"][0, 0]) / h, (by["P3"][0, 0] - b0["P3"][0, 0]) / h],
                      [(bx["P3"][0, 1] - b0["P3"][0, 1]) / h, (by["P3"][0, 1] - b0["P3"][0, 1]) / h]])
        dx = np.linalg.solve(j, [ex, ey]); ax -= dx[0]; ay -= dx[1]
    return ax, ay
_sx, _sy = _seen_corner()
V["dist_corner_mm_deg"] = f2(math.hypot(_sx, _sy) - math.hypot(math.degrees(math.atan(40 / K)), math.degrees(math.atan(20 / K))))
BANDS = {"blue": (0.430, 0.470), "green": (0.500, 0.560), "red": (0.595, 0.645)}     # LCD colour-filter passbands (ASSUMED)
_full = float(O.n_pmma(0.45) - O.n_pmma(0.62))
_res = max(float(O.n_pmma(lo) - O.n_pmma(hi)) for lo, hi in BANDS.values()) / _full
V["lc_resid_frac"] = f"{_res*100:.0f}%"
V["lc_resid"] = f2(_res * float(V["lc_edge"]))
V["dist_corner_mm_abs"] = V["dist_corner_mm"].lstrip("-"); V["dist_corner_abs"] = V["dist_corner"].lstrip("-")
V["dist_edge_abs"] = V["dist_edge"].lstrip("-")
V["dim_edge"] = f"{100 - float(V['eyeclean_90'].rstrip('%')):.0f}%"

# ---- Ghosts measured in the Cycles eye render (blender/measure_ghosts.py) --------------------------------
_gp = os.path.join(HERE, "blender", "renders", "ghosts.json")
if os.path.exists(_gp):
    import json as _json
    _g = _json.load(open(_gp))["regions"]
    V["ghost_line"] = f"{max(_g['lane ghost UL']['of_white'], _g['lane ghost UL2']['of_white'])*100:.1f}%"
    V["ghost_area"] = f"{max(_g['ribbon ghost']['of_ribbon'], _g['ribbon ghost2']['of_ribbon'])*100:.0f}%"
    V["ghost_corner"] = f"{max(_g['blob BL2']['of_white'], _g['blob BR']['of_white'])*100:.1f}%"
    V["veil_black"] = f"{_g['black reference']['of_white']*100:.1f}%"
else:
    V["ghost_line"] = V["ghost_area"] = V["ghost_corner"] = V["veil_black"] = "??"
_worst = max(D["sun_off"], key=lambda q: q[3])
V["sun_worst"] = f0(_worst[3]); V["sun_worst_ang"] = f0(_worst[0])
