# Windshield AR HUD simulator (TFT LCD edition)

An interactive 3-D simulation of the HUD in `docs/ARHUD-PLAN-TFT-SPEC.md`: every component, how each is built, how it is installed in the car, each part working, and the view from the driver's seat with the HUD running.

## Run it

ES modules do not load from `file://`, so serve the folder:

```
cd docs/arhud-sim
python3 -m http.server 8000
```

Then open <http://localhost:8000>. three.js 0.170.0 loads from jsDelivr, so the first load needs a network connection.

Deep links: `#drive`, `#vehicle`, `#build`, `#parts`, `#part-<id>` (for example `#part-backlight`).

## The screen

The 3-D stage is the subject; the chrome stays out of its way.

- **Labels.** Every named part carries a small dot. Point at the part (or its dot) and its name appears; click it for its numbers. The selected part stays labelled. Captions on the Vehicle overlays (virtual image, eye box, road coverage, sun patch, camera fields) appear for a few seconds when the overlay is switched on and whenever its toggle is hovered. The **Labels** control in the top bar switches between *Hover* (the default), *All* (every label at once, as before) and *Off* (no labels, and no explanatory captions on the component animations either). The choice is remembered.
- **Panels.** Each panel folds to its title with the chevron in its header. Inside the panels, the everyday controls sit in the open and the experiment groups (picture generator, optics, latency, head tracking, faults; overlays, body, mirror) are folding sections. **Hide panels** in the top bar, or the `H` key, clears the stage entirely.
- **Mini views.** In the Driver view the PGU frame and the audience view share one dock under the live numbers; tabs switch between them and the chevron folds the dock.
- **Full screen.** The **Full screen** button in the top bar, or the `F` key, puts the simulator on the whole display. Where the browser or the host page refuses that (an iframe without permission), the same button hides the top bar and lets the stage fill the page instead. Escape or `F` leaves either.
- Dev flags on the hash: `&labels=all|off`, `&nopanels`, `&hover=<part id>` (shows that part's label as if hovered, for screenshots), `&strip=full|nodriver|noseats|front` (Vehicle), `&ribbon=fill|blank` (Driver view), `&blur=1`, `&focus=image|road|infinity` and `&pupil=MM` (Driver view's focus blur, with `&mirror=` and `&glass=RH,RV`), plus `&warm=`, `&env=`, `&fov=` and `&debug` as before.

## Modes

