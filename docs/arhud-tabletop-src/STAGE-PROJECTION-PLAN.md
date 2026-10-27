# Brief: write the projection software for the tabletop AR HUD bench

You are writing the display side of the two-monitor tabletop bench described in
`docs/ARHUD-TABLETOP-DESIGN.pdf` (source in `docs/arhud-tabletop-src/parts/`). The bench is a
teleprompter turned on its side: monitor unit 1 (the PGU) lies face up under a 45° beamsplitter,
monitor unit 2 (the road monitor) stands upright behind the glass showing a recorded drive, and the
viewer sees the PGU's reflection lying exactly on the road picture. Your code puts the road on
monitor 2 and the registered HUD overlay on monitor 1.

## Scope

In scope (the design's stages T-A software, T-B, T-C, the T-E calibration and sync modes, the
display half of T-F):

- `hud/` package skeleton, bus, clock, schemas, config and calibration loaders.
- Test card and grid tools for setting the flip and checking coplanarity.
- `roadsrc`: the full-screen road player with life-size crop, vsync scheduling, frame-ID strip,
  timing patch, ego and truth republishing. Sources: any video file, comma2k19 segment, openpilot
  comma-three route, MetaDrive bench recording.
- `hudd`: the renderer on the PGU with the plan's drawing rules, the bench projection chain, the
  flip-plus-homography warp, gain, sync and live modes, age compensation, stats.
- `tools/synth.py` (synthetic topics), `tools/calib_rig.py` (mirror homography),
  `tools/calib_source.py` (source pitch from a vanishing point, manual clicks), the MetaDrive
  exporter in `docs/arhud-road/tools/`, and `scored` for the display-chain residual.

Out of scope, a second brief: `laned`, `detectd`, `planed` (perception), the Pico photodiode
latency tool, `headtrackd` and the parallax variant, the camera-in-the-loop path. Leave clean seams
for them (topics and schemas exist, nothing publishes them yet).

## The windowing requirement (overrides design §10.3)

The owner drags windows to the right display by hand. So:

- Every GUI process opens as a normal, decorated, resizable window on whatever display the
  launching terminal is on. Title shows the role: `ARHUD PGU`, `ARHUD ROAD`, `ARHUD CALIB`.
- Key `F` (and the `--fullscreen` flag) switches to borderless fullscreen on the monitor the window
  is currently on. Use raylib ≥ 5.0 `ToggleBorderlessWindowed` with `GetCurrentMonitor`, not native
  fullscreen, so macOS Spaces do not interfere. `F` again returns to a window.
- Optional `--monitor N` moves the window to monitor N first for scripted runs. No EDID matching.
- `--scale 0.5` is the development mode: a half-size window, all pixel maths at full resolution
  (below), so the Mac's internal display can stand in for either monitor.

## macOS pixel exactness (the design underplays this)

The attached YODOIT runs at 3840 × 2400 with "UI looks like 1920 × 1200", exactly 2×. Only that
setting gives a backing store equal to the panel. Build for it:

- Set `FLAG_WINDOW_HIGHDPI` before `InitWindow`.
- Render every frame into a `RenderTexture` of the monitor's physical size (3840 × 2400) and blit it
  once to the screen. All drawing code works in physical pixels and never sees logical units.
- After going fullscreen, assert `GetRenderWidth() == 3840 and GetRenderHeight() == 2400`. If not,
  print the fix in one line (display set to the default "looks like 1920 × 1200"; HiDPI flag on)
  and keep running.
- Upload source frames to a texture at their native size and let the GPU scale them through the
  crop rectangle with bilinear filtering. Never CPU-resize a frame to 3840 × 2400.
- If raylib's HiDPI path blocks pixel-exact output, you may switch the display layer to
  pyglet or moderngl. Report the reason; keep the rest of the package unchanged.

## Read first

