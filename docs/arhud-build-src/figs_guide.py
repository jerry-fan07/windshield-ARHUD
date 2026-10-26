"""The build guide's own figures. Plain inline SVG through the plan's svgkit; text inherits Helvetica Neue.
Colour appears only in figures. Hues carry one meaning each, and every coloured element is also labelled:
  LIGHT (image light, rays)  orange      DATA (USB, HDMI, Ethernet)  blue
  POWER                      red         SUN and heat                gold
  EYE and head tracking      purple      structure                   greys
Geometry figures marked "to scale" read docs/arhud-cad/layout.json (the layout the CAD housing was built around)."""
import json, math, os
from svgkit import Svg, fig, INK, INK2, MUTED, GRID, AXIS, SURF, GREY_T, BLUE, BLUE_T, ORANGE, ORANGE_T

HERE = os.path.dirname(os.path.abspath(__file__))
LAY = json.load(open(os.path.join(os.path.dirname(HERE), "arhud-cad", "layout.json")))

LIGHT, LIGHT_T = ORANGE, ORANGE_T
DATA, DATA_T = BLUE, BLUE_T
POWER, POWER_T = "#c0392b", "#f8e6e4"
SUN, SUN_T = "#b8860b", "#f7efd9"
EYEC, EYE_T = "#7a4fbf", "#efe8f8"
GLASS = "#7d9db5"
STEEL = "#a9a8a3"
DARK = "#3a3a38"


def note(s, x, y, text, size=10.5, fill=INK2, anchor="start", weight=400):
    s.text(x, y, text, size=size, fill=fill, anchor=anchor, weight=weight)


def leader(s, x1, y1, x2, y2):
    s.line(x1, y1, x2, y2, stroke=INK2, sw=0.8)
    s.circle(x2, y2, 1.8, fill=INK2)


def box(s, x, y, w, h, title, lines=(), fill=SURF, stroke=INK2, tsize=11, lsize=9.5, tcol=INK, sw=1):
    s.rect(x, y, w, h, fill=fill, stroke=stroke, sw=sw, rx=4)
    s.text(x + w / 2, y + 16, title, size=tsize, weight=650, fill=tcol, anchor="middle")
    for i, ln in enumerate(lines):
        s.text(x + w / 2, y + 31 + i * 12.5, ln, size=lsize, fill=INK2, anchor="middle")


def dim_h(s, x1, x2, y, label, size=9.5, tick=4):
    s.line(x1, y, x2, y, stroke=INK2, sw=0.8)
    s.line(x1, y - tick, x1, y + tick, stroke=INK2, sw=0.8)
    s.line(x2, y - tick, x2, y + tick, stroke=INK2, sw=0.8)
    s.text((x1 + x2) / 2, y - 4, label, size=size, fill=INK2, anchor="middle")


def dim_v(s, x, y1, y2, label, size=9.5, tick=4, side="right"):
    s.line(x, y1, x, y2, stroke=INK2, sw=0.8)
    s.line(x - tick, y1, x + tick, y1, stroke=INK2, sw=0.8)
    s.line(x - tick, y2, x + tick, y2, stroke=INK2, sw=0.8)
    if side == "right":
        s.text(x + 6, (y1 + y2) / 2 + 3, label, size=size, fill=INK2)
    else:
        s.text(x - 6, (y1 + y2) / 2 + 3, label, size=size, fill=INK2, anchor="end")


def polyline(s, pts, stroke, sw=1.2, extra=""):
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    s.path(d, stroke=stroke, sw=sw, extra=extra)


# =====================================================================================================
@fig("g_overview")
def g_overview():
    """Schematic side view of the installed system (cabin roughly to scale, the road ahead compressed)."""
    W, H = 680, 380
    s = Svg(W, H, "Side view of the installed HUD: cameras, computer, optics and the virtual image ahead")
    s.rect(0, 0, W, H, fill=SURF)
    k = 150.0
    P = lambda x, y: (170 + x * k, 335 - y * k)
    s.line(10, 335, W - 10, 335, stroke=INK2, sw=1.2)
    note(s, W - 14, 350, "road", anchor="end")
    for bx in (520, 528):
        s.line(bx, 327, bx + 6, 343, stroke=INK2, sw=1)
    note(s, 524, 362, "distance compressed", size=9, anchor="middle")
    # body: roof, windshield, bonnet, dash, firewall, floor
    polyline(s, [P(-0.95, 1.42), P(0.314, 1.385)], STEEL, 2.4)
    s.line(*P(0.314, 1.385), *P(1.414, 0.80), stroke=GLASS, sw=3.2)
    polyline(s, [P(1.414, 0.80), P(2.30, 0.74)], STEEL, 2.4)
    polyline(s, [P(0.45, 0.80), P(1.40, 0.80)], STEEL, 2.0)
    polyline(s, [P(0.45, 0.80), P(0.56, 0.62), P(1.40, 0.62), P(1.40, 0.18), P(-0.75, 0.18)], STEEL, 1.4)
    # seat, driver, wheel and column
    s.path("M%.1f,%.1f L%.1f,%.1f L%.1f,%.1f" % (*P(-0.58, 1.10), *P(-0.44, 0.47), *P(0.10, 0.47)), stroke=STEEL, sw=5)
    head = P(-0.05, 1.235)
    s.circle(head[0], head[1], 15, fill="#e9e7e1", stroke=INK2, sw=1)
    eye = P(0, 1.22)
    s.circle(*eye, 3.4, fill=EYEC)
    s.line(*P(0.30, 0.98), *P(0.42, 0.72), stroke=DARK, sw=4)
    s.line(*P(0.36, 0.85), *P(0.70, 0.70), stroke=DARK, sw=3)
    # HUD housing and the light path inside it
    s.poly([P(0.57, 0.80), P(1.03, 0.80), P(1.03, 1.00), P(0.57, 1.10)], fill="#d9d8d3", stroke=INK2, sw=1)
    PN, F, M, G = P(0.692, 0.955), P(0.692, 1.005), P(0.94, 0.914), P(0.747, 1.155)
    s.rect(PN[0] - 8, PN[1], 16, 4, fill=DARK)
    polyline(s, [PN, F, M, G], LIGHT, 1.8)
    s.arrow(*G, eye[0] + 6, eye[1] + 0.5, color=LIGHT, sw=1.8)
    # line of sight to the virtual image
    vx = 610
    vy = eye[1] + math.tan(math.radians(5)) * (vx - eye[0])
    s.line(*eye, vx, vy, stroke=LIGHT, sw=1, extra='stroke-dasharray="4 4"')
    s.line(vx, vy - 30, vx, vy + 30, stroke=LIGHT, sw=3.4)
    note(s, vx, vy - 40, "virtual image 7.5 m ahead", size=10.5, fill=INK, anchor="middle", weight=600)
    note(s, vx, vy + 46, "a 10.8° × 5.4° window", size=9.5, anchor="middle")
    # sensors and computer
    cam = P(0.36, 1.33)
    s.rect(cam[0] - 10, cam[1] - 4, 20, 9, fill=DARK, rx=2)
    oak = P(0.50, 0.86)
    s.rect(oak[0] - 8, oak[1] - 9, 16, 8, fill=DARK, rx=2)
    ant = P(1.27, 0.81)
    s.rect(ant[0] - 7, ant[1] - 5, 14, 5, fill=DARK, rx=2)
    jet = P(0.85, 0.18)
    s.rect(jet[0] - 24, jet[1] - 20, 48, 20, fill=DARK, rx=3)
    # data cables: camera along the A-pillar, everything down to the footwell
    polyline(s, [(cam[0] + 10, cam[1] + 2), P(0.42, 1.31), P(1.36, 0.84), P(1.36, 0.25), (jet[0] + 24, jet[1] - 10)], DATA, 1.2)
    polyline(s, [(oak[0], oak[1] - 1), P(0.62, 0.55), (jet[0] - 20, jet[1] - 20)], DATA, 1.2)
    polyline(s, [P(0.80, 0.80), P(0.82, 0.62), (jet[0] - 4, jet[1] - 20)], DATA, 1.2)
    polyline(s, [(ant[0], ant[1]), P(1.30, 0.62), (jet[0] + 12, jet[1] - 20)], DATA, 1.2)
    def lab(px, py, tx, ty, text, anchor="start"):
        leader(s, tx, ty, px, py)
        s.text(tx + (4 if anchor == "start" else -4), ty + 4, text, size=10, fill=INK, anchor=anchor)
    lab(cam[0], cam[1] - 4, 250, 40, "road camera (ZED 2i), clamped to the mirror stalk")
    lab(*P(1.10, 0.97), 420, 95, "windshield: reflects about a quarter of the HUD light")
    lab(*P(0.80, 1.04), 420, 130, "HUD housing on the dash: panel, fold, concave mirror")
    lab(eye[0] - 3, eye[1], 30, 70, "driver's eye")
    lab(oak[0] - 8, oak[1] - 4, 30, 260, "driver camera (OAK-D Pro) on the column", "start")
    lab(ant[0] + 7, ant[1] - 3, 430, 222, "GNSS antenna on the dash")
    lab(jet[0] + 24, jet[1] - 12, 380, 300, "Jetson, GNSS receiver, switch in the footwell")
    note(s, 12, 16, "Schematic: the cabin is drawn roughly to scale, the road ahead is compressed. Orange: HUD light. Blue: data cables.", size=9.5, fill=MUTED)
    return s


