"""Figures for sections 5-8: what the eye sees, distortion and colour, groove orientation, artefacts."""
import math
import numpy as np
from svgkit import *
import optics as O
import teeth as TT
from calc import V, D, CROP_W, CROP_H, PITCH_55, PITCH_MON, HFW, HFH, _edge_angle

_clip_n = [0]
def clip_rect(s, x, y, w, h):
    _clip_n[0] += 1
    cid = f"clip{s.uid}_{_clip_n[0]}"
    s.add(f'<clipPath id="{cid}"><rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"/></clipPath>')
    return cid

@fig("eyebox")
def f_eyebox():
    W, H = 680, 700
    s = Svg(W, H, "Top view of the unfolded path: three eye positions, the rays to the image edges, and where the lens aperture cuts the view")
    s.rect(0, 0, W, H, fill=SURF)
    step(s, 16, 28, "A", "Top view, unfolded, to scale (0.55 px per mm): how far the head can move sideways")
    k = 0.55; cx = 250; zt = 120
    X = lambda x: cx + x * k
    Z = lambda z: zt + (O.EYE_Z - z) * k
    s.line(X(-O.HALF), Z(0), X(O.HALF), Z(0), stroke=TEAL, sw=4)
    s.text(X(-O.HALF) - 8, Z(0) + 4, "lens, 300 mm", size=11, fill=TEAL, weight=700, anchor="end")
    s.line(X(-40), Z(O.Z_PANEL), X(40), Z(O.Z_PANEL), stroke=INK, sw=4)
    s.text(X(40) + 8, Z(O.Z_PANEL) + 4, "panel crop, 80 mm wide", size=11, weight=700)
    ebx = D["eyebox"][0]
    s.rect(X(-ebx), Z(O.EYE_Z) - 5, 2 * ebx * k, 10, fill=GREEN_T, stroke=GREEN, sw=1)
    s.text(X(-ebx) - 8, Z(O.EYE_Z) + 4, f"eye box {V['eyebox_w']} mm", size=11, fill=GREEN, anchor="end", weight=700)
    eyes = ((0.0, INK, "centre", "end", -10), (0.98 * ebx, GREEN, "box edge", "middle", -24), (ebx + 60, CRIT, "outside", "start", -10))
    for e, col, lab, anc, dy in eyes:
        s.circle(X(e), Z(O.EYE_Z), 6, fill=col)
        tx = X(e) - 9 if anc == "end" else (X(e) + 9 if anc == "start" else X(e))
        s.text(tx, Z(O.EYE_Z) + dy, lab, size=11, fill=col, anchor=anc, weight=700)
        for tgt in (-CROP_W / 2, CROP_W / 2):
            a, b = _edge_angle(e, tgt, 0)
            hit = b["P1"][0, 0]
            if abs(hit) <= O.HALF:
                pts = [(X(e), Z(O.EYE_Z)), (X(hit), Z(0)), (X(b["P2"][0, 0]), Z(-O.T)), (X(b["P3"][0, 0]), Z(O.Z_PANEL))]
                polyline(s, pts, stroke=col, sw=1.4)
            else:
                s.line(X(e), Z(O.EYE_Z), X(hit), Z(0), stroke=col, sw=1.4, extra='stroke-dasharray="5 4"')
                s.text(X(hit), Z(0) + 6, "×", size=20, fill=CRIT, weight=700, anchor="middle")
                s.text(X(hit) + 14, Z(0) - 30, "misses the lens:", size=10.5, fill=CRIT)
                s.text(X(hit) + 14, Z(0) - 16, "right edge of the", size=10.5, fill=CRIT)
                s.text(X(hit) + 14, Z(0) - 2, "image disappears", size=10.5, fill=CRIT)
    s.text(16, Z(O.Z_PANEL) + 40, "Every eye position looks at the same virtual image from a slightly different angle, and the rays to the image's left and right", size=10.5, fill=INK2)
    s.text(16, Z(O.Z_PANEL) + 55, "edges land on the crop's edges. When the ray to an image edge would pass outside the lens, that part of the image disappears.", size=10.5, fill=INK2)
    s.text(16, Z(O.Z_PANEL) + 70, f"Traced eye box: {V['eyebox_w']} mm across and {V['eyebox_h']} mm up and down (the crop is only 40 mm tall), set by the 300 mm lens alone.", size=10.5, fill=INK, weight=700)
    return s