| What | Where |
|---|---|
| The design, chapters 2, 3, 6, 8, 10, 11 and appendix B | `docs/arhud-tabletop-src/parts/02_rig.html`, `03_optics.html`, `06_display.html`, `08_calibration.html`, `10_software.html`, `11_stages.html`, `13_appendix.html` (or the PDF) |
| Every bench number, as code | `docs/arhud-tabletop-src/tcalc.py` (`python3 tcalc.py` prints all keys); it imports `docs/arhud-plan-tft-src/calc.py` |
| Build stage B6: test card, synthetic log, hudd's two passes, drawing rules, sign test | `docs/arhud-build-src/parts/08_b6.html` |
| The plan's architecture, content, rendering rules | `docs/ARHUD-PLAN-TFT-SPEC.md` §3, §4, §6 |
| Working Python hudd with the drawing rules, to port | `docs/arhud-road/arhud_road/hudd.py`, `canvas.py` (cv2 drawing), `perception.py` (`apply_delta`), `frames.py` (projection), `plan.py` (numbers), `truth.py` |
| The MetaDrive app the exporter extends | `docs/arhud-road/run.py`, `arhud_road/app.py`, `world.py`; README for the venv and macOS notes |
| comma camera models | `openpilot/common/transformations/camera.py` in this checkout (`_neo_config` 1164 × 874 f = 910; `_ar_ox_config` 1928 × 1208 f = 2648) |

## Numbers (from tcalc.py; do not rederive, do read them from calc/config at runtime)

| Quantity | Value |
|---|---|
| Monitor, both units | 3840 × 2400 px, 352.1 × 220.1 mm, pitch 0.0917 mm (277 ppi), 1,200 cd/m² vendor white |
| Glass centre to PGU face and to road monitor face | 200 mm each (coplanar) |
| Eye to glass centre, eye to image | 400 mm, 600 mm (`d_img`, a config value) |
| Life-size field of the road monitor at 600 mm | 32.7° × 20.8°, 115 px per degree, 0.53′ per px |
| HUD window | 10.8° × 5.4° = 1242 × 621 px = 113.9 × 56.9 mm, centred on the monitor |
| Look-down to window centre | 5° = 575 px, so the source horizon lands on row 1200 − 575 = 625 |
| Glass reflects | 315 of 352 mm: 3,435 px wide, centred; 203 px at each side never reflect |
| Line width | plan 6 px on 87 px/deg becomes 8 px here (× 115/87) |
| Gains (share of PGU white) | plan minimum over sky 0.35; design backlight over sky 0.45, over asphalt 0.18; Stage 1 0.084 |
| Ghost | 1.49 mm = 16 px, under 1% with the AR face toward the viewer |
| comma2k19 | f 910 px, 1164 × 874, 20 Hz; life-size crop 534 px wide, scale × 7.2; height 1.22 m assumed |
| comma three route | f 2648 px, 1928 × 1208, 20 Hz; crop 1,554 px, × 2.5; mount from liveCalibration |
| Bench camera (synth, MetaDrive, the monitor itself) | pinhole f 6543 px at 3840 × 2400, cx 1919.5, cy 1199.5, pitch 5.02° down puts the horizon on row 625 |
| Phone 4K clip | about 70° wide assumed; crop 1,609 px, × 2.4; intrinsics from a chessboard |
| Tolerances | coplanarity: crosses separate ≤ 5 px over a 100 mm eye shift; homography ≤ 2 px RMS, ≤ 4 px max; registration 0.10° = 11 px; 0.5° = 57 px |
| Vsync | 16.67 ms; a 20 Hz source shows each frame for 3 vsyncs |

## Conventions and traps

- **Car frame** (spec §6): x forward, y right, z down, origin at the source camera. `arhud_road`
  uses its own frames; convert at the boundary when porting, with a test that a point 20 m ahead on
  the ground at height 1.22 m projects to the row `tcalc` predicts.
- **The flip.** Appendix B's placeholder `homography_pr = [[-1,0,0],[0,1,0],[0,0,1]]` flips x and
  contradicts `flip: "vertical"` and §3.2. Use the vertical mirror as the identity-rig mapping from
  road-monitor pixel (u, v) to PGU pixel (u, H − 1 − v), that is `[[1,0,0],[0,-1,H-1],[0,0,1]]`
  with H = 2400, and let the test card settle it on hardware. `calib_rig.py` refines this matrix.
- **Window placement** (§6.1 reads two ways). The window is centred on the road monitor's centre,
  which is the glass centre. `roadsrc` offsets the life-size crop so the source's horizon row
  (cy − f · tan pitch) lands 575 px above the monitor's centre. Because the bench eye sits at the
  recording's camera, the plan's `view_from_eye` look-down is replaced by this crop offset and
  `view_from_eye` is the identity.
- **Bench projection chain** for a car-frame point p: PGU pixel = H_PR · F · S · K_source ·
  camera_from_car · p, where S is the scale and offset of the life-size crop onto the road monitor.
  Every matrix comes from config; the code path is the car's with different matrices.
