"""Shared helpers for the Blender scripts: the simulator's layout (layout.json, written by dump_layout.mjs), the frame
conversion, Cycles setup, materials, and image I/O.

Frames. The simulator's car frame is X forward, Y up, Z right (metres). Blender is Z up and its glTF exporter maps
Blender (x, y, z) to glTF (x, z, -y), so a simulator point (xs, ys, zs) is built in Blender at (xs, -zs, ys):
X forward, Y left, Z up. Everything exported lands in the simulator's frame without any rotation on the JS side.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SIM_DIR = os.path.normpath(os.path.join(HERE, "..", "arhud-sim"))
ASSETS_DIR = os.path.join(SIM_DIR, "assets")


def load_layout():
    path = os.path.join(HERE, "layout.json")
    if not os.path.exists(path):
        raise SystemExit("layout.json is missing: run `node dump_layout.mjs` first")
    with open(path) as f:
        return json.load(f)


def B(p):
    """Simulator (x, y, z) -> Blender Vector (x, -z, y). Works for points and directions."""
    return Vector((p[0], -p[2], p[1]))


def script_args():
    """Arguments after `--` on the Blender command line."""
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else []


def arg(args, key, default=None, cast=str):
    for a in args:
        if a.startswith(key + "="):
            return cast(a[len(key) + 1:])
    return default


# ---- scene -------------------------------------------------------------------------------------------------------
def fresh_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    return sc


def setup_cycles(sc, samples=128, gpu=True, bounces=12):
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    used_gpu = False
    if gpu:
        try:
            prefs.compute_device_type = "METAL"
            prefs.get_devices()
            for d in prefs.devices:
                d.use = d.type == "METAL"
            sc.cycles.device = "GPU"
            used_gpu = True
        except Exception as e:  # no Metal device: the CPU path renders the same picture, slower
            print("cycles: no GPU,", e)
            sc.cycles.device = "CPU"
    else:
        sc.cycles.device = "CPU"
    cy = sc.cycles
    cy.samples = samples
    cy.use_denoising = False
    cy.use_adaptive_sampling = False
    cy.max_bounces = bounces
    cy.diffuse_bounces = 4
    cy.glossy_bounces = bounces
    cy.transmission_bounces = bounces
    cy.transparent_max_bounces = bounces
    cy.volume_bounces = 0
    cy.caustics_reflective = True
    cy.caustics_refractive = True
    cy.blur_glossy = 0.0          # "filter glossy" would smear the sharp specular chain
    cy.sample_clamp_direct = 0.0
    cy.sample_clamp_indirect = 0.0
    cy.use_light_tree = True
    sc.render.use_persistent_data = True
    sc.render.film_transparent = False
    return used_gpu


def set_output_exr(sc, path, w, h):
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "OPEN_EXR"
    sc.render.image_settings.color_depth = "32"
    sc.render.image_settings.exr_codec = "ZIP"
    sc.render.image_settings.color_mode = "RGB"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.render.filepath = path


def black_world(sc):
    w = bpy.data.worlds.new("Black")
    sc.world = w
    nt = w.node_tree
    bg = nt.nodes.get("Background")
    if bg is None:
        bg = nt.nodes.new("ShaderNodeBackground")
        out = nt.nodes.new("ShaderNodeOutputWorld")
        nt.links.new(bg.outputs[0], out.inputs[0])
    bg.inputs["Color"].default_value = (0, 0, 0, 1)
    bg.inputs["Strength"].default_value = 0.0
    return w


# ---- materials ----------------------------------------------------------------------------------------------------
def _tree(mat):
    if mat.node_tree is None:
        mat.use_nodes = True
    return mat.node_tree


def _clear_tree(nt):
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return out


def mirror_material(name="Mirror", color=(1, 1, 1, 1), roughness=0.0):
    """A perfect specular reflector: metallic Principled with white base colour and zero roughness."""
    mat = bpy.data.materials.new(name)
    nt = _tree(mat)
    out = _clear_tree(nt)
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = color
    p.inputs["Metallic"].default_value = 1.0
    p.inputs["Roughness"].default_value = roughness
    nt.links.new(p.outputs[0], out.inputs[0])
    return mat


def glass_material(name="Glass", ior=1.52):
    mat = bpy.data.materials.new(name)
    nt = _tree(mat)
    out = _clear_tree(nt)
    g = nt.nodes.new("ShaderNodeBsdfGlass")
    g.inputs["Color"].default_value = (1, 1, 1, 1)
    g.inputs["Roughness"].default_value = 0.0
    g.inputs["IOR"].default_value = ior
    nt.links.new(g.outputs[0], out.inputs[0])
    return mat


def black_material(name="Black"):
    mat = bpy.data.materials.new(name)
    nt = _tree(mat)
    out = _clear_tree(nt)
    p = nt.nodes.new("ShaderNodeBsdfDiffuse")
    p.inputs["Color"].default_value = (0, 0, 0, 1)
    nt.links.new(p.outputs[0], out.inputs[0])
    return mat


def emission_image_material(name, image, strength=1.0):
    """Emits the image (linear, non-colour data) with the given strength; black elsewhere."""
    mat = bpy.data.materials.new(name)
    nt = _tree(mat)
    out = _clear_tree(nt)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Linear"
    tex.extension = "CLIP"
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs[0])
    mat.use_backface_culling = False
    return mat


# ---- meshes --------------------------------------------------------------------------------------------------------
def mesh_object(name, verts, faces, uvs=None, material=None, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    if uvs is not None:
        uv = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                uv.data[li].uv = uvs[vi]
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if material is not None:
        me.materials.append(material)
    return ob


def rect_object(name, centre, axis_a, axis_b, a0, a1, b0, b1, material=None, uv=True):
    """A single quad: centre + a*axis_a + b*axis_b for a in [a0, a1], b in [b0, b1] (all Blender-frame vectors)."""
    c = Vector(centre)
    A = Vector(axis_a)
    Bv = Vector(axis_b)
    verts = [c + A * a0 + Bv * b0, c + A * a1 + Bv * b0, c + A * a1 + Bv * b1, c + A * a0 + Bv * b1]
    uvs = [(0, 0), (1, 0), (1, 1), (0, 1)] if uv else None
    return mesh_object(name, verts, [(0, 1, 2, 3)], uvs, material, smooth=False)


def slab_object(name, centre, axis_a, axis_b, normal, a0, a1, b0, b1, t0, t1, material=None):
    """A box: the rect above extruded along `normal` from t0 to t1 (the windshield laminate)."""
    c = Vector(centre)
    A = Vector(axis_a)
    Bv = Vector(axis_b)
    N = Vector(normal)
    corners = [(a0, b0), (a1, b0), (a1, b1), (a0, b1)]
    verts = [c + A * a + Bv * b + N * t0 for a, b in corners] + [c + A * a + Bv * b + N * t1 for a, b in corners]
    faces = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return mesh_object(name, verts, faces, None, material, smooth=False)


# ---- cameras -------------------------------------------------------------------------------------------------------
def pinhole_camera(name, position, forward, up, fov_h_deg, clip_start=0.01, clip_end=200.0):
    """Perspective camera at `position` looking along `forward` (Blender-frame) with `up`; horizontal FOV in degrees."""
    cam = bpy.data.cameras.new(name)
    cam.type = "PERSP"
    cam.sensor_fit = "HORIZONTAL"
    cam.lens_unit = "FOV"
    cam.angle = math.radians(fov_h_deg)
    cam.clip_start = clip_start
    cam.clip_end = clip_end
    cam.dof.use_dof = False
    ob = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(ob)
    aim_camera(ob, position, forward, up)
    return ob


def aim_camera(ob, position, forward, up):
    f = Vector(forward).normalized()
    u = Vector(up).normalized()
    r = f.cross(u).normalized()
    u = r.cross(f).normalized()
    # camera looks down local -Z, local +Y up, local +X right
    rot = Matrix((r, u, -f)).transposed()      # columns = local axes in world
    ob.matrix_world = Matrix.Translation(Vector(position)) @ rot.to_4x4()


# ---- images ----------------------------------------------------------------------------------------------------------
def image_from_array(name, arr, float_buffer=True, colorspace="Non-Color"):
    """arr: numpy (H, W, 3 or 4) float, row 0 at the bottom (Blender's order)."""
    import numpy as np
    h, w = arr.shape[:2]
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1), dtype=arr.dtype)], axis=2)
    img = bpy.data.images.new(name, width=w, height=h, alpha=True, float_buffer=float_buffer)
    img.colorspace_settings.name = colorspace
    img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    img.pack()
    return img


def load_exr(path):
    """Read an EXR written by the renderer into a numpy (H, W, 4) array, row 0 at the bottom."""
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    return buf.reshape(h, w, 4)


def save_png(path, rgb, flip=True):
    """rgb: numpy (H, W, 3) display-referred in [0, 1], row 0 at the TOP when flip=True."""
    import numpy as np
    arr = rgb[::-1] if flip else rgb
    h, w = arr.shape[:2]
    img = bpy.data.images.new(os.path.basename(path), width=w, height=h, alpha=False)
    img.colorspace_settings.name = "sRGB"
    rgba = np.concatenate([np.clip(arr, 0, 1), np.ones((h, w, 1))], axis=2).astype(np.float32)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def tonemap(lin, exposure=1.0, gamma=2.2):
    import numpy as np
    x = np.clip(lin * exposure, 0, None)
    x = x / (1 + x)                       # Reinhard
    return np.power(x, 1 / gamma)


def render_to(sc, path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path
