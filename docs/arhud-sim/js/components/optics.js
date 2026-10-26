// Relay optics and housing: the cold-mirror fold with its IR absorber, the concave mirror, the shutter, the dust cover,
// the printed housing, the installed HUD unit, and the Stage 0 and Stage 1 rigs.
//
// Local frames are the car frame (X forward, Y up, Z right, metres) translated to a component origin; nothing is
// rotated except the shutter and dust cover, which are built flat and tilted onto the lid plane by buildHudUnit().
// Every installed position comes from geom.js, so the parts follow any change to the layout there.
import * as THREE from 'three';
import { P, R, V } from '../params.js';
import { M } from '../mats.js';
import * as G from '../geom.js';
import { rbox, box, cyl, sphere, at, extrude, tube, polyline, canvasTexture, textDecal, rng, DEG, clamp, lerp, smoothstep, easeInOut } from '../util.js';
import { makeComponent, addPart } from './contract.js';
import { labelSprite, glowSprite, polArrow, screw, costOf, buildPgu, buildPanelKit, PANEL, hudPlaceholderTexture, BACKLIGHT_DEPTH, ribbon } from './pgu.js';
import { CAD, buildCadHousing, cadUnitGroups } from './cad.js';

const v3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const slab = (x, y, z, mat) => box(x, y, z, mat);
const AMBER = 0xffb347, IR = 0xd2283c, SUNC = 0xfff2d0, BLOCKED = 0xff4040;

// Box with explicit axes (x, y unit vectors; z = x × y), centred at c.
function orientedBox(sx, sy, sz, xAxis, yAxis, c, mat) {
  const zAxis = new THREE.Vector3().crossVectors(xAxis, yAxis).normalize();
  const m = slab(sx, sy, sz, mat);
  m.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(xAxis.clone().normalize(), yAxis.clone().normalize(), zAxis));
  m.position.copy(c);
  return m;
}

// Line through points with an optional dashed style; returns the THREE.Line.
function ray(points, color, opts = {}) {
  const l = polyline(points, color, { opacity: opts.opacity ?? 0.95, dashed: opts.dashed, dash: opts.dash ?? 0.006, gap: opts.gap ?? 0.004, additive: opts.additive ?? true, renderOrder: 15 });
  l.material.toneMapped = false;
  return l;
}
function setRay(line, points) {
  const pos = line.geometry.getAttribute('position');
  if (pos && pos.count === points.length) { line.geometry.setFromPoints(points); line.geometry.computeBoundingSphere(); }
  else { line.geometry.dispose(); line.geometry = new THREE.BufferGeometry().setFromPoints(points); }
  if (line.material.isLineDashedMaterial) line.computeLineDistances();
}

// Segment A->B against a rectangle (centre c, unit axes a and b, half sizes ha and hb).
function segHitsRect(A, B, c, a, b, ha, hb) {
  const n = new THREE.Vector3().crossVectors(a, b).normalize();
  const dA = A.clone().sub(c).dot(n), dB = B.clone().sub(c).dot(n);
  if (dA * dB > 0 || dA === dB) return false;
  const P0 = A.clone().lerp(B, dA / (dA - dB)).sub(c);
  return Math.abs(P0.dot(a)) <= ha && Math.abs(P0.dot(b)) <= hb;
}

// ---------------------------------------------------------------------------------------------------------------
// Layout helpers shared by the fold, housing and installed unit
// ---------------------------------------------------------------------------------------------------------------
// Fold rectangle sized from the traced beam footprint (eye-box corners x field corners), with a small margin; the top
// edge is trimmed close because the exit beam passes just above it.
export function foldFrame(mode = G.MIRROR.mode) {
  const fu = v3(0, 0, 1);
  const fv = new THREE.Vector3().crossVectors(G.FOLD_N, fu).normalize(); if (fv.y < 0) fv.negate();
  const fp = G.footprints(mode);
  let u0 = 1e9, u1 = -1e9, v0 = 1e9, v1 = -1e9;
  for (const p of fp.fold) { const r = p.clone().sub(G.FOLD_C); const u = r.dot(fu), v = r.dot(fv); u0 = Math.min(u0, u); u1 = Math.max(u1, u); v0 = Math.min(v0, v); v1 = Math.max(v1, v); }
  return { fu, fv, n: G.FOLD_N.clone(), u0: u0 - 0.008, u1: u1 + 0.008, v0: v0 - 0.006, v1: v1 + 0.002, thick: 0.003, footprint: { u0, u1, v0, v1 } };
}

// Dense ray sample through the installed optics: eye-box grid x field grid.
export function sampleRays(mode = G.MIRROR.mode, n = 5) {
  const out = [];
  const lin = (k) => (n === 1 ? [0] : Array.from({ length: n }, (_, i) => -1 + 2 * i / (n - 1)));
  for (const ex of lin(n)) for (const ey of [-1, 0, 1]) for (const fx of lin(n)) for (const fy of [-1, -0.5, 0, 0.5, 1]) {
    const e = G.EYE.clone().add(v3(0, ey * G.EYEBOX_H / 2, ex * G.EYEBOX_W / 2));
    const r = G.traceFromEye(e, G.fieldDir(fx * G.FOV_W / 2, fy * G.FOV_H / 2), mode);
    if (r) out.push({ ...r, ex, ey, fx, fy });
  }
  return out;
}

// Mirror geometry helpers in the mirror's frame.
function mirrorPoint(u, v, mode) {
  return G.MIRROR_U.clone().multiplyScalar(u).addScaledVector(G.MIRROR_V, v).addScaledVector(G.MIRROR_N, G.mirrorSag(u, v, mode));
}
function mirrorNormal(u, v, mode) {
  const [gu, gv] = G.mirrorGrad(u, v, mode);
  return G.MIRROR_N.clone().addScaledVector(G.MIRROR_U, -gu).addScaledVector(G.MIRROR_V, -gv).normalize();
}
const MIRROR_BACK = 0.012;                       // substrate thickness behind the vertex

// The housing layout in car coordinates: lid plane, aperture, shutter garage and walls, all derived from the traces.
export function housingLayout(mode = G.MIRROR.mode) {
  const H = G.HOUSING, floor = H.floor;
  const ff = foldFrame(mode);
  // front: behind the mirror's top back corner
  const top = mirrorPoint(0, G.MIRROR_H / 2, mode).add(G.MIRROR_C);
  const topBack = G.MIRROR_C.clone().addScaledVector(G.MIRROR_V, G.MIRROR_H / 2).addScaledVector(G.MIRROR_N, -MIRROR_BACK);
  const xF = Math.max(H.xMax, topBack.x + 0.016);
  const yF = G.glassYAt(xF) - 0.005;
  // fold and absorber top corners must sit under the lid
  const foldTop = G.FOLD_C.clone().addScaledVector(ff.fv, ff.v1).addScaledVector(ff.n, -0.022);
  const pts = [foldTop, G.FOLD_C.clone().addScaledVector(ff.fv, ff.v1), top];
  let s = 0.1;
  for (const p of pts) s = Math.max(s, (p.y + 0.009 - yF) / (xF - p.x));
  const lidY = (x) => yF + s * (xF - x);
  // aperture: where the exit beam (glass <-> mirror) crosses the lid plane
  const rays = sampleRays(mode, 5);
  let ax0 = 1e9, ax1 = -1e9, az0 = 1e9, az1 = -1e9;
  for (const r of rays) {
    const A = r.pts[1], B = r.pts[2];
    const fA = A.y - lidY(A.x), fB = B.y - lidY(B.x);
    if (fA * fB >= 0) continue;
    const Pc = A.clone().lerp(B, fA / (fA - fB));
    ax0 = Math.min(ax0, Pc.x); ax1 = Math.max(ax1, Pc.x); az0 = Math.min(az0, Pc.z); az1 = Math.max(az1, Pc.z);
  }
  ax0 -= 0.006; ax1 = Math.min(ax1 + 0.006, xF - 0.006); az0 -= 0.005; az1 += 0.005;
  const lidDir = v3(1, -s, 0).normalize(), lidN = v3(s, 1, 0).normalize();
  const along = (x) => (x - ax0) / lidDir.x;                       // distance along the lid from the aperture's rear edge
  const L = along(ax1);                                            // aperture length along the lid
  const W = az1 - az0;
  const garageLen = L / 2 + 0.014;
  const xGarage = ax0 - garageLen * lidDir.x;
  const xR = Math.min(G.PANEL_C.x - PANEL.outX / 2 - 0.012, G.PANEL_C.x - 0.088, xGarage - 0.008, G.FOLD_C.x + ff.fv.x * ff.v0 - 0.03);
  const apC = v3((ax0 + ax1) / 2, lidY((ax0 + ax1) / 2), (az0 + az1) / 2);
  return { floor, xF, xR, yF, s, lidY, lidDir, lidN, ax0, ax1, az0, az1, L, W, garageLen, xGarage, apC, zW: H.zMax, ff, rays };
}

