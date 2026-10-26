"""Software, hardware, schedule and validation figures."""
from svgkit import *
from calc import V, COST

def box(s, x, y, w, h, title, sub=None, fill=BLUE_T, stroke=BLUE, tsize=12):
    s.rect(x, y, w, h, fill=fill, stroke=stroke, sw=1.4, rx=6)
    s.text(x + w / 2, y + 22, title, size=tsize, weight=700, fill=INK, anchor="middle")
    if sub:
        for i, t in enumerate(sub):
            s.text(x + w / 2, y + 40 + i * 15, t, size=10.5, fill=INK2, anchor="middle")

@fig("calib")
def f_calib():
    W, H = 680, 280
    s = Svg(W, H, "Projection chain from car frame to eye frame, virtual plane and panel pixels, with how each step is measured")
    s.rect(0, 0, W, H, fill=SURF)
    steps = [("Car frame", ["x forward, y right, z down", "origin at road camera"], BLUE_T, BLUE),
             ("Eye frame", ["eye_from_car, fixed +", "live head-tracker offset"], GREEN_T, GREEN),
             ("Virtual plane", ["K_eye pinhole, 7.5 m", "focal = (H/2) / tan(vfov/2)"], ORANGE_T, ORANGE),
             ("Panel pixels", ["3840 × 2400", "D pre-distortion mesh"], GREY_T, INK2)]
    bw, gap, y0, bh = 136, 32, 40, 84
    x = 14
    for i, (t, sub, fill, stroke) in enumerate(steps):
        box(s, x, y0, bw, bh, t, sub, fill, stroke, tsize=12)
        if i < len(steps) - 1:
            s.arrow(x + bw + 2, y0 + bh / 2, x + bw + gap - 2, y0 + bh / 2, color=INK, sw=1.8)
        x += bw + gap
    captions = [("step 1 · measured once", "tape, then a 30 m", "target board"),
                ("step 2 · measured once", "camera at the eye", "point, rendered grid"),
                ("step 3 · fitted once", "grid photograph", "fits the warp")]
    for i, lines in enumerate(captions):
        cxp = 14 + (i + 1) * (bw + gap) - gap / 2
        s.text(cxp, y0 + bh + 22, lines[0], size=10.5, weight=700, fill=INK, anchor="middle")
        s.text(cxp, y0 + bh + 38, lines[1], size=10.5, fill=INK2, anchor="middle")
        s.text(cxp, y0 + bh + 52, lines[2], size=10.5, fill=INK2, anchor="middle")
    s.text(14, 224, "Frame conventions from camera.py: x forward, y right, z down. Ground points add the 1.22 m default height.", size=11, fill=INK2)
    s.text(14, 242, "The head tracker shifts the eye frame live; the other two transforms are fixed once calibrated.", size=11, fill=INK2)
    s.text(14, 262, "Parameters are stored in Params on the Jetson. The matrix is D @ K_eye @ view_from_eye @ eye_from_car.", size=11, fill=INK2)
    return s

@fig("bench")
def f_bench():
    W, H = 680, 300
    s = Svg(W, H, "Bench chain: replay on mini PC 1, bridge to the Jetson, hudd on monitor 1, with regression tools alongside")
    s.rect(0, 0, W, H, fill=SURF)
    row = [("replay", ["route msgq from", "tools/replay --demo"], BLUE_T, BLUE),
           ("bridge (send)", ["mini PC 1, ZMQ out"], BLUE_T, BLUE),
           ("bridge (receive)", ["Jetson, local msgq"], GREEN_T, GREEN),
           ("hudd", ["renders at 4K60"], GREEN_T, GREEN),
           ("monitor 1", ["bench rig, camera"], ORANGE_T, ORANGE)]
    bw, gap = 110, 28
    x = 14
    for i, (t, sub, fill, stroke) in enumerate(row):
        box(s, x, 40, bw, 74, t, sub, fill, stroke, tsize=11.5)
        if i < len(row) - 1:
            s.arrow(x + bw + 2, 77, x + bw + gap - 2, 77, color=INK, sw=1.8)
        x += bw + gap
    s.text(14, 26, "Mini PC 1 stands in for the comma four. The Jetson receives the same messages either way.", size=11, fill=INK2)
    # side tools from hudd
    box(s, 14, 172, 210, 66, "tools/clip", ["renders HUD to MP4", "regression check per build"], GREY_T, INK2, tsize=11.5)
    box(s, 254, 172, 210, 66, "tools/sim (MetaDrive)", ["exercises engagement changes", "without a car"], GREY_T, INK2, tsize=11.5)
    box(s, 494, 172, 172, 66, "mini PC 2", ["nightly clip renders", "demo-day recording"], GREY_T, INK2, tsize=11.5)
    s.arrow(580, 118, 580, 170, color=INK2, sw=1.2)
    s.text(14, 268, "NTP between hosts is required so that message age can be measured across machines.", size=11, fill=INK2)
    s.text(14, 286, "The tools above run on the bench only. None of them is in the car.", size=11, fill=INK2)
    return s