@fig("footprint")
def f_footprint():
    W, H = 680, 640
    s = Svg(W, H, "Why the grooves blur out: one image point is seen through a small patch of lens that covers several grooves, and the eye is focused far beyond them")
    s.rect(0, 0, W, H, fill=SURF)
    step(s, 16, 28, "A", "The light the eye uses for one image point")
    # side schematic: image point (left), lens, pupil (right). Not to scale in length; cone angles exaggerated.
    ay = 150
    xi, xl, xe = 60, 470, 640
    s.line(30, ay, W - 20, ay, stroke=AXIS, sw=1)
    s.circle(xi, ay, 5, fill=ORANGE)
    s.text(xi, ay - 14, "image point", size=11, fill=ORANGE, weight=700, anchor="middle")
    s.text(xi, ay + 26, f"{V['d_eye_img']} m from the eye", size=10.5, fill=INK2, anchor="middle")
    pr = 34
    fp = pr * (xl - xi) / (xe - xi)
    s.poly([(xi, ay), (xe, ay - pr), (xe, ay + pr)], fill=ORANGE_T, stroke="none")
    s.line(xi, ay, xe, ay - pr, stroke=ORANGE, sw=1, extra='stroke-dasharray="5 4"')
    s.line(xi, ay, xe, ay + pr, stroke=ORANGE, sw=1, extra='stroke-dasharray="5 4"')
    s.line(xl, ay - fp, xe, ay - pr, stroke=ORANGE, sw=1.6)
    s.line(xl, ay + fp, xe, ay + pr, stroke=ORANGE, sw=1.6)
    s.line(xl, ay - 70, xl, ay + 70, stroke=TEAL, sw=4)
    s.text(xl, ay - 78, "lens", size=11, fill=TEAL, weight=700, anchor="middle")
    s.rect(xl - 6, ay - fp, 12, 2 * fp, fill="none", stroke=CRIT, sw=2)
    s.text(xl - 12, ay + fp + 18, f"footprint {V['fp_4']} mm", size=10.5, fill=CRIT, anchor="end", weight=700)
    s.line(xe, ay - pr, xe, ay + pr, stroke=INK, sw=4)
    s.text(xe - 4, ay + pr + 18, "pupil 4 mm", size=10.5, anchor="middle", weight=700)
    s.text(16, ay + 82, f"The rays that reach a {4} mm pupil from one image point cross the lens in a patch {V['fp_4']} mm wide ({V['fp_6']} mm for a 6 mm night pupil):", size=10.5, fill=INK2)
    s.text(16, ay + 97, f"pupil × image distance ÷ (image distance + eye distance) = 4 × 4.2 ÷ 4.9. Lengths not to scale.", size=10.5, fill=INK2)
    # ---------- B: the footprint on the teeth ----------
    y0 = 290
    step(s, 16, y0, "B", f"That patch on the real teeth near r = 90 mm, magnified 120×: {V['fp_g_4']} grooves share the work")
    kk = 120.0; r0 = 90.0
    ra, rb = r0 - 2.3, r0 + 2.3
    X = lambda q: 70 + (q - ra) * kk
    base = y0 + 240
    Z = lambda z: base - z * kk
    from figs_a import tooth_poly
    s.poly(tooth_poly(ra, rb, X, Z, base + 60), fill=ACRYLIC, stroke=ACRYLIC_S, sw=1)
    fpw = float(V["fp_4"])
    # rays of the bundle: parallel-ish lines arriving from the eye side, slightly converging (eye side) - draw 9
    for i, q in enumerate(np.linspace(r0 - fpw / 2, r0 + fpw / 2, 13)):
        s.line(X(q) - 18, Z(1.0) - 70, X(q), Z(float(TT.sag(q) - TT.sag((math.floor(q / O.PITCH) + 1) * O.PITCH))), stroke=ORANGE, sw=1.1)
    dim(s, X(r0 - fpw / 2), Z(1.0) - 84, X(r0 + fpw / 2), Z(1.0) - 84, f"{V['fp_4']} mm = {V['fp_g_4']} grooves at {V['pitch']} mm", off=0, size=10.5, color=CRIT)
    s.text(70, base + 80, "Each groove sends its own sliver of the same image point; the eye adds them up. No single groove decides the pixel.", size=10.5, fill=INK2)
    return s