// ---------------------------------------------------------------------------------------------------------------
// coldMirror
// ---------------------------------------------------------------------------------------------------------------
export function buildColdMirror(opts = {}) {
  const mode = opts.mode || G.MIRROR.mode;
  const ff = foldFrame(mode);
  const c = makeComponent(THREE, {
    id: 'coldMirror',
    name: 'Cold-mirror fold with IR absorber',
    category: 'optics',
    mount: 'centre of the reflecting surface at geom.FOLD_C; car-frame orientation (normal geom.FOLD_N)',
    size: [0.1, 0.09, ff.u1 - ff.u0 + 0.04],
    desc: 'The flat fold between the panel and the concave mirror is a dielectric cold mirror: it reflects visible light and transmits infrared. Sunlight that the concave mirror focuses back into the housing loses its infrared half here, into a black absorber, before it can reach the cell.',
    working: 'Visible light reflects between the panel and the concave mirror; the infrared part of focused sunlight passes through the coating into the absorber, which warms.',
  });
  const fu = ff.fu, fv = ff.fv, n = ff.n;
  const lenU = ff.u1 - ff.u0, lenV = ff.v1 - ff.v0;
  const uc = (ff.u0 + ff.u1) / 2, vc = (ff.v0 + ff.v1) / 2;
  const at2 = (u, v, w = 0) => fu.clone().multiplyScalar(u).addScaledVector(fv, v).addScaledVector(n, w);
  c.facts = [
    ['Size (from the traced footprint)', `${(lenU * 1000).toFixed(0)} × ${(lenV * 1000).toFixed(0)} mm, 3 mm glass`],
    ['Incidence', `${(G.FOLD_INC / DEG).toFixed(1)}° at the centre`],
    ['Visible passed on (sun)', `${V.vis_frac} of the focused solar power (ASSUMED): ${V.sun_w} → ${V.sun_after_cold}`],
    ['With the IR-cut glass', `${V.filt_frac} passes (TI DLPA096): ${V.sun_after_filt}`],
    ['Polarisation', 'plane of incidence aligned with the windshield\'s; s-reflectance checked against the vendor curve'],
    ['Price', costOf('Cold mirror')],
  ];
  // glass with a dichroic front
  const edgeMat = new THREE.MeshPhysicalMaterial({ color: 0x9fd6c8, roughness: 0.1, transparent: true, opacity: 0.6 });
  const backMat = new THREE.MeshStandardMaterial({ color: 0x2a3436, roughness: 0.2, metalness: 0.2 });
  const glass = new THREE.Group();
  {
    const zA = new THREE.Vector3().crossVectors(fv, n);
    const geo = new THREE.BoxGeometry(lenV, ff.thick, lenU);
    const m = new THREE.Mesh(geo, [edgeMat, edgeMat, M.coldMirror, backMat, edgeMat, edgeMat]);
    m.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(fv, n, zA));
    m.position.copy(at2(uc, vc, -ff.thick / 2));
    m.castShadow = true; glass.add(m);
    const tag = textDecal('COLD MIRROR · R vis > 95% · T IR > 85%', 0.06, { color: '#d8e6ff' });
    tag.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(zA.clone().negate(), fv, n.clone().negate()));
    tag.position.copy(at2(uc, ff.v0 + 0.008, -ff.thick - 0.0003)); tag.scale.setScalar(0.5); glass.add(tag);
  }
  // printed bracket: U-frame round the bottom and sides, arms out to the housing walls
  const bracket = new THREE.Group();
  {
    const wall = G.HOUSING.zMax - 0.004;
    const fr = 0.006, d = 0.012;
    bracket.add(orientedBox(0.006, d, lenU + 2 * fr, fv, n, at2(uc, ff.v0 - 0.003, -0.004), M.printBlack));
    for (const sg of [-1, 1]) {
      const uEdge = sg > 0 ? ff.u1 + fr / 2 : ff.u0 - fr / 2;
      bracket.add(orientedBox(lenV + 0.006, d, fr, fv, n, at2(uEdge, vc - 0.0015, -0.004), M.printBlack));
      // arm to the wall
      const armLen = wall - Math.abs(uEdge) - fr / 2;
      const armC = at2(sg * (Math.abs(uEdge) + fr / 2 + armLen / 2), vc - 0.004, -0.008);
      bracket.add(orientedBox(0.02, 0.006, armLen, fv, n, armC, M.printBlack));
      const tab = orientedBox(0.026, 0.012, 0.004, fv, n, at2(sg * (wall - 0.002), vc - 0.004, -0.008), M.printBlack); bracket.add(tab);
      const sc = screw(0.0012, 0.006); sc.position.copy(at2(sg * (wall - 0.002), vc - 0.004, -0.008)); sc.rotation.x = sg * Math.PI / 2; bracket.add(sc);
    }
  }
  // absorber: black finned plate behind the glass, trimmed at the top to stay out of the exit beam
  const absMat = new THREE.MeshStandardMaterial({ color: 0x0b0b0c, roughness: 0.9, metalness: 0.3, emissive: 0xc8300c, emissiveIntensity: 0 });
  const absorber = new THREE.Group();
  const absV0 = ff.v0 - 0.002, absV1 = ff.v1 - 0.022;
  {
    const lv = absV1 - absV0, vmid = (absV0 + absV1) / 2;
    absorber.add(orientedBox(lv, 0.003, lenU - 0.006, fv, n, at2(uc, vmid, -0.010), absMat));
    for (let i = 0; i < 11; i++) {
      const u = ff.u0 + 0.008 + i * (lenU - 0.016) / 10;
      absorber.add(orientedBox(lv, 0.012, 0.0012, fv, n, at2(u, vmid, -0.0175), absMat));
    }
  }
  const clips = new THREE.Group();
  for (const [u, v] of [[ff.u0 + 0.02, ff.v0], [ff.u1 - 0.02, ff.v0], [ff.u0 + 0.02, ff.v1], [ff.u1 - 0.02, ff.v1]]) {
    clips.add(orientedBox(0.004, 0.0015, 0.01, fv, n, at2(u, v + (v > vc ? -0.001 : 0.001), 0.0008), M.printBlack));
  }
  addPart(c, 'bracket', 'Printed fold bracket', bracket, n.clone().multiplyScalar(-0.04), 'Holds the glass at the traced angle; arms bolt to bosses on the housing walls.');
  addPart(c, 'absorber', 'IR absorber', absorber, n.clone().multiplyScalar(-0.08).add(v3(0, 0.02, 0)), 'Black finned aluminium: the infrared the coating transmits ends here as heat.');
  addPart(c, 'glass', 'Cold-mirror glass', glass, n.clone().multiplyScalar(0.05), 'Dielectric coating: reflects visible, transmits infrared.');
  addPart(c, 'clips', 'Retaining clips', clips, n.clone().multiplyScalar(0.08), '');
  c.assembly = [
    { title: 'Bracket', parts: ['bracket'], text: 'The printed bracket sets the fold angle.' },
    { title: 'Absorber', parts: ['absorber'], text: 'The black absorber mounts behind where the glass will sit.' },
    { title: 'Cold-mirror glass', parts: ['glass'], text: 'The glass drops into the frame, coating toward the panel and the concave mirror; plane of incidence aligned with the windshield\'s.' },
    { title: 'Clips', parts: ['clips'], text: 'Four clips hold the glass without stress.' },
  ];
  c.fold = ff;
  // ---- working: sunlight from the concave mirror splits; image light from the panel reflects ----
  c.fx = new THREE.Group(); c.fx.name = 'workingFX'; c.group.add(c.fx); c.fx.visible = false;
  const fromMirror = G.TO_FOLD.clone().negate();                     // direction fold -> concave mirror
  const sunIn = G.TO_FOLD.clone();                                    // sunlight travels mirror -> fold
  const visRays = [], irRays = [], imgRays = [];
  const samples = [[-0.05, -0.02], [0, 0.0], [0.05, 0.015], [-0.025, 0.025], [0.03, -0.03]];
  for (const [u, v] of samples) {
    const hit = at2(u, v, 0);
    const start = hit.clone().addScaledVector(fromMirror, 0.12);
    const out = G.reflect(sunIn, n);
    const vis = ray([start, hit, hit.clone().addScaledVector(out, 0.07 / Math.max(0.2, Math.abs(out.y)))], SUNC, { opacity: 0.8 });
    const irEnd = hit.clone().addScaledVector(sunIn, 0.03);
    const ir = ray([start.clone().add(v3(0, 0.0015, 0)), hit.clone().add(v3(0, 0.0015, 0)), irEnd], IR, { dashed: true, dash: 0.004, gap: 0.003 });
    const panelPt = hit.clone().add(v3(0, -0.07, 0));
    const img = ray([panelPt, hit, hit.clone().addScaledVector(fromMirror, 0.1)], AMBER, { opacity: 0.9 });
    visRays.push(vis); irRays.push(ir); imgRays.push(img);
    c.fx.add(vis, ir, img);
  }
  const l1 = labelSprite(['Cold mirror', 'reflects visible, transmits infrared'], 0.007, { accent: '#8fb5ff' }); l1.position.copy(at2(ff.u1 + 0.01, ff.v1, 0.01)); c.fx.add(l1);
  const l2 = labelSprite(['Sun from the concave mirror', `${V.sun_w} collected → ${V.sun_after_cold} visible goes on`, `(${V.vis_frac} visible, ASSUMED)`], 0.007, { accent: '#fff2d0' }); l2.position.copy(at2(0, 0, 0).addScaledVector(fromMirror, 0.13).add(v3(0, 0.02, 0))); c.fx.add(l2);
  const l3 = labelSprite(['Infrared → absorber (heat)'], 0.007, { accent: '#d2283c' }); l3.position.copy(at2(ff.u0, absV1, -0.03)); c.fx.add(l3);
  const l4 = labelSprite(['Image light: panel → fold → mirror'], 0.007, { accent: '#ffb347' }); l4.position.copy(at2(ff.u0 - 0.02, ff.v0, 0).add(v3(0, -0.06, 0))); c.fx.add(l4);
  let heat = 0;
  c.setWorking = (on) => { c.fx.visible = on; if (!on) { heat = 0; absMat.emissiveIntensity = 0; } };
  c.update = (t, dt, s) => {
    if (!(s && s.working)) return;
    heat = Math.min(1, heat + dt * 0.25);
    absMat.emissiveIntensity = 0.16 * heat * (0.85 + 0.15 * Math.sin(t * 3));
    const ph = (t * 0.6) % 1;
    irRays.forEach((r) => { r.material.dashOffset = -t * 0.02; });
    visRays.forEach((r, i) => { r.material.opacity = 0.55 + 0.35 * Math.sin(t * 2 + i); });
    imgRays.forEach((r, i) => { r.material.opacity = 0.6 + 0.3 * Math.sin(t * 2.4 + i + ph); });
  };
  return c;
}

// ---------------------------------------------------------------------------------------------------------------
// concaveMirror
// ---------------------------------------------------------------------------------------------------------------
function mirrorSubstrate(mode) {
  const g = new THREE.Group();
  const nu = 40, nv = 28, hw = G.MIRROR_W / 2, hh = G.MIRROR_H / 2;
  const pos = [], idx = [];
  for (let j = 0; j <= nv; j++) for (let i = 0; i <= nu; i++) {
    const p = mirrorPoint(-hw + 2 * hw * i / nu, -hh + 2 * hh * j / nv, mode); pos.push(p.x, p.y, p.z);
  }
  for (let j = 0; j < nv; j++) for (let i = 0; i < nu; i++) {
    const a = j * (nu + 1) + i, b = a + 1, cc = a + nu + 1, d = cc + 1;
    idx.push(a, b, cc, b, d, cc);
  }
  const fg = new THREE.BufferGeometry(); fg.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); fg.setIndex(idx); fg.computeVertexNormals();
  const front = new THREE.Mesh(fg, M.mirror); front.castShadow = true; front.receiveShadow = true; g.add(front);
  // back plane and edges
  const back = (u, v) => G.MIRROR_U.clone().multiplyScalar(u).addScaledVector(G.MIRROR_V, v).addScaledVector(G.MIRROR_N, -MIRROR_BACK);
  const sidePos = [];
  const edge = (pts) => { for (let k = 0; k < pts.length - 1; k++) { const [u0, v0] = pts[k], [u1, v1] = pts[k + 1]; const a = mirrorPoint(u0, v0, mode), b = mirrorPoint(u1, v1, mode), cB = back(u0, v0), dB = back(u1, v1); sidePos.push(...a.toArray(), ...b.toArray(), ...cB.toArray(), ...b.toArray(), ...dB.toArray(), ...cB.toArray()); } };
  const ring = [];
  for (let i = 0; i <= nu; i++) ring.push([-hw + 2 * hw * i / nu, -hh]);
  for (let j = 1; j <= nv; j++) ring.push([hw, -hh + 2 * hh * j / nv]);
  for (let i = nu - 1; i >= 0; i--) ring.push([-hw + 2 * hw * i / nu, hh]);
  for (let j = nv - 1; j >= 0; j--) ring.push([-hw, -hh + 2 * hh * j / nv]);
  edge(ring);
  const c0 = back(-hw, -hh), c1 = back(hw, -hh), c2 = back(hw, hh), c3 = back(-hw, hh);
  sidePos.push(...c0.toArray(), ...c2.toArray(), ...c1.toArray(), ...c0.toArray(), ...c3.toArray(), ...c2.toArray());
  const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.Float32BufferAttribute(sidePos, 3)); sg.computeVertexNormals();
  const glassBody = new THREE.Mesh(sg, new THREE.MeshPhysicalMaterial({ color: 0x8aa59c, roughness: 0.15, transparent: true, opacity: 0.85, side: THREE.DoubleSide }));
  glassBody.castShadow = true; g.add(glassBody);
  const lbl = textDecal(`R ${mode === 'sphere' ? '660' : `${(G.R_T_CORR * 1000).toFixed(0)} / ${(G.R_S_CORR * 1000).toFixed(0)}`} mm · first surface Al + SiO₂`, 0.12, { color: '#cfd6dc' });
  const zA = G.MIRROR_U.clone();
  lbl.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(zA.clone().negate(), G.MIRROR_V, G.MIRROR_N.clone().negate()));
  lbl.position.copy(back(0, -0.06).addScaledVector(G.MIRROR_N, -0.0004)); lbl.scale.setScalar(0.5); g.add(lbl);
  return g;
}