# =====================================================================================================
@fig("g_chain")
def g_chain():
    W, H = 680, 330
    s = Svg(W, H, "The chain of problems the HUD solves, with the parts that solve each")
    s.rect(0, 0, W, H, fill=SURF)
    cols = [
        ("1  Where is the road?", ["stereo road camera", "lane network", "object detector", "ground-plane fit"], DATA, DATA_T),
        ("2  Where is the eye?", ["driver camera", "face landmarks", "eye point in the", "car frame"], EYEC, EYE_T),
        ("3  How old is it?", ["timestamps", "GNSS speed", "IMU yaw rate", "age compensation"], DATA, DATA_T),
        ("4  Draw for that eye", ["projection", "pre-distortion", "60 Hz renderer", "on the Jetson"], DATA, DATA_T),
        ("5  Make enough light", ["5.5-inch TFT", "custom LED", "backlight", "LED driver"], LIGHT, LIGHT_T),
        ("6  Put it 7.5 m out", ["cold-mirror fold", "concave mirror", "windshield", "as a combiner"], LIGHT, LIGHT_T),
    ]
    bw, gap, x0, y0, bh = 100, 12, 12, 40, 118
    for i, (t, ls, c, ct) in enumerate(cols):
        x = x0 + i * (bw + gap)
        s.rect(x, y0, bw, bh, fill=ct, stroke=c, sw=1.2, rx=5)
        s.text(x + 8, y0 + 18, t, size=10, weight=650, fill=INK)
        for j, l in enumerate(ls):
            s.text(x + 8, y0 + 40 + j * 15, l, size=9.6, fill=INK2)
        if i < len(cols) - 1:
            s.arrow(x + bw + 1, y0 + bh / 2, x + bw + gap - 1, y0 + bh / 2, color=INK2, sw=1.2)
    note(s, x0, 26, "Every frame, left to right, in about 40 to 100 ms:", size=10.5, fill=INK, weight=600)
    # safety layer
    y1 = 196
    note(s, x0, y1 - 10, "Underneath, all the time: problems that are not about the picture", size=10.5, fill=INK, weight=600)
    safe = [
        ("Heat", "fan, heat sink, thermistor,", "controller derates the LEDs", POWER, POWER_T),
        ("Sunlight focused by the mirror", "shutter, cold mirror, IR-cut glass,", "polariser, sun-watch rule", SUN, SUN_T),
        ("Night glare, day contrast", "ambient-light sensor and", "a dimming curve", INK2, GREY_T),
        ("The car itself", "fused 12 V only, ignition-sensed", "converter, removable mounts", POWER, POWER_T),
    ]
    sw_ = (W - 2 * x0 - 3 * 10) / 4
    for i, (t, a, b, c, ct) in enumerate(safe):
        x = x0 + i * (sw_ + 10)
        s.rect(x, y1, sw_, 74, fill=ct, stroke=c, sw=1.2, rx=5)
        s.text(x + 8, y1 + 18, t, size=10, weight=650, fill=INK)
        s.text(x + 8, y1 + 38, a, size=9.4, fill=INK2)
        s.text(x + 8, y1 + 52, b, size=9.4, fill=INK2)
    note(s, x0, 304, "Blue: data and computation. Purple: the driver's eye. Orange: making and relaying the image.",
         size=9.5, fill=MUTED)
    note(s, x0, 318, "Red: power and heat. Gold: sunlight. Grey: brightness control.", size=9.5, fill=MUTED)
    return s


# =====================================================================================================
@fig("g_magnifier")
def g_magnifier():
    W, H = 680, 300
    s = Svg(W, H, "Why an object inside the focal length makes a distant virtual image: magnifier, concave mirror, windshield")
    s.rect(0, 0, W, H, fill=SURF)
    ay = 150
    # ---- A: lens (f = 70 px, object 42.8 px inside, image 110 px out, magnification 2.57)
    note(s, 12, 22, "A  A magnifying glass", size=11, fill=INK, weight=650)
    lx, f, u = 150, 70, 42.8
    ox, ix = lx - u, lx - 110
    s.line(14, ay, 226, ay, stroke=AXIS, sw=0.8)
    s.path(f"M{lx},{ay-62} Q{lx+11},{ay} {lx},{ay+62} Q{lx-11},{ay} {lx},{ay-62} Z", fill=DATA_T, stroke=GLASS, sw=1.2)
    s.circle(lx - f, ay, 2.6, fill=INK2); note(s, lx - f, ay - 8, "F", size=9.5, anchor="middle")
    s.arrow(ox, ay, ox, ay - 20, color=LIGHT, sw=2)
    tip_i = ay - 20 * 110 / u
    s.line(ix, ay, ix, tip_i + 6, stroke=LIGHT, sw=1.6, extra='stroke-dasharray="4 3"')
    s.poly([(ix - 4, tip_i + 7), (ix + 4, tip_i + 7), (ix, tip_i)], fill=LIGHT)
    s.line(ox, ay - 20, lx, ay - 20, stroke=LIGHT, sw=1)
    s1 = 20 / f
    s.line(lx, ay - 20, 222, ay - 20 + (222 - lx) * s1, stroke=LIGHT, sw=1)
    s2 = 20 / u
    s.line(ox, ay - 20, 222, ay - 20 + (222 - ox) * s2, stroke=LIGHT, sw=1)
    s.line(lx, ay - 20, ix, tip_i, stroke=LIGHT, sw=0.7, extra='stroke-dasharray="3 3"')
    s.line(ox, ay - 20, ix, tip_i, stroke=LIGHT, sw=0.7, extra='stroke-dasharray="3 3"')
    s.circle(216, ay + 14, 4.5, fill=EYEC); note(s, 216, ay + 32, "eye", size=9.5, anchor="middle")
    note(s, ox, ay + 16, "object", size=9.5, anchor="middle")
    note(s, ix, ay + 16, "virtual image", size=9.5, anchor="middle")
    s.lines(12, 232, ["The object sits just inside the focal", "point F. Its rays leave the lens", "spreading as if from a bigger object", "farther away; the eye focuses there."], size=9.6, fill=INK2)
    # ---- B: concave mirror (f = 50 px, object 30.8 px inside, image 80 px behind, magnification 2.6)
    bx = 236
    note(s, bx, 22, "B  A concave mirror does the same", size=11, fill=INK, weight=650)
    mx, f, u = bx + 140, 50, 30.8
    ox, ix = mx - u, mx + 80
    s.line(bx + 4, ay, bx + 224, ay, stroke=AXIS, sw=0.8)
    s.path(f"M{mx-9},{ay-66} Q{mx+9},{ay} {mx-9},{ay+66}", stroke=DARK, sw=3.2)
    s.circle(mx - f, ay, 2.6, fill=INK2); note(s, mx - f, ay + 16, "F", size=9.5, anchor="middle")
    s.rect(ox - 2, ay - 20, 4, 20, fill=DARK)
    note(s, ox, ay + 30, "panel", size=9.5, anchor="middle")
    tip_i = ay - 20 * 80 / u
    s.line(ix, ay, ix, tip_i + 6, stroke=LIGHT, sw=1.6, extra='stroke-dasharray="4 3"')
    s.poly([(ix - 4, tip_i + 7), (ix + 4, tip_i + 7), (ix, tip_i)], fill=LIGHT)
    note(s, ix, ay + 16, "image", size=9.5, anchor="middle")
    s.line(ox, ay - 20, mx, ay - 20, stroke=LIGHT, sw=1)
    s.line(mx, ay - 20, bx + 20, ay - 20 + (mx - bx - 20) * 20 / f, stroke=LIGHT, sw=1)
    s.line(ox, ay - 20, mx, ay, stroke=LIGHT, sw=1)
    s.line(mx, ay, bx + 40, ay + (mx - bx - 40) * 20 / u, stroke=LIGHT, sw=1)
    s.line(mx, ay - 20, ix, tip_i, stroke=LIGHT, sw=0.7, extra='stroke-dasharray="3 3"')
    s.line(mx, ay, ix, tip_i, stroke=LIGHT, sw=0.7, extra='stroke-dasharray="3 3"')
    s.circle(bx + 30, ay + 46, 4.5, fill=EYEC); note(s, bx + 30, ay + 64, "eye", size=9.5, anchor="middle")
    s.lines(bx, 232, ["Same rule, folded back: a panel just", "inside the mirror's focal point gives an", "upright, magnified virtual image behind", "it. The HUD: 316 mm in, 7.5 m out."], size=9.6, fill=INK2)
    # ---- C: windshield as the combiner (rake 28 deg, eye ray 5 deg down)
    cx = 466
    note(s, cx, 22, "C  The windshield folds it to the eye", size=11, fill=INK, weight=650)
    r = math.radians(28)
    g0 = (cx + 44, 56); dvec = (math.cos(r), math.sin(r))
    g1 = (g0[0] + 150 * dvec[0], g0[1] + 150 * dvec[1])
    s.line(*g0, *g1, stroke=GLASS, sw=3.2)
    note(s, g1[0] + 4, g1[1] + 14, "glass", size=9.5, anchor="end")
    eye = (cx + 10, 84)
    v = (math.cos(math.radians(5)), math.sin(math.radians(5)))
    # intersect the eye ray with the glass line
    den = v[0] * dvec[1] - v[1] * dvec[0]
    tt = ((g0[0] - eye[0]) * dvec[1] - (g0[1] - eye[1]) * dvec[0]) / den
    gp = (eye[0] + tt * v[0], eye[1] + tt * v[1])
    dot = v[0] * dvec[0] + v[1] * dvec[1]
    rv = (2 * dot * dvec[0] - v[0], 2 * dot * dvec[1] - v[1])     # mirror image of v about the glass line
    src = (gp[0] + 80 * rv[0], gp[1] + 80 * rv[1])
    s.arrow(*src, gp[0] + 2 * rv[0], gp[1] + 2 * rv[1], color=LIGHT, sw=1.6)
    s.arrow(*gp, eye[0] + 7, eye[1] + 0.6, color=LIGHT, sw=1.6)
    s.line(*gp, cx + 205, gp[1] + (cx + 205 - gp[0]) * v[1] / v[0], stroke=LIGHT, sw=1, extra='stroke-dasharray="4 3"')
    s.circle(*eye, 4.5, fill=EYEC); note(s, eye[0], eye[1] - 10, "eye", size=9.5, anchor="middle")
    note(s, cx + 205, gp[1] - 4, "seen out here", size=9.5, anchor="end")
    note(s, src[0] - 6, src[1] + 4, "from the mirror", size=9.5, anchor="end")
    s.lines(cx, 232, ["About a quarter of the light reflects", "off the glass toward the eye and the", "road shows through. The picture", "appears over the road, not on the glass."], size=9.6, fill=INK2)
    return s