@fig("grooveblur")
def f_grooveblur():
    W, H = 680, 420
    s = Svg(W, H, "Brightness across the lens as a pinhole camera and as the eye see it: the groove pattern almost disappears in the eye's blur")
    s.rect(0, 0, W, H, fill=SURF)
    s.text(16, 26, "The eye focuses on the image, 4.9 m away, not on the lens 0.7 m away", size=13, weight=700)
    ax = Axes(s, 80, 46, 520, 220, (-2.5, 2.5), (0, 1.05))
    ax.frame([-2, -1, 0, 1, 2], [0, 0.2, 0.4, 0.6, 0.8, 1.0], xfmt="{:+.0f}", yfmt="{:.1f}",
             xlabel="position across the lens near r = 90 mm (mm)", ylabel="brightness of a white image")
    frac = 1 - [q for q in D["eye_stats"] if q[0] == 90][0][2]
    xs = np.linspace(-8.0, 8.0, 6401)
    ph = (xs / O.PITCH) % 1.0
    T = np.where(ph > 1 - frac, 0.0, 1.0)
    vis = (xs >= -2.5) & (xs <= 2.5)
    ax.curve(list(zip(xs[vis], T[vis])), stroke=MUTED, sw=1.2)
    d = float(V["fp_4"]); dx = xs[1] - xs[0]
    kx = np.arange(-d / 2, d / 2 + dx, dx); kern = np.sqrt(np.clip(1 - (2 * kx / d) ** 2, 0, None)); kern /= kern.sum()
    Tb = np.convolve(T, kern, mode="same")
    ax.curve(list(zip(xs[vis], Tb[vis])), stroke=ORANGE, sw=3)
    legend(s, 90, 318, [(f"pinhole camera at the eye point: a dark gap wherever the sight line hits a draft wall ({frac*100:.0f}% of each groove)", MUTED),
                        (f"the eye, focused at 4.9 m with a 4 mm pupil: an even {(1-frac)*100:.0f}%, ripple under {V['mtf4_05']}", ORANGE)], size=10.5)
    s.text(16, H - 30, f"Grooves are {V['groove_arcmin']}′ apart as seen from the eye but {V['defocus_D']} D out of focus, so each is smeared over about {V['blur_arcmin_4']}′.", size=10.8, weight=700)
    s.text(16, H - 13, "The pattern averages out to a slight, even dimming. What survives is anything that is not periodic (Figure [[N stray]] and the renders).", size=10.5, fill=INK2)
    return s

@fig("pitch")
def f_pitch():
    W, H = 680, 560
    s = Svg(W, H, "Choosing a groove pitch: diffraction blur grows as the pitch shrinks, flat-facet blur grows with it, and the visible groove pattern fades")
    s.rect(0, 0, W, H, fill=SURF)
    s.text(16, 26, "Finer grooves diffract more; coarser flat facets smear more; the groove pattern itself hardly shows", size=13, weight=700)
    ax = Axes(s, 80, 50, 500, 330, (0.1, 1.5), (0, 16))
    ax.frame([0.1, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5], [0, 2, 4, 6, 8, 10, 12, 14, 16], xfmt="{:g}",
             xlabel="groove pitch (mm)", ylabel="blur width (arcminutes)")
    pt = D["pitch_trade"]
    ax.clip_curve([(p, d) for p, d, m4, m6 in pt], stroke=BLUE, sw=2.8)
    ax.clip_curve(D["pitch_flat"], stroke=PURPLE, sw=2.6, extra='stroke-dasharray="7 4"')
    ry = lambda v: ax.y + ax.h - v / 10.0 * ax.h
    fp4 = float(V["fp_4"])
    env = lambda p: min(1.0, 2 * math.sqrt(2 / math.pi) * (math.pi * fp4 / p) ** -1.5)
    polyline(s, [(ax.X(p), ry(env(p) * 100)) for p, d, m4, m6 in pt], stroke=ORANGE, sw=2.2)
    for v in (0, 2, 4, 6, 8, 10):
        s.text(ax.x + ax.w + 6, ry(v) + 4, f"{v}%", size=11, fill=ORANGE)
    cx, cy = ax.x + ax.w + 44, ax.y + ax.h / 2
    s.text(cx, cy, "groove pattern left after the eye's blur", size=11, fill=ORANGE, anchor="middle", extra=f'transform="rotate(90 {cx} {cy})"')
    for yv, lab, dy in ((float(V["arcmin_px_55"]), "one 5.5-inch pixel", 12), (1.0, "one 4K-monitor pixel ≈ the eye's limit", -5)):
        s.line(ax.x, ax.Y(yv), ax.x + ax.w, ax.Y(yv), stroke=MUTED, sw=1, extra='stroke-dasharray="3 3"')
        s.text(ax.x + ax.w - 6, ax.Y(yv) + dy, lab, size=10, fill=INK2, anchor="end")
    s.line(ax.X(0.5), ax.y, ax.X(0.5), ax.y + ax.h, stroke=INK, sw=1.2)
    s.text(ax.X(0.5) + 6, ax.y + 16, f"Knight LFQ300300: {V['pitch']} mm", size=10.5, weight=700)
    s.circle(ax.X(0.5), ax.Y(float(V["diff_05"])), 4.5, fill=BLUE)
    s.text(ax.X(0.5) - 8, ax.Y(float(V["diff_05"])) + 16, f"{V['diff_05']}′", size=11, weight=700, fill=BLUE, anchor="end")
    s.circle(ax.X(0.5), ax.Y(float(V["flat_blur"])), 4.5, fill=PURPLE)
    s.text(ax.X(0.5) + 8, ax.Y(float(V["flat_blur"])) - 6, f"{V['flat_blur']}′", size=11, weight=700, fill=PURPLE)
    legend(s, ax.x + 66, ax.y + 18, [("diffraction across the grooves", BLUE), ("flat (conical) facets: image steps", PURPLE),
                                       ("groove pattern left, 4 mm pupil (right scale, worst case)", ORANGE)], size=10.5)
    s.text(16, H - 70, f"Diffraction: each groove is a {V['pitch']} mm slit and spreads light by about λ ÷ pitch: {V['diff_05']}′ at 0.5 mm, {V['diff_1']}′ at 1 mm, {V['diff_025']}′ at 0.25 mm.", size=10.5, fill=INK2)
    s.text(16, H - 54, f"Flat facets: if each tooth is cut straight instead of curved, the image steps by about pitch ÷ focal length per groove ({V['flat_blur']}′ traced).", size=10.5, fill=INK2)
    s.text(16, H - 38, f"Both act across the grooves only. With flat facets the best pitch is about {V['p_best_flat']} mm ({V['blur_best_flat']}′); with curved facets coarser is better.", size=10.5, fill=INK2)
    s.text(16, H - 20, "For HUD graphics a few pixels wide, 0.5 mm is a sensible choice either way. Ask the supplier whether the facets are curved.", size=10.5, fill=INK, weight=700)
    return s

