"""Figures for sections 1-2: the stage in the car, the unfolded axis, and how a Fresnel lens works."""
import math
import numpy as np
from svgkit import *
import optics as O
import teeth as TT
from calc import V, D

def _car_frame():
    """Car side-view coordinates (mm, x forward, z up, eye at the origin) and the combiner fold."""
    C = D["car"]
    lk = math.radians(float(V["lookdown"]))
    u = np.array([math.cos(lk), -math.sin(lk)])               # eye -> combiner
    nperp = np.array([math.sin(lk), math.cos(lk)])            # 'up' across the line of sight
    comb = np.array(C["comb"])
    din = np.array([0.0, 1.0]); dout = -u
    Nc = (dout - din) / np.linalg.norm(dout - din)
    def unfold(z_axis, lat):
        """Unfolded optical-axis point (z from the lens toward the eye, lateral = vertical field) -> car point (virtual)."""
        return np.array(C["eye"]) + (O.EYE_Z - z_axis) * u + lat * nperp
    def real(q):
        q = np.asarray(q, float)
        if np.dot(q - comb, Nc) < 0:                         # beyond the combiner: reflect into the dash
            return q - 2 * np.dot(q - comb, Nc) * Nc
        return q
    return C, u, nperp, comb, Nc, unfold, real

def tooth_poly(ra, rb, X, Z, bottom_px, n=500):
    """Screen polygon of the real tooth profile between radii ra and rb, closed down to bottom_px."""
    def ztop(q):
        kq = int(math.floor(q / O.PITCH + 1e-9)); return TT.sag(q) - TT.sag((kq + 1) * O.PITCH)
    qs = np.linspace(ra, rb, n)
    poly = [(X(ra), bottom_px)]
    prev = None
    for q in qs:
        kq = int(math.floor(q / O.PITCH + 1e-9))
        if prev is not None and kq != prev:
            qb = kq * O.PITCH
            poly += [(X(qb), Z(0)), (X(qb), Z(TT.sag(qb) - TT.sag(qb + O.PITCH)))]
        poly.append((X(q), Z(ztop(q))))
        prev = kq
    poly.append((X(rb), bottom_px))
    return poly

