// Electronics: the Jetson, the hud/ software graph, the RP2040 controller, LED driver, power, network and displays.
// Also exports the small modelling helpers (ports, LEDs, live panels) that sensors.js and instruments.js reuse.
import * as THREE from 'three';
import { M } from '../mats.js';
import { rbox, box, cyl, cylX, cylZ, sphere, tube, canvasTexture, textDecal, rng, DEG, clamp, lerp } from '../util.js';
import { makeComponent, addPart } from './contract.js';
import { P, R } from '../params.js';

export const FONT = '"Helvetica Neue", Helvetica, Arial, sans-serif';
export const vec = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);

// ---- helpers ------------------------------------------------------------------
// Place obj in parent. Rotation is set only when given, so pre-oriented objects (cylX, decals) keep theirs.
export function put(parent, obj, x = 0, y = 0, z = 0, rx, ry, rz) {
  obj.position.set(x, y, z);
  if (rx !== undefined || ry !== undefined || rz !== undefined) obj.rotation.set(rx || 0, ry || 0, rz || 0);
  parent.add(obj); return obj;
}

const matCache = new Map();
export function mat(key, make) { if (!matCache.has(key)) matCache.set(key, make()); return matCache.get(key); }
export const MX = {
  get usbBlue() { return mat('usbBlue', () => M.color(0x2a6fdb, 0.5)); },
  get brass() { return mat('brass', () => M.color(0xc9a24a, 0.35, 1)); },
  get capTan() { return mat('capTan', () => M.color(0xb59a6a, 0.5)); },
  get jstWhite() { return mat('jst', () => M.color(0xeeeae0, 0.6)); },
  get termGreen() { return mat('term', () => M.color(0x2d8a4a, 0.55)); },
  get fr4() { return mat('fr4', () => new THREE.MeshStandardMaterial({ map: perfTexture(), roughness: 0.7 })); },
  get redPlastic() { return mat('redP', () => M.color(0xb3262e, 0.5)); },
  get yellowWire() { return mat('yelW', () => M.color(0xe6c229, 0.55)); },
  get epoxy() { return mat('epoxy', () => M.color(0x0b0b0c, 0.15, 0.1)); },
  get ferrite() { return mat('ferr', () => M.color(0x2b2b2e, 0.7)); },
  get coil() { return mat('coil', () => M.color(0xb86b35, 0.35, 1)); },
  get electrolytic() { return mat('elec', () => M.color(0x1d2f5a, 0.4, 0.2)); },
  get sticker() { return mat('stick', () => M.color(0xe6e8ea, 0.6)); },
  get greyPlastic() { return mat('gp', () => M.color(0x34373c, 0.55)); },
  get silverPlastic() { return mat('sp', () => M.color(0xa9adb3, 0.4, 0.4)); },
  get darkGlass() { return mat('dg', () => new THREE.MeshPhysicalMaterial({ color: 0x050608, roughness: 0.05, metalness: 0.2, clearcoat: 1 })); },
};

function perfTexture() {
  return canvasTexture(256, 256, (ctx, W, H) => {
    ctx.fillStyle = '#b98c4e'; ctx.fillRect(0, 0, W, H);
    for (let y = 8; y < H; y += 16) for (let x = 8; x < W; x += 16) {
      ctx.fillStyle = '#d7a660'; ctx.beginPath(); ctx.arc(x, y, 5.5, 0, 7); ctx.fill();
      ctx.fillStyle = '#2a1d10'; ctx.beginPath(); ctx.arc(x, y, 2.4, 0, 7); ctx.fill();
    }
  }, { repeat: [2, 2] });
}

export function cost(prefix) {
  const row = P.COST.find((r) => r[0].startsWith(prefix));
  if (!row) return 'owned';
  const [name, lo, hi, tag] = row;
  const price = lo === hi ? `$${lo.toLocaleString('en-US')}` : `$${lo.toLocaleString('en-US')}–${hi.toLocaleString('en-US')}`;
  return `${price} (${tag}; plan line "${name}", last seen 2026-10-21)`;
}

// Text decal oriented so its readable side faces the given local direction.
export function decal(text, w, face = '+x', opts = {}) {
  const m = textDecal(text, w, opts);
  const rot = { '+x': [0, Math.PI / 2, 0], '-x': [0, -Math.PI / 2, 0], '+z': [0, 0, 0], '-z': [0, Math.PI, 0], '+y': [-Math.PI / 2, 0, 0], '-y': [Math.PI / 2, 0, 0] }[face];
  m.rotation.set(...rot);
  m.renderOrder = 3;
  return m;
}

export function instanced(geo, material, transforms) {
  const im = new THREE.InstancedMesh(geo, material, Math.max(1, transforms.length));
  const o = new THREE.Object3D();
  transforms.forEach((t, i) => {
    o.position.set(t[0], t[1], t[2]); o.rotation.set(t[3] || 0, t[4] || 0, t[5] || 0); o.scale.set(t[6] ?? 1, t[7] ?? 1, t[8] ?? 1);
    o.updateMatrix(); im.setMatrixAt(i, o.matrix);
  });
  im.count = transforms.length;
  im.castShadow = true; im.receiveShadow = true;
  im.instanceMatrix.needsUpdate = true;
  return im;
}

// Random small SMD parts on a board top at height y (resistors, capacitors, SOT packages).
export function smd(w, d, n, seed, y, avoid = []) {
  const r = rng(seed); const g = new THREE.Group();
  const a = [], b = [], s = [];
  for (let i = 0; i < n; i++) {
    const x = (r() - 0.5) * w * 0.92, z = (r() - 0.5) * d * 0.92;
    if (avoid.some(([ax, az, aw, ad]) => Math.abs(x - ax) < aw / 2 && Math.abs(z - az) < ad / 2)) continue;
    const rot = r() > 0.5 ? Math.PI / 2 : 0; const k = r();
    if (k < 0.45) a.push([x, y + 0.00025, z, 0, rot, 0]);
    else if (k < 0.85) b.push([x, y + 0.00025, z, 0, rot, 0]);
    else s.push([x, y + 0.0006, z, 0, rot, 0]);
  }
  if (a.length) g.add(instanced(new THREE.BoxGeometry(0.0016, 0.0005, 0.0008), M.chip, a));
  if (b.length) g.add(instanced(new THREE.BoxGeometry(0.001, 0.0005, 0.0005), MX.capTan, b));
  if (s.length) g.add(instanced(new THREE.BoxGeometry(0.0029, 0.0011, 0.0016), M.chip, s));
  return g;
}

// IC package with an optional label on top. Sits on y = 0.
export function chip(w, d, h = 0.0009, label = '', labelW = 0) {
  const g = new THREE.Group();
  put(g, box(w, h, d, M.chip), 0, h / 2, 0);
  if (label) put(g, decal(label, labelW || w * 0.8, '+y', { color: '#c9ccd1', font: '500 48px ' + FONT }), 0, h + 0.00005, 0);
  return g;
}

let glowTex = null;
export function glowTexture() {
  if (!glowTex) glowTex = canvasTexture(64, 64, (ctx, W, H) => {
    const gr = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.25, 'rgba(255,255,255,0.55)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H);
  });
  return glowTex;
}
export function glow(color, size, opacity = 1) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity, toneMapped: false }));
  s.scale.set(size, size, 1); s.renderOrder = 8;
  return s;
}

// Small LED with a glow sprite. led.userData.set(level 0..1).
export function led(color, w = 0.0016, h = 0.0006, d = 0.0008) {
  const m = M.led(color, 0);
  const mesh = box(w, h, d, m);
  const g = glow(color, Math.max(w, d) * 7); g.visible = false; mesh.add(g);
  mesh.userData.set = (k) => { m.emissiveIntensity = k * 3; g.visible = k > 0.03; g.material.opacity = Math.min(1, k); };
  return mesh;
}

// Ports: opening faces +X, origin at the centre of the opening, body extends toward -X.
export const Port = {
  usbA({ blue = true } = {}) {
    const g = new THREE.Group();
    put(g, box(0.014, 0.0058, 0.0132, M.steel), -0.007, 0, 0);
    put(g, box(0.0004, 0.0047, 0.0121, M.flock), 0.0001, 0, 0);
    put(g, box(0.0006, 0.0018, 0.0108, blue ? MX.usbBlue : M.plasticBlack), 0.00035, 0.0009, 0);
    return g;
  },
  usbAStack(blue = true) {
    const g = new THREE.Group();
    put(g, box(0.015, 0.0152, 0.0145, M.steel), -0.0075, 0, 0);
    put(g, Port.usbA({ blue }), 0.0001, 0.0036, 0);
    put(g, Port.usbA({ blue }), 0.0001, -0.0036, 0);
    return g;
  },
  hdmi() {
    const g = new THREE.Group();
    put(g, box(0.011, 0.0062, 0.0152, M.steel), -0.0055, 0, 0);
    put(g, box(0.0004, 0.0048, 0.0138, M.flock), 0.0001, 0.0002, 0);
    put(g, box(0.0006, 0.0012, 0.0110, M.plasticBlack), 0.00035, 0.0004, 0);
    return g;
  },
  usbC() {
    const g = new THREE.Group();
    put(g, rbox(0.007, 0.0033, 0.009, 0.0015, M.steel, 2), -0.0035, 0, 0);
    put(g, rbox(0.0004, 0.0025, 0.0082, 0.0011, M.flock, 2), 0.0001, 0, 0);
    put(g, box(0.0006, 0.0007, 0.0066, M.plasticBlack), 0.00035, 0, 0);
    return g;
  },
  microUsb() {
    const g = new THREE.Group();
    put(g, box(0.005, 0.0027, 0.0076, M.steel), -0.0025, 0, 0);
    put(g, box(0.0004, 0.0019, 0.0066, M.flock), 0.0001, 0, 0);
    put(g, box(0.0005, 0.0006, 0.005, M.plasticBlack), 0.0003, 0.0004, 0);
    return g;
  },
  rj45() {
    const g = new THREE.Group();
    put(g, box(0.021, 0.0136, 0.0160, M.steel), -0.0105, 0, 0);
    put(g, box(0.0004, 0.0086, 0.0118, M.flock), 0.0001, -0.0012, 0);
    for (let i = 0; i < 8; i++) put(g, box(0.0003, 0.0002, 0.0005, M.gold), 0.0003, 0.0022, -0.0045 + i * 0.0013);
    const l1 = put(g, led(0x35e06a, 0.0002, 0.002, 0.0028), 0.0003, 0.0052, -0.0055, 0, 0, 0);
    const l2 = put(g, led(0xffb020, 0.0002, 0.002, 0.0028), 0.0003, 0.0052, 0.0055, 0, 0, 0);
    g.userData.leds = [l1, l2];
    return g;
  },
  dcJack() {
    const g = new THREE.Group();
    put(g, box(0.014, 0.011, 0.009, M.plasticBlack), -0.007, 0, 0);
    put(g, cylX(0.0032, 0.0004, M.flock, 20), 0.0001, 0, 0);
    put(g, cylX(0.001, 0.006, M.gold, 12), -0.0025, 0, 0);
    return g;
  },
  sma() {
    const g = new THREE.Group();
    put(g, cylX(0.0045, 0.002, MX.brass, 6), -0.001, 0, 0);
    put(g, cylX(0.003, 0.008, MX.brass, 20), 0.003, 0, 0);
    put(g, cylX(0.0021, 0.0003, M.plasticWhite, 16), 0.0071, 0, 0);
    put(g, cylX(0.00045, 0.001, M.gold, 8), 0.0072, 0, 0);
    return g;
  },
};

// JST-SH / Qwiic style connector, opening faces +X, sits on y = 0.
export function jst(n, white = true) {
  const g = new THREE.Group();
  const len = 0.001 * (n - 1) + 0.003;
  put(g, box(0.0042, 0.0029, len, white ? MX.jstWhite : M.plasticBlack), -0.0021, 0.00145, 0);
  put(g, box(0.0003, 0.0018, len - 0.0012, M.flock), 0.00005, 0.0016, 0);
  return g;
}

// Male pin header along Z, base on y = 0, pins up.
export function header(n, rows = 1, pitch = 0.00254) {
  const g = new THREE.Group();
  put(g, box(rows * pitch, 0.0025, n * pitch, M.plasticBlack), 0, 0.00125, 0);
  const t = [];
  for (let r = 0; r < rows; r++) for (let i = 0; i < n; i++) t.push([(r - (rows - 1) / 2) * pitch, 0.0025, (i - (n - 1) / 2) * pitch]);
  const geo = new THREE.BoxGeometry(0.00064, 0.0085, 0.00064); geo.translate(0, 0.0015, 0);
  g.add(instanced(geo, M.gold, t));
  return g;
}

// Screw terminal block along Z, base on y = 0, wire entries facing +X.
export function screwTerminal(n, pitch = 0.00508) {
  const g = new THREE.Group();
  put(g, box(0.0078, 0.010, n * pitch, MX.termGreen), 0, 0.005, 0);
  for (let i = 0; i < n; i++) {
    const z = (i - (n - 1) / 2) * pitch;
    put(g, cyl(0.0017, 0.0017, 0.0008, M.steel, 16), -0.0008, 0.0102, z);
    put(g, box(0.0036, 0.0004, 0.0005, M.flock), -0.0008, 0.0107, z);
    put(g, box(0.0004, 0.0035, 0.0034, M.flock), 0.0039, 0.0035, z);
  }
  return g;
}

// Axial fan, axis along Y, centred. fan.userData.rotor spins about Y.
export function axialFan(size, thick, blades = 7, frameMat = M.plasticBlack, bladeMat = M.plasticBlack) {
  const g = new THREE.Group();
  const h = size / 2;
  const s = new THREE.Shape(); s.moveTo(-h, -h); s.lineTo(h, -h); s.lineTo(h, h); s.lineTo(-h, h); s.lineTo(-h, -h);
  const hole = new THREE.Path(); hole.absarc(0, 0, size * 0.47, 0, Math.PI * 2, true); s.holes.push(hole);
  const geo = new THREE.ExtrudeGeometry(s, { depth: thick, bevelEnabled: false, curveSegments: 40 });
  geo.translate(0, 0, -thick / 2); geo.rotateX(Math.PI / 2);
  const frame = new THREE.Mesh(geo, frameMat); frame.castShadow = true; g.add(frame);
  for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) put(g, cyl(size * 0.035, size * 0.035, thick * 1.02, M.flock, 12), sx * h * 0.82, 0, sz * h * 0.82);
  // struts
  for (let i = 0; i < 3; i++) { const st = box(size * 0.47, thick * 0.25, size * 0.025, frameMat); st.position.y = -thick * 0.38; st.rotation.y = i * 2.094; st.translateX(size * 0.235); g.add(st); }
  const rotor = new THREE.Group(); g.add(rotor);
  put(rotor, cyl(size * 0.16, size * 0.16, thick * 0.8, bladeMat, 32), 0, 0, 0);
  put(rotor, cyl(size * 0.12, size * 0.12, 0.0003, M.plasticWhite, 32), 0, thick * 0.4 + 0.0002, 0);
  for (let i = 0; i < blades; i++) {
    const piv = new THREE.Group(); piv.rotation.y = (i / blades) * Math.PI * 2; rotor.add(piv);
    const b = box(size * 0.30, thick * 0.65, 0.0008, bladeMat); b.position.x = size * 0.31; b.rotation.x = 0.55; piv.add(b);
  }
  g.userData.rotor = rotor;
  return g;
}

