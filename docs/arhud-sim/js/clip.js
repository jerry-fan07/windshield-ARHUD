// Does a traced ray get through the housing? The lid aperture, the mirror aperture and the fold glass as the housing
// sizes them (components/optics.js): shared by the Driver view's vignette and the Cycles comparison.
import * as GM from './geom.js';
import { foldFrame, housingLayout } from './components/optics.js';

let cache = null;
export function clipFrames(mode = GM.MIRROR.mode) {
  if (!cache || cache.key !== mode) {
    let hl = null, ff = null;
    try { hl = housingLayout(mode); } catch (e) { hl = null; }
    try { ff = foldFrame(mode); } catch (e) { ff = null; }
    cache = { key: mode, hl, ff };
  }
  return cache;
}

// Is the traced ray inside the lid aperture, the mirror aperture and the fold glass?
export function reaches(trace, ff, hl) {
  // the crop: the ray must land on the lit 60 x 30 mm of the panel, which from a displaced eye it may not
  const out = { lid: true, mirror: trace.mirror.inside, fold: !ff, crop: Math.abs(trace.panelZ) <= 0.03 && Math.abs(trace.panelX) <= 0.015 };
  if (hl) {
    // the eye-to-glass leg must clear the housing itself: its lid rises toward the rear to lidY(xR), and from a low
    // eye the ray to the window's bottom passes below that edge (Cycles: 50% of the window gone at 70 mm down)
    const E = trace.pts[0], Gp = trace.pts[1];
    for (const x of [hl.xR, hl.ax0, hl.ax1, hl.xF]) {
      if (x <= E.x || x >= Gp.x) continue;
      const y = E.y + (Gp.y - E.y) * (x - E.x) / (Gp.x - E.x), z = E.z + (Gp.z - E.z) * (x - E.x) / (Gp.x - E.x);
      if (y < hl.lidY(x) && Math.abs(z) <= hl.zW) { out.lid = false; break; }
    }
    // the glass-to-mirror leg crosses the lid plane y = lidY(x); the crossing must fall in the aperture
    const A = trace.pts[1], Bp = trace.pts[2];
    const fA = A.y - hl.lidY(A.x), fB = Bp.y - hl.lidY(Bp.x);
    if (fA * fB < 0) {
      const P = A.clone().lerp(Bp, fA / (fA - fB));
      out.lid = out.lid && P.x >= hl.ax0 && P.x <= hl.ax1 && P.z >= hl.az0 && P.z <= hl.az1;
    }
    // the mirror-to-fold leg runs under the lid (the fold sits behind the aperture's rear edge): a steep ray from the
    // mirror's top toward the fold hits the lid's underside, which is what clips the window from a low eye
    if (out.lid && trace.pts.length > 3) {
      const M = trace.pts[2], F = trace.pts[3];
      const gM = M.y - hl.lidY(M.x), gF = F.y - hl.lidY(F.x);
      if (gM > 0 || gF > 0 || gM * gF < 0) out.lid = false;
    }
  }
  if (!out.mirror || !ff) return out;
  const rel = trace.fold.clone().sub(GM.FOLD_C);
  const u = rel.dot(ff.fu), v = rel.dot(ff.fv);
  out.fold = u >= ff.u0 && u <= ff.u1 && v >= ff.v0 && v <= ff.v1;
  return out;
}

export function rayReaches(trace, mode = GM.MIRROR.mode) {
  const { hl, ff } = clipFrames(mode);
  const r = reaches(trace, ff, hl);
  return r.lid && r.mirror && r.fold && r.crop;
}
