// The installed layout: where every optical surface and every component sits in the car, computed from params.js.
//
// Simulation frame (Three.js): X forward, Y up, Z right, metres. Origin on the road surface directly below the
// driver's nominal eye point. The plan's car frame (x forward, y right, z down, origin at the ZED left lens) is
// related by a translation and an axis swap: see toPlanFrame().
//
// The side-view optical design (all in the vertical plane through the eye):
//   eye --(look-down 5 deg, 750 mm)--> glass point G --(reflected, 51 deg below horizontal forward)--> concave mirror M
//   M --(rearward and up at FOLD_ELEV)--> cold-mirror fold F --(straight down)--> panel P.  |MF| + |FP| = u.
// The plan's assumed 1 m eye-to-mirror path puts the top of a 200 mm-tall mirror into a 28-degree windshield, so the
// simulation uses GLASS_TO_MIRROR = 0.31 m (path 1.06 m), which leaves about 24 mm of clearance. See SIM_NOTES.
import * as THREE from 'three';
import { R } from './params.js';
import { DEG } from './util.js';
import { FREEFORM } from './freeform.js';
import { FREEFORM as FREEFORM_CURVED } from './freeform_curved.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);

export const EYE_H = R.H_CAM;                     // 1.22 m eye height (plan's worked example)
export const RAKE = R.RAKE * DEG;                 // windshield angle above horizontal (ASSUMED 28)
export const LOOKDOWN = R.LOOKDOWN * DEG;         // eye ray depression to the window centre (ASSUMED 5)
export const EYE_TO_GLASS = R.L_EYE_GLASS / 1000; // 0.75 m (ASSUMED)
export const GLASS_TO_MIRROR = 0.31;              // sim choice; plan ASSUMED 0.25 (1 m path) does not clear the glass
export const FOLD_ELEV = 20 * DEG;                // direction mirror -> fold, above the rearward horizontal (sim choice; 25 deg let the fold clip the exit beam)
export const FOLD_TO_PANEL = 0.05;                // vertical leg fold -> panel (sim choice)
export const U = R.U2 / 1000;                     // 0.316 m PGU distance
export const F_MIRROR = R.F2 / 1000;              // 0.330 m
export const VID = R.D_IMG / 1000;                // 7.5 m virtual image distance from the eye
export const FOV_W = R.FOV_W * DEG, FOV_H = R.FOV_H * DEG;
export const IMG_W = R.PGU_W * R.M2 / 1000, IMG_H = R.PGU_H * R.M2 / 1000; // 1.42 x 0.71 m
export const EYEBOX_W = R.EYEBOX_W / 1000, EYEBOX_H = R.EYEBOX_H / 1000;
export const MIRROR_W = 0.300, MIRROR_H = 0.200;   // plan's quoted aperture
export const CAR_CENTER_Z = 0.37;                  // car centreline is to the driver's right (left-hand drive)

export const SIM_NOTES = [];

// ---- eye and windshield -----------------------------------------------------
export const EYE = V(0, EYE_H, 0);
export const LOOK = V(Math.cos(LOOKDOWN), -Math.sin(LOOKDOWN), 0);          // unit view direction to window centre
export const G = EYE.clone().addScaledVector(LOOK, EYE_TO_GLASS);           // glass point on the inner surface
export const GLASS_N = V(Math.sin(RAKE), Math.cos(RAKE), 0);                // outward normal (forward and up)
export const GLASS_UP = V(-Math.cos(RAKE), Math.sin(RAKE), 0);              // along the glass, toward the roof
export const GLASS_T = R.T_GLASS / 1000;                                    // 4.96 mm laminate (ASSUMED)
export const glassYAt = (x) => G.y - (x - G.x) * Math.tan(RAKE);            // inner surface height at fore-aft x
export const glassXAt = (y) => G.x - (y - G.y) / Math.tan(RAKE);
export const COWL_Y = 0.80, ROOF_Y = 1.385;                                 // windshield bottom and top edges
export const WS_BOTTOM_X = glassXAt(COWL_Y), WS_TOP_X = glassXAt(ROOF_Y);

