// Dump the simulator's installed optical layout to layout.json for the build123d housing.
// Run from this folder:  node dump_layout.mjs
//
// geom.js and optics.js are the single source of the layout (they are built from calc.py through params.js), so the
// CAD sits on exactly the numbers the simulator traces. Frame: X forward, Y up, Z right, metres, origin on the road
// under the driver's nominal eye. three.js resolves through docs/arhud-sim/node_modules (`npm install three@0.170.0`
// there, or a symlink to any copy of it).
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const G = await import('../arhud-sim/js/geom.js');
const { R } = await import('../arhud-sim/js/params.js');
const { PANEL, BACKLIGHT_DEPTH } = await import('../arhud-sim/js/components/pgu.js');
const O = await import('../arhud-sim/js/components/optics.js');

const v = (p) => [p.x, p.y, p.z];
const lay = O.housingLayout('toroid');
const ff = O.foldFrame('toroid');

// Every sampled ray (eye-box grid x field grid) for both mirror figures: eye, glass, mirror, fold, panel.
const rays = {};
for (const mode of ['toroid', 'sphere']) {
  rays[mode] = O.sampleRays(mode, 5).map((r) => ({ pts: r.pts.map(v), inside: r.mirror.inside, e: [r.ex, r.ey], f: [r.fx, r.fy] }));
}
// The mirror surface itself (biconic sag) on a grid, so the CAD can model the substrate the cradle holds.
const sag = (mode) => { const { Rt, Rs } = G.mirrorRadii(mode); return { Rt, Rs }; };

const out = {
  generated_from: 'docs/arhud-sim/js/geom.js and components/optics.js via docs/arhud-cad/dump_layout.mjs',
  frame: 'X forward, Y up, Z right, metres; origin on the road under the nominal eye',
  eye: v(G.EYE),
  glass: { G: v(G.G), N: v(G.GLASS_N), rakeDeg: R.RAKE, T: G.GLASS_T, cowlY: G.COWL_Y },
  mirror: {
    C: v(G.MIRROR_C), N: v(G.MIRROR_N), U: v(G.MIRROR_U), V: v(G.MIRROR_V), W: G.MIRROR_W, H: G.MIRROR_H,
    back: 0.012,                                   // optics.js MIRROR_BACK: substrate thickness behind the vertex
    toroid: sag('toroid'), sphere: sag('sphere'), incDeg: G.MIRROR_INC * 180 / Math.PI,
  },
  fold: { C: v(G.FOLD_C), N: v(G.FOLD_N), incDeg: G.FOLD_INC * 180 / Math.PI,
    fu: v(ff.fu), fv: v(ff.fv), u0: ff.u0, u1: ff.u1, v0: ff.v0, v1: ff.v1, thick: ff.thick, footprint: ff.footprint },
  panel: { C: v(G.PANEL_C), outX: PANEL.outX, outZ: PANEL.outZ, cropX: PANEL.cropX, cropZ: PANEL.cropZ,
    activeX: PANEL.activeX, activeZ: PANEL.activeZ, backlightDepth: BACKLIGHT_DEPTH },
  housing: G.HOUSING,
  layout: { floor: lay.floor, xF: lay.xF, xR: lay.xR, yF: lay.yF, s: lay.s, ax0: lay.ax0, ax1: lay.ax1, az0: lay.az0,
    az1: lay.az1, L: lay.L, W: lay.W, garageLen: lay.garageLen, xGarage: lay.xGarage, apC: v(lay.apC), zW: lay.zW,
    lidDir: v(lay.lidDir), lidN: v(lay.lidN) },
  rays,
  params: { PGU_W: R.PGU_W, PGU_H: R.PGU_H, F2: R.F2, U2: R.U2, R_SPH: R.R_SPH },
};
writeFileSync(join(here, 'layout.json'), JSON.stringify(out, null, 1));
const nIn = rays.toroid.filter((r) => r.inside).length;
console.log(`wrote layout.json: housing ${((lay.xF - lay.xR) * 1000).toFixed(0)} x ${(2 * lay.zW * 1000).toFixed(0)} mm, ` +
  `${rays.toroid.length} rays per figure (${nIn} land on the mirror)`);
