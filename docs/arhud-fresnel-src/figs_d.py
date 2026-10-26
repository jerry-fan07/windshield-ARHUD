"""Figures for sections 9-11: the combiner, brightness, sunlight through the lens, packaging and alignment."""
import math
import numpy as np
from svgkit import *
import optics as O
from calc import V, D, T_COMB, R_COMB, I_COMB, N_GL, SCENES

@fig("combiner")
def f_combiner():
    W, H = 680, 800
    s = Svg(W, H, "What a combiner does, and the faint second image from its back surface")
    s.rect(0, 0, W, H, fill=SURF)
    step(s, 16, 28, "A", "A sheet of glass that is partly a window and partly a mirror")
    cx, cy = 330, 200
    L = 150
    ang = math.radians(90 - I_COMB)                         # glass tilt from horizontal on screen
    tx, ty = math.cos(ang), math.sin(ang)
    s.line(cx - L * tx, cy - L * ty, cx + L * tx, cy + L * ty, stroke=BLUE, sw=5)
    s.text(cx - L * tx - 8, cy - L * ty - 4, "combiner", size=12, fill=BLUE, weight=700, anchor="end")
    s.text(cx - L * tx - 8, cy - L * ty + 12, "glass with a partly", size=10.5, fill=INK2, anchor="end")
    s.text(cx - L * tx - 8, cy - L * ty + 26, "reflective coating", size=10.5, fill=INK2, anchor="end")
    # eye on the left, road on the right, lens below
    ex, ey = 60, cy - 18
    s.circle(ex, ey, 9, fill=INK)
    s.text(ex, ey - 16, "eye", size=12, weight=700, anchor="middle")
    # road light: from the right, through the glass, to the eye
    s.arrow(W - 30, ey - 2, cx + 20, ey - 1, color=MUTED, sw=3)
    s.arrow(cx - 10, ey, ex + 16, ey, color=MUTED, sw=3)
    s.text(W - 30, ey - 14, "light from the road", size=11, fill=INK2, anchor="end", weight=700)
    s.text(cx - 20, ey - 14, "70% passes through", size=11, fill=INK2, anchor="end")
    s.text(W - 30, ey + 22, "30% bounces off (lost upward)", size=10.5, fill=MUTED, anchor="end")
    # HUD light from below, reflecting to the eye
    s.arrow(cx + 12, cy + 210, cx + 12, ey + 6, color=ORANGE, sw=3)
    s.arrow(cx + 6, ey + 6, ex + 18, ey + 6, color=ORANGE, sw=3)
    s.text(cx + 22, cy + 160, "light from the lens and panel", size=11, fill=ORANGE, weight=700)
    s.text(cx + 22, cy + 176, "30% reflects toward the eye;", size=10.5, fill=INK2)
    s.text(cx + 22, cy + 191, "70% passes up and is lost", size=10.5, fill=INK2)
    s.text(ex + 10, ey + 36, "both arrive together:", size=11, fill=INK, weight=700)
    s.text(ex + 10, ey + 51, "the graphics float over the road", size=10.5, fill=INK2)
    s.text(16, 418, f"In the car the light from below meets the glass at {V['i_comb']}° (the eye looks {V['lookdown']}° down); drawn here at 45°. The plan uses 70/30 teleprompter glass.", size=10.5, fill=INK2)
    # ---------- B: ghost ----------
    y0 = 470
    s.line(14, y0 - 24, W - 14, y0 - 24, stroke=GRID, sw=1)
    step(s, 16, y0, "B", "The back surface reflects too: a second, fainter copy, slightly shifted")
    # thick plate, drawn horizontal for clarity; light arrives from below-left, reflects up-left
    px0, py0, pw, pt = 120, y0 + 150, 440, 70
    s.rect(px0, py0, pw, pt, fill="#e7f0fb", stroke=BLUE, sw=1.4)
    s.line(px0, py0, px0 + pw, py0, stroke=BLUE, sw=4)
    s.text(px0 + pw + 8, py0 + 4, "coated front (30%)", size=10.5, fill=BLUE, weight=700)
    s.text(px0 + pw + 8, py0 + pt + 4, f"plain back ({V['r_back']}%)", size=10.5, fill=INK2, weight=700)
    th = math.radians(I_COMB); tt = math.asin(math.sin(th) / N_GL)
    # incoming ray hits the front at A
    Ax, Ay = 290, py0
    inc = (math.sin(th), -math.cos(th))                     # travelling up-right toward the plate from below? use downward geometry
    # draw with light coming from above (eye side up): incoming from upper-left, reflecting to upper-right
    a_in = (Ax - 110 * math.tan(th), Ay - 110)
    s.line(*a_in, Ax, Ay, stroke=ORANGE, sw=2.4)
    r1 = (Ax + 110 * math.tan(th), Ay - 110)
    s.arrow(Ax, Ay, *r1, color=ORANGE, sw=2.4)
    Bx = Ax + pt * math.tan(tt); By = Ay + pt
    s.line(Ax, Ay, Bx, By, stroke=ORANGE, sw=1.4, extra='stroke-dasharray="4 3"')
    Cx = Bx + pt * math.tan(tt); Cy = Ay
    s.line(Bx, By, Cx, Cy, stroke=ORANGE, sw=1.4, extra='stroke-dasharray="4 3"')
    r2 = (Cx + 110 * math.tan(th), Cy - 110)
    s.arrow(Cx, Cy, *r2, color=ORANGE, sw=1.4)
    s.text(r1[0] - 6, r1[1] - 8, "main image (30%)", size=10.5, fill=ORANGE, weight=700, anchor="end")
    s.text(r2[0] + 6, r2[1] - 8, f"ghost ({V['ghost_rel']}% of the main)", size=10.5, fill=ORANGE, weight=700)
    dim(s, Ax, Ay - 6, Cx, Cy - 6, "offset", off=-20, size=10, color=CRIT)
    s.text(px0 + 6, py0 + pt / 2 + 4, "glass, n = 1.52", size=10.5, fill=INK2)
    rows = [f"For 3 mm glass the two copies are {V['gh_off_3']} mm apart, which at {V['d_eye_img']} m is {V['gh_am_3']}′; 6 mm glass doubles it ({V['gh_am_6']}′). A pixel is about 0.7–1′.",
            f"The ghost carries {V['ghost_rel']}% of the main image's brightness for unpolarised light. At {V['i_comb']}° the plain surface reflects {V['rs_comb']}% of s-polarised",
            f"light but only {V['rp_comb']}% of p-polarised, and the LCD's light is polarised: turned to p, the ghost almost vanishes, but the coating's",
            "own reflectance changes with polarisation too. Measure both with the panel at the combiner before deciding (section 9)."]
    for i, t in enumerate(rows):
        s.text(16, y0 + 248 + i * 16, t, size=10.5, fill=INK2)
    return s