// Raspberry Pi Pico (51 x 21 mm), PCB centred at origin with its top at y = 0.001, micro-USB at +X.
export function pico() {
  const g = new THREE.Group();
  const pcb = put(g, box(0.051, 0.001, 0.021, M.pcbGreen), 0, 0.0005, 0);
  pcb.material = mat('picoGreen', () => new THREE.MeshStandardMaterial({ color: 0x1f8a4c, roughness: 0.5 }));
  const pads = [];
  for (let i = 0; i < 20; i++) for (const s of [-1, 1]) pads.push([-0.0241 + i * 0.00254, 0.0005, s * 0.0102]);
  g.add(instanced(new THREE.CylinderGeometry(0.0008, 0.0008, 0.00105, 10), M.gold, pads));
  put(g, chip(0.007, 0.007, 0.0009, 'RP2040', 0.006), -0.002, 0.001, 0);
  put(g, chip(0.0052, 0.004, 0.0013, 'W25Q16', 0.004), 0.008, 0.001, 0.003);
  put(g, box(0.0032, 0.0008, 0.0025, M.steel), -0.009, 0.0014, 0.004);
  put(g, Port.microUsb(), 0.0255, 0.0024, 0);
  put(g, box(0.0035, 0.0012, 0.0045, M.plasticWhite), 0.013, 0.0016, -0.0045);
  put(g, cyl(0.0012, 0.0012, 0.0008, M.plasticWhite, 12), 0.013, 0.0024, -0.0045);
  const l = put(g, led(0x46ff7a), 0.019, 0.0013, -0.0068);
  g.userData.led = l;
  put(g, smd(0.040, 0.016, 30, 42, 0.001, [[-0.002, 0, 0.009, 0.009], [0.008, 0.003, 0.007, 0.006], [0.02, 0, 0.012, 0.01]]), -0.004, 0, 0);
  put(g, decal('Raspberry Pi Pico', 0.016, '+y', { color: '#f2f2f2', font: '600 48px ' + FONT }), -0.012, 0.00102, -0.0066);
  return g;
}

// Canvas-backed info panel. Sprite by default (always faces the camera).
export function livePanel(pxW, pxH, worldW, { sprite = true } = {}) {
  const cv = document.createElement('canvas'); cv.width = pxW; cv.height = pxH;
  const ctx = cv.getContext('2d');
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
  const worldH = worldW * pxH / pxW;
  let obj;
  if (sprite) {
    obj = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false, toneMapped: false }));
    obj.scale.set(worldW, worldH, 1);
  } else {
    obj = new THREE.Mesh(new THREE.PlaneGeometry(worldW, worldH), new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, toneMapped: false, side: THREE.DoubleSide }));
  }
  obj.renderOrder = 30;
  const p = { obj, ctx, tex, W: pxW, H: pxH, worldH, acc: 1, draw(fn) { ctx.clearRect(0, 0, pxW, pxH); fn(ctx, pxW, pxH); tex.needsUpdate = true; } };
  // Redraw at most `hz` times a second.
  p.tick = (dt, hz, fn) => { p.acc += dt; if (p.acc >= 1 / hz) { p.acc = 0; p.draw(fn); } };
  return p;
}

export function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
export function panelBg(ctx, W, H, title, sub) {
  ctx.fillStyle = 'rgba(9,13,19,0.9)'; roundRect(ctx, 2, 2, W - 4, H - 4, 18); ctx.fill();
  ctx.strokeStyle = 'rgba(110,170,230,0.55)'; ctx.lineWidth = 2; ctx.stroke();
  ctx.textBaseline = 'top'; ctx.textAlign = 'left';
  if (title) { ctx.fillStyle = '#eef4fa'; ctx.font = `600 30px ${FONT}`; ctx.fillText(title, 22, 18); }
  if (sub) { ctx.fillStyle = '#8fa3b6'; ctx.font = `400 21px ${FONT}`; ctx.fillText(sub, 22, 54); }
}
export function txt(ctx, s, x, y, { size = 22, color = '#cdd8e3', weight = 400, align = 'left', base = 'middle' } = {}) {
  ctx.font = `${weight} ${size}px ${FONT}`; ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = base; ctx.fillText(s, x, y);
}
export function lamp(ctx, x, y, on, color, label) {
  ctx.beginPath(); ctx.arc(x, y, 10, 0, 7); ctx.fillStyle = on ? color : 'rgba(120,130,140,0.25)'; ctx.fill();
  if (on) { ctx.beginPath(); ctx.arc(x, y, 16, 0, 7); ctx.fillStyle = color.replace('rgb', 'rgba').replace(')', ',0.25)'); ctx.fill(); }
  txt(ctx, label, x + 24, y, { size: 21, color: on ? '#eef4fa' : '#7d8b98' });
}

// Cable (tube) helper with a material.
export function cable(points, r, material) { return tube(points.map((p) => (Array.isArray(p) ? vec(...p) : p)), r, material, 48); }

// Visible-only bounding box (working visuals are hidden children).
export function visibleBox(obj) {
  const b = new THREE.Box3(); obj.updateWorldMatrix(true, true);
  obj.traverseVisible((o) => { if ((o.isMesh || o.isInstancedMesh) && o.geometry) { const gb = new THREE.Box3().setFromObject(o, false); if (!gb.isEmpty()) b.union(gb); } });
  return b;
}

// ---- Jetson: Seeed reComputer J4012 ----------------------------------------------
export function buildJetson() {
  const c = makeComponent(THREE, {
    id: 'jetson', name: 'Seeed reComputer J4012 (Jetson Orin NX 16 GB)', category: 'compute',
    mount: 'centre of the underside (rubber feet on y = 0); I/O panel faces +X', size: [0.120, 0.0585, 0.130],
  });
  const X = 0.120, Z = 0.130, H = 0.0585, top = 0.0126;
  // base plate and feet
  const base = new THREE.Group();
  put(base, rbox(X, 0.003, Z, 0.002, M.aluDark), 0, 0.0035, 0);
  for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) put(base, cyl(0.006, 0.0065, 0.002, M.rubber, 20), sx * (X / 2 - 0.012), 0.001, sz * (Z / 2 - 0.012));
  addPart(c, 'base', 'Base plate and feet', base, vec(0, -0.06, 0), 'Aluminium base plate; the carrier board stands on it.');

  // M.2 NVMe SSD under the carrier
  const ssd = new THREE.Group();
  put(ssd, box(0.080, 0.0008, 0.022, M.pcbBlack), 0, 0, 0);
  put(ssd, chip(0.012, 0.012, 0.0009, 'NAND', 0.008), -0.016, 0.0004, 0);
  put(ssd, chip(0.009, 0.009, 0.0009, 'CTRL', 0.007), 0.012, 0.0004, 0);
  put(ssd, box(0.002, 0.0009, 0.0215, M.gold), 0.039, 0, 0);
  put(ssd, decal('NVMe M.2 2280', 0.02, '+y', { color: '#d8dde2', font: '500 48px ' + FONT }), -0.003, 0.00045, 0.007);
  addPart(c, 'ssd', 'M.2 2280 NVMe SSD', put(new THREE.Group(), ssd, 0, 0, 0), vec(0, -0.03, -0.11), 'System disk: JetPack 6.2, the hud/ package and topic logs.');
  c.parts[c.parts.length - 1].object.position.set(-0.008, 0.0098, -0.03);

  // carrier board with I/O
  const car = new THREE.Group();
  put(car, box(0.112, 0.0016, 0.122, M.pcbBlack), 0, 0.0118, 0);
  for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) put(car, cyl(0.0024, 0.0024, 0.006, MX.brass, 6), sx * 0.050, 0.008, sz * 0.055);
  put(car, smd(0.105, 0.115, 160, 5, top, [[-0.02, 0, 0.05, 0.074], [0.045, 0, 0.03, 0.125]]), 0, 0, 0);
  put(car, box(0.006, 0.0052, 0.074, M.plasticBlack), 0.006, top + 0.0026, 0);   // 260-pin SO-DIMM socket
  const io = 0.0606;
  put(car, Port.dcJack(), io, top + 0.0055, -0.052);
  put(car, Port.usbC(), io, top + 0.0017, -0.0405);
  put(car, Port.hdmi(), io, top + 0.0031, -0.027);
  put(car, Port.usbAStack(), io, top + 0.0076, -0.008);
  put(car, Port.usbAStack(), io, top + 0.0076, 0.0105);
  const rj = put(car, Port.rj45(), io, top + 0.0068, 0.0315);
  put(car, jst(4, true), 0.050, top, 0.050);                                          // CAN (unused)
  put(car, cylX(0.0024, 0.006, M.plasticBlack, 16), io - 0.002, top + 0.006, 0.0505);  // power button
  const pwrLed = put(car, led(0x3dff7a, 0.0008, 0.002, 0.002), io, top + 0.0115, 0.0505);
  const sysLed = put(car, led(0x5aa8ff, 0.0008, 0.002, 0.002), io, top + 0.0115, 0.0565);
  put(car, header(4, 1), -0.050, top, 0.045);                                         // fan header
  addPart(c, 'carrier', 'J401 carrier board and I/O', car, vec(0, 0.0, 0), 'Carrier with 1x HDMI 2.1, 4x USB 3.2, gigabit Ethernet, a 9–19 V DC jack, a CAN port (unused: no vehicle bus), two camera connectors and the M.2 slot.');

  // Orin NX module
  const som = new THREE.Group();
  put(som, box(0.045, 0.0012, 0.0696, M.pcbGreen), 0, 0, 0);
  put(som, smd(0.04, 0.065, 50, 9, 0.0006), 0, 0, 0);
  put(som, chip(0.010, 0.012, 0.0011, 'LPDDR5', 0.008), 0.012, 0.0006, 0.024);
  put(som, chip(0.010, 0.012, 0.0011, 'LPDDR5', 0.008), 0.012, 0.0006, -0.024);
  put(som, rbox(0.040, 0.0035, 0.060, 0.0012, M.aluDark), -0.002, 0.0024, 0);
  put(som, decal('NVIDIA Jetson Orin NX 16GB', 0.034, '+y', { color: '#e8ecef', font: '600 48px ' + FONT }), -0.002, 0.0042, 0);
  addPart(c, 'som', 'Jetson Orin NX 16 GB module', put(new THREE.Group(), som, 0, 0, 0), vec(0, 0.035, 0), '8-core Arm CPU, 1024-core Ampere GPU, 16 GB LPDDR5. Runs every HUD process; MAXN mode, never MAXN SUPER.');
  c.parts[c.parts.length - 1].object.position.set(-0.016, top + 0.0032, 0);

  // heatsink with heat pipes
  const hs = new THREE.Group();
  put(hs, box(0.050, 0.003, 0.066, M.alu), 0, 0, 0);
  const fins = [];
  for (let i = 0; i < 17; i++) fins.push([0, 0.0115, -0.032 + i * 0.004]);
  hs.add(instanced(new THREE.BoxGeometry(0.048, 0.020, 0.0008), M.alu, fins));
  put(hs, cable([[-0.02, 0.003, -0.02], [0.0, 0.004, -0.02], [0.022, 0.01, -0.02], [0.022, 0.018, -0.02]], 0.0022, M.copper), 0, 0, 0);
  put(hs, cable([[-0.02, 0.003, 0.02], [0.0, 0.004, 0.02], [0.022, 0.01, 0.02], [0.022, 0.018, 0.02]], 0.0022, M.copper), 0, 0, 0);
  const hsPart = addPart(c, 'heatsink', 'Heatsink and heat pipes', hs, vec(0, 0.07, 0), 'Copper heat pipes carry heat from the module to aluminium fins.');
  hsPart.position.set(-0.018, top + 0.0082, 0);

  // fan
  const fan = axialFan(0.050, 0.010, 9);
  put(fan, decal('12V DC', 0.008, '+y', { color: '#333', font: '600 48px ' + FONT }), 0, 0.0046, 0);
  const fanPart = addPart(c, 'fan', 'Cooling fan', fan, vec(0, 0.10, 0), 'Draws air through the fins; the carrier cannot cool the MAXN SUPER mode, so the plan runs MAXN.');
  fanPart.position.set(-0.018, 0.0486, 0);

  // shell walls
  const shell = new THREE.Group();
  const wy = 0.005 + 0.0515 / 2;
  put(shell, box(0.002, 0.0515, Z, M.aluAnodBlack), X / 2 - 0.001, wy, 0);
  put(shell, box(0.002, 0.0515, Z, M.alu), -X / 2 + 0.001, wy, 0);
  put(shell, box(X - 0.004, 0.0515, 0.002, M.alu), 0, wy, Z / 2 - 0.001);
  put(shell, box(X - 0.004, 0.0515, 0.002, M.alu), 0, wy, -Z / 2 + 0.001);
  const slots = [];
  for (let i = 0; i < 14; i++) slots.push([-X / 2 - 0.00005, 0.02 + (i % 7) * 0.0045, -0.04 + Math.floor(i / 7) * 0.05]);
  shell.add(instanced(new THREE.BoxGeometry(0.0004, 0.0018, 0.036), M.flock, slots));
  for (const s of [1, -1]) for (let i = 0; i < 6; i++) put(shell, box(0.10, 0.0006, 0.0004, M.flock), 0, 0.012 + i * 0.007, s * (Z / 2 + 0.00005));
  for (const [t, z, w] of [['DC 9–19V', -0.052, 0.009], ['USB-C', -0.0405, 0.007], ['HDMI 2.1', -0.027, 0.009], ['USB 3.2', 0.0012, 0.01], ['GbE', 0.0315, 0.006], ['CAN', 0.048, 0.005]]) {
    put(shell, decal(t, w, '+x', { color: '#c7ccd2', font: '500 48px ' + FONT }), X / 2 + 0.0002, 0.0335, z);
  }
  put(shell, decal('reComputer J4012', 0.05, '+z', { color: '#5a5f66', font: '600 48px ' + FONT }), 0, 0.034, Z / 2 + 0.0002);
  addPart(c, 'shell', 'Enclosure walls', shell, vec(0, 0.0, 0.0), 'Aluminium enclosure; the I/O panel side is anodised black.');
  // lid
  const lid = new THREE.Group();
  put(lid, rbox(X, 0.002, Z, 0.0018, M.alu), 0, H - 0.001, 0);
  const vs = [];
  for (let i = 0; i < 22; i++) for (const s of [-1, 1]) vs.push([-0.05 + i * 0.0047, H + 0.00005, s * 0.048]);
  lid.add(instanced(new THREE.BoxGeometry(0.0022, 0.0003, 0.022), M.flock, vs));
  put(lid, cyl(0.024, 0.024, 0.0003, M.flock, 40), -0.018, H + 0.0001, 0);
  for (let r = 0.006; r < 0.024; r += 0.004) { const ring = new THREE.Mesh(new THREE.TorusGeometry(r, 0.0006, 6, 40), M.alu); ring.rotation.x = Math.PI / 2; ring.position.set(-0.018, H + 0.0004, 0); lid.add(ring); }
  put(lid, decal('Seeed Studio · reComputer', 0.045, '+y', { color: '#3e4349', font: '600 48px ' + FONT }), 0.035, H + 0.0002, 0);
  addPart(c, 'lid', 'Top cover with vents', lid, vec(0, 0.14, 0), 'Vented aluminium cover over the fan.');

  // working visuals
  const fx = new THREE.Group(); fx.visible = false; c.group.add(fx);
  const heat = [];
  for (let i = 0; i < 7; i++) { const s = glow(0xff8a3a, 0.03, 0.12); s.position.set(-0.03 + (i % 4) * 0.02, H, -0.03 + (i % 3) * 0.03); fx.add(s); heat.push(s); }
  const gpu = livePanel(760, 430, 0.15);
  gpu.obj.position.set(0, H + 0.09, 0); fx.add(gpu.obj);
  const vals = P.GPU.map(([, lo]) => lo);

  c.assembly = [
    { title: 'Base plate and feet', parts: ['base'], text: 'Start from the aluminium base; the rubber feet keep it off the bracket.' },
    { title: 'Fit the SSD', parts: ['ssd'], text: 'The M.2 2280 NVMe drive holds JetPack 6.2, the hud/ package and logs.' },
    { title: 'Carrier board', parts: ['carrier'], text: 'The J401 carrier stands on brass spacers; all ports face the I/O side.' },
    { title: 'Seat the Orin NX module', parts: ['som'], text: 'The module clips into the 260-pin socket.' },
    { title: 'Heatsink and fan', parts: ['heatsink', 'fan'], text: 'Thermal pad, heat-pipe heatsink, then the fan on its 4-pin header.' },
    { title: 'Close the enclosure', parts: ['shell', 'lid'], text: 'Walls and the vented lid. Reflash to JetPack 6.2 from Seeed\'s image and set MAXN (nvpmodel mode 0).' },
  ];
  c.facts = [
    ['Module', 'Jetson Orin NX 16 GB (8-core Arm, 1024-core Ampere GPU)'],
    ['Carrier', 'Seeed J401: 1x HDMI 2.1, no DisplayPort, 4x USB 3.2, GbE, CAN (unused)'],
    ['Power', '9–19 V input, from the ignition-sensed DC-DC'],
    ['Mode', 'MAXN; Seeed says the carrier cannot cool MAXN SUPER'],
    ['Software', 'JetPack 6.2 (Ubuntu 22.04, Python 3.10, TensorRT 10)'],
    ['GPU budget', `${R.GPU_MIN}–${R.GPU_MAX} ms serial per frame (ASSUMED except ZED depth and YOLO11s); 33 ms at 30 Hz`],
    ['Cited', 'ZED NEURAL_LIGHT 23% / NEURAL 59% GPU at 30 fps; YOLO11s FP16 7.9 ms'],
    ['State', 'Recorded 2026-10-07 on JetPack 5.1.3; unreachable since: verify before flashing'],
    ['Cost', 'owned'],
  ];
  c.desc = 'The only computer in the car. It runs every HUD process: stereo depth and the ground plane, the lane and object networks, ego-motion, head tracking, the 60 Hz renderer and the logs. It drives the panel over its single HDMI port and streams the audience view over Ethernet.';
  c.working = 'The fan spins, the status LED blinks, warm air rises from the vents and the panel shows GPU time per job against the 33 ms frame period.';
  c.setWorking = (on) => { fx.visible = on; pwrLed.userData.set(on ? 1 : 0); if (!on) { sysLed.userData.set(0); rj.userData.leds.forEach((l) => l.userData.set(0)); } };
  let acc30 = 0;
  c.update = (t, dt, s) => {
    if (!s || !s.working) return;
    fan.userData.rotor.rotation.y -= dt * 45;
    sysLed.userData.set(Math.sin(t * 6) > 0.3 ? 1 : 0.1);
    rj.userData.leds[0].userData.set(1); rj.userData.leds[1].userData.set(Math.random() > 0.5 ? 1 : 0.2);
    heat.forEach((h, i) => { const ph = (t * 0.45 + i / heat.length) % 1; h.position.y = H + ph * 0.05; h.material.opacity = 0.16 * Math.sin(ph * Math.PI); h.scale.setScalar(0.02 + ph * 0.03); });
    acc30 += dt;
    if (acc30 >= 1 / 30) {
      acc30 = 0;
      P.GPU.forEach(([, lo, hi], i) => { vals[i] = lo + (hi - lo) * (0.5 + 0.42 * Math.sin(t * (0.7 + i * 0.37) + i) + 0.08 * (Math.random() - 0.5)); });
    }
    gpu.tick(dt, 15, (ctx, W, Hh) => drawGpu(ctx, W, Hh, vals));
  };
  gpu.draw((ctx, W, Hh) => drawGpu(ctx, W, Hh, vals));
  return c;
}

