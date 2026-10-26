"""Render named figures (or all) to out/preview/*.png for visual QA: python3 preview.py [name ...]"""
import os, subprocess, sys
from build import CSS, HERE
from svgkit import REG
names = sys.argv[1:] or list(REG)
html = "".join(f'<figure data-name="{n}">{REG[n]().render()}</figure>' for n in names)
p = os.path.join(HERE, "out", "preview.html")
open(p, "w").write(f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body><main>{html}</main></body></html>')
subprocess.run(["node", os.path.join(HERE, "preview.js"), p, os.path.join(HERE, "out", "preview")], check=True)