export function buildConcaveMirror(opts = {}) {
  let mode = opts.mode || G.MIRROR.mode;
  const c = makeComponent(THREE, {
    id: 'concaveMirror',
    name: 'Custom concave relay mirror, 300 × 200 mm, f = 330 mm',
    category: 'optics',
    mount: 'mirror vertex at geom.MIRROR_C; car-frame orientation (normal geom.MIRROR_N, axes geom.MIRROR_U lateral, geom.MIRROR_V tangential)',
    size: [0.2, 0.25, 0.32],
    desc: `The one custom optic. With the panel 316 mm away, inside its 330 mm focal length, the mirror forms a magnified virtual image 7.5 m behind itself, which the windshield folds into the driver's view. Used ${(G.MIRROR_INC / DEG).toFixed(1)}° off axis, a plain sphere splits that image into two focal distances; a toroid with different radii in the two planes brings them together.`,
    working: 'A panel point sends a fan of rays that leave the mirror diverging, as if from a point 7.5 m behind it; in a second phase, parallel sunlight from the windshield is focused to a 6 mm spot just past the panel.',
  });
  const im = (m) => G.mirrorImages(m);
  c.facts = [
    ['Focal length, radius (plan)', `f = ${R.F2} mm, R = ${R.R_SPH} mm (spherical)`],
    ['Object distance', `u = ${R.U2.toFixed(0)} mm, ${V.focus_gap} inside focus`],
    ['Magnification, image', `${R.M2.toFixed(1)}; ${V.img2_w} × ${V.img2_h} at 7.5 m`],
    ['Incidence in this layout', `${(G.MIRROR_INC / DEG).toFixed(1)}°`],
    ['Sphere at this incidence', `tangential image ${(-im('sphere').vt).toFixed(1)} m, sagittal ${(-im('sphere').vs).toFixed(1)} m behind the mirror`],
    ['Toroid correction', `Rt ${(G.R_T_CORR * 1000).toFixed(0)} mm, Rs ${(G.R_S_CORR * 1000).toFixed(0)} mm: both images at ${(-im('toroid').vt).toFixed(1)} m`],
    ['Aperture needed', `${V.mir_w} × ${V.mir_h} mm at 1 m (traced here: about ${(G.footprints(mode).mirrorUV.max.x - G.footprints(mode).mirrorUV.min.x) * 1000 | 0} mm wide)`],
    ['Sun focus', `${V.sun_w} into a ${V.sun_spot_mm} mm spot (${V.sun_wcm2} W/cm²) before filters`],
    ['Price', costOf('Concave mirror')],
  ];
  const N = G.MIRROR_N, U = G.MIRROR_U, Vv = G.MIRROR_V;
  const mp = (u, v, w) => U.clone().multiplyScalar(u).addScaledVector(Vv, v).addScaledVector(N, w);
  let substrate = mirrorSubstrate(mode);
  const subPart = new THREE.Group(); subPart.add(substrate);
  // cradle: printed back plate, two legs to the housing floor, feet
  const cradle = new THREE.Group();
  const floorY = G.HOUSING.floor - G.MIRROR_C.y;
  {
    cradle.add(orientedBox(0.26, 0.16, 0.008, U, Vv, mp(0, 0, -0.032), M.printBlack));
    for (let i = 0; i < 6; i++) cradle.add(orientedBox(0.004, 0.15, 0.012, U, Vv, mp(-0.11 + i * 0.044, 0, -0.042), M.printBlack));
    for (const sg of [-1, 1]) {
      const topP = mp(sg * 0.1, -0.06, -0.036);
      const h = topP.y - floorY;
      const leg = slab(0.016, h, 0.012, M.printBlack); leg.position.set(topP.x, floorY + h / 2, topP.z); cradle.add(leg);
      const foot = rbox(0.04, 0.006, 0.026, 0.002, M.printBlack); foot.position.set(topP.x, floorY + 0.003, topP.z); cradle.add(foot);
      for (const dx of [-0.013, 0.013]) { const sc = screw(0.0013, 0.006); sc.position.set(topP.x + dx, floorY + 0.0062, topP.z); cradle.add(sc); }
    }
  }
  // three adjusters: two at the bottom corners, one at the top centre (push-pull screws with springs)
  const adjusters = new THREE.Group();
  for (const [u, v] of [[-0.1, -0.06], [0.1, -0.06], [0, 0.065]]) {
    const a = mp(u, v, -MIRROR_BACK), b = mp(u, v, -0.036);
    const q = new THREE.Quaternion().setFromUnitVectors(v3(0, 1, 0), N);
    const spring = new THREE.Mesh(new THREE.TorusGeometry(0.004, 0.0006, 6, 16), M.steel);
    for (let k = 0; k < 6; k++) { const s2 = spring.clone(); s2.quaternion.copy(q).multiply(new THREE.Quaternion().setFromAxisAngle(v3(1, 0, 0), Math.PI / 2)); s2.position.copy(a.clone().lerp(b, 0.15 + k * 0.13)); adjusters.add(s2); }
    const rod = cyl(0.0015, 0.0015, a.distanceTo(b) + 0.012, M.steel, 10); rod.quaternion.copy(q); rod.position.copy(a.clone().lerp(b, 0.5).addScaledVector(N, -0.006)); adjusters.add(rod);
    const knob = cyl(0.0055, 0.0055, 0.006, M.aluAnodBlack, 18); knob.quaternion.copy(q); knob.position.copy(b.clone().addScaledVector(N, -0.016)); adjusters.add(knob);
  }
  const clips = new THREE.Group();
  for (const [u, v] of [[-0.15, -0.1], [0.15, -0.1], [-0.15, 0.1], [0.15, 0.1]]) {
    const p = mirrorPoint(u, v, mode);
    clips.add(orientedBox(0.012, 0.012, 0.004, U, Vv, p.clone().addScaledVector(U, -Math.sign(u) * 0.004).addScaledVector(Vv, -Math.sign(v) * 0.004).addScaledVector(N, 0.0015), M.printBlack));
  }
  addPart(c, 'cradle', 'Printed cradle', cradle, N.clone().multiplyScalar(-0.06).add(v3(0, -0.04, 0)), 'Back plate and two legs; feet screw to the mirror boss on the housing floor.');
  addPart(c, 'adjusters', 'Tilt adjusters', adjusters, N.clone().multiplyScalar(-0.03), 'Three push-pull screws set the mirror angle during calibration.');
  addPart(c, 'substrate', 'Mirror (first surface)', subPart, N.clone().multiplyScalar(0.06), 'Aluminium on the front face, so there is no second reflection.');
  addPart(c, 'clips', 'Edge clips', clips, N.clone().multiplyScalar(0.11), 'Hold the mirror on its adjusters without bending it.');
  c.assembly = [
    { title: 'Cradle', parts: ['cradle'], text: 'The printed cradle stands on the mirror boss.' },
    { title: 'Adjusters', parts: ['adjusters'], text: 'Three spring-loaded screws give tilt in both axes.' },
    { title: 'Mirror', parts: ['substrate'], text: 'The first-surface mirror sits on the adjusters, coating facing the fold and the windshield.' },
    { title: 'Edge clips', parts: ['clips'], text: 'Four clips hold it.' },
  ];
  // ---- working visuals ----
  c.fx = new THREE.Group(); c.fx.name = 'workingFX'; c.group.add(c.fx); c.fx.visible = false;
  const fxImage = new THREE.Group(), fxSun = new THREE.Group(); c.fx.add(fxImage, fxSun);
  const src = G.TO_FOLD.clone().multiplyScalar(G.U);                // the panel point, unfolded through the fold
  const srcDot = sphere(0.003, M.emissive(0xffb347, 2), 12); srcDot.position.copy(src); fxImage.add(srcDot);
  const srcGlow = glowSprite(0.03, 0xffb347); srcGlow.position.copy(src); fxImage.add(srcGlow);
  const fans = [];
  const tanPts = [-0.085, -0.045, 0, 0.045, 0.085].map((v) => [0, v, 'tan']);
  const sagPts = [-0.13, -0.065, 0.065, 0.13].map((u) => [u, 0, 'sag']);
  for (const [u, v, kind] of [...tanPts, ...sagPts]) {
    const col = kind === 'tan' ? AMBER : 0x5ec8ff;
    const inc = ray([src, src], col, { opacity: 0.85 });
    const out = ray([src, src], col, { opacity: 0.85 });
    const back = ray([src, src], col, { dashed: true, opacity: 0.6, dash: 0.01, gap: 0.006 });
    fxImage.add(inc, out, back);
    fans.push({ u, v, kind, inc, out, back });
  }
  let imgLabel = null, inset = null;
  const sunRays = [];
  for (let i = 0; i < 5; i++) for (let j = 0; j < 4; j++) {
    const r1 = ray([src, src], SUNC, { opacity: 0.7 }), r2 = ray([src, src], 0xff7a3a, { opacity: 0.85 });
    fxSun.add(r1, r2); sunRays.push({ u: -0.13 + 0.065 * i, v: -0.075 + 0.05 * j, r1, r2 });
  }
  const spot = new THREE.Mesh(new THREE.CircleGeometry(R.R90_PGU / 1000, 32), new THREE.MeshBasicMaterial({ color: 0xffe2a0, toneMapped: false, side: THREE.DoubleSide }));
  spot.quaternion.setFromUnitVectors(v3(0, 0, 1), G.TO_FOLD); spot.position.copy(src); fxSun.add(spot);
  const spotGlow = glowSprite(0.05, 0xff8a3a); spotGlow.position.copy(src); fxSun.add(spotGlow);
  const panelPlane = new THREE.Mesh(new THREE.PlaneGeometry(0.06, 0.03), new THREE.MeshBasicMaterial({ color: 0x223344, transparent: true, opacity: 0.6, side: THREE.DoubleSide }));
  panelPlane.quaternion.setFromUnitVectors(v3(0, 0, 1), G.TO_FOLD); panelPlane.position.copy(src); fxSun.add(panelPlane);
  const sunLbl = labelSprite(['Sun focus (phase 2)', `${V.sun_w} collected through the glass (70%, ASSUMED)`, `90% of rays within ${V.r90_pgu} mm at the panel: ${V.sun_wcm2} W/cm²`, `focus ${V.focus_gap} beyond the panel`, `after cold mirror + IR cut + polariser: ${V.sun_after_pol}, ${V.sun_after_pol_wcm2} W/cm² ≈ ${V.sun_suns} suns`], 0.009, { accent: '#ff7a3a' });
  sunLbl.position.copy(mp(0, 0.12, 0.05)); fxSun.add(sunLbl);

  const traceFans = () => {
    const { Rt, Rs } = G.mirrorRadii(mode);
    for (const f of fans) {
      const Pm = mirrorPoint(f.u, f.v, mode);
      const d = Pm.clone().sub(src).normalize();
      const nn = mirrorNormal(f.u, f.v, mode);
      const r = G.reflect(d, nn).normalize();
      setRay(f.inc, [src, Pm]);
      setRay(f.out, [Pm, Pm.clone().addScaledVector(r, 0.42)]);
      setRay(f.back, [Pm, Pm.clone().addScaledVector(r, -0.7)]);
    }
    for (const s of sunRays) {
      const Pm = mirrorPoint(s.u, s.v, mode);
      const din = G.TO_MIRROR.clone();
      const r = G.reflect(din, mirrorNormal(s.u, s.v, mode)).normalize();
      // to the unfolded panel plane through src, then on to 2 cm past it
      const t = src.clone().sub(Pm).dot(G.TO_FOLD) / r.dot(G.TO_FOLD);
      setRay(s.r1, [Pm.clone().addScaledVector(din, -0.22), Pm]);
      setRay(s.r2, [Pm, Pm.clone().addScaledVector(r, t + 0.02)]);
    }
    const a = G.mirrorImages(mode);
    if (imgLabel) { fxImage.remove(imgLabel); imgLabel.material.map.dispose(); }
    imgLabel = labelSprite([
      mode === 'sphere' ? `Sphere R 660, used ${(G.MIRROR_INC / DEG).toFixed(1)}° off axis` : `Toroid Rt ${(G.R_T_CORR * 1000).toFixed(0)} / Rs ${(G.R_S_CORR * 1000).toFixed(0)} mm`,
      `amber (tangential fan): image ${(-a.vt).toFixed(1)} m behind`,
      `blue (sagittal fan): image ${(-a.vs).toFixed(1)} m behind`,
      'dashed: where the reflected rays appear to come from',
    ], 0.009, { accent: mode === 'sphere' ? '#ff5a5a' : '#4fd18b' });
    imgLabel.position.copy(mp(0, 0.12, 0.05)); fxImage.add(imgLabel);
    // inset: distances to scale, 0..20 m
    if (inset) { fxImage.remove(inset); inset.material.map.dispose(); }
    const tex = canvasTexture(900, 220, (ctx, W, H) => {
      ctx.fillStyle = 'rgba(12,14,18,0.86)'; ctx.fillRect(0, 0, W, H);
      const x0 = 50, x1 = W - 40, k = (x1 - x0) / 20;
      ctx.strokeStyle = '#8a9099'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x0, 150); ctx.lineTo(x1, 150); ctx.stroke();
      ctx.fillStyle = '#c9ced6'; ctx.font = `500 22px "Helvetica Neue", Helvetica, Arial, sans-serif`; ctx.textAlign = 'center';
      for (let m = 0; m <= 20; m += 5) { ctx.fillText(`${m} m`, x0 + m * k, 185); ctx.beginPath(); ctx.moveTo(x0 + m * k, 145); ctx.lineTo(x0 + m * k, 155); ctx.stroke(); }
      const mark = (d, col, txt, yy) => { const x = x0 + Math.min(20, d) * k; ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x, 150, 9, 0, 7); ctx.fill(); ctx.fillText(txt, Math.min(x, x1 - 90), yy); };
      mark(7.5, '#4fd18b', 'target 7.5', 120);
      mark(-a.vt, '#ffb347', `tangential ${(-a.vt).toFixed(1)}`, 60);
      mark(-a.vs, '#5ec8ff', `sagittal ${(-a.vs).toFixed(1)}`, 90);
      ctx.textAlign = 'left'; ctx.fillStyle = '#f3efe6'; ctx.font = `600 24px "Helvetica Neue", Helvetica, Arial, sans-serif`;
      ctx.fillText('Virtual image distance behind the mirror', x0, 32);
    });
    inset = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true, toneMapped: false }));
    inset.scale.set(0.26, 0.26 * 220 / 900, 1); inset.position.copy(mp(0, -0.15, 0.06)); inset.renderOrder = 50; fxImage.add(inset);
  };
  traceFans();
  c.handles = {
    setMode(m) {
      if (m === mode) return; mode = m;
      subPart.remove(substrate); substrate.traverse((o) => { if (o.geometry) o.geometry.dispose(); });
      substrate = mirrorSubstrate(mode); subPart.add(substrate);
      traceFans();
    },
    getMode: () => mode,
  };
  c.setWorking = (on) => { c.fx.visible = on; };
  c.update = (t, dt, s) => {
    if (!(s && s.working)) return;
    const ph = t % 14;
    const sunPhase = ph >= 8;
    fxImage.visible = !sunPhase; fxSun.visible = sunPhase;
    const pulse = 0.65 + 0.35 * Math.sin(t * 3);
    fans.forEach((f) => { f.back.material.dashOffset = -t * 0.03; f.out.material.opacity = 0.6 + 0.3 * pulse; });
    spotGlow.material.opacity = sunPhase ? smoothstep(8, 10, ph) * pulse : 0;
    spot.material.color.setRGB(1, 0.75 + 0.2 * pulse, 0.4 + 0.3 * pulse);
  };
  return c;
}

