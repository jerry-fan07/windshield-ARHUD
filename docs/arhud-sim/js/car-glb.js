// The Blender-baked car: assets/car.glb (docs/arhud-blender/car_bake.py) holds a smoothed copy of every static part of
// the procedural car with ambient occlusion in its vertex colours. Each part is named by its path under the car's
// groups (body, interior, leftSide, rightSide) and carries the vertex count and bounding box of the procedural mesh it
// was made from. A part replaces its original only when both still match, so a stale file after a change to car.js
// leaves the procedural mesh in place. The replacement keeps the original's local transform, shadows and material
// (cloned with vertex colours on), so cutaways, the x-ray, mount points and draw-call counts are unchanged.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { ASSET_BASE } from './assets.js';

const DRACO_PATH = 'https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/libs/draco/gltf/';

// The artifact host serves text but not .glb, so every model travels as base64 in a .glb.txt beside it.
async function loadGlb(url) {
  const loader = new GLTFLoader();
  const draco = new DRACOLoader();
  draco.setDecoderPath(DRACO_PATH);
  loader.setDRACOLoader(draco);
  const r = await fetch(url + '.txt', { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${url.split('/').pop()}.txt: ${r.status}`);
  const bin = atob((await r.text()).trim());
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const gltf = await new Promise((resolve, reject) => loader.parse(bytes.buffer, '', resolve, reject));
  draco.dispose();
  return gltf;
}

// Material clones (vertex colours on) made from the car's own materials; the x-ray and the cutaways change flags on
// the originals, so one wrapper keeps every clone in step.
const clones = [];
function keepClonesInStep(car) {
  if (car._clonesWrapped) return;
  const orig = car.setCutaway;
  if (!orig) return;
  car.setCutaway = (mode) => {
    orig(mode);
    for (const [s, c] of clones) { c.transparent = s.transparent; c.opacity = s.opacity; c.depthWrite = s.depthWrite; c.needsUpdate = true; }
  };
  car._clonesWrapped = true;
}
const groupsOf = (car) => ({ body: car.body, interior: car.interior, leftSide: car.leftSide, rightSide: car.body.getObjectByName('rightSide') });
const resolvePath = (roots, path) => { const [root, ...idx] = path.split('/'); let t = roots[root]; for (const i of idx) t = t && t.children[+i]; return t; };

export async function applyBakedCar(car, { url = ASSET_BASE + 'car.glb', tol = 0.003 } = {}) {
  const gltf = await loadGlb(url);
  const roots = groupsOf(car);
  const stats = { replaced: 0, skipped: 0, reasons: {} };
  const skip = (why) => { stats.skipped++; stats.reasons[why] = (stats.reasons[why] || 0) + 1; };
  const meshes = [];
  // the path lives in extras (userData): GLTFLoader strips ':' and '/' from node names
  gltf.scene.traverse((m) => { if (m.isMesh && m.userData && m.userData.kind === 'static' && m.userData.path) meshes.push(m); });
  for (const m of meshes) {
    const t = resolvePath(roots, m.userData.path);
    const u = m.userData || {};
    if (!t || !t.isMesh || !t.geometry || !u.bbox) { skip('no target'); continue; }
    if (Array.isArray(t.material)) { skip('multi-material'); continue; }
    t.geometry.computeBoundingBox();
    const b = t.geometry.boundingBox;
    const got = [b.min.x, b.min.y, b.min.z, b.max.x, b.max.y, b.max.z];
    if (u.bbox.some((v, k) => Math.abs(v - got[k]) > tol) || u.verts !== t.geometry.attributes.position.count) { skip('changed'); continue; }
    if (!m.geometry.attributes.color) { skip('no colour'); continue; }
    const mat = t.material.clone();
    mat.vertexColors = true;
    mat.needsUpdate = true;
    clones.push([t.material, mat]);
    const nm = new THREE.Mesh(m.geometry, mat);
    nm.position.copy(t.position); nm.quaternion.copy(t.quaternion); nm.scale.copy(t.scale);
    nm.castShadow = t.castShadow; nm.receiveShadow = t.receiveShadow; nm.renderOrder = t.renderOrder;
    nm.name = t.name; nm.userData = { ...t.userData, baked: true };
    t.parent.add(nm);
    t.visible = false;
    t.userData.replacedBy = nm;
    stats.replaced++;
  }
  keepClonesInStep(car);
  car.setCutaway && car.setCutaway(car.cutaway || 'none');
  car.baked = stats;
  return stats;
}

// The body shell modelled in Blender (docs/arhud-blender/car_body.py): two halves, left and right of the centre line,
// each listing the procedural exterior parts it stands in for. Materials come from those parts: the paint is the
// clear-coated one, the glass the translucent one, the black trim the dark one; the shell's own slots are placeholders.
export async function applyBodyShell(car, { url = ASSET_BASE + 'car_body.glb' } = {}) {
  const gltf = await loadGlb(url);
  const roots = groupsOf(car);
  const stats = { halves: 0, hidden: 0 };
  // a mesh with several material slots arrives as a Group of one Mesh per slot; the node's extras sit on the Group
  const halves = [];
  gltf.scene.traverse((o) => { if (o.userData && o.userData.kind === 'shell') halves.push(o); });
  for (const m of halves) {
    const group = roots[m.userData.group];
    if (!group) continue;
    const prims = m.isMesh ? [m] : m.children.filter((c) => c.isMesh);
    const replaces = JSON.parse(m.userData.replaces || '[]');
    const hidden = [];
    for (const p of replaces) { const t = resolvePath(roots, p); if (t && t.isMesh && !t.userData.baked) { hidden.push(t); } }
    const pool = hidden.map((t) => t.material).filter((x) => x && !Array.isArray(x));
    const pick = (f, fallback) => pool.find(f) || fallback;
    const paint = pick((x) => x.isMeshPhysicalMaterial && x.clearcoat > 0.5, pool[0]);
    const glass = pick((x) => x.transparent && x.opacity > 0.3 && x.opacity < 0.6, paint);
    const black = pick((x) => !x.transparent && x.color && x.color.r < 0.08 && x.color.g < 0.08, paint);
    if (!paint) continue;
    const byName = (n) => (n === 'paint' ? paint : n === 'sideGlass' || n === 'rearGlass' ? glass : n === 'black' ? black : paint);
    for (const pm of prims) {
      const n = (pm.material && pm.material.name) || 'paint';
      const x = byName(n.replace(/\.\d+$/, ''));
      const c = x.clone(); c.vertexColors = !!pm.geometry.attributes.color; c.needsUpdate = true; clones.push([x, c]);
      const nm = new THREE.Mesh(pm.geometry, c);
      nm.name = 'shell:' + m.userData.group + ':' + n; nm.castShadow = true; nm.receiveShadow = true; nm.userData.baked = true;
      nm.renderOrder = c.transparent ? 8 : 0;
      group.add(nm);
    }
    for (const t of hidden) { if (t.visible) { t.visible = false; stats.hidden++; } if (t.userData.replacedBy) t.userData.replacedBy.visible = false; }
    stats.halves++;
  }
  keepClonesInStep(car);
  car.setCutaway && car.setCutaway(car.cutaway || 'none');
  car.shell = stats;
  return stats;
}
