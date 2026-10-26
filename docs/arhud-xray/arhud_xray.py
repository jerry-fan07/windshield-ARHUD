# AR HUD x-ray display: the component list, the x-ray switching and the sidebar panel.
#
# build_scene.py embeds this file in arhud-xray.blend as the text block "arhud_xray.py" (Register ticked), so the panel
# appears when the file is opened with Python scripts allowed. render.py imports it from disk for command-line renders.
#
# Model: every object that belongs to a component carries the custom property "xr_item" (an item id). The item tree
# (ids, names, parents, categories, descriptions, facts) is the JSON text block "arhud_items.json", written by
# build_scene.py. scene.arhud.items holds one row per item with a "solid" flag. Objects whose item is solid keep their
# own materials; every other object is switched to a ghost material through an object-linked material slot (so the
# mesh data and its real materials are untouched) and stops casting shadows. Blur is a compositor pass: every real
# material writes the AOV "xr_solid" = 1, ghosts write nothing, and the compositor blurs only where the AOV is 0.
bl_info = {
    'name': 'AR HUD x-ray component display',
    'author': 'windshield-ARHUD',
    'version': (1, 0, 0),
    'blender': (4, 2, 0),
    'location': 'View3D > Sidebar > AR HUD',
    'description': 'Pick AR HUD components to show solid; the rest become x-ray ghosts, frosted, blurred or hidden',
    'category': '3D View',
}

import json
import math

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty, StringProperty
from mathutils import Vector

ITEMS_TEXT = 'arhud_items.json'
AOV = 'xr_solid'
GHOST_NAMES = {'XRAY': 'XR ghost: x-ray', 'FADE': 'XR ghost: frosted'}
COMP_GROUP = 'XR compositor'
CAMERAS = [
    ('overview', 'Overview', 'CAM Overview'),
    ('side', 'Side cutaway', 'CAM Side'),
    ('hud', 'HUD unit', 'CAM HUD unit'),
    ('footwell', 'Footwell', 'CAM Footwell'),
    ('bench', 'Bench', 'CAM Bench'),
    ('top', 'Top', 'CAM Top'),
]

FACE = 0.38
_busy = [False]
_cache = {}
_last_sel = [None]


# ---------------------------------------------------------------------------------------------------------- item data
def data():
    """The item tree from the JSON text block, cached per text revision."""
    t = bpy.data.texts.get(ITEMS_TEXT)
    if t is None:
        return {'categories': [], 'items': []}
    s = t.as_string()
    if _cache.get('src') != s:
        d = json.loads(s)
        by_id = {it['id']: it for it in d['items']}
        kids = {}
        for it in d['items']:
            kids.setdefault(it.get('parent'), []).append(it['id'])
        _cache.update(src=s, data=d, by_id=by_id, kids=kids)
    return _cache['data']


def by_id():
    data()
    return _cache.get('by_id', {})


def children(iid):
    data()
    return _cache.get('kids', {}).get(iid, [])


def descendants(iid):
    out = []
    for c in children(iid):
        out.append(c)
        out += descendants(c)
    return out


def ancestors(iid):
    out, b = [], by_id()
    p = b.get(iid, {}).get('parent')
    while p:
        out.append(p)
        p = b.get(p, {}).get('parent')
    return out


def settings(scene=None):
    return (scene or bpy.context.scene).arhud


def row_of(s, iid):
    for r in s.items:
        if r.iid == iid:
            return r
    return None


def sync_items(scene):
    """Make scene.arhud.items match the JSON (adds missing rows with their defaults, drops stale ones)."""
    s = settings(scene)
    d = data()
    have = {r.iid: r for r in s.items}
    _busy[0] = True
    try:
        for it in d['items']:
            if it['id'] not in have:
                r = s.items.add()
                r.iid = it['id']
                r.solid = bool(it.get('default', True))
        ids = {it['id'] for it in d['items']}
        for i in reversed(range(len(s.items))):
            if s.items[i].iid not in ids:
                s.items.remove(i)
        have_c = {c.cid for c in s.cats}
        for cid, _name in d['categories']:
            if cid not in have_c:
                c = s.cats.add()
                c.cid = cid
    finally:
        _busy[0] = False


# ---------------------------------------------------------------------------------------------------------- materials
GHOST_VERSION = 4


