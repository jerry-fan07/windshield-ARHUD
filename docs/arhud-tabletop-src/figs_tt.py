"""Figures for the tabletop design. Plain inline SVG through the plan's svgkit; text inherits Helvetica Neue.
Same hue convention as the build guide (one meaning per hue, every coloured element also labelled):
  LIGHT (image light, rays) orange   DATA (topics, cables) blue   EYE purple   structure greys   GLASS blue-grey.
Geometry figures marked "to scale" are drawn from calc.py's numbers with a fixed millimetre scale."""
import math
from svgkit import Svg, fig, INK, INK2, MUTED, GRID, AXIS, SURF, GREY_T, BLUE, BLUE_T, ORANGE, ORANGE_T
import tcalc as C

LIGHT, LIGHT_T = ORANGE, ORANGE_T
DATA, DATA_T = BLUE, BLUE_T
EYEC, EYE_T = "#7a4fbf", "#efe8f8"
GLASS = "#7d9db5"
STEEL = "#a9a8a3"
DARK = "#3a3a38"
ROAD = "#5d6b77"
ROAD_T = "#e7ebee"


def note(s, x, y, text, size=10.5, fill=INK2, anchor="start", weight=400):
    s.text(x, y, text, size=size, fill=fill, anchor=anchor, weight=weight)


def dim_h(s, x1, x2, y, label, size=9.5, tick=4, above=True):
    s.line(x1, y, x2, y, stroke=INK2, sw=0.8)
    s.line(x1, y - tick, x1, y + tick, stroke=INK2, sw=0.8)
    s.line(x2, y - tick, x2, y + tick, stroke=INK2, sw=0.8)
    s.text((x1 + x2) / 2, y - 4 if above else y + 12, label, size=size, fill=INK2, anchor="middle")


def dim_v(s, x, y1, y2, label, size=9.5, tick=4, side="right"):
    s.line(x, y1, x, y2, stroke=INK2, sw=0.8)
    s.line(x - tick, y1, x + tick, y1, stroke=INK2, sw=0.8)
    s.line(x - tick, y2, x + tick, y2, stroke=INK2, sw=0.8)
    if side == "right":
        s.text(x + 6, (y1 + y2) / 2 + 3, label, size=size, fill=INK2)
    else:
        s.text(x - 6, (y1 + y2) / 2 + 3, label, size=size, fill=INK2, anchor="end")


def box(s, x, y, w, h, title, lines=(), fill=SURF, stroke=INK2, tsize=10.5, lsize=9, tcol=INK, sw=1):
    s.rect(x, y, w, h, fill=fill, stroke=stroke, sw=sw, rx=4)
    s.text(x + w / 2, y + 15, title, size=tsize, weight=650, fill=tcol, anchor="middle")
    for i, ln in enumerate(lines):
        s.text(x + w / 2, y + 29 + i * 12, ln, size=lsize, fill=INK2, anchor="middle")


def polyline(s, pts, stroke, sw=1.2, extra=""):
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    s.path(d, stroke=stroke, sw=sw, extra=extra)


# ---- Side view, to scale -------------------------------------------------------------------------------------------
class Side:
    """Bench side view: x along the viewing axis (eye at negative x), z up, origin at the glass centre. k px per mm."""
    def __init__(self, s, ox, oz, k):
        self.s, self.ox, self.oz, self.k = s, ox, oz, k

    def p(self, x, z):
        return self.ox + x * self.k, self.oz - z * self.k

    def draw_rig(self, eye_x=-C.D_EYE, road_x=C.D_GLASS, labels=True):
        s, k = self.s, self.k
        pf = -C.D_GLASS                                   # PGU face height
        # bench and PGU monitor (face up), 10 mm body
        x0, x1 = -C.MON_H / 2, C.MON_H / 2
        s.rect(*self.p(x0, pf), (x1 - x0) * k, 10 * k, fill=DARK)
        s.line(*self.p(x0 + 6, pf), *self.p(x1 - 6, pf), stroke=LIGHT, sw=2)
        by = self.p(0, pf - 10)[1]
        s.line(self.p(eye_x - 60, 0)[0], by, self.p(road_x + 60, 0)[0], by, stroke=STEEL, sw=2)
        # glass
        g = C.GLASS_FOOT / 2
        s.line(*self.p(-g, g), *self.p(g, -g), stroke=GLASS, sw=3)
        # road monitor, upright, 10 mm body, on its stand
        rx = road_x
        s.rect(*self.p(rx, C.MON_H / 2), 10 * k, C.MON_H * k, fill=DARK)
        s.line(*self.p(rx, C.MON_H / 2 - 6), *self.p(rx, -C.MON_H / 2 + 6), stroke=ROAD, sw=2)
        s.rect(*self.p(rx + 2, -C.MON_H / 2), 6 * k, (C.R_BOTTOM) * k, fill=STEEL)
        # eye
        ex, ez = self.p(eye_x, 0)
        s.circle(ex, ez, 6, fill=EYEC)
        if labels:
            note(s, ex, ez - 14, "eye or measuring camera", size=9.4, anchor="middle")
            note(s, self.p(0, pf)[0], by + 14, "PGU monitor (unit 1), face up, picture mirrored", size=9.4, anchor="middle")
            note(s, self.p(rx + 5, 0)[0], by + 27, "road monitor (unit 2), upright, on its slide", size=9.4, anchor="middle")
            note(s, self.p(-g, g)[0] - 8, self.p(-g, g)[1] - 4, f"glass {C.V['glass_w']} × {C.V['glass_w']} × {C.V['glass_t']} mm at 45°, AR face toward the viewer", size=9.4, anchor="end")

    def ray(self, xp, eye_x=-C.D_EYE, road_x=C.D_GLASS, dashed_image=True):
        """Light from the PGU point xp (mm) to the eye, and its virtual continuation to the image."""
        s = self.s
        pz = -C.D_GLASS
        img = (C.D_GLASS, -xp)                            # mirror of (xp, pz) about the plane z = -x
        # intersection of eye->image with the glass plane z = -x
        ex, ez = eye_x, 0.0
        t = (-ex) / ((img[0] - ex) + (img[1] - ez)) if (img[0] - ex) + (img[1] - ez) else 0
        hx, hz = ex + t * (img[0] - ex), ez + t * (img[1] - ez)
        s.line(*self.p(xp, pz + 0.5), *self.p(hx, hz), stroke=LIGHT, sw=1.2)
        s.line(*self.p(hx, hz), *self.p(ex, ez), stroke=LIGHT, sw=1.2)
        if dashed_image:
            s.line(*self.p(hx, hz), *self.p(img[0], img[1]), stroke=LIGHT, sw=1, extra='stroke-dasharray="4 3"')
            s.circle(*self.p(img[0], img[1]), 2.6, fill=LIGHT)
        return (hx, hz), img