@fig("power")
def f_power():
    W, H = 680, 380
    s = Svg(W, H, "Power and data wiring: car battery to DC-DC to Jetson, comma four to Jetson by Ethernet, monitors on USB-C PD")
    s.rect(0, 0, W, H, fill=SURF)
    s.line(14, 20, 44, 20, stroke=INK, sw=2)
    s.text(50, 24, "power", size=11, fill=INK)
    s.line(104, 20, 134, 20, stroke=BLUE, sw=2)
    s.text(140, 24, "data", size=11, fill=INK)
    s.text(W - 14, 24, "unverified items are marked in red", size=10.5, fill=MUTED, anchor="end")
    # column A: power source and sensors
    box(s, 14, 46, 150, 62, "Car 12 V", ["battery, ignition"], GREY_T, INK2, tsize=12)
    box(s, 14, 150, 150, 70, "DC-DC, ignition-sensed", ["Mini-Box, clean shutdown"], GREY_T, INK2, tsize=11.5)
    box(s, 14, 292, 150, 66, "OAK-D Pro", ["USB, IR for night"], BLUE_T, BLUE, tsize=11.5)
    s.arrow(89, 108, 89, 148, color=INK, sw=2)
    # column B: compute
    box(s, 230, 140, 200, 96, "Jetson Orin NX", ["hudd · headtrackd", "perceptd · hudmirror", "9–19 V input"], GREEN_T, GREEN, tsize=12)
    s.arrow(164, 185, 228, 185, color=INK, sw=2)
    s.text(196, 176, "power", size=10.5, fill=INK2, anchor="middle")
    s.arrow(164, 318, 246, 238, color=BLUE, sw=2)
    s.text(192, 286, "USB", size=10.5, fill=INK2, anchor="middle")
    box(s, 230, 290, 200, 70, "comma four", ["in car, harness to CAN", "bridge behind a Params flag"], BLUE_T, BLUE, tsize=12)
    s.arrow(330, 288, 330, 240, color=BLUE, sw=2)
    s.text(342, 270, "Ethernet, via", size=10.5, fill=INK2)
    s.text(342, 284, "USB-C adapter", size=10.5, fill=INK2)
    # column C: displays and chargers
    box(s, 480, 46, 186, 62, "USB-C PD car chargers ×2", ["100 W each, power both monitors"], GREY_T, INK2, tsize=11.5)
    box(s, 480, 150, 186, 62, "monitor 1 (HUD)", ["16″ 4K, 3840 × 2400"], ORANGE_T, ORANGE, tsize=11.5)
    box(s, 480, 262, 186, 62, "monitor 2 (audience)", ["16″ 4K, driven by hudmirror"], ORANGE_T, ORANGE, tsize=11.5)
    s.arrow(573, 108, 573, 148, color=INK, sw=2)
    s.arrow(430, 182, 478, 182, color=BLUE, sw=2)
    s.text(454, 172, "HDMI", size=10.5, fill=INK2, anchor="middle")
    s.arrow(430, 224, 478, 282, color=CRIT, sw=1.6)
    s.text(440, 262, "unverified", size=10.5, fill=CRIT, weight=600)
    s.text(14, 370, "The panda sits inside the comma four and sees the car bus. Nothing on the Jetson can reach it.", size=11, fill=INK2)
    return s

