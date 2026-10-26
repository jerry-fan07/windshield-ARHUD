// Picture generation unit: the 5.5-inch HDMI panel kit, its LCD cell, the custom direct-lit backlight, the half-wave
// retarder and the assembled PGU. Every number comes from params.js (calc.py); ASSUMED values are tagged as in the spec.
//
// Local frames: X forward, Y up, Z right, metres. The panel lies flat and faces +Y with its long side along Z, as it sits
// in the housing. The PGU's origin is the centre of the 60 x 30 mm crop on the front-polariser surface, so it drops onto
// geom.PANEL_C unchanged.
import * as THREE from 'three';
import { P, R, V } from '../params.js';
import { M } from '../mats.js';
import { rbox, box, cyl, sphere, at, extrude, tube, canvasTexture, textDecal, rng, mm, DEG, clamp, lerp, smoothstep } from '../util.js';
import { makeComponent, addPart } from './contract.js';

export const PANEL = {
  activeZ: R.PANEL_W / 1000, activeX: R.PANEL_H / 1000,      // 121.8 x 68.5 mm (ASSUMED from the diagonal)
  outZ: 0.1255, outX: 0.0735,                                // glass outline
  cropZ: R.PGU_W / 1000, cropX: R.PGU_H / 1000,              // 60 x 30 mm crop
};
const FONT = '"Helvetica Neue", Helvetica, Arial, sans-serif';

// ---------------------------------------------------------------------------------------------------------------
// Shared helpers (also imported by optics.js)
// ---------------------------------------------------------------------------------------------------------------
export function costOf(substr) {
  const row = P.COST.find((r) => r[0].includes(substr));
  if (!row) return '—';
  return row[1] === row[2] ? `$${row[1].toLocaleString()}` : `$${row[1].toLocaleString()}–${row[2].toLocaleString()} (${row[3]})`;
}

// Billboard label for working visuals. lineH is the height of one text line in metres.
export function labelSprite(lines, lineH = 0.005, { color = '#f3efe6', bg = 'rgba(12,14,18,0.82)', accent = null, anchor = 'bottom' } = {}) {
  const arr = Array.isArray(lines) ? lines : String(lines).split('\n');
  const fs = 40, lh = fs * 1.28, pad = 16;
  const meas = document.createElement('canvas').getContext('2d');
  const widthOf = (l, i) => { meas.font = `${i === 0 ? 600 : 500} ${fs}px ${FONT}`; return meas.measureText(l).width; };
  const W = Math.ceil(Math.max(...arr.map(widthOf)) + pad * 2 + (accent ? 10 : 0));
  const H = Math.ceil(lh * arr.length + pad * 2);
  const tex = canvasTexture(W, H, (ctx) => {
    ctx.fillStyle = bg;
    const r = 14;
    ctx.beginPath(); ctx.moveTo(r, 0); ctx.arcTo(W, 0, W, H, r); ctx.arcTo(W, H, 0, H, r); ctx.arcTo(0, H, 0, 0, r); ctx.arcTo(0, 0, W, 0, r); ctx.fill();
    if (accent) { ctx.fillStyle = accent; ctx.fillRect(0, 10, 6, H - 20); }
    ctx.textBaseline = 'middle';
    arr.forEach((l, i) => {
      ctx.font = `${i === 0 ? 600 : 500} ${fs}px ${FONT}`;
      ctx.fillStyle = color;
      ctx.fillText(l, pad + (accent ? 10 : 0), pad + lh * (i + 0.5));
    });
  });
  const mat = new THREE.SpriteMaterial({ map: tex, depthTest: false, depthWrite: false, transparent: true, toneMapped: false });
  const s = new THREE.Sprite(mat);
  const sh = lineH * H / lh;
  s.scale.set(sh * W / H, sh, 1);
  if (anchor === 'bottom') s.center.set(0.5, 0);
  else if (anchor === 'left') s.center.set(0, 0.5);
  else if (anchor === 'right') s.center.set(1, 0.5);
  s.renderOrder = 50;
  s.layers.set(1);   // the label layer: cameras show it unless labels are off; the audience camera never does
  return s;
}

let _glowTex = null;
export function glowTexture() {
  if (!_glowTex) {
    _glowTex = canvasTexture(64, 64, (ctx, W, H) => {
      const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
      g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.2, 'rgba(255,244,220,0.7)'); g.addColorStop(1, 'rgba(255,230,190,0)');
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    });
  }
  return _glowTex;
}
export function glowSprite(size, color = 0xfff1d8) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, toneMapped: false }));
  s.scale.set(size, size, 1);
  return s;
}

// Double-headed polarisation arrow lying in the XZ plane; angle measured from +X toward +Z.
export function polArrow(len, color) {
  const g = new THREE.Group();
  const mat = new THREE.MeshBasicMaterial({ color, toneMapped: false, transparent: true });
  const shaft = new THREE.Mesh(new THREE.BoxGeometry(len * 0.8, len * 0.035, len * 0.035), mat);
  g.add(shaft);
  for (const sgn of [-1, 1]) {
    const cone = new THREE.Mesh(new THREE.ConeGeometry(len * 0.07, len * 0.14, 12), mat);
    cone.rotation.z = -sgn * Math.PI / 2;
    cone.position.x = sgn * len * 0.43;
    g.add(cone);
  }
  g.userData.mat = mat;
  g.setAngle = (a) => { g.rotation.set(0, -a, 0); };
  return g;
}

// Additive line-segment streaks for ray particles.
export class Streaks {
  constructor(n, { opacity = 0.9 } = {}) {
    this.n = n;
    this.pos = new Float32Array(n * 6);
    this.col = new Float32Array(n * 6);
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('color', new THREE.BufferAttribute(this.col, 3).setUsage(THREE.DynamicDrawUsage));
    this.mesh = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 20;
  }
  set(i, ax, ay, az, bx, by, bz, r, g, b, fade = 0.25) {
    const p = this.pos, c = this.col, k = i * 6;
    p[k] = ax; p[k + 1] = ay; p[k + 2] = az; p[k + 3] = bx; p[k + 4] = by; p[k + 5] = bz;
    c[k] = r; c[k + 1] = g; c[k + 2] = b; c[k + 3] = r * fade; c[k + 4] = g * fade; c[k + 5] = b * fade;
  }
  hide(i) { const k = i * 6; for (let j = 0; j < 6; j++) { this.pos[k + j] = 0; this.col[k + j] = 0; } }
  commit() { this.mesh.geometry.attributes.position.needsUpdate = true; this.mesh.geometry.attributes.color.needsUpdate = true; }
}

// Flat flexible ribbon (FPC, flat cables) along a list of points; side is the in-plane width direction.
export function ribbon(points, width, side, mat) {
  const pts = points.map((p) => (p.isVector3 ? p : new THREE.Vector3(...p)));
  const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
  const N = 48, pos = [], uv = [], idx = [];
  const s = side.clone().normalize().multiplyScalar(width / 2);
  for (let i = 0; i <= N; i++) {
    const p = curve.getPoint(i / N);
    pos.push(p.x - s.x, p.y - s.y, p.z - s.z, p.x + s.x, p.y + s.y, p.z + s.z);
    uv.push(0, i / N, 1, i / N);
    if (i < N) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx); g.computeVertexNormals();
  const m = new THREE.Mesh(g, mat);
  m.castShadow = true;
  return m;
}

// Pan-head screw, axis along +Y, head top at y = 0.
export function screw(r = 0.0013, len = 0.004, mat = M.steel) {
  const g = new THREE.Group();
  const head = cyl(r * 1.8, r * 1.9, r * 1.2, mat, 16); head.position.y = -r * 0.6; g.add(head);
  const slot = box(r * 2.6, r * 0.5, r * 0.5, M.plasticBlack); slot.position.y = 0; g.add(slot);
  const slot2 = slot.clone(); slot2.rotation.y = Math.PI / 2; g.add(slot2);
  const shank = cyl(r, r, len, mat, 10); shank.position.y = -r * 1.2 - len / 2; g.add(shank);
  return g;
}

const slab = (x, y, z, mat) => box(x, y, z, mat);
const lmat = (o) => new THREE.MeshStandardMaterial(o);

// Lambertian (cosine-weighted) direction about +Y.
function lambert(rand, out) {
  const r1 = rand(), phi = rand() * Math.PI * 2, s = Math.sqrt(r1);
  out[0] = s * Math.cos(phi); out[1] = Math.sqrt(1 - r1); out[2] = s * Math.sin(phi);
  return out;
}

// ---------------------------------------------------------------------------------------------------------------
// Textures for the panel
// ---------------------------------------------------------------------------------------------------------------
function testPatternTexture() {
  return canvasTexture(960, 540, (ctx, W, H) => {
    const bars = ['#f4f4f4', '#f0e020', '#20e0e8', '#20d040', '#e030d8', '#e83020', '#2040e8', '#101010'];
    bars.forEach((c, i) => { ctx.fillStyle = c; ctx.fillRect(i * W / 8, 0, W / 8 + 1, H * 0.6); });
    const g = ctx.createLinearGradient(0, 0, W, 0); g.addColorStop(0, '#000'); g.addColorStop(1, '#fff');
    ctx.fillStyle = g; ctx.fillRect(0, H * 0.6, W, H * 0.14);
    ctx.fillStyle = '#0c0c0e'; ctx.fillRect(0, H * 0.74, W, H * 0.26);
    ctx.strokeStyle = 'rgba(255,255,255,0.35)'; ctx.lineWidth = 2;
    for (let x = 0; x <= W; x += 60) { ctx.beginPath(); ctx.moveTo(x, H * 0.74); ctx.lineTo(x, H); ctx.stroke(); }
    ctx.beginPath(); ctx.arc(W / 2, H * 0.37, H * 0.3, 0, Math.PI * 2); ctx.strokeStyle = '#000'; ctx.lineWidth = 4; ctx.stroke();
    ctx.fillStyle = '#fff'; ctx.font = `600 34px ${FONT}`; ctx.textAlign = 'center';
    ctx.fillText('1920 × 1080 · stock backlight 450 cd/m²', W / 2, H * 0.89);
  });
}

