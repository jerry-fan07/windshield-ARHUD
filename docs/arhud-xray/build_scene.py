# Builds arhud-xray.blend: every component of the TFT-edition AR HUD, installed in the car, plus the bench rigs and test
# instruments, on a white studio floor, with the x-ray component panel (arhud_xray.py) embedded.
#
#   /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P docs/arhud-xray/build_scene.py
#
# Geometry comes from the simulator (docs/arhud-sim) through tools/export.html: source/installed.glb (the car with every
# part at its mount point and the cable runs), source/bench.glb (rigs and instruments) and source/layout.json (mount
# points, cable runs, the traced light path, and each component's description and facts). This script sorts the
# imported objects into components, adds the light path and eye box, the studio, cameras, the ghost materials and the
# blur compositor, and saves the file.
import json
import math
import os
import re
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'source')
OUT = os.path.join(HERE, 'arhud-xray.blend')
sys.path.insert(0, HERE)

BENCH_X, BENCH_YAW = -4.0, -27  # bench row behind the car; items turned toward the overview camera
LAYOUT = json.load(open(os.path.join(SRC, 'layout.json')))
COMPS = LAYOUT['components']


def sim(p):
    """Simulation frame (X forward, Y up, Z right) to Blender (X forward, Y left, Z up), as the glTF importer does."""
    return Vector((p[0], -p[2], p[1]))


# ---------------------------------------------------------------------------------------------------------- item tree
CATEGORIES = [
    ('hud', 'HUD optical unit'),
    ('sensor', 'Sensors'),
    ('compute', 'Computer'),
    ('controller', 'Controller & LED driver'),
    ('power', 'Power'),
    ('network', 'Network & audience'),
    ('cables', 'Cables'),
    ('optics', 'Windshield & light path'),
    ('bench', 'Bench & instruments'),
    ('vehicle', 'Car (context)'),
]

ITEMS = []  # dicts: id, name, parent, cat, kind, default, desc, facts, where


def comp_meta(cid):
    c = COMPS.get(cid, {})
    return {'desc': c.get('desc', ''), 'facts': c.get('facts', [])}


def part_desc(cid, pid):
    for p in COMPS.get(cid, {}).get('parts', []):
        if p['id'] == pid:
            return p.get('desc', '')
    return ''


def add(iid, name, cat, parent=None, kind='component', default=True, desc=None, facts=None, where='', meta=None):
    m = comp_meta(meta or iid)
    ITEMS.append({'id': iid, 'name': name, 'parent': parent, 'cat': cat, 'kind': kind, 'default': default,
                  'desc': desc if desc is not None else m['desc'], 'facts': facts if facts is not None else m['facts'],
                  'where': where or LAYOUT['mounts'].get(meta or iid, {}).get('note', '')})


mnote = lambda k: LAYOUT['mounts'].get(k, {}).get('note', '')
add('hudUnit', 'HUD optical unit', 'hud', where=mnote('hudUnit'))
add('housing', '3-D printed housing, baffles and lid', 'hud', 'hudUnit', where='dash top')
add('pgu', 'Picture generation unit (TFT)', 'hud', 'hudUnit', where='rear of the housing, lowest')
add('backlight', 'Custom direct-lit LED backlight', 'hud', 'pgu', where='under the LCD cell')
add('lcdCell', 'LCD cell, 60 × 30 mm crop lit', 'hud', 'pgu', where='on the backlight')
add('retarder', 'Half-wave retarder film', 'hud', 'pgu', where='on the cell')
add('pguBoard', 'HDMI driver board and flex', 'hud', 'pgu', desc=part_desc('pgu', 'board') or 'The panel kit\'s HDMI driver board and the flex cable to the cell.',
    facts=[[k, v] for k, v in COMPS['panelKit']['facts'][:4]], where='beside the PGU')
add('pguBracket', 'PGU bracket and cell thermistor', 'hud', 'pgu', desc=(part_desc('pgu', 'bracket') + ' ' + part_desc('pgu', 'ntc')).strip(), facts=[], where='PGU')
add('coldMirror', 'Cold-mirror fold and IR absorber', 'hud', 'hudUnit', where='above the panel')
add('concaveMirror', 'Concave relay mirror, 300 × 200 mm', 'hud', 'hudUnit', where='front of the housing')
add('shutter', 'Sun shutter and servo', 'hud', 'hudUnit', where='under the lid aperture')
add('dustCover', 'Dust cover, s-pass polariser, light sensor', 'hud', 'hudUnit', where='lid aperture')

