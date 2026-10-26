"""Raster figures: the Cycles renders written by blender/*.py into out/png/."""
import os
from svgkit import REG

HERE = os.path.dirname(os.path.abspath(__file__))

class Img:
    def __init__(self, src, alt):
        self.src, self.alt = src, alt
    def render(self):
        path = os.path.join(HERE, "out", "png", self.src)
        if not os.path.exists(path):
            raise SystemExit(f"missing render {path}: run the Blender scripts in blender/")
        return f'<img src="png/{self.src}" alt="{self.alt}">'

def img(name, src, alt):
    REG[name] = lambda: Img(src, alt)

img("thr_pinhole", "through_pinhole.png", "Cycles render through the grooved lens with a pinhole camera at the eye point")
img("thr_eye", "through_eye.png", "Cycles render through the grooved lens with a 4 mm pupil focused at the virtual image")
img("thr_pinhole_edge", "through_pinhole_edge.png", "Enlarged left edge, pinhole camera")
img("thr_eye_edge", "through_eye_edge.png", "Enlarged left edge, 4 mm pupil")
img("thr_pinhole_centre", "through_pinhole_centre.png", "Enlarged centre, pinhole camera")
img("thr_eye_centre", "through_eye_centre.png", "Enlarged centre, 4 mm pupil")
img("thr_ghost", "through_ghosts.png", "The eye render with exposure raised 16 times to show the reflection ghosts")
img("thr_flat_pinhole_centre", "through_pinhole_flat_centre.png", "Enlarged centre through a flat-facet lens, pinhole camera")
img("thr_flat_eye_centre", "through_eye_flat_centre.png", "Enlarged centre through a flat-facet lens, 4 mm pupil")