// What the crop shows until the app hands over the live HUD frame: an illustrative frame in image coordinates.
export function hudPlaceholderTexture() {
  return canvasTexture(946, 473, (ctx, W, H) => {
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = 'rgba(70,170,255,0.55)';
    ctx.beginPath(); ctx.moveTo(W * 0.28, H); ctx.lineTo(W * 0.47, H * 0.08); ctx.lineTo(W * 0.56, H * 0.08); ctx.lineTo(W * 0.78, H); ctx.fill();
    ctx.strokeStyle = '#7fd0ff'; ctx.lineWidth = 8;
    ctx.beginPath(); ctx.moveTo(W * 0.26, H); ctx.lineTo(W * 0.465, H * 0.08); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(W * 0.80, H); ctx.lineTo(W * 0.565, H * 0.08); ctx.stroke();
    ctx.fillStyle = '#ffd24a';
    ctx.beginPath(); ctx.moveTo(W * 0.47, H * 0.22); ctx.lineTo(W * 0.515, H * 0.30); ctx.lineTo(W * 0.56, H * 0.22); ctx.lineTo(W * 0.56, H * 0.26); ctx.lineTo(W * 0.515, H * 0.34); ctx.lineTo(W * 0.47, H * 0.26); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.font = `700 30px ${FONT}`; ctx.textAlign = 'center'; ctx.fillText('32 m · 1.9 s', W * 0.515, H * 0.43);
    ctx.fillStyle = 'rgba(255,255,255,0.92)'; ctx.font = `700 74px ${FONT}`; ctx.textAlign = 'left'; ctx.fillText('62', W * 0.04, H * 0.86);
    ctx.font = `600 28px ${FONT}`; ctx.fillText('mph · limit 65', W * 0.16, H * 0.86);
  });
}

function pixelGridTexture() {
  return canvasTexture(256, 256, (ctx, W, H) => {
    ctx.fillStyle = '#20262e'; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = 'rgba(190,200,215,0.35)'; ctx.lineWidth = 1;
    for (let i = 0; i < W; i += 8) { ctx.beginPath(); ctx.moveTo(i + 0.5, 0); ctx.lineTo(i + 0.5, H); ctx.stroke(); }
    for (let j = 0; j < H; j += 24) { ctx.beginPath(); ctx.moveTo(0, j + 0.5); ctx.lineTo(W, j + 0.5); ctx.stroke(); }
  }, { repeat: [12, 3] });
}

function cfTexture() {
  return canvasTexture(96, 32, (ctx, W, H) => {
    ['#3a1418', '#16301a', '#141c3a'].forEach((c, i) => { ctx.fillStyle = c; ctx.fillRect(i * 32, 0, 32, H); });
    ctx.fillStyle = '#050505'; for (let i = 0; i < 3; i++) ctx.fillRect(i * 32, 0, 3, H);
  }, { repeat: [60, 12] });
}

function lgpTexture() {
  return canvasTexture(256, 256, (ctx, W, H) => {
    ctx.fillStyle = 'rgba(220,235,245,1)'; ctx.fillRect(0, 0, W, H);
    for (let y = 8; y < H; y += 16) for (let x = 8; x < W; x += 16) {
      const r = 1.2 + 3.6 * (x / W);           // dots grow away from the LED edge
      ctx.fillStyle = 'rgba(255,255,255,0.95)'; ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
    }
  }, { repeat: [3, 2] });
}

function polHatchTexture(alongZ) {
  return canvasTexture(128, 128, (ctx, W, H) => {
    ctx.fillStyle = '#3c4a4c'; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = 'rgba(200,230,230,0.35)'; ctx.lineWidth = 2;
    for (let i = 0; i < W; i += 8) { ctx.beginPath(); if (alongZ) { ctx.moveTo(0, i); ctx.lineTo(W, i); } else { ctx.moveTo(i, 0); ctx.lineTo(i, H); } ctx.stroke(); }
  }, { repeat: [8, 8] });
}

// Crop image plane: exactly 60 x 30 mm, lying flat facing +Y; texture u runs toward +Z and the image's top is at -X.
// Three reflections (fold, concave mirror, windshield) mirror the image, so the panel shows it flipped this way.
export function cropPlane(tex) {
  const hz = PANEL.cropZ / 2, hx = PANEL.cropX / 2;
  const g = new THREE.BufferGeometry();
  // vertices: (x, z) corners with uv (u = (z + hz) / 2hz, v = (hx - x) / 2hx)
  const pos = [-hx, 0, -hz, -hx, 0, hz, hx, 0, -hz, hx, 0, hz];
  const uv = [0, 1, 1, 1, 0, 0, 1, 0];
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex([0, 1, 2, 1, 3, 2]);
  g.computeVertexNormals();
  const mat = new THREE.MeshBasicMaterial({ map: tex, toneMapped: false, side: THREE.DoubleSide });
  const m = new THREE.Mesh(g, mat);
  m.name = 'cropImage';
  return m;
}

// ---------------------------------------------------------------------------------------------------------------
// Sub-assemblies
// ---------------------------------------------------------------------------------------------------------------
// LCD cell layers, each a group positioned at its bottom surface. Front polariser top is at y = 0.
function cellLayers({ withLedge = true } = {}) {
  const X = PANEL.outX, Z = PANEL.outZ;
  const L = {};
  const mk = (y0, th, x, z, mat, offX = 0) => { const g = new THREE.Group(); g.position.y = y0; const m = slab(x, th, z, mat); m.position.set(offX, th / 2, 0); g.add(m); g.userData.mesh = m; return g; };
  L.rearPol = mk(-0.0015, 0.0002, X - 0.002, Z - 0.002, new THREE.MeshPhysicalMaterial({ color: 0xffffff, map: polHatchTexture(false), roughness: 0.3, transparent: true, opacity: 0.8 }));
  // TFT glass is 4 mm longer on the -X edge: the ledge carries the chip-on-glass driver and the FPC bond.
  const tftMat = new THREE.MeshPhysicalMaterial({ color: 0xffffff, map: pixelGridTexture(), roughness: 0.08, metalness: 0.1, transparent: true, opacity: 0.92 });
  L.tft = mk(-0.0013, 0.0005, X + (withLedge ? 0.004 : 0), Z, tftMat, withLedge ? -0.002 : 0);
  if (withLedge) {
    const ic = slab(0.0012, 0.0004, 0.024, M.chip); ic.position.set(-X / 2 - 0.0018, 0.0007, 0); L.tft.add(ic);
    const ic2 = ic.clone(); ic2.position.z = 0.03; L.tft.add(ic2);
    const bond = slab(0.0015, 0.0001, 0.034, M.fpc); bond.position.set(-X / 2 - 0.0032, 0.00055, -0.008); L.tft.add(bond);
  }
  L.lc = mk(-0.0008, 0.0001, X - 0.003, Z - 0.003, new THREE.MeshPhysicalMaterial({ color: 0x9fd8e8, roughness: 0.2, transparent: true, opacity: 0.6, iridescence: 1, iridescenceIOR: 1.7 }));
  // seal line around the LC
  const seal = new THREE.Group();
  for (const [sx, sz, w, d] of [[0, (Z - 0.003) / 2, X - 0.003, 0.0008], [0, -(Z - 0.003) / 2, X - 0.003, 0.0008], [(X - 0.003) / 2, 0, 0.0008, Z - 0.003], [-(X - 0.003) / 2, 0, 0.0008, Z - 0.003]]) {
    const s = slab(w, 0.0001, d, M.ceramic); s.position.set(sx, 0.00005, sz); seal.add(s);
  }
  L.lc.add(seal);
  L.cf = mk(-0.0007, 0.0005, X, Z, new THREE.MeshPhysicalMaterial({ color: 0xffffff, map: cfTexture(), roughness: 0.1, transparent: true, opacity: 0.85 }));
  L.frontPol = mk(-0.0002, 0.0002, X - 0.001, Z - 0.001, M.lcdGlass);
  return L;
}

function hdmiBoard() {
  const g = new THREE.Group(); g.name = 'hdmiBoardBody';
  const W = 0.064, D = 0.046, T = 0.0016;            // along Z, along X, thickness
  const pcb = rbox(D, T, W, 0.0015, M.pcbBlack); pcb.position.y = T / 2; g.add(pcb);
  // HDMI type-A receptacle on the -X edge
  const hdmi = new THREE.Group();
  const shell = rbox(0.011, 0.0058, 0.0152, 0.0006, M.steel); hdmi.add(shell);
  const mouth = slab(0.0005, 0.0036, 0.0124, M.plasticBlack); mouth.position.x = -0.0054; hdmi.add(mouth);
  const tongue = slab(0.006, 0.0012, 0.0098, M.plasticBlack); tongue.position.set(-0.002, 0, 0); hdmi.add(tongue);
  hdmi.position.set(-D / 2 + 0.004, T + 0.0029, -0.014); g.add(hdmi);
  // micro-USB power
  const usb = rbox(0.0055, 0.0026, 0.0078, 0.0004, M.steel); usb.position.set(-D / 2 + 0.002, T + 0.0013, 0.012); g.add(usb);
  // bridge IC, flash, regulators, crystal, inductors
  const ic = rbox(0.012, 0.0012, 0.012, 0.0004, M.chip); ic.position.set(0.002, T + 0.0006, -0.004); g.add(ic);
  const dot = cyl(0.0006, 0.0006, 0.0001, M.plasticGrey, 10); dot.position.set(-0.0035, T + 0.00125, -0.0085); g.add(dot);
  const flash = rbox(0.005, 0.0012, 0.004, 0.0003, M.chip); flash.position.set(0.012, T + 0.0006, -0.016); g.add(flash);
  for (let i = 0; i < 3; i++) { const reg = rbox(0.003, 0.0012, 0.0016, 0.0002, M.chip); reg.position.set(-0.008 + i * 0.005, T + 0.0006, 0.018); g.add(reg); }
  const xtal = rbox(0.0032, 0.0009, 0.0025, 0.0003, M.steel); xtal.position.set(0.009, T + 0.00045, 0.004); g.add(xtal);
  for (let i = 0; i < 2; i++) { const ind = rbox(0.0045, 0.0022, 0.0045, 0.0006, M.plasticGrey); ind.position.set(-0.012, T + 0.0011, 0.004 + i * 0.006); g.add(ind); }
  const rnd = rng(21);
  for (let i = 0; i < 26; i++) { const cap = slab(0.0012, 0.0006, 0.0007, rnd() > 0.5 ? M.ceramic : M.chip); cap.position.set(-0.016 + rnd() * 0.034, T + 0.0003, -0.026 + rnd() * 0.05); g.add(cap); }
  const led = slab(0.0012, 0.0005, 0.0008, M.led(0x30ff60, 0.0)); led.position.set(-0.016, T + 0.00025, 0.024); g.add(led); g.userData.led = led;
  // 40-pin ZIF FPC connector on the +X edge
  const zif = rbox(0.0045, 0.002, 0.03, 0.0003, M.plasticWhite); zif.position.set(D / 2 - 0.004, T + 0.001, 0); g.add(zif);
  const latch = slab(0.0015, 0.0006, 0.03, M.plasticBlack); latch.position.set(D / 2 - 0.0015, T + 0.0022, 0); g.add(latch);
  const silk = textDecal('HDMI → MIPI 1080P  V2.1', 0.026, { color: '#e8e8e8' }); silk.rotation.set(-Math.PI / 2, 0, Math.PI / 2); silk.position.set(0.014, T + 0.0001, 0.006); g.add(silk);
  for (const [x, z] of [[-D / 2 + 0.003, -W / 2 + 0.003], [-D / 2 + 0.003, W / 2 - 0.003], [D / 2 - 0.003, -W / 2 + 0.003], [D / 2 - 0.003, W / 2 - 0.003]]) {
    const ring = cyl(0.0017, 0.0017, 0.00005, M.gold, 16); ring.position.set(x, T + 0.00003, z); g.add(ring);
  }
  g.userData.size = [D, W];
  return g;
}

