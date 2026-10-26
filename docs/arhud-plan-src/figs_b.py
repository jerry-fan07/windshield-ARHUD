"""Optics figures: reflectance, ghost image, luminance, window geometry, the three stages, sun focus."""
import math
from svgkit import *
from calc import V, CURVE, LUM, L_DLP, PGU_W, PGU_H, U2, F2, M2, MIRROR_R

# ---------- Fresnel reflectance chart (two series, legend + direct labels) ----------
@fig("fresnel")
def f_fresnel():
    W, H = 680, 360
    s = Svg(W, H, "Reflectance of glass at n = 1.52 versus angle of incidence, s and p polarisation")
    s.rect(0, 0, W, H, fill=SURF)
    X0, X1, Y0, Y1 = 62, 630, 300, 40        # plot box (px)
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
    # 65 degree operating point
    xa = sx(65)
    s.line(xa, Y1, xa, Y0, stroke=INK2, sw=1)
    s.text(xa + 6, Y1 + 12, "65° design point", size=11, fill=INK)
    s.circle(xa, sy(23.6), 5, fill=BLUE, stroke=SURF, sw=2)
    s.circle(xa, sy(1.23), 5, fill=ORANGE, stroke=SURF, sw=2)
    s.text(xa - 8, sy(23.6) - 10, f"s  {V['rs65']}", size=12, weight=600, fill=INK, anchor="end")
    s.text(sx(4), sy(44), f"At 65°:  s = {V['rs65']},   p = {V['rp65']}", size=12, weight=600, fill=INK)
    # Brewster
    xb = sx(56.7)
    s.circle(xb, sy(0), 4, fill=ORANGE, stroke=SURF, sw=2)
    s.text(xb, sy(0) - 12, f"Brewster {V['brewster']}°: p = 0", size=11, fill=INK, anchor="middle")
    # direct labels at curve ends
    s.text(sx(61), sy(46), "s-polarised", size=12, weight=600, fill=INK, anchor="end")
    # legend
    s.line(X0 + 2, 20, X0 + 26, 20, stroke=BLUE, sw=2.2)
    s.text(X0 + 32, 24, "s (perpendicular) polarisation", size=11.5, fill=INK)
    s.line(X0 + 232, 20, X0 + 256, 20, stroke=ORANGE, sw=2.2)
    s.text(X0 + 262, 24, "p (parallel) polarisation", size=11.5, fill=INK)
    return s

# ---------- Ghost image and wedge PVB (schematic, not to scale) ----------
@fig("ghost")
def f_ghost():
    W, H = 680, 260
    s = Svg(W, H, "Two reflections from a laminated windshield: plain laminate (two images) and wedge interlayer (one image)")
    s.rect(0, 0, W, H, fill=SURF)
    panels = [(14, "Plain laminate: parallel surfaces"), (354, "Wedge interlayer: tilted inner surface")]
    for px, title in panels:
        s.rect(px, 28, 312, 220, fill="#f7f7f4", rx=6)
        s.text(px + 12, 48, title, size=12, weight=700, fill=INK)
        ys = 150                                   # outer surface
        yi = 168                                   # inner surface
        s.line(px + 30, ys, px + 300, ys, stroke=INK2, sw=2)
        if px == 14:
            s.line(px + 30, yi, px + 300, yi, stroke=INK2, sw=2)
        else:
            s.line(px + 30, yi, px + 300, yi + 14, stroke=INK2, sw=2)
        s.text(px + 300, ys - 8, "outer surface", size=10.5, fill=INK2, anchor="end")
        s.text(px + 300, (yi + 14 if px != 14 else yi) + 16, "inner surface", size=10.5, fill=INK2, anchor="end")
        # eye plane
        s.line(px + 300, 66, px + 300, 196, stroke=MUTED, sw=1)
        s.text(px + 300, 216, "eye plane", size=10.5, fill=MUTED, anchor="end")
        # incident ray (black) and reflection off the outer surface (orange) to image 1
        P1 = (px + 140, ys)
        S = (px + 40, ys - 50)
        s.arrow(S[0], S[1], P1[0], P1[1], color=INK, sw=1.6)
        E1 = (px + 300, ys - 80)
        s.line(P1[0], P1[1], E1[0], E1[1], stroke=ORANGE, sw=2)
        if px == 14:
            P3 = (px + 176, yi)
            P4 = (px + 212, ys)
            E2 = (px + 300, ys - 44)
            s.line(P1[0], P1[1], P3[0], P3[1], stroke=BLUE, sw=2)
            s.line(P3[0], P3[1], P4[0], P4[1], stroke=BLUE, sw=2)
            s.line(P4[0], P4[1], E2[0], E2[1], stroke=BLUE, sw=2)
            s.circle(E1[0], E1[1], 5, fill=ORANGE)
            s.circle(E2[0], E2[1], 5, fill=BLUE)
            s.text(E1[0] - 10, E1[1] - 9, "image 1", size=11, weight=600, fill=ORANGE, anchor="end")
            s.text(E2[0] - 10, E2[1] + 16, "image 2", size=11, weight=600, fill=BLUE, anchor="end")
            s.text(px + 14, 232, "Parallel reflections land at two points:", size=11, fill=INK)
            s.text(px + 14, 248, "two images side by side.", size=11, fill=INK)
        else:
            P3 = (px + 200, yi + 14)
            P4 = (px + 223, ys)
            s.line(P1[0], P1[1], P3[0], P3[1], stroke=BLUE, sw=2)
            s.line(P3[0], P3[1], E1[0], E1[1], stroke=BLUE, sw=2)
            s.circle(E1[0], E1[1], 5, fill=ORANGE, stroke=SURF, sw=1.5)
            s.text(E1[0] - 10, E1[1] - 9, "images 1 and 2 overlap", size=11, weight=600, fill=INK, anchor="end")
            s.text(px + 14, 232, "The tilt sends image 2 to the same point,", size=11, fill=INK)
            s.text(px + 14, 248, "at the design eye height only.", size=11, fill=INK)
    s.text(W / 2, 20, "Schematic: refraction omitted, angles exaggerated. The wedge angle is set by the glass maker.", size=10, fill=MUTED, anchor="middle")
    return s

