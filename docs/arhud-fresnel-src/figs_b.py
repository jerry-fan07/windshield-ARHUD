"""Figures for sections 3-4: the magnifier, where the image sits, and how stable that is."""
import math
import numpy as np
from svgkit import *
import optics as O
from calc import V, D

@fig("magnifier")
def f_magnifier():
    W, H = 680, 720
    s = Svg(W, H, "How a converging lens makes a magnified virtual image when the object sits inside the focal length: the three construction rays")
    s.rect(0, 0, W, H, fill=SURF)
    step(s, 16, 28, "A", "The construction, with the proportions changed so it fits (u = 0.7 f here)")
    # teaching geometry, f = 200 px, u = 140 px -> v = -466 px, M = 3.33
    f = 150.0; u = 0.7 * f; v = -u * f / (f - u); M = -v / u
    lx = 470; ay = 360
    s.line(20, ay, W - 20, ay, stroke=AXIS, sw=1)
    s.line(lx, ay - 200, lx, ay + 60, stroke=TEAL, sw=3)
    s.text(lx, ay + 78, "lens", size=11.5, fill=TEAL, weight=700, anchor="middle")
    for x, lab in ((lx - f, "F"), (lx + f, "F′")):
        s.circle(x, ay, 3.5, fill=INK2); s.text(x, ay + 18, lab, size=12, weight=700, fill=INK2, anchor="middle")
    oh = 52.0
    ox = lx - u
    s.arrow(ox, ay, ox, ay - oh, color=INK, sw=3)
    s.text(ox, ay + 18, "panel", size=11.5, weight=700, anchor="middle")
    ix = lx + v; ih = oh * M
    s.line(ix, ay, ix, ay - ih, stroke=ORANGE, sw=3, extra='stroke-dasharray="7 4"')
    s.circle(ix, ay - ih, 3, fill=ORANGE)
    s.text(ix, ay + 18, "virtual image", size=11.5, weight=700, fill=ORANGE, anchor="middle")
    s.text(ix, ay + 33, "upright, larger,", size=10.5, fill=INK2, anchor="middle")
    s.text(ix, ay + 47, "on the panel's side", size=10.5, fill=INK2, anchor="middle")
    tip = (ox, ay - oh)
    # ray 1: parallel to the axis, then through F'
    s.line(*tip, lx, ay - oh, stroke=BLUE, sw=2)
    d1 = np.array([f, oh]) / math.hypot(f, oh)
    s.line(lx, ay - oh, lx + d1[0] * 150, ay - oh + d1[1] * 150, stroke=BLUE, sw=2)
    s.line(lx, ay - oh, ix, ay - ih, stroke=BLUE, sw=1, extra='stroke-dasharray="4 4"')
    # ray 2: through the centre, undeviated
    d2 = np.array([u, oh]) / math.hypot(u, oh)
    s.line(*tip, tip[0] + d2[0] * 280, tip[1] + d2[1] * 280, stroke=PURPLE, sw=2)
    s.line(*tip, ix, ay - ih, stroke=PURPLE, sw=1, extra='stroke-dasharray="4 4"')
    # ray 3: as if from F, through the tip, leaves parallel
    yl = ay - oh * f / (f - u)
    s.line(lx - f, ay, *tip, stroke=GREEN, sw=1, extra='stroke-dasharray="4 4"')
    s.line(*tip, lx, yl, stroke=GREEN, sw=2)
    s.line(lx, yl, lx + 150, yl, stroke=GREEN, sw=2)
    s.line(lx, yl, ix, yl, stroke=GREEN, sw=1, extra='stroke-dasharray="4 4"')
    s.circle(lx + 150, ay - 40, 0.1)
    legend(s, 24, 66, [("1  leaves the panel parallel to the axis, so the lens sends it through F′", BLUE),
                        ("2  passes through the lens centre without bending", PURPLE),
                        ("3  starts as if from F, so the lens sends it out parallel to the axis", GREEN)], size=11)
    s.text(24, 128, "The three rays spread apart after the lens: they never meet on the eye's side, so no real image forms there.", size=10.5, fill=INK2)
    s.text(24, 143, "Traced backward (dashed) they meet at one point behind the panel. That point is what the eye sees: a virtual image.", size=10.5, fill=INK2)
    s.circle(W - 34, ay - 30, 7, fill=INK)
    s.text(W - 34, ay - 44, "eye", size=11.5, weight=700, anchor="middle")
    # ---------- B: the formulas with the real numbers ----------
    y0 = 520
    s.line(14, y0 - 22, W - 14, y0 - 22, stroke=GRID, sw=1)
    step(s, 16, y0, "B", "The same construction with Stage 1's numbers")
    rows = [
        ("Lens equation", f"1/v = 1/f − 1/u = 1/{V['f']} − 1/{V['u']}   so   v = −{V['v']} mm (the minus sign means: on the panel's side, virtual)"),
        ("Magnification", f"M = |v| / u = {V['v']} / {V['u']} = {V['M']}: the {V['crop_w']} × {V['crop_h']} mm crop becomes {V['img_w']} × {V['img_h']} m"),
        ("Why so large", f"u is {V['sun_focus_beyond']} mm short of f. As u approaches f, f − u shrinks and both |v| = uf / (f − u) and M = f / (f − u) grow without limit."),
        ("From the eye", f"the image is {V['v']} + {V['eye_z']} = {V['d_eye_img']} m away and fills {V['fov_eye_w']}° × {V['fov_eye_h']}° (traced, including distortion)."),
        ("Pixels", f"80 mm is {V['px_mon']} px on the 4K monitor ({V['ppd_mon_eye']} px/deg) or {V['px_55']} px on the 5.5-inch panel ({V['ppd_55_eye']} px/deg)."),
    ]
    for i, (h, t) in enumerate(rows):
        yy = y0 + 32 + i * 30
        s.text(16, yy, h, size=11, weight=700)
        s.text(126, yy, t, size=10.5, fill=INK2)
    return s

