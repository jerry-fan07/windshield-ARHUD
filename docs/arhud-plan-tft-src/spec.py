"""Write the condensed, agent-readable specification (docs/ARHUD-PLAN-TFT-SPEC.md) from the same numbers as the PDF.
Run: python3 spec.py"""
import os, re
from calc import V, LAT, LAT_MIN, LAT_MAX, COST, COST_OPT, GPU, GPU_MIN, GPU_MAX, PGU_TABLE

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "ARHUD-PLAN-TFT-SPEC.md")

def fill(text):
    missing = set()
    def rep(m):
        k = m.group(1)
        if k not in V:
            missing.add(k); return "??"
        return str(V[k])
    out = re.sub(r"\{\{(\w+)\}\}", rep, text)
    if missing:
        raise SystemExit(f"missing values: {sorted(missing)}")
    return out

lat_rows = "\n".join(f"| {n} | {a}–{b} ms |" for n, a, b in LAT)
gpu_rows = "\n".join(f"| {n} | {a}–{b} ms |" for n, a, b in GPU)
cost_rows = "\n".join(f"| {n} | ${lo:,}" + (f"–{hi:,}" if hi != lo else "") + f" | {tag} |" for n, lo, hi, tag in COST)
opt_rows = "\n".join(f"| {n} | ${lo:,}–{hi:,} | optional |" for n, lo, hi in COST_OPT)
pgu_rows = "\n".join(f"| {lab} | {w:.1f} | {M:.1f} | {u:.0f} | {f:.0f} | {R:.0f} | {ppd:.0f} |" for lab, w, M, u, f, R, ppd in PGU_TABLE)

