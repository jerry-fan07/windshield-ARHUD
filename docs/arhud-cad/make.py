"""Build the housing, check it against the traced light path, the windshield, the car and the printer, and export.

    ~/.venvs/arhud-cad/bin/python make.py            # build, check, export to out/ and ../arhud-sim/assets/cad/
    ~/.venvs/arhud-cad/bin/python make.py --quick    # build and check only
Refresh layout.json first (node dump_layout.mjs) whenever the simulator's geom.js or calc.py numbers change.
"""
import json
import sys
import time
from pathlib import Path

from hudcad import assembly, checks, geo as g

HERE = Path(__file__).resolve().parent
t0 = time.time()
parts = assembly.build()
print(f"built {len(parts)} parts in {time.time() - t0:.1f} s")

res = {}
res["beam"] = checks.check_beam(parts)
b = res["beam"]
print(f"beam: {b['rays']} rays (both mirror figures), {b['blocked']} blocked by the housing {b['by'] or ''}; "
      f"{b['panel']} clipped by the panel's own glass (layout)")
print("  nearest parts to the beam (mm):", {k: round(v, 1) for k, v in b["nearest"].items()})
res["envelope"] = checks.check_envelope(parts)
print("envelope:", res["envelope"])
fits, _ = checks.check_fits(parts)
res["fits"] = fits
print("fits: overlapping pairs", fits["pairs"], "| hits on simulator-drawn parts", fits["refHits"], "| mirror points inside parts", fits["mirror"])
bed = []
for p in parts:
    if p.kind == "printed":
        po = checks.print_orient(p)
        bed.append((p.id, po["size"], po["fits"]))
bad = [x for x in bed if not x[2]]
print(f"printer: {len(bed)} printed parts, {len(bad)} do not fit {g.BED}: {bad}")
res["printer"] = dict(parts=len(bed), notFitting=[x[0] for x in bad])
print(f"checks done at {time.time() - t0:.1f} s")

if "--quick" not in sys.argv:
    from hudcad.export import export_all
    clean = json.loads(json.dumps(res, default=float))
    man = export_all(parts, clean, HERE / "out", HERE.parent / "arhud-sim" / "assets" / "cad")
    print("exported:", man["summary"])
    print(f"done in {time.time() - t0:.1f} s")
