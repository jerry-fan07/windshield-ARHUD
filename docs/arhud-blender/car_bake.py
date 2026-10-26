"""Blender pass over the simulator's ego car.

The car in arhud-sim/js/car.js is built from primitives (boxes, extrusions, grid surfaces) with hard edges and no
indirect-light shading. This script takes the GLB that dev/export-car.html writes from that very car, and for every
static part: merges the duplicated vertices, bevels the plain boxes, tessellates large faces, shades smooth by angle,
and bakes ambient occlusion from the whole car (wheels, driver, glass and emissive parts included as occluders) into a
vertex colour layer. It exports the static parts alone as a Draco GLB that js/car-glb.js lays over the live car:
each baked mesh replaces the procedural mesh at the same path, so the geometry, mount points, cutaways and the x-ray
keep working, and the simulator falls back to the procedural car when the file is missing or stale.

Run:  /Applications/Blender.app/Contents/MacOS/Blender -b -P car_bake.py -- in=car_src.glb [out=../arhud-sim/assets/car.glb]
      [samples=48] [bevel=1] [draco=1] [aodist=1.2]
"""
import math
import os
import sys
import time

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bl_common as C  # noqa: E402

ARGS = C.script_args()
IN = C.arg(ARGS, "in", None)
OUT = C.arg(ARGS, "out", os.path.join(C.ASSETS_DIR, "car.glb"))
SAMPLES = C.arg(ARGS, "samples", 48, int)
BEVEL = C.arg(ARGS, "bevel", 1, int)
DRACO = C.arg(ARGS, "draco", 1, int)
AO_DIST = C.arg(ARGS, "aodist", 0.35, float)       # short: contact shading in creases, not a cabin-wide dimming
EDGE = C.arg(ARGS, "edge", 0.05, float)          # tessellate edges longer than this for AO resolution
if not IN or not os.path.exists(IN):
    raise SystemExit("in=<car_src.glb> is required (write it with arhud-sim/dev/export-car.html)")


def prep_mesh(ob):
    """Merge doubles, bevel plain boxes, tessellate long edges, smooth by angle. Returns (verts before, after)."""
    me = ob.data
    n0 = len(me.vertices)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.verts.ensure_lookup_table()
    dims = ob.dimensions
    small = min(dims.x, dims.y, dims.z)
    # bevel the plain boxes and extrusions (few faces, chunky): rounded boxes and surfaces are left alone
    if BEVEL and len(bm.faces) <= 14 and small > 0.015:
        w = min(0.004, 0.12 * small)
        geom = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(25)]
        if geom:
            bmesh.ops.bevel(bm, geom=geom, offset=w, offset_type="OFFSET", segments=2, profile=0.5, affect="EDGES", clamp_overlap=True)
    # tessellate: ambient occlusion lives on the vertices, so long edges need intermediate vertices
    for _ in range(3):
        long_edges = [e for e in bm.edges if e.calc_length() > EDGE]
        if not long_edges:
            break
        bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=1, use_grid_fill=True)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    # smooth by angle (Blender 4.1+), with the hard creases kept
    for p in me.polygons:
        p.use_smooth = True
    try:
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(32), keep_sharp_edges=True)
    except Exception as e:
        print("  shade_smooth_by_angle failed:", e)
    return n0, len(me.vertices)


def main():
    t0 = time.time()
    sc = C.fresh_scene()
    used_gpu = C.setup_cycles(sc, samples=SAMPLES, gpu=True, bounces=4)
    bpy.ops.import_scene.gltf(filepath=IN, merge_vertices=False, import_shading="FLAT")
    objs = [o for o in sc.objects if o.type == "MESH"]
    static = [o for o in objs if o.name.startswith("s:")]
    occl = [o for o in objs if o.name.startswith("o:")]
    other = [o for o in objs if not (o.name.startswith("s:") or o.name.startswith("o:"))]
    print(f"imported {len(objs)} meshes: {len(static)} static, {len(occl)} occluders, {len(other)} other", flush=True)
    for o in other:
        bpy.data.objects.remove(o, do_unlink=True)
    # the AO bake needs a world: a uniform one; the distance limits the occlusion search
    w = bpy.data.worlds.new("AO")
    sc.world = w
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (1, 1, 1, 1)
    w.light_settings.distance = AO_DIST
    nv0 = nv1 = 0
    for o in static:
        a, b = prep_mesh(o)
        nv0 += a
        nv1 += b
        ca = o.data.color_attributes.new(name="AO", type="BYTE_COLOR", domain="CORNER")
        o.data.color_attributes.active_color = ca
        o.data.color_attributes.render_color_index = o.data.color_attributes.find("AO")
        if not o.data.materials:
            o.data.materials.append(bpy.data.materials.new("bake"))
    print(f"prepared: {nv0} -> {nv1} vertices", flush=True)
    # bake every static object in one go (each bakes into its own active colour attribute)
    sc.cycles.bake_type = "AO"
    sc.render.bake.target = "VERTEX_COLORS"
    sc.render.bake.use_selected_to_active = False
    bpy.ops.object.select_all(action="DESELECT")
    for o in static:
        o.select_set(True)
    bpy.context.view_layer.objects.active = static[0]
    t1 = time.time()
    try:
        bpy.ops.object.bake(type="AO", target="VERTEX_COLORS")
        print(f"baked {len(static)} objects in {time.time() - t1:.0f} s", flush=True)
    except Exception as e:
        print("batch bake failed, baking one by one:", e, flush=True)
        for k, o in enumerate(static):
            bpy.ops.object.select_all(action="DESELECT")
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.bake(type="AO", target="VERTEX_COLORS")
            if k % 20 == 0:
                print(f"  {k}/{len(static)}", flush=True)
    # a gentle floor: AO of 0 would turn a vertex black with the multiply in three
    import numpy as np
    for o in static:
        ca = o.data.color_attributes["AO"]
        n = len(ca.data)
        buf = np.empty(n * 4, dtype=np.float32)
        ca.data.foreach_get("color", buf)
        buf = buf.reshape(n, 4)
        buf[:, :3] = 0.35 + 0.65 * np.clip(buf[:, :3], 0, 1) ** 0.8
        ca.data.foreach_set("color", buf.ravel())
    for o in occl:
        bpy.data.objects.remove(o, do_unlink=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_apply=True, export_materials="NONE",
                              export_vertex_color="ACTIVE", export_all_vertex_colors=False, export_active_vertex_color_when_no_material=True,
                              export_texcoords=False, export_normals=True, export_extras=True, export_yup=True,
                              export_draco_mesh_compression_enable=bool(DRACO), export_draco_mesh_compression_level=6,
                              export_draco_position_quantization=14, export_draco_normal_quantization=10, export_draco_color_quantization=8)
    import base64
    with open(OUT + ".txt", "w") as f:            # the artifact host serves text but not .glb; js/car-glb.js decodes this
        f.write(base64.b64encode(open(OUT, "rb").read()).decode())
    print(f"wrote {OUT}: {os.path.getsize(OUT) // 1024} KB (+ base64 .txt), {len(static)} parts, {time.time() - t0:.0f} s, gpu={used_gpu}", flush=True)


if __name__ == "__main__":
    main()
