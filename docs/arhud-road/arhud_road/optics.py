"""What the optics put in front of the driver, and how the scene shows it.

Display regions, in drawing order:
  0  MetaDrive's 3-D scene (road, traffic, the cockpit built here)
  1  scene exposure: a full-window multiply that darkens the scene for dusk and night, so that the HUD (next) is not
     darkened with it; the HUD's brightness is set from luminance ratios instead (controllerd.overlay_gain)
  2  the HUD: the PGU frame on the virtual-image plane, fixed to the car, drawn with additive blending and no depth
     test. The light comes off the windshield, so it lies over everything in the view, including a car closer than
     the image distance. Its ghost (outer-surface reflection) and the unlit window's glow are drawn here too.
  10 MetaDrive's 2-D layer, where the app's panels live.

For the outside views (chase, top) the HUD region is switched off and the virtual image is shown in the world as a
translucent card with its frustum from the eye and the stretch of road the window covers.
"""
import math

import numpy as np
from panda3d.core import (Camera, CardMaker, ColorBlendAttrib, GeomVertexFormat, GeomVertexData, GeomVertexWriter,
                          GeomTriangles, Geom, GeomNode, LineSegs, NodePath, OrthographicLens, Texture,
                          TransparencyAttrib)

from panda3d.core import Shader

from . import plan as PL
from .frames import car_to_local

# One small shader for everything this module draws. MetaDrive runs Panda3D in an OpenGL core profile on macOS, where
# the built-in fallback shader ignores colour scale, so the HUD's luminance gain has to be an explicit uniform.
_VERT = """#version 330
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec4 p3d_Color;
in vec2 p3d_MultiTexCoord0;
out vec2 uv;
out vec4 vcol;
void main() { gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex; uv = p3d_MultiTexCoord0; vcol = p3d_Color; }
"""
_FRAG = """#version 330
uniform sampler2D p3d_Texture0;
uniform vec4 tint;          // flat: multiplies the colour. light: linear luminance gain (eye / adapting, scaled)
uniform float textured;     // 1: sample the texture, 0: use the vertex colour
uniform float light;        // 1: the HUD's light, added in linear terms to a background of linear level bref
uniform float bref;
in vec2 uv;
in vec4 vcol;
out vec4 color;
void main() {
  vec4 c = textured > 0.5 ? texture(p3d_Texture0, uv) : vcol;
  if (light > 0.5) {
    // The panel emits the frame's values as sRGB: linear luminance pow(c, 2.2), scaled to the scene. The framebuffer
    // holds sRGB, so the increment that adds that luminance to a background of linear level bref is
    // srgb(bref + d) - srgb(bref). Exact where the background is at the adapting level (the road); it overstates the
    // HUD a little against the brighter sky.
    vec3 d = pow(c.rgb, vec3(2.2)) * tint.rgb;
    vec3 b = vec3(max(bref, 1e-5));
    color = vec4(pow(b + d, vec3(1.0 / 2.2)) - pow(b, vec3(1.0 / 2.2)), 1.0);
  } else {
    color = c * tint;
  }
}
"""
_SHADER = None


def flat_shader(node, tint=(1, 1, 1, 1), textured=False, priority=10):
    """Put the module's shader on `node` with a tint and texture switch."""
    global _SHADER
    if _SHADER is None:
        _SHADER = Shader.make(Shader.SL_GLSL, _VERT, _FRAG)
    node.setShader(_SHADER, priority)
    node.setShaderInput("tint", tuple(float(v) for v in tint), priority=priority)
    node.setShaderInput("textured", 1.0 if textured else 0.0, priority=priority)
    node.setShaderInput("light", 0.0, priority=priority)
    node.setShaderInput("bref", 0.1, priority=priority)


def lin(c):
    """MetaDrive renders the 3-D scene in linear light and encodes it for display afterwards, so geometry colours
    meant as display values are given as their linear equivalents."""
    return tuple(max(0.0, float(v)) ** 2.2 for v in c)


