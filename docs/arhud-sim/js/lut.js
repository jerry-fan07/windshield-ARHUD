// The eye-position-to-panel lookup table: what hudd on the Jetson uses instead of a ray trace per symbol. For a grid
// of eye positions over the eye box and a grid of field directions over the window, the panel point the trace lands
// on; a symbol is placed by interpolating in both. The inverse of the nominal eye's mapping (panel point -> canvas
// pixel) is a second table, since the canvas is the nominal eye's view and the pre-distortion to the panel is that
// mapping. Built from geom.js, exported by dev/export-lut.mjs as assets/hudd_lut.json.
import * as GM from './geom.js';
import * as THREE from 'three';

export const LUT_DEFAULT = { eyeNz: 11, eyeNy: 7, eyeHalfZ: 0.08, eyeHalfY: 0.045, fieldNx: 57, fieldNy: 29, fieldMargin: 1.15 };   // 0.35' rms, 0.75' max against the exact trace (toroid), 1.0' max (freeform); 137 to 243 ms to build

function windowAngles() {
  // the spec window's half-angles (tan-linear about LOOK) with a margin: every figure's traced window fits inside
  return { ax: Math.atan(Math.tan(GM.FOV_W / 2) * LUT_DEFAULT.fieldMargin), ay: Math.atan(Math.tan(GM.FOV_H / 2) * LUT_DEFAULT.fieldMargin) };
}

export function buildLut(mode = GM.MIRROR.mode, opt = {}) {
  const o = { ...LUT_DEFAULT, ...opt };
  const half = o.halfAngles || windowAngles();
  const n = o.eyeNz * o.eyeNy * o.fieldNx * o.fieldNy;
  const panel = new Float32Array(n * 2).fill(NaN);
  let k = 0, misses = 0;
  for (let j = 0; j < o.eyeNy; j++) for (let i = 0; i < o.eyeNz; i++) {
    const dy = (o.eyeNy > 1 ? j / (o.eyeNy - 1) * 2 - 1 : 0) * o.eyeHalfY, dz = (o.eyeNz > 1 ? i / (o.eyeNz - 1) * 2 - 1 : 0) * o.eyeHalfZ;
    const e = GM.EYE.clone().add(new THREE.Vector3(0, dy, dz));
    for (let q = 0; q < o.fieldNy; q++) for (let p = 0; p < o.fieldNx; p++) {
      const tx = (p / (o.fieldNx - 1) * 2 - 1) * Math.tan(half.ax), ty = (q / (o.fieldNy - 1) * 2 - 1) * Math.tan(half.ay);
      const tr = GM.traceFromEye(e, GM.fieldDir(Math.atan(tx), Math.atan(ty)), mode);
      if (tr) { panel[k * 2] = tr.panelZ; panel[k * 2 + 1] = tr.panelX; } else misses++;
      k++;
    }
  }
  // the inverse of the nominal mapping: panel grid -> field direction (tan-linear) from the nominal eye
  // beyond the crop by 40%: a symbol an off-centre eye sees at the window's edge lands outside the crop's own grid
  const pz0 = -0.042, pz1 = 0.042, px0 = -0.021, px1 = 0.021, inv = { nz: 43, nx: 22, pz0, pz1, px0, px1, field: new Float32Array(43 * 22 * 2).fill(NaN) };
  for (let q = 0; q < inv.nx; q++) for (let p = 0; p < inv.nz; p++) {
    const sol = GM.panelPointField(GM.EYE, pz0 + (pz1 - pz0) * p / (inv.nz - 1), px0 + (px1 - px0) * q / (inv.nx - 1), mode);
    if (sol) { inv.field[(q * inv.nz + p) * 2] = Math.tan(sol.ax); inv.field[(q * inv.nz + p) * 2 + 1] = Math.tan(sol.ay); }
  }
  return { mode, ...o, halfTanAx: Math.tan(half.ax), halfTanAy: Math.tan(half.ay), panel, misses, inverse: inv, glass: { Rh: GM.GLASS.Rh, Rv: GM.GLASS.Rv } };
}

