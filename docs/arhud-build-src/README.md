# ARHUD build guide: source for docs/ARHUD-BUILD-GUIDE.pdf

The build guide for the HUD-only TFT LCD edition: the intuitive overview (Part I), workshop and materials (Part II),
the fourteen build stages B1–B14 (Part III) and the reference appendices. It is a companion to
`docs/ARHUD-PLAN-TFT.pdf`, not a revision of it.

    cd docs/arhud-build-src
    python3 build.py            # writes out/guide.pdf (two passes for the contents page numbers)
    cp out/guide.pdf ../ARHUD-BUILD-GUIDE.pdf

Requirements: the same as the plan's (Python 3.12 standard library, Node with puppeteer-core through the
`node_modules` symlink, poppler's `pdftotext`, Google Chrome) plus macOS `sips` for the embedded CAD renders.

Where things come from, so the guide cannot drift from the project:

- `{{key}}` values are imported from `../arhud-plan-tft-src/calc.py` (never copied); the plan's own figures
  (`[[FIG mockup]]`, `sunentry`, `arch`, `gantt`) come from its figure registry.
- `data.py` reads the CAD housing (`../arhud-cad/out/housing.json`, `layout.json`) for the printed-parts, fastener and
  per-step tables (`[[TBL cadstep_<id>]]`) and the plan's cost, GPU and latency lists.
- `figs_guide.py` holds the guide's own diagrams; `g_section` is drawn to scale from `../arhud-cad/layout.json`.
- `[[IMG path|alt]]` embeds the CAD renders from `../arhud-cad/out/preview/` as JPEG.

Text is in `parts/` (file order is document order). Keep the document monochrome outside figures and in Helvetica
Neue throughout; after a build, `pdffonts out/guide.pdf` must list only the HelveticaNeue family.
Rerun after any change to `calc.py`, the CAD (`make.py`) or the simulator's layout (`dump_layout.mjs`).