@fig("cost")
def f_cost():
    W = 680
    rows = sorted(COST, key=lambda c: c[2], reverse=True)
    rh = 25; top = 36
    H = top + rh * len(rows) + 58
    s = Svg(W, H, "Acquisition cost ranges per item in US dollars, low to high")
    s.rect(0, 0, W, H, fill=SURF)
    X0, X1 = 330, 640
    vmax = 4000.0
    sx = lambda v: X0 + v / vmax * (X1 - X0)
    for v in range(0, 4001, 1000):
        xx = sx(v)
        s.line(xx, top - 10, xx, top + rh * len(rows) - 6, stroke=GRID, sw=1)
        s.text(xx, top + rh * len(rows) + 10, f"${v:,}", size=11, fill=INK2, anchor="middle")
    for i, (name, lo, hi, tag) in enumerate(rows):
        y = top + i * rh
        tagtxt = "" if tag in ("firm", "range") else f" ({tag})"
        s.text(X0 - 12, y + 5, name + tagtxt, size=11, fill=INK, anchor="end")
        if hi > lo:
            s.rect(sx(lo), y - 7, sx(hi) - sx(lo), 14, fill=BLUE, rx=4)
            s.text(sx(hi) + 7, y + 4, f"${lo:,}–${hi:,}", size=10.5, fill=INK2)
        else:
            s.circle(sx(lo), y, 5, fill=BLUE, stroke=SURF, sw=2)
            s.text(sx(lo) + 9, y + 4, f"${lo:,}", size=10.5, fill=INK2)
    s.text(14, H - 24, f"Total of the listed ranges: ${V['cost_low']}–${V['cost_high']} (before tax, shipping and the deferred ZED-F9P GNSS at $260).", size=10.5, fill=INK, weight=600)
    s.text(14, H - 8, "Prices are as listed in the plan (last seen, not quotes). 'estimate' and 'unverified' are the plan's own tags.", size=10.5, fill=MUTED)
    return s

@fig("gantt")
def f_gantt():
    W, H = 680, 330
    s = Svg(W, H, "Phase schedule over weeks 0 to 13, with Track B after week 12")
    s.rect(0, 0, W, H, fill=SURF)
    X0, X1 = 230, 650
    wk = lambda w: X0 + w / 13.0 * (X1 - X0)
    phases = [("Phase 0 · decide, order", 0, 1, BLUE),
              ("Phase 1 · bench HUD", 1, 3, BLUE),
              ("Phase 2 · Jetson, bridge", 2, 4, BLUE),
              ("Phase 3 · car drives", 3, 6, BLUE),
              ("Phase 4 · Stage 1 in car", 4, 8, BLUE),
              ("Phase 5 · Stage 2 daylight", 6, 12, BLUE),
              ("Phase 6 · perception, rehearsal", 8, 12, BLUE),
              ("Track B · openpilot on Jetson", 12, 13, MUTED)]
    top = 46; rh = 28
    for w in range(0, 14):
        xx = wk(w)
        s.line(xx, top - 14, xx, top + rh * len(phases) - 6, stroke=GRID, sw=1)
        s.text(xx, top + rh * len(phases) + 6, f"{w}", size=11, fill=INK2, anchor="middle")
    s.text(X1, top + rh * len(phases) + 24, "week", size=11, fill=INK2, anchor="end")
    for i, (name, a, b, col) in enumerate(phases):
        y = top + i * rh
        s.text(X0 - 12, y + 5, name, size=11.5, fill=INK, anchor="end")
        s.rect(wk(a), y - 8, wk(b) - wk(a), 16, fill=col, rx=4)
        if name.startswith("Track B"):
            s.text(wk(b) - 10, y + 5, "starts after week 12, gated by the parity test", size=10.5, fill=INK2, anchor="end")
    s.text(14, H - 10, "Phases overlap. Weeks run from the day the car and comma four are chosen.", size=10.5, fill=MUTED)
    return s