const LED_BASE = new THREE.MeshStandardMaterial({ color: 0xc9b88a, roughness: 0.5 });
// Ceramic-base XP-G class LED with a silicone dome. Origin at the base centre; top of dome at about 2.4 mm.
function powerLed(emissiveMat) {
  const g = new THREE.Group();
  const base = slab(0.00345, 0.0006, 0.00345, LED_BASE); base.position.y = 0.0003; g.add(base);
  const ring = cyl(0.0016, 0.0016, 0.0003, M.steel, 20); ring.position.y = 0.00075; g.add(ring);
  const phos = slab(0.0022, 0.0002, 0.0022, emissiveMat); phos.position.y = 0.0008; g.add(phos);
  const dome = new THREE.Mesh(new THREE.SphereGeometry(0.0014, 20, 10, 0, Math.PI * 2, 0, Math.PI / 2),
    new THREE.MeshPhysicalMaterial({ color: 0xffffff, transmission: 0.9, roughness: 0.05, thickness: 0.001, transparent: true, opacity: 0.5 }));
  dome.scale.y = 1.2; dome.position.y = 0.0006; g.add(dome);
  return g;
}

// 40 mm axial fan, frame 10 mm thick. Origin at frame centre. Returns { group, rotor }.
function fan40() {
  const g = new THREE.Group();
  const s = 0.040, r = 0.0192;
  const shape = new THREE.Shape([new THREE.Vector2(-s / 2, -s / 2), new THREE.Vector2(s / 2, -s / 2), new THREE.Vector2(s / 2, s / 2), new THREE.Vector2(-s / 2, s / 2)]);
  const hole = new THREE.Path(); hole.absarc(0, 0, r, 0, Math.PI * 2, true); shape.holes.push(hole);
  for (const [x, y] of [[-0.016, -0.016], [0.016, -0.016], [0.016, 0.016], [-0.016, 0.016]]) { const h = new THREE.Path(); h.absarc(x, y, 0.0017, 0, Math.PI * 2, true); shape.holes.push(h); }
  const fg = new THREE.ExtrudeGeometry(shape, { depth: 0.010, bevelEnabled: false, curveSegments: 32 });
  fg.translate(0, 0, -0.005); fg.rotateX(-Math.PI / 2);
  const frame = new THREE.Mesh(fg, M.plasticBlack); frame.castShadow = true; g.add(frame);
  // support spokes at the bottom
  for (let i = 0; i < 4; i++) { const sp = slab(0.019, 0.0015, 0.0018, M.plasticBlack); sp.position.set(0, -0.0042, 0); sp.rotation.y = i * Math.PI / 2 + Math.PI / 4; sp.translateX(0.0095); g.add(sp); }
  const rotor = new THREE.Group();
  const hub = cyl(0.0078, 0.0078, 0.0085, M.plasticBlack, 24); rotor.add(hub);
  const sticker = cyl(0.0065, 0.0065, 0.0002, M.plasticWhite, 24); sticker.position.y = 0.0044; rotor.add(sticker);
  const lab = textDecal('12V 0.10A', 0.010, { color: '#222' }); lab.rotation.x = -Math.PI / 2; lab.position.y = 0.0046; rotor.add(lab);
  for (let i = 0; i < 7; i++) {
    const blade = new THREE.Group();
    const b = slab(0.0105, 0.0006, 0.0072, M.plasticBlack); b.position.x = 0.0128; b.rotation.x = 0.55; blade.add(b);
    blade.rotation.y = i * Math.PI * 2 / 7; rotor.add(blade);
  }
  g.add(rotor);
  const wires = tube([[0.016, 0.003, 0.004], [0.022, 0.003, 0.004], [0.03, 0.0, 0.01]], 0.0006, M.cableRed); g.add(wires);
  const wires2 = tube([[0.016, 0.003, 0.0055], [0.022, 0.003, 0.0055], [0.03, 0.0, 0.0115]], 0.0006, M.cableBlack); g.add(wires2);
  return { group: g, rotor };
}

// Crossed-prism (BEF) film: a real sawtooth profile, ridges along Z when ridgesAlongZ, else along X.
function prismFilm(sizeX, sizeZ, ridgesAlongZ, mat) {
  const across = ridgesAlongZ ? sizeX : sizeZ, along = ridgesAlongZ ? sizeZ : sizeX;
  const pitch = 0.0006, h = 0.0003, tb = 0.00012;
  const n = Math.floor(across / pitch);
  const w = n * pitch;
  const pts = [[-w / 2, 0], [w / 2, 0], [w / 2, tb]];
  for (let i = n - 1; i >= 0; i--) { const x0 = -w / 2 + i * pitch; pts.push([x0 + pitch / 2, tb + h], [x0, tb]); }
  const m = extrude(pts, along, mat);
  if (!ridgesAlongZ) m.rotation.y = Math.PI / 2;
  return m;
}

