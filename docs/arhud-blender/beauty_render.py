"""The driver's view, path-traced: the real PGU frame through the real optics into the simulator's own car.

Inputs: the car exported by arhud-sim/dev/export-car.html (every mesh with its three.js material, the windshield
included), the PGU frame the simulator's hudd drew (main.js dumps it with #drive&warm=10&dump=pgu), and the optics
from layout.json via optics_check.py's builders (panel emitter, fold, toroid mirror, housing walls). Cycles renders
from the eye with the sky model as the world and a plain road under the car. The HUD light reaches the camera the
same way it reaches the driver: panel -> fold -> mirror -> inner surface of the laminate, with its ghost.

Output: docs/arhud-sim/assets/cycles/driver_view.png (+ a HUD-off twin), and a `beauty` entry in results.json.

Run:  /Applications/Blender.app/Contents/MacOS/Blender -b -P beauty_render.py -- car=/tmp/car_src.glb pgu=/tmp/pgu_frame.png
      [samples=256] [res=1600] [elev=38] [az=215] [hud=2.0]
"""
import json
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bl_common as C  # noqa: E402

ARGS = C.script_args()
CAR = C.arg(ARGS, "car", None)
PGU = C.arg(ARGS, "pgu", None)
OUT = C.arg(ARGS, "out", os.path.join(C.ASSETS_DIR, "cycles"))
SAMPLES = C.arg(ARGS, "samples", 256, int)
RES_W = C.arg(ARGS, "res", 1600, int)
RES_H = int(round(RES_W * 9 / 16))
SUN_ELEV = C.arg(ARGS, "elev", 38.0, float)        # degrees above the horizon
SUN_AZ = C.arg(ARGS, "az", 215.0, float)           # degrees from straight ahead, clockwise seen from above (215: behind-left)
HUD_GAIN = C.arg(ARGS, "hud", 60.0, float)         # emission strength of the PGU frame: white digits about two thirds of the sky
FOV = C.arg(ARGS, "fov", 82.0, float)              # horizontal field of the picture (the Driver view uses 55 deg vertical)
SCENE = C.arg(ARGS, "scene", "day")                # day, or night (sun below the horizon, headlights and the cabin's own light)
EYE_DY = C.arg(ARGS, "eyeDy", 0.0, float)         # the eye moved up (m) for the registration check
EYE_DZ = C.arg(ARGS, "eyeDz", 0.0, float)         # the eye moved right (m)
MARKS = C.arg(ARGS, "marks", 0, int)              # marks=1: white discs on the road at the four points pattern=marks draws
NAME = C.arg(ARGS, "name", "")                    # output suffix for a check run; the beauty entries are left alone
NPY = C.arg(ARGS, "npy", "")                      # directory to save the on/off renders as .npy for measurement
VEIL = C.arg(ARGS, "veil", 0, int)                 # veil=1: the daytime black level, the dark panel lit by sky light through the aperture
VEIL_DIFFUSE = C.arg(ARGS, "veilDiffuse", 0.02, float)   # ASSUMED: the off cell's diffuse reflectance (anti-glare front)
VEIL_SPEC = C.arg(ARGS, "veilSpec", 0.04, float)         # ASSUMED: its specular reflectance at normal incidence
VEIL_ROUGH = C.arg(ARGS, "veilRough", 0.3, float)        # ASSUMED: the anti-glare roughness
if not (CAR and os.path.exists(CAR) and PGU and os.path.exists(PGU)):
    raise SystemExit("car=<car_src.glb> and pgu=<pgu_frame.png> are required")

