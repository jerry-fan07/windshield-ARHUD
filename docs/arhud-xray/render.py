# Command-line renders of the x-ray display, using the same switching code as the panel.
#
#   B=/Applications/Blender.app/Contents/MacOS/Blender
#   $B -b docs/arhud-xray/arhud-xray.blend -P docs/arhud-xray/render.py -- --show jetson,zed2i --camera auto --out /tmp/a.png
#   $B -b docs/arhud-xray/arhud-xray.blend -P docs/arhud-xray/render.py -- --gallery docs/arhud-xray/renders/gallery
#
# --show      default | all | none | comma-separated item ids (see --list)
# --mode      XRAY | FADE | HIDE (how everything else is drawn)
# --blur N    blur the ghosts with an N-pixel compositor blur
# --camera    overview | side | hud | footwell | bench | top | auto (fit along the overview direction) | auto:<preset>
# --res WxH, --samples N, --engine eevee|cycles, --list (print the item ids and exit)
import argparse
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import arhud_xray as XR  # noqa: E402  (registers the panel classes and scene.arhud)

CAM = {k: c for k, _l, c in XR.CAMERAS}
# preset direction each item is best seen from in the gallery
# (a preset name, or a view direction for items no preset sees well)
GALLERY_VIEW = {'hud': 'hud', 'sensor': 'overview', 'compute': 'footwell', 'controller': 'hud', 'power': 'footwell',
                'network': 'footwell', 'cables': 'footwell', 'optics': 'side', 'bench': 'bench', 'vehicle': 'overview'}
ITEM_VIEW = {'zed2i': 'overview', 'oakdPro': 'hud', 'gnssAntenna': 'hud', 'miniPC': 'footwell', 'fuseTap': 'footwell',
             'pdCharger': 'footwell', 'ledDriver': 'hud', 'windshield': 'overview', 'eyeBox': 'hud', 'housing': 'overview',
             'concaveMirror': 'side', 'coldMirror': (-0.55, 0.30, 0.78), 'hudUnit': 'hud',
             'monitor': (0.9, 0.3, -0.3)}
# shown as a cutaway: these items render with part of themselves ghosted so the inside can be seen
GHOST_EXTRA = {'hudUnit': ['housing']}
ITEM_MARGIN = {'cables_usb': 1.15, 'cables_power': 1.15, 'cables_hdmi': 1.15, 'cables_eth': 1.15, 'cables_serial': 1.15, 'cables_rf': 1.15}


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument('--show', default='default')
    p.add_argument('--mode', default='XRAY')
    p.add_argument('--blur', type=int, default=0)
    p.add_argument('--camera', default='overview')
    p.add_argument('--out', default=os.path.join(HERE, 'renders', 'render.png'))
    p.add_argument('--res', default='1600x1000')
    p.add_argument('--samples', type=int, default=48)
    p.add_argument('--engine', default='eevee')
    p.add_argument('--gallery', default='')
    p.add_argument('--margin', type=float, default=1.35)
    p.add_argument('--list', action='store_true')
    return p.parse_args(a)


def use_camera(sc, key, margin, ids=None):
    if isinstance(key, tuple):
        cam = bpy.data.objects['CAM Auto']
        cam.matrix_world = Matrix.Translation((0, 0, 0)) @ Vector(key).to_track_quat('-Z', 'Y').to_matrix().to_4x4()
        cam.data.lens = 35
        cam.data.type = 'PERSP'
        XR.frame_camera(sc, cam, ids=ids, margin=margin)
    elif key.startswith('auto'):
        preset = key.split(':', 1)[1] if ':' in key else 'overview'
        src = bpy.data.objects[CAM[preset]]
        cam = bpy.data.objects['CAM Auto']
        cam.matrix_world = src.matrix_world.copy()
        cam.data.lens = src.data.lens
        cam.data.type = src.data.type
        XR.frame_camera(sc, cam, ids=ids, margin=margin)
    else:
        cam = bpy.data.objects[CAM[key]]
    sc.camera = cam


def render(sc, out):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sc.render.filepath = os.path.abspath(out)
    bpy.ops.render.render(write_still=True)
    print('wrote', out)


def main():
    A = args()
    sc = bpy.context.scene
    XR.sync_items(sc)
    s = XR.settings(sc)
    if A.list:
        for it in XR.data()['items']:
            print(f"{it['id']:<22} {it['cat']:<11} {'  ' if it.get('parent') else ''}{it['name']}")
        return
    w, h = map(int, A.res.lower().split('x'))
    sc.render.resolution_x, sc.render.resolution_y = w, h
    if A.engine == 'cycles':
        sc.render.engine = 'CYCLES'
        sc.cycles.samples = A.samples
        try:
            prefs = bpy.context.preferences.addons['cycles'].preferences
            prefs.compute_device_type = 'METAL'
            prefs.get_devices()
            for d in prefs.devices:
                d.use = True
            sc.cycles.device = 'GPU'
        except Exception as e:
            print('cycles gpu:', e)
    else:
        sc.render.engine = 'BLENDER_EEVEE'
        sc.eevee.taa_render_samples = A.samples
    XR._busy[0] = True
    s.mode = A.mode
    XR._busy[0] = False
    if A.blur:
        s.blur_size = A.blur
    XR.set_blur(sc, bool(A.blur))
    if A.gallery:
        items = XR.data()['items']
        for it in items:
            if it['kind'] == 'cable' and it.get('parent'):
                continue
            XR.isolate(sc, [it['id']])
            if it['id'] in GHOST_EXTRA:
                XR.set_solid(sc, GHOST_EXTRA[it['id']], False)
            view = ITEM_VIEW.get(it['id'], GALLERY_VIEW.get(it['cat'], 'overview'))
            use_camera(sc, view if isinstance(view, tuple) else 'auto:' + view, ITEM_MARGIN.get(it['id'], A.margin), ids=[it['id']])
            render(sc, os.path.join(A.gallery, f"{it['cat']}-{it['id']}.png"))
        XR.reset_defaults(sc)
        return
    if A.show == 'default':
        XR.reset_defaults(sc)
    elif A.show == 'all':
        XR.set_solid(sc, [], True, others=True)
    elif A.show == 'none':
        XR.set_solid(sc, [], True, others=False)
    else:
        XR.isolate(sc, [i.strip() for i in A.show.split(',') if i.strip()])
    XR.apply(sc)
    use_camera(sc, A.camera, A.margin)
    render(sc, A.out)


main()