@fig("t_side")
def t_side():
    W, H = 680, 372
    s = Svg(W, H, "Tabletop rig in side view, to scale")
    s.rect(0, 0, W, H, fill=SURF)
    k = 0.84
    v = Side(s, 400, 140, k)
    v.draw_rig()
    for xp in (-70.0, 0.0, 70.0):
        v.ray(xp)
    # the image plane
    s.line(*v.p(C.D_GLASS - 1, C.MON_H / 2 + 14), *v.p(C.D_GLASS - 1, -C.MON_H / 2 - 4), stroke=LIGHT, sw=0.8, extra='stroke-dasharray="2 3"')
    note(s, v.p(C.D_GLASS, C.MON_H / 2 + 26)[0] - 4, v.p(0, C.MON_H / 2 + 26)[1], "virtual image of the PGU", size=9.2, fill=LIGHT, anchor="end")
    note(s, v.p(C.D_GLASS, C.MON_H / 2 + 26)[0] - 4, v.p(0, C.MON_H / 2 + 26)[1] + 11, "lies on the road monitor's face", size=9.2, fill=LIGHT, anchor="end")
    # dimensions
    pf = -C.D_GLASS
    dim_v(s, v.p(-C.MON_H / 2 - 16, 0)[0], v.p(0, 0)[1], v.p(0, pf)[1], f"{C.V['d_glass']} mm", side="left")
    dim_h(s, v.p(0, 0)[0], v.p(C.D_GLASS, 0)[0], v.p(0, -C.MON_H / 2 - 18)[1], f"{C.V['d_glass']} mm", above=False)
    dim_h(s, v.p(-C.D_EYE, 0)[0], v.p(0, 0)[0], v.p(0, -C.GLASS_FOOT / 2 - 30)[1], f"{C.V['d_eye']} mm eye to glass centre", above=False)
    dim_v(s, v.p(C.D_GLASS + 46, 0)[0], v.p(0, -C.MON_H / 2)[1], v.p(0, pf)[1], f"{C.V['r_bottom']}", side="right")
    dim_v(s, v.p(C.GLASS_FOOT / 2 + 12, 0)[0], v.p(0, -C.GLASS_FOOT / 2)[1], v.p(0, pf)[1], f"{C.V['clear_low']} clear", side="right")
    s.circle(*v.p(0, 0), 2.2, fill=INK)
    note(s, v.p(0, 0)[0] + 6, v.p(0, 0)[1] - 6, "glass centre: origin of every rig dimension", size=8.8)
    note(s, 16, H - 10, f"Eye to image {C.V['d_img']} mm. Orange: light from three PGU points to the eye, with its virtual continuation (dashed) to the image on the road monitor's face.", size=9.2)
    return s