@fig("luminance")
def f_luminance():
    W, H = 680, 640
    s = Svg(W, H, "Brightness from the panel to the eye in Stage 1, and the contrast against the road for three panels in five lighting conditions")
    s.rect(0, 0, W, H, fill=SURF)
    step(s, 16, 28, "A", "What reaches the eye: lens, then the combiner's 30% reflection")
    steps_ = [("panel", 100.0), ("after the lens (2 surfaces)", float(V["T_axis"].rstrip("%"))),
              ("after the groove losses", float(V["T_axis"].rstrip("%")) * (1 - float(V["draft_loss"].rstrip("%")) / 100)),
              ("after the combiner (30%)", float(V["path1"].rstrip("%")))]
    x0, y = 230, 56
    for lab, v in steps_:
        s.text(x0 - 10, y + 17, lab, size=11, anchor="end", weight=600)
        s.rect(x0, y + 4, v * 3.8, 20, fill=ORANGE if v < 50 else TEAL, rx=3, extra='opacity="0.85"')
        s.text(x0 + v * 3.8 + 8, y + 19, f"{v:.0f}%", size=11, weight=700)
        y += 32
    s.text(16, y + 16, f"A lens does not change luminance (cd/m²) except for its losses, however much it magnifies. So: eye = panel × {V['path1']}.", size=10.5, fill=INK2)
    s.text(16, y + 32, f"16-inch 4K monitor, 1,200 cd/m²: {V['lum_0']} cd/m² at the eye.  5.5-inch kit, stock: {V['lum_1']}.  5.5-inch kit, custom backlight, 10,000: {V['lum_2']}.", size=10.5, fill=INK, weight=700)
    # ---------- B: contrast ----------
    y0 = y + 80
    step(s, 16, y0, "B", "Contrast against the road seen through the combiner (70%)")
    ax = Axes(s, 80, y0 + 40, 520, 240, (0.5, 20000), (1.0, 1000), xlog=True, ylog=True)
    for v in (1, 10, 100, 1000, 10000):
        s.line(ax.X(v), ax.y, ax.X(v), ax.y + ax.h, stroke=GRID, sw=0.8)
    for v in (1, 1.15, 2, 10, 100, 1000):
        s.line(ax.x, ax.Y(v), ax.x + ax.w, ax.Y(v), stroke=GRID, sw=0.8)
    s.rect(ax.x, ax.y, ax.w, ax.h, fill="none", stroke=AXIS, sw=1)
    for v, lab in ((1, "1"), (10, "10"), (100, "100"), (1000, "1,000"), (10000, "10,000")):
        s.text(ax.X(v), ax.y + ax.h + 15, lab, size=11, fill=INK2, anchor="middle")
    for v, lab in ((1, "1"), (2, "2"), (10, "10"), (100, "100"), (1000, "1,000")):
        s.text(ax.x - 6, ax.Y(v) + 4, lab, size=11, fill=INK2, anchor="end")
    s.text(ax.x + ax.w / 2, ax.y + ax.h + 33, "road luminance (cd/m²)", size=11.5, anchor="middle", weight=500)
    cx_, cy_ = ax.x - 46, ax.y + ax.h / 2
    s.text(cx_, cy_, "contrast ratio", size=11.5, anchor="middle", weight=500, extra=f'transform="rotate(-90 {cx_} {cy_})"')
    s.line(ax.x, ax.Y(1.15), ax.x + ax.w, ax.Y(1.15), stroke=CRIT, sw=1.4, extra='stroke-dasharray="6 3"')
    s.text(ax.x + 8, ax.Y(1.15) - 6, "1.15: the plan's minimum to be readable", size=10.5, fill=CRIT)
    path = float(V["path1"].rstrip("%")) / 100
    for (name, lp, le), col in zip(D["lum"], (BLUE, MUTED, ORANGE)):
        pts = [(L, (lp * path + T_COMB * L) / (T_COMB * L)) for L in np.logspace(math.log10(0.5), math.log10(20000), 60)]
        ax.clip_curve(pts, stroke=col, sw=2.6)
    for nm, L in SCENES:
        s.line(ax.X(L), ax.y, ax.X(L), ax.y + 8, stroke=INK, sw=1.4)
        lab = {"Night, headlit road": "night", "Dusk": "dusk", "Overcast day": "overcast", "Sunlit road": "sunlit", "Bright sky / snow": "sky"}[nm]
        s.text(ax.X(L), ax.y - 6, lab, size=9.5, fill=INK2, anchor="middle")
    legend(s, ax.x + 300, ax.y + 34, [("custom backlight, 10,000", ORANGE), ("4K monitor, 1,200", BLUE), ("5.5-inch kit stock, 450", MUTED)], size=10.5)
    s.text(16, H - 30, f"Night (about 1 cd/m²) is easy with anything: the HUD must be dimmed {V['night_dim']}× from full for the plan's 50 cd/m² night ceiling.", size=10.5, fill=INK2)
    s.text(16, H - 13, "With the custom backlight, Stage 1 stays readable even against a sunlit road. The limit in daylight is sunlight through the lens (section 10).", size=10.5, fill=INK2)
    return s

