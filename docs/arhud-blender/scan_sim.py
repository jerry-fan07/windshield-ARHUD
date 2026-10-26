"""A simulated handheld scanner inside the car, to test the scan workflow on scanner-like data.

Real scans of a dash are not a clean mesh: they are overlapping sheets from several sensor poses, with range noise,
dropouts, holes behind the wheel and the stalk, no returns from glass, seams where sheets overlap, and the scanner's
own units and frame. This script makes such a scan from the exported car: it places sensor poses on the driver's
seat and the passenger's, casts a depth image from each (a structured-light-like grid of rays), adds range noise and
dropouts, drops hits on glass and emissive surfaces, triangulates each depth image where neighbouring samples are
close, merges the sheets, moves the whole thing by an unknown rigid transform into millimetres, and writes a PLY.
Landmarks a user would measure in the scan (the cowl's bottom centre at the glass, the mirror-stalk button, the top
of the steering-column shroud) are written beside it in the scanner's frame, so import_scan.py can be run on the
result exactly as it would be on a real scan.

Run:  /Applications/Blender.app/Contents/MacOS/Blender -b -P scan_sim.py -- car=/tmp/car_src.glb [out=/tmp/scan_sim.ply]
      [res=160] [noise=0.002] [dropout=0.05]
"""
import json
import math
import os
import random
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bl_common as C  # noqa: E402

ARGS = C.script_args()
CAR = C.arg(ARGS, "car", None)
OUT = C.arg(ARGS, "out", os.path.join(HERE, "..", "arhud-sim", "assets", "scan_sim.ply"))
RES = C.arg(ARGS, "res", 160, int)
NOISE = C.arg(ARGS, "noise", 0.002, float)
DROPOUT = C.arg(ARGS, "dropout", 0.05, float)
FOV = 62.0
L = C.load_layout()
B = C.B
if not CAR or not os.path.exists(CAR):
    raise SystemExit("car=<car_src.glb> is required")


def is_glass_or_emissive(ob):
    for m in ob.data.materials:
        if not m or not m.node_tree:
            continue
        b = m.node_tree.nodes.get("Principled BSDF")
        if not b:
            continue
        if b.inputs["Alpha"].default_value < 0.6 or b.inputs["Transmission Weight"].default_value > 0.5:
            return True
        if b.inputs["Emission Strength"].default_value > 0 and max(b.inputs["Emission Color"].default_value[:3]) > 0.1 and not b.inputs["Base Color"].is_linked:
            return True
    return False