# =====================================================================================================
@fig("g_section")
def g_section():
    """To scale, from layout.json: eye, windshield, housing, panel, fold, mirror and traced rays."""
    W, H = 680, 330
    s = Svg(W, H, "To-scale side section of the Stage 2 optics with traced rays")
    s.rect(0, 0, W, H, fill=SURF)
    x_min, x_max, y_min, y_max = -0.06, 1.46, 0.76, 1.42
    k = (W - 30) / (x_max - x_min)
    P = lambda x, y: (15 + (x - x_min) * k, 20 + (y_max - y) * k)
    G = LAY["glass"]["G"]
    tanr = math.tan(math.radians(LAY["glass"]["rakeDeg"]))
    gx = lambda y: G[0] - (y - G[1]) / tanr
    # dash line and windshield
    s.line(*P(0.40, 0.80), *P(1.46, 0.80), stroke=STEEL, sw=1.6)
    s.line(*P(gx(1.40), 1.40), *P(gx(0.80), 0.80), stroke=GLASS, sw=3.2)
    # housing outline (from the CAD layout)
    lay = LAY["layout"]
    lid_y = lambda x: lay["apC"][1] + (x - lay["apC"][0]) * lay["lidDir"][1] / lay["lidDir"][0]
    xr, xf = lay["xR"], lay["xF"]
    hp = [P(xr, 0.962), P(0.64, 0.962), P(0.64, 0.809), P(xf, 0.809), P(xf, lid_y(xf)), P(xr, lid_y(xr))]
    s.poly(hp, fill="#ecebe7", stroke=INK2, sw=1)
    # aperture on the lid
    a0, a1 = lay["ax0"], lay["ax1"]
    s.line(*P(a0, lid_y(a0)), *P(a1, lid_y(a1)), stroke=SURF, sw=3)
    s.line(*P(a0, lid_y(a0)), *P(a1, lid_y(a1)), stroke=GLASS, sw=1.2)
    # rays: lateral centre of the eye box and of the field
    for r in LAY["rays"]["toroid"]:
        if r["e"][0] != 0 or r["f"][0] != 0:
            continue
        pts = [P(p[0], p[1]) for p in r["pts"]]
        polyline(s, pts, LIGHT, 0.7, 'stroke-opacity="0.75"')
    # mirror (arc), fold, panel and backlight
    m = LAY["mirror"]; C, Vv = m["C"], m["V"]; Nn = m["N"]
    e1 = P(C[0] - 0.1 * Vv[0], C[1] - 0.1 * Vv[1]); e2 = P(C[0] + 0.1 * Vv[0], C[1] + 0.1 * Vv[1])
    sag = 0.2 ** 2 / (8 * m["toroid"]["Rt"])
    ctl = P(C[0] - 2 * sag * Nn[0], C[1] - 2 * sag * Nn[1])
    s.path(f"M{e1[0]:.1f},{e1[1]:.1f} Q{ctl[0]:.1f},{ctl[1]:.1f} {e2[0]:.1f},{e2[1]:.1f}", stroke=DARK, sw=3.2)
    f = LAY["fold"]; FC, fv = f["C"], f["fv"]
    s.line(*P(FC[0] + f["v0"] * fv[0], FC[1] + f["v0"] * fv[1]), *P(FC[0] + f["v1"] * fv[0], FC[1] + f["v1"] * fv[1]),
           stroke=DATA, sw=2.6)
    pn = LAY["panel"]; PC = pn["C"]
    s.line(*P(PC[0] - pn["outX"] / 2, PC[1]), *P(PC[0] + pn["outX"] / 2, PC[1]), stroke=DARK, sw=3)
    s.line(*P(PC[0] - pn["cropX"] / 2, PC[1] + 0.002), *P(PC[0] + pn["cropX"] / 2, PC[1] + 0.002), stroke=LIGHT, sw=2.2)
    bx0, by0 = P(PC[0] - 0.035, PC[1] - 0.003)
    bx1, by1 = P(PC[0] + 0.035, PC[1] - pn["backlightDepth"])
    s.rect(bx0, by0, bx1 - bx0, by1 - by0, fill="#d9d8d3", stroke=INK2, sw=0.8)
    # eye box
    ex, ey = P(0, 1.22)
    s.rect(ex - 3, ey - 0.035 * k, 6, 0.07 * k, fill=EYE_T, stroke=EYEC, sw=1)
    s.circle(ex, ey, 2.6, fill=EYEC)
    # labels
    def lab(px, py, tx, ty, text, anchor="start"):
        leader(s, tx, ty, px, py)
        s.text(tx + (4 if anchor == "start" else -4), ty + 4, text, size=9.8, fill=INK, anchor=anchor)
    lab(ex, ey + 0.035 * k, 30, 200, "eye box, 130 × 70 mm, centred on the eye")
    gp = P(gx(1.30), 1.30)
    lab(*gp, 250, 40, "windshield, rake 28° (assumed), 4.96 mm laminate")
    lab(*P(C[0], C[1]), 560, 252, f"concave mirror, toroid Rt {LAY['mirror']['toroid']['Rt']*1000:.0f} / Rs {LAY['mirror']['toroid']['Rs']*1000:.0f} mm", "end")
    lab(*P(FC[0] - 0.02, FC[1] - 0.01), 250, 150, f"cold-mirror fold, {f['incDeg']:.0f}° incidence")
    lab(*P(PC[0] - 0.012, PC[1] + 0.002), 140, 175, "TFT panel, 60 × 30 mm crop lit")
    lab(*P(PC[0] - 0.03, PC[1] - 0.04), 150, 270, "backlight, heat sink, fan")
    lab(*P((a0 + a1) / 2, lid_y((a0 + a1) / 2)), 560, 120, "dust cover, polariser, shutter", "end")
    lab(*P(0.60, 0.962), 30, 240, "housing steps over the cluster hood")
    dx0, dy = P(0, 0.785)[0], P(0, 0.785)[1]
    dim_h(s, P(xr, 0.78)[0], P(xf, 0.78)[0], P(0, 0.772)[1] + 8, "")
    note(s, P(xr, 0.78)[0] - 8, P(0, 0.772)[1] + 12, "housing: 459 mm long, 370 mm wide, 300 mm tall", size=9.4, anchor="end")
    note(s, 15, 14, "To scale. Side section on the driver's centreline; forward is to the right. Rays from the centre of the eye box to the top, centre and bottom of the window.", size=9.3, fill=MUTED)
    return s


# =====================================================================================================
@fig("g_registration")
def g_registration():
    W, H = 680, 270
    s = Svg(W, H, "Registration: the mark must lie on the line from the eye to the road point, so it moves when the head moves")
    s.rect(0, 0, W, H, fill=SURF)
    gy = 225
    s.line(20, gy, W - 20, gy, stroke=INK2, sw=1.2)
    note(s, W - 22, gy + 15, "road", anchor="end")
    e1 = (150, 110); e2 = (150, 150)
    vx = 330
    s.line(vx, 40, vx, gy, stroke=LIGHT, sw=1.6, extra='stroke-dasharray="5 4"')
    note(s, vx, 32, "virtual image plane (7.5 m)", size=10, fill=INK, anchor="middle", weight=600)
    pts = [(490, "lane point 15 m"), (630, "lead car 30 m")]
    for (px, lbl) in pts:
        s.circle(px, gy, 5, fill=INK)
        note(s, px, gy + 18, lbl, size=9.8, fill=INK, anchor="middle")
        for e, c in ((e1, EYEC), (e2, "#b9a6dc")):
            s.line(e[0], e[1], px, gy, stroke=c, sw=1)
            yc = e[1] + (vx - e[0]) / (px - e[0]) * (gy - e[1])
            s.circle(vx, yc, 4.5, fill=LIGHT if c == EYEC else ORANGE_T, stroke=LIGHT, sw=1.2)
    s.circle(*e1, 6, fill=EYEC); s.circle(*e2, 6, fill="#b9a6dc")
    note(s, 138, e1[1] + 4, "eye", size=10, anchor="end")
    note(s, 138, e2[1] + 4, "eye after a 40 mm dip", size=10, anchor="end")
    s.lines(352, 62, ["For each road point there is exactly one place on the", "image plane where its mark lines up, and it depends", "on where the eye is. Move the head and the right", "place moves (filled marks: first eye; pale: second)."], size=9.8, fill=INK2)
    s.lines(352, 132, ["The road camera is not at the eye, so the software", "must know both positions. That is why the HUD needs", "a driver camera and a calibrated car frame."], size=9.8, fill=INK2)
    note(s, 20, 260, "Schematic. Untracked, a 150 mm head shift misplaces a mark by 0.29° for a point at 10 m, 0.86° at 30 m, and nothing at the 7.5 m image distance.", size=9.3, fill=MUTED)
    return s


