"""Chapters 1-4: concept, architecture, transport, timing, latency, prediction, parallax."""
import math
from svgkit import *
from calc import V, LAT, LAT_MIN, LAT_MAX, PAR, V_EGO, T_AGE, H_CAM, DEP0, DEP1

# ---------- perspective helpers for the driver's-eye mockups ----------
def proj(X, Z, cx, cy, f, h=H_CAM):
    return cx + f * X / Z, cy + f * h / Z

def path_centerline(Z):
    return 0.6 * (Z / 40.0) ** 2          # gentle right-hand curve, metres

def draw_road(s, W, H, cx, cy, f):
    s.rect(0, 0, W, cy, fill=GREY_T)                       # sky / horizon band
    s.poly([(0, cy), (W, cy), (W, H), (0, H)], fill="#e7e6e1")
    # road edges (ego lane edges at ±1.85 m) and lane marks
    for X in (-5.5, 5.5):
        pts = [proj(X, Z, cx, cy, f) for Z in (10, 14, 20, 30, 45, 70)]
        s.path("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts), stroke=MUTED, sw=1.2)
    for X in (-1.85, 1.85):
        pts = [proj(X, Z, cx, cy, f) for Z in (10, 14, 20, 30, 45, 70)]
        s.path("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts), stroke=SURF, sw=3.2)

def drive_path(s, cx, cy, f, fill=GREEN, op=0.38):
    zs = [10 + i * 2.5 for i in range(21)]
    left = [proj(path_centerline(Z) - 0.9, Z, cx, cy, f) for Z in zs]
    right = [proj(path_centerline(Z) + 0.9, Z, cx, cy, f) for Z in reversed(zs)]
    s.poly(left + right, fill=fill, extra=f'fill-opacity="{op}"')
    s.path("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in left), stroke=fill, sw=2)
    s.path("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in right), stroke=fill, sw=2)

def lead_car(s, cx, cy, f, Z=32.0):
    xl, yb = proj(-0.9, Z, cx, cy, f, h=H_CAM)
    xr, _ = proj(0.9, Z, cx, cy, f, h=H_CAM)
    _, yt = proj(0, Z, cx, cy, f, h=H_CAM - 1.5)
    s.rect(xl, yt, xr - xl, yb - yt, fill="#3a3a38", rx=5)
    s.rect(xl + 6, yt + 6, xr - xl - 12, (yb - yt) * 0.36, fill="#6c6b66", rx=3)
    s.poly([(xl, yb + 7), ((xl + xr) / 2, yb + 17), (xr, yb + 7),
            (xr, yb + 11), ((xl + xr) / 2, yb + 21), (xl, yb + 11)], fill=INK)
    return xl, yb, xr, yt

@fig("cover")
def f_cover():
    W, H = 680, 330
    cx, cy, f = 340, 150, 1475
    s = Svg(W, H, "Driver's-eye mockup of the HUD window, illustrative")
    s.rect(0, 0, W, H, fill=GREY_T)
    draw_road(s, W, H, cx, cy, f)
    drive_path(s, cx, cy, f)
    lead_car(s, cx, cy, f)
    # hazard outline (perceptd, HUD-only)
    hx, hy = proj(3.2, 20, cx, cy, f)
    hw = 0.3 * f / 20
    s.rect(hx - hw, hy - 1.7 * f / 20, 2 * hw, 1.7 * f / 20, fill="none", stroke=ORANGE, sw=2.2, rx=3)
    # speed block (fixed, not registered)
    s.rect(18, 262, 150, 52, fill=INK, rx=8)
    s.text(30, 300, "62", size=30, weight=600, fill=SURF)
    s.text(108, 283, "SET 65", size=12, weight=500, fill=SURF)
    s.text(108, 298, "engaged", size=11, weight=400, fill="#9ad3b8")
    s.rect(2, 2, W - 4, H - 4, fill="none", stroke=INK2, sw=1.2, rx=6)
    s.pill(W - 18, 26, "Illustrative only · not measured", size=10.5, anchor="end")
    return s

@fig("mockup")
def f_mockup():
    W, H = 680, 360
    cx, cy, f = 340, 150, 1475
    s = Svg(W, H, "Demo window mockup with five labelled elements")
    s.rect(0, 0, W, H, fill=SURF)
    s.rect(14, 14, W - 28, 300, fill=GREY_T)
    draw_road(s, W - 28, 300, cx - 14, cy - 14, f)
    drive_path(s, cx - 14, cy - 14, f)
    lead_car(s, cx - 14, cy - 14, f)
    hx, hy = proj(3.2, 20, cx - 14, cy - 14, f)
    hw = 0.3 * f / 20
    s.rect(hx - hw, hy - 1.7 * f / 20, 2 * hw, 1.7 * f / 20, fill="none", stroke=ORANGE, sw=2.2, rx=3)
    s.rect(32, 262, 150, 40, fill=INK, rx=8)
    s.text(44, 290, "62 · SET 65", size=15, weight=600, fill=SURF)
    s.rect(14, 14, W - 28, 300, fill="none", stroke=INK2, sw=1.2)
    # callouts: pills with leaders to their targets
    lx, ly = proj(-1.85, 14, cx - 14, cy - 14, f)
    s.pill(30, 46, "lane lines fade with confidence", size=11)
    s.line(60, 52, lx, ly, stroke=INK2, sw=1)
    lpx, lpy = proj(path_centerline(30), 30, cx - 14, cy - 14, f)
    s.pill(330, 344, "drive path, green when engaged", size=11)
    s.line(330, 330, lpx, lpy + 6, stroke=INK2, sw=1)
    s.pill(650, 46, "lead chevron under the bumper", size=11, anchor="end")
    s.line(560, 52, 388, 216, stroke=INK2, sw=1)
    s.pill(650, 262, "hazard outline, HUD-only", size=11, anchor="end")
    s.line(560, 262, 602, 196, stroke=INK2, sw=1)
    s.pill(190, 296, "speed block, fixed", size=11)
    return s

@fig("concept")
def f_concept():
    W, H = 680, 250
    s = Svg(W, H, "Side view: where a virtual image lies relative to road points")
    s.rect(0, 0, W, H, fill=SURF)
    gy = 220
    s.line(40, gy, W - 20, gy, stroke=INK2, sw=1.2)
    s.text(W - 22, gy + 16, "road surface", size=11, fill=INK2, anchor="end")
    eye = (70, 150)
    s.line(150, 46, 180, 190, stroke=BLUE, sw=2.2)
    s.text(146, 36, "windshield", size=11, fill=INK2)
    vx = 330
    s.line(vx, 58, vx, gy, stroke=ORANGE, sw=2)
    s.text(vx, 46, "virtual image plane, 7.5 m", size=11.5, weight=600, fill=INK, anchor="middle")
    pts = []
    for xa, label in ((430, "road point, 10 m"), (600, "road point, 30 m")):
        s.circle(xa, gy, 5, fill=INK)
        s.text(xa, gy + 18, label, size=11, fill=INK, anchor="middle")
        s.line(eye[0], eye[1], xa, gy, stroke=MUTED, sw=1)
        yc = eye[1] + (vx - eye[0]) / (xa - eye[0]) * (gy - eye[1])
        s.circle(vx, yc, 5.5, fill=ORANGE, stroke=SURF, sw=2)
        pts.append((xa, yc))
    s.circle(eye[0], eye[1], 9, fill=INK)
    s.text(eye[0], eye[1] - 16, "eye", size=11, fill=INK, anchor="middle")
    s.text(24, 184, "driver's eye, 1.22 m", size=11, fill=INK2)
    # labels for the two content marks, placed right of the plane with short leaders
    (x10, y10), (x30, y30) = pts
    s.text(346, 118, "30 m point: content at 0.9 m above road", size=11.5, fill=INK)
    s.line(344, 122, x30 + 4, y30 - 4, stroke=INK2, sw=1)
    s.text(346, 160, "10 m point: content at 0.3 m above road", size=11.5, fill=INK)
    s.line(344, 164, x10 + 4, y10 - 4, stroke=INK2, sw=1)
    s.text(14, 20, "Schematic. Positions are not to scale. Heights are true-geometry values.", size=10, fill=MUTED)
    return s

@fig("arch")
def f_arch():
    W, H = 680, 330
    s = Svg(W, H, "Two-computer architecture: one-way data flow from the driving computer to the HUD computer to the optics")
    s.rect(0, 0, W, H, fill=SURF)
    # left: driving computer
    s.rect(14, 16, 226, 262, fill=BLUE_T, stroke=BLUE, sw=1.2, rx=6)
    s.rect(14, 16, 226, 30, fill=BLUE, rx=6)
    s.rect(14, 34, 226, 12, fill=BLUE)
    s.text(26, 37, "Driving computer · comma four", size=12.5, weight=700, fill=SURF)
    s.lines(26, 70, ["camerad to modeld (Qualcomm)", "plannerd · controlsd · card", "pandad / panda (SPI)"], size=11.5)
    s.rect(24, 108, 206, 1, fill=BLUE)
    s.lines(26, 130, ["bridge (msgq to ZMQ)", "publishes modelV2 at 20 Hz,", "radarState, carState,", "controlsState, selfdriveState,", "extrinsicsCalibration, deviceState,", "pandaStates"], size=11.5, weight=400)
    s.text(26, 254, "Car CAN bus; panda enforces limits", size=11, fill=INK2)
    s.text(26, 268, "in firmware, on every frame", size=11, fill=INK2)
    # middle: HUD computer
    s.rect(300, 16, 230, 262, fill=GREEN_T, stroke=GREEN, sw=1.2, rx=6)
    s.rect(300, 16, 230, 30, fill=GREEN, rx=6)
    s.rect(300, 34, 230, 12, fill=GREEN)
    s.text(312, 37, "HUD computer · Jetson Orin NX", size=12.5, weight=700, fill=SURF)
    s.lines(312, 70, ["bridge <ip> <whitelist>", "(ZMQ to msgq)"], size=11.5, weight=600)
    s.lines(312, 112, ["hudd: eye-frame projection", "headtrackd: OAK-D + MediaPipe", "perceptd: TensorRT 10 detector", "hudmirror: audience view"], size=11.5)
    s.text(312, 240, "4K60 out over HDMI", size=11.5, fill=INK2)
    # right: optics
    s.rect(560, 16, 106, 262, fill=ORANGE_T, stroke=ORANGE, sw=1.2, rx=6)
    s.rect(560, 16, 106, 30, fill=ORANGE, rx=6)
    s.rect(560, 34, 106, 12, fill=ORANGE)
    s.text(568, 37, "Optics", size=12.5, weight=700, fill=INK)
    s.lines(570, 70, ["PGU (laser", "DLP on a", "diffuser)", "", "fold mirror", "", "concave", "mirror", "f ≈ 330 mm", "", "windshield", "(wedge PVB)", "", "image at", "7.5 m"], size=11, lh=14.5)
    # arrows
    s.arrow(240, 150, 300, 150, color=INK, sw=2)
    s.text(270, 138, "Ethernet", size=11, fill=INK, anchor="middle")
    s.text(270, 170, "one way", size=11, fill=INK2, anchor="middle")
    s.arrow(530, 240, 560, 240, color=INK, sw=2)
    # no-path marker
    s.text(14, H - 30, "No path from the Jetson to the car's CAN bus. The HUD cannot send a control message.", size=11.5, fill=INK, weight=600)
    s.text(14, H - 12, "Drawn to scale: no. Arrows show the only data paths.", size=10.5, fill=MUTED)
    return s

@fig("safety")
def f_safety():
    W, H = 680, 290
    s = Svg(W, H, "Safety boundary: the control path and the HUD path meet only at a one-way link")
    s.rect(0, 0, W, H, fill=SURF)
    s.text(14, 22, "CONTROL PATH · drives the car", size=11.5, weight=700, fill=BLUE)
    row = ["controlsd", "card", "pandad", "panda", "CAN bus"]
    x = 14
    ws = [122, 102, 112, 104, 104]
    for i, (lab, w) in enumerate(zip(row, ws)):
        s.rect(x, 34, w, 40, fill=BLUE_T, stroke=BLUE, sw=1.2, rx=6)
        s.text(x + w / 2, 59, lab, size=12, weight=600, fill=INK, anchor="middle")
        if i < len(row) - 1:
            s.arrow(x + w + 2, 54, x + w + 22, 54, color=BLUE, sw=2)
        x += w + 24
    s.text(14, 96, "The panda checks every frame against the car's safety model before it goes out.", size=11, fill=INK2)
    # wall
    s.line(14, 130, W - 14, 130, stroke=CRIT, sw=3)
    s.rect(W / 2 - 150, 116, 300, 26, fill=SURF, stroke="none")
    s.text(W / 2, 134, "hardware boundary · no link from HUD to CAN", size=11.5, weight=700, fill=CRIT, anchor="middle")
    s.text(14, 168, "HUD PATH · draws only, never sends control", size=11.5, weight=700, fill=GREEN)
    row2 = ["bridge (subscribe)", "hudd", "PGU / monitor"]
    ws2 = [190, 150, 170]
    x = 14
    for i, (lab, w) in enumerate(zip(row2, ws2)):
        s.rect(x, 180, w, 40, fill=GREEN_T, stroke=GREEN, sw=1.2, rx=6)
        s.text(x + w / 2, 205, lab, size=12, weight=600, fill=INK, anchor="middle")
        if i < len(row2) - 1:
            s.arrow(x + w + 2, 200, x + w + 22, 200, color=GREEN, sw=2)
        x += w + 24
    s.text(14, 246, "The Jetson receives a copy of messages over Ethernet. Nothing it does can reach the panda.", size=11, fill=INK2)
    s.text(14, 268, "Power-cycling the Jetson mid-drive leaves openpilot unaffected (validation criterion).", size=11, fill=INK2)
    return s

@fig("transport")
def f_transport():
    W, H = 680, 250
    s = Svg(W, H, "Message transport: msgq on the comma four, ZMQ over Ethernet, msgq on the Jetson")
    s.rect(0, 0, W, H, fill=SURF)
    s.rect(14, 22, 200, 200, fill=BLUE_T, stroke=BLUE, sw=1.2, rx=6)
    s.text(26, 44, "comma four", size=12.5, weight=700, fill=INK)
    s.lines(26, 66, ["modelV2  (msgq)", "carState  (msgq)", "radarState  (msgq)", "…every service", "in cereal/services.py"], size=11.5)
    s.rect(246, 22, 170, 200, fill=BLUE_T, stroke=BLUE, sw=1.2, rx=6)
    s.text(258, 44, "bridge (send)", size=12, weight=700, fill=INK)
    s.lines(258, 66, ["subscribes msgq", "publishes ZMQ", "one port per", "service name"], size=11.5)
    s.text(258, 150, "port = hash(service name)", size=11, fill=INK2)
    s.text(258, 166, "known FIXME in source", size=11, fill=INK2)
    s.arrow(446, 122, 488, 122, color=INK, sw=2)
    s.text(467, 108, "Ethernet", size=11, fill=INK, anchor="middle")
    s.text(467, 144, "ZMQ", size=11, fill=INK2, anchor="middle")
    s.rect(492, 22, 174, 200, fill=GREEN_T, stroke=GREEN, sw=1.2, rx=6)
    s.text(504, 44, "bridge (receive)", size=12, weight=700, fill=INK)
    s.lines(504, 66, ["bridge <ip> <whitelist>", "subscribes ZMQ", "republishes msgq", "whitelist match:", "service name in", "the list string"], size=11.5)
    s.text(W / 2, H - 6, "hudd uses a plain SubMaster on the Jetson. No change to the message code is needed.", size=11, fill=INK2, anchor="middle")
    return s

@fig("rates")
def f_rates():
    W, H = 680, 300
    s = Svg(W, H, "Message rates for the services hudd reads, drawn over one second")
    s.rect(0, 0, W, H, fill=SURF)
    rows = [("deviceState", 2), ("extrinsicsCalibration", 4), ("pandaStates", 10),
            ("modelV2", 20), ("radarState", 20), ("longitudinalPlan", 20),
            ("controlsState", 100), ("selfdriveState", 100), ("carState", 100)]
    x0, x1 = 210, 600
    top = 20; rh = 26
    for i, (name, hz) in enumerate(rows):
        y = top + i * rh + 12
        s.text(x0 - 12, y + 4, name, size=11.5, fill=INK, anchor="end")
        s.rect(x0, y - 8, x1 - x0, 16, fill="#f3f2ee")
        n = hz
        for k in range(n):
            t = k / hz
            xx = x0 + t * (x1 - x0)
            s.rect(xx - 1, y - 7, 2, 14, fill=BLUE)
        s.text(x1 + 10, y + 4, f"{hz} Hz", size=11.5, fill=INK2)
    yb = top + len(rows) * rh + 4
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        xx = x0 + t * (x1 - x0)
        s.line(xx, yb, xx, yb + 5, stroke=AXIS, sw=1)
        s.text(xx, yb + 18, f"{t:.2f} s" if t else "0", size=11, fill=INK2, anchor="middle")
    s.text(W - 14, H - 10, "Each tick is one message. The model and the car bus arrive on different clocks.", size=10.5, fill=MUTED, anchor="end")
    return s

@fig("latency")
def f_latency():
    W, H = 680, 330
    s = Svg(W, H, "Latency budget as horizontal range bars from minimum to maximum")
    s.rect(0, 0, W, H, fill=SURF)
    x0, x1 = 300, 640
    vmax = 160.0
    sx = lambda v: x0 + v / vmax * (x1 - x0)
    rows = [(n, a, b, BLUE) for n, a, b in LAT]
    rows.append(("Total, uncompensated", LAT_MIN, LAT_MAX, INK))
    rows.append(("Head tracker (parallax only)", 30, 50, MUTED))
    top = 30; rh = 40
    for t in range(0, 161, 20):
        xx = sx(t)
        s.line(xx, top - 8, xx, top + rh * len(rows) - 6, stroke=GRID, sw=1)
        s.text(xx, top + rh * len(rows) + 6, f"{t}", size=11, fill=INK2, anchor="middle")
    s.text(x1 + 26, top + rh * len(rows) + 18, "ms", size=11, fill=INK2, anchor="start")
    for i, (name, a, b, col) in enumerate(rows):
        y = top + i * rh
        if name.startswith("Total"):
            s.line(14, y - 8, W - 14, y - 8, stroke=AXIS, sw=1)
        s.text(290, y + 5, name, size=12, weight=600 if name.startswith("Total") else 400, fill=INK, anchor="end")
        s.rect(sx(a), y - 8, sx(b) - sx(a), 16, fill=col, rx=4)
        s.text(sx(b) + 8, y + 5, f"{a}–{b} ms", size=11.5, fill=INK2)
    s.text(14, H - 8, "The plan rounds the total to 70–140 ms. The exact sums of the stage ranges are shown.", size=10.5, fill=MUTED)
    return s

@fig("prediction")
def f_prediction():
    W, H = 680, 262
    s = Svg(W, H, "Side view of the camera moving 3 m in 100 ms while sighting a road point 10 m ahead")
    s.rect(0, 0, W, H, fill=SURF)
    k = 46.7                       # px per metre, true scale both axes
    x0, gy = 40, 178
    s.line(20, gy, W - 20, gy, stroke=INK2, sw=1.2)
    s.text(W - 20, gy + 16, "road", size=11, fill=INK2, anchor="end")
    cam_h = H_CAM * k
    c0 = (x0, gy - cam_h)
    c1 = (x0 + 3.0 * k, gy - cam_h)
    P = (x0 + 10 * k, gy)
    for c, lab in ((c0, "camera at t0"), (c1, "camera at t0 + 100 ms")):
        s.rect(c[0] - 7, c[1] - 7, 14, 14, fill=INK, rx=2)
        s.text(c[0], c[1] - 16, lab, size=11, fill=INK, anchor="middle")
    s.arrow(c0[0], c0[1] + 24, c1[0], c1[1] + 24, color=INK2, sw=1.5)
    s.text((c0[0] + c1[0]) / 2, c1[1] + 40, "3.0 m at 30 m/s", size=11, fill=INK2, anchor="middle")
    s.line(c0[0], c0[1], P[0], P[1], stroke=BLUE, sw=2)
    s.line(c1[0], c1[1], P[0], P[1], stroke=ORANGE, sw=2)
    s.circle(P[0], P[1], 6, fill=INK)
    s.text(P[0], gy + 18, "road point, 10 m", size=11.5, fill=INK, anchor="middle")
    s.text(P[0] - 6, P[1] - 30, "same point, two sight lines", size=10.5, fill=INK2, anchor="end")
    # depression-angle arcs drawn from the horizontal at each camera
    def arc(c, ang_deg, color, rad=34):
        a = math.radians(ang_deg)
        ex, ey = c[0] + rad * math.cos(a), c[1] + rad * math.sin(a)
        s.path(f"M{c[0]+rad:.1f},{c[1]:.1f} A{rad},{rad} 0 0 1 {ex:.1f},{ey:.1f}", stroke=color, sw=1.5)
    arc(c0, DEP0, BLUE)
    arc(c1, DEP1, ORANGE)
    s.text(c0[0] + 44, c0[1] + 24, f"{DEP0:.2f}°", size=12, weight=600, fill=BLUE)
    s.text(c1[0] + 44, c1[1] + 30, f"{DEP1:.2f}°", size=12, weight=600, fill=ORANGE)
    # two result panels
    by = 240
    s.rect(14, by - 16, 326, 34, fill=ORANGE_T, rx=5)
    s.text(24, by + 6, f"Without prediction: {DEP1-DEP0:.1f}° shift at 10 m", size=12, weight=600)
    s.rect(346, by - 16, 320, 34, fill=BLUE_T, rx=5)
    s.text(356, by + 6, f"With prediction: {V['resid_deg']}° for 1 m/s² unmodelled", size=12, weight=600)
    return s

@fig("parallax")
def f_parallax():
    import math as m
    W, H = 680, 290
    s = Svg(W, H, "Parallax angle for a 150 mm head shift against object distance, with the plan's test distances marked")
    s.rect(0, 0, W, H, fill=SURF)
    X0, X1, Y0, Y1 = 62, 630, 230, 30
    dmax, amax = 40.0, 2.0
    sx = lambda d: X0 + d / dmax * (X1 - X0)
    sy = lambda a: Y0 - a / amax * (Y0 - Y1)
    for a in (0, 0.5, 1.0, 1.5, 2.0):
        s.line(X0, sy(a), X1, sy(a), stroke=GRID if a else AXIS, sw=1)
        s.text(X0 - 10, sy(a) + 4, f"{a:.1f}°", size=11, fill=INK2, anchor="end")
    for d in (0, 10, 20, 30, 40):
        s.line(sx(d), Y0, sx(d), Y0 + 4, stroke=AXIS, sw=1)
        s.text(sx(d), Y0 + 18, f"{d} m", size=11, fill=INK2, anchor="middle")
    s.text((X0 + X1) / 2, Y0 + 38, "Distance of the object", size=11.5, fill=INK, anchor="middle")
    pts = []
    for i in range(1, 161):
        d = dmax * i / 160.0
        pts.append((sx(d), sy(m.degrees(m.atan(0.150 / d)))))
    s.path("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts), stroke=BLUE, sw=2.2)
    for d, lab in ((7.5, "7.5 m · 1.15°"), (10, "10 m · 0.86°"), (30, "30 m · 0.29°")):
        a = m.degrees(m.atan(0.150 / d))
        s.circle(sx(d), sy(a), 5, fill=BLUE, stroke=SURF, sw=2)
        anchor = "start" if d < 20 else "end"
        dx = 10 if d < 20 else -10
        s.text(sx(d) + dx, sy(a) - 10, lab, size=11.5, weight=600, fill=INK, anchor=anchor)
    s.text(X0 + 10, 26, "Parallax angle, 150 mm head shift", size=11.5, weight=600, fill=INK)
    s.text(W - 14, H - 8, "Angle = atan(0.150 m ÷ distance). Without tracking, content drifts by this much.", size=10.5, fill=MUTED, anchor="end")
    return s
