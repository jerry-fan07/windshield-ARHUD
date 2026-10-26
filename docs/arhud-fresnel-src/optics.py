"""Ray tracer for the Stage 1 Fresnel magnifier (numpy only).

Model: a PMMA Fresnel sheet of thickness T. Its flat face is at z = -T, its grooved face is
collapsed onto the plane z = 0 (the thin-facet model): at radius r the grooved face has the
slope of the continuous asphere it replaces, but no sag. The facet slopes are solved so that a
collimated beam arriving on the grooved side, travelling toward -z, focuses on the axis at the
back focal distance of an f = 300 mm lens (stock lenses are designed for that conjugate; ASSUMED).

Stage 1 runs the lens the other way: light leaves the panel (z < -T), enters the flat face, leaves
through the facets toward the eye (z > 0). The eye sees the panel through the combiner, a plane
mirror, so the path is unfolded onto one axis: the eye sits on the +z axis at z = EYE_Z.

Principal planes of a plano-convex sheet used flat side first: H at z = -T + T/n, H' at z = 0.
The panel distance U is measured from H; the virtual image distance from H'.
"""
import math
import numpy as np

# ---- Material -----------------------------------------------------------------------------
def n_pmma(lam_um):
    """PMMA, Sellmeier fit (Szczurowski 2012, via refractiveindex.info)."""
    l2 = np.asarray(lam_um, float) ** 2
    return np.sqrt(1 + 0.99654 * l2 / (l2 - 0.00787) + 0.18964 * l2 / (l2 - 0.02191)
                   + 0.00411 * l2 / (l2 - 3.85727))

def n_bk7(lam_um):
    l2 = np.asarray(lam_um, float) ** 2
    return np.sqrt(1 + 1.03961212 * l2 / (l2 - 0.00600069867) + 0.231792344 * l2 / (l2 - 0.0200179144)
                   + 1.01046945 * l2 / (l2 - 103.560653))

def n_pc(lam_um):
    """Polycarbonate, one-term Sellmeier (Sultanova 2009 class fit)."""
    l2 = np.asarray(lam_um, float) ** 2
    return np.sqrt(1 + 1.4182 * l2 / (l2 - 0.021304))

LAM_D = 0.5876                      # design wavelength, µm
LAM_RGB = (0.620, 0.530, 0.450)     # LCD primaries, µm (typical; ASSUMED)
N_D = float(n_pmma(LAM_D))

# ---- Lens and layout (Stage 1 numbers from the plan) --------------------------------------
F = 300.0                           # effective focal length, mm (plan calc.py F1)
U = 280.0                           # panel distance from the principal plane H, mm (plan calc.py U1)
T = 2.0                             # sheet thickness, mm (Knight Optical LFQ300300 listing)
PITCH = 0.5                         # groove pitch, mm (Knight Optical LFQ300300 "facet width")
HALF = 150.0                        # half-width of the 300 mm square sheet, mm
EYE_Z = 700.0                       # eye to lens along the unfolded path, mm (ASSUMED)
Z_H = -T + T / N_D                  # object-side principal plane
Z_PANEL = Z_H - U                   # panel plane

# ---- Vector helpers ---------------------------------------------------------------------
def unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)

def refract(d, nrm, n1, n2):
    """Refract unit directions d at unit normals nrm (any orientation). Returns (t, tir, cos_i, cos_t)."""
    n1 = np.broadcast_to(np.asarray(n1, float), d.shape[:-1])
    n2 = np.broadcast_to(np.asarray(n2, float), d.shape[:-1])
    c = np.sum(d * nrm, axis=-1)
    nrm = np.where((c > 0)[..., None], -nrm, nrm)
    cosi = np.abs(c)
    eta = n1 / n2
    k = 1 - eta ** 2 * (1 - cosi ** 2)
    tir = k < 0
    kk = np.sqrt(np.clip(k, 0, None))
    t = eta[..., None] * d + (eta * cosi - kk)[..., None] * nrm
    return unit(t), tir, cosi, kk