# =====================================================================================================
@fig("g_delay")
def g_delay():
    W, H = 680, 250
    s = Svg(W, H, "Timeline of one frame from camera to photons, with the car's travel at 30 m/s")
    s.rect(0, 0, W, H, fill=SURF)
    stages = [("camera", 10, 30), ("perception", 10, 25), ("publish", 1, 3), ("render", 8, 16), ("panel scan-out", 8, 25)]
    x0, y0, scale = 40, 60, 5.9     # px per ms at the high end
    t = 0
    cols = [DATA, DATA, DATA, DATA, LIGHT]
    for i, (n, lo, hi) in enumerate(stages):
        w = hi * scale
        s.rect(x0 + t * scale, y0, w - 2, 26, fill=DATA_T if i < 4 else LIGHT_T, stroke=cols[i], sw=1, rx=3)
        if w > 40:
            s.text(x0 + t * scale + 5, y0 + 17, n, size=9.6, fill=INK)
            s.text(x0 + t * scale + 5, y0 + 42, f"{lo}–{hi} ms", size=9, fill=INK2)
        else:
            s.text(x0 + t * scale + w / 2, y0 + 42, f"{n} {lo}–{hi} ms", size=9, fill=INK2, anchor="middle")
            s.line(x0 + t * scale + w / 2, y0 + 27, x0 + t * scale + w / 2, y0 + 32, stroke=INK2, sw=0.8)
        t += hi
    note(s, x0, y0 - 14, "Worst case of each stage from the plan's latency budget (37–99 ms in total):", size=10, fill=INK, weight=600)
    # car travel bar
    y1 = 160
    s.line(x0, y1, x0 + 99 * scale, y1, stroke=INK2, sw=1)
    for ms in range(0, 100, 10):
        s.line(x0 + ms * scale, y1 - 3, x0 + ms * scale, y1 + 3, stroke=INK2, sw=0.8)
        note(s, x0 + ms * scale, y1 + 15, f"{ms * 0.03:.1f} m", size=8.6, anchor="middle")
    note(s, x0, y1 - 10, "distance the car has moved at 30 m/s (about 67 mph) since the camera's exposure", size=9.6)
    s.lines(x0, 210, ["By the time the light leaves the panel, the car is 1 to 3 m further on. Drawn as captured, every mark would lag behind", "the paint. Each message carries its capture time; the renderer moves each point by the measured speed and yaw rate", "over its age before drawing it (age compensation)."], size=9.6, fill=INK2)
    return s


# =====================================================================================================
@fig("g_budget")
def g_budget():
    """Light budget from the panel to the eye, on a log scale, single series, direct labels."""
    W, H = 680, 270
    s = Svg(W, H, "Luminance budget: panel to eye through two mirrors and the windshield, against the noon targets")
    s.rect(0, 0, W, H, fill=SURF)
    steps = [("panel (custom backlight)", 10000), ("after the cold-mirror fold (90%)", 9000),
             ("after the concave mirror (90%)", 8100), ("at the eye after the windshield (23.6%)", 1944)]
    x0, x1 = 260, 650
    lo, hi = math.log10(100), math.log10(20000)
    X = lambda v: x0 + (math.log10(v) - lo) / (hi - lo) * (x1 - x0)
    y = 38
    for v in (100, 300, 1000, 3000, 10000):
        s.line(X(v), 30, X(v), 30 + 4 * 34 + 8, stroke=GRID, sw=0.8)
        note(s, X(v), 30 + 4 * 34 + 22, f"{v:,}", size=9, anchor="middle")
    note(s, (x0 + x1) / 2, 30 + 4 * 34 + 36, "cd/m², log scale", size=9, anchor="middle")
    for i, (n, v) in enumerate(steps):
        yy = y + i * 34
        s.rect(X(100), yy, X(v) - X(100), 16, fill=LIGHT, rx=2)
        note(s, x0 - 8, yy + 12, n, size=9.8, fill=INK, anchor="end")
        note(s, X(v) + 6, yy + 12, f"{v:,}", size=9.8, fill=INK, weight=600)
    # targets
    for v, lbl in ((1500, "noon sky target 1,500"), (750, "sunlit road target 750")):
        s.line(X(v), 34, X(v), 30 + 4 * 34 + 4, stroke=INK, sw=1, extra='stroke-dasharray="3 3"')
    note(s, X(1500) + 4, 28, "noon sky target 1,500", size=9, fill=INK)
    note(s, X(750) - 4, 28, "sunlit road 750", size=9, fill=INK, anchor="end")
    note(s, 12, 240, "The windshield is the big loss: it reflects about a quarter of s-polarised light and almost none of p. The stock panel (450 cd/m²)", size=9.4, fill=INK2)
    note(s, 12, 254, "would give 87 cd/m² at the eye, invisible at noon; the custom backlight brings it to 10,000 (13,000 in this guide, to cover the losses B10 adds).", size=9.4, fill=INK2)
    return s


# =====================================================================================================
@fig("g_stack")
def g_stack():
    W, H = 680, 555
    s = Svg(W, H, "Exploded cross-section of the PGU stack in assembly order, bottom to top")
    s.rect(0, 0, W, H, fill=SURF)
    layers = [  # (label, detail, thickness px, fill, stroke)
        ("hot-mirror IR-cut glass, on the mask", "in front of the cell: the sun arrives from above", 7, "#dbe9f5", DATA),
        ("panel mask (printed)", "opening = traced footprint + 3 mm", 6, DARK, DARK),
        ("half-wave retarder (only if needed)", "fast axis at the measured angle", 4, "#e7e1f3", EYEC),
        ("LCD cell: front polariser", "the panel's own; output is polarised", 4, "#cfd8e2", GLASS),
        ("LCD cell: glass, liquid crystal, filters", "the 60 × 30 mm crop is the only lit area", 12, "#b9c6d3", GLASS),
        ("LCD cell: rear polariser", "keep intact during teardown", 4, "#cfd8e2", GLASS),
        ("0.5 mm air gap", "carrier holds the cell by its edges", 4, "none", "none"),
        ("clear cover glass", "seals the cavity; the carrier holds the cell above it", 7, "#f1f1ef", STEEL),
        ("prism film 2, prisms crossed", "90° to film 1", 4, "#e6f0fb", DATA),
        ("prism film 1", "salvaged stock film or new", 4, "#e6f0fb", DATA),
        ("diffuser plate", "closes the cavity", 7, "#f1f1ef", STEEL),
        ("mixing cavity, 22 mm, white walls", "evens the LEDs into one surface", 46, "#fbfbf8", STEEL),
        ("LED board: 8 white LEDs", "aluminium core, screwed through the pad", 7, "#e6e2d2", SUN),
        ("thermal pad", "", 3, "#cfcfcf", STEEL),
        ("finned heat sink", "", 30, "#bdbcb7", STEEL),
        ("40 mm fan", "blows down through the bay floor", 12, DARK, DARK),
    ]
    x0, w = 70, 230
    y = 30
    gap = 7
    for i, (lbl, det, t, fc, sc) in enumerate(layers):
        if lbl.startswith("0.5 mm"):
            s.line(x0, y + t / 2, x0 + w, y + t / 2, stroke=AXIS, sw=0.8, extra='stroke-dasharray="2 3"')
        elif lbl.startswith("mixing"):
            s.rect(x0, y, 6, t, fill=SURF, stroke=STEEL, sw=1)
            s.rect(x0 + w - 6, y, 6, t, fill=SURF, stroke=STEEL, sw=1)
            for j in range(8):
                lx = x0 + 22 + j * (w - 44) / 7
                s.path(f"M{lx},{y + t} L{lx - 18},{y + 6} M{lx},{y + t} L{lx + 18},{y + 6} M{lx},{y + t} L{lx},{y + 4}", stroke=SUN, sw=0.7, extra='stroke-opacity="0.6"')
        elif lbl.startswith("LED board"):
            s.rect(x0, y, w, t, fill=fc, stroke=sc, sw=1)
            for j in range(8):
                lx = x0 + 22 + j * (w - 44) / 7
                s.rect(lx - 5, y - 4, 10, 4, fill=SUN)
        elif lbl.startswith("finned"):
            s.rect(x0, y, w, 8, fill=fc, stroke=INK2, sw=0.8)
            for j in range(14):
                s.rect(x0 + 4 + j * (w - 8) / 14, y + 8, 6, t - 8, fill=fc, stroke=INK2, sw=0.5)
        elif lbl.startswith("40 mm"):
            s.rect(x0 + w / 2 - 40, y, 80, t, fill=fc, rx=2)
        elif lbl.startswith("prism"):
            s.rect(x0, y, w, t, fill=fc, stroke=sc, sw=0.8)
            if "2" in lbl:
                for j in range(0, int(w), 6):
                    s.line(x0 + j, y, x0 + j, y + t, stroke=sc, sw=0.4)
            else:
                s.line(x0, y + t / 2, x0 + w, y + t / 2, stroke=sc, sw=0.4)
        elif lbl.startswith("panel mask"):
            s.rect(x0 - 10, y, 60, t, fill=fc)
            s.rect(x0 + w - 50, y, 60, t, fill=fc)
        else:
            s.rect(x0, y, w, t, fill=fc, stroke=sc, sw=0.8)
        s.line(x0 + w + 12, y + t / 2, 330, y + t / 2, stroke=AXIS, sw=0.6)
        s.text(336, y + t / 2 + 3, lbl, size=9.8, fill=INK, weight=600 if not lbl.startswith("0.5") else 400)
        if det:
            s.text(336, y + t / 2 + 15, det, size=8.8, fill=INK2)
        y += max(t + gap, 30 if det else 20)
    note(s, 20, 548, "Exploded; thicknesses not to scale. Build it from the bottom up. The cell and its polarisers are the panel's own; everything else is new.", size=9.2, fill=MUTED)
    return s


