# ARHUD housing CAD (build123d)

The printed housing for the TFT-edition HUD, modelled in build123d from the simulator's own optical layout. The
script builds every part and checks the result against the traced light path, the windshield, the simulator's car and
the printer. It then writes print files and a GLB that the simulator loads.

## Run it

```
cd docs/arhud-cad
node dump_layout.mjs                              # only when geom.js or calc.py numbers change
~/.venvs/arhud-cad/bin/python make.py             # build, check, export (about 30 s)
~/.venvs/arhud-cad/bin/python make.py --quick     # build and check only
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/preview.py -- OUT_DIR [assembled cutaway exploded bay mirror lid section]
```

- `dump_layout.mjs` imports `../arhud-sim/js/geom.js` and `components/optics.js` and writes `layout.json`. It includes the panel, fold, mirror and lid frames, the traced aperture and 375 sampled rays for each mirror figure. Node finds three.js through `docs/arhud-sim/node_modules`.
- The venv is `~/.venvs/arhud-cad` (build123d 0.13.0; see the simulator README for how to recreate it).

## Outputs

| File | What |
|---|---|
| `out/arhud-housing.step` | Every part as a named solid in the car frame (mm): the assembly for any CAD tool |
| `out/stl/*.stl` | One STL per printed part, already on its print face and yawed to fit the bed |
| `out/shutter-leaves.dxf` | Flat patterns for the two 0.5 mm aluminium shutter leaves (laser cut) |
| `out/BOM.md` | Printed parts with bed size, supports and mass, bought and sheet parts, every fastener |
| `out/housing.json` | Parts, build steps, explode offsets, print orientation, check results |
| `out/preview/*.png` | Blender renders: assembled, cutaway, exploded, and a side section with the traced rays |
| `../arhud-sim/assets/cad/housing.glb`, `housing.json` | What the simulator loads (car frame, metres, one node per part) |

## The design

The layout fixes the envelope: 459 mm long, 370 mm wide and 300 mm tall from the dash. No desktop printer takes that in one piece. Every printed piece here fits a 250 mm cube (`BED` in `hudcad/geo.py`).

- **Body.** Four quarters, split at x = 796 mm and on the centreline. They print on their side walls with no supports. Continuous internal flange strips at the seams take M3 screws into brass heat-set inserts and keep light out of the joints. The rear quarters' front strip is the stray-light baffle, 6 mm under the lowest mirror-to-fold ray.
- **Step over the cluster hood.** In the simulator's car the instrument-cluster hood stands where the housing's rear and the panel's HDMI board were. The floor steps up at x = 640 mm, and the rear 73 mm (the shutter garage) rides 5 mm over the hood.
- **Lid.** Four pieces, printed face down. They join with half laps and countersunk screws so the underside the shutter runs on stays flat. Spigot tabs drop 14 mm into the body, and M3 screws through the body walls hold them. The 6 mm lid takes the 3 mm dust-cover glass flush in a rebate. A facet at the nose keeps the housing 8 mm under the windshield.
- **PGU bay.** A sealed tub under the panel holds the heat sink (on four posts between its outer fins), the fan duct, and the HDMI board stood on edge against the right wall. The fan blows out through a grille in the floor, and fresh air comes in through slots fore and aft. The cables leave through TPU grommets in the bay floor and run under the housing in the 14 mm gap the levelling feet leave.
- **Panel carrier and mask.** These hold the cell by its edges at the traced height. The mask opening is the traced footprint plus 3 mm.
- **Fold bracket.** Holds the cold mirror at 35° and 50 mm over the panel, with tabs for the IR absorber. Its cheeks share the bay's corner screws, so panel and fold are one module.
- **Mirror mount.** The mirror is bonded with RTV to a ribbed strongback. Three M4 screws with springs (bed-levelling style) hold it to a stand on the floor. A ball-end key reaches them through three plugged holes in the front wall. Two clips catch the bottom edge outside the footprint.
- **Shutter.** Printed rails, two per side, hold the two leaves under the lid. The SG90 servo hangs behind the opening, out of the beam, with its lever under the leaves. A post under the front rim anchors the return spring.
- **Light traps and sensor.** Saw-tooth vanes line the mirror bay's walls. The ambient-light sensor sits in a pod on the lid, behind the glass.
- **Material.** ASA, matte black. Dash tops pass 80 °C in summer sun, PETG softens near 75 °C, and ASA holds to about 95 °C.

## What the checks report (`make.py`)

- **Beam.** 0 of 690 traced rays touch any part, for both mirror figures. The shutter leaves are checked in their open position. The nearest part is 1.8 mm from the beam, at the lid opening's front edge.
- **Panel glass (a layout finding).** 42 of the 690 rays pass through the front edge of the panel's own cell glass. They are the top of the HUD window seen from the top of the eye box. The fold sits only 50 mm over the panel (`FOLD_TO_PANEL` in geom.js, a simulator choice), so the mirror-to-fold rays skim the panel's front edge. 65–70 mm clears it with margin. That change moves the panel about 14–19 mm forward and 20–27 mm down, and this CAD regenerates around it. The simulator's HUD unit now draws these rays red.
- **Envelope.** Windshield 8 mm, cluster hood 5 mm, dash 11 mm under the floor bosses.
- **Fits.** No two solid parts overlap. Nothing overlaps the optics and boards the simulator draws itself (cell, backlight, heat sink, fan, HDMI board, fold glass, absorber, servo, mirror substrate).
- **Printer.** All 32 printed parts fit 250 × 250 × 250 mm.

## What the CAD changed in the simulator

- The lid opening is 262 × 263 mm. It is sized from the rays that actually land on the 300 mm mirror, so it is narrower than the simulator's 262 × 329 mm, which included rays the mirror's edge already loses. The dust cover and shutter in the installed unit take the CAD sizes.
- The shutter's pivot moved 2 mm inside the opening's edge, the lever runs under the leaves, the servo body sits behind the pivot, and the spring anchor sits 18 mm ahead of the opening. As drawn before, the lever swept through the rails' space and its pin left the leaf at both ends of travel.
- In the installed unit the HDMI board stands on edge in the bay.

## Files

- `hudcad/geo.py`: layout in millimetres, plus the design constants (printer, material, wall thicknesses, seams, clearances).
- `hudcad/shell.py`: body quarters and lid pieces, joints, aperture, glass rebate.
- `hudcad/internals.py`: bay, carrier, mask, fold bracket, mirror mount, rails, servo bracket, clamps, pod, vanes, grommets, plugs, feet.
- `hudcad/assembly.py`: builds everything and records the 18 build steps.
- `hudcad/checks.py`: beam, envelope, fit and printer checks.
- `hudcad/export.py`, `hudcad/mesh.py`: STEP, STL, DXF, BOM and the GLB (written directly from the B-rep triangulation, so the simulator's frame needs no axis conversion).
- `tools/preview.py`: Blender renders for checking the model by eye.