def _forward_seen(px, py, iters=8):
    """Field angles at which the centred eye sees panel points (px, py): Newton on the backward trace."""
    K = D["dist"]["K"]
    ax = np.degrees(np.arctan(px / K)); ay = np.degrees(np.arctan(py / K))
    for _ in range(iters):
        b = O.panel_point(ax, ay)
        ex = b["P3"][:, 0] - px; ey = b["P3"][:, 1] - py
        h = 1e-3
        bx = O.panel_point(ax + h, ay); by = O.panel_point(ax, ay + h)
        j11 = (bx["P3"][:, 0] - b["P3"][:, 0]) / h; j21 = (bx["P3"][:, 1] - b["P3"][:, 1]) / h
        j12 = (by["P3"][:, 0] - b["P3"][:, 0]) / h; j22 = (by["P3"][:, 1] - b["P3"][:, 1]) / h
        det = j11 * j22 - j12 * j21
        ax = ax - (j22 * ex - j12 * ey) / det
        ay = ay - (-j21 * ex + j11 * ey) / det
    return ax, ay

@fig("distortion")
def f_distortion():
    W, H = 680, 810
    s = Svg(W, H, "Pincushion distortion of the magnifier and the barrel-shaped pre-distortion the renderer draws to cancel it, exaggerated four times")
    s.rect(0, 0, W, H, fill=SURF)
    EX = 4.0
    K = D["dist"]["K"]
    def draw_grid(x0, y0, sc, pts_fn, ideal_fn, title, sub, col):
        nx, ny = 13, 7
        gx = np.linspace(-1, 1, nx); gy = np.linspace(-1, 1, ny)
        GX, GY = np.meshgrid(gx, gy)
        ix, iy = ideal_fn(GX, GY)
        ax_, ay_ = pts_fn(GX, GY)
        dx = ix + EX * (ax_ - ix); dy = iy + EX * (ay_ - iy)
        P = lambda x, y: (x0 + x * sc, y0 - y * sc)
        s.poly([P(ix[0, 0], iy[0, 0]), P(ix[0, -1], iy[0, -1]), P(ix[-1, -1], iy[-1, -1]), P(ix[-1, 0], iy[-1, 0])], fill="none", stroke=MUTED, sw=1.2, extra='stroke-dasharray="5 4"')
        for i in range(ny):
            polyline(s, [P(dx[i, j], dy[i, j]) for j in range(nx)], stroke=col, sw=1.3)
        for j in range(nx):
            polyline(s, [P(dx[i, j], dy[i, j]) for i in range(ny)], stroke=col, sw=1.3)
    step(s, 16, 28, "A", "If the panel shows a straight grid, the eye sees it bowed outward (pincushion)")
    s.text(40, 48, "Eye's view, degrees. Dashed: a perfect rectangle. Bending exaggerated 4×; true values below.", size=10.5, fill=INK2)
    hw, hh = CROP_W / 2, CROP_H / 2
    def seen(GX, GY):
        a, b = _forward_seen((GX * hw).ravel(), (GY * hh).ravel())
        return a.reshape(GX.shape), b.reshape(GX.shape)
    def ideal_seen(GX, GY):
        return np.degrees(np.arctan(GX * hw / K)), np.degrees(np.arctan(GY * hh / K))
    draw_grid(340, 220, 36.0, seen, ideal_seen, "", "", ORANGE)
    a_c, b_c = _forward_seen(np.array([hw]), np.array([hh]))
    ia, ib = ideal_seen(np.array([1.0]), np.array([1.0]))
    s.text(340, 380, f"Corner of the 80 × 40 mm crop: seen at {a_c[0]:.2f}° × {b_c[0]:.2f}° instead of {ia[0]:.2f}° × {ib[0]:.2f}°; that is {math.hypot(a_c[0], b_c[0]) - math.hypot(ia[0], ib[0]):.2f}° further out.", size=10.5, fill=INK2, anchor="middle")
    y0 = 420
    s.line(14, y0 - 20, W - 14, y0 - 20, stroke=GRID, sw=1)
    step(s, 16, y0, "B", "So the renderer draws the grid pulled inward (barrel) and the eye sees it straight")
    s.text(40, y0 + 20, "Panel, mm. Dashed: the crop. Each grid point is where the traced ray from that direction lands. Exaggerated 4×.", size=10.5, fill=INK2)
    def drawn(GX, GY):
        a = np.degrees(np.arctan(GX * hw / K)); b = np.degrees(np.arctan(GY * hh / K))
        bb = O.panel_point(a.ravel(), b.ravel())
        return bb["P3"][:, 0].reshape(GX.shape), bb["P3"][:, 1].reshape(GX.shape)
    def ideal_panel(GX, GY):
        return GX * hw, GY * hh
    draw_grid(340, y0 + 165, 6.2, drawn, ideal_panel, "", "", BLUE)
    s.text(340, y0 + 310, f"Corner: drawn {V['dist_corner_mm'].replace('-', '')} mm closer to the centre ({V['dist_corner'].replace('-', '')}% of its radius); mid-edge {V['dist_edge'].replace('-', '')}%.", size=10.5, fill=INK2, anchor="middle")
    s.text(16, H - 46, "This is the plan's pre-distortion mesh. The calibration photograph measures it directly, so the numbers here are a check, not an input.", size=10.5, fill=INK2)
    s.text(16, H - 29, "The mesh is exact for one eye position; within the eye box the distortion changes a little, which the head tracker can follow", size=10.5, fill=INK2)
    s.text(16, H - 13, "with a set of meshes measured at several eye points.", size=10.5, fill=INK2)
    return s