# =====================================================================================================
@fig("g_ledboard")
def g_ledboard():
    W, H = 680, 250
    s = Svg(W, H, "LED board top view behind the 60 by 30 mm crop, with the two series strings")
    s.rect(0, 0, W, H, fill=SURF)
    k = 3.2                     # px per mm
    x0, y0 = 40, 40
    bw, bh = 76, 46             # board mm
    s.rect(x0, y0, bw * k, bh * k, fill="#e6e2d2", stroke=INK2, sw=1, rx=3)
    cx0, cy0 = x0 + 8 * k, y0 + 8 * k
    s.rect(cx0, cy0, 60 * k, 30 * k, fill="none", stroke=LIGHT, sw=1.4, extra='stroke-dasharray="5 3"')
    note(s, cx0 + 2, cy0 - 5, "60 × 30 mm crop (cavity inner wall)", size=9.4, fill=INK)
    leds = []
    for r in range(2):
        for c in range(4):
            lx = cx0 + (7.5 + c * 15) * k
            ly = cy0 + (7.5 + r * 15) * k
            leds.append((lx, ly))
            s.rect(lx - 7, ly - 7, 14, 14, fill=SUN, rx=2)
    # strings
    a = leds[:4]; b = leds[4:]
    polyline(s, [(a[0][0] - 20, a[0][1])] + a + [(a[-1][0] + 24, a[-1][1])], POWER, 1.4)
    polyline(s, [(b[0][0] - 20, b[0][1])] + b + [(b[-1][0] + 24, b[-1][1])], DATA, 1.4)
    note(s, a[-1][0] + 28, a[-1][1] + 4, "string A", size=9.4, fill=INK)
    note(s, b[-1][0] + 28, b[-1][1] + 4, "string B", size=9.4, fill=INK)
    dim_h(s, cx0 + 7.5 * k, cx0 + 22.5 * k, y0 + bh * k + 18, "15 mm pitch")
    dim_h(s, x0, x0 + bw * k, y0 + bh * k + 36, "board about 76 × 46 mm")
    s.lines(330, 50, [
        "Eight LEDs on a 15 mm grid fill the crop evenly once the",
        "22 mm cavity mixes them: cavity depth at least the LED",
        "pitch is the rule of thumb. Two strings of four, each on",
        "its own constant-current channel, so one failed LED",
        "darkens half the board, not all of it, and each string's",
        "voltage stays below what a 19 V supply can drive.",
        "",
        "Keep the outermost LED centres 7.5 mm from the cavity",
        "wall; the white wall acts as a mirror and fills the edge.",
        "Measure uniformity over the crop before closing the",
        "stack; move to a 3 × 5 grid if corners read low.",
    ], size=9.6, fill=INK2)
    return s


# =====================================================================================================
@fig("g_stage0d")
def g_stage0d():
    W, H = 680, 270
    s = Svg(W, H, "Stage 0 bench rig, dimensioned side view")
    s.rect(0, 0, W, H, fill=SURF)
    by = 220
    s.line(20, by, 660, by, stroke=INK2, sw=1.2); note(s, 24, by + 14, "bench")
    # enclosure
    s.path(f"M120,{by} L120,{by-110} M300,{by} L300,{by-26}", stroke=DARK, sw=3)
    s.rect(120, by - 16, 180, 16, fill=DARK)
    s.rect(132, by - 22, 156, 6, fill=LIGHT)
    note(s, 210, by + 14, "panel face up, crop drawn mirrored", size=9.4, anchor="middle")
    # beamsplitter at 45 degrees
    s.line(140, by - 30, 280, by - 170, stroke=GLASS, sw=3)
    note(s, 270, by - 176, "70/30 glass at 45°", size=9.6, fill=INK, anchor="end")
    # backdrop
    s.rect(96, by - 190, 10, 190, fill=DARK)
    note(s, 92, by - 196, "black backdrop", size=9.4, anchor="end")
    # rays
    for px in (160, 210, 260):
        gy_ = by - 22 - (px - 140) * 0
        hit_y = by - 30 - (px - 140)
        s.line(px, by - 22, px, hit_y, stroke=LIGHT, sw=1)
        s.line(px, hit_y, 620, hit_y, stroke=LIGHT, sw=1)
    s.circle(620, by - 100, 6, fill=EYEC)
    s.rect(606, by - 112, 30, 24, fill="none", stroke=INK2, sw=1, rx=3)
    note(s, 622, by - 120, "camera or eye", size=9.6, anchor="middle")
    s.line(210, by - 100, 100, by - 100, stroke=LIGHT, sw=1, extra='stroke-dasharray="4 3"')
    note(s, 106, by - 104, "image appears here", size=9.2)
    note(s, 410, by - 40, "camera about 0.4 m from the glass; the image lies", size=9.2)
    note(s, 410, by - 28, "panel-to-glass farther: about 0.6 m in all", size=9.2)
    s.lines(350, 24, ["One reflection flips the picture top to bottom:", "set the renderer's flip until a test card reads", "correctly through the glass. Nothing here", "magnifies; Stage 0 tests software, not optics."], size=9.6, fill=INK2)
    return s


# =====================================================================================================
@fig("g_stage1d")
def g_stage1d():
    W, H = 680, 330
    s = Svg(W, H, "Stage 1 in-car rig: Fresnel magnifier and free-standing combiner, dimensioned")
    s.rect(0, 0, W, H, fill=SURF)
    by = 300
    s.line(20, by, 660, by, stroke=STEEL, sw=2); note(s, 24, by + 14, "dash top")
    k = 0.5                                        # px per mm, vertical
    ex0, ex1 = 260, 430
    fy = by - 14 - 280 * k
    s.path(f"M{ex0},{by} L{ex0},{fy} M{ex1},{by} L{ex1},{fy}", stroke=DARK, sw=3)
    s.rect(ex0 + 6, by - 10, ex1 - ex0 - 12, 10, fill=DARK)
    s.rect(ex0 + 30, by - 14, (ex1 - ex0) - 60, 4, fill=LIGHT)
    note(s, (ex0 + ex1) / 2, by + 14, "panel face up, 80 × 40 mm crop", size=9.4, anchor="middle")
    s.rect(ex0, fy - 3, ex1 - ex0, 4, fill="#dbe9f5", stroke=DATA, sw=0.8)
    note(s, ex1 + 8, fy + 2, "300 mm Fresnel, f = 300 mm, grooves down", size=9.4, fill=INK)
    dim_v(s, ex0 - 16, by - 14, fy, "280 mm", side="left")
    ca, cb = (ex0 + 150, fy - 20), (ex0 + 20, fy - 120)
    s.line(*ca, *cb, stroke=GLASS, sw=3)
    note(s, cb[0] - 8, cb[1] + 4, "30% combiner, leaning toward the driver", size=9.4, fill=INK, anchor="end")
    eye = (70, fy - 10)
    for px in (ex0 + 55, ex0 + 85):
        fr = (ca[0] - px) / (ca[0] - cb[0])
        hy = ca[1] + fr * (cb[1] - ca[1])
        s.line(px, by - 14, px, hy, stroke=LIGHT, sw=1)
        s.line(px, hy, eye[0] + 6, eye[1], stroke=LIGHT, sw=1)
    s.circle(*eye, 6, fill=EYEC); note(s, eye[0], eye[1] + 20, "eye", size=9.6, anchor="middle")
    s.lines(ex1 + 8, fy + 40, ["Panel 280 mm inside a 300 mm focal length:", "1/v = 1/300 − 1/280, so v = −4.2 m (virtual);", "magnification 15: the 80 × 40 mm crop becomes", "1.2 × 0.6 m at about 4.2 m, or 16° × 8°."], size=9.4, fill=INK2)
    note(s, 20, 324, "Schematic; the 280 mm is to scale (0.5 px per mm). The combiner stands free above the dash; nothing touches the windshield.", size=9.2, fill=MUTED)
    return s