function drawGpu(ctx, W, H, vals) {
  panelBg(ctx, W, H, 'GPU time per camera frame', 'Orin NX 16 GB · plan §5.6 · ranges ASSUMED except the two cited');
  const barX = 360, barW = W - barX - 120, scale = barW / 22;
  const short = ['ZED stereo depth', 'Lane network FP16', 'YOLO11s FP16, 640 px', 'Face landmarks (if on Jetson)', 'hudd render + warp'];
  P.GPU.forEach(([, lo, hi], i) => {
    const y = 112 + i * 44;
    txt(ctx, short[i], 22, y, { size: 22 });
    ctx.fillStyle = 'rgba(94,200,255,0.18)'; ctx.fillRect(barX + lo * scale, y - 13, (hi - lo) * scale, 26);
    ctx.fillStyle = '#5ec8ff'; ctx.fillRect(barX, y - 8, vals[i] * scale, 16);
    txt(ctx, `${vals[i].toFixed(1)} ms`, barX + vals[i] * scale + 10, y, { size: 21, color: '#eef4fa', weight: 600 });
  });
  const tot = vals.reduce((a, b) => a + b, 0);
  const y = 352, sc2 = barW / 55;
  let x = barX;
  const cols = ['#5ec8ff', '#4fd18b', '#ffb347', '#c78bff', '#ff7b7b'];
  vals.forEach((v, i) => { ctx.fillStyle = cols[i]; ctx.fillRect(x, y - 12, v * sc2, 24); x += v * sc2; });
  for (const [ms, lab] of [[1000 / 30, '30 Hz'], [50, '20 Hz']]) {
    ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(barX + ms * sc2, y - 22); ctx.lineTo(barX + ms * sc2, y + 22); ctx.stroke();
    txt(ctx, lab, barX + ms * sc2, y + 34, { size: 18, align: 'center', color: '#c0ccd8' });
  }
  txt(ctx, 'Serial total', 22, y, { size: 22, weight: 600, color: '#eef4fa' });
  const pct = tot / (1000 / 30) * 100;
  txt(ctx, `${tot.toFixed(1)} ms · ${pct.toFixed(0)}% of a 33 ms frame`, 22, y + 36, { size: 20, color: pct > 100 ? '#ff8a8a' : '#9fe6bd' });
}

// ---- Software: the hud/ process graph ---------------------------------------------------
const SW_NODES = {
  // id: [u, v, label, sub, colour, kind]
  zedSrc: [-0.44, 0.16, 'ZED 2i', 'USB 3', 0x5c6470, 'src'],
  f9rSrc: [-0.44, -0.02, 'ZED-F9R', 'USB serial', 0x5c6470, 'src'],
  oakSrc: [-0.44, -0.12, 'OAK-D Pro', 'USB 3', 0x5c6470, 'src'],
  picoSrc: [-0.44, -0.22, 'RP2040', 'USB serial', 0x5c6470, 'src'],
  roadd: [-0.24, 0.16, 'roadd', 'depth · plane · lift', 0x2f6fd1, 'proc'],
  laned: [0.0, 0.225, 'laned', 'lane net TRT FP16', 0x2f6fd1, 'proc'],
  detectd: [0.0, 0.095, 'detectd', 'YOLO11s + tracker', 0x2f6fd1, 'proc'],
  egod: [-0.24, -0.02, 'egod', 'speed · yaw · sun', 0x1f9a8a, 'proc'],
  headtrackd: [-0.24, -0.12, 'headtrackd', 'eye midpoint', 0x7b4fd1, 'proc'],
  controllerd: [-0.24, -0.22, 'controllerd', 'backlight · shutter', 0xc8892a, 'proc'],
  hudd: [0.13, -0.07, 'hudd', '60 Hz renderer (root)', 0xe0702c, 'root'],
  logd: [0.30, 0.13, 'logd', 'records all topics', 0x6b7380, 'proc'],
  audienced: [0.30, -0.20, 'audienced', 'MJPEG to mini PC 2', 0x6b7380, 'proc'],
  panelOut: [0.47, -0.07, 'TFT panel', 'HDMI 1080p60', 0x5c6470, 'out'],
  pcOut: [0.47, -0.20, 'Mini PC 2', 'Ethernet', 0x5c6470, 'out'],
  ssdOut: [0.47, 0.13, 'SSD', 'topic logs', 0x5c6470, 'out'],
};
const SW_EDGES = [
  // from, to, label, rate (Hz), bend (perpendicular, board units), label position along the curve
  ['zedSrc', 'roadd', 'frames + IMU', 30, 0, 0.5],
  ['roadd', 'laned', 'left image', 30, 0.045, 0.5],
  ['laned', 'roadd', 'lanes2d 30 Hz', 30, -0.012, 0.55],
  ['roadd', 'detectd', 'left image', 30, 0.01, 0.5],
  ['detectd', 'roadd', 'objects2d 30 Hz', 30, -0.04, 0.5],
  ['roadd', 'egod', 'imu 400 Hz', 400, 0, 0.5],
  ['roadd', 'hudd', 'lanes 30 Hz', 30, 0.035, 0.62],
  ['roadd', 'hudd', 'objects 30 Hz', 30, -0.0, 0.62],
  ['f9rSrc', 'egod', 'fused ≤ 30 Hz', 30, 0, 0.5],
  ['egod', 'hudd', 'ego 100 Hz', 100, 0.03, 0.55],
  ['egod', 'hudd', 'gnss 10 Hz', 10, 0.0, 0.55],
  ['egod', 'hudd', 'sunWatch 1 Hz', 1, -0.03, 0.55],
  ['egod', 'controllerd', 'sunWatch 1 Hz', 1, -0.08, 0.5],
  ['oakSrc', 'headtrackd', 'landmarks 30 Hz', 30, 0, 0.5],
  ['headtrackd', 'hudd', 'eyePose 30 Hz', 30, -0.02, 0.5],
  ['picoSrc', 'controllerd', 'serial 10 Hz', 10, 0, 0.5],
  ['controllerd', 'hudd', 'health 2 Hz', 2, -0.03, 0.5],
  ['hudd', 'logd', 'hudStats 10 Hz', 10, 0.02, 0.5],
  ['hudd', 'audienced', 'hudFrame 15 Hz', 15, -0.02, 0.5],
  ['hudd', 'panelOut', 'HDMI 60 Hz', 60, 0, 0.6],
  ['audienced', 'pcOut', 'MJPEG 15 Hz', 15, 0, 0.5],
  ['logd', 'ssdOut', 'files', 5, 0, 0.5],
];
const CRASH_CYCLE = ['laned', 'detectd', 'headtrackd', 'egod'];

