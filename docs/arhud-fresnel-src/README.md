# The Fresnel Stage: source for docs/ARHUD-FRESNEL-STAGE.pdf

An optics explainer for Stage 1 of the TFT LCD plan (`docs/ARHUD-PLAN-TFT.pdf`, section 5): the 300 mm Fresnel
magnifier, the combiner, and what the eye sees, with every number traced through a model of the real lens.

Requirements: Python 3.12 with numpy, Node.js with puppeteer-core (`node_modules` is a symlink to
`../arhud-plan-src/node_modules`), poppler (`pdftotext`), Google Chrome, and Blender 5.2 for the renders.

    cd docs/arhud-fresnel-src
    /Applications/Blender.app/Contents/MacOS/Blender -b --python blender/through_lens.py -- samples=384               # curved facets (main)
    /Applications/Blender.app/Contents/MacOS/Blender -b --python blender/through_lens.py -- samples=384 facets=flat    # flat-facet comparison
    /Applications/Blender.app/Contents/MacOS/Blender -b --python blender/measure_ghosts.py                            # ghost levels -> renders/ghosts.json
    python3 build.py                     # out/fresnel.pdf (two passes for the contents page numbers)
    cp out/fresnel.pdf ../ARHUD-FRESNEL-STAGE.pdf

Files:
- `optics.py`: the lens model (facet slopes solved for f = 300 mm, PMMA dispersion) and the sequential ray tracer; `python3 optics.py` runs the on-axis self-check against the thin-lens equation.
- `teeth.py`: groove-level 2-D trace through the real tooth profile (draft walls, total internal reflection).
- `calc.py`: every number in the text (`{{key}}` in `parts/`); imports the plan's Stage 1 numbers from `../arhud-plan-tft-src/calc.py`. Values marked ASSUMED are tagged in the text.
- `figs_a.py` to `figs_d.py`: the SVG figures; `figs_e.py`: the Cycles renders in `out/png/`. Figures are numbered automatically by order of first `[[FIG name]]`; `[[N name]]` gives a figure's number.
- `blender/testframe.html`: the HUD test frame (render with `node blender/shot.js`).
- `preview.py name ...`: screenshots single figures to `out/preview/` for checking; `contact.py`: page contact sheets.