def ensure_ghosts(s=None):
    """The two ghost materials. Alpha = fill + fresnel rim; both fade for surfaces close to the camera, so a close-up
    looks through the nearby layers (roof, dash) instead of tinting the solid parts behind them, while the far outline
    of the car stays. The x-ray ghost is unlit emission, so it reads the same in EEVEE, Cycles and every light."""
    mats = {}
    tint = tuple(s.tint) if s else (0.12, 0.33, 0.70)
    op = s.opacity if s else 0.55
    for mode, name in GHOST_NAMES.items():
        m = bpy.data.materials.get(name)
        if m is None:
            m = bpy.data.materials.new(name)
        m.use_fake_user = True                      # keep the unused one (frosted) when the file is saved
        if m.get('xr_ver') != GHOST_VERSION or m.node_tree is None:
            _build_ghost(m, mode)
        nt = m.node_tree
        if mode == 'XRAY':
            nt.nodes['rimA'].outputs[0].default_value = 1.1 * op
            nt.nodes['faceA'].outputs[0].default_value = FACE * op
            nt.nodes['tint'].inputs['Color'].default_value = (*tint, 1)
            nt.nodes['tint'].inputs['Strength'].default_value = 1.0
            m.diffuse_color = (*tint, 0.18)
        else:
            nt.nodes['rimA'].outputs[0].default_value = 0.9 * op
            nt.nodes['faceA'].outputs[0].default_value = 0.30 * op
            frost = tuple(0.45 + 0.4 * c for c in tint)
            nt.nodes['tint'].inputs['Base Color'].default_value = (*frost, 1)
            m.diffuse_color = (*frost, 0.25)
        mats[mode] = m
    return mats


def _build_ghost(m, mode):
    if bpy.app.version < (5, 0, 0):
        m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links

    def node(t, loc, name=None, **kw):
        n = N.new(t)
        n.location = loc
        if name:
            n.name = name
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def math(op, loc, a=None, b=None, c=None, clamp=False):
        n = node('ShaderNodeMath', loc, operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]

    out = node('ShaderNodeOutputMaterial', (900, 0))
    mix = node('ShaderNodeMixShader', (700, 0))
    tr = node('ShaderNodeBsdfTransparent', (500, 120))
    lw = node('ShaderNodeLayerWeight', (-700, 100))
    lw.inputs['Blend'].default_value = 0.45 if mode == 'XRAY' else 0.3
    # focus fade: a ghost surface well in front of the solid parts (between them and the camera) fades, so the parts
    # are seen through it untinted; ghosts beside and behind them keep full strength. focus = centre (fx, fy, fz) and radius fr of the solid set, written by apply().
    cam = node('ShaderNodeCameraData', (-1300, -200))
    geo = node('ShaderNodeNewGeometry', (-1300, -450))
    fpos = node('ShaderNodeCombineXYZ', (-1100, -650), name='focus')
    for i, k in enumerate(('fx', 'fy', 'fz')):
        v = node('ShaderNodeValue', (-1300, -650 - 80 * i), name=k)
        L.new(v.outputs[0], fpos.inputs[i])
    fr = node('ShaderNodeValue', (-1100, -850), name='fr')
    fr.outputs[0].default_value = 1000.0
    scaled = node('ShaderNodeVectorMath', (-1100, -350), operation='SCALE')
    L.new(geo.outputs['Incoming'], scaled.inputs[0])
    L.new(cam.outputs['View Distance'], scaled.inputs['Scale'])
    campos = node('ShaderNodeVectorMath', (-900, -400), operation='ADD')
    L.new(geo.outputs['Position'], campos.inputs[0])
    L.new(scaled.outputs[0], campos.inputs[1])
    dist = node('ShaderNodeVectorMath', (-700, -450), operation='DISTANCE')
    L.new(campos.outputs[0], dist.inputs[0])
    L.new(fpos.outputs[0], dist.inputs[1])
    # ratio = how far along the way from the camera to the solid set this surface lies (scale-free, so it behaves the
    # same in an overview and in a close-up): under ~0.55 it fades, from ~0.9 on it keeps full strength
    near = math('SUBTRACT', (-500, -450), dist.outputs['Value'], fr.outputs[0])
    near = math('MAXIMUM', (-400, -450), near, 0.01)
    ratio = math('DIVIDE', (-300, -400), cam.outputs['View Distance'], near)
    fade = node('ShaderNodeMapRange', (-100, -350), name='fade', clamp=True)
    for k, v in (('From Min', 0.55), ('From Max', 0.9), ('To Min', 0.1), ('To Max', 1.0)):
        fade.inputs[k].default_value = v
    L.new(ratio, fade.inputs['Value'])
    rimA = node('ShaderNodeValue', (-500, 250), name='rimA')
    faceA = node('ShaderNodeValue', (-500, 0), name='faceA')
    rim = math('POWER', (-300, 100), lw.outputs['Facing'], 1.6 if mode == 'XRAY' else 2.0)
    rim = math('MULTIPLY', (-100, 150), rim, rimA.outputs[0])
    rim_fade = math('MULTIPLY_ADD', (-300, -250), fade.outputs['Result'], 0.5, 0.5)
    rim = math('MULTIPLY', (100, 150), rim, rim_fade)
    face = math('MULTIPLY', (-100, -50), faceA.outputs[0], fade.outputs['Result'])
    alpha = math('ADD', (300, 50), rim, face, clamp=True)
    L.new(alpha, mix.inputs[0])
    L.new(tr.outputs[0], mix.inputs[1])
    if mode == 'XRAY':
        sh = node('ShaderNodeEmission', (500, -80), name='tint')
    else:
        sh = node('ShaderNodeBsdfPrincipled', (500, -80), name='tint')
        sh.inputs['Roughness'].default_value = 0.55
    L.new(sh.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs['Surface'])
    m.surface_render_method = 'BLENDED'
    m.use_transparency_overlap = False
    m.use_backface_culling = False
    m['xr_ver'] = GHOST_VERSION