def fresnel_T(cosi, cost, n1, n2):
    """Unpolarised power transmittance of one surface."""
    rs = ((n1 * cosi - n2 * cost) / (n1 * cosi + n2 * cost)) ** 2
    rp = ((n1 * cost - n2 * cosi) / (n1 * cost + n2 * cosi)) ** 2
    return 1 - 0.5 * (rs + rp), 1 - rs, 1 - rp

# ---- Facet design ---------------------------------------------------------------------
def _design_focus_error(r, g, n=N_D):
    """Collimated ray at radius r, travelling -z, through a facet whose normal is tilted
    outward by g (rad). Returns the radius where it would cross the design focal plane."""
    zf = Z_H - F                                 # back focus: EFL from H, measured on the flat side
    d = np.array([0.0, -1.0])
    nf = np.stack([np.sin(g), np.cos(g)], -1)    # (r, z) components
    d3 = np.broadcast_to(d, nf.shape)
    t, _, _, _ = refract(d3, nf, 1.0, n)
    # to the flat face
    s = (-T - 0.0) / t[..., 1]
    r1 = r + s * t[..., 0]
    t2, _, _, _ = refract(t, np.broadcast_to(np.array([0.0, 1.0]), t.shape), n, 1.0)
    s2 = (zf - (-T)) / t2[..., 1]
    return r1 + s2 * t2[..., 0]

def _solve_slopes(rs):
    lo = np.zeros_like(rs); hi = np.full_like(rs, math.radians(80))
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        e = _design_focus_error(rs, mid)
        lo = np.where(e > 0, mid, lo)
        hi = np.where(e > 0, hi, mid)
    return 0.5 * (lo + hi)

R_TAB = np.linspace(0, 230, 4601)
G_TAB = _solve_slopes(R_TAB)                     # outward tilt of the facet normal, rad

def facet_tilt(r):
    return np.interp(r, R_TAB, G_TAB)

def facet_angle_deg(r):
    """Angle between the facet face and the sheet plane (equals the normal tilt)."""
    return np.degrees(facet_tilt(r))

def groove_depth(r, pitch=PITCH):
    return pitch * np.tan(facet_tilt(r))

def facet_normals(x, y):
    r = np.hypot(x, y)
    g = facet_tilt(r)
    with np.errstate(invalid="ignore", divide="ignore"):
        cx = np.where(r > 0, x / r, 0.0); cy = np.where(r > 0, y / r, 0.0)
    return np.stack([np.sin(g) * cx, np.sin(g) * cy, np.cos(g)], -1)

# ---- Sequential traces -------------------------------------------------------------------
def trace_backward(E, D, lam=LAM_D, z_panel=None, glass=n_pmma, flipped=False):
    """Rays from the eye side (points E, unit dirs D with D_z < 0) to the panel plane.
    Returns dict with panel hits, lens hits, masks and surface transmittance."""
    z_panel = Z_PANEL if z_panel is None else z_panel
    n = float(glass(lam))
    E = np.asarray(E, float); D = unit(np.asarray(D, float))
    out = {}
    if not flipped:
        s = (0.0 - E[..., 2]) / D[..., 2]
        P1 = E + s[..., None] * D
        nf = facet_normals(P1[..., 0], P1[..., 1])
        t1, tir1, ci1, ct1 = refract(D, nf, 1.0, n)
        s = (-T - P1[..., 2]) / t1[..., 2]
        P2 = P1 + s[..., None] * t1
        t2, tir2, ci2, ct2 = refract(t1, np.broadcast_to(np.array([0, 0, 1.0]), t1.shape), n, 1.0)
        T1 = fresnel_T(ci1, ct1, 1.0, n)[0]; T2 = fresnel_T(ci2, ct2, n, 1.0)[0]
    else:
        # grooves toward the panel: flat face at z = 0, facets collapsed onto z = -T
        s = (0.0 - E[..., 2]) / D[..., 2]
        P1 = E + s[..., None] * D
        t1, tir1, ci1, ct1 = refract(D, np.broadcast_to(np.array([0, 0, 1.0]), D.shape), 1.0, n)
        s = (-T - P1[..., 2]) / t1[..., 2]
        P2 = P1 + s[..., None] * t1
        nf = facet_normals(P2[..., 0], P2[..., 1]) * np.array([1, 1, -1.0])
        t2, tir2, ci2, ct2 = refract(t1, nf, n, 1.0)
        T1 = fresnel_T(ci1, ct1, 1.0, n)[0]; T2 = fresnel_T(ci2, ct2, n, 1.0)[0]
    s = (z_panel - P2[..., 2]) / t2[..., 2]
    P3 = P2 + s[..., None] * t2
    out.update(P1=P1, P2=P2, P3=P3, d1=t1, d2=t2, tir=tir1 | tir2, T=T1 * T2,
               inc1=np.degrees(np.arccos(np.clip(ci1, -1, 1))), inc2=np.degrees(np.arccos(np.clip(ci2, -1, 1))))
    return out