export function reflect(d, n) { return d.clone().addScaledVector(n, -2 * d.dot(n)); }

// Reflected direction of the eye ray (the HUD light travels the reverse way).
export const TO_MIRROR = reflect(LOOK, GLASS_N).normalize();                // forward and down at 51 deg
export const MIRROR_C = G.clone().addScaledVector(TO_MIRROR, GLASS_TO_MIRROR);
export const TO_FOLD = V(-Math.cos(FOLD_ELEV), Math.sin(FOLD_ELEV), 0);     // from the mirror centre toward the fold
export const FOLD_C = MIRROR_C.clone().addScaledVector(TO_FOLD, U - FOLD_TO_PANEL);
export const PANEL_C = FOLD_C.clone().add(V(0, -FOLD_TO_PANEL, 0));
export const PANEL_N = V(0, 1, 0);
// The panel's pose per mirror mode: flat as the plan has it; the freeform design tilts it about the lateral axis and
// shifts it along the fold-to-panel leg (freeform_mirror.py fitted both with the surface, which is what gives a flat
// image and straight window edges together). U is the lateral in-plane axis, VP the fore-aft one (+x when flat).
export function panelPose(mode = MIRROR.mode) {
  const f = fitOf(mode);
  const th = f ? (f.panelTiltDeg || 0) * DEG : 0;
  const dz = f ? (f.panelShiftMm || 0) / 1000 : 0;
  const N = V(-Math.sin(th), Math.cos(th), 0);
  const U = V(0, 0, 1);
  const VP = new THREE.Vector3().crossVectors(N, U);
  return { C: PANEL_C.clone().add(V(0, -dz, 0)), N, U, VP, tiltDeg: th / DEG, shiftMm: dz * 1000 };
}