@fig("car")
def f_car():
    W, H = 680, 840
    s = Svg(W, H, "Stage 1 in the car, side view: whole scene to scale on top, the rig enlarged below with every distance")
    s.rect(0, 0, W, H, fill=SURF)
    C, u, nperp, comb, Nc, unfold, real = _car_frame()
    cowl = np.array(C["cowl"]); rake = math.radians(C["rake"])
    ws_z = lambda x: cowl[1] + (cowl[0] - x) * math.tan(rake)
    header = np.array([cowl[0] - (250 - cowl[1]) / math.tan(rake), 250.0])
    tang = np.array([Nc[1], -Nc[0]])
    CH = 110.0                                              # combiner half-length (ASSUMED)
    c1 = comb - CH * tang; c2 = comb + CH * tang
    if c1[1] < c2[1]:
        c1, c2 = c2, c1
    # ---------- tier A ----------
    step(s, 16, 28, "A", "The whole scene, to scale (1 px ≈ 9 mm)")
    k = 0.108; ox, oy = 60, 104
    P = lambda q: (ox + q[0] * k, oy - q[1] * k)
    road = C["road_z"]
    body = [(-900, 330), header, cowl, (2250, -480), (2330, -620), (2330, -820), (-900, -820)]
    s.poly([P(q) for q in body], fill="#f2f1ed", stroke=AXIS, sw=1)
    s.line(*P(header), *P(cowl), stroke=BLUE, sw=2.6)
    dash = [(300, C["dash_z"]), (cowl[0] - 60, C["dash_z"]), (cowl[0] - 60, C["dash_z"] - 140), (300, C["dash_z"] - 240)]
    s.poly([P(q) for q in dash], fill="#e1e0d9", stroke=AXIS, sw=0.8)
    s.rect(14, P((0, road))[1], W - 28, 7, fill="#d9d8d2")
    s.circle(*P((0, 0)), 4.5, fill=INK)
    s.text(P((0, 0))[0] - 10, P((0, 0))[1] + 4, "eye", size=11, anchor="end", weight=700)
    ln = np.array(C["lens"])
    s.line(*P(ln - (150, 0)), *P(ln + (150, 0)), stroke=TEAL, sw=2.4)
    s.line(*P(c1), *P(c2), stroke=BLUE, sw=2.2)
    d_img = abs(O.paraxial_v()) + O.EYE_Z
    vi_c = np.array(C["eye"]) + d_img * u
    half_h = float(V["img_h"]) * 1000 / 2
    vt = vi_c + half_h * nperp; vb = vi_c - half_h * nperp
    for q in (vt, vb):
        s.line(*P((0, 0)), *P(q), stroke=ORANGE, sw=1, extra='stroke-dasharray="4 3"')
    s.line(*P(vt), *P(vb), stroke=ORANGE, sw=4)
    s.line(*P((0, 0)), W - 16, P((0, 0))[1], stroke=MUTED, sw=0.8, extra='stroke-dasharray="2 4"')
    s.text(W - 18, P((0, 0))[1] - 6, "eye level (the lead car, 30 m ahead, is off the page)", size=10, fill=INK2, anchor="end")
    s.text(W - 18, P(vb)[1] + 16, f"virtual image {V['img_w']} × {V['img_h']} m, {V['d_eye_img']} m from the eye", size=10.5, fill=ORANGE, anchor="end", weight=700)
    s.text(W - 18, P(vb)[1] + 30, f"its centre is {V['img_above_road']} m above the road", size=10.5, fill=INK2, anchor="end")
    s.text(*P(header + (cowl - header) * 0.18 + np.array([60, 30])), "windshield", size=10, fill=BLUE)
    s.text(P(ln)[0] - 20, P(ln)[1] + 30, "rig", size=10.5, fill=TEAL, weight=700, anchor="end")
    dim(s, *P((0, road - 150)), *P((d_img * u[0], road - 150)), f"{V['img_ahead']} m ahead", off=0, size=10.5)
    s.text(16, P((0, road))[1] + 40, "road 1.2 m below the eye (ASSUMED)", size=10, fill=INK2)
    # ---------- tier B ----------
    y0 = 292
    s.line(14, y0 - 10, W - 14, y0 - 10, stroke=GRID, sw=1)
    step(s, 16, y0 + 16, "B", "The rig, enlarged (1 px ≈ 1.4 mm)",
         sub="Solid lines: the real light path. Dashed: where the eye thinks the light comes from.")
    k2 = 0.70; ox2, oy2 = 40, y0 + 95
    Q = lambda q: (ox2 + q[0] * k2, oy2 - q[1] * k2)
    # windshield and dash
    s.line(*Q((610, ws_z(610))), *Q((905, ws_z(905))), stroke=BLUE, sw=2.2, extra='opacity="0.55"')
    s.text(Q((640, ws_z(640)))[0] + 14, Q((640, ws_z(640)))[1] - 4, "windshield", size=10.5, fill=BLUE)
    dz = C["dash_z"]
    s.rect(Q((300, dz))[0], Q((300, dz))[1], Q((905, dz))[0] - Q((300, dz))[0], 10, fill="#e1e0d9", stroke=AXIS, sw=0.8, extra='opacity="0.85"')
    s.text(Q((905, dz))[0], Q((905, dz))[1] + 26, "dash top (ASSUMED 300 mm below the eye)", size=10.5, fill=INK2, anchor="end")
    # rays
    hf = float(V["hfh"])
    for a, col in ((hf, PURPLE), (0.0, ORANGE), (-hf, BLUE)):
        b = O.panel_point(np.array([0.0]), np.array([a]))
        e = unfold(O.EYE_Z, 0.0); l1 = unfold(0.0, b["P1"][0, 1]); p3 = unfold(O.Z_PANEL, b["P3"][0, 1])
        dvec = l1 - e
        cm = e + np.dot(comb - e, Nc) / np.dot(dvec, Nc) * dvec
        s.line(*Q(e), *Q(cm), stroke=col, sw=1.7)
        s.line(*Q(cm), *Q(real(l1)), stroke=col, sw=1.7)
        s.line(*Q(real(l1)), *Q(real(p3)), stroke=col, sw=1.7)
        far = e + dvec / np.linalg.norm(dvec) * 905
        s.line(*Q(cm), *Q(far), stroke=col, sw=1, extra='stroke-dasharray="5 4"')
    # road light along the centre line of sight
    rl0 = np.array(C["eye"]) + 900 * u; rl1 = np.array(C["eye"]) + 600 * u
    s.text(*Q((905, -175)), "road light reaches the eye through the combiner (70%)", size=10, fill=INK2, anchor="end")
    # components
    s.rect(Q(ln - (150, 0))[0], Q(ln)[1] - 2.5, 300 * k2, 5, fill=TEAL)
    s.text(Q(ln + (150, 0))[0] + 8, Q(ln)[1] - 2, "Fresnel lens", size=12, weight=700, fill=TEAL)
    s.text(Q(ln + (150, 0))[0] + 8, Q(ln)[1] + 13, f"300 × 300 mm, f = {V['f']} mm", size=10.5, fill=INK2)
    s.text(Q(ln + (150, 0))[0] + 8, Q(ln)[1] + 27, "grooves face up", size=10.5, fill=INK2)
    s.line(*Q(c1), *Q(c2), stroke=BLUE, sw=3.2)
    s.text(Q(c1)[0] - 8, Q(c1)[1] - 2, "combiner, 70/30 glass", size=12, weight=700, fill=BLUE, anchor="end")
    s.text(Q(c1)[0] - 8, Q(c1)[1] + 13, f"light meets it at {V['i_comb']}°", size=10.5, fill=INK2, anchor="end")
    pan_c = real(unfold(O.Z_PANEL, 0.0))
    pw = 40 * k2
    s.rect(Q(pan_c)[0] - pw / 2, Q(pan_c)[1] - 1, pw, 5, fill=INK)
    s.text(Q(pan_c)[0] + pw / 2 + 10, Q(pan_c)[1] - 6, "panel crop (40 mm of the 80 × 40 mm)", size=11, weight=700)
    s.text(Q(pan_c)[0] + pw / 2 + 10, Q(pan_c)[1] + 10, f"{V['lens_below_dash']} mm below the dash top: a straight", size=10.5, fill=CRIT)
    s.text(Q(pan_c)[0] + pw / 2 + 10, Q(pan_c)[1] + 24, "path does not fit. Section 11 folds it.", size=10.5, fill=CRIT)
    s.circle(*Q((0, 0)), 6, fill=INK)
    s.text(Q((0, 0))[0] + 2, Q((0, 0))[1] - 14, "eye", size=12, anchor="middle", weight=700)
    # dimensions
    xl = ln[0] - 150
    dim(s, *Q((xl - 18, ln[1])), *Q((xl - 18, pan_c[1])), f"{V['u']} mm", off=0, size=10.5)
    s.line(*Q((comb[0] - 8, comb[1])), *Q((xl - 26, comb[1])), stroke=AXIS, sw=0.7, extra='stroke-dasharray="2 2"')
    dim(s, *Q((xl - 18, comb[1])), *Q((xl - 18, ln[1])), f"{V['comb_lens']} mm", off=0, size=10.5)
    mid = np.array(C["eye"]) + 0.42 * (comb - np.array(C["eye"]))
    s.text(Q(mid)[0], Q(mid)[1] + 52, f"eye to combiner {V['eye_comb']} mm", size=10.5, fill=INK2, anchor="middle")
    legend(s, 40, oy2 + 250, [(f"top of the field (+{V['hfh']}°)", PURPLE), ("centre", ORANGE), (f"bottom (−{V['hfh']}°)", BLUE)], size=10.5)
    note(s, 16, H - 50, [f"Eye to lens along the light path: {V['eye_comb']} + {V['comb_lens']} = {V['eye_z']} mm (ASSUMED). Rays are traced through the lens model (section A.2).",
                         "Car outline, dash height, combiner size and the 550 / 150 mm split are ASSUMED; the plan fixes f, u, the crop and the 70/30 glass."], size=10.5, lh=17)
    return s

