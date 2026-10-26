"""Sun focus: where sunlight that enters the housing ends up, by a deterministic ray bundle.

The plan's hazard figure (42 W collected by the mirror, 5.5 W reaching a 3.2 mm spot on the panel after the cold
mirror, the IR-cut glass and the polariser, about 170 kW/m2) comes from the mirror equation. This script traces a
bundle of parallel rays (the sun, with its 0.53 deg disc) through the real geometry in layout.json: the laminated
windshield (refraction offsets), the housing lid aperture, the 300 x 200 mm mirror as a true toroid or sphere, the
cold-mirror fold as the housing sizes it, down to the panel plane. It reports the irradiance footprint on the panel
for the plan's nominal sun (51 deg elevation behind the car) and scans sun directions to map the entry patch: the set
of sun directions from which focused light lands on the crop. A path tracer cannot render this (a reflective caustic
of a delta light), so it is a numeric trace, not a Cycles render.

Outputs (default docs/arhud-sim/assets/cycles/): sun_focus.json, sun_spot.png, sun_patch.png.

Run:  python3 sun_focus.py [out=DIR] [mode=toroid|sphere] [fine=1]   (numpy only; Blender not needed)
"""
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = [a for a in sys.argv[1:] if "=" in a]
def arg(key, default, cast=str):
    for a in ARGS:
        if a.startswith(key + "="):
            return cast(a[len(key) + 1:])
    return default
OUT = arg("out", os.path.normpath(os.path.join(HERE, "..", "arhud-sim", "assets", "cycles")))
MODE = arg("mode", "toroid")
FINE = arg("fine", 1, int)
os.makedirs(OUT, exist_ok=True)

with open(os.path.join(HERE, "layout.json")) as f:
    L = json.load(f)
RAW = L["params"]["raw"]
A = lambda p: np.array(p, dtype=np.float64)
norm = lambda v: v / np.linalg.norm(v, axis=-1, keepdims=True)

# ---- surfaces (simulator frame: X forward, Y up, Z right) -------------------------------------------------------
M = L["mirror"]
MC, MN, MU, MV = A(M["C"]), A(M["N"]), A(M["U"]), A(M["V"])
Rt, Rs = M[MODE]["Rt"], M[MODE]["Rs"]
MW, MH = M["W"], M["H"]
G, GN, GT = A(L["glass"]["G"]), A(L["glass"]["N"]), L["glass"]["T"]
N_GLASS = L["glass"]["nGlass"]
FC, FN = A(L["fold"]["C"]), A(L["fold"]["N"])
FF = L["foldFrame"]
FU, FV = A(FF["fu"]), A(FF["fv"])
PC = A(L["panel"]["C"])
CROP_Z, CROP_X = L["panel"]["cropZ"], L["panel"]["cropX"]
CELL_Z, CELL_X = RAW["PANEL_W"] / 1000, RAW["PANEL_H"] / 1000
HL = L["housingLayout"]
LID_N = norm(A([HL["s"], 1.0, 0.0]))
LID_P = A([HL["xF"], HL["yF"], 0.0])
SUN_IRR = 1000.0                                  # W/m2, direct normal


def sag(u, v):
    if abs(Rt - Rs) < 1e-9:
        return Rt - np.sqrt(Rt * Rt - u * u - v * v)
    inner = Rt - Rs + np.sqrt(np.clip(Rs * Rs - u * u, 0, None))
    return Rt - np.sqrt(np.clip(inner * inner - v * v, 0, None))


def mirror_normal(u, v, h=1e-6):
    du = (sag(u + h, v) - sag(u - h, v)) / (2 * h)
    dv = (sag(u, v + h) - sag(u, v - h)) / (2 * h)
    n = MN[None, :] - du[:, None] * MU[None, :] - dv[:, None] * MV[None, :]
    return norm(n)