// Concave mirror orientation: normal bisects the directions to the glass and to the fold.
const toGlass = TO_MIRROR.clone().negate();
export const MIRROR_N = toGlass.clone().add(TO_FOLD).normalize();
export const MIRROR_INC = Math.acos(MIRROR_N.dot(toGlass));                 // incidence at the centre, radians
export const MIRROR_U = V(0, 0, 1);                                          // lateral axis (sagittal), 300 mm
export const MIRROR_V = new THREE.Vector3().crossVectors(MIRROR_N, MIRROR_U).negate().normalize(); // in the side plane (tangential), 200 mm
if (MIRROR_V.y < 0) MIRROR_V.negate();
// Radii. Plan as written: sphere R = 2f. Corrected: toroid with Rt = 2f / cos(i), Rs = 2f cos(i) (Coddington), which
// gives both foci at f for this incidence.
export const R_SPHERE = R.R_SPH / 1000;
export const R_T_CORR = 2 * F_MIRROR / Math.cos(MIRROR_INC);
export const R_S_CORR = 2 * F_MIRROR * Math.cos(MIRROR_INC);
export const MIRROR = { mode: 'toroid' };                                    // 'sphere' (as written), 'toroid', 'freeform', 'freeformCurved'
// The freeform fits from docs/arhud-blender/freeform_mirror.py: a polynomial sag (with a panel tilt and shift) that
// puts the virtual image at one distance over the whole window. 'freeform' is fitted for the plan's flat glass,
// 'freeformCurved' for a windshield with 4 m lateral and 8 m vertical radii (see GLASS and setGlassForMode).
export const FITS = { freeform: FREEFORM, freeformCurved: FREEFORM_CURVED };
const fitOf = (mode) => FITS[mode] || null;
// The windshield's curvature in the trace: radii in metres, 0 = the plan's flat plane. A real windshield wraps toward
// the pillars and the roof, so its surfaces come toward the cabin away from the glass point: w = b^2/2Rh + a^2/2Rv
// along -GLASS_N, with a along GLASS_UP and b lateral.
export const GLASS = { Rh: 0, Rv: 0 };
export function setGlassForMode(mode = MIRROR.mode) {
  const f = fitOf(mode);
  GLASS.Rh = f && f.glass ? f.glass.Rh : 0;
  GLASS.Rv = f && f.glass ? f.glass.Rv : 0;
  return GLASS;
}
export function mirrorRadii(mode = MIRROR.mode) {
  const f = fitOf(mode);
  if (f) return { Rt: f.Rt, Rs: f.Rs };
  return mode === 'sphere' ? { Rt: R_SPHERE, Rs: R_SPHERE } : { Rt: R_T_CORR, Rs: R_S_CORR };
}
// Sag w(u, v) along MIRROR_N and its gradient, for any mode (the sphere and toroid are the paraboloid the trace uses).
export function mirrorSag(u, v, mode = MIRROR.mode) {
  const f = fitOf(mode);
  if (f) { let w = 0; f.terms.forEach(([i, j], k) => { w += f.c[k] * u ** i * v ** j; }); return w; }
  const { Rt, Rs } = mirrorRadii(mode);
  // the true surfaces, as Cycles builds them (the paraboloid they were traced as before is 0.4 mm low at the
  // edge of the 300 x 200 mm aperture, 18' of slope, which showed as 33' of registration error at the eye-box edge)
  if (Math.abs(Rt - Rs) < 1e-9) return Rt - Math.sqrt(Math.max(0, Rt * Rt - u * u - v * v));
  const A = Rt - Rs + Math.sqrt(Math.max(0, Rs * Rs - u * u));
  return Rt - Math.sqrt(Math.max(0, A * A - v * v));
}
// Local curvatures d2w/du2 and d2w/dv2 (the sagittal and tangential principal curvatures near the plane of symmetry).
export function mirrorCurv(u, v, mode = MIRROR.mode) {
  const f = fitOf(mode);
  if (f) {
    let cu = 0, cv = 0;
    f.terms.forEach(([i, j], k) => { if (i > 1) cu += f.c[k] * i * (i - 1) * u ** (i - 2) * v ** j; if (j > 1) cv += f.c[k] * j * (j - 1) * u ** i * v ** (j - 2); });
    return [cu, cv];
  }
  // the true sphere and toroid: second derivatives by central differences (1/Rs and 1/Rt at the vertex)
  const h = 1e-4, w0 = mirrorSag(u, v, mode);
  return [(mirrorSag(u + h, v, mode) - 2 * w0 + mirrorSag(u - h, v, mode)) / (h * h), (mirrorSag(u, v + h, mode) - 2 * w0 + mirrorSag(u, v - h, mode)) / (h * h)];
}
export function mirrorGrad(u, v, mode = MIRROR.mode) {
  const f = fitOf(mode);
  if (f) {
    let du = 0, dv = 0;
    f.terms.forEach(([i, j], k) => { if (i > 0) du += f.c[k] * i * u ** (i - 1) * v ** j; if (j > 0) dv += f.c[k] * j * u ** i * v ** (j - 1); });
    return [du, dv];
  }
  const { Rt, Rs } = mirrorRadii(mode);
  if (Math.abs(Rt - Rs) < 1e-9) { const S = Math.sqrt(Math.max(1e-12, Rt * Rt - u * u - v * v)); return [u / S, v / S]; }
  const q = Math.sqrt(Math.max(1e-12, Rs * Rs - u * u)), A = Rt - Rs + q, S = Math.sqrt(Math.max(1e-12, A * A - v * v));
  return [A * u / (S * q), v / S];
}

// Fold: reflects light going up from the panel into the direction fold -> mirror.
const foldIn = V(0, 1, 0), foldOut = TO_FOLD.clone().negate();
export const FOLD_N = foldOut.clone().sub(foldIn).normalize();               // faces forward and down
export const FOLD_INC = Math.acos(-foldIn.dot(FOLD_N));