export function buildSoftware() {
  const c = makeComponent(THREE, {
    id: 'software', name: 'hud/ software: processes and topics', category: 'software',
    mount: 'centre of the back board; the diorama faces +X', size: [0.06, 0.62, 1.0],
  });
  const P3 = (u, v, x = 0) => vec(x, v, -u);   // board coordinates (u right, v up) to local, viewer at +X
  const board = new THREE.Group();
  put(board, rbox(0.008, 0.62, 1.04, 0.008, M.color(0x14171c, 0.8)), -0.004, 0, 0);
  put(board, rbox(0.004, 0.53, 0.75, 0.006, M.color(0x1c2129, 0.8)), 0.002, -0.015, -0.035);
  put(board, decal('Jetson Orin NX · one host · ZeroMQ PUB/SUB over ipc, msgpack', 0.36, '+x', { color: '#8fa3b6', font: '500 48px ' + FONT }), 0.0045, -0.268, -0.035);
  put(board, decal('sensors', 0.05, '+x', { color: '#8fa3b6', font: '500 48px ' + FONT }), 0.0045, 0.215, 0.44);
  put(board, decal('outputs', 0.05, '+x', { color: '#8fa3b6', font: '500 48px ' + FONT }), 0.0045, 0.19, -0.47);
  addPart(c, 'board', 'Jetson host (JetPack 6.2)', board, vec(-0.08, 0, 0), 'One host, one monotonic clock; every topic carries its sensor frame\'s capture time.');

  const nodes = {};
  for (const [id, [u, v, label, sub, color, kind]] of Object.entries(SW_NODES)) {
    const g = new THREE.Group();
    const w = kind === 'root' ? 0.15 : kind === 'proc' ? 0.11 : 0.09;
    const h = kind === 'root' ? 0.062 : 0.044;
    const m = new THREE.MeshStandardMaterial({ color, roughness: 0.45, metalness: 0.1, emissive: color, emissiveIntensity: 0.05 });
    put(g, rbox(0.028, h, w, 0.008, m), 0.014, 0, 0);
    put(g, decal(label, Math.min(w * 0.86, 0.0118 * label.length + 0.006), '+x', { color: '#ffffff', font: '700 64px ' + FONT }), 0.0285, h * 0.16, 0);
    put(g, decal(sub, Math.min(w * 0.9, 0.0052 * sub.length + 0.004), '+x', { color: '#e3ebf3', font: '400 44px ' + FONT }), 0.0285, -h * 0.25, 0);
    let light = null;
    if (kind !== 'src' && kind !== 'out') light = put(g, led(0x46ff7a, 0.004, 0.006, 0.006), 0.026, h / 2 - 0.006, -w / 2 + 0.008);
    g.position.copy(P3(u, v));
    addPart(c, id, kind === 'src' ? `${label} (sensor input)` : kind === 'out' ? `${label} (output)` : `${label} process`, g, vec(0.06 + (kind === 'root' ? 0.06 : 0.03), 0, 0), sub);
    nodes[id] = { g, m, color, light, w, h, u, v };
  }
  // supervisor bar
  const sup = new THREE.Group();
  const supMat = new THREE.MeshStandardMaterial({ color: 0x3a4250, roughness: 0.5, emissive: 0x6688ff, emissiveIntensity: 0 });
  put(sup, rbox(0.02, 0.03, 0.60, 0.006, supMat), 0.01, 0, 0);
  put(sup, decal('supervisor · restarts a crashed process after 1 s, marks its topics stale', 0.5, '+x', { color: '#dfe7ef', font: '500 44px ' + FONT }), 0.0205, 0, 0);
  sup.position.copy(P3(-0.05, 0.275));
  addPart(c, 'supervisor', 'Supervisor', sup, vec(0.05, 0.05, 0), 'Starts every process, restarts a crashed one after 1 s and marks its topics stale.');

  // topics: tubes, labels and particles
  const topics = new THREE.Group();
  const edges = SW_EDGES.map(([a, b, label, rate, bend, lt]) => {
    const A = nodes[a], B = nodes[b];
    const pa = P3(A.u, A.v, 0.012), pb = P3(B.u, B.v, 0.012);
    const du = B.u - A.u, dv = B.v - A.v, dl = Math.hypot(du, dv);
    const mu = (A.u + B.u) / 2 - (dv / dl) * bend * 2.2, mv = (A.v + B.v) / 2 + (du / dl) * bend * 2.2;
    const mid = P3(mu, mv, 0.016);
    const curve = new THREE.QuadraticBezierCurve3(pa, mid, pb);
    const tm = new THREE.MeshStandardMaterial({ color: 0x7f8c99, roughness: 0.5, emissive: 0x335577, emissiveIntensity: 0.2 });
    const mesh = new THREE.Mesh(new THREE.TubeGeometry(curve, 40, rate >= 100 ? 0.0022 : 0.0015, 6, false), tm);
    topics.add(mesh);
    const lp = curve.getPoint(lt);
    const lab = decal(label, 0.0058 * label.length + 0.012, '+x', { color: '#c9d7e5', font: '500 40px ' + FONT, bg: 'rgba(12,16,22,0.78)' });
    lab.position.set(0.031, lp.y, lp.z); topics.add(lab);
    return { a, b, label, rate, curve, tm, acc: Math.random(), stale: false };
  });
  const maxP = 700;
  const pGeo = new THREE.SphereGeometry(0.0035, 8, 6);
  const pMat = new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false });
  const parts = new THREE.InstancedMesh(pGeo, pMat, maxP);
  parts.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(maxP * 3), 3);
  parts.frustumCulled = false; parts.visible = false; topics.add(parts);
  addPart(c, 'topics', 'Topics (ZeroMQ PUB/SUB, msgpack)', topics, vec(0.03, 0, 0), 'Each message carries capture time, publish time and a sequence; empty messages are still published so silence is not absence.');

  // status panel
  const status = livePanel(820, 200, 0.36);
  status.obj.position.copy(P3(0.25, 0.36, 0.05)); status.obj.visible = false; c.group.add(status.obj);

  c.assembly = [
    { title: 'Flash the Jetson', parts: ['board'], text: 'Reflash to JetPack 6.2 from Seeed\'s image (Ubuntu 22.04, Python 3.10, TensorRT 10); set MAXN.' },
    { title: 'Road camera and roadd', parts: ['zedSrc', 'roadd'], text: 'Install the ZED SDK package that matches the reported L4T release; roadd owns the ZED 2i: capture, depth, RANSAC ground plane, IMU.' },
    { title: 'Networks', parts: ['laned', 'detectd'], text: 'Export the lane network and YOLO11s to TensorRT FP16 engines; laned and detectd run them on the left image.' },
    { title: 'Ego-motion', parts: ['f9rSrc', 'egod'], text: 'egod fuses the ZED-F9R and the ZED IMU into speed, yaw rate and pitch at 100 Hz, and computes the sun direction at 1 Hz.' },
    { title: 'Head tracking', parts: ['oakSrc', 'headtrackd'], text: 'headtrackd reads on-camera face landmarks and depth from the OAK-D Pro: eye midpoint in the car frame.' },
    { title: 'Controller link', parts: ['picoSrc', 'controllerd'], text: 'controllerd talks to the RP2040: ambient light, cell temperature, backlight duty, shutter.' },
    { title: 'Renderer', parts: ['hudd', 'panelOut'], text: 'hudd is the root: age compensation, eye projection, 60 Hz draw with vsync, pre-distortion warp, full-screen HDMI.' },
    { title: 'Logging and audience', parts: ['logd', 'ssdOut', 'audienced', 'pcOut'], text: 'logd records every topic; audienced streams the HUD frame and driver camera to mini PC 2.' },
    { title: 'Supervisor and topics', parts: ['supervisor', 'topics'], text: 'The supervisor starts everything; topics flow at their rates with hudd at the root of the tree.' },
  ];
  c.facts = [
    ['Processes', '9, one per job, plus a supervisor (restart after 1 s, topics marked stale)'],
    ['Transport', 'ZeroMQ PUB/SUB over ipc, msgpack maps'],
    ['Each message', 'capture time, publish time, sequence; empty messages still published'],
    ['Rates', 'ego 100 Hz · lanes, objects, eyePose 30 Hz · gnss, hudStats 10 Hz · health 2 Hz · sunWatch 1 Hz'],
    ['Stale rule', 'lanes/objects fade over 300 ms once older than 250 ms, gone at 600 ms'],
    ['Renderer', 'raylib (GL 3.3 core), 1920 × 1080 at 60 Hz, vsync; only the 946 × 473 px crop is drawn'],
    ['GPU budget', `${R.GPU_MIN}–${R.GPU_MAX} ms serial per frame (ASSUMED)`],
    ['Package', 'standalone hud/ (planned), no openpilot build dependency'],
  ];
  c.desc = 'The HUD software is one process per job on the Jetson. Sensor processes publish topics; hudd subscribes to all of them, compensates each for its age and draws the frame at 60 Hz. The graph is a tree with hudd at the root.';
  c.working = 'Messages flow along each topic at its real rate (fast streams thinned for display); every 12 s one process crashes, its topics go stale and the supervisor restarts it after 1 s.';
  c.setWorking = (on) => {
    parts.visible = on; status.obj.visible = on;
    for (const n of Object.values(nodes)) if (n.light) n.light.userData.set(on ? 1 : 0);
  };
  const pool = [];
  const col = new THREE.Color();
  const dummy = new THREE.Object3D();
  let lastCrash = '';
  c.update = (t, dt, s) => {
    if (!s || !s.working) return;
    const cyc = Math.floor(t / 12), ph = t - cyc * 12;
    const crashed = ph >= 8 && ph < 9 ? CRASH_CYCLE[cyc % CRASH_CYCLE.length] : null;
    const restarting = ph >= 9 && ph < 9.6 ? CRASH_CYCLE[cyc % CRASH_CYCLE.length] : null;
    for (const [id, n] of Object.entries(nodes)) {
      if (!n.light) continue;
      if (id === crashed) { n.m.color.setHex(0xb02a2a); n.m.emissive.setHex(0xff2020); n.m.emissiveIntensity = 0.4 + 0.3 * Math.sin(t * 20); n.light.userData.set(0); }
      else if (id === restarting) { n.m.color.setHex(n.color); n.m.emissive.setHex(0x80ffb0); n.m.emissiveIntensity = 0.6 * (1 - (ph - 9) / 0.6); n.light.userData.set(1); }
      else { n.m.color.setHex(n.color); n.m.emissive.setHex(n.color); n.m.emissiveIntensity = 0.05; n.light.userData.set(1); }
    }
    supMat.emissiveIntensity = restarting ? 0.8 * (1 - (ph - 9) / 0.6) : crashed ? 0.25 + 0.2 * Math.sin(t * 12) : 0;
    for (const e of edges) {
      e.stale = e.a === crashed;
      e.tm.color.setHex(e.stale ? 0x4a4f56 : 0x7f8c99);
      e.tm.emissive.setHex(e.stale ? 0x000000 : 0x335577);
      if (e.stale) continue;
      e.acc += dt * Math.min(e.rate, 40);
      while (e.acc >= 1 && pool.length < maxP) { e.acc -= 1; pool.push({ e, u: 0 }); }
      if (e.acc >= 1) e.acc = 0;
    }
    let k = 0;
    for (let i = pool.length - 1; i >= 0; i--) {
      const p = pool[i];
      p.u += dt / 0.9;
      if (p.u >= 1) { pool.splice(i, 1); continue; }
    }
    for (const p of pool) {
      dummy.position.copy(p.e.curve.getPoint(p.u)); dummy.position.x += 0.004;
      const sc = p.e.rate >= 100 ? 0.8 : p.e.rate <= 2 ? 1.6 : 1;
      dummy.scale.setScalar(sc); dummy.updateMatrix();
      parts.setMatrixAt(k, dummy.matrix);
      col.setHex(p.e.b === 'hudd' ? 0xffb347 : p.e.a === 'hudd' ? 0xff7b3d : 0x7fd3ff);
      parts.setColorAt(k, col); k++;
    }
    parts.count = k; parts.instanceMatrix.needsUpdate = true; if (parts.instanceColor) parts.instanceColor.needsUpdate = true;
    const key = crashed ? 'c' + crashed : restarting ? 'r' + restarting : 'ok';
    if (key !== lastCrash) {
      lastCrash = key;
      status.draw((ctx, W, H) => {
        panelBg(ctx, W, H, 'supervisor');
        if (crashed) {
          const outs = edges.filter((e) => e.a === crashed).map((e) => e.label.split(' ')[0]);
          txt(ctx, `${crashed} exited · restart in 1 s`, 22, 92, { size: 26, color: '#ff9a9a', weight: 600 });
          txt(ctx, `stale: ${[...new Set(outs)].join(', ')} · hudd fades what depends on them`, 22, 140, { size: 22 });
        } else if (restarting) {
          txt(ctx, `${restarting} restarted`, 22, 92, { size: 26, color: '#9fe6bd', weight: 600 });
          txt(ctx, 'topics fresh again; rules re-apply the 3-frame appearance', 22, 140, { size: 22 });
        } else {
          txt(ctx, 'all 9 processes running', 22, 92, { size: 26, color: '#9fe6bd', weight: 600 });
          txt(ctx, 'fast streams thinned for display; labels give the real rates', 22, 140, { size: 22 });
        }
      });
    }
  };
  return c;
}