@fig("t_top")
def t_top():
    W, H = 680, 350
    s = Svg(W, H, "Tabletop rig in plan view, to scale")
    s.rect(0, 0, W, H, fill=SURF)
    k = 0.78
    ox, oy = 392, 165                                     # glass centre
    def p(x, y):                                          # x along the axis, y across (right positive, drawn downward)
        return ox + x * k, oy + y * k
    # PGU monitor under the glass (its short side along x)
    s.rect(*p(-C.MON_H / 2, -C.MON_W / 2), C.MON_H * k, C.MON_W * k, fill=GREY_T, stroke=STEEL, sw=1)
    note(s, *p(-C.MON_H / 2 + 4, -C.MON_W / 2 - 6), "PGU monitor, face up, under the glass", size=9)
    # glass footprint
    g = C.GLASS_FOOT / 2
    s.rect(*p(-g, -C.GLASS_W / 2), 2 * g * k, C.GLASS_W * k, fill="none", stroke=GLASS, sw=2)
    note(s, *p(-g + 4, C.GLASS_W / 2 - 6), f"glass footprint {C.V['glass_foot']} × {C.V['glass_w']} mm", size=9, fill=GLASS)
    # unreflected margins
    for sgn in (-1, 1):
        y0 = sgn * C.GLASS_W / 2
        y1 = sgn * C.MON_W / 2
        s.rect(*p(-C.MON_H / 2, min(y0, y1)), C.MON_H * k, abs(y1 - y0) * k, fill="#f0dcd6")
    note(s, *p(0, C.MON_W / 2 + 14), f"{C.V['unreflected_side']} mm of the PGU each side lies outside the glass: not reflected", size=8.8, anchor="middle")
    # HUD window on the PGU (mirrored position = centre)
    s.rect(*p(-C.WIN_H / 2, -C.WIN_W / 2), C.WIN_H * k, C.WIN_W * k, fill=LIGHT_T, stroke=LIGHT, sw=1)
    note(s, *p(0, 4), f"window {C.V['win_w']} × {C.V['win_h']} mm", size=8.8, fill=INK, anchor="middle")
    note(s, *p(0, 16), f"{C.V['win_px_w']} × {C.V['win_px_h']} px", size=8.8, fill=INK, anchor="middle")
    # road monitor
    s.rect(*p(C.D_GLASS, -C.MON_W / 2), 10 * k, C.MON_W * k, fill=DARK)
    note(s, *p(C.D_GLASS + 14, -C.MON_W / 2 + 10), "road monitor,", size=9)
    note(s, *p(C.D_GLASS + 14, -C.MON_W / 2 + 22), "upright", size=9)
    note(s, *p(C.D_GLASS + 14, -C.MON_W / 2 + 34), "(slides back", size=8.6)
    note(s, *p(C.D_GLASS + 14, -C.MON_W / 2 + 46), "for the parallax", size=8.6)
    note(s, *p(C.D_GLASS + 14, -C.MON_W / 2 + 58), "variant)", size=8.6)
    s.arrow(*p(C.D_GLASS + 20, 40), *p(C.D_GLASS + 60, 40), color=INK2, sw=1)
    note(s, *p(C.D_GLASS + 20, 56), "Δ", size=9.5)
    # eye and sightlines to the road monitor's edges
    ex, ey = p(-C.D_EYE, 0)
    s.circle(ex, ey, 6, fill=EYEC)
    note(s, ex, ey - 12, "eye", size=9, anchor="middle")
    for sgn in (-1, 1):
        s.line(ex, ey, *p(C.D_GLASS, sgn * C.MON_W / 2), stroke=EYEC, sw=0.8, extra='stroke-dasharray="3 3"')
    # loop camera above the glass's top edge
    cx, cy = p(-g - 30, C.MON_W / 2 + 46)
    s.rect(cx - 10, cy - 7, 20, 14, fill="none", stroke=DATA, sw=1.2, rx=2)
    note(s, cx - 16, cy - 2, "loop camera (later): above the glass's top edge,", size=8.6, fill=DATA, anchor="end")
    note(s, cx - 16, cy + 10, "sees the road monitor, never the reflection", size=8.6, fill=DATA, anchor="end")
    s.line(cx + 10, cy, *p(C.D_GLASS, -C.MON_W / 2 + 20), stroke=DATA, sw=0.8, extra='stroke-dasharray="3 3"')
    s.line(cx + 10, cy, *p(C.D_GLASS, C.MON_W / 2 - 20), stroke=DATA, sw=0.8, extra='stroke-dasharray="3 3"')
    # tracker webcam above the road monitor looking at the viewer
    tx, ty = p(C.D_GLASS + 5, C.MON_W / 2 + 34)
    s.rect(tx - 8, ty - 6, 16, 12, fill="none", stroke=EYEC, sw=1.2, rx=2)
    note(s, tx + 12, ty - 2, "tracker webcam on the", size=8.6, fill=EYEC)
    note(s, tx + 12, ty + 10, "road monitor's top edge,", size=8.6, fill=EYEC)
    note(s, tx + 12, ty + 22, "facing the viewer", size=8.6, fill=EYEC)
    dim_h(s, *[p(-C.MON_H / 2, 0)[0], p(C.MON_H / 2, 0)[0]], p(0, -C.MON_W / 2 - 22)[1], f"{C.V['mon_h']} mm", size=8.8)
    dim_v(s, p(C.MON_H / 2 + 26, 0)[0], p(0, -C.MON_W / 2)[1], p(0, C.MON_W / 2)[1], f"{C.V['mon_w']} mm", size=8.8)
    return s