@fig("latcolour")
def f_latcolour():
    W, H = 680, 820
    s = Svg(W, H, "Lateral colour: red, green and blue leave the lens at slightly different angles, more so toward the field edge; PMMA, glass and polycarbonate compared")
    s.rect(0, 0, W, H, fill=SURF)
    step(s, 16, 28, "A", "Why colours split: the plastic bends blue light more than red")
    bx, by = 200, 190
    s.poly([(60, by + 80), (60, by + 10), (bx - 90, by + 10), (bx - 90, by - 55), (bx + 130, by + 12), (350, by + 10), (350, by + 80)], fill=ACRYLIC, stroke=ACRYLIC_S, sw=1.2)
    hx, hy = bx, by - 12
    s.line(hx - 30, by + 95, hx, hy, stroke=INK, sw=2.4)
    s.text(hx - 30, by + 110, "white light from the panel", size=10.5, anchor="middle", weight=600)
    for ang, col, lab, n, ly in ((-10, RGB[0], "red 620 nm", V["n_r"], 70), (0, RGB[1], "green 530 nm", V["n_g"], 56), (10, RGB[2], "blue 450 nm", V["n_b"], 42)):
        a = math.radians(-6 + ang)
        ex, ey = hx - 125 * math.sin(a), hy - 125 * math.cos(a)
        s.line(hx, hy, ex, ey, stroke=col, sw=2.4)
    s.text(hx - 50, 64, "blue, n = " + V["n_b"], size=10.5, fill=RGB[2], weight=700, anchor="end")
    s.text(hx + 4, 52, "green, " + V["n_g"], size=10.5, fill=RGB[1], weight=700, anchor="middle")
    s.text(hx + 58, 64, "red, " + V["n_r"], size=10.5, fill=RGB[0], weight=700)
    s.text(380, 120, "The fan is drawn 25× wider than it is.", size=10.5, fill=INK2)
    s.text(380, 136, f"PMMA's refractive index is {V['n_b']} for blue", size=10.5, fill=INK2)
    s.text(380, 152, f"and {V['n_r']} for red, so blue is bent", size=10.5, fill=INK2)
    s.text(380, 168, "about 2% more at every surface.", size=10.5, fill=INK2)
    s.text(380, 192, "The split grows with how hard the lens", size=10.5, fill=INK2)
    s.text(380, 208, "bends the light at that spot, which grows", size=10.5, fill=INK2)
    s.text(380, 224, "with distance from its centre.", size=10.5, fill=INK2)
    s.text(380, 248, f"Abbe number (higher = less colour):", size=10.5, fill=INK, weight=700)
    s.text(380, 264, f"PMMA {V['abbe_pmma']}, BK7 glass {V['abbe_bk7']}, polycarbonate {V['abbe_pc']}", size=10.5, fill=INK2)
    # ---------- B: chart ----------
    y0 = 330
    step(s, 16, y0, "B", "Blue-to-red spread across the field, seen from the eye")
    ax = Axes(s, 80, y0 + 24, 470, 260, (0, 8), (0, 0.8))
    ax.frame([0, 1, 2, 3, 4, 5, 6, 7, 8], [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8], yfmt="{:.1f}",
             xlabel="field angle from the centre (degrees)", ylabel="blue-to-red spread (degrees)")
    ax.curve([(a, abs(sp)) for a, sp, sg, xs in D["lat_col"]], stroke=TEAL, sw=3)
    mat = D["lc_mat"]
    ax.curve(mat["BK7 glass"], stroke=MUTED, sw=2, extra='stroke-dasharray="6 4"')
    ax.curve(mat["Polycarbonate"], stroke=CRIT, sw=2, extra='stroke-dasharray="6 4"')
    # eye 50 mm off-centre (PMMA, paraxial): chief ray height h = 50 + 700 tan a
    nb, ng, nr = float(V["n_b"]), float(V["n_g"]), float(V["n_r"])
    off = [(a, math.degrees((50 + O.EYE_Z * math.tan(math.radians(a))) / O.F * (nb - nr) / (ng - 1))) for a in np.linspace(0, HFW, 15)]
    ax.curve(off, stroke=PURPLE, sw=2, extra='stroke-dasharray="2 3"')
    px = lambda deg_: deg_ * CROP_W / PITCH_55 / (2 * HFW)
    for v in (0, 10, 20, 30, 40, 50, 60):
        dv = v / (CROP_W / PITCH_55 / (2 * HFW))
        if dv <= 0.8:
            s.text(ax.x + ax.w + 6, ax.Y(dv) + 4, f"{v}", size=11, fill=INK2)
    cx, cy = ax.x + ax.w + 40, ax.y + ax.h / 2
    s.text(cx, cy, "5.5-inch panel pixels", size=11, fill=INK2, anchor="middle", extra=f'transform="rotate(90 {cx} {cy})"')
    s.line(ax.X(HFW), ax.y, ax.X(HFW), ax.y + ax.h, stroke=INK2, sw=1, extra='stroke-dasharray="3 3"')
    s.text(ax.X(HFW) - 4, ax.y + 14, "field edge", size=10, fill=INK2, anchor="end")
    legend(s, ax.x + 14, ax.y + 18, [("PMMA, traced (this lens)", TEAL), ("PMMA, eye 50 mm off-centre", PURPLE), ("BK7 glass, same lens shape", MUTED), ("polycarbonate", CRIT)], size=10.5)
    s.text(ax.X(HFW) - 6, ax.Y(float(V["lc_edge"])) - 10, f"{V['lc_edge']}° = {V['lc_edge_px']} px", size=11, weight=700, fill=TEAL, anchor="end")
    # ---------- C: what to do ----------
    y1 = y0 + 350
    step(s, 16, y1, "C", "What it looks like, and the fix")
    rows = [f"A thin white line near the field edge spreads into a {V['lc_edge_arcmin']}′ rainbow: red on the inside, blue on the outside.",
            "Green-only graphics barely show it (one primary); white text and mixed colours do.",
            "Fix: draw red, green and blue through slightly different pre-distortion meshes (VR headsets do this for their Fresnel lenses).",
            "The split depends on where the light crosses the lens, so it moves with the head: with the eye 50 mm off-centre the centre",
            "of the field already splits by 0.2°. The per-colour mesh should follow the head tracker, like the geometric one."]
    for i, t in enumerate(rows):
        s.text(16, y1 + 24 + i * 17, t, size=10.5, fill=INK2 if i else INK, weight=700 if i == 0 else 400)
    return s

