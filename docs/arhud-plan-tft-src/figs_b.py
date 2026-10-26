"""Optics figures: reflectance, ghost image, luminance, window, the three stages, sun focus, sun entry, backlight, emission cone."""
import math
from svgkit import *
from calc import (V, CURVE, LUM, SOURCES, PGU_W, PGU_H, U2, F2, M2, MIRROR_R, GHOST_75,
                  RAKE, LOOKDOWN, PATH_WS, PATH_WS_TWO, L_DAY_EYE, L_NIGHT_EYE, L_ROAD_EYE,
                  CONE_H_HALF, LAMB_FRAC)

# ---------- Fresnel reflectance chart ----------
@fig("fresnel")
def f_fresnel():
    W, H = 680, 360
    s = Svg(W, H, "Reflectance of glass at n = 1.52 versus angle of incidence, s and p polarisation")
    s.rect(0, 0, W, H, fill=SURF)
    X0, X1, Y0, Y1 = 62, 630, 300, 40
    amax = 80.0; vmax = 60.0
    sx = lambda a: X0 + a / amax * (X1 - X0)
    sy = lambda v: Y0 - v / vmax * (Y0 - Y1)
    for v in range(0, 61, 10):
        s.line(X0, sy(v), X1, sy(v), stroke=GRID if v else AXIS, sw=1)
        s.text(X0 - 10, sy(v) + 4, f"{v}%", size=11, fill=INK2, anchor="end")
    for a in range(0, 81, 10):
        s.line(sx(a), Y0, sx(a), Y0 + 4, stroke=AXIS, sw=1)
        s.text(sx(a), Y0 + 19, f"{a}°", size=11, fill=INK2, anchor="middle")
    s.text((X0 + X1) / 2, Y0 + 40, "Angle of incidence, from the normal", size=11.5, fill=INK, anchor="middle")
    s.text(18, (Y0 + Y1) / 2, "Reflected fraction", size=11.5, fill=INK, anchor="middle",
           extra=f'transform="rotate(-90 18 {(Y0+Y1)/2})"')
    pts_s = [(sx(a), sy(v)) for a, v, _ in CURVE if a <= amax]
    pts_p = [(sx(a), sy(p)) for a, _, p in CURVE if a <= amax]
    s.path("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts_s), stroke=BLUE, sw=2.2)
    s.path("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts_p), stroke=ORANGE, sw=2.2)
    xa = sx(65)
    s.line(xa, Y1, xa, Y0, stroke=INK2, sw=1)
    s.text(xa + 6, Y1 + 12, "65° design point", size=11, fill=INK)
    s.circle(xa, sy(23.6), 5, fill=BLUE, stroke=SURF, sw=2)
    s.circle(xa, sy(1.23), 5, fill=ORANGE, stroke=SURF, sw=2)
    s.text(xa - 8, sy(23.6) - 10, f"s  {V['rs65']}", size=12, weight=600, fill=INK, anchor="end")
    s.text(sx(4), sy(44), f"At 65°:  s = {V['rs65']},   p = {V['rp65']}", size=12, weight=600, fill=INK)
    xb = sx(56.7)
    s.circle(xb, sy(0), 4, fill=ORANGE, stroke=SURF, sw=2)
    s.text(xb, sy(0) - 12, f"Brewster {V['brewster']}°: p = 0", size=11, fill=INK, anchor="middle")
    s.text(sx(61), sy(46), "s-polarised", size=12, weight=600, fill=INK, anchor="end")
    s.line(X0 + 2, 20, X0 + 26, 20, stroke=BLUE, sw=2.2)
    s.text(X0 + 32, 24, "s (perpendicular) polarisation", size=11.5, fill=INK)
    s.line(X0 + 232, 20, X0 + 256, 20, stroke=ORANGE, sw=2.2)
    s.text(X0 + 262, 24, "p (parallel) polarisation", size=11.5, fill=INK)
    return s

# ---------- Ghost image geometry, with the numbers ----------
@fig("ghost")
def f_ghost():
    W, H = 680, 290
    s = Svg(W, H, "Two reflections from a plain laminated windshield: the two reflected rays are parallel and offset by about 3 mm")
    s.rect(0, 0, W, H, fill=SURF)
    # glass slab, drawn horizontal for clarity, thickness exaggerated
    ys, yi = 150, 190                         # outer and inner surfaces (inner faces the cabin, drawn below)
    s.rect(60, ys, 420, yi - ys, fill=BLUE_T, stroke="none")
    s.line(60, ys, 480, ys, stroke=INK2, sw=2)
    s.line(60, yi, 480, yi, stroke=INK2, sw=2)
    s.text(64, ys - 8, "outer surface", size=10.5, fill=INK2)
    s.text(476, yi + 16, "inner surface (cabin side)", size=10.5, fill=INK2, anchor="end")
    s.text(270, (ys + yi) / 2 + 4, f"glass + PVB + glass, {V['t_glass']} total (assumed)", size=10.5, fill=INK2, anchor="middle")
    # incoming ray from the mirror at 65 degrees to the normal, hitting the inner surface
    P1 = (200, yi)
    S = (P1[0] - 150 * math.tan(math.radians(65)) * 0.5, yi + 75)
    s.arrow(S[0], S[1], P1[0], P1[1], color=INK, sw=1.8)
    s.text(S[0] - 6, S[1] + 14, "from the mirror, 65°", size=10.5, fill=INK, anchor="start")
    # reflection 1 off the inner surface
    E1 = (P1[0] + 150 * math.tan(math.radians(65)) * 0.5, yi + 75)
    s.line(P1[0], P1[1], E1[0], E1[1], stroke=ORANGE, sw=2.2)
    # refracted ray inside, reflection at the outer surface, exit
    P2 = (P1[0] + (yi - ys) * math.tan(math.radians(36.6)), ys)
    P3 = (P2[0] + (yi - ys) * math.tan(math.radians(36.6)), yi)
    E2 = (P3[0] + 150 * math.tan(math.radians(65)) * 0.5, yi + 75)
    s.line(P1[0], P1[1], P2[0], P2[1], stroke=BLUE, sw=2)
    s.line(P2[0], P2[1], P3[0], P3[1], stroke=BLUE, sw=2)
    s.line(P3[0], P3[1], E2[0], E2[1], stroke=BLUE, sw=2.2)
    s.text(E1[0] - 4, E1[1] + 14, "image 1 (24%)", size=11, weight=600, fill=ORANGE, anchor="end")
    s.text(E2[0] + 4, E2[1] + 14, f"image 2 ({V['ghost_rel']} of image 1)", size=11, weight=600, fill=BLUE)
    s.text(P3[0] + 8, yi - 8, f"{V['ghost_surf']} along the glass", size=10.5, fill=INK2)
    # numbers panel
    s.rect(500, 40, 166, 200, fill=GREY_T, rx=6)
    s.lines(510, 62, ["Parallel rays, offset", f"d = {V['ghost_perp']}", "", "Seen as two images", "separated by d ÷ D:", f"2 m image: {V['ghost_2']}′", f"7.5 m image: {V['ghost_7_5']}′", f"10 m image: {V['ghost_10']}′", "", f"At 7.5 m that is {V['ghost_px']} px", f"of a {V['px_arcmin']}′ pixel."], size=10.8, lh=15)
    s.text(14, 22, "Refraction drawn; angles true for n = 1.52. The wedge interlayer (not shown) tilts the inner surface so the two rays converge at the design eye point.", size=10, fill=MUTED)
    return s

# ---------- Luminance budget (log axis) ----------
@fig("luminance")
def f_luminance():
    import math as m
    W, H = 680, 420
    s = Svg(W, H, "Luminance at the eye for each TFT source through the windshield path, log scale, with the sky target, road target and night ceiling")
    s.rect(0, 0, W, H, fill=SURF)
    X0, X1 = 330, 640      # 10 .. 100,000 cd/m2
    lx = lambda v: X0 + (m.log10(v) - 1) / 4 * (X1 - X0)
    rows = []
    for key, label, lp in SOURCES:
        rows.append((label.replace("cd/m2", "cd/m²"), LUM[key]["ws"], BLUE))
    rows.insert(0, ("YODOIT monitor · Stage 0/1 combiner path (30%)", LUM["yod"]["comb"], MUTED))
    top = 70; rh = 34
    for dec in (10, 100, 1000, 10000, 100000):
        xx = lx(dec)
        s.line(xx, top - 14, xx, top + rh * len(rows) - 8, stroke=GRID, sw=1)
        s.text(xx, top + rh * len(rows) + 8, f"{dec:,}", size=11, fill=INK2, anchor="middle")
    s.text((X0 + X1) / 2, top + rh * len(rows) + 28, "cd/m² at the eye (log scale)", size=11.5, fill=INK, anchor="middle")
    for i, (name, v, col) in enumerate(rows):
        y = top + i * rh
        s.text(X0 - 14, y + 5, name, size=10.5, fill=INK, anchor="end")
        s.rect(X0, y - 8, lx(v) - X0, 16, fill=col, rx=4)
        s.text(lx(v) + 8, y + 5, f"{v:,.0f}", size=11.5, fill=INK2)
    for val, label, anchor, dx in ((L_DAY_EYE, "sky target 1,500", "start", 6), (L_ROAD_EYE, "road target 750", "end", -6), (L_NIGHT_EYE, "night ceiling 50", "end", -6)):
        xx = lx(val)
        s.line(xx, 40, xx, top + rh * len(rows) - 8, stroke=INK, sw=1.5)
        s.text(xx + dx, 34 if val != L_ROAD_EYE else 50, label, size=11, weight=600, fill=INK, anchor=anchor)
    s.text(14, H - 28, f"Windshield path: two mirrors at 90% and one glass surface at 24%, together {V['path_ws']} of the panel's luminance.", size=10.5, fill=INK)
    s.text(14, H - 10, f"With both glass surfaces overlapping (wedge glass or a broad patch) the path passes {V['path_ws_two']}. Bars start at 10 cd/m².", size=10.5, fill=MUTED)
    return s

# ---------- Window geometry at 7.5 m ----------
@fig("window")
def f_window():
    W, H = 680, 300
    s = Svg(W, H, "Demo window sizes at 7.5 metres, drawn to scale and centred")
    s.rect(0, 0, W, H, fill=SURF)
    k = 260.0
    cx, cy = 340, 150
    opts = [(1.42, 0.71, GREY_T, AXIS, f"{V['fov2_w']}° × {V['fov2_h']}° · the 60 × 30 mm crop at magnification {V['m2']} (design)"),
            (1.31, 0.66, BLUE_T, BLUE, "10° × 5° · 2:1, a 55 × 28 mm crop"),
            (1.31, 0.52, ORANGE_T, ORANGE, f"10° × 4° · 2.5:1, a {V['crop_10x4_w']} × {V['crop_10x4_h']} mm crop")]
    for w, h, fill, stroke, label in opts:
        s.rect(cx - w * k / 2, cy - h * k / 2, w * k, h * k, fill=fill, stroke=stroke, sw=1.5)
    s.text(cx, 282, "Sizes at 7.5 m. Outer to inner. The crop is a software setting; the mirror is the same for all three.", size=11, fill=MUTED, anchor="middle")
    yy = 52
    for w, h, fill, stroke, label in opts:
        s.rect(20, yy - 11, 14, 14, fill=fill, stroke=stroke, sw=1.5)
        s.text(42, yy + 1, label, size=11.5, fill=INK)
        yy += 26
    return s

# ---------- Stage 0 ----------
@fig("stage0")
def f_stage0():
    W, H = 680, 270
    s = Svg(W, H, "Stage 0 bench rig: monitor face-up, 70/30 beamsplitter at 45 degrees, eye on the far side")
    s.rect(0, 0, W, H, fill=SURF)
    bx, by = 290, 120
    s.line(bx - 62, by + 62, bx + 62, by - 62, stroke=BLUE, sw=3)
    s.text(bx + 70, by - 60, "70/30 beamsplitter", size=11.5, fill=INK)
    s.rect(bx - 60, 224, 120, 14, fill=INK, rx=2)
    s.text(bx, 258, "monitor 1, face-up (or the 5.5-inch panel)", size=11.5, fill=INK, anchor="middle")
    s.arrow(bx, 222, bx, by, color=ORANGE, sw=2.4)
    s.line(bx, by, 600, by, stroke=ORANGE, sw=2.4)
    s.text(bx + 90, by - 12, "reflected panel light (30%)", size=11, fill=INK, anchor="start")
    s.line(40, by, bx, by, stroke=MUTED, sw=2)
    s.text(40, by - 12, "road light (70%)", size=11, fill=INK2)
    s.circle(616, by, 10, fill=INK)
    s.text(616, by - 18, "eye", size=11.5, fill=INK, anchor="middle")
    s.text(14, 26, "Virtual image distance equals the panel's path length (about 0.6 m).", size=11, fill=INK2)
    s.text(14, 44, "Purpose: renderer bring-up, projection maths, colour, latency. Not a driving view.", size=11, fill=INK2)
    return s

# ---------- Stage 1 ----------
@fig("stage1")
def f_stage1():
    W, H = 680, 300
    s = Svg(W, H, "Stage 1: panel, Fresnel magnifier at 280 mm, combiner, eye; virtual image about 4 m away")
    s.rect(0, 0, W, H, fill=SURF)
    s.rect(24, 74, 120, 160, fill=BLUE_T, stroke=BLUE, sw=1.2, rx=4)
    s.text(84, 160, "virtual", size=12, weight=600, fill=INK, anchor="middle")
    s.text(84, 178, "image", size=12, weight=600, fill=INK, anchor="middle")
    s.text(84, 252, "1.2 × 0.6 m at ≈ 4.2 m", size=11, fill=INK2, anchor="middle")
    s.rect(220, 112, 16, 60, fill=INK, rx=2)
    s.text(228, 96, "panel", size=11.5, fill=INK, anchor="middle")
    s.text(228, 186, "80 × 40 mm crop", size=10.5, fill=INK2, anchor="middle")
    lxp = 330
    s.line(lxp, 60, lxp, 230, stroke=BLUE, sw=2.6)
    s.text(lxp, 52, "Fresnel lens", size=11.5, fill=INK, anchor="middle")
    s.text(lxp, 244, "f = 300 mm", size=11.5, fill=INK, anchor="middle")
    s.line(236, 142, lxp, 142, stroke=ORANGE, sw=2)
    s.line(lxp, 142, 470, 142, stroke=ORANGE, sw=2)
    cxp, cyp = 470, 142
    s.line(cxp - 40, cyp + 40, cxp + 40, cyp - 40, stroke=BLUE, sw=2.6)
    s.text(cxp + 46, cyp + 52, "70/30 combiner", size=11.5, fill=INK)
    s.line(cxp, cyp, cxp, 62, stroke=ORANGE, sw=2)
    s.circle(cxp, 52, 9, fill=INK)
    s.text(cxp + 14, 56, "eye", size=11.5, fill=INK)
    s.line(cxp, 62, 144, 142, stroke=MUTED, sw=1)
    s.text(W - 14, H - 14, "Schematic. Panel at 280 mm from the lens, inside the 300 mm focal length, gives a virtual image.", size=10.5, fill=MUTED, anchor="end")
    s.text(14, 26, f"1/v = 1/f − 1/u = 1/300 − 1/280 so v = −{V['s1_dist']} ;  magnification {V['s1_M']}", size=11.5, fill=INK, weight=600)
    return s

# ---------- Stage 2 block diagram ----------
@fig("stage2")
def f_stage2():
    W, H = 680, 262
    s = Svg(W, H, "Stage 2 light path: TFT PGU, cold-mirror fold, concave mirror, windshield, eye, with the single-mirror numbers")
    s.rect(0, 0, W, H, fill=SURF)
    blocks = [("TFT PGU", "5.5-inch panel, 60 × 30", "mm crop, s-polarised", ORANGE_T, ORANGE),
              ("Cold-mirror fold", "reflects the image,", "passes solar infrared", GREY_T, INK2),
              ("Concave mirror", f"f = {V['f2']}", f"PGU at {V['u2']}", ORANGE_T, ORANGE),
              ("Windshield", f"{V['rs65']} s-reflection", "plain glass first", BLUE_T, BLUE),
              ("Eye", "eye box 130 × 70 mm", "head-tracked", SURF, INK)]
    bw, gap, y0, bh = 118, 18, 40, 92
    x = 14
    for i, (t, l1, l2, fill, stroke) in enumerate(blocks):
        s.rect(x, y0, bw, bh, fill=fill, stroke=stroke, sw=1.4, rx=6)
        s.text(x + bw / 2, y0 + 24, t, size=12, weight=700, fill=INK, anchor="middle")
        s.text(x + bw / 2, y0 + 47, l1, size=10.5, fill=INK2, anchor="middle")
        if l2:
            s.text(x + bw / 2, y0 + 63, l2, size=10.5, fill=INK2, anchor="middle")
        if i < len(blocks) - 1:
            s.arrow(x + bw + 2, y0 + bh / 2, x + bw + gap - 2, y0 + bh / 2, color=INK, sw=1.8)
        x += bw + gap
    s.text(14, 162, "Numbers from the single-mirror equation, with the object inside the focal length:", size=11.5, fill=INK, weight=600)
    lines = [
        f"1/u + 1/v = 1/f with f = {V['f2']} and v = −7.5 m (virtual)  so  u = {V['u2']}",
        f"magnification {V['m2']};  image {V['img2_w']} × {V['img2_h']} at 7.5 m;  field {V['fov2_w']}° × {V['fov2_h']}°;  {V['ppd2']} px per degree",
        f"mirror aperture from the eye box and field: about {V['mir_w']} × {V['mir_h']} mm at 1 m from the eye",
    ]
    for i, t in enumerate(lines):
        s.text(14, 182 + i * 18, t, size=11.2, fill=INK, weight=500)
    s.text(14, 250, "The windshield is in the light path but not in this model. A ray trace with the chosen car's glass must precede the mirror order.", size=11, fill=INK2, weight=600)
    return s

# ---------- Sun focus hazard, with the defence in depth ----------
@fig("sunhazard")
def f_sunhazard():
    W, H = 680, 262
    s = Svg(W, H, "Sunlight entering the windshield, focused by the concave mirror onto the panel, and what each defence removes")
    s.rect(0, 0, W, H, fill=SURF)
    steps = [("Sun", f"{V['sun_w']} collected", GREY_T, INK2),
             ("Concave mirror", "focuses it", ORANGE_T, ORANGE),
             ("Cold mirror + IR cut", f"{V['sun_after_filt']} left", BLUE_T, BLUE),
             ("Aperture polariser", f"halves it: {V['sun_after_pol']} left", BLUE_T, BLUE),
             ("Panel", f"{V['sun_spot_mm']} mm spot", ORANGE_T, ORANGE)]
    bw, gap, y0, bh = 118, 18, 30, 70
    x = 14
    for i, (t, sub, fill, stroke) in enumerate(steps):
        s.rect(x, y0, bw, bh, fill=fill, stroke=stroke, sw=1.4, rx=6)
        s.text(x + bw / 2, y0 + 28, t, size=11.5, weight=700, fill=INK, anchor="middle")
        s.text(x + bw / 2, y0 + 50, sub, size=10.2, fill=INK2, anchor="middle")
        if i < len(steps) - 1:
            s.arrow(x + bw + 2, y0 + bh / 2, x + bw + gap - 2, y0 + bh / 2, color=INK, sw=1.8)
        x += bw + gap
    s.text(14, 130, f"The focal point is {V['focus_gap']} beyond the panel, so the panel sits almost at the focus.", size=11.5, fill=INK, weight=600)
    s.text(14, 150, f"Ray trace, on-axis sun, no losses: 90% of rays land within {V['r90_pgu']} mm of the axis at the panel plane,", size=11, fill=INK2)
    s.text(14, 166, f"a concentration of about {V['conc_pgu']}: {V['sun_w']} into a {V['sun_spot_mm']} mm spot is {V['sun_wcm2']} W/cm², before any filter.", size=11, fill=INK2)
    s.text(14, 186, f"After the infrared filters ({V['filt_frac']} passes, TI) and the polariser, {V['sun_after_pol']} remains: {V['sun_after_pol_wcm2']} W/cm², about {V['sun_suns']} suns.", size=11, fill=INK2)
    s.text(14, 210, "Filters reduce the load; they do not remove the focus. The shutter and the sun-watch rule keep the spot off the panel.", size=11, fill=CRIT, weight=600)
    s.text(14, 230, "Ideal geometry only, not a measurement. The thermocouple test precedes any sun exposure of the assembled unit.", size=11, fill=INK2)
    return s

# ---------- Sun entry direction (side view) ----------
@fig("sunentry")
def f_sunentry():
    W, H = 680, 300
    s = Svg(W, H, "Side view: the HUD's own rays, continued through the glass, point at the sky behind the car; the sun there is focused onto the panel")
    s.rect(0, 0, W, H, fill=SURF)
    # geometry in the figure: forward is to the left, up is up
    gx, gy = 300, 150                       # glass point
    rake = math.radians(RAKE)
    # glass line: runs backward-up (to the right and up) at the rake angle
    L = 120
    s.line(gx + L * math.cos(rake), gy - L * math.sin(rake), gx - L * math.cos(rake), gy + L * math.sin(rake), stroke=BLUE, sw=3)
    s.text(gx - L * math.cos(rake) - 6, gy + L * math.sin(rake) + 16, f"windshield, {V['rake']}° above horizontal", size=10.5, fill=INK, anchor="end")
    # eye behind (to the right) looking forward-down by LOOKDOWN
    ex, ey = 560, 128
    s.circle(ex, ey, 8, fill=INK)
    s.text(ex, ey - 16, "eye", size=11, fill=INK, anchor="middle")
    s.line(ex, ey, gx, gy, stroke=INK, sw=1.6)
    s.text(430, 128, f"look-down {V['lookdown']}°", size=10.5, fill=INK2, anchor="middle")
    # reflected (reversed) ray to the mirror: forward and down at mirror_dir degrees
    md = math.radians(float(V["mirror_dir"]))
    mx, my = gx - 90 * math.cos(md), gy + 90 * math.sin(md)
    s.line(gx, gy, mx, my, stroke=ORANGE, sw=2.2)
    s.rect(mx - 22, my - 4, 44, 8, fill=ORANGE, rx=2)
    s.text(mx, my + 24, "concave mirror", size=11, fill=INK, anchor="middle")
    s.text(mx - 20, my - 12, f"{V['mirror_dir']}° down", size=10.5, fill=INK2, anchor="middle")
    # continuation through the glass, backward and up, to the sun
    sx_, sy_ = gx + 118 * math.cos(md), gy - 118 * math.sin(md)
    s.line(gx, gy, sx_, sy_, stroke=ORANGE, sw=2.2)
    s.circle(sx_ + 12 * math.cos(md), sy_ - 12 * math.sin(md), 11, fill="#f2c14e", stroke=ORANGE, sw=1.5)
    s.text(sx_ + 30, sy_ + 4, f"sun at {V['sun_elev']}° elevation,", size=11, weight=600, fill=INK, anchor="start")
    s.text(sx_ + 30, sy_ + 18, "behind the car", size=11, weight=600, fill=INK, anchor="start")
    # horizon reference
    s.line(gx - 150, gy, gx + 60, gy, stroke=GRID, sw=1)
    s.text(gx - 150, gy - 6, "horizontal", size=10, fill=MUTED)
    # labels
    s.text(14, 22, "Forward is to the left. Orange: the HUD ray reversed, and its continuation through the glass.", size=10.5, fill=MUTED)
    s.text(14, 268, f"Light reverses: sunlight from that direction transmits through the glass, hits the mirror and is focused on the panel.", size=11, fill=INK)
    s.text(14, 286, f"The entry patch is about {V['patch_w']}° × {V['patch_h']}° of sky (eye box plus field). Rake 25°: {V['sun_elev_25']}°; rake 35°: {V['sun_elev_35']}°. The sun crosses it in about {V['patch_minutes']} minutes.", size=10.5, fill=INK2)
    return s

# ---------- Backlight stack ----------
@fig("backlight")
def f_backlight():
    W, H = 680, 300
    s = Svg(W, H, "Cross-section of the custom direct-lit backlight behind the panel's 60 × 30 mm crop, with the design numbers")
    s.rect(0, 0, W, H, fill=SURF)
    x0 = 60; w = 300
    layers = [("heat sink and fan", 40, "#d9d8d2", INK2),
              ("LED board: 6–8 high-power white LEDs", 18, ORANGE_T, ORANGE),
              ("mixing cavity, white walls, 20–25 mm", 40, SURF, INK2),
              ("diffuser plate", 8, GREY_T, INK2),
              ("BEF prism films ×2 (crossed)", 10, BLUE_T, BLUE),
              ("IR-cut glass", 6, BLUE_T, BLUE),
              ("LCD cell, stock polarisers; only the crop is lit", 12, INK, INK),
              ("half-wave retarder film if the axis is wrong", 6, GREY_T, INK2)]
    y = 250
    for name, h, fill, stroke in layers:
        y -= h
        s.rect(x0, y, w, h, fill=fill, stroke=stroke, sw=1)
        s.text(x0 + w + 12, y + h / 2 + 4, name, size=10.8, fill=INK)
    s.text(x0, 268, "bottom: LEDs", size=10, fill=MUTED)
    s.text(x0 + w, 268, "top: image toward the fold mirror", size=10, fill=MUTED, anchor="end")
    # arrows of light
    for xx in (x0 + 60, x0 + 150, x0 + 240):
        s.arrow(xx, 236, xx, 60, color=ORANGE, sw=1.4)
    # numbers
    s.rect(14, 14, 420, 44, fill=GREY_T, rx=6)
    s.text(22, 32, f"Target {V['l_panel_design']} cd/m² at the panel through a {V['t_lcd']} cell: backlight {V['l_bl']} cd/m²", size=10.8, weight=600, fill=INK)
    s.text(22, 50, f"{V['phi_out']} lm leave the {V['a_crop_cm2']} cm² crop; at {V['eta_bl']} optical efficiency and {V['led_lmw']} lm/W: {V['p_led']} of LED, {V['p_led_film']} with the films", size=10.8, fill=INK)
    return s

# ---------- Emission cone versus eye box ----------
@fig("cone")
def f_cone():
    W, H = 680, 260
    s = Svg(W, H, "Why the backlight should be directional: a panel point must send light only into the cone that the mirror maps onto the eye box")
    s.rect(0, 0, W, H, fill=SURF)
    px, py = 90, 130
    mx = 440
    k = (mx - px) / U2                      # px per mm along the axis
    # panel point and mirror
    s.rect(px - 6, py - 40, 6, 80, fill=INK)
    s.text(px - 10, py + 58, "panel point", size=11, fill=INK, anchor="middle")
    s.path(f"M{mx:.1f},{py-100:.1f} Q{mx+28:.1f},{py:.1f} {mx:.1f},{py+100:.1f}", stroke=ORANGE, sw=3)
    s.text(mx + 8, py - 104, f"concave mirror, {V['u2']} away", size=11, fill=INK)
    # cone to the eye-box-sized region on the mirror
    half = 65 * k
    s.poly([(px, py), (mx, py - half), (mx, py + half)], fill=BLUE_T, stroke=BLUE, sw=1.2)
    s.text((px + mx) / 2, py - 6, f"±{V['cone_h']}° covers a 130 mm patch", size=11, weight=600, fill=INK, anchor="middle")
    s.text((px + mx) / 2, py + 14, "that the mirror sends to the eye box", size=10.5, fill=INK2, anchor="middle")
    # wasted light outside the cone
    s.line(px, py, px + 200, py - 150, stroke=MUTED, sw=1)
    s.line(px, py, px + 200, py + 150, stroke=MUTED, sw=1)
    s.text(px + 160, py - 86, "light outside the cone never reaches an eye", size=10.5, fill=MUTED)
    # numbers
    s.rect(470, 40, 196, 150, fill=GREY_T, rx=6)
    s.lines(480, 62, [f"Lambertian panel: {V['lamb_frac']} of", f"its flux falls inside ±{V['cone_design']}°;", f"{V['lamb_waste']} is wasted.", "", f"Ideal collimation gain: {V['collim_ideal']}×", f"Prism films (assumed): {V['gain_film']}×", f"Collimated design (assumed): {V['gain_collim']}×"], size=10.8, lh=15)
    s.text(14, 24, f"Not to scale. Horizontal cone shown; the vertical cone is ±{V['cone_v']}° for the 70 mm eye-box height.", size=10, fill=MUTED)
    s.text(14, 248, "Production HUD backlights collimate for this reason. Crossed prism films are the first step; a lens-and-diffuser backlight the second.", size=10.5, fill=INK2)
    return s
