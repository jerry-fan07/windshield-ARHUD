"""Cycles cross-check of the installed optics.

The simulator's geom.js traces the HUD analytically (Coddington for the mirror's two foci, a biconic paraboloid for the
mirror surface, a single reflecting plane for the windshield). This script builds the same surfaces as real meshes in
Blender and lets Cycles, an independent physically-based path tracer, form the image:

  camera at the eye -> laminated windshield (Glass BSDF, 4.96 mm, n = 1.52) -> concave mirror (true sphere or toroid,
  300 x 200 mm) -> cold-mirror fold (plane) -> the 60 x 30 mm crop of the panel, emitting a dot grid.

What it measures (all geometric, so Cycles' unpolarised Fresnel does not matter):
  - the virtual image distance from the eye, by stereo parallax: renders from eye points moved laterally and vertically
    give the sagittal and tangential image distances separately, for the toroid and for the sphere as the plan wrote it;
  - the ghost: the second (outer-surface) reflection of the laminate, its angular offset and its unpolarised brightness;
  - the field: the lit window's angular size and keystone from the nominal eye;
  - eye-box vignetting: which dots still reach the eye from nine eye-box points through the 300 x 200 mm mirror and the
    fold as the housing sizes it.

Outputs (default docs/arhud-sim/assets/cycles/): results.json, and PNGs the simulator shows beside its own numbers.

Run:  /Applications/Blender.app/Contents/MacOS/Blender -b -P optics_check.py -- [out=DIR] [samples=256] [res=1800]
      [quick=1] [surface=true|parabolic] [gpu=0]
"""
import json
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bl_common as C  # noqa: E402

ARGS = C.script_args()
OUT = C.arg(ARGS, "out", os.path.join(C.ASSETS_DIR, "cycles"))
QUICK = C.arg(ARGS, "quick", 0, int)
SAMPLES = C.arg(ARGS, "samples", 24 if QUICK else 256, int)
RES_W = C.arg(ARGS, "res", 700 if QUICK else 1800, int)
RES_H = int(round(RES_W * 9 / 16))
SURFACE = C.arg(ARGS, "surface", "true")
GPU = bool(C.arg(ARGS, "gpu", 1, int))
FOV_WIDE = 14.0             # degrees, horizontal; the traced window is about 8.7 x 4.6
FOV_ZOOM = 1.0              # for the ghost measurement
LATERAL = 0.040             # parallax baseline half-length along VIMG_RIGHT, m (the labeller de-aliases with the expected shift)
VERTICAL = 0.030            # along VIMG_UP, m
os.makedirs(OUT, exist_ok=True)

L = C.load_layout()
B = C.B
EYE = B(L["eye"])
LOOK = B(L["look"]).normalized()
RIGHT = B(L["vimg"]["RIGHT"]).normalized()
UP = B(L["vimg"]["UP"]).normalized()
EYEBOX_W, EYEBOX_H = L["eyeboxW"], L["eyeboxH"]

# ---- the panel test pattern -------------------------------------------------------------------------------------
# Image coordinates on the crop: u right (car +Z), v up (car -X), millimetres about the crop centre.
CROP_W_MM, CROP_H_MM = L["panel"]["cropZ"] * 1000, L["panel"]["cropX"] * 1000     # 60 x 30
DOT_U = [-25 + 5 * i for i in range(11)]          # 11 columns
DOT_V = [10 - 5 * j for j in range(5)]            # 5 rows, top row first
DOT_R = 0.5                                       # mm
MARK_R = 0.9                                      # the top-left dot is bigger: it fixes the image orientation
FILL = 0.02                                       # faint fill so the window outline (keystone) shows
BORDER = 0.2                                      # well under the dot threshold


def pattern_image(px_per_mm=20):
    w, h = int(CROP_W_MM * px_per_mm), int(CROP_H_MM * px_per_mm)
    ys, xs = np.mgrid[0:h, 0:w]
    u = (xs + 0.5) / px_per_mm - CROP_W_MM / 2
    v = (ys + 0.5) / px_per_mm - CROP_H_MM / 2            # row 0 is the bottom (v = -15)
    img = np.full((h, w), FILL, dtype=np.float32)
    edge = (np.abs(u) > CROP_W_MM / 2 - 0.3) | (np.abs(v) > CROP_H_MM / 2 - 0.3)
    img[edge] = BORDER
    for j, dv in enumerate(DOT_V):
        for i, du in enumerate(DOT_U):
            r = MARK_R if (i == 0 and j == 0) else DOT_R
            img[(u - du) ** 2 + (v - dv) ** 2 <= r * r] = 1.0
    rgb = np.stack([img, img, img], axis=2)
    return C.image_from_array("pattern", rgb)


# ---- mirror surfaces ---------------------------------------------------------------------------------------------
FREEFORM = None
# the freeform fit to use: freeform.json for flat glass, freeform_curved.json when the glass radii are given
# (both from freeform_mirror.py); ff=<name> overrides
_ffname = C.arg(ARGS, "ff", "freeform_curved" if (C.arg(ARGS, "glassRh", 0.0, float) > 0 or C.arg(ARGS, "glassRv", 0.0, float) > 0) else "freeform")
_ff = os.path.join(os.path.dirname(os.path.abspath(__file__)), _ffname + ".json")
if os.path.exists(_ff):
    with open(_ff) as _f:
        FREEFORM = json.load(_f)
        FREEFORM["name"] = _ffname
_MODE_SAG = {"mode": "toroid"}


def sag(u, v, Rt, Rs):
    """Surface height along the mirror normal (toward the incoming light) at lateral u, tangential v."""
    if _MODE_SAG["mode"] == "freeform" and FREEFORM:        # the optimised polynomial (freeform_mirror.py)
        return sum(ck * u ** i * v ** j for ck, (i, j) in zip(FREEFORM["coefficients"], FREEFORM["terms"]))
    if SURFACE == "parabolic":                      # what geom.js traces
        return u * u / (2 * Rs) + v * v / (2 * Rt)
    if abs(Rt - Rs) < 1e-9:                         # true sphere
        return Rt - math.sqrt(Rt * Rt - u * u - v * v)
    # true toroid: a circle of radius Rs (lateral) swept about an axis Rt from the vertex (tangential)
    return Rt - math.sqrt((Rt - Rs + math.sqrt(Rs * Rs - u * u)) ** 2 - v * v)


def radii(mode):
    if mode == "freeform" and FREEFORM:
        return FREEFORM["vertexRadii"]["Rt"], FREEFORM["vertexRadii"]["Rs"]
    return L["mirror"][mode]["Rt"], L["mirror"][mode]["Rs"]


def build_mirror(mode, nu=200, nv=140):
    _MODE_SAG["mode"] = mode
    m = L["mirror"]
    Cm, N, U, V = B(m["C"]), B(m["N"]), B(m["U"]), B(m["V"])
    Rt, Rs = radii(mode)
    W, H = m["W"], m["H"]
    verts, faces = [], []
    for j in range(nv + 1):
        v = -H / 2 + H * j / nv
        for i in range(nu + 1):
            u = -W / 2 + W * i / nu
            verts.append(Cm + U * u + V * v + N * sag(u, v, Rt, Rs))
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
    ob = C.mesh_object("concaveMirror_" + mode, verts, faces, None, C.mirror_material("MirrorCoat"), smooth=True)
    return ob