# =====================================================================================================
@fig("g_glassmeasure")
def g_glassmeasure():
    W, H = 680, 290
    s = Svg(W, H, "Three windshield measurements: rake, laminate thickness by laser double spot, curvature by sagitta")
    s.rect(0, 0, W, H, fill=SURF)
    # A rake
    note(s, 12, 18, "A  Rake", size=11, fill=INK, weight=650)
    s.line(30, 220, 200, 220, stroke=INK2, sw=1)
    s.line(60, 220, 190, 220 - 130 * math.tan(math.radians(28)) * 1.0 - 0, stroke=GLASS, sw=3)
    s.rect(110, 172, 50, 12, fill=DARK, rx=2, extra=f'transform="rotate(-28 135 178)"')
    note(s, 140, 160, "angle gauge on the glass", size=9.4, anchor="middle")
    note(s, 95, 214, "28°?", size=9.8, fill=INK)
    s.lines(12, 248, ["Zero the gauge on the floor under", "the car, then read it on the inner", "glass at the HUD patch: 3 readings."], size=9.4, fill=INK2)
    # B thickness by laser
    bx = 238
    note(s, bx, 18, "B  Laminate thickness", size=11, fill=INK, weight=650)
    s.rect(bx + 70, 40, 14, 170, fill="#dbe9f5", stroke=GLASS, sw=1)
    s.line(bx + 77, 40, bx + 77, 210, stroke=GLASS, sw=0.5, extra='stroke-dasharray="2 2"')
    s.arrow(bx + 10, 70, bx + 70, 125, color=POWER, sw=1.4)
    s.line(bx + 70, 125, bx + 20, 175, stroke=POWER, sw=1.2)
    s.line(bx + 70, 125, bx + 84, 138, stroke=POWER, sw=0.8)
    s.line(bx + 84, 138, bx + 70, 151, stroke=POWER, sw=0.8)
    s.line(bx + 70, 151, bx + 20, 200, stroke=POWER, sw=1.2)
    s.rect(bx + 4, 168, 6, 40, fill=DARK)
    note(s, bx + 2, 220, "card: two spots", size=9.4)
    note(s, bx + 2, 62, "laser pointer", size=9.4)
    s.lines(bx, 248, ["Spots on the card are d apart:", "t = d / (2 tan θt cos θi), θt from", "Snell (n = 1.52). Repeat at 3 angles."], size=9.4, fill=INK2)
    # C curvature by sagitta
    cx = 470
    note(s, cx, 18, "C  Curvature", size=11, fill=INK, weight=650)
    s.path(f"M{cx+10},{170} Q{cx+100},{130} {cx+190},{170}", stroke=GLASS, sw=3)
    s.line(cx + 10, 168, cx + 190, 168, stroke=DARK, sw=3)
    dim_v(s, cx + 100, 150, 168, "sagitta s")
    dim_h(s, cx + 10, cx + 190, 196, "straightedge length L")
    s.lines(cx, 248, ["Straightedge on the inner glass,", "across and along: R = L² / 8s.", "Two radii feed the ray trace."], size=9.4, fill=INK2)
    return s


# =====================================================================================================
@fig("g_target")
def g_target():
    W, H = 680, 330
    s = Svg(W, H, "Registration set-up: target board 30 m ahead on the car's axis, camera at the eye point")
    s.rect(0, 0, W, H, fill=SURF)
    # plan view
    note(s, 12, 18, "Plan view (not to scale)", size=11, fill=INK, weight=650)
    s.rect(30, 70, 90, 46, fill="#e9e7e1", stroke=INK2, sw=1, rx=8)
    note(s, 75, 128, "car", size=9.6, anchor="middle")
    s.circle(62, 84, 4, fill=EYEC); note(s, 58, 64, "camera at eye", size=9.2, anchor="middle")
    s.line(10, 93, 400, 93, stroke=INK2, sw=0.8, extra='stroke-dasharray="6 4"')
    note(s, 300, 88, "car centreline, strings or chalk", size=9.2, anchor="middle")
    s.rect(400, 66, 8, 54, fill=DARK)
    note(s, 404, 136, "board at 30 m", size=9.4, anchor="middle")
    dim_h(s, 62, 404, 160, "30.0 m, surveyed with the rangefinder from the eye point")
    s.line(62, 84, 404, 74, stroke=EYEC, sw=0.8)
    s.line(62, 84, 404, 112, stroke=EYEC, sw=0.8)
    # board face
    note(s, 440, 18, "Board face", size=11, fill=INK, weight=650)
    bx, by, bw, bh = 440, 34, 220, 150
    s.rect(bx, by, bw, bh, fill="#fbfbf8", stroke=INK, sw=1.2)
    for i in range(8):
        for j in range(4):
            if (i + j) % 2 == 0:
                s.rect(bx + 30 + i * 20, by + 20 + j * 20, 20, 20, fill=INK)
    for (tx, ty) in ((bx + 15, by + 15), (bx + bw - 15, by + 15), (bx + 15, by + bh - 15), (bx + bw - 15, by + bh - 15), (bx + bw / 2, by + bh - 25)):
        s.circle(tx, ty, 8, fill="none", stroke=POWER, sw=2)
        s.circle(tx, ty, 2, fill=POWER)
    note(s, bx + bw / 2, by + bh + 16, "2.0 × 1.4 m plywood, matte white", size=9.4, anchor="middle")
    note(s, bx + bw / 2, by + bh + 30, "checkerboard and survey rings", size=9.4, anchor="middle")
    s.lines(12, 240, [
        "1  Park on level ground; mark the centreline from two points on the car (badge, rear-window centre).",
        "2  Put the board 30 m ahead, square to the centreline, ring centre at a surveyed height.",
        "3  Camera on a tripod head at the nominal eye point, focused at infinity.",
        "4  The road camera's own detection of the checkerboard and the survey of the rings give two answers;",
        "    their difference is perception error, the HUD mark against the rings is optics error.",
    ], size=9.6, fill=INK2, lh=15)
    return s


# =====================================================================================================
@fig("g_vid")
def g_vid():
    W, H = 680, 230
    s = Svg(W, H, "Measuring the virtual image distance by parallax against a pole at a known distance")
    s.rect(0, 0, W, H, fill=SURF)
    gy = 190
    s.line(20, gy, 660, gy, stroke=INK2, sw=1)
    e1, e2 = (130, 100), (130, 140)
    pole_x = 470
    s.line(pole_x, gy, pole_x, 60, stroke=DARK, sw=3)
    note(s, pole_x, gy + 14, "pole at 7.5 m", size=9.6, anchor="middle")
    vx = 470
    s.circle(vx, 118, 5, fill=LIGHT)
    for e, c in ((e1, EYEC), (e2, "#b9a6dc")):
        s.circle(*e, 6, fill=c)
        s.line(e[0], e[1], vx, 118, stroke=c, sw=1)
        s.line(vx, 118, vx + 140, 118 + (118 - e[1]) * 140 / (vx - e[0]), stroke=c, sw=0.6, extra='stroke-dasharray="3 3"')
    note(s, 118, 104, "camera, high", size=9.4, anchor="end")
    note(s, 118, 144, "camera, low", size=9.4, anchor="end")
    s.lines(20, 24, ["Move the camera sideways or up and down by 50–75 mm while it watches a HUD cross and a pole.",
                      "If the cross stays on the pole, the image is at the pole's distance. If the cross moves with the camera,",
                      "the image is nearer than the pole; if it moves against the camera, farther. Slide the pole until it holds."], size=9.6, fill=INK2, lh=14)
    return s


# =====================================================================================================
@fig("g_stages")
def g_stages():
    W, H = 680, 380
    s = Svg(W, H, "Build stages and their dependencies; the optics critical path is outlined in black")
    s.rect(0, 0, W, H, fill=SURF)
    B = {}
    def node(key, x, y, w, title, sub, col, colt, crit=False):
        s.rect(x, y, w, 40, fill=colt, stroke=INK if crit else col, sw=2.2 if crit else 1, rx=4)
        s.text(x + 7, y + 16, title, size=9.6, weight=650, fill=INK)
        s.text(x + 7, y + 30, sub, size=8.8, fill=INK2)
        B[key] = (x, y, w)
    def edge(a, b):
        ax, ay, aw = B[a]; bx, by, bw = B[b]
        x1, y1 = ax + aw, ay + 20
        x2, y2 = bx, by + 20
        if abs(y1 - y2) < 2:
            s.arrow(x1 + 1, y1, x2 - 2, y2, color=INK2, sw=1)
        else:
            mx = x1 + 8
            s.path(f"M{x1+1},{y1} L{mx},{y1} L{mx},{y2} L{x2-6},{y2}", stroke=INK2, sw=1)
            s.arrow(x2 - 8, y2, x2 - 2, y2, color=INK2, sw=1)
    node("s0", 10, 170, 92, "B1", "car, measure, order", INK2, GREY_T, True)
    node("s1", 120, 40, 100, "B2", "Jetson set-up", DATA, DATA_T)
    node("s2", 240, 40, 100, "B3", "sensors, recording", DATA, DATA_T)
    node("s3", 360, 40, 100, "B4", "perception · G1", DATA, DATA_T)
    node("s4", 120, 100, 100, "B5", "controller board", POWER, POWER_T)
    node("s5", 240, 100, 100, "B6", "Stage 0 rig · G2", DATA, DATA_T)
    node("s6", 480, 40, 90, "B7", "car install · G3", DATA, DATA_T)
    node("s7", 580, 40, 92, "B8", "Stage 1 rig · G4", LIGHT, LIGHT_T)
    node("s8", 240, 170, 100, "B9", "PGU, backlight · G5", LIGHT, LIGHT_T)
    node("s9", 120, 240, 100, "B10", "mirror, fold, filters", LIGHT, LIGHT_T, True)
    node("s9b", 240, 240, 100, "mirror lead time", "unquoted", LIGHT, SURF, True)
    node("s10", 360, 240, 100, "B11", "print the housing", STEEL, GREY_T)
    node("s11", 480, 240, 90, "B12", "optics, first light", LIGHT, LIGHT_T, True)
    node("s12", 580, 240, 92, "B13", "Stage 2 · G6", LIGHT, LIGHT_T, True)
    node("s13", 580, 320, 92, "B14", "rehearsal · G7", INK2, GREY_T)
    for a, b in [("s0", "s1"), ("s1", "s2"), ("s2", "s3"), ("s3", "s6"), ("s6", "s7"), ("s0", "s4"), ("s4", "s5"),
                 ("s0", "s8"), ("s0", "s9"), ("s9", "s9b"), ("s9b", "s10"), ("s10", "s11"), ("s11", "s12")]:
        edge(a, b)
    # extra dependencies drawn as notes
    s.path(f"M290,140 L290,170", stroke=INK2, sw=1); s.arrow(290, 160, 290, 168, color=INK2, sw=1)
    s.path(f"M340,190 L525,190 L525,236", stroke=INK2, sw=1); s.arrow(525, 228, 525, 238, color=INK2, sw=1)
    s.path(f"M626,82 L626,236", stroke=INK2, sw=1, extra='stroke-dasharray="3 3"')
    s.path(f"M626,282 L626,318", stroke=INK2, sw=1); s.arrow(626, 310, 626, 318, color=INK2, sw=1)
    s.path(f"M290,140 L290,140", stroke=INK2, sw=1)
    s.lines(10, 312, ["Thick black outline: the optics critical path. The car fixes the windshield, the windshield",
                      "fixes the ray trace, the trace fixes the mirror, and the mirror's lead time fixes the daylight date.",
                      "Software stages (blue) need only a camera and a seat, so they run in parallel from week 1. B1 includes the trace.",
                      "G1 to G7 are the plan's gates; a stage is finished when its gate passes."], size=9.4, fill=INK2, lh=13.5)
    note(s, 10, 18, "Build stages B1 to B14, left to right in time; arrows point from a prerequisite to the stage that needs it.", size=9.6, fill=INK, weight=600)
    return s