@fig("axis")
def f_axis():
    W, H = 680, 600
    s = Svg(W, H, "The light path unfolded onto one straight axis, with the scale broken between the virtual image and the panel")
    s.rect(0, 0, W, H, fill=SURF)
    s.text(16, 26, "The combiner is a flat mirror, so the path can be straightened onto one axis.", size=12.5, weight=700)
    s.text(16, 44, "Distances along the axis to scale (0.5 px per mm); heights ×3 so the rays can be told apart.", size=10.5, fill=INK2)
    ay = 270
    k = 0.5; kv = 1.5
    xz = lambda z: 126 + (z + 330) * k
    yv = lambda y: ay - y * kv
    xb = 96
    s.line(24, ay, xb - 8, ay, stroke=AXIS, sw=1)
    s.line(xb + 10, ay, xz(720) + 12, ay, stroke=AXIS, sw=1)
    for dx in (0, 6):
        s.line(xb - 4 + dx, ay - 9, xb + 2 + dx, ay + 9, stroke=INK2, sw=1.2)
    s.text(xb + 1, ay + 26, "scale", size=9.5, fill=MUTED, anchor="middle")
    s.text(xb + 1, ay + 38, "break", size=9.5, fill=MUTED, anchor="middle")
    # virtual image (symbolic size)
    s.line(52, ay - 92, 52, ay + 92, stroke=ORANGE, sw=4.5)
    s.text(52, ay - 102, "virtual image", size=11.5, weight=700, fill=ORANGE, anchor="middle")
    s.text(52, ay + 110, f"{V['img_w']} × {V['img_h']} m", size=10.5, fill=INK2, anchor="middle")
    s.text(52, ay + 124, f"{V['v']} mm", size=10.5, fill=INK2, anchor="middle")
    s.text(52, ay + 138, "before the lens", size=10.5, fill=INK2, anchor="middle")
    pz = O.Z_PANEL
    s.rect(xz(pz) - 3, yv(20), 6, 40 * kv, fill=INK)
    s.text(xz(pz), yv(20) - 10, "panel", size=11.5, weight=700, anchor="middle")
    s.text(xz(pz) + 2, yv(-20) + 16, "crop", size=10, fill=INK2, anchor="middle")
    s.text(xz(pz) + 2, yv(-20) + 28, "40 mm", size=10, fill=INK2, anchor="middle")
    zF = O.Z_H - O.F; zF2 = O.F
    for z, lab in ((zF, "F"), (zF2, "F′")):
        s.circle(xz(z), ay, 3.4, fill=INK2)
        s.text(xz(z), ay + 18, lab, size=11.5, fill=INK2, anchor="middle", weight=700)
    # lens, truncated at ±95 mm
    LH = 95
    s.rect(xz(-O.T) - 2, yv(LH), 4.5, 2 * LH * kv, fill=TEAL)
    for sgn in (1, -1):
        yy = yv(sgn * LH)
        s.line(xz(-1) - 7, yy - sgn * 3, xz(-1) + 7, yy + sgn * 3, stroke=TEAL, sw=1.2)
    s.text(xz(0) - 6, yv(LH) - 22, "Fresnel lens", size=11.5, weight=700, fill=TEAL, anchor="end")
    s.text(xz(0) - 6, yv(LH) - 8, "(continues to ±150 mm)", size=9.5, fill=INK2, anchor="end")
    zc = O.EYE_Z - float(V["eye_comb"].replace(",", ""))
    s.line(xz(zc), yv(LH), xz(zc), yv(-LH), stroke=BLUE, sw=2, extra='stroke-dasharray="6 3"')
    s.text(xz(zc) + 6, yv(LH) - 8, "combiner", size=11.5, weight=700, fill=BLUE)
    s.circle(xz(O.EYE_Z), ay, 6, fill=INK)
    s.text(xz(O.EYE_Z), ay - 14, "eye", size=12, weight=700, anchor="middle")
    # traced ray from the eye to the top edge of the crop; backward extension to the virtual image
    b = O.panel_point(np.array([0.0]), np.array([float(V["hfh"])]))
    pts = [(xz(O.EYE_Z), yv(0)), (xz(0), yv(b["P1"][0, 1])), (xz(-O.T), yv(b["P2"][0, 1])), (xz(pz), yv(b["P3"][0, 1]))]
    polyline(s, pts, stroke=PURPLE, sw=2)
    # a second ray from the same panel point to the lower edge of a 6 mm pupil, to show both diverge from the image point
    s.line(xz(0), yv(b["P1"][0, 1]), xb + 14, ay - 92, stroke=PURPLE, sw=1.1, extra='stroke-dasharray="5 4"')
    s.line(xb - 10, ay - 92, 56, ay - 92, stroke=PURPLE, sw=1.1, extra='stroke-dasharray="5 4"')
    s.text(282, ay - 132, "the eye traces the ray back:", size=10.5, fill=PURPLE, anchor="end")
    s.text(282, ay - 118, "it seems to come from the image", size=10.5, fill=PURPLE, anchor="end")
    # dimensions
    dy = ay + 165
    dim(s, xz(pz), dy, xz(O.Z_H), dy, f"u = {V['u']} mm (panel to the principal plane H)", off=0, size=10.5)
    dim(s, xz(zF), dy + 36, xz(O.Z_H), dy + 36, f"f = {V['f']} mm: F lies {V['sun_focus_beyond']} mm beyond the panel", off=0, size=10.5)
    dim(s, xz(0), dy + 72, xz(zc), dy + 72, f"{V['comb_lens']} mm", off=0, size=10.5)
    dim(s, xz(zc), dy + 72, xz(O.EYE_Z), dy + 72, f"{V['eye_comb']} mm", off=0, size=10.5)
    s.line(16, H - 56, W - 16, H - 56, stroke=GRID, sw=1)
    s.text(16, H - 36, f"Image distance from the eye: {V['v']} + {V['eye_z']} mm = {V['d_eye_img']} m. Field of view from the eye: {V['fov_eye_w']}° × {V['fov_eye_h']}°.", size=11.5, weight=700)
    s.text(16, H - 18, "The plan's 16° × 8° is the same image measured from the lens, not the eye: 2 × atan(0.6 ÷ 4.2).", size=10.5, fill=INK2)
    # inset: principal plane inside the sheet
    ix, iy, iw, ih = 440, 64, 222, 104
    s.rect(ix, iy, iw, ih, fill="#fff", stroke=AXIS, sw=1, rx=4)
    s.text(ix + 8, iy + 16, "inside the 2 mm sheet, ×30", size=10, fill=INK2, weight=700)
    kk = 30.0
    sx = lambda z: ix + 40 + (z + O.T) * kk
    s.rect(sx(-O.T), iy + 26, O.T * kk, ih - 40, fill=ACRYLIC, stroke=ACRYLIC_S, sw=1)
    s.line(sx(O.Z_H), iy + 22, sx(O.Z_H), iy + ih - 10, stroke=CRIT, sw=1.4, extra='stroke-dasharray="3 2"')
    s.text(sx(O.Z_H) - 4, iy + 40, "H", size=11, fill=CRIT, weight=700, anchor="end")
    s.text(sx(-O.T), iy + ih - 2, "flat", size=9.5, fill=INK2, anchor="middle")
    s.text(sx(0), iy + ih - 2, "grooves", size=9.5, fill=INK2, anchor="middle")
    s.text(ix + iw - 8, iy + 52, f"H sits {V['zh']} mm", size=10, fill=INK2, anchor="end")
    s.text(ix + iw - 8, iy + 66, "inside the flat face;", size=10, fill=INK2, anchor="end")
    s.text(ix + iw - 8, iy + 80, f"panel to flat face {V['u_flat']}", size=10, fill=INK2, anchor="end")
    s.line(xz(-1), yv(LH) - 30, ix + 40, iy + ih, stroke=AXIS, sw=0.8, extra='stroke-dasharray="2 2"')
    return s

