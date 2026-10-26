"""A car body modelled from scratch in Blender, to the simulator's dimensions.

The procedural car's exterior is flat extrusions and grid surfaces. This script lofts a sedan shell as a
subdivision-surface cage from the numbers in arhud-sim/js/car.js and layout.json: the side silhouette (sill, door
bulge, shoulder, belt line), the hood, the planar windshield on the traced glass plane, the A-pillars, the
tumblehome of the side glass, the roof, the rear glass and the deck, with wheel arches cut and ambient occlusion
baked with the rest of the car as occluders. It exports assets/car_body.glb (+ base64) as two halves, left and
right of the car's centre line, so the Vehicle mode's side cutaways still work. js/car-glb.js lays the halves over the
procedural shell parts listed in their extras and borrows the procedural paint and glass materials, so the x-ray and
the cutaways behave as before. The windshield faces are left out: the procedural glass is the optical surface the
trace uses and stays in place, frit and all.

Run:  /Applications/Blender.app/Contents/MacOS/Blender -b -P car_body.py -- car=/tmp/car_src.glb [out=../arhud-sim/assets/car_body.glb]
      [preview=1] [samples=48] [subdiv=2]
"""
import base64
import json
import math
import os
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
CAR = C.arg(ARGS, "car", None)
OUT = C.arg(ARGS, "out", os.path.join(C.ASSETS_DIR, "car_body.glb"))
PREVIEW = C.arg(ARGS, "preview", 1, int)
SAMPLES = C.arg(ARGS, "samples", 48, int)
SUBDIV = C.arg(ARGS, "subdiv", 2, int)
L = C.load_layout()
B = C.B

# ---- the car's numbers (simulator frame: X forward, Y up, Z right; Z measured from the centre line) ------------
CZ = L["carCenterZ"]
HW = 0.905
FRONT_AXLE, REAR_AXLE, ARCH_R, TRACK = 1.55, -1.30, 0.39, 0.80
COWL_X, COWL_Y, TOP_X, ROOF_Y_GLASS = L["glass"]["bottomX"], L["glass"]["cowlY"], L["glass"]["topX"], L["glass"]["roofY"]
RAKE = math.radians(L["rakeDeg"])
WS_LS = (ROOF_Y_GLASS - COWL_Y) / math.sin(RAKE)
ROOF_X0, ROOF_X1 = TOP_X - 0.005, -0.98


def belt_y(x):
    """The shoulder / belt line from car.js's side outline."""
    pts = [(2.31, 0.70), (2.27, 0.765), (1.90, 0.785), (1.50, 0.80), (1.40, 0.81), (1.25, 0.92), (1.0, 0.94), (-0.40, 0.97), (-1.30, 0.995), (-1.75, 1.0), (-2.20, 0.985), (-2.29, 0.93)]
    return np.interp(-x, [-p[0] for p in pts], [p[1] for p in pts])


def floor_y(x):
    return 0.30 if x < -2.2 or x > 2.2 else 0.22


def hood_y(x):
    u = (x - 1.50) / 0.83
    return 0.80 - 0.04 * u - 0.03 * u ** 6


def roof_y(x):
    return 1.43 - 0.042 * ((x + 0.35) / 0.645) ** 2 if x >= -0.35 else 1.43 - 0.022 * ((x + 0.35) / 0.63) ** 2


def ws_y(x):
    return COWL_Y + (COWL_X - x) * math.tan(RAKE)


def ws_half(x):
    a = (ws_y(x) - COWL_Y) / math.sin(RAKE)
    return 0.765 - 0.115 * (a / WS_LS)


def tumble_z(y):
    return 0.90 - (min(max(y, 0.9), 1.45) - 0.95) * (0.25 / 0.43)


def roof_half(x):
    return 0.655 - 0.015 * (ROOF_X0 - x) / (ROOF_X0 - ROOF_X1)


