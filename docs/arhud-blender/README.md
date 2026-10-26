# Blender pipeline for the AR HUD simulator

Blender 5.2 (headless) adds two things the Three.js simulator in `../arhud-sim` cannot do on its own: an
independent, physically based picture of the optics, and image-based lighting from a real sky model. Everything
here builds from the simulator's own layout, so the two never disagree about where a surface is.

```
node dump_layout.mjs                                   # geom.js -> layout.json (npm install here once)
/Applications/Blender.app/Contents/MacOS/Blender -b -P optics_check.py   # Cycles cross-check -> ../arhud-sim/assets/cycles/
python3 sun_focus.py                                   # sun-focus ray bundle -> ../arhud-sim/assets/cycles/
python3 freeform_mirror.py                             # freeform mirror fit -> freeform.json, ../arhud-sim/js/freeform.js
python3 freeform_mirror.py glassRh=4 glassRv=8 name=freeform_curved   # the same against a curved windshield
/Applications/Blender.app/Contents/MacOS/Blender -b -P mirror_export.py -- name=freeform   # sag table + STL -> export/
/Applications/Blender.app/Contents/MacOS/Blender -b -P optics_check.py -- lum=1 res=700 samples=32   # luminance survey -> results.json 'luminance'
/Applications/Blender.app/Contents/MacOS/Blender -b -P bake_sky.py       # sky maps -> ../arhud-sim/assets/sky/
# the car pass: export the procedural car from a browser, then let Blender smooth it and bake its ambient occlusion
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --use-angle=swiftshader --enable-unsafe-swiftshader \
  --virtual-time-budget=60000 --dump-dom "http://127.0.0.1:8000/dev/export-car.html" > /tmp/car.html   # with `python3 -m http.server 8000` in ../arhud-sim
python3 -c "import re,base64;s=open('/tmp/car.html').read();open('/tmp/car_src.glb','wb').write(base64.b64decode(re.search(r'<pre id=\"out\">([^<]*)',s).group(1)))"
/Applications/Blender.app/Contents/MacOS/Blender -b -P car_bake.py -- in=/tmp/car_src.glb        # -> ../arhud-sim/assets/car.glb
/Applications/Blender.app/Contents/MacOS/Blender -b -P car_body.py -- car=/tmp/car_src.glb        # -> ../arhud-sim/assets/car_body.glb
```

Rerun the first line after any change to `geom.js` or `params.js`, then the others. `arhud-sim/node_modules` is a
symlink to this folder's `node_modules`, so Node can resolve `three` when it imports the simulator's modules.

## Files

- `dump_layout.mjs`: imports `../arhud-sim/js/geom.js` (and the fold frame and housing layout from
  `components/optics.js`) under Node and writes `layout.json`: eye, glass, mirror (both radius sets), fold, panel,
  housing, mounts, the traced corner rays and the plan's raw parameters. The Blender scripts read nothing else.
- `bl_common.py`: frame conversion (simulator X forward, Y up, Z right -> Blender X forward, Y left, Z up, which the
  glTF exporter maps back to the simulator's frame), Cycles setup on Metal, materials, meshes, cameras, EXR and PNG I/O.
- `optics_check.py`: the Cycles cross-check. The laminate is a 4.96 mm slab of n = 1.52 glass, the 300 x 200 mm
  mirror a true sphere or toroid (`surface=parabolic` builds the paraboloid geom.js traces instead), the fold a
  plane sized as the housing sizes it, the housing black walls with the lid aperture cut out, and the 60 x 30 mm crop
  an emitter showing an 11 x 5 dot grid (the bigger dot is the top-left corner). A pinhole camera at the eye renders
  the image; stereo pairs (eye moved 40 mm sideways, 30 mm up and down) give the sagittal and tangential image
  distances dot by dot; a single 0.06 mm dot seen through the laminate gives the ghost; nine eye-box points give the
  vignetting; a second field of view checks the pixel-to-angle mapping (0.07 arcminute). Writes `results.json` and the
  pictures the simulator shows in the Vehicle mode's optics panel under "Cycles reference". About 5 minutes on the M4
  GPU at 256 samples; `quick=1` runs a small subset in seconds.
- `sun_focus.py`: numpy only. Parallel sunlight (with the 0.53 deg disc) through the laminate, the lid aperture, the
  mirror and the fold to the panel plane, for the nominal sun and for a grid of sun directions. Writes
  `sun_focus.json`, `sun_spot.png` (irradiance on the panel) and `sun_patch.png` (which sun directions light the crop
  and the cell). A path tracer cannot render a reflective caustic of a delta light, which is why this is a ray bundle.
- `bake_sky.py`: Blender's multiple-scattering sky (the model behind Cycles' Sky Texture, sun disc off) rendered to
  512 x 256 equirectangular EXRs at nine sun elevations from 2.3 deg (the dusk scene) to 76 deg (solar noon on June 21
  at 37 N), plus a CIE overcast sky and a moonless night floor made in numpy. Each map is normalised and the
  manifest records its sun column, so `arhud-sim/js/assets.js` rotates it to the world's sun at run time. The
  artifact host serves no `.exr`, so the script also writes each map as `.exr.txt` (the same bytes in base64), which
  `assets.js` decodes; those are what the artifact carries, published as `text/plain`.