def ensure_aov(mat):
    """Real materials write AOV xr_solid = 1 so the blur pass knows what to keep sharp."""
    if mat is None or mat.name in GHOST_NAMES.values() or not mat.node_tree:
        return
    # EEVEE's blended surfaces write no render passes, so a blended part would be blurred with the ghosts; dithered
    # transparency writes them and still looks see-through once the samples settle
    if mat.surface_render_method == 'BLENDED':
        mat.surface_render_method = 'DITHERED'
    nt = mat.node_tree
    if any(n.bl_idname == 'ShaderNodeOutputAOV' for n in nt.nodes):
        return
    n = nt.nodes.new('ShaderNodeOutputAOV')
    n.aov_name = AOV
    n.inputs['Value'].default_value = 1.0
    n.location = (900, -300)


# ---------------------------------------------------------------------------------------------------------- applying state
def object_state(o, solid_ids, mode):
    iid = o.get('xr_item')
    if iid is None:
        return None
    return 'SOLID' if iid in solid_ids else mode


def set_state(o, st, ghosts):
    if o.get('xr_state') == st:
        return
    hide = st == 'HIDE'
    o.hide_render = hide
    try:
        o.hide_set(hide)
    except RuntimeError:
        pass
    if o.type in {'MESH', 'CURVE', 'FONT', 'SURFACE'}:
        g = ghosts.get(st)
        for slot in o.material_slots:
            if g is not None:
                slot.link = 'OBJECT'
                slot.material = g
            else:
                slot.link = 'DATA'
        o.visible_shadow = st == 'SOLID'
    o['xr_state'] = st


def set_pickable(scene):
    """With Click to focus on, ghosts cannot be selected, so a click goes through the x-ray shell to the solid part."""
    focus = settings(scene).follow_selection
    for o in scene.objects:
        if o.type != 'MESH':
            continue
        st = o.get('xr_state')
        if st is not None:
            want = focus and st != 'SOLID'
            if o.hide_select != want:
                o.hide_select = want


def apply(scene=None):
    scene = scene or bpy.context.scene
    s = settings(scene)
    solid = {r.iid for r in s.items if r.solid}
    ghosts = ensure_ghosts(s)
    for o in scene.objects:
        st = object_state(o, solid, s.mode)
        if st is not None:
            set_state(o, st, ghosts)
    set_focus(scene, solid, ghosts)
    set_pickable(scene)


def set_focus(scene, solid, ghosts):
    """Tell the ghost shaders where the solid parts are (centre and radius of their bounds)."""
    objs = [o for o in scene.objects if o.type == 'MESH' and o.get('xr_item') in solid]
    lo, hi = bounds(objs)
    if lo is None:
        c, r = Vector((0, 0, 0)), 1000.0
    else:
        c, r = (lo + hi) / 2, max(0.03, (hi - lo).length / 2)
    for m in ghosts.values():
        n = m.node_tree.nodes
        for k, v in zip(('fx', 'fy', 'fz'), c):
            n[k].outputs[0].default_value = v
        n['fr'].outputs[0].default_value = r


def set_solid(scene, ids, value=True, others=None):
    """Set the solid flag of ids (and their descendants); others=True/False sets every other item too."""
    s = settings(scene)
    want = set()
    for i in ids:
        want.add(i)
        want.update(descendants(i))
    _busy[0] = True
    try:
        for r in s.items:
            if r.iid in want:
                r.solid = value
            elif others is not None:
                r.solid = others
        _fix_parents(s)
    finally:
        _busy[0] = False
    apply(scene)