# =====================================================================================================
@fig("g_polar")
def g_polar():
    W, H = 680, 230
    s = Svg(W, H, "Polarisation through the HUD: panel axis, half-wave retarder, s at the windshield, dust-cover pass axis")
    s.rect(0, 0, W, H, fill=SURF)
    def disc(cx, cy, ang, title, sub, col=LIGHT, extra_axis=None):
        s.circle(cx, cy, 34, fill=SURF, stroke=AXIS, sw=1)
        dx, dy = 30 * math.cos(math.radians(ang)), -30 * math.sin(math.radians(ang))
        s.line(cx - dx, cy - dy, cx + dx, cy + dy, stroke=col, sw=2.6)
        if extra_axis is not None:
            ex, ey = 30 * math.cos(math.radians(extra_axis)), -30 * math.sin(math.radians(extra_axis))
            s.line(cx - ex, cy - ey, cx + ex, cy + ey, stroke=EYEC, sw=1.2, extra='stroke-dasharray="4 3"')
        s.text(cx, cy + 52, title, size=9.8, fill=INK, anchor="middle", weight=650)
        for i, l in enumerate(sub):
            s.text(cx, cy + 66 + i * 12, l, size=9, fill=INK2, anchor="middle")
    disc(70, 70, 45, "panel output", ["often 45° to the edges", "(measure it)"])
    s.arrow(110, 70, 160, 70, color=INK2, sw=1)
    disc(200, 70, 0, "after retarder", ["fast axis 67.5° (dashed):", "2 × 67.5 − 45 = 90"], extra_axis=22.5)
    s.arrow(240, 70, 290, 70, color=INK2, sw=1)
    disc(330, 70, 0, "after fold and mirror", ["s stays s: all planes of", "incidence are the side plane"])
    s.arrow(370, 70, 420, 70, color=INK2, sw=1)
    disc(460, 70, 0, "s at the windshield", ["across the car, horizontal", "(23.6% reflects; p: 1.2%)"], col=LIGHT)
    s.arrow(500, 70, 550, 70, color=INK2, sw=1)
    disc(590, 70, 0, "dust-cover polariser", ["pass axis across the car;", "halves unpolarised sun"], col=SUN)
    note(s, 12, 215, "Each disc looks along the light; horizontal is across the car. Angles are measured from the fore-aft axis, so across the car is 90°.", size=9.2, fill=MUTED)
    note(s, 12, 227, "A half-wave film turns an input at angle a into 2f − a, f being its fast axis. If the panel already emits at 90°, leave the retarder out.", size=9.2, fill=MUTED)
    return s


# =====================================================================================================
@fig("g_cabin")
def g_cabin():
    """Top view of the front of the cabin (left-hand drive), schematic: where each part goes and how cables run."""
    W, H = 680, 420
    s = Svg(W, H, "Top view of the cabin: positions of every installed part and the cable routes")
    s.rect(0, 0, W, H, fill=SURF)
    # car outline: forward is up
    cx0, cx1 = 150, 530
    s.path(f"M{cx0},400 L{cx0},120 Q{cx0},70 {cx0+40},60 L{cx1-40},60 Q{cx1},70 {cx1},120 L{cx1},400", stroke=STEEL, sw=2)
    # windshield band and dash
    s.path(f"M{cx0+12},110 Q340,78 {cx1-12},110", stroke=GLASS, sw=6, extra='stroke-opacity="0.7"')
    note(s, 340, 74, "windshield", size=9.5, anchor="middle")
    s.rect(cx0 + 10, 118, cx1 - cx0 - 20, 52, fill="#ecebe7", stroke=STEEL, sw=1, rx=6)
    note(s, cx1 - 16, 166, "dash", size=9, anchor="end")
    # seats
    for x in (205, 395):
        s.rect(x, 250, 80, 90, fill="#e9e7e1", stroke=STEEL, sw=1, rx=10)
    note(s, 245, 352, "driver", size=9.5, anchor="middle")
    note(s, 435, 352, "passenger", size=9.5, anchor="middle")
    # steering wheel
    s.path("M215,212 Q245,196 275,212", stroke=DARK, sw=4)
    # HUD housing in front of the driver
    s.rect(222, 120, 46, 40, fill="#cfcec8", stroke=INK, sw=1.2, rx=3)
    # road camera at mirror stalk (centre)
    s.rect(330, 92, 22, 9, fill=DARK, rx=2)
    # GNSS antenna on dash near glass, right of centre
    s.circle(300, 124, 5, fill=DARK)
    # OAK-D on column
    s.rect(237, 192, 16, 8, fill=DARK, rx=2)
    # controller and LED driver beside the housing
    s.rect(272, 140, 18, 14, fill=DARK, rx=2)
    s.rect(272, 124, 18, 12, fill=DARK, rx=2)
    # footwell plate (passenger): Jetson, GNSS board, switch, DC-DC
    s.rect(400, 186, 70, 50, fill="#d9d8d3", stroke=INK2, sw=1, rx=3)
    s.rect(406, 192, 34, 22, fill=DARK, rx=2)
    s.rect(444, 192, 20, 12, fill=DARK, rx=2)
    s.rect(444, 208, 20, 10, fill=DARK, rx=2)
    s.rect(406, 218, 24, 12, fill=DARK, rx=2)
    # console socket and audience side
    s.rect(330, 236, 18, 18, fill="none", stroke=POWER, sw=1.6, rx=3)
    s.rect(410, 376, 50, 16, fill=DARK, rx=2)   # monitor 2 on headrest back
    s.rect(470, 376, 28, 16, fill=DARK, rx=2)   # mini PC 2
    # cables: data blue, power red
    polyline(s, [(341, 101), (341, 104), (520, 104), (520, 170), (470, 200)], DATA, 1.3)        # ZED along header/A-pillar
    polyline(s, [(245, 200), (245, 228), (300, 228), (300, 205), (406, 205)], DATA, 1.3)        # OAK-D under dash
    polyline(s, [(268, 140), (300, 160), (380, 175), (406, 196)], DATA, 1.3)                     # HDMI and USB from HUD
    polyline(s, [(300, 129), (318, 150), (384, 182), (444, 198)], DATA, 1.0)                     # antenna cable
    polyline(s, [(470, 230), (470, 300), (485, 376)], DATA, 1.3)                                 # Ethernet to mini PC 2
    polyline(s, [(339, 245), (360, 245), (418, 228)], POWER, 1.6)                                # 12 V to DC-DC
    polyline(s, [(418, 222), (380, 180), (281, 132)], POWER, 1.2)                                # LED driver feed
    polyline(s, [(339, 254), (339, 300), (430, 376)], POWER, 1.6)                                # second feed to PD charger
    def lab(px, py, tx, ty, text, anchor="start"):
        leader(s, tx, ty, px, py)
        s.text(tx + (4 if anchor == "start" else -4), ty + 4, text, size=9.6, fill=INK, anchor=anchor)
    lab(341, 92, 545, 40, "road camera, mirror stalk")
    lab(245, 120, 140, 40, "HUD housing on the dash", "end")
    lab(300, 120, 545, 80, "GNSS antenna")
    lab(281, 130, 545, 120, "LED driver, controller")
    lab(245, 196, 140, 196, "driver camera, column", "end")
    lab(470, 203, 545, 200, "footwell plate: Jetson,")
    note(s, 549, 216, "GNSS board, switch, DC-DC", size=9.6, fill=INK)
    lab(339, 245, 140, 260, "12 V socket, fused (feed 1)", "end")
    lab(339, 254, 140, 300, "second socket (feed 2)", "end")
    lab(485, 384, 545, 384, "monitor 2, mini PC 2")
    note(s, 12, 16, "Schematic top view, forward is up, left-hand drive. Blue: data cables. Red: 12 V power. Nothing is wired into the car beyond the sockets.", size=9.3, fill=MUTED)
    return s