DOC = r"""# Windshield AR HUD, HUD-only TFT LCD edition: condensed specification

Generated 2026-10-21 from `docs/arhud-plan-tft-src/calc.py` (run `python3 spec.py` to regenerate). The full plan with derivations, figures and sources is `docs/ARHUD-PLAN-TFT.pdf` (79 pages). This file is the plan's specification in brief, for use as context by a person or an AI agent. Values tagged ASSUMED are design assumptions to be replaced by the named measurement; UNVERIFIED means not confirmed from a primary source; prices are last seen on 2026-10-21, not quotes.

## 0. Scope in five lines

- A road-registered augmented-reality head-up display (HUD) for a car driven by a person. No self-driving, no driver-assistance stack, no connection to any vehicle bus or actuator; the only vehicle interface is a fused, ignition-sensed 12 V accessory feed.
- One computer (NVIDIA Jetson Orin NX 16 GB) runs its own perception from a stereo road camera, measures ego-motion from GNSS and an IMU, tracks the driver's head, and renders at 60 Hz onto a TFT LCD picture generation unit (PGU).
- A cold-mirror fold and a custom concave mirror relay the PGU image into the windshield as a virtual image 7.5 m ahead, {{fov2_w}}° × {{fov2_h}}°.
- Daylight brightness comes from a custom LED backlight behind a 60 × 30 mm crop of a 5.5-inch 1080p panel; the stock windshield is used (wedge glass optional).
- Twelve-week plan with seven gates; the critical path is car choice → ray trace → custom mirror order → lead time.

## 1. Requirements and acceptance criteria

| Quantity | Requirement | Measured by |
|---|---|---|
| Virtual image distance | ≥ 6 m, target 7.5 m | camera-focus method against a known-distance target |
| Field of view | {{fov2_w}}° × {{fov2_h}}° (10°×4° to 13°×5° acceptable) | rendered grid photographed from the eye point |
| Eye box | ≥ 120 × 60 mm without tracking; design 130 × 70 mm | camera on a rail at the eye point |
| Luminance at the eye, noon, against sky | ≥ 1,500 cd/m² (contrast ratio (overlay+bg)/bg ≥ 1.15 vs 10,000 cd/m²) | spot luminance meter at the eye point, white patch, same direction as the background |
| Luminance at the eye, noon, against sunlit road | ≥ {{l_road_eye}} cd/m² (ratio 1.15 vs 5,000 cd/m² asphalt, ASSUMED) | same meter, lower window against the road; reported separately |
| Night | white ≤ 50 cd/m² at the night setting; unlit window ≤ 0.1 cd/m² | same meter at the night setting |
| Panel (PGU) luminance | ≥ {{need_panel_day}} cd/m² on axis (design {{l_panel_design}}); uniformity ±20% over the crop; ≥ 50% of on-axis at ±{{cone_design}}° horizontal | meter on the panel |
| Cell temperature | under the panel's rating after 30 min at full backlight in a 40 °C enclosure; derate and cut-off thresholds verified | thermistor log, one thermocouple cross-check |
| Static registration at 30 m | ≤ 0.5° | camera at eye point vs surveyed target board; marker from the road camera's own detection, and from the survey, to separate perception from optics error |
| Registration under ±75 mm head motion | ≤ 0.3° | same, camera on a rail, tracker on |
| Motion-to-photon latency | whole chain ≤ 90 ms; predicted (compensated) error ≤ 0.3° | photodiode on the panel triggered by an LED flashed at the road camera; synthetic `lanes` step for renderer+panel alone; cross-check `hudStats` age |
| Ghost image | separation within 2× the predicted {{ghost_7_5}}′; acceptable on demo graphics at three eye heights | photograph at the eye point |
| Sun focus | thermocouple at the focus stays under the cell rating for 10 min with the shutter open at the worst sun position; sun-watch rule closes the shutter inside the entry patch | empty-housing sun test, then a logged drive |
| Installation | checklist signed before each drive: no connector to any vehicle bus, all mounts removable, fuse in place, nothing bonded to the glass | inspection |
| Speed shown | within 1 m/s of a reference GNSS trace while moving; dash without a fix | logged drive vs a phone trace |

Production context (not a requirement): production AR HUDs deliver {{prod_eye_lo}}–{{prod_eye_hi}} cd/m² at the eye (Continental EP3719561; TI DLPA057), implying {{need_panel_prod_lo}}+ cd/m² at the panel through this path. The 1,500 target is a minimum-visibility threshold; collimated backlighting is the route toward production brightness.

## 2. Hardware

Owned: Seeed reComputer J4012 (Orin NX 16 GB; one HDMI 2.1, no DisplayPort; 4× USB 3.2; 9–19 V in; run at MAXN, never MAXN SUPER; recorded 2026-10-07 on JetPack 5.1.3, unreachable since); two YODOIT 16-inch 3840 × 2400 1,200-nit monitors (Stage 0/1 PGU with an 80 × 40 mm crop; audience display); two ACEMAGIC x86 mini PCs (renderer bench and CI; audience view in the car). No CUDA on the mini PCs.

To acquire (USD, last seen 2026-10-21):

| Item | Cost | Basis |
|---|---|---|
""" + cost_rows + r"""
""" + opt_rows + r"""

Total of listed ranges: ${{cost_low}}–{{cost_high}} (previous plan $9,000–17,000). Dropped from the previous plan: comma four + harness, laser projector, wedge windshield (${{cost_removed}} at their low ends).

Key part facts: ZED 2i 4 mm lens (store page 80° × 52°, datasheet 72° × 44°, CONFLICT), depth 1.0/1.5–35 m, rolling shutter, 400 Hz IMU, USB 3, ZED SDK 5.5.1 supports JetPack 6.2.x (installer needs an exact L4T match). ZED X (global shutter, GMSL2) is excluded: needs a ZED Link card and a carrier-certified driver; Seeed J401 is not certified. OAK-D Pro: global-shutter stereo pair, IR flood + dot projector, on-device depth and NN inference (RVC2), BNO086 IMU, $349–429. u-blox ZED-F9R: fused output ≤ 30 Hz, velocity 0.05 m/s, heading 0.2°, dead reckoning ≈ 2% of distance; NEO-M9N ($71, 25 Hz, no DR) is the budget fallback. Panel: Wisecoco 5.5-inch 1920 × 1080 HDMI kit ($95, 450 cd/m²); no 5-inch 1080p kit exists; budget option Waveshare 5-inch 720 × 1280 ($60, 350 cd/m², 62.1 × 110.4 mm → {{w720_ppd}} px/deg). Industrial sunlight-readable panels top out near 1,600 cd/m² (Litemax 7-inch); the common class is 1,000–1,100 (Newhaven 5-inch HDMI 1,100 nit $74.75, used for Stage 1 nights). HUD-grade TFTs (Kyocera 1.1–3.1 inch, 6–8.5% transmittance, −40…+105 °C; Tianma 4.1-inch 1280 × 640 collimated) publish no luminance and are not sold singly; used OEM HUD units are $80–650 on eBay and nobody has documented re-driving one (experiment, not critical path). Luminance meter: Konica Minolta LS-150 (1° spot, 1 m to ∞, ≈$3,900) assumed; Sekonic L-858D ($689, 1° spot) if it can focus on a virtual image (UNVERIFIED).

## 3. Architecture and interfaces

- Single host. Sensors → Jetson over USB; Jetson → panel driver board over HDMI (1920 × 1080 at 60 Hz, only the crop lit); Jetson → mini PC 2 over Ethernet (MJPEG audience stream, 15 Hz); Jetson ↔ RP2040 HUD controller over USB serial.
- Mounting: road camera high on the windshield centreline near the mirror stalk (within ≈ {{b_ce}} of the driver's eye; registration depends on this baseline, see §5.4); driver camera on the dash or column shroud; GNSS antenna on the dash; dash-top housing removable without tools; nothing bonded to the glass.
- Power: car 12 V → Mini-Box DCDC-USB-200 (ignition-sensed, configurable shutdown delay, 11.2 V cut-off) → Jetson and the LED driver; 5 V buck or Jetson USB → panel board; USB-C PD charger → mini PC 2 and monitor 2.
- Clock: one monotonic clock; camera timestamps translated at capture; every topic carries the capture time of the sensor frame it came from.

### 3.1 Processes (one process per job; supervisor restarts a crashed process after 1 s and marks its topics stale)

| Process | Role | Publishes |
|---|---|---|
| `roadd` | owns the ZED 2i: capture 30 Hz, stereo depth, RANSAC ground-plane fit on the road region, IMU stream; lifts 2D lanes and boxes to the car frame; records SVO on request | `lanes`, `objects`, `imu` |
| `laned` | lane network on the left image (TensorRT FP16); up to 4 lines as image points + confidence, road edges if available | `lanes2d` |
| `detectd` | object detector (TensorRT FP16) + tracker; sign classifier on sign crops | `objects2d` |
| `egod` | fuses ZED-F9R (serial) and `imu` into speed, yaw rate, pitch, fix quality at 100 Hz; computes the sun direction in the car frame at 1 Hz | `ego`, `gnss`, `sunWatch` |
| `headtrackd` | owns the OAK-D Pro: on-camera face detection + landmarks, on-camera stereo depth at the eye landmarks; eye midpoint in the car frame + confidence | `eyePose` |
| `hudd` | renderer: age compensation, eye projection, 60 Hz draw with vsync, pre-distortion warp pass, full-screen HDMI | `hudFrame` (downscaled), `hudStats` |
| `controllerd` | RP2040 link: ambient light, cell thermistor, backlight duty from the dimming curve, shutter from `sunWatch` and power state, health flags | `health` |
| `logd` | records all topics with timestamps; triggers camera recordings | files |
| `audienced` | composites HUD frame + driver camera with eye point + live numbers; streams to mini PC 2 | MJPEG/HTTP |

### 3.2 Topics (ZeroMQ PUB/SUB over ipc, msgpack maps; each message: capture time, publish time, sequence; empty messages are still published so silence ≠ absence; graph is a tree with `hudd` at the root)

| Topic | Rate | Fields |
|---|---|---|
| `lanes` | 30 Hz (20 if GPU-bound) | per line: car-frame points on the fitted plane, confidence, type (ego left/right, other, edge); plane parameters; capture time |
| `objects` | 30 Hz | per track: id, class, bearing, range, car-frame position, velocity, image box, track age, sign value; capture time |
| `ego` | 100 Hz | speed, yaw rate, pitch, pitch rate, longitudinal accel, fix quality, source flags |
| `gnss` | 10 Hz | position, course, speed, accuracies, time |
| `eyePose` | 30 Hz | eye midpoint (car frame), confidence, capture time |
| `health` | 2 Hz | ambient lux, backlight duty, cell temperature, shutter state, process liveness, SoC temperatures |
| `sunWatch` | 1 Hz | sun azimuth/elevation in the car frame, inside-patch flag |
| `hudStats` | 10 Hz | age per topic as drawn, render time, dropped frames, last registration residual |

## 4. Content (what is drawn)

1. Lane ribbon: translucent fill between the ego lane's two detected lines, from the window's bottom edge to the last confident point (typ. 40–60 m). Hero element; never called a path.
2. Lane lines and road edges: thin lines over the paint where confident, faded by confidence.
3. Lead vehicle chevron under the nearest tracked vehicle in the ribbon within 80 m, with gap in metres and seconds (seconds only above 3 m/s).
4. Speed block (fixed, non-conformal): GNSS speed + fix glyph; last speed-limit sign value + sign glyph (10 min timeout); dash without a fix.
5. Hazard outlines: tracked pedestrians, cyclists, signs; informational only.
6. Audience view on monitor 2: rendered frame, driver camera with the eye point, live registration/age/contrast numbers beside their targets.

Excluded: any drive path (nothing plans), lane-departure warnings (stretch), navigation arrows (stretch), full-windshield clutter (a 10 s "clutter mode" exists only as a demo contrast).

## 5. Perception specification

### 5.1 Road sensor and ground plane
ZED 2i, 4 mm lens, 1080p or 720p at 30 Hz. Ground plane: own RANSAC fit on the depth map's road region every frame (the SDK's plane API requires positional tracking, which costs ≈ 44% of the Orin NX GPU, and the SDK's visual-inertial tracking is unreliable in cars; both are cross-checks only). Fallback when the fit fails: calibrated static ground plane + IMU pitch. Lane points = ray from camera ∩ fitted plane.

### 5.2 Networks
- Lanes (choose in Phase 1 by measured score on course recordings): Ultra Fast Lane Detection v2 (MIT, CULane F1 75–76, ships ONNX/TensorRT scripts; 36 fps on a TX2 at 320 × 800 FP32) first; CLRNet/CLRerNet (Apache, F1 79.6–81.4) second; CondLaneNet (Apache); YOLOP/YOLOPv2 (MIT, BDD100K, multi-task) if one inference must do everything. No published Orin figures for any of them.
- Objects: YOLO11s FP16 TensorRT, 7.9 ms per 640-px image on an Orin NX 16 GB (Ultralytics table; INT8 accuracy collapses on this board, so FP16). AGPL-3.0: fine while the repository is public; Apache alternatives RF-DETR Nano (6 ms on the same board) or NVIDIA TAO DashCamNet. COCO classes used: person, bicycle, motorcycle, car, bus, truck, stop sign, traffic light.
- Tracker: ByteTrack or OC-SORT (MIT, CPU; association ≈ 700 fps on a desktop CPU).
- Signs: tiny classifier on sign crops for US speed-limit values; datasets LISA (academic licence) or Mapillary Traffic Sign (research edition). Accept a value after two consistent reads of a tracked sign. Stretch within the demo.

### 5.3 Range and lead rules
Range = median stereo depth over the lower fifth of the box; beyond stereo range (35 m for the 4 mm lens) use the ground plane at the box base. Lead = nearest tracked car/bus/truck/motorcycle whose base is inside the ribbon. Chevron drawn at the bearing of the box's bottom centre at that range, on the ground.

### 5.4 Registration error model (why range barely matters)
Bearing comes from the image and is exact; a range error Δz moves the eye-side mark by ≈ b·Δz/z² (b = camera-to-eye baseline, {{b_ce}}). 10% range error: {{reg_10_1m}}° at 10 m, {{reg_20_10pct}}° at 20 m, {{reg_30_10pct}}° at 30 m. Stereo error (0.25 px disparity, f ≈ 1,144 px, B = 0.12 m): {{sdz_10}} m at 10 m, {{sdz_20}} m at 20 m, {{sdz_30}} m at 30 m, {{sdz_50}} m at 50 m → {{sreg_30}}° at 30 m. Static-plane fallback with a 1° pitch error moves a 20 m lane point to {{pitch_z1}} m → {{pitch_reg}}° at the eye. Keep the camera within ≈ 0.5 m of the eye; a dash-top camera doubles every number.

### 5.5 Ego-motion
GNSS Doppler speed (ZED-F9R, 0.05 m/s) as the unbiased reference; ZED IMU gyro for yaw rate (low latency); accelerometer propagates speed between GNSS updates and corrects GNSS latency (unspecified by u-blox; ≈ 12 ms measured by one user on a similar module; treat as a parameter measured with the LED test). Below 1 m/s: speed shows 0, no prediction. No fix: dash + glyph, no prediction.

### 5.6 GPU budget (ASSUMED except where cited; measure in week 1)

| Job | Per frame |
|---|---|
""" + gpu_rows + r"""
| Serial total | {{gpu_min}}–{{gpu_max}} ms |

Frame period {{gpu_frame_30}} ms at 30 Hz ({{gpu_load_30_min}}–{{gpu_load_30}} load) and {{gpu_frame_20}} ms at 20 Hz ({{gpu_load_20_min}}–{{gpu_load_20}}). Cited: ZED NEURAL_LIGHT 23% / NEURAL 59% GPU at 30 fps on an Orin NX 16 GB (Stereolabs); YOLO11s 7.9 ms (Ultralytics). Run camera-rate topics at 30 Hz if measurements allow, else 20 Hz; depth may run at half the network rate.

### 5.7 Phase 1 score (gate G1), on 300 hand-labelled frames of the demo course
Ego lane found ≥ 95% of frames; lane lateral error ≤ 0.15 m at 10 m, ≤ 0.3 m at 20 m, ≤ 0.5 m at 30 m; ego-lane vehicles within 50 m recalled ≥ 90%; pedestrians within 30 m ≥ 85%; range within 10% of the stereo median. Fallback if failed: comma four in passive mode (§12).

## 6. Rendering specification

- Projection chain: `D @ K_eye @ view_from_eye @ eye_from_car`. Car frame: x forward, y right, z down, origin at the ZED left lens; ground from the stereo plane. `eye_from_car` = fixed nominal eye point (tape, then refined with a 30 m target board) + live head-tracker offset. `view_from_eye` = look along x, depressed by the look-down to the window centre. `K_eye` = pinhole for the virtual plane: focal (px) = (crop height / 2) / tan(vfov / 2). `D` = 2-D pre-distortion mesh fitted from a photographed rendered grid, applied as a render-to-texture pass.
- Age compensation, applied before projection: `age = t_now − t_capture`; `p_now = Rz(−∫yawRate dt) · (p_capture − [∫v dt, 0, 0])`, integrals from `ego` over the age. Confirm the sign and rotation direction on a recording before any drive. Tracked objects are additionally advanced by their own tracked velocity.
- Worked numbers (eye 1.22 m high, point 10 m ahead, 30 m/s, 100 ms): uncompensated shift {{uncomp}}° ({{dep0}}° → {{dep1}}°); residual {{resid_deg}}° for 1 m/s² unmodelled acceleration; {{resid_speed_deg}}° for a 1 m/s speed error.
- Parallax for a 150 mm head shift: {{par_7_5}}° at 7.5 m, {{par_10}}° at 10 m, {{par_30}}° at 30 m → the head tracker is part of the design.
- Output: 1920 × 1080 at 60 Hz, vsync on, raylib (GL 3.3 core) full screen; only the {{crop_px_w}} × {{crop_px_h}} px crop is drawn, the rest black.

Drawing rules (proposed; confirm in Phase 3):

| Rule | Value |
|---|---|
| Stale cutoff | `lanes`/`objects`: fade over 300 ms once older than 250 ms, gone at 600 ms. `ego`: prediction off at 200 ms, speed dash at 1 s. `eyePose`: nominal eye point after 500 ms + glyph |
| Lane-line fade | appear above confidence 0.6, full at 0.8; fade below 0.5, gone at 0.3; 3 consecutive frames before first appearance |
| Ribbon | between the two ego lines where both drawn; one line missing → standard 3.7 m width from the other, lighter tint; far end = nearer of the two lines' last confident point |
| Hazards | 3 consecutive detections with confidence > 0.5; persist 400 ms after the last detection, fading in the last 200 ms; drawn only inside the window |
| Lead chevron | nearest tracked vehicle in the ribbon within 80 m; not drawn when the ribbon is not drawn |
| Draw region | nothing below the window's bottom edge or above horizon + 2° |
| Brightness | backlight duty follows the ambient sensor from the night ceiling to full at ≥ 10,000 lux; 1 s update, 1 s ramp; driver offset ± one step |
| Clutter mode (demo) | all lines regardless of confidence, every track outlined, gap text at every vehicle, 10 s on a key press |

## 7. Optics specification

### 7.1 Geometry (single-mirror model; windshield not yet in the model)
Concave spherical first-surface mirror f = {{f2}}, radius {{r2}}, aperture ≈ 300 × 200 mm (from eye box + field at ≈ 1 m path: {{mir_w}} × {{mir_h}} mm; about f/1.1). PGU (object) distance u = {{u2}} (inside f → virtual image); virtual image at 7.5 m from the eye; magnification {{m2}}; image {{img2_w}} × {{img2_h}}; field {{fov2_w}}° × {{fov2_h}}°. The mirror cannot be ordered until a ray trace includes the chosen car's windshield curvature, eye point and eye box; the trace must also report the solar spot at the panel.

PGU active-width options (same window at 7.5 m):

| Active region | w (mm) | M | u (mm) | f (mm) | R (mm) | px/deg |
|---|---|---|---|---|---|---|
""" + pgu_rows + r"""

### 7.2 Windshield reflection and polarisation
Fresnel, n = 1.52, 65° incidence: s = {{rs65}}, p = {{rp65}} (ratio {{rs65_x}}); Brewster {{brewster}}°. Both surfaces overlapping (wedge glass or a broad patch): {{rs65_two}}. The panel's output is linearly polarised: measure its axis (often 45° to the edges) and orient it s to the windshield, or add a half-wave retarder film. The dielectric cold-mirror fold must be oriented with its plane of incidence aligned to the windshield's and its s-reflectance checked. An s-pass polariser on the dust cover passes the image and halves unpolarised sunlight. Polarised sunglasses block the image: demo rule, no polarised eyewear. Assumed rake {{rake}}°, look-down {{lookdown}}° → incidence {{inc_check}}°.

### 7.3 Ghost image (plain laminate, ASSUMED {{t_glass}} = 2.1 + 0.76 + 2.1)
Reflected rays parallel, offset {{ghost_perp}} (= 2t·tanθt·cosθi, θt = {{theta_t}}°); seen as d / D: {{ghost_2}}′ at 2 m, {{ghost_7_5}}′ at 7.5 m ({{ghost_px}} px of {{px_arcmin}}′), {{ghost_10}}′ at 10 m; ghost brightness {{ghost_rel}} of the main image. Checked against Lumetrics' example (0.0643° at 2.75 m eye-to-image). TI DLPA057: wedge glass "no longer required" at long virtual image distances. Decision: stock windshield; lines ≥ 6 px, ribbons as area fills, heavy text; wedge-PVB glass ($600–1,500) only if the Stage 2 photograph says so.

### 7.4 Luminance budget (cd/m²; path = 0.90 × 0.90 × 0.236 = {{path_ws}}; both surfaces {{path_ws_two}})
Panel needed: {{need_panel_day}} for the sky target ({{need_panel_day_two}} with both surfaces), {{need_panel_road}} for the road target, {{need_panel_night}} for the night ceiling.

| PGU | At panel | At eye | Share of sky target | Ambient beaten (eye/0.15) |
|---|---|---|---|---|
| YODOIT monitor (Stage 0/1 via 30% combiner: {{yod_comb}}) | {{yod_panel}} | {{yod_ws}} | {{yod_pct}} | {{yod_amb}} |
| 5.5-inch kit, stock backlight | {{stock_panel}} | {{stock_ws}} | {{stock_pct}} | {{stock_amb}} |
| Industrial sunlight-readable (brightest found) | {{ind_panel}} | {{ind_ws}} | {{ind_pct}} | {{ind_amb}} |
| 5.5-inch panel + custom backlight (design) | {{bl_panel}} | {{bl_ws}} | {{bl_pct}} | {{bl_amb}} |
| Same, collimated (gain {{gain_collim}}, ASSUMED) | {{blc_panel}} | {{blc_ws}} | {{blc_pct}} | {{blc_amb}} |
| HUD-grade TFT (Continental's figure, UNVERIFIED) | {{hud_panel}} | {{hud_ws}} | {{hud_pct}} | {{hud_amb}} |

Scene references: clear sky at noon ≈ 10,000; overcast ≈ 1,000; sunlit asphalt {{asph_lo}}–{{asph_hi}} (0.07–0.10 cd/m² per lux). Dimming: {{dim_day_night}} from the sky target to the night ceiling; {{dim_bl_night}} from full custom backlight to night; PWM covers it. Black level (IPS {{cr_panel}} ASSUMED): {{black_day_eye}} cd/m² at the eye by day, {{black_night_eye}} at night (faint rectangle risk; VA cell is the alternative).

### 7.5 TFT PGU and backlight
Panel: 5.5-inch 1920 × 1080 IPS HDMI kit; active {{panel_w}} × {{panel_h}} mm (ASSUMED from the diagonal), pitch {{pitch_5}} µm; crop 60 × 30 mm = {{crop_px_w}} × {{crop_px_h}} px = {{crop_frac}} of the panel; {{ppd2}} px/deg; {{mm_per_px_75}} mm per px at 7.5 m. Stock edge-lit backlight removed; direct-lit unit behind the crop: 6–8 high-power white LEDs on a star board + heat sink + fan → 20–25 mm white mixing cavity → diffuser plate → crossed prism films → IR-cut glass → the panel's own cell and polarisers (+ half-wave retarder if the axis is wrong). Design: {{l_panel_design}} ÷ T_cell {{t_lcd}} (ASSUMED; measure stock luminance / backlight luminance with the cell removed) = {{l_bl}} cd/m² backlight; Φ = π·L·A = {{phi_out}} lm from the {{a_crop_cm2}} cm² crop; at {{eta_bl}} optical efficiency and {{led_lmw}} lm/W: {{p_led}} LED ({{p_led_film}} with films, gain {{gain_film}} ASSUMED; {{p_led_collim}} collimated). Cell absorbs ≈ {{p_abs_cell}} ({{irr_cell}} W/m²). Lighting the whole panel instead would need {{p_led_full}}. Emission cone needed for the eye box: ±{{cone_h}}° × ±{{cone_v}}° (design ±{{cone_design}}°); a Lambertian panel puts {{lamb_frac}} of its flux in that cone (ideal collimation gain {{collim_ideal}}×). LED driver: constant current with analogue + PWM dimming (Recom RCD-24 class); PWM > 2 kHz to avoid camera beat (Mean Well NLDD-H is PWM ≤ 1 kHz, not chosen). Thermal: consumer LC clears near 75 °C, automotive > 100 °C, Kyocera HUD panels rated 105 °C, industrial modules 70 °C operating; thermistor derates then blanks.
Panel measurement order (Phase 5): stock luminance and uniformity; backlight luminance without the cell (→ transmittance); polarisation axis; contrast; custom backlight on/off axis and cell temperature vs time; HDMI board input lag with the photodiode.

### 7.6 Build stages
- Stage 0 (bench, weeks 1–3): panel face-up, 70/30 teleprompter beamsplitter at 45°, virtual image ≈ 0.6 m; renderer, colour, latency instrumentation.
- Stage 1 (in car, weeks 4–8): 300 mm Fresnel f = 300 mm, panel at 280 mm → v = −{{s1_dist}}, M = {{s1_M}}, 80 × 40 mm crop → {{s1_w}} × {{s1_h}} at ≈ 4.2 m, {{s1_angw}}° × {{s1_angh}}°, {{s1_ppd}} px/deg on the monitor; free-standing combiner above the dash; night/overcast; the demo fallback.
- Stage 2 (weeks 6–12): panel → cold-mirror fold (passes solar IR to an absorber) → concave mirror → windshield → eye; dust cover with s-pass polariser and shutter; 3D-printed matte-black housing; keystone corrected by the pre-distortion mesh; residual astigmatism accepted.

### 7.7 Sun hazard
On-axis trace: 90% of rays within {{r90_pgu}} mm at the panel plane (focus is {{focus_gap}} beyond the panel); concentration ≈ {{conc_pgu}}×; collected ≈ {{sun_w}} (1,000 W/m² × 0.06 m² × {{ws_t_sun}} windshield, ASSUMED) into a {{sun_spot_mm}} mm spot = {{sun_wcm2}} W/cm². After the cold mirror alone (visible share {{vis_frac}}, ASSUMED) {{sun_after_cold}}; after cold mirror + IR-cut glass ({{filt_frac}} passes, TI DLPA096) {{sun_after_filt}}; after the aperture polariser ({{pol_t}}, ASSUMED) {{sun_after_pol}} = {{sun_after_pol_wcm2}} W/cm² ≈ {{sun_suns}} suns ≈ {{sun_after_pol_kwm2}} kW/m², {{sun_vs_ti}}× TI's production peak ({{ti_peak}} kW/m²) and {{sun_vs_ti_tft}}× the 12 kW/m² that raised a BMW HUD TFT 45 °C. Entry direction: the HUD ray reflected in the glass continues to the sky at {{sun_elev}}° elevation behind the car (rake {{rake}}°; {{sun_elev_25}}° at 25°, {{sun_elev_35}}° at 35°); entry patch ≈ {{patch_w}}° × {{patch_h}}°; the sun crosses it in ≈ {{patch_minutes}} min at fixed heading. Defences, in order: shutter closed whenever the HUD is off (fails closed); sun-watch rule (sun vector from GNSS time/position/heading vs the ray-traced patch → close shutter, blank, glyph, log); cold-mirror fold + IR-cut glass + aperture polariser; thermistor cut-off; thermocouple test of the empty housing before any sun exposure. Note: a production freeform mirror spreads the spot; ask the mirror shop to report it.

### 7.8 Calibration (stored in a YAML file on the Jetson; redo per car and after any camera remount)
(1) car frame → nominal eye (tape + 30 m target board; head tracker adds a live offset; driver camera pose measured once); (2) eye → virtual plane pinhole (camera at the eye point photographs a rendered grid vs a ground grid); (3) pre-distortion mesh from the same photograph.

## 8. HUD controller (Raspberry Pi Pico / RP2040)
Inputs: ambient-light sensor at the dust cover (TSL2591 or VEML7700), NTC on the cell's back, MAX31855 thermocouple for the sun test. Outputs: backlight PWM (> 2 kHz) / analogue dim to the LED driver, shutter servo. Reports over USB serial at 10 Hz. Fail-safe rules independent of the Jetson: above threshold 1 halve the duty; above threshold 2 backlight off + shutter closed; USB silent 5 s → same.

## 9. Software layout and bench
New standalone package `hud/` in the repository (no openpilot build dependency; openpilot tree is reference only: `selfdrive/ui/onroad/model_renderer.py`, `system/ui/lib/application.py`). Jetson: reflash to JetPack 6.2 from Seeed's image (Ubuntu 22.04, Python 3.10, TensorRT 10); install the ZED SDK package matching the reported L4T; MediaPipe is unsupported on Jetson (on-camera landmarks primary; OpenSeeFace is the CPU alternative). Recording/replay: ZED SVO (replays through the same capture call) + topic logs; replay tool publishes logs at original timing; clip tool renders hudd output to MP4 for regression (nightly on mini PC 2). Perception bench runs on the Jetson (needs CUDA); renderer bench on mini PC 1 from topic logs. Replay has no live latency: only the photodiode test measures the real chain. Audience view: Ethernet stream to mini PC 2 (the J401 has one HDMI).

## 10. Latency budget (estimates; replace with the photodiode measurement in Phase 2)

| Stage | Estimate |
|---|---|
""" + lat_rows + r"""
| Total, uncompensated | {{lat_min}}–{{lat_max}} ms ({{lat_travel_min}}–{{lat_travel_max}} m at 30 m/s) |
| Head tracker (parallax only) | 30–50 ms |

## 11. Phases and gates (weeks from the day the car and venue are agreed)

| Phase | Weeks | Work | Gate (done when) |
|---|---|---|---|
| 0 Decide and order | 0–1 | choose car (measure rake, thickness, dash); order non-car-dependent parts; request mirror quotes (state the f-ratio); venue; sign-off; installation checklist | G0: car named, orders placed, venue agreed, checklist exists |
| 1 Recordings and perception | 1–4 | reflash JetPack 6.2; ZED SDK, TensorRT exports; measure GPU time per job; record course (day/dusk/night) + ordinary road from the passenger seat; label 300 frames; build roadd/laned/detectd + scoring; choose lane net; egod on the bench then a drive vs a phone trace | G1: §5.7 scores pass; GPU time known |
| 2 Bench HUD + Stage 0 | 1–3 | topic schemas; hudd vs synthetic then recorded logs; drawing rules; prediction sign on a recording; controller firmware + dimming curve; latency probe; hudd on the Jetson full screen | G2: 60 fps from a log on the rig; whole chain ≤ 90 ms by photodiode + LED; sign confirmed |
| 3 Live in car on a monitor | 3–5 | mount cameras, antenna, Jetson, power; checklist; overlay on the road camera image in the footwell; camera-to-car + eye calibration; headtrackd on the audience view | G3: overlay within 0.5° of paint and lead for 20 min at ≤ 25 m/s with prediction; GNSS speed within 1 m/s |
| 4 Stage 1 combiner | 4–8 | dash enclosure (panel, Fresnel, combiner); target-board calibration; mesh; night/overcast drives; registration on the rail | G4: static ≤ 1.0° at 30 m; ribbon on the lane through curves at 25 m/s |
| 5 Picture generator | 4–8 | stock panel measurements; backlight build; on/off-axis luminance; thermal; retarder; thermocouple sun test of the empty housing | G5: ≥ {{need_panel_day}} cd/m² on axis, ±20%, cell under rating after 30 min at 40 °C, polarisation oriented, input lag measured |
| 6 Stage 2 daylight | 6–12 | ray trace → mirror → housing with fold, mirror, dust cover, shutter; recalibrate; ghost photos at 3 heights; noon luminance vs sky and road; night black level; dimming curve | G6: every row of §1 passes at noon |
| 7 Hazards, signs, rehearsal | 8–12 | hazard rules with a volunteer; sign classifier (drop if unreliable); clutter review; audience layout; three rehearsals | G7: script runs twice without an operator touching the Jetson |

Unknowns that move dates: mirror lead time (unquoted), camera/GNSS delivery, ray-trace time, backlight uniformity iterations, lane-net generalisation to the course.

## 12. Alternatives considered (one line each)
- comma four as a passive sensor head: VERIFIED in this checkout, `openpilot/selfdrive/car/card.py` lines 113–117 set `CP.passive` and panda safety model `noOutput` when `OpenpilotEnabledToggle` is off (`selfdrived.py` line 46 ignores `noOutput`); the previous plan's bridge + renderer would then work unchanged. Rejected: $1,098 (price read 2026-10-08), supported-car + harness constraint, whole openpilot runtime in the loop. It is the fallback if G1 fails.
- openpilot's driving model on the Jetson as perception: blocked (no CUDA build in this tree; comma camera geometry); would reintroduce a planned path.
- Monocular + flat road: fallback mode only (pitch sensitivity §5.4, no lead range).
- OBD-II/CAN speed: even "read-only" dongles transmit; car-specific; GNSS suffices.
- Radar: unnecessary; bearing from the image, range from stereo.
- ZED X (global shutter): needs a capture card + certified-carrier driver; J401 not certified.

## 13. Risks (short)
Lane net does not generalise to the course (score early; fine-tune; passive comma four fallback) · plane fit fails in traffic/rain/night (static-plane fallback, {{pitch_reg}}° per degree at 20 m) · GPU over-subscribed (20 Hz, half-rate depth, lighter modes) · backlight hot spots/heat (mixing cavity ≥ LED pitch, diffuser, thermistor derating, 30 min test) · panel short of the sky target ({{bl_headroom}}× margin; films, collimation, HUD-grade module) · night window glow (dimming curve, VA cell) · panel-board input lag (measure; other board) · mirror lead time/quality (Stage 1 fallback) · relay geometry depends on the windshield (ray trace before order) · ghost worse than predicted (wedge glass option) · sun focus (five defences) · head tracker at night (IR illuminator) · GNSS outages (dead reckoning, open-sky course) · camera mount drift (rigid bracket, target check before demos) · prediction sign wrong (confirm on a recording) · stale data (rules + empty messages) · polarised sunglasses (demo rule) · panel polarisation orientation (measure; retarder) · attention capture (conformal, sparse) · Jetson state unknown (verify before flashing) · GNSS speed ≠ speedometer (labelled).

## 14. Legal (confirm locally) and demo conditions
No federal HUD standard; state windshield-obstruction statutes (e.g. California VC 26708; Texas 547.613; Florida 316.2952) govern objects on or near the glass; the windshield camera sits where factory/aftermarket cameras go but must be checked per state. Dash-top housing with nothing attached to the glass is the least exposed configuration; the Stage 1 combiner is more exposed. Demo: closed course or private lot, a safety driver who is not the presenter, university risk-office sign-off before any public road use; no polarised eyewear.

## 15. Open decisions and assumptions
Decisions gating Phase 0: which car (rake/curvature → mirror ray trace; dash top); demo venue; who signs off the installation.
Open: HUD-grade TFT purchasability; venue permission for a lead car and a volunteer pedestrian; whether Stage 1 is shown; ray-trace outputs (f, u, mirror figure, sun patch); lane-net choice/fine-tuning; the bought panel's transmittance, contrast and temperature rating; ZED VIO usability; panel-board input lag; ghost acceptability; stretch goals (collimated backlight, lane-departure glow, navigation arrows, p-polarised glass).
ASSUMED values (replace by measurement): mirror reflectance 0.90 each; windshield s-reflectance 0.236 at 65°; laminate {{t_glass}}; cell transmittance {{t_lcd}}; IPS contrast {{cr_panel}}; backlight optical efficiency {{eta_bl}}; LED efficacy {{led_lmw}} lm/W; film gain {{gain_film}}; collimated gain {{gain_collim}}; stock panel 450 cd/m² (vendor); panel active area from the diagonal; eye-to-glass 750 mm; eye-to-mirror path 1 m; rake {{rake}}°, look-down {{lookdown}}°; windshield solar transmission {{ws_t_sun}}; visible share after a cold mirror {{vis_frac}}; polariser 42%; camera-to-eye baseline {{b_ce}}; road camera height 1.30 m; disparity error 0.25 px; sunlit road 5,000 cd/m²; GPU per-job times except the two cited.

## 16. Decision-driving sources (read 2026-10-21)
TI DLPA057 ti.com/lit/pdf/dlpa057 (AR HUD distances; wedge not required at long VID; 15,000 cd/m²) · TI DLPA096 ti.com/lit/wp/dlpa096/dlpa096.pdf (solar load) · Lumetrics wedge-angle note lumetrics.com (ghost geometry) · Continental EP3719561 (virtual image 10,000–15,000; LCD 50,000–100,000) · NS International US12699266B2 (cold-mirror fold, hot-mirror glass) · Stereolabs depth modes docs.stereolabs.com/docs/depth-sensing/depth-modes, tracking modes, plane detection, ZED 2i store/datasheet · Ultralytics DeepStream Jetson guide docs.ultralytics.com/guides/deepstream-nvidia-jetson/ · Seeed J4012 wiki wiki.seeedstudio.com/reComputer_J4012_Flash_Jetpack/ · u-blox ZED-F9R datasheet (SparkFun CDN) · Kyocera display.kyocera.com/automotive-displays · 3M BEF/DBEF data (orientdisplay.com uploads) · AGC p-polarised HUD news · SAE J1757-2; ISO/TS 21957 · FHWA road-lighting report (asphalt luminance coefficients).
"""

if __name__ == "__main__":
    text = fill(DOC)
    open(OUT, "w", encoding="utf-8").write(text)
    words = len(text.split())
    print("wrote", os.path.normpath(OUT), words, "words")