def build_fold():
    f = L["fold"]
    ff = L.get("foldFrame")
    Cf, N = B(f["C"]), B(f["N"])
    if ff:
        fu, fv = B(ff["fu"]), B(ff["fv"])
        u0, u1, v0, v1 = ff["u0"], ff["u1"], ff["v0"], ff["v1"]
    else:
        fu = B([0, 0, 1])
        fv = N.cross(fu).normalized()
        if fv.z < 0:
            fv = -fv
        u0, u1, v0, v1 = -0.09, 0.09, -0.05, 0.05
    return C.rect_object("coldMirror", Cf, fu, fv, u0, u1, v0, v1, C.mirror_material("FoldCoat"), uv=False)


def panel_pose(mode=None):
    """Panel centre and in-plane axes (simulator frame): flat for the plan, tilted and shifted for the freeform design."""
    p = L["panel"]
    C0 = np.array(p["C"], dtype=np.float64)
    th, dz = 0.0, 0.0
    if (mode or _MODE_SAG["mode"]) == "freeform" and FREEFORM:
        th = math.radians(FREEFORM.get("panelTiltDeg", 0.0))
        dz = FREEFORM.get("panelShiftMm", 0.0) / 1000
    n = np.array([-math.sin(th), math.cos(th), 0.0])
    centre = C0 + np.array([0.0, -dz, 0.0])
    u = np.array([0.0, 0.0, 1.0])
    v = np.cross(n, u)                              # in-plane fore-aft axis, +x when flat
    return centre, n, u, v


LCD_K = C.arg(ARGS, "lcdK", 0.0, float)          # viewing-angle falloff of the cell: L = L0 cos^k(theta); 0 = Lambertian (the plan)