def _fix_parents(s):
    """A parent row is ticked when all its children are."""
    rows = {r.iid: r for r in s.items}

    def solid_of(iid):
        k = children(iid)
        if not k:
            return rows[iid].solid if iid in rows else False
        vals = [solid_of(c) for c in k]   # visit every subtree (all() would stop at the first False)
        v = all(vals)
        if iid in rows:
            rows[iid].solid = v
        return v
    for it in data()['items']:
        if not it.get('parent'):
            solid_of(it['id'])


def isolate(scene, ids):
    set_solid(scene, ids, True, others=False)


def reset_defaults(scene):
    s = settings(scene)
    _busy[0] = True
    try:
        b = by_id()
        for r in s.items:
            r.solid = bool(b.get(r.iid, {}).get('default', True))
        _fix_parents(s)
    finally:
        _busy[0] = False
    apply(scene)


def objects_of(scene, ids):
    want = set()
    for i in ids:
        want.add(i)
        want.update(descendants(i))
    return [o for o in scene.objects if o.get('xr_item') in want]


def bounds(objs):
    lo = Vector((1e9, 1e9, 1e9)); hi = -lo
    n = 0
    for o in objs:
        if o.type != 'MESH':
            continue
        for c in o.bound_box:
            p = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, p)); hi = Vector(map(max, hi, p))
            n += 1
    return (lo, hi) if n else (None, None)


# ---------------------------------------------------------------------------------------------------------- blur
def set_blur(scene, on):
    s = settings(scene)
    scene.render.use_compositing = bool(on)
    ng = bpy.data.node_groups.get(COMP_GROUP)
    if ng and 'blur_a' in ng.nodes:
        for k in ('blur_a', 'blur_b'):
            ng.nodes[k].inputs['Size'].default_value = (s.blur_size, s.blur_size)
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == 'VIEW_3D':
                for sp in area.spaces:
                    if sp.type == 'VIEW_3D':
                        sp.shading.use_compositor = 'ALWAYS' if on else 'DISABLED'


# ---------------------------------------------------------------------------------------------------------- cameras
def frame_camera(scene, cam, ids=None, margin=1.25):
    """Aim cam (keeping its direction) at the given items (default: the solid ones) and move it along its view axis
    until their bounding-box corners fill the frame; margin > 1 leaves room around them."""
    s = settings(scene)
    if ids is None:
        ids = [r.iid for r in s.items if r.solid and not children(r.iid)]
    objs = [o for o in objects_of(scene, ids) if not o.hide_render and o.type == 'MESH']
    lo, hi = bounds(objs)
    if lo is None:
        return False
    rot = cam.matrix_world.to_quaternion()
    fwd, right, up = rot @ Vector((0, 0, -1)), rot @ Vector((1, 0, 0)), rot @ Vector((0, 1, 0))
    W, H = scene.render.resolution_x, scene.render.resolution_y
    h = cam.data.angle if W >= H else 2 * math.atan(math.tan(cam.data.angle / 2) * W / H)
    tx = math.tan(h / 2)
    ty = tx * H / W
    corners = []
    for o in objs:
        for c in o.bound_box:
            corners.append(o.matrix_world @ Vector(c))
    # centre the box on screen: shift the aim point sideways until the projected extents are symmetric
    c = (lo + hi) / 2
    dist = max((hi - lo).length, 0.1)
    for _ in range(6):
        p = c - fwd * dist
        xs = [(q - p).dot(right) / max(1e-6, (q - p).dot(fwd)) for q in corners]
        ys = [(q - p).dot(up) / max(1e-6, (q - p).dot(fwd)) for q in corners]
        need = max((max(xs) - min(xs)) / (2 * tx), (max(ys) - min(ys)) / (2 * ty))
        dx, dy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        depth = (c - p).dot(fwd)
        c = c + right * dx * depth + up * dy * depth
        dist = max(0.05, dist * need * margin)
    cam.location = c - fwd * dist
    cam.data.clip_start = 0.005
    return True


# ---------------------------------------------------------------------------------------------------------- UI properties
def _item_update(self, context):
    if _busy[0]:
        return
    s = settings(context.scene)
    _busy[0] = True
    try:
        for d in descendants(self.iid):
            r = row_of(s, d)
            if r:
                r.solid = self.solid
        _fix_parents(s)
    finally:
        _busy[0] = False
    apply(context.scene)


def _apply_update(self, context):
    if not _busy[0]:
        apply(context.scene)


def _ghost_update(self, context):
    ensure_ghosts(settings(context.scene))


def _blur_update(self, context):
    set_blur(context.scene, self.blur)


def _focus_update(self, context):
    _last_sel[0] = None          # the current selection takes effect at the next click
    set_pickable(context.scene)