// ---------------------------------------------------------------------------------------------------------------
// shutter: two telescoping leaves, a Scotch-yoke lever on an SG90-class servo, a constant-force return spring
// ---------------------------------------------------------------------------------------------------------------
// Built flat in its own XZ plane: the aperture runs along X from -L/2 to +L/2 (rear to front), width W along Z.
export function buildShutter(opts = {}) {
  const L = opts.L ?? 0.26, W = opts.W ?? 0.29;
  const c = makeComponent(THREE, {
    id: 'shutter',
    name: 'Sun shutter: two-leaf blade, servo and return spring',
    category: 'optics',
    mount: 'centre of the aperture in the plane of the blades (local X along the lid toward the front)',
    size: [L * 2 + 0.03, 0.03, W + 0.05],
    desc: 'Two thin black leaves cover the mirror aperture under the dust cover. A micro servo opens them through a Scotch-yoke lever; a constant-force spring pulls them shut, so the shutter fails closed if power or the controller stops. It closes whenever the HUD is off and whenever the sun-watch rule finds the sun in the entry patch.',
    working: 'The servo horn swings the lever, the front leaf slides back under the rear one and carries it into the garage; on release the spring draws both closed.',
  });
  c.facts = [
    ['Why', `focused sun: ${V.sun_after_pol} in a ${V.sun_spot_mm} mm spot even after the filters (≈ ${V.sun_suns} suns)`],
    ['Closed when', 'the HUD is off (parked car is the long-exposure case), sun-watch says so, cell too hot, or USB silent 5 s'],
    ['Entry patch', `${V.patch_w}° × ${V.patch_h}° of sky, ${V.sun_elev}° elevation behind the car; crossed in about ${V.patch_minutes} min`],
    ['Actuator', 'SG90-class micro servo on the HUD controller, 140 mm Scotch-yoke lever'],
    ['Fail-safe', 'constant-force spring closes it with no power'],
    ['Price', `${costOf('HUD controller')} (servo is in the controller line)`],
  ];
  const leafLen = L / 2 + 0.01, rail = 0.004;
  const xBack = -L / 2 - leafLen - 0.012, xFront = L / 2 + 0.014;
  // rails and stops
  const rails = new THREE.Group();
  for (const sg of [-1, 1]) {
    const z = sg * (W / 2 + rail / 2 + 0.001);
    const r = slab(xFront - xBack, 0.006, rail, M.printBlack); r.position.set((xBack + xFront) / 2, -0.001, z); rails.add(r);
    const lip = slab(xFront - xBack, 0.0012, rail + 0.003, M.printBlack); lip.position.set((xBack + xFront) / 2, 0.0025, z - sg * 0.0015); rails.add(lip);
  }
  for (const x of [xBack, xFront]) { const stop = slab(0.004, 0.006, W + 2 * rail + 0.002, M.printBlack); stop.position.set(x, -0.001, 0); rails.add(stop); }
  // leaves: part groups at their closed positions, blades as animated children
  const leafMat = new THREE.MeshStandardMaterial({ color: 0x0c0c0d, roughness: 0.85, metalness: 0.1 });
  const mkLeaf = (x, y) => {
    const g = new THREE.Group(); g.position.set(x, y, 0);
    const blade = new THREE.Group();
    const b = slab(leafLen, 0.0008, W, leafMat); blade.add(b);
    for (const z of [-W / 2 + 0.003, W / 2 - 0.003]) { const shoe = slab(leafLen - 0.01, 0.0018, 0.004, M.plasticWhite); shoe.position.set(0, 0, z); blade.add(shoe); }
    g.add(blade); g.userData.blade = blade; return g;
  };
  const leafRear = mkLeaf(-L / 4 - 0.0025, 0.0012);
  const leafFront = mkLeaf(L / 4 + 0.0025, -0.0008);
  // Servo and lever (Scotch yoke). The lever runs under the leaves and its pin reaches up into a slot under the front
  // leaf. The pivot sits 2 mm inside the blade width so the pin stays on the leaf at both ends of the travel, and the
  // servo body hangs behind it, out of the beam (docs/arhud-cad checks this against the traced rays).
  const Rl = L / 2 + 0.003;
  const pivot = v3(-L / 2 + 0.0035, 0, W / 2 - 0.002);
  // pick-up tab on the front leaf and the yoke slot (along Z) under its rear edge
  {
    const bl = leafFront.userData.blade;
    const slotLen = Rl + 0.008;
    const slotBar1 = slab(0.002, 0.0015, slotLen, M.printBlack); slotBar1.position.set(-leafLen / 2 + 0.006, -0.00115, pivot.z + 0.004 - slotLen / 2); bl.add(slotBar1);
    const slotBar2 = slotBar1.clone(); slotBar2.position.x += 0.007; bl.add(slotBar2);
    const tab = slab(0.006, 0.004, 0.012, M.printBlack); tab.position.set(-leafLen / 2 + 0.003, 0.0025, -W / 2 + 0.02); bl.add(tab);
  }
  const servo = new THREE.Group();
  const horn = new THREE.Group();
  {
    const body = rbox(0.0225, 0.0227, 0.0122, 0.001, new THREE.MeshStandardMaterial({ color: 0x1f4fb8, roughness: 0.4 }));
    body.position.set(pivot.x - 0.006, -0.0235, pivot.z); servo.add(body);
    const tabs = slab(0.032, 0.0025, 0.0122, new THREE.MeshStandardMaterial({ color: 0x1f4fb8, roughness: 0.4 })); tabs.position.set(pivot.x - 0.006, -0.0155, pivot.z); servo.add(tabs);
    const lab = textDecal('SG90', 0.012, { color: '#fff' }); lab.position.set(pivot.x - 0.006, -0.0235, pivot.z + 0.0062); servo.add(lab);
    const shaft = cyl(0.0025, 0.0025, 0.007, M.plasticWhite, 16); shaft.position.set(pivot.x, -0.0085, pivot.z); servo.add(shaft);
    for (const dz of [-0.002, 0, 0.002]) { const w = tube([[pivot.x - 0.017, -0.0275, pivot.z + dz], [pivot.x - 0.03, -0.0295, pivot.z + dz], [pivot.x - 0.05, -0.0375, pivot.z + dz]], 0.0005, [M.cableBlack, M.cableRed, M.cableOrange][dz === 0 ? 1 : dz < 0 ? 0 : 2]); servo.add(w); }
    const arm = slab(Rl, 0.0018, 0.006, M.plasticWhite); arm.position.set(Rl / 2, 0, 0); horn.add(arm);
    const hub = cyl(0.005, 0.005, 0.0025, M.plasticWhite, 16); horn.add(hub);
    const pin = cyl(0.0018, 0.0018, 0.0034, M.steel, 10); pin.position.set(Rl, 0.002, 0); horn.add(pin);
    horn.position.set(pivot.x, -0.004, pivot.z);
    servo.add(horn);
  }
  // constant-force spring: drum rides on the front leaf's rear corner, ribbon anchored at the front stop
  const spring = new THREE.Group();
  const anchor = v3(xFront + 0.004, -0.0035, -W / 2 + 0.006);           // 18 mm ahead of the aperture, out of the beam
  let ribbonMesh, drum;
  {
    drum = new THREE.Group();
    const d0 = cyl(0.0048, 0.0048, 0.005, M.steel, 24); drum.add(d0);
    const coil = new THREE.Mesh(new THREE.TorusGeometry(0.0038, 0.0009, 6, 24), M.steel); coil.rotation.x = Math.PI / 2; drum.add(coil);
    spring.add(drum);
    const block = slab(0.006, 0.008, 0.008, M.printBlack); block.position.copy(anchor); spring.add(block);
    ribbonMesh = slab(1, 0.0003, 0.004, M.steel); spring.add(ribbonMesh);
  }
  addPart(c, 'rails', 'Rails and stops', rails, v3(0, -0.02, 0), 'Printed guides under the dust cover; the garage is behind the aperture.');
  addPart(c, 'leafRear', 'Rear leaf', leafRear, v3(0, 0.03, 0), 'Black blade; the front leaf picks it up halfway.');
  addPart(c, 'leafFront', 'Front leaf', leafFront, v3(0, 0.015, 0), 'Driven by the yoke; slides under the rear leaf.');
  addPart(c, 'servo', 'Servo and Scotch-yoke lever', servo, v3(0, -0.03, 0.03), 'SG90-class servo on the controller\'s PWM; the lever pin rides in the slot.');
  addPart(c, 'spring', 'Constant-force return spring', spring, v3(0.03, -0.01, 0), 'Pulls the front leaf closed: the shutter fails closed.');
  c.assembly = [
    { title: 'Rails', parts: ['rails'], text: 'The rails go under the lid, with the garage behind the aperture.' },
    { title: 'Rear leaf', parts: ['leafRear'], text: 'The rear leaf slides into the rails.' },
    { title: 'Front leaf', parts: ['leafFront'], text: 'The front leaf slides in below it, slot toward the servo.' },
    { title: 'Servo and lever', parts: ['servo'], text: 'The servo mounts beside the garage; its lever pin drops into the slot.' },
    { title: 'Return spring', parts: ['spring'], text: 'The constant-force spring hooks onto the front leaf: no power, shutter closed.' },
  ];
  // kinematics: open fraction o in [0,1] -> lever angle; front-leaf shift = pin x travel; rear leaf picked up past half
  let open = 0, target = null;
  const apply = () => {
    const th = Math.PI * open;                                       // lever angle 0 (pointing +X) .. 180 degrees
    horn.rotation.y = th;                                            // rotates the pin from +X through -Z to -X
    const pinX = pivot.x + Rl * Math.cos(th);
    const fShift = pinX - (pivot.x + Rl);                            // 0 .. -2Rl
    leafFront.userData.blade.position.x = fShift;
    leafRear.userData.blade.position.x = Math.min(0, fShift + L / 2 + 0.005);
    // drum follows the front leaf; the ribbon runs forward to the anchor
    const dpos = leafFront.position.clone().add(v3(fShift - leafLen / 2 + 0.006, -0.0035, -W / 2 + 0.006)).sub(spring.position);
    drum.position.copy(dpos);
    const a = dpos.clone().add(v3(0.0045, 0, 0)), end = anchor.clone();
    const len = Math.max(0.001, a.distanceTo(end));
    ribbonMesh.scale.x = len; ribbonMesh.position.copy(a.clone().lerp(end, 0.5));
    ribbonMesh.rotation.y = -Math.atan2(end.z - a.z, end.x - a.x);
  };
  apply();
  c.handles = { setOpen(x) { target = clamp(x, 0, 1); }, getOpen: () => open };
  c.fx = new THREE.Group(); c.fx.name = 'workingFX'; c.group.add(c.fx); c.fx.visible = false;
  const lbl = labelSprite(['Shutter', 'closed whenever the HUD is off;', 'the sun-watch rule closes it while driving', 'spring-return: fails closed'], 0.01, { accent: '#ffc04d' });
  lbl.position.set(0, 0.03, 0); c.fx.add(lbl);
  c.setWorking = (on) => { c.fx.visible = on; };
  c.update = (t, dt, s) => {
    let goal;
    if (target !== null) goal = target;
    else if (s && s.working) { const ph = t % 8; goal = ph < 1 ? 0 : ph < 4 ? 1 : ph < 5 ? 1 : 0; }
    else goal = open;
    const rate = goal > open ? 0.7 : 1.4;                              // servo opens, spring closes faster
    open += clamp(goal - open, -rate * dt, rate * dt);
    apply();
  };
  return c;
}