# =====================================================================================================
@fig("g_controller")
def g_controller():
    """HUD controller schematic: Pico, sensors, the two LED-driver channels, servo, power."""
    W, H = 680, 470
    s = Svg(W, H, "HUD controller wiring: Raspberry Pi Pico, light sensor, thermocouple amplifier, NTC, two LED-driver channels, servo")
    s.rect(0, 0, W, H, fill=SURF)
    # Pico in the middle
    px, py, pw, ph = 250, 60, 150, 345
    s.rect(px, py, pw, ph, fill="#e6e2d2", stroke=INK, sw=1.2, rx=4)
    s.text(px + pw / 2, py + 20, "Raspberry Pi Pico", size=11, weight=650, fill=INK, anchor="middle")
    left = [("GP4 · pin 6", "I²C0 SDA", 90), ("GP5 · pin 7", "I²C0 SCL", 108), ("GP18 · pin 24", "SPI0 SCK", 150), ("GP16 · pin 21", "SPI0 RX", 168),
            ("GP17 · pin 22", "SPI0 CS", 186), ("GP26 · pin 31", "ADC0", 228), ("ADC_VREF · 35", "", 246), ("AGND · pin 33", "", 264)]
    right = [("pin 19 · GP14", "string A level", 90), ("pin 20 · GP15", "string A enable", 108), ("pin 16 · GP12", "string B level", 150),
             ("pin 17 · GP13", "string B enable", 168), ("pin 29 · GP22", "servo signal", 228), ("pin 39 · VSYS", "5 V in", 300), ("pin 38 · GND", "", 318)]
    for lab_, fn, y in left:
        s.line(px - 20, py + y, px, py + y, stroke=INK2, sw=1)
        s.text(px + 6, py + y + 3.5, lab_, size=8.8, fill=INK)
    for lab_, fn, y in right:
        s.line(px + pw, py + y, px + pw + 20, py + y, stroke=INK2, sw=1)
        s.text(px + pw - 6, py + y + 3.5, lab_, size=8.8, fill=INK, anchor="end")
    s.text(px + pw / 2, py + ph - 10, "USB to the Jetson (serial)", size=8.8, fill=DATA, anchor="middle")
    s.line(px + pw / 2, py + ph, px + pw / 2, py + ph + 30, stroke=DATA, sw=1.6)
    # left side devices
    box(s, 20, py + 70, 190, 50, "TSL2591 light sensor", ["I²C 0x29, 3V3, in the lid pod"], fill=GREY_T)
    s.line(210, py + 95, px - 20, py + 90, stroke=DATA, sw=1); s.line(210, py + 100, px - 20, py + 108, stroke=DATA, sw=1)
    box(s, 20, py + 135, 190, 60, "MAX31855K + type-K", ["SPI read-only, 3V3", "bead at the panel for tests"], fill=SUN_T, stroke=SUN)
    for yy, ty in ((py + 150, py + 150), (py + 165, py + 168), (py + 180, py + 186)):
        s.line(210, yy, px - 20, ty, stroke=DATA, sw=1)
    # NTC divider
    s.text(20, py + 222, "NTC divider (cell temperature)", size=9.6, weight=650, fill=INK)
    s.lines(20, py + 238, ["ADC_VREF to 10 kΩ 0.1% to ADC0;", "ADC0 to 10 kΩ NTC (on the cell) to AGND;", "100 nF from ADC0 to AGND"], size=8.8, fill=INK2, lh=12)
    s.line(215, py + 228, px - 20, py + 228, stroke=POWER, sw=1)
    # right side: two LED channels
    def channel(y0, name):
        x0 = 440
        s.rect(x0, y0, 220, 112, fill=POWER_T, stroke=POWER, sw=1, rx=4)
        s.text(x0 + 8, y0 + 16, f"LED channel {name}: RECOM RCD-24", size=9.6, weight=650, fill=INK)
        s.lines(x0 + 8, y0 + 32, ["level: PWM 25 kHz, two RC stages", "(10 kΩ, 1 µF), op-amp ×1.33 on 5 V,", "to pin 2 analogue (0.13 V full, 4.2 V off)",
                                  "enable: an NPN pulls pin 3 low;", "4.7 kΩ pull-up to 5 V holds it off", "+Vin 16 V, 4 LEDs in series, 0.5 A"], size=8.6, fill=INK2, lh=12)
    channel(py + 72, "A")
    channel(py + 190, "B")
    s.line(px + pw + 20, py + 90, 440, py + 100, stroke=POWER, sw=1); s.line(px + pw + 20, py + 108, 440, py + 140, stroke=POWER, sw=1)
    s.line(px + pw + 20, py + 150, 440, py + 218, stroke=POWER, sw=1); s.line(px + pw + 20, py + 168, 440, py + 258, stroke=POWER, sw=1)
    # servo and power
    box(s, 440, py + 318, 220, 46, "SG90 shutter servo", ["signal GP22; 5 V from the buck, 470 µF"], fill=GREY_T)
    s.line(px + pw + 20, py + 228, 425, py + 228, stroke=INK2, sw=1)
    s.path(f"M425,{py+228} L425,{py+340} L440,{py+340}", stroke=INK2, sw=1)
    box(s, 20, py + 318, 190, 46, "5 V, 5 A buck from 16 V", ["VSYS via a Schottky diode"], fill=POWER_T, stroke=POWER)
    s.path(f"M210,{py+341} L232,{py+341} L232,{py+300} L{px},{py+300}", stroke=POWER, sw=1.2)
    s.path(f"M{px+pw+20},{py+300} L{px+pw+20},{py+300}", stroke=POWER, sw=1)
    note(s, 12, 18, "Pin numbers are the Pico's physical pins. Grounds are common. Both LED channels default to off: an unpowered or resetting Pico leaves", size=9.2, fill=MUTED)
    note(s, 12, 31, "the enable MOSFETs off, so the pull-ups hold the drivers' PWM/ON/OFF pins high. The analogue level is inverted: higher voltage, dimmer.", size=9.2, fill=MUTED)
    return s


# =====================================================================================================
@fig("g_power2")
def g_power2():
    """Power and data wiring in the car."""
    W, H = 680, 420
    s = Svg(W, H, "Power and data wiring in the car: two fused feeds, the ignition-sensed converter, the 16 V and 5 V rails, data links")
    s.rect(0, 0, W, H, fill=SURF)
    # feed 1
    box(s, 12, 50, 130, 50, "Always-live 12 V", ["socket, fused 10 A"], fill=POWER_T, stroke=POWER)
    box(s, 12, 112, 130, 50, "Switched 12 V", ["socket (ignition)"], fill=POWER_T, stroke=POWER)
    box(s, 175, 70, 150, 76, "Mini-Box DCDC-USB-200", ["Automotive mode, 16 V out", "VIN, IGN, GND in; J8 pulse", "1 min off delay, 1 min hard off"], fill=SURF, stroke=POWER, sw=1.4)
    s.arrow(142, 75, 175, 90, color=POWER, sw=1.6); note(s, 150, 72, "VIN", size=8.6)
    s.arrow(142, 137, 175, 126, color=POWER, sw=1.2); note(s, 150, 146, "IGN", size=8.6)
    # rails
    box(s, 370, 24, 140, 54, "Jetson J4012", ["16 V, 5.5 × 2.5 mm plug", "J8 pulse to button pins 1–2"], fill=DATA_T, stroke=DATA)
    box(s, 370, 92, 140, 46, "LED channels A and B", ["RCD-24 ×2, 16 V in"], fill=POWER_T, stroke=POWER)
    box(s, 370, 154, 140, 46, "5 V, 5 A buck", ["the 5 V loads at right"], fill=POWER_T, stroke=POWER)
    for yy in (53, 115, 177):
        s.arrow(325, 108, 370, yy, color=POWER, sw=1.4)
    s.path("M355,88 L355,88", stroke=POWER)
    note(s, 333, 99, "16 V", size=8.6, fill=INK)
    # 5 V loads
    loads = [("panel board (USB 5 V)", 545, 150), ("Pico VSYS", 545, 172), ("servo", 545, 194), ("fan", 545, 216), ("OAK-D Y-adapter power", 545, 238)]
    for t_, x, y in loads:
        s.line(510, 177, x - 5, y - 4, stroke=POWER, sw=0.8)
        note(s, x, y, t_, size=8.8, fill=INK)
    # data
    s.text(12, 268, "Data", size=10.5, weight=650, fill=INK)
    data = [("ZED 2i", "USB 3, 1.5 or 3 m Stereolabs cable", 290), ("OAK-D Pro", "USB-C data leg of the Y-adapter", 310), ("ZED-F9R", "USB-C", 330),
            ("HUD controller (Pico)", "USB serial", 350), ("Panel board", "HDMI from the J4012's only HDMI port", 370), ("Mini PC 2", "Ethernet through the switch (MJPEG audience stream)", 390)]
    for a, b_, y in data:
        s.text(30, y, a, size=9.2, fill=INK, weight=600)
        s.arrow(170, y - 3, 220, y - 3, color=DATA, sw=1.2)
        s.text(228, y, b_, size=9.2, fill=INK2)
    s.text(420, 268, "Feed 2 (audience side)", size=10.5, weight=650, fill=INK)
    s.lines(420, 288, ["Second 12 V socket, its own fuse", "USB-C PD charger, 100 W", "mini PC 2 and monitor 2", "gigabit switch (Jetson port 1, PC port 2)"], size=9.2, fill=INK2, lh=14)
    note(s, 12, 18, "Red: power. Blue: data. The only connections to the car are the two accessory sockets. Wire sizes and fuses: Appendix A.", size=9.3, fill=MUTED)
    return s