- `car_bake.py`: the Blender pass over the simulator's own car. `arhud-sim/dev/export-car.html` writes the procedural
  car (`js/car.js`) as a GLB in which every mesh is named by its path under the car's groups and tagged static or
  occluder (wheels, driver, glass, emissive parts). Blender merges the duplicated vertices, bevels the plain boxes,
  tessellates long edges, shades smooth by angle, bakes ambient occlusion from the whole car into a vertex colour
  layer, and exports the static parts as a Draco GLB. `js/car-glb.js` lays each baked part over its procedural twin
  (same parent, transform, shadows and material, cloned with vertex colours on) only while the vertex count and
  bounding box still match, so a stale file after a change to `car.js` leaves that part procedural. `&noglb` on the
  hash keeps the procedural car. Rerun the export and the bake after any change to `car.js`.

- `car_body.py`: a car body modelled from scratch in Blender, to the simulator's dimensions. A subdivision-surface
  cage lofted from the numbers in `car.js` and `layout.json` (sill, door bulge, shoulder and belt line, hood, the
  planar windshield on the traced glass plane, A-pillars, the tumblehome of the side glass, roof, rear glass, deck),
  wheel arches cut with booleans, a black B-pillar, ambient occlusion baked with the rest of the car as occluders,
  exported as two halves (left and right of the centre line) that `js/car-glb.js` lays over the 27 procedural exterior
  parts they stand in for, borrowing the car's paint, glass and trim materials so the x-ray and the cutaways keep
  working. The windshield faces are left out: the procedural glass is the optical surface the trace uses. `preview=1`
  writes Workbench views to `_car_body_preview/`.
- `freeform_mirror.py`: a freeform mirror that flattens the image surface. Numpy only. On the same trace geom.js uses,
  it solves for every dot of the test grid the field directions from eyes 40 mm sideways and 30 mm vertically that
  land on the dot, takes the sagittal and tangential image distances from the parallax, and fits a polynomial sag
  (nine terms, even in the lateral coordinate) by Levenberg-Marquardt on the dioptric error against a target of 7.5
  m, with a distortion term that keeps the dots on an affine grid (weight `distortion=`, default 3). Writes
  `freeform.json` (optics_check.py reads it for `modes=freeform`) and `arhud-sim/js/freeform.js` (geom.js traces the
  same surface as mirror mode `freeform`; the Vehicle and Components panels offer it as a third figure). Cycles
  confirms the result independently.