@fig("vofu")
def f_vofu():
    W, H = 680, 780
    s = Svg(W, H, "Image distance against panel distance in metres and in dioptres, with the plan's 280 mm marked")
    s.rect(0, 0, W, H, fill=SURF)
    step(s, 16, 28, "A", "Image distance from the lens, for panel distances 255 to 299 mm")
    ax = Axes(s, 80, 52, 520, 300, (255, 300), (0, 20))
    ax.frame([255, 260, 265, 270, 275, 280, 285, 290, 295, 300], [0, 4, 8, 12, 16, 20],
             xlabel="panel to lens, u (mm)", ylabel="virtual image distance (m)")
    pts = [(u, v / 1000) for u, v in D["v_of_u"]]
    ax.clip_curve(pts, stroke=ORANGE, sw=2.8)
    s.line(ax.X(300), ax.y, ax.X(300), ax.y + ax.h, stroke=CRIT, sw=1.4, extra='stroke-dasharray="5 3"')
    s.text(ax.X(300) - 6, ax.y + 16, "u = f: image at infinity", size=10.5, fill=CRIT, anchor="end")
    # mark 280
    x0, y0v = ax.P(280, 4.2)
    s.circle(x0, y0v, 5, fill=ORANGE)
    s.line(x0, y0v, x0, ax.y + ax.h, stroke=ORANGE, sw=1, extra='stroke-dasharray="3 3"')
    s.line(ax.x, y0v, x0, y0v, stroke=ORANGE, sw=1, extra='stroke-dasharray="3 3"')
    s.text(x0 - 10, y0v - 12, f"plan: {V['u']} mm gives {V['v_m']} m", size=11.5, weight=700, anchor="end")
    # tangent slope 225 mm/mm
    sl = float(V["dvdu"]) / 1000
    s.line(*ax.P(276, 4.2 - 4 * sl), *ax.P(284, 4.2 + 4 * sl), stroke=INK, sw=1.4)
    s.text(*ax.P(256.5, 12.0), f"Slope at 280 mm: {V['dvdu']} mm of image distance", size=11, weight=700)
    s.text(*ax.P(256.5, 11.0), "per mm of panel movement (= M², the", size=10.5, fill=INK2)
    s.text(*ax.P(256.5, 10.2), "magnification squared). Black tangent line.", size=10.5, fill=INK2)
    for uu, lab in ((290, None), (295, None)):
        vv = abs(O.paraxial_v(O.F, uu)) / 1000
        s.circle(*ax.P(uu, vv), 3.5, fill=INK2)
        s.text(ax.P(uu, vv)[0] - 8, ax.P(uu, vv)[1] + 4, f"{uu} mm gives {vv:.1f} m", size=10.5, fill=INK2, anchor="end")
    # ---------- B: dioptres ----------
    y0 = 420
    step(s, 16, y0, "B", "The same curve in dioptres (1 ÷ distance from the eye in metres): the scale the eye focuses on")
    ax2 = Axes(s, 80, y0 + 26, 520, 230, (255, 300), (0, 0.6))
    ax2.frame([255, 260, 265, 270, 275, 280, 285, 290, 295, 300], [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6], yfmt="{:.1f}",
              xlabel="panel to lens, u (mm)", ylabel="dioptres at the eye")
    dpts = [(u, 1000 / (v + O.EYE_Z)) for u, v in D["v_of_u"]]
    # depth of focus band: ±0.25 D around the plan point (typical relaxed-eye tolerance)
    d0 = 1000 / (abs(O.paraxial_v()) + O.EYE_Z)
    s.rect(ax2.x, ax2.Y(d0 + 0.25), ax2.w, ax2.Y(max(d0 - 0.25, 0)) - ax2.Y(d0 + 0.25), fill=GREEN_T)
    s.text(ax2.x + 8, ax2.Y(d0 + 0.25) + 14, "±0.25 D: looks equally sharp to a relaxed eye", size=10.5, fill=GREEN)
    ax2.curve(dpts, stroke=BLUE, sw=2.8)
    xp, yp = ax2.P(280, d0)
    s.circle(xp, yp, 5, fill=BLUE)
    s.text(xp + 10, yp - 10, f"{V['diopt_eye']} D at {V['u']} mm", size=11.5, weight=700)
    s.text(ax2.x + ax2.w - 6, ax2.Y(0.56), f"{V['diopt_per_mm']} D per mm of panel movement:", size=10.5, fill=INK2, anchor="end")
    s.text(ax2.x + ax2.w - 6, ax2.Y(0.56) + 15, "nearly a straight line, and gentle", size=10.5, fill=INK2, anchor="end")
    s.text(16, H - 30, "In metres the image distance looks wildly sensitive; in dioptres it is not. The eye cannot tell 4 m from 6 m by focus.", size=11, weight=700)
    s.text(16, H - 12, "What the distance does change is parallax: where a symbol appears against the road when the head moves (Figure [[N parallax]]).", size=10.5, fill=INK2)
    return s