def box_node(name, x0, x1, y0, y1, z0, z1, rgb):
    """Axis-aligned box in car-frame coordinates (x fwd, y left, z up) as a GeomNode in rig-local space.
    rgb is a display (sRGB) colour."""
    rgb = lin(rgb)
    fmt = GeomVertexFormat.getV3n3c4()
    vd = GeomVertexData(name, fmt, Geom.UHStatic)
    vw, nw, cw = GeomVertexWriter(vd, "vertex"), GeomVertexWriter(vd, "normal"), GeomVertexWriter(vd, "color")
    tris = GeomTriangles(Geom.UHStatic)
    faces = [((1, 0, 0), [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)]),
             ((-1, 0, 0), [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)]),
             ((0, 1, 0), [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)]),
             ((0, -1, 0), [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]),
             ((0, 0, 1), [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]),
             ((0, 0, -1), [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)])]
    i = 0
    for n, quad in faces:
        shade = 0.75 + 0.25 * max(0.0, n[2]) + 0.1 * n[0]
        for p in quad:
            vw.addData3(*car_to_local(p))
            nw.addData3(*car_to_local(n))
            cw.addData4(rgb[0] * shade, rgb[1] * shade, rgb[2] * shade, 1)
        tris.addVertices(i, i + 1, i + 2)
        tris.addVertices(i, i + 2, i + 3)
        i += 4
    g = Geom(vd)
    g.addPrimitive(tris)
    gn = GeomNode(name)
    gn.addGeom(g)
    return NodePath(gn)


def quad_node(name, pts, rgb, alpha=1.0):
    """A flat quad from four car-frame points (both sides). rgb is one colour or one per corner."""
    fmt = GeomVertexFormat.getV3c4()
    vd = GeomVertexData(name, fmt, Geom.UHStatic)
    vw, cw = GeomVertexWriter(vd, "vertex"), GeomVertexWriter(vd, "color")
    cols = [lin(c) for c in rgb] if isinstance(rgb[0], (tuple, list)) else [lin(rgb)] * 4
    for p, c in zip(pts, cols):
        vw.addData3(*car_to_local(p))
        cw.addData4(c[0], c[1], c[2], alpha)
    tris = GeomTriangles(Geom.UHStatic)
    tris.addVertices(0, 1, 2)
    tris.addVertices(0, 2, 3)
    g = Geom(vd)
    g.addPrimitive(tris)
    gn = GeomNode(name)
    gn.addGeom(g)
    np_ = NodePath(gn)
    np_.setTwoSided(True)
    return np_