// ---------------------------------------------------------------------------------------------------------------
// dustCover
// ---------------------------------------------------------------------------------------------------------------
export function buildDustCover(opts = {}) {
  const L = opts.L ?? 0.27, W = opts.W ?? 0.30;
  const c = makeComponent(THREE, {
    id: 'dustCover',
    name: 'Dust cover with s-pass polariser',
    category: 'optics',
    mount: 'centre of the glass underside, in the lid plane (local X along the lid toward the front)',
    size: [L + 0.02, 0.008, W + 0.02],
    desc: 'The window in the top of the housing. It keeps dust off the mirror, and a polariser laminated to its inside passes the HUD\'s own s-polarised light while absorbing more than half of any unpolarised sunlight trying to get in. The ambient-light sensor looks out through a window at one edge.',
    working: 'The HUD\'s s-polarised light passes; unpolarised sunlight arrives and only about 42% gets through.',
  });
  c.facts = [
    ['Polariser', `s-pass (axis across the car); ${V.pol_t} of unpolarised light (ASSUMED)`],
    ['HUD light', 's-polarised, so it passes almost unchanged'],
    ['Sun after the filters', `${V.sun_after_filt} → ${V.sun_after_pol}`],
    ['Sensor window', 'ambient-light sensor (TSL2591 or VEML7700) for the dimming curve'],
    ['Demo rule', 'no polarised sunglasses: they block exactly this light'],
    ['Price', costOf('Half-wave')],
  ];
  const glass = new THREE.Group();
  { const m = slab(L, 0.003, W, M.glass); m.position.y = 0.0015; glass.add(m); }
  const polTex = canvasTexture(128, 128, (ctx, Wc, Hc) => {
    ctx.fillStyle = 'rgba(70,90,92,0.9)'; ctx.fillRect(0, 0, Wc, Hc);
    ctx.strokeStyle = 'rgba(210,235,235,0.25)'; ctx.lineWidth = 2;
    for (let i = 0; i < Wc; i += 8) { ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, Hc); ctx.stroke(); }
  }, { repeat: [6, 6] });
  const pol = new THREE.Group();
  { const m = slab(L - 0.002, 0.0003, W - 0.002, new THREE.MeshPhysicalMaterial({ color: 0xffffff, map: polTex, transparent: true, opacity: 0.5, roughness: 0.3, depthWrite: false })); m.position.y = -0.00015; pol.add(m); }
  const bezel = new THREE.Group();
  {
    const t = 0.008, h = 0.005;
    for (const [x, z, w, d] of [[0, W / 2 + t / 2, L + 2 * t, t], [0, -W / 2 - t / 2, L + 2 * t, t], [L / 2 + t / 2, 0, t, W], [-L / 2 - t / 2, 0, t, W]]) {
      const b = rbox(w, h, d, 0.0015, M.printBlack); b.position.set(x, h / 2 - 0.001, z); bezel.add(b);
    }
    for (const [x, z] of [[-L / 2 - 0.004, -W / 2 - 0.004], [L / 2 + 0.004, -W / 2 - 0.004], [-L / 2 - 0.004, W / 2 + 0.004], [L / 2 + 0.004, W / 2 + 0.004]]) { const s = screw(0.0011, 0.004); s.position.set(x, 0.0042, z); bezel.add(s); }
  }
  const als = new THREE.Group();
  {
    const win = cyl(0.004, 0.004, 0.0052, new THREE.MeshPhysicalMaterial({ color: 0xe8f0ff, transmission: 0.8, roughness: 0.2, transparent: true, opacity: 0.6 }), 20);
    win.position.set(-L / 2 - 0.004, 0.0016, 0); als.add(win);
    const pipe = cyl(0.0025, 0.0025, 0.012, new THREE.MeshPhysicalMaterial({ color: 0xffffff, transmission: 0.7, roughness: 0.3, transparent: true, opacity: 0.5 }), 12); pipe.position.set(-L / 2 - 0.004, -0.007, 0); als.add(pipe);
  }
  addPart(c, 'glass', 'Cover glass', glass, v3(0, 0.03, 0), '3 mm float glass.');
  addPart(c, 'polariser', 's-pass polariser film', pol, v3(0, -0.015, 0), 'Laminated to the inside of the glass, pass axis across the car.');
  addPart(c, 'bezel', 'Printed bezel', bezel, v3(0, 0.05, 0), 'Clamps the glass into the lid opening.');
  addPart(c, 'als', 'Ambient-light window', als, v3(-0.03, 0.02, 0), 'Light pipe to the controller\'s light sensor.');
  c.assembly = [
    { title: 'Cover glass', parts: ['glass'], text: 'The glass is cut to the traced aperture.' },
    { title: 'Polariser', parts: ['polariser'], text: 'The s-pass polariser is laminated to its inside face, pass axis across the car.' },
    { title: 'Bezel', parts: ['bezel'], text: 'The printed bezel holds it in the lid.' },
    { title: 'Sensor window', parts: ['als'], text: 'A light pipe at the rear edge feeds the ambient-light sensor.' },
  ];
  c.fx = new THREE.Group(); c.fx.name = 'workingFX'; c.group.add(c.fx); c.fx.visible = false;
  const hud = [], sun = [];
  for (let i = 0; i < 4; i++) {
    const x = -L / 3 + i * L / 4.5;
    const up = ray([v3(x, -0.07, -0.05), v3(x + 0.0, 0.07, -0.05)], AMBER);
    c.fx.add(up);
    for (const yy of [-0.04, 0.04]) { const a = polArrow(0.014, AMBER); a.position.set(x, yy, -0.05); a.setAngle(Math.PI / 2); c.fx.add(a); }
    const sIn = ray([v3(x, 0.08, 0.06), v3(x, 0.0, 0.06)], SUNC, { opacity: 0.95 });
    const sOut = ray([v3(x, 0.0, 0.06), v3(x, -0.07, 0.06)], SUNC, { opacity: 0.4 });
    c.fx.add(sIn, sOut);
    const a1 = polArrow(0.014, 0xffffff); a1.position.set(x, 0.045, 0.06); a1.setAngle(0); c.fx.add(a1);
    const a2 = polArrow(0.014, 0xffffff); a2.position.set(x, 0.045, 0.06); a2.setAngle(Math.PI / 2); c.fx.add(a2);
    const a3 = polArrow(0.014 * Math.sqrt(R.POL_T_UNPOL * 2), 0xffffff); a3.position.set(x, -0.04, 0.06); a3.setAngle(Math.PI / 2); a3.userData.mat.opacity = 0.6; c.fx.add(a3);
    hud.push(up); sun.push(sOut);
  }
  const l1 = labelSprite(['HUD light, s-polarised: passes'], 0.006, { accent: '#ffb347' }); l1.position.set(0, -0.09, -0.05); c.fx.add(l1);
  const l2 = labelSprite(['Sunlight, unpolarised', `only ${V.pol_t} passes (ASSUMED)`], 0.006, { accent: '#fff2d0' }); l2.position.set(0, 0.09, 0.06); c.fx.add(l2);
  c.setWorking = (on) => { c.fx.visible = on; };
  c.update = (t, dt, s) => {
    if (!(s && s.working)) return;
    hud.forEach((r, i) => { r.material.opacity = 0.7 + 0.25 * Math.sin(t * 3 + i); });
    sun.forEach((r, i) => { r.material.opacity = 0.25 + 0.1 * Math.sin(t * 2 + i); });
  };
  return c;
}

// ---------------------------------------------------------------------------------------------------------------
// housing pieces (car coordinates)
// ---------------------------------------------------------------------------------------------------------------
function quadMesh(pts, mat) {
  // planar polygon given as world points (convex, in order)
  const pos = [];
  for (let i = 1; i < pts.length - 1; i++) pos.push(...pts[0].toArray(), ...pts[i].toArray(), ...pts[i + 1].toArray());
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.computeVertexNormals();
  const uv = []; for (let i = 0; i < pos.length / 3; i++) uv.push(pos[i * 3] * 20 + pos[i * 3 + 2] * 20, pos[i * 3 + 1] * 20);
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  const m = new THREE.Mesh(g, mat); m.castShadow = true; m.receiveShadow = true;
  return m;
}
// Extrude a side profile (x, y points) across Z from z0 to z1.
function sideProfile(pts, z0, z1, mat) {
  const shape = new THREE.Shape(pts.map(([x, y]) => new THREE.Vector2(x, y)));
  const g = new THREE.ExtrudeGeometry(shape, { depth: z1 - z0, bevelEnabled: false });
  g.translate(0, 0, z0);
  const m = new THREE.Mesh(g, mat); m.castShadow = true; m.receiveShadow = true;
  return m;
}

function housingPieces(lay, mat = M.printBlack, lidMat = null) {
  const { floor, xF, xR, lidY, zW } = lay;
  const T = 0.003;                                                   // wall thickness
  const pieces = {};
  // base: floor plate with a vent grille under the fan, feet with dash pads, PGU pedestal, fan duct, bosses
  const floorG = new THREE.Group(), wallsG = new THREE.Group(), bossesG = new THREE.Group();
  let base = floorG;
  {
    const fx0 = xR, fx1 = xF, fanX = G.PANEL_C.x, fanZ = G.PANEL_C.z;
    const slots = 9, sw = 0.0025;
    // floor in strips around the vent
    const ventX0 = fanX - 0.02, ventX1 = fanX + 0.02, ventZ0 = fanZ - 0.02, ventZ1 = fanZ + 0.02;
    const strip = (x0, x1, z0, z1) => { const m = slab(x1 - x0, T, z1 - z0, mat); m.position.set((x0 + x1) / 2, floor + T / 2, (z0 + z1) / 2); base.add(m); };
    strip(fx0, ventX0, -zW, zW); strip(ventX1, fx1, -zW, zW); strip(ventX0, ventX1, -zW, ventZ0); strip(ventX0, ventX1, ventZ1, zW);
    for (let i = 0; i < slots; i++) { if (i % 2 === 0) continue; const z0 = ventZ0 + i * (ventZ1 - ventZ0) / slots; strip(ventX0, ventX1, z0, z0 + (ventZ1 - ventZ0) / slots); }
    // feet with soft pads
    for (const x of [fx0 + 0.03, fx1 - 0.03]) for (const z of [-zW + 0.03, zW - 0.03]) {
      const foot = cyl(0.012, 0.014, 0.008, mat, 20); foot.position.set(x, floor - 0.004, z); base.add(foot);
      const pad = cyl(0.014, 0.014, 0.003, M.rubber, 20); pad.position.set(x, floor - 0.0095, z); base.add(pad);
    }
    // PGU pedestal: four posts to the heat-sink base, and the duct from the fan to the vent
    const hsBase = G.PANEL_C.y - 0.0020 - 0.0325;
    for (const dx of [-0.021, 0.021]) for (const dz of [-0.037, 0.037]) {
      const h = hsBase - floor - T; const post = slab(0.006, h, 0.006, mat); post.position.set(fanX + dx, floor + T + h / 2, fanZ + dz); base.add(post);
    }
    const fanBot = G.PANEL_C.y - 0.0020 - BACKLIGHT_DEPTH;
    const dh = fanBot - floor - T;
    if (dh > 0.002) for (const [dx, dz, w, d] of [[0, 0.0215, 0.043, 0.002], [0, -0.0215, 0.043, 0.002], [0.0215, 0, 0.002, 0.043], [-0.0215, 0, 0.002, 0.043]]) {
      const duct = slab(w, dh, d, mat); duct.position.set(fanX + dx, floor + T + dh / 2, fanZ + dz); base.add(duct);
    }
    // walls: left, right (side profile), rear, front
    base = wallsG;
    const prof = [[xR, floor], [xF, floor], [xF, lidY(xF)], [xR, lidY(xR)]];
    base.add(sideProfile(prof, -zW, -zW + T, mat));
    base.add(sideProfile(prof, zW - T, zW, mat));
    const rear = slab(T, lidY(xR) - floor, 2 * zW, mat); rear.position.set(xR + T / 2, (lidY(xR) + floor) / 2, 0); base.add(rear);
    const front = slab(T, lidY(xF) - floor, 2 * zW, mat); front.position.set(xF - T / 2, (lidY(xF) + floor) / 2, 0); base.add(front);
    // fold-bracket bosses on the side walls, mirror boss on the floor
    base = bossesG;
    const ff = lay.ff;
    for (const sg of [-1, 1]) {
      const p = G.FOLD_C.clone().addScaledVector(ff.fv, (ff.v0 + ff.v1) / 2 - 0.004).addScaledVector(ff.n, -0.008);
      const boss = slab(0.03, 0.02, 0.006, mat); boss.position.set(p.x, p.y, sg * (zW - T - 0.003)); base.add(boss);
      const rib = slab(0.006, p.y - floor, 0.006, mat); rib.position.set(p.x, (p.y + floor) / 2, sg * (zW - T - 0.003)); base.add(rib);
    }
    for (const sg of [-1, 1]) {
      const mp0 = G.MIRROR_C.clone().addScaledVector(G.MIRROR_U, sg * 0.1).addScaledVector(G.MIRROR_V, -0.06).addScaledVector(G.MIRROR_N, -0.036);
      const boss = slab(0.05, 0.004, 0.034, mat); boss.position.set(mp0.x, floor + T + 0.002, mp0.z); base.add(boss);
    }
    // cable gland at the rear wall
    base = wallsG;
    const gland = cyl(0.008, 0.008, 0.012, M.rubber, 20); gland.rotation.z = Math.PI / 2; gland.position.set(xR - 0.002, floor + 0.03, -zW + 0.05); base.add(gland);
    const tag = textDecal('ARHUD · TFT · PETG-CF', 0.07, { color: '#5b5f66' }); tag.position.set(xF + 0.0002, floor + 0.04, 0); tag.rotation.y = Math.PI / 2; base.add(tag);
  }
  pieces.floor = floorG; pieces.walls = wallsG; pieces.bosses = bossesG;
  pieces.base = new THREE.Group(); pieces.base.add(floorG, wallsG, bossesG);
  // baffles: a stray-light baffle between the panel and the mirror's foot, and wall ribs
  const baffles = new THREE.Group();
  {
    // find the lowest point of the mirror->fold beam above the baffle line
    const bx = (G.PANEL_C.x + PANEL.outX / 2 + G.MIRROR_C.x - 0.08) / 2;
    let lowest = 1e9;
    for (const r of lay.rays) {
      const A = r.pts[2], B = r.pts[3];                               // mirror -> fold
      if ((A.x - bx) * (B.x - bx) > 0) continue;
      const t = (bx - A.x) / (B.x - A.x); lowest = Math.min(lowest, A.y + (B.y - A.y) * t);
    }
    const topY = Math.min(lowest - 0.006, G.PANEL_C.y + 0.01);
    const h = topY - floor - T;
    const b = slab(T, h, 2 * zW - 2 * T, mat); b.position.set(bx, floor + T + h / 2, 0); baffles.add(b);
    const lip = slab(0.012, T, 2 * zW - 2 * T, mat); lip.position.set(bx - 0.006, topY, 0); baffles.add(lip);
    for (const sg of [-1, 1]) for (let i = 0; i < 5; i++) {
      const x = xR + 0.04 + i * (xF - xR - 0.08) / 4; const hh = lidY(x) - floor - 0.01;
      const rib = slab(0.002, hh, 0.006, mat); rib.position.set(x, floor + hh / 2 + 0.004, sg * (zW - T - 0.003)); baffles.add(rib);
    }
    baffles.userData.x = bx; baffles.userData.top = topY;
  }
  pieces.baffles = baffles;
  // lid: the plane over the garage and the rims round the aperture
  const lid = new THREE.Group();
  {
    if (!lidMat) { lidMat = mat.clone(); lidMat.side = THREE.DoubleSide; }
    const { ax0, ax1, az0, az1 } = lay;
    const P = (x, z, dy = 0) => v3(x, lidY(x) + dy, z);
    const panel = (x0, x1, z0, z1) => {
      const top = quadMesh([P(x0, z0, T), P(x1, z0, T), P(x1, z1, T), P(x0, z1, T)].reverse(), lidMat);
      const bot = quadMesh([P(x0, z0), P(x1, z0), P(x1, z1), P(x0, z1)], lidMat);
      lid.add(top, bot);
    };
    panel(xR, ax0, -zW, zW);                                          // over the garage
    panel(ax1, xF, -zW, zW);                                          // front rim
    panel(ax0, ax1, -zW, az0);                                        // side rims
    panel(ax0, ax1, az1, zW);
    // glare-trap lip under the aperture's rear edge
    const lipC = P(ax0 - 0.004, 0, -0.008);
    const lp = slab(0.004, 0.016, az1 - az0, mat); lp.position.copy(lipC); lp.position.z = (az0 + az1) / 2; lid.add(lp);
  }
  pieces.lid = lid;
  return pieces;
}