add('zed2i', 'Stereolabs ZED 2i road camera', 'sensor')
add('oakdPro', 'Luxonis OAK-D Pro driver camera', 'sensor')
add('gnssAntenna', 'GNSS antenna', 'sensor')
add('zedF9r', 'u-blox ZED-F9R GNSS board', 'sensor')
add('jetson', 'Seeed reComputer J4012 (Jetson Orin NX)', 'compute')
add('controller', 'HUD controller (RP2040) and sensors', 'controller')
add('ledDriver', 'Constant-current LED driver', 'controller')
add('dcdc', 'Mini-Box DCDC-USB-200 converter', 'power')
add('fuseTap', '12 V plug and inline fuse', 'power')
add('pdCharger', 'USB-C PD car charger', 'power')
add('ethSwitch', 'Gigabit Ethernet switch', 'network')
add('miniPC', 'Mini PC 2 (audience view)', 'network')
add('monitor', 'Monitor 2 (audience view)', 'network')

CABLE_KINDS = [('power', '12 V and DC power'), ('usb', 'USB'), ('hdmi', 'HDMI video'), ('eth', 'Ethernet'), ('serial', 'USB serial'), ('rf', 'GNSS coax')]
for kind, kname in CABLE_KINDS:
    runs = [c for c in LAYOUT['cables'] if c['kind'] == kind]
    if not runs:
        continue
    add('cables_' + kind, f'{kname} ({len(runs)})', 'cables', kind='cable', desc=f'{kname} runs, as routed in the car.', facts=[], where='')
    for c in runs:
        add('cable_' + c['id'], c['label'], 'cables', 'cables_' + kind, kind='cable', desc=c['label'] + '.',
            facts=[['Length as routed', f"{c['length']:.2f} m"]], where='')

O = LAYOUT['optics']
add('windshield', 'Windshield (the combiner)', 'optics', meta='windshield', default=False,
    where=f"rake {O['RAKE_DEG']:.0f}° (ASSUMED); the HUD reflects off its inner surface")
add('lightPath', 'Traced light path, panel to eye', 'optics', kind='overlay',
    desc='Rays traced back from the eye box through the corners and centre of the 10.8° × 5.4° window: eye ← windshield ← concave mirror ← fold ← panel. Light travels the other way.',
    facts=[['Eye to glass', '750 mm (ASSUMED)'], ['Glass to mirror', '310 mm (simulation; the plan\'s 250 mm does not clear the glass)'],
           ['Panel to mirror (u)', '316 mm'], ['Mirror focal length', '330 mm'], ['Virtual image', '7.5 m ahead (plan)']], where='')
add('eyeBox', 'Eye box, 130 × 70 mm', 'optics', kind='overlay',
    desc='The region the driver\'s eyes can move in and still see the whole window, centred on the nominal eye point 1.22 m above the road.',
    facts=[['Design', '130 × 70 mm'], ['Requirement', '≥ 120 × 60 mm without tracking']], where='driver\'s eye point')

for bid, bname in [('stage0Rig', 'Stage 0 bench rig'), ('stage1Rig', 'Stage 1 Fresnel and combiner rig'), ('panelKit', '5.5-inch HDMI panel kit, as unboxed'),
                   ('latencyProbe', 'Latency probe (photodiode + LED)'), ('lumMeter', 'Spot luminance meter on tripod'),
                   ('targetBoard', '30 m registration target board'), ('rangefinder', 'Laser rangefinder')]:
    add(bid, bname, 'bench', where='bench (not installed in the car)')

add('carBody', 'Car body shell', 'vehicle', kind='context', default=False, desc='The car the HUD is installed in (a generic left-hand-drive sedan from the simulator).', facts=[])
add('carInterior', 'Dashboard, seats and trim', 'vehicle', kind='context', default=False, desc='Dash, centre stack, column shroud, steering wheel, seats and rear-view mirror.', facts=[])
add('driver', 'Driver', 'vehicle', kind='context', default=False, desc='The driver mannequin, eyes at the nominal eye point.', facts=[])
add('wheels', 'Wheels', 'vehicle', kind='context', default=False, desc='Wheels, tyres and brakes.', facts=[])