class Optics:
    def __init__(self, engine, rig, plane):
        self.engine = engine
        self.rig = rig
        self.plane = plane
        win = engine.win
        # ---- the PGU frame as a texture (BGR bytes, no flip: the card's UVs are flipped) -------------------------
        self.tex = Texture("pgu-frame")
        self.tex.setup2dTexture(PL.CROP_W, PL.CROP_H, Texture.T_unsigned_byte, Texture.F_rgb8)
        # no mipmaps: the frame is re-uploaded every frame and stale mip levels showed as a pale slab when the
        # image was minified; lines are >= 6 px, so plain linear filtering holds up at the wide zoom
        self.tex.setMinfilter(Texture.FT_linear)
        self.tex.setMagfilter(Texture.FT_linear)
        self.tex.setWrapU(Texture.WM_border_color)
        self.tex.setWrapV(Texture.WM_border_color)
        self.tex.setBorderColor((0, 0, 0, 1))
        # ---- region 1: scene exposure ---------------------------------------------------------------------------
        self.dim_root = NodePath("scene-exposure")
        self.dim_root.setDepthTest(False)
        self.dim_root.setDepthWrite(False)
        lens = OrthographicLens()
        lens.setFilmSize(2, 2)
        lens.setNearFar(-10, 10)
        dcam = Camera("exposure-cam", lens)
        dcam_np = self.dim_root.attachNewNode(dcam)
        self.dim_dr = win.makeDisplayRegion()
        self.dim_dr.setSort(1)
        self.dim_dr.setCamera(dcam_np)
        cm = CardMaker("exposure")
        cm.setFrame(-1, 1, -1, 1)
        self.dim_card = self.dim_root.attachNewNode(cm.generate())
        self.dim_card.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_fbuffer_color,
                                                      ColorBlendAttrib.O_zero))
        self.dim_card.setColor(1, 1, 1, 1)
        flat_shader(self.dim_card)
        # ---- region 2: the HUD ------------------------------------------------------------------------------------
        self.hud_root = NodePath("hud-light")
        self.hud_root.setDepthTest(False)
        self.hud_root.setDepthWrite(False)
        self.hud_root.setLightOff(1)
        self.hud_cam = Camera("hud-cam", engine.cam.node().getLens())
        self.hud_cam_np = self.hud_root.attachNewNode(self.hud_cam)
        self.hud_dr = win.makeDisplayRegion()
        self.hud_dr.setSort(2)
        self.hud_dr.setCamera(self.hud_cam_np)
        self.hud_rig = self.hud_root.attachNewNode("hud-rig")
        add = ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_one, ColorBlendAttrib.O_one)
        self.vimg = self._image_card(self.hud_rig, "virtual-image")
        self.ghost = self._image_card(self.hud_rig, "ghost")
        self.black = self._image_card(self.hud_rig, "unlit-glow", textured=False)
        for n in (self.vimg, self.ghost, self.black):
            n.setAttrib(add)
            n.setShaderInput("light", 1.0, priority=10)
        self.outline = None
        self._build_outline()
        # ---- world-side pieces (region 0) --------------------------------------------------------------------------
        self.cockpit = self._build_cockpit()
        self.explain = None
        self.explain_card = None
        self.build_explain()
        self.view = "driver"
        self.mask = None

    def _image_card(self, parent, name, textured=True):
        cm = CardMaker(name)
        cm.setFrame(-0.5, 0.5, -0.5, 0.5)
        cm.setUvRange((0, 1), (1, 0))
        n = parent.attachNewNode(cm.generate())
        if textured:
            n.setTexture(self.tex)
        n.setTwoSided(True)
        flat_shader(n, textured=textured)
        return n

    def place_image(self, ghost_scale=1.0):
        """Size and place the image cards for the current window."""
        pl = self.plane
        c = car_to_local(pl.c)
        pitch = -math.degrees(PL.LOOKDOWN)
        for n in (self.vimg, self.black):
            n.setPos(*c)
            n.setHpr(0, pitch, 0)
            n.setScale(pl.w, 1, pl.h)
        g = pl.c + pl.up * PL.GHOST_PERP_M * ghost_scale
        self.ghost.setPos(*car_to_local(g))
        self.ghost.setHpr(0, pitch, 0)
        self.ghost.setScale(pl.w, 1, pl.h)
        self._build_outline()
        self.build_explain()

    def _build_outline(self):
        if self.outline is not None:
            self.outline.removeNode()
        pl = self.plane
        ls = LineSegs("window-outline")
        ls.setThickness(1.5)
        ls.setColor(0.55, 0.75, 1.0, 1)
        corners = [pl.pixel_point(0, 0), pl.pixel_point(PL.CROP_W, 0), pl.pixel_point(PL.CROP_W, PL.CROP_H),
                   pl.pixel_point(0, PL.CROP_H), pl.pixel_point(0, 0)]
        ls.moveTo(*car_to_local(corners[0]))
        for p in corners[1:]:
            ls.drawTo(*car_to_local(p))
        self.outline = self.hud_rig.attachNewNode(ls.create())
        self.outline.setColorScale(0.35, 0.35, 0.35, 1)
        self.outline.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_one,
                                                     ColorBlendAttrib.O_one))
        flat_shader(self.outline, (0.35, 0.35, 0.35, 1))
        self.outline.hide()

    def _build_cockpit(self):
        """A plain left-hand-drive cockpit: dash top with the HUD dust cover, A-pillars, roof header, mirror, the
        ZED 2i behind the mirror, and the hood beyond the glass. Car-frame numbers from the 3-D simulator's layout."""
        root = self.rig.np.attachNewNode("cockpit")
        g = PL.LAYOUT["glass"]
        bx, tx, cz, rz = g["bottomX"], g["topX"], g["cowlY"], g["roofY"]
        yl, yr = PL.CAR_CENTER_Y + 0.88, PL.CAR_CENTER_Y - 0.88
        dash = (0.13, 0.135, 0.145)
        trim = (0.09, 0.09, 0.1)
        box_node("dash", 0.30, bx + 0.02, yr, yl, cz - 0.10, cz, dash).reparentTo(root)
        box_node("binnacle", 0.42, 0.66, -0.20, 0.20, cz, cz + 0.07, dash).reparentTo(root)
        # HUD dust cover: black glass in the dash top under the glass patch, with its s-pass polariser
        dc = quad_node("dust-cover", [(0.80, 0.16, cz + 0.004), (1.05, 0.16, cz + 0.004),
                                      (1.05, -0.16, cz + 0.004), (0.80, -0.16, cz + 0.004)], (0.02, 0.025, 0.03))
        dc.reparentTo(root)
        for side, y0 in (("L", yl), ("R", yr)):
            # A-pillar: a slab from the cowl corner to the roof corner
            w = 0.10
            sgn = 1 if side == "L" else -1
            pts_in = [(bx, y0 - sgn * w, cz), (tx, y0 - sgn * (w + 0.04), rz)]
            pil = quad_node("pillar" + side, [(bx, y0, cz), (tx, y0 - sgn * 0.04, rz), pts_in[1], pts_in[0]], trim)
            pil.reparentTo(root)
            pil2 = quad_node("pillar-b" + side, [(bx - 0.06, y0, cz - 0.02), (tx - 0.06, y0 - sgn * 0.04, rz),
                                                 (tx, y0 - sgn * 0.04, rz), (bx, y0, cz)], trim)
            pil2.reparentTo(root)
        box_node("roof", tx - 0.6, tx + 0.02, yr - 0.1, yl + 0.1, rz, rz + 0.07, (0.16, 0.16, 0.17)).reparentTo(root)
        st = PL.LAYOUT.get("mirrorStalk")
        mx, my, mz = 0.36, PL.CAR_CENTER_Y, 1.30
        box_node("mirror", mx - 0.02, mx + 0.02, my - 0.13, my + 0.13, mz - 0.035, mz + 0.035, (0.06, 0.06, 0.07)).reparentTo(root)
        box_node("mirror-stalk", mx, mx + 0.03, my - 0.01, my + 0.01, mz, 1.36, trim).reparentTo(root)
        cx, cy, cz2 = PL.ROAD_CAM
        box_node("zed2i", cx - 0.03, cx + 0.003, cy - 0.0875 + 0.06, cy + 0.0875 + 0.06, cz2 - 0.016, cz2 + 0.016,
                 (0.2, 0.2, 0.22)).reparentTo(root)
        # the hood (the ego body is hidden in the driver view): darker toward the front, a sheen near the glass
        near, farc = (0.30, 0.32, 0.36), (0.13, 0.14, 0.16)
        hood = quad_node("hood", [(bx - 0.05, yl - 0.05, cz - 0.02), (2.40, yl - 0.14, cz - 0.12),
                                  (2.40, yr + 0.14, cz - 0.12), (bx - 0.05, yr + 0.05, cz - 0.02)],
                         [near, farc, farc, near])
        hood.reparentTo(root)
        root.setLightOff(1)
        flat_shader(root)
        return root

    def build_explain(self):
        """Outside-view pieces: the image as a translucent card, its frustum from the eye, the road it covers."""
        if self.explain is not None:
            self.explain.removeNode()
        root = self.rig.np.attachNewNode("explain")
        pl = self.plane
        eye = pl.eye0
        cm = CardMaker("vimg-world")
        cm.setFrame(-0.5, 0.5, -0.5, 0.5)
        cm.setUvRange((0, 1), (1, 0))
        card = root.attachNewNode(cm.generate())
        card.setTexture(self.tex)
        card.setPos(*car_to_local(pl.c))
        card.setHpr(0, -math.degrees(PL.LOOKDOWN), 0)
        card.setScale(pl.w, 1, pl.h)
        card.setTwoSided(True)
        # emitted light: additive, so the frame's black is clear
        card.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_one, ColorBlendAttrib.O_one))
        flat_shader(card, (1, 1, 1, 1), textured=True, priority=20)
        back = root.attachNewNode(cm.generate())
        back.setPos(*car_to_local(pl.c + pl.look * 0.01))
        back.setHpr(0, -math.degrees(PL.LOOKDOWN), 0)
        back.setScale(pl.w, 1, pl.h)
        back.setTwoSided(True)
        back.setTransparency(TransparencyAttrib.M_alpha)
        back.setColor(0.2, 0.35, 0.6, 0.25)
        flat_shader(back, (0.2, 0.35, 0.6, 0.25), priority=20)
        self.explain_card = card
        ls = LineSegs("frustum")
        ls.setThickness(1.5)
        corners = [pl.pixel_point(0, 0), pl.pixel_point(PL.CROP_W, 0), pl.pixel_point(PL.CROP_W, PL.CROP_H),
                   pl.pixel_point(0, PL.CROP_H)]
        ls.setColor(0.55, 0.8, 1.0, 1)
        for c in corners:
            ls.moveTo(*car_to_local(eye))
            ls.drawTo(*car_to_local(c))
        for i in range(4):
            ls.moveTo(*car_to_local(corners[i]))
            ls.drawTo(*car_to_local(corners[(i + 1) % 4]))
        # where the frustum meets a flat road
        ground = []
        for c in [corners[3], corners[2], corners[1], corners[0]]:
            d = c - eye
            t = -eye[2] / d[2] if d[2] < -1e-6 else None
            ground.append(eye + d * min(t, 90.0 / max(d[0], 1e-6)) if t else eye + d * (90.0 / max(d[0], 1e-6)))
        ls.setColor(0.4, 1.0, 0.6, 1)
        for i in range(4):
            a, b = ground[i].copy(), ground[(i + 1) % 4].copy()
            a[2] = max(a[2], 0) + 0.04
            b[2] = max(b[2], 0) + 0.04
            ls.moveTo(*car_to_local(a))
            ls.drawTo(*car_to_local(b))
        root.attachNewNode(ls.create())
        gq = [g.copy() for g in ground]
        for g in gq:
            g[2] = max(g[2], 0) + 0.03
        cov = quad_node("coverage", gq, (0.3, 1.0, 0.5), 0.22)
        cov.setTransparency(TransparencyAttrib.M_alpha)
        cov.reparentTo(root)
        eye_m = box_node("eye", -0.03, 0.03, -0.03, 0.03, PL.EYE_H - 0.03, PL.EYE_H + 0.03, (1.0, 0.85, 0.3))
        eye_m.reparentTo(root)
        root.setLightOff(1)
        flat_shader(root)
        root.setDepthWrite(False)
        root.setBin("transparent", 30)
        self.explain = root
        self.explain.show() if getattr(self, "view", "driver") != "driver" else self.explain.hide()

    # ---- per frame --------------------------------------------------------------------------------------------
    def set_view(self, view):
        self.view = view
        driver = view == "driver"
        self.hud_dr.setActive(driver)
        if self.explain is not None:
            (self.explain.hide if driver else self.explain.show)()
        (self.cockpit.show if driver else self.cockpit.hide)()

    def upload(self, frame):
        self.tex.setRamImage(frame.tobytes())

    def apply_vignette(self, frame, eye_off):
        """Darken the parts of the image the 300 mm mirror cuts off for this eye position (soft edge: pupil)."""
        pl = self.plane
        ul, ur, vb, vt = pl.visible_box(eye_off)
        if ul <= -pl.w / 2 and ur >= pl.w / 2 and vb <= -pl.h / 2 and vt >= pl.h / 2:
            self.mask = None
            return frame
        edge = 0.004 * pl.dist / PL.EYE_TO_MIRROR
        us = (np.arange(PL.CROP_W) + 0.5) / PL.CROP_W * pl.w - pl.w / 2
        vs = pl.h / 2 - (np.arange(PL.CROP_H) + 0.5) / PL.CROP_H * pl.h
        mx = np.clip((us - ul) / edge + 0.5, 0, 1) * np.clip((ur - us) / edge + 0.5, 0, 1)
        my = np.clip((vs - vb) / edge + 0.5, 0, 1) * np.clip((vt - vs) / edge + 0.5, 0, 1)
        self.mask = (mx, my)
        m = (my[:, None] * mx[None, :]).astype(np.float32)
        return (frame.astype(np.float32) * m[:, :, None]).astype(np.uint8)

    def update(self, gain, black_gain, ghost_mode, scene_scale, sky_tint, show_window, bref=0.39):
        self.hud_rig.setMat(self.rig.np.getMat(self.engine.render))
        self.hud_cam_np.setMat(self.engine.camera.getMat(self.engine.render))
        g = float(gain)
        for n in (self.vimg, self.ghost, self.black):
            n.setShaderInput("bref", float(bref), priority=10)
        self.vimg.setShaderInput("tint", (g, g, g, 1.0), priority=10)
        if ghost_mode == "off":
            self.ghost.hide()
        else:
            self.ghost.show()
            gg = g * PL.GHOST_REL
            self.ghost.setShaderInput("tint", (gg, gg, gg, 1.0), priority=10)
        b = float(black_gain)
        self.black.setShaderInput("tint", (b, b, b, 1.0), priority=10)
        s = scene_scale
        self.dim_card.setShaderInput("tint", (s * sky_tint[0], s * sky_tint[1], s * sky_tint[2], 1.0), priority=10)
        self.dim_dr.setActive(s < 0.999 or sky_tint != (1.0, 1.0, 1.0))
        (self.outline.show if show_window else self.outline.hide)()