// ---- HUD controller: RP2040 + sensors ----------------------------------------------
export function buildController() {
  const c = makeComponent(THREE, {
    id: 'controller', name: 'HUD controller (Raspberry Pi Pico, RP2040)', category: 'controller',
    mount: 'centre of the carrier board underside', size: [0.12, 0.02, 0.10],
  });
  const BW = 0.072, BD = 0.052;
  const board = new THREE.Group();
  put(board, box(BW, 0.0016, BD, MX.fr4), 0, 0.0008, 0);
  for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) put(board, cyl(0.0016, 0.0016, 0.0017, M.steel, 12), sx * (BW / 2 - 0.004), 0.0009, sz * (BD / 2 - 0.004));
  put(board, header(20, 1), -0.004, 0.0016, 0.0102).rotation.y = Math.PI / 2;
  put(board, header(20, 1), -0.004, 0.0016, -0.0102).rotation.y = Math.PI / 2;
  const ledOk = put(board, led(0x46ff7a, 0.0025, 0.0012, 0.0025), 0.028, 0.0022, 0.011);
  const ledT1 = put(board, led(0xffb020, 0.0025, 0.0012, 0.0025), 0.028, 0.0022, 0.015);
  const ledT2 = put(board, led(0xff3030, 0.0025, 0.0012, 0.0025), 0.028, 0.0022, 0.019);
  for (const [t, z] of [['OK', 0.011], ['T1', 0.015], ['T2', 0.019]]) put(board, decal(t, 0.0032, '+y', { color: '#2a1d10', font: '700 48px ' + FONT }), 0.0325, 0.00165, z);
  put(board, header(3, 1), 0.030, 0.0016, -0.016);
  put(board, decal('SERVO', 0.007, '+y', { color: '#2a1d10', font: '700 48px ' + FONT }), 0.022, 0.00165, -0.016);
  put(board, header(4, 1), -0.031, 0.0016, -0.018);           // I2C to the light sensor
  put(board, header(5, 1), -0.031, 0.0016, 0.016);            // SPI to the MAX31855
  put(board, screwTerminal(2), 0.008, 0.0016, -0.019, 0, Math.PI / 2, 0);   // dim output to the LED driver
  put(board, decal('DIM', 0.005, '+y', { color: '#2a1d10', font: '700 48px ' + FONT }), 0.008, 0.00165, -0.0125);
  put(board, jst(2), 0.020, 0.0016, 0.019);                   // NTC
  addPart(c, 'board', 'Carrier perfboard', board, vec(0, -0.03, 0), 'Perfboard with headers for the Pico, the sensor leads, the servo and the LED-driver dim output.');

  const pi = pico();
  const piPart = addPart(c, 'pico', 'Raspberry Pi Pico (RP2040)', pi, vec(0, 0.035, 0), 'Dual-core RP2040 microcontroller: reads the sensors, sets backlight PWM and the shutter servo, reports at 10 Hz over USB serial.');
  piPart.position.set(-0.004, 0.0042, 0);

  // jumper wires on the perfboard
  const wires = new THREE.Group();
  const wmats = [M.cableRed, M.cableBlack, M.cableBlue, M.cableYellow, M.cableGreen, M.cableOrange];
  const routes = [
    [[0.012, 0.0056, 0.0102], [0.02, 0.0075, 0.011], [0.028, 0.0035, 0.011]],
    [[0.017, 0.0056, -0.0102], [0.024, 0.0075, -0.013], [0.030, 0.0045, -0.0135]],
    [[-0.020, 0.0056, -0.0102], [-0.026, 0.0075, -0.014], [-0.031, 0.0045, -0.0165]],
    [[-0.020, 0.0056, 0.0102], [-0.026, 0.0075, 0.012], [-0.031, 0.0045, 0.0135]],
    [[0.0, 0.0056, -0.0102], [0.004, 0.0075, -0.014], [0.008, 0.012, -0.017]],
    [[0.008, 0.0056, 0.0102], [0.013, 0.0075, 0.016], [0.017, 0.0035, 0.019]],
  ];
  routes.forEach((r, i) => wires.add(cable(r, 0.00055, wmats[i % wmats.length])));
  addPart(c, 'wires', 'Jumper wiring', wires, vec(0, 0.012, 0), 'Point-to-point wiring on the perfboard.');

  // TSL2591 on its lead (it sits at the dust cover in the car)
  const tsl = new THREE.Group();
  put(tsl, box(0.0178, 0.0016, 0.0254, mat('adaBlue', () => new THREE.MeshStandardMaterial({ color: 0x1a2a4a, roughness: 0.5 }))), 0, 0.0008, 0);
  put(tsl, box(0.002, 0.0009, 0.0024, M.chip), 0, 0.0021, 0);
  put(tsl, box(0.0012, 0.0002, 0.0012, mat('window', () => M.color(0x8a6a3a, 0.2))), 0, 0.0026, 0);
  put(tsl, jst(4), 0.0085, 0.0016, 0.007);
  put(tsl, jst(4), -0.0085, 0.0016, 0.007, 0, Math.PI, 0);
  put(tsl, decal('TSL2591', 0.009, '+y', { color: '#e6e9ee', font: '600 48px ' + FONT }), 0, 0.0017, -0.007);
  put(tsl, cable([[0.0085, 0.003, 0.007], [0.02, 0.007, -0.01], [0.027, 0.01, -0.04], [0.029, 0.009, -0.053]], 0.0011, M.cableBlack), 0, 0, 0);
  const tslPart = addPart(c, 'lightSensor', 'TSL2591 ambient-light sensor', tsl, vec(-0.03, 0.03, 0.03), 'Ambient light at the dust cover; sets the backlight from the night ceiling up to full at 10,000 lux and above.');
  tslPart.position.set(-0.060, 0.0, 0.035);

  // MAX31855 + thermocouple
  const mx = new THREE.Group();
  put(mx, box(0.0254, 0.0016, 0.0178, mat('adaBlue2', () => new THREE.MeshStandardMaterial({ color: 0x1a2a4a, roughness: 0.5 }))), 0, 0.0008, 0);
  put(mx, chip(0.005, 0.004, 0.0013, 'MAX31855', 0.0045), 0.002, 0.0016, 0);
  put(mx, screwTerminal(2, 0.0035), -0.0095, 0.0016, 0, 0, Math.PI, 0);
  put(mx, cable([[0.011, 0.003, 0.0], [0.02, 0.008, 0.02], [0.026, 0.01, 0.04], [0.027, 0.009, 0.048]], 0.0011, M.cableBlack), 0, 0, 0);
  put(mx, cable([[-0.013, 0.006, -0.0018], [-0.03, 0.007, -0.006], [-0.05, 0.004, -0.02], [-0.065, 0.003, -0.022]], 0.0009, MX.yellowWire), 0, 0, 0);
  put(mx, cable([[-0.013, 0.006, 0.0018], [-0.03, 0.007, -0.002], [-0.05, 0.0045, -0.017], [-0.065, 0.0035, -0.021]], 0.0009, M.cableRed), 0, 0, 0);
  put(mx, sphere(0.0016, mat('bead', () => M.color(0x9aa0a6, 0.3, 1)), 12), -0.067, 0.0032, -0.0215);
  const mxPart = addPart(c, 'thermocouple', 'MAX31855 and K-type thermocouple', mx, vec(-0.02, 0.03, -0.035), 'Reads the thermocouple placed at the sun focus for the empty-housing sun test.');
  mxPart.position.set(-0.058, 0.0, -0.032);

  // NTC lead: plugs into the 2-pin socket and runs to the back of the LCD cell
  const ntc = new THREE.Group();
  put(ntc, box(0.004, 0.003, 0.0035, MX.jstWhite), 0.002, 0.0015, 0);
  put(ntc, cable([[0.004, 0.0015, -0.0006], [0.015, 0.004, 0.002], [0.03, 0.003, 0.008], [0.045, 0.0016, 0.014]], 0.0005, M.cableBlack), 0, 0, 0);
  put(ntc, cable([[0.004, 0.0015, 0.0006], [0.015, 0.004, 0.0032], [0.03, 0.003, 0.0092], [0.045, 0.0016, 0.0152]], 0.0005, M.cableRed), 0, 0, 0);
  put(ntc, sphere(0.0018, MX.epoxy, 12), 0.047, 0.0016, 0.0148).scale.set(1.3, 1, 1);
  const ntcPart = addPart(c, 'ntc', '10 kΩ NTC thermistor on the cell', ntc, vec(0.025, 0.025, 0.03), 'Glued to the back of the LCD cell: derates the backlight above threshold 1 and blanks it above threshold 2.');
  ntcPart.position.set(0.020, 0.0016, 0.019);

  // servo lead and USB cable
  const cab = new THREE.Group();
  put(cab, box(0.003, 0.0075, 0.0078, M.plasticBlack), 0.030, 0.0079, -0.016);
  for (const [i, m] of [[0, mat('servoBrown', () => M.color(0x5a3a22, 0.6))], [1, M.cableRed], [2, M.cableOrange]]) {
    const z = -0.0185 + i * 0.00254;
    put(cab, cable([[0.030, 0.0116, z], [0.033, 0.016, z], [0.05, 0.014, z - 0.006], [0.07, 0.006, z - 0.014]], 0.0005, m), 0, 0, 0);
  }
  put(cab, rbox(0.010, 0.0045, 0.011, 0.001, M.plasticBlack), 0.0265, 0.0066, 0);
  put(cab, cable([[0.0315, 0.0066, 0], [0.05, 0.008, 0], [0.07, 0.006, 0.01], [0.09, 0.004, 0.02]], 0.0018, M.cableBlack), 0, 0, 0);
  addPart(c, 'leads', 'Servo lead and USB cable', cab, vec(0.035, 0.01, 0), 'Servo to the shutter; USB to the Jetson for power and the 10 Hz serial link.');

  // working panel
  const fx = new THREE.Group(); fx.visible = false; c.group.add(fx);
  const pnl = livePanel(860, 560, 0.14); pnl.obj.position.set(0, 0.075, 0); fx.add(pnl.obj);
  const nightDuty = (R.L_NIGHT_EYE / R.PATH_WS) / R.L_PANEL_DESIGN;   // 257 / 10,000
  const st = { lux: 1, duty: 1, temp: 30, usbSilent: 0, mode: 'ok' };

  c.assembly = [
    { title: 'Carrier board', parts: ['board'], text: 'Perfboard with headers for the Pico, the sensors, the servo and the dim output to the LED driver.' },
    { title: 'Pico', parts: ['pico'], text: 'Solder headers and seat the Raspberry Pi Pico.' },
    { title: 'Wiring', parts: ['wires'], text: 'I2C to the light sensor, SPI to the MAX31855, ADC to the NTC divider, PWM to the LED driver and the servo.' },
    { title: 'Sensor leads', parts: ['lightSensor', 'thermocouple', 'ntc'], text: 'The light sensor goes to the dust cover, the NTC onto the back of the LCD cell, the thermocouple to the sun focus for the test.' },
    { title: 'Servo and USB', parts: ['leads'], text: 'Shutter servo lead and the USB cable to the Jetson.' },
  ];
  c.facts = [
    ['MCU', 'Raspberry Pi Pico (RP2040), USB serial to controllerd at 10 Hz'],
    ['Inputs', 'TSL2591 or VEML7700 ambient light; 10 kΩ NTC on the cell; MAX31855 thermocouple for the sun test'],
    ['Outputs', 'backlight PWM above 2 kHz and analogue dim to the LED driver; shutter servo'],
    ['Dimming', `night ceiling ${Math.round(R.L_NIGHT_EYE / R.PATH_WS)} cd/m² at the panel (${(nightDuty * 100).toFixed(1)}% of full) up to full at ≥ 10,000 lux; 1 s update, 1 s ramp`],
    ['Fail-safe', 'above threshold 1 halve the duty; above threshold 2 backlight off and shutter closed; USB silent 5 s, the same'],
    ['Thresholds', 'set from the bought panel\'s rating (not published for the kit); values shown here are examples'],
    ['Cost', cost('HUD controller')],
  ];
  c.desc = 'A Raspberry Pi Pico that owns the HUD\'s analogue world: it reads ambient light and the cell temperature, drives the backlight and the sun shutter, and enforces the thermal and watchdog rules on its own, so a stuck Jetson cannot cook the panel.';
  c.working = 'Ambient light sweeps from night to noon and the PWM duty follows; the cell heats until threshold 1 halves the duty and threshold 2 blanks it and closes the shutter; a 5 s USB silence does the same.';
  c.setWorking = (on) => { fx.visible = on; if (!on) [ledOk, ledT1, ledT2, pi.userData.led].forEach((l) => l.userData.set(0)); };
  c.update = (t, dt, s) => {
    if (!s || !s.working) return;
    const ph = t % 32;
    // ambient sweep (log), 1 lux at night to 100,000 lux at noon and back
    st.lux = Math.pow(10, 2.5 + 2.5 * Math.sin((t / 32) * Math.PI * 2 - Math.PI / 2));
    const want = st.lux >= 10000 ? 1 : st.lux <= 10 ? nightDuty : nightDuty + (1 - nightDuty) * (Math.log10(st.lux) - 1) / 3;
    // scenario: heat soak 12–20 s, over T2 16–19 s, USB silent 24–29 s
    const T1 = 60, T2 = 70;
    let target = 32 + 30 * want;
    if (ph > 11 && ph < 20) target = 74;
    st.temp += (target - st.temp) * Math.min(1, dt * 0.9);
    st.usbSilent = ph > 23 && ph < 30 ? ph - 23 : 0;
    let duty = want, mode = 'ok';
    if (st.temp > T1) { duty = want * 0.5; mode = 't1'; }
    if (st.temp > T2) { duty = 0; mode = 't2'; }
    if (st.usbSilent >= 5) { duty = 0; mode = 'usb'; }
    st.duty += (duty - st.duty) * Math.min(1, dt * 2);
    st.mode = mode;
    ledOk.userData.set(mode === 'ok' ? 1 : 0.05);
    ledT1.userData.set(mode === 't1' ? 1 : 0.05);
    ledT2.userData.set(mode === 't2' || mode === 'usb' ? (Math.sin(t * 10) > 0 ? 1 : 0.2) : 0.05);
    pi.userData.led.userData.set(st.usbSilent > 0 ? 0 : (Math.sin(t * Math.PI * 2 * 2) > 0 ? 1 : 0.15));
    pnl.tick(dt, 15, (ctx, W, H) => drawController(ctx, W, H, st, t, T1, T2));
  };
  return c;
}

function drawController(ctx, W, H, st, t, T1, T2) {
  panelBg(ctx, W, H, 'HUD controller · RP2040', 'backlight PWM (> 2 kHz) follows ambient light; fail-safe rules run on the Pico');
  txt(ctx, `ambient ${st.lux >= 1000 ? (st.lux / 1000).toFixed(1) + ' klux' : st.lux.toFixed(0) + ' lux'}`, 22, 112, { size: 26, color: '#eef4fa', weight: 600 });
  txt(ctx, `duty ${(st.duty * 100).toFixed(1)}%`, 330, 112, { size: 26, color: '#ffd27a', weight: 600 });
  txt(ctx, `cell ${st.temp.toFixed(1)} °C`, 560, 112, { size: 26, color: st.temp > T2 ? '#ff8a8a' : st.temp > T1 ? '#ffc04d' : '#9fe6bd', weight: 600 });
  // PWM waveform: 4 periods
  const x0 = 30, y0 = 150, w = W - 60, h = 120;
  ctx.strokeStyle = 'rgba(255,255,255,0.12)'; ctx.lineWidth = 1; ctx.strokeRect(x0, y0, w, h);
  ctx.strokeStyle = '#ffd27a'; ctx.lineWidth = 3; ctx.beginPath();
  const per = w / 4, d = Math.max(0, Math.min(1, st.duty));
  for (let i = 0; i < 4; i++) {
    const xa = x0 + i * per;
    ctx.moveTo(xa, y0 + h - 10); ctx.lineTo(xa, d > 0.001 ? y0 + 12 : y0 + h - 10); ctx.lineTo(xa + per * d, d > 0.001 ? y0 + 12 : y0 + h - 10); ctx.lineTo(xa + per * d, y0 + h - 10); ctx.lineTo(xa + per, y0 + h - 10);
  }
  ctx.stroke();
  txt(ctx, 'PWM to the LED driver · 4 periods at > 2 kHz (no beat with the 30 Hz cameras)', x0, y0 + h + 22, { size: 19, color: '#8fa3b6' });
  // temperature bar
  const by = 345;
  ctx.fillStyle = 'rgba(255,255,255,0.08)'; ctx.fillRect(x0, by, w, 26);
  const tx = (T) => x0 + (T - 20) / 60 * w;
  ctx.fillStyle = st.temp > T2 ? '#ff6a6a' : st.temp > T1 ? '#ffc04d' : '#4fd18b'; ctx.fillRect(x0, by, tx(st.temp) - x0, 26);
  for (const [T, lab] of [[T1, 'T1'], [T2, 'T2']]) { ctx.fillStyle = '#fff'; ctx.fillRect(tx(T) - 1, by - 8, 3, 42); txt(ctx, `${lab} ${T} °C`, tx(T), by + 52, { size: 18, align: 'center', color: '#c0ccd8' }); }
  txt(ctx, 'cell temperature (thresholds are examples)', x0, by + 52, { size: 18, color: '#8fa3b6' });
  lamp(ctx, 40, 440, st.mode === 'ok', 'rgb(79,209,139)', 'normal: dimming curve');
  lamp(ctx, 40, 478, st.mode === 't1', 'rgb(255,192,77)', 'over T1: duty halved');
  lamp(ctx, 40, 516, st.mode === 't2', 'rgb(255,90,90)', 'over T2: off, shutter closed');
  lamp(ctx, 450, 440, st.usbSilent > 0, 'rgb(255,192,77)', `USB silent ${st.usbSilent.toFixed(1)} s`);
  lamp(ctx, 450, 478, st.mode === 'usb', 'rgb(255,90,90)', 'silent ≥ 5 s: off, shutter closed');
  lamp(ctx, 450, 516, st.mode === 't2' || st.mode === 'usb', 'rgb(255,90,90)', 'shutter closed');
}

