// Small geometry and maths helpers shared by every module. Units are metres; the car frame is X forward, Y up, Z right.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

export const DEG = Math.PI / 180;
export const mm = (x) => x / 1000;
export const lerp = (a, b, t) => a + (b - a) * t;
export const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
export const smoothstep = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
export const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
export const v3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);

// Rounded box centred on the origin. w along X, h along Y, d along Z.
export function rbox(w, h, d, r, mat, segs = 3) {
  const rr = Math.max(0, Math.min(r, w / 2 - 1e-5, h / 2 - 1e-5, d / 2 - 1e-5));
  const g = rr > 0 ? new RoundedBoxGeometry(w, h, d, segs, rr) : new THREE.BoxGeometry(w, h, d);
  const m = new THREE.Mesh(g, mat);
  m.castShadow = true; m.receiveShadow = true;
  return m;
}

export function box(w, h, d, mat) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
  m.castShadow = true; m.receiveShadow = true;
  return m;
}

// Cylinder along Y, centred.
export function cyl(rTop, rBot, h, mat, seg = 24, open = false) {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(rTop, rBot, h, seg, 1, open), mat);
  m.castShadow = true; m.receiveShadow = true;
  return m;
}

// Cylinder whose axis runs along X (forward), centred.
export function cylX(r, h, mat, seg = 24) {
  const m = cyl(r, r, h, mat, seg);
  m.rotation.z = Math.PI / 2;
  return m;
}

// Cylinder whose axis runs along Z (right), centred.
export function cylZ(r, h, mat, seg = 24) {
  const m = cyl(r, r, h, mat, seg);
  m.rotation.x = Math.PI / 2;
  return m;
}

export function sphere(r, mat, seg = 24) {
  const m = new THREE.Mesh(new THREE.SphereGeometry(r, seg, Math.max(8, seg >> 1)), mat);
  m.castShadow = true; m.receiveShadow = true;
  return m;
}

export function at(obj, x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0) {
  obj.position.set(x, y, z);
  obj.rotation.set(rx, ry, rz);
  return obj;
}

export function named(obj, name) { obj.name = name; return obj; }

export function group(name, ...children) {
  const g = new THREE.Group();
  g.name = name || '';
  for (const c of children) if (c) g.add(c);
  return g;
}

// Extrude a 2-D outline (array of [x, y] in metres) by depth along +Z, then centre it on Z.
export function extrude(points, depth, mat, bevel = 0) {
  const s = new THREE.Shape(points.map(([x, y]) => new THREE.Vector2(x, y)));
  const g = new THREE.ExtrudeGeometry(s, {
    depth, bevelEnabled: bevel > 0, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 2, curveSegments: 16,
  });
  g.translate(0, 0, -depth / 2);
  const m = new THREE.Mesh(g, mat);
  m.castShadow = true; m.receiveShadow = true;
  return m;
}

// A tube along a list of points (cables, hoses). Points are Vector3 or [x, y, z].
export function tube(points, radius, mat, tubular = 64) {
  const pts = points.map((p) => (p.isVector3 ? p : new THREE.Vector3(...p)));
  const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
  const m = new THREE.Mesh(new THREE.TubeGeometry(curve, tubular, radius, 8, false), mat);
  m.castShadow = true;
  m.userData.curve = curve;
  return m;
}

// Thin line strip (rays, outlines). Colour as a hex number.
export function polyline(points, color = 0xffffff, opts = {}) {
  const g = new THREE.BufferGeometry().setFromPoints(points.map((p) => (p.isVector3 ? p : new THREE.Vector3(...p))));
  const matOpts = { color, transparent: true, opacity: opts.opacity ?? 1, depthWrite: false };
  const mat = opts.dashed
    ? new THREE.LineDashedMaterial({ ...matOpts, dashSize: opts.dash ?? 0.02, gapSize: opts.gap ?? 0.015 })
    : new THREE.LineBasicMaterial(matOpts);
  if (opts.additive) mat.blending = THREE.AdditiveBlending;
  const l = new THREE.Line(g, mat);
  if (opts.dashed) l.computeLineDistances();
  l.renderOrder = opts.renderOrder ?? 5;
  return l;
}

// Canvas texture helper: draw(ctx, w, h) paints it once.
export function canvasTexture(w, h, draw, { srgb = true, repeat = null } = {}) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const ctx = c.getContext('2d');
  draw(ctx, w, h);
  const t = new THREE.CanvasTexture(c);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repeat[0], repeat[1]); }
  return t;
}

// Flat text decal (silkscreen, labels on parts). Returns a mesh of width w metres; height follows the text box aspect.
export function textDecal(text, w, { color = '#ffffff', bg = null, font = '600 64px "Helvetica Neue", Helvetica, Arial, sans-serif', pad = 10, align = 'center' } = {}) {
  const meas = document.createElement('canvas').getContext('2d');
  meas.font = font;
  const lines = String(text).split('\n');
  const lh = parseInt(font.match(/(\d+)px/)[1], 10) * 1.15;
  const tw = Math.max(...lines.map((l) => meas.measureText(l).width)) + pad * 2;
  const th = lh * lines.length + pad * 2;
  const tex = canvasTexture(Math.ceil(tw), Math.ceil(th), (ctx, W, H) => {
    if (bg) { ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H); }
    ctx.font = font; ctx.fillStyle = color; ctx.textBaseline = 'middle';
    ctx.textAlign = align;
    const x = align === 'center' ? W / 2 : align === 'right' ? W - pad : pad;
    lines.forEach((l, i) => ctx.fillText(l, x, pad + lh * (i + 0.5)));
  });
  const h = w * (th / tw);
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, toneMapped: false }));
  m.userData.height = h;
  return m;
}

// Seeded pseudo-random numbers, so scenery and noise are the same on every load.
export function rng(seed = 1) {
  let s = seed >>> 0;
  return () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

// Gaussian sample from a uniform source.
export function gauss(rand) { let u = 0, v = 0; while (u === 0) u = rand(); while (v === 0) v = rand(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }

// Traverse helper: set a flag on every mesh.
export function shadows(obj, cast = true, receive = true) {
  obj.traverse((o) => { if (o.isMesh) { o.castShadow = cast; o.receiveShadow = receive; } });
  return obj;
}

export function disposeTree(obj) {
  obj.traverse((o) => {
    if (o.geometry) o.geometry.dispose();
    if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m.dispose && m.dispose());
  });
}

export function fmt(x, d = 0) { return Number(x).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }); }

// Bounding box over visible meshes only (working-animation visuals are hidden children and must not count).
export function visibleBox(obj) {
  const box = new THREE.Box3();
  obj.updateMatrixWorld(true);
  const tmp = new THREE.Box3();
  const walk = (o) => {
    if (!o.visible) return;
    if ((o.isMesh || o.isLine || o.isPoints) && !o.isSprite && o.geometry) {
      if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
      tmp.copy(o.geometry.boundingBox).applyMatrix4(o.matrixWorld);
      if (isFinite(tmp.min.x)) box.union(tmp);
    }
    for (const c of o.children) walk(c);
  };
  walk(obj);
  return box;
}