// Astigmatism of the concave mirror at this incidence (paraxial Coddington equations).
export function mirrorImages(mode = MIRROR.mode, u = U) {
  const { Rt, Rs } = mirrorRadii(mode);
  const ft = (Rt / 2) * Math.cos(MIRROR_INC), fs = (Rs / 2) / Math.cos(MIRROR_INC);
  const v = (f) => 1 / (1 / f - 1 / u);                                       // > 0 real, < 0 virtual (behind the mirror)
  return { ft, fs, vt: v(ft), vs: v(fs), eyeToMirror: EYE_TO_GLASS + GLASS_TO_MIRROR };
}

// ---- virtual image plane ------------------------------------------------------
export const VIMG_C = EYE.clone().addScaledVector(LOOK, VID);
export const VIMG_N = LOOK.clone().negate();                                  // faces the driver
export const VIMG_RIGHT = V(0, 0, 1);
export const VIMG_UP = new THREE.Vector3().crossVectors(VIMG_RIGHT, LOOK).normalize(); // perpendicular to LOOK, upward
if (VIMG_UP.y < 0) VIMG_UP.negate();
// Road coverage of the window from the nominal eye on flat ground.
export const WINDOW_TOP_DEP = LOOKDOWN - FOV_H / 2, WINDOW_BOT_DEP = LOOKDOWN + FOV_H / 2;
export const ROAD_NEAR = EYE_H / Math.tan(WINDOW_BOT_DEP), ROAD_FAR = WINDOW_TOP_DEP > 0 ? EYE_H / Math.tan(WINDOW_TOP_DEP) : Infinity;

// ---- ray tracing through the installed optics ----------------------------------
// Plane hit: returns t or null.
function hitPlane(o, d, p, n) { const den = d.dot(n); if (Math.abs(den) < 1e-9) return null; const t = p.clone().sub(o).dot(n) / den; return t > 1e-6 ? t : null; }

// Concave mirror as a biconic paraboloid in its local frame: w = u^2/(2Rs) + v^2/(2Rt), w along MIRROR_N.
export function hitMirror(o, d, mode = MIRROR.mode) {
  const { Rt, Rs } = mirrorRadii(mode);
  const rel = o.clone().sub(MIRROR_C);
  const ou = rel.dot(MIRROR_U), ov = rel.dot(MIRROR_V), ow = rel.dot(MIRROR_N);
  const du = d.dot(MIRROR_U), dv = d.dot(MIRROR_V), dw = d.dot(MIRROR_N);
  const a = du * du / (2 * Rs) + dv * dv / (2 * Rt);
  const b = ou * du / Rs + ov * dv / Rt - dw;
  const c = ou * ou / (2 * Rs) + ov * ov / (2 * Rt) - ow;
  let t;
  if (Math.abs(a) < 1e-12) t = -c / b;
  else {
    const disc = b * b - 4 * a * c; if (disc < 0) return null;
    const s = Math.sqrt(disc); const t1 = (-b - s) / (2 * a), t2 = (-b + s) / (2 * a);
    t = Math.min(...[t1, t2].filter((x) => x > 1e-6));
  }
  if (!isFinite(t) || t <= 0) return null;
  {
    // Newton on the true surface (sphere, toroid or the freeform polynomial) from the paraboloid's hit
    for (let it = 0; it < 8; it++) {
      const u = ou + t * du, v = ov + t * dv, w = ow + t * dw;
      const F = w - mirrorSag(u, v, mode);
      const [gu, gv] = mirrorGrad(u, v, mode);
      const dF = dw - (gu * du + gv * dv);
      if (Math.abs(dF) < 1e-12) break;
      t -= F / dF;
      if (Math.abs(F) < 1e-10) break;
    }
  }
  const p = o.clone().addScaledVector(d, t);
  const pr = p.clone().sub(MIRROR_C);
  const u = pr.dot(MIRROR_U), v = pr.dot(MIRROR_V);
  const [gu, gv] = mirrorGrad(u, v, mode);
  const n = MIRROR_N.clone().addScaledVector(MIRROR_U, -gu).addScaledVector(MIRROR_V, -gv).normalize();
  return { p, n, u, v, inside: Math.abs(u) <= MIRROR_W / 2 && Math.abs(v) <= MIRROR_H / 2 };
}