@fig("t_flip")
def t_flip():
    W, H = 680, 230
    s = Svg(W, H, "One reflection mirrors the picture")
    s.rect(0, 0, W, H, fill=SURF)
    # left: the PGU seen from above, with the viewer at the bottom of the drawing
    s.rect(40, 40, 200, 125, fill=GREY_T, stroke=STEEL, sw=1)
    note(s, 140, 32, "PGU face, seen from above", size=9.5, anchor="middle", fill=INK)
    note(s, 140, 182, "viewer is on this side", size=9, anchor="middle")
    s.arrow(140, 176, 140, 168, color=EYEC, sw=1.2)
    s.text(140, 128, "F", size=70, weight=700, fill=LIGHT, anchor="middle", extra='transform="scale(1,-1) translate(0,-210)"')
    note(s, 54, 58, "drawn upside down:", size=8.8)
    note(s, 54, 70, "its top toward the viewer", size=8.8)
    # middle: the glass
    s.line(290, 60, 360, 160, stroke=GLASS, sw=3)
    note(s, 325, 50, "glass", size=9, anchor="middle", fill=GLASS)
    s.arrow(250, 110, 285, 110, color=LIGHT, sw=1.2)
    s.arrow(365, 110, 400, 110, color=LIGHT, sw=1.2)
    # right: the image as the eye sees it
    s.rect(420, 40, 200, 125, fill=ROAD_T, stroke=STEEL, sw=1)
    note(s, 520, 32, "what the eye sees on the road monitor's plane", size=9.5, anchor="middle", fill=INK)
    s.text(520, 128, "F", size=70, weight=700, fill=LIGHT, anchor="middle")
    note(s, 434, 58, "reads correctly", size=8.8)
    s.lines(40, 205, ["The reflection maps the PGU's near edge to the top of the image and its far edge to the bottom; left stays left.",
                      "hudd's warp pass holds the flip (a vertical mirror with the monitor's top edge away from the viewer), as B6 says."], size=9.2, fill=INK2)
    return s


@fig("t_scale")
def t_scale():
    W, H = 680, 300
    s = Svg(W, H, "Angular scale: source frame, life-size crop, HUD window")
    s.rect(0, 0, W, H, fill=SURF)
    # source frame (comma2k19) at left
    src_w, src_h, f = 1164, 874, 910.0
    ks = 0.17
    x0, y0 = 30, 50
    s.rect(x0, y0, src_w * ks, src_h * ks, fill=GREY_T, stroke=STEEL, sw=1)
    note(s, x0, y0 - 8, f"source frame: comma2k19, {src_w} × {src_h} px, f = {C.V['c2k_f']} px, {C.V['c2k_hfov']}° wide", size=9.2, fill=INK)
    crop = C.SRC_TABLE[0][6]; crop_h = crop * C.MON_PX_H / C.MON_PX_W
    cx0, cy0 = x0 + (src_w - crop) / 2 * ks, y0 + (src_h - crop_h) / 2 * ks
    s.rect(cx0, cy0, crop * ks, crop_h * ks, fill=ROAD_T, stroke=ROAD, sw=1.2)
    win = C.SRC_TABLE[0][8]; win_h = win * C.WIN_H / C.WIN_W
    wx0, wy0 = x0 + (src_w - win) / 2 * ks, y0 + (src_h / 2 - win_h * 0.1) * ks
    s.rect(wx0, wy0, win * ks, win_h * ks, fill=LIGHT_T, stroke=LIGHT, sw=1.2)
    note(s, x0, y0 + src_h * ks + 14, f"grey: life-size crop, {C.V['c2k_crop']} px across ({C.V['hfov_shown']}°)", size=8.6, fill=ROAD)
    note(s, x0, y0 + src_h * ks + 26, f"orange: the HUD window, {C.V['c2k_win']} px across ({C.V['fov_w']}°)", size=8.6, fill=LIGHT)
    # arrow
    s.arrow(x0 + src_w * ks + 14, 120, x0 + src_w * ks + 60, 120, color=INK2, sw=1.2)
    note(s, x0 + src_w * ks + 37, 108, f"× {C.V['c2k_up']}", size=9.5, anchor="middle", fill=INK)
    # monitor at right
    km = 0.085
    mx0, my0 = 330, 50
    s.rect(mx0, my0, C.MON_PX_W * km, C.MON_PX_H * km, fill=ROAD_T, stroke=ROAD, sw=1.2)
    note(s, mx0, my0 - 8, f"road monitor: {C.V['mon_px_w']} × {C.V['mon_px_h']} px, {C.V['mon_w']} × {C.V['mon_h']} mm, {C.V['hfov_shown']}° × {C.V['vfov_shown']}° from {C.V['d_img']} mm", size=9.2, fill=INK)
    ww, wh = C.WIN_PX_W * km, C.WIN_PX_H * km
    wx, wy = mx0 + (C.MON_PX_W * km - ww) / 2, my0 + C.MON_PX_H * km / 2 - wh * 0.1
    s.rect(wx, wy, ww, wh, fill=LIGHT_T, stroke=LIGHT, sw=1.2)
    note(s, wx + ww / 2, wy + wh / 2 + 4, f"HUD window {C.V['win_px_w']} × {C.V['win_px_h']} px = {C.V['win_w']} × {C.V['win_h']} mm", size=8.6, anchor="middle", fill=INK)
    note(s, wx + ww / 2, wy + wh + 12, f"{C.V['ppd']} px per degree (plan's crop: {C.V['ppd_plan']})", size=8.6, anchor="middle", fill=LIGHT)
    s.lines(30, 240, [f"Life size: the monitor subtends at the eye the angle the crop subtended at the camera. One monitor pixel is {C.V['px_arcmin']}′;",
                      f"one comma2k19 pixel becomes {C.V['c2k_up']} monitor pixels ({C.V['c2k_px_mm']} mm, {C.V['c2k_px_arcmin']}′), soft at the eye, but perception runs on the",
                      f"source. The comma three camera needs only × {C.V['c3_up']}; a MetaDrive render is made at the monitor's field and is not scaled."], size=9, fill=INK2)
    return s