- **Spec pixel counts are car numbers.** 1920 × 1080 output and the 946 × 473 crop belong to the
  car. Every bench count comes from `tcalc`.
- **Sync offset** uses `timing.lag_road_ms` and `lag_pgu_ms`, both null until measured. Default 0,
  say so in the log line.
- **Gain is applied in linear light:** a drawn value c is shown as c · gain^(1/2.2). Do it in the
  warp pass (shader uniform or a per-frame multiply), never by darkening the content texture's
  colours.
- **Age compensation on the bench:** the road monitor shows the frame of time t_c, not the road at
  t_photon. A correctly compensated mark leads the picture. `--target photon` (default in live
  mode) compensates to the predicted photon time; `--target picture` compensates to the frame's own
  capture time for registration checks against the picture.
- **HEVC decode** on the Mac through hardware: `cv2.VideoCapture(path, cv2.CAP_AVFOUNDATION)` first,
  PyAV with videotoolbox as the fallback. Measure decode time per frame against the source rate and
  print it.
- **Perception runs on source pixels,** never on the enlarged picture. Nothing here runs
  perception, but `roadFrame` must carry the native frame (shared-memory slot) so a later `laned`
  can.

## Package layout (in-scope modules only; the car inherits this layout)

```
hud/
  pyproject.toml          numpy, opencv-python, pyzmq, msgpack, pyyaml, raylib, av, pytest
  README.md               how to run every tool, the owner's rig checklist, the key table
  hud/common/
    clock.py              monotonic now(); vsync estimate from EndDrawing timing; drop detection
    display.py            window open / F toggle / HiDPI RenderTexture / --scale / --monitor / screenshot
    bus.py                ZeroMQ PUB/SUB, msgpack, envelope {t_capture, t_publish, seq}; empty messages still published
    schema.py             one dataclass per topic (roadFrame, display, truth, ego, lanes, objects, eyePose, hudFrame, hudStats)
    frames.py             shared-memory ring for the native frame on one host
    calib.py              calibration.yaml and bench.yaml loaders, with date and provenance per field
    geometry.py           camera models, car frame, plane intersection, homographies, the rig frame, the crop scale S
  hud/roadsrc/
    __main__.py           python -m hud.roadsrc --source <spec> [--fullscreen] [--scale 0.5] [--loop]
    sources/{video,comma2k19,oproute,recording}.py   one interface (below)
    display.py            full-screen player, crop, scheduling, frame-ID strip, timing patch, display topic
    republish.py          ego at 100 Hz by interpolation, truth per frame
  hud/hudd/
    __main__.py           python -m hud.hudd --mode {live,sync-truth} --gain 0.45 [--target off|picture|photon]
    draw.py               port of arhud_road/hudd.py + canvas.py: rules, ribbon, lines, chevron, hazards, speed block, clutter
    project.py            the chain above; K_eye = S · K_source; D from warp.py
    warp.py               mesh (64 × 32 quads) from a 3 × 3 homography or a lookup table; the flip
    compensate.py         age, ∫v, ∫ω, apply_delta, tracks by their own velocity
    stats.py              hudStats at 10 Hz, hudFrame downscaled as JPEG
  hud/scored/             display-chain residual: hudd's drawn points against truth, in degrees and px
  hud/tools/
    testcard.py           --monitor pgu: F, up arrow, grid, 1 px checkerboard, centre and corner crosses; --monitor road: grid and the same crosses
    synth.py              B6.3's topics at real rates
    calib_rig.py          chessboard on the road monitor, ArUco on the PGU, one photo -> H_PR
    calib_source.py       click two lane lines on straight frames -> vanishing point -> pitch, yaw
    recording.md          the bench recording format
  config/
    bench.yaml            source, mode, gain, d_img, data_root, remembered monitor per role, lag defaults
    calibration.yaml      appendix B, with the flip matrix corrected as above
docs/arhud-road/tools/export_bench.py     the MetaDrive exporter; runs in ~/.venvs/arhud-metadrive
```

### Source interface

Each source yields frames with: monotonic index; native image (numpy BGR); camera model (f, cx, cy,
size, distortion or None); mount (height_m, pitch_deg, yaw_deg, lateral_m); the nearest ego sample
(speed, yaw rate, their times) and the full ego stream; truth for the frame if any; the display
crop (source rectangle that fills the road monitor at life size, computed by `geometry.py` from f,
the horizon row and `d_img`). The source's own timeline starts at 0; `roadsrc` maps it to the clock.