def hit_mirror(o, d):
    """Rays o + t d against the mirror surface w = sag(u, v) (w along MN). Returns p, n, inside, ok."""
    rel = o - MC
    ou, ov, ow = rel @ MU, rel @ MV, rel @ MN
    du, dv, dw = d @ MU, d @ MV, d @ MN
    # paraboloid start
    a = du * du / (2 * Rs) + dv * dv / (2 * Rt)
    b = ou * du / Rs + ov * dv / Rt - dw
    c = ou * ou / (2 * Rs) + ov * ov / (2 * Rt) - ow
    disc = b * b - 4 * a * c
    ok = disc >= 0
    s = np.sqrt(np.clip(disc, 0, None))
    with np.errstate(divide="ignore", invalid="ignore"):
        t1 = (-b - s) / (2 * a)
        t2 = (-b + s) / (2 * a)
        tlin = -c / b
    t = np.where(np.abs(a) < 1e-12, tlin, np.where(t1 > 1e-6, t1, t2))
    ok &= t > 1e-6
    # Newton on the true surface
    for _ in range(8):
        u, v, w = ou + t * du, ov + t * dv, ow + t * dw
        F = w - sag(u, v)
        h = 1e-6
        dF = dw - (sag(u + h * du, v + h * dv) - sag(u - h * du, v - h * dv)) / (2 * h)
        with np.errstate(divide="ignore", invalid="ignore"):
            step = np.where(np.abs(dF) > 1e-12, F / dF, 0.0)
        t = t - step
    u, v = ou + t * du, ov + t * dv
    p = o + t[:, None] * d
    n = mirror_normal(u, v)
    inside = (np.abs(u) <= MW / 2) & (np.abs(v) <= MH / 2) & ok
    return p, n, inside


def hit_plane(o, d, p0, n):
    den = d @ n
    with np.errstate(divide="ignore", invalid="ignore"):
        t = ((p0 - o) @ n) / den
    ok = (np.abs(den) > 1e-12) & (t > 1e-9)
    return o + t[:, None] * d, ok


def reflect(d, n):
    return d - 2 * np.sum(d * n, axis=1, keepdims=True) * n


def through_glass(o, d):
    """Refract through the laminate (outer surface at (p - G).N = T, inner at 0): the ray leaves parallel, offset."""
    pO, ok = hit_plane(o, d, G + GN * GT, GN)
    cos_i = -(d @ GN)
    ok &= cos_i > 0
    eta = 1 / N_GLASS
    k = 1 - eta * eta * (1 - cos_i * cos_i)
    dr = eta * d + (eta * cos_i - np.sqrt(np.clip(k, 0, None)))[:, None] * GN[None, :]
    dr = norm(dr)
    pI, ok2 = hit_plane(pO, dr, G, GN)
    return pI, ok & ok2


def trace(o, d):
    """Trace parallel sunlight to the panel plane. Returns landing (x, z) about the crop centre, and masks."""
    o, ok = through_glass(o, d)
    pl, okl = hit_plane(o, d, LID_P, LID_N)
    in_ap = okl & (pl[:, 0] >= HL["ax0"]) & (pl[:, 0] <= HL["ax1"]) & (pl[:, 2] >= HL["az0"]) & (pl[:, 2] <= HL["az1"])
    ok &= in_ap
    pm, nm, on_mirror = hit_mirror(pl, d)
    ok &= on_mirror
    d2 = reflect(d, nm)
    pf, okf = hit_plane(pm, d2, FC, FN)
    rel = pf - FC
    fu, fv = rel @ FU, rel @ FV
    on_fold = okf & (fu >= FF["u0"]) & (fu <= FF["u1"]) & (fv >= FF["v0"]) & (fv <= FF["v1"])
    ok_fold = ok & on_fold
    d3 = reflect(d2, FN)
    pp, okp = hit_plane(pf, d3, PC, A([0, 1, 0]))
    ok_panel = ok_fold & okp
    x, z = pp[:, 0] - PC[0], pp[:, 2] - PC[2]
    return x, z, ok, ok_fold, ok_panel


