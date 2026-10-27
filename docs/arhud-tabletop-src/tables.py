"""Tables generated from calc.py's lists, so the document's tables cannot drift from its numbers."""
import tcalc as C

TABLES = {}


def tbl(name):
    def deco(fn):
        TABLES[name] = fn
        return fn
    return deco


def table(head, rows, widths=None, cls="tight"):
    th = "".join(f'<th{' class="num"' if h.startswith("#") else ""}{f' style="width:{w}"' if widths and widths[i] else ""}>{h.lstrip("#")}</th>'
                 for i, (h, w) in enumerate(zip(head, widths or [None] * len(head))))
    body = []
    for row in rows:
        tds = []
        for h, c in zip(head, row):
            tds.append(f'<td{' class="num"' if h.startswith("#") else ""}>{c}</td>')
        body.append("<tr>" + "".join(tds) + "</tr>")
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table>'


@tbl("dist")
def dist():
    rows = []
    for di, de, hf, vf, ww, wh, pw, ph, ppd in C.DIST_TABLE:
        mark = " (design)" if abs(di - C.D_IMG) < 1 else ""
        rows.append((f"{di:.0f}{mark}", f"{de:.0f}", f"{hf:.1f}° × {vf:.1f}°", f"{ww:.0f} × {wh:.0f}", f"{pw:,.0f} × {ph:,.0f}", f"{ppd:.0f}"))
    return table(["#Eye to image (mm)", "#Eye to glass (mm)", "Road field shown, life size", "#Window on the monitors (mm)", "#Window (px)", "#px per degree"], rows)


@tbl("sources")
def sources():
    rows = []
    for name, w, h, f, hfov, fps, crop, up, win, note in C.SRC_TABLE:
        rows.append((name, f"{w} × {h}", f"{f:,.0f}", f"{hfov:.1f}°", f"{fps}", f"{crop:,.0f}", f"× {up:.1f}", f"{win:,.0f}", note))
    return table(["Source", "#Frame (px)", "#f (px)", "#Field", "#Hz", "#Crop (px)", "#Scale", "#Window (px)", "What it gives"], rows,
                 widths=["27%", None, None, None, None, None, None, None, "27%"])


@tbl("cond")
def cond():
    rows = []
    for label, l_eye, l_bg, ratio, gain, ok in C.COND_TABLE:
        rows.append((label, f"{l_eye:,.0f}", f"{l_bg:,.0f}", f"{ratio:.2f}" if ratio < 1.05 or ratio > 1.3 else f"{ratio:.3f}", f"{gain:.2f}" if gain >= 0.1 else f"{gain:.3f}", "yes" if ok == "yes" else "no: beyond the monitor"))
    return table(["Condition in the car", "#HUD at eye", "#Background", "#Ratio", "#Bench gain", "On the bench"], rows,
                 widths=["40%", None, None, None, None, "18%"])


@tbl("parallax")
def parallax():
    rows = []
    for z, dl, ang in C.PAR_TABLE:
        zs = "infinity" if z == float("inf") else f"{z:.0f} m"
        rows.append((zs, f"{dl:.1f}", f"{ang:.2f}°"))
    rows.append(("(no car equivalent)", "100", f"{C.V['par_100']}°"))
    rows.append(("(no car equivalent)", "300", f"{C.V['par_300']}°"))
    return table(["Road point in the car (image at 7.5 m)", "#Δ on the bench (mm)", f"#Angle per {C.V['sway']} mm of sway"], rows)


@tbl("latency")
def latency():
    rows = [(lab, f"{a}", f"{b}") for lab, a, b in C.BENCH_LAT]
    rows.append(("<b>Total, road photon to HUD photon</b>", f"<b>{C.V['lat_bench_min']}</b>", f"<b>{C.V['lat_bench_max']}</b>"))
    rows.append(("Plan's car chain, for comparison (camera exposure to panel)", C.V["lat_plan_min"], C.V["lat_plan_max"]))
    return table(["Stage", "#min (ms)", "#max (ms)"], rows, widths=["70%", None, None])