class ARHUD_Item(bpy.types.PropertyGroup):
    iid: StringProperty()
    solid: BoolProperty(name='Show solid', default=True, update=_item_update,
                        description='Show this component solid; unticked components become x-ray ghosts')
    expanded: BoolProperty(default=False)


class ARHUD_Cat(bpy.types.PropertyGroup):
    cid: StringProperty()
    expanded: BoolProperty(default=False)


class ARHUD_Settings(bpy.types.PropertyGroup):
    items: CollectionProperty(type=ARHUD_Item)
    cats: CollectionProperty(type=ARHUD_Cat)
    mode: EnumProperty(name='Others', default='XRAY', update=_apply_update, items=[
        ('XRAY', 'X-ray', 'Components that are not ticked become translucent blue x-ray ghosts with bright edges'),
        ('FADE', 'Frosted', 'Components that are not ticked become pale frosted ghosts that keep their shading'),
        ('HIDE', 'Hide', 'Components that are not ticked are hidden'),
    ])
    opacity: FloatProperty(name='Ghost strength', default=0.55, min=0.05, max=1.0, update=_ghost_update,
                           description='How strongly the ghosts show')
    tint: FloatVectorProperty(name='Ghost tint', subtype='COLOR', size=3, min=0, max=1, default=(0.12, 0.33, 0.70), update=_ghost_update)
    blur: BoolProperty(name='Blur ghosts', default=False, update=_blur_update,
                       description='Blur everything that is not shown solid and keep the solid parts sharp (compositor; '
                                   'in the viewport it needs Material Preview or Rendered shading)')
    blur_size: IntProperty(name='Radius', default=14, min=1, max=80, update=_blur_update, description='Blur radius in pixels')
    follow_selection: BoolProperty(name='Click to focus', default=False, update=_focus_update,
                                   description='Clicking a part in the viewport shows its component solid and ghosts the rest; '
                                               'ghosts cannot be clicked, so clicks go through the x-ray shell')
    info: StringProperty(default='hudUnit')
    filter: StringProperty(name='Filter', default='', options={'TEXTEDIT_UPDATE'},
                           description='Show only components whose name, group or description contains this text')


# ---------------------------------------------------------------------------------------------------------- operators
class ARHUD_OT_isolate(bpy.types.Operator):
    bl_idname = 'arhud.isolate'
    bl_label = 'Isolate'
    bl_description = 'Show only this component solid (Shift-click: add it to the components already shown)'
    bl_options = {'REGISTER', 'UNDO'}
    iid: StringProperty()

    def invoke(self, context, event):
        if event.shift:
            set_solid(context.scene, [self.iid], True)
            settings(context.scene).info = self.iid
            return {'FINISHED'}
        return self.execute(context)

    def execute(self, context):
        isolate(context.scene, [self.iid])
        settings(context.scene).info = self.iid
        return {'FINISHED'}


class ARHUD_OT_set_all(bpy.types.Operator):
    bl_idname = 'arhud.set_all'
    bl_label = 'Set all'
    bl_options = {'REGISTER', 'UNDO'}
    action: EnumProperty(items=[('ALL', 'All', 'Every component solid'), ('NONE', 'None', 'Every component ghosted'),
                                ('INVERT', 'Invert', 'Swap solid and ghosted'), ('RESET', 'Reset', 'Back to the default: project parts solid, car ghosted')])
    cat: StringProperty(default='')

    @classmethod
    def description(cls, context, props):
        if props.cat:
            return {'ALL': 'Show this whole group solid', 'NONE': 'Ghost this whole group'}.get(props.action, '')
        return {'ALL': 'Show every component solid', 'NONE': 'Ghost every component', 'INVERT': 'Swap solid and ghosted components',
                'RESET': 'Back to the default: project parts solid, car ghosted'}[props.action]

    def execute(self, context):
        sc = context.scene
        s = settings(sc)
        if self.action == 'RESET':
            reset_defaults(sc)
            return {'FINISHED'}
        if self.cat:
            ids = [it['id'] for it in data()['items'] if it['cat'] == self.cat]
            set_solid(sc, ids, self.action == 'ALL')
            return {'FINISHED'}
        if self.action == 'INVERT':
            leaves = [r for r in s.items if not children(r.iid)]
            flip = [r.iid for r in leaves if not r.solid]
            set_solid(sc, flip, True, others=False)
            return {'FINISHED'}
        set_solid(sc, [], True, others=self.action == 'ALL')
        return {'FINISHED'}