def trace_forward(P, D, lam=LAM_D, glass=n_pmma, flipped=False):
    """Rays from the panel side (points P below the lens, dirs D with D_z > 0) to just above z = 0."""
    n = float(glass(lam))
    P = np.asarray(P, float); D = unit(np.asarray(D, float))
    zfac, zflat = (0.0, -T) if not flipped else (-T, 0.0)
    if not flipped:
        s = (-T - P[..., 2]) / D[..., 2]
        P1 = P + s[..., None] * D
        t1, tir1, ci1, ct1 = refract(D, np.broadcast_to(np.array([0, 0, 1.0]), D.shape), 1.0, n)
        s = (0.0 - P1[..., 2]) / t1[..., 2]
        P2 = P1 + s[..., None] * t1
        t2, tir2, ci2, ct2 = refract(t1, facet_normals(P2[..., 0], P2[..., 1]), n, 1.0)
    else:
        s = (-T - P[..., 2]) / D[..., 2]
        P1 = P + s[..., None] * D
        nf = facet_normals(P1[..., 0], P1[..., 1]) * np.array([1, 1, -1.0])
        t1, tir1, ci1, ct1 = refract(D, nf, 1.0, n)
        s = (0.0 - P1[..., 2]) / t1[..., 2]
        P2 = P1 + s[..., None] * t1
        t2, tir2, ci2, ct2 = refract(t1, np.broadcast_to(np.array([0, 0, 1.0]), t1.shape), n, 1.0)
    T1 = fresnel_T(ci1, ct1, 1.0, n)[0]; T2 = fresnel_T(ci2, ct2, n, 1.0)[0]
    return dict(P1=P1, P2=P2, d=t2, tir=tir1 | tir2, T=T1 * T2,
                inc1=np.degrees(np.arccos(np.clip(ci1, -1, 1))), inc2=np.degrees(np.arccos(np.clip(ci2, -1, 1))))

def closest_points(p1, d1, p2, d2):
    """Parameters of closest approach between lines p1 + a d1 and p2 + b d2."""
    w = p1 - p2
    a_ = np.sum(d1 * d1, -1); b_ = np.sum(d1 * d2, -1); c_ = np.sum(d2 * d2, -1)
    d_ = np.sum(d1 * w, -1); e_ = np.sum(d2 * w, -1)
    den = a_ * c_ - b_ * b_
    sa = (b_ * e_ - c_ * d_) / den
    sb = (a_ * e_ - b_ * d_) / den
    return p1 + sa[..., None] * d1, p2 + sb[..., None] * d2