def bundle(sun_dir, spacing, jitter=0, seed=0):
    """Parallel rays toward -sun_dir on a grid perpendicular to the beam, with optional sun-disc jitter."""
    d0 = -norm(sun_dir)
    e1 = norm(np.cross(d0, [0, 0, 1.0])) if abs(d0[2]) < 0.9 else norm(np.cross(d0, [1.0, 0, 0]))
    e2 = np.cross(d0, e1)
    half = 0.30
    g = np.arange(-half, half + 1e-9, spacing)
    gu, gv = np.meshgrid(g, g)
    o0 = MC - d0 * 1.5
    o = o0[None, :] + gu.ravel()[:, None] * e1[None, :] + gv.ravel()[:, None] * e2[None, :]
    n = o.shape[0]
    d = np.repeat(d0[None, :], n, axis=0)
    if jitter > 0:
        rng = np.random.default_rng(seed)
        r = jitter * np.sqrt(rng.random(n))
        th = 2 * np.pi * rng.random(n)
        d = norm(d + (r * np.cos(th))[:, None] * e1[None, :] + (r * np.sin(th))[:, None] * e2[None, :])
    return o, d, SUN_IRR * spacing * spacing


def sun_vector(elev_deg, az_deg):
    """Unit vector toward the sun: elevation above the horizon, azimuth about the vertical from straight behind
    the car (positive toward the right side)."""
    e, a = math.radians(elev_deg), math.radians(az_deg)
    return A([-math.cos(e) * math.cos(a), math.sin(e), math.cos(e) * math.sin(a)])


def nominal_sun():
    """The plan's nominal: light along the reversed exit beam, i.e. the sun at MIRROR_DIR elevation behind the car."""
    g = L["glass"]
    look = A(L["look"])
    to_mirror = look - 2 * (look @ GN) * GN
    s = -to_mirror
    elev = math.degrees(math.asin(s[1]))
    return s, elev


def spot_stats(x, z, w, chain):
    """Irradiance footprint on the panel plane: bins of 0.25 mm, 1 mm box blur for the peak."""
    bx = np.arange(-0.040, 0.040 + 1e-9, 0.00025)
    bz = np.arange(-0.060, 0.060 + 1e-9, 0.00025)
    Hh, _, _ = np.histogram2d(x, z, bins=[bx, bz], weights=np.full_like(x, w))
    area = 0.00025 * 0.00025
    irr = Hh / area * chain
    k = 4
    blur = np.zeros_like(irr)
    cs = np.cumsum(np.cumsum(np.pad(irr, ((k, 0), (k, 0))), axis=0), axis=1)
    blur = (cs[k:, k:] - cs[:-k, k:] - cs[k:, :-k] + cs[:-k, :-k]) / (k * k)
    total = float(Hh.sum() * chain)                      # the histogram already sums the ray weights
    if total <= 0:
        return {"powerW": 0.0}, irr
    cx = float(x.mean()) if len(x) else 0.0
    cz = float(z.mean()) if len(z) else 0.0
    r = np.hypot(x - cx, z - cz)
    rs = np.sort(r)
    r50 = float(rs[int(0.5 * len(rs))]) if len(rs) else 0.0
    r90 = float(rs[int(0.9 * len(rs)) - 1]) if len(rs) else 0.0
    on_crop = float(((np.abs(x) <= CROP_X / 2) & (np.abs(z) <= CROP_Z / 2)).sum() * w * chain)
    on_cell = float(((np.abs(x) <= CELL_X / 2) & (np.abs(z) <= CELL_Z / 2)).sum() * w * chain)
    return {"powerW": total, "onCropW": on_crop, "onCellW": on_cell, "centroid_mm": [cx * 1000, cz * 1000],
            "r50_mm": r50 * 1000, "r90_mm": r90 * 1000, "peak_kW_m2": float(blur.max() / 1000),
            "extent_mm": [float((np.abs(x - cx)).max() * 1000) * 2, float((np.abs(z - cz)).max() * 1000) * 2]}, irr