- `freeform_mirror.py` also takes `glassRh=`/`glassRv=` (the windshield's radii, as optics_check.py builds the laminate) and `name=`, so the same fit runs against a curved windshield; with a coarse search over the vertex powers and the panel tilt before the local fit, since the plan's toroid is nowhere near a solution for curved glass.
- `scan_sim.py`: a simulated handheld scanner inside the car, so the scan workflow is exercised on data that behaves
  like a scanner's output rather than a perturbed mesh. Six sensor poses on the two front seats cast depth images
  (a structured-light-like grid of rays, 62 deg field) into the exported car with glass and emissive parts removed
  (scanners return nothing from glass), add range noise that grows with distance and 5% dropouts, triangulate each
  depth image without bridging depth jumps (so occlusions leave holes), merge the overlapping sheets, move the whole
  thing by an unknown rigid transform into millimetres, and write a PLY plus the landmarks a user would measure in it.
  `import_scan.py` run on that output exactly as on a real scan (scale=0.001, four pairs with 3 mm measuring noise)
  fits to 1.4 mm rms and brings landmarks it did not use (the eye, the top of the glass, the crop, the mirror) back
  within 5 to 6 mm, which is the measuring noise, not the tool. That scan ships as the stand-in under "Scanned car".
- `optics_check.py lum=1`: the luminance survey. A uniform white panel instead of the dot grid, and the mean
  radiance over the window's interior at the nominal eye and the nine eye-box points, for each mirror figure and for
  cells with viewing-angle profiles cos^k (lcdKs=0,1,2: Lambertian as the plan assumes, IPS-like, TN-like; the
  emission strength is |N.I|^k). Radiance survives reflection except for the reflectance, so this is the luminance
  at the eye as a fraction of the panel's, independent of magnification and blur. Findings: with a Lambertian cell
  every figure delivers 25.0% (mirrors perfect), which is Fresnel for both surfaces of the laminate, unpolarised, at
  the chief ray's 67.0 deg incidence (24.6%). The freeform figure's 38.7 deg panel tilt costs 23% with an IPS-like
  cell and 40% with a TN-like one (eye box down to 47%); the curved-glass refit's 15 deg tilt costs 4% and 8%. The
  plan's path figures (R_WS 0.24 one surface, 0.37 both) are the s-polarised values at 65 deg. The plan designs for
  s-polarised panel light (spec 7.2: measure the panel's axis, often 45 deg, orient it s or add a half-wave retarder
  film; polarised sunglasses block the image, demo rule none worn), so the figure holds once the axis is set;
  unpolarised, or at 45 deg as bought, the path is 0.14 / 0.25, 59% of the plan's. The plan's own rake 28 deg and
  look-down 5 deg give 67.0 deg incidence (spec 7.2 prints that check) and the simulator's glass sits there, while
  the plan's reflectance and ghost use 65 deg: at 67.0 deg the s-polarised path is 0.26 / 0.40, 11% more. Merged into results.json
  under "luminance"; shown in the Cycles section as "Luminance at the eye".
- `optics_check.py stray=1`: the stray-light survey. White panel, a 30 deg view from the eye, every connected lit
  region measured against the image, then the mirror and the fold hidden in turn to attribute each region. Result:
  none above 0.1% of the image from the optics alone. This run found that the Cycles panel emitted from both faces
  with its front turned away from the fold, so the mirror saw the panel's back directly: the "second window" in the
  night driver's view was that artefact, not a stray path (the caption said otherwise and is corrected). The cell
  is now one-sided and faces the fold; the luminance figures are unaffected (their profile was symmetric), and
  `driver_view.png` and `driver_view_night.png` are re-rendered with the corrected panel: one window, no halo.
  After the fix the whole cross-check was rerun at the published settings (128 samples, 1800 px; flat and curved
  glass): the curved-glass numbers reproduce to six decimals, the toroid and sphere within noise, but the flat-glass
  freeform's window had been contaminated by the artefact's lit region above the image (5.8 deg top width, 5.7 deg
  tall, centre 1.1 deg up); the clean value is 9.15 deg wide at both edges and 3.64 deg tall, against the trace's
  9.13 x 3.50, which is the straight-edged window the tilted panel was designed to give.
  `cover=1` adds the dust cover (2 mm uncoated glass across the lid aperture, in the lid plane): still no stray
  region above 0.1%, and the image drops to 88% of its bare value from the cover's two surfaces at the beam's
  incidence, which an anti-reflection coat would recover (results.json "strayCover").
- `beauty_render.py veil=1`: the daytime black level. The panel dark but real (diffuse 2%, specular 4%, anti-glare
  roughness 0.3, all ASSUMED; veilDiffuse/veilSpec/veilRough to change), lit by sky light through the aperture and
  imaged to the eye; three renders (panel hidden, dark, white at low samples for the window mask) and the veil is
  dark minus hidden over the mask. Result in the day scene (sun 38 deg up, behind-left): the veil is 0.07% of the
  scene behind the window and 0.06% of the sky, far below the eye's threshold for a uniform patch (about 1 to 2%),
  so sky light on the dark cell does not make the window show as a slab by day. Direct sun into the housing is a
  caustic path a path tracer cannot sample; sun_focus.py covers it. results.json "veil", driver_view_veil.png.
- The simulator's own drawing, checked against Cycles: a headless Chrome capture of the Driver view at the Cycles
  field of view (1800 x 1012, 7.9 deg vertical, `#drive&env=night&warm=2&bare=1&pattern=white&fov=7.9&noibl&noglb`)
  with the HUD canvas painted white, measured with the strict-threshold bounding box (the bloom glow fools a half-max
  one). The traced window rasterises at 8.748 x 4.579 deg, centre (0.000, 0.012), against the trace's 8.746 x 4.589
  (one pixel at 128 px/deg) and the projected quad corners; so the three.js camera, the image plane and the
  projection agree with the trace, which Cycles confirmed. The Driver view had defaulted to the plan's spec window
  (10.84 x 5.42 deg drawn), 24% wider and 18% taller than the hardware gives; the default is now the traced window
  and the spec stays as a labelled chip. results.json "simCheck"; a row in the Cycles section (toroid figure).
- The Driver view's virtual image on its real surface: install.js `imageSurface` / `imageDistanceAlong` put each
  grid point of the traced window at the sagittal image distance along the nominal eye's ray (the same local
  Coddington as cycles.js `fieldDistances`, which Cycles confirmed across the window). The nominal picture is
  identical by construction (the corners project to the same angles); head motion now swims each part of the image
  by its own distance: 65 mm lateral moves the top 43', the centre 26', the bottom 10' (toroid; the drawn surface
  spans 5.1 to 24.9 m). The freeform figures give a near-flat surface, which is the point of them.
  Registration is scored against the surface (hud.js `surfaceDir`), with the plane model's figure kept beside it,
  and hudd gets an option to project onto the surface (`surfaceAware`: the plane projection iterated against the
  local image distance; exact at the nominal eye and at 60 mm offset, where the plane projection leaves 35').
  In the plan's sway test (±75 mm) the plane-projecting hudd's lead error is 0.39 deg against the surface (the
  plane model said 0.08), failing the 0.3 deg gate; lane 0.24 deg (plane model 0.12). Surface-aware: 0.11 / 0.14.
  So hudd must carry the image-surface map; a single virtual-image distance is not enough for a toroid.
  The surface also gives the vergence conflict per symbol (hud.js `binocularConflict`: the eyes 65 mm apart converge
  on the symbol's surface point and on the object): lead marker about 50' on the toroid, 19' on the flat freeform
  (7 to 12 m); lane at 20 m 24' and 14'. Fusion limits 10 to 20' (ASSUMED). Shown in the Driver view's Live numbers.
- Registration through the optics, end to end. `main.js` `#drive&eye=DY,DZ&surf=0|1|2&pattern=marks&dump=pgupanel`
  makes hudd draw crosses at four road points (16 and 24 m ahead, 1 m left and right) for the eye it tracks, with
  the plane (0), image-surface (1) or eye-to-panel trace (2) projection, and dumps the frame pre-distorted to the
  panel by the trace (the mapping panel point -> field direction on an 8 px grid). `beauty_render.py marks=1
  eyeDz=0.075 name=... npy=...` renders it through the optics from that eye over red self-lit discs at the same
  points (fov 30, 128 samples, 0.89 px per arcminute); the scratchpad's measure.py pairs cross centroids with disc
  centroids. Results (results.json "regCheck"): nominal eye 1.2' mean, 2.3' max; eye 75 mm right with the plane
  projection 12.9' mean, 17.6' max; the image-surface map 9.0' / 15.6' (one side fixed, the other's vertical error
  stays); the optical model 1.4' / 1.6' at 75 mm and 2.3' / 4.2' at 60 mm; eye 35 mm up: plane 14.5' max, optical model 1.3'; the
  freeform figure (mirror=freeform on both ends): nominal 1.3' max, eye 75 mm right with the plane projection 31'
  (the tilted panel's image swims with the eye, flat only for the nominal one), optical model 1.2'; the curved
  windshield (glassRh=4 glassRv=8 on the render, glass=4,8 on the capture, or mirror=freeformCurved for the refit on
  both): refitted freeform, nominal 5 to 6' (the curved-glass trace carries a 4' vertical bias against Cycles), eye
  75 mm right with the plane projection 89' on one mark and 1.7' on the other, optical model 3.2 to 3.7'. The
  toroid with the curved glass forms no usable virtual image and was not checked. So hudd must project by the optical
  model from the tracked eye (or a calibrated eye-position-to-panel map); an image-surface map is not enough.
  The check also caught the trace itself: geom.js traced the sphere and toroid as paraboloids, 0.4 mm low at the
  aperture edge (18' of slope), which Cycles showed as 33' of registration error at the eye-box edge; the trace
  now uses the true surfaces (Newton on the sag for every figure), and its nominal-eye dot agreement with Cycles
  went from 2.56' rms / 6.0' max to 0.59' / 0.94' (toroid) and 1.92' / 4.9' to 0.32' / 0.57' (sphere).
- The lookup table for hudd (`../arhud-sim/js/lut.js`, `dev/export-lut.mjs`): the optical model as the Jetson would
  run it, a table of 11 x 7 eye positions over the eye box (with margin) by 57 x 29 field directions over the window,
  each entry the panel point the trace lands on, plus the inverse of the nominal mapping on a 43 x 22 panel grid;
  bilinear in the eye and in the field. Against the exact trace over 400 random eye positions and directions: 0.35'
  rms, 0.75' max (toroid), 0.32' / 1.01' (freeform); a 7 x 5 by 29 x 15 table gives 2 to 2.7' max. Built in 0.1 to
  0.26 s; 1.8 MB as JSON per figure (`assets/hudd_lut_toroid.json`, `_freeform.json`,
  `_freeformCurved_glass4x8.json`). In the simulator's sway test on the four window marks the table matches the
  exact projection (5.7' against 5.6' worst, the tracker's lag) at full frame rate, where the plane gives 17' and
  the image-surface map 15'. Through Cycles (surf=3 on the capture) the table's frame at 75 mm registers to 1.4' mean,
  1.6' max, the same as the exact projection. The Live numbers now score only symbols inside the window; the earlier lead and lane
  figures had included off-window symbols the plane and trace extrapolated.
- `optics_check.py eyebox=1`: the eye box as measured. The white window from eyes moved laterally to 140 mm and
  vertically to ±85 mm; the lit area relative to the nominal eye. Whole to ±80 mm lateral (91% at 95, 83% at 110,
  75% at 125, 67% at 140); vertically the perspective changes the area too (a lower eye sees a larger window: 115%
  at -35 mm), and clipping takes hold past about +55 mm (86%, then 68% at +70) and -50 mm (83% at -55, 50% at -70).
  So the real eye box is about ±85 x ±50 mm against the plan's ±65 x ±35, with no dimming before the clip
  (mean radiance within a few percent throughout). results.json "eyeboxExtent"; a block in the Cycles section.
  The freeform figure (ebMode=freeform): the same laterally, more tolerant vertically (104% at +55, 95% at -55,
  81% at +70). The Driver view's vignette tested only the mirror aperture; it now tests the lid aperture and the fold
  glass and the lit crop too (js/clip.js, shared with cycles.js) and matches Cycles laterally (92 / 79 / 70 / 62% at
  95 / 110 / 125 / 140 mm against 91 / 83 / 75 / 67) and upward (86 / 71% at +55 / +70 against 86 / 68). Downward
  it did not, until hiding the housing's parts in Cycles one at a time (lid, floor, end walls, side walls) and
  casting single rays through the scene found the cause: from a low eye the ray to the window's bottom hits the
  housing's own rear top (lidY(xR) = 1.1035 m) before it reaches the glass. The nominal eye's line clears that edge
  by 43 mm, the plan's lowest eye (-35 mm) by 11 mm, -45 mm by 1 mm; so the eye box's lower limit is the housing's
  rear height, not the optics. With that test the vignette gives 86 / 57 / 29% at -55 / -70 / -85 against Cycles'
  83 / 50 / 15, the 13 x 7 grid's resolution.
- The night slab's shape: the Driver view drew the lit panel's black-level glow as the inscribed rectangle; the
  night render shows the crop's true image, a trapezoid wider at the bottom. The glow is now drawn over the crop
  mapped through the trace (install.js `cropSurface`: 8.97 deg wide at the top, 10.04 at the bottom, 4.76 tall,
  against Cycles' 8.99 / 10.05 / 4.93), the content on the inscribed rectangle as before.
- `optics_check.py field=1`: the window outline re-measured with median edges (per-column top and bottom, per-row
  widths near the edges) instead of the first and last lit row, which a few stray pixels of the glass's sampling
  noise had stretched. Toroid 9.01 / 10.03 deg wide, 4.82 deg tall (was 4.93) against the trace's 8.97 / 10.04 /
  4.76; sphere 5.42 (was 5.53); freeform 3.61 (was 3.64). The remaining 0.06 deg of height is the edge blur at the
  half-fill threshold. Only the field entries change.
- `mirror_export.py`: the fitted mirror for manufacture. Writes `export/sag_<fit>.csv` (a 1 mm sag table over the
  300 x 200 mm aperture, u lateral, v in the plane of incidence, w toward the light, millimetres, next to the plan's
  toroid as a reference) and `export/mirror_<fit>.stl` (the surface over a 12 mm substrate, millimetres) for a CNC or
  diamond-turning quote. The flat-glass freeform departs from the toroid by at most 0.57 mm; the curved-glass fit by
  5.9 mm.
- `beauty_render.py`: the driver's view, path-traced. The car from `export-car.html` (every mesh with its three.js
  material, the windshield turned into real laminated glass), the PGU frame hudd actually drew (main.js dumps it with
  `#drive&warm=10&dump=pgu` under a headless `--dump-dom`), and the optics from `optics_check.py`'s builders, under
  the sky model with its sun. The HUD light reaches the camera as it reaches the driver, ghost and keystone included.
  Writes `driver_view.png` and a HUD-off twin to `assets/cycles/` and a `beauty` entry in `results.json`; the Driver
  view's Cycles dock tab and the Cycles reference section show it. `scene=night` adds `driver_view_night.png`: the sun
  below the horizon, headlight spots where car.js puts them, the HUD at a night gain.
- `import_scan.py`: the scan workflow. Imports a scan of the real dash and glass (PLY, OBJ, STL or GLB), joins it,
  drops loose fragments, optionally decimates, aligns it to the simulator's frame by a Kabsch fit over point pairs
  you measure (`pair=sx,sy,sz:tx,ty,tz`, scan point to simulator point: the eye, the glass's bottom centre, the
  mirror-stalk button, the top of the glass), prints the residual, and exports `assets/scan.glb` (+ base64 and a
  `scan.json` with the provenance). `js/scan.js` shows it in Vehicle mode under "Scanned car". `test=1` builds a
  synthetic scan from the exported car, perturbs it and checks the fit (2.5 mm residual, 4 mm landmark error with
  1.5 mm noise); `hard=1` makes it a worst case (millimetre units with the scale refitted, 5 mm noise, half the dash
  missing, loose junk, three pairs) and still lands within 4 mm. That synthetic scan ships, clearly labelled, until a
  real one replaces it.

## The freeform fix, and why the panel has to tilt

With the toroid the image runs from 6 to 19 m across the window. A freeform surface alone cannot fix that: the terms
that flatten the image distance are the same terms that bow the window's edges, so every weighting of
`freeform_mirror.py` with a flat panel trades one for the other (image 7.1-7.7 m with a 3.6 deg window, or 5.7-10.6 m
with 4.1 deg; pushing the edges straight at weight 20 sends the image from -5.7 to 59 m). The coupling breaks when
the panel is a free parameter too. With the panel tilted 38.7 deg about the lateral axis (rear edge up) and shifted
3 mm along the fold-to-panel leg, the fit gives a virtual image at 7.44-7.53 m sagittal and 7.46-7.54 m tangential
over the whole crop, dots on an affine grid to 0.006 deg rms and window edges straight to 0.002 deg. Cycles, with
the tilted panel and the fitted surface built as meshes, measures 7.53-7.65 m and 7.61-7.74 m with the edge rows
straight to 0.005 deg: a rectangular window with no keystone. The price is height: the tilted crop is seen
foreshortened, so the 60 x 30 mm crop gives a 9.1 x 3.6 deg window instead of 8.75 x 4.6; a 60 x 38 mm crop of the
same 5.5-inch panel restores the height, and the IPS cell's viewing angle covers the 39 deg off-normal view. This is
the simulator's third mirror figure, "Freeform + tilted panel": geom.js traces the tilted panel for it
(`panelPose`), while the PGU is still drawn flat in the housing.

## What Cycles and the ray bundle found (toroid, true surface)

- The pixel-to-angle mapping and the dot pattern are consistent to 0.07 arcminute, so the numbers below are geometry,
  not measurement noise.
- Image distance at the window centre: 9.1 m sagittal, 9.3 m tangential from the eye, against the paraxial trace's
  8.56 m. The real finding is across the window: 6.2 m at the top row to 19.5 m at the bottom row (sagittal), 5.5 m to
  46 m (tangential). The panel sits 14 mm inside the focus, so the small change of incidence across the window moves
  the image a long way, and the wrong way round for a road: the top of the window, which covers the far road, is the
  near image. A flat 7.5 m image needs either a freeform mirror or a smaller magnification.
- The sphere as the plan wrote it: sagittal 4.3 to 7.3 m across the window, tangential from 9 m through infinity to a
  real image 8 m in front of the eye. The astigmatism is as predicted, and it varies strongly across the field.
- The ghost sits 1.24 arcminutes above the main image, 74% as bright with Cycles' unpolarised Fresnel (the plan's
  s-polarised figure is 58%). calc.py's 1.43 arcminutes assumes a 7.5 m image; at the measured 9 m it is 1.2.
- Eye box: every dot of the grid reaches the eye from all nine eye-box points (65 mm sideways, 35 mm up and down)
  through the lid aperture, the 300 mm mirror and the fold; the dots sit 5 mm inside the crop's edge, so the
  vignetting the trace predicts for the window's outer corners at the eye-box edges does not reach them. From the
  upper eye-box row a faint, flattened second copy of the window appears about 3.5 deg above the main one: the exit
  beam reflected back from the inside of the glass to the mirror and out again, a path the real unit's dust cover
  and dash must absorb.
- Sun focus: the mirror collects 31 W through the lid aperture (the plan's 42 W assumes the whole mirror face-on);
  4.0 W reach the panel after the cold mirror, the IR-cut glass and the polariser, into a comatic spot (a hot core
  with two wings) whose 90% radius is 6 mm, twice the plan's 3.2 mm, with a 1 mm peak of 130 kW/m2, about three
  times TI's production figure. Focused light lands on the crop only for sun elevations of 48 to 52.5 deg (18 deg of
  azimuth), but it lands somewhere on the cell for 43.5 to 57 deg and 39 deg of azimuth: the sun-watch rule should
  use the cell patch, which is wider than the plan's 20.7 x 10.8 deg patch. The simulator's hudd now does: install.js
  hands the cell patch from `sun_focus.json` to the sun-watch rule when the file is present.

## Scope ledger: every Blender candidate, and where it ended

| Candidate | Status | Evidence |
|---|---|---|
| Physically based cross-check of the optics | done | `optics_check.py`; three figures, 0.07' mapping self-check, results in the Vehicle panel |
| Sun focus and entry patch | done | `sun_focus.py`; comatic spot, cell patch now used by hudd |
| Sky lighting for the driving world | done | `bake_sky.py`; nine elevations plus overcast and night, rotated at run time |
| Smoother, shaded car | done twice | `car_bake.py` (131 parts, baked occlusion) and `car_body.py` (shell modelled from scratch) |
| Driver's view with the real HUD frame | done, day and night | `beauty_render.py`; `driver_view.png`, `driver_view_night.png` |
| Luminance cost of the tilted panel, and the windshield path against the plan's figure | done |
| Stray light: the optics alone and with the dust cover | done, none above 0.1%; the cover costs 12% of the image |
| Daytime black level from sky light on the dark cell | done, 0.07% of the scene behind the window |
| The Driver view's drawing of the window against the trace and Cycles | done, within a pixel; default changed from the spec window to the traced one |
| The virtual image drawn on the Cycles-confirmed image surface, so head motion swims as in the car | done, 5.1 to 24.9 m across the toroid's window |
| Registration scored against that surface; hudd option to project onto it | done; the sway test's lead error is 0.39° with a plane-projecting hudd, 0.11° surface-aware |
| Vergence conflict per symbol from the image surface | done; lead marker 50′ on the toroid, 19′ on the flat freeform |
| Registration through the optics end to end (hudd frame → Cycles) for three projections, lateral and vertical offsets, toroid, freeform and the curved-glass refit | done; plane 18′ (freeform 31′, curved glass 89′), surface map 16′, optical model 1.6 to 3.7′ at 75 mm |
| The trace's mirror surfaces made true (sphere, toroid) | done; nominal dot agreement with Cycles 2.6′ → 0.6′ rms |
| hudd's calibration table (eye position × field → panel), exported, with its accuracy | done; within 1′ of the exact projection, full frame rate in the simulator |
| The eye box as measured, against the plan's | done; whole to ±80 mm lateral and about ±50 mm vertical |
| The night slab drawn as the crop's keystoned image | done; 8.97 / 10.04° against Cycles' 9.01 / 10.03° |
| The window outline measurement in Cycles made robust to sampling noise | done; the height discrepancy against the trace fell from 0.17° to 0.06° |
| The Driver view's vignette model checked against that survey and completed with the housing's top, the lid, the fold and the crop | done; matches in every direction; the housing's rear height sets the lower eye-box limit, 11 mm of margin at the plan's lowest eye |
| Scan of the real dash into the simulator | done to the limit of what exists | `import_scan.py` on `scan_sim.py`'s simulated handheld scan (six poses, 56k returns, range noise, dropouts, occlusion holes, no glass, unknown frame in millimetres): 1.4 mm fit, landmarks not used in the fit within 5 to 6 mm, the measuring noise. The physical scan of the car is user input that does not exist yet; everything up to it is built and exercised |
| Flat image across the window | done, with the panel tilt | `freeform_mirror.py`; a surface alone cannot (shown at three weights), surface plus a 38.7 deg panel tilt can, Cycles agrees to 1.5% |
| Sun-focus render in Cycles | not possible | a reflective caustic of a delta light; path tracing and MNEE do not resolve it, hence the numeric bundle |
| Windshield modelled in Blender, the design refitted for it, and the curved glass in the simulator's own trace | done | `optics_check.py glassRh=4 glassRv=8`: a windshield with 4 m lateral and 8 m vertical radii (concave toward the driver) turns the toroid's 9 m image into a real image about 12 m in front of the eye sagittally and 11 m tangentially, widens the window to about 10 x 7.5 deg and doubles the ghost; the plan's flat-glass assumption does not survive a real windshield. `freeform_mirror.py glassRh=4 glassRv=8 name=freeform_curved` refits the mirror and the panel against that glass: image 7.4-7.6 m sagittal and 7.5 m tangential across the window, edges straight, with a weaker mirror (vertex radii 764 / 1113 mm), a 15 deg panel tilt and a 27 mm shift; `optics_check.py glassRh=4 glassRv=8 modes=freeform` verifies it. The simulator's trace models the curved glass too (figure "Freeform for a curved windshield"), so the Driver view runs on it; the Cycles section shows both the damage and the refit |
| Tilted PGU drawn in the housing for the freeform | done | `Garage.applyPanelPose` tilts and shifts the installed PGU part with the figure; the housing itself is another session's build123d model |

## Conventions

- Cycles' Fresnel is unpolarised. Positions, distances and vignetting are compared; brightness ratios are reported but
  not compared with the plan's s-polarised numbers.
- Pictures are display-referred PNGs made from the linear EXR renders in numpy (Reinhard, gamma 2.2), with the fill of
  the crop (2% emission) kept visible so the window's keystone shows.
- The sky maps are lighting only; the procedural sky in `world.js` remains the visible background and follows the sun
  continuously, while the environment map switches to the nearest baked elevation.