@fig("regrig")
def f_regrig():
    W, H = 680, 380
    s = Svg(W, H, "Registration rig from above and latency probe, with the distances and steps used")
    s.rect(0, 0, W, H, fill=SURF)
    s.text(14, 24, "A · Registration test (top view, not to scale in depth)", size=12, weight=700, fill=INK)
    # camera at eye point, rail, rendered marker, target board
    s.rect(60, 80, 18, 22, fill=INK, rx=3)
    s.text(69, 70, "camera at eye point", size=11, fill=INK, anchor="middle")
    s.line(40, 130, 100, 130, stroke=INK2, sw=2)
    s.line(40, 130, 40, 130, stroke=INK2, sw=2)
    s.text(70, 150, "rail ±75 mm", size=11, fill=INK2, anchor="middle")
    s.line(230, 60, 230, 170, stroke=ORANGE, sw=3)
    s.text(230, 50, "HUD virtual plane 7.5 m", size=11, fill=INK, anchor="middle")
    s.line(560, 60, 560, 170, stroke=INK, sw=5)
    s.text(560, 50, "target board 30 m", size=11, fill=INK, anchor="middle")
    s.line(78, 90, 560, 110, stroke=MUTED, sw=1)
    s.text(330, 150, "rendered marker on the plane, surveyed target on the board", size=11, fill=INK2, anchor="middle")
    s.text(330, 168, "Angular error = atan(offset in px ÷ focal length in px)", size=11, fill=INK2, anchor="middle")
    # latency probe
    s.text(14, 212, "B · Latency probe (photodiode on the PGU)", size=12, weight=700, fill=INK)
    box(s, 14, 232, 160, 62, "synthetic modelV2", ["step fed to hudd"], BLUE_T, BLUE, tsize=11)
    box(s, 210, 232, 160, 62, "hudd render", ["age reported in log"], GREEN_T, GREEN, tsize=11)
    box(s, 406, 232, 130, 62, "PGU, photodiode", ["light step seen"], ORANGE_T, ORANGE, tsize=11)
    box(s, 572, 232, 94, 62, "MCU", ["timestamps"], GREY_T, INK2, tsize=11)
    s.arrow(176, 263, 208, 263, color=INK, sw=1.8)
    s.arrow(372, 263, 404, 263, color=INK, sw=1.8)
    s.arrow(538, 263, 570, 263, color=INK, sw=1.8)
    s.text(14, 322, "Compare the photodiode step time with the age that hudd reports for the same frame.", size=11, fill=INK2)
    s.text(14, 340, "Pass: age ≤ 60 ms on the monitor, ≤ 100 ms on the projector (section 10).", size=11, fill=INK2)
    s.text(14, 358, "Latency probe parts: photodiode, microcontroller, laser rangefinder (plan's acquisition list).", size=11, fill=MUTED)
    return s

@fig("storyboard")
def f_storyboard():
    W, H = 680, 170
    s = Svg(W, H, "Five-minute demo script on a timeline from 0:00 to 4:30, six scenes")
    s.rect(0, 0, W, H, fill=SURF)
    scenes = [(0, "0:00", "1 Set up"), (45, "0:45", "2 Engage"), (105, "1:45", "3 Lane lines"),
              (165, "2:45", "4 Lead car"), (225, "3:45", "5 Pedestrian"), (270, "4:30", "6 Stop")]
    x0, x1 = 40, 640
    tx = lambda t: x0 + t / 270.0 * (x1 - x0)
    y = 96
    s.line(x0, y, x1, y, stroke=INK2, sw=2)
    for i, (t, lab, name) in enumerate(scenes):
        xx = tx(t)
        s.circle(xx, y, 7, fill=BLUE, stroke=SURF, sw=2)
        s.text(xx, y - 22, lab, size=12, weight=700, fill=INK, anchor="middle")
        s.text(xx, y + 30, name, size=11.5, fill=INK, anchor="middle")
    s.text(14, H - 12, "Times are the plan's script marks, not timed rehearsals. Scene detail is in the table below.", size=10.5, fill=MUTED)
    return s

