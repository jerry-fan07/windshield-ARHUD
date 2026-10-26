# AR HUD x-ray component display (Blender)

A 3-D display of every component in the TFT-edition AR HUD (`docs/ARHUD-PLAN-TFT-SPEC.md`), together, on a white background. The HUD unit and its optics, the cameras, GNSS, Jetson, controller, power, network, audience display, every cable run, the traced light path and eye box sit at their mount points in the car. The bench rigs and test instruments stand in a row behind the car. Pick the components you want to see. Everything else becomes an x-ray ghost (translucent blue with bright edges), a frosted ghost, or is hidden, and the ghosts can also be blurred.

## Open it

1. Open `arhud-xray.blend` in Blender 5.2 (built with 5.2.3; it uses the 5.x compositor API, and earlier versions are untested).
2. Blender blocks scripts embedded in a file until you allow them. Click **Allow Execution** in the warning that appears, or reopen the file with Auto Run Python Scripts enabled. The panel is the embedded text block `arhud_xray.py`, registered on load.
   - Alternatively, install `arhud_xray.py` once as an add-on (Edit › Preferences › Add-ons › Install from Disk). The panel then works in this file without the prompt and stays empty in other files.
3. The 3-D view opens in Material Preview with the sidebar on the **AR HUD** tab. Press `N` if the sidebar is closed.

The file opens in its default state: project parts solid, the car ghosted.

## The panel (View3D › Sidebar › AR HUD)

**X-ray display**

- **X-ray / Frosted / Hide**: how unticked components are drawn.
  - X-ray is unlit blue with a bright fresnel rim, so outlines stay legible on white.
  - Frosted is pale and keeps its shading.
  - Hide removes them.
- **Ghost strength** and **tint** change both ghost materials live.
- **Blur ghosts** (with its radius) blurs only what is not solid. Every real material writes the AOV `xr_solid`, and the compositor blurs where that AOV is 0. The blur shows in Material Preview and Rendered shading, and in F12 renders.
- **All / None / Invert / Reset**: every component solid, all ghosted, swap, or back to the default (project parts solid, car and windshield ghosted).
- **Selected parts** shows solid the components of whatever you selected in the viewport. **Click to focus** does this on every click; ghosts become unclickable then, so a click goes through the x-ray shell to the part inside.

**About**: the component you last chose. It shows the name, which assembly it belongs to, the description, and the key numbers from the plan, tagged ASSUMED or UNVERIFIED as the plan tags them. It also shows where the part is mounted, with **Isolate** and **Frame** buttons. Frame moves the view to the part and leaves the selection alone.

**Components**: a search box and the tree.
- Each category shows a solid/total count, plus buttons to make the whole group solid or ghost it.
- Components and their sub-parts nest under each category. For example, HUD optical unit › Picture generator › LED backlight, LCD cell, retarder, HDMI board, bracket.
- The checkbox means "show solid", and ticking a parent ticks all its parts.
- The star button isolates that component (Shift-click adds it to what is shown). The **i** button shows it in the About card.

**Views** (folded): preset cameras (Overview, Side cutaway, HUD unit, Footwell, Bench, Top) and *Fit a camera to the solid parts*. F12 renders the active camera with the current ghosts and blur.

Close-ups: a ghost surface that lies well in front of the solid parts fades out, so you look through the roof or the dash at the part instead of seeing it tinted blue. Ghosts beside and behind the part keep their full strength as context. The shader is told where the solid parts are each time the selection changes, so this holds while you orbit.

Solid viewport shading also works. Ghost materials carry a translucent viewport colour, and the world colour keeps the background white. The blur needs Material Preview or Rendered.

## Display choices

- **Floor.** The floor is an emission shader at exactly white, darkened only by ambient occlusion where something sits close above it. A lit white floor renders above 1.0 and clips, which washed out every ghost seen against it.
- **Glass and film.** The windshield, dust cover, retarder, prism films and bench combiners are teal with a fresnel edge, so solid glass cannot be mistaken for a blue ghost. Polished mirrors are toned down so they don't render as blank white cards.
- **Cables.** The runs are thickened for display (a Displace modifier). USB is charcoal and the GNSS coax is tan, so neither looks like a ghost.
- **Layout corrections.** These are applied here, not in the simulator:
  - The USB-C PD charger was mounted backwards inside the console; it is turned round.
  - The 30 m target board faces the cameras.
  - Two helper empties 34 m away are removed, so View All frames the scene.

