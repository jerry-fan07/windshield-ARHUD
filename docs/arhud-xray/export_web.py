# Exports arhud-xray.blend for the web viewer: viewer/arhud.glb.gz and viewer/arhud.glb (every component with its real
# materials, each node tagged with its item id in glTF extras; gzip and Draco versions) and viewer/items.json (the item tree, descriptions and facts).
#
#   /Applications/Blender.app/Contents/MacOS/Blender -b docs/arhud-xray/arhud-xray.blend -P docs/arhud-xray/export_web.py
import base64
import gzip
import json
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import arhud_xray as XR  # noqa: E402

OUT = os.path.join(HERE, 'viewer')
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
XR.sync_items(sc)
ghosts = XR.ensure_ghosts(XR.settings(sc))
for o in sc.objects:
    if o.get('xr_item') is not None:
        XR.set_state(o, 'SOLID', ghosts)
# camera presets for the viewer, in glTF axes (x, z, -y): position, a target 3 m ahead, vertical field of view
import math
from mathutils import Vector
W, H = sc.render.resolution_x, sc.render.resolution_y
cams = []
for key, label, name in XR.CAMERAS:
    o = bpy.data.objects.get(name)
    if not o:
        continue
    fwd = o.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    p = o.matrix_world.translation
    t = p + fwd * (3.0 if key not in ('overview', 'bench', 'top', 'side') else (p - Vector((0.3, -0.37, 0.6))).length)
    h = o.data.angle if W >= H else 2 * math.atan(math.tan(o.data.angle / 2) * W / H)
    vfov = math.degrees(2 * math.atan(math.tan(h / 2) * H / W))
    g = lambda v: [round(v.x, 4), round(v.z, 4), round(-v.y, 4)]
    cams.append({'key': key, 'label': label, 'position': g(p), 'target': g(t), 'vfov': round(vfov, 2),
                 'ortho': o.data.type == 'ORTHO', 'orthoScale': o.data.ortho_scale})
json.dump(cams, open(os.path.join(OUT, 'cameras.json'), 'w'), indent=1)
# studio, cameras and lights stay in Blender
for o in list(sc.objects):
    if o.type in {'CAMERA', 'LIGHT', 'FONT'} or o.name == 'floor':
        bpy.data.objects.remove(o, do_unlink=True)
for o in sc.objects:
    o.select_set(False)
    for k in [k for k in o.keys() if k not in ('xr_item',)]:
        del o[k]
common = dict(export_format='GLB', export_extras=True, export_cameras=False, export_lights=False, export_apply=True,
              export_yup=True, export_image_format='WEBP', export_jpeg_quality=85, export_materials='EXPORT', use_visible=False)
# Plain GLB, gzipped: 3.3 MB, decoded in the browser by the built-in DecompressionStream (no worker, no WebAssembly)
plain = os.path.join(OUT, 'arhud-plain.glb')
bpy.ops.export_scene.gltf(filepath=plain, **common)
with open(plain, 'rb') as f, gzip.open(os.path.join(OUT, 'arhud.glb.gz'), 'wb', compresslevel=9) as g:
    g.write(f.read())
os.remove(plain)
# The same bytes as base64 text: the claude.ai artifact host serves only web file types (.txt yes, .gz and .glb no)
with open(os.path.join(OUT, 'arhud.glb.gz'), 'rb') as f, open(os.path.join(OUT, 'arhud.glb.gz.b64.txt'), 'w') as t:
    t.write(base64.b64encode(f.read()).decode('ascii'))
# Draco GLB: the fallback for browsers without DecompressionStream
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, 'arhud.glb'), export_draco_mesh_compression_enable=True,
                          export_draco_mesh_compression_level=7, **common)
d = XR.data()
json.dump(d, open(os.path.join(OUT, 'items.json'), 'w'), ensure_ascii=False, indent=1)
print('exported', os.path.getsize(os.path.join(OUT, 'arhud.glb.gz')), 'bytes gz,', os.path.getsize(os.path.join(OUT, 'arhud.glb')), 'bytes draco')