class ARHUD_OT_from_selection(bpy.types.Operator):
    bl_idname = 'arhud.from_selection'
    bl_label = 'Selected parts'
    bl_description = 'Show solid the components of the parts selected in the viewport; ghost the rest'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ids = sorted({o.get('xr_item') for o in context.selected_objects if o.get('xr_item')})
        if not ids:
            self.report({'WARNING'}, 'Select a part in the viewport first')
            return {'CANCELLED'}
        isolate(context.scene, ids)
        settings(context.scene).info = ids[0]
        return {'FINISHED'}


def _sidebar_shift(context, r3d, dist):
    """World offset that centres a framed part in the visible part of the view when the sidebar overlaps it."""
    area = context.area
    win = next((r for r in area.regions if r.type == 'WINDOW'), None)
    ui = next((r for r in area.regions if r.type == 'UI'), None)
    if not (win and ui and ui.width > 1 and context.preferences.system.use_region_overlap):
        return Vector((0, 0, 0))
    lens = area.spaces.active.lens
    view_w = 2 * dist * (36 / (2 * lens)) * 2          # visible width at the target (viewport sensor ~72 mm)
    px = view_w / max(1, win.width)
    return r3d.view_rotation @ Vector((ui.width / 2 * px, 0, 0))


class ARHUD_OT_frame(bpy.types.Operator):
    bl_idname = 'arhud.frame'
    bl_label = 'Frame'
    bl_description = 'Move the viewport to this component (the selection is left alone)'
    iid: StringProperty()

    def execute(self, context):
        lo, hi = bounds(objects_of(context.scene, [self.iid]))
        if lo is None:
            self.report({'WARNING'}, 'No geometry for this component')
            return {'CANCELLED'}
        settings(context.scene).info = self.iid
        area = context.area if context.area and context.area.type == 'VIEW_3D' else None
        if area is None:
            return {'FINISHED'}
        r3d = area.spaces.active.region_3d
        if r3d.view_perspective == 'CAMERA':
            r3d.view_perspective = 'PERSP'
        # move the view, not the selection: selecting hundreds of parts would bury the view in outlines
        dist = max(0.12, (hi - lo).length * 1.3)
        r3d.view_distance = dist
        r3d.view_location = (lo + hi) / 2 + _sidebar_shift(context, r3d, dist)
        return {'FINISHED'}


class ARHUD_OT_info(bpy.types.Operator):
    bl_idname = 'arhud.info'
    bl_label = 'About'
    bl_description = 'Show what this component is and its key numbers in the About card'
    iid: StringProperty()

    def execute(self, context):
        settings(context.scene).info = self.iid
        return {'FINISHED'}


class ARHUD_OT_camera(bpy.types.Operator):
    bl_idname = 'arhud.camera'
    bl_label = 'View'
    bl_description = 'Look through this preset camera'
    cam: StringProperty()
    fit: BoolProperty(default=False)

    def execute(self, context):
        cam = bpy.data.objects.get(self.cam)
        if not cam:
            return {'CANCELLED'}
        if self.fit:
            src = context.scene.camera if context.scene.camera and context.scene.camera != cam else bpy.data.objects.get('CAM Overview')
            if src:
                cam.matrix_world = src.matrix_world.copy()
                cam.data.lens = src.data.lens
                cam.data.type = src.data.type
            if not frame_camera(context.scene, cam, margin=1.15):
                self.report({'WARNING'}, 'Nothing is shown solid')
                return {'CANCELLED'}
        context.scene.camera = cam
        if context.area and context.area.type == 'VIEW_3D':
            context.area.spaces.active.region_3d.view_perspective = 'CAMERA'
        return {'FINISHED'}


# ---------------------------------------------------------------------------------------------------------- panels
def _text_width(context):
    """Usable text width of the sidebar in pixels, and a function measuring a string in the UI font."""
    ui = context.preferences.system.ui_scale
    w = ((context.region.width if context.region else 560) - 50 * ui) * 0.9    # 10% slack: Blender ellipsizes overlong labels
    try:
        import blf
        blf.size(0, 11 * ui)
        return w, lambda t: blf.dimensions(0, t)[0]
    except Exception:
        return w, lambda t: len(t) * 6.2 * ui


def _wrap(context, text, indent=0):
    width, measure = _text_width(context)
    width -= indent
    lines, cur = [], ''
    for w in text.split():
        cand = (cur + ' ' + w).strip()
        if cur and measure(cand) > width:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines or ['']


def _labels(context, layout, text, icon='NONE'):
    col = layout.column(align=True)
    for i, line in enumerate(_wrap(context, text, 22 * context.preferences.system.ui_scale if icon != 'NONE' else 0)):
        col.label(text=line, icon=icon if i == 0 else ('BLANK1' if icon != 'NONE' else 'NONE'))
    return col