def _draw_fan(s, x0, y0, w, h, r0, flipped, kk):
    """Tooth-level fan around r0 in a box, isotropic scale kk px/mm; returns (clean, other)."""
    L, rays = TT.fan(r0, flipped=flipped, width=2.4, nrays=29)
    ideal = TT.ideal_exit_dir(r0, flipped)
    cid = clip_rect(s, x0, y0, w, h)
    ra = r0 - (w / kk) / 2
    X = lambda q: x0 + (q - ra) * kk
    Z = lambda z: y0 + h * 0.58 - (z + O.T / 2) * kk
    s.rect(x0, y0, w, h, fill="#ffffff", stroke=AXIS, sw=1, rx=4)
    s.add(f'<g clip-path="url(#{cid})">')
    s.poly([(X(p[0]), Z(p[1])) for p in L.poly], fill=ACRYLIC, stroke=ACRYLIC_S, sw=1)
    good = bad = 0
    for ry in rays:
        walls = any(k == "wall" for _, k in ry["events"]); tirs = any(t == "tir" for t, _ in ry["events"])
        ok = (not walls) and (not tirs) and abs(ry["ang"] - ideal) < 0.5
        good += ok; bad += (not ok)
        polyline(s, [(X(p[0]), Z(p[1])) for p in ry["path"]], stroke=ORANGE if ok else CRIT, sw=1.1 if ok else 1.5)
    s.add("</g>")
    return good, bad