def main():
    t0 = time.time()
    sc = C.fresh_scene()
    bpy.ops.import_scene.gltf(filepath=CAR, merge_vertices=False, import_shading="FLAT")
    objs = [o for o in sc.objects if o.type == "MESH"]
    # a scanner sees no glass; the driver's head is not in the car during a scan
    eye = B(L["eye"])
    for o in objs:
        c = o.matrix_world @ (0.125 * sum((Vector(b) for b in o.bound_box), Vector()))
        if is_glass_or_emissive(o) or o.get("orig") == "windshield" or (c - eye).length < 0.16:
            bpy.data.objects.remove(o, do_unlink=True)
    dg = bpy.context.evaluated_depsgraph_get()
    random.seed(11)
    # sensor poses: from the driver's seat and the passenger's, aimed at the dash, the cowl and the pillar
    cz = L["carCenterZ"]
    poses = [
        ([0.15, 1.10, 0.00], [1.2, 0.85, 0.0]), ([0.10, 1.05, 0.25], [1.3, 0.80, 0.5]), ([0.25, 1.20, -0.25], [1.1, 1.0, 0.1]),
        ([0.15, 1.10, 2 * cz], [1.2, 0.85, cz]), ([0.0, 1.25, cz], [1.3, 1.25, cz]), ([0.35, 0.95, 0.15], [1.0, 0.6, 0.0]),
    ]
    sheets = []
    total_rays = 0
    for pi, (pos, aim) in enumerate(poses):
        o = B(pos)
        f = (B(aim) - o).normalized()
        r = f.cross(Vector((0, 0, 1))).normalized()
        u = r.cross(f).normalized()
        t = math.tan(math.radians(FOV / 2))
        h = int(RES * 3 / 4)
        pts = np.full((h, RES, 3), np.nan)
        for j in range(h):
            for i in range(RES):
                d = (f + r * ((i + 0.5) / RES * 2 - 1) * t + u * ((h - j - 0.5) / h * 2 - 1) * t * 0.75).normalized()
                hit, loc, nrm, idx, ob, mw = sc.ray_cast(dg, o, d)
                total_rays += 1
                if not hit or random.random() < DROPOUT:
                    continue
                dist = (loc - o).length + random.gauss(0, NOISE) * (1 + dist_factor(loc, o))
                p = o + d * dist
                pts[j, i] = (p.x, p.y, p.z)
        sheets.append(pts)
        print(f"  pose {pi}: {int(np.isfinite(pts[..., 0]).sum())} returns", flush=True)
    # triangulate each sheet where neighbours are close (no bridging across depth jumps), merge
    verts, faces = [], []
    for pts in sheets:
        h, w = pts.shape[:2]
        index = -np.ones((h, w), dtype=int)
        for j in range(h):
            for i in range(w):
                if np.isfinite(pts[j, i, 0]):
                    index[j, i] = len(verts)
                    verts.append(tuple(pts[j, i]))
        for j in range(h - 1):
            for i in range(w - 1):
                q = [index[j, i], index[j, i + 1], index[j + 1, i + 1], index[j + 1, i]]
                if min(q) < 0:
                    continue
                P = [np.array(verts[k]) for k in q]
                if max(np.linalg.norm(P[k] - P[(k + 1) % 4]) for k in range(4)) > 0.03:
                    continue
                faces.append((q[0], q[1], q[2]))
                faces.append((q[0], q[2], q[3]))
    # the scanner's own frame: an unknown rigid move, millimetres
    rot = Matrix.Rotation(math.radians(random.uniform(-40, 40)), 4, "Z") @ Matrix.Rotation(math.radians(random.uniform(-12, 12)), 4, "X") @ Matrix.Rotation(math.radians(random.uniform(-8, 8)), 4, "Y")
    tr = Matrix.Translation(Vector((random.uniform(-2, 2), random.uniform(-2, 2), random.uniform(-1, 1))))
    M = tr @ rot
    V = np.array([list(M @ Vector(v)) for v in verts]) * 1000.0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("ply\nformat ascii 1.0\ncomment simulated handheld scan of the dash, millimetres, scanner frame\n")
        f.write(f"element vertex {len(V)}\nproperty float x\nproperty float y\nproperty float z\n")
        f.write(f"element face {len(faces)}\nproperty list uchar int vertex_indices\nend_header\n")
        for v in V:
            f.write(f"{v[0]:.2f} {v[1]:.2f} {v[2]:.2f}\n")
        for a, b, c in faces:
            f.write(f"3 {a} {b} {c}\n")
    # landmarks the user would measure in the scan (scanner frame, mm), with a few mm of measuring error, and the
    # simulator points they correspond to
    g = L["glass"]
    landmarks = {
        "cowlBottomCentre": [g["bottomX"], g["cowlY"], cz],
        "mirrorStalkButton": L["mounts"]["mirrorStalk"],
        "columnShroudTop": [L["mounts"]["driverCam"][0], L["mounts"]["driverCam"][1] + 0.0425, L["mounts"]["driverCam"][2]],
        "gnssAntennaSpot": L["mounts"]["gnss"],
    }
    pairs = []
    for name, p in landmarks.items():
        q = M @ B(p)
        pairs.append({"name": name, "scan_mm": [round((q.x + random.gauss(0, 0.003)) * 1000, 1), round((q.y + random.gauss(0, 0.003)) * 1000, 1), round((q.z + random.gauss(0, 0.003)) * 1000, 1)], "sim_m": p})
    meta = {"generated": time.strftime("%Y-%m-%d %H:%M"), "poses": len(poses), "rays": total_rays, "vertices": len(V), "faces": len(faces),
            "noise_m": NOISE, "dropout": DROPOUT, "truth": [list(r) for r in M], "pairs": pairs,
            "note": "scanner frame is Blender-like (x forward, y left, z up) moved by an unknown rigid transform; coordinates in millimetres"}
    with open(os.path.splitext(OUT)[0] + ".json", "w") as f:
        json.dump(meta, f, indent=1)
    print(f"wrote {OUT}: {len(V)} vertices, {len(faces)} faces from {len(poses)} poses in {time.time() - t0:.0f} s", flush=True)
    print("pairs for import_scan.py: " + " ".join(f"pair={p['scan_mm'][0]},{p['scan_mm'][1]},{p['scan_mm'][2]}:{p['sim_m'][0]},{p['sim_m'][1]},{p['sim_m'][2]}" for p in pairs), flush=True)


def dist_factor(loc, o):
    """Range noise grows with distance, as it does for structured-light scanners."""
    return (loc - o).length


if __name__ == "__main__":
    main()
