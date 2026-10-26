"""Software, hardware, schedule and validation figures."""
from svgkit import *
from calc import V, COST, COST_OPT, GPU, GPU_MIN, GPU_MAX

def box(s, x, y, w, h, title, sub=None, fill=BLUE_T, stroke=BLUE, tsize=12):
    s.rect(x, y, w, h, fill=fill, stroke=stroke, sw=1.4, rx=6)
    s.text(x + w / 2, y + 22, title, size=tsize, weight=700, fill=INK, anchor="middle")
    if sub:
        for i, t in enumerate(sub):
            s.text(x + w / 2, y + 40 + i * 15, t, size=10.5, fill=INK2, anchor="middle")

@fig("calib")
def f_calib():
    W, H = 680, 280
    s = Svg(W, H, "Projection chain from the car frame to the eye frame, the virtual plane and panel pixels, with how each step is measured")
    s.rect(0, 0, W, H, fill=SURF)
    steps = [("Car frame", ["x forward, y right, z down", "origin at the road camera"], BLUE_T, BLUE),
             ("Eye frame", ["eye_from_car, fixed +", "live head-tracker offset"], GREEN_T, GREEN),
             ("Virtual plane", ["K_eye pinhole, 7.5 m", "focal = (H/2) / tan(vfov/2)"], ORANGE_T, ORANGE),
             ("Panel pixels", [f"{V['crop_px_w']} × {V['crop_px_h']} crop", "D pre-distortion mesh"], GREY_T, INK2)]
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
    s.text(14, 224, "Car frame: x forward, y right, z down, origin at the ZED's left camera. Ground points come from the stereo plane fit.", size=11, fill=INK2)
    s.text(14, 242, "The head tracker shifts the eye frame live; the other two transforms are fixed once calibrated.", size=11, fill=INK2)
    s.text(14, 262, "Parameters live in a YAML file on the Jetson. The matrix is D @ K_eye @ view_from_eye @ eye_from_car.", size=11, fill=INK2)
    return s

@fig("bench")
def f_bench():
    W, H = 680, 320
    s = Svg(W, H, "Bench chains: the Jetson replays stereo recordings through perception; the mini PC replays topic logs into the renderer")
    s.rect(0, 0, W, H, fill=SURF)
    s.text(14, 26, "A · Perception bench, on the Jetson (needs CUDA)", size=11.5, weight=700, fill=INK)
    row = [("SVO recording", ["ZED stereo + IMU", "from a drive"], BLUE_T, BLUE),
           ("roadd, laned, detectd", ["same code as live"], GREEN_T, GREEN),
           ("topic log", ["lanes, objects, ego", "with timestamps"], GREY_T, INK2),
           ("scoring", ["against hand-labelled", "frames of the course"], GREY_T, INK2)]
    bw, gap = 148, 22
    x = 14
    for i, (t, sub, fill, stroke) in enumerate(row):
        box(s, x, 40, bw, 74, t, sub, fill, stroke, tsize=11.5)
        if i < len(row) - 1:
            s.arrow(x + bw + 2, 77, x + bw + gap - 2, 77, color=INK, sw=1.8)
        x += bw + gap
    s.text(14, 156, "B · Renderer bench, on mini PC 1 (no CUDA needed)", size=11.5, weight=700, fill=INK)
    row2 = [("topic log", ["recorded or synthetic", "lanes, objects, ego"], GREY_T, INK2),
            ("hudd", ["eye projection, warp,", "60 Hz, as in the car"], GREEN_T, GREEN),
            ("Stage 0 rig", ["panel + beamsplitter,", "camera at the eye"], ORANGE_T, ORANGE),
            ("MP4 and metrics", ["regression per build,", "mini PC 2 nightly"], GREY_T, INK2)]
    x = 14
    for i, (t, sub, fill, stroke) in enumerate(row2):
        box(s, x, 170, bw, 74, t, sub, fill, stroke, tsize=11.5)
        if i < len(row2) - 1:
            s.arrow(x + bw + 2, 207, x + bw + gap - 2, 207, color=INK, sw=1.8)
        x += bw + gap
    s.text(14, 276, "Recordings come from passenger-seat drives in week 1, before any part of the car is touched.", size=11, fill=INK2)
    s.text(14, 294, "Replayed data has no live latency: timing is measured only by the photodiode test on the live system.", size=11, fill=INK2)
    return s