- **Driver view.** You sit at the eye point and drive a 5 km loop. The hudd renderer draws the PGU frame (946 × 473 px) with the plan's drawing rules, and the frame is shown as light on a plane 7.5 m ahead. Registration, parallax, latency, the ghost, eye-box vignetting and contrast all come out of the geometry. Controls cover speed, scene (noon, overcast, dusk, night), time of day and a sun-in-patch scenario, the picture generator (stock 450 to HUD-grade 50,000 cd/m²), dimming, the spec window or the traced one, the ghost (true size or exaggerated), age compensation (photon time, draw time, none), each latency stage, head tracking, a ±75 mm head sway, clutter mode and a GNSS outage. **Lane on the HUD** (or the L key) switches between the plan's filled lane, whose edges show any misalignment against the paint, and a blank lane with only the lines and symbols drawn; the lane is still computed, so the lead chevron works either way, and the choice is remembered. Live numbers sit beside their acceptance criteria. The PGU frame and the audience view are shown as insets. **Mirror, windshield and focus blur** combines a concave mirror (the generic 660 mm sphere the plan wrote, the toroid or the freeform fitted to flat glass, or the freeform fitted to 4 m × 8 m glass) with a windshield (flat, or 8 × 20, 4 × 8 or 3 × 6 m radii, lateral × vertical, ASSUMED) and draws what the driver's eye sees: every grid point of the window is traced from eyes 10 mm apart (`fieldVergences` in geom.js), the parallax gives the sagittal and tangential vergences, and a pupil (from the scene, 3 to 6 mm, or chosen) focused on the HUD, the road or infinity blurs the frame by a uniform ellipse pupil × the dioptre error wide in each direction. The readouts give the two image distances at the centre, the worst astigmatism and the blur. On flat glass the toroid stays within 0.04 D and about 1′; the sphere has 0.28 D (5.2 m sagittal, 57 m tangential at the centre); on 4 × 8 m glass the toroid has 1.6 D with the whole window past infinity, and only the mirror fitted to that glass is sharp.
- **Vehicle.** The parked car with everything installed, with the driver's side, the passenger's side or both opened up (or an X-ray body). **Strip the car** takes out the driver, then the seats, then everything behind the front section: the car is cut 0.2 m behind the rearmost installed part, so mini PC 2 keeps its floor, and the passenger headrest stays as monitor 2's mount. **Through the cut** looks into the open cabin from behind, where the HUD unit, both cameras, the wiring and the audience monitor show at once. The choice is remembered. Overlays: the traced light path (eye, glass, mirror, fold, panel), the virtual image at 7.5 m with the HUD frame on it, the eye box, the road the window covers, camera fields of view, the sun-entry patch, and signal flow on every cable. Point at any part for its name; click it for its numbers.
- **Build.** 76 steps from the parts on the bench to the first drive: the backlight and PGU from the ground up, the Stage 0 rig, the printed housing from the CAD model (18 steps), the optical train going into it, the HUD controller, Stage 1, installation in the car with every cable routed, then the software bring-up and calibration.
- **Components.** Every part on its own: explode it, run its working animation, step through its assembly, and read its numbers. Point at a piece for its name; the dots appear once the part is exploded.

The HUD frame's texture coordinates on the image surface come from the nominal eye's ray through each fragment (`hudImageMaterial` in install.js), not from the grid. The surface's vertices run from 5 m to past infinity across the toroid's window, and interpolating grid coordinates across such cells stretched the frame toward the near corner: the smeared speed block in the lower left. Past-infinity points are drawn at 300 m (`GM.surfaceDistance`) instead of falling back to the plane.

## Where the numbers come from

`js/params.js` is generated from the plan's single source of truth:

```
cd docs/arhud-plan-tft-src
python3 sim_params.py
```

Values the plan tags ASSUMED or UNVERIFIED are tagged the same way in the simulation. `js/geom.js` computes the installed layout from those numbers and ray-traces it. Its choices beyond the plan are listed at the top of that file and in the Vehicle mode's optics panel.

## What the simulation found