@fig("sunspot")
def f_sunspot():
    W, H = 680, 800
    s = Svg(W, H, "Sunlight straight down the lens axis: the lens focuses it 20 mm beyond the panel, into a 22 mm spot on the panel")
    s.rect(0, 0, W, H, fill=SURF)
    step(s, 16, 28, "A", "Side view, to scale (1.1 px per mm): sun straight down the lens axis")
    k = 1.1; cx = 240; ytop = 70
    X = lambda x: cx + x * k
    Y = lambda z: ytop + (40 - z) * k
    # sunlight arrows above the lens
    for x in np.linspace(-140, 140, 15):
        s.arrow(X(x), Y(36), X(x), Y(6), color="#e0a800", sw=1.4)
    s.text(X(150) + 8, Y(26), "sunlight through the windshield", size=10.5, fill="#9a7400", weight=700)
    s.text(X(150) + 8, Y(26) + 15, f"and the combiner: {V['sun_W']} W on the lens", size=10.5, fill=INK2)
    s.line(X(-150), Y(0), X(150), Y(0), stroke=TEAL, sw=4)
    s.text(X(150) + 8, Y(0) + 4, "lens", size=11, fill=TEAL, weight=700)
    # traced rays: collimated, through the lens to beyond the panel
    zF = O.Z_H - O.F
    for x in np.linspace(-148, 148, 23):
        E = np.array([[x, 0.0, 10.0]]); Dd = np.array([[0.0, 0.0, -1.0]])
        b = O.trace_backward(E, Dd)
        p2 = b["P2"][0]; d2 = b["d2"][0]
        z_end = zF - 25
        t = (z_end - p2[2]) / d2[2]
        q = p2 + t * d2
        s.line(X(x), Y(0), X(p2[0]), Y(p2[2]), stroke="#e0a800", sw=0.9)
        s.line(X(p2[0]), Y(p2[2]), X(q[0]), Y(q[2]), stroke="#e0a800", sw=0.9, extra='opacity="0.8"')
    s.line(X(-60), Y(O.Z_PANEL), X(60), Y(O.Z_PANEL), stroke=INK, sw=4)
    s.text(X(-62), Y(O.Z_PANEL) + 4, "panel", size=11, weight=700, anchor="end")
    s.circle(X(0), Y(zF), 3.5, fill=CRIT)
    s.text(X(8), Y(zF) + 16, f"focus, {V['sun_focus_beyond']} mm past the panel", size=10.5, fill=CRIT, weight=700)
    dim(s, X(-150) - 20, Y(0), X(-150) - 20, Y(O.Z_PANEL), f"{V['u']} mm", off=0, size=10.5)
    s.text(X(70), Y(O.Z_PANEL) - 8, f"spot ≈ {2*int(V['sun_r90'])} mm across", size=11, weight=700)
    # ---------- B: irradiance map ----------
    y0 = Y(zF) + 60
    step(s, 16, y0, "B", "The spot on the panel, traced: power per area (kW/m²)")
    st = D["sun0"]["stats"]
    Hm = st["H"] / (1e-3) ** 2 / 1000                        # kW/m2 per 1 mm bin
    n = Hm.shape[0]
    cell = 4.0
    ox, oy = 70, y0 + 24
    vmax = Hm.max()
    sub = Hm[20:60, 20:60]
    m = sub.shape[0]
    for i in range(m):
        for j in range(m):
            v = sub[i, j] / vmax
            if v <= 0.002:
                continue
            col = f"rgb({int(255)},{int(255 - 200 * v)},{int(230 - 230 * v)})"
            s.rect(ox + j * cell, oy + (m - 1 - i) * cell, cell + 0.3, cell + 0.3, fill=col)
    s.rect(ox, oy, m * cell, m * cell, fill="none", stroke=AXIS, sw=1)
    s.text(ox + m * cell / 2, oy + m * cell + 16, "40 × 40 mm window on the panel", size=10.5, fill=INK2, anchor="middle")
    # colour bar
    bx = ox + m * cell + 30
    for i in range(50):
        v = 1 - i / 49
        s.rect(bx, oy + i * 3.2, 16, 3.4, fill=f"rgb(255,{int(255 - 200 * v)},{int(230 - 230 * v)})")
    s.text(bx + 22, oy + 8, f"{vmax:.0f} kW/m² (1 mm bins)", size=10.5, fill=INK2)
    s.text(bx + 22, oy + 160, "0", size=10.5, fill=INK2)
    tx = bx + 180
    rows = [("Collected", f"{V['sun_W']} W", f"({V['sun_W_nocomb']} W with no combiner above)"),
            ("Spot", f"90% within {V['sun_r90']} mm", "of its centre"),
            ("Peak", f"{V['sun_peak']} kW/m²", f"about {V['sun_peak_suns']} suns"),
            ("TI limit", f"{V['tw_peak']} kW/m²", "production HUD design peak"),
            ("BMW TFT", f"+45 °C at {V['bmw_peak']} kW/m²", "(plan, section 6.8)")]
    for i, (a, b, c) in enumerate(rows):
        s.text(tx - 40, oy + 20 + i * 32, a, size=11, weight=700)
        s.text(tx + 34, oy + 20 + i * 32, b, size=11, fill=INK, weight=600)
        s.text(tx + 34, oy + 34 + i * 32, c, size=10, fill=INK2)
    s.text(16, H - 30, "There is no cold mirror, IR filter or shutter in Stage 1: all of this lands on the LCD, whose polarisers absorb half of it at once.", size=10.8, weight=700)
    s.text(16, H - 13, "The windshield's 70% and the combiner's 70% transmission are ASSUMED; the lens is traced with its real facets.", size=10.5, fill=INK2)
    return s

