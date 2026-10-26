// The printed housing as modelled in build123d (docs/arhud-cad): every printed piece, fastener and bought part,
// loaded from assets/cad/housing.glb (car frame, metres, one node per part) and assets/cad/housing.json (names, build
// steps, explode offsets, print orientation, check results). Regenerate both with docs/arhud-cad/make.py.
//
// Optional by design: without the files, or under Node (docs/arhud-blender imports optics.js), CAD stays null and
// optics.js keeps its procedural housing.
import * as THREE from 'three';
import { M } from '../mats.js';
import * as G from '../geom.js';
import { makeComponent, addPart } from './contract.js';

export let CAD = null;

async function loadCad() {
  const base = new URL('../../assets/cad/', import.meta.url).href;
  const timeout = (p, ms, what) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error(what + ' timed out')), ms))]);
  const r = await timeout(fetch(base + 'housing.json', { cache: 'no-cache' }), 8000, 'housing.json');
  if (!r.ok) throw new Error('housing.json ' + r.status);
  const man = await r.json();
  const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
  const loader = new GLTFLoader();
  // The artifact host serves text but not .glb, so the model also travels as base64 in housing.glb.txt; read that
  // first and fall back to the binary file.
  let gltf;
  const t = await timeout(fetch(base + 'housing.glb.txt', { cache: 'no-cache' }), 15000, 'housing.glb.txt').catch(() => null);
  if (t && t.ok) {
    const bin = atob((await t.text()).trim());
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    gltf = await new Promise((resolve, reject) => loader.parse(bytes.buffer, '', resolve, reject));
  } else {
    gltf = await timeout(loader.loadAsync(base + 'housing.glb'), 30000, 'housing.glb');
  }
  const geo = {};
  gltf.scene.updateMatrixWorld(true);
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    const g = o.geometry.clone();
    g.applyMatrix4(o.matrixWorld);
    g.computeBoundingBox(); g.computeBoundingSphere();
    geo[o.name] = g;
  });
  const parts = Object.fromEntries(man.parts.map((p) => [p.id, p]));
  return { man, geo, parts };
}

if (typeof window !== 'undefined' && typeof fetch === 'function') {
  try { CAD = await loadCad(); } catch (e) { console.warn('CAD housing not loaded, using the procedural one:', e.message); CAD = null; }
}

// ---- materials ------------------------------------------------------------------------------------------------
const MAT = {
  asa: () => M.printBlack, tpu: () => M.rubber, rubber: () => M.rubber, brass: () => M.gold, steel: () => M.steel,
  alu: () => M.aluAnodBlack, glass: () => M.glass, rtv: () => M.plasticWhite,
};
export function cadMaterial(key) { return (MAT[key] || MAT.asa)(); }

export function cadMesh(id, mat) {
  const g = CAD && CAD.geo[id];
  if (!g) return null;
  const m = new THREE.Mesh(g, mat || cadMaterial(CAD.parts[id].material));
  m.name = 'cad:' + id;
  m.castShadow = true; m.receiveShadow = true;
  return m;
}

const isShell = (id) => /^(body|cap)/.test(id);
const V3 = (a) => new THREE.Vector3(a[0], a[1], a[2]);

// ---- in the installed unit: CAD meshes grouped by the HUD unit's assembly parts --------------------------------
// Returns { housingBase, lid, baffles, pgu, coldMirror, concaveMirror, shutter, dustCover } of THREE.Groups in car
// coordinates. Shell pieces take the unit's see-through materials so the cutaway works.
export function cadUnitGroups(shellMat, shellLid) {
  const out = {};
  for (const p of CAD.man.parts) {
    if (!p.unit) continue;
    const mat = p.material === 'asa' && isShell(p.id) ? (p.id.startsWith('cap') ? shellLid : shellMat) : null;
    const m = cadMesh(p.id, mat);
    if (!m) continue;
    m.userData.cadPart = p.id;
    (out[p.hud] = out[p.hud] || new THREE.Group()).add(m);
  }
  return out;
}

