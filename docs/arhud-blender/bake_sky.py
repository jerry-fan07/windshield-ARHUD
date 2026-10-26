"""Bake image-based lighting for the driving world from Blender's physically based sky model.

The simulator's world lights the car with a directional sun and a hemisphere light; nothing in the driving scene has
an environment map, so paint, glass and metal reflect nothing and the cabin's indirect light has no colour. This
script renders Blender's multiple-scattering sky (the model behind Cycles' Sky Texture) to small equirectangular
maps at a set of sun elevations, which the simulator uses as `scene.environment` (rotated at run time to the sun's
azimuth). The sun disc is left out: the simulator's DirectionalLight is the sun and casts the shadows.

Overcast and night are not sky-model renders: overcast is the CIE overcast luminance distribution and night a
moonless twilight floor, both written by the same code path so the simulator treats every map alike.

Each map is normalised so its upper hemisphere averages 1.0; the manifest records the physical factor it was divided
by, the sun's column in the image, and the parameters. Output: docs/arhud-sim/assets/sky/*.exr + manifest.json.

Run:  /Applications/Blender.app/Contents/MacOS/Blender -b -P bake_sky.py -- [out=DIR] [w=512] [preview=1]
"""
import json
import math
import os
import sys
import time

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bl_common as C  # noqa: E402

ARGS = C.script_args()
OUT = C.arg(ARGS, "out", os.path.join(C.ASSETS_DIR, "sky"))
W = C.arg(ARGS, "w", 512, int)
H = W // 2
PREVIEW = C.arg(ARGS, "preview", 1, int)
os.makedirs(OUT, exist_ok=True)

# Sun elevations to bake (degrees). The simulator picks the nearest for the current time of day; 2.3 deg is the
# dusk scene (19:03 solar time on June 21 at 37 N), 76 deg the solar noon maximum there.
ELEVATIONS = [2.3, 8, 15, 25, 35, 45, 55, 65, 76]


def sky_scene(elevation_deg, azimuth_deg=0.0):
    sc = C.fresh_scene()
    C.setup_cycles(sc, samples=16, gpu=True, bounces=4)
    w = bpy.data.worlds.new("Sky")
    sc.world = w
    nt = w.node_tree
    bg = nt.nodes.get("Background") or nt.nodes.new("ShaderNodeBackground")
    out = next((n for n in nt.nodes if n.type == "OUTPUT_WORLD"), None) or nt.nodes.new("ShaderNodeOutputWorld")
    if not any(l.to_node == out for l in nt.links):
        nt.links.new(bg.outputs[0], out.inputs[0])
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_disc = False                       # the simulator's directional light is the sun
    sky.sun_elevation = math.radians(elevation_deg)
    sky.sun_rotation = math.radians(azimuth_deg)
    sky.sun_intensity = 1.0
    sky.altitude = 0.0
    sky.air_density = 1.0
    sky.aerosol_density = 0.6                  # a clear day, like the simulator's turbidity 1.8
    sky.ozone_density = 1.0
    if hasattr(sky, "ground_albedo"):
        sky.ground_albedo = 0.18
    bg.inputs["Strength"].default_value = 1.0
    nt.links.new(sky.outputs[0], bg.inputs["Color"])
    cam = bpy.data.objects.new("pano", bpy.data.cameras.new("pano"))
    cam.data.type = "PANO"
    cam.data.panorama_type = "EQUIRECTANGULAR"
    cam.rotation_euler = (math.pi / 2, 0, 0)   # horizon across the middle, zenith at the top
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc


def render_equirect(sc, path):
    C.set_output_exr(sc, path, W, H)
    bpy.ops.render.render(write_still=True)
    arr = C.load_exr(path)[::-1, :, :3]          # row 0 = top = zenith
    return arr