def save_png(path, rgb):
    """Minimal PNG writer (no PIL in a stock Python): rgb uint8 (H, W, 3)."""
    import struct
    import zlib
    h, w = rgb.shape[:2]
    raw = b"".join(b"\x00" + rgb[i].tobytes() for i in range(h))
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def heat(img, vmax=None, gamma=0.5):
    v = np.clip(img / (vmax or max(img.max(), 1e-9)), 0, 1) ** gamma
    r = np.clip(1.6 * v, 0, 1)
    g = np.clip(1.6 * v - 0.5, 0, 1)
    b = np.clip(3 * v - 2.2, 0, 1) * 0.9 + 0.08 * (1 - v)
    return (np.stack([r, g, b], axis=2) * 255).astype(np.uint8)


def main():
    t0 = time.time()
    chain_collect = RAW["WS_T_SUN"] * RAW["MIRROR_R"]                       # glass transmission, mirror reflectance
    chain_panel = chain_collect * RAW["FILT_FRAC"] * RAW["POL_T_UNPOL"]      # cold mirror + IR-cut, polariser
    s_nom, elev_nom = nominal_sun()
    res = {"mode": MODE, "surface": "true " + MODE, "nominalElevationDeg": elev_nom, "planElevationDeg": 180 - RAW["SUN_ELEV"],
           "chain": {"collect": chain_collect, "toPanel": chain_panel, "WS_T_SUN": RAW["WS_T_SUN"], "MIRROR_R": RAW["MIRROR_R"], "FILT_FRAC": RAW["FILT_FRAC"], "POL_T_UNPOL": RAW["POL_T_UNPOL"]},
           "plan": {"collectedW": RAW["SUN_W"], "afterFiltersW": RAW["SUN_AFTER_POL"], "r90_mm": RAW["R90_PGU"], "patchDeg": [RAW["PATCH_W"], RAW["PATCH_H"]], "tiImagerPeak_kW_m2": RAW["TI_IMAGER_PEAK"]}}
    # ---- nominal spot, with the sun's disc ----
    spacing = 0.0015 if FINE else 0.004
    xs, zs, nray, n_ap, n_fold, n_panel = [], [], 0, 0, 0, 0
    sub = 12 if FINE else 4
    for k in range(sub):
        o, d, w = bundle(s_nom, spacing, jitter=math.radians(0.266), seed=k)
        x, z, ok, okf, okp = trace(o, d)
        xs.append(x[okp]); zs.append(z[okp])
        nray += len(x); n_ap += int(ok.sum()); n_fold += int(okf.sum()); n_panel += int(okp.sum())
    x, z = np.concatenate(xs), np.concatenate(zs)
    w_eff = w / sub
    collected = n_ap / sub * w * chain_collect
    stats, irr = spot_stats(x, z, w_eff, chain_panel)
    res["nominal"] = {"rays": nray, "collectedByMirrorW": collected, "throughApertureW_raw": n_ap / sub * w,
                      "onFoldFraction": n_fold / max(1, n_ap), "onPanelPlaneFraction": n_panel / max(1, n_ap), **stats}
    save_png(os.path.join(OUT, "sun_spot.png"), heat(irr))
    res["spotImage"] = {"file": "sun_spot.png", "x_mm": [-40, 40], "z_mm": [-60, 60], "note": "rows = fore-aft x (rear at top), columns = lateral z; 0.25 mm bins; colour = irradiance^0.5"}
    print(f"nominal sun {elev_nom:.1f} deg: collected {collected:.1f} W (plan {RAW['SUN_W']}), on panel plane {stats.get('powerW', 0):.2f} W after filters (plan {RAW['SUN_AFTER_POL']}), "
          f"r50 {stats.get('r50_mm', 0):.1f} mm, r90 {stats.get('r90_mm', 0):.1f} mm (plan {RAW['R90_PGU']:.1f}), peak {stats.get('peak_kW_m2', 0):.0f} kW/m2, centroid {stats.get('centroid_mm')}", flush=True)
    # ---- the entry patch: sun directions from which light reaches the crop ----
    els = np.arange(elev_nom - 24, elev_nom + 24.01, 1.5 if FINE else 3)
    azs = np.arange(-30, 30.01, 1.5 if FINE else 3)
    crop = np.zeros((len(els), len(azs)))
    cell = np.zeros_like(crop)
    fold = np.zeros_like(crop)
    for i, el in enumerate(els):
        for j, az in enumerate(azs):
            o, d, w = bundle(sun_vector(el, az), 0.005)
            x, z, ok, okf, okp = trace(o, d)
            n_ok = max(1, int(ok.sum()))
            on_crop = okp & (np.abs(x) <= CROP_X / 2) & (np.abs(z) <= CROP_Z / 2)
            on_cell = okp & (np.abs(x) <= CELL_X / 2) & (np.abs(z) <= CELL_Z / 2)
            crop[i, j] = on_crop.sum() * w * chain_panel
            cell[i, j] = on_cell.sum() * w * chain_panel
            fold[i, j] = okf.sum() * w * chain_collect
    def extent(mask, axis_vals):
        idx = np.nonzero(mask.any(axis=1 if axis_vals is els else 0))[0]
        return [float(axis_vals[idx[0]]), float(axis_vals[idx[-1]])] if len(idx) else None
    hot = crop > 0.05 * crop.max() if crop.max() > 0 else crop > 1
    hot_cell = cell > 0.05 * cell.max() if cell.max() > 0 else cell > 1
    res["patch"] = {"elevations": els.tolist(), "azimuths": azs.tolist(), "cropW": crop.round(3).tolist(), "cellW": cell.round(3).tolist(), "foldW": fold.round(2).tolist(),
                    "cropHot": {"elevation": extent(hot, els), "azimuth": extent(hot, azs)},
                    "cellHot": {"elevation": extent(hot_cell, els), "azimuth": extent(hot_cell, azs)},
                    "maxCropW": float(crop.max()), "maxCellW": float(cell.max())}
    e_ext, a_ext = res["patch"]["cropHot"]["elevation"], res["patch"]["cropHot"]["azimuth"]
    ce, ca = res["patch"]["cellHot"]["elevation"], res["patch"]["cellHot"]["azimuth"]
    if ce and ca:
        res["patch"]["cellSizeDeg"] = [ca[1] - ca[0], ce[1] - ce[0]]
        print(f"cell patch (>5% of max): elevation {ce[0]:.1f}–{ce[1]:.1f}, azimuth {ca[0]:.1f}–{ca[1]:.1f} deg", flush=True)
    if e_ext and a_ext:
        res["patch"]["sizeDeg"] = [a_ext[1] - a_ext[0], e_ext[1] - e_ext[0]]
        print(f"crop patch (>5% of max): elevation {e_ext[0]:.1f}–{e_ext[1]:.1f}, azimuth {a_ext[0]:.1f}–{a_ext[1]:.1f} deg: {a_ext[1] - a_ext[0]:.0f} x {e_ext[1] - e_ext[0]:.0f} deg (plan {RAW['PATCH_W']:.1f} x {RAW['PATCH_H']:.1f})", flush=True)
    # patch picture: crop power (amber), cell power (dim), one pixel per direction, scaled up 6x
    pic = np.zeros((len(els), len(azs), 3))
    cm = max(cell.max(), 1e-9)
    pic[..., 0] = np.clip(cell / cm, 0, 1) * 0.45 + np.clip(crop / cm, 0, 1) * 0.55
    pic[..., 1] = np.clip(cell / cm, 0, 1) * 0.35 + np.clip(crop / cm, 0, 1) * 0.45
    pic[..., 2] = np.clip(cell / cm, 0, 1) * 0.25
    pic = np.kron(pic[::-1], np.ones((6, 6, 1)))             # elevation up the image
    save_png(os.path.join(OUT, "sun_patch.png"), (np.clip(pic, 0, 1) ** 0.6 * 255).astype(np.uint8))
    res["patchImage"] = {"file": "sun_patch.png", "note": "rows = sun elevation (top = high), columns = azimuth about straight behind (left = driver side); bright = power on the crop, dim = on the cell"}
    res["elapsedSec"] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, "sun_focus.json"), "w") as f:
        json.dump(res, f, indent=1)
    print("wrote", os.path.join(OUT, "sun_focus.json"), f"in {res['elapsedSec']} s", flush=True)


if __name__ == "__main__":
    main()