def section(x):
    """Half cross-section at station x, 12 points from the underside centre to the roof centre: (y, z)."""
    fy, by = floor_y(x), belt_y(x)
    sill = HW - 0.02
    pts = [(fy, 0.0), (fy, sill - 0.12), (fy + 0.08, sill), (0.55, sill + 0.025), (by - 0.09, sill + 0.01), (by, sill - 0.02)]
    if x >= COWL_X:                                   # hood and nose: the top is the hood surface
        top = hood_y(x) if x < 2.27 else min(hood_y(x), 0.765 - (x - 2.27) * 0.8)
        pts += [(by + 0.015, sill - 0.05), (top, 0.80), (top + 0.01, 0.6), (top + 0.02, 0.35), (top + 0.025, 0.0)]
    elif x >= ROOF_X0:                                # windshield: planar glass between the A-pillars
        y, hw = ws_y(x), ws_half(x)
        pts += [(by + 0.03, sill - 0.06), (y - 0.025, hw + 0.045), (y, hw), (y, hw * 0.5), (y, 0.0)]
    elif x >= ROOF_X1:                                # greenhouse: tumblehome side glass, roof
        ry = roof_y(x)
        mid = (by + ry) / 2
        pts += [(by + 0.02, tumble_z(by + 0.02)), (mid, tumble_z(mid)), (ry - 0.035, tumble_z(ry - 0.035)), (ry, roof_half(x) - 0.08), (ry + 0.004, 0.0)]
    elif x >= -1.73:                                  # rear glass and sail panels
        t = (ROOF_X1 - x) / (ROOF_X1 + 1.73)
        ry = roof_y(ROOF_X1) * (1 - t) + 1.0 * t
        hw = 0.63 * (1 - t) + 0.80 * t
        pts += [(by + 0.02, tumble_z(by + 0.02)), ((by + ry) / 2, (tumble_z(by + 0.02) + hw) / 2), (ry - 0.02, hw), (ry, hw * 0.5), (ry + 0.004, 0.0)]
    else:                                             # deck and tail
        top = 1.0 - 0.015 * (-1.73 - x) / 0.56 - 0.02 * ((-1.73 - x) / 0.56) ** 5
        if x < -2.25:
            top = min(top, 0.93)
        pts += [(by + 0.01, sill - 0.04), (top, 0.80), (top + 0.01, 0.6), (top + 0.02, 0.3), (top + 0.025, 0.0)]
    return pts


STATIONS = [2.34, 2.31, 2.27, 2.10, 1.90, 1.70, 1.50, 1.41, 1.30, 1.15, 1.00, 0.85, 0.70, 0.55, 0.40, 0.31, 0.15, -0.10, -0.30, -0.40, -0.47, -0.60, -0.85, -0.98, -1.15, -1.35, -1.55, -1.73, -1.90, -2.10, -2.25, -2.29, -2.31]


def loft():
    """Quad grid of the half body in the simulator frame, with per-face material slots and glass tags."""
    secs = [section(x) for x in STATIONS]
    n = len(secs[0])
    verts, faces, mats, tags = [], [], [], []
    for x, s in zip(STATIONS, secs):
        for (y, z) in s:
            verts.append((x, y, z))
    for i in range(len(STATIONS) - 1):
        x0, x1 = STATIONS[i], STATIONS[i + 1]
        xm = (x0 + x1) / 2
        for j in range(n - 1):
            a = i * n + j
            faces.append((a, a + n, a + n + 1, a + 1))
            # material: 0 paint, 1 side glass, 2 rear glass, 3 windshield (left out later), 4 black
            m = 0
            if ROOF_X0 <= xm < COWL_X and j >= 8:
                m = 3
            elif ROOF_X1 <= xm < ROOF_X0 and j in (6, 7) and -0.9 < xm < 0.28:
                m = 4 if -0.47 <= xm <= -0.40 else 1          # the B-pillar is a black strip in the glass
            elif -1.73 <= xm < ROOF_X1 and j in (6, 7, 8):
                m = 2
            mats.append(m)
    return verts, faces, mats