export function buildHousing(opts = {}) {
  if (CAD) return buildCadHousing(opts);                           // the build123d model, when assets/cad loaded
  const mode = opts.mode || G.MIRROR.mode;
  const lay = housingLayout(mode);
  const pcs = housingPieces(lay);
  const origin = v3((lay.xR + lay.xF) / 2, lay.floor, 0);
  const c = makeComponent(THREE, {
    id: 'housing',
    name: '3D-printed housing (matte black)',
    category: 'housing',
    mount: 'centre of the floor underside; in the car this point sits at the housing origin on the dash top',
    size: [lay.xF - lay.xR, lay.lidY(lay.xR) - lay.floor, 2 * lay.zW],
    desc: 'The whole optical train lives in one printed, matte-black shell on the dash top. Panel and backlight sit at the rear, lowest, venting through the base; the fold sits above them; the concave mirror sits at the front; the dust cover and shutter close the top. It comes off without tools, so the car returns to stock.',
    working: 'Exploded, the housing shows how the base, walls, bosses, baffles and lid fit; matte black inside keeps stray light from showing as haze.',
  });
  c.facts = [
    ['Outside size', `${((lay.xF - lay.xR) * 1000).toFixed(0)} × ${((lay.lidY(lay.xR) - lay.floor) * 1000).toFixed(0)} × ${(2 * lay.zW * 1000).toFixed(0)} mm (L × H × W)`],
    ['Lid slope', `${(Math.atan(lay.s) / DEG).toFixed(1)}° (stays under the glass, over the fold)`],
    ['Aperture (traced)', `${(lay.L * 1000).toFixed(0)} × ${(lay.W * 1000).toFixed(0)} mm`],
    ['Material', 'printed matte black, layer lines inside break up reflections'],
    ['Mounting', 'four feet with soft pads; no tools, nothing bonded to the glass'],
    ['Price', costOf('Housing')],
  ];
  const wrap = (obj) => { const g = new THREE.Group(); g.position.copy(origin).negate(); g.add(obj); return g; };
  addPart(c, 'floor', 'Floor, vent, feet and PGU pedestal', wrap(pcs.floor), v3(0, -0.06, 0), 'The fan vents through the grille under the backlight.');
  addPart(c, 'walls', 'Walls', wrap(pcs.walls), v3(0, 0, 0), 'Side, front and rear walls; a gland at the rear for the cables.');
  addPart(c, 'bosses', 'Fold and mirror bosses', wrap(pcs.bosses), v3(0, 0.03, 0), 'Mounting points for the fold bracket and the mirror cradle.');
  addPart(c, 'baffles', 'Internal baffles', wrap(pcs.baffles), v3(0, 0.06, 0), 'Block stray paths from the panel to the aperture.');
  addPart(c, 'lid', 'Lid', wrap(pcs.lid), v3(0, 0.14, 0), 'Covers the shutter garage; the aperture opening takes the dust cover.');
  c.assembly = [
    { title: 'Floor', parts: ['floor'], text: 'The floor with its vent grille, soft-padded feet and the PGU pedestal.' },
    { title: 'Walls', parts: ['walls'], text: 'Walls follow the lid slope, under the glass.' },
    { title: 'Bosses', parts: ['bosses'], text: 'Bosses for the fold bracket arms and the mirror cradle feet.' },
    { title: 'Baffles', parts: ['baffles'], text: 'A stray-light baffle and wall ribs.' },
    { title: 'Lid', parts: ['lid'], text: 'The lid closes the top round the aperture.' },
  ];
  c.layout = lay;
  c.setWorking = () => {};
  c.update = () => {};
  return c;
}

// ---------------------------------------------------------------------------------------------------------------
// hudUnit: everything in car coordinates
// ---------------------------------------------------------------------------------------------------------------
export function buildHudUnit(opts = {}) {
  let mode = opts.mode || G.MIRROR.mode;
  const lay = housingLayout(mode);
  const shellMat = M.printBlack.clone(); shellMat.transparent = true;
  const shellLid = shellMat.clone(); shellLid.side = THREE.DoubleSide;
  const pcs = housingPieces(lay, shellMat, shellLid);
  // With the CAD model loaded, its printed parts replace the procedural shell and the printed mounts drawn by the
  // optics' own builders; the shutter and the dust cover take the CAD aperture's size (traced for the 300 mm mirror).
  const cad = CAD ? cadUnitGroups(shellMat, shellLid) : null;
  const cs = CAD && CAD.man.shutter, cg = CAD && CAD.man.glass;
  const pgu = buildPgu();
  const fold = buildColdMirror({ mode });
  const mir = buildConcaveMirror({ mode });
  const shut = buildShutter(cad ? { L: cs.L, W: cs.W } : { L: lay.L, W: lay.W });
  const dc = buildDustCover(cad ? { L: cg.L, W: cg.W } : { L: lay.L, W: lay.W });
  const c = makeComponent(THREE, {
    id: 'hudUnit',
    name: 'HUD optical unit, installed',
    category: 'housing',
    mount: 'car-frame origin (group origin = simulation origin); parts sit at the geom.js positions',
    size: [lay.xF - lay.xR, lay.lidY(lay.xR) - lay.floor + 0.01, 2 * lay.zW],
    desc: 'The finished optical unit on the dash: TFT PGU at the rear and lowest, the cold-mirror fold above it, the concave mirror at the front, the shutter and dust cover in the lid. Light leaves the crop, folds forward, is magnified by the concave mirror and leaves through the dust cover to the windshield, which reflects it to the driver.',
    working: 'Rays traced back from the eye box through the window corners land on the panel crop: eye ← windshield ← concave mirror ← fold ← panel. Amber rays are clear; red rays are blocked by a part.',
  });
  // part placement
  pgu.group.position.copy(G.PANEL_C);
  fold.group.position.copy(G.FOLD_C);
  mir.group.position.copy(G.MIRROR_C);
  const lidQ = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(lay.lidDir, lay.lidN, v3(0, 0, 1)));
  const dcPos = cad ? lay.apC.clone().addScaledVector(lay.lidDir, cg.sc).addScaledVector(lay.lidN, cg.n0) : lay.apC.clone().addScaledVector(lay.lidN, 0.0005);
  dc.group.position.copy(dcPos); dc.group.quaternion.copy(lidQ);
  shut.group.position.copy(lay.apC.clone().addScaledVector(lay.lidDir, cad ? cs.sc : 0).addScaledVector(lay.lidN, -0.006)); shut.group.quaternion.copy(lidQ);
  const wrap = (obj) => { const g = new THREE.Group(); g.add(obj); return g; };
  if (cad) {
    // CAD meshes are in car coordinates: hang each set inside its optic's group with the inverse of that group's pose
    const attach = (comp, set, hide = []) => {
      for (const id of hide) { const p = comp.parts.find((q) => q.id === id); if (p) p.object.visible = false; }
      if (!set) return;
      comp.group.updateMatrix();
      set.applyMatrix4(comp.group.matrix.clone().invert());
      comp.group.add(set);
    };
    attach(pgu, cad.pgu, ['bracket', 'fpc']);
    attach(fold, cad.coldMirror, ['bracket']);
    attach(mir, cad.concaveMirror, ['cradle', 'adjusters', 'clips']);
    attach(shut, cad.shutter, ['rails']);
    attach(dc, cad.dustCover, ['bezel', 'als']);
    // the HDMI board stands on edge against the bay's right wall, HDMI receptacle down (the bay is too short for it
    // behind the heat sink, and the cluster hood sits where pgu.js puts it)
    const b = CAD.man.board.c, board = pgu.parts.find((q) => q.id === 'board');
    if (board) {
      board.object.position.set(b[0] - G.PANEL_C.x, b[1] - G.PANEL_C.y, b[2] + 0.0016 - G.PANEL_C.z);
      board.object.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(v3(0, 1, 0), v3(0, 0, -1), v3(-1, 0, 0)));
      const flex = ribbon([[-PANEL.outX / 2 - 0.0032, -0.0008, -0.008], [-PANEL.outX / 2 - 0.0062, -0.006, -0.008], [-PANEL.outX / 2 - 0.0062, -0.05, -0.008],
        [-0.03, -0.068, 0.03], [b[0] + 0.002 - G.PANEL_C.x, b[1] + 0.024 - G.PANEL_C.y, b[2] - 0.0004 - G.PANEL_C.z]], 0.022, v3(0, 0, 1), M.fpc);
      pgu.group.add(flex);
    }
  }
  addPart(c, 'housingBase', 'Housing base and walls', wrap(cad ? cad.housingBase : pcs.base), v3(0, -0.1, 0), cad ? 'Four printed body quarters on levelling feet, the sealed PGU bay and the panel carrier.' : 'Printed base with vent, feet, pedestal, walls and bosses.');
  addPart(c, 'pgu', 'TFT picture generation unit', pgu.group, v3(-0.02, 0.08, -0.42), 'Backlight, cell, retarder, thermistor, HDMI board.');
  addPart(c, 'coldMirror', 'Cold-mirror fold and absorber', fold.group, v3(0, 0.22, -0.3), 'Bracket arms bolt to the wall bosses.');
  addPart(c, 'concaveMirror', 'Concave mirror on its cradle', mir.group, v3(0.26, 0.05, 0.05), 'Cradle feet on the mirror boss.');
  addPart(c, 'baffles', cad ? 'Light-trap vanes' : 'Baffles', wrap(cad ? cad.baffles : pcs.baffles), v3(0, 0.06, 0.4), cad ? 'Saw-tooth vanes on the mirror bay\'s side walls; the stray-light baffle is the body\'s seam wall.' : 'Stray-light baffle between the panel and the mirror foot; ribs on the walls.');
  addPart(c, 'shutter', 'Shutter', shut.group, lay.lidN.clone().multiplyScalar(0.2), 'Under the lid; garage behind the aperture.');
  addPart(c, 'lid', 'Lid', wrap(cad ? cad.lid : pcs.lid), v3(0, 0.28, 0), cad ? 'Four printed lid pieces joined with half laps; spigot tabs drop into the body.' : 'Closes over the shutter garage; the aperture takes the dust cover.');
  addPart(c, 'dustCover', 'Dust cover', dc.group, lay.lidN.clone().multiplyScalar(0.38), 'Glass with the s-pass polariser.');
  c.assembly = [
    { title: 'Housing base', parts: ['housingBase'], text: 'The printed base goes on the dash top on its padded feet; nothing is bonded or screwed to the car.' },
    { title: 'Picture generation unit', parts: ['pgu'], text: 'The PGU drops onto its pedestal at the rear, lowest, fan over the vent; the HDMI and LED leads leave through the rear gland.' },
    { title: 'Cold-mirror fold', parts: ['coldMirror'], text: `The fold goes above the panel at ${(G.FOLD_INC / DEG).toFixed(1)}° incidence, absorber behind it.` },
    { title: 'Concave mirror', parts: ['concaveMirror'], text: `The concave mirror stands at the front, ${(G.U * 1000).toFixed(0)} mm of folded path from the crop.` },
    { title: 'Baffles', parts: ['baffles'], text: 'The stray-light baffle and wall ribs go in.' },
    { title: 'Shutter', parts: ['shutter'], text: 'The shutter rails, leaves, servo and spring mount under the lid line.' },
    { title: 'Lid', parts: ['lid'], text: 'The lid closes over the shutter garage.' },
    { title: 'Dust cover', parts: ['dustCover'], text: 'The dust cover, polariser inside, closes the aperture.' },
  ];
  if (cad) {
    const say = (id, title, text) => { const s = c.assembly.find((a) => a.parts[0] === id); if (s) { s.title = title; s.text = text; } };
    say('housingBase', 'Housing base', 'The printed body stands on the dash on four levelling feet, its rear riding over the cluster hood; nothing is bonded or screwed to the car. The sealed PGU bay and the panel carrier are already in it.');
    say('pgu', 'Picture generation unit', 'The backlight\'s heat sink screws to the bay\'s four posts, fan over the duct; the HDMI board stands on edge against the bay wall; the cell drops into the carrier and the mask clamps it.');
    say('coldMirror', 'Cold-mirror fold', `The fold bracket stands on the carrier at ${(G.FOLD_INC / DEG).toFixed(1)}° incidence, sharing the bay's corner screws; the absorber sits on its tabs behind the glass.`);
    say('concaveMirror', 'Concave mirror', 'The mirror, bonded to its strongback, goes onto the stand\'s three spring-loaded adjusters; two clips catch its bottom edge.');
    say('baffles', 'Light-trap vanes', 'Saw-tooth vanes line the mirror bay\'s side walls; the stray-light baffle is the body\'s seam wall.');
    say('shutter', 'Shutter', 'The leaves run in printed rails under the lid; the servo hangs behind the opening with its lever under the leaves, and the spring pulls them shut.');
    say('lid', 'Lid', 'The four lid pieces, joined with half laps, drop their spigot tabs into the body and screw to its walls.');
    say('dustCover', 'Dust cover', 'The glass, polariser underneath, sits flush in the lid\'s rebate under eight clamps; the light-sensor pod sits behind it.');
  }
  c.layout = lay;
  c.sub = { pgu, coldMirror: fold, concaveMirror: mir, shutter: shut, dustCover: dc };
  // ---- light path ----
  c.fx = new THREE.Group(); c.fx.name = 'workingFX'; c.group.add(c.fx); c.fx.visible = false;
  const rayLines = [];
  const rayDefs = [];
  for (const [fx, fy] of [[0, 0], [-1, 1], [1, 1], [-1, -1], [1, -1]]) rayDefs.push({ e: [0, 0], f: [fx, fy] });
  for (const [ex, ey] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) for (const [fx, fy] of [[0, 0], [-1, 0], [1, 0]]) rayDefs.push({ e: [ex, ey], f: [fx, fy] });
  for (const d of rayDefs) { const l = ray([G.EYE, G.EYE], AMBER, { opacity: d.e[0] === 0 ? 0.95 : 0.55 }); c.fx.add(l); rayLines.push(l); }
  // blocking test against the fold glass, the absorber, the baffle and the mirror's edges
  const blockers = () => {
    const ff = fold.fold;
    const out = [];
    const fc = G.FOLD_C.clone().addScaledVector(ff.fv, (ff.v0 + ff.v1) / 2).addScaledVector(ff.fu, (ff.u0 + ff.u1) / 2);
    out.push({ name: 'fold glass', c: fc, a: ff.fv, b: ff.fu, ha: (ff.v1 - ff.v0) / 2, hb: (ff.u1 - ff.u0) / 2, segs: [1] });
    const av0 = ff.v0 - 0.002, av1 = ff.v1 - 0.022;
    const ac = G.FOLD_C.clone().addScaledVector(ff.fv, (av0 + av1) / 2).addScaledVector(ff.n, -0.012);
    out.push({ name: 'absorber', c: ac, a: ff.fv, b: ff.fu, ha: (av1 - av0) / 2, hb: (ff.u1 - ff.u0) / 2, segs: [1] });
    if (!cad) {
      const bx = pcs.baffles.userData.x, bt = pcs.baffles.userData.top;
      out.push({ name: 'baffle', c: v3(bx, (bt + lay.floor) / 2, 0), a: v3(0, 1, 0), b: v3(0, 0, 1), ha: (bt - lay.floor) / 2, hb: lay.zW, segs: [2, 3] });
    }
    // The panel's own cell glass: with the fold 50 mm over the panel, the mirror -> fold rays for the top of the window
    // seen from the top of the eye box pass through the cell's front edge (found by docs/arhud-cad's ray check).
    const cx0 = G.PANEL_C.x - PANEL.outX / 2 - 0.004, cx1 = G.PANEL_C.x + PANEL.outX / 2;
    out.push({ name: 'panel glass (layout)', c: v3((cx0 + cx1) / 2, G.PANEL_C.y, 0), a: v3(1, 0, 0), b: v3(0, 0, 1), ha: (cx1 - cx0) / 2, hb: PANEL.outZ / 2, segs: [2] });
    return out;
  };
  const analyse = () => {
    const B = blockers();
    const rays = sampleRays(mode, 5);
    const by = {}; let blocked = 0;
    for (const r of rays) {
      let hit = null;
      if (!r.mirror.inside) hit = 'mirror edge (vignetting)';
      for (const b of B) {
        if (hit) break;
        for (const si of b.segs) if (segHitsRect(r.pts[si], r.pts[si + 1], b.c, b.a, b.b, b.ha, b.hb)) { hit = b.name; break; }
      }
      if (!hit) {
        const fA = r.pts[1].y - lay.lidY(r.pts[1].x), fB = r.pts[2].y - lay.lidY(r.pts[2].x);
        if (fA * fB < 0) {
          const Pc = r.pts[1].clone().lerp(r.pts[2], fA / (fA - fB));
          if (cad) {
            const ap = CAD.man.layout.aperture, s = Pc.clone().sub(lay.apC).dot(lay.lidDir);
            if (s < ap.s0 || s > ap.s1 || Pc.z < ap.z0 || Pc.z > ap.z1) hit = 'lid';
          } else if (Pc.x < lay.ax0 || Pc.x > lay.ax1 || Pc.z < lay.az0 || Pc.z > lay.az1) hit = 'lid';
        }
      }
      if (hit) { blocked++; by[hit] = (by[hit] || 0) + 1; }
    }
    // clearances
    const topEdge = mirrorPoint(0, G.MIRROR_H / 2, mode).add(G.MIRROR_C);
    const lidAtFront = lay.lidY(lay.xF) + 0.003;
    return {
      rays: rays.length, blocked, by,
      mirrorTopToGlassMm: (G.glassYAt(topEdge.x) - topEdge.y) * 1000,
      lidFrontToGlassMm: (G.glassYAt(lay.xF) - lidAtFront) * 1000,
      lidRearToGlassMm: (G.glassYAt(lay.xR) - (lay.lidY(lay.xR) + 0.003)) * 1000,
      blockers: B,
    };
  };
  const retrace = () => {
    const B = blockers();
    rayDefs.forEach((d, i) => {
      const e = G.EYE.clone().add(v3(0, d.e[1] * G.EYEBOX_H / 2, d.e[0] * G.EYEBOX_W / 2));
      const r = G.traceFromEye(e, G.fieldDir(d.f[0] * G.FOV_W / 2, d.f[1] * G.FOV_H / 2), mode);
      if (!r) { rayLines[i].visible = false; return; }
      let blocked = !r.mirror.inside;
      for (const b of B) for (const si of b.segs) if (!blocked && segHitsRect(r.pts[si], r.pts[si + 1], b.c, b.a, b.b, b.ha, b.hb)) blocked = true;
      setRay(rayLines[i], r.pts.slice().reverse());
      rayLines[i].material.color.set(blocked ? BLOCKED : AMBER);
    });
  };
  retrace();
  c.stats = analyse();
  // window outline at the panel (where the field corners land) for orientation
  const pc = G.panelCorners(mode);
  const outline = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([pc.tl, pc.tr, pc.br, pc.bl].map((p) => p.clone().add(v3(0, 0.0006, 0)))), new THREE.LineBasicMaterial({ color: 0x5ec8ff, transparent: true, opacity: 0.9 }));
  c.fx.add(outline);
  const lbl = labelSprite(['Light path (traced from the eye box)', 'eye ← windshield ← concave mirror ← fold ← panel', 'blue outline: where the 10.8° × 5.4° window lands on the panel'], 0.012, { accent: '#ffb347' });
  lbl.position.copy(lay.apC.clone().add(v3(0, 0.12, 0))); c.fx.add(lbl);
  let shutterTarget = null;
  c.handles = {
    setPanelTexture: (tex) => pgu.handles.setPanelTexture(tex),
    setBacklight: (x) => pgu.handles.setBacklight(x),
    setShutter: (x) => { shutterTarget = clamp(x, 0, 1); shut.handles.setOpen(shutterTarget); },
    setMirrorMode: (m) => { mode = m; mir.handles.setMode(m); retrace(); c.stats = analyse(); },
    getStats: () => c.stats,
  };
  c.handles.setCutaway = (x) => {                                    // 0 solid .. 1 see-through shell
    const op = 1 - 0.82 * clamp(x, 0, 1);
    for (const m of [shellMat, shellLid]) { m.opacity = op; m.depthWrite = op > 0.99; m.needsUpdate = true; }
  };
  c.setWorking = (on) => {
    c.fx.visible = on;
    c.handles.setCutaway(on ? 1 : 0);
    pgu.setWorking(on);
    if (on && shutterTarget === null) shut.handles.setOpen(1);
  };
  c.update = (t, dt, s) => {
    const w = !!(s && s.working);
    pgu.update(t, dt, { working: w });
    shut.update(t, dt, { working: false });
    if (w) rayLines.forEach((l, i) => { l.material.opacity = (rayDefs[i].e[0] === 0 ? 0.8 : 0.45) + 0.15 * Math.sin(t * 3 + i * 0.4); });
  };
  return c;
}