// The windshield's inner surface along a ray: the plane through G, or the curved surface GLASS describes. Returns the
// hit point and the local normal (outward), or null.
export function hitGlass(o, d) {
  let t = hitPlane(o, d, G, GLASS_N); if (t === null) return null;
  if (!(GLASS.Rh > 0 || GLASS.Rv > 0)) return { p: o.clone().addScaledVector(d, t), n: GLASS_N.clone() };
  const Z = V(0, 0, 1);
  const sagAt = (a, b) => (GLASS.Rh > 0 ? b * b / (2 * GLASS.Rh) : 0) + (GLASS.Rv > 0 ? a * a / (2 * GLASS.Rv) : 0);
  for (let it = 0; it < 8; it++) {
    const p = o.clone().addScaledVector(d, t), rel = p.clone().sub(G);
    const a = rel.dot(GLASS_UP), b = rel.dot(Z), w = rel.dot(GLASS_N);
    const F = w + sagAt(a, b);
    const ga = GLASS.Rv > 0 ? a / GLASS.Rv : 0, gb = GLASS.Rh > 0 ? b / GLASS.Rh : 0;
    const dF = d.dot(GLASS_N) + ga * d.dot(GLASS_UP) + gb * d.dot(Z);
    if (Math.abs(dF) < 1e-12) break;
    t -= F / dF;
    if (Math.abs(F) < 1e-10) break;
  }
  if (!(t > 1e-6)) return null;
  const p = o.clone().addScaledVector(d, t), rel = p.clone().sub(G);
  const a = rel.dot(GLASS_UP), b = rel.dot(Z);
  const n = GLASS_N.clone().addScaledVector(GLASS_UP, GLASS.Rv > 0 ? a / GLASS.Rv : 0).addScaledVector(Z, GLASS.Rh > 0 ? b / GLASS.Rh : 0).normalize();
  return { p, n };
}

// Trace backward from an eye point along a viewing direction: eye -> glass -> mirror -> fold -> panel.
// Returns the polyline and the panel-plane coordinates (lateral z, fore-aft x relative to PANEL_C) of the landing point.
export function traceFromEye(eye, dir, mode = MIRROR.mode) {
  const pts = [eye.clone()];
  let o = eye.clone(), d = dir.clone().normalize();
  const gh = hitGlass(o, d); if (!gh) return null;
  o = gh.p; pts.push(o.clone()); d = reflect(d, gh.n);
  let t;
  const m = hitMirror(o, d, mode); if (!m) return null;
  o = m.p; pts.push(o.clone()); d = reflect(d, m.n);
  t = hitPlane(o, d, FOLD_C, FOLD_N); if (t === null) return null;
  o = o.clone().addScaledVector(d, t); pts.push(o.clone()); const foldHit = o.clone(); d = reflect(d, FOLD_N);
  const pp = panelPose(mode);
  t = hitPlane(o, d, pp.C, pp.N); if (t === null) return null;
  o = o.clone().addScaledVector(d, t); pts.push(o.clone());
  const rel = o.clone().sub(pp.C);
  return { pts, mirror: m, fold: foldHit, panel: o.clone(), panelZ: rel.dot(pp.U), panelX: rel.dot(pp.VP) };
}

// Viewing direction for a field angle (ax right, ay up, radians) about the window centre.
export function fieldDir(ax, ay) {
  return LOOK.clone().addScaledVector(VIMG_RIGHT, Math.tan(ax)).addScaledVector(VIMG_UP, Math.tan(ay)).normalize();
}