def _match(it, flt):
    if not flt:
        return True
    cats = dict(data()['categories'])
    hay = ' '.join([it['name'], it.get('short', ''), it['id'], cats.get(it['cat'], ''), it.get('desc', '')]).lower()
    return flt in hay


def _short(it):
    return it.get('short') or it['name']


class _Base:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'AR HUD'


class ARHUD_PT_main(_Base, bpy.types.Panel):
    bl_label = 'X-ray display'
    bl_order = 0

    def draw(self, context):
        s = settings(context.scene)
        L = self.layout
        if not s.items:
            L.label(text='No component list in this file', icon='ERROR')
            return
        L.row(align=True).prop(s, 'mode', expand=True)
        sub = L.column(align=True)
        sub.active = s.mode != 'HIDE'
        sub.prop(s, 'opacity', slider=True)
        sub.prop(s, 'tint')
        r = sub.row(align=True)
        r.prop(s, 'blur', toggle=True, icon='MOD_SMOOTH')
        rr = r.row(align=True)
        rr.active = s.blur
        rr.prop(s, 'blur_size')
        sp = context.space_data
        if s.blur and sp and sp.type == 'VIEW_3D' and sp.shading.type in {'SOLID', 'WIREFRAME'}:
            L.label(text='Blur shows in Material Preview or Rendered', icon='INFO')
        r = L.row(align=True)
        for a, t in (('ALL', 'All'), ('NONE', 'None'), ('INVERT', 'Invert'), ('RESET', 'Reset')):
            r.operator('arhud.set_all', text=t).action = a
        r = L.row(align=True)
        r.operator('arhud.from_selection', icon='RESTRICT_SELECT_OFF')
        r.prop(s, 'follow_selection', toggle=True, icon='MOUSE_LMB')


class ARHUD_PT_info(_Base, bpy.types.Panel):
    bl_label = 'About'
    bl_order = 1

    def draw(self, context):
        s = settings(context.scene)
        b = by_id()
        it = b.get(s.info)
        L = self.layout
        if not it:
            L.label(text='Press i beside a component', icon='INFO')
            return
        head = L.column(align=True)
        _labels(context, head, it['name'], icon='INFO')
        p = it.get('parent')
        if p:
            _labels(context, head, 'Part of: ' + b[p]['name'])
        if it.get('desc'):
            _labels(context, L, it['desc'])
        if it.get('facts'):
            box = L.box().column(align=True)
            for k, v in it['facts']:
                lines = _wrap(context, f'{k}: {v}', 14 * context.preferences.system.ui_scale)
                for j, line in enumerate(lines):
                    box.label(text=('    ' if j else '') + line)
        if it.get('where'):
            _labels(context, L, 'Where: ' + it['where'], icon='OBJECT_ORIGIN')
        r = L.row(align=True)
        r.operator('arhud.isolate', text='Isolate', icon='SOLO_ON').iid = it['id']
        r.operator('arhud.frame', text='Frame', icon='ZOOM_SELECTED').iid = it['id']


class ARHUD_PT_tree(_Base, bpy.types.Panel):
    bl_label = 'Components'
    bl_order = 2

    def draw(self, context):
        s = settings(context.scene)
        L = self.layout
        if not s.items:
            return
        L.prop(s, 'filter', text='', icon='VIEWZOOM')
        flt = s.filter.strip().lower()
        rows = {r_.iid: r_ for r_ in s.items}
        cats = {c.cid: c for c in s.cats}
        b = by_id()
        shown = 0
        for cid, cname in data()['categories']:
            items = [it for it in data()['items'] if it['cat'] == cid]
            tops = [it for it in items if not it.get('parent')]
            if not tops or (flt and not any(_match(it, flt) for it in items)):
                continue
            shown += 1
            box = L.box()
            c = cats.get(cid)
            hr = box.row(align=True)
            open_ = bool(flt) or (c is not None and c.expanded)
            if c:
                hr.prop(c, 'expanded', text='', emboss=False, icon='DOWNARROW_HLT' if open_ else 'RIGHTARROW')
            n_on = sum(1 for it in items if not children(it['id']) and rows.get(it['id']) and rows[it['id']].solid)
            n_all = sum(1 for it in items if not children(it['id']))
            hr.label(text=f'{n_on}/{n_all}  {cname}')
            op = hr.operator('arhud.set_all', text='', icon='SHADING_SOLID', emboss=False); op.action = 'ALL'; op.cat = cid
            op = hr.operator('arhud.set_all', text='', icon='GHOST_ENABLED', emboss=False); op.action = 'NONE'; op.cat = cid
            if not open_:
                continue
            colb = box.column(align=True)
            for it in tops:
                self.draw_item(context, colb, it['id'], 0, rows, b, flt)
        if flt and not shown:
            L.label(text='No component matches', icon='INFO')

    def draw_item(self, context, col, iid, depth, rows, b, flt):
        it = b[iid]
        r_ = rows.get(iid)
        kids = children(iid)
        if r_ is None or not (_match(it, flt) or any(_match(b[k], flt) for k in descendants(iid))):
            return
        row = col.row(align=True)
        if depth:
            row.separator(factor=1.4 * depth)
        open_ = bool(flt) or r_.expanded
        if kids:
            row.prop(r_, 'expanded', text='', emboss=False, icon='DOWNARROW_HLT' if open_ else 'RIGHTARROW')
        row.prop(r_, 'solid', text=_short(it))
        row.operator('arhud.isolate', text='', icon='SOLO_ON', emboss=False).iid = iid
        info = row.operator('arhud.info', text='', icon='INFO', emboss=False, depress=settings(context.scene).info == iid)
        info.iid = iid
        if kids and open_:
            for k in kids:
                self.draw_item(context, col, k, depth + 1, rows, b, flt)