@fig("tolerance")
def f_tolerance():
    W, H = 680, 760
    s = Svg(W, H, "How the lens's focal-length tolerance and its temperature move the virtual image, and the panel distance that restores it")
    s.rect(0, 0, W, H, fill=SURF)
    step(s, 16, 28, "A", "The lens's focal length is only known to ±2% (precision grade) or ±5% (standard)")
    rows = D["tol"]
    x0 = 150; y = 70; bh = 30; gap = 14
    s.text(16, y - 8, "focal length", size=10.5, fill=INK2, weight=700)
    s.text(x0, y - 8, "image distance from the lens with the panel left at 280 mm", size=10.5, fill=INK2, weight=700)
    s.text(W - 16, y - 8, "panel distance for 4.2 m", size=10.5, fill=INK2, weight=700, anchor="end")
    scale = 300 / 16.0                                       # px per metre (0..16 m)
    for p, f, v, u_set in rows:
        col = TEAL if p == 0 else (BLUE if abs(p) == 2 else ORANGE)
        s.text(16, y + 20, f"{f:.0f} mm ({p:+d}%)".replace("-", "−") if p else f"{f:.0f} mm (nominal)", size=11, weight=700 if p == 0 else 500)
        wv = min(v / 1000, 16) * scale
        s.rect(x0, y + 4, wv, bh - 8, fill=col, rx=3, extra='opacity="0.85"')
        s.text(x0 + wv + 8, y + 20, f"{v/1000:.1f} m", size=11, weight=700)
        s.text(W - 16, y + 20, f"{u_set:.1f} mm", size=11, weight=700 if p == 0 else 500, anchor="end")
        y += bh + gap
    s.line(x0 + 4.2 * scale, 64, x0 + 4.2 * scale, y - 6, stroke=INK, sw=1, extra='stroke-dasharray="3 3"')
    s.text(x0 + 4.2 * scale + 4, y + 6, "4.2 m (plan)", size=10, fill=INK2)
    s.text(16, y + 30, f"A focal length 2% long ({V['tol_f_p2']} mm) brings the image in to {V['tol_v_p2']} m; 2% short ({V['tol_f_m2']} mm) pushes it out to {V['tol_v_m2']} m.", size=10.5, fill=INK2)
    s.text(16, y + 46, f"Fix it once, per lens, by moving the panel: the right-hand column. That is a {float(V['tol_u_p2']) - float(V['tol_u_m2']):.1f} mm range for the precision grade.", size=10.5, fill=INK2)
    # ---------- B: temperature ----------
    y0 = y + 92
    step(s, 16, y0, "B", "Warming the lens lengthens its focal length and pulls the image in")
    ax = Axes(s, 80, y0 + 26, 520, 230, (-20, 60), (3.0, 5.0))
    ax.frame([-20, -10, 0, 10, 20, 30, 40, 50, 60], [3.0, 3.5, 4.0, 4.5, 5.0], yfmt="{:.1f}",
             xlabel="lens temperature rise above the temperature it was set at (K)", ylabel="image distance from lens (m)")
    ax.curve([(dT, v / 1000) for dT, f, v in D["therm"]], stroke=ORANGE, sw=2.8)
    # glass for comparison: alpha 7e-6, dn/dT +3e-6
    gl = []
    for dT in range(-20, 61, 2):
        f = O.F * (1 + 7e-6 * dT) * (1.517 - 1) / (1.517 - 1 + 3e-6 * dT)
        gl.append((dT, abs(O.paraxial_v(f)) / 1000))
    ax.curve(gl, stroke=MUTED, sw=2, extra='stroke-dasharray="6 4"')
    for dT in (10, 20, 40):
        vv = float(V[f"th_v_{dT}"])
        s.circle(*ax.P(dT, vv), 4, fill=ORANGE)
        s.text(ax.P(dT, vv)[0] + 6, ax.P(dT, vv)[1] - 8, f"+{dT} K: {vv:.2f} m", size=10.5, weight=700)
    legend(s, ax.x + 300, ax.y + 22, [("PMMA lens", ORANGE), ("glass lens, for comparison", MUTED)], size=10.5)
    s.text(16, H - 30, f"PMMA expands {V['alpha']} ppm/K and its index falls {abs(float(V['dndt'])):.2f}×10⁻⁴ per K; both lengthen f (+{float(V['th_f_40']) - 300:.1f} mm at +40 K).", size=10.5, fill=INK2)
    s.text(16, H - 13, f"The image moves {4.2 - float(V['th_v_40']):.2f} m, which is {abs(1000/(float(V['th_v_40'])*1000+700) - 1000/4900):.3f} D: invisible to focus, {V['par_th_40']}° of parallax per {V['head']} mm of head offset (Figure [[N parallax]]).", size=10.5, fill=INK2)
    return s