@fig("t_lum")
def t_lum():
    W, H = 680, 250
    s = Svg(W, H, "Luminance at the eye through the glass, and the plan conditions the bench can reproduce")
    s.rect(0, 0, W, H, fill=SURF)
    rows = [
        ("road monitor white, through the glass", C.L_ROAD_WHITE, ROAD),
        (f"sunlit asphalt in the clip ({C.V['asphalt_pct']}% of white, assumed)", C.L_ASPHALT, ROAD),
        ("PGU white, reflected by the glass", C.L_HUD_EYE, LIGHT),
        (f"PGU at gain {C.V['g_bl_sky']}: design backlight over a noon sky (ratio {C.V['cr_bl_sky']})", C.L_HUD_EYE * C.COND_TABLE[1][4], LIGHT),
        (f"PGU at gain {C.V['g_plan_min']}: the plan's minimum over the sky (ratio {C.V['cr_plan_min']})", C.L_HUD_EYE * C.COND_TABLE[0][4], LIGHT),
        (f"PGU at gain {C.V['g_bl_road']}: design backlight over asphalt (ratio {C.V['cr_bl_road']})", C.L_HUD_EYE * C.COND_TABLE[2][4], LIGHT),
        (f"PGU at gain {C.V['g_s1_sky']}: this monitor as the Stage 1 PGU over the sky (ratio {C.V['cr_s1_sky']})", C.L_HUD_EYE * C.COND_TABLE[3][4], LIGHT),
    ]
    x0, w, y, rh = 300, 340, 34, 26
    scale = w / 900.0
    s.line(x0, y - 8, x0, y + rh * len(rows) - 6, stroke=AXIS, sw=0.8)
    for t in (0, 200, 400, 600, 800):
        s.line(x0 + t * scale, y - 8, x0 + t * scale, y + rh * len(rows) - 6, stroke=GRID, sw=0.6)
        note(s, x0 + t * scale, y + rh * len(rows) + 6, f"{t}", size=8.4, anchor="middle")
    note(s, x0 + w / 2, y + rh * len(rows) + 20, "cd/m² at the eye", size=8.8, anchor="middle")
    for i, (label, val, col) in enumerate(rows):
        yy = y + i * rh
        s.rect(x0, yy, max(val * scale, 1.5), 12, fill=col, rx=2)
        note(s, x0 - 8, yy + 10, label, size=8.4, anchor="end", fill=INK)
        note(s, x0 + max(val * scale, 1.5) + 5, yy + 10, f"{val:,.0f}", size=8.4, fill=INK2)
    s.lines(16, 14, ["Vendor figures (1,200 cd/m² white, 70/30 glass); both monitors and the glass are metered in T-G before any gain is trusted."], size=9.2, fill=INK2)
    return s


@fig("t_parallax")
def t_parallax():
    W, H = 680, 260
    s = Svg(W, H, "Parallax variant: the road monitor slid back by Δ, seen from above")
    s.rect(0, 0, W, H, fill=SURF)
    k = 0.62
    ex0, ey0 = 60, 150                                    # nominal eye
    img_x = ex0 + C.D_IMG * k
    dl = 120.0                                            # drawn offset, exaggerated for the figure
    road_x = img_x + dl * k
    # planes
    s.line(img_x, 40, img_x, 230, stroke=LIGHT, sw=2)
    note(s, img_x - 6, 32, "PGU's image plane", size=9, anchor="end", fill=LIGHT)
    s.line(road_x, 40, road_x, 230, stroke=ROAD, sw=3)
    note(s, road_x + 6, 32, "road monitor, slid back by Δ", size=9, anchor="start", fill=ROAD)
    dim_h(s, img_x, road_x, 240, "Δ", size=9.5)
    # a road point and two eyes
    py = 110
    s.circle(road_x, py, 4, fill=ROAD)
    note(s, road_x + 8, py + 4, "a point of the road picture", size=8.8, fill=ROAD)
    for sgn, lab in ((0, "nominal eye"), (1, f"eye shifted {C.V['sway']} mm")):
        ey = ey0 + sgn * C.SWAY * k
        s.circle(ex0, ey, 6, fill=EYEC)
        note(s, ex0 + 10, ey + 4, lab, size=8.8, fill=EYEC)
        s.line(ex0, ey, road_x, py, stroke=EYEC, sw=0.9, extra='stroke-dasharray="4 3"' if sgn else "")
        # crossing of the image plane
        t = (img_x - ex0) / (road_x - ex0)
        cy = ey + t * (py - ey)
        s.circle(img_x, cy, 3.5, fill=LIGHT)
        if sgn:
            s.line(img_x + 6, cy, img_x + 6, py + (cy - py) * 0, stroke=INK2, sw=0.8)
    t = (img_x - ex0) / (road_x - ex0)
    cy0 = ey0 + t * (py - ey0); cy1 = (ey0 + C.SWAY * k) + t * (py - (ey0 + C.SWAY * k))
    dim_v(s, img_x - 14, cy0, cy1, "the mark must move", size=8.6, side="left")
    s.lines(300, 196, [f"Angle per {C.V['sway']} mm of sway: {C.V['sway']} mm × (1/{C.V['d_img_m']} m − 1/({C.V['d_img_m']} m + Δ)).",
                       f"Δ = {C.V['delta_20']} mm reproduces the car's 7.5 m image against a 20 m road point ({C.V['par_20']}°);",
                       f"Δ = {C.V['delta_inf']} mm, the road at infinity ({C.V['par_inf']}°). Δ = 300 mm is {C.V['par_300']}°, far past the car."], size=9, fill=INK2)
    return s