// ---- traced rays through the housing (working visual) ---------------------------------------------------------
const CELL = (() => {                                       // the panel's cell glass (pgu.js PANEL) as an AABB
  const x0 = G.PANEL_C.x - 0.03675 - 0.004, x1 = G.PANEL_C.x + 0.03675;
  return new THREE.Box3(new THREE.Vector3(x0, G.PANEL_C.y - 0.0015, -0.06275), new THREE.Vector3(x1, G.PANEL_C.y, 0.06275));
})();
function segHitsBox(a, b, box) {
  const d = b.clone().sub(a);
  let t0 = 0, t1 = 1;
  for (const k of ['x', 'y', 'z']) {
    if (Math.abs(d[k]) < 1e-12) { if (a[k] < box.min[k] || a[k] > box.max[k]) return false; continue; }
    let ta = (box.min[k] - a[k]) / d[k], tb = (box.max[k] - a[k]) / d[k];
    if (ta > tb) [ta, tb] = [tb, ta];
    t0 = Math.max(t0, ta); t1 = Math.min(t1, tb);
    if (t0 > t1) return false;
  }
  return true;
}
export function tracedRays(origin) {
  const g = new THREE.Group(); g.name = 'cadRays';
  const lin = [-1, 0, 1];
  let clipped = 0, n = 0;
  for (const ex of lin) for (const ey of lin) for (const fx of lin) for (const fy of [-1, 0, 1]) {
    const e = G.EYE.clone().add(new THREE.Vector3(0, ey * G.EYEBOX_H / 2, ex * G.EYEBOX_W / 2));
    const r = G.traceFromEye(e, G.fieldDir(fx * G.FOV_W / 2, fy * G.FOV_H / 2));
    if (!r || !r.mirror.inside) continue;
    n++;
    const bad = segHitsBox(r.pts[2], r.pts[3], CELL);
    if (bad) clipped++;
    const pts = r.pts.slice(1).map((p) => p.clone().sub(origin));
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({
      color: bad ? 0xff4040 : 0xffb347, transparent: true, opacity: bad ? 0.95 : 0.75, toneMapped: false, depthWrite: false }));
    line.renderOrder = 15;
    g.add(line);
  }
  g.userData = { n, clipped };
  return g;
}