def main():
    t0 = time.time()
    sc = C.fresh_scene()
    used_gpu = C.setup_cycles(sc, samples=SAMPLES, gpu=True, bounces=4)
    verts, faces, mats = loft()
    me = bpy.data.meshes.new("shell")
    me.from_pydata([tuple(B(v)) for v in verts], [], faces)
    me.update()
    names = ["paint", "sideGlass", "rearGlass", "windshield", "black"]
    for nm in names:
        m = bpy.data.materials.new(nm)
        me.materials.append(m)
    for p, m in zip(me.polygons, mats):
        p.material_index = m
        p.use_smooth = True
    ob = bpy.data.objects.new("shell", me)
    sc.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    # creases: the belt line and the glass edges stay crisp under subdivision; the windshield plane stays flat
    bm = bmesh.new()
    bm.from_mesh(me)
    cl = bm.edges.layers.float.get("crease_edge") or bm.edges.layers.float.new("crease_edge")
    n = len(section(0))
    for e in bm.edges:
        js = sorted(v.index % n for v in e.verts)
        xs = [v.co.x for v in e.verts]
        along = js[0] == js[1]                        # edge runs between stations
        if along and js[0] in (5, 7):                 # belt line, glass edge
            e[cl] = 0.8
        if along and js[0] in (8, 9, 10) and all(ROOF_X0 - 1e-6 <= x <= COWL_X + 1e-6 for x in xs):
            e[cl] = 1.0                               # windshield stays planar
        if not along and js == (7, 8) and all(ROOF_X0 - 1e-6 <= x <= COWL_X + 1e-6 for x in xs):
            e[cl] = 1.0
    bm.to_mesh(me)
    bm.free()
    # mirror about the centre line (Blender y = -CZ), subdivide, apply
    piv = bpy.data.objects.new("centre", None)
    piv.location = (0, -CZ, 0)
    sc.collection.objects.link(piv)
    mod = ob.modifiers.new("mirror", "MIRROR")
    mod.use_axis = (False, True, False)
    mod.mirror_object = piv
    mod.use_clip = True
    mod.merge_threshold = 1e-4
    sub = ob.modifiers.new("subsurf", "SUBSURF")
    sub.levels = SUBDIV
    sub.render_levels = SUBDIV
    sub.use_creases = True
    bpy.ops.object.modifier_apply(modifier="mirror")
    bpy.ops.object.modifier_apply(modifier="subsurf")
    # wheel arches
    for x in (FRONT_AXLE, REAR_AXLE):
        bpy.ops.mesh.primitive_cylinder_add(radius=ARCH_R, depth=2.6, location=B([x, 0.33, 0]))
        cyl = bpy.context.object
        cyl.rotation_euler = (math.radians(90), 0, 0)
        bo = ob.modifiers.new("arch", "BOOLEAN")
        bo.operation = "DIFFERENCE"
        bo.object = cyl
        bo.solver = "EXACT"
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier="arch")
        bpy.data.objects.remove(cyl, do_unlink=True)
    # drop the windshield faces: the procedural glass is the optical surface and stays
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index == 3], context="FACES")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    try:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40), keep_sharp_edges=True)
    except Exception:
        pass
    print(f"shell: {len(me.vertices)} vertices, {len(me.polygons)} faces", flush=True)
    # the rest of the car as occluders for the AO bake
    replaces = []
    if CAR and os.path.exists(CAR):
        bpy.ops.import_scene.gltf(filepath=CAR, merge_vertices=False, import_shading="FLAT")
        carobjs = [o for o in sc.objects if o.type == "MESH" and o is not ob]
        for o in carobjs:
            p = o.get("path") or ""
            if not p:
                continue
            c = o.matrix_world @ (0.125 * sum((Vector(b) for b in o.bound_box), Vector()))
            d = o.dimensions
            dark = False
            try:
                bsdf = o.data.materials[0].node_tree.nodes.get("Principled BSDF") if o.data.materials and o.data.materials[0] else None
                dark = bool(bsdf) and not bsdf.inputs["Base Color"].is_linked and max(bsdf.inputs["Base Color"].default_value[:3]) < 0.08
            except Exception:
                dark = False
            # the shell: the big exterior parts above the floor pan; grilles, seams, liners and lamps stay
            shell_like = (p.startswith("body") or p.startswith("leftSide") or p.startswith("rightSide")) and max(d) > 0.4 and c.z > 0.25 \
                and not (dark and max(d) < 1.0) and o.get("orig") not in ("windshield", "frit")
            if shell_like and o.get("kind") == "static":
                replaces.append(p)
                o.hide_render = True                  # the loft replaces it; do not let it shade the loft
    # bake AO into vertex colours
    w = bpy.data.worlds.new("AO")
    sc.world = w
    w.light_settings.distance = 0.5
    ca = me.color_attributes.new(name="AO", type="BYTE_COLOR", domain="CORNER")
    me.color_attributes.active_color = ca
    sc.cycles.bake_type = "AO"
    sc.render.bake.target = "VERTEX_COLORS"
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.bake(type="AO", target="VERTEX_COLORS")
    nloop = len(ca.data)
    buf = np.empty(nloop * 4, dtype=np.float32)
    ca.data.foreach_get("color", buf)
    buf = buf.reshape(nloop, 4)
    buf[:, :3] = 0.4 + 0.6 * np.clip(buf[:, :3], 0, 1) ** 0.8
    ca.data.foreach_set("color", buf.ravel())
    if PREVIEW:
        preview(sc, ob)
    # split into the left and right halves about the centre line and export
    for o in [o for o in sc.objects if o.type == "MESH" and o is not ob]:
        bpy.data.objects.remove(o, do_unlink=True)
    halves = []
    for side, group, sign in (("left", "leftSide", 1), ("right", "rightSide", -1)):
        h = ob.copy()
        h.data = me.copy()
        h.name = side
        sc.collection.objects.link(h)
        bm = bmesh.new()
        bm.from_mesh(h.data)
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        # Blender y = -z_sim: the left side of the car (sim z < CZ) is Blender y > -CZ
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, -CZ, 0), plane_no=(0, sign, 0), clear_inner=False, clear_outer=True)
        bm.to_mesh(h.data)
        bm.free()
        h["kind"] = "shell"
        h["group"] = group
        h["replaces"] = json.dumps([p for p in replaces if p.startswith(group) or p.startswith("body")])
        h["materials"] = json.dumps(names)
        halves.append(h)
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for h in halves:
        h.select_set(True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", use_selection=True, export_apply=True, export_materials="EXPORT",
                              export_vertex_color="ACTIVE", export_all_vertex_colors=False, export_active_vertex_color_when_no_material=True,
                              export_texcoords=False, export_normals=True, export_extras=True, export_yup=True,
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6, export_draco_color_quantization=8)
    with open(OUT + ".txt", "w") as f:
        f.write(base64.b64encode(open(OUT, "rb").read()).decode())
    print(f"wrote {OUT}: {os.path.getsize(OUT) // 1024} KB, replaces {len(replaces)} procedural parts, {time.time() - t0:.0f} s, gpu={used_gpu}", flush=True)


