"""Render preview images of the housing with Blender (headless).

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/preview.py -- OUT_DIR [view ...]

Views: assembled, cutaway, exploded, bay, mirror, lid. Reads ../arhud-sim/assets/cad/housing.glb and housing.json.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent.parent
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = Path(args[0] if args else "/tmp/arhud-preview")
views = args[1:] or ["assembled", "cutaway", "exploded", "bay", "mirror", "lid"]
out.mkdir(parents=True, exist_ok=True)
GLB = HERE.parent / "arhud-sim" / "assets" / "cad" / "housing.glb"
MAN = json.loads((HERE.parent / "arhud-sim" / "assets" / "cad" / "housing.json").read_text())
PARTS = {p["id"]: p for p in MAN["parts"]}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(GLB))
objs = [o for o in bpy.data.objects if o.type == "MESH"]


def mat(name, rgb, rough=0.6, metal=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Alpha"].default_value = alpha
    m.diffuse_color = (*rgb, alpha)
    return m


MATS = {
    "asa": mat("asa", (0.30, 0.31, 0.33), 0.8),
    "tpu": mat("tpu", (0.12, 0.10, 0.09), 0.9),
    "brass": mat("brass", (0.80, 0.58, 0.25), 0.35, 1.0),
    "steel": mat("steel", (0.55, 0.56, 0.58), 0.35, 1.0),
    "rtv": mat("rtv", (0.85, 0.85, 0.8), 0.7),
    "rubber": mat("rubber", (0.02, 0.02, 0.02), 0.95),
    "alu": mat("alu", (0.08, 0.08, 0.09), 0.5, 0.6),
    "glass": mat("glass", (0.55, 0.75, 0.8), 0.05, 0.0, 0.25),
}
ACCENT = {"bay": (0.06, 0.08, 0.12), "carrier": (0.10, 0.07, 0.05), "foldBracket": (0.05, 0.09, 0.06),
          "mirrorStand": (0.09, 0.05, 0.08), "strongback": (0.08, 0.08, 0.05)}
for o in objs:
    pid = o.name.split(".")[0]
    p = PARTS.get(pid, {})
    m = MATS.get(p.get("material", "asa"), MATS["asa"])
    if pid in ACCENT:
        m = mat("acc_" + pid, ACCENT[pid], 0.8)
    o.data.materials.clear()
    o.data.materials.append(m)
    o["pid"] = pid
    o["base"] = tuple(o.location)

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_cavity = True
scene.display.shading.cavity_type = "BOTH"
scene.display.shading.show_shadows = True
scene.display.shading.shadow_intensity = 0.35
scene.display.shading.show_specular_highlight = True
scene.render.resolution_x, scene.render.resolution_y = 1500, 1000
scene.world = bpy.data.worlds.new("w")
scene.world.color = (0.78, 0.80, 0.83)
scene.display_settings.display_device = "sRGB"
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam)
scene.camera = cam
cam.data.lens = 50


def car(x, y, z):
    """Simulator frame (m) -> Blender (glTF import turns Y-up into Z-up: x, -z, y)."""
    return Vector((x, -z, y))


def look(eye, target, lens=50):
    cam.location = eye
    d = target - eye
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens


def show(fn):
    for o in objs:
        o.hide_render = not fn(o["pid"])
        o.location = Vector(o["base"])


def explode(scale=1.0):
    for o in objs:
        e = PARTS.get(o["pid"], {}).get("explode", [0, 0, 0])
        o.location = Vector(o["base"]) + car(*e) * scale


def add_rays():
    """The traced rays (toroid, landing on the mirror) as thin amber curves, and the windshield line."""
    lay = json.loads((HERE / "layout.json").read_text())
    cu = bpy.data.curves.new("rays", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.0004
    for r in lay["rays"]["toroid"]:
        if not r["inside"] or r["e"][0] not in (-1, 0, 1) or r["f"][0] != 0:
            continue
        pts = [car(*p) for p in r["pts"][1:]]
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            sp.points[i].co = (*p, 1)
    ob = bpy.data.objects.new("rays", cu)
    ob.data.materials.append(mat("ray", (1.0, 0.55, 0.1), 0.5))
    scene.collection.objects.link(ob)
    g = lay["glass"]
    import math as m
    t = m.tan(m.radians(g["rakeDeg"]))
    gx, gy = g["G"][0], g["G"][1]
    cu2 = bpy.data.curves.new("glass", "CURVE"); cu2.dimensions = "3D"; cu2.bevel_depth = 0.0008
    sp = cu2.splines.new("POLY"); sp.points.add(1)
    for i, x in enumerate((0.55, 1.10)):
        sp.points[i].co = (*car(x, gy - (x - gx) * t, 0.0), 1)
    ob2 = bpy.data.objects.new("glassline", cu2)
    ob2.data.materials.append(mat("gl", (0.2, 0.5, 0.9), 0.5))
    scene.collection.objects.link(ob2)
    return [ob, ob2]


C = car(0.80, 0.95, 0.0)
extra = []
for v in views:
    for o in extra:
        o.hide_render = True
    if v == "section":
        extra = extra or add_rays()
        for o in extra:
            o.hide_render = False
        show(lambda p: not p.startswith("cap") or "Right" in p)
        for o in objs:
            if "Left" in o["pid"] or o["pid"] in ("vaneL", "mirrorClipL", "railLeftRear", "railLeftFront", "coverGlass", "leafRear", "leafFront"):
                o.hide_render = True
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = 0.56
        cam.location = car(0.80, 0.97, -1.5)
        cam.rotation_euler = (car(0.80, 0.97, 0.0) - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(out / f"{v}.png")
        bpy.ops.render.render(write_still=True)
        print("wrote", scene.render.filepath)
        cam.data.type = "PERSP"
        continue
    if v == "assembled":
        show(lambda p: True)
        look(car(0.25, 1.45, -0.55), C, 45)
    elif v == "front":
        show(lambda p: True)
        look(car(1.45, 1.25, 0.45), C, 45)
    elif v == "cutaway":
        show(lambda p: not p.startswith("cap") and p not in ("bodyRearLeft", "bodyFrontLeft", "vaneL", "coverGlass", "clamps", "alsPod")
             and not p.startswith("rail") and not p.startswith("leaf") and p != "springAnchor")
        look(car(0.55, 1.30, -0.75), car(0.82, 0.90, 0.0), 42)
    elif v == "exploded":
        show(lambda p: True)
        explode(1.0)
        look(car(0.05, 1.75, -1.05), car(0.82, 1.05, 0.0), 40)
    elif v == "bay":
        show(lambda p: p in ("bay", "carrier", "mask", "foldBracket", "grommetHdmi", "grommetLed") or p.startswith("hwBay") or p.startswith("hwPanel"))
        look(car(0.55, 1.15, -0.30), car(0.69, 0.93, 0.0), 55)
    elif v == "mirror":
        show(lambda p: p in ("mirrorStand", "strongback", "mirrorClipL", "mirrorClipR", "bodyFrontRight", "accessPlug1", "accessPlug2", "accessPlug3")
             or p.startswith("hwMirror"))
        look(car(1.25, 1.10, -0.45), car(0.95, 0.88, 0.0), 45)
    elif v == "lid":
        show(lambda p: p.startswith("cap") or p.startswith("rail") or p.startswith("leaf") or p in ("servoBracket", "springAnchor", "hwShutter0", "hwShutter1", "hwShutter2", "hwShutter3"))
        look(car(0.80, 0.55, -0.70), car(0.82, 1.05, 0.0), 38)
    scene.render.filepath = str(out / f"{v}.png")
    bpy.ops.render.render(write_still=True)
    print("wrote", scene.render.filepath)
