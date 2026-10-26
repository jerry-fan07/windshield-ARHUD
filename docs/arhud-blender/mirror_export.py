"""Export a fitted mirror for manufacture: a sag table and a mesh.

Reads freeform.json (or name=freeform_curved) and writes, into docs/arhud-blender/export/: a sag table CSV on a 1 mm
grid over the 300 x 200 mm aperture (u lateral, v in the plane of incidence, w toward the light, millimetres, the
convention optics shops quote from), the same for the plan's toroid as a reference, and an STL of the fitted
surface with a 12 mm substrate behind it (Blender's STL exporter), for a CNC or a diamond-turning quote.

Run:  /Applications/Blender.app/Contents/MacOS/Blender -b -P mirror_export.py -- [name=freeform] [step=1]
"""
import json
import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bl_common as C  # noqa: E402

ARGS = C.script_args()
NAME = C.arg(ARGS, "name", "freeform")
STEP = C.arg(ARGS, "step", 1.0, float)
OUT = os.path.join(HERE, "export")
os.makedirs(OUT, exist_ok=True)
L = C.load_layout()
with open(os.path.join(HERE, NAME + ".json")) as f:
    F = json.load(f)
W, H = L["mirror"]["W"], L["mirror"]["H"]
Rt0, Rs0 = L["mirror"]["toroid"]["Rt"], L["mirror"]["toroid"]["Rs"]


def sag_free(u, v):
    return sum(ck * u ** i * v ** j for ck, (i, j) in zip(F["coefficients"], F["terms"]))


def sag_toroid(u, v):
    inner = Rt0 - Rs0 + np.sqrt(Rs0 * Rs0 - u * u)
    return Rt0 - np.sqrt(inner * inner - v * v)


us = np.arange(-W / 2, W / 2 + 1e-9, STEP / 1000)
vs = np.arange(-H / 2, H / 2 + 1e-9, STEP / 1000)
U, V = np.meshgrid(us, vs)
for label, fn in (("sag_" + NAME, sag_free), ("sag_toroid", sag_toroid)):
    Wg = fn(U, V)
    path = os.path.join(OUT, label + ".csv")
    with open(path, "w") as f:
        f.write("# u_mm (lateral), v_mm (plane of incidence), w_mm (toward the light); mirror vertex at 0,0,0; " + ("freeform fit " + NAME if fn is sag_free else "plan toroid Rt %.1f Rs %.1f mm" % (Rt0 * 1000, Rs0 * 1000)) + "\n")
        for j in range(len(vs)):
            for i in range(len(us)):
                f.write(f"{us[i] * 1000:.1f},{vs[j] * 1000:.1f},{Wg[j, i] * 1000:.4f}\n")
    print(f"wrote {path}: {len(us)} x {len(vs)} points, sag {Wg.min() * 1000:.3f} to {Wg.max() * 1000:.3f} mm", flush=True)
# the difference between the two, to see what the freeform asks beyond the toroid
D = (sag_free(U, V) - sag_toroid(U, V)) * 1000
print(f"freeform minus toroid: {D.min():.3f} to {D.max():.3f} mm over the aperture", flush=True)
# STL: the surface with a substrate
sc = C.fresh_scene()
nu, nv = int(W * 1000 / 2), int(H * 1000 / 2)
verts, faces = [], []
for j in range(nv + 1):
    v = -H / 2 + H * j / nv
    for i in range(nu + 1):
        u = -W / 2 + W * i / nu
        verts.append((u, v, float(sag_free(u, v))))
n0 = len(verts)
back = -0.012
for j in range(nv + 1):
    v = -H / 2 + H * j / nv
    for i in range(nu + 1):
        u = -W / 2 + W * i / nu
        verts.append((u, v, back))
for j in range(nv):
    for i in range(nu):
        a = j * (nu + 1) + i
        faces.append((a, a + 1, a + nu + 2, a + nu + 1))
        b = n0 + a
        faces.append((b, b + nu + 1, b + nu + 2, b + 1))
for i in range(nu):
    faces.append((i, n0 + i, n0 + i + 1, i + 1))
    t = nv * (nu + 1) + i
    faces.append((t, t + 1, n0 + t + 1, n0 + t))
for j in range(nv):
    k = j * (nu + 1)
    faces.append((k, k + nu + 1, n0 + k + nu + 1, n0 + k))
    k = j * (nu + 1) + nu
    faces.append((k, n0 + k, n0 + k + nu + 1, k + nu + 1))
ob = C.mesh_object("mirror_" + NAME, verts, faces, None, None, smooth=True)
import bmesh
bm = bmesh.new(); bm.from_mesh(ob.data); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(ob.data); bm.free()
bpy.ops.object.select_all(action="DESELECT"); ob.select_set(True); bpy.context.view_layer.objects.active = ob
stl = os.path.join(OUT, "mirror_" + NAME + ".stl")
bpy.ops.wm.stl_export(filepath=stl, export_selected_objects=True, global_scale=1000.0)   # millimetres
print(f"wrote {stl} ({os.path.getsize(stl) // 1024} KB): the fitted surface over a 12 mm substrate, millimetres, vertex at the origin, w toward the light", flush=True)