# ---------- Luminance budget (log axis, single series) ----------
@fig("luminance")
def f_luminance():
    import math as m
    W, H = 680, 356
    s = Svg(W, H, "Luminance at the eye for each source and path, log scale, with the day target and night ceiling")
    s.rect(0, 0, W, H, fill=SURF)
    X0, X1 = 330, 640      # 10 cd/m2 .. 100,000 cd/m2
    lx = lambda v: X0 + (m.log10(v) - 1) / 4 * (X1 - X0)
    rows = [
        ("YODOIT 16″ peak · combiner (30%)", LUM["yod_peak_comb"]),
        ("YODOIT 16″ peak · windshield (24%)", LUM["yod_peak_ws"]),
        ("YODOIT sustained · windshield (unverified)", LUM["yod_sust_ws"]),
        ("Laser DLP · combiner (30%)", LUM["dlp_comb"]),
        ("Laser DLP · windshield (24%)", LUM["dlp_ws"]),
        ("Laser DLP · windshield + 2 mirrors (90% each, assumed)", LUM["dlp_ws_mirr"]),
        (f"Laser DLP · + 2 mirrors + {V['pol_t']} polariser (assumed)", LUM["dlp_ws_mirr_pol"]),
    ]
    top = 60; rh = 36
    for dec in (10, 100, 1000, 10000, 100000):
        xx = lx(dec)
        s.line(xx, top - 14, xx, top + rh * len(rows) - 8, stroke=GRID, sw=1)
        s.text(xx, top + rh * len(rows) + 8, f"{dec:,}", size=11, fill=INK2, anchor="middle")
    s.text((X0 + X1) / 2, top + rh * len(rows) + 28, "cd/m² at the eye (log scale)", size=11.5, fill=INK, anchor="middle")
    for i, (name, v) in enumerate(rows):
        y = top + i * rh
        s.text(X0 - 14, y + 5, name, size=11, fill=INK, anchor="end")
        s.rect(X0, y - 8, lx(v) - X0, 16, fill=BLUE, rx=4)
        s.text(lx(v) + 8, y + 5, f"{v:,.0f}", size=11.5, fill=INK2)
    # thresholds: solid ink lines (never dashed)
    for val, label, anchor, dx in ((1500, "noon target 1,500", "start", 6), (50, "night ceiling 50", "end", -6)):
        xx = lx(val)
        s.line(xx, 30, xx, top + rh * len(rows) - 8, stroke=INK, sw=1.5)
        s.text(xx + dx, 24, label, size=11.5, weight=600, fill=INK, anchor=anchor)
    s.text(14, H - 10, "Bars start at 10 cd/m². Daylight target: 1,500 at the eye. Night ceiling: 50 at the eye.", size=10.5, fill=MUTED)
    return s