@fig("t_chain")
def t_chain():
    W, H = 680, 330
    s = Svg(W, H, "Processes and topics on the bench")
    s.rect(0, 0, W, H, fill=SURF)
    # sources
    box(s, 16, 20, 130, 74, "road source", ["comma2k19 segment,", "openpilot route, MetaDrive", "render, phone clip, camera"], fill=GREY_T)
    box(s, 16, 116, 130, 58, "calibration.yaml", ["camera model, plane,", "homography, gains, flip"], fill=GREY_T)
    # roadsrc
    box(s, 180, 20, 150, 74, "roadsrc", ["schedules each frame to a", "vsync, shows it full screen,", "holds it until shown"], fill=DATA_T, stroke=DATA)
    s.arrow(146, 57, 178, 57, color=INK2, sw=1.2)
    # road monitor
    box(s, 180, 116, 150, 44, "road monitor (unit 2)", ["the scene, life size"], fill=ROAD_T, stroke=ROAD)
    s.arrow(255, 94, 255, 114, color=ROAD, sw=1.4)
    # topics from roadsrc
    s.arrow(330, 40, 376, 40, color=DATA, sw=1.2); note(s, 353, 34, "roadFrame", size=8.2, anchor="middle", fill=DATA)
    s.arrow(330, 80, 376, 220, color=DATA, sw=1.2); note(s, 366, 196, "ego (log speed, yaw rate), truth, display", size=8.2, fill=DATA, anchor="end")
    # perception stack
    box(s, 378, 20, 120, 40, "laned", ["lanes2d"], fill=SURF, stroke=INK2)
    box(s, 378, 70, 120, 40, "detectd", ["objects2d + tracks"], fill=SURF, stroke=INK2)
    s.arrow(440, 60, 440, 68, color=INK2, sw=0.8)
    box(s, 378, 130, 120, 54, "planed", ["lifts pixels to the car", "frame on the static plane", "(roadd on the bench)"], fill=SURF, stroke=INK2)
    s.arrow(440, 110, 440, 128, color=INK2, sw=0.8)
    box(s, 378, 204, 120, 40, "egod", ["ego at 100 Hz, log-timed"], fill=SURF, stroke=INK2)
    box(s, 378, 256, 120, 40, "headtrackd", ["eyePose from the webcam"], fill=EYE_T, stroke=EYEC)
    # hudd
    box(s, 540, 110, 124, 86, "hudd", ["age compensation,", "projection, drawing rules,", "warp (flip + homography),", "60 Hz on the PGU"], fill=LIGHT_T, stroke=LIGHT)
    s.arrow(498, 157, 538, 150, color=DATA, sw=1.2); note(s, 518, 146, "lanes, objects", size=8.2, anchor="middle", fill=DATA)
    s.arrow(498, 224, 538, 180, color=DATA, sw=1.2); note(s, 520, 214, "ego", size=8.2, anchor="middle", fill=DATA)
    s.arrow(498, 276, 538, 190, color=EYEC, sw=1.2); note(s, 530, 248, "eyePose", size=8.2, anchor="middle", fill=EYEC)
    box(s, 540, 220, 124, 44, "PGU monitor (unit 1)", ["mirrored window, rest black"], fill=LIGHT_T, stroke=LIGHT)
    s.arrow(602, 196, 602, 218, color=LIGHT, sw=1.4)
    # logd / scored
    box(s, 540, 20, 124, 70, "logd, scored", ["every topic with times;", "residuals against truth", "(MetaDrive) or modelV2"], fill=GREY_T)
    s.arrow(602, 108, 602, 92, color=INK2, sw=0.8); note(s, 610, 104, "hudStats, hudFrame", size=8.2, fill=INK2)
    s.lines(16, 296, ["Blue: ZeroMQ PUB/SUB topics (msgpack) as in the plan; roadFrame is a shared-memory ring on one host, JPEG over TCP across two.",
                      "On the bench roadsrc stands in for the camera: a frame's capture time is the moment it is on the road monitor."], size=9, fill=INK2)
    return s