# optics_check parses the command line at import: hand it a quiet one
_argv = sys.argv
sys.argv = [sys.argv[0], "--", "quick=1", "out=" + os.path.join(OUT, "_beauty_tmp")]
import optics_check as O  # noqa: E402
MIRROR_MODE = C.arg(ARGS, "mirror", "toroid")     # toroid | sphere | freeform | freeformCurved (the tilted panel comes with it)
GLASS_RH = C.arg(ARGS, "glassRh", 0.0, float)     # curved windshield radii (m), 0 = the plan's flat slab; freeformCurved brings its own
GLASS_RV = C.arg(ARGS, "glassRv", 0.0, float)
if MIRROR_MODE == "freeformCurved":
    O.load_fit("freeform_curved")                 # the refit for the 4 x 8 m glass, and its glass radii
    MIRROR_MODE = "freeform"
elif GLASS_RH > 0 or GLASS_RV > 0:
    O.GLASS_RH, O.GLASS_RV = GLASS_RH, GLASS_RV
sys.argv = _argv

L = O.L
B = C.B


def road_and_world(sc):
    # the sky model as the world, with its sun disc (the only light)
    w = bpy.data.worlds.new("Sky")
    sc.world = w
    nt = w.node_tree
    bg = nt.nodes.get("Background")
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_disc = True
    sky.sun_elevation = math.radians(SUN_ELEV if SCENE == "day" else -14.0)
    # Blender's sun_rotation is about +Z from +X toward +Y; the car's forward is +X, left +Y (bl_common.B), so an
    # azimuth measured from straight ahead toward the driver's left is the same angle
    sky.sun_rotation = math.radians(SUN_AZ)
    sky.sun_intensity = 1.0
    sky.sun_size = math.radians(0.545)
    sky.aerosol_density = 0.8
    nt.links.new(sky.outputs[0], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    # road: asphalt with two white lane lines and a dashed centre, grass beyond
    asph = bpy.data.materials.new("Asphalt")
    p = asph.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.055, 0.055, 0.058, 1)
    p.inputs["Roughness"].default_value = 0.85
    grass = bpy.data.materials.new("Grass")
    p = grass.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.08, 0.14, 0.05, 1)
    p.inputs["Roughness"].default_value = 1.0
    white = bpy.data.materials.new("Paint")
    p = white.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.8, 0.8, 0.78, 1)
    p.inputs["Roughness"].default_value = 0.7
    yellow = bpy.data.materials.new("PaintY")
    p = yellow.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.75, 0.55, 0.08, 1)
    p.inputs["Roughness"].default_value = 0.7
    X, Y = B([1, 0, 0]), B([0, 0, 1])          # forward, car-right (Blender -Y)
    g = C.rect_object("ground", B([0, -0.002, 0]), X, Y, -300, 600, -300, 300, grass, uv=False)
    r = C.rect_object("road", B([0, -0.001, 0]), X, Y, -300, 600, -3.7 * 2 - 1.5 - 1.85, 3.7 * 2 + 1.5 - 1.85, asph, uv=False)
    # the ego drives the right-hand lane: lane centre 1.5 lanes right of the double yellow (world.js), so the lines
    # sit at z = -1.85 (edge right), -5.55 (centre of the road, yellow), +1.85 (lane divider, dashed)
    for z, mat in ((1.85, white),):
        C.rect_object("edgeR", B([0, 0, z]), X, Y, -300, 600, -0.075, 0.075, mat, uv=False)
    for z in (-5.55 - 0.11, -5.55 + 0.11):
        C.rect_object("centre", B([0, 0, z]), X, Y, -300, 600, -0.05, 0.05, yellow, uv=False)
    k = 0
    for x0 in range(-300, 600, 12):
        C.rect_object(f"dash{k}", B([x0 + 1.5, 0, -1.85]), X, Y, -1.5, 1.5, -0.075, 0.075, white, uv=False)
        k += 1
    return g