// ---- LED driver: Recom RCD-24 class ------------------------------------------------
export function buildLedDriver() {
  const c = makeComponent(THREE, {
    id: 'ledDriver', name: 'Constant-current LED driver (Recom RCD-24 class)', category: 'power',
    mount: 'centre of the board underside', size: [0.045, 0.016, 0.035],
  });
  const board = new THREE.Group();
  put(board, box(0.044, 0.0016, 0.032, M.pcbBlue), 0, 0.0008, 0);
  put(board, smd(0.03, 0.02, 14, 21, 0.0016, [[0, 0, 0.026, 0.012]]), 0, 0, 0.004);
  for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) put(board, cyl(0.0016, 0.0016, 0.0017, M.steel, 12), sx * 0.019, 0.0009, sz * 0.0135);
  put(board, decal('Vin 12 V    LED  ▸', 0.03, '+y', { color: '#dfe7ef', font: '600 48px ' + FONT }), 0, 0.00165, -0.0125);
  addPart(c, 'board', 'Driver board', board, vec(0, -0.025, 0), 'Small carrier for the driver module, terminals and the dim header.');
  const mod = new THREE.Group();
  put(mod, rbox(0.0221, 0.0095, 0.0126, 0.0008, M.plasticBlack), 0, 0.0048 + 0.002, 0);
  put(mod, decal('RECOM\nRCD-24-0.70', 0.016, '+y', { color: '#e6e9ee', font: '600 44px ' + FONT }), 0, 0.0116, 0);
  const pins = [];
  for (let i = 0; i < 6; i++) pins.push([-0.009 + i * 0.0036, 0.0012, 0.004]);
  mod.add(instanced(new THREE.BoxGeometry(0.0006, 0.0028, 0.0004), M.solder, pins));
  addPart(c, 'module', 'RCD-24 buck module', mod, vec(0, 0.03, 0), 'Constant-current buck converter with analogue and PWM dimming inputs.');
  c.parts[c.parts.length - 1].object.position.set(0, 0.0016, -0.002);
  const tin = put(new THREE.Group(), screwTerminal(2), 0, 0, 0); tin.rotation.y = Math.PI;
  addPart(c, 'termIn', 'Input terminal (12 V from the DC-DC)', tin, vec(-0.025, 0, 0), '12 V from the ignition-sensed converter.');
  tin.position.set(-0.018, 0.0016, 0.006);
  const tout = put(new THREE.Group(), screwTerminal(2), 0, 0, 0);
  addPart(c, 'termOut', 'Output terminal (LED string)', tout, vec(0.025, 0, 0), 'Constant current to the backlight LEDs.');
  tout.position.set(0.018, 0.0016, 0.006);
  const dim = put(new THREE.Group(), header(3, 1), 0, 0, 0); dim.rotation.y = Math.PI / 2;
  put(dim, decal('PWM  ADIM  GND', 0.012, '+y', { color: '#dfe7ef', font: '600 44px ' + FONT }), -0.004, 0.0002, 0).rotation.z = 0;
  addPart(c, 'dim', 'Dim header (PWM, analogue, ground)', dim, vec(0, 0.012, 0.02), 'From the RP2040: PWM above 2 kHz and an analogue level.');
  dim.position.set(0.004, 0.0016, 0.012);
  // demo load: a short lead to a white LED star
  const load = new THREE.Group();
  put(load, cable([[0.022, 0.006, 0.0045], [0.035, 0.008, 0.004], [0.05, 0.004, 0.0]], 0.0008, M.cableRed), 0, 0, 0);
  put(load, cable([[0.022, 0.006, 0.0075], [0.035, 0.008, 0.008], [0.05, 0.004, 0.004]], 0.0008, M.cableBlack), 0, 0, 0);
  const star = new THREE.Group(); star.position.set(0.058, 0.002, 0.002); load.add(star);
  put(star, cyl(0.010, 0.010, 0.0016, M.mcpcb, 6), 0, 0, 0);
  const lm = M.led(0xfff1d6, 0);
  put(star, box(0.0035, 0.0012, 0.0035, M.ceramic), 0, 0.0014, 0);
  put(star, cyl(0.0014, 0.0014, 0.0006, lm, 16), 0, 0.0023, 0);
  const lg = glow(0xfff1d6, 0.03, 0); lg.position.y = 0.004; star.add(lg);
  addPart(c, 'load', 'Demo load: one LED of the backlight string', load, vec(0.03, 0, 0), 'Stands in for the 6–8 LED backlight string built in the PGU.');

  const fx = new THREE.Group(); fx.visible = false; c.group.add(fx);
  const pnl = livePanel(820, 420, 0.11); pnl.obj.position.set(0, 0.06, 0); fx.add(pnl.obj);
  const st = { duty: 0.6, adim: 1 };
  c.assembly = [
    { title: 'Board', parts: ['board'], text: 'Carrier board.' },
    { title: 'Driver module', parts: ['module'], text: 'Solder the RCD-24 module.' },
    { title: 'Terminals and dim header', parts: ['termIn', 'termOut', 'dim'], text: '12 V in, LED string out, PWM and analogue dim from the controller.' },
    { title: 'Connect the LED string', parts: ['load'], text: 'The backlight LEDs in series on the output.' },
  ];
  c.facts = [
    ['Type', 'constant-current buck with analogue + PWM dimming (Recom RCD-24 class, about $18)'],
    ['PWM', 'above 2 kHz to avoid a beat with the cameras; Mean Well NLDD-H rejected (PWM ≤ 1 kHz)'],
    ['LED power', `${R.P_LED.toFixed(1)} W Lambertian design; ${(R.P_LED / R.GAIN_FILM).toFixed(1)} W with prism films (gain ${R.GAIN_FILM}, ASSUMED)`],
    ['Supply', '12 V rail from the DC-DC converter'],
    ['Current variant', '0.70 A shown (example); choose with the LED string'],
    ['Cost', cost('Backlight')],
  ];
  c.desc = 'Holds the backlight LEDs at a constant current, whatever their temperature, and dims them in two ways: an analogue level that lowers the current, and PWM that switches it on and off thousands of times a second.';
  c.working = 'The PWM input above 2 kHz chops the constant current; the analogue input sets its height; the LED brightness follows the average.';
  c.setWorking = (on) => { fx.visible = on; if (!on) { lm.emissiveIntensity = 0; lg.material.opacity = 0; } };
  c.update = (t, dt, s) => {
    if (!s || !s.working) return;
    st.duty = 0.15 + 0.8 * (0.5 + 0.5 * Math.sin(t * 0.6));
    st.adim = 0.55 + 0.45 * (0.5 + 0.5 * Math.sin(t * 0.23 + 1));
    const avg = st.duty * st.adim;
    lm.emissiveIntensity = 0.5 + 4 * avg; lg.material.opacity = Math.min(1, avg * 1.2);
    pnl.tick(dt, 15, (ctx, W, H) => {
      panelBg(ctx, W, H, 'Constant current, two ways to dim', 'PWM above 2 kHz (shown 4 periods) × analogue level');
      const x0 = 30, w = W - 60;
      const trace = (y0, h, hi, color, label) => {
        ctx.strokeStyle = 'rgba(255,255,255,0.12)'; ctx.strokeRect(x0, y0, w, h);
        ctx.strokeStyle = color; ctx.lineWidth = 3; ctx.beginPath();
        const per = w / 4;
        for (let i = 0; i < 4; i++) { const xa = x0 + i * per; ctx.moveTo(xa, y0 + h - 6); ctx.lineTo(xa, y0 + h - 6 - (h - 14) * hi); ctx.lineTo(xa + per * st.duty, y0 + h - 6 - (h - 14) * hi); ctx.lineTo(xa + per * st.duty, y0 + h - 6); ctx.lineTo(xa + per, y0 + h - 6); }
        ctx.stroke(); txt(ctx, label, x0 + 6, y0 - 14, { size: 19, color: '#8fa3b6' });
      };
      trace(118, 90, 1, '#c78bff', `PWM input · duty ${(st.duty * 100).toFixed(0)}%`);
      trace(260, 110, st.adim, '#ffd27a', `LED current · ${(700 * st.adim).toFixed(0)} mA peak (analogue ${(st.adim * 100).toFixed(0)}%)`);
      txt(ctx, `average ${(700 * avg).toFixed(0)} mA → brightness ${(avg * 100).toFixed(0)}%`, x0, 396, { size: 22, color: '#eef4fa', weight: 600 });
    });
  };
  return c;
}

// ---- Mini-Box DCDC-USB-200 -----------------------------------------------------------
export function buildDcdc() {
  const c = makeComponent(THREE, {
    id: 'dcdc', name: 'Mini-Box DCDC-USB-200 (ignition-sensed converter)', category: 'power',
    mount: 'centre of the enclosure underside; terminal end faces -X, output end +X', size: [0.095, 0.028, 0.062],
  });
  const L = 0.086, Hh = 0.026, D = 0.060;
  const pcb = new THREE.Group();
  put(pcb, box(0.080, 0.0016, 0.054, M.pcbGreen), 0, 0.006, 0);
  put(pcb, smd(0.07, 0.05, 50, 33, 0.0068), 0, 0, 0);
  const coil = new THREE.Mesh(new THREE.TorusGeometry(0.0075, 0.0035, 12, 24), MX.coil); coil.rotation.x = Math.PI / 2; coil.position.set(0.004, 0.0105, -0.008); pcb.add(coil);
  put(pcb, cyl(0.0042, 0.0042, 0.003, MX.ferrite, 20), 0.004, 0.0105, -0.008);
  for (const [x, z] of [[-0.022, 0.012], [-0.012, 0.016], [0.022, 0.014]]) { put(pcb, cyl(0.004, 0.004, 0.011, MX.electrolytic, 20), x, 0.0123, z); put(pcb, cyl(0.0041, 0.0041, 0.0004, M.steel, 20), x, 0.0181, z); }
  for (let i = 0; i < 3; i++) put(pcb, chip(0.0065, 0.005, 0.0016, 'FET', 0.004), 0.024, 0.0068, -0.016 + i * 0.008);
  put(pcb, chip(0.006, 0.006, 0.001, 'PIC', 0.004), -0.012, 0.0068, -0.012);
  const ledG = put(pcb, led(0x46ff7a, 0.002, 0.0012, 0.002), 0.038, 0.0076, 0.018);
  const ledY = put(pcb, led(0xffb020, 0.002, 0.0012, 0.002), 0.038, 0.0076, 0.013);
  addPart(c, 'pcb', 'Converter board', pcb, vec(0, 0.05, 0), 'Buck-boost converter with a microcontroller that watches the ignition line and the input voltage.');
  const shell = new THREE.Group();
  put(shell, box(L, 0.0015, D, M.aluDark), 0, Hh - 0.00075, 0);
  put(shell, box(L, 0.0015, D, M.aluDark), 0, 0.00075, 0);
  put(shell, box(L, Hh, 0.0015, M.aluDark), 0, Hh / 2, D / 2 - 0.00075);
  put(shell, box(L, Hh, 0.0015, M.aluDark), 0, Hh / 2, -D / 2 + 0.00075);
  for (let i = 0; i < 8; i++) put(shell, box(L, 0.0012, 0.0012, M.aluDark), 0, Hh + 0.0005, -0.025 + i * 0.0072);
  put(shell, decal('DCDC-USB-200', 0.04, '+y', { color: '#d5d9de', font: '600 48px ' + FONT }), 0, Hh + 0.0012, 0.0);
  addPart(c, 'shell', 'Extruded enclosure', shell, vec(0, 0, -0.08), 'Aluminium extrusion; slides off the board.');
  const endIn = new THREE.Group();
  put(endIn, box(0.003, Hh, D, M.plasticBlack), 0, Hh / 2, 0);
  const tb = put(endIn, screwTerminal(4), -0.0015, 0.004, 0); tb.rotation.y = Math.PI;
  put(endIn, decal('V+  GND  IGN  GND', 0.032, '-x', { color: '#dfe3e8', font: '600 44px ' + FONT }), -0.0017, 0.020, 0);
  addPart(c, 'endIn', 'Input end: 12 V, ground, ignition sense', endIn, vec(-0.04, 0, 0), 'Fused 12 V accessory feed and the ignition-sense wire.');
  endIn.position.set(-L / 2 - 0.0015, 0, 0);
  const endOut = new THREE.Group();
  put(endOut, box(0.003, Hh, D, M.plasticBlack), 0, Hh / 2, 0);
  put(endOut, screwTerminal(2), 0.0015, 0.004, -0.012);
  put(endOut, Port.microUsb(), 0.0016, 0.012, 0.012);
  const ol1 = put(endOut, led(0x46ff7a, 0.0008, 0.002, 0.002), 0.0016, 0.020, 0.018);
  const ol2 = put(endOut, led(0xffb020, 0.0008, 0.002, 0.002), 0.0016, 0.020, 0.022);
  put(endOut, decal('CONFIG   OUT 12 V', 0.03, '+x', { color: '#dfe3e8', font: '600 44px ' + FONT }), 0.0017, 0.0205, -0.006);
  addPart(c, 'endOut', 'Output end: regulated 12 V and the USB configuration port', endOut, vec(0.04, 0, 0), 'Feeds the Jetson and the LED driver.');
  endOut.position.set(L / 2 + 0.0015, 0, 0);

  const fx = new THREE.Group(); fx.visible = false; c.group.add(fx);
  const pnl = livePanel(820, 420, 0.13); pnl.obj.position.set(0, 0.075, 0); fx.add(pnl.obj);
  c.assembly = [
    { title: 'Board', parts: ['pcb'], text: 'The converter board.' },
    { title: 'Enclosure', parts: ['shell'], text: 'Slide the board into the extrusion.' },
    { title: 'End plates', parts: ['endIn', 'endOut'], text: 'Input terminals with the ignition sense; output terminals and the configuration USB.' },
  ];
  c.facts = [
    ['Job', 'ignition-sensed 12 V supply with configurable shutdown delays and a deep-discharge cut-off'],
    ['Cut-off', '11.2 V'],
    ['Feeds', 'the Jetson (9–19 V input) and the LED driver'],
    ['Why', 'a bare converter would corrupt the Jetson\'s filesystem at key-off'],
    ['Vehicle link', 'only the fused 12 V accessory feed; no wire to any vehicle bus'],
    ['Cost', cost('DC-DC')],
  ];
  c.desc = 'Sits between the car\'s 12 V accessory feed and the Jetson. It watches the ignition line: on key-on it powers up; on key-off it waits a set delay, tells the Jetson to shut down cleanly, then cuts power. It also cuts out if the battery sags below 11.2 V.';
  c.working = 'Ignition on: the output comes up. Ignition off: a shutdown countdown runs, the Jetson is told to shut down, then the output goes off.';
  const st = { phase: '' };
  c.setWorking = (on) => { fx.visible = on; if (!on) [ledG, ledY, ol1, ol2].forEach((l) => l.userData.set(0)); };
  c.update = (t, dt, s) => {
    if (!s || !s.working) return;
    const ph = t % 20;
    let ign, out, msg, cd = 0;
    if (ph < 1) { ign = false; out = false; msg = 'parked: output off'; }
    else if (ph < 2) { ign = true; out = ph > 1.5; msg = 'ignition on → output on'; }
    else if (ph < 10) { ign = true; out = true; msg = 'running: Jetson and LED driver powered'; }
    else if (ph < 16) { ign = false; out = true; cd = 16 - ph; msg = 'ignition off → shutdown delay running'; }
    else if (ph < 18) { ign = false; out = true; msg = 'Jetson told to shut down; filesystem synced'; }
    else { ign = false; out = false; msg = 'hard off'; }
    const vin = ign ? 13.8 : 12.5;
    ledY.userData.set(ign ? 1 : 0.05); ol2.userData.set(ign ? 1 : 0.05);
    ledG.userData.set(out ? 1 : 0.05); ol1.userData.set(out ? 1 : 0.05);
    pnl.tick(dt, 12, (ctx, W, H) => {
      panelBg(ctx, W, H, 'Ignition-sensed power', 'delays shown sped up; the real delay is configurable');
      lamp(ctx, 40, 120, ign, 'rgb(255,192,77)', `ignition ${ign ? 'ON' : 'OFF'}`);
      lamp(ctx, 40, 165, out, 'rgb(79,209,139)', `12 V output ${out ? 'ON' : 'OFF'}`);
      txt(ctx, `input ${vin.toFixed(1)} V (cut-off 11.2 V)`, 420, 120, { size: 22 });
      txt(ctx, msg, 30, 230, { size: 26, color: '#eef4fa', weight: 600 });
      if (cd > 0) {
        ctx.fillStyle = 'rgba(255,255,255,0.08)'; ctx.fillRect(30, 270, W - 60, 30);
        ctx.fillStyle = '#ffc04d'; ctx.fillRect(30, 270, (W - 60) * cd / 6, 30);
        txt(ctx, `shutdown in ${cd.toFixed(1)} s (example)`, 30, 330, { size: 22, color: '#ffd27a' });
      }
    });
  };
  return c;
}