@fig("t_timing")
def t_timing():
    W, H = 680, 302
    s = Svg(W, H, "Timing of one road frame through the bench, in the two sync modes")
    s.rect(0, 0, W, H, fill=SURF)
    x0, x1 = 150, 650
    ms = (x1 - x0) / 150.0                                # 150 ms across
    def X(t):
        return x0 + t * ms
    rows = [("road monitor vsync", 40), ("frame N on the road monitor", 70), ("perception on frame N", 100), ("hudd draws (60 Hz)", 130), ("PGU monitor shows", 160)]
    for lab, y in rows:
        note(s, x0 - 8, y + 4, lab, size=8.8, anchor="end", fill=INK)
        s.line(x0, y, x1, y, stroke=GRID, sw=0.8)
    for t in range(0, 151, 50):
        note(s, X(t), 204, f"{t} ms", size=8.2, anchor="middle")
        s.line(X(t), 32, X(t), 194, stroke=GRID, sw=0.6)
    for i in range(0, 10):
        s.line(X(i * 16.67), 36, X(i * 16.67), 44, stroke=INK2, sw=0.8)
    # frame N shown (scan-out ~ 16 ms, after an input lag)
    lag = 20.0
    s.rect(X(lag), 64, 16.67 * ms, 12, fill=ROAD, rx=2)
    note(s, X(lag) + 4, 60, "scan-out of frame N (T_d: the frame's capture time)", size=8.2, fill=ROAD)
    # perception
    p0, p1 = lag + 8, lag + 8 + 30
    s.rect(X(p0), 94, (p1 - p0) * ms, 12, fill=INK2, rx=2)
    note(s, X(p1) + 4, 104, "lanes, objects published", size=8.2)
    # hudd draw slots
    for i in range(0, 9):
        s.rect(X(i * 16.67), 124, 3, 12, fill=LIGHT if i * 16.67 >= p1 else AXIS, rx=1)
    hd = (int(p1 / 16.67) + 1) * 16.67
    note(s, X(hd) + 6, 134, "first slot after publish", size=8.2, fill=LIGHT)
    # PGU shows
    s.rect(X(hd + lag), 154, 16.67 * ms, 12, fill=LIGHT, rx=2)
    note(s, X(hd + lag) + 4, 150, "HUD for frame N on the PGU", size=8.2, fill=LIGHT)
    dim_h(s, X(lag), X(hd + lag), 180, "motion-to-photon on the bench", size=8.4, above=False)
    # sync mode marker
    s.rect(X(lag), 154, 16.67 * ms, 12, fill="none", stroke=LIGHT, sw=1, extra='stroke-dasharray="3 2"')
    note(s, X(lag + 16.67) + 4, 164, "dashed: sync mode, HUD N with frame N", size=8.2, fill=LIGHT)
    s.lines(16, 226, ["Live mode (solid): perception starts only once frame N is on the road monitor, so the chain is the car's chain with the camera replaced",
                      "by the monitor's scan-out; age compensation moves the drawing by the recorded speed and yaw rate over the measured age.",
                      "Sync mode (dashed): the HUD for frame N is scheduled for the same vsync as frame N, from precomputed perception: a zero-latency",
                      "baseline whose only errors are calibration, lifting and drawing. Both monitors' input lags are measured in T-F and entered here."], size=9, fill=INK2)
    return s


@fig("t_calib")
def t_calib():
    W, H = 680, 250
    s = Svg(W, H, "What the measuring camera at the eye sees during rig calibration")
    s.rect(0, 0, W, H, fill=SURF)
    x0, y0, w, h = 40, 26, 380, 200
    s.rect(x0, y0, w, h, fill=ROAD_T, stroke=ROAD, sw=1.2)
    note(s, x0 + 6, y0 + 14, "road monitor through the glass: chessboard, 12 × 7, and a frame-ID strip", size=8.6, fill=ROAD)
    # chessboard
    cw, ch = 20, 20
    bx, by = x0 + 30, y0 + 30
    for i in range(12):
        for j in range(7):
            if (i + j) % 2 == 0:
                s.rect(bx + i * cw, by + j * ch, cw, ch, fill=ROAD)
    # frame-ID strip
    for i, bit in enumerate((1, 0, 1, 1, 0, 0, 1, 0)):
        s.rect(x0 + 300 + i * 9, y0 + 22, 8, 8, fill=INK if bit else SURF, stroke=INK2, sw=0.5)
    note(s, x0 + 300, y0 + 40, "8 squares = frame index", size=7.8, fill=INK2)
    # reflected ArUco-like markers from the PGU, offset by a small residual
    for (mx, my) in ((bx + 2 * cw + 3, by + 1 * ch + 2), (bx + 8 * cw + 3, by + 1 * ch + 2), (bx + 2 * cw + 3, by + 5 * ch + 2), (bx + 8 * cw + 3, by + 5 * ch + 2)):
        s.rect(mx, my, 16, 16, fill="none", stroke=LIGHT, sw=1.6)
        s.rect(mx + 4, my + 4, 8, 8, fill=LIGHT)
    note(s, x0 + 6, y0 + h - 8, "orange: the PGU's reflected markers, drawn at the chessboard's corners; the fit makes them coincide", size=8.6, fill=LIGHT)
    # timing patches
    s.rect(x0 + w - 40, y0 + h - 40, 28, 28, fill=SURF, stroke=INK2, sw=0.8)
    note(s, x0 + w - 26, y0 + h - 44, "timing patch", size=7.8, anchor="middle")
    s.lines(440, 48, ["Procedure (T-E):", "1  roadsrc shows the chessboard,", "   hudd the markers at the same", "   nominal pixels, mirrored.", "2  One photograph from the eye", "   point; detect both.", "3  Fit the homography PGU from road;", "   expect flip + unit scale.", "4  Residual ≤ 2 px RMS; store it.", "", "Coplanar planes make the fit", "independent of where the camera", "stood (T-A's parallax check)."], size=9, fill=INK2)
    return s