// ---------------------------------------------------------------------------------------------------------------
// panelKit
// ---------------------------------------------------------------------------------------------------------------
export function buildPanelKit() {
  const c = makeComponent(THREE, {
    id: 'panelKit',
    name: 'Wisecoco 5.5-inch 1920 × 1080 IPS HDMI kit (as unboxed)',
    category: 'pgu',
    mount: 'centre of the active area, on the front-polariser surface',
    size: [0.14, 0.012, 0.13],
    desc: 'The picture generator starts as a hobby HDMI kit: a 5.5-inch 1920 × 1080 IPS panel with its stock edge-lit backlight and an HDMI-to-MIPI driver board. The plan buys two; one stays stock for Stage 0 and as a spare, the other is taken apart so only a 60 × 30 mm crop of its cell is lit by the custom backlight.',
    working: 'The stock edge LEDs light the light-guide plate and the panel shows a test image at the vendor\'s 450 cd/m², about 6% of the daylight sky target at the eye.',
  });
  c.facts = [
    ['Active area', `${R.PANEL_W} × ${R.PANEL_H} mm (ASSUMED from the 5.5-inch diagonal)`],
    ['Resolution, pitch', `1920 × 1080, ${V.pitch_5} µm`],
    ['Stock luminance', `${V.stock_panel} cd/m² (vendor); ${V.stock_ws} cd/m² at the eye through the windshield path`],
    ['Interface', 'HDMI in, MIPI DSI to the panel over a 40-pin FPC; 5 V on micro-USB'],
    ['Price', `$95 each; panels line ${costOf('Panels')}`],
    ['Why this panel', 'the only small 1080p HDMI kit found; no 5-inch 1080p kit exists'],
    ['Stock backlight', 'edge-lit light guide, a few hundred cd/m²; removed for Stage 2'],
  ];
  const X = PANEL.outX, Z = PANEL.outZ;
  const L = cellLayers();
  // Stock backlight stack below the cell (y < -1.5 mm)
  const mkLayer = (y0, th, x, z, mat) => { const g = new THREE.Group(); g.position.y = y0; const m = slab(x, th, z, mat); m.position.y = th / 2; g.add(m); g.userData.mesh = m; return g; };
  const tray = new THREE.Group(); tray.position.y = -0.0037;
  {
    const floor = slab(X + 0.002, 0.0003, Z + 0.002, M.steel); floor.position.y = 0.00015; tray.add(floor);
    for (const [px, pz, w, d] of [[0, (Z + 0.002) / 2, X + 0.002, 0.0003], [0, -(Z + 0.002) / 2, X + 0.002, 0.0003], [(X + 0.002) / 2, 0, 0.0003, Z + 0.002], [-(X + 0.002) / 2, 0, 0.0003, Z + 0.002]]) {
      const w1 = slab(w, 0.0034, d, M.steel); w1.position.set(px, 0.0017, pz); tray.add(w1);
    }
    const lbl = textDecal('WS055FHD-01  1920×1080  IPS', 0.05, { color: '#333' }); lbl.rotation.x = Math.PI / 2; lbl.position.set(0, -0.00002, 0); tray.add(lbl);
  }
  const reflector = mkLayer(-0.0034, 0.0001, X - 0.001, Z - 0.004, M.plasticWhite);
  const lgpMat = new THREE.MeshPhysicalMaterial({ color: 0xffffff, map: lgpTexture(), roughness: 0.05, transmission: 0.5, transparent: true, opacity: 0.75 });
  const lgp = mkLayer(-0.0031, 0.0008, X - 0.0015, Z - 0.006, lgpMat);
  const ledMat = M.led(0xfff4dd, 0);
  const ledStrip = new THREE.Group(); ledStrip.position.set(0, -0.0031, 0);
  {
    const flex = slab(X - 0.004, 0.0008, 0.0002, M.fpc); flex.position.set(0, 0.0004, Z / 2 - 0.0025); ledStrip.add(flex);
    for (let i = 0; i < 18; i++) {
      const led = slab(0.0028, 0.0006, 0.0008, M.plasticWhite); led.position.set(-X / 2 + 0.005 + i * (X - 0.01) / 17, 0.0004, Z / 2 - 0.0031); ledStrip.add(led);
      const em = slab(0.002, 0.0004, 0.0001, ledMat); em.position.set(led.position.x, 0.0004, Z / 2 - 0.0036); ledStrip.add(em);
    }
  }
  const diff = mkLayer(-0.0022, 0.0001, X - 0.002, Z - 0.004, M.diffuser);
  const prismA = mkLayer(-0.0020, 0.0001, X - 0.002, Z - 0.004, M.prismFilm);
  const prismB = mkLayer(-0.0018, 0.0001, X - 0.002, Z - 0.004, M.prismFilm);
  // FPC and board
  const board = hdmiBoard(); board.position.set(-X / 2 - 0.042, -0.0035, -0.006);
  const fpc = ribbon([[-X / 2 - 0.0032, -0.00075, -0.008], [-X / 2 - 0.010, -0.0008, -0.008], [-X / 2 - 0.016, -0.0005, -0.007], [-X / 2 - 0.019, -0.0012, -0.006]], 0.022, new THREE.Vector3(0, 0, 1), M.fpc);
  const fpcGroup = new THREE.Group(); fpcGroup.add(fpc);
  // Test image on the active area (working)
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(PANEL.activeZ, PANEL.activeX), new THREE.MeshBasicMaterial({ map: testPatternTexture(), toneMapped: false, transparent: true, opacity: 1 }));
  screen.rotation.set(-Math.PI / 2, 0, -Math.PI / 2); screen.position.y = 0.00026; screen.visible = false; L.frontPol.add(screen);
  const lgpGlow = new THREE.Mesh(new THREE.PlaneGeometry(Z - 0.006, X - 0.0015), new THREE.MeshBasicMaterial({ color: 0xbfe0ff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
  lgpGlow.rotation.set(-Math.PI / 2, 0, -Math.PI / 2); lgpGlow.position.y = 0.00085; lgp.add(lgpGlow);

  addPart(c, 'tray', 'Metal backlight tray', tray, new THREE.Vector3(0, -0.06, 0), 'Stamped steel frame that holds the stock backlight sheets.');
  addPart(c, 'reflector', 'Reflector sheet', reflector, new THREE.Vector3(0, -0.045, 0), 'White film that sends light escaping downward back into the light guide.');
  addPart(c, 'lgp', 'Light-guide plate', lgp, new THREE.Vector3(0, -0.032, 0), 'Acrylic plate; printed dots grow away from the LED edge so light leaves evenly.');
  addPart(c, 'ledStrip', 'Edge LED strip (18 LEDs)', ledStrip, new THREE.Vector3(0, -0.032, 0.02), 'Side-view LEDs on a flex strip along one long edge.');
  addPart(c, 'stockDiffuser', 'Stock diffuser sheet', diff, new THREE.Vector3(0, -0.02, 0), '');
  addPart(c, 'stockPrismA', 'Stock prism sheet 1', prismA, new THREE.Vector3(0, -0.012, 0), '');
  addPart(c, 'stockPrismB', 'Stock prism sheet 2', prismB, new THREE.Vector3(0, -0.006, 0), '');
  addPart(c, 'rearPol', 'Rear polariser', L.rearPol, new THREE.Vector3(0, 0.004, 0), 'Passes one linear polarisation into the cell.');
  addPart(c, 'tft', 'TFT glass with driver ICs', L.tft, new THREE.Vector3(0, 0.012, 0), 'One thin-film transistor per subpixel; the chip-on-glass drivers sit on the ledge.');
  addPart(c, 'lc', 'Liquid-crystal layer', L.lc, new THREE.Vector3(0, 0.02, 0), 'A few micrometres of liquid crystal, sealed between the two glasses.');
  addPart(c, 'cf', 'Colour-filter glass', L.cf, new THREE.Vector3(0, 0.028, 0), 'Red, green and blue filter stripes, one per subpixel.');
  addPart(c, 'frontPol', 'Front polariser', L.frontPol, new THREE.Vector3(0, 0.036, 0), 'Crossed with the rear polariser; the panel\'s output is linearly polarised.');
  addPart(c, 'fpc', 'Flexible printed circuit', fpcGroup, new THREE.Vector3(-0.01, 0.01, 0), '40-pin MIPI DSI flex from the glass to the board.');
  addPart(c, 'board', 'HDMI driver board', board, new THREE.Vector3(-0.03, 0, 0), 'HDMI-to-MIPI bridge; 5 V on micro-USB.');
  c.assembly = [
    { title: 'Backlight tray', parts: ['tray'], text: 'The stamped steel tray is the base of the stock module.' },
    { title: 'Reflector sheet', parts: ['reflector'], text: 'A white reflector lines the tray floor.' },
    { title: 'Light guide and edge LEDs', parts: ['lgp', 'ledStrip'], text: 'The light-guide plate drops in with the 18-LED flex strip against its long edge.' },
    { title: 'Stock optical sheets', parts: ['stockDiffuser', 'stockPrismA', 'stockPrismB'], text: 'Diffuser and two prism sheets even out and steer the light.' },
    { title: 'Cell: rear polariser', parts: ['rearPol'], text: 'The rear polariser sits on top of the stock sheets, under the cell glass.' },
    { title: 'Cell: TFT glass', parts: ['tft'], text: 'The transistor glass, with the chip-on-glass drivers on its ledge.' },
    { title: 'Cell: liquid crystal', parts: ['lc'], text: 'The liquid crystal fills the sealed gap between the glasses.' },
    { title: 'Cell: colour filters', parts: ['cf'], text: 'The colour-filter glass closes the cell.' },
    { title: 'Cell: front polariser', parts: ['frontPol'], text: 'The front polariser is crossed with the rear one.' },
    { title: 'Flex and driver board', parts: ['fpc', 'board'], text: 'The FPC plugs into the HDMI board\'s ZIF connector.' },
  ];
  c.fx = new THREE.Group(); c.fx.name = 'workingFX'; c.group.add(c.fx); c.fx.visible = false;
  const lab = labelSprite(['Stock backlight on', `${V.stock_panel} cd/m² at the panel (vendor)`, `${V.stock_ws} cd/m² at the eye: ${V.stock_pct} of the sky target`], 0.0045, { accent: '#ffb347' });
  lab.position.set(0, 0.02, 0); c.fx.add(lab);
  c.setWorking = (on) => { c.fx.visible = on; screen.visible = on; };
  c.update = (t, dt, s) => {
    const on = !!(s && s.working);
    ledMat.emissiveIntensity = on ? 2.2 : 0;
    lgpGlow.material.opacity = on ? 0.35 + 0.05 * Math.sin(t * 2) : 0;
    board.userData.led.material.emissiveIntensity = on ? 1.5 : 0;
  };
  return c;
}

// ---------------------------------------------------------------------------------------------------------------
// lcdCell (after teardown) with the pixel diorama
// ---------------------------------------------------------------------------------------------------------------
function buildPixelDiorama() {
  const g = new THREE.Group(); g.name = 'pixelDiorama';
  const sub = 0.018, len = 0.054, n = 3, W = sub * n;          // three subpixels along Z
  const y = { base: 0, rear: 0.008, tft: 0.016, lcLo: 0.022, lcHi: 0.032, cf: 0.040, front: 0.048, out: 0.066 };
  const glassMat = new THREE.MeshPhysicalMaterial({ color: 0xdfe8ee, roughness: 0.05, transparent: true, opacity: 0.18, depthWrite: false });
  const plate = (yy, th, mat) => { const m = slab(len, th, W, mat); m.position.y = yy; m.castShadow = false; g.add(m); return m; };
  // backlight surface
  plate(y.base, 0.002, new THREE.MeshBasicMaterial({ color: 0xfff6e8, toneMapped: false }));
  plate(y.rear, 0.0015, new THREE.MeshPhysicalMaterial({ color: 0xffffff, map: polHatchTexture(false), transparent: true, opacity: 0.55, depthWrite: false }));
  plate(y.tft, 0.002, glassMat);
  plate(y.cf, 0.002, glassMat);
  plate(y.front, 0.0015, new THREE.MeshPhysicalMaterial({ color: 0xffffff, map: polHatchTexture(true), transparent: true, opacity: 0.55, depthWrite: false }));
  // TFT: electrodes (interdigitated, IPS), gate and data lines, transistor per subpixel
  const ito = new THREE.MeshStandardMaterial({ color: 0x7fb6d8, metalness: 0.4, roughness: 0.3, transparent: true, opacity: 0.8 });
  for (let k = 0; k < n; k++) {
    const zc = -W / 2 + sub * (k + 0.5);
    for (let e = 0; e < 4; e++) { const s = slab(len * 0.82, 0.0004, 0.0012, ito); s.position.set(0, y.tft + 0.0012, zc - sub * 0.33 + e * sub * 0.22); g.add(s); }
    const tr = slab(0.004, 0.0012, 0.004, M.chip); tr.position.set(-len / 2 + 0.004, y.tft + 0.0016, zc + sub * 0.3); g.add(tr);
    const data = slab(len, 0.0005, 0.0008, M.gold); data.position.set(0, y.tft + 0.0012, zc + sub * 0.47); g.add(data);
  }
  const gate = slab(0.0008, 0.0005, W, M.gold); gate.position.set(-len / 2 + 0.0015, y.tft + 0.0012, 0); g.add(gate);
  // colour filters
  const cfCols = [0xe0352b, 0x2fbf4a, 0x2f5ae0];
  const filters = cfCols.map((col, k) => { const f = slab(len * 0.96, 0.0016, sub * 0.92, new THREE.MeshStandardMaterial({ color: col, transparent: true, opacity: 0.75, roughness: 0.3 })); f.position.set(0, y.cf, -W / 2 + sub * (k + 0.5)); g.add(f); return f; });
  // LC rods: in-plane switching rotates them about Y
  const rodMat = new THREE.MeshStandardMaterial({ color: 0x9fe4f2, roughness: 0.25, metalness: 0.1, transparent: true, opacity: 0.9 });
  const rodGeo = new THREE.CapsuleGeometry(0.0007, 0.0055, 4, 8); rodGeo.rotateZ(Math.PI / 2);
  const rods = [[], [], []];
  for (let k = 0; k < n; k++) for (let i = 0; i < 4; i++) for (let j = 0; j < 3; j++) for (const yy of [y.lcLo + 0.0025, y.lcHi - 0.0025]) {
    const r = new THREE.Mesh(rodGeo, rodMat);
    r.position.set(-len / 2 + len * (i + 0.5) / 4, yy, -W / 2 + sub * (k + 0.2 + 0.3 * j));
    g.add(r); rods[k].push(r);
  }
  // light columns and polarisation arrows per subpixel
  const beamMat = (col, op) => new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: op, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false });
  const columns = [];
  for (let k = 0; k < n; k++) {
    const zc = -W / 2 + sub * (k + 0.5);
    const lo = new THREE.Mesh(new THREE.CylinderGeometry(0.0022, 0.0022, y.cf - y.base, 12), beamMat(0xfff4e0, 0.35)); lo.position.set(0.012, (y.cf + y.base) / 2, zc); g.add(lo);
    const hi = new THREE.Mesh(new THREE.CylinderGeometry(0.0022, 0.0022, y.out - y.cf, 12), beamMat(cfCols[k], 0.6)); hi.position.set(0.012, (y.out + y.cf) / 2, zc); g.add(hi);
    const a0 = polArrow(0.010, 0xffffff); a0.position.set(-0.010, (y.rear + y.tft) / 2, zc); a0.setAngle(0); g.add(a0);
    const a1 = polArrow(0.010, 0xffd66b); a1.position.set(-0.010, (y.lcHi + y.cf) / 2, zc); g.add(a1);
    const a2 = polArrow(0.010, cfCols[k]); a2.position.set(-0.010, y.front + 0.008, zc); a2.setAngle(Math.PI / 2); g.add(a2);
    // voltage bar
    const bar = slab(0.002, 0.012, 0.004, new THREE.MeshBasicMaterial({ color: 0xffc04d, toneMapped: false })); bar.position.set(-len / 2 - 0.006, 0.006, zc); g.add(bar);
    columns.push({ lo, hi, a1, a2, bar });
  }
  // labels
  const lab = (text, yy) => { const s = labelSprite([text], 0.0026, { anchor: 'left' }); s.position.set(-len / 2, yy, W / 2 + 0.006); g.add(s); };
  lab('backlight (unpolarised)', y.base);
  lab('rear polariser, axis along X', y.rear);
  lab('TFT glass + IPS electrodes', y.tft);
  lab('liquid crystal: rotates with voltage', (y.lcLo + y.lcHi) / 2);
  lab('colour filters R G B', y.cf);
  lab('front polariser, axis along Z', y.front);
  const title = labelSprite([`One pixel, about ×${Math.round(sub / (R.PITCH_5 / 3000))}`, 'output is linearly polarised: orient it s to the windshield,', 'or add the half-wave retarder'], 0.0034, { accent: '#ffb347' });
  title.position.set(0, y.out + 0.006, 0); g.add(title);
  const update = (t) => {
    for (let k = 0; k < n; k++) {
      const v = 0.5 + 0.5 * Math.sin(t * 1.3 + k * 2.1);           // drive voltage, 0..1
      const theta = v * Math.PI / 4;                                 // IPS: molecules rotate up to 45 degrees in plane
      rods[k].forEach((r) => { r.rotation.y = -theta; });
      const T = Math.pow(Math.sin(2 * theta), 2);                    // half-wave cell between crossed polarisers
      columns[k].a1.setAngle(2 * theta);
      columns[k].hi.material.opacity = 0.08 + 0.7 * T;
      columns[k].a2.scale.setScalar(0.15 + 0.85 * Math.sqrt(T));
      columns[k].a2.userData.mat.opacity = 0.2 + 0.8 * T;
      columns[k].bar.scale.y = 0.1 + 0.9 * v; columns[k].bar.position.y = 0.006 * (0.1 + 0.9 * v);
    }
  };
  return { group: g, update };
}

