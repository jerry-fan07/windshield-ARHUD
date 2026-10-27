# ARHUD tabletop design: source for docs/ARHUD-TABLETOP-DESIGN.pdf

The design of the two-monitor tabletop rig for the HUD-only TFT LCD edition: monitor unit 1 face up under a
teleprompter beamsplitter as the picture generator (as in build stage B6), monitor unit 2 upright behind the glass
showing a road, the HUD software detecting the road in that picture and drawing the registered overlay into the
reflection. Rig geometry and optics (Part I), road sources and detection (Part II), the renderer, timing,
calibration and the camera-in-the-loop variant (Part III), software layout, bring-up stages T-A to T-I, risks and
the bill of materials (Part IV).

    cd docs/arhud-tabletop-src
    python3 build.py            # writes out/tabletop.pdf (two passes for the contents page numbers)
    cp out/tabletop.pdf ../ARHUD-TABLETOP-DESIGN.pdf

Requirements: the same as the plan's (Python 3.12 standard library, Node with puppeteer-core through the
`node_modules` symlink to `../arhud-plan-src/node_modules`, poppler's `pdftotext`, Google Chrome).

Where things come from, so the design cannot drift from the project:

- `tcalc.py` derives every bench number (geometry, angular scale, luminance and gains, ghost, parallax variant,
  timing, lifting, BOM) and imports the TFT plan's `calc.py` (`../arhud-plan-tft-src`) for everything shared
  (the window, the monitor's ppi and luminance, the combiner split, the latency budget, camera height). Run
  `python3 tcalc.py` to print every `{{key}}`.
- `figs_tt.py` holds the figures (inline SVG through the plan's `svgkit`); `t_side` and `t_top` are drawn to
  scale from `tcalc.py`.
- `tables.py` generates the tables from `tcalc.py`'s lists (`[[TBL name]]`).
- `style.css` is the build guide's stylesheet, copied; keep the document monochrome outside figures and in
  Helvetica Neue throughout (`pdffonts out/tabletop.pdf` must list only the HelveticaNeue family).

Text is in `parts/` (file order is document order). Rerun after any change to `tcalc.py` or to the plan's `calc.py`.