@tbl("gpu")
def gpu():
    rows = [(lab, f"{a}", f"{b}") for lab, a, b in C.GPU_MAC]
    rows.append(("<b>Serial total on the M4 (assumed)</b>", f"<b>{C.V['gpu_mac_min']}</b>", f"<b>{C.V['gpu_mac_max']}</b>"))
    return table(["Job per frame on the MacBook Pro M4", "#min (ms)", "#max (ms)"], rows, widths=["70%", None, None])


@tbl("bom")
def bom():
    rows = [(item, f"{lo:,}" if lo else "0", f"{hi:,}" if hi else "0", basis) for item, lo, hi, basis in C.BOM]
    rows.append(("<b>Total of new purchases</b>", f"<b>{C.V['bom_lo']}</b>", f"<b>{C.V['bom_hi']}</b>", ""))
    return table(["Item", "#Low (USD)", "#High (USD)", "Basis"], rows, widths=["48%", None, None, "30%"])


@tbl("rows")
def rows_():
    rows = []
    for key, lab in (("c2k", "comma2k19 (f = 910 px)"), ("c3", "comma three (f = 2,648 px)")):
        rows.append((lab, C.V[f"row_{key}_10"], C.V[f"dz_{key}_10"], C.V[f"row_{key}_20"], C.V[f"dz_{key}_20"], C.V[f"row_{key}_30"], C.V[f"dz_{key}_30"]))
    return table(["Camera", "#Rows below the horizon at 10 m", "#m per row", "#at 20 m", "#m per row", "#at 30 m", "#m per row"], rows)


@tbl("accept")
def accept():
    rows = [
        ("T-A rig", "Test card reads correctly; parallax check: cross on the PGU and cross on the road monitor separate by ≤ " + C.V["cop_tol_px"] + f" px over a {C.V['e_shift']} mm eye shift (planes within {C.V['cop_tol_mm']} mm)", "eye camera, two photographs"),
        ("T-C displays", "Both monitors at 3,840 × 2,400, 60 Hz, native pixels, no scaling, no auto-brightness; each full-screen window on its own monitor", "screenshot and the monitor's own menu"),
        ("T-E calibration", f"Homography residual ≤ {C.V['t_cal_px']} px RMS ({C.V['t_cal_deg']}°) over the whole window; flip correct", "eye camera, one photograph"),
        ("T-D perception", "Plan §5.7 on 300 MetaDrive frames with truth: ego lane found ≥ 95%; lateral error ≤ 0.15 m at 10 m, 0.30 at 20, 0.50 at 30; vehicles within 50 m ≥ 90%; pedestrians within 30 m ≥ 85%", "scored against truth"),
        ("T-E sync modes", f"Truth-fed: drawn lane line within {C.V['t_reg_deg']}° ({C.V['t_reg_px']} px) of the painted line's truth on the road monitor at 10, 20 and 30 m, median over a 24 s MetaDrive drive. Perception-fed: the same residual reported, expected within the §5.7 angles ({C.V['lat_10_deg']}°, {C.V['lat_20_deg']}°, {C.V['lat_30_deg']}°)", "hudd's own residual against truth"),
        ("T-F live mode", f"hudd at 60 fps with no dropped frames for 10 min; road photon to HUD photon ≤ {C.V['t_lat']} ms (median and 95th); prediction sign confirmed with the +200 ms test; lead chevron 95th-percentile residual with compensation below the value without", "photodiode pair; residual log"),
        ("T-G photometry", f"Measured contrast at the eye within ±10% of the set condition for ratios {C.V['cr_plan_min']}, {C.V['cr_bl_sky']} and {C.V['cr_bl_road']}; ghost ≤ 2% of the main image or documented", "spot meter or calibrated camera"),
        ("T-H parallax variant", f"With Δ = {C.V['delta_20']} mm and ±{C.V['sway']} mm sway: residual ≤ {C.V['par_crit']}° with the tracker on; the same test with it off fails (≈ {C.V['par_20']}°)", "eye camera on a rail"),
        ("T-I camera loop", "Camera-to-monitor homography ≤ 2 px; lane residual through the camera within 0.05° of the direct path; latency through the camera measured", "as above, with the loop camera"),
    ]
    return table(["Stage", "Passes when", "Measured by"], rows, widths=["14%", "62%", None])