SHORT = {
    'housing': 'Housing, baffles, lid', 'pgu': 'Picture generator (PGU)', 'backlight': 'LED backlight', 'lcdCell': 'LCD cell',
    'retarder': 'Half-wave retarder', 'pguBoard': 'HDMI board + flex', 'pguBracket': 'Bracket + thermistor',
    'coldMirror': 'Cold-mirror fold', 'concaveMirror': 'Concave mirror', 'shutter': 'Sun shutter', 'dustCover': 'Dust cover + polariser',
    'zed2i': 'ZED 2i road camera', 'oakdPro': 'OAK-D Pro driver cam', 'gnssAntenna': 'GNSS antenna', 'zedF9r': 'ZED-F9R GNSS board',
    'jetson': 'Jetson Orin NX', 'controller': 'HUD controller', 'ledDriver': 'LED driver', 'dcdc': 'DC-DC converter',
    'fuseTap': '12 V plug + fuse', 'pdCharger': 'USB-C PD charger', 'ethSwitch': 'Ethernet switch', 'miniPC': 'Mini PC 2',
    'monitor': 'Monitor 2', 'windshield': 'Windshield', 'lightPath': 'Light path', 'eyeBox': 'Eye box', 'stage0Rig': 'Stage 0 rig',
    'stage1Rig': 'Stage 1 rig', 'panelKit': 'Panel kit (unboxed)', 'latencyProbe': 'Latency probe', 'lumMeter': 'Luminance meter',
    'targetBoard': 'Target board', 'rangefinder': 'Rangefinder', 'carBody': 'Body shell', 'carInterior': 'Dash, seats, trim',
    'cable_usbZed': 'ZED 2i → Jetson', 'cable_usbOak': 'OAK-D → Jetson', 'cable_usbGnss': 'GNSS board → Jetson',
    'cable_video': 'Mini PC → monitor', 'cable_hdmi': 'Jetson → panel board', 'cable_eth': 'Jetson → mini PC',
    'cable_serial': 'Jetson → controller', 'cable_p12': '12 V → DC-DC', 'cable_pJetson': 'DC-DC → Jetson',
    'cable_pLed': 'DC-DC → LED driver', 'cable_pdPC': 'PD charger → mini PC', 'cable_rfGnss': 'Antenna → GNSS board',
}
for _it in ITEMS:
    _it['short'] = SHORT.get(_it['id'], _it['name'])

PGU_SUB = {'backlight': 'backlight', 'cell': 'lcdCell', 'retarder': 'retarder', 'board': 'pguBoard', 'fpc': 'pguBoard', 'bracket': 'pguBracket', 'ntc': 'pguBracket'}
HUD_SUB = {'housingBase': 'housing', 'baffles': 'housing', 'lid': 'housing', 'pgu': 'pgu', 'coldMirror': 'coldMirror', 'concaveMirror': 'concaveMirror',
           'shutter': 'shutter', 'dustCover': 'dustCover'}


# ---------------------------------------------------------------------------------------------------------- import
def base(n):
    return re.sub(r'\.\d{3}$', '', n)


def chain(o):
    out = []
    while o:
        out.append(o)
        o = o.parent
    return list(reversed(out))


def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path, import_shading='NORMALS')
    return [o for o in bpy.data.objects if o not in before]


def is_wheel(o):
    # wheel pivots sit at an axle (x 1.55 or -1.30) at wheel-centre height 0.33
    return o.type == 'EMPTY' and abs(o.location.z - 0.33) < 0.01 and min(abs(o.location.x - 1.55), abs(o.location.x + 1.30)) < 0.01


def classify(o):
    ch = chain(o)
    names = [base(a.name) for a in ch]
    if 'installed' in names:
        i = next((k for k, n in enumerate(names) if n.startswith('mount:')), None)
        if i is None:
            return None
        cid = names[i][6:]
        if cid != 'hudUnit':
            return cid
        if len(names) <= i + 2:
            return 'hudUnit'
        sub = HUD_SUB.get(names[i + 2], 'hudUnit')
        if sub == 'pgu' and len(names) > i + 3:
            return PGU_SUB.get(names[i + 3], 'pgu')
        return sub
    if 'cables' in names:
        for a in reversed(ch):
            pid = a.get('pickId')
            if isinstance(pid, str) and pid.startswith('cable:'):
                return 'cable_' + pid[6:]
        return None
    if 'bench' in names and len(names) > 1 and names[1].startswith('bench:'):
        return names[1][6:]
    if 'body' in names:
        if 'windshield' in names:
            return 'windshield'
        if any(is_wheel(a) for a in ch):
            return 'wheels'
        return 'carBody'
    if 'interior' in names:
        return 'driver' if 'driver' in names else 'carInterior'
    return None


# ---------------------------------------------------------------------------------------------------------- helpers
def new_collection(name, parent):
    c = bpy.data.collections.new(name)
    parent.children.link(c)
    return c


def move_to(o, coll):
    for c in list(o.users_collection):
        c.objects.unlink(o)
    coll.objects.link(o)


def world_bounds(objs):
    lo = Vector((1e9,) * 3); hi = -lo
    for o in objs:
        if o.type != 'MESH':
            continue
        for c in o.bound_box:
            p = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, p)); hi = Vector(map(max, hi, p))
    return lo, hi