@fig("sunangle")
def f_sunangle():
    W, H = 680, 700
    s = Svg(W, H, "Sunlight away from the lens axis: where the spot lands on the panel and how intense it is, and when the sun is in that range")
    s.rect(0, 0, W, H, fill=SURF)
    step(s, 16, 28, "A", "Sun off the lens axis: the spot moves across the panel and gets sharper before it spreads")
    so = D["sun_off"]
    ax = Axes(s, 80, 52, 520, 240, (0, 40), (1, 3000), ylog=True)
    for v in (1, 10, 100, 1000):
        s.line(ax.x, ax.Y(v), ax.x + ax.w, ax.Y(v), stroke=GRID, sw=0.8)
        s.text(ax.x - 6, ax.Y(v) + 4, f"{v:,}", size=11, fill=INK2, anchor="end")
    for v in range(0, 41, 5):
        s.line(ax.X(v), ax.y, ax.X(v), ax.y + ax.h, stroke=GRID, sw=0.8)
        s.text(ax.X(v), ax.y + ax.h + 15, str(v), size=11, fill=INK2, anchor="middle")
    s.rect(ax.x, ax.y, ax.w, ax.h, fill="none", stroke=AXIS, sw=1)
    s.text(ax.x + ax.w / 2, ax.y + ax.h + 33, "sun's angle from the lens axis (degrees)", size=11.5, anchor="middle", weight=500)
    cx_, cy_ = ax.x - 50, ax.y + ax.h / 2
    s.text(cx_, cy_, "peak on the panel (kW/m²)", size=11.5, anchor="middle", weight=500, extra=f'transform="rotate(-90 {cx_} {cy_})"')
    # bands where the spot centre lies on the crop / 5.5-inch panel / 16-inch monitor
    def ang_for(x):
        return min(so, key=lambda q: abs(abs(q[1]) - x))[0]
    for x_lim, lab, col in ((40, "on the 80 mm crop", "#fde3d6"), (61, "on the 5.5-inch panel", "#fdeee6"), (172, "on the 16-inch monitor", "#fdf6f1")):
        pass
    a_crop = ang_for(40); a_55 = ang_for(61); a_mon = ang_for(172)
    s.rect(ax.X(0), ax.y, ax.X(a_mon) - ax.X(0), ax.h, fill="#fbefe8")
    s.rect(ax.X(0), ax.y, ax.X(a_55) - ax.X(0), ax.h, fill="#f9dfd2")
    s.rect(ax.X(0), ax.y, ax.X(a_crop) - ax.X(0), ax.h, fill="#f6cdb9")
    for v in (1, 10, 100, 1000):
        s.line(ax.x, ax.Y(v), ax.x + ax.w, ax.Y(v), stroke=GRID, sw=0.6)
    s.text(ax.X(a_crop / 2), ax.y + ax.h - 8, "crop", size=10, fill=INK, anchor="middle", weight=700)
    s.text(ax.X((a_crop + a_55) / 2), ax.y + ax.h - 8, "5.5″", size=10, fill=INK, anchor="middle", weight=700)
    s.text(ax.X((a_55 + a_mon) / 2), ax.y + ax.h - 8, "16-inch monitor", size=10, fill=INK, anchor="middle", weight=700)
    ax.curve([(a, max(pk, 1.0)) for a, x, r90, pk, tot in so], stroke=CRIT, sw=2.8)
    for v, lab in ((40, "TI production limit, 40"), (12, "BMW TFT +45 °C, 12")):
        s.line(ax.x, ax.Y(v), ax.x + ax.w, ax.Y(v), stroke=INK2, sw=1, extra='stroke-dasharray="5 3"')
        s.text(ax.x + ax.w - 6, ax.Y(v) - 5, lab, size=10, fill=INK2, anchor="end")
    worst = max(so, key=lambda q: q[3])
    s.circle(ax.X(worst[0]), ax.Y(worst[3]), 4.5, fill=CRIT)
    s.text(ax.X(worst[0]) + 26, ax.Y(worst[3]) - 2, f"{worst[3]:,.0f} kW/m² at {worst[0]:.0f}°: the focus", size=10.5, fill=CRIT, weight=700)
    s.text(ax.X(worst[0]) + 26, ax.Y(worst[3]) + 12, "curves onto the panel plane", size=10.5, fill=CRIT)
    s.text(16, ax.y + ax.h + 56, f"Shaded bands: where the spot's centre lands (on the crop up to {a_crop:.0f}°, on the 5.5-inch panel up to {a_55:.0f}°, on the monitor up to {a_mon:.0f}°).", size=10.5, fill=INK2)
    s.text(16, ax.y + ax.h + 71, "Off axis the focal surface bends toward the lens (section 4) and crosses the panel plane near 12°, so the worst case is not straight down.", size=10.5, fill=INK2)
    # ---------- B: when is the sun there ----------
    y0 = ax.y + ax.h + 112
    step(s, 16, y0, "B", "Sun's angle from straight up at solar noon, with the lens lying flat (lens axis vertical)")
    lats = (25, 35, 45)
    decl = (("June", 23.4), ("Mar / Sep", 0.0), ("December", -23.4))
    bx0, by = 150, y0 + 30
    sc = 380 / 70.0
    for i, (mname, dcl) in enumerate(decl):
        yy = by + i * 64
        s.text(bx0 - 10, yy + 26, mname, size=11, anchor="end", weight=700)
        for j, lat in enumerate(lats):
            z = abs(lat - dcl)
            col = CRIT if z <= 20 else (ORANGE if z <= 30 else MUTED)
            s.rect(bx0, yy + j * 18, z * sc, 14, fill=col, rx=2, extra='opacity="0.85"')
            s.text(bx0 + z * sc + 6, yy + j * 18 + 11, f"{lat}° latitude: {z:.0f}°", size=10, fill=INK2)
    s.line(bx0 + 20 * sc, by - 6, bx0 + 20 * sc, by + 190, stroke=CRIT, sw=1, extra='stroke-dasharray="4 3"')
    s.text(bx0 + 20 * sc + 4, by - 10, "20°", size=10, fill=CRIT)
    s.text(16, by + 214, "Summer middays at most latitudes put the sun within 20° of straight up for hours: a parked car with the rig uncovered will", size=10.5, fill=INK2)
    s.text(16, by + 229, "eventually focus it onto the panel. The real angle also depends on the car's heading, the lens tilt and the roof line,", size=10.5, fill=INK2)
    s.text(16, by + 244, "so the plan's sun-watch rule (section 6.8 of the plan) has to be extended to Stage 1, with the lid as the primary defence.", size=10.5, fill=INK2)
    return s