@fig("orient")
def f_orient():
    W, H = 680, 800
    s = Svg(W, H, "Which way the grooves face: real teeth traced at r = 150 mm in both orientations, same scale across and in depth")
    s.rect(0, 0, W, H, fill=SURF)
    step(s, 16, 28, "A", "Grooves toward the eye (correct): rays from the panel's centre at r = 150 mm, 80× true size")
    g1, b1 = _draw_fan(s, 16, 42, 648, 330, 150.0, False, 80.0)
    s.text(30, 62, "eye side (top)", size=10.5, fill=INK2, weight=700)
    s.text(30, 362, "panel side (bottom)", size=10.5, fill=INK2, weight=700)
    s.text(650, 62, f"orange: clean ({g1} of {g1+b1}); red: hits a draft wall", size=10.5, fill=INK2, anchor="end")
    step(s, 16, 410, "B", "Grooves toward the panel (flipped): the same lens and the same rays")
    g2, b2 = _draw_fan(s, 16, 424, 648, 330, 150.0, True, 80.0)
    s.text(30, 444, "eye side (top)", size=10.5, fill=INK2, weight=700)
    s.text(30, 744, "panel side (bottom)", size=10.5, fill=INK2, weight=700)
    s.text(650, 444, f"orange: clean ({g2} of {g2+b2}); red: hits a draft wall or is trapped", size=10.5, fill=INK2, anchor="end")
    s.text(16, H - 14, "Flipped, the facets must do all the bending at grazing angles; much of the light strikes the draft walls and is guided sideways in the sheet.", size=10.5, fill=INK2)
    return s

@fig("orientchart")
def f_orientchart():
    W, H = 680, 330
    s = Svg(W, H, "Share of the light from the panel's centre that passes cleanly, against radius, for both groove orientations")
    s.rect(0, 0, W, H, fill=SURF)
    ax = Axes(s, 80, 20, 520, 240, (0, 210), (0, 100))
    ax.frame([0, 25, 50, 75, 100, 125, 150, 175, 200], [0, 25, 50, 75, 100], xlabel="radius on the lens (mm)", ylabel="passes cleanly (%)")
    for fl, col in ((False, TEAL), (True, CRIT)):
        ax.curve([(r, g * 100) for r, g, st, t, l in D["fwd_survey"][fl]], stroke=col, sw=2.8)
    s.line(ax.X(90), ax.y, ax.X(90), ax.y + ax.h, stroke=INK2, sw=1, extra='stroke-dasharray="3 3"')
    s.text(ax.X(90) + 5, ax.y + 16, "the centred eye looks through r < 90 mm", size=10.5, fill=INK2)
    s.line(ax.X(150), ax.y, ax.X(150), ax.y + ax.h, stroke=INK2, sw=1, extra='stroke-dasharray="3 3"')
    s.text(ax.X(150) + 5, ax.y + 34, "lens edge", size=10.5, fill=INK2)
    legend(s, ax.x + 14, ax.y + ax.h - 40, [("grooves toward the eye", TEAL), ("grooves toward the panel", CRIT)], size=11)
    return s