// Bilinear sample of a 2-D table of pairs; NaN if any corner is missing.
function sample2(arr, nx, ny, fx, fy) {
  const x = Math.min(Math.max(fx, 0), nx - 1 - 1e-9), y = Math.min(Math.max(fy, 0), ny - 1 - 1e-9);
  const i = Math.floor(x), j = Math.floor(y), tx = x - i, ty = y - j;
  const g = (ii, jj, c) => arr[((jj * nx) + ii) * 2 + c];
  const out = [0, 0];
  for (let c = 0; c < 2; c++) {
    const v = (1 - ty) * ((1 - tx) * g(i, j, c) + tx * g(i + 1, j, c)) + ty * ((1 - tx) * g(i, j + 1, c) + tx * g(i + 1, j + 1, c));
    if (!isFinite(v)) return null;
    out[c] = v;
  }
  return out;
}

// Panel point (pz, px) for eye offset (dy, dz) and field direction tangents (tx, ty), by interpolation.
export function lutPanelPoint(L, dy, dz, tx, ty) {
  const fz = (dz / L.eyeHalfZ + 1) / 2 * (L.eyeNz - 1), fy = (dy / L.eyeHalfY + 1) / 2 * (L.eyeNy - 1);
  const fp = (tx / L.halfTanAx + 1) / 2 * (L.fieldNx - 1), fq = (ty / L.halfTanAy + 1) / 2 * (L.fieldNy - 1);
  if (fp < 0 || fp > L.fieldNx - 1 || fq < 0 || fq > L.fieldNy - 1) return null;     // outside the table: no panel point, nothing to draw
  const stride = L.fieldNx * L.fieldNy;
  const ez = Math.min(Math.max(fz, 0), L.eyeNz - 1 - 1e-9), ey = Math.min(Math.max(fy, 0), L.eyeNy - 1 - 1e-9);
  const i = Math.floor(ez), j = Math.floor(ey), tz = ez - i, tyy = ey - j;
  const cell = (ii, jj) => sample2(L.panel.subarray(((jj * L.eyeNz) + ii) * stride * 2, ((jj * L.eyeNz) + ii + 1) * stride * 2), L.fieldNx, L.fieldNy, fp, fq);
  const a = cell(i, j), b = cell(Math.min(i + 1, L.eyeNz - 1), j), c = cell(i, Math.min(j + 1, L.eyeNy - 1)), d = cell(Math.min(i + 1, L.eyeNz - 1), Math.min(j + 1, L.eyeNy - 1));
  if (!a || !b || !c || !d) return null;
  return [0, 1].map((k) => (1 - tyy) * ((1 - tz) * a[k] + tz * b[k]) + tyy * ((1 - tz) * c[k] + tz * d[k]));
}

// Field direction tangents from the nominal eye for a panel point, by the inverse table.
export function lutNominalField(L, pz, px) {
  const inv = L.inverse;
  return sample2(inv.field, inv.nz, inv.nx, (pz - inv.pz0) / (inv.pz1 - inv.pz0) * (inv.nz - 1), (px - inv.px0) / (inv.px1 - inv.px0) * (inv.nx - 1));
}

// Serialise for hudd: plain arrays, millimetres on the panel, tangents for the field.
export function lutToJson(L) {
  const round = (v, d) => (isFinite(v) ? +v.toFixed(d) : null);
  return {
    what: 'hudd calibration: panel point (mm from the crop centre, lateral then fore-aft) for an eye offset (up, right; m) and a field direction (tangents right, up about the look direction); interpolate bilinearly in the eye and in the field. inverse: field tangents from the nominal eye for a panel grid.',
    mode: L.mode, glass: L.glass, generated: new Date().toISOString().slice(0, 16).replace('T', ' '),
    eye: { nz: L.eyeNz, ny: L.eyeNy, halfZ: L.eyeHalfZ, halfY: L.eyeHalfY }, field: { nx: L.fieldNx, ny: L.fieldNy, halfTanX: round(L.halfTanAx, 6), halfTanY: round(L.halfTanAy, 6) },
    panelMm: Array.from(L.panel, (v) => round(v * 1000, 3)),
    inverse: { nz: L.inverse.nz, nx: L.inverse.nx, pzMm: [L.inverse.pz0 * 1000, L.inverse.pz1 * 1000], pxMm: [L.inverse.px0 * 1000, L.inverse.px1 * 1000], fieldTan: Array.from(L.inverse.field, (v) => round(v, 6)) },
  };
}