@fig("fold")
def f_fold():
    W, H = 680, 560
    s = Svg(W, H, "A suggested package for Stage 1: a fold mirror under the lens brings the panel up onto the dash, with a lid that closes over the lens")
    s.rect(0, 0, W, H, fill=SURF)
    s.text(16, 26, "A suggestion, not in the plan: fold the 280 mm path so the box sits on the dash", size=13, weight=700)
    s.text(16, 44, "Side view to scale (1 px per mm). Light path: panel, then a front-surface mirror at 45°, then the lens and the combiner. Same path length.", size=10.5, fill=INK2)
    k = 1.0; ox, oy = 40, 420
    X = lambda x: ox + x * k
    Y = lambda z: oy - z * k
    s.rect(20, Y(0), W - 40, 10, fill="#e1e0d9", stroke=AXIS, sw=0.8)
    s.text(W - 24, Y(0) + 26, "dash top", size=10.5, fill=INK2, anchor="end")
    zl = 110.0; xl0, xl1 = 100.0, 400.0; xc = (xl0 + xl1) / 2
    zm = 48.0
    leg = O.U - (zl - zm)
    xp = xc + leg
    s.rect(X(xl0 - 20), Y(zl + 6), (xp + 24 - (xl0 - 20)) * k, (zl + 6) * k, fill="#f7f7f4", stroke=INK2, sw=1.4, rx=4)
    s.text(X(xl0 - 12), Y(10), "matte black inside", size=10, fill=INK2)
    s.line(X(xl0), Y(zl), X(xl1), Y(zl), stroke=TEAL, sw=4)
    s.text(X(xl0) + 4, Y(zl) - 10, "Fresnel lens, grooves up", size=11, fill=TEAL, weight=700)
    mh = 40.0
    s.line(X(xc - mh), Y(zm + mh), X(xc + mh), Y(zm - mh), stroke=BLUE, sw=4)
    s.text(X(xc - mh) - 6, Y(zm + mh) + 14, "front-surface", size=10.5, fill=BLUE, weight=700, anchor="end")
    s.text(X(xc - mh) - 6, Y(zm + mh) + 28, "mirror at 45°", size=10.5, fill=BLUE, weight=700, anchor="end")
    s.line(X(xp), Y(zm - 20), X(xp), Y(zm + 20), stroke=INK, sw=5)
    s.text(X(xp) + 10, Y(zm) - 4, "panel crop", size=10.5, weight=700)
    s.text(X(xp) + 10, Y(zm) + 10, "(40 mm tall),", size=10.5, fill=INK2)
    s.text(X(xp) + 10, Y(zm) + 24, "backlight behind", size=10.5, fill=INK2)
    n = np.array([1.0, 1.0]) / math.sqrt(2)
    for p, col in ((-20, BLUE), (0, ORANGE), (20, PURPLE)):
        slope = 1.15 * p / O.U
        P0 = np.array([xp, zm + p]); d = np.array([-1.0, slope]); d /= np.linalg.norm(d)
        t = ((xc - P0[0]) - (P0[1] - zm)) / (d[0] + d[1])
        M = P0 + t * d
        d2 = d - 2 * np.dot(d, n) * n
        t2 = (zl - M[1]) / d2[1]
        Lh = M + t2 * d2
        conv = -(Lh[0] - xc) / O.EYE_Z
        top = Lh + np.array([conv * 130, 130])
        polyline(s, [(X(P0[0]), Y(P0[1])), (X(M[0]), Y(M[1])), (X(Lh[0]), Y(Lh[1])), (X(top[0]), Y(top[1]))], stroke=col, sw=1.5)
    s.line(X(xc - 120), Y(zl + 230), X(xc + 80), Y(zl + 140), stroke=BLUE, sw=3, extra='opacity="0.7"')
    s.text(X(xc + 86), Y(zl + 140) + 4, "combiner above", size=10.5, fill=BLUE)
    s.line(X(xl0 - 20), Y(zl + 8), X(xl0 - 60), Y(zl + 130), stroke=CRIT, sw=3)
    s.text(X(xl0 - 52), Y(zl + 154), "opaque lid: closed whenever", size=10.5, fill=CRIT, weight=700)
    s.text(X(xl0 - 52), Y(zl + 140), "the HUD is off or the car is parked", size=10.5, fill=CRIT)
    dim(s, X(xc), Y(zm) + 46, X(xp), Y(zm) + 46, f"{leg:.0f} mm", off=0, size=10.5)
    dim(s, X(xl1) + 14, Y(zl), X(xl1) + 14, Y(zm), f"{zl - zm:.0f}", off=0, size=10.5)
    s.text(X(xl1) + 40, Y(zl + 60), f"{leg:.0f} + {zl - zm:.0f} = {O.U:.0f} mm,", size=11, weight=700)
    s.text(X(xl1) + 40, Y(zl + 60) + 15, "panel to lens as before", size=10.5, fill=INK2)
    dim(s, X(xl0 - 20), Y(0) + 34, X(xp + 24), Y(0) + 34, f"box about {xp + 44 - xl0:.0f} mm long, {zl + 6:.0f} mm tall", off=0, size=10.5)
    rows = ["The mirror reverses the image once; the renderer flips it. A front-surface mirror avoids a second, ghost reflection.",
            "Set the 280 mm along the folded path with the panel on a slide (section 11) and keep every stray-light surface matte black.",
            "The mirror and panel must stay put to well under a millimetre: 1 mm of panel movement shifts the image 0.2 m (section 4)."]
    for i, t in enumerate(rows):
        s.text(16, H - 46 + i * 16, t, size=10.5, fill=INK2)
    return s