// ---- Fuse tap: 12 V plug + inline fuse ------------------------------------------------------
export function buildFuseTap() {
  const c = makeComponent(THREE, {
    id: 'fuseTap', name: '12 V accessory plug and inline fuse', category: 'power',
    mount: 'tip of the 12 V plug at the origin; the lead runs toward -X', size: [0.26, 0.03, 0.06],
  });
  const plug = new THREE.Group();
  put(plug, cylX(0.0105, 0.045, M.plasticBlack, 32), -0.0275, 0, 0);
  put(plug, cylX(0.0032, 0.006, M.steel, 16), -0.002, 0, 0);
  for (const s of [-1, 1]) { const sp = box(0.022, 0.0012, 0.004, M.steel); sp.position.set(-0.03, s * 0.0108, 0); sp.rotation.z = s * 0.06; plug.add(sp); }
  put(plug, cylX(0.0135, 0.022, M.plasticGrey, 32), -0.061, 0, 0);
  for (let i = 0; i < 6; i++) { const r = new THREE.Mesh(new THREE.TorusGeometry(0.0136, 0.0007, 6, 32), M.plasticBlack); r.rotation.y = Math.PI / 2; r.position.x = -0.054 - i * 0.0028; plug.add(r); }
  const pl = put(plug, led(0xff4040, 0.0008, 0.003, 0.003), -0.0722, 0, 0);
  addPart(c, 'plug', '12 V accessory-socket plug', plug, vec(0.04, 0, 0), 'Fused 12 V from the accessory socket: the only connection to the car.');
  const lead = new THREE.Group();
  put(lead, cable([[-0.072, 0, 0.002], [-0.10, 0.004, 0.01], [-0.13, 0.0, 0.012], [-0.155, 0, 0.004]], 0.0022, M.cableRed), 0, 0, 0);
  put(lead, cable([[-0.072, 0, -0.002], [-0.10, -0.004, -0.008], [-0.13, 0.0, -0.018], [-0.20, 0, -0.02], [-0.25, 0, -0.016]], 0.0022, M.cableBlack), 0, 0, 0);
  put(lead, cable([[-0.195, 0, 0.004], [-0.22, 0.002, 0.006], [-0.25, 0, 0.008]], 0.0022, M.cableRed), 0, 0, 0);
  for (const [z, m] of [[0.008, M.cableRed], [-0.016, M.cableBlack]]) { put(lead, cylX(0.0028, 0.008, m, 12), -0.254, 0, z); put(lead, cylX(0.0011, 0.010, M.steel, 8), -0.262, 0, z); }
  addPart(c, 'lead', 'Twin lead with ferrules', lead, vec(-0.02, -0.02, 0), 'Red to the DC-DC V+ through the fuse; black to ground.');
  const fuse = new THREE.Group();
  put(fuse, rbox(0.040, 0.012, 0.016, 0.003, M.plasticBlack), -0.175, 0, 0.004);
  const cap = put(new THREE.Group(), rbox(0.018, 0.0125, 0.0165, 0.003, MX.redPlastic), -0.168, 0, 0.004);
  fuse.add(cap);
  addPart(c, 'fuseHolder', 'Inline ATO blade-fuse holder', fuse, vec(0, 0.03, 0), 'Protects the wiring; sized to the measured draw.');
  const blade = new THREE.Group();
  put(blade, box(0.0192, 0.0127, 0.0051, mat('fuseBlade', () => new THREE.MeshPhysicalMaterial({ color: 0xc8a020, transparent: true, opacity: 0.75, roughness: 0.2 }))), 0, 0, 0);
  put(blade, decal('7.5', 0.006, '+z', { color: '#3a2a00', font: '700 64px ' + FONT }), 0, 0.002, 0.0027);
  for (const s of [-1, 1]) put(blade, box(0.0028, 0.007, 0.0008, M.steel), s * 0.0045, -0.009, 0);
  addPart(c, 'fuse', 'Blade fuse (rating to the measured draw; 7.5 A shown)', blade, vec(0, 0.06, 0.02), 'Example rating; the real value follows the measured draw.');
  blade.position.set(-0.175, 0.0, 0.004);
  const fx = new THREE.Group(); fx.visible = false; c.group.add(fx);
  const curve = new THREE.CatmullRomCurve3([vec(-0.072, 0, 0.002), vec(-0.10, 0.004, 0.01), vec(-0.13, 0, 0.012), vec(-0.175, 0.008, 0.004), vec(-0.22, 0.002, 0.006), vec(-0.25, 0, 0.008)]);
  const dots = [];
  for (let i = 0; i < 12; i++) { const d = sphere(0.0018, M.emissive(0xffd27a, 2), 8); fx.add(d); dots.push(d); }
  const pnl = livePanel(640, 200, 0.10); pnl.obj.position.set(-0.13, 0.05, 0); fx.add(pnl.obj);
  pnl.draw((ctx, W, H) => { panelBg(ctx, W, H, '≈ 3 A at 12 V (estimate)'); txt(ctx, 'Jetson ≤ 25 W + backlight LEDs 12.6 W', 22, 110, { size: 22 }); txt(ctx, 'fused; no other wire to the car', 22, 150, { size: 22, color: '#9fe6bd' }); });
  c.assembly = [
    { title: 'Plug', parts: ['plug'], text: 'The 12 V accessory-socket plug.' },
    { title: 'Lead', parts: ['lead'], text: 'Twin lead, crimped ferrules for the DC-DC terminals.' },
    { title: 'Fuse holder and fuse', parts: ['fuseHolder', 'fuse'], text: 'Inline in the positive lead, close to the plug.' },
  ];
  c.facts = [
    ['Role', 'the only vehicle interface: a fused, ignition-sensed 12 V accessory feed'],
    ['Load', 'about 3 A at 12 V (estimate: Jetson ≤ 25 W plus 12.6 W of LEDs)'],
    ['Fuse', 'sized to the measured draw (7.5 A shown as an example)'],
    ['Checklist', 'fuse in place, no connector to any vehicle bus, signed before each drive'],
    ['Cost', cost('USB-C PD')],
  ];
  c.desc = 'The single connection to the car: a plug in the accessory socket with a fuse in the positive lead. Everything else in the HUD runs from the converter downstream of it.';
  c.working = 'Current flows from the plug through the fuse toward the converter.';
  c.setWorking = (on) => { fx.visible = on; pl.userData.set(on ? 1 : 0); };
  c.update = (t, dt, s) => { if (!s || !s.working) return; dots.forEach((d, i) => d.position.copy(curve.getPoint(((t * 0.4 + i / dots.length) % 1)))); };
  return c;
}

// ---- Ethernet switch -------------------------------------------------------------------
export function buildEthSwitch() {
  const c = makeComponent(THREE, {
    id: 'ethSwitch', name: 'Gigabit Ethernet switch, 5 ports', category: 'network',
    mount: 'centre of the underside; LEDs face +X, ports -X', size: [0.07, 0.024, 0.10],
  });
  const X = 0.068, Hh = 0.022, Z = 0.099;
  const bottom = new THREE.Group();
  put(bottom, rbox(X, 0.008, Z, 0.003, M.plasticBlack), 0, 0.004, 0);
  for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) put(bottom, cyl(0.004, 0.004, 0.0012, M.rubber, 12), sx * 0.026, -0.0002, sz * 0.04);
  addPart(c, 'bottom', 'Lower shell', bottom, vec(0, -0.03, 0), 'Lower case half.');
  const pcb = new THREE.Group();
  put(pcb, box(X - 0.006, 0.0016, Z - 0.006, M.pcbGreen), 0, 0.0055, 0);
  put(pcb, chip(0.014, 0.014, 0.0014, 'GbE SWITCH', 0.012), 0.01, 0.0063, 0);
  for (let i = 0; i < 5; i++) { put(pcb, Port.rj45(), -X / 2 - 0.0004, 0.0131, -0.040 + i * 0.017, 0, Math.PI, 0); put(pcb, chip(0.005, 0.009, 0.002, '', 0), -0.006, 0.0063, -0.040 + i * 0.017); }
  put(pcb, Port.dcJack(), -X / 2 - 0.0004, 0.0118, 0.045, 0, Math.PI, 0).scale.setScalar(0.8);
  const leds = [];
  for (let i = 0; i < 6; i++) leds.push(put(pcb, led(i === 0 ? 0x46ff7a : 0x5aff9a, 0.0008, 0.002, 0.002), X / 2 + 0.0004, 0.012, -0.040 + i * 0.016));
  put(pcb, smd(0.05, 0.08, 40, 77, 0.0063, [[0.01, 0, 0.016, 0.016], [-0.02, 0, 0.02, 0.1]]), 0, 0, 0);
  addPart(c, 'pcb', 'Switch board with ports', pcb, vec(0, 0.02, 0), 'Five gigabit ports: Jetson, mini PC 2 and spares.');
  const topS = new THREE.Group();
  put(topS, rbox(X, Hh - 0.008, Z, 0.003, M.plasticBlack), 0, 0.008 + (Hh - 0.008) / 2, 0);
  ['PWR', '1', '2', '3', '4', '5'].forEach((t, i) => put(topS, decal(t, t.length > 1 ? 0.0055 : 0.0022, '+x', { color: '#9aa3ad', font: '600 48px ' + FONT }), X / 2 + 0.0002, 0.0165, -0.040 + i * 0.016));
  put(topS, decal('GIGABIT SWITCH', 0.04, '+y', { color: '#9aa3ad', font: '600 48px ' + FONT }), 0.01, Hh + 0.0001, 0);
  addPart(c, 'top', 'Upper shell', topS, vec(0, 0.05, 0), 'Upper case half with the port legend.');
  c.assembly = [
    { title: 'Lower shell', parts: ['bottom'], text: '' },
    { title: 'Board', parts: ['pcb'], text: 'Switch chip, magnetics, five RJ45 ports and the DC jack.' },
    { title: 'Close', parts: ['top'], text: 'Jetson on port 1, mini PC 2 on port 2.' },
  ];
  c.facts = [
    ['Role', 'Ethernet link from the Jetson to mini PC 2 for the audience view'],
    ['Stream', 'MJPEG over HTTP at 15 Hz (the J401 has one HDMI port, used by the panel)'],
    ['Power', 'USB or 12 V from the PD charger side of the wiring'],
    ['Cost', cost('USB-C PD')],
  ];
  c.desc = 'A small gigabit switch that links the Jetson to the passenger-side mini PC, which shows the audience view on the second monitor.';
  c.working = 'Link LEDs light for the two used ports and blink with traffic.';
  c.setWorking = (on) => { if (!on) leds.forEach((l) => l.userData.set(0)); };
  c.update = (t, dt, s) => {
    if (!s || !s.working) return;
    leds[0].userData.set(1);
    leds[1].userData.set(Math.sin(t * 31) > -0.2 ? 1 : 0.1);
    leds[2].userData.set(Math.sin(t * 17 + 1) > 0 ? 1 : 0.1);
    for (let i = 3; i < 6; i++) leds[i].userData.set(0.03);
  };
  return c;
}

// ---- USB-C PD car charger ---------------------------------------------------------------
export function buildPdCharger() {
  const c = makeComponent(THREE, {
    id: 'pdCharger', name: 'USB-C PD car charger', category: 'power',
    mount: 'tip of the plug at the origin, pointing -X into the socket; ports face +X', size: [0.065, 0.032, 0.032],
  });
  const body = new THREE.Group();
  put(body, cylX(0.0105, 0.045, M.plasticBlack, 32), 0.0245, 0, 0);
  put(body, cylX(0.003, 0.005, M.steel, 16), 0.0015, 0, 0);
  for (const s of [-1, 1]) { const sp = box(0.02, 0.0012, 0.004, M.steel); sp.position.set(0.026, 0, s * 0.0108); sp.rotation.y = s * 0.05; body.add(sp); }
  addPart(c, 'plug', 'Socket plug', body, vec(-0.03, 0, 0), 'Fits the second 12 V socket.');
  const pcb = new THREE.Group();
  put(pcb, box(0.036, 0.0012, 0.017, M.pcbBlack), 0.024, 0, 0);
  put(pcb, chip(0.005, 0.005, 0.001, 'PD', 0.004), 0.02, 0.0006, 0);
  const ind = new THREE.Mesh(new THREE.TorusGeometry(0.003, 0.0014, 8, 16), MX.coil); ind.position.set(0.03, 0.003, 0); ind.rotation.x = Math.PI / 2; pcb.add(ind);
  addPart(c, 'pcb', 'PD controller board', pcb, vec(0, 0.03, 0), 'Negotiates USB Power Delivery voltage with each device.');
  const head = new THREE.Group();
  put(head, cylX(0.016, 0.014, M.aluDark, 40), 0.054, 0, 0);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.0145, 0.0008, 8, 48), M.led(0x3d8bff, 0)); ring.rotation.y = Math.PI / 2; ring.position.x = 0.0612; head.add(ring);
  put(head, Port.usbC(), 0.0612, 0.005, 0);
  put(head, Port.usbC(), 0.0612, -0.005, 0);
  put(head, decal('PD', 0.004, '+x', { color: '#c9ced4', font: '700 48px ' + FONT }), 0.0613, 0, 0.0095);
  addPart(c, 'head', 'Head with two USB-C PD ports', head, vec(0.03, 0, 0), 'Feeds mini PC 2 and monitor 2.');
  c.assembly = [
    { title: 'Plug', parts: ['plug'], text: '' },
    { title: 'Board', parts: ['pcb'], text: '' },
    { title: 'Head', parts: ['head'], text: 'Two USB-C PD ports.' },
  ];
  c.facts = [
    ['Feeds', 'mini PC 2 and monitor 2 (audience view)'],
    ['Check', 'that the mini PC accepts USB-C PD input (many take a barrel jack) (UNVERIFIED)'],
    ['Cost', cost('USB-C PD')],
  ];
  c.desc = 'Powers the passenger-side audience display chain, so it does not load the Jetson\'s converter.';
  c.working = 'The ring LED lights when power is negotiated.';
  c.setWorking = (on) => { ring.material.emissiveIntensity = on ? 2 : 0; };
  c.update = (t, dt, s) => { if (s && s.working) ring.material.emissiveIntensity = 1.6 + 0.6 * Math.sin(t * 2); };
  return c;
}