export function buildLcdCell() {
  const c = makeComponent(THREE, {
    id: 'lcdCell',
    name: 'LCD cell after teardown (60 × 30 mm crop marked)',
    category: 'pgu',
    mount: 'centre of the 60 × 30 mm crop, on the front-polariser surface',
    size: [0.08, 0.002, 0.13],
    desc: 'The panel with its stock backlight removed. The cell makes no light: each subpixel is a voltage-controlled shutter between two crossed polarisers. Only a 60 × 30 mm crop in the middle is lit and drawn; the rest stays black.',
    working: 'In the zoomed pixel, the IPS liquid crystal rotates with each subpixel\'s voltage, turning the light\'s polarisation so it passes the front polariser; the output is linearly polarised.',
  });
  c.facts = [
    ['Crop', `${R.PGU_W} × ${R.PGU_H} mm = ${V.crop_px_w} × ${V.crop_px_h} px, ${V.crop_frac} of the panel`],
    ['Pixel pitch', `${V.pitch_5} µm (from the assumed active area)`],
    ['Resolution in the window', `${V.ppd2} px/deg, ${V.mm_per_px_75} mm per px at 7.5 m`],
    ['Cell transmittance', `${V.t_lcd} (ASSUMED; Phase 5 measures stock luminance ÷ backlight luminance)`],
    ['Contrast', `${V.cr_panel} (ASSUMED IPS); black at night ${V.black_night_eye} cd/m² at the eye`],
    ['Heat in the cell', `about ${V.p_abs_cell} absorbed over ${V.a_crop_cm2} cm² at full backlight`],
    ['Polarisation', 'linear; the axis is measured in Phase 5 (often 45° to the edges)'],
  ];
  const L = cellLayers();
  const fpc = new THREE.Group();
  fpc.add(ribbon([[-PANEL.outX / 2 - 0.0032, -0.00075, -0.008], [-PANEL.outX / 2 - 0.012, -0.0009, -0.008], [-PANEL.outX / 2 - 0.022, -0.004, -0.008]], 0.022, new THREE.Vector3(0, 0, 1), M.fpc));
  const conn = slab(0.004, 0.0006, 0.022, M.gold); conn.position.set(-PANEL.outX / 2 - 0.023, -0.0042, -0.008); fpc.add(conn);
  // crop marker on the front polariser
  const hz = PANEL.cropZ / 2, hx = PANEL.cropX / 2;
  const outline = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-hx, 0, -hz), new THREE.Vector3(-hx, 0, hz), new THREE.Vector3(hx, 0, hz), new THREE.Vector3(hx, 0, -hz)]), new THREE.LineBasicMaterial({ color: 0xffb347 }));
  outline.position.y = 0.0003; L.frontPol.add(outline);
  const cropLbl = textDecal(`60 × 30 mm crop · ${V.crop_px_w} × ${V.crop_px_h} px`, 0.05, { color: '#ffb347' }); cropLbl.rotation.set(-Math.PI / 2, 0, 0); cropLbl.position.set(hx + 0.006, 0.0003, 0); L.frontPol.add(cropLbl);
  addPart(c, 'tft', 'TFT glass with driver ICs', L.tft, new THREE.Vector3(0, -0.012, 0), 'The transistor substrate; drivers on the ledge.');
  addPart(c, 'lc', 'Liquid-crystal layer and seal', L.lc, new THREE.Vector3(0, -0.004, 0), 'Sealed between the glasses.');
  addPart(c, 'cf', 'Colour-filter glass', L.cf, new THREE.Vector3(0, 0.006, 0), 'RGB stripes and the black matrix.');
  addPart(c, 'rearPol', 'Rear polariser', L.rearPol, new THREE.Vector3(0, -0.022, 0), 'Laminated to the back of the TFT glass.');
  addPart(c, 'frontPol', 'Front polariser', L.frontPol, new THREE.Vector3(0, 0.016, 0), 'Laminated to the colour-filter glass; crossed with the rear.');
  addPart(c, 'fpc', 'FPC tail', fpc, new THREE.Vector3(-0.012, 0, 0), 'Unplugged from the board during teardown.');
  c.assembly = [
    { title: 'TFT substrate', parts: ['tft'], text: 'The cell is built on the transistor glass.' },
    { title: 'Liquid crystal and seal', parts: ['lc'], text: 'The liquid crystal is filled and sealed.' },
    { title: 'Colour-filter glass', parts: ['cf'], text: 'The filter glass closes the cell.' },
    { title: 'Rear polariser', parts: ['rearPol'], text: 'Laminated to the back.' },
    { title: 'Front polariser', parts: ['frontPol'], text: 'Laminated to the front, crossed with the rear.' },
    { title: 'Flex tail', parts: ['fpc'], text: 'The FPC stays bonded to the ledge.' },
  ];
  c.fx = new THREE.Group(); c.fx.name = 'workingFX'; c.group.add(c.fx); c.fx.visible = false;
  const dio = buildPixelDiorama(); dio.group.position.set(0, 0.004, PANEL.outZ / 2 + 0.05); c.fx.add(dio.group);
  // a thin leader from the crop to the diorama
  const leader = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0.0005, hz), new THREE.Vector3(0, 0.004, PANEL.outZ / 2 + 0.05 - 0.03)]), new THREE.LineDashedMaterial({ color: 0xffb347, dashSize: 0.002, gapSize: 0.0015 }));
  leader.computeLineDistances(); c.fx.add(leader);
  c.setWorking = (on) => { c.fx.visible = on; };
  c.update = (t, dt, s) => { if (s && s.working) dio.update(t); };
  return c;
}

// ---------------------------------------------------------------------------------------------------------------
// backlight
// ---------------------------------------------------------------------------------------------------------------
// Origin: centre of the top surface of the IR-cut glass. The stack runs downward to the fan.
const BL = (() => {
  const y = {};
  y.irTop = 0; y.irBot = -0.0011;
  y.bef2Bot = -0.0016; y.bef1Bot = -0.0021;
  y.diffTop = -0.0023; y.diffBot = -0.0043;
  y.cavTop = -0.0044; y.cavBot = -0.0264;
  y.boardTop = -0.0264; y.boardBot = -0.0280;
  y.padBot = -0.0285;
  y.hsTop = -0.0285; y.hsBaseBot = -0.0325; y.hsFinBot = -0.0485;
  y.fanTop = -0.0485; y.fanBot = -0.0585;
  return y;
})();
export const BACKLIGHT_DEPTH = -BL.fanBot;
const LEDS = (() => { const a = []; for (const x of [-0.0075, 0.0075]) for (const z of [-0.0225, -0.0075, 0.0075, 0.0225]) a.push([x, z]); return a; })();

