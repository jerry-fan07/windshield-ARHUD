"""Cycles render of what the eye sees through the Stage 1 Fresnel lens (unfolded path, no combiner).

The lens is built tooth by tooth from optics.py's solved facet slopes (0.5 mm pitch, 2 mm PMMA sheet,
grooves toward the eye), out to r = 160 mm. The panel shows the HUD test frame (testframe.png) on an
80 x 40 mm crop at the traced panel distance. Three passes per camera at the PMMA index for 620, 530
and 450 nm, each emitting only that colour channel, are merged into one RGB picture, so the lens's
dispersion appears as it would. Two cameras at the eye point: a pinhole, and a 4 mm pupil focused at
the virtual image (4.9 m), which is how an eye sees it.

Run: /Applications/Blender.app/Contents/MacOS/Blender -b --python through_lens.py -- [samples=256] [quick=1]
Writes ../out/png/through_*.png (and EXR intermediates in renders/).
"""
import math, os, sys, time
import numpy as np
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import optics as O          # noqa: E402
import teeth as TT          # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d, cast=str):
    for a in ARGS:
        if a.startswith(k + "="):
            return cast(a.split("=", 1)[1])
    return d
SAMPLES = arg("samples", 256, int)
QUICK = arg("quick", 0, int)
SEG = arg("seg", 1024, int)
RMAX = arg("rmax", 160.0, float)
NOWALLS = arg("nowalls", 0, int)
REFR = arg("refr", 0, int)
ONLY = arg("only", "", str)
TAG = arg("tag", "", str)
FOCUS = arg("focus", 0.0, float)
FACETS = arg("facets", "curved", str)            # curved: exact asphere normals per ring; flat: conical facets
SUFFIX = "" if FACETS == "curved" else "_flat"
W_PX, H_PX = (950, 450) if QUICK else (1900, 900)
HFOV = 17.0
OUT = os.path.join(os.path.dirname(HERE), "out", "png")
REN = os.path.join(HERE, "renders")
os.makedirs(OUT, exist_ok=True); os.makedirs(REN, exist_ok=True)

def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0            # scene in metres: geometry is built in mm and scaled by S
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "METAL"; prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == "METAL"
        sc.cycles.device = "GPU"
    except Exception as e:
        print("no GPU", e); sc.cycles.device = "CPU"
    cy = sc.cycles
    cy.samples = SAMPLES; cy.use_adaptive_sampling = False
    cy.max_bounces = 24; cy.glossy_bounces = 24; cy.transmission_bounces = 24; cy.diffuse_bounces = 2
    cy.transparent_max_bounces = 8; cy.caustics_reflective = True; cy.caustics_refractive = True
    cy.blur_glossy = 0.0; cy.sample_clamp_direct = 0; cy.sample_clamp_indirect = 0
    cy.use_denoising = True
    try:
        cy.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    cy.filter_width = 1.0
    sc.render.resolution_x, sc.render.resolution_y = W_PX, H_PX
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
    w = bpy.data.worlds.new("Black"); sc.world = w
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0, 0, 0, 1); bg.inputs["Strength"].default_value = 0
    return sc

S = 1e-3                                           # mm -> m (Cycles' camera aperture is in metres)

def mesh_from_np(name, verts, quads=None, tris=None, smooth=True):
    verts = np.asarray(verts, float) * S
    me = bpy.data.meshes.new(name)
    polys = []
    if quads is not None:
        polys.append((quads, 4))
    if tris is not None:
        polys.append((tris, 3))
    loops = np.concatenate([p.ravel() for p, _ in polys]).astype(np.int32)
    starts = []; off = 0
    for p, n in polys:
        starts.append(off + np.arange(p.shape[0]) * n); off += p.size
    starts = np.concatenate(starts).astype(np.int32)
    me.vertices.add(len(verts)); me.vertices.foreach_set("co", verts.astype(np.float32).ravel())
    me.loops.add(len(loops)); me.loops.foreach_set("vertex_index", loops)
    me.polygons.add(len(starts)); me.polygons.foreach_set("loop_start", starts)
    me.update(calc_edges=True)
    me.polygons.foreach_set("use_smooth", np.full(len(starts), smooth, dtype=bool))
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob

def build_lens():
    """Teeth on top (z >= 0, grooves toward the eye at +z), flat face at z = -T, rim at RMAX."""
    p = O.PITCH; K = int(round(RMAX / p))
    rk = np.arange(K + 1) * p
    sag = TT.sag(rk)
    h = sag[:-1] - sag[1:]                           # tip height of zone k (at r_k)
    th = np.linspace(0, 2 * np.pi, SEG, endpoint=False)
    c, s_ = np.cos(th), np.sin(th)
    rings = []                                       # (r, z) per ring; strips pair consecutive rings
    strips = []
    for k in range(K):
        r0 = max(rk[k], 1e-3); r1 = rk[k + 1]
        a = len(rings); rings.append((r0, h[k])); rings.append((r1, 0.0))
        strips.append((a, a + 1))                    # facet: tip ring -> valley ring
        if k + 1 < K:
            b = len(rings); rings.append((r1, 0.0)); rings.append((r1, h[k + 1]))
            strips.append((b, b + 1))                # wall: bottom -> top, faces the axis
    nr = len(rings)
    R = np.array(rings)
    verts = np.zeros((nr * SEG, 3))
    verts[:, 0] = (R[:, 0:1] * c[None, :]).ravel()
    verts[:, 1] = (R[:, 0:1] * s_[None, :]).ravel()
    verts[:, 2] = np.repeat(R[:, 1], SEG)
    i = np.arange(SEG); j = (i + 1) % SEG
    quads = []
    for a, b in strips:
        A = a * SEG; B = b * SEG
        quads.append(np.stack([A + i, B + i, B + j, A + j], 1))
    quads = np.concatenate(quads)
    # rim (outward) and flat face (down)
    base = len(verts)
    rim_top = np.stack([RMAX * c, RMAX * s_, np.zeros(SEG)], 1)
    rim_bot = np.stack([RMAX * c, RMAX * s_, np.full(SEG, -O.T)], 1)
    flat = np.stack([RMAX * c, RMAX * s_, np.full(SEG, -O.T)], 1)
    centre = np.array([[0, 0, -O.T]])
    verts = np.concatenate([verts, rim_bot, rim_top, flat, centre])
    RB, RT, FL, CE = base, base + SEG, base + 2 * SEG, base + 3 * SEG
    quads = np.concatenate([quads, np.stack([RB + i, RB + j, RT + j, RT + i], 1)])
    tris = np.stack([np.full(SEG, CE), FL + j, FL + i], 1)
    ob = mesh_from_np("FresnelLens", verts, quads, tris, smooth=True)
    if FACETS == "curved":
        # per-vertex normals: facet rings get the asphere's normal at their radius (so the shading normal varies
        # across each facet exactly as a curved facet would); walls face the axis; rim outward; flat face down
        nrm = np.zeros((len(verts), 3))
        kind = []
        for a, b in strips:
            kind.append((a, b))
        ring_kind = np.zeros(nr, int)                  # 0 facet, 1 wall
        for idx, (a, b) in enumerate(strips):
            if R[a, 0] == R[b, 0]:
                ring_kind[a] = ring_kind[b] = 1
        g = O.facet_tilt(R[:, 0])
        rr = np.repeat(R[:, 0], SEG); gg = np.repeat(g, SEG); kk = np.repeat(ring_kind, SEG)
        cc = np.tile(c, nr); ss = np.tile(s_, nr)
        nf = np.stack([np.sin(gg) * cc, np.sin(gg) * ss, np.cos(gg)], 1)
        nw = np.stack([-cc, -ss, np.zeros_like(cc)], 1)
        nrm[:nr * SEG] = np.where(kk[:, None] == 1, nw, nf)
        nrm[RB:RB + SEG] = np.stack([c, s_, np.zeros(SEG)], 1)
        nrm[RT:RT + SEG] = np.stack([c, s_, np.zeros(SEG)], 1)
        nrm[FL:FL + SEG] = (0, 0, -1); nrm[CE] = (0, 0, -1)
        ob.data.normals_split_custom_set_from_vertices(nrm.tolist())
    print(f"lens ({FACETS} facets): {len(verts):,} verts, {len(quads) + len(tris):,} faces")
    return ob

