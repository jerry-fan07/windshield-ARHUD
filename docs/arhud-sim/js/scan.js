// A scan of the real car's dash and glass, aligned to the simulator's frame by docs/arhud-blender/import_scan.py and
// shown in Vehicle mode over the modelled car. assets/scan.glb.txt is the mesh (base64 GLB), assets/scan.json its
// provenance (source file, fit residual, face count). Without the files the section says so and does nothing.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { ASSET_BASE, fetchJson } from './assets.js';
import { h, kv, section, toggle } from './ui.js';

const DRACO_PATH = 'https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/libs/draco/gltf/';
let metaP = null;
export function loadScanInfo() {
  if (!metaP) metaP = fetchJson('scan.json').catch(() => null);
  return metaP;
}

async function loadScanMesh() {
  const r = await fetch(ASSET_BASE + 'scan.glb.txt', { cache: 'no-cache' });
  if (!r.ok) throw new Error(`scan.glb.txt: ${r.status}`);
  const bin = atob((await r.text()).trim());
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const loader = new GLTFLoader();
  const draco = new DRACOLoader();
  draco.setDecoderPath(DRACO_PATH);
  loader.setDRACOLoader(draco);
  const gltf = await new Promise((res, rej) => loader.parse(bytes.buffer, '', res, rej));
  const g = new THREE.Group();
  g.name = 'scan';
  const mat = new THREE.MeshStandardMaterial({ color: 0x9fd8ff, roughness: 0.6, metalness: 0, transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false });
  gltf.scene.traverse((m) => { if (m.isMesh) { const c = new THREE.Mesh(m.geometry, mat); c.renderOrder = 7; g.add(c); } });
  draco.dispose();
  return g;
}

// The section for the Vehicle mode's optics panel: provenance and a toggle that loads the scan on first use.
export function scanSection(meta, garage) {
  if (!meta) {
    return section('veh-scan', 'Scanned car', false,
      h('p', { class: 'hint' }, 'No scan yet. Scan the real dash and glass, then run docs/arhud-blender/import_scan.py with three measured point pairs; the aligned mesh appears here over the modelled car.'));
  }
  let mesh = garage.carGroup.getObjectByName('scan') || null;
  const tog = toggle({ id: 'scanShow', label: 'Show the scan over the modelled car', checked: !!(mesh && mesh.visible), onChange: async (v) => {
    if (!mesh) {
      try { mesh = await loadScanMesh(); garage.carGroup.add(mesh); } catch (e) { console.warn('scan', e); return; }
    }
    mesh.visible = v;
  } });
  return section('veh-scan', 'Scanned car', false,
    h('p', { class: 'hint' }, meta.source === 'simulated scanner'
      ? `A stand-in for the real scan until one exists: scan_sim.py scanned the modelled cabin with a simulated handheld scanner (${meta.scanner.poses} poses, ${meta.scanner.rays.toLocaleString()} rays, ${meta.scanner.noise_mm} mm range noise, ${Math.round(meta.scanner.dropout * 100)}% dropouts, no returns from glass, holes behind the wheel and the stalk), in its own frame in millimetres; import_scan.py aligned it from four measured points as it would a real one, and landmarks it did not use came back within ${meta.scanner.landmarkErrorMm} mm.`
      : meta.source === 'synthetic test'
        ? 'A synthetic test scan: the modelled dash and glass, moved by a random rigid transform with 1.5 mm noise, then re-aligned by import_scan.py from five noisy point pairs. Replace it with the real scan.'
        : `Scan ${meta.source}, aligned to the eye, the glass and the mirror stalk.`),
    kv([['Faces', String(meta.faces)], ['Fit residual over the point pairs', `${meta.rmsFit_mm.toFixed(1)} mm (${meta.pairs} pairs)`], ['Scale fitted', meta.scale.toFixed(4)], ['Fragments removed', String(meta.fragmentsRemoved)], ['Made', meta.generated]]),
    tog);
}