@fig("parallax")
def f_parallax():
    W, H = 680, 780
    s = Svg(W, H, "Why the image distance matters for registration: parallax between a symbol on the image and a target on the road when the head moves")
    s.rect(0, 0, W, H, fill=SURF)
    step(s, 16, 28, "A", "Top view: the head moves sideways; the symbol and the target do not move together")
    # top view, not to scale in depth (log-ish): eye y=360, image at y=200, target at y=70
    ey, iy, ty = 420, 250, 90
    xs = 260
    e1, e2 = xs - 50, xs + 50
    s.line(60, iy, 560, iy, stroke=ORANGE, sw=3)
    s.text(566, iy + 4, f"virtual image, {V['d_eye_img']} m", size=11, fill=ORANGE, weight=700)
    s.line(60, ty, 560, ty, stroke=MUTED, sw=1, extra='stroke-dasharray="3 4"')
    s.text(566, ty + 4, "road target, 30 m", size=11, fill=INK2, weight=700)
    s.circle(xs, ty, 7, fill=INK)
    s.text(xs + 10, ty - 10, "lead car", size=10.5, fill=INK2)
    for ex, col, lab in ((e1, BLUE, "eye, before"), (e2, PURPLE, "eye, moved 50 mm")):
        s.circle(ex, ey, 7, fill=col)
        s.text(ex, ey + 24, lab, size=10.5, fill=col, anchor="middle", weight=700)
        # line of sight to the target crosses the image plane here
        tpar = (iy - ey) / (ty - ey)
        cx = ex + (xs - ex) * tpar
        s.line(ex, ey, xs, ty, stroke=col, sw=1.4)
        s.rect(cx - 6, iy - 6, 12, 12, fill="none", stroke=col, sw=2.2)
    # the symbol drawn for the first eye position stays at e1's crossing
    t = (iy - ey) / (ty - ey)
    c1 = e1 + (xs - e1) * t; c2 = e2 + (xs - e2) * t
    s.line(e2, ey, e2 + (c1 - e2) * (ty - ey) / (iy - ey), ty, stroke=PURPLE, sw=1, extra='stroke-dasharray="4 4"')
    s.text(e2 + (c1 - e2) * (ty - ey) / (iy - ey) - 8, ty + 18, "the moved eye sees the old symbol here", size=10, fill=PURPLE, anchor="end")
    s.text(c1 - 10, iy - 14, "symbol drawn here", size=10.5, fill=BLUE, anchor="end")
    s.text(c2 + 10, iy - 14, "needs to move here", size=10.5, fill=PURPLE)
    s.text(16, ey + 62, "If the symbol stays put, the moved eye sees it off the target by e × (1/D_image − 1/D_target). The head tracker redraws it in the right", size=10.5, fill=INK2)
    s.text(16, ey + 77, "place, but only if the software knows D_image. Depth not to scale.", size=10.5, fill=INK2)
    # ---------- B: error chart ----------
    y0 = 540
    step(s, 16, y0, "B", "Registration error at 30 m against head offset")
    ax = Axes(s, 80, y0 + 24, 400, 170, (0, 100), (0, 1.2))
    ax.frame([0, 20, 40, 60, 80, 100], [0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2], yfmt="{:.1f}",
             xlabel="head offset from where the calibration was done (mm)", ylabel="error (degrees)")
    D_img = abs(O.paraxial_v()) + O.EYE_Z
    def err(e, d_true, d_ass):
        return math.degrees(e * abs(1 / d_true - 1 / d_ass))
    cases = [("no head tracking", lambda e: err(e, D_img, 30000.0), CRIT),
             ("tracked; f 2% off, not measured", lambda e: err(e, abs(O.paraxial_v(O.F * 1.02)) + O.EYE_Z, D_img), ORANGE),
             ("tracked; lens 40 K warmer", lambda e: err(e, float(V["th_v_40"]) * 1000 + O.EYE_Z, D_img), BLUE),
             ("tracked; distance measured", lambda e: 0.0, GREEN)]
    for lab, fn, col in cases:
        ax.curve([(e, fn(e)) for e in np.linspace(0, 100, 51)], stroke=col, sw=2.4)
    s.line(ax.x, ax.Y(1.0), ax.x + ax.w, ax.Y(1.0), stroke=INK, sw=1.2, extra='stroke-dasharray="6 3"')
    s.text(ax.x + 6, ax.Y(1.0) - 6, "plan's gate G4: 1.0° static", size=10.5, fill=INK)
    legend(s, ax.x + ax.w + 18, ax.y + 12, [(lab, col) for lab, _, col in cases], size=10.5, dy=20)
    s.text(ax.x + ax.w + 18, ax.y + 110, f"At {V['head']} mm: {V['par_30m']}°, {V['par_tol_p2']}°,", size=10.5, fill=INK2)
    s.text(ax.x + ax.w + 18, ax.y + 125, f"{V['par_th_40']}° and 0°.", size=10.5, fill=INK2)
    return s