export function buildBacklight() {
  const c = makeComponent(THREE, {
    id: 'backlight',
    name: 'Custom direct-lit LED backlight (behind the 60 × 30 mm crop)',
    category: 'pgu',
    mount: 'centre of the top surface of the IR-cut glass (the cell sits on it)',
    size: [0.05, BACKLIGHT_DEPTH, 0.08],
    desc: 'The stock edge-lit backlight gives a few hundred cd/m². This replacement lights only the crop, from directly behind: eight high-power white LEDs on an aluminium board, a white mixing cavity, a diffuser plate, two crossed prism films and an infrared-cut glass, cooled by a finned heat sink and a 40 mm fan.',
    working: 'The LEDs emit in all directions; the white cavity and diffuser even the light out, the crossed prism films send part of it back and bend the rest toward the ±15° cone the eye box needs.',
  });
  c.facts = [
    ['Design luminance at the panel', `${V.l_panel_design} cd/m²`],
    ['Backlight luminance', `${V.l_panel_design} ÷ ${V.t_lcd} cell (ASSUMED) = ${V.l_bl} cd/m²`],
    ['Flux', `Φ = π·L·A = ${V.phi_out} lm from ${V.a_crop_cm2} cm²`],
    ['LED power', `${V.p_led} at ${V.eta_bl} efficiency, ${V.led_lmw} lm/W (ASSUMED); ${V.p_led_film} with films`],
    ['Prism films', `crossed pair, gain ${V.gain_film} (ASSUMED; 3M about 1.5 per film)`],
    ['Emission cone needed', `±${V.cone_h}° × ±${V.cone_v}° (design ±${V.cone_design}°); Lambertian puts ${V.lamb_frac} inside`],
    ['Driver', 'constant current, analogue + PWM dimming above 2 kHz (Recom RCD-24 class)'],
    ['Price', costOf('Backlight')],
  ];
  const fanBuilt = fan40();
  const fanPart = new THREE.Group(); fanPart.position.y = BL.fanBot; fanBuilt.group.position.y = 0.005; fanPart.add(fanBuilt.group);
  for (const [x, z] of [[-0.016, -0.016], [0.016, -0.016], [0.016, 0.016], [-0.016, 0.016]]) { const s = screw(0.0012, 0.012); s.rotation.x = Math.PI; s.position.set(x, 0.0, z); fanPart.add(s); }

  // heat sink
  const hsMat = lmat({ color: 0x8b9097, metalness: 0.85, roughness: 0.4, emissive: 0xff6a20, emissiveIntensity: 0 });
  const hs = new THREE.Group(); hs.position.y = BL.hsFinBot;
  {
    const baseT = BL.hsTop - BL.hsBaseBot, finH = BL.hsBaseBot - BL.hsFinBot;
    const base = rbox(0.050, baseT, 0.080, 0.001, hsMat); base.position.y = finH + baseT / 2; hs.add(base);
    for (let i = 0; i < 13; i++) { const f = slab(0.050, finH, 0.0012, hsMat); f.position.set(0, finH / 2, -0.039 + i * 0.0065); hs.add(f); }
    const lbl = textDecal('Al 6063 · 80 × 50', 0.02, { color: '#2b2b2b' }); lbl.rotation.set(0, Math.PI / 2, 0); lbl.position.set(0.0252, finH + baseT / 2, 0); lbl.scale.setScalar(0.6); hs.add(lbl);
  }
  // thermal pad
  const pad = new THREE.Group(); pad.position.y = BL.padBot;
  { const m = slab(0.042, BL.boardBot - BL.padBot, 0.072, M.thermal); m.position.y = (BL.boardBot - BL.padBot) / 2; pad.add(m); }
  // LED board
  const ledMat = M.led(0xfff3dc, 0); ledMat.color.set(0xffd23a);
  const board = new THREE.Group(); board.position.y = BL.boardBot;
  const glows = [];
  {
    const th = BL.boardTop - BL.boardBot;
    const pcb = rbox(0.042, th, 0.072, 0.002, M.mcpcb); pcb.position.y = th / 2; board.add(pcb);
    for (const [x, z] of LEDS) {
      const led = powerLed(ledMat); led.position.set(x, th, z); board.add(led);
      const padL = slab(0.0015, 0.00005, 0.004, M.copper); padL.position.set(x - 0.0025, th, z); board.add(padL);
      const padR = padL.clone(); padR.position.x = x + 0.0025; board.add(padR);
      const gl = glowSprite(0.016); gl.position.set(x, th + 0.003, z); gl.visible = false; board.add(gl); glows.push(gl);
    }
    // series traces
    for (const x of [-0.0075, 0.0075]) { const tr = slab(0.0008, 0.00005, 0.047, M.copper); tr.position.set(x - 0.0035, th, 0); board.add(tr); }
    for (const [x, z] of [[-0.018, -0.033], [0.018, -0.033], [-0.018, 0.033], [0.018, 0.033]]) { const s = screw(0.0011, 0.004); s.position.set(x, th + 0.0013, z); board.add(s); }
    const wp = slab(0.006, 0.00005, 0.003, M.solder); wp.position.set(0, th, 0.034); board.add(wp);
    const silk = textDecal('8 × XP-G4  4S2P', 0.016, { color: '#555' }); silk.rotation.set(-Math.PI / 2, 0, -Math.PI / 2); silk.position.set(0.0165, th + 0.00003, 0); board.add(silk);
  }
  // LED leads to the driver
  const leads = new THREE.Group();
  leads.add(tube([[-0.0012, BL.boardTop + 0.0003, 0.0345], [-0.0012, BL.boardTop + 0.002, 0.042], [-0.0012, BL.boardTop - 0.004, 0.055], [-0.0012, BL.boardTop - 0.012, 0.064]], 0.0007, M.cableRed));
  leads.add(tube([[0.0012, BL.boardTop + 0.0003, 0.0345], [0.0012, BL.boardTop + 0.002, 0.042], [0.0012, BL.boardTop - 0.004, 0.055], [0.0012, BL.boardTop - 0.012, 0.064]], 0.0007, M.cableBlack));
  { const jst = rbox(0.006, 0.0045, 0.006, 0.0005, M.plasticWhite); jst.position.set(0, BL.boardTop - 0.0135, 0.067); leads.add(jst); }
  // mixing cavity (white walls, 2 mm thick, inner 60 x 30)
  const cavMat = new THREE.MeshStandardMaterial({ color: 0xf6f6f2, roughness: 0.95, transparent: true, opacity: 1 });
  const cav = new THREE.Group(); cav.position.y = BL.cavBot;
  {
    const H = BL.cavTop - BL.cavBot, t = 0.002, ix = 0.030, iz = 0.060;
    for (const [x, z, w, d] of [[0, iz / 2 + t / 2, ix + 2 * t, t], [0, -iz / 2 - t / 2, ix + 2 * t, t], [ix / 2 + t / 2, 0, t, iz], [-ix / 2 - t / 2, 0, t, iz]]) {
      const wall = slab(w, H, d, cavMat); wall.position.set(x, H / 2, z); cav.add(wall);
    }
    const tag = textDecal('mixing cavity 22 mm, white PTFE', 0.03, { color: '#666' }); tag.position.set(ix / 2 + t + 0.0001, H / 2, 0); tag.rotation.y = Math.PI / 2; tag.scale.setScalar(0.7); cav.add(tag);
  }
  // diffuser plate
  const diff = new THREE.Group(); diff.position.y = BL.diffBot;
  { const m = slab(0.034, BL.diffTop - BL.diffBot, 0.064, M.diffuser); m.position.y = (BL.diffTop - BL.diffBot) / 2; diff.add(m); }
  // prism films, crossed
  const bef1 = new THREE.Group(); bef1.position.y = BL.bef1Bot;
  { const m = prismFilm(0.034, 0.064, true, M.prismFilm); bef1.add(m); }
  const bef2 = new THREE.Group(); bef2.position.y = BL.bef2Bot;
  { const m = prismFilm(0.034, 0.064, false, M.prismFilm); bef2.add(m); }
  // IR-cut glass
  const ir = new THREE.Group(); ir.position.y = BL.irBot;
  { const m = slab(0.036, BL.irTop - BL.irBot, 0.066, M.irCut); m.position.y = (BL.irTop - BL.irBot) / 2; ir.add(m); }

  addPart(c, 'heatsink', 'Finned heat sink', hs, new THREE.Vector3(0, -0.03, 0), 'Aluminium, 80 × 50 mm; carries about 12 W of LED heat to the fan.');
  addPart(c, 'fan', '40 mm fan', fanPart, new THREE.Vector3(0, -0.07, 0), 'Draws cabin air through the fins and out of the housing base.');
  addPart(c, 'pad', 'Thermal pad', pad, new THREE.Vector3(0, -0.012, 0), 'Bonds the LED board to the heat sink.');
  addPart(c, 'ledBoard', 'LED board, 8 high-power white LEDs', board, new THREE.Vector3(0, 0.0, 0), 'XP-G class LEDs (158–195 lm/W at 700 mA) on an aluminium MCPCB.');
  addPart(c, 'leads', 'LED leads and connector', leads, new THREE.Vector3(0, 0, 0.03), 'To the constant-current driver.');
  addPart(c, 'cavity', 'White mixing cavity', cav, new THREE.Vector3(0, 0.03, 0), 'The LEDs are spaced less than the cavity depth so the spots merge.');
  addPart(c, 'diffuser', 'Diffuser plate', diff, new THREE.Vector3(0, 0.055, 0), 'Scatters the light so no LED spot shows through.');
  addPart(c, 'bef1', 'Prism film 1 (BEF)', bef1, new THREE.Vector3(0, 0.07, 0), 'Micro-prisms bend light toward the axis and recycle the rest.');
  addPart(c, 'bef2', 'Prism film 2 (BEF, crossed)', bef2, new THREE.Vector3(0, 0.083, 0), 'Rotated 90° so both directions are narrowed.');
  addPart(c, 'ircut', 'IR-cut glass', ir, new THREE.Vector3(0, 0.097, 0), 'Keeps infrared (LED and solar) off the cell.');
  c.assembly = [
    { title: 'Heat sink', parts: ['heatsink'], text: 'Everything is built up on the finned heat sink.' },
    { title: 'Fan', parts: ['fan'], text: 'The 40 mm fan screws to the fin side and vents through the housing base.' },
    { title: 'Thermal pad', parts: ['pad'], text: 'A thermal pad goes on the heat sink face.' },
    { title: 'LED board', parts: ['ledBoard'], text: 'Eight high-power white LEDs on an aluminium board, screwed down through the pad.' },
    { title: 'LED leads', parts: ['leads'], text: 'Two leads run to the constant-current driver.' },
    { title: 'Mixing cavity', parts: ['cavity'], text: 'A 22 mm white-walled cavity over the LEDs mixes their light.' },
    { title: 'Diffuser plate', parts: ['diffuser'], text: 'The diffuser closes the cavity.' },
    { title: 'Prism film 1', parts: ['bef1'], text: 'First brightness-enhancement film, prisms along one direction.' },
    { title: 'Prism film 2, crossed', parts: ['bef2'], text: 'Second film at 90° to the first.' },
    { title: 'IR-cut glass', parts: ['ircut'], text: 'The infrared-cut glass is the top of the stack; the cell sits on it.' },
  ];

  // ---- working visuals ----
  c.fx = new THREE.Group(); c.fx.name = 'workingFX'; c.group.add(c.fx); c.fx.visible = false;
  const NP = 420;
  const streaks = new Streaks(NP);
  c.fx.add(streaks.mesh);
  const st = { pos: new Float32Array(NP * 3), dir: new Float32Array(NP * 3), phase: new Uint8Array(NP), warm: false };
  const rand = rng(77);
  const tmp = [0, 0, 0];
  const coneH = 0.05;
  const designCone = new THREE.Mesh(new THREE.ConeGeometry(coneH * Math.tan(R.CONE_DESIGN * DEG), coneH, 40, 1, true),
    new THREE.MeshBasicMaterial({ color: 0x5ec8ff, transparent: true, opacity: 0.16, side: THREE.DoubleSide, depthWrite: false, toneMapped: false }));
  designCone.rotation.x = Math.PI; c.fx.add(designCone);
  const coneEdge = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.ConeGeometry(coneH * Math.tan(R.CONE_DESIGN * DEG), coneH, 12, 1, true)), new THREE.LineBasicMaterial({ color: 0x5ec8ff, transparent: true, opacity: 0.6 }));
  coneEdge.rotation.x = Math.PI; c.fx.add(coneEdge);
  const hemi = new THREE.Mesh(new THREE.SphereGeometry(coneH * 0.8, 32, 12, 0, Math.PI * 2, 0, Math.PI / 2),
    new THREE.MeshBasicMaterial({ color: 0xffd9a0, transparent: true, opacity: 0.05, side: THREE.DoubleSide, depthWrite: false, wireframe: true, toneMapped: false }));
  c.fx.add(hemi);
  const readout = labelSprite([
    'Backlight design (spec §7.5)',
    `${V.l_panel_design} cd/m² ÷ ${V.t_lcd} cell (ASSUMED) = ${V.l_bl} cd/m²`,
    `Φ = π·L·A = ${V.phi_out} lm from ${V.a_crop_cm2} cm²`,
    `${V.p_led} of LED at ${V.eta_bl}, ${V.led_lmw} lm/W; ${V.p_led_film} with films`,
    `Lambertian: ${V.lamb_frac} of the flux inside ±${V.cone_design}° (blue cone)`,
  ], 0.0042, { accent: '#ffb347' });
  c.fx.add(readout);
  const coneLbl = labelSprite([`design cone ±${V.cone_design}°`], 0.0035, { anchor: 'left', color: '#bfe8ff' });
  c.fx.add(coneLbl);

  const L = () => {                                                    // live layer heights (they move when exploded)
    const ly = (id, off) => c.parts.find((p) => p.id === id).object.position.y + off;
    return {
      ledTop: ly('ledBoard', BL.boardTop - BL.boardBot + 0.0024),
      diffBot: ly('diffuser', 0), diffTop: ly('diffuser', BL.diffTop - BL.diffBot),
      filmTop: ly('bef2', 0.0005), irTop: ly('ircut', BL.irTop - BL.irBot),
      cavDy: ly('cavity', 0) - BL.cavBot,
    };
  };
  const spawn = (i, ly) => {
    const [x, z] = LEDS[Math.floor(rand() * LEDS.length)];
    st.pos[i * 3] = x + (rand() - 0.5) * 0.002; st.pos[i * 3 + 1] = ly.ledTop; st.pos[i * 3 + 2] = z + (rand() - 0.5) * 0.002;
    lambert(rand, tmp); st.dir[i * 3] = tmp[0]; st.dir[i * 3 + 1] = tmp[1]; st.dir[i * 3 + 2] = tmp[2];
    st.phase[i] = 0;
  };
  const step = (dt, ly) => {
    const sp = 0.06;
    for (let i = 0; i < NP; i++) {
      const k = i * 3;
      let x = st.pos[k] + st.dir[k] * sp * dt, y = st.pos[k + 1] + st.dir[k + 1] * sp * dt, z = st.pos[k + 2] + st.dir[k + 2] * sp * dt;
      const ph = st.phase[i];
      if (ph === 0) {
        if (Math.abs(x) > 0.015) { x = Math.sign(x) * 0.015; lambert(rand, tmp); st.dir[k] = -Math.sign(x) * tmp[1]; st.dir[k + 1] = tmp[0]; st.dir[k + 2] = tmp[2]; }
        if (Math.abs(z) > 0.030) { z = Math.sign(z) * 0.030; lambert(rand, tmp); st.dir[k + 2] = -Math.sign(z) * tmp[1]; st.dir[k + 1] = tmp[0]; st.dir[k] = tmp[2]; }
        if (y < ly.ledTop - 0.0022) { y = ly.ledTop - 0.0022; lambert(rand, tmp); st.dir[k] = tmp[0]; st.dir[k + 1] = tmp[1]; st.dir[k + 2] = tmp[2]; }
        if (y >= ly.diffBot) { y = ly.diffTop; lambert(rand, tmp); st.dir[k] = tmp[0]; st.dir[k + 1] = tmp[1]; st.dir[k + 2] = tmp[2]; st.phase[i] = 1; }
      } else if (ph === 1) {
        if (y < ly.diffTop) { y = ly.diffTop; lambert(rand, tmp); st.dir[k] = tmp[0]; st.dir[k + 1] = tmp[1]; st.dir[k + 2] = tmp[2]; }
        x = clamp(x, -0.016, 0.016); z = clamp(z, -0.031, 0.031);
        if (y >= ly.filmTop) {
          if (rand() < 0.55) {                                        // refracted toward the axis by the crossed prisms
            const th = Math.abs(rand() + rand() + rand() - 1.5) * 0.38, phi = rand() * Math.PI * 2;
            st.dir[k] = Math.sin(th) * Math.cos(phi); st.dir[k + 1] = Math.cos(th); st.dir[k + 2] = Math.sin(th) * Math.sin(phi);
            y = ly.irTop; st.phase[i] = 2;
          } else {                                                     // totally reflected back: recycled
            y = ly.filmTop - 0.0002; lambert(rand, tmp); st.dir[k] = tmp[0]; st.dir[k + 1] = -tmp[1]; st.dir[k + 2] = tmp[2];
          }
        }
      } else if (y > ly.irTop + 0.045) { spawn(i, ly); continue; }
      st.pos[k] = x; st.pos[k + 1] = y; st.pos[k + 2] = z;
    }
  };
  const draw = () => {
    for (let i = 0; i < NP; i++) {
      const k = i * 3, ph = st.phase[i];
      const L0 = ph === 2 ? 0.006 : 0.003;
      const b = ph === 2 ? 1.0 : ph === 1 ? 0.75 : 0.55;
      streaks.set(i, st.pos[k], st.pos[k + 1], st.pos[k + 2], st.pos[k] - st.dir[k] * L0, st.pos[k + 1] - st.dir[k + 1] * L0, st.pos[k + 2] - st.dir[k + 2] * L0, b, b * 0.93, b * 0.8, 0.1);
    }
    streaks.commit();
  };
  let primed = false, level = 1;
  c.handles = { setLevel(x) { level = clamp(x, 0, 1); } };
  c.setWorking = (on) => { c.fx.visible = on; glows.forEach((g) => { g.visible = on; }); cavMat.opacity = on && c.fx.visible ? 0.28 : 1; cavMat.depthWrite = !(on && c.fx.visible); };
  c.update = (t, dt, s) => {
    const on = !!(s && s.working);
    const lv = on ? level : 0;
    ledMat.emissiveIntensity = 3.5 * lv;
    glows.forEach((g) => { g.material.opacity = lv; });
    hsMat.emissiveIntensity = 0.05 * lv * (0.9 + 0.1 * Math.sin(t * 0.7));
    fanBuilt.rotor.rotation.y += dt * 45 * (on ? 1 : 0);
    if (!on || !c.fx.visible) return;
    const ly = L();
    if (!primed) { for (let i = 0; i < NP; i++) spawn(i, ly); for (let j = 0; j < 240; j++) step(1 / 60, ly); primed = true; }
    step(Math.min(dt, 0.05), ly);
    draw();
    designCone.position.y = ly.irTop + coneH / 2; coneEdge.position.y = designCone.position.y;
    hemi.position.y = ly.irTop;
    readout.position.set(0, ly.irTop + coneH + 0.008, 0);
    coneLbl.position.set(0, ly.irTop + coneH * 0.9, coneH * Math.tan(R.CONE_DESIGN * DEG) + 0.003);
  };
  return c;
}