# ---------- How a Fresnel lens is made ----------
@fig("collapse")
def f_collapse():
    W, H = 680, 830
    s = Svg(W, H, "From a solid lens to a Fresnel lens: the same curved surface cut into rings and lowered onto a thin sheet")
    s.rect(0, 0, W, H, fill=SURF)
    r = D["asphere_r"]; sg = D["asphere_sag"]
    R = O.HALF
    k = 1.6                                                  # px per mm for the half-lens (0..150 mm)
    def draw_half(x0, y0, profile_pts, base_y=None, fill=ACRYLIC, stroke=ACRYLIC_S):
        pts = [(x0 + rr * k, y0 - zz * k) for rr, zz in profile_pts]
        s.poly(pts, fill=fill, stroke=stroke, sw=1)
    # (a) solid asphere: thickness at centre = sag(150) depth + 2 mm
    edge = -np.interp(R, r, sg)
    x0 = 60
    y_a = 80
    step(s, 16, 30, "A", "A solid lens that does the same job")
    s.text(16, 50, f"Same focal length ({V['f']} mm), round, 300 mm across, drawn to scale (centre to edge). Thickness at the centre: {V['asph_sag_edge']} mm plus the 2 mm base.", size=10.5, fill=INK2)
    prof = [(0, -O.T)] + [(rr, np.interp(rr, r, sg) + edge) for rr in np.linspace(0, R, 120)] + [(R, -O.T)]
    ya = y_a + edge * k - 6
    draw_half(x0, ya, prof)
    s.line(x0, ya + O.T * k + 4, x0, ya - edge * k - 16, stroke=MUTED, sw=0.8, extra='stroke-dasharray="4 3"')
    dim(s, x0 + R * k + 14, ya + O.T * k, x0 + R * k + 14, ya - edge * k, f"{V['asph_sag_edge']} mm", off=0, size=10.5)
    s.text(x0 + R * k + 70, ya - edge * k * 0.6, f"weight ≈ {V['bulk_kg']} kg of PMMA", size=11.5, weight=600)
    s.text(x0 + R * k + 70, ya - edge * k * 0.6 + 17, "(a 300 mm square would be heavier:", size=10.5, fill=INK2)
    s.text(x0 + R * k + 70, ya - edge * k * 0.6 + 31, f"its corners need {V['asph_sag_corner']} mm of sag)", size=10.5, fill=INK2)
    s.text(x0 + R * k + 70, ya - edge * k * 0.6 + 52, f"A spherical lens can't do it at all: R = {V['r_pcx']} mm,", size=10.5, fill=INK2)
    s.text(x0 + R * k + 70, ya - edge * k * 0.6 + 66, f"so its widest possible size is {V['pcx_max_d']} mm.", size=10.5, fill=INK2)
    # (b) cut into rings (10 mm for clarity)
    ring = 15.0
    y_b = ya + 52
    step(s, 16, y_b, "B", f"Cut it into rings ({ring:.0f} mm wide here so you can see them; the real ones are {V['pitch']} mm)")
    yb = y_b + edge * k + 16
    edges_r = np.arange(0, R + 1e-6, ring)
    for i in range(len(edges_r) - 1):
        r0, r1 = edges_r[i], edges_r[i + 1]
        rr = np.linspace(r0, r1, 12)
        zz = np.interp(rr, r, sg) + edge
        base = np.interp(r1, r, sg) + edge
        # the part above the next ring's base level is the useful sliver (orange), the rest is dead weight (grey)
        top = [(x0 + q * k, yb - z * k) for q, z in zip(rr, zz)]
        s.poly([(x0 + r0 * k, yb + O.T * k)] + top + [(x0 + r1 * k, yb + O.T * k)], fill="#eceae4", stroke=AXIS, sw=0.6)
        sl = top + [(x0 + r1 * k, yb - base * k), (x0 + r0 * k, yb - base * k)]
        s.poly(sl, fill=ORANGE_T, stroke=ORANGE, sw=1)
        s.line(x0 + r0 * k, yb + O.T * k, x0 + r0 * k, yb - zz[0] * k, stroke=INK2, sw=0.6, extra='stroke-dasharray="2 2"')
    s.text(x0 + R * k + 14, yb - edge * k * 0.75, "orange: the thin sliver of", size=10.5, fill=ORANGE, weight=600)
    s.text(x0 + R * k + 14, yb - edge * k * 0.75 + 14, "curved surface on each ring.", size=10.5, fill=ORANGE, weight=600)
    s.text(x0 + R * k + 14, yb - edge * k * 0.75 + 32, "Grey: material underneath that", size=10.5, fill=INK2)
    s.text(x0 + R * k + 14, yb - edge * k * 0.75 + 46, "only carries light straight", size=10.5, fill=INK2)
    s.text(x0 + R * k + 14, yb - edge * k * 0.75 + 60, "through. It adds no bending,", size=10.5, fill=INK2)
    s.text(x0 + R * k + 14, yb - edge * k * 0.75 + 74, "so it can go.", size=10.5, fill=INK2)
    # (c) lowered slivers
    y_c = yb + 44
    step(s, 16, y_c, "C", "Drop every sliver onto a thin base: the result is a Fresnel lens")
    yc = y_c + 54
    pts = []
    for i in range(len(edges_r) - 1):
        r0, r1 = edges_r[i], edges_r[i + 1]
        rr = np.linspace(r0, r1, 12)
        zz = np.interp(rr, r, sg) - np.interp(r1, r, sg)
        pts += [(x0 + r0 * k, yc)] + [(x0 + q * k, yc - z * k) for q, z in zip(rr, zz)]
    s.poly([(x0, yc + O.T * k)] + pts + [(x0 + R * k, yc), (x0 + R * k, yc + O.T * k)], fill=ACRYLIC, stroke=ACRYLIC_S, sw=1)
    s.text(x0 + R * k + 14, yc - 18, "Each tooth's slanted face has the same", size=10.5, fill=INK2)
    s.text(x0 + R * k + 14, yc - 4, "angle as the solid lens at that radius,", size=10.5, fill=INK2)
    s.text(x0 + R * k + 14, yc + 10, "so light bends the same way. The", size=10.5, fill=INK2)
    s.text(x0 + R * k + 14, yc + 24, "vertical steps do no useful work.", size=10.5, fill=INK2)
    # (d) the real lens: 2 mm sheet, 0.5 mm teeth (magnified inset)
    y_d = yc + 50
    step(s, 16, y_d, "D", f"The real lens: a {V['t']} mm sheet, {V['n_grooves_edge']} teeth from centre to edge ({V['n_grooves_corner']} to the corner), {V['sheet_g']} g", size=12.5)
    yd = y_d + 34
    s.rect(x0, yd, R * k, O.T * k, fill=ACRYLIC, stroke=ACRYLIC_S, sw=1)
    s.text(x0 + R * k + 14, yd + 5, "at this scale the teeth are a", size=10.5, fill=INK2)
    s.text(x0 + R * k + 14, yd + 19, "fuzz on the top surface", size=10.5, fill=INK2)
    # inset: 6 teeth at r = 100 mm at 120 px/mm
    ix, iy, iw, ih = 60, yd + 30, 560, 190
    s.rect(ix, iy, iw, ih, fill="#fff", stroke=AXIS, sw=1, rx=5)
    kk = 150.0                                               # px per mm
    r_c = 100.0; ra, rb = r_c - 1.75, r_c + 1.75
    base_y = iy + 150
    X = lambda q: ix + 20 + (q - ra) * kk
    Z = lambda z: base_y - z * kk
    s.poly(tooth_poly(ra, rb, X, Z, iy + ih - 8), fill=ACRYLIC, stroke=ACRYLIC_S, sw=1.2)
    s.text(ix + 10, iy + 18, f"Six teeth around r = 100 mm, magnified 150×. Each is {V['pitch']} mm wide and {V['fd_100']} mm tall here.", size=11, weight=600)
    s.text(ix + iw - 10, iy + ih + 16, "the sheet continues below (2 mm in all)", size=10, fill=MUTED, anchor="end")
    s.line(x0 + r_c * k, yd - 3, ix + 20 + 1.75 * kk, iy, stroke=AXIS, sw=0.8, extra='stroke-dasharray="2 2"')
    s.circle(x0 + r_c * k, yd - 2, 2.5, fill=CRIT)
    # tooth labels on one tooth
    k0 = int(math.floor(r_c / O.PITCH))
    t0 = k0 * O.PITCH; t1 = t0 + O.PITCH
    h0 = TT.sag(t0) - TT.sag(t1)
    s.line(X(t0), Z(h0), X(t1), Z(0), stroke=ORANGE, sw=3)
    s.line(X(t1), Z(0), X(t1), Z(TT.sag(t1) - TT.sag(t1 + O.PITCH)), stroke=CRIT, sw=3)
    s.text(X((t0 + t1) / 2) + 6, Z(h0 / 2) - 14, "facet", size=11.5, fill=ORANGE, weight=700)
    s.text(X(t1) + 6, Z(h0) - 6, "draft (step)", size=11.5, fill=CRIT, weight=700)
    dim(s, X(t0), Z(0) + 22, X(t1), Z(0) + 22, f"pitch {V['pitch']} mm", off=0, size=10.5)
    s.text(ix + iw - 10, iy + 40, "left: toward the lens centre; right: toward the edge", size=10, fill=MUTED, anchor="end")
    return s