@fig("isurf")
def f_isurf():
    W, H = 680, 820
    s = Svg(W, H, "The virtual image is not flat: traced tangential and sagittal image distance across the field, in metres and dioptres")
    s.rect(0, 0, W, H, fill=SURF)
    step(s, 16, 28, "A", "Top view of the image surface, traced through the lens model (horizontal field)")
    # top view: x = lateral position of the image point (m), y = distance from eye (m)
    ax = Axes(s, 80, 52, 520, 330, (-1.0, 1.0), (0, 9))
    ax.frame([-1.0, -0.5, 0, 0.5, 1.0], [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], xfmt="{:+.1f}",
             xlabel="sideways from the line of sight (m)", ylabel="distance from the eye (m)")
    sl = D["surf_line"]
    def pts(idx):
        out = []
        for a, dt, ds in sl:
            d = (dt, ds)[idx] / 1000
            out.append((d * math.tan(math.radians(a)), d * math.cos(math.radians(a))))
        return [(-x, y) for x, y in reversed(out)] + out
    s.rect(ax.X(-0.6), ax.Y(4.9) - 2, ax.X(0.6) - ax.X(-0.6), 4, fill=MUTED, extra='opacity="0.5"')
    s.text(ax.X(0.62), ax.Y(4.9) + 4, "flat plane the plan assumes (4.9 m)", size=10.5, fill=INK2)
    ax.curve(pts(0), stroke=ORANGE, sw=2.8)
    ax.curve(pts(1), stroke=BLUE, sw=2.8)
    hw = float(V["hfw"])
    for sg in (-1, 1):
        s.line(ax.X(0), ax.Y(0), ax.X(sg * 9 * math.tan(math.radians(hw))), ax.Y(9), stroke=INK2, sw=0.8, extra='stroke-dasharray="3 3"')
    s.circle(ax.X(0), ax.Y(0) - 0.5, 6, fill=INK)
    s.text(ax.X(0) + 10, ax.Y(0) - 8, "eye", size=11, weight=700)
    s.text(ax.X(0.80), ax.Y(8.7), "field edge", size=10, fill=INK2, anchor="end")
    legend(s, ax.X(0.12), ax.Y(3.0), [("tangential focus: circles round the", ORANGE), ("centre are sharpest here", "none"), ("sagittal focus: lines pointing at the", BLUE), ("centre are sharpest here", "none")], size=10.5, dy=16)
    # ---------- B: in dioptres ----------
    y0 = 450
    step(s, 16, y0, "B", "The same in dioptres across the field, horizontal and diagonal")
    ax2 = Axes(s, 80, y0 + 26, 520, 230, (0, 8.0), (0, 0.3))
    ax2.frame([0, 1, 2, 3, 4, 5, 6, 7, 8], [0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30], yfmt="{:.2f}",
              xlabel="field angle from the centre (degrees)", ylabel="dioptres at the eye")
    ax2.curve([(a, 1000 / dt) for a, dt, ds in sl], stroke=ORANGE, sw=2.6)
    ax2.curve([(a, 1000 / ds) for a, dt, ds in sl], stroke=BLUE, sw=2.6)
    srf = D["surf"]
    # diagonal: corner points of the grid
    diag = [(math.hypot(srf["ax"][i, j], srf["ay"][i, j]), srf["dt"][i, j], srf["ds"][i, j]) for i, j in zip(range(4, 9), range(7, 15, 2))]
    for a, dt, ds in diag:
        s.circle(*ax2.P(a, 1000 / dt), 3.5, fill=ORANGE); s.circle(*ax2.P(a, 1000 / ds), 3.5, fill=BLUE)
    s.text(ax2.X(6.2), ax2.Y(0.255), "dots: diagonal toward the corner", size=10.5, fill=INK2)
    s.text(16, H - 46, f"Centre {V['isurf_c']} m ({V['isurf_c_D']} D). Horizontal edge {V['isurf_w_t']} m tangential / {V['isurf_w_s']} m sagittal. Corner {V['isurf_k_t']} / {V['isurf_k_s']} m.", size=10.8, weight=700)
    s.text(16, H - 29, f"The corner's two foci are {V['astig_D']} D apart; the eye tolerates about 0.25 D, so the image looks sharp everywhere.", size=10.5, fill=INK2)
    s.text(16, H - 13, "The curvature still matters for registration: the renderer should use the traced distance per field point, not one plane.", size=10.5, fill=INK2)
    return s