def build_panel(image, mode=None):
    p = L["panel"]
    centre, n, u, v = panel_pose(mode)
    a = B(list(u))          # image u: car +Z
    b = B(list(-v))         # image v: toward the rear edge of the crop (the top of the image lands there)
    mat = C.emission_image_material("PanelEmit", image, strength=1.0)
    if True:
        # strength = |N . I|^k: the cell is dimmer off its normal, as an IPS panel is (k about 1) or a TN (k 2 or
        # more); k = 0 is the Lambertian cell the plan assumes (power 0 gives exactly 1, so the main runs are unchanged)
        nt = mat.node_tree
        em = next(nd for nd in nt.nodes if nd.type == "EMISSION")
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        dot = nt.nodes.new("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        nt.links.new(geo.outputs["Normal"], dot.inputs[0])
        nt.links.new(geo.outputs["Incoming"], dot.inputs[1])
        ab = nt.nodes.new("ShaderNodeMath")
        ab.operation = "ABSOLUTE"
        nt.links.new(dot.outputs["Value"], ab.inputs[0])
        pw = nt.nodes.new("ShaderNodeMath")
        pw.operation = "POWER"
        pw.name = "LCDPower"
        pw.inputs[1].default_value = LCD_K
        nt.links.new(ab.outputs[0], pw.inputs[0])
        # one-sided: a real cell emits from its front face only (Cycles emission is two-sided by default)
        front = nt.nodes.new("ShaderNodeMath")
        front.operation = "SUBTRACT"
        front.inputs[0].default_value = 1.0
        nt.links.new(geo.outputs["Backfacing"], front.inputs[1])
        side = nt.nodes.new("ShaderNodeMath")
        side.operation = "MULTIPLY"
        nt.links.new(pw.outputs[0], side.inputs[0])
        nt.links.new(front.outputs[0], side.inputs[1])
        nt.links.new(side.outputs[0], em.inputs["Strength"])
    ob = C.rect_object("panelCrop", B(list(centre)), a, b, -p["cropZ"] / 2, p["cropZ"] / 2, -p["cropX"] / 2, p["cropX"] / 2, mat)
    # the cell's front face is the one that faces the fold (the layout's panel normal); the rect's winding put it the
    # other way, which with two-sided emission went unnoticed until the one-sided cell showed the mirror seeing the back
    nw = (ob.matrix_world.to_3x3() @ ob.data.polygons[0].normal).normalized()
    if nw.dot(B(L["fold"]["C"]) - B(list(centre))) < 0:
        ob.data.flip_normals()
    return ob


GLASS_RH = C.arg(ARGS, "glassRh", 0.0, float)     # lateral curvature radius of the windshield, m (0 = flat, as the plan assumes)
GLASS_RV = C.arg(ARGS, "glassRv", 0.0, float)     # vertical (along the glass) curvature radius, m


def build_windshield(laminate=True):
    g = L["glass"]
    G, N, UPg = B(g["G"]), B(g["N"]), B(g["UP"])
    Z = B([0, 0, 1])
    a0, a1 = -0.78, 0.50          # along the glass, from the cowl to the roof
    b0, b1 = -0.72, 0.72
    mat = C.glass_material("Laminate", ior=g["nGlass"])
    if GLASS_RH > 0 or GLASS_RV > 0:
        # a curved laminate: a windshield wraps back toward the pillars and the roof, so away from the glass point its
        # surfaces come toward the cabin (along -N) by b^2/2Rh + a^2/2Rv: concave toward the driver, a weak concave
        # mirror the plan's flat-glass trace ignores. The eye's central ray still meets the plane the trace uses at G.
        na, nb = 40, 40
        def surf(t):
            verts = []
            for j in range(nb + 1):
                b = b0 + (b1 - b0) * j / nb
                for i in range(na + 1):
                    a = a0 + (a1 - a0) * i / na
                    w = (b * b / (2 * GLASS_RH) if GLASS_RH > 0 else 0) + (a * a / (2 * GLASS_RV) if GLASS_RV > 0 else 0)
                    verts.append(G + UPg * a + Z * b + N * (t - w))
            return verts
        inner, outer = surf(0.0), surf(g["T"] if laminate else 0.0)
        verts, faces = [], []
        if laminate:
            verts = inner + outer
            nvt = len(inner)
            for j in range(nb):
                for i in range(na):
                    k = j * (na + 1) + i
                    faces.append((k, k + 1, k + na + 2, k + na + 1))                            # inner (normal fixed below)
                    faces.append((nvt + k, nvt + k + na + 1, nvt + k + na + 2, nvt + k + 1))    # outer
            # the four sides
            for i in range(na):
                faces.append((i, nvt + i, nvt + i + 1, i + 1))
                top = nb * (na + 1) + i
                faces.append((top, top + 1, nvt + top + 1, nvt + top))
            for j in range(nb):
                k = j * (na + 1)
                faces.append((k, k + na + 1, nvt + k + na + 1, nvt + k))
                k = j * (na + 1) + na
                faces.append((k, nvt + k, nvt + k + na + 1, k + na + 1))
            ob = C.mesh_object("windshield", verts, faces, None, mat, smooth=True)
            recalc_normals(ob)
            return ob
        verts = inner
        for j in range(nb):
            for i in range(na):
                k = j * (na + 1) + i
                faces.append((k, k + 1, k + na + 2, k + na + 1))
        return C.mesh_object("windshieldInner", verts, faces, None, mat, smooth=True)
    if laminate:
        ob = C.slab_object("windshield", G, UPg, Z, N, a0, a1, b0, b1, 0.0, g["T"], mat)
        recalc_normals(ob)
        return ob
    return C.rect_object("windshieldInner", G, UPg, Z, a0, a1, b0, b1, mat, uv=False)


def recalc_normals(ob):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def build_housing_walls():
    """The printed housing as black walls: floor, four sides and the lid with its aperture cut out, so stray paths
    (rays that miss the fold or bounce back to the glass) die as they do in the real unit."""
    H, HL = L["housing"], L["housingLayout"]
    black = C.black_material("HousingBlack")
    xR, xF, zW, floor = HL["xR"], HL["xF"], HL["zW"], H["floor"]
    lidY = lambda x: HL["yF"] + HL["s"] * (HL["xF"] - x)
    quads = []
    for (x0, x1, z0, z1) in [(xR, HL["ax0"], -zW, zW), (HL["ax1"], xF, -zW, zW), (HL["ax0"], HL["ax1"], -zW, HL["az0"]), (HL["ax0"], HL["ax1"], HL["az1"], zW)]:
        quads.append([(x0, lidY(x0), z0), (x1, lidY(x1), z0), (x1, lidY(x1), z1), (x0, lidY(x0), z1)])
    quads.append([(xR, floor, -zW), (xF, floor, -zW), (xF, floor, zW), (xR, floor, zW)])
    for x in (xR, xF):
        quads.append([(x, floor, -zW), (x, floor, zW), (x, lidY(x), zW), (x, lidY(x), -zW)])
    for z in (-zW, zW):
        quads.append([(xR, floor, z), (xF, floor, z), (xF, lidY(xF), z), (xR, lidY(xR), z)])
    verts, faces = [], []
    for q in quads:
        k = len(verts)
        verts += [B(v) for v in q]
        faces.append((k, k + 1, k + 2, k + 3))
    return C.mesh_object("housingWalls", verts, faces, None, black, smooth=False)


def shrink(arr, k):
    h, w = arr.shape[:2]
    return arr[: h // k * k, : w // k * k].reshape(h // k, k, w // k, k, arr.shape[2]).mean(axis=(1, 3))


def build_scene(mode, laminate=True):
    sc = C.fresh_scene()
    used_gpu = C.setup_cycles(sc, samples=SAMPLES, gpu=GPU)
    C.black_world(sc)
    img = pattern_image()
    _MODE_SAG["mode"] = mode
    build_panel(img, mode)
    build_fold()
    build_mirror(mode)
    build_windshield(laminate)
    build_housing_walls()
    # a black cabin behind the eye so nothing but the HUD light reaches the camera (the world is black already;
    # this also stops the glass refracting a view of the panel from the outside into the ghost measurement)
    cam = C.pinhole_camera("eye", EYE, LOOK, UP, FOV_WIDE)
    sc.camera = cam
    return sc, cam, used_gpu


def render(sc, cam, name, offset=Vector((0, 0, 0)), fov=FOV_WIDE):
    cam.data.angle = math.radians(fov)
    C.aim_camera(cam, EYE + offset, LOOK, UP)
    path = os.path.join(OUT, "_" + name + ".exr")
    C.set_output_exr(sc, path, RES_W, RES_H)
    t0 = time.time()
    C.render_to(sc, path)
    arr = C.load_exr(path)[::-1, :, :3]                 # row 0 at the top from here on
    os.remove(path)
    print(f"  render {name}: {time.time() - t0:.1f} s, max {arr.max():.4f}", flush=True)
    return arr


# ---- measurement ---------------------------------------------------------------------------------------------------
def luminance(arr):
    return arr.mean(axis=2)


def angles(px, py, fov_deg, w, h):
    """Pixel centre -> (ax right, ay up) in radians for the pinhole camera (sensor fit horizontal)."""
    t = math.tan(math.radians(fov_deg) / 2)
    ax = math.atan(((px + 0.5) - w / 2) / (w / 2) * t)
    ay = math.atan((h / 2 - (py + 0.5)) / (w / 2) * t)
    return ax, ay


def blobs(lum, thresh, min_area=3):
    """Connected components above thresh: intensity-weighted centroid (px), area, sum, peak."""
    mask = lum > thresh
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    ys, xs = np.nonzero(mask)
    out = []
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = True
        pts = []
        while stack:
            y, x = stack.pop()
            pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    stack.append((yy, xx))
        if len(pts) < min_area:
            continue
        p = np.array(pts)
        wgt = lum[p[:, 0], p[:, 1]]
        s = wgt.sum()
        out.append({"cx": float((p[:, 1] * wgt).sum() / s), "cy": float((p[:, 0] * wgt).sum() / s), "area": int(len(pts)), "sum": float(s), "peak": float(wgt.max())})
    return out


def find_dots(arr, fov_deg, rel_thresh=0.5):
    """Dot images: blobs above half the peak (the border line sits at 20%), at least a tenth of a nominal dot."""
    lum = luminance(arr)
    peak = float(lum.max())
    if peak <= 0:
        return []
    if fov_deg == FOV_WIDE:
        # a tenth of a nominal dot image: radius = DOT_R x magnification / image distance, in pixels
        r_rad = DOT_R * 1e-3 * L["params"]["raw"]["M2"] / (L["mirror"]["eyeToMirror"] - L["mirror"]["toroid"]["vt"])
        r_px = r_rad * arr.shape[1] / math.radians(fov_deg)
        min_area = max(3, int(0.1 * math.pi * r_px * r_px))
    else:
        min_area = 3
    bl = blobs(lum, rel_thresh * peak, min_area)
    for b in bl:
        b["ax"], b["ay"] = angles(b["cx"], b["cy"], fov_deg, arr.shape[1], arr.shape[0])
    return bl


NROWS, NCOLS = len(DOT_V), len(DOT_U)
IC = NCOLS // 2        # the centre column (u = 0) sits on the optical plane of symmetry: ax = 0 at every eye on it


def label_grid(dots, shift=(0.0, 0.0), ref=None):
    """Place the dot images on the pattern grid. Returns grid[j][i] = dot or None (j = 0 is the top row v = +10 mm,
    i = 0 is u = -25 mm).

    With a reference grid (the nominal eye's labelled dots) each dot is matched to the nearest reference dot after
    removing `shift`, the expected parallax of the image for this eye position (tan units); rows that bow or tilt at
    the eye-box corners cannot confuse that. Without one (the nominal render itself) rows are clustered by ay and
    columns use the mirror symmetry about the car's vertical plane: the u = 0 column sits at ax = 0 and the column
    pitch is measured within each row, so the keystone cannot shift the labels."""
    grid = [[None] * NCOLS for _ in range(NROWS)]
    if not dots:
        return grid
    if ref is not None:
        pts = [(j, i, q["ax"], q["ay"]) for j, row in enumerate(ref) for i, q in enumerate(row) if q]
        if pts:
            P = np.array([[p[2], p[3]] for p in pts])
            Q = np.array([[q["ax"], q["ay"]] for q in dots])
            d2 = ((P[:, None, :] - P[None, :, :]) ** 2).sum(axis=2)
            np.fill_diagonal(d2, np.inf)
            tol = 0.45 * math.sqrt(d2.min())             # 45% of the closest reference spacing
            # Start from the expected parallax as a pure shift, then refine with an affine map fitted to the matches:
            # rows tilt and the pitch changes at the eye-box corners, which a shift alone cannot follow.
            A = np.array([[1.0, 0.0, shift[0]], [0.0, 1.0, shift[1]]])
            matches = []
            for it in range(3):
                pred = (np.c_[P, np.ones(len(P))] @ A.T)         # reference -> expected observed position
                matches = []
                for n, q in enumerate(Q):
                    k = int(np.argmin(((pred - q) ** 2).sum(axis=1)))
                    if math.hypot(*(pred[k] - q)) <= tol:
                        matches.append((k, n))
                if len(matches) < 6:
                    break
                src = np.array([[P[k][0], P[k][1], 1.0] for k, _ in matches])
                dst = np.array([Q[n] for _, n in matches])
                A = np.linalg.lstsq(src, dst, rcond=None)[0].T
            for k, n in matches:
                j, i = pts[k][0], pts[k][1]
                q = dots[n]
                if grid[j][i] is None or q["sum"] > grid[j][i]["sum"]:
                    grid[j][i] = q
            return grid
    ays = np.array(sorted(d["ay"] for d in dots))
    d = np.diff(ays)
    big = d[d > 0.5 * d.max()] if len(d) else np.array([])
    pr = float(np.median(big)) if len(big) else 0.02
    order = sorted(dots, key=lambda q: -q["ay"])       # top first
    rows, cur = [], [order[0]]
    for q in order[1:]:
        if cur[-1]["ay"] - q["ay"] > 0.5 * pr:
            rows.append(cur)
            cur = [q]
        else:
            cur.append(q)
    rows.append(cur)
    mark = max(dots, key=lambda q: q["area"])
    marker_row = next((k for k, r in enumerate(rows) if mark in r), None)
    for k, r in enumerate(rows):
        j = k - marker_row if marker_row is not None else k
        if not (0 <= j < NROWS):
            continue
        axs = sorted(q["ax"] for q in r)
        if len(axs) >= 2:
            dd = np.diff(axs)
            pc = float(np.median(dd[dd < 1.5 * dd.min()]))
        else:
            pc = pr * 1.05
        for q in r:
            i = int(round((q["ax"] - shift[0]) / pc)) + IC
            if 0 <= i < NCOLS and (grid[j][i] is None or q["sum"] > grid[j][i]["sum"]):
                grid[j][i] = q
    return grid


def grid_angles(grid):
    return [[[math.degrees(q["ax"]), math.degrees(q["ay"])] if q else None for q in row] for row in grid]


def parallax_distance(g_minus, g_plus, baseline, axis, central=True):
    """Image distance from the eye along LOOK from two labelled grids rendered with the eye displaced by -+baseline
    along `axis` ('x': lateral, use ax; 'y': vertical, use ay). The virtual image plane is perpendicular to LOOK, so
    tan(angle) shifts by exactly 2 * baseline / D for every dot."""
    k = 0 if axis == "x" else 1
    key = "ax" if axis == "x" else "ay"
    ds, per = [], []
    for j in range(NROWS):
        row = []
        for i in range(NCOLS):
            a, b = g_minus[j][i], g_plus[j][i]
            if a is None or b is None:
                row.append(None)
                continue
            dt = math.tan(a[key]) - math.tan(b[key])
            D = 2 * baseline / dt if abs(dt) > 1e-12 else None
            row.append(round(D, 2) if D else None)
            if D and (not central or (abs(j - NROWS // 2) <= 1 and abs(i - IC) <= 1)):
                ds.append(D)
        per.append(row)
    if not ds:
        return None, per
    return {"D": float(np.median(ds)), "min": float(np.min(ds)), "max": float(np.max(ds)), "n": len(ds)}, per


def field_from_fill(arr, fov_deg):
    """The lit window from the faint fill: widths at the top and bottom edges and the height, degrees. The edges are
    medians over columns (top, bottom) and over rows near the edges (widths), so a few stray lit pixels from the
    glass's sampling noise do not stretch the outline (the first version took the first and last lit row, which
    overstated the height by 0.17 deg against the trace while the widths and the dots agreed)."""
    lum = luminance(arr)
    lit = lum[lum > 1e-6]
    if lit.size == 0:
        return None
    fill_level = float(np.percentile(lit, 50))
    mask = lum > 0.5 * fill_level
    h, w = arr.shape[:2]
    cols_lit = np.nonzero(mask.any(axis=0))[0]
    if cols_lit.size < 10:
        return None
    c0, c1 = int(cols_lit[0]), int(cols_lit[-1])
    # top and bottom: per column, the first and last lit row; median over the central 60% of the lit columns
    cc = range(c0 + (c1 - c0) * 2 // 10, c1 - (c1 - c0) * 2 // 10)
    tops, bots = [], []
    for c in cc:
        r = np.nonzero(mask[:, c])[0]
        if r.size: tops.append(r[0]); bots.append(r[-1])
    top, bot = float(np.median(tops)), float(np.median(bots))
    # widths: per row, the lit extent; median over the rows within 5% of the height from the top and from the bottom
    def width_at(r0, r1):
        ws = []
        for r in range(int(r0), int(r1) + 1):
            cols = np.nonzero(mask[r])[0]
            if cols.size: ws.append(angles(cols[-1], 0, fov_deg, w, h)[0] - angles(cols[0], 0, fov_deg, w, h)[0])
        return math.degrees(float(np.median(ws))) if ws else 0.0
    n = max(2, int((bot - top) * 0.05))
    ayt = angles(0, top, fov_deg, w, h)[1]
    ayb = angles(0, bot, fov_deg, w, h)[1]
    return {"topW": width_at(top, top + n), "botW": width_at(bot - n, bot), "height": math.degrees(ayt - ayb), "centreUpDeg": math.degrees((ayt + ayb) / 2)}


def field_survey():
    """field=1: re-measure the window outline from the nominal eye for the given modes with the median-edge measure
    (no other result touched), and store it as modes[mode].field."""
    modes = C.arg(ARGS, "modes", "toroid,sphere,freeform").split(",")
    rp = os.path.join(OUT, "results.json")
    res = json.load(open(rp))
    for mode in modes:
        if mode == "freeform":
            load_fit("freeform")
        else:
            globals()["GLASS_RH"], globals()["GLASS_RV"] = 0.0, 0.0
        sc, cam, _ = build_scene(mode, laminate=True)
        f = field_from_fill(render(sc, cam, f"field_{mode}"), FOV_WIDE)
        print(f"  {mode}: top {f['topW']:.2f} bottom {f['botW']:.2f} height {f['height']:.2f} centre {f['centreUpDeg']:+.2f} (was height {res['modes'][mode]['field']['height']:.2f})", flush=True)
        res["modes"][mode]["field"] = f
    with open(rp, "w") as fh:
        json.dump(res, fh, indent=1)
    print("fields updated in", rp, flush=True)


GHOST_DOT_R = 0.03e-3       # m: about 0.5 arcminute in the image, so the ghost 1.3 arcminutes away is a separate spot


def ghost_dot_object():
    """A tiny emitting disc on the crop centre (the panel itself goes dark for the ghost renders)."""
    centre, n, u, v = panel_pose()
    Cp = B(list(centre + 0.02e-3 * n))
    a, b = B(list(u)), B(list(-v))
    n = 24
    verts = [Cp + a * (GHOST_DOT_R * math.cos(2 * math.pi * k / n)) + b * (GHOST_DOT_R * math.sin(2 * math.pi * k / n)) for k in range(n)]
    mat = bpy.data.materials.new("GhostDot")
    nt = C._tree(mat)
    out = C._clear_tree(nt)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs[0])
    return C.mesh_object("ghostDot", verts, [tuple(range(n))], None, mat, smooth=False)


# ---- pictures -------------------------------------------------------------------------------------------------------
def picture(arr, exposure=None, flip=False):
    lum = luminance(arr)
    if exposure is None:
        # the dots saturate, the fill stays visible
        fill = np.percentile(lum[lum > 1e-6], 40) if (lum > 1e-6).any() else 1e-3
        exposure = 0.12 / max(fill, 1e-6)
    return C.tonemap(arr, exposure)


def anaglyph(a_minus, a_plus):
    lm, lp = luminance(a_minus), luminance(a_plus)
    peak = max(lm.max(), lp.max(), 1e-6)
    r = np.clip(lm / peak * 2.5, 0, 1) ** (1 / 2.2)
    c = np.clip(lp / peak * 2.5, 0, 1) ** (1 / 2.2)
    return np.stack([r, c, c], axis=2)


def montage(tiles, cols, scale=3):
    h, w = tiles[0].shape[:2]
    hs, ws = h // scale, w // scale
    rows = (len(tiles) + cols - 1) // cols
    out = np.zeros((rows * hs, cols * ws, 3), dtype=np.float32)
    for k, t in enumerate(tiles):
        small = t[:hs * scale, :ws * scale].reshape(hs, scale, ws, scale, 3).mean(axis=(1, 3))
        r, c = divmod(k, cols)
        out[r * hs:(r + 1) * hs, c * ws:(c + 1) * ws] = small
    return out


# ---- main --------------------------------------------------------------------------------------------------------------
def set_panel_image(image):
    mat = bpy.data.materials["PanelEmit"]
    for n in mat.node_tree.nodes:
        if n.type == "TEX_IMAGE":
            n.image = image


def white_image():
    return C.image_from_array("white", np.ones((int(CROP_H_MM * 4), int(CROP_W_MM * 4), 3), dtype=np.float32))


def erode(mask, r):
    m = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            m &= np.roll(np.roll(mask, dy, 0), dx, 1)
    return m


def window_radiance(arr):
    """With a uniform white panel: the radiance over the lit window's interior (its edge eroded away), in the render's
    units where the panel emits 1. Radiance is what the eye sees as luminance, and a reflection leaves it unchanged
    except for the reflectance, so this is the HUD's luminance as a fraction of the panel's, independent of the
    magnification and of any blur (which a per-dot measure is not)."""
    lum = luminance(arr)
    lit = lum[lum > 1e-6]
    if lit.size == 0:
        return None
    mask = lum > 0.3 * float(np.percentile(lit, 50))
    h, w = lum.shape
    inner = erode(mask, max(2, h // 60))
    if inner.sum() < 50:
        return None
    rows = np.nonzero(inner.any(axis=1))[0]
    cols = np.nonzero(inner.any(axis=0))[0]
    cy, cx = (rows[0] + rows[-1]) // 2, (cols[0] + cols[-1]) // 2
    r = max(2, h // 80)
    vals = lum[inner]
    return {"mean": float(vals.mean()), "centre": float(np.median(lum[cy - r:cy + r + 1, cx - r:cx + r + 1])),
            "p5": float(np.percentile(vals, 5)), "p95": float(np.percentile(vals, 95)), "pixels": int(inner.sum())}


def load_fit(name):
    global FREEFORM
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".json")) as f:
        FREEFORM = json.load(f)
        FREEFORM["name"] = name
    g = FREEFORM.get("glass", {"Rh": 0.0, "Rv": 0.0})
    globals()["GLASS_RH"], globals()["GLASS_RV"] = g["Rh"], g["Rv"]


def luminance_survey():
    """lum=1: the HUD's luminance as a fraction of the panel's, for each mirror figure, at the nominal eye and the
    nine eye-box points, for cells with viewing-angle profiles cos^k (lcdKs=0,1,2: Lambertian, IPS-like, TN-like).
    The tilted panel of the freeform figures sends the chief ray to the mirror off the cell's normal, and a real cell
    is dimmer there; this is that cost, measured. Merged into results.json under "luminance"."""
    ks = [float(k) for k in str(C.arg(ARGS, "lcdKs", "0,1,2")).split(",")]
    modes = C.arg(ARGS, "modes", "toroid,sphere,freeform,freeformCurved").split(",")
    out = {"generated": time.strftime("%Y-%m-%d %H:%M"), "lcdKs": ks, "samples": SAMPLES, "res": [RES_W, RES_H],
           "eyeboxHalf_mm": [EYEBOX_W / 2 * 1000, EYEBOX_H / 2 * 1000], "modes": {},
           "glassIncidenceDeg": math.degrees(math.acos(abs(LOOK.dot(B(L["glass"]["N"]).normalized())))), "planThetaDeg": L["glass"]["thetaI"]}
    for mode in modes:
        real_mode = mode
        if mode == "freeformCurved":
            load_fit("freeform_curved")
            real_mode = "freeform"
        elif mode == "freeform":
            load_fit("freeform")
        else:
            globals()["GLASS_RH"], globals()["GLASS_RV"] = 0.0, 0.0
        sc, cam, _ = build_scene(real_mode, laminate=True)
        set_panel_image(white_image())              # after the scene reset, which removes every image
        pw = bpy.data.materials["PanelEmit"].node_tree.nodes["LCDPower"]
        centre, n, u, v = panel_pose(real_mode)
        # the chief ray's angle off the cell's normal: panel centre -> fold centre
        fold_c = B(L["fold"]["C"])
        chief = (fold_c - B(list(centre))).normalized()
        off_axis = math.degrees(math.acos(min(1.0, abs(chief.dot(B(list(n)))))))
        entry = {"panelTiltDeg": (FREEFORM.get("panelTiltDeg", 0.0) if real_mode == "freeform" and FREEFORM else 0.0),
                 "chiefOffNormalDeg": off_axis, "glass": [GLASS_RH, GLASS_RV], "byK": {}}
        for k in ks:
            pw.inputs[1].default_value = k
            nom = window_radiance(render(sc, cam, f"lum_{mode}_k{k:g}_nominal"))
            pts = []
            for ey in (1, 0, -1):
                for ez in (-1, 0, 1):
                    dy, dz = ey * EYEBOX_H / 2, ez * EYEBOX_W / 2
                    wr = window_radiance(render(sc, cam, f"lum_{mode}_k{k:g}_{ey}_{ez}", B([0, dy, dz])))
                    pts.append({"dy_mm": dy * 1000, "dz_mm": dz * 1000, "mean": wr["mean"] if wr else 0.0, "p5": wr["p5"] if wr else 0.0})
            entry["byK"][f"{k:g}"] = {"nominal": nom, "eyebox": pts, "eyeboxMin": min(p["mean"] for p in pts), "eyeboxMax": max(p["mean"] for p in pts)}
            print(f"  {mode} k={k:g}: nominal mean {nom['mean']:.4f} (centre {nom['centre']:.4f}, p5 {nom['p5']:.4f}); eye box {entry['byK'][f'{k:g}']['eyeboxMin']:.4f} .. {entry['byK'][f'{k:g}']['eyeboxMax']:.4f}", flush=True)
        out["modes"][mode] = entry
        print(f"  {mode}: chief ray {off_axis:.1f} deg off the cell's normal", flush=True)
    rp = os.path.join(OUT, "results.json")
    res = json.load(open(rp)) if os.path.exists(rp) else {}
    res["luminance"] = out
    with open(rp, "w") as f:
        json.dump(res, f, indent=1)
    print("merged luminance into", rp, flush=True)


def build_dust_cover(t=0.002):
    """The dust cover: an uncoated glass sheet across the lid aperture, in the lid plane (optics.js puts it there),
    t thick, 10 mm larger than the aperture all round. Its two surfaces reflect about 4% each of the exit beam back
    into the housing, toward the mirror."""
    HL = L["housingLayout"]
    sl = HL["s"]
    k = math.sqrt(1 + sl * sl)
    d = Vector((1.0, -sl, 0.0)) / k           # along the lid, toward the front (simulator frame)
    n = Vector((sl, 1.0, 0.0)) / k            # lid normal, up
    apc = Vector(HL["apC"])
    a0 = -(apc.x - HL["ax0"]) * k - 0.01
    a1 = (HL["ax1"] - apc.x) * k + 0.01
    b0, b1 = HL["az0"] - 0.01, HL["az1"] + 0.01
    ob = C.slab_object("dustCover", B(list(apc)), B(list(d)), B([0, 0, 1]), B(list(n)), a0, a1, b0, b1, 0.0, t, C.glass_material("CoverGlass"))
    recalc_normals(ob)
    return ob


def stray_survey():
    """stray=1: everything lit that is not the image. A uniform white panel, a wide view from the nominal eye, every
    connected lit region found and measured against the main window (mean radiance ratio, angular offset, size), then
    the same with the concave mirror hidden and with the fold hidden, to say which path each region comes by. The
    night driver's view showed a second window above the image; this puts a number on it. Merged into results.json
    under "stray"; the picture is stray.png (log-scaled so faint regions show)."""
    fov = C.arg(ARGS, "strayFov", 30.0, float)
    mode = C.arg(ARGS, "strayMode", "toroid")
    if mode in ("freeform", "freeformCurved"):
        load_fit("freeform_curved" if mode == "freeformCurved" else "freeform")
    real_mode = "freeform" if mode == "freeformCurved" else mode
    sc, cam, _ = build_scene(real_mode, laminate=True)
    set_panel_image(white_image())
    cover = C.arg(ARGS, "cover", 0, int)
    key = C.arg(ARGS, "strayKey", "strayCover" if cover else "stray")
    if cover:
        build_dust_cover(C.arg(ARGS, "coverT", 0.002, float))
    h, w = RES_H, RES_W

    def regions(arr, rel=1e-3):
        lum = luminance(arr)
        peak = float(np.percentile(lum[lum > 1e-6], 99)) if (lum > 1e-6).any() else 1.0
        bl = blobs(lum, rel * peak, min_area=max(6, (w * h) // 40000))
        bl.sort(key=lambda b: -b["sum"])
        return lum, bl

    full = render(sc, cam, "stray_full", fov=fov)
    lum, bl = regions(full)
    if not bl:
        print("  no lit region at all", flush=True)
        return
    main = bl[0]
    mean_main = main["sum"] / main["area"]
    ax0, ay0 = angles(main["cx"], main["cy"], fov, w, h)
    px_deg2 = (fov / w) ** 2                      # solid angle per pixel, deg^2 (small-angle)

    def describe(b):
        ax, ay = angles(b["cx"], b["cy"], fov, w, h)
        return {"ratio": (b["sum"] / b["area"]) / mean_main, "peakRatio": b["peak"] / main["peak"], "offsetDeg": [math.degrees(ax - ax0), math.degrees(ay - ay0)],
                "areaDeg2": b["area"] * px_deg2, "px": [b["cx"], b["cy"]]}

    strays = [describe(b) for b in bl[1:]]
    # which path: hide the mirror, then the fold, and see which regions survive
    variants = {}
    for name, obname in (("withoutMirror", "concaveMirror_" + real_mode), ("withoutFold", "coldMirror")):
        ob = bpy.data.objects.get(obname)
        ob.hide_render = True
        arr = render(sc, cam, "stray_" + name, fov=fov)
        ob.hide_render = False
        lv, bv = regions(arr)
        variants[name] = [{"px": [b["cx"], b["cy"]], "mean": b["sum"] / b["area"]} for b in bv]
    for st in strays:
        for name, lst in variants.items():
            near = [v for v in lst if abs(v["px"][0] - st["px"][0]) < w * 0.02 and abs(v["px"][1] - st["px"][1]) < h * 0.02]
            st[name] = (max(v["mean"] for v in near) / mean_main) if near else 0.0
    out = {"generated": time.strftime("%Y-%m-%d %H:%M"), "mode": mode, "fovDeg": fov, "samples": SAMPLES, "res": [w, h], "cover": bool(cover),
           "coverT_mm": (C.arg(ARGS, "coverT", 0.002, float) * 1000 if cover else 0), "main": {"meanRadiance": mean_main, "areaDeg2": main["area"] * px_deg2}, "strays": strays, "file": key + ".png"}
    # the picture: log scale from 1e-4 of the main's mean to the main's mean, the main window's centroid marked
    lg = np.clip((np.log10(np.maximum(lum, 1e-9) / mean_main) + 4) / 4, 0, 1)
    rgb = np.stack([lg, lg, lg], axis=2).astype(np.float32)
    for st in strays:
        x, y = int(st["px"][0]), int(st["px"][1])
        rgb[max(0, y - 1):y + 2, max(0, x - 14):x + 15, :] = [1, 0.3, 0.1]
        rgb[max(0, y - 14):y + 15, max(0, x - 1):x + 2, :] = [1, 0.3, 0.1]
    C.save_png(os.path.join(OUT, key + ".png"), rgb, flip=False)
    print(f"  main window: mean radiance {mean_main:.4f}, {main['area'] * px_deg2:.1f} deg^2", flush=True)
    for st in strays:
        print(f"  stray at {st['offsetDeg'][0]:+.1f} / {st['offsetDeg'][1]:+.1f} deg: {st['ratio'] * 100:.2f}% of the main (peak {st['peakRatio'] * 100:.1f}%), {st['areaDeg2']:.2f} deg^2; without mirror {st['withoutMirror'] * 100:.2f}%, without fold {st['withoutFold'] * 100:.2f}%", flush=True)
    rp = os.path.join(OUT, "results.json")
    res = json.load(open(rp)) if os.path.exists(rp) else {}
    res[key] = out
    with open(rp, "w") as f:
        json.dump(res, f, indent=1)
    print("merged", key, "into", rp, flush=True)


def eyebox_survey():
    """eyebox=1: where the window actually clips. A uniform white panel seen from eyes moved laterally and vertically
    beyond the plan's eye box (130 x 70 mm); the lit window's pixel count and mean radiance relative to the nominal
    eye say how much of it survives at each offset. Merged into results.json under "eyeboxExtent"."""
    mode = C.arg(ARGS, "ebMode", "toroid")
    if mode == "freeform":
        load_fit("freeform")
    sc, cam, _ = build_scene(mode, laminate=True)
    set_panel_image(white_image())
    nom = window_radiance(render(sc, cam, "eb_nominal"))
    out = {"generated": time.strftime("%Y-%m-%d %H:%M"), "mode": mode, "planHalf_mm": [EYEBOX_W / 2 * 1000, EYEBOX_H / 2 * 1000], "nominalPixels": nom["pixels"], "lateral": [], "vertical": []}
    for dz in (0.05, 0.065, 0.08, 0.095, 0.11, 0.125, 0.14):
        wr = window_radiance(render(sc, cam, f"eb_z{dz:g}", B([0, 0, dz])))
        out["lateral"].append({"mm": dz * 1000, "fraction": (wr["pixels"] / nom["pixels"]) if wr else 0.0, "meanRel": (wr["mean"] / nom["mean"]) if wr else 0.0})
        print(f"  lateral {dz * 1000:.0f} mm: window {out['lateral'][-1]['fraction'] * 100:.0f}% of the nominal area, mean radiance {out['lateral'][-1]['meanRel'] * 100:.0f}%", flush=True)
    for dy in (0.025, 0.035, 0.045, 0.055, 0.07, 0.085):
        for sign in (1, -1):
            wr = window_radiance(render(sc, cam, f"eb_y{sign * dy:g}", B([0, sign * dy, 0])))
            out["vertical"].append({"mm": sign * dy * 1000, "fraction": (wr["pixels"] / nom["pixels"]) if wr else 0.0, "meanRel": (wr["mean"] / nom["mean"]) if wr else 0.0})
            print(f"  vertical {sign * dy * 1000:+.0f} mm: window {out['vertical'][-1]['fraction'] * 100:.0f}%, mean radiance {out['vertical'][-1]['meanRel'] * 100:.0f}%", flush=True)
    rp = os.path.join(OUT, "results.json")
    res = json.load(open(rp)) if os.path.exists(rp) else {}
    res["eyeboxExtent" if mode == "toroid" else "eyeboxExtent_" + mode] = out
    with open(rp, "w") as f:
        json.dump(res, f, indent=1)
    print("merged eyeboxExtent into", rp, flush=True)


def main():
    if C.arg(ARGS, "field", 0, int):
        field_survey()
        return
    if C.arg(ARGS, "eyebox", 0, int):
        eyebox_survey()
        return
    if C.arg(ARGS, "stray", 0, int):
        stray_survey()
        return
    if C.arg(ARGS, "lum", 0, int):
        luminance_survey()
        return
    t_all = time.time()
    results = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "blender": bpy.app.version_string,
        "settings": {"samples": SAMPLES, "res": [RES_W, RES_H], "fovWideDeg": FOV_WIDE, "fovZoomDeg": FOV_ZOOM, "surface": SURFACE,
                     "lateralBaseline": LATERAL, "verticalBaseline": VERTICAL, "eyebox": [EYEBOX_W, EYEBOX_H], "quick": QUICK, "glassRh": GLASS_RH, "glassRv": GLASS_RV},
        "pattern": {"dotU_mm": DOT_U, "dotV_mm": DOT_V, "dotR_mm": DOT_R, "markerR_mm": MARK_R, "fill": FILL, "ghostDotR_mm": GHOST_DOT_R * 1000},
        "layout": {"eyeToMirror": L["mirror"]["eyeToMirror"], "mirrorIncDeg": L["mirror"]["incDeg"],
                   "toroid": L["mirror"]["toroid"], "sphere": L["mirror"]["sphere"], "vid": L["vid"],
                   "ghostPerpMm": L["ghost"]["perpMm"], "ghostArcmin75": L["ghost"]["arcmin75"],
                   "fovW": math.degrees(L["fovW"]), "fovH": math.degrees(L["fovH"])},
        "modes": {},
    }
    modes = C.arg(ARGS, "modes", "toroid" if QUICK else "toroid,sphere").split(",")
    D_toroid = None
    for mode in modes:
        print(f"== {mode}", flush=True)
        sc, cam, used_gpu = build_scene(mode, laminate=True)
        results["settings"]["gpu"] = used_gpu
        R = {}
        nominal = render(sc, cam, f"{mode}_nominal")
        g0 = label_grid(find_dots(nominal, FOV_WIDE))
        R["dots"] = grid_angles(g0)
        R["dotsFound"] = sum(1 for row in g0 for q in row if q)
        R["field"] = field_from_fill(nominal, FOV_WIDE)
        C.save_png(os.path.join(OUT, f"{mode}{'_curved' if (GLASS_RH > 0 or GLASS_RV > 0) else ''}_eye.png"), shrink(picture(nominal), 2))
        # self-check of the pixel-to-angle mapping: the same dots at a narrower field must give the same angles
        g_chk = label_grid(find_dots(render(sc, cam, f"{mode}_fovcheck", fov=10.0), 10.0))
        diffs = [math.hypot(a["ax"] - b["ax"], a["ay"] - b["ay"]) for ra, rb in zip(g0, g_chk) for a, b in zip(ra, rb) if a and b]
        R["fovCheckArcmin"] = math.degrees(max(diffs)) * 60 if diffs else None
        print(f"  fov self-check: {R['fovCheckArcmin']:.3f} arcmin max over {len(diffs)} dots" if diffs else "  fov self-check: no dots", flush=True)
        # stereo parallax: lateral (sagittal plane) and vertical (tangential plane). The expected shift passed to the
        # labeller only keeps the column labels honest; the distance comes from the measured shift.
        if mode == "freeform" and FREEFORM:
            Dx = Dy = FREEFORM["targetDistance"]
        else:
            exp = L["mirror"][mode]
            Dx = L["mirror"]["eyeToMirror"] - exp["vs"]
            Dy = L["mirror"]["eyeToMirror"] - exp["vt"]
        xm = render(sc, cam, f"{mode}_xm", RIGHT * -LATERAL)
        xp = render(sc, cam, f"{mode}_xp", RIGHT * LATERAL)
        ym = render(sc, cam, f"{mode}_ym", UP * -VERTICAL)
        yp = render(sc, cam, f"{mode}_yp", UP * VERTICAL)
        gxm = label_grid(find_dots(xm, FOV_WIDE), (LATERAL / Dx, 0), g0)
        gxp = label_grid(find_dots(xp, FOV_WIDE), (-LATERAL / Dx, 0), g0)
        gym = label_grid(find_dots(ym, FOV_WIDE), (0, VERTICAL / Dy), g0)
        gyp = label_grid(find_dots(yp, FOV_WIDE), (0, -VERTICAL / Dy), g0)
        sag_d, sag_map = parallax_distance(gxm, gxp, LATERAL, "x")
        tan_d, tan_map = parallax_distance(gym, gyp, VERTICAL, "y")
        sag_all, _ = parallax_distance(gxm, gxp, LATERAL, "x", central=False)
        tan_all, _ = parallax_distance(gym, gyp, VERTICAL, "y", central=False)
        R["imageDistance"] = {"sagittal": sag_d, "tangential": tan_d, "sagittalAllDots": sag_all, "tangentialAllDots": tan_all,
                              "expectedSagittal": Dx, "expectedTangential": Dy}
        R["distanceMap"] = {"sagittal": sag_map, "tangential": tan_map}
        C.save_png(os.path.join(OUT, f"{mode}{'_curved' if (GLASS_RH > 0 or GLASS_RV > 0) else ''}_parallax.png"), shrink(anaglyph(xm, xp), 2))
        if mode == "toroid" and sag_d:
            D_toroid = sag_d["D"]
        if mode == "toroid":
            # ---- ghost: one tiny dot; the laminate shows it twice ----
            bpy.data.objects["panelCrop"].hide_render = True
            dot = ghost_dot_object()
            zoom_lam = render(sc, cam, "ghost_laminate", fov=FOV_ZOOM)
            bpy.data.objects.remove(bpy.data.objects["windshield"], do_unlink=True)
            build_windshield(laminate=False)
            zoom_one = render(sc, cam, "ghost_single", fov=FOV_ZOOM)
            bl_lam = sorted(find_dots(zoom_lam, FOV_ZOOM, rel_thresh=0.15), key=lambda b: -b["sum"])
            bl_one = sorted(find_dots(zoom_one, FOV_ZOOM, rel_thresh=0.15), key=lambda b: -b["sum"])
            if len(bl_lam) >= 2 and bl_one:
                main_single = bl_one[0]
                # the main image is the laminate blob nearest the single-surface image; the ghost is the other one
                bl_lam.sort(key=lambda b: math.hypot(b["ax"] - main_single["ax"], b["ay"] - main_single["ay"]))
                m, gh = bl_lam[0], bl_lam[1]
                R["ghost"] = {"sepArcmin": math.degrees(math.hypot(gh["ax"] - m["ax"], gh["ay"] - m["ay"])) * 60,
                              "dxArcmin": math.degrees(gh["ax"] - m["ax"]) * 60, "dyArcmin": math.degrees(gh["ay"] - m["ay"]) * 60,
                              "brightnessRatioUnpolarised": gh["sum"] / m["sum"], "mainSum": m["sum"], "ghostSum": gh["sum"],
                              "expectedArcminAtMeasuredDistance": math.degrees(L["ghost"]["perpMm"] / 1000 / (D_toroid or Dx)) * 60,
                              "blobsLaminate": len(bl_lam), "blobsSingle": len(bl_one)}
            else:
                R["ghost"] = {"error": f"found {len(bl_lam)} blobs with the laminate and {len(bl_one)} with one surface"}
            # picture: contrast-stretched crop around the two spots
            lam_l = luminance(zoom_lam)
            pk = max(lam_l.max(), 1e-9)
            pic = np.clip(lam_l / pk * 1.6, 0, 1) ** (1 / 1.8)
            pic = np.stack([pic, pic * 0.92, pic * 0.75], axis=2)
            hh, ww = pic.shape[:2]
            cy, cx = hh // 2, ww // 2
            C.save_png(os.path.join(OUT, "ghost.png"), pic[cy - hh // 4:cy + hh // 4, cx - hh // 4:cx + hh // 4])
            bpy.data.objects.remove(bpy.data.objects["windshieldInner"], do_unlink=True)
            build_windshield(laminate=True)
            bpy.data.objects.remove(dot, do_unlink=True)
            bpy.data.objects["panelCrop"].hide_render = False
            # ---- eye box: nine eye points (car Y up, Z right) ----
            if not QUICK:
                tiles, vig = [], []
                Dm = D_toroid or Dx
                for ey in (1, 0, -1):
                    for ez in (-1, 0, 1):
                        dy, dz = ey * EYEBOX_H / 2, ez * EYEBOX_W / 2
                        arr = render(sc, cam, f"eyebox_{ey}_{ez}", B([0, dy, dz]))
                        g = label_grid(find_dots(arr, FOV_WIDE), (-dz / Dm, -dy / Dm), g0)
                        vis = [[1 if q else 0 for q in row] for row in g]
                        n = sum(map(sum, vis))
                        vig.append({"dy_mm": dy * 1000, "dz_mm": dz * 1000, "visible": n, "blobs": len(find_dots(arr, FOV_WIDE)), "of": NROWS * NCOLS, "map": vis})
                        tiles.append(picture(arr))
                        print(f"  eye box dy {dy * 1000:+.0f} dz {dz * 1000:+.0f} mm: {n}/{NROWS * NCOLS} dots", flush=True)
                R["eyebox"] = vig
                C.save_png(os.path.join(OUT, "eyebox.png"), montage(tiles, 3, scale=4))
        key = mode + (f"_glassRh{GLASS_RH:g}" if GLASS_RH > 0 else "") + (f"_glassRv{GLASS_RV:g}" if GLASS_RV > 0 else "")
        R["glass"] = {"Rh": GLASS_RH, "Rv": GLASS_RV}
        if mode == "freeform" and FREEFORM:
            R["freeformFit"] = {"name": FREEFORM.get("name"), "panelTiltDeg": FREEFORM.get("panelTiltDeg", 0.0), "panelShiftMm": FREEFORM.get("panelShiftMm", 0.0), "vertexRadii": FREEFORM.get("vertexRadii")}
        results["modes"][key] = R
        print(json.dumps({k: v for k, v in R.items() if k in ("imageDistance", "field", "ghost", "dotsFound")}), flush=True)
    results["elapsedSec"] = round(time.time() - t_all, 1)
    rp = os.path.join(OUT, "results.json")
    if os.path.exists(rp):                      # keep what other scripts added (the beauty render's entry)
        try:
            with open(rp) as f:
                old = json.load(f)
            for k, v in old.items():
                if k not in results and k != "modes":
                    results[k] = v
            for m, v in (old.get("modes") or {}).items():
                results["modes"].setdefault(m, v)
        except Exception:
            pass
    with open(rp, "w") as f:
        json.dump(results, f, indent=1)
    print("wrote", os.path.join(OUT, "results.json"), f"in {results['elapsedSec']} s", flush=True)


if __name__ == "__main__":
    main()