# ---------- Window geometry at 7.5 m (true scale, concentric) ----------
@fig("window")
def f_window():
    W, H = 680, 300
    s = Svg(W, H, "Demo window sizes at 7.5 metres, drawn to scale and centred")
    s.rect(0, 0, W, H, fill=SURF)
    k = 260.0                     # px per metre
    cx, cy = 340, 150
    opts = [(1.42, 0.71, GREY_T, AXIS, "10.8° × 5.4° · matches 2:1 PGU (single-mirror model)"),
            (1.31, 0.66, BLUE_T, BLUE, "10° × 5° · 2:1"),
            (1.31, 0.52, ORANGE_T, ORANGE, "10° × 4° · 2.5:1, needs cropping of the 2:1 PGU")]
    for w, h, fill, stroke, label in opts:
        s.rect(cx - w * k / 2, cy - h * k / 2, w * k, h * k, fill=fill, stroke=stroke, sw=1.5)
    s.text(cx, 282, "Sizes at 7.5 m. Outer to inner.", size=11, fill=MUTED, anchor="middle")
    # legend list at left
    yy = 52
    for w, h, fill, stroke, label in opts:
        s.rect(20, yy - 11, 14, 14, fill=fill, stroke=stroke, sw=1.5)
        s.text(42, yy + 1, label, size=11.5, fill=INK)
        yy += 26
    return s

# ---------- Stage 0 (bench beamsplitter) ----------
@fig("stage0")
def f_stage0():
    W, H = 680, 270
    s = Svg(W, H, "Stage 0 bench rig: monitor face-up, 70/30 beamsplitter at 45 degrees, eye on the far side")
    s.rect(0, 0, W, H, fill=SURF)
    bx, by = 290, 120
    # beamsplitter at 45 degrees
    s.line(bx - 62, by + 62, bx + 62, by - 62, stroke=BLUE, sw=3)
    s.text(bx + 70, by - 60, "70/30 beamsplitter", size=11.5, fill=INK)
    # monitor (face-up) under the beamsplitter
    s.rect(bx - 60, 224, 120, 14, fill=INK, rx=2)
    s.text(bx, 258, "monitor 1, face-up", size=11.5, fill=INK, anchor="middle")
    # monitor light: up to beamsplitter, then right to the eye
    s.arrow(bx, 222, bx, by, color=ORANGE, sw=2.4)
    s.line(bx, by, 600, by, stroke=ORANGE, sw=2.4)
    s.text(bx + 90, by - 12, "reflected monitor light (30%)", size=11, fill=INK, anchor="start")
    # road light through the beamsplitter
    s.line(40, by, bx, by, stroke=MUTED, sw=2)
    s.text(40, by - 12, "road light (70%)", size=11, fill=INK2)
    s.circle(616, by, 10, fill=INK)
    s.text(616, by - 18, "eye", size=11.5, fill=INK, anchor="middle")
    s.text(14, 26, "Virtual image distance equals the monitor's path length (about 0.6 m in the plan).", size=11, fill=INK2)
    s.text(14, 44, "Purpose: software bring-up, projection maths, colour, latency. Not a driving view.", size=11, fill=INK2)
    return s

# ---------- Stage 1 (Fresnel magnifier + combiner) ----------
@fig("stage1")
def f_stage1():
    W, H = 680, 300
    s = Svg(W, H, "Stage 1: monitor, Fresnel magnifier at 280 mm, combiner, eye; virtual image about 4 m away")
    s.rect(0, 0, W, H, fill=SURF)
    # virtual image (faint box at far left, not to scale)
    s.rect(24, 74, 120, 160, fill=BLUE_T, stroke=BLUE, sw=1.2, rx=4)
    s.text(84, 160, "virtual", size=12, weight=600, fill=INK, anchor="middle")
    s.text(84, 178, "image", size=12, weight=600, fill=INK, anchor="middle")
    s.text(84, 252, "1.2 × 0.6 m at ≈ 4.2 m", size=11, fill=INK2, anchor="middle")
    # monitor
    s.rect(220, 112, 16, 60, fill=INK, rx=2)
    s.text(228, 96, "monitor", size=11.5, fill=INK, anchor="middle")
    s.text(228, 186, "80 × 40 mm", size=10.5, fill=INK2, anchor="middle")
    # Fresnel lens
    lxp = 330
    s.line(lxp, 60, lxp, 230, stroke=BLUE, sw=2.6)
    s.text(lxp, 52, "Fresnel lens", size=11.5, fill=INK, anchor="middle")
    s.text(lxp, 244, "f = 300 mm", size=11.5, fill=INK, anchor="middle")
    # light: monitor -> lens (refracted, diverging) -> combiner -> eye
    s.line(236, 142, lxp, 142, stroke=ORANGE, sw=2)
    s.line(lxp, 142, 470, 142, stroke=ORANGE, sw=2)
    # combiner at 45 degrees and eye above it
    cxp, cyp = 470, 142
    s.line(cxp - 40, cyp + 40, cxp + 40, cyp - 40, stroke=BLUE, sw=2.6)
    s.text(cxp + 46, cyp + 52, "70/30 combiner", size=11.5, fill=INK)
    s.line(cxp, cyp, cxp, 62, stroke=ORANGE, sw=2)
    s.circle(cxp, 52, 9, fill=INK)
    s.text(cxp + 14, 56, "eye", size=11.5, fill=INK)
    # apparent direction through the lens to the virtual image
    s.line(cxp, 62, 144, 142, stroke=MUTED, sw=1)
    s.text(W - 14, H - 14, "Schematic. Monitor at 280 mm from the lens, inside the 300 mm focal length, gives a virtual image.", size=10.5, fill=MUTED, anchor="end")
    s.text(14, 26, f"1/v = 1/f − 1/u = 1/300 − 1/280 so v = −{V['s1_dist']} ;  magnification {V['s1_M']}", size=11.5, fill=INK, weight=600)
    return s