def emission_mat(name, color, strength=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bs = nt.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Emission Color'].default_value = (*color, 1)
    bs.inputs['Emission Strength'].default_value = strength
    bs.inputs['Roughness'].default_value = 0.4
    m.diffuse_color = (*color, 1)
    return m


def polyline_mesh(name, pts, radius, mat, coll):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = 2
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (*q, 1)
    tmp = bpy.data.objects.new(name, cu)
    coll.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(mat)
    coll.objects.link(o)
    return o


def look_at(obj, target, roll_up=Vector((0, 0, 1))):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def add_camera(name, loc, target, lens=35, coll=None, ortho=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.01
    cd.clip_end = 200
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    o = bpy.data.objects.new(name, cd)
    (coll or bpy.context.scene.collection).objects.link(o)
    o.location = loc
    look_at(o, target)
    return o


# ---------------------------------------------------------------------------------------------------------- display fixes
GLASS = (0.50, 0.80, 0.75)      # teal: real glass and film must not look like the blue x-ray ghosts
CABLE_COLOURS = {'usb': (0.035, 0.035, 0.04), 'rf': (0.45, 0.30, 0.12)}   # USB was ghost-blue; RF coax made distinct from it


def principled(m):
    if not m or not m.node_tree:
        return None
    return next((n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)


def dress_materials():
    """Display tweaks to the imported materials (the simulator's own look is tuned for a dark garage)."""
    cable_mats = {}
    for o in bpy.data.objects:
        iid = o.get('xr_item', '')
        if o.type == 'MESH' and iid.startswith('cable_'):
            kind = next((it['parent'][7:] for it in ITEMS if it['id'] == iid), None)
            for m in o.data.materials:
                cable_mats.setdefault(m, kind)
            # thicken the 6-8 mm runs so they read at car scale
            if not any(md.type == 'DISPLACE' for md in o.modifiers):
                md = o.modifiers.new('thicker', 'DISPLACE')
                md.mid_level = 0.0
                md.strength = 0.0022
    for m, kind in cable_mats.items():
        b = principled(m)
        if b is not None and kind in CABLE_COLOURS:
            b.inputs['Base Color'].default_value = (*CABLE_COLOURS[kind], 1)
            m.diffuse_color = (*CABLE_COLOURS[kind], 1)
    glass, mirrors = [], []
    size = {}
    for o in bpy.data.objects:
        if o.type == 'MESH':
            for m in o.data.materials:
                if m:
                    size[m] = max(size.get(m, 0), max(o.dimensions))
    for m in list(bpy.data.materials):
        b = principled(m)
        if b is None or m in cable_mats:
            continue
        a = b.inputs['Alpha']
        # (the LED dies' 3 mm phosphor domes are translucent too, but they are not glass)
        if not a.is_linked and a.default_value < 0.6 and size.get(m, 1) > 0.006:
            glass.append(m.name)
            a0 = min(0.3, max(0.12, a.default_value))
            b.inputs['Base Color'].default_value = (*GLASS, 1)
            b.inputs['Roughness'].default_value = 0.3
            b.inputs['Specular IOR Level'].default_value = 0.1      # no white hotspot from the studio key light
            nt = m.node_tree
            lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.4
            pw = nt.nodes.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 1.5
            ma = nt.nodes.new('ShaderNodeMath'); ma.operation = 'MULTIPLY_ADD'; ma.use_clamp = True
            ma.inputs[1].default_value = 0.6 - a0
            ma.inputs[2].default_value = a0
            nt.links.new(lw.outputs['Facing'], pw.inputs[0])
            nt.links.new(pw.outputs[0], ma.inputs[0])
            nt.links.new(ma.outputs[0], a)
            m.diffuse_color = (*GLASS, 0.45)
        elif b.inputs['Metallic'].default_value > 0.9 and b.inputs['Roughness'].default_value < 0.1:
            # polished mirrors only reflect the white studio and read as blank white cards; give them some tone
            mirrors.append(m.name)
            b.inputs['Base Color'].default_value = (0.66, 0.70, 0.77, 1)
            b.inputs['Roughness'].default_value = 0.24
    print('glass materials:', glass)
    print('mirror materials:', mirrors)


def fix_layout(imported):
    """Corrections to the simulator layout, done here so docs/arhud-sim stays untouched. Returns removed objects' ids."""
    removed = set()
    # The USB-C PD charger was mounted backwards inside the centre console (plug tip out, head in). Turn it round so
    # the plug enters the console's rear face and the head with its ports sticks out toward the rear seats.
    m = next((o for o in imported if base(o.name) == 'mount:pdCharger'), None)
    if m is not None:
        m.rotation_mode = 'QUATERNION'
        m.rotation_quaternion = Quaternion((0, 0, 1), math.pi) @ m.rotation_quaternion
        bpy.context.view_layer.update()
        lo, hi = world_bounds([k for k in m.children_recursive if k.type == 'MESH'])
        m.location.x += -0.445 - hi.x        # plug tip 25 mm into the console, whose rear face is at x = -0.47
        bpy.context.view_layer.update()
    # helper empties far from the car (the simulator's headlight targets) make View All zoom out to 90 m
    for o in list(imported):
        if o.type == 'EMPTY' and not o.get('xr_item') and o.matrix_world.translation.length > 12 \
                and not any(k.type == 'MESH' for k in o.children_recursive):
            removed.add(id(o))
            bpy.data.objects.remove(o, do_unlink=True)
    return removed


def add_notice(coll):
    """A 3-D note that is visible only when Blender did not run the embedded panel script (it hides itself)."""
    cu = bpy.data.curves.new('notice', 'FONT')
    cu.body = 'Scripts are off, so the AR HUD panel is missing.\nReopen the file and choose Allow Execution\n(or install arhud_xray.py as an add-on), then press N.'
    cu.size = 0.16
    cu.align_x = 'CENTER'
    o = bpy.data.objects.new('XR notice: scripts are off', cu)
    coll.objects.link(o)
    cam = bpy.data.objects['CAM Overview']
    o.location = (0.4, -0.4, 2.35)
    o.rotation_euler = cam.rotation_euler
    m = emission_mat('notice text', (0.75, 0.12, 0.10), 1.0)
    cu.materials.append(m)
    o.hide_select = True
    return o


# ---------------------------------------------------------------------------------------------------------- build
def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = 'AR HUD x-ray display'
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.length_unit = 'MILLIMETERS'

    car_objs = import_glb(os.path.join(SRC, 'installed.glb'))
    bench_objs = import_glb(os.path.join(SRC, 'bench.glb'))
    imported = car_objs + bench_objs

    # drop the bench copy of the windshield section: the car's own windshield is the combiner
    drop = [o for o in bench_objs if any(base(a.name) == 'bench:windshield' for a in chain(o))]
    dropped = {id(o) for o in drop}
    imported = [o for o in imported if id(o) not in dropped]
    for o in drop:
        bpy.data.objects.remove(o, do_unlink=True)

    gone = fix_layout(imported)
    imported = [o for o in imported if id(o) not in gone]

    # ---- bench row: behind the car, items side by side on the floor ----
    roots = [o for o in imported if base(o.name).startswith('bench:')]
    order = ['stage0Rig', 'stage1Rig', 'panelKit', 'latencyProbe', 'lumMeter', 'rangefinder', 'targetBoard']
    roots.sort(key=lambda r: order.index(base(r.name)[6:]) if base(r.name)[6:] in order else 99)
    bench_parent = next(o for o in imported if base(o.name) == 'bench')
    bench_parent.location = (0, 0, 0)
    # a row behind the car, across its width, fronts turned toward the overview camera (front right)
    y = 0.0
    gap = 0.3
    for r in roots:
        r.rotation_mode = 'XYZ'
        # the target board's rings face its local -X; turn it round so they face the cameras like everything else
        r.rotation_euler = (0, 0, math.radians(BENCH_YAW + (180 if base(r.name) == 'bench:targetBoard' else 0)))
        bpy.context.view_layer.update()
        kids = [k for k in r.children_recursive if k.type == 'MESH']
        lo, hi = world_bounds(kids)
        r.location += Vector((BENCH_X - (lo.x + hi.x) / 2, y - hi.y, -lo.z))
        y -= (hi.y - lo.y) + gap
        bpy.context.view_layer.update()
    lo, hi = world_bounds([k for r in roots for k in r.children_recursive])
    shift = -LAYOUT['optics']['CAR_CENTER_Z'] - (lo.y + hi.y) / 2
    for r in roots:
        r.location.y += shift
    bpy.context.view_layer.update()

    # ---- collections ----
    top = new_collection('AR HUD components', sc.collection)
    cat_coll = {}
    for i, (cid, cname) in enumerate(CATEGORIES):
        cat_coll[cid] = new_collection(f'{i + 1:02d} {cname}', top)
    item_coll = {}
    byid = {it['id']: it for it in ITEMS}

    def coll_for(iid):
        if iid in item_coll:
            return item_coll[iid]
        it = byid[iid]
        parent = coll_for(it['parent']) if it.get('parent') else cat_coll[it['cat']]
        c = new_collection(it['name'], parent)
        item_coll[iid] = c
        return c
    for it in ITEMS:
        coll_for(it['id'])
    structure = new_collection('Structure (empties)', sc.collection)

    # ---- sort imported objects ----
    unmapped = []
    for o in imported:
        iid = classify(o)
        if o.type == 'EMPTY':
            o.empty_display_size = 0.01
            o.hide_select = True
            if iid:
                o['xr_item'] = iid
            move_to(o, structure)
            continue
        if iid is None or iid not in byid:
            unmapped.append(o.name)
            iid = None
        if iid:
            o['xr_item'] = iid
            move_to(o, coll_for(iid))
        else:
            move_to(o, structure)
    print('unmapped meshes:', len(unmapped), unmapped[:20])
    counts = {}
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.get('xr_item'):
            counts[o['xr_item']] = counts.get(o['xr_item'], 0) + 1
    empty_items = [it['id'] for it in ITEMS if it['id'] not in counts and not any(c['parent'] == it['id'] for c in ITEMS) and it['kind'] != 'overlay']
    print('items without meshes:', empty_items)

    # ---- light path and eye box ----
    amber = emission_mat('Light path (amber)', (1.0, 0.52, 0.05), 1.0)
    lp = coll_for('lightPath')
    for k, r in enumerate(r for r in O['rays'] if r['eye'] == [0, 0]):
        pts = [sim(p) for p in r['pts']]
        rad = 0.0016 if r['eye'] == [0, 0] else 0.0009
        ob = polyline_mesh(f'ray {k:02d}', list(reversed(pts)), rad, amber, lp)
        ob['xr_item'] = 'lightPath'
        ob.visible_shadow = False
    eyeC = sim(O['EYE'])
    eb = coll_for('eyeBox')
    look = sim(O['LOOK'])
    right = Vector((0, -1, 0))
    up = right.cross(look).normalized()
    if up.z < 0:
        up = -up
    hw, hh = O['EYEBOX_W'] / 2, O['EYEBOX_H'] / 2
    corners = [eyeC + right * sx * hw + up * sy * hh for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1))]
    green = emission_mat('Eye box (green)', (0.05, 0.62, 0.32), 1.0)
    ob = polyline_mesh('eye box frame', corners, 0.0015, green, eb)
    ob['xr_item'] = 'eyeBox'
    ob.visible_shadow = False
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.008, location=eyeC)
    dot = bpy.context.object
    dot.name = 'eye point'
    dot.data.materials.append(green)
    dot['xr_item'] = 'eyeBox'
    move_to(dot, eb)

    # ---- materials: every real material writes the blur mask AOV; give blank meshes a material ----
    import arhud_xray as XR
    plain = bpy.data.materials.new('plain grey')
    plain.use_nodes = True
    for o in bpy.data.objects:
        if o.type == 'MESH' and len(o.material_slots) == 0:
            o.data.materials.append(plain)
    dress_materials()
    for m in bpy.data.materials:
        XR.ensure_aov(m)

    # ---- studio: white everywhere the camera looks, soft light, white floor that catches shadows ----
    world = bpy.data.worlds.new('White studio')
    sc.world = world
    world.color = (1, 1, 1)          # Solid-mode background (viewport shading 'World') and Workbench renders
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    mix = nt.nodes.new('ShaderNodeMixShader')
    lp_node = nt.nodes.new('ShaderNodeLightPath')
    cam_bg = nt.nodes.new('ShaderNodeBackground'); cam_bg.inputs['Color'].default_value = (1, 1, 1, 1); cam_bg.inputs['Strength'].default_value = 1.0
    light_bg = nt.nodes.new('ShaderNodeBackground'); light_bg.inputs['Color'].default_value = (0.93, 0.95, 1.0, 1); light_bg.inputs['Strength'].default_value = 0.45
    nt.links.new(lp_node.outputs['Is Camera Ray'], mix.inputs[0])
    nt.links.new(light_bg.outputs[0], mix.inputs[1])
    nt.links.new(cam_bg.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.render.film_transparent = False

    studio = new_collection('Studio', sc.collection)
    bpy.ops.mesh.primitive_plane_add(size=16, location=(-0.6, -0.4, -0.0005))
    floor = bpy.context.object
    floor.name = 'floor'
    # Emission, not a lit surface: a lit white floor renders above 1.0 and clips, which washes out every ghost seen
    # against it. The ambient-occlusion term darkens it only where something sits close above it (contact shadows).
    fm = bpy.data.materials.new('floor white')
    fn = fm.node_tree.nodes
    fn.clear()
    fo = fn.new('ShaderNodeOutputMaterial')
    fe = fn.new('ShaderNodeEmission')
    fao = fn.new('ShaderNodeAmbientOcclusion')
    fao.inputs['Distance'].default_value = 0.6
    fao.samples = 16
    fr_ = fn.new('ShaderNodeMapRange')
    for k, v in (('From Min', 0.0), ('From Max', 1.0), ('To Min', 0.72), ('To Max', 1.0)):
        fr_.inputs[k].default_value = v
    fm.node_tree.links.new(fao.outputs['AO'], fr_.inputs['Value'])
    fm.node_tree.links.new(fr_.outputs['Result'], fe.inputs['Strength'])
    fe.inputs['Color'].default_value = (1, 1, 1, 1)
    fm.node_tree.links.new(fe.outputs[0], fo.inputs['Surface'])
    floor.data.materials.append(fm)
    floor.hide_select = True
    move_to(floor, studio)

    def light(name, kind, loc, target, energy, size=1.0, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, kind)
        ld.energy = energy
        ld.color = color
        if kind == 'AREA':
            ld.shape = 'DISK'
            ld.size = size
        if kind == 'SUN':
            ld.angle = math.radians(size)
        ld.specular_factor = 0.25           # big soft lights would print white hotspots on every glass and mirror
        o = bpy.data.objects.new(name, ld)
        studio.objects.link(o)
        o.location = loc
        look_at(o, target)
        o.hide_select = True
        return o
    light('Sun', 'SUN', (3, -2, 6), (0, 0, 0), 1.6, size=10)
    light('Key', 'AREA', (2.5, -3.5, 4.0), (0.5, -0.3, 0.8), 380, size=4)
    light('Fill', 'AREA', (-3.0, 3.5, 3.0), (0.5, -0.3, 0.8), 160, size=5, color=(0.92, 0.96, 1.0))

    # ---- cameras ----
    cams = new_collection('Cameras', sc.collection)
    cabin = Vector((0.55, -0.37, 0.75))
    add_camera('CAM Overview', (4.5, -5.2, 4.1), (-0.75, -0.25, 0.35), lens=30, coll=cams)
    add_camera('CAM Auto', (4.5, -5.2, 4.1), (-0.75, -0.25, 0.35), lens=30, coll=cams)
    add_camera('CAM Side', (0.04, 6.9, 0.95), (0.04, -0.37, 0.70), lens=45, coll=cams)
    add_camera('CAM HUD unit', (0.05, 0.42, 1.42), (0.95, -0.02, 0.86), lens=30, coll=cams)
    add_camera('CAM Footwell', (-0.75, -2.15, 1.45), (0.25, -0.62, 0.30), lens=22, coll=cams)
    lo, hi = world_bounds([k for r in roots for k in r.children_recursive])
    bc = (lo + hi) / 2
    add_camera('CAM Bench', (bc.x + 2.4, bc.y - 3.9, 1.7), (bc.x, bc.y, 0.45), lens=30, coll=cams)
    add_camera('CAM Top', (0.04, -0.37, 12), (0.04, -0.37, 0), lens=50, coll=cams, ortho=5.6)
    sc.camera = bpy.data.objects['CAM Overview']

    # ---- render settings ----
    sc.display.shading.color_type = 'MATERIAL'
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1200
    sc.render.resolution_percentage = 100
    ee = sc.eevee
    ee.taa_render_samples = 96
    ee.taa_samples = 16
    ee.use_shadows = True
    ee.shadow_ray_count = 2
    ee.shadow_step_count = 8
    ee.use_raytracing = True
    ee.use_fast_gi = True
    sc.cycles.samples = 128
    sc.view_layers[0].name = 'View layer'
    aov = sc.view_layers[0].aovs.add()
    aov.name = XR.AOV
    aov.type = 'VALUE'

    # ---- compositor: masked blur (blur(img·g) / blur(g), g = 1 - xr_solid), sharp where xr_solid = 1 ----
    def S(coll, ident):
        return next(x for x in coll if x.identifier == ident)
    ng = bpy.data.node_groups.new(XR.COMP_GROUP, 'CompositorNodeTree')
    sc.compositing_node_group = ng
    N = ng.nodes
    rl = N.new('CompositorNodeRLayers'); rl.location = (-800, 0)
    inv = N.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0; inv.location = (-600, -200)
    ng.links.new(rl.outputs[XR.AOV], inv.inputs[1])
    mul = N.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.location = (-400, 100)
    mul.inputs['Factor'].default_value = 1.0
    ng.links.new(rl.outputs['Image'], S(mul.inputs, 'A_Color'))
    ng.links.new(inv.outputs[0], S(mul.inputs, 'B_Color'))
    ba = N.new('CompositorNodeBlur'); ba.name = 'blur_a'; ba.location = (-200, 100)
    bb = N.new('CompositorNodeBlur'); bb.name = 'blur_b'; bb.location = (-200, -200)
    for n in (ba, bb):
        n.inputs['Size'].default_value = (14, 14)
        try:
            n.inputs['Type'].default_value = 'Gaussian'
        except Exception as e:
            print('blur type', e)
    ng.links.new(S(mul.outputs, 'Result_Color'), ba.inputs['Image'])
    ng.links.new(inv.outputs[0], bb.inputs['Image'])
    mx = N.new('ShaderNodeMath'); mx.operation = 'MAXIMUM'; mx.inputs[1].default_value = 1e-4; mx.location = (0, -200)
    ng.links.new(bb.outputs['Image'], mx.inputs[0])
    div = N.new('ShaderNodeMix'); div.data_type = 'RGBA'; div.blend_type = 'DIVIDE'; div.location = (200, 100)
    div.inputs['Factor'].default_value = 1.0
    ng.links.new(ba.outputs['Image'], S(div.inputs, 'A_Color'))
    ng.links.new(mx.outputs[0], S(div.inputs, 'B_Color'))
    fin = N.new('ShaderNodeMix'); fin.data_type = 'RGBA'; fin.location = (400, 0)
    ng.links.new(rl.outputs[XR.AOV], fin.inputs['Factor'])
    ng.links.new(S(div.outputs, 'Result_Color'), S(fin.inputs, 'A_Color'))
    ng.links.new(rl.outputs['Image'], S(fin.inputs, 'B_Color'))
    go = N.new('NodeGroupOutput'); go.location = (650, 0)
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    ng.links.new(S(fin.outputs, 'Result_Color'), go.inputs[0])
    vw = N.new('CompositorNodeViewer'); vw.location = (650, -200)
    ng.links.new(S(fin.outputs, 'Result_Color'), vw.inputs[0])
    sc.render.use_compositing = False

    # ---- items, embedded module, initial state ----
    t = bpy.data.texts.new(XR.ITEMS_TEXT)
    t.from_string(json.dumps({'categories': CATEGORIES, 'items': ITEMS}, indent=1, ensure_ascii=False))
    code = open(os.path.join(HERE, 'arhud_xray.py')).read()
    mt = bpy.data.texts.new('arhud_xray.py')
    mt.from_string(code)
    mt.use_module = True
    readme = bpy.data.texts.new('READ ME')
    readme.from_string(open(os.path.join(HERE, 'README.md')).read() if os.path.exists(os.path.join(HERE, 'README.md')) else '')
    XR.sync_items(sc)
    for c in XR.settings(sc).cats:
        c.expanded = c.cid == 'hud'
    for r in XR.settings(sc).items:
        r.expanded = r.iid in ('hudUnit',)
    XR.reset_defaults(sc)
    XR.ensure_ghosts(XR.settings(sc))
    # overview: fit every item along the overview direction (the car, its parts and the bench row behind it)
    bpy.context.view_layer.update()
    tops = [it['id'] for it in ITEMS if not it.get('parent')]
    for name in ('CAM Overview', 'CAM Auto'):
        XR.frame_camera(sc, bpy.data.objects[name], ids=tops, margin=1.04)

    # ---- viewport: material preview, sidebar open, framed on the car ----
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type != 'VIEW_3D':
                continue
            for sp in area.spaces:
                if sp.type != 'VIEW_3D':
                    continue
                sp.shading.type = 'MATERIAL'
                sp.shading.color_type = 'MATERIAL'        # Solid mode: ghosts use the ghost materials' translucent colour
                sp.shading.background_type = 'WORLD'      # Solid mode: white background from the world colour
                sp.shading.use_scene_world = True
                sp.shading.use_scene_lights = True
                sp.show_region_ui = True
                sp.overlay.show_floor = False
                sp.overlay.show_axis_x = False
                sp.overlay.show_axis_y = False
                sp.overlay.show_relationship_lines = False
                sp.overlay.show_extras = False
                sp.clip_start = 0.005
                r3 = sp.region_3d
                r3.view_location = (0.3, -0.6, 0.7)
                r3.view_distance = 6.0
                cam = bpy.data.objects['CAM Overview']
                fwd = cam.rotation_euler.to_quaternion() @ Vector((0, 0, -1))
                r3.view_rotation = cam.rotation_euler.to_quaternion()
                lo, hi = world_bounds([o for o in bpy.data.objects if o.get('xr_item')])
                d = ((lo + hi) / 2 - cam.location).dot(fwd)
                right = cam.rotation_euler.to_quaternion() @ Vector((1, 0, 0))
                r3.view_distance = d
                r3.view_location = cam.location + fwd * d + right * d * 0.12   # content clear of the sidebar
                r3.view_perspective = 'PERSP'
                sp.lens = 45
            for rg in area.regions:
                if rg.type == 'UI':
                    try:
                        rg.active_panel_category = 'AR HUD'
                    except Exception as e:
                        print('sidebar tab:', e)

    notice = add_notice(studio)
    notice.hide_viewport = False
    notice.hide_render = False
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = None
    bpy.context.preferences.filepaths.save_version = 0       # no arhud-xray.blend1 backup next to the file
    bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
    print('saved', OUT, 'objects', len(bpy.data.objects))


if __name__ == '__main__':
    build()