@fig("stray")
def f_stray():
    W, H = 680, 800
    s = Svg(W, H, "Looking from the eye into the grooves: most sight lines pass a facet cleanly, some strike a draft wall and end up somewhere else")
    s.rect(0, 0, W, H, fill=SURF)
    step(s, 16, 28, "A", "Sight lines from the eye into the grooves at r = 90 mm (the field edge), real teeth")
    L, rays = TT.eye_fan(90.0, width=1.6, nrays=33)
    x0, y0, w, h = 16, 44, 648, 290
    kk = 260.0
    cid = clip_rect(s, x0, y0, w, h)
    ra = 90.0 - (w / kk) / 2
    X = lambda q: x0 + (q - ra) * kk
    Z = lambda z: y0 + 120 - z * kk
    s.rect(x0, y0, w, h, fill="#ffffff", stroke=AXIS, sw=1, rx=4)
    s.add(f'<g clip-path="url(#{cid})">')
    s.poly([(X(p[0]), Z(p[1])) for p in L.poly], fill=ACRYLIC, stroke=ACRYLIC_S, sw=1.2)
    for ry in rays:
        col = CRIT if ry["walls"] else ORANGE
        polyline(s, [(X(p[0]), Z(p[1])) for p in ry["path"]], stroke=col, sw=1.6 if ry["walls"] else 1.0)
    s.add("</g>")
    s.text(x0 + 10, y0 + 18, "eye side (light arrives here on its way to the eye)", size=10.5, fill=INK2)
    s.text(x0 + 10, y0 + h - 10, "flat face, then 279 mm on to the panel", size=10.5, fill=INK2)
    s.text(x0 + w - 10, y0 + 18, "orange: through a facet to the intended pixel", size=10.5, fill=ORANGE, anchor="end", weight=700)
    s.text(x0 + w - 10, y0 + 34, "red: strikes a draft wall, ends up elsewhere", size=10.5, fill=CRIT, anchor="end", weight=700)
    # ---------- B: chart ----------
    yb = y0 + h + 40
    step(s, 16, yb, "B", "What the eye's sight lines meet, across the field")
    ax = Axes(s, 80, yb + 22, 420, 220, (0, 10.5), (0, 100))
    ax.frame([0, 2, 4, 6, 8, 10], [0, 20, 40, 60, 80, 100], xlabel="angle from the centre of the view (degrees)", ylabel="share of sight lines (%)")
    st = D["eye_stats"]
    ax.curve([(a, cl * 100) for r, a, cl, far, lost, x in st], stroke=ORANGE, sw=2.6)
    ax.curve([(a, far * 100) for r, a, cl, far, lost, x in st], stroke=CRIT, sw=2.2)
    ax.curve([(a, lost * 100) for r, a, cl, far, lost, x in st], stroke=PURPLE, sw=2.2, extra='stroke-dasharray="5 3"')
    s.line(ax.X(HFW), ax.y, ax.X(HFW), ax.y + ax.h, stroke=INK2, sw=1, extra='stroke-dasharray="3 3"')
    s.text(ax.X(HFW) - 4, ax.y + 120, "field edge", size=10, fill=INK2, anchor="end")
    legend(s, ax.x + ax.w + 14, ax.y + 16, [("clean: the intended pixel", ORANGE), ("a pixel far away", CRIT), ("trapped in the sheet", PURPLE)], size=10.5, dy=20)
    s.text(ax.x + ax.w + 14, ax.y + 90, f"at the field edge:", size=10.5, fill=INK2, weight=700)
    s.text(ax.x + ax.w + 14, ax.y + 106, f"{V['eyeclean_90']} clean,", size=10.5, fill=INK2)
    s.text(ax.x + ax.w + 14, ax.y + 121, f"{V['eyefar_90']} from far away,", size=10.5, fill=INK2)
    s.text(ax.x + ax.w + 14, ax.y + 136, f"{V['eyelost_90']} trapped", size=10.5, fill=INK2)
    yc = yb + 300
    rows = [("Dimming toward the edge.", f"The wall zones repeat every {V['pitch']} mm, so the eye's blur turns them into an even loss: about {100 - float(V['eyeclean_90'].rstrip('%')):.0f}% darker at"),
            ("", "the field edge than at the centre. It does not depend on the pitch: finer grooves are shallower by the same factor."),
            ("Ghosts and rays.", "The 'far away' light comes from a panel spot well outside the crop. If that spot is lit (a bright graphic, the stock"),
            ("", "backlight, sunlight on the panel), the eye sees a faint smear arranged around the lens centre: rings and radial streaks."),
            ("At night", "this is the visible part: a dim glow or streak next to bright symbols on black. Keep the panel black outside the graphics,"),
            ("", "light only the crop, and make every surface the stray light can reach matte black. Dust in the grooves scatters the same way.")]
    for i, (a, b) in enumerate(rows):
        yy = yc + i * 17
        if a:
            s.text(16, yy, a, size=10.5, weight=700)
        s.text(16 + (len(a) * 5.6 + 8 if a else 0), yy, b, size=10.5, fill=INK2)
    return s
