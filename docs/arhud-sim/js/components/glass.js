// A section of the car's own laminated windshield, the HUD's last reflector: the two reflections (main image and
// ghost), Fresnel s and p reflectance at the design incidence, and the wedge-PVB option. Thickness drawn 10x.
import * as THREE from 'three';
import { R } from '../params.js';
import { M, C } from '../mats.js';
import { box, polyline, textDecal, DEG, clamp } from '../util.js';
import { makeComponent, addPart } from './contract.js';

const SCALE_T = 10;                 // thickness exaggeration for legibility

export function buildWindshieldSection() {
  const c = makeComponent(THREE, {
    id: 'windshield', name: 'Windshield: reflection and ghost', category: 'optics',
    mount: 'centre of the inner (cabin-side) surface; local +Y is the inward normal',
    size: [0.24, 0.06, 0.14],
  });
  const ply = 2.1 / 1000 * SCALE_T, pvb = 0.76 / 1000 * SCALE_T, T = ply * 2 + pvb;
  const Wd = 0.24, D = 0.14;
  const glassMat = new THREE.MeshPhysicalMaterial({ color: 0xcfe7e0, roughness: 0.02, transmission: 0.9, thickness: 0.01, transparent: true, opacity: 0.38, side: THREE.DoubleSide, depthWrite: false });
  const pvbMat = new THREE.MeshPhysicalMaterial({ color: 0x9fc9d6, roughness: 0.3, transparent: true, opacity: 0.45, side: THREE.DoubleSide, depthWrite: false });
  const inner = box(Wd, ply, D, glassMat); inner.position.y = -ply / 2;
  const mid = box(Wd, pvb, D, pvbMat); mid.position.y = -ply - pvb / 2;
  const outer = box(Wd, ply, D, glassMat); outer.position.y = -ply - pvb - ply / 2;
  addPart(c, 'innerPly', 'Inner glass ply, 2.1 mm (ASSUMED)', inner, new THREE.Vector3(0, 0.05, 0), 'Cabin side. Reflects the main image.');
  addPart(c, 'pvb', 'PVB interlayer, 0.76 mm (ASSUMED)', mid, new THREE.Vector3(0, 0, 0), 'Plain (parallel) interlayer on a stock windshield; a wedge-PVB layer tilts the outer surface to merge the ghost.');
  addPart(c, 'outerPly', 'Outer glass ply, 2.1 mm (ASSUMED)', outer, new THREE.Vector3(0, -0.05, 0), 'Outside. Its reflection is the ghost, offset 3.1 mm.');
  const lab = textDecal(`laminate ${R.T_GLASS.toFixed(2)} mm drawn ×${SCALE_T} thick`, 0.11, { color: '#9fb3c2', font: '500 40px "Helvetica Neue", Helvetica, Arial, sans-serif' });
  lab.position.set(-Wd / 2 + 0.06, -T - 0.012, D / 2 + 0.001);
  const labelHolder = new THREE.Group(); labelHolder.add(lab);
  addPart(c, 'note', 'Scale note', labelHolder, new THREE.Vector3(0, -0.03, 0), '');
  c.assembly = [
    { title: 'Inner ply', parts: ['innerPly'], text: 'The windshield as the factory laminates it. The HUD uses the stock glass; nothing is bonded to it.' },
    { title: 'Interlayer', parts: ['pvb'], text: 'A plain PVB interlayer keeps the two glass surfaces parallel, so the two reflections leave parallel and offset.' },
    { title: 'Outer ply', parts: ['outerPly', 'note'], text: 'The outer surface reflects a second, weaker copy: the ghost.' },
  ];

  // ---- rays (working visuals) ----
  const rays = new THREE.Group(); rays.visible = false; c.group.add(rays);
  const thI = R.THETA_I * DEG, thT = R.THETA_T * DEG;
  const hitX = -0.03;
  const L = 0.1;
  const inDir = new THREE.Vector3(Math.sin(thI), -Math.cos(thI), 0);
  const refDir = new THREE.Vector3(Math.sin(thI), Math.cos(thI), 0);
  const p0 = new THREE.Vector3(hitX, 0, 0);
  const start = p0.clone().addScaledVector(inDir, -L);
  const p1 = p0.clone().add(new THREE.Vector3(T * Math.tan(thT), -T, 0));             // outer surface hit
  const p2 = p1.clone().add(new THREE.Vector3(T * Math.tan(thT), T, 0));              // exits the inner surface
  const mk = (pts, col, op = 1, dashed = false) => { const l = polyline(pts, col, { opacity: op, dashed, dash: 0.006, gap: 0.004 }); rays.add(l); return l; };
  mk([start, p0], C.ray);
  const mainRay = mk([p0, p0.clone().addScaledVector(refDir, L)], C.ray);
  mk([p0, p1, p2], 0xffd8a0, 0.7);
  const ghostRay = mk([p2, p2.clone().addScaledVector(refDir, L)], 0xffd8a0, 0.6);
  // transmitted ray to the sky (the sun's way in, reversed)
  mk([p1, p1.clone().addScaledVector(inDir, 0.06)], 0x9fb3c2, 0.6, true);
  // offset dimension
  const perp = new THREE.Vector3(-Math.cos(thI), Math.sin(thI), 0);
  const a = p0.clone().addScaledVector(refDir, 0.07), b = a.clone().addScaledVector(perp, -(2 * T * Math.tan(thT) * Math.cos(thI)));
  mk([a, b], 0xffffff, 0.8);
  const offTxt = textDecal(`offset ${R.GHOST_PERP.toFixed(1)} mm (×${SCALE_T})  →  ${R.GHOST_75.toFixed(1)}′ at 7.5 m`, 0.12, { color: '#ffe2b0', font: '600 40px "Helvetica Neue", Helvetica, Arial, sans-serif' });
  offTxt.position.copy(a).add(new THREE.Vector3(0.05, 0.012, 0)); rays.add(offTxt);
  const t1 = textDecal(`main image: s reflects ${(R.RS65 * 100).toFixed(1)}%, p ${(R.RP65 * 100).toFixed(1)}%`, 0.12, { color: '#ffd28a', font: '600 40px "Helvetica Neue", Helvetica, Arial, sans-serif' });
  t1.position.set(0.05, 0.09, 0); rays.add(t1);
  const t2 = textDecal(`ghost: ${((1 - R.RS65) ** 2 * 100).toFixed(0)}% as bright, parallel`, 0.1, { color: '#ffe2b0', font: '500 40px "Helvetica Neue", Helvetica, Arial, sans-serif' });
  t2.position.set(0.07, 0.072, 0); rays.add(t2);
  const t3 = textDecal(`incidence ${R.THETA_I}°, Brewster ${(Math.atan(R.N_GLASS) / DEG).toFixed(1)}°`, 0.1, { color: '#9fb3c2', font: '500 40px "Helvetica Neue", Helvetica, Arial, sans-serif' });
  t3.position.set(-0.07, 0.05, 0); rays.add(t3);
  // polarisation arrows on the incoming ray
  const arrows = new THREE.Group(); rays.add(arrows);
  const arrowMat = M.emissive(0x8fd3ff, 1.4);
  const sArrow = new THREE.Mesh(new THREE.CylinderGeometry(0.0012, 0.0012, 0.03, 8), arrowMat); sArrow.rotation.x = Math.PI / 2; // along Z: s
  const pArrow = new THREE.Mesh(new THREE.CylinderGeometry(0.0012, 0.0012, 0.03, 8), M.emissive(0xffb0d0, 1.2));
  arrows.add(sArrow, pArrow);
  // photons
  const photon = new THREE.Mesh(new THREE.SphereGeometry(0.0025, 12, 8), M.emissive(0xfff0c0, 3));
  const photon2 = photon.clone();
  rays.add(photon, photon2);
  // wedge option: tilt the outer ply so the ghost leaves parallel to... converging on the eye
  let wedge = false;
  const pathA = [start, p0, p0.clone().addScaledVector(refDir, L)];
  const pathB = [start, p0, p1, p2, p2.clone().addScaledVector(refDir, L)];
  const along = (path, f) => {
    const seg = []; let tot = 0; for (let i = 1; i < path.length; i++) { const l = path[i].distanceTo(path[i - 1]); seg.push(l); tot += l; }
    let d = f * tot; for (let i = 1; i < path.length; i++) { if (d <= seg[i - 1]) return path[i - 1].clone().lerp(path[i], d / seg[i - 1]); d -= seg[i - 1]; }
    return path[path.length - 1].clone();
  };
  c.desc = 'The car\'s stock laminated windshield is the HUD\'s final reflector. Its inner surface reflects about a quarter of the s-polarised image toward the eye; the outer surface reflects a second, parallel copy offset by 3.1 mm. At a 7.5 m image that is 1.4 arcminutes, about two pixels, so the plan keeps the stock glass and draws thick lines and area fills.';
  c.working = 'An s-polarised ray from the mirror splits into the main reflection and the ghost; the offset and each share are labelled from calc.py.';
  c.facts = [
    ['s reflectance at 65°', `${(R.RS65 * 100).toFixed(1)}%`],
    ['p reflectance at 65°', `${(R.RP65 * 100).toFixed(1)}% (ratio ${(R.RS65 / R.RP65).toFixed(0)})`],
    ['Brewster angle', `${(Math.atan(R.N_GLASS) / DEG).toFixed(1)}°`],
    ['Laminate', `${R.T_GLASS.toFixed(2)} mm = 2.1 + 0.76 + 2.1 (ASSUMED)`],
    ['Ghost offset', `${R.GHOST_PERP.toFixed(1)} mm → ${R.GHOST_75.toFixed(1)}′ at 7.5 m`],
    ['Ghost brightness', `${((1 - R.RS65) ** 2 * 100).toFixed(0)}% of the main image`],
    ['Both surfaces counted', `${(R.RS65_TWO * 100).toFixed(0)}%`],
    ['Wedge-PVB windshield', '$600–1,500, only if the Stage 2 photo needs it'],
  ];
  c.controls = [{ id: 'wedge', type: 'toggle', label: 'Wedge-PVB interlayer', value: false, onChange: (v) => { wedge = v; } }];
  c.setWorking = (on) => { rays.visible = on; };
  c.update = (t, dt, s) => {
    if (!rays.visible) return;
    const ang = (t * 0.6) % (Math.PI * 2);
    const sAmp = Math.abs(Math.cos(ang)), pAmp = Math.abs(Math.sin(ang));
    const pos = along([start, p0], 0.5);
    arrows.position.copy(pos);
    sArrow.scale.set(1, Math.max(0.05, sAmp), 1);
    pArrow.scale.set(1, Math.max(0.05, pAmp), 1);
    pArrow.rotation.z = -thI;           // in the plane of incidence, perpendicular to the ray
    const f = (t * 0.35) % 1;
    photon.position.copy(along(pathA, f));
    photon2.position.copy(along(pathB, f));
    // wedge tilts the ghost back onto the main ray's direction toward one eye point
    ghostRay.rotation.z = 0;
    if (wedge) {
      const pivot = p2;
      ghostRay.position.copy(pivot); ghostRay.rotation.z = 0;
      const g = ghostRay.geometry; const arr = g.attributes.position.array;
      const tilt = Math.atan2(2 * T * Math.tan(thT) * Math.cos(thI), 0.085);
      const dir = refDir.clone().applyAxisAngle(new THREE.Vector3(0, 0, 1), tilt);
      arr[0] = 0; arr[1] = 0; arr[2] = 0; arr[3] = dir.x * L; arr[4] = dir.y * L; arr[5] = 0; g.attributes.position.needsUpdate = true;
      outer.rotation.z = -0.02;
    } else {
      ghostRay.position.set(0, 0, 0);
      const g = ghostRay.geometry; const arr = g.attributes.position.array;
      arr[0] = p2.x; arr[1] = p2.y; arr[2] = 0; arr[3] = p2.x + refDir.x * L; arr[4] = p2.y + refDir.y * L; arr[5] = 0; g.attributes.position.needsUpdate = true;
      outer.rotation.z = 0;
    }
  };
  return c;
}
