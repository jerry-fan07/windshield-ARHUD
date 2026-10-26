"""Chapters 1-4: mockups, concept, architecture, interfaces, pipeline, timing, latency, prediction, parallax, camera-to-eye."""
import math
from svgkit import *
from calc import V, LAT, LAT_MIN, LAT_MAX, PAR, V_EGO, T_AGE, H_CAM, DEP0, DEP1, B_CE

# ---------- perspective helpers for the driver's-eye mockups ----------
def proj(X, Z, cx, cy, f, h=H_CAM):
    return cx + f * X / Z, cy + f * h / Z

def lane_centerline(Z):
    return 0.6 * (Z / 40.0) ** 2          # gentle right-hand curve, metres

def draw_road(s, W, H, cx, cy, f):
    s.rect(0, 0, W, cy, fill=GREY_T)                       # sky / horizon band
    s.poly([(0, cy), (W, cy), (W, H), (0, H)], fill="#e7e6e1")
    for X in (-5.5, 5.5):
        pts = [proj(lane_centerline(Z) + X, Z, cx, cy, f) for Z in (10, 14, 20, 30, 45, 70)]
        s.path("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts), stroke=MUTED, sw=1.2)
    for X in (-1.85, 1.85):
        pts = [proj(lane_centerline(Z) + X, Z, cx, cy, f) for Z in (10, 14, 20, 30, 45, 70)]
        s.path("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts), stroke=SURF, sw=3.2)

def lane_ribbon(s, cx, cy, f, fill=BLUE, op=0.30, zmax=45):
    """Translucent ribbon between the detected lane lines, drawn only where they are detected."""
    zs = [10 + i * 2.5 for i in range(int((zmax - 10) / 2.5) + 1)]
    left = [proj(lane_centerline(Z) - 1.7, Z, cx, cy, f) for Z in zs]
    right = [proj(lane_centerline(Z) + 1.7, Z, cx, cy, f) for Z in reversed(zs)]
    s.poly(left + right, fill=fill, extra=f'fill-opacity="{op}"')

def lane_lines(s, cx, cy, f, zmax=45):
    zs = [10 + i * 2.5 for i in range(int((zmax - 10) / 2.5) + 1)]
    for X in (-1.85, 1.85):
        pts = [proj(lane_centerline(Z) + X, Z, cx, cy, f) for Z in zs]
        s.path("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts), stroke=BLUE, sw=2.4)

def lead_car(s, cx, cy, f, Z=32.0):
    xo = lane_centerline(Z)
    xl, yb = proj(xo - 0.9, Z, cx, cy, f, h=H_CAM)
    xr, _ = proj(xo + 0.9, Z, cx, cy, f, h=H_CAM)
    _, yt = proj(xo, Z, cx, cy, f, h=H_CAM - 1.5)
    s.rect(xl, yt, xr - xl, yb - yt, fill="#3a3a38", rx=5)
    s.rect(xl + 6, yt + 6, xr - xl - 12, (yb - yt) * 0.36, fill="#6c6b66", rx=3)
    s.poly([(xl, yb + 7), ((xl + xr) / 2, yb + 17), (xr, yb + 7),
            (xr, yb + 11), ((xl + xr) / 2, yb + 21), (xl, yb + 11)], fill=INK)
    s.text((xl + xr) / 2, yb + 36, "32 m · 1.9 s", size=10.5, weight=600, fill=INK, anchor="middle")
    return xl, yb, xr, yt

def hazard(s, cx, cy, f, X=3.4, Z=20.0):
    hx, hy = proj(X, Z, cx, cy, f)
    hw = 0.3 * f / Z
    s.rect(hx - hw, hy - 1.7 * f / Z, 2 * hw, 1.7 * f / Z, fill="none", stroke=ORANGE, sw=2.2, rx=3)
    return hx, hy, hw

def speed_block(s, x, y, w=150, h=52):
    s.rect(x, y, w, h, fill=INK, rx=8)
    s.text(x + 12, y + 38, "62", size=30, weight=600, fill=SURF)
    s.text(x + 90, y + 21, "mph", size=11, weight=500, fill=SURF)
    s.text(x + 90, y + 38, "limit 65", size=11, weight=400, fill="#9ad3b8")

@fig("cover")
def f_cover():
    W, H = 680, 330
    cx, cy, f = 340, 150, 1475
    s = Svg(W, H, "Driver's-eye mockup of the HUD window, illustrative")
    s.rect(0, 0, W, H, fill=GREY_T)
    draw_road(s, W, H, cx, cy, f)
    lane_ribbon(s, cx, cy, f)
    lane_lines(s, cx, cy, f)
    lead_car(s, cx, cy, f)
    hazard(s, cx, cy, f)
    speed_block(s, 18, 262)
    s.rect(2, 2, W - 4, H - 4, fill="none", stroke=INK2, sw=1.2, rx=6)
    s.pill(W - 18, 26, "Illustrative only · not measured", size=10.5, anchor="end")
    return s

@fig("mockup")
def f_mockup():
    W, H = 680, 360
    cx, cy, f = 340, 150, 1475
    s = Svg(W, H, "Demo window mockup with the registered and fixed elements labelled")
    s.rect(0, 0, W, H, fill=SURF)
    s.rect(14, 14, W - 28, 300, fill=GREY_T)
    draw_road(s, W - 28, 300, cx - 14, cy - 14, f)
    lane_ribbon(s, cx - 14, cy - 14, f)
    lane_lines(s, cx - 14, cy - 14, f)
    lead_car(s, cx - 14, cy - 14, f)
    hx, hy, hw = hazard(s, cx - 14, cy - 14, f)
    s.rect(32, 262, 150, 40, fill=INK, rx=8)
    s.text(44, 290, "62 mph · limit 65", size=15, weight=600, fill=SURF)
    s.rect(14, 14, W - 28, 300, fill="none", stroke=INK2, sw=1.2)
    lx, ly = proj(-1.85, 14, cx - 14, cy - 14, f)
    s.pill(30, 46, "lane lines fade with confidence", size=11)
    s.line(60, 52, lx, ly, stroke=INK2, sw=1)
    lpx, lpy = proj(lane_centerline(30), 30, cx - 14, cy - 14, f)
    s.pill(300, 344, "lane ribbon between the detected lines", size=11)
    s.line(330, 330, lpx, lpy + 6, stroke=INK2, sw=1)
    s.pill(650, 46, "lead chevron and gap, from stereo depth", size=11, anchor="end")
    s.line(560, 52, 388, 216, stroke=INK2, sw=1)
    s.pill(650, 262, "hazard outline, from the detector", size=11, anchor="end")
    s.line(560, 262, hx + hw, hy - 20, stroke=INK2, sw=1)
    s.pill(190, 296, "speed block, fixed: GNSS speed, last limit sign", size=11)
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
    (x10, y10), (x30, y30) = pts
    s.text(346, 118, "30 m point: content at 0.9 m above road", size=11.5, fill=INK)
    s.line(344, 122, x30 + 4, y30 - 4, stroke=INK2, sw=1)
    s.text(346, 160, "10 m point: content at 0.3 m above road", size=11.5, fill=INK)
    s.line(344, 164, x10 + 4, y10 - 4, stroke=INK2, sw=1)
    s.text(14, 20, "Schematic. Positions are not to scale. Heights are true-geometry values.", size=10, fill=MUTED)
    return s

@fig("arch")
def f_arch():
    W, H = 680, 372
    s = Svg(W, H, "Single-computer architecture: sensors into the Jetson, the Jetson into the TFT panel and the optics, with an audience PC on Ethernet")
    s.rect(0, 0, W, H, fill=SURF)
    # left: sensors
    s.rect(14, 16, 186, 300, fill=BLUE_T, stroke=BLUE, sw=1.2, rx=6)
    s.rect(14, 16, 186, 30, fill=BLUE, rx=6)
    s.rect(14, 34, 186, 12, fill=BLUE)
    s.text(24, 37, "Sensors", size=12.5, weight=700, fill=SURF)
    s.lines(24, 68, ["ZED 2i stereo camera", "road view, depth, IMU", "USB 3, 30 Hz"], size=11, lh=14)
    s.line(24, 116, 190, 116, stroke=BLUE, sw=1)
    s.lines(24, 134, ["OAK-D Pro driver camera", "face landmarks, IR at night", "USB 3, 30 Hz"], size=11, lh=14)
    s.line(24, 182, 190, 182, stroke=BLUE, sw=1)
    s.lines(24, 200, ["u-blox ZED-F9R GNSS", "speed, heading, 10 Hz"], size=11, lh=14)
    s.line(24, 234, 190, 234, stroke=BLUE, sw=1)
    s.lines(24, 252, ["HUD controller (RP2040)", "ambient light, panel temperature,", "backlight PWM, sun shutter", "USB serial"], size=11, lh=14)
    # middle: Jetson
    s.rect(246, 16, 220, 300, fill=GREEN_T, stroke=GREEN, sw=1.2, rx=6)
    s.rect(246, 16, 220, 30, fill=GREEN, rx=6)
    s.rect(246, 34, 220, 12, fill=GREEN)
    s.text(256, 37, "Jetson Orin NX · the only computer", size=12.5, weight=700, fill=SURF)
    s.lines(256, 68, ["roadd: capture, depth, ground plane", "laned: lane network (TensorRT)", "detectd: objects, signs, tracker", "egod: speed, yaw rate, pitch", "headtrackd: eye position", "hudd: age compensation, eye", "    projection, pre-distortion, 60 Hz", "controllerd: brightness, thermal, sun", "logd: recording for replay"], size=11, lh=15.5)
    s.text(256, 228, "topics over ZeroMQ (ipc), msgpack", size=10.5, fill=INK2)
    s.text(256, 256, "HDMI out: 1920 × 1080 at 60 Hz", size=11.5, weight=600, fill=INK)
    s.text(256, 272, "to the panel's driver board", size=10.5, fill=INK2)
    s.text(256, 298, "Ethernet: audience stream to mini PC 2", size=10.5, fill=INK2)
    # right: optics
    s.rect(512, 16, 154, 300, fill=ORANGE_T, stroke=ORANGE, sw=1.2, rx=6)
    s.rect(512, 16, 154, 30, fill=ORANGE, rx=6)
    s.rect(512, 34, 154, 12, fill=ORANGE)
    s.text(522, 37, "Optics", size=12.5, weight=700, fill=INK)
    s.lines(522, 68, ["TFT PGU: 5.5-inch panel,", "60 × 30 mm active crop,", "custom LED backlight", "", "cold-mirror fold", "(passes solar infrared)", "", "concave mirror", f"f = {V['f2']}, 300 × 200 mm", "", "windshield, s-polarised", f"reflection {V['rs65']}", "", "virtual image at 7.5 m", f"{V['fov2_w']}° × {V['fov2_h']}°"], size=11, lh=14.5)
    # arrows
    s.arrow(200, 166, 246, 166, color=INK, sw=2)
    s.text(223, 156, "USB", size=10.5, fill=INK, anchor="middle")
    s.arrow(466, 256, 512, 256, color=INK, sw=2)
    s.text(489, 246, "HDMI", size=10.5, fill=INK, anchor="middle")
    s.text(14, H - 34, "No connection to any vehicle bus. The only vehicle interface is the 12 V accessory supply.", size=11.5, fill=INK, weight=600)
    s.text(14, H - 16, "Drawn to scale: no. Arrows show the data paths into and out of the Jetson.", size=10.5, fill=MUTED)
    return s

@fig("interfaces")
def f_interfaces():
    W, H = 680, 250
    s = Svg(W, H, "The HUD's interfaces to the car: 12 V power only; no bus, no actuator, nothing attached to the glass")
    s.rect(0, 0, W, H, fill=SURF)
    s.text(14, 22, "THE CAR · driven by a person", size=11.5, weight=700, fill=BLUE)
    row = ["driver", "steering, pedals", "ECUs and CAN bus", "actuators"]
    ws = [100, 150, 170, 120]
    x = 14
    for i, (lab, w) in enumerate(zip(row, ws)):
        s.rect(x, 34, w, 40, fill=BLUE_T, stroke=BLUE, sw=1.2, rx=6)
        s.text(x + w / 2, 59, lab, size=12, weight=600, fill=INK, anchor="middle")
        if i < len(row) - 1:
            s.arrow(x + w + 2, 54, x + w + 22, 54, color=BLUE, sw=2)
        x += w + 24
    s.text(14, 96, "Nothing in the HUD can send a frame on the bus or move an actuator: there is no wire that could carry it.", size=11, fill=INK2)
    s.line(14, 130, W - 14, 130, stroke=CRIT, sw=3)
    s.rect(W / 2 - 190, 116, 380, 26, fill=SURF, stroke="none")
    s.text(W / 2, 134, "the only crossing: 12 V accessory supply, fused, ignition-sensed", size=11.5, weight=700, fill=CRIT, anchor="middle")
    s.text(14, 168, "THE HUD · perceives and draws", size=11.5, weight=700, fill=GREEN)
    row2 = ["cameras, GNSS, IMU", "Jetson", "TFT PGU and mirror"]
    ws2 = [190, 150, 200]
    x = 14
    for i, (lab, w) in enumerate(zip(row2, ws2)):
        s.rect(x, 180, w, 40, fill=GREEN_T, stroke=GREEN, sw=1.2, rx=6)
        s.text(x + w / 2, 205, lab, size=12, weight=600, fill=INK, anchor="middle")
        if i < len(row2) - 1:
            s.arrow(x + w + 2, 200, x + w + 22, 200, color=GREEN, sw=2)
        x += w + 24
    s.text(14, 242, "The housing sits on the dash and is removable without tools. The windshield is not modified in the base design.", size=11, fill=INK2)
    return s

@fig("pipeline")
def f_pipeline():
    W, H = 680, 300
    s = Svg(W, H, "Perception pipeline from camera frames to pixels on the panel")
    s.rect(0, 0, W, H, fill=SURF)
    def bx(x, y, w, h, t, sub, fill, stroke):
        s.rect(x, y, w, h, fill=fill, stroke=stroke, sw=1.3, rx=6)
        s.text(x + w / 2, y + 19, t, size=11.5, weight=700, fill=INK, anchor="middle")
        for i, l in enumerate(sub):
            s.text(x + w / 2, y + 35 + i * 13, l, size=10, fill=INK2, anchor="middle")
    bx(14, 20, 120, 64, "ZED 2i frames", ["left image, depth", "IMU at 400 Hz"], BLUE_T, BLUE)
    bx(170, 20, 150, 64, "laned", ["lane network: 2D points", "per lane, confidence"], GREEN_T, GREEN)
    bx(170, 110, 150, 64, "detectd", ["detector: boxes, classes", "tracker: stable IDs"], GREEN_T, GREEN)
    bx(170, 200, 150, 64, "roadd", ["ground plane fit", "depth at box feet"], GREEN_T, GREEN)
    bx(356, 20, 150, 64, "lanes (3D)", ["points on the ground", "plane, car frame"], GREY_T, INK2)
    bx(356, 110, 150, 64, "objects (3D)", ["bearing from the image,", "range from stereo"], GREY_T, INK2)
    bx(356, 200, 150, 64, "ego", ["speed (GNSS), yaw rate", "and pitch (IMU), 100 Hz"], GREY_T, INK2)
    bx(542, 20, 124, 244, "hudd", ["age compensation", "eye projection", "(head tracker)", "draw at 60 Hz", "pre-distortion", "warp pass", "", "HDMI to the", "panel board"], ORANGE_T, ORANGE)
    for y in (52, 142, 232):
        s.arrow(136, 52, 168, y, color=INK, sw=1.4) if y != 52 else s.arrow(136, 52, 168, 52, color=INK, sw=1.4)
    s.arrow(322, 52, 354, 52, color=INK, sw=1.4)
    s.arrow(322, 142, 354, 142, color=INK, sw=1.4)
    s.arrow(322, 232, 354, 232, color=INK, sw=1.4)
    for y in (52, 142, 232):
        s.arrow(508, y, 540, y, color=INK, sw=1.4)
    s.text(14, 110, "GNSS speed", size=10.5, fill=INK2)
    s.text(14, 124, "ZED-F9R, 10 Hz", size=10.5, fill=INK2)
    s.arrow(90, 118, 168, 232, color=INK2, sw=1.1)
    s.text(14, 286, "Every topic carries the capture timestamp of the frame it came from, so hudd can measure its age.", size=10.5, fill=MUTED)
    return s

@fig("rates")
def f_rates():
    W, H = 680, 262
    s = Svg(W, H, "Topic rates the renderer reads, drawn over one second")
    s.rect(0, 0, W, H, fill=SURF)
    rows = [("sunWatch", 1), ("health", 2), ("gnss", 10), ("lanes", 30), ("objects", 30),
            ("eyePose", 30), ("ego", 100)]
    x0, x1 = 210, 600
    top = 20; rh = 26
    for i, (name, hz) in enumerate(rows):
        y = top + i * rh + 12
        s.text(x0 - 12, y + 4, name, size=11.5, fill=INK, anchor="end")
        s.rect(x0, y - 8, x1 - x0, 16, fill="#f3f2ee")
        for k in range(hz):
            t = k / hz
            xx = x0 + t * (x1 - x0)
            s.rect(xx - 1, y - 7, 2, 14, fill=BLUE)
        s.text(x1 + 10, y + 4, f"{hz} Hz", size=11.5, fill=INK2)
    yb = top + len(rows) * rh + 4
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        xx = x0 + t * (x1 - x0)
        s.line(xx, yb, xx, yb + 5, stroke=AXIS, sw=1)
        s.text(xx, yb + 18, f"{t:.2f} s" if t else "0", size=11, fill=INK2, anchor="middle")
    s.text(W - 14, H - 10, "Each tick is one message. hudd draws at 60 Hz whatever the topic rates are.", size=10.5, fill=MUTED, anchor="end")
    return s

@fig("latency")
def f_latency():
    W, H = 680, 350
    s = Svg(W, H, "Latency budget as horizontal range bars from minimum to maximum")
    s.rect(0, 0, W, H, fill=SURF)
    x0, x1 = 316, 640
    vmax = 120.0
    sx = lambda v: x0 + v / vmax * (x1 - x0)
    rows = [(n, a, b, BLUE) for n, a, b in LAT]
    rows.append(("Total, uncompensated", LAT_MIN, LAT_MAX, INK))
    rows.append(("Head tracker (parallax only)", 30, 50, MUTED))
    top = 30; rh = 40
    for t in range(0, 121, 20):
        xx = sx(t)
        s.line(xx, top - 8, xx, top + rh * len(rows) - 6, stroke=GRID, sw=1)
        s.text(xx, top + rh * len(rows) + 6, f"{t}", size=11, fill=INK2, anchor="middle")
    s.text(x1 + 26, top + rh * len(rows) + 18, "ms", size=11, fill=INK2, anchor="start")
    for i, (name, a, b, col) in enumerate(rows):
        y = top + i * rh
        if name.startswith("Total"):
            s.line(14, y - 8, W - 14, y - 8, stroke=AXIS, sw=1)
        s.text(306, y + 5, name, size=11.5, weight=600 if name.startswith("Total") else 400, fill=INK, anchor="end")
        s.rect(sx(a), y - 8, sx(b) - sx(a), 16, fill=col, rx=4)
        s.text(sx(b) + 8, y + 5, f"{a}–{b} ms", size=11.5, fill=INK2)
    s.text(14, H - 8, "Stage ranges are estimates to be replaced by the photodiode measurement in Phase 2. The whole chain is on one computer.", size=10.5, fill=MUTED)
    return s

@fig("prediction")
def f_prediction():
    W, H = 680, 262
    s = Svg(W, H, "Side view of the camera moving 3 m in 100 ms while sighting a road point 10 m ahead")
    s.rect(0, 0, W, H, fill=SURF)
    k = 46.7
    x0, gy = 40, 178
    s.line(20, gy, W - 20, gy, stroke=INK2, sw=1.2)
    s.text(W - 20, gy + 16, "road", size=11, fill=INK2, anchor="end")
    cam_h = H_CAM * k
    c0 = (x0, gy - cam_h)
    c1 = (x0 + 3.0 * k, gy - cam_h)
    P = (x0 + 10 * k, gy)
    for c, lab in ((c0, "eye at t0"), (c1, "eye at t0 + 100 ms")):
        s.rect(c[0] - 7, c[1] - 7, 14, 14, fill=INK, rx=2)
        s.text(c[0], c[1] - 16, lab, size=11, fill=INK, anchor="middle")
    s.arrow(c0[0], c0[1] + 24, c1[0], c1[1] + 24, color=INK2, sw=1.5)
    s.text((c0[0] + c1[0]) / 2, c1[1] + 40, "3.0 m at 30 m/s", size=11, fill=INK2, anchor="middle")
    s.line(c0[0], c0[1], P[0], P[1], stroke=BLUE, sw=2)
    s.line(c1[0], c1[1], P[0], P[1], stroke=ORANGE, sw=2)
    s.circle(P[0], P[1], 6, fill=INK)
    s.text(P[0], gy + 18, "road point, 10 m", size=11.5, fill=INK, anchor="middle")
    s.text(P[0] - 6, P[1] - 30, "same point, two sight lines", size=10.5, fill=INK2, anchor="end")
    def arc(c, ang_deg, color, rad=34):
        a = math.radians(ang_deg)
        ex, ey = c[0] + rad * math.cos(a), c[1] + rad * math.sin(a)
        s.path(f"M{c[0]+rad:.1f},{c[1]:.1f} A{rad},{rad} 0 0 1 {ex:.1f},{ey:.1f}", stroke=color, sw=1.5)
    arc(c0, DEP0, BLUE)
    arc(c1, DEP1, ORANGE)
    s.text(c0[0] + 44, c0[1] + 24, f"{DEP0:.2f}°", size=12, weight=600, fill=BLUE)
    s.text(c1[0] + 44, c1[1] + 30, f"{DEP1:.2f}°", size=12, weight=600, fill=ORANGE)
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
    sx = lambda dd: X0 + dd / dmax * (X1 - X0)
    sy = lambda a: Y0 - a / amax * (Y0 - Y1)
    for a in (0, 0.5, 1.0, 1.5, 2.0):
        s.line(X0, sy(a), X1, sy(a), stroke=GRID if a else AXIS, sw=1)
        s.text(X0 - 10, sy(a) + 4, f"{a:.1f}°", size=11, fill=INK2, anchor="end")
    for dd in (0, 10, 20, 30, 40):
        s.line(sx(dd), Y0, sx(dd), Y0 + 4, stroke=AXIS, sw=1)
        s.text(sx(dd), Y0 + 18, f"{dd} m", size=11, fill=INK2, anchor="middle")
    s.text((X0 + X1) / 2, Y0 + 38, "Distance of the object", size=11.5, fill=INK, anchor="middle")
    pts = []
    for i in range(1, 161):
        dd = dmax * i / 160.0
        pts.append((sx(dd), sy(m.degrees(m.atan(0.150 / dd)))))
    s.path("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts), stroke=BLUE, sw=2.2)
    for dd, lab in ((7.5, "7.5 m · 1.15°"), (10, "10 m · 0.86°"), (30, "30 m · 0.29°")):
        a = m.degrees(m.atan(0.150 / dd))
        s.circle(sx(dd), sy(a), 5, fill=BLUE, stroke=SURF, sw=2)
        anchor = "start" if dd < 20 else "end"
        dx = 10 if dd < 20 else -10
        s.text(sx(dd) + dx, sy(a) - 10, lab, size=11.5, weight=600, fill=INK, anchor=anchor)
    s.text(X0 + 10, 26, "Parallax angle, 150 mm head shift", size=11.5, weight=600, fill=INK)
    s.text(W - 14, H - 8, "Angle = atan(0.150 m ÷ distance). Without tracking, content drifts by this much.", size=10.5, fill=MUTED, anchor="end")
    return s

@fig("cameye")
def f_cameye():
    W, H = 680, 270
    s = Svg(W, H, "Top view: the road camera sits beside the eye, so a range error moves the mark by the baseline times the error over distance squared")
    s.rect(0, 0, W, H, fill=SURF)
    ey = 150; cy_ = 92
    ex = 60
    s.circle(ex, ey, 9, fill=INK)
    s.text(ex, ey + 26, "eye", size=11.5, fill=INK, anchor="middle")
    s.rect(ex - 8, cy_ - 8, 16, 16, fill=BLUE, rx=2)
    s.text(ex, cy_ - 16, "road camera", size=11.5, fill=INK, anchor="middle")
    s.arrow(ex + 20, ey, ex + 20, cy_, color=INK2, sw=1.2)
    s.text(ex + 28, (ey + cy_) / 2 + 4, f"baseline b = {V['b_ce']}", size=11, fill=INK2)
    ox_true, ox_est = 520, 580
    s.circle(ox_true, cy_, 6, fill=INK)
    s.text(ox_true - 10, cy_ - 14, "true object at range z", size=11, fill=INK, anchor="end")
    s.circle(ox_est, cy_, 6, fill=ORANGE, stroke=SURF, sw=1.5)
    s.text(ox_est, cy_ + 20, "range read as z + dz", size=11, fill=ORANGE, anchor="end")
    s.line(ex, cy_, ox_est, cy_, stroke=BLUE, sw=1.5)
    s.text(300, cy_ - 8, "the camera sees both at the same bearing", size=10.5, fill=INK2, anchor="middle")
    s.line(ex, ey, ox_true, cy_, stroke=INK, sw=1.5)
    s.line(ex, ey, ox_est, cy_, stroke=ORANGE, sw=1.5)
    s.text(330, 150, "from the eye, the two bearings differ by b·dz ÷ z²", size=11, weight=600, fill=INK, anchor="middle")
    rows = [("10 m, range off by 1 m", V["reg_10_1m"]), ("20 m, range off by 2 m", V["reg_20_10pct"]), ("30 m, range off by 3 m", V["reg_30_10pct"]), (f"30 m, stereo error {V['sdz_30']} m", V["sreg_30"])]
    y = 196
    for lab, val in rows:
        s.text(60, y, lab, size=11, fill=INK)
        s.text(300, y, f"{val}°", size=11, weight=600, fill=INK, anchor="end")
        y += 17
    s.text(340, 196, "Bearing comes from the image and is exact;", size=11, fill=INK2)
    s.text(340, 213, "range only matters through the baseline.", size=11, fill=INK2)
    s.text(340, 230, "Keep the camera within half a metre of the eye", size=11, fill=INK2)
    s.text(340, 247, "and a 10% range error stays under 0.3°.", size=11, fill=INK2)
    return s