// ---- the housing component (Components mode, Build mode) ------------------------------------------------------
export function buildCadHousing() {
  const man = CAD.man, S = man.summary, ck = man.checks || {};
  const floorBot = man.layout.floorBot;
  const xs = man.parts.filter((p) => p.id.startsWith('body')).map((p) => CAD.geo[p.id].boundingBox);
  const xMin = Math.min(...xs.map((b) => b.min.x)), xMax = Math.max(...xs.map((b) => b.max.x));
  const origin = new THREE.Vector3((xMin + xMax) / 2, floorBot, 0);
  const printed = man.parts.filter((p) => p.kind === 'printed');
  const c = makeComponent(THREE, {
    id: 'housing',
    name: `3D-printed housing (CAD, ${S.printedPieces} printed pieces)`,
    category: 'housing',
    mount: 'centre of the floor underside; in the car this point stands on the dash on four levelling feet',
    size: [S.sizeMm[0] / 1000, S.sizeMm[1] / 1000, S.sizeMm[2] / 1000],
    desc: `The real housing, modelled in build123d from the simulator's own layout: ${S.printedParts} different printed parts in ${man.material}, each small enough for a ${man.bed[0]} mm printer, joined with brass heat-set inserts and M3 screws. A sealed, ventilated bay holds the backlight and HDMI board; the cold mirror and the concave mirror sit on printed mounts; the shutter runs in rails under a lid made in four pieces. The rear rides over the cluster hood.`,
    working: `Rays traced from the eye box run through the see-through housing: amber rays clear every part. Red rays are the ones the panel's own glass clips near its front edge, a layout finding (see the numbers).`,
  });
  const beam = ck.beam || {}, env = ck.envelope || {};
  const hwTypes = Object.entries(man.hardware || {}).sort((a, b) => b[1] - a[1]);
  const near = Object.values(beam.nearest || {});
  const nearMm = near.length ? Math.min(...near).toFixed(1) : '?';
  const kg = (S.printedMassG / 1000).toFixed(1);
  const vol = printed.reduce((a, p) => a + p.volumeCm3 * (p.qty || 1), 0);
  c.facts = [
    ['Outside size', `${S.sizeMm[0]} × ${S.sizeMm[1]} × ${S.sizeMm[2]} mm (L × H × W)`],
    ['Printed', `${S.printedPieces} pieces, ${S.printedParts} different; every one fits ${man.bed.join(' × ')} mm in the orientation of its STL`],
    ['Plastic', `${(vol / 1000).toFixed(1)} L of ASA as modelled (${kg} kg solid); very roughly ${Math.round(vol / 30)}–${Math.round(vol / 15)} printer-hours`],
    ['Fasteners', `${S.fasteners}: ${hwTypes.slice(0, 4).map(([k, n]) => `${n} ${k}`).join(', ')}${hwTypes.length > 4 ? ', and the rest in docs/arhud-cad/out/BOM.md' : ''}`],
    ['Light path', `${beam.blocked ?? '?'} of ${beam.rays ?? '?'} traced rays touch a part (both mirror figures); the nearest part is ${nearMm} mm from the beam`],
    ['Panel glass', `${beam.panel ?? '?'} of ${beam.rays ?? '?'} rays clipped by the cell's front edge: the fold sits 50 mm over the panel; 65–70 mm clears it`],
    ['Clearances', `windshield ${env.glassClearMm ?? '?'} mm, cluster hood ${env.hoodClearMm ?? '?'} mm`],
    ['Lid opening', `${Math.round((man.layout.aperture.s1 - man.layout.aperture.s0) * 1000)} × ${Math.round((man.layout.aperture.z1 - man.layout.aperture.z0) * 1000)} mm, from the rays that land on the 300 mm mirror`],
    ['Joints', 'body: flange strips with M3 inserts; lid: half laps; lid to body: spigot tabs'],
  ];
  // parts: one per CAD part, in a wrapper so the explode and assembly can move it; inner group carries the bed view
  const holders = [];
  const asaMat = M.printBlack.clone(); asaMat.transparent = true;
  for (const p of man.parts) {
    const mat = p.material === 'asa' && isShell(p.id) ? asaMat : null;    // see-through shell, solid internals
    const mesh = cadMesh(p.id, mat);
    if (!mesh) continue;
    const wrap = new THREE.Group();
    const inner = new THREE.Group(); inner.position.copy(origin).negate();
    inner.add(mesh); wrap.add(inner);
    const info = [p.desc, p.spec].filter(Boolean).join(' ');
    const pr = p.print ? ` Prints ${p.print.bedMm[0]} × ${p.print.bedMm[1]} × ${p.print.bedMm[2]} mm${p.print.supports !== 'none' ? ', ' + p.print.supports : ', no supports'}; ${p.massG} g solid.` : '';
    addPart(c, p.id, p.name, wrap, V3(p.explode), (info + pr).trim());
    holders.push({ p, wrap, inner });
  }
  c.assembly = man.steps.filter((s) => s.parts.length).map((s) => ({ title: s.title, parts: s.parts.filter((id) => c.parts.some((q) => q.id === id)), text: s.text }));
  // working visual: traced rays
  c.fx = new THREE.Group(); c.fx.name = 'workingFX'; c.group.add(c.fx); c.fx.visible = false;
  const rays = tracedRays(origin); c.fx.add(rays);
  // print-bed view: every printed part on its own 250 mm plate, laid out in a grid beside the housing
  const beds = new THREE.Group(); beds.name = 'beds'; beds.visible = false; c.group.add(beds);
  const bedMat = new THREE.MeshStandardMaterial({ color: 0x6b7480, roughness: 0.55, metalness: 0.35 });
  const bedSize = man.bed[0] / 1000, pitch = bedSize + 0.04, cols = 8;
  const C = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1);   // printer (Z up) -> sim (Y up)
  const bedPose = new Map();
  printed.forEach((p, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    const o = new THREE.Vector3((col - (cols - 1) / 2) * pitch, -0.004, 0.32 + row * pitch);
    const plate = new THREE.Mesh(new THREE.BoxGeometry(bedSize, 0.004, bedSize), bedMat);
    plate.position.copy(o).add(new THREE.Vector3(bedSize / 2, -0.002, -bedSize / 2)); plate.receiveShadow = true; beds.add(plate);
    if (!p.print) return;
    const q = new THREE.Quaternion(...p.print.quat);
    const R = new THREE.Matrix4().makeRotationFromQuaternion(q);
    const T = new THREE.Matrix4().makeTranslation(...p.print.offsetM);
    const B = new THREE.Matrix4().makeTranslation(o.x, o.y, o.z);
    bedPose.set(p.id, B.multiply(C).multiply(T).multiply(R));          // car point -> bed point (sim frame)
  });
  let view = 'assembled';
  const setView = (v) => {
    view = v;
    beds.visible = v === 'beds';
    for (const { p, wrap, inner } of holders) {
      // a set of identical pieces (the eight glass clamps) shows one piece on its bed
      const one = CAD.geo[p.id + 'One'];
      if (one) inner.children[0].geometry = v === 'beds' ? one : CAD.geo[p.id];
      if (v === 'beds') {
        const M4 = bedPose.get(p.id);
        wrap.visible = !!M4;
        if (M4) { inner.matrix.copy(M4); inner.matrixAutoUpdate = false; inner.matrixWorldNeedsUpdate = true; }
      } else {
        wrap.visible = true;
        inner.matrixAutoUpdate = true; inner.position.copy(origin).negate(); inner.quaternion.identity();
      }
    }
    // Move each part's label anchor with it, then ask the Components mode (when it is showing this component) to
    // redraw the labels and frame the new layout.
    for (const { p, wrap, inner } of holders) {
      if (v === 'beds') wrap.position.set(0, 0, 0);
      wrap.updateMatrixWorld(true);
      const part = c.parts.find((q) => q.id === p.id);
      const bb = new THREE.Box3().setFromObject(inner);
      if (part && !bb.isEmpty()) part.anchor = wrap.worldToLocal(bb.getCenter(new THREE.Vector3()));
    }
    const app = typeof window !== 'undefined' && window.__app;
    const pm = app && app.modes && app.modes.parts;
    if (pm && pm.current === c) {
      pm.labels();
      const box = new THREE.Box3();
      for (const { wrap } of holders) if (wrap.visible) box.expandByObject(wrap);
      if (v === 'beds') box.expandByObject(beds);
      if (!box.isEmpty()) app.frameObject(box, { dir: new THREE.Vector3(0.35, 1.1, 1.0), pad: 1.05 });
    }
  };
  c.controls = [{ id: 'view', type: 'chips', label: 'Show', value: 'assembled', options: [['assembled', 'Assembled'], ['beds', 'On the print beds']], onChange: (v) => setView(v) }];
  c.handles = {
    setCutaway: (x) => { asaMat.opacity = 1 - 0.8 * Math.max(0, Math.min(1, x)); asaMat.depthWrite = asaMat.opacity > 0.99; asaMat.needsUpdate = true; },
    getView: () => view,
  };
  c.setWorking = (on) => { c.fx.visible = on && view === 'assembled'; c.handles.setCutaway(on ? 0.75 : 0); };
  c.update = (t, dt, s) => {
    // the explode and the assembly stepper move and show the wrappers every frame; the bed view overrides both
    if (view === 'beds') for (const { p, wrap } of holders) { wrap.position.set(0, 0, 0); wrap.visible = bedPose.has(p.id); }
    if (s && s.working) rays.children.forEach((l, i) => { l.material.opacity = (l.material.color.r > 0.99 && l.material.color.g < 0.3 ? 0.95 : 0.55) + 0.2 * Math.sin(t * 3 + i * 0.3); });
  };
  c.cad = { origin, rays: rays.userData };
  return c;
}
