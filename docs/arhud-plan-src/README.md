# ARHUD plan: source for docs/ARHUD-PLAN.pdf

Rebuilds the PDF from the parts in `parts/`, the figures (`figs_*.py`), and the computed values (`calc.py`).

Requirements: Python 3.12 (standard library only), Node.js, poppler (`pdftotext`), and Google Chrome.

    cd docs/arhud-plan-src
    npm i puppeteer-core
    python3 build.py

The output is written to `out/plan.pdf`. Copy it to `docs/ARHUD-PLAN.pdf` to update the plan.
Set `CHROME_PATH` if Chrome is not in `/Applications`. `out/` and `node_modules/` are build artefacts and can be deleted.
Numbers quoted in the text come from `calc.py`; change them there, not in the parts.