// ---- ACEMAGIC mini PC -------------------------------------------------------------------------
export function buildMiniPC() {
  const c = makeComponent(THREE, {
    id: 'miniPC', name: 'ACEMAGIC mini PC (unit 2, audience view)', category: 'compute',
    mount: 'centre of the underside; front ports face +X', size: [0.128, 0.041, 0.128],
  });
  const S = 0.128, Hh = 0.041;
  const base = new THREE.Group();
  put(base, rbox(S, 0.004, S, 0.008, M.plasticBlack), 0, 0.002, 0);
  for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) put(base, cyl(0.006, 0.006, 0.0015, M.rubber, 16), sx * 0.048, -0.0005, sz * 0.048);
  addPart(c, 'base', 'Bottom cover', base, vec(0, -0.05, 0), '');
  const mb = new THREE.Group();
  put(mb, box(0.112, 0.0016, 0.112, M.pcbBlack), 0, 0.007, 0);
  put(mb, smd(0.1, 0.1, 120, 55, 0.0078, [[0.0, 0, 0.04, 0.04], [-0.03, 0, 0.03, 0.08]]), 0, 0, 0);
  put(mb, chip(0.03, 0.03, 0.0015, 'CPU', 0.02), 0.0, 0.0078, 0);
  for (const z of [-0.02, 0.0]) { put(mb, box(0.07, 0.004, 0.006, M.plasticBlack), -0.02, 0.0098, z + 0.035); }
  const ram = new THREE.Group(); put(ram, box(0.07, 0.0012, 0.030, M.pcbGreen), 0, 0, 0);
  for (let i = 0; i < 4; i++) put(ram, chip(0.009, 0.010, 0.001, '', 0), -0.025 + i * 0.017, 0.0006, 0);
  ram.position.set(-0.02, 0.0125, 0.038); mb.add(ram);
  const io = 0.0645;
  put(mb, Port.usbA(), io, 0.0125, -0.03); put(mb, Port.usbA(), io, 0.0125, -0.012); put(mb, Port.usbC(), io, 0.0110, 0.005);
  put(mb, cylX(0.0035, 0.006, M.flock, 16), io - 0.002, 0.0115, 0.018);
  for (const [x, z, k] of [[-io, -0.04, 'dc'], [-io, -0.024, 'hdmi'], [-io, -0.005, 'hdmi'], [-io, 0.016, 'rj'], [-io, 0.037, 'usb']]) {
    const p = k === 'dc' ? Port.dcJack() : k === 'hdmi' ? Port.hdmi() : k === 'rj' ? Port.rj45() : Port.usbA();
    put(mb, p, x, k === 'rj' ? 0.0158 : 0.0125, z, 0, Math.PI, 0);
  }
  addPart(c, 'mainboard', 'Mainboard with RAM and ports', mb, vec(0, 0.0, 0), 'x86 board; no CUDA, so it runs the renderer bench and the audience view only.');
  const cooler = new THREE.Group();
  const fan = axialFan(0.05, 0.008, 9); fan.position.set(0.02, 0.021, -0.025); cooler.add(fan);
  const fins = [];
  for (let i = 0; i < 14; i++) fins.push([-0.025, 0.02, -0.05 + i * 0.0035]);
  cooler.add(instanced(new THREE.BoxGeometry(0.03, 0.014, 0.0006), M.alu, fins));
  put(cooler, box(0.035, 0.002, 0.035, M.copper), 0.0, 0.0095, 0);
  addPart(c, 'cooler', 'CPU cooler and fan', cooler, vec(0, 0.06, 0), '');
  const shell = new THREE.Group();
  for (const [x, z, w, d] of [[S / 2 - 0.0012, 0, 0.0024, S], [-S / 2 + 0.0012, 0, 0.0024, S], [0, S / 2 - 0.0012, S - 0.005, 0.0024], [0, -S / 2 + 0.0012, S - 0.005, 0.0024]]) put(shell, box(w, Hh - 0.006, d, MX.greyPlastic), x, 0.004 + (Hh - 0.006) / 2, z);
  const pw = put(shell, led(0x5aa8ff, 0.0006, 0.0025, 0.0025), S / 2 + 0.0002, 0.0115, 0.018);
  for (const [t, z, w] of [['USB', -0.03, 0.0065], ['USB', -0.012, 0.0065], ['USB-C', 0.005, 0.009], ['⏻', 0.018, 0.0035]]) put(shell, decal(t, w, '+x', { color: '#c9ced4', font: '500 44px ' + FONT }), S / 2 + 0.0002, 0.0205, z);
  for (let i = 0; i < 10; i++) put(shell, box(0.08, 0.0012, 0.0004, M.flock), 0, 0.01 + i * 0.0026, S / 2 + 0.0001);
  addPart(c, 'shell', 'Case walls', shell, vec(0, 0, 0), '');
  const lid = new THREE.Group();
  put(lid, rbox(S, 0.004, S, 0.008, MX.silverPlastic), 0, Hh - 0.002, 0);
  put(lid, decal('ACEMAGIC', 0.04, '+y', { color: '#5a5f66', font: '700 48px ' + FONT }), 0, Hh + 0.0001, 0);
  addPart(c, 'lid', 'Top cover', lid, vec(0, 0.12, 0), '');
  const fx = new THREE.Group(); fx.visible = false; c.group.add(fx);
  const pnl = livePanel(700, 180, 0.12); pnl.obj.position.set(0, Hh + 0.05, 0); fx.add(pnl.obj);
  pnl.draw((ctx, W, H) => { panelBg(ctx, W, H, 'Mini PC 2 · audience view'); txt(ctx, 'MJPEG 15 Hz from the Jetson over Ethernet → monitor 2', 22, 110, { size: 22 }); });
  c.assembly = [
    { title: 'Bottom cover', parts: ['base'], text: '' },
    { title: 'Mainboard', parts: ['mainboard'], text: '' },
    { title: 'Cooler', parts: ['cooler'], text: '' },
    { title: 'Case', parts: ['shell', 'lid'], text: '' },
  ];
  c.facts = [
    ['Unit 1', 'x86 renderer bench and CI: topic replay, hudd from logs, clip tool, unit tests'],
    ['Unit 2', 'audience view in the car (Ethernet stream to monitor 2) and nightly clip regressions'],
    ['GPU', 'no CUDA: no perception on these'],
    ['Cost', 'owned (two units)'],
  ];
  c.desc = 'One of the two owned x86 mini PCs. In the car, unit 2 receives the Jetson\'s audience stream over Ethernet and shows it on the passenger-side monitor; on the bench, it renders recorded logs for regression clips.';
  c.working = 'Power LED on, fan spinning, receiving the audience stream.';
  c.setWorking = (on) => { fx.visible = on; pw.userData.set(on ? 1 : 0); };
  c.update = (t, dt, s) => { if (s && s.working) fan.userData.rotor.rotation.y -= dt * 30; };
  return c;
}

// ---- YODOIT 16-inch monitor -------------------------------------------------------------------
export function buildMonitor() {
  const c = makeComponent(THREE, {
    id: 'monitor', name: 'YODOIT 16-inch 3840 × 2400 monitor (unit 2)', category: 'display',
    mount: 'centre of the screen; the screen faces +X', size: [0.03, 0.26, 0.36],
  });
  const AW = 0.3446, AH = 0.2154, OW = 0.357, OH = 0.233, T = 0.008;
  const back = new THREE.Group();
  put(back, rbox(T - 0.002, OH, OW, 0.006, M.aluDark), -0.002, 0, 0);
  for (const y of [-0.07, -0.05]) {
    const holder = put(back, new THREE.Group(), -0.002, y, -OW / 2 - 0.0002, 0, Math.PI / 2, 0);
    put(holder, Port.usbC(), 0, 0, 0, Math.PI / 2, 0, 0);
  }
  put(back, box(0.0036, 0.0105, 0.002, M.steel), -0.002, -0.03, -OW / 2 - 0.0005);
  put(back, decal('YODOIT · 16" 3840 × 2400 · 1,200 nit', 0.12, '-x', { color: '#9aa3ad', font: '500 48px ' + FONT }), -0.0052, -0.08, 0);
  addPart(c, 'back', 'Rear shell with USB-C and mini-HDMI', back, vec(-0.05, 0, 0), '');
  const panel = new THREE.Group();
  put(panel, rbox(0.002, OH, OW, 0.006, M.plasticBlack), 0.002, 0, 0);
  const scrTex = defaultAudienceTexture();
  const scr = new THREE.Mesh(new THREE.PlaneGeometry(AW, AH), new THREE.MeshBasicMaterial({ map: scrTex, toneMapped: false }));
  scr.rotation.y = Math.PI / 2; scr.position.x = 0.0031; panel.add(scr);
  addPart(c, 'panel', 'IPS panel and bezel', panel, vec(0.04, 0, 0), '3840 × 2400, 277 ppi, 1,200 cd/m² peak.');
  // headrest bracket: two clamps on the headrest posts and a holder frame
  const br = new THREE.Group();
  for (const s of [-1, 1]) {
    put(br, rbox(0.012, 0.03, 0.012, 0.003, M.aluAnodBlack), -0.03, OH / 2 + 0.07, s * 0.075);
    put(br, cyl(0.0045, 0.0045, 0.08, M.steel, 16), -0.03, OH / 2 + 0.11, s * 0.075);
  }
  put(br, rbox(0.01, 0.012, 0.18, 0.003, M.aluAnodBlack), -0.03, OH / 2 + 0.07, 0);
  put(br, cable([[-0.03, OH / 2 + 0.065, 0], [-0.025, OH / 2 + 0.02, 0], [-0.012, 0.0, 0]], 0.004, M.aluAnodBlack), 0, 0, 0);
  for (const s of [-1, 1]) put(br, rbox(0.012, 0.03, 0.01, 0.003, M.aluAnodBlack), -0.006, s * (OH / 2 - 0.01), -OW / 2 - 0.004);
  put(br, rbox(0.01, 0.04, 0.03, 0.003, M.aluAnodBlack), -0.01, 0, 0);
  addPart(c, 'bracket', 'Headrest bracket', br, vec(-0.06, 0.06, 0), 'Clamps to the passenger headrest posts; faces the rear-seat audience. Removable without tools.');
  c.handles = {
    setScreenTexture(tex) { scr.material.map = tex || scrTex; scr.material.needsUpdate = true; },
    screen: scr,
  };
  c.assembly = [
    { title: 'Bracket', parts: ['bracket'], text: 'Clamp the holder to the headrest posts.' },
    { title: 'Monitor', parts: ['back', 'panel'], text: 'Seat the monitor; USB-C power from the PD charger, video from mini PC 2.' },
  ];
  c.facts = [
    ['Panel', '16-inch 3840 × 2400, 277 ppi, 1,200 cd/m² peak'],
    ['Unit 1', 'Stage 0/1 picture generator (80 × 40 mm crop), Phase 3 footwell display'],
    ['Unit 2', 'audience and debug display on the passenger side'],
    ['Through a 30% combiner', `${Math.round(1200 * R.PATH_COMB)} cd/m² at the eye (${(1200 * R.PATH_COMB / R.L_DAY_EYE * 100).toFixed(0)}% of the sky target)`],
    ['Cost', 'owned (two units)'],
  ];
  c.desc = 'One of the two owned 16-inch 4K monitors. Unit 2 shows the audience view: the rendered HUD frame, the driver camera with the eye point, and live registration, age and contrast numbers.';
  c.working = 'The screen shows the audience view layout; the app can feed it the live frame.';
  const fx = { on: false };
  c.setWorking = (on) => { fx.on = on; };
  c.update = (t, dt, s) => {
    if (!s || !s.working || scr.material.map !== scrTex) return;
    scrTex.userData.t = (scrTex.userData.t || 0) + dt;
    if (scrTex.userData.t > 0.25) { scrTex.userData.t = 0; drawAudience(scrTex.image.getContext('2d'), scrTex.image.width, scrTex.image.height, t); scrTex.needsUpdate = true; }
  };
  return c;
}

function defaultAudienceTexture() {
  const t = canvasTexture(1024, 640, (ctx, W, H) => drawAudience(ctx, W, H, 0));
  return t;
}
function drawAudience(ctx, W, H, t) {
  ctx.fillStyle = '#07090c'; ctx.fillRect(0, 0, W, H);
  txt(ctx, 'AUDIENCE VIEW', 30, 36, { size: 26, color: '#8fa3b6', weight: 600 });
  // HUD frame
  ctx.fillStyle = '#000'; ctx.fillRect(30, 70, 620, 310); ctx.strokeStyle = '#2b3440'; ctx.strokeRect(30, 70, 620, 310);
  ctx.fillStyle = 'rgba(94,200,255,0.35)'; ctx.beginPath(); const sh = 30 * Math.sin(t * 0.5);
  ctx.moveTo(250 + sh, 380); ctx.lineTo(320 + sh * 0.3, 140); ctx.lineTo(360 + sh * 0.3, 140); ctx.lineTo(500 + sh, 380); ctx.fill();
  ctx.strokeStyle = '#5ec8ff'; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(250 + sh, 380); ctx.lineTo(320 + sh * 0.3, 140); ctx.moveTo(500 + sh, 380); ctx.lineTo(360 + sh * 0.3, 140); ctx.stroke();
  ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.moveTo(318, 200); ctx.lineTo(340, 214); ctx.lineTo(362, 200); ctx.lineTo(362, 207); ctx.lineTo(340, 221); ctx.lineTo(318, 207); ctx.fill();
  txt(ctx, '32 m · 1.9 s', 340, 238, { size: 20, color: '#fff', align: 'center', weight: 600 });
  ctx.fillStyle = 'rgba(20,24,30,0.9)'; ctx.fillRect(48, 316, 190, 50); txt(ctx, '62 mph · limit 65', 60, 341, { size: 22, color: '#fff', weight: 600 });
  txt(ctx, 'rendered HUD frame (946 × 473 crop)', 30, 400, { size: 18, color: '#7d8b98' });
  // driver camera
  ctx.fillStyle = '#14181e'; ctx.fillRect(680, 70, 314, 236);
  ctx.fillStyle = '#3a4048'; ctx.beginPath(); ctx.ellipse(837, 190, 60, 78, 0, 0, 7); ctx.fill();
  ctx.strokeStyle = '#ffd27a'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(822 + 4 * Math.sin(t), 172); ctx.lineTo(852 + 4 * Math.sin(t), 172); ctx.moveTo(837 + 4 * Math.sin(t), 160); ctx.lineTo(837 + 4 * Math.sin(t), 184); ctx.stroke();
  txt(ctx, 'driver camera + eye point', 680, 322, { size: 18, color: '#7d8b98' });
  const rows = [['registration', `${(0.18 + 0.05 * Math.sin(t)).toFixed(2)}°`, '≤ 0.5°'], ['lanes age', `${(62 + 8 * Math.sin(t * 1.3)).toFixed(0)} ms`, '≤ 90 ms'], ['contrast', '1.19', '≥ 1.15'], ['cell', '48 °C', '< rating']];
  rows.forEach(([k, val, tgt], i) => { txt(ctx, k, 680, 380 + i * 50, { size: 22 }); txt(ctx, val, 860, 380 + i * 50, { size: 22, color: '#9fe6bd', weight: 600 }); txt(ctx, tgt, 950, 380 + i * 50, { size: 18, color: '#7d8b98' }); });
  txt(ctx, 'live numbers beside their targets (illustrative until the app feeds the real frame)', 30, 610, { size: 18, color: '#5d6874' });
}