@fig("anatomy")
def f_anatomy():
    W, H = 680, 760
    s = Svg(W, H, "Anatomy of the teeth: one tooth drawn large with every part named, and the tooth shape at five radii")
    s.rect(0, 0, W, H, fill=SURF)
    step(s, 16, 28, "A", "One tooth at r = 100 mm, magnified 600×")
    kk = 600.0
    r_c = 100.0; k0 = int(round(r_c / O.PITCH)); t0 = k0 * O.PITCH; t1 = t0 + O.PITCH
    ra, rb = t0 - 0.22, t1 + 0.10
    X = lambda q: 110 + (q - ra) * kk
    base = 340
    Z = lambda z: base - z * kk
    poly = tooth_poly(ra, rb, X, Z, base + 120)
    s.poly(poly, fill=ACRYLIC, stroke=ACRYLIC_S, sw=1.6)
    s.text(X(ra) + 6, base + 112, "PMMA (acrylic), continues 2 mm down to the flat face", size=10.5, fill=ACRYLIC_S)
    h0 = TT.sag(t0) - TT.sag(t1)
    g = float(O.facet_angle_deg((t0 + t1) / 2))
    # facet highlight
    s.line(X(t0), Z(h0), X(t1), Z(0), stroke=ORANGE, sw=4)
    s.text(X(t0 + 0.30), Z(h0 * 0.42) - 40, "active facet", size=12, weight=700, fill=ORANGE)
    s.text(X(t0 + 0.30), Z(h0 * 0.42) - 25, "bends the light; slope follows", size=10.5, fill=INK2)
    s.text(X(t0 + 0.30), Z(h0 * 0.42) - 11, "the solid lens at this radius", size=10.5, fill=INK2)
    # draft walls
    s.line(X(t0), Z(0), X(t0), Z(h0), stroke=CRIT, sw=4)
    s.text(X(t0) - 10, Z(h0 / 2) + 4, "draft wall", size=12, weight=700, fill=CRIT, anchor="end")
    s.text(X(t0) - 10, Z(h0 / 2) + 19, "(step back up)", size=10.5, fill=INK2, anchor="end")
    # tip and valley
    s.circle(X(t0), Z(h0), 4, fill=INK)
    s.text(X(t0) + 8, Z(h0) - 8, "tip", size=11, weight=600)
    s.circle(X(t1), Z(0), 4, fill=INK)
    s.text(X(t1) + 8, Z(0) + 18, "valley", size=11, weight=600)
    # dimensions
    dim(s, X(t0), Z(0) + 40, X(t1), Z(0) + 40, f"pitch {V['pitch']} mm", off=0, size=11)
    dim(s, X(rb) + 40, Z(0), X(rb) + 40, Z(h0), f"depth {V['fd_100']} mm", off=0, size=11, text_off=14)
    s.line(X(t0) + 6, Z(h0), X(rb) + 46, Z(h0), stroke=AXIS, sw=0.7, extra='stroke-dasharray="2 2"')
    # facet angle arc at the valley
    arc(s, X(t1), Z(0), 70, 180 - g, 180, color=ORANGE, sw=1.4, label=f"{V['fa_100']}°", size=12, lr=90, weight=700)
    s.line(X(t1), Z(0), X(t1) - 200, Z(0), stroke=MUTED, sw=0.8, extra='stroke-dasharray="4 3"')
    s.text(X(t1) - 205, Z(0) + 14, "sheet plane", size=10, fill=MUTED, anchor="start")
    # normal to the facet
    mx, mz = (t0 + t1) / 2, h0 / 2
    nx, nz = math.sin(math.radians(g)), math.cos(math.radians(g))
    s.line(X(mx), Z(mz), X(mx) + nx * 150, Z(mz) - nz * 150, stroke=INK2, sw=1.2, extra='stroke-dasharray="5 3"')
    s.text(X(mx) + nx * 150 + 6, Z(mz) - nz * 150, "facet normal", size=10.5, fill=INK2)
    s.text(X(mx) + nx * 150 + 6, Z(mz) - nz * 150 + 14, f"tilted {V['fa_100']}° outward", size=10.5, fill=INK2)
    # axis direction hint
    s.text(W - 20, 56, "left: toward the lens centre; right: toward its edge", size=10.5, fill=MUTED, anchor="end")
    s.text(W - 20, 72, "grooves face the eye (up)", size=10.5, fill=MUTED, anchor="end")
    # ---------- B: five radii ----------
    y0 = 500
    s.line(14, y0 - 18, W - 14, y0 - 18, stroke=GRID, sw=1)
    step(s, 16, y0, "B", "The same tooth at five radii, all at 160×: depth and angle grow toward the edge")
    k2 = 160.0
    cols_x = [40, 168, 296, 424, 552]
    for (rr, a, h, kz), cx in zip(D["facet_rows"], cols_x):
        kz0 = int(math.floor(rr / O.PITCH)); q0 = kz0 * O.PITCH
        q0 = max(q0, 0.0); q1 = q0 + O.PITCH
        hh = TT.sag(q0) - TT.sag(q1)
        bx = cx; bz = y0 + 150
        pts = [(bx, bz + 30), (bx, bz), (bx, bz - hh * k2), (bx + O.PITCH * k2, bz), (bx + O.PITCH * k2, bz + 30)]
        s.poly(pts, fill=ACRYLIC, stroke=ACRYLIC_S, sw=1.2)
        s.line(bx, bz - hh * k2, bx + O.PITCH * k2, bz, stroke=ORANGE, sw=2.4)
        s.line(bx, bz, bx, bz - hh * k2, stroke=CRIT, sw=2.4)
        s.text(bx + 40, bz + 50, f"r = {rr} mm", size=11.5, weight=700, anchor="middle")
        s.text(bx + 40, bz + 66, f"{a:.1f}°, {h:.2f} mm", size=10.5, fill=INK2, anchor="middle")
        s.text(bx + 40, bz + 80, f"tooth no. {kz}", size=10, fill=MUTED, anchor="middle")
    s.text(16, H - 10, "r = 212 mm is the corner of the 300 mm square. The profile comes from solving each facet so that parallel light focuses at 300 mm (section A.2).", size=10, fill=INK2)
    return s