// Footprints of the beam on each surface, from the eye-box corners and the field corners.
export function footprints(mode = MIRROR.mode) {
  const out = { mirror: [], fold: [], panel: [], glass: [] };
  for (const ex of [-1, 0, 1]) for (const ey of [-1, 0, 1]) {
    const e = EYE.clone().add(V(0, ey * EYEBOX_H / 2, ex * EYEBOX_W / 2));
    for (const fx of [-1, 0, 1]) for (const fy of [-1, 0, 1]) {
      const r = traceFromEye(e, fieldDir(fx * FOV_W / 2, fy * FOV_H / 2), mode);
      if (!r) continue;
      out.glass.push(r.pts[1]); out.mirror.push(r.pts[2]); out.fold.push(r.fold); out.panel.push(r.panel);
    }
  }
  const bb = (arr, f) => { const b = new THREE.Box3(); arr.forEach((p) => b.expandByPoint(f ? f(p) : p)); return b; };
  return {
    ...out,
    mirrorUV: bb(out.mirror, (p) => { const r = p.clone().sub(MIRROR_C); return V(r.dot(MIRROR_U), r.dot(MIRROR_V), 0); }),
    panelBox: bb(out.panel), foldBox: bb(out.fold), glassBox: bb(out.glass),
  };
}

// Where the crop corners land: trace the four window corners from the nominal eye.
export function panelCorners(mode = MIRROR.mode) {
  const c = {};
  for (const [k, fx, fy] of [['tl', -1, 1], ['tr', 1, 1], ['bl', -1, -1], ['br', 1, -1], ['c', 0, 0]]) {
    const r = traceFromEye(EYE, fieldDir(fx * FOV_W / 2, fy * FOV_H / 2), mode);
    c[k] = r ? r.panel : null;
  }
  return c;
}

// ---- clearances, reported in the optics panel ------------------------------
{
  const top = MIRROR_C.clone().addScaledVector(MIRROR_V, MIRROR_H / 2);
  const clear = glassYAt(top.x) - top.y;
  SIM_NOTES.push({ key: 'mirrorClear', text: `Mirror top edge clears the glass by ${(clear * 1000).toFixed(0)} mm with the eye-to-mirror path at ${((EYE_TO_GLASS + GLASS_TO_MIRROR) * 1000).toFixed(0)} mm. At the plan's assumed 1,000 mm it would touch the glass.` });
}

// ---- vehicle and component mount points --------------------------------------
// Housing: the 3-D printed shell around panel, fold and mirror, on the dash top in front of the driver.
export const HOUSING = (() => {
  const xMin = PANEL_C.x - 0.075, xMax = MIRROR_C.x + 0.06;
  const floor = 0.80;                        // underside of the housing (dash top is shaped below it)
  return { xMin, xMax, floor, zMin: -0.185, zMax: 0.185, topRear: FOLD_C.y + 0.06, topFront: glassYAt(xMax) - 0.012 };
})();

// Road camera on the windshield centreline near the mirror stalk, clamped to the stalk (nothing bonded to the glass).
export const ROAD_CAM = V(glassXAt(1.30) - 0.045, 1.30, CAR_CENTER_Z - 0.06);  // left lens centre, plan's frame origin
export const ROAD_CAM_BASELINE = ROAD_CAM.distanceTo(EYE);
export const MIRROR_STALK = V(glassXAt(1.355) - 0.01, 1.355, CAR_CENTER_Z);
export const DRIVER_CAM = V(0.53, 0.86, 0.0);                                    // OAK-D Pro on the column shroud
export const GNSS_ANT = V(glassXAt(0.815) - 0.06, 0.815, CAR_CENTER_Z + 0.42);  // dash top, passenger side, near the glass
export const JETSON = V(0.62, 0.20, CAR_CENTER_Z + 0.52);                       // passenger footwell bracket
export const DCDC = V(0.48, 0.16, CAR_CENTER_Z + 0.30);
export const SWITCH = V(0.30, 0.15, CAR_CENTER_Z + 0.55);
export const MINIPC2 = V(-0.55, 0.32, CAR_CENTER_Z + 0.40);
export const MONITOR2 = V(-0.42, 0.95, CAR_CENTER_Z + 0.37);                    // back of the passenger headrest
export const ACC_SOCKET = V(0.42, 0.50, CAR_CENTER_Z - 0.02);