// ---------------------------------------------------------------------------------------------------------------
// Stage 0 bench rig
// ---------------------------------------------------------------------------------------------------------------
function cameraOnTripod() {
  const g = new THREE.Group();
  const body = rbox(0.13, 0.08, 0.06, 0.008, M.plasticBlack); body.position.set(0, 0.04, 0); g.add(body);
  const lens = cyl(0.03, 0.032, 0.08, M.aluAnodBlack, 28); lens.rotation.z = Math.PI / 2; lens.position.set(-0.1, 0.04, 0); g.add(lens);
  const glassF = cyl(0.026, 0.026, 0.002, M.lens, 28); glassF.rotation.z = Math.PI / 2; glassF.position.set(-0.141, 0.04, 0); g.add(glassF);
  const grip = rbox(0.03, 0.08, 0.06, 0.008, M.rubber); grip.position.set(0.06, 0.035, 0.0); g.add(grip);
  const head = cyl(0.02, 0.025, 0.03, M.aluDark, 16); head.position.y = -0.015; g.add(head);
  for (let i = 0; i < 3; i++) {
    const a = i * Math.PI * 2 / 3;
    const leg = tube([[0, -0.03, 0], [Math.cos(a) * 0.12, -0.18, Math.sin(a) * 0.12]], 0.006, M.aluDark, 4); g.add(leg);
  }
  return g;
}

export function buildStage0Rig() {
  const c = makeComponent(THREE, {
    id: 'stage0Rig',
    name: 'Stage 0 bench rig (weeks 1–3)',
    category: 'stage',
    mount: 'centre of the enclosure base on the bench',
    size: [0.95, 0.45, 0.4],
    desc: 'The first optics are a desk rig for software: the panel lies face-up in a black enclosure under a 70/30 teleprompter beamsplitter at 45°. A camera or the developer\'s eye looks through the glass and sees the panel reflected, floating over whatever is behind. There is no virtual distance and no windshield; it tests the renderer, colours and latency, not the optics.',
    working: 'Light from the panel goes up, 30% reflects off the beamsplitter toward the camera, and appears to come from a virtual copy of the panel behind the glass, about 0.6 m from the camera.',
  });
  c.facts = [
    ['Beamsplitter', '70/30 teleprompter glass at 45°; the first number is usually the transmitted share (verify with the vendor)'],
    ['Virtual image', 'about 0.6 m from the camera (no magnification)'],
    ['Purpose', 'projection maths, colour and alpha, latency instrumentation'],
    ['Luminance through it', `${V.yod_comb} cd/m² from the 1,200-nit monitor (${V.yod_comb_pct} of the sky target)`],
    ['Price', costOf('Teleprompter')],
  ];
  const panelY = 0.065, bsC = v3(0, panelY + 0.12, 0), camPos = v3(0.62, bsC.y - 0.04, 0);
  const base = new THREE.Group();
  { const b = rbox(0.34, 0.06, 0.26, 0.006, M.printBlack); b.position.y = 0.03; base.add(b); const well = slab(0.14, 0.004, 0.09, M.flock); well.position.y = 0.0605; base.add(well); }
  const panel = new THREE.Group();
  {
    const p = slab(0.0735, 0.004, 0.1255, M.lcdGlass); p.position.y = panelY; panel.add(p);
    const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.1218, 0.0685), new THREE.MeshBasicMaterial({ map: hudPlaceholderTexture(), toneMapped: false }));
    scr.rotation.set(-Math.PI / 2, 0, -Math.PI / 2); scr.position.y = panelY + 0.0021; panel.add(scr); panel.userData.scr = scr;
    const brd = slab(0.046, 0.0016, 0.064, M.pcbBlack); brd.position.set(-0.1, 0.061, 0); panel.add(brd);
  }
  const cheeks = new THREE.Group();
  for (const sg of [-1, 1]) {
    const tri = sideProfile([[-0.13, 0.06], [0.13, 0.06], [0.13, 0.316]], 0, 0.006, M.printBlack);
    tri.position.z = sg * 0.155 - 0.003; cheeks.add(tri);
  }
  const bs = new THREE.Group();
  {
    const nrm = v3(1, -1, 0).normalize(), along = v3(1, 1, 0).normalize();
    bs.add(orientedBox(0.36, 0.003, 0.3, along, nrm.clone().negate(), bsC, M.beamsplitter));
    const frame = orientedBox(0.37, 0.006, 0.006, along, nrm.clone().negate(), bsC.clone().add(v3(0, 0, 0.152)), M.aluAnodBlack); bs.add(frame);
    const frame2 = frame.clone(); frame2.position.z = -0.152; bs.add(frame2);
  }
  const hood = new THREE.Group();
  { const h = slab(0.006, 0.32, 0.32, M.flock); h.position.set(-0.19, 0.22, 0); hood.add(h); }
  const cam = new THREE.Group(); const cg = cameraOnTripod(); cg.position.copy(camPos); cam.add(cg);
  addPart(c, 'base', 'Black enclosure base', base, v3(0, -0.08, 0), '');
  addPart(c, 'panel', 'Panel, face up', panel, v3(0, 0.0, 0), 'The 5.5-inch kit (or the monitor) showing the HUD frame.');
  addPart(c, 'cheeks', 'Side cheeks', cheeks, v3(0, 0.0, 0.12), 'Hold the glass at 45°.');
  addPart(c, 'beamsplitter', '70/30 beamsplitter', bs, v3(0, 0.15, 0), 'Teleprompter glass: about 30% reflected toward the viewer.');
  addPart(c, 'hood', 'Black backdrop', hood, v3(-0.1, 0, 0), 'A dark background behind the glass.');
  addPart(c, 'camera', 'Camera at the eye position', cam, v3(0.15, 0, 0), 'Records what the eye would see.');
  c.assembly = [
    { title: 'Enclosure', parts: ['base'], text: 'A black enclosure base on the bench.' },
    { title: 'Panel face-up', parts: ['panel'], text: 'The panel lies face-up in the well.' },
    { title: 'Cheeks', parts: ['cheeks'], text: 'Two cheeks carry the glass.' },
    { title: 'Beamsplitter at 45°', parts: ['beamsplitter'], text: 'The 70/30 glass sits at 45° above the panel.' },
    { title: 'Backdrop', parts: ['hood'], text: 'A black backdrop behind the glass.' },
    { title: 'Camera', parts: ['camera'], text: 'The camera (or the developer) looks through the glass from the far side.' },
  ];
  c.fx = new THREE.Group(); c.fx.name = 'workingFX'; c.group.add(c.fx); c.fx.visible = false;
  const lensP = camPos.clone().add(v3(-0.142, 0.04, 0));
  const nrm = v3(1, -1, 0).normalize();
  const lines = [];
  for (const [x, z] of [[0, 0], [0.025, 0.04], [-0.025, -0.04], [0.02, -0.05]]) {
    const pp = v3(x, panelY + 0.002, z);
    // point on the glass where the reflected ray heads to the lens: mirror the lens across the glass plane
    const lensM = lensP.clone().sub(nrm.clone().multiplyScalar(2 * lensP.clone().sub(bsC).dot(nrm)));
    const dir = lensM.clone().sub(pp).normalize();
    const t = bsC.clone().sub(pp).dot(nrm) / dir.dot(nrm);
    const hit = pp.clone().addScaledVector(dir, t);
    const l1 = ray([pp, hit, lensP], AMBER); c.fx.add(l1);
    const virt = hit.clone().addScaledVector(hit.clone().sub(lensP).normalize(), pp.distanceTo(hit));
    const l2 = ray([hit, virt], AMBER, { dashed: true, opacity: 0.6 }); c.fx.add(l2);
    lines.push(l1);
  }
  const vimg = new THREE.Mesh(new THREE.PlaneGeometry(0.1218, 0.0685), new THREE.MeshBasicMaterial({ map: hudPlaceholderTexture(), transparent: true, opacity: 0.45, toneMapped: false, side: THREE.DoubleSide, depthWrite: false }));
  vimg.rotation.y = Math.PI / 2; vimg.position.set(bsC.x - (bsC.y - panelY), bsC.y, 0); c.fx.add(vimg);
  const l = labelSprite(['Stage 0: virtual image of the panel behind the glass', `≈ ${(lensP.distanceTo(vimg.position)).toFixed(2)} m from the camera; 30% reflected`], 0.018, { accent: '#ffb347' });
  l.position.set(0, 0.42, 0); c.fx.add(l);
  c.setWorking = (on) => { c.fx.visible = on; };
  c.update = (t, dt, s) => { if (s && s.working) lines.forEach((ln, i) => { ln.material.opacity = 0.7 + 0.25 * Math.sin(t * 3 + i); }); };
  return c;
}