// ---------------------------------------------------------------------------------------------------------------
// retarder
// ---------------------------------------------------------------------------------------------------------------
export function buildRetarder() {
  const c = makeComponent(THREE, {
    id: 'retarder',
    name: 'Half-wave retarder film',
    category: 'pgu',
    mount: 'centre of the film\'s underside, laid over the crop',
    size: [0.04, 0.001, 0.07],
    desc: 'The windshield reflects s-polarised light (perpendicular to the plane of incidence) 19 times better than p. The panel already emits linearly polarised light, but its axis may sit at 45° to the edges. A half-wave film rotates that axis to s at no cost in brightness.',
    working: 'A half-wave film mirrors the polarisation about its fast axis: output angle = 2 × fast axis − input, so a 45° input with the fast axis at 67.5° leaves at 90°, which is s at the windshield.',
  });
  c.facts = [
    ['Windshield reflectance at 65°', `s ${V.rs65}, p ${V.rp65} (ratio ${V.rs65_x})`],
    ['Rule', 'output angle = 2 × fast-axis angle − input angle'],
    ['Needed when', 'the measured panel axis is not already along s (Phase 5)'],
    ['Sheet sources', 'Edmund WP280 600 × 500 mm about £324; Knight Optical 305 mm £213'],
    ['Price', costOf('retarder')],
  ];
  const film = new THREE.Group();
  { const m = slab(0.036, 0.0002, 0.066, M.retarder); m.position.y = 0.0001; film.add(m);
    const tab = slab(0.006, 0.0002, 0.012, M.retarder); tab.position.set(0.021, 0.0001, 0.026); film.add(tab);
    const mark = textDecal('FAST AXIS →', 0.012, { color: '#8fb5ff' }); mark.rotation.set(-Math.PI / 2, 0, 0); mark.position.set(0.021, 0.00025, 0.026); mark.scale.setScalar(0.6); film.add(mark); }
  const liner = new THREE.Group(); liner.position.y = -0.0002;
  { const m = slab(0.037, 0.0001, 0.067, M.plasticWhite); m.position.y = 0.00005; liner.add(m); }
  addPart(c, 'liner', 'Release liner', liner, new THREE.Vector3(0, -0.02, 0.0), 'Peeled off before the film goes on the panel.');
  addPart(c, 'film', 'Retarder film', film, new THREE.Vector3(0, 0.01, 0), 'Cut to cover the crop, fast axis set from the measured panel axis.');
  c.assembly = [
    { title: 'Peel the liner', parts: ['liner'], text: 'The release liner comes off.' },
    { title: 'Lay the film', parts: ['film'], text: 'The film goes over the crop with its fast axis at the angle the measurement gives.' },
  ];
  c.fx = new THREE.Group(); c.fx.name = 'workingFX'; c.group.add(c.fx); c.fx.visible = false;
  const inA = polArrow(0.03, 0xffffff); inA.position.y = -0.018; inA.setAngle(Math.PI / 4); c.fx.add(inA);
  const outA = polArrow(0.03, 0xffb347); outA.position.y = 0.02; c.fx.add(outA);
  const axis = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.0004, 0.0008), new THREE.MeshBasicMaterial({ color: 0x8fb5ff, toneMapped: false })); axis.position.y = 0.0006; c.fx.add(axis);
  const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.004, 0.004, 0.05, 16, 1, true), new THREE.MeshBasicMaterial({ color: 0xfff1d0, transparent: true, opacity: 0.12, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, toneMapped: false }));
  c.fx.add(beam);
  const lIn = labelSprite(['input 45° (panel polariser)'], 0.0035, { anchor: 'left' }); lIn.position.set(0, -0.018, 0.02); c.fx.add(lIn);
  let lOut = labelSprite(['output'], 0.0035, { anchor: 'left' }); lOut.position.set(0, 0.02, 0.02); c.fx.add(lOut);
  const lAx = labelSprite(['fast axis'], 0.0035, { anchor: 'left', color: '#bcd0ff' }); lAx.position.set(0, 0.003, 0.03); c.fx.add(lAx);
  let lastKey = '';
  c.setWorking = (on) => { c.fx.visible = on; };
  c.update = (t, dt, s) => {
    if (!(s && s.working)) return;
    const k = smoothstep(0, 1, 0.5 - 0.5 * Math.cos(t * 0.6));
    const fast = (45 + 22.5 * k) * DEG, inp = 45 * DEG;
    const out = 2 * fast - inp;
    axis.rotation.y = -fast; outA.setAngle(out);
    const deg = Math.round(out / DEG);
    const Rw = R.RS65 * Math.sin(out) ** 2 + R.RP65 * Math.cos(out) ** 2;
    const key = `${deg}`;
    if (key !== lastKey) {
      lastKey = key;
      const pos = lOut.position.clone();
      c.fx.remove(lOut); lOut.material.map.dispose(); lOut.material.dispose();
      lOut = labelSprite([`output ${deg}°${deg === 90 ? ' = s' : ''}`, `windshield reflects ${(Rw * 100).toFixed(1)}%`, `(s ${V.rs65}, p ${V.rp65})`], 0.0035, { anchor: 'left', accent: deg === 90 ? '#4fd18b' : '#ffb347' });
      lOut.position.copy(pos); c.fx.add(lOut);
    }
  };
  return c;
}

