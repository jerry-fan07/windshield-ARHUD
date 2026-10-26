// Assets baked by the Blender pipeline in docs/arhud-blender: the sky environment maps (bake_sky.py) that light the
// driving world, and the loader the Cycles reference uses. Everything here is optional: if assets/ is missing the
// simulator runs exactly as before, with its analytic lights only.
import * as THREE from 'three';
import { EXRLoader } from 'three/addons/loaders/EXRLoader.js';
import { DEG } from './util.js';

export const ASSET_BASE = new URL('../assets/', import.meta.url).href;

export async function fetchJson(rel) {
  const r = await fetch(ASSET_BASE + rel, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${rel}: ${r.status}`);
  return r.json();
}

// Image-based lighting from Blender's sky model, one equirectangular map per sun elevation plus overcast and night.
// The maps are normalised (upper hemisphere mean 1.0) and carry the sun's column, so the map is rotated at run time to
// put its sun aureole where the world's sun is. three samples an equirect at u = atan2(z, x) / 2pi + 0.5, and the
// world's azimuth b (0 = north = -Z, 90 = east = +X) lands at u = 0.25 + b / 360; environmentRotation.y = theta turns
// a direction's azimuth to b - theta before the lookup, so theta = b - 360 (sunU - 0.25) degrees aligns the suns.
export class SkyIBL {
  constructor(renderer) {
    this.renderer = renderer;
    this.pmrem = new THREE.PMREMGenerator(renderer);
    this.pmrem.compileEquirectangularShader();
    this.loader = new EXRLoader();
    this.cache = new Map();
    this.manifest = null;
    this.current = null;
    this.ok = false;
  }

  async load() {
    try {
      this.manifest = await fetchJson('sky/manifest.json');
      this.ok = Array.isArray(this.manifest.maps) && this.manifest.maps.length > 0;
    } catch (e) {
      console.warn('sky maps not available:', e.message);
      this.ok = false;
    }
    return this.ok;
  }

  pick(envName, elevationDeg) {
    const maps = this.manifest.maps;
    if (envName === 'overcast' || envName === 'night') return maps.find((m) => m.kind === envName) || null;
    const skies = maps.filter((m) => m.kind === 'sky');
    if (!skies.length) return null;
    let best = skies[0];
    for (const m of skies) if (Math.abs(m.elevation - elevationDeg) < Math.abs(best.elevation - elevationDeg)) best = m;
    return best;
  }

  // The PMREM environment for a manifest entry. Maps are EXR; a `.exr.txt` is the same file in base64, which the
  // artifact host can serve (it serves text, not EXR), decoded here and handed to EXRLoader.parse.
  texture(entry) {
    if (this.cache.has(entry.file)) return this.cache.get(entry.file);
    const url = ASSET_BASE + 'sky/' + entry.file;
    const toEnv = (tex) => { const env = this.pmrem.fromEquirectangular(tex).texture; tex.dispose(); return env; };
    const p = entry.file.endsWith('.txt')
      ? fetch(url, { cache: 'no-cache' }).then((r) => { if (!r.ok) throw new Error(`${entry.file}: ${r.status}`); return r.text(); }).then((b64) => {
          const bin = atob(b64.trim());
          const bytes = new Uint8Array(bin.length);
          for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
          const td = this.loader.parse(bytes.buffer);
          const tex = new THREE.DataTexture(td.data, td.width, td.height, td.format, td.type);
          tex.colorSpace = td.colorSpace;
          tex.minFilter = THREE.LinearFilter; tex.magFilter = THREE.LinearFilter;
          tex.generateMipmaps = false; tex.flipY = false; tex.needsUpdate = true;
          return toEnv(tex);
        })
      : new Promise((resolve, reject) => this.loader.load(url, (tex) => resolve(toEnv(tex)), undefined, reject));
    this.cache.set(entry.file, p);
    return p;
  }

  // Apply the map for this environment and sun to the scene. Returns the manifest entry in use (or null).
  apply(scene, envName, elevationDeg, azimuthDeg, intensity) {
    if (!this.ok) return null;
    const entry = this.pick(envName, elevationDeg);
    if (!entry) return null;
    const theta = entry.sunU == null ? 0 : (azimuthDeg - 360 * (entry.sunU - 0.25)) * DEG;
    scene.environmentRotation.set(0, theta, 0);
    scene.environmentIntensity = intensity;
    if (this.current !== entry.file) {
      this.current = entry.file;
      this.texture(entry).then((tex) => { if (this.current === entry.file) scene.environment = tex; }).catch((e) => console.warn('sky map', entry.file, e));
    }
    return entry;
  }
}