// Plan frame: x forward, y right, z down, origin at the ZED left lens.
export function toPlanFrame(p) { return V(p.x - ROAD_CAM.x, p.z - ROAD_CAM.z, -(p.y - ROAD_CAM.y)); }

export const LAYOUT_SUMMARY = () => {
  const im = mirrorImages();
  const imS = mirrorImages('sphere');
  return {
    G, MIRROR_C, FOLD_C, PANEL_C,
    mirrorIncDeg: MIRROR_INC / DEG, foldIncDeg: FOLD_INC / DEG,
    eyeToMirror: im.eyeToMirror,
    toroid: im, sphere: imS,
    roadNear: ROAD_NEAR, roadFar: ROAD_FAR,
    baseline: ROAD_CAM_BASELINE,
  };
};

// Sagittal image distance from eye e along viewing direction d: the trace to the mirror, then the local Coddington
// equation at the hit (as cycles.js fieldDistances does, and as Cycles confirmed across the window). Null when the
// ray misses the optics. The Driver view draws the traced window on this surface and scores registration against it.
export function imageDistanceAlong(e, d, mode = MIRROR.mode) {
  const tr = traceFromEye(e, d, mode);
  if (!tr || !tr.pts || tr.pts.length < 5 || !tr.mirror) return null;
  const [eye, glass, hit, fold, panel] = tr.pts;
  const din = hit.clone().sub(glass).normalize();
  const cosI = Math.max(1e-6, -din.dot(tr.mirror.n));
  const uLocal = hit.distanceTo(fold) + fold.distanceTo(panel);
  const eyeToMirror = eye.distanceTo(glass) + glass.distanceTo(hit);
  const [cu] = mirrorCurv(tr.mirror.u, tr.mirror.v, mode);
  const fs = (1 / cu / 2) / cosI;
  const v = 1 / (1 / fs - 1 / uLocal);
  return eyeToMirror - v;
}

// Field angles (ax right, ay up, radians, tan-linear about LOOK) whose ray from eye point e lands on the panel at
// (pz, px) metres from the crop centre: Newton on the trace. Null where no ray reaches that panel point.
export function panelPointField(e, pz, px, mode = MIRROR.mode) {
  let ax = pz / 0.06 * FOV_W * 0.8, ay = -px / 0.03 * FOV_H * 0.8;
  const f = (a, b) => { const r = traceFromEye(e, fieldDir(a, b), mode); return r ? [r.panelZ, r.panelX, r] : [NaN, NaN, null]; };
  let r = null;
  for (let it = 0; it < 25; it++) {
    const [z0, x0, r0] = f(ax, ay);
    r = r0;
    if (!r0) return null;
    const hh = 1e-4;
    const [z1, x1] = f(ax + hh, ay), [z2, x2] = f(ax, ay + hh);
    const J = [[(z1 - z0) / hh, (z2 - z0) / hh], [(x1 - x0) / hh, (x2 - x0) / hh]];
    const det = J[0][0] * J[1][1] - J[0][1] * J[1][0];
    if (!isFinite(det) || Math.abs(det) < 1e-12) return null;
    const ez = pz - z0, ex = px - x0;
    const dax = (J[1][1] * ez - J[0][1] * ex) / det, day = (-J[1][0] * ez + J[0][0] * ex) / det;
    ax += dax; ay += day;
    if (Math.abs(dax) < 1e-9 && Math.abs(day) < 1e-9) break;
  }
  const [, , rf] = f(ax, ay);
  return rf ? { ax, ay, trace: rf } : null;
}