def glass(name, ior):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); g = nt.nodes.new("ShaderNodeBsdfRefraction" if REFR else "ShaderNodeBsdfGlass")
    g.inputs["Roughness"].default_value = 0.0; g.inputs["IOR"].default_value = ior
    nt.links.new(g.outputs[0], out.inputs[0])
    return m, g

def black(name, refl=0.02):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); d = nt.nodes.new("ShaderNodeBsdfDiffuse")
    d.inputs["Color"].default_value = (refl, refl, refl, 1)
    nt.links.new(d.outputs[0], out.inputs[0])
    return m

def panel_material(img):
    m = bpy.data.materials.new("PanelEmission"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img; tex.interpolation = "Closest"; tex.extension = "CLIP"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = 1.0
    nt.links.new(tex.outputs["Color"], sep.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs[0])
    return m, nt, sep, em

def quad(name, x0, x1, y0, y1, z, mat, uv=False, flip=False):
    v = np.array([[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]], float)
    f = np.array([[0, 3, 2, 1]] if flip else [[0, 1, 2, 3]])
    ob = mesh_from_np(name, v, quads=f, smooth=False)
    if uv:
        me = ob.data; lay = me.uv_layers.new(name="UVMap")
        uvs = {0: (0, 0), 1: (1, 0), 2: (1, 1), 3: (0, 1)}
        for li, l in enumerate(me.loops):
            lay.data[li].uv = uvs[l.vertex_index]
    ob.data.materials.append(mat)
    return ob

def main():
    t0 = time.time()
    sc = fresh()
    lens = build_lens()
    gmat, gnode = glass("PMMA", float(O.N_D)); lens.data.materials.append(gmat)
    img = bpy.data.images.load(os.path.join(HERE, "testframe.png")); img.colorspace_settings.name = "sRGB"
    pmat, pnt, sep, em = panel_material(img)
    zp = O.Z_PANEL
    quad("PanelCrop", -40, 40, -20, 20, zp, pmat, uv=True)                    # faces +z (toward the lens)
    blk = black("Black")
    quad("PanelRest", -61, 61, -34.3, 34.3, zp - 0.05, blk)
    # housing: four walls and a floor, matte black, open at the lens
    for nm, verts in (("WallN", [[-170, 170, zp - 5], [170, 170, zp - 5], [170, 170, -O.T - 1], [-170, 170, -O.T - 1]]),
                      ("WallS", [[170, -170, zp - 5], [-170, -170, zp - 5], [-170, -170, -O.T - 1], [170, -170, -O.T - 1]]),
                      ("WallE", [[170, 170, zp - 5], [170, -170, zp - 5], [170, -170, -O.T - 1], [170, 170, -O.T - 1]]),
                      ("WallW", [[-170, -170, zp - 5], [-170, 170, zp - 5], [-170, 170, -O.T - 1], [-170, -170, -O.T - 1]]),
                      ("Floor", [[-170, -170, zp - 5], [170, -170, zp - 5], [170, 170, zp - 5], [-170, 170, zp - 5]])):
        if NOWALLS:
            continue
        ob = mesh_from_np(nm, np.array(verts, float), quads=np.array([[0, 1, 2, 3]]), smooth=False)
        ob.data.materials.append(blk)
    cam_d = bpy.data.cameras.new("Eye"); cam = bpy.data.objects.new("Eye", cam_d)
    sc.collection.objects.link(cam); sc.camera = cam
    cam.location = (0, 0, O.EYE_Z * S); cam.rotation_euler = (0, 0, 0)
    cam_d.sensor_fit = "HORIZONTAL"; cam_d.sensor_width = 36.0
    cam_d.lens = 18.0 / math.tan(math.radians(HFOV / 2))
    cam_d.clip_start = 0.001; cam_d.clip_end = 100.0
    d_img = abs(O.paraxial_v()) + O.EYE_Z
    print(f"build {time.time() - t0:.1f}s; focal {cam_d.lens:.1f} mm; focus {d_img:.0f} mm")
    chans = (("R", 0.620, "Red"), ("G", 0.530, "Green"), ("B", 0.450, "Blue"))
    results = {}
    for mode in (("pinhole", "eye") if not ONLY else (ONLY,)):
        if mode == "eye":
            cam_d.dof.use_dof = True
            cam_d.dof.focus_distance = (FOCUS or d_img) * S
            cam_d.dof.aperture_fstop = cam_d.lens / (2 * 2.0)          # radius = lens/(2 fstop) mm = 2 mm: a 4 mm pupil
            cam_d.dof.aperture_blades = 0
        else:
            cam_d.dof.use_dof = False
        planes = []
        for ch, lam, sockname in chans:
            gnode.inputs["IOR"].default_value = float(O.n_pmma(lam))
            for l in list(pnt.links):
                if l.to_node == em and l.to_socket.name == "Color":
                    pnt.links.remove(l)
            pnt.links.new(sep.outputs[sockname], em.inputs["Color"])
            path = os.path.join(REN, f"{mode}{SUFFIX}_{ch}.exr")
            sc.render.image_settings.file_format = "OPEN_EXR"; sc.render.image_settings.color_depth = "32"
            sc.render.filepath = path
            t1 = time.time()
            bpy.ops.render.render(write_still=True)
            print(f"{mode} {ch} n={float(O.n_pmma(lam)):.4f} rendered in {time.time() - t1:.1f}s")
            im = bpy.data.images.load(path)
            px = np.empty(W_PX * H_PX * 4, np.float32); im.pixels.foreach_get(px)
            planes.append(px.reshape(H_PX, W_PX, 4)[:, :, 0].copy())
            bpy.data.images.remove(im)
        rgb = np.stack(planes, -1)
        results[mode] = rgb
        save_png(rgb, os.path.join(OUT if not TAG else REN, f"through_{mode}{SUFFIX}{TAG}.png"), sc)
        if TAG:
            continue
        if mode == "eye" and not SUFFIX:
            save_png(rgb * 16.0, os.path.join(OUT, "through_ghosts.png"), sc)
        # enlarged crops: left edge (dots, EDGE text) and centre (ribbon top, chevron)
        for nm, (fx0, fx1, fy0, fy1) in (("edge", (0.03, 0.21, 0.08, 0.40)), ("centre", (0.42, 0.58, 0.40, 0.72))):
            x0, x1 = int(fx0 * W_PX), int(fx1 * W_PX); y0, y1 = int(fy0 * H_PX), int(fy1 * H_PX)
            crop = rgb[y0:y1, x0:x1]
            crop = np.repeat(np.repeat(crop, 3, 0), 3, 1)
            save_png(crop, os.path.join(OUT, f"through_{mode}{SUFFIX}_{nm}.png"), sc)
    print(f"total {time.time() - t0:.1f}s")

def save_png(rgb, path, sc):
    h, w, _ = rgb.shape
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=False, float_buffer=True)
    px = np.ones((h, w, 4), np.float32); px[:, :, :3] = np.clip(rgb, 0, None)
    im.pixels.foreach_set(px.ravel())
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_depth = "8"
    sc.render.image_settings.color_mode = "RGB"
    im.save_render(path, scene=sc)
    bpy.data.images.remove(im)
    print("wrote", path)

main()
