# ARHUD plan, HUD-only TFT LCD edition: source for docs/ARHUD-PLAN-TFT.pdf

Rebuilds the PDF from the parts in `parts/`, the figures (`figs_*.py`), and the computed values (`calc.py`).
This is a parallel plan to `docs/ARHUD-PLAN.pdf` (the self-driving, laser-DLP edition built from `../arhud-plan-src/`), not a revision of it.

Requirements: Python 3.12 (standard library only), Node.js, poppler (`pdftotext`), and Google Chrome.

    cd docs/arhud-plan-tft-src
    npm i puppeteer-core      # or keep the node_modules symlink to ../arhud-plan-src/node_modules
    python3 build.py

The output is written to `out/plan.pdf`. Copy it to `docs/ARHUD-PLAN-TFT.pdf` to update the plan.
`python3 spec.py` writes the condensed, agent-readable specification to `docs/ARHUD-PLAN-TFT-SPEC.md` from the same numbers; regenerate it whenever `calc.py` changes.
Set `CHROME_PATH` if Chrome is not in `/Applications`. `out/` and `node_modules/` are build artefacts and can be deleted.
Numbers quoted in the text come from `calc.py`; change them there, not in the parts. Values marked ASSUMED in `calc.py` are design assumptions the text tags.
