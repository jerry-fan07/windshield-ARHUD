// Dump the traced HUD window and the optical layout from the 3-D simulator (docs/arhud-sim) to
// arhud_road/traced.json, so the MetaDrive road simulator uses the same ray trace instead of a second copy of it.
// Run: node tools/dump_traced.mjs      (three.js resolves through docs/arhud-sim/node_modules)
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const G = await import('../../arhud-sim/js/geom.js');
const { tracedWindow } = await import('../../arhud-sim/js/hud.js');
const v = (p) => [p.x, p.y, p.z];
const tw = tracedWindow();
const im = G.mirrorImages('toroid');
const out = {
  generated_from: 'docs/arhud-sim/js/geom.js and hud.js tracedWindow() via docs/arhud-road/tools/dump_traced.mjs',
  frame: 'X forward, Y up, Z right, metres; origin on the road under the nominal eye',
  eye: v(G.EYE), look: v(G.LOOK), roadCam: v(G.ROAD_CAM), driverCam: v(G.DRIVER_CAM), carCenterZ: G.CAR_CENTER_Z,
  eyeToMirror: im.eyeToMirror, mirrorW: G.MIRROR_W, mirrorH: G.MIRROR_H,
  glass: { G: v(G.G), N: v(G.GLASS_N), cowlY: G.COWL_Y, roofY: G.ROOF_Y, bottomX: G.WS_BOTTOM_X, topX: G.WS_TOP_X },
  entry: v(G.TO_MIRROR.clone().negate()),
  traced: { dist: tw.dist, w: tw.w, h: tw.h, fovW: tw.fovW, fovH: tw.fovH, topW: tw.topW, botW: tw.botW },
};
writeFileSync(join(here, '..', 'arhud_road', 'traced.json'), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out.traced), 'eyeToMirror', out.eyeToMirror);