@fig("power")
def f_power():
    W, H = 680, 424
    s = Svg(W, H, "Power and data wiring: car 12 V to the DC-DC converter, Jetson, backlight driver and panel board; sensors on USB; audience PC on Ethernet")
    s.rect(0, 0, W, H, fill=SURF)
    s.line(14, 20, 44, 20, stroke=INK, sw=2)
    s.text(50, 24, "power", size=11, fill=INK)
    s.line(104, 20, 134, 20, stroke=BLUE, sw=2)
    s.text(140, 24, "data", size=11, fill=INK)
    box(s, 14, 46, 150, 62, "Car 12 V", ["accessory socket, fused"], GREY_T, INK2, tsize=12)
    box(s, 14, 140, 150, 70, "DC-DC, ignition-sensed", ["Mini-Box, clean shutdown"], GREY_T, INK2, tsize=11.5)
    s.arrow(89, 108, 89, 138, color=INK, sw=2)
    box(s, 14, 250, 150, 56, "ZED 2i", ["USB 3"], BLUE_T, BLUE, tsize=11.5)
    box(s, 14, 320, 150, 56, "OAK-D Pro · ZED-F9R", ["USB 3 · USB serial"], BLUE_T, BLUE, tsize=11.5)
    box(s, 230, 130, 200, 96, "Jetson Orin NX", ["all HUD processes", "9–19 V input, MAXN"], GREEN_T, GREEN, tsize=12)
    s.arrow(164, 175, 228, 175, color=INK, sw=2)
    s.text(196, 166, "12 V", size=10.5, fill=INK2, anchor="middle")
    s.arrow(164, 278, 246, 228, color=BLUE, sw=2)
    s.arrow(164, 348, 262, 228, color=BLUE, sw=2)
    box(s, 230, 262, 200, 66, "HUD controller (RP2040)", ["ambient light, NTC on the cell,", "backlight PWM, shutter servo"], GREY_T, INK2, tsize=11)
    s.arrow(330, 260, 330, 228, color=BLUE, sw=2)
    s.text(342, 248, "USB serial", size=10.5, fill=INK2)
    box(s, 230, 344, 200, 48, "LED driver, constant current", ["from 12 V, PWM input"], GREY_T, INK2, tsize=11)
    s.arrow(330, 330, 330, 342, color=BLUE, sw=1.6)
    s.arrow(164, 190, 230, 368, color=INK, sw=1.6)
    box(s, 480, 46, 186, 62, "panel driver board", ["HDMI in, 5 V from the Jetson's", "USB or a 5 V buck"], ORANGE_T, ORANGE, tsize=11.5)
    box(s, 480, 140, 186, 62, "TFT PGU", ["LCD cell + custom backlight"], ORANGE_T, ORANGE, tsize=11.5)
    s.arrow(430, 160, 478, 80, color=BLUE, sw=2)
    s.text(448, 112, "HDMI", size=10.5, fill=INK2, anchor="middle")
    s.arrow(573, 108, 573, 138, color=BLUE, sw=2)
    s.arrow(430, 368, 480, 200, color=INK, sw=1.6)
    s.text(442, 352, "LED current", size=10.5, fill=INK2, anchor="start")
    box(s, 480, 250, 186, 62, "mini PC 2 + monitor 2", ["audience view over Ethernet"], GREY_T, INK2, tsize=11.5)
    s.arrow(430, 200, 478, 270, color=BLUE, sw=2)
    s.text(466, 232, "Ethernet", size=10.5, fill=INK2, anchor="middle")
    s.text(14, 414, "No wire reaches the car's buses. The 12 V feed is the only connection to the vehicle.", size=11, fill=INK2)
    return s