@fig("align")
def f_align():
    W, H = 680, 560
    s = Svg(W, H, "Setting the panel distance by parallax: where the HUD cross appears against a target when the head moves, for an image too close and too far")
    s.rect(0, 0, W, H, fill=SURF)
    s.text(16, 26, "Put a target where the image should be, look past the HUD cross at it, and move your head", size=13, weight=700)
    s.text(16, 44, "Top view, depth not to scale. The cross is fixed on the virtual image; the lines show where each eye sees it against the target.", size=10.5, fill=INK2)
    def panel(cx, y_img, title, verdict, fix):
        yt, yh = 130, 400
        s.text(cx, 80, title, size=12, weight=700, anchor="middle")
        s.line(cx - 140, yt, cx + 140, yt, stroke=MUTED, sw=1, extra='stroke-dasharray="3 4"')
        s.text(cx + 140, yt - 8, "target", size=10, fill=INK2, anchor="end")
        s.circle(cx, yt, 7, fill="none", stroke=INK, sw=2)
        s.line(cx - 140, y_img, cx + 140, y_img, stroke=ORANGE, sw=1.4, extra='stroke-dasharray="6 3"')
        s.text(cx - 140, y_img - 6, "virtual image", size=10, fill=ORANGE, weight=700)
        s.line(cx - 6, y_img, cx + 6, y_img, stroke=ORANGE, sw=2.4); s.line(cx, y_img - 6, cx, y_img + 6, stroke=ORANGE, sw=2.4)
        for ex, col, lab in ((cx - 45, BLUE, "head left"), (cx + 45, PURPLE, "head right")):
            s.circle(ex, yh, 7, fill=col)
            s.text(ex, yh + 22, lab, size=10.5, anchor="middle", weight=700, fill=col)
            t = (yt - yh) / (y_img - yh)
            xt = ex + (cx - ex) * t
            s.line(ex, yh, xt, yt, stroke=col, sw=1.2)
            s.line(xt - 5, yt - 5, xt + 5, yt + 5, stroke=col, sw=2); s.line(xt - 5, yt + 5, xt + 5, yt - 5, stroke=col, sw=2)
        s.text(cx, yh + 50, verdict, size=10.8, anchor="middle", weight=700)
        s.text(cx, yh + 66, fix, size=10.5, anchor="middle", fill=INK2)
    panel(175, 210, "Image too close", "The cross slides opposite to your head.", "Move the panel away from the lens.")
    panel(505, 100, "Image too far", "The cross slides with your head.", "Move the panel toward the lens.")
    s.text(16, H - 30, "When the cross stays on the target as the head moves, the image is at the target's distance. Each millimetre of panel travel", size=10.5, fill=INK2)
    s.text(16, H - 14, "changes the image by 0.013 D, so half-millimetre steps are easy to see against a target 4.9 m away.", size=10.5, fill=INK2)
    return s