// ---------------------------------------------------------------------------------------------------------------
// pgu (assembled)
// ---------------------------------------------------------------------------------------------------------------
export function buildPgu() {
  const c = makeComponent(THREE, {
    id: 'pgu',
    name: 'Picture generation unit (assembled)',
    category: 'pgu',
    mount: 'centre of the 60 × 30 mm crop on the front-polariser surface (place at geom.PANEL_C)',
    size: [0.14, 0.064, 0.13],
    desc: 'The finished picture generator: the stock cell on the custom backlight, the half-wave retarder on top if the axis needs it, an NTC thermistor on the cell\'s back for the controller\'s derating, and the HDMI board on a bracket. Only the crop is lit and drawn; the rest of the panel is black.',
    working: 'The LEDs light the crop from behind and the crop shows the HUD frame the Jetson renders, mirrored as three reflections require; the fan runs and the heat sink warms.',
  });
  c.facts = [
    ['Panel luminance (design)', `${V.l_panel_design} cd/m² on axis; uniformity ±20% over the crop`],
    ['At the eye', `${V.bl_ws} cd/m² (path ${V.path_ws}: two 90% mirrors × ${V.rs65} glass)`],
    ['Image', `${V.crop_px_w} × ${V.crop_px_h} px of 1920 × 1080 at 60 Hz over HDMI`],
    ['Cell temperature', 'thermistor derates, then blanks; 30 min at full power in a 40 °C box must stay under the rating'],
    ['Black level', `${V.black_day_eye} cd/m² at the eye by day, ${V.black_night_eye} at night (IPS ${V.cr_panel}, ASSUMED)`],
    ['Heat', `${V.p_led} LED, about ${V.p_abs_cell} absorbed in the cell`],
  ];
  const bl = buildBacklight();
  bl.group.name = 'backlightUnit';
  bl.group.position.y = -0.0020;
  const L = cellLayers();
  const cell = new THREE.Group(); cell.name = 'cellUnit';
  Object.values(L).forEach((g) => cell.add(g));
  const crop = cropPlane(hudPlaceholderTexture()); crop.position.y = 0.0004; cell.add(crop);
  const ntc = new THREE.Group();
  {
    const bead = sphere(0.0011, M.plasticBlack, 12); bead.scale.set(1, 0.7, 1); bead.position.set(0, -0.0024, 0.036); ntc.add(bead);
    const tape = slab(0.007, 0.00006, 0.006, new THREE.MeshStandardMaterial({ color: 0xd59a2a, transparent: true, opacity: 0.8, roughness: 0.4 })); tape.position.set(0, -0.0016, 0.036); ntc.add(tape);
    ntc.add(tube([[0, -0.0024, 0.0372], [0.001, -0.004, 0.042], [0.004, -0.012, 0.05], [0.008, -0.03, 0.054]], 0.0003, M.cableRed));
    ntc.add(tube([[0, -0.0024, 0.0372], [-0.001, -0.004, 0.042], [0.002, -0.012, 0.051], [0.006, -0.03, 0.055]], 0.0003, M.cableBlack));
  }
  const ret = new THREE.Group();
  { const m = slab(0.036, 0.0002, 0.066, M.retarder); m.position.y = 0.00025; ret.add(m); }
  // bracket on the heat sink with standoffs, and the board
  const bracket = new THREE.Group();
  const hsBaseY = -0.0020 + BL.hsBaseBot;
  {
    const plate = slab(0.004, 0.022, 0.05, M.aluDark); plate.position.set(-0.027, hsBaseY - 0.004, 0); bracket.add(plate);
    const arm = slab(0.05, 0.002, 0.05, M.aluDark); arm.position.set(-0.05, hsBaseY - 0.014, 0); bracket.add(arm);
    for (const [x, z] of [[-0.069, -0.022], [-0.069, 0.022], [-0.031, -0.022], [-0.031, 0.022]]) { const so = cyl(0.0022, 0.0022, 0.006, M.gold, 6); so.position.set(x, hsBaseY - 0.010, z); bracket.add(so); }
    for (const z of [-0.012, 0.012]) { const s = screw(0.0011, 0.004); s.rotation.z = Math.PI / 2; s.position.set(-0.0292, hsBaseY - 0.004, z); bracket.add(s); }
  }
  const board = hdmiBoard(); board.position.set(-0.05, hsBaseY - 0.007, 0);
  const fpc = new THREE.Group();
  fpc.add(ribbon([[-PANEL.outX / 2 - 0.0032, -0.00075, -0.008], [-PANEL.outX / 2 - 0.009, -0.0015, -0.008], [-PANEL.outX / 2 - 0.011, -0.012, -0.006], [-0.03 + 0.004, hsBaseY - 0.005, -0.002]], 0.022, new THREE.Vector3(0, 0, 1), M.fpc));

  addPart(c, 'backlight', 'Custom backlight', bl.group, new THREE.Vector3(0, -0.06, 0), 'Heat sink, fan, LEDs, cavity, diffuser, prism films, IR-cut glass.');
  addPart(c, 'ntc', 'NTC thermistor on the cell back', ntc, new THREE.Vector3(0, -0.012, 0.03), '10 kΩ NTC taped to the cell beside the crop, read by the controller.');
  addPart(c, 'cell', 'LCD cell with the crop', cell, new THREE.Vector3(0, 0.02, 0), 'The stock cell on the IR-cut glass, crop centred over the cavity.');
  addPart(c, 'retarder', 'Half-wave retarder', ret, new THREE.Vector3(0, 0.04, 0), 'Rotates the output polarisation to s if the measured axis needs it.');
  addPart(c, 'bracket', 'Board bracket and standoffs', bracket, new THREE.Vector3(-0.03, -0.03, 0), 'Screws to the heat sink base.');
  addPart(c, 'board', 'HDMI driver board', board, new THREE.Vector3(-0.05, -0.04, 0), 'HDMI in from the Jetson, 1920 × 1080 at 60 Hz.');
  addPart(c, 'fpc', 'Panel FPC', fpc, new THREE.Vector3(-0.03, 0.0, 0), 'Reconnected after the teardown.');
  c.assembly = [
    { title: 'Backlight unit', parts: ['backlight'], text: 'The finished backlight is the base of the PGU.' },
    { title: 'Thermistor', parts: ['ntc'], text: 'The NTC is taped to the cell\'s back beside the crop, where it reads the hottest glass the backlight sees.' },
    { title: 'LCD cell', parts: ['cell'], text: 'The cell, stripped of its stock backlight, lies on the IR-cut glass with the 60 × 30 mm crop over the cavity.' },
    { title: 'Retarder', parts: ['retarder'], text: 'If the Phase 5 measurement says the axis is wrong, the half-wave film goes over the crop.' },
    { title: 'Board bracket', parts: ['bracket'], text: 'A bracket on the heat sink carries the board on four standoffs.' },
    { title: 'HDMI board', parts: ['board'], text: 'The driver board mounts on the standoffs.' },
    { title: 'Flex reconnected', parts: ['fpc'], text: 'The panel flex plugs back into the board.' },
  ];
  let level = 1, working = false;
  c.fx = new THREE.Group(); c.fx.name = 'workingFX'; c.group.add(c.fx); c.fx.visible = false;
  const glow = glowSprite(0.07, 0xfff0d8); glow.position.y = 0.002; glow.material.opacity = 0.18; c.fx.add(glow);
  const applyLevel = () => { crop.material.color.setScalar(0.08 + 0.92 * (working ? level : 0.35)); };
  applyLevel();
  c.handles = {
    setPanelTexture(tex) { crop.material.map = tex; crop.material.needsUpdate = true; },
    setBacklight(x) { level = clamp(x, 0, 1); bl.handles.setLevel(level); applyLevel(); },
    crop, backlight: bl,
  };
  c.setWorking = (on) => { working = on; c.fx.visible = on; bl.setWorking(on); bl.fx.visible = false; applyLevel(); };
  c.update = (t, dt, s) => {
    bl.update(t, dt, { working: !!(s && s.working) });
    if (s && s.working) board.userData.led.material.emissiveIntensity = 1.5;
  };
  return c;
}
