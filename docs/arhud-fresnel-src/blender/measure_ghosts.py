"""Measure ghost brightness in the eye render (EXR, linear): median in small boxes clear of the real graphics."""
import os, numpy as np, bpy
HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1900, 900
def load(ch):
    im = bpy.data.images.load(os.path.join(HERE, "renders", f"eye_{ch}.exr"))
    px = np.empty(W * H * 4, np.float32); im.pixels.foreach_get(px)
    return px.reshape(H, W, 4)[::-1, :, 0]
L = 0.2126 * load("R") + 0.7152 * load("G") + 0.0722 * load("B")
med = lambda x0, x1, y0, y1: float(np.median(L[y0:y1, x0:x1]))
white = float(np.percentile(L[430:850, 560:1340], 99.5))
rib = med(900, 1000, 650, 780)
print(f"white line {white:.3f}  ribbon {rib:.4f}")
import json
res = {}
for name, box in (("black reference", (700, 760, 250, 330)), ("lane ghost UL", (560, 600, 80, 120)), ("lane ghost UL2", (640, 700, 150, 190)),
                  ("ribbon ghost", (880, 930, 100, 160)), ("ribbon ghost2", (970, 1020, 100, 160)),
                  ("blob BL", (150, 200, 640, 690)), ("blob BL2", (60, 100, 700, 760)), ("blob BR", (1700, 1750, 640, 690))):
    v = med(*box)
    print(f"{name}: {v:.5f} = {v/white*100:.2f}% of white, {v/rib*100:.1f}% of ribbon")
    res[name] = dict(lin=v, of_white=v / white, of_ribbon=v / rib)
json.dump(dict(white=white, ribbon=rib, regions=res), open(os.path.join(HERE, "renders", "ghosts.json"), "w"), indent=1)