@fig("t_loop")
def t_loop():
    W, H = 680, 300
    s = Svg(W, H, "Camera-in-the-loop placement, side view to scale")
    s.rect(0, 0, W, H, fill=SURF)
    k = 0.72
    v = Side(s, 400, 150, k)
    v.draw_rig(labels=False)
    for xp in (-60.0, 60.0):
        v.ray(xp, dashed_image=False)
    g = C.GLASS_FOOT / 2
    cx, cz = -g - 40, g + 40
    px_, py_ = v.p(cx, cz)
    s.rect(px_ - 12, py_ - 8, 24, 16, fill="none", stroke=DATA, sw=1.4, rx=2)
    note(s, px_ - 16, py_ + 4, "loop camera, above the glass's top edge", size=9, fill=DATA, anchor="end")
    for z in (C.MON_H / 2, -C.MON_H / 2):
        s.line(px_ + 12, py_, *v.p(C.D_GLASS, z), stroke=DATA, sw=0.9, extra='stroke-dasharray="4 3"')
    ang = math.degrees(math.atan2(cz, C.D_GLASS - cx))
    note(s, 16, 96, f"The camera looks down about {ang:.0f}° at the road monitor;", size=9, fill=DATA)
    note(s, 16, 109, "a homography removes the keystone. It sits outside the", size=9, fill=INK2)
    note(s, 16, 122, "cone of rays the glass sends to the viewer: it never sees the HUD.", size=9, fill=INK2)
    return s


@fig("t_lift")
def t_lift():
    W, H = 680, 230
    s = Svg(W, H, "Lifting an image row to the ground on a static plane")
    s.rect(0, 0, W, H, fill=SURF)
    gx0, gx1, gy = 60, 640, 180
    s.line(gx0, gy, gx1, gy, stroke=INK2, sw=1.4)
    note(s, gx1, gy + 14, "road", size=9, anchor="end")
    cx, cy = 110, 60
    s.circle(cx, cy, 5, fill=INK)
    note(s, cx - 8, cy - 8, "camera", size=9, anchor="end")
    s.line(cx, cy, cx, gy, stroke=INK2, sw=0.8, extra='stroke-dasharray="3 3"')
    note(s, cx + 6, (cy + gy) / 2, "h", size=10, fill=INK)
    # optical axis pitched down by theta
    th = math.radians(6)
    ax = (cx + 420 * math.cos(th), cy + 420 * math.sin(th))
    s.line(cx, cy, *ax, stroke=AXIS, sw=1)
    note(s, ax[0] + 4, ax[1] + 4, "optical axis, pitched down by θ", size=8.8)
    # ray to the ground point
    z = 400
    gx = cx + z
    s.line(cx, cy, gx, gy, stroke=LIGHT, sw=1.4)
    s.circle(gx, gy, 4, fill=LIGHT)
    note(s, gx + 8, gy - 6, "ground point at range z", size=8.8, fill=LIGHT)
    dim_h(s, cx, gx, gy + 24, "z = h / tan(θ + α)", size=9.5, above=False)
    # image plane
    ipx = cx + 90
    s.line(ipx, cy - 40, ipx, cy + 70, stroke=INK2, sw=1)
    note(s, ipx + 4, cy - 30, "image plane, f", size=8.8)
    row_y = cy + 90 * math.tan(math.atan2(gy - cy, gx - cx))
    s.circle(ipx, row_y, 3, fill=LIGHT)
    note(s, ipx - 6, row_y + 16, "row v: α = atan((v − c_y)/f)", size=8.8, fill=INK, anchor="end")
    s.lines(372, 22, ["Lateral: y = z · (u − c_x) / f.", f"One row at the horizon end is {C.V['dz_c2k_30']} m at 30 m for the",
                      f"comma2k19 camera (f = {C.V['c2k_f']} px) and {C.V['dz_c3_30']} m for the comma",
                      f"three (f = {C.V['c3_f']} px). A 1° pitch error moves a 20 m point",
                      f"by {C.V['pitch_dz_10']} m; 0.1° by {C.V['pitch_dz_01']} m. Pitch comes from the log's",
                      "calibration or from the vanishing point of the lane lines."], size=9, fill=INK2)
    return s