def preview(sc, ob):
    """Workbench renders from three sides, for a look at the shape."""
    out = os.path.join(os.path.dirname(OUT), "_car_body_preview")
    os.makedirs(out, exist_ok=True)
    prev_engine = sc.render.engine
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    sc.render.image_settings.file_format = "PNG"
    sc.render.resolution_x, sc.render.resolution_y = 1100, 620
    cols = [(0.55, 0.62, 0.70, 1), (0.25, 0.45, 0.65, 1), (0.25, 0.45, 0.65, 1), (0.3, 0.3, 0.3, 1), (0.05, 0.05, 0.05, 1)]
    for i, m in enumerate(ob.data.materials):
        if m:
            m.diffuse_color = cols[i % len(cols)]
    centre = B([0.0, 0.7, 0.0])
    for name, pos in (("front34", B([6.5, 2.6, -5.5])), ("rear34", B([-6.0, 2.4, 5.0])), ("side", B([0.0, 1.0, -8.5])), ("top", B([0.3, 9.0, -0.01]))):
        cam = C.pinhole_camera("pv_" + name, pos, (centre - pos), (0, 0, 1), 42)
        sc.camera = cam
        sc.render.filepath = os.path.join(out, name + ".png")
        bpy.ops.render.render(write_still=True)
    sc.render.engine = prev_engine
    print("previews in", out, flush=True)


if __name__ == "__main__":
    main()