# ---------- Stage 2 (block diagram with the single-mirror numbers) ----------
@fig("stage2")
def f_stage2():
    W, H = 680, 262
    s = Svg(W, H, "Stage 2 light path: PGU, fold mirror, concave mirror, windshield, eye, with the single-mirror numbers")
    s.rect(0, 0, W, H, fill=SURF)
    blocks = [("PGU", "laser DLP on", "60 × 30 mm diffuser", ORANGE_T, ORANGE),
              ("Fold mirror", "folds the path", "into the dash", GREY_T, INK2),
              ("Concave mirror", f"f = {V['f2']}", f"PGU at {V['u2']}", ORANGE_T, ORANGE),
              ("Windshield", "wedge PVB, 24% s", "reflects toward eye", BLUE_T, BLUE),
              ("Eye", "eye box ≥ 120 × 60 mm", "", SURF, INK)]
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
        f"1/v = 1/f − 1/u with f = {V['f2']}, virtual image at 7.5 m  so  u = {V['u2']}",
        f"magnification {V['m2']};  image {V['img2_w']} × {V['img2_h']} at 7.5 m;  field {V['fov2_w']}° × {V['fov2_h']}°",
        f"The plan's earlier u = 346 mm puts a REAL image at {V['plan_v']}, not a virtual one.",
    ]
    for i, t in enumerate(lines):
        s.text(14, 182 + i * 18, t, size=11.2, fill=INK if i < 2 else "#d03b3b", weight=500 if i < 2 else 600)
    s.text(14, 250, "The windshield is in the light path but is not in this model. A ray trace must include it.", size=11, fill=INK2, weight=600)
    return s

# ---------- Sun focus hazard (block diagram) ----------
@fig("sunhazard")
def f_sunhazard():
    W, H = 680, 230
    s = Svg(W, H, "Sunlight entering the windshield, focused by the concave mirror near the PGU")
    s.rect(0, 0, W, H, fill=SURF)
    steps = [("Sun", "0.53° disk, ahead", GREY_T, INK2),
             ("Windshield", "transmits sunlight", BLUE_T, BLUE),
             ("Concave mirror", "focuses it", ORANGE_T, ORANGE),
             ("PGU plane", f"{V['u2']} from mirror", ORANGE_T, ORANGE)]
    bw, gap, y0, bh = 136, 30, 30, 70
    x = 14
    for i, (t, sub, fill, stroke) in enumerate(steps):
        s.rect(x, y0, bw, bh, fill=fill, stroke=stroke, sw=1.4, rx=6)
        s.text(x + bw / 2, y0 + 28, t, size=12, weight=700, fill=INK, anchor="middle")
        s.text(x + bw / 2, y0 + 50, sub, size=10.5, fill=INK2, anchor="middle")
        if i < len(steps) - 1:
            s.arrow(x + bw + 2, y0 + bh / 2, x + bw + gap - 2, y0 + bh / 2, color=INK, sw=1.8)
        x += bw + gap
    s.text(14, 134, "Focal point is 14 mm beyond the PGU, so the diffuser sits almost at the focus.", size=11.5, fill=INK, weight=600)
    s.text(14, 154, f"Ray trace, on-axis sun, no losses: 90% of rays land within {V['r90_pgu']} mm radius at the PGU plane,", size=11, fill=INK2)
    s.text(14, 170, f"about {V['conc_pgu']} times the sunlight intensity: roughly {V['sun_w']} into a spot about {V['sun_spot_mm']} mm across. The sun's 0.53° disk adds blur.", size=11, fill=INK2)
    s.text(14, 190, "Ideal geometry only, not a measurement. The sun must be tested with a thermocouple before any sun exposure.", size=11, fill=CRIT, weight=600)
    s.text(14, 210, "Plan's mitigations: IR filter before the diffuser (the plan's \"cold mirror\" should read hot mirror); dash lip shades the aperture.", size=11, fill=INK2)
    return s