@fig("facetplot")
def f_facetplot():
    W, H = 680, 380
    s = Svg(W, H, "Facet angle and groove depth against radius for the 300 mm focal length, 0.5 mm pitch PMMA lens")
    s.rect(0, 0, W, H, fill=SURF)
    ax = Axes(s, 70, 40, 520, 270, (0, 215), (0, 60))
    ax.frame([0, 25, 50, 75, 100, 125, 150, 175, 200], [0, 10, 20, 30, 40, 50, 60], xlabel="radius from the lens centre (mm)", ylabel="facet angle (degrees)")
    ax.curve([(r, a) for r, a, h in D["facet_curve"]], stroke=ORANGE, sw=2.6)
    # depth on a right axis 0..0.8 mm
    dep = lambda h: ax.y + ax.h - h / 0.8 * ax.h
    polyline(s, [(ax.X(r), dep(h)) for r, a, h in D["facet_curve"]], stroke=CRIT, sw=2.2, extra='stroke-dasharray="6 3"')
    for v in (0, 0.2, 0.4, 0.6, 0.8):
        s.text(ax.x + ax.w + 6, dep(v) + 4, f"{v:.1f}", size=11, fill=CRIT)
    cx, cy = ax.x + ax.w + 46, ax.y + ax.h / 2
    s.text(cx, cy, "groove depth (mm)", size=11.5, fill=CRIT, anchor="middle", weight=500, extra=f'transform="rotate(90 {cx} {cy})"')
    for xv, lab in ((150, "edge of the square"), (212.1, "corner")):
        s.line(ax.X(xv), ax.y, ax.X(xv), ax.y + ax.h, stroke=INK2, sw=1, extra='stroke-dasharray="3 3"')
        s.text(ax.X(xv) - 4, ax.y + 14, lab, size=10, fill=INK2, anchor="end")
    for r, a, h, k in D["facet_rows"]:
        s.circle(ax.X(r), ax.Y(a), 3.5, fill=ORANGE)
    legend(s, 90, 62, [("facet angle", ORANGE), ("groove depth (right scale)", CRIT)], size=11)
    s.text(16, H - 14, f"Pitch is constant ({V['pitch']} mm), so the depth is pitch × tan(angle). Critical angle in PMMA: {V['crit']}°.", size=10.5, fill=INK2)
    return s