def eye_dirs(ax_deg, ay_deg):
    """Unit view directions from the eye for horizontal/vertical field angles (deg)."""
    ax = np.radians(np.asarray(ax_deg, float)); ay = np.radians(np.asarray(ay_deg, float))
    v = np.stack([np.tan(ax), np.tan(ay), -np.ones_like(ax)], -1)
    return unit(v)

def panel_point(ax, ay, eye=(0, 0, EYE_Z), lam=LAM_D, **kw):
    E = np.broadcast_to(np.asarray(eye, float), np.shape(ax) + (3,))
    return trace_backward(E, eye_dirs(ax, ay), lam=lam, **kw)

def image_point(ax, ay, eye=(0, 0, EYE_Z), lam=LAM_D, eps=1e-4, flipped=False):
    """Virtual image of the panel point seen in field direction (ax, ay) from the eye.
    Returns tangential and sagittal image distances from the eye (mm) and the image points."""
    ax = np.atleast_1d(np.asarray(ax, float)); ay = np.atleast_1d(np.asarray(ay, float))
    b = panel_point(ax, ay, eye, lam, flipped=flipped)
    P = b["P3"]; dchief = -b["d2"]                     # chief ray leaves the panel point toward the lens
    # tangential plane contains the axis and the chief ray; fall back to y on axis
    rad = np.stack([P[:, 0], P[:, 1], np.zeros_like(P[:, 0])], -1)
    rn = np.linalg.norm(rad, axis=-1, keepdims=True)
    rad = np.where(rn > 1e-9, rad / np.maximum(rn, 1e-12), np.array([0, 1.0, 0]))
    sag = unit(np.cross(dchief, rad))
    tan_ = unit(np.cross(sag, dchief))
    f0 = trace_forward(P, dchief, lam, flipped=flipped)
    res = {}
    for name, e in (("t", tan_), ("s", sag)):
        f1 = trace_forward(P, dchief + eps * e, lam, flipped=flipped)
        f2 = trace_forward(P, dchief - eps * e, lam, flipped=flipped)
        q1, _ = closest_points(f1["P2"], f1["d"], f2["P2"], f2["d"])
        res[name] = q1
    E = np.asarray(eye, float)
    dist = {k: np.linalg.norm(v - E, axis=-1) for k, v in res.items()}
    return dict(dt=dist["t"], ds=dist["s"], It=res["t"], Is=res["s"], P=P, chief0=f0)

# ---- Self-check ------------------------------------------------------------------------
def paraxial_v(f=F, u=U):
    return 1 / (1 / f - 1 / u)

def selfcheck():
    """On-axis virtual image distance from the trace vs the thin-lens equation."""
    # paraxial ray from the on-axis panel point
    P = np.array([[0, 0, Z_PANEL], [0, 0, Z_PANEL]])
    D = np.array([[1e-4, 0, 1.0], [-1e-4, 0, 1.0]])
    fw = trace_forward(P, D)
    q, _ = closest_points(fw["P2"][0], fw["d"][0], fw["P2"][1], fw["d"][1])
    return q[2], paraxial_v()

if __name__ == "__main__":
    z, v = selfcheck()
    print(f"n_d {N_D:.4f}  traced virtual image z {z:.1f} mm (from H' at z=0)   thin lens v {v:.1f} mm")
    # back-focus check: collimated rays at several heights
    for r in (5, 50, 100, 150, 210):
        print(r, "focus error", float(_design_focus_error(np.array([r * 1.0]), facet_tilt(np.array([r * 1.0])))[0]),
              "facet angle", round(float(facet_angle_deg(r)), 2), "depth", round(float(groove_depth(r)), 3))
    ip = image_point(0.0, 0.0)
    print("image distance on axis from eye, t/s", ip["dt"], ip["ds"])
    for ax in (2, 4, 6, 7):
        ip = image_point(ax, 0.0)
        print("field", ax, "panel x", round(float(ip["P"][0, 0]), 2), "dist t/s", ip["dt"].round(0), ip["ds"].round(0))
