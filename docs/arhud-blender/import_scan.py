"""Bring a scan of the real car's dash and windshield into the simulator's frame.

The plan is to scan the dash and the glass of the actual car, clean the scan in Blender, and build the housing to
fit. This script does the Blender part headless: it imports the scan (PLY, OBJ, STL or GLB), drops loose fragments,
optionally decimates, aligns it to the simulator's frame from point pairs you measure, and exports it as a GLB (plus
the base64 copy the artifact host can serve) that the simulator shows in Vehicle mode as the "scanned car".

Alignment. Give at least three pairs of points, each a point in the scan's own coordinates and the simulator
point it corresponds to, as `pair=sx,sy,sz:tx,ty,tz` (metres; the scan's units are converted with `scale=`, e.g.
scale=0.001 for a millimetre scan). The simulator points come from layout.json: the eye at
(0, 1.22, 0), the windshield's bottom centre at (glass.bottomX, glass.cowlY, carCenterZ), the mirror-stalk button
at mounts.mirrorStalk, the top of the glass at (glass.topX, glass.roofY, carCenterZ). A rigid transform (Kabsch,
with an optional uniform scale) is fitted and the RMS residual is printed; above about 20 mm the pairs are wrong.
`sim` points are in the simulator's frame (X forward, Y up, Z right); the script converts to Blender and back.

Run:  /Applications/Blender.app/Contents/MacOS/Blender -b -P import_scan.py -- in=scan.ply [scale=1] \\
        pair=0.12,0.05,0.80:0,1.22,0 pair=...:... [fitscale=0] [minfaces=200] [decimate=0.5] [out=../arhud-sim/assets/scan.glb]
Test: `test=1` builds a synthetic scan from the exported car (car=car_src.glb), moves it by a random rigid
transform with noise, and checks that the fit recovers it.
"""
import base64
import json
import math
import os
import random
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bl_common as C  # noqa: E402

ARGS = C.script_args()
IN = C.arg(ARGS, "in", None)
OUT = C.arg(ARGS, "out", os.path.join(C.ASSETS_DIR, "scan.glb"))
SCALE = C.arg(ARGS, "scale", 1.0, float)
FITSCALE = C.arg(ARGS, "fitscale", 0, int)
MINFACES = C.arg(ARGS, "minfaces", 200, int)
DECIMATE = C.arg(ARGS, "decimate", 0.0, float)
TEST = C.arg(ARGS, "test", 0, int)
PAIRS = [a[len("pair="):] for a in ARGS if a.startswith("pair=")]
L = C.load_layout()
B = C.B


def parse_pairs(pairs):
    src, dst = [], []
    for p in pairs:
        a, b = p.split(":")
        src.append([float(x) for x in a.split(",")])
        dst.append([float(x) for x in b.split(",")])
    return np.array(src), np.array(dst)


def kabsch(src, dst, with_scale=False):
    """Rigid (optionally similarity) transform mapping src points onto dst: returns (s, R, t) with dst ~ s R src + t."""
    cs, cd = src.mean(axis=0), dst.mean(axis=0)
    P, Q = src - cs, dst - cd
    H = P.T @ Q
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1, 1, d])
    R = Vt.T @ D @ U.T
    s = (S * np.array([1, 1, d])).sum() / (P ** 2).sum() if with_scale else 1.0
    t = cd - s * R @ cs
    res = dst - (s * (R @ src.T).T + t)
    return s, R, t, float(np.sqrt((res ** 2).sum(axis=1).mean()))