## Command-line renders

```
B=/Applications/Blender.app/Contents/MacOS/Blender
$B -b docs/arhud-xray/arhud-xray.blend -P docs/arhud-xray/render.py -- --list
$B -b docs/arhud-xray/arhud-xray.blend -P docs/arhud-xray/render.py -- --show jetson,zed2i --camera auto:footwell --out /tmp/a.png
$B -b docs/arhud-xray/arhud-xray.blend -P docs/arhud-xray/render.py -- --show pgu,coldMirror,concaveMirror --camera side --blur 10 --out /tmp/b.png
$B -b docs/arhud-xray/arhud-xray.blend -P docs/arhud-xray/render.py -- --gallery docs/arhud-xray/renders/gallery
```

`--show` takes `default`, `all`, `none` or item ids. `--mode` is `XRAY`, `FADE` or `HIDE`. `--camera` takes a preset or `auto:<preset>`, which fits the camera to the shown items along that preset's direction. `--engine cycles` renders with Cycles on the GPU.

## Where it comes from, and how to rebuild

The geometry is the simulator's (`docs/arhud-sim`), so the parts keep the dimensions and mount points computed there from `calc.py`. Blender adds the assembly into one scene, the component tree, the x-ray, frosted and blur system, the white studio, the cameras, and the exports. Nothing under `docs/arhud-sim` is modified.

1. **Export from the simulator.** Run `python3 docs/arhud-xray/tools/serve.py 8765`, then open `http://127.0.0.1:8765/arhud-xray/tools/export.html` in Chrome (headless works). The simulator may since have gained a baked-car overlay (`js/car-glb.js`); if a re-export shows doubled car parts, disable it the way that module documents (`&noglb`) before exporting. It writes `source/installed.glb` (the car with every installed part and the cable runs), `source/bench.glb` (rigs and instruments) and `source/layout.json` (mount points, cable runs, the traced light path, and each component's description, facts and parts).
2. **Build the .blend.** Run `$B -b --factory-startup -P docs/arhud-xray/build_scene.py`. It sorts the imported objects into components by their node path (`mount:<id>`, the HUD unit's part names, `cable:<id>`, `bench:<id>`, car body, interior, wheels, driver), stores the tree as the text block `arhud_items.json`, and adds the light path, eye box, studio, cameras and compositor.
3. **Web export.** Run `$B -b docs/arhud-xray/arhud-xray.blend -P docs/arhud-xray/export_web.py`. It writes the model three ways, plus two JSON files:
   - `viewer/arhud.glb.gz`: the plain GLB, gzipped. The browser unpacks it with DecompressionStream.
   - `viewer/arhud.glb.gz.b64.txt`: the same bytes as base64 text, for the artifact host.
   - `viewer/arhud.glb`: Draco-compressed, the fallback.
   - `viewer/items.json` and `viewer/cameras.json`.

   Every node carries `extras.xr_item`.
4. **Publish.** The browser version is the private artifact https://claude.ai/artifact/PvGzt49DwMgEXMVshykBrB. Republish `viewer/index.html` to that URL with `arhud.glb.gz.b64.txt`, `items.json` and `cameras.json` as its files. The host serves only web file types (no `.gz` or `.glb`), which is why the model ships as base64 text.

## Files

- `arhud-xray.blend`: the display.
- `arhud_xray.py`: the component tree, the x-ray switching, the panel. It is embedded in the .blend and also installable as an add-on.
- `build_scene.py`, `render.py`, `export_web.py`: build, render and export.
- `tools/export.html`, `tools/serve.py`: the simulator export.
- `source/`: the exported simulator geometry and layout.
- `viewer/`: the browser version (same tree, modes and blur), built from the web export and published at https://claude.ai/artifact/PvGzt49DwMgEXMVshykBrB.
- `renders/`: `gallery/` holds one render per component, isolated; `views/` holds the six preset views plus one with blur.

## Known limitations of the browser version

- Ghost silhouettes are not antialiased.
- With a filter typed in, All, None and Invert still act on the whole tree.
- Interior parts (seats, mannequin) read a little denser in close-ups than in EEVEE.
- Each glass material's own base alpha is lost in glTF; the viewer uses one value for all glass.