class ARHUD_PT_views(_Base, bpy.types.Panel):
    bl_label = 'Views'
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        g = self.layout.grid_flow(columns=2, align=True)
        for _key, label, cam in CAMERAS:
            if cam in bpy.data.objects:
                g.operator('arhud.camera', text=label, icon='CAMERA_DATA').cam = cam
        op = self.layout.operator('arhud.camera', text='Fit a camera to the solid parts', icon='VIEW_CAMERA')
        op.cam = 'CAM Auto'
        op.fit = True
        col = self.layout.column(align=True)
        col.label(text='F12 renders the active camera,')
        col.label(text='with the ghosts and the blur.')


# ---------------------------------------------------------------------------------------------------------- handlers
@bpy.app.handlers.persistent
def _on_depsgraph(scene, depsgraph):
    try:
        s = scene.arhud
    except AttributeError:
        return
    if not s.follow_selection or _busy[0]:
        return
    try:
        sel = tuple(sorted(o.name for o in bpy.context.selected_objects if o.get('xr_item')))
    except AttributeError:
        return
    if sel == _last_sel[0]:
        return
    _last_sel[0] = sel
    if not sel:
        return
    ids = sorted({bpy.data.objects[n]['xr_item'] for n in sel})
    isolate(scene, ids)
    s.info = ids[0]


NOTICE = 'XR notice: scripts are off'


def _hide_notice():
    o = bpy.data.objects.get(NOTICE)
    if o is not None:
        o.hide_viewport = True
        o.hide_render = True


def _show_tab():
    """Open the AR HUD sidebar tab in every 3-D view of a file that carries the component list."""
    if bpy.data.texts.get(ITEMS_TEXT) is None:
        return None
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                for sp in area.spaces:
                    if sp.type == 'VIEW_3D':
                        sp.show_region_ui = True
                for rg in area.regions:
                    if rg.type == 'UI':
                        try:
                            rg.active_panel_category = 'AR HUD'
                        except Exception:
                            pass
    return None


@bpy.app.handlers.persistent
def _on_load(_dummy=None):
    try:
        _hide_notice()
    except Exception:
        pass
    if not bpy.app.background:
        bpy.app.timers.register(_show_tab, first_interval=0.3)


CLASSES = [ARHUD_Item, ARHUD_Cat, ARHUD_Settings, ARHUD_OT_isolate, ARHUD_OT_set_all, ARHUD_OT_from_selection, ARHUD_OT_frame,
           ARHUD_OT_info, ARHUD_OT_camera, ARHUD_PT_main, ARHUD_PT_info, ARHUD_PT_tree, ARHUD_PT_views]


def register():
    unregister()
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.arhud = PointerProperty(type=ARHUD_Settings)
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)
    bpy.app.handlers.load_post.append(_on_load)
    _on_load()


def unregister():
    for hl in (bpy.app.handlers.depsgraph_update_post, bpy.app.handlers.load_post):
        for h in list(hl):
            if getattr(h, '__name__', '') in ('_on_depsgraph', '_on_load'):
                hl.remove(h)
    if hasattr(bpy.types.Scene, 'arhud'):
        try:
            del bpy.types.Scene.arhud
        except Exception:
            pass
    for name in [c.__name__ for c in CLASSES] + ['ARHUD_PT_facts']:
        old = getattr(bpy.types, name, None)
        if old is not None:
            try:
                bpy.utils.unregister_class(old)
            except RuntimeError:
                pass


register()