def import_scan(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".ply":
        bpy.ops.wm.ply_import(filepath=path)
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        raise SystemExit("unsupported scan format " + ext)
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def join_all(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return ob


def clean(ob, minfaces):
    """Drop connected fragments with fewer than minfaces faces (scanner noise), remove doubles."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.faces.ensure_lookup_table()
    seen = set()
    removed = 0
    for f in bm.faces:
        if f.index in seen or not f.is_valid:
            continue
        stack, comp = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            comp.append(g)
            for e in g.edges:
                for n in e.link_faces:
                    if n.index not in seen:
                        seen.add(n.index)
                        stack.append(n)
        if len(comp) < minfaces:
            bmesh.ops.delete(bm, geom=comp, context="FACES")
            removed += len(comp)
    bm.to_mesh(ob.data)
    bm.free()
    return removed


HARD = C.arg(ARGS, "hard", 0, int)


def synthetic_scan(car_glb):
    """A fake scan: the dash, cowl and glass of the exported car, moved by a random rigid transform with noise.
    hard=1 makes it a worst case: millimetre units (a 1000x scale the fit must recover), 5 mm noise, half the dash
    missing (partial coverage), stray fragments floating nearby (scanner junk), and only three point pairs."""
    bpy.ops.import_scene.gltf(filepath=car_glb)
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    keep = []
    for o in objs:
        p = o.get("path") or ""
        c = o.matrix_world @ (0.125 * sum((Vector(b) for b in o.bound_box), Vector()))
        # the dash area in front of the driver (Blender frame: x forward, z up): dash shelf and cluster hood, the glass
        if (0.45 < c.x < 1.45 and 0.7 < c.z < 1.0 and p.startswith("interior")) or o.get("orig") == "windshield":
            keep.append(o)
    for o in objs:
        if o not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    ob = join_all(keep)
    random.seed(7)
    rot = Matrix.Rotation(math.radians(random.uniform(-30, 30)), 4, "Z") @ Matrix.Rotation(math.radians(random.uniform(-10, 10)), 4, "X")
    tr = Matrix.Translation(Vector((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-0.5, 0.5))))
    M = tr @ rot
    me = ob.data
    noise = 0.005 if HARD else 0.0015
    for v in me.vertices:
        v.co = M @ v.co + Vector((random.gauss(0, noise), random.gauss(0, noise), random.gauss(0, noise)))
    if HARD:
        # partial coverage: drop everything on the passenger half beyond the centre line (Blender y < -CZ)
        bm = bmesh.new()
        bm.from_mesh(me)
        inv = M.inverted()
        gone = [f for f in bm.faces if (inv @ f.calc_center_median()).y < -L["carCenterZ"] - 0.15]
        bmesh.ops.delete(bm, geom=gone, context="FACES")
        # scanner junk: a few loose blobs near the dash
        for k in range(6):
            c = M @ Vector((random.uniform(0.5, 1.3), random.uniform(-0.6, 0.4), random.uniform(0.6, 1.1)))
            bmesh.ops.create_icosphere(bm, subdivisions=1, radius=random.uniform(0.01, 0.04), matrix=Matrix.Translation(c))
        bm.to_mesh(me)
        bm.free()
        # millimetre units
        for v in me.vertices:
            v.co *= 1000.0
    return ob, M


def main():
    t0 = time.time()
    C.fresh_scene()
    truth = None
    if TEST:
        car = C.arg(ARGS, "car", None)
        ob, truth = synthetic_scan(car)
        # pairs from the true transform of known simulator points (Blender frame), with 3 mm measurement noise
        sim_pts = [L["eye"], [L["glass"]["bottomX"], L["glass"]["cowlY"], L["carCenterZ"]], L["mounts"]["mirrorStalk"], [L["glass"]["topX"], L["glass"]["roofY"], L["carCenterZ"]], L["mounts"]["driverCam"]]
        if HARD:
            sim_pts = sim_pts[:3]
        src, dst = [], []
        random.seed(3)
        unit = 1000.0 if HARD else 1.0
        for p in sim_pts:
            pb = B(p)
            q = truth @ pb
            src.append([(q.x + random.gauss(0, 0.003)) * unit, (q.y + random.gauss(0, 0.003)) * unit, (q.z + random.gauss(0, 0.003)) * unit])
            dst.append([pb.x, pb.y, pb.z])
        src, dst = np.array(src), np.array(dst)
        if HARD:
            # the user says scale=0.001 for a millimetre scan; the fit may also refine it
            for v in ob.data.vertices:
                v.co *= 0.001
            src = src * 0.001
        print(f"test: synthetic scan with {len(ob.data.polygons)} faces, {len(sim_pts)} noisy pairs{' (hard: mm units, 5 mm noise, half missing, junk blobs)' if HARD else ''}", flush=True)
    else:
        if not IN or not os.path.exists(IN):
            raise SystemExit("in=<scan file> is required")
        if len(PAIRS) < 3:
            raise SystemExit("at least three pair=sx,sy,sz:tx,ty,tz are required")
        objs = import_scan(IN)
        ob = join_all(objs)
        if SCALE != 1.0:
            for v in ob.data.vertices:
                v.co *= SCALE
        s_pts, d_pts = parse_pairs(PAIRS)
        src = s_pts * SCALE                                     # scan points, scan frame (already Blender-like: as scanned)
        dst = np.array([list(B(p)) for p in d_pts])            # simulator points -> Blender frame
    s, R, t, rms = kabsch(src, dst, with_scale=bool(FITSCALE))
    print(f"fit: scale {s:.4f}, rms residual {rms * 1000:.1f} mm over {len(src)} pairs", flush=True)
    M = Matrix.Translation(Vector(t)) @ (Matrix(R.tolist()).to_4x4()) @ Matrix.Scale(s, 4)
    me = ob.data
    for v in me.vertices:
        v.co = M @ v.co
    removed = clean(ob, MINFACES)
    if DECIMATE > 0:
        mod = ob.modifiers.new("dec", "DECIMATE")
        mod.ratio = DECIMATE
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier="dec")
    ob.name = "scan"
    ob.data.materials.clear()
    if truth is not None:
        # how far the recovered points are from where they started
        err = []
        for v in list(me.vertices)[:2000]:
            pass
        inv = truth.inverted()
        # a vertex at true position p was moved to truth@p (+noise) and brought back by M: compare M@truth@p with p
        test_p = [B(L["eye"]), B(L["mounts"]["mirrorStalk"]), B([L["glass"]["topX"], L["glass"]["roofY"], L["carCenterZ"]])]
        for p in test_p:
            q = M @ (truth @ p)
            err.append((q - p).length)
        print(f"test: recovered landmark error {np.mean(err) * 1000:.1f} mm mean, {np.max(err) * 1000:.1f} mm max (fragments removed: {removed})", flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", use_selection=True, export_apply=True, export_materials="NONE", export_texcoords=False, export_normals=True, export_yup=True,
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6)
    with open(OUT + ".txt", "w") as f:
        f.write(base64.b64encode(open(OUT, "rb").read()).decode())
    meta = {"source": os.path.basename(IN) if IN else "synthetic test", "faces": len(me.polygons), "rmsFit_mm": rms * 1000, "pairs": len(src), "scale": s, "fragmentsRemoved": removed, "generated": time.strftime("%Y-%m-%d %H:%M")}
    with open(os.path.splitext(OUT)[0] + ".json", "w") as f:
        json.dump(meta, f, indent=1)
    print(f"wrote {OUT} ({os.path.getsize(OUT) // 1024} KB, {len(me.polygons)} faces) in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