def import_car():
    bpy.ops.import_scene.gltf(filepath=CAR, merge_vertices=False, import_shading="FLAT")
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    eye = B(L["eye"])
    removed = 0
    ws = None
    for o in objs:
        orig = o.get("orig") or ""
        if orig == "windshield":
            ws = o
            continue
        if orig == "frit":
            continue
        # the driver's head sits on the camera: drop meshes within 0.16 m of the eye
        c = o.matrix_world @ (0.125 * sum((Vector(b) for b in o.bound_box), Vector()))
        if (c - eye).length < 0.16:
            bpy.data.objects.remove(o, do_unlink=True)
            removed += 1
    # the windshield as real laminated glass: the exported extrusion is not a closed manifold (its caps and sides
    # share no vertices), which breaks refraction, so the clean slab from optics_check stands in for it
    if ws is not None:
        bpy.data.objects.remove(ws, do_unlink=True)
        O.build_windshield(laminate=True)
    # three's transparent/opacity materials import with alpha; give the lenses and side glass a glassy look
    for o in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
        for m in o.data.materials:
            if not m or not m.node_tree:
                continue
            bsdf = m.node_tree.nodes.get("Principled BSDF")
            if not bsdf:
                continue
            a = bsdf.inputs["Alpha"].default_value
            if a < 0.6 and o is not ws:
                bsdf.inputs["Alpha"].default_value = 1.0
                bsdf.inputs["Transmission Weight"].default_value = 1.0
                bsdf.inputs["Roughness"].default_value = 0.05
                m.surface_render_method = "DITHERED" if hasattr(m, "surface_render_method") else m.surface_render_method
    return removed, ws is not None


def pgu_image():
    img = bpy.data.images.load(PGU)
    img.colorspace_settings.name = "sRGB"
    return img


def render(sc, cam, path, hud_on):
    bpy.data.objects["panelCrop"].hide_render = not hud_on
    sc.render.filepath = path
    C.set_output_exr(sc, path, RES_W, RES_H)
    bpy.ops.render.render(write_still=True)
    arr = C.load_exr(path)[::-1, :, :3]
    os.remove(path)
    return arr


