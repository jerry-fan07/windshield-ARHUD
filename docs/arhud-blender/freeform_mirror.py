"""A freeform mirror that flattens the image surface.

The Cycles cross-check showed the toroid's virtual image running from about 6 m at the top of the window to 19 m at the
bottom (the panel sits 14 mm inside the focus, so the incidence change across the window moves the image a long way).
This script fits a polynomial sag w(u, v) = sum c_ij u^i v^j on the mirror (u lateral, v in the plane of incidence,
w along the mirror normal toward the light) so that the virtual image sits at one distance from the eye over the
whole 60 x 30 mm crop, measured the way the driver's head measures it: by parallax. For every dot of the Cycles test
grid, the field directions from eyes displaced 40 mm sideways and 30 mm vertically that land on the dot are solved
on the same trace geom.js uses (glass plane, mirror, fold plane, panel plane), and the sagittal and tangential image
distances follow from the shifts. Levenberg-Marquardt on the dioptric error brings both to the target distance.

Outputs: freeform.json beside this script (optics_check.py reads it for surface=freeform / modes=freeform),
arhud-sim/js/freeform.js (geom.js traces the same surface as mode 'freeform'), and the before/after distance maps.

Run:  python3 freeform_mirror.py [target=7.5] [iters=40]
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
TARGET = arg("target", 7.5, float)
ITERS = arg("iters", 40, int)
LATERAL, VERTICAL = 0.040, 0.030
GLASS_RH = arg("glassRh", 0.0, float)          # windshield radii as optics_check.py takes them (0 = flat, the plan)
GLASS_RV = arg("glassRv", 0.0, float)
OUT_NAME = arg("name", "freeform")             # freeform.json / freeform.js, or e.g. freeform_curved

with open(os.path.join(HERE, "layout.json")) as f:
    L = json.load(f)
A = lambda p: np.array(p, dtype=np.float64)
EYE, LOOK = A(L["eye"]), A(L["look"])
RIGHT, UP = A(L["vimg"]["RIGHT"]), A(L["vimg"]["UP"])
G, GN = A(L["glass"]["G"]), A(L["glass"]["N"])
MC, MN, MU, MV = A(L["mirror"]["C"]), A(L["mirror"]["N"]), A(L["mirror"]["U"]), A(L["mirror"]["V"])
MW, MH = L["mirror"]["W"], L["mirror"]["H"]
FC, FN = A(L["fold"]["C"]), A(L["fold"]["N"])
PC = A(L["panel"]["C"])
Rt0, Rs0 = L["mirror"]["toroid"]["Rt"], L["mirror"]["toroid"]["Rs"]
DOT_U = [-25 + 5 * i for i in range(11)]
DOT_V = [10 - 5 * j for j in range(5)]
TERMS = [(2, 0), (0, 2), (0, 3), (2, 1), (4, 0), (2, 2), (0, 4), (2, 3), (0, 5), (4, 1), (4, 2), (2, 4), (0, 6)]


def sag(c, u, v):
    return sum(ck * u ** i * v ** j for ck, (i, j) in zip(c, TERMS))


def grad(c, u, v):
    du = sum(ck * i * u ** (i - 1) * v ** j for ck, (i, j) in zip(c, TERMS) if i > 0)
    dv = sum(ck * j * u ** i * v ** (j - 1) for ck, (i, j) in zip(c, TERMS) if j > 0)
    return du, dv


def reflect(d, n):
    return d - 2 * np.sum(d * n, axis=-1, keepdims=True) * n


def hit_plane(o, d, p0, n):
    t = ((p0 - o) @ n) / (d @ n)
    return o + t[:, None] * d


def hit_mirror(c, o, d):
    rel = o - MC
    ou, ov, ow = rel @ MU, rel @ MV, rel @ MN
    du, dv, dw = d @ MU, d @ MV, d @ MN
    # start from the paraboloid with the vertex curvatures
    a = du * du * c[0] + dv * dv * c[1]
    b = 2 * ou * du * c[0] + 2 * ov * dv * c[1] - dw
    cc = ou * ou * c[0] + ov * ov * c[1] - ow
    disc = np.clip(b * b - 4 * a * cc, 0, None)
    s = np.sqrt(disc)
    with np.errstate(divide="ignore", invalid="ignore"):
        t1 = (-b - s) / (2 * a)
        t2 = (-b + s) / (2 * a)
        tl = -cc / b
    t = np.where(np.abs(a) < 1e-12, tl, np.where(t1 > 1e-6, t1, t2))
    for _ in range(8):
        u, v, w = ou + t * du, ov + t * dv, ow + t * dw
        F = w - sag(c, u, v)
        gu, gv = grad(c, u, v)
        dF = dw - (gu * du + gv * dv)
        t = t - F / dF
    u, v = ou + t * du, ov + t * dv
    p = o + t[:, None] * d
    gu, gv = grad(c, u, v)
    n = MN[None, :] - gu[:, None] * MU[None, :] - gv[:, None] * MV[None, :]
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    inside = (np.abs(u) <= MW / 2) & (np.abs(v) <= MH / 2)
    return p, n, inside


GUP = A(L["glass"]["UP"])
GZ = A([0.0, 0.0, 1.0])


def hit_glass(o, d):
    """The windshield's inner surface: the plane through G, or the surface that comes toward the cabin by
    b^2/2Rh + a^2/2Rv away from G (concave toward the driver), as optics_check.py builds it. Returns point, normal."""
    o = hit_plane(o, d, G, GN)
    n = np.repeat(GN[None, :], len(o), axis=0)
    if GLASS_RH <= 0 and GLASS_RV <= 0:
        return o, n
    # Newton along the ray on F = (p - G).N + sag(a, b) = 0, with a along GUP and b along GZ
    t = np.zeros(len(o))
    for _ in range(8):
        p = o + t[:, None] * d
        rel = p - G
        a, b, w = rel @ GUP, rel @ GZ, rel @ GN
        sag = (b * b / (2 * GLASS_RH) if GLASS_RH > 0 else 0) + (a * a / (2 * GLASS_RV) if GLASS_RV > 0 else 0)
        F = w + sag
        ga = (a / GLASS_RV if GLASS_RV > 0 else 0)
        gb = (b / GLASS_RH if GLASS_RH > 0 else 0)
        dF = d @ GN + ga * (d @ GUP) + gb * (d @ GZ)
        t = t - F / dF
    p = o + t[:, None] * d
    rel = p - G
    a, b = rel @ GUP, rel @ GZ
    ga = (a / GLASS_RV if GLASS_RV > 0 else 0)
    gb = (b / GLASS_RH if GLASS_RH > 0 else 0)
    n = GN[None, :] + ga[:, None] * GUP[None, :] + gb[:, None] * GZ[None, :]
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    return p, n


def land(c, e, ax, ay):
    """Panel landing (z, x) about the crop centre for field angles from eye e (both arrays)."""
    n = len(ax)
    d = LOOK[None, :] + np.tan(ax)[:, None] * RIGHT[None, :] + np.tan(ay)[:, None] * UP[None, :]
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    o = np.repeat(e[None, :], n, axis=0)
    o, gn = hit_glass(o, d)
    d = reflect(d, gn)
    o, nm, inside = hit_mirror(c, o, d)
    d = reflect(d, nm)
    o = hit_plane(o, d, FC, FN)
    d = reflect(d, FN[None, :])
    pc, pn, pu, pv = panel_pose(c)
    o = hit_plane(o, d, pc, pn)
    rel = o - pc
    return rel @ pu, rel @ pv, inside


def solve_field(c, e, pz, px):
    """Field angles from eye e whose rays land on panel points (pz, px): 2-D Newton, vectorised over the dots."""
    ax = pz / 0.06 * 0.15
    ay = -px / 0.03 * 0.08
    h = 1e-5
    for _ in range(12):
        z0, x0, _ = land(c, e, ax, ay)
        z1, x1, _ = land(c, e, ax + h, ay)
        z2, x2, _ = land(c, e, ax, ay + h)
        J00, J01 = (z1 - z0) / h, (z2 - z0) / h
        J10, J11 = (x1 - x0) / h, (x2 - x0) / h
        det = J00 * J11 - J01 * J10
        ez, ex = pz - z0, px - x0
        ax = ax + (J11 * ez - J01 * ex) / det
        ay = ay + (-J10 * ez + J00 * ex) / det
    _, _, inside = land(c, e, ax, ay)
    return ax, ay, inside


PANEL_FREE = arg("panel", 1, int)              # 1: let the panel tilt and move too (a design study; the simulator keeps it flat)
NPOLY = len(TERMS)


def panel_pose(c):
    """Panel centre, normal and in-plane axes for parameter vector c (tilt and shift are the last two entries when
    the panel is free; otherwise the plan's horizontal panel)."""
    th = c[NPOLY] if PANEL_FREE and len(c) > NPOLY else 0.0
    dz = c[NPOLY + 1] if PANEL_FREE and len(c) > NPOLY + 1 else 0.0
    n = A([-math.sin(th), math.cos(th), 0.0])
    centre = PC + A([0.0, -dz, 0.0])
    u_axis = A([0.0, 0.0, 1.0])
    v_axis = np.cross(n, u_axis)                 # in-plane fore-aft axis (+x when flat)
    return centre, n, u_axis, v_axis


PZ = np.array([u / 1000 for v in DOT_V for u in DOT_U])
PX = np.array([-v / 1000 for v in DOT_V for u in DOT_U])


def distances(c):
    """Sagittal and tangential image distances from the eye for every dot, by parallax."""
    axm, _, im = solve_field(c, EYE - RIGHT * LATERAL, PZ, PX)
    axp, _, ip = solve_field(c, EYE + RIGHT * LATERAL, PZ, PX)
    _, aym, jm = solve_field(c, EYE - UP * VERTICAL, PZ, PX)
    _, ayp, jp = solve_field(c, EYE + UP * VERTICAL, PZ, PX)
    Ds = 2 * LATERAL / (np.tan(axm) - np.tan(axp))
    Dt = 2 * VERTICAL / (np.tan(aym) - np.tan(ayp))
    return Ds, Dt, im & ip & jm & jp


DISTORTION_W = arg("distortion", 1.0, float)     # weight of the "dots on a regular grid" term against the dioptric one
UU = np.array([u for v in DOT_V for u in DOT_U], dtype=np.float64)
VV = np.array([v for v in DOT_V for u in DOT_U], dtype=np.float64)
DESIGN = np.c_[np.ones_like(UU), UU, VV]


def distortion(c):
    """Residual of the dot angles from the nominal eye against the best affine map of the crop: the pincushion or
    barrel that a pre-distortion warp would have to undo, and that eats the inscribed window. Degrees."""
    ax, ay, _ = solve_field(c, EYE, PZ, PX)
    out = []
    for a in (ax, ay):
        coef, *_ = np.linalg.lstsq(DESIGN, a, rcond=None)
        out.append(np.degrees(a - DESIGN @ coef))
    return np.concatenate(out)


EDGE_W = arg("edges", 6.0, float)                 # weight of the straight-window-edge term (degrees)


def edges(c):
    """How much the window's edges bow: the top and bottom dot rows should share one ay, the left and right columns
    one ax. These bows are what shrink the inscribed rectangle after pre-distortion. Degrees."""
    ax, ay, _ = solve_field(c, EYE, PZ, PX)
    ax = ax.reshape(5, 11)
    ay = ay.reshape(5, 11)
    out = [ay[0] - ay[0].mean(), ay[-1] - ay[-1].mean(), ax[:, 0] - ax[:, 0].mean(), ax[:, -1] - ax[:, -1].mean()]
    return np.degrees(np.concatenate(out))


def residuals(c):
    with np.errstate(all="ignore"):
        Ds, Dt, ok = distances(c)
        r = np.concatenate([(1 / Ds - 1 / TARGET), (1 / Dt - 1 / TARGET)]) * 10      # tenths of a dioptre
        rd = distortion(c) * DISTORTION_W
        re = edges(c) * EDGE_W
    # rays that miss a surface or fail to converge: a finite penalty instead of NaN, so the fit can walk back
    r = np.where(np.isfinite(r), np.clip(r, -50, 50), 50.0)
    rd = np.where(np.isfinite(rd), np.clip(rd, -20, 20), 20.0)
    re = np.where(np.isfinite(re), np.clip(re, -20, 20), 20.0)
    r = np.where(np.concatenate([ok, ok]), r, 50.0)
    reg = np.array([ck * s for ck, s in zip(c[2:NPOLY], [1e-3, 1e-3, 3e-4, 3e-4, 3e-4, 1e-4, 1e-4, 1e-4, 3e-5, 3e-5, 3e-5])])
    if PANEL_FREE:
        reg = np.concatenate([reg, [c[NPOLY] * 0.05, c[NPOLY + 1] * 2.0]])      # mild: keep the tilt and shift small
    return np.concatenate([r, rd, re, reg]), Ds, Dt, ok


def coarse_start(c0):
    """A grid over the two vertex powers (and the panel tilt when free) before the local fit: with a curved
    windshield the plan's toroid is far from any solution and Levenberg-Marquardt alone cannot find its way."""
    best, best_cost = np.array(c0, dtype=np.float64), np.inf
    tilts = [0.0, 0.3, 0.6, 0.9] if PANEL_FREE else [0.0]
    for ks in (0.3, 0.5, 0.7, 0.85, 1.0, 1.2):
        for kt in (0.3, 0.5, 0.7, 0.85, 1.0, 1.2):
            for th in tilts:
                c = np.array(c0, dtype=np.float64)
                c[0] *= ks
                c[1] *= kt
                if PANEL_FREE:
                    c[NPOLY] = th
                r, _, _, _ = residuals(c)
                cost = float(r @ r)
                if cost < best_cost:
                    best, best_cost = c, cost
    print(f"  coarse start: vertex powers x{best[0] / c0[0]:.2f}, x{best[1] / c0[1]:.2f}" + (f", tilt {math.degrees(best[NPOLY]):.0f} deg" if PANEL_FREE else "") + f", cost {best_cost:.3f}", flush=True)
    return best


def lm(c0):
    c = coarse_start(c0)
    r, _, _, _ = residuals(c)
    cost = float(r @ r)
    lam = 1e-3
    for it in range(ITERS):
        Jm = np.zeros((len(r), len(c)))
        for k in range(len(c)):
            h = max(1e-6, 1e-4 * abs(c[k]))
            cp = c.copy()
            cp[k] += h
            rp, _, _, _ = residuals(cp)
            Jm[:, k] = (rp - r) / h
        g = Jm.T @ r
        H = Jm.T @ Jm
        improved = False
        for _ in range(8):
            step = np.linalg.solve(H + lam * np.diag(np.diag(H) + 1e-12), -g)
            cn = c + step
            rn, _, _, _ = residuals(cn)
            cn_cost = float(rn @ rn)
            if cn_cost < cost:
                c, r, cost = cn, rn, cn_cost
                lam = max(lam / 3, 1e-9)
                improved = True
                break
            lam *= 4
        print(f"  iter {it}: cost {cost:.5f}, lambda {lam:.1e}", flush=True)
        if not improved or abs(step).max() < 1e-9:
            break
    return c


def main():
    t0 = time.time()
    c0 = [1 / (2 * Rs0), 1 / (2 * Rt0)] + [0.0] * (len(TERMS) - 2) + ([0.0, 0.0] if PANEL_FREE else [])
    Ds0, Dt0, ok0 = distances(np.array(c0))
    print(f"toroid (paraboloid) start: sagittal {Ds0.min():.1f}-{Ds0.max():.1f} m, tangential {Dt0.min():.1f}-{Dt0.max():.1f} m, centre {Ds0[27]:.2f}/{Dt0[27]:.2f}", flush=True)
    c = lm(c0)
    Ds, Dt, ok = distances(c)
    print(f"freeform: sagittal {Ds.min():.2f}-{Ds.max():.2f} m, tangential {Dt.min():.2f}-{Dt.max():.2f} m, centre {Ds[27]:.2f}/{Dt[27]:.2f}, all dots on the mirror: {bool(ok.all())}", flush=True)
    # where the dots land in angle from the nominal eye (for the registration check) and the vertex radii
    ax, ay, _ = solve_field(c, EYE, PZ, PX)
    Rs, Rt = 1 / (2 * c[0]), 1 / (2 * c[1])
    if PANEL_FREE:
        print(f"panel: tilt {math.degrees(c[NPOLY]):+.2f} deg about the lateral axis, shift {c[NPOLY + 1] * 1000:+.1f} mm along the fold-to-panel leg", flush=True)
    d0, d1 = distortion(np.array(c0)), distortion(c)
    e0, e1 = edges(np.array(c0)), edges(c)
    print(f"distortion (rms deviation of the dots from an affine grid): toroid {np.sqrt((d0 ** 2).mean()):.3f} deg, freeform {np.sqrt((d1 ** 2).mean()):.3f} deg; edge bow max: toroid {np.abs(e0).max():.3f}, freeform {np.abs(e1).max():.3f} deg", flush=True)
    out = {
        "generated": time.strftime("%Y-%m-%d %H:%M"), "targetDistance": TARGET, "distortionWeight": DISTORTION_W, "glass": {"Rh": GLASS_RH, "Rv": GLASS_RV},
        "distortionRmsDeg": {"toroid": float(np.sqrt((d0 ** 2).mean())), "freeform": float(np.sqrt((d1 ** 2).mean()))},
        "edgeBowMaxDeg": {"toroid": float(np.abs(e0).max()), "freeform": float(np.abs(e1).max())}, "edgeWeight": EDGE_W,
        "terms": TERMS, "coefficients": [float(x) for x in c[:NPOLY]], "panelTiltDeg": (math.degrees(c[NPOLY]) if PANEL_FREE else 0.0), "panelShiftMm": (c[NPOLY + 1] * 1000 if PANEL_FREE else 0.0), "panelFree": bool(PANEL_FREE),
        "frame": "w = sum c_ij u^i v^j on the mirror: u along geom.MIRROR_U (lateral), v along MIRROR_V (plane of incidence), w along MIRROR_N toward the light; metres",
        "vertexRadii": {"Rs": Rs, "Rt": Rt},
        "before": {"sagittal": Ds0.reshape(5, 11).round(2).tolist(), "tangential": Dt0.reshape(5, 11).round(2).tolist()},
        "after": {"sagittal": Ds.reshape(5, 11).round(2).tolist(), "tangential": Dt.reshape(5, 11).round(2).tolist()},
        "dotsDeg": {"ax": np.degrees(ax).reshape(5, 11).round(3).tolist(), "ay": np.degrees(ay).reshape(5, 11).round(3).tolist()},
        "sagMaxMm": float(max(abs(sag(c, u, v)) for u in np.linspace(-MW / 2, MW / 2, 7) for v in np.linspace(-MH / 2, MH / 2, 5)) * 1000),
        "elapsedSec": round(time.time() - t0, 1),
    }
    with open(os.path.join(HERE, OUT_NAME + ".json"), "w") as f:
        json.dump(out, f, indent=1)
    os.makedirs(os.path.join(HERE, "..", "arhud-sim", "assets", "cycles"), exist_ok=True)
    with open(os.path.join(HERE, "..", "arhud-sim", "assets", "cycles", OUT_NAME + ".json"), "w") as f:
        json.dump(out, f, indent=1)
    js = os.path.join(HERE, "..", "arhud-sim", "js", OUT_NAME + ".js")
    with open(js, "w") as f:
        f.write("// Generated by docs/arhud-blender/freeform_mirror.py. Do not edit; rerun the script.\n")
        f.write("// The freeform mirror: w = sum c u^i v^j in the mirror frame (u lateral, v in the plane of incidence, w toward the light).\n")
        f.write("export const FREEFORM = " + json.dumps({"terms": TERMS, "c": [float(x) for x in c[:NPOLY]], "Rs": Rs, "Rt": Rt, "target": TARGET, "panelTiltDeg": (math.degrees(c[NPOLY]) if PANEL_FREE else 0.0), "panelShiftMm": (c[NPOLY + 1] * 1000 if PANEL_FREE else 0.0), "glass": {"Rh": GLASS_RH, "Rv": GLASS_RV}}) + ";\n")
    print(f"wrote {OUT_NAME}.json and {os.path.relpath(js, HERE)} in {time.time() - t0:.0f} s; vertex radii Rs {Rs * 1000:.1f} Rt {Rt * 1000:.1f} mm", flush=True)


if __name__ == "__main__":
    main()