### Bench recording format (`hud/tools/recording.md`; the exporter writes it, `sources/recording.py` reads it)

```
<rec>/meta.json    source, fps, frame size, camera {f, cx, cy, size}, mount {height_m, pitch_deg, yaw_deg, lateral_m}
<rec>/frames.mp4   or frames/%06d.png (lossless preferred for truth runs)
<rec>/ego.csv      t_s, speed_mps, yaw_rate_rps, pitch_deg (optional)
<rec>/truth.jsonl  one line per frame: {i, t, lines:[{kind, pts:[[x,y,z],...]}], objects:[{id, cls, pos, vel, box}], plane:{height_m, pitch_deg}}
```

Car frame as above, origin at the exporter's camera. The exporter may render at 1920 × 1200 with the
same 32.7° × 20.8° field if 3840 × 2400 offscreen is too slow in Panda3D on macOS; record the render
size in `camera.size` and let the crop scale handle it.

### Topics on the bus

`roadFrame` (index, t_capture, slot, camera id, source name, patch flag), `display` (index, scheduled
vsync, lag used, crop in source px), `truth`, `ego` (100 Hz), `hudFrame`, `hudStats`. `lanes`,
`objects`, `eyePose` have schemas and subscribers in hudd but no publisher yet except `synth.py`.
ZeroMQ over `ipc:///tmp/arhud/<topic>`; msgpack maps; every message carries the envelope.

## Milestones

Each milestone lists checks you run (no rig needed, the Mac's own display stands in) and checks only
the owner can run on the rig. Do the owner checks' preparation (the exact command and what to look
for) and put them in `hud/README.md`.

### M0. Environment and skeleton

- `uv venv --python 3.12 ~/.venvs/arhud-hud`; install the package editable. Do not touch
  `~/.venvs/arhud-metadrive` (Python 3.11, pinned MetaDrive commit) except to run the exporter in it.
- `hud/` with the layout above, `config/*.yaml` filled from `tcalc`, `.gitignore` for `models/`,
  `runs/`, `shots/`. Data lives under `~/data/arhud/` (configurable `data_root`), not in the repo.