- **Mirror clearance.** At the plan's assumed 1,000 mm eye-to-mirror path, the top of a 200 mm-tall mirror meets a 28° windshield. The layout uses 1,060 mm, which leaves about 25 mm.
- **Astigmatism.** With the panel 14 mm inside focus, a spherical mirror used 15.5° off-axis (the incidence this layout needs to keep the fold clear of the exit beam) splits the image to 52.7 m (tangential) and 4.1 m (sagittal). A toroid with Rt ≈ 685 mm and Rs ≈ 636 mm brings both to 7.5 m. The ray trace with the real windshield sets the final figure.
- **Image distance and field.** `calc.py` uses 7.5 m as the mirror-to-image distance in the mirror equation, but as the eye-to-image distance for the field of view. With the eye about 1.06 m from the mirror, the specified hardware puts the image about 8.6 m from the eye. After keystone correction the window is about 8.7° × 4.6°. Either shorten u to about 314 mm and enlarge the crop to about 69 × 35 mm, or accept the smaller window.
- **Road coverage.** A 5° look-down with a 5.4° tall window covers flat road only from about 9 to 31 m. A lead car farther away sits above the window.
- **Head-motion parallax.** The plan gives parallax as atan(0.15 m ÷ d), so it is largest for near objects (1.15° at 7.5 m, 0.29° at 30 m). The misregistration that matters is between the object and the virtual image, which is 0.15 m × |1/7.5 − 1/d|. That is zero at 7.5 m, 0.29° at 10 m and 0.86° at 30 m, and approaches 1.15° far away. The tracker matters most for far content such as the lead chevron. The Driver view shows this: turn the tracker off and sway the head.
- **Window width against the lane.** The 10.8° window is narrower than a 3.7 m lane at any distance under about 19.5 m. Across the window's lower half the ribbon fills the full width, and the lane edges appear only near its top. The plan's mockup uses an illustrative view about 25° wide.
- **Night brightness.** At the plan's 50 cd/m² night ceiling, white is about 30 times a headlit road (1.5–2 cd/m²), and the ribbon fill alone is about 17 cd/m². The window reads as a bright slab. TI's figure for night is under 3 cd/m², so the dimming curve needs a much lower floor than one driver step.
- **Mirror width.** The eye box plus the field needs about 330 mm of mirror width at this path length (320 mm at the plan's 1 m). The 300 mm mirror vignettes the outer field at the eye-box edges.
- **Panel edge in the beam.** Found by the CAD housing's ray check. With the fold mirror 50 mm over the panel (this layout's `FOLD_TO_PANEL`), the mirror-to-fold rays for the top edge of the window, seen from the top of the eye box, pass through the front edge of the panel's own cell glass: 21 of 345 rays per mirror figure. A fold 65–70 mm over the panel clears it; that moves the panel about 14–19 mm forward and 20–27 mm down. The HUD unit draws these rays red.
- **Cluster hood.** In this car the instrument-cluster hood occupies the space where the housing's rear and the HDMI board were drawn. The CAD housing steps up over it, and the board stands on edge inside the PGU bay.

## The CAD housing

`docs/arhud-cad` models the printed housing in build123d from this simulator's layout (`geom.js`, `optics.js`). It has 32 printed parts (39 pieces) in matte-black ASA, each fitting a 250 mm printer, plus every insert, screw, spring, foot, grommet and the glass. The model is checked against the traced light path, the windshield, this car and the printer. `make.py` writes STEP, STL, DXF and a bill of materials, and also `assets/cad/housing.glb.txt` (base64 GLB, one node per part, in this frame) and `assets/cad/housing.json`. `js/components/cad.js` loads them:

- **Components → 3-D printed housing** shows every CAD part with its name, the 18-step build from the ground up, explode, a see-through shell with the traced rays, and **On the print beds** (each printed part on a 250 mm plate, in the orientation of its STL).
- **Build → Optical housing** starts with those 18 steps.
- The installed **HUD unit** (Vehicle, Driver view, Build) uses the CAD shell and mounts in place of the procedural ones. Its dust cover and shutter take the CAD opening, 262 × 263 mm, which is sized from the rays that land on the 300 mm mirror.

Without `assets/cad`, or under Node, `cad.js` leaves the procedural housing in place. See `docs/arhud-cad/README.md` for the design and the checks.

## Tools for extending the simulator

Installed outside the repo on 2026-10-21, for bringing scanned and CAD geometry into the simulation and for driving the HUD software against a simulated road:

- **Blender 5.2.3 LTS (release candidate)** (`/Applications/Blender.app`): cleans up scans and exports glTF. Scripts run headless with `/Applications/Blender.app/Contents/MacOS/Blender -b --python script.py`.
- **build123d 0.13.0** in `~/.venvs/arhud-cad` (Python 3.12): parametric CAD that imports `calc.py` directly and exports STEP, STL and glTF.
- **MetaDrive** in `~/.venvs/arhud-metadrive` (Python 3.11), installed from GitHub commit `fe54b03`. The PyPI release (0.4.3, December 2024) cannot render on Apple-silicon Macs: it asks for more antialiasing samples than macOS OpenGL offers, so no window opens, and its road shaders need a newer OpenGL context than it requests. The GitHub version fixes both.

To recreate them:

```
uv venv --python 3.12 ~/.venvs/arhud-cad
uv pip install --python ~/.venvs/arhud-cad/bin/python build123d==0.13.0
uv venv --python 3.11 ~/.venvs/arhud-metadrive
uv pip install --python ~/.venvs/arhud-metadrive/bin/python "metadrive-simulator @ git+https://github.com/metadriverse/metadrive.git@fe54b03327b14bcfc17a9a04b60c8abbee4d7ab1"
```

MetaDrive on macOS:

- Its cameras render through an on-screen window, never offscreen, so camera scripts must run in a logged-in desktop session, not over SSH.
- An RGB and a depth camera at 640 × 360 together run at about 31 fps.
- Each run starts with `objc` warnings that SDL is "implemented in both" pygame and OpenCV. Both packages bundle their own copy of SDL. The warnings have been harmless in testing so far.
- The first run downloaded about 170 MB of assets into the environment.

## Blender: the Cycles reference and the baked sky

`docs/arhud-blender/` holds the Blender 5.2 pipeline (its README has the commands and the findings). It feeds the simulator two things through `assets/`:

- **Cycles reference** (`assets/cycles/`, from `optics_check.py` and `sun_focus.py`). Blender's path tracer renders the same optics the simulator traces, built from `layout.json`, which `dump_layout.mjs` writes from `js/geom.js`: the laminate as 4.96 mm of glass, the mirror as a true sphere or toroid, the fold, the housing walls with the lid aperture, and the crop emitting a dot grid. The Vehicle mode's optics panel shows the comparison under **Cycles reference**: image distance by stereo parallax (sagittal and tangential, dot by dot) against the trace, the window's size and keystone, every dot's position against the trace (`js/cycles.js` solves the trace for each dot), the ghost's offset, the eye box from nine eye points, and a numeric sun-focus trace with its irradiance footprint and entry patch. The Driver view's dock has a **Cycles** tab with the render from the eye.
- **The baked car** (`assets/car.glb`, from `dev/export-car.html` and `car_bake.py`). The procedural car goes through Blender: duplicated vertices merged, plain boxes bevelled, long edges tessellated, smooth shading by angle, and ambient occlusion from the whole car baked into vertex colours. `js/car-glb.js` lays each baked part over its procedural twin, keeping the parent, transform, shadows and material, and only while the part still matches `car.js` (vertex count and bounding box), so the geometry, mount points, cutaways and x-ray are untouched. `&noglb` on the hash keeps the procedural car.
- **The body shell modelled in Blender** (`assets/car_body.glb`, from `car_body.py`): a subdivision-surface sedan shell lofted to the car's own dimensions, with arches, pillars and baked occlusion, laid over the procedural exterior parts as two halves so the side cutaways and the x-ray still work. The procedural windshield stays, since it is the optical surface. `&noglb` keeps the procedural car.
- **The driver's view, path-traced** (`assets/cycles/driver_view.png`, from `beauty_render.py`): the frame hudd drew, through the real optics into the car under the sky model. It is the Driver view's **Cycles** dock tab and heads the Cycles reference section, with a night twin (headlights, moonless sky).
- **Scanned car** (`assets/scan.*`, from `import_scan.py`): a scan of the real dash and glass aligned to the simulator's frame, shown in Vehicle mode under **Scanned car** (`js/scan.js`). Until a real scan exists, the stand-in is a simulated handheld scan of the modelled cabin (`scan_sim.py`: six poses, range noise, dropouts, occlusion holes, no glass returns), aligned by the same tool from four measured points to within 5 to 6 mm on landmarks it did not use.
- **Freeform mirror with a tilted panel** (`js/freeform.js`, from `freeform_mirror.py`): a third mirror figure in the Vehicle and Components panels. A polynomial surface fitted together with a 38.7° panel tilt puts the virtual image at 7.5 m over the whole window with straight edges (the toroid's runs from 6 to 19 m); the window is 9.1° × 3.6° with the 60 × 30 mm crop, so the plan would want a 60 × 38 mm crop. The trace follows the tilted panel and the installed PGU tilts with it. A fourth figure, **Freeform for a curved windshield**, switches the trace's own glass model to a 4 m × 8 m windshield (`js/freeform_curved.js`) and uses the design refitted for it, so the Driver view runs on curved glass; the car's glass is still drawn flat. The Driver view now defaults to the **traced** window (8.7° × 4.6° at 8.6 m, what the hardware gives and Cycles confirmed) rather than the plan's spec window (10.8° × 5.4°), which stays as a chip. Two development flags support the end-to-end check of that drawing: `#drive&bare=1` (no top bar, no panels, the stage fills the window) and `#drive&pattern=white` (the HUD canvas painted white, so the window is a plain lit rectangle); a headless capture at the Cycles field of view measured the drawn window at 8.75° × 4.58°, within a pixel of the trace. With the traced window the Driver view draws the virtual image on the **image surface** the optics make rather than on a plane: each grid point of the window sits at the traced sagittal image distance along the nominal eye's ray (local Coddington at the mirror hit, which Cycles confirmed at 6 to 19 m across the toroid's window; the drawn surface runs 5.1 m at the top to 24.9 m at the bottom). From the nominal eye nothing changes; when the head moves, the parts of the image swim against the road by their own distances, as they do in the car: a 65 mm lateral move shifts the top of the image 43′, the centre 26′ and the bottom 10′, where the flat plane moved everything 26′. The Driver view's Window readout shows the surface's range. The black-level glow of the lit panel, which is what shows as the slab at night, is drawn over the crop's true image, the keystoned trapezoid the optics make (8.97° wide at the top, 10.04° at the bottom, mapped through the trace), while the content stays on the inscribed rectangle hudd draws into. The spec and Stage 1 windows stay planes. Registration is scored by the trace (`traceDir` in hud.js): the drawn pixel's panel point, and the direction from the true eye whose ray lands there, which is the pinhole-eye physics Cycles reproduces. The Optics panel's chips **hudd places a symbol for the tracked eye by** offer the plan's plane at one distance, the image-surface map, the optical model from the eye to the panel (exact, ray tracing per symbol), and the same as a lookup table, which is the Jetson's way (`projection` in hud.js; `js/lut.js` builds the table of eye positions by field directions from the trace in about 0.2 s and interpolates, within 1′ of the exact projection, at full frame rate; `node dev/export-lut.mjs <figure>` writes it as `assets/hudd_lut_<figure>.json`, the calibration file hudd would load). The window's vignette (the Window visible readout and the fade of the virtual image) now tests each ray against the housing's own top on the way to the glass, the lid aperture, the fold glass and the lit crop as well as the mirror (`js/clip.js`, shared with the Cycles comparison), and matches the Cycles eye-box survey in every direction. The housing's rear height is what limits the eye box downward: the nominal eye's line to the bottom of the window clears it by 43 mm, the plan's lowest eye by 11 mm. The Live numbers score registration only for symbols actually inside the window, and add **window marks**, four fixed road points scored whenever they are in view, so the sway test has a number that does not depend on the traffic: plane 17′ worst, surface map 15′, optical model and lookup table 6′ (the tracker's lag), head still 1.4′. In the ±75 mm sway test the plane leaves the lead marker about 0.3° off, the surface map helps one side only, and the optical model registers within the tracker's noise. Cycles confirmed this end to end (the Cycles section's *Registration through the optics*): hudd's own frame for a displaced eye, pre-distorted to the panel, rendered through the real optics over discs on the road, registers within 2′ at 75 mm with the optical model, against up to 18′ for the plane; the same holds for a 35 mm vertical offset and for the freeform figure, where the plane projection is worse still (31′) because the tilted panel's image swims with the eye, and on the curved windshield with the mirror refitted for it, where the plane projection misses by 1.5° at 75 mm and the optical model holds 4′ ( puts a curved windshield into the trace for any figure). The trace itself now uses the true sphere and toroid rather than their paraboloids, which brought its nominal-eye agreement with Cycles from 2.6′ rms to 0.6′. The same surface gives the **vergence conflict** row: the eyes converge on a symbol at its image distance and on the object at its own, and the difference is the disparity the driver must fuse (Panum's area, 10 to 20′, assumed). The lead marker on the toroid runs about 50′ (the lane at 20 m about 24′), so it doubles whenever the driver looks at the car; the flat freeform image brings the lead to about 19′ and the lane to 14′. A far-registered symbol needs a far image. The Cycles section's **Luminance at the eye** rows come from a uniform-white-panel survey: the fraction of the panel's luminance that reaches the eye for each figure and for Lambertian, IPS-like and TN-like cells, so the tilted panel's cost is a number, and the windshield path is checked against Fresnel and the plan's s-polarised figure. The Cycles reference shows the measured distances for it, and what a curved windshield (4 m lateral, 8 m vertical radii) does to the toroid's image: a real image in front of the eye, a wider window, a doubled ghost, so the mirror must be designed against the measured glass.
- **Sun-watch patch.** With `assets/cycles/sun_focus.json` present, hudd's sun-watch rule uses the set of sun directions the Blender trace found lighting the whole cell instead of the plan's patch; the shutter reason names the source.
- **Sky maps** (`assets/sky/`, from `bake_sky.py`). Blender's physically based sky rendered to small equirectangular maps at nine sun elevations, plus a CIE overcast sky and a night floor. `js/assets.js` loads the map nearest the sun's elevation as `scene.environment`, rotated to the sun's azimuth, so paint, glass and metal reflect a sky with the right colour and the cabin's indirect light follows the time of day. The procedural sky stays the visible background. Add `&noibl` to the hash to see the analytic lights alone. Without `assets/` the simulator runs as before.

What the Cycles reference found, beyond the list above: the image surface is far from a flat plane at one distance (6 m at the top of the window to 19 m at the bottom, the wrong way round for a road), the sun's spot on the panel is comatic with twice the plan's 90% radius, and sunlight reaches the cell from a wider range of directions than the plan's sun-watch patch covers.

## Files

- `index.html`: page shell and styles.
- `js/main.js`, `js/app.js`: boot, renderer, post-processing, studio scene, hover labels, picking.
- `js/ui.js`: panels, folding sections, the mini-view dock and the small controls.
- `js/geom.js`: layout and ray trace (sphere, toroid, and the freeform from `js/freeform.js`).
- `js/hud.js`: perception, hudd, controllerd and sun-watch, in miniature.
- `js/install.js`: mount points, cable runs, the virtual image, the sky maps.
- `js/assets.js`, `js/cycles.js`, `js/car-glb.js`, `js/scan.js`: the Blender-baked sky maps, the Cycles reference panel, the baked car overlay and the scanned car (see above).
- `js/world.js`, `js/car.js`: road loop, traffic and sky; the ego car and its interior.
- `js/components/*.js`: every component, following `contract.js`; `cad.js` loads the CAD housing from `assets/cad/`.
- `js/modes/*.js`: the four modes.
- `dev/*.html`: development pages for the component sets; `dev/ibl-test.html` checks the sky-map rotation; `dev/export-car.html` writes the procedural car as a GLB for the Blender pass.
- `assets/`: written by `docs/arhud-blender/`; `assets/cycles/` (renders, `results.json`, `sun_focus.json`) and `assets/sky/` (EXR maps, their base64 `.exr.txt` copies for the artifact host, which serves no `.exr`, and `manifest.json`), and `assets/car.glb` with its base64 `car.glb.txt` (the artifact host serves no `.glb`).
- `assets/cad/`: written by `docs/arhud-cad/make.py`: `housing.glb` with its base64 `housing.glb.txt`, and `housing.json`.