@fig("onefacet")
def f_onefacet():
    W, H = 680, 760
    s = Svg(W, H, "One ray through the sheet at r = 100 mm, with Snell's law at each surface and every angle labelled")
    s.rect(0, 0, W, H, fill=SURF)
    FX = D["facet_example"]
    s.text(16, 28, "A ray from the centre of the panel to r = 100 mm, followed through both surfaces", size=13, weight=700)
    s.text(16, 46, "Angles are the traced values. The tooth and the sheet are drawn large; the angles are true.", size=10.5, fill=INK2)
    g = FX["g"]; a_air = FX["a_air"]; a_in = FX["a_in"]; a_out = FX["a_out"]
    yflat = 450; yfac = 310
    xL, xR = 40, 640
    fx0, fx1 = 220, 460
    fz = (fx1 - fx0) * math.tan(math.radians(g))
    poly = [(xL, yflat), (xL, yfac), (fx0, yfac), (fx0, yfac - fz), (fx1, yfac), (xR, yfac), (xR, yflat)]
    s.poly(poly, fill=ACRYLIC, stroke=ACRYLIC_S, sw=1.4)
    s.text(xL + 8, yflat - 10, f"PMMA, n = {V['n_d']}", size=11, fill=ACRYLIC_S, weight=700)
    s.text(xR - 6, yflat + 18, "flat face, toward the panel", size=10.5, fill=INK2, anchor="end")
    s.text(fx1 + 8, yfac - 10, "facet, toward the eye", size=10.5, fill=INK2)
    t_ex = 0.55
    ex = fx0 + (fx1 - fx0) * t_ex; ez = yfac - fz * (1 - t_ex)
    A = (ex - math.tan(math.radians(a_in)) * (yflat - ez), yflat); B = (ex, ez)
    L0 = 110
    A0 = (A[0] - math.tan(math.radians(a_air)) * L0, yflat + L0)
    s.line(*A0, *A, stroke=ORANGE, sw=2.6)
    s.line(*A, *B, stroke=ORANGE, sw=2.6)
    L1 = 105
    B1 = (B[0] + math.tan(math.radians(a_out)) * L1, B[1] - L1)
    s.arrow(*B, *B1, color=ORANGE, sw=2.6)
    s.text(A0[0] - 6, A0[1] - 2, "from the panel", size=10.5, fill=ORANGE, anchor="end", weight=600)
    s.text(B1[0] + 8, B1[1] + 8, "to the combiner and the eye", size=10.5, fill=ORANGE, weight=600)
    # normals
    s.line(A[0], A[1] - 95, A[0], A[1] + 95, stroke=INK2, sw=1, extra='stroke-dasharray="5 3"')
    nx, nz = math.sin(math.radians(g)), math.cos(math.radians(g))
    s.line(B[0] - nx * 110, B[1] + nz * 110, B[0] + nx * 150, B[1] - nz * 150, stroke=INK2, sw=1, extra='stroke-dasharray="5 3"')
    s.text(B[0] + nx * 150 + 6, B[1] - nz * 150 + 4, "facet normal", size=10.5, fill=INK2)
    s.text(A[0] + 6, A[1] + 92, "normal to the flat face", size=10.5, fill=INK2)
    # arcs at A (screen angles: 90 = up)
    arc(s, A[0], A[1], 62, 270, 270 + a_air, color=ORANGE, sw=1.5)
    s.text(A[0] + 30, A[1] + 82, f"{V['fx_air']}° in air", size=11.5, fill=ORANGE, weight=700)
    arc(s, A[0], A[1], 62, 90, 90 - a_in, color=BLUE, sw=1.5)
    s.text(A[0] + 26, A[1] - 66, f"{V['fx_in']}° inside", size=11.5, fill=BLUE, weight=700)
    # arcs at B, measured from the facet normal
    nang = 90 - g
    arc(s, B[0], B[1], 70, 90 - a_out, nang, color=ORANGE, sw=1.5)
    s.text(B[0] + 8, B[1] - 86, f"{V["fx_e"]}°", size=11.5, fill=ORANGE, weight=700)
    arc(s, B[0], B[1], 52, 270 - g, 270 - a_in, color=BLUE, sw=1.5)
    s.text(B[0] - 58, B[1] + 52, f"{V['fx_i']}°", size=11.5, fill=BLUE, weight=700)
    s.circle(*A, 4, fill=INK); s.circle(*B, 4, fill=INK)
    s.text(A[0] - 12, A[1] - 8, "1", size=13, weight=700, anchor="end")
    s.text(B[0] - 12, B[1] - 8, "2", size=13, weight=700, anchor="end")
    # explanation
    y = 600
    s.line(16, y - 22, W - 16, y - 22, stroke=GRID, sw=1)
    rows = [
        ("1  Flat face.", f"The ray leaves the panel at {V['fx_air']}° from the axis, slows in the plastic and bends toward the normal:"),
        ("", f"sin {V['fx_air']}° = {V['n_d']} × sin {V['fx_in']}°"),
        ("2  Facet.", f"Inside, it meets the facet at {V['fx_i']}° to the facet's normal (tilted {V['fx_g']}° outward), then bends away from the normal:"),
        ("", f"{V['n_d']} × sin {V['fx_i']}° = sin {V['fx_e']}°, so it leaves at {V['fx_g']}° − {V['fx_e']}° = {V['fx_out']}° from the axis"),
        ("Result.", f"{V['fx_air']}° becomes {V['fx_out']}°: almost parallel, slightly outward, as if it came from a point {V['v_m']} m behind the"),
        ("", f"lens (100 mm ÷ 4,200 mm ≈ 1.4°). Reflection at the two surfaces costs {100 - float(V['fx_T'].rstrip('%')):.1f}%."),
        ("Trapping.", f"{V['fx_i']}° is far below PMMA's {V['crit']}° critical angle, so no light is trapped by total internal reflection here."),
    ]
    for i, (h, t) in enumerate(rows):
        yy = y + i * 21
        if h:
            s.text(16, yy, h, size=11, weight=700)
            s.text(100, yy, t, size=10.5, fill=INK2)
        elif "=" in t:
            s.text(100, yy, t, size=11.2, fill=INK, weight=600)
        else:
            s.text(100, yy, t, size=10.5, fill=INK2)
    return s
