// Dump the simulator's installed layout (docs/arhud-sim/js/geom.js) to layout.json for the Blender scripts.
// Run: node dump_layout.mjs      (needs `npm install` here once; three.js is the only dependency)
//
// geom.js is the single source of the optical layout, so the Blender scene is built from the same numbers the
// simulator traces, in the same frame: X forward, Y up, Z right, metres, origin on the road under the driver's eye.
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const G = await import('../arhud-sim/js/geom.js');
const { R, P } = await import('../arhud-sim/js/params.js');
const { PANEL } = await import('../arhud-sim/js/components/pgu.js').catch(() => ({ PANEL: null }));
const optics = await import('../arhud-sim/js/components/optics.js').catch((e) => { console.warn('optics.js not importable:', e.message); return null; });

const v = (p) => [p.x, p.y, p.z];
const im = G.mirrorImages('toroid'), imS = G.mirrorImages('sphere');
const fp = G.footprints('toroid');
const box = (b) => ({ min: v(b.min), max: v(b.max) });

const out = {
  generated_from: 'docs/arhud-sim/js/geom.js via docs/arhud-blender/dump_layout.mjs',
  frame: 'X forward, Y up, Z right, metres; origin on the road under the nominal eye',
  eye: v(G.EYE), look: v(G.LOOK), eyeH: G.EYE_H,
  lookdownDeg: R.LOOKDOWN, rakeDeg: R.RAKE,
  eyeToGlass: G.EYE_TO_GLASS, glassToMirror: G.GLASS_TO_MIRROR, u: G.U, fMirror: G.F_MIRROR, vid: G.VID,
  fovW: G.FOV_W, fovH: G.FOV_H, imgW: G.IMG_W, imgH: G.IMG_H,
  eyeboxW: G.EYEBOX_W, eyeboxH: G.EYEBOX_H,
  glass: { G: v(G.G), N: v(G.GLASS_N), UP: v(G.GLASS_UP), T: G.GLASS_T, cowlY: G.COWL_Y, roofY: G.ROOF_Y, bottomX: G.WS_BOTTOM_X, topX: G.WS_TOP_X, nGlass: R.N_GLASS, thetaI: R.THETA_I },
  mirror: {
    C: v(G.MIRROR_C), N: v(G.MIRROR_N), U: v(G.MIRROR_U), V: v(G.MIRROR_V), W: G.MIRROR_W, H: G.MIRROR_H,
    incDeg: G.MIRROR_INC * 180 / Math.PI,
    sphere: { Rt: G.R_SPHERE, Rs: G.R_SPHERE, vt: imS.vt, vs: imS.vs },
    toroid: { Rt: G.R_T_CORR, Rs: G.R_S_CORR, vt: im.vt, vs: im.vs },
    eyeToMirror: im.eyeToMirror,
    footprintUV: box(fp.mirrorUV),
  },
  fold: { C: v(G.FOLD_C), N: v(G.FOLD_N), incDeg: G.FOLD_INC * 180 / Math.PI, box: box(fp.foldBox) },
  // the fold glass as the housing builder sizes it: lateral u (car Z) and in-plane v extents about FOLD_C, metres
  foldFrame: optics ? (({ fu, fv, u0, u1, v0, v1, thick, footprint }) => ({ fu: v(fu), fv: v(fv), u0, u1, v0, v1, thick, footprint }))(optics.foldFrame('toroid')) : null,
  housingLayout: optics ? (({ xF, xR, yF, s, ax0, ax1, az0, az1, L, W, garageLen, xGarage, apC, zW }) => ({ xF, xR, yF, s, ax0, ax1, az0, az1, L, W, garageLen, xGarage, apC: v(apC), zW }))(optics.housingLayout('toroid')) : null,
  panel: { C: v(G.PANEL_C), N: v(G.PANEL_N), cropZ: PANEL ? PANEL.cropZ : R.PGU_W / 1000, cropX: PANEL ? PANEL.cropX : R.PGU_H / 1000, box: box(fp.panelBox) },
  vimg: { C: v(G.VIMG_C), N: v(G.VIMG_N), RIGHT: v(G.VIMG_RIGHT), UP: v(G.VIMG_UP) },
  housing: G.HOUSING,
  road: { near: G.ROAD_NEAR, far: G.ROAD_FAR },
  carCenterZ: G.CAR_CENTER_Z,
  mounts: { roadCam: v(G.ROAD_CAM), mirrorStalk: v(G.MIRROR_STALK), driverCam: v(G.DRIVER_CAM), gnss: v(G.GNSS_ANT), jetson: v(G.JETSON), dcdc: v(G.DCDC), ethSwitch: v(G.SWITCH), miniPC: v(G.MINIPC2), monitor: v(G.MONITOR2), accSocket: v(G.ACC_SOCKET) },
  ghost: { perpMm: R.GHOST_PERP, arcmin75: R.GHOST_75 },
  // the traced corner rays (nominal eye, window corners): where they land on each surface
  corners: Object.fromEntries(['tl', 'tr', 'bl', 'br', 'c'].map((k) => {
    const [fx, fy] = { tl: [-1, 1], tr: [1, 1], bl: [-1, -1], br: [1, -1], c: [0, 0] }[k];
    const r = G.traceFromEye(G.EYE, G.fieldDir(fx * G.FOV_W / 2, fy * G.FOV_H / 2), 'toroid');
    return [k, r ? { pts: r.pts.map(v), panelZ: r.panelZ, panelX: r.panelX } : null];
  })),
  simNotes: G.SIM_NOTES.map((n) => n.text),
  params: { assumed: P.assumed, raw: R },
};
const file = join(here, 'layout.json');
writeFileSync(file, JSON.stringify(out, null, 1));
console.log('wrote', file);
console.log(`mirror C ${v(G.MIRROR_C).map((x) => x.toFixed(4))}, inc ${(G.MIRROR_INC * 180 / Math.PI).toFixed(2)} deg, toroid Rt ${(G.R_T_CORR * 1000).toFixed(1)} Rs ${(G.R_S_CORR * 1000).toFixed(1)} mm`);
console.log(`sphere images vt ${imS.vt.toFixed(2)} vs ${imS.vs.toFixed(2)} m; toroid vt ${im.vt.toFixed(2)} vs ${im.vs.toFixed(2)} m; eye-mirror ${im.eyeToMirror.toFixed(3)} m`);