@fig("cost")
def f_cost():
    W = 680
    rows = sorted(COST, key=lambda c: c[2], reverse=True)
    rh = 24; top = 36
    H = top + rh * len(rows) + 74
    s = Svg(W, H, "Acquisition cost ranges per item in US dollars, low to high")
    s.rect(0, 0, W, H, fill=SURF)
    X0, X1 = 340, 640
    vmax = 4000.0
    sx = lambda v: X0 + v / vmax * (X1 - X0)
    for v in range(0, 4001, 1000):
        xx = sx(v)
        s.line(xx, top - 10, xx, top + rh * len(rows) - 6, stroke=GRID, sw=1)
        s.text(xx, top + rh * len(rows) + 10, f"${v:,}", size=11, fill=INK2, anchor="middle")
    for i, (name, lo, hi, tag) in enumerate(rows):
        y = top + i * rh
        tagtxt = "" if tag in ("firm", "range") else f" ({tag})"
        s.text(X0 - 12, y + 5, name + tagtxt, size=10.5, fill=INK, anchor="end")
        if hi > lo:
            s.rect(sx(lo), y - 7, sx(hi) - sx(lo), 14, fill=BLUE, rx=4)
            s.text(sx(hi) + 7, y + 4, f"${lo:,}–${hi:,}", size=10.5, fill=INK2)
        else:
            s.circle(sx(lo), y, 5, fill=BLUE, stroke=SURF, sw=2)
            s.text(sx(lo) + 9, y + 4, f"${lo:,}", size=10.5, fill=INK2)
    s.text(14, H - 40, f"Total of the listed ranges: ${V['cost_low']}–${V['cost_high']}, before tax and shipping.", size=10.5, fill=INK, weight=600)
    s.text(14, H - 24, f"Optional, not in the total: wedge-PVB windshield and a HUD-grade TFT module, ${V['cost_opt_low']}–${V['cost_opt_high']} together.", size=10.5, fill=INK)
    s.text(14, H - 8, "Prices are last seen, not quotes. 'estimate' is the plan's own tag.", size=10.5, fill=MUTED)
    return s

@fig("gantt")
def f_gantt():
    W, H = 680, 340
    s = Svg(W, H, "Phase schedule over weeks 0 to 13")
    s.rect(0, 0, W, H, fill=SURF)
    X0, X1 = 250, 650
    wk = lambda w: X0 + w / 13.0 * (X1 - X0)
    phases = [("Phase 0 · decide, order", 0, 1, BLUE),
              ("Phase 1 · recordings, perception", 1, 4, BLUE),
              ("Phase 2 · bench HUD, renderer", 1, 3, BLUE),
              ("Phase 3 · live in car, on a monitor", 3, 5, BLUE),
              ("Phase 4 · Stage 1 combiner, night", 4, 8, BLUE),
              ("Phase 5 · TFT PGU and backlight", 4, 8, ORANGE),
              ("Phase 6 · Stage 2 mirror, daylight", 6, 12, ORANGE),
              ("Phase 7 · hazards, signs, rehearsal", 8, 12, BLUE)]
    top = 46; rh = 30
    for w in range(0, 14):
        xx = wk(w)
        s.line(xx, top - 14, xx, top + rh * len(phases) - 6, stroke=GRID, sw=1)
        s.text(xx, top + rh * len(phases) + 6, f"{w}", size=11, fill=INK2, anchor="middle")
    s.text(X1, top + rh * len(phases) + 24, "week", size=11, fill=INK2, anchor="end")
    for i, (name, a, b, col) in enumerate(phases):
        y = top + i * rh
        s.text(X0 - 12, y + 5, name, size=11.5, fill=INK, anchor="end")
        s.rect(wk(a), y - 8, wk(b) - wk(a), 16, fill=col, rx=4)
    s.text(14, H - 28, "Blue: software and in-car phases. Orange: the optics chain, which carries the mirror's lead time.", size=10.5, fill=INK2)
    s.text(14, H - 10, "Phases overlap. Weeks run from the day the car and the venue are agreed.", size=10.5, fill=MUTED)
    return s