def write_exr(path, rgb_top_first):
    """Half-float ZIP EXR (what three's EXRLoader reads) from a numpy (H, W, 3) array with row 0 at the top."""
    h, w = rgb_top_first.shape[:2]
    img = bpy.data.images.new(os.path.basename(path), width=w, height=h, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    rgba = np.concatenate([rgb_top_first[::-1], np.ones((h, w, 1))], axis=2).astype(np.float32)
    img.pixels.foreach_set(rgba.ravel())
    sc = bpy.context.scene
    sc.render.image_settings.file_format = "OPEN_EXR"
    sc.render.image_settings.color_depth = "16"
    sc.render.image_settings.exr_codec = "ZIP"
    sc.render.image_settings.color_mode = "RGB"
    img.save_render(path, scene=sc)
    bpy.data.images.remove(img)


def luminance(rgb):
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def finish(name, rgb, meta):
    """Fill the ground half, normalise, write the EXR and a preview, return the manifest entry."""
    h, w = rgb.shape[:2]
    lum = luminance(rgb)
    upper = lum[: h // 2]
    scale = float(upper.mean()) if upper.mean() > 0 else 1.0
    # ground: the model's lower hemisphere is dark; give it the horizon's light times a road-and-grass albedo
    horizon = rgb[h // 2 - 3: h // 2 + 1].mean(axis=(0, 1))
    ground = horizon * np.array([0.26, 0.27, 0.22])
    v = (np.arange(h)[:, None] + 0.5) / h
    down = np.clip((v - 0.5) * 2, 0, 1)                   # 0 at the horizon, 1 at the nadir
    blend = np.clip(down * 12, 0, 1)[..., None]
    rgb = rgb.copy()
    rgb[h // 2:] = rgb[h // 2:] * (1 - blend[h // 2:]) + ground * blend[h // 2:] * (0.75 + 0.25 * (1 - down[h // 2:, ..., None]))
    rgb /= scale
    # the sun's column: the brightest column of the upper hemisphere (the disc is off, but the aureole is there)
    col = luminance(rgb[: h // 2]).sum(axis=0)
    sun_u = float((np.argmax(col) + 0.5) / w) if meta.get("elevation") is not None else None
    path = os.path.join(OUT, name + ".exr")
    write_exr(path, rgb)
    # the artifact host serves text but not EXR: the same bytes in base64 beside it, which assets.js decodes
    import base64
    with open(path + ".txt", "w") as f:
        f.write(base64.b64encode(open(path, "rb").read()).decode())
    if PREVIEW:
        C.save_png(os.path.join(OUT, name + ".png"), C.tonemap(rgb, exposure=0.8), flip=True)
    entry = {"file": name + ".exr.txt", "scale": scale, "sunU": sun_u, "size": [w, h], **meta}
    print(f"  {name}: mean upper {scale:.4g}, sun column {sun_u}, zenith {rgb[2, w // 2].round(3).tolist()}, horizon {rgb[h // 2 - 2, w // 2].round(3).tolist()}", flush=True)
    return entry


def cie_overcast():
    """CIE standard overcast sky: L(theta) = Lz (1 + 2 sin(elevation)) / 3, neutral and slightly cool."""
    v = (np.arange(H)[:, None] + 0.5) / H
    elev = (0.5 - v) * math.pi                   # +pi/2 at the top row
    lz = 1.0
    L = lz * (1 + 2 * np.clip(np.sin(elev), 0, 1)) / 3
    rgb = np.repeat(L[..., None], 3, axis=2) * np.array([0.93, 0.96, 1.0])
    rgb = np.repeat(rgb, W, axis=1)
    return rgb.astype(np.float32)


def night():
    """Moonless night: a faint blue-grey glow brightening toward the horizon (airglow and distant lights)."""
    v = (np.arange(H)[:, None] + 0.5) / H
    elev = (0.5 - v) * math.pi
    L = 0.6 + 0.4 * (1 - np.clip(np.sin(elev), 0, 1)) ** 2
    rgb = np.repeat(L[..., None], 3, axis=2) * np.array([0.55, 0.65, 1.0])
    rgb = np.repeat(rgb, W, axis=1)
    return rgb.astype(np.float32)


def main():
    t0 = time.time()
    manifest = {"generated": time.strftime("%Y-%m-%d %H:%M"), "blender": bpy.app.version_string, "size": [W, H],
                "convention": "equirectangular, row 0 = zenith, columns = azimuth; sunU is the sun's column (0..1) in the image",
                "encoding": "each map is a half-float ZIP EXR; the .exr.txt beside it is the same bytes in base64, because the artifact host serves text but not EXR",
                "maps": []}
    for el in ELEVATIONS:
        print(f"== sky at {el} deg", flush=True)
        sc = sky_scene(el)
        tmp = os.path.join(OUT, "_tmp.exr")
        rgb = render_equirect(sc, tmp)
        os.remove(tmp)
        manifest["maps"].append(finish(f"sky_e{el:g}".replace(".", "p"), rgb, {"kind": "sky", "elevation": el, "aerosol": 0.6}))
    C.fresh_scene()
    manifest["maps"].append(finish("overcast", cie_overcast(), {"kind": "overcast", "elevation": None, "model": "CIE overcast"}))
    manifest["maps"].append(finish("night", night(), {"kind": "night", "elevation": None, "model": "synthetic moonless"}))
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"wrote {len(manifest['maps'])} maps to {OUT} in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