- You run: `pytest` passes on `geometry.py` (the 20 m ground point lands on the predicted row; the
  flip matrix maps (u, v) to (u, 2399 − v); crop scale for each source equals the table's).

### M1. Display layer and test cards (T-A software)

- `display.py` as specified above. `testcard.py --monitor pgu` draws the letter F, an up arrow, a
  grid, a 1 px checkerboard patch and crosses at the window's centre and four corners, all through
  the flip so the reflection reads correctly. `--monitor road` draws the grid and the same crosses
  unflipped. `--no-flip` for the raw card.
- You run: `--scale 0.5` windows on the internal display; `--shot` writes the RenderTexture at
  3840 × 2400 to `hud/shots/`; a script asserts the F is mirrored vertically between the two shots and
  the cross pixels coincide after the flip.
- Owner runs: card reads correctly in the glass; coplanarity by two phone photos 100 mm apart,
  crosses within 5 px; 1 px checkerboard photographed as a clean checkerboard (proves pixel
  exactness). Record the glass orientation and flip in `calibration.yaml`.

### M2. Bus, clock, schemas, synthetic topics

- `bus.py`, `schema.py`, `clock.py`, `calib.py`. `synth.py` publishes B6.3's scene at real rates:
  straight lane 3.7 m wide then a 300 m curve, lead 30 m ahead braking at 5 m/s², pedestrian crossing
  at 20 m, 25 m/s with the matching yaw rate, lane points as the bench camera would see them, truth
  as well. `--delay 200` adds a fixed publication delay for the sign test.
- You run: a subscriber script prints every topic's rate for 10 s within 5% of nominal; empty
  messages arrive on silence.

### M3. hudd from synthetic topics (T-B)

- Port `arhud_road/hudd.py` and `canvas.py` into `draw.py`, stripping MetaDrive and `features.py`;
  keep the rules of B6.4 and spec §6: stale cut-offs, line hysteresis, three frames before
  appearance, ribbon (one-sided 3.7 m fallback, lighter), lead chevron within 80 m with gap, hazards
  after three detections, fixed speed block, draw region, clutter mode on `C`, blank-ribbon switch on
  `B`. Content into an off-screen canvas at twice the window (2484 × 1242); fall back to 1× if the
  cv2 pass exceeds 6 ms, and say so.
- `project.py` with the bench chain; `warp.py` builds the mesh once from `homography_pr` and the
  flip, rebuilds only on reload (`R`). Gain on `G` cycles 0.35, 0.45, 0.18, 1.0. Only the 1242 × 621
  window region is lit; the rest of the PGU is black.
- `stats.py`: hudStats at 10 Hz (age per topic as drawn, render ms, dropped frames, last residual);
  hudFrame downscaled. A `--preview` flag shows the content texture in the window's corner in
  windowed mode only.
- There is no synth mode in hudd: `--mode live` draws from whatever publishes, and `synth.py` is the
  publisher. You run: `synth.py` plus `hudd --mode live --scale 0.5` for 10 minutes: one frame per
  vsync of the display it is on (the M4's internal panel may run 120 Hz; hudStats reports the
  measured vsync interval and counts drops against it; 60 is the YODOIT's figure), zero drops; a shot
  shows ribbon, lines, chevron and speed block within the window and nothing outside it; `--no-flip`
  versus default differ by exactly a vertical mirror.
- Owner runs: hudd fullscreen on the PGU; the window sits inside the glass's reflected area and
  reads upright; `G` visibly steps brightness.

### M4. roadsrc and the sources (T-C)

- In this order: `sources/video.py` (any mp4 or mov: phone clip; intrinsics from config or a default
  70°), `recording.py` (the format above), `comma2k19.py` (video.hevc via hardware decode;
  `processed_log/CAN/speed` and `IMU/gyro` are plain numpy arrays, no openpilot import; height
  1.22 m; pitch from `calib_source.py` or config), and last `oproute.py` (the demo route
  `5beb9b58bd12b691/0000010a--a51155e496` through `openpilot/tools/lib/route.py` and LogReader for
  `liveCalibration` and `carState`). oproute needs openpilot's log reader and cereal bindings, which
  may not import on this Mac; if they do not within an hour, defer the source with a note in the
  report rather than building cereal.
- `display.py`: life-size crop with the horizon on row 625, scheduled presentation of each frame to
  the nearest vsync at the source's rate (3 vsyncs per frame at 20 Hz), frame-ID strip (eight squares
  encoding index mod 256 at a corner), timing patch (60 × 60 px white for one frame on `P` or at
  random 0.5 to 1.5 s intervals with `--patch auto`, flag on `roadFrame`), `display` topic per
  frame, every schedule miss logged. `republish.py` puts ego on the bus at 100 Hz by interpolation
  on the bench timeline and truth per frame.
- Capture time of a frame = its scheduled vsync + `lag_road_ms` (default 0). Hold `roadFrame`
  publication until that time has passed.
- You run: each source plays 60 s at its rate with zero schedule misses at `--scale 0.5` on the
  internal display, decode time printed; a shot of the frame-ID strip decodes to the logged index
  with a small decoder script; ego speed at a known frame equals the log's.
- Owner runs: a source fullscreen on the road monitor; the horizon sits on the glass centre line
  minus 5°; a phone photo decodes the strip.

### M5. Calibration tools (T-E, 8.3 and 8.4)

- `calib_rig.py`: shows a 12 × 7 chessboard filling the window region on the road monitor and ArUco
  markers on the PGU at the pixels the identity rig would reflect onto the corners. Takes one photo
  from the eye point (file path), detects both, fits the homography from road-monitor px to PGU px,
  prints RMS and max residual in road-monitor px, writes `warp.homography_pr`, `warp.flip`,
  `warp.residual_px` with the date. `--verify` makes hudd show the chessboard through the new warp
  so a second photo should show one chessboard.
- `calib_source.py`: on a chosen set of straight frames the user clicks two points on each ego lane
  line; the tool fits the vanishing point (median over frames), pitch = atan((v − cy)/f), yaw from
  u, writes `sources.<name>.mount`. Cross-check printed against `liveCalibration` for routes.
- You run: a synthetic photo (render the chessboard, apply a known homography and a vertical flip,
  save) recovers the matrix within 0.5 px RMS. A synthetic straight-road frame recovers a 5.02°
  pitch within 0.05°.
- Owner runs: the real photo; residual ≤ 2 px RMS, ≤ 4 px max; second photo shows no doubling.

### M6. MetaDrive exporter and truth-fed sync mode (T-E)

- `docs/arhud-road/tools/export_bench.py` in the MetaDrive venv: drives the simulator's seeded
  24 s bench route (map `SCrSXSOSCTSRS`, seed 3, as `run.py --bench`), renders the road camera at the
  bench field (f 6543 px at 3840 × 2400, or 1920 × 1200 at the same field), writes the recording
  format with ego at 100 Hz and truth per frame from `truth.py` (painted boundaries as car-frame
  polylines, vehicles and pedestrians with velocity, the true plane). Run with `--fast`; it need not
  be real time.
- hudd `--mode sync-truth`: subscribes to `truth` and `display`; for the frame due at its next
  present it draws truth N at the vsync roadsrc shows frame N, offset by `lag_pgu − lag_road`
  (default 0). Age is zero by construction; compensation off.
- `scored`: from hudd's own projected points (published in hudStats or a side topic) against truth
  projected through the same chain with the identity warp, the residual of the ego lines at 10, 20,
  30 m and of the chevron, median and 95th percentile in degrees and px over the drive. Writes a
  small table to `runs/`.
- You run: exporter produces a recording that `sources/recording.py` plays; sync-truth at
  `--scale 0.5` on one display with both windows; `scored` reports a residual that is zero to the
  pixel with the identity homography (a non-zero number here is a bug in the chain, not the rig).
- Owner runs: sync-truth on the rig with the calibrated homography; drawn line within 0.10° (11 px)
  of the painted line at 10, 20, 30 m, median over the drive.

### M7. Live mode and the sign test (display half of T-F)

- hudd `--mode live`: draws from the newest `lanes`/`objects`/`truth` at 60 Hz with compensation
  to `--target photon` (now + render ms + `lag_pgu`) using the recording's ego stream; `--target
  picture` for registration against the picture. With no perception yet, live mode runs on
  `synth.py` and on the exporter's truth published at frame rate with `--delay`.
- Sign test: `synth.py --delay 200` or a comma2k19 curve with truth-free visual judgement; with
  compensation off the marks lag the paint, on they lead it onto the paint's future position.
  `--target off|picture|photon` (key `K` cycles the same three) is the one compensation control;
  log s and ψ per frame.
- Audience view: `python -m hud.tools.audience` on the Mac's own screen shows the road frame with
  hudd's lines mapped back through the inverse chain, the hudFrame, and the live hudStats numbers,
  laid out like the road simulator's right panel. Windowed only.
- You run: with `--delay 200` on the synthetic curve the compensated residual (scored against truth
  at photon time) is below the uncompensated one; the opposite sign makes it worse. Print all three.
- Owner runs: a comma2k19 curve on the rig, judge by eye that the compensated lines move toward
  the paint in a left and a right curve.

## Keys (put this table in README.md and in `?`)

| Key | Where | Does |
|---|---|---|
| F | all | borderless fullscreen on the current monitor / back to a window |
| Esc | all | quit, print the summary |
| S | all | screenshot of the RenderTexture to `hud/shots/` |
| Space, ←, → | roadsrc | pause, step a frame |
| P | roadsrc | fire the timing patch once |
| B, C, G, R | hudd | blank ribbon, clutter 10 s, gain cycle, reload calibration and rebuild the mesh |
| T | hudd | chessboard through the warp (calibration verify) |
| K | hudd | compensation target off / picture / photon |

## Constraints

- New venv `~/.venvs/arhud-hud` (Python 3.12). Never modify `~/.venvs/arhud-metadrive`, the
  simulator's pinned environment, except to run the exporter inside it.
- No edits to openpilot code in this checkout; read `openpilot/tools/lib` and `openpilot/common/transformations` only.
- Nothing in `hud/` imports openpilot at runtime unless guarded (the route and frame readers are
  optional fallbacks).
- Models, data, runs and shots are gitignored. Do not commit; leave the working tree for review.
- Keep the design's names for processes, topics and files. Where you deviate (the windowing above,
  the corrected flip matrix, the recording format), note it at the top of `hud/README.md` so the
  design PDF can be updated later.
- Measure, do not assume: decode time, cv2 draw time, texture upload time, frames per second. Print
  them on exit.

## Reporting

Finish with a report that lists, per milestone: done or not; which "you run" checks passed, with
the command and the shot path; which were skipped and why; anything that failed with its output.
Then the owner's rig checklist in order. State plainly what has not been verified on real hardware.