@fig("regrig")
def f_regrig():
    W, H = 680, 380
    s = Svg(W, H, "Registration rig from above and latency probe, with the distances and steps used")
    s.rect(0, 0, W, H, fill=SURF)
    s.text(14, 24, "A · Registration test (top view, not to scale in depth)", size=12, weight=700, fill=INK)
    s.rect(60, 80, 18, 22, fill=INK, rx=3)
    s.text(69, 70, "camera at eye point", size=11, fill=INK, anchor="middle")
    s.line(40, 130, 100, 130, stroke=INK2, sw=2)
    s.text(70, 150, "rail ±75 mm", size=11, fill=INK2, anchor="middle")
    s.line(230, 60, 230, 170, stroke=ORANGE, sw=3)
    s.text(230, 50, "HUD virtual plane 7.5 m", size=11, fill=INK, anchor="middle")
    s.line(560, 60, 560, 170, stroke=INK, sw=5)
    s.text(560, 50, "target board 30 m", size=11, fill=INK, anchor="middle")
    s.line(78, 90, 560, 110, stroke=MUTED, sw=1)
    s.text(330, 150, "rendered marker on the plane, surveyed target on the board", size=11, fill=INK2, anchor="middle")
    s.text(330, 168, "Angular error = atan(offset in px ÷ focal length in px)", size=11, fill=INK2, anchor="middle")
    s.text(14, 212, "B · Latency probe (photodiode on the panel)", size=12, weight=700, fill=INK)
    box(s, 14, 232, 160, 62, "synthetic lanes step", ["fed to hudd as a topic"], BLUE_T, BLUE, tsize=11)
    box(s, 210, 232, 160, 62, "hudd render", ["age reported in log"], GREEN_T, GREEN, tsize=11)
    box(s, 406, 232, 130, 62, "panel, photodiode", ["light step seen"], ORANGE_T, ORANGE, tsize=11)
    box(s, 572, 232, 94, 62, "MCU", ["timestamps"], GREY_T, INK2, tsize=11)
    s.arrow(176, 263, 208, 263, color=INK, sw=1.8)
    s.arrow(372, 263, 404, 263, color=INK, sw=1.8)
    s.arrow(538, 263, 570, 263, color=INK, sw=1.8)
    s.text(14, 322, "Compare the photodiode step time with the age that hudd reports for the same frame. A second probe on an LED", size=11, fill=INK2)
    s.text(14, 340, "flashed in front of the road camera measures the whole chain from photons in to photons out.", size=11, fill=INK2)
    s.text(14, 358, "Pass: whole chain ≤ 90 ms; predicted error ≤ 0.3° (section 10). The HUD controller's RP2040 can be the MCU.", size=11, fill=MUTED)
    return s

@fig("storyboard")
def f_storyboard():
    W, H = 680, 170
    s = Svg(W, H, "Five-minute demo script on a timeline from 0:00 to 4:30, six scenes")
    s.rect(0, 0, W, H, fill=SURF)
    scenes = [(0, "0:00", "1 Set up"), (45, "0:45", "2 Pull out"), (105, "1:45", "3 Head tracking"),
              (165, "2:45", "4 Lead car"), (225, "3:45", "5 Pedestrian, sign"), (270, "4:30", "6 Stop")]
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

@fig("gpu")
def f_gpu():
    W, H = 680, 300
    s = Svg(W, H, "Estimated GPU time per frame for each job on the Orin NX, as ranges, against the 30 Hz and 20 Hz frame periods")
    s.rect(0, 0, W, H, fill=SURF)
    x0, x1 = 300, 640
    vmax = 60.0
    sx = lambda v: x0 + v / vmax * (x1 - x0)
    rows = [(n, a, b, BLUE) for n, a, b in GPU]
    rows.append(("Total, if run serially", GPU_MIN, GPU_MAX, INK))
    top = 30; rh = 34
    for t in range(0, 61, 10):
        xx = sx(t)
        s.line(xx, top - 8, xx, top + rh * len(rows) - 6, stroke=GRID, sw=1)
        s.text(xx, top + rh * len(rows) + 6, f"{t}", size=11, fill=INK2, anchor="middle")
    s.text(x1 + 26, top + rh * len(rows) + 18, "ms", size=11, fill=INK2, anchor="start")
    for i, (name, a, b, col) in enumerate(rows):
        y = top + i * rh
        if name.startswith("Total"):
            s.line(14, y - 8, W - 14, y - 8, stroke=AXIS, sw=1)
        s.text(290, y + 5, name, size=11.5, weight=600 if name.startswith("Total") else 400, fill=INK, anchor="end")
        s.rect(sx(a), y - 8, sx(b) - sx(a), 16, fill=col, rx=4)
        s.text(sx(b) + 8, y + 5, f"{a}–{b} ms", size=11.5, fill=INK2)
    for val, lab in ((33.3, "30 Hz"), (50.0, "20 Hz")):
        xx = sx(val)
        s.line(xx, top - 14, xx, top + rh * len(rows) - 6, stroke=CRIT, sw=1.5)
        s.text(xx, top - 18, lab, size=11, weight=600, fill=CRIT, anchor="middle")
    s.text(14, H - 10, "All values are assumptions to be replaced by measurements in Phase 1. Jobs overlap on the GPU, so the serial total is pessimistic.", size=10.5, fill=MUTED)
    return s