// ---------------------------------------------------------------------------------------------------------------
// Stage 1 in-car rig
// ---------------------------------------------------------------------------------------------------------------
function fresnelTexture() {
  return canvasTexture(512, 512, (ctx, W, H) => {
    ctx.clearRect(0, 0, W, H);
    for (let r = 4; r < W * 0.72; r += 5) {
      ctx.strokeStyle = `rgba(255,255,255,${0.12 + 0.18 * ((r / 5) % 2)})`; ctx.lineWidth = 1.4;
      ctx.beginPath(); ctx.arc(W / 2, H / 2, r, 0, Math.PI * 2); ctx.stroke();
    }
  });
}

export function buildStage1Rig() {
  const c = makeComponent(THREE, {
    id: 'stage1Rig',
    name: 'Stage 1 in-car rig: Fresnel magnifier and combiner (weeks 4–8)',
    category: 'stage',
    mount: 'centre of the enclosure base on the dash top; the eye marker is the driver\'s eye',
    size: [1.0, 0.65, 0.42],
    desc: 'Before the custom mirror exists, a 300 mm Fresnel lens makes the virtual image: the panel sits 280 mm below it, inside its 300 mm focal length, like an object under a magnifying glass. A free-standing combiner glass above the dash folds the light to the driver. It tests registration at a 4.2 m image at night and in overcast light.',
    working: 'Rays from the 80 × 40 mm crop pass the Fresnel, fold off the combiner into the eye, and appear to come from a 1.2 × 0.6 m image about 4.2 m ahead.',
  });
  c.facts = [
    ['Lens', `Fresnel, 300 mm square, f = ${R.F1} mm; panel at u = ${R.U1} mm`],
    ['Virtual image', `v = ${V.s1_dist} on the panel side; M = ${V.s1_M}`],
    ['Image', `${V.s1_w} × ${V.s1_h}, ${V.s1_angw}° × ${V.s1_angh}°, ${V.s1_ppd} px/deg on the monitor`],
    ['Combiner', '70/30 teleprompter glass above the dash (30% reflected)'],
    ['Luminance', `${V.yod_comb} cd/m² from the monitor: night and overcast only`],
    ['Price', `Fresnel ${costOf('Fresnel')}`],
  ];
  const Hb = 0.30, lensY = 0.012 + R.U1 / 1000;
  const box0 = new THREE.Group();
  {
    const t = 0.004, w = 0.32, d = 0.36;
    const fl = slab(w, t, d, M.printBlack); fl.position.y = t / 2; box0.add(fl);
    for (const [x, z, ww, dd] of [[0, d / 2, w, t], [0, -d / 2, w, t], [w / 2, 0, t, d], [-w / 2, 0, t, d]]) { const wl = slab(ww, Hb, dd, M.printBlack); wl.position.set(x, Hb / 2, z); box0.add(wl); }
  }
  const mon = new THREE.Group();
  {
    const body = rbox(0.24, 0.009, 0.357, 0.004, M.plasticBlack); body.position.y = 0.0085; mon.add(body);
    const scr = slab(0.228, 0.0005, 0.345, M.screenOff); scr.position.y = 0.0133; mon.add(scr);
    const crop = new THREE.Mesh(new THREE.PlaneGeometry(0.08, 0.04), new THREE.MeshBasicMaterial({ map: hudPlaceholderTexture(), toneMapped: false }));
    crop.rotation.set(-Math.PI / 2, 0, -Math.PI / 2); crop.position.y = 0.0137; mon.add(crop);
    const lab = textDecal('YODOIT 16″ · 80 × 40 mm crop lit', 0.12, { color: '#777' }); lab.rotation.set(-Math.PI / 2, 0, -Math.PI / 2); lab.position.set(0.1, 0.0136, 0); lab.scale.setScalar(0.6); mon.add(lab);
  }
  const lens = new THREE.Group();
  {
    const plate = slab(0.3, 0.002, 0.3, M.fresnel); plate.position.y = lensY; lens.add(plate);
    const grooves = new THREE.Mesh(new THREE.PlaneGeometry(0.3, 0.3), new THREE.MeshBasicMaterial({ map: fresnelTexture(), transparent: true, depthWrite: false, toneMapped: false }));
    grooves.rotation.x = -Math.PI / 2; grooves.position.y = lensY + 0.0012; lens.add(grooves);
    const frame = new THREE.Group();
    for (const [x, z, w, d] of [[0, 0.152, 0.31, 0.006], [0, -0.152, 0.31, 0.006], [0.152, 0, 0.006, 0.31], [-0.152, 0, 0.006, 0.31]]) { const f = slab(w, 0.006, d, M.printBlack); f.position.set(x, lensY + 0.002, z); frame.add(f); }
    lens.add(frame);
  }
  // combiner: folds upward light back to the eye, 10 degrees up
  const cC = v3(0.0, lensY + 0.13, 0);
  const eye = cC.clone().add(v3(-0.62, 0.07, 0));                  // looks about 6 degrees down at the combiner
  const toEye = eye.clone().sub(cC).normalize();
  const cN = toEye.clone().sub(v3(0, 1, 0)).normalize();          // reflects +Y into toEye
  const cAlong = new THREE.Vector3().crossVectors(v3(0, 0, 1), cN).normalize();
  const comb = new THREE.Group();
  {
    comb.add(orientedBox(0.26, 0.003, 0.32, cAlong, cN.clone().negate(), cC, M.beamsplitter));
    for (const sg of [-1, 1]) {
      const p = cC.clone().addScaledVector(cAlong, cAlong.y < 0 ? 0.13 : -0.13).add(v3(0, 0, sg * 0.165));
      const post = cyl(0.004, 0.004, p.y - Hb, M.aluDark, 10); post.position.set(p.x, (p.y + Hb) / 2, p.z); comb.add(post);
      const clamp1 = rbox(0.016, 0.012, 0.01, 0.002, M.printBlack); clamp1.position.copy(p); comb.add(clamp1);
    }
  }
  const eyeM = new THREE.Group();
  { const e = sphere(0.012, M.color(0xf2f2f2, 0.3), 16); e.position.copy(eye); eyeM.add(e); const iris = sphere(0.006, M.color(0x335577, 0.2), 12); iris.position.copy(eye).addScaledVector(toEye, -0.009); eyeM.add(iris); }
  addPart(c, 'enclosure', 'Dash enclosure', box0, v3(0, -0.12, 0), 'Black box on the dash top; 280 mm deep.');
  addPart(c, 'monitor', 'Monitor face up (PGU)', mon, v3(0, -0.06, 0), 'YODOIT 16-inch 1,200 nit; only an 80 × 40 mm crop lit.');
  addPart(c, 'fresnel', 'Fresnel lens f = 300 mm', lens, v3(0, 0.1, 0), '300 mm square; the panel is 280 mm below, inside f.');
  addPart(c, 'combiner', 'Free-standing combiner', comb, v3(0, 0.22, 0), '70/30 glass above the dash.');
  addPart(c, 'eye', 'Driver\'s eye (reference)', eyeM, v3(-0.15, 0, 0), '');
  c.assembly = [
    { title: 'Enclosure on the dash', parts: ['enclosure'], text: 'A 280 mm deep black box sits on the dash top.' },
    { title: 'Monitor face up', parts: ['monitor'], text: 'The monitor lies face-up at the bottom; an 80 × 40 mm crop is drawn.' },
    { title: 'Fresnel lens', parts: ['fresnel'], text: 'The 300 mm Fresnel closes the top, grooves down, 280 mm above the panel.' },
    { title: 'Combiner', parts: ['combiner'], text: 'The combiner glass stands above the lens, tilted to reach the eye.' },
    { title: 'Eye point', parts: ['eye'], text: 'The design eye point the image is aimed at.' },
  ];
  // rays via the unfolded eye: E' = eye mirrored in the combiner; image point I = (M x, lens - 4.2 m)
  c.fx = new THREE.Group(); c.fx.name = 'workingFX'; c.group.add(c.fx); c.fx.visible = false;
  const Ep = eye.clone().sub(cN.clone().multiplyScalar(2 * eye.clone().sub(cC).dot(cN)));
  const vDist = Math.abs(R.V1_mm) / 1000;
  const lines = [];
  for (const [ox, oz] of [[0, 0], [0.02, 0.04], [-0.02, -0.04], [-0.02, 0.04], [0.02, -0.04]]) {
    for (const eoff of [-0.03, 0, 0.03]) {
      const Epo = Ep.clone().add(v3(0, 0, eoff));
      const O = v3(ox, 0.0137, oz);
      const I = v3(ox * R.M1, lensY - vDist, oz * R.M1);
      const t = (lensY - Epo.y) / (I.y - Epo.y);
      const Hh = Epo.clone().lerp(I, t);
      const d = Epo.clone().sub(Hh).normalize();
      const tc = cC.clone().sub(Hh).dot(cN) / d.dot(cN);
      const Cc = Hh.clone().addScaledVector(d, tc);
      const eyeO = eye.clone().add(v3(0, 0, eoff));
      const l1 = ray([O, Hh, Cc, eyeO], AMBER, { opacity: eoff === 0 ? 0.9 : 0.45 }); c.fx.add(l1); lines.push(l1);
      if (eoff === 0) { const back = ray([Cc, Cc.clone().addScaledVector(Cc.clone().sub(eyeO).normalize(), 0.45)], AMBER, { dashed: true, opacity: 0.55 }); c.fx.add(back); }
    }
  }
  const l = labelSprite(['Stage 1: virtual image ahead of the combiner', `${V.s1_dist} away, ${V.s1_w} × ${V.s1_h}, ${V.s1_angw}° × ${V.s1_angh}°`, `M = ${V.s1_M}; dashed lines continue toward it`], 0.02, { accent: '#ffb347' });
  l.position.copy(cC.clone().add(v3(0.25, 0.12, 0))); c.fx.add(l);
  c.setWorking = (on) => { c.fx.visible = on; };
  c.update = (t, dt, s) => { if (s && s.working) lines.forEach((ln, i) => { ln.material.opacity = (i % 3 === 1 ? 0.8 : 0.4) + 0.15 * Math.sin(t * 3 + i * 0.3); }); };
  return c;
}