def veil_survey(sc, cam, t0):
    """The window's daytime glow with the panel dark: sky light comes in through the aperture, lights the cell, and the
    optics image the lit cell to the eye as a grey veil over the window. Three renders: the panel hidden (the scene
    behind the window, with the housing floor's faint reflection), the panel as a dark reflective cell, and the panel
    as a white emitter at low samples for the window mask. The veil is the dark render minus the hidden one over the
    mask; it is reported against the scene behind the window and against the sky. Direct sun into the housing is a
    caustic path a path tracer cannot sample; the numeric sun bundle (sun_focus.py) covers that case."""
    panel = bpy.data.objects["panelCrop"]
    off = render(sc, cam, os.path.join(OUT, "_veil_off.exr"), False)
    dark = bpy.data.materials.new("PanelDark")
    dark.use_nodes = True
    pr = dark.node_tree.nodes["Principled BSDF"]
    pr.inputs["Base Color"].default_value = (VEIL_DIFFUSE, VEIL_DIFFUSE, VEIL_DIFFUSE, 1)
    pr.inputs["Roughness"].default_value = VEIL_ROUGH
    pr.inputs["Specular IOR Level"].default_value = VEIL_SPEC / 0.08      # 0.5 is 4% at normal incidence
    panel.data.materials[0] = dark
    darkr = render(sc, cam, os.path.join(OUT, "_veil_dark.exr"), True)
    white = bpy.data.materials.new("PanelWhite")
    white.use_nodes = True
    nt = white.node_tree
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    panel.data.materials[0] = white
    full = sc.cycles.samples
    sc.cycles.samples = 32
    whiter = render(sc, cam, os.path.join(OUT, "_veil_white.exr"), True)
    sc.cycles.samples = full
    lum = lambda a: a.mean(axis=2)
    mask = (lum(whiter) - lum(off)) > 0.03
    h, w = mask.shape
    if mask.sum() < 100:
        print("  no window mask found", flush=True)
        return
    veil = float((lum(darkr) - lum(off))[mask].mean())
    behind = float(lum(off)[mask].mean())
    sky = float(np.percentile(lum(off)[: h // 4, w // 4: 3 * w // 4], 60))
    exposure = 1.4 / max(float(np.percentile(lum(off)[: h // 4, w // 4: 3 * w // 4], 80)), 1e-6)
    C.save_png(os.path.join(OUT, "driver_view_veil.png"), O.shrink(C.tonemap(darkr, exposure), 1))
    rp = os.path.join(OUT, "results.json")
    R = json.load(open(rp)) if os.path.exists(rp) else {}
    R["veil"] = {"file": "driver_view_veil.png", "veil": veil, "behind": behind, "sky": sky, "veilOverBehind": veil / behind if behind else None,
                 "veilOverSky": veil / sky if sky else None, "maskPx": int(mask.sum()),
                 "panel": {"diffuse": VEIL_DIFFUSE, "specular": VEIL_SPEC, "roughness": VEIL_ROUGH, "assumed": True},
                 "sunElevDeg": SUN_ELEV, "sunAzDeg": SUN_AZ, "samples": SAMPLES, "generated": time.strftime("%Y-%m-%d %H:%M")}
    with open(rp, "w") as f:
        json.dump(R, f, indent=1)
    print(f"  veil {veil:.5f} over the window; scene behind {behind:.5f} (veil/behind {veil / behind:.3f}); sky {sky:.4f} (veil/sky {veil / sky:.4f}); mask {int(mask.sum())} px; {time.time() - t0:.0f} s", flush=True)


def main():
    t0 = time.time()
    sc = C.fresh_scene()
    used_gpu = C.setup_cycles(sc, samples=SAMPLES, gpu=True, bounces=10)
    sc.cycles.use_denoising = True
    sc.cycles.blur_glossy = 0.0
    road_and_world(sc)
    removed, has_ws = import_car()
    if SCENE == "night":
        # headlights: two spots where car.js puts them, aimed forward and down; a faint moonless sky remains
        for side in (-1, 1):
            lamp = bpy.data.lights.new("headlight", "SPOT")
            lamp.energy = 2500.0
            lamp.spot_size = math.radians(48)
            lamp.spot_blend = 0.6
            lamp.color = (0.95, 0.97, 1.0)
            ob = bpy.data.objects.new("headlight", lamp)
            sc.collection.objects.link(ob)
            pos = B([2.32, 0.68, L["carCenterZ"] + side * 0.62])
            aim = B([34.0, 0.0, L["carCenterZ"] + side * 0.9])
            ob.location = pos
            ob.rotation_euler = (aim - pos).to_track_quat("-Z", "Y").to_euler()
        sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
    # the optics: emitter with the real PGU frame, fold, mirror, housing walls
    img = pgu_image()
    O._MODE_SAG["mode"] = MIRROR_MODE
    O.build_panel(img, MIRROR_MODE)
    mat = bpy.data.materials["PanelEmit"]
    for n in mat.node_tree.nodes:
        if n.type == "EMISSION":
            n.inputs["Strength"].default_value = HUD_GAIN
    O.build_fold()
    O.build_mirror(MIRROR_MODE)
    walls = O.build_housing_walls()
    # the printed housing on the dash top is matte dark plastic, not a perfect absorber, in the picture
    wm = walls.data.materials[0]
    for n in wm.node_tree.nodes:
        if n.type == "BSDF_DIFFUSE":
            n.inputs["Color"].default_value = (0.045, 0.045, 0.05, 1)
    # the eye, looking along LOOK, a wide field so the dash, the wheel and the road are in the picture
    eye, look, up = B(L["eye"]), B(L["look"]).normalized(), B(L["vimg"]["UP"]).normalized()
    eye = eye + B([0.0, EYE_DY, EYE_DZ])
    if MARKS:
        white = bpy.data.materials.new("MarkPaint")      # red and self-lit, so the discs are found by colour, not brightness
        white.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0, 0, 1)
        white.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1, 0, 0, 1)
        white.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 4.0
        for (x, y, z) in ((16, 0, 1.0), (16, 0, -1.0), (24, 0, 1.0), (24, 0, -1.0)):      # the points main.js pattern=marks draws
            bpy.ops.mesh.primitive_circle_add(vertices=32, radius=0.10, fill_type="NGON", location=tuple(B([x, y + 0.004, z])))
            ob = bpy.context.active_object
            ob.name = "mark"
            ob.data.materials.append(white)
    cam = C.pinhole_camera("eye", eye, look, up, FOV, clip_start=0.05, clip_end=2000)
    sc.camera = cam
    os.makedirs(OUT, exist_ok=True)
    if VEIL:
        veil_survey(sc, cam, t0)
        return
    on = render(sc, cam, os.path.join(OUT, "_beauty_on.exr"), True)
    off = render(sc, cam, os.path.join(OUT, "_beauty_off.exr"), False)
    if NAME:
        if NPY:
            os.makedirs(NPY, exist_ok=True)
            np.save(os.path.join(NPY, NAME + "_on.npy"), on)
            np.save(os.path.join(NPY, NAME + "_off.npy"), off)
        lum = off.mean(axis=2)
        exposure = 1.4 / max(float(np.percentile(lum[: lum.shape[0] // 4, lum.shape[1] // 4: 3 * lum.shape[1] // 4], 80)), 1e-6)
        C.save_png(os.path.join(NPY or OUT, NAME + ".png"), O.shrink(C.tonemap(on, exposure), 1))
        print(f"wrote {NAME} (eye +{EYE_DY * 1000:.0f} up, +{EYE_DZ * 1000:.0f} right; marks {MARKS}) in {time.time() - t0:.0f} s", flush=True)
        return
    # exposure so that the road reads mid-grey; the same for both pictures
    lum = off.mean(axis=2)
    if SCENE == "day":
        sky = lum[: lum.shape[0] // 4, lum.shape[1] // 4: 3 * lum.shape[1] // 4]     # the glass and the sky through it
        exposure = 1.4 / max(float(np.percentile(sky, 80)), 1e-6)   # the sky white-ish, the cabin in its shade
    else:
        exposure = 0.6 / max(float(np.percentile(lum[lum > 1e-6], 97)), 1e-6)   # the headlit road near white
    suffix = "" if SCENE == "day" else "_night"
    C.save_png(os.path.join(OUT, f"driver_view{suffix}.png"), O.shrink(C.tonemap(on, exposure), 1))
    C.save_png(os.path.join(OUT, f"driver_view_hud_off{suffix}.png"), O.shrink(C.tonemap(off, exposure), 1))
    rp = os.path.join(OUT, "results.json")
    if os.path.exists(rp):
        with open(rp) as f:
            R = json.load(f)
        entry = {"file": f"driver_view{suffix}.png", "hudOff": f"driver_view_hud_off{suffix}.png", "res": [RES_W, RES_H], "fovDeg": FOV, "sunElevDeg": SUN_ELEV if SCENE == "day" else -14.0, "sunAzDeg": SUN_AZ,
                 "hudGain": HUD_GAIN, "samples": SAMPLES, "headMeshesRemoved": removed, "windshieldAsGlass": has_ws, "scene": SCENE, "generated": time.strftime("%Y-%m-%d %H:%M")}
        if SCENE == "day":
            R["beauty"] = {**(R.get("beauty") or {}), **entry}
        else:
            R["beautyNight"] = entry
        with open(rp, "w") as f:
            json.dump(R, f, indent=1)
    print(f"wrote driver_view{suffix}.png ({RES_W}x{RES_H}, {SAMPLES} samples, gpu={used_gpu}) in {time.time() - t0:.0f} s; head meshes removed {removed}, windshield glass {has_ws}", flush=True)


if __name__ == "__main__":
    main()
