// Shared materials and procedural textures. Import M and use M.alu, M.pcbGreen, ...; call M.led(color) etc. for parametric ones.
import * as THREE from 'three';
import { canvasTexture, rng } from './util.js';

const cache = new Map();
const once = (key, make) => { if (!cache.has(key)) cache.set(key, make()); return cache.get(key); };

// ---- procedural textures --------------------------------------------------
export function noiseTex(key, w, h, paint, repeat) { return once('tex:' + key, () => canvasTexture(w, h, paint, { repeat })); }

function brushed() {
  return noiseTex('brushed', 512, 512, (ctx, W, H) => {
    const r = rng(7);
    ctx.fillStyle = '#9a9ea3'; ctx.fillRect(0, 0, W, H);
    for (let i = 0; i < 2600; i++) {
      const y = r() * H, g = 140 + r() * 70 | 0;
      ctx.strokeStyle = `rgba(${g},${g + 3},${g + 6},${0.08 + r() * 0.12})`;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y + (r() - 0.5) * 2); ctx.stroke();
    }
  }, [2, 2]);
}

function printLayers() {
  // FDM layer lines, used as a bump map on the printed housing
  return noiseTex('layers', 64, 256, (ctx, W, H) => {
    for (let y = 0; y < H; y++) { const v = (y % 4 < 2) ? 150 : 95; ctx.fillStyle = `rgb(${v},${v},${v})`; ctx.fillRect(0, y, W, 1); }
  }, [6, 40]);
}

function pcb(color, traceColor) {
  return noiseTex('pcb' + color, 512, 512, (ctx, W, H) => {
    const r = rng(11);
    ctx.fillStyle = color; ctx.fillRect(0, 0, W, H);
    ctx.lineCap = 'round';
    for (let i = 0; i < 160; i++) {
      ctx.strokeStyle = traceColor; ctx.lineWidth = 1 + r() * 3; ctx.globalAlpha = 0.55;
      let x = r() * W, y = r() * H; ctx.beginPath(); ctx.moveTo(x, y);
      for (let k = 0; k < 3; k++) { if (r() > 0.5) x += (r() - 0.5) * 180; else y += (r() - 0.5) * 180; ctx.lineTo(x, y); }
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    for (let i = 0; i < 90; i++) { ctx.fillStyle = '#d8b25a'; const x = r() * W, y = r() * H; ctx.beginPath(); ctx.arc(x, y, 2 + r() * 3, 0, 7); ctx.fill(); }
  }, [1, 1]);
}

function asphalt() {
  return noiseTex('asphalt', 512, 512, (ctx, W, H) => {
    const r = rng(3);
    ctx.fillStyle = '#4a4a4c'; ctx.fillRect(0, 0, W, H);
    for (let i = 0; i < 26000; i++) {
      const g = 40 + r() * 70 | 0; ctx.fillStyle = `rgba(${g},${g},${g + 2},0.55)`;
      ctx.fillRect(r() * W, r() * H, 1 + r() * 2, 1 + r() * 2);
    }
  }, [1, 1]);
}

function grass() {
  return noiseTex('grass', 512, 512, (ctx, W, H) => {
    const r = rng(5);
    ctx.fillStyle = '#5d7a3a'; ctx.fillRect(0, 0, W, H);
    for (let i = 0; i < 30000; i++) {
      const g = 90 + r() * 70 | 0; ctx.fillStyle = `rgba(${g * 0.55 | 0},${g},${g * 0.35 | 0},0.35)`;
      ctx.fillRect(r() * W, r() * H, 1, 2 + r() * 3);
    }
  }, [1, 1]);
}

function dashTex() {
  return noiseTex('dash', 256, 256, (ctx, W, H) => {
    const r = rng(9);
    ctx.fillStyle = '#2a2b2e'; ctx.fillRect(0, 0, W, H);
    for (let i = 0; i < 9000; i++) { const g = 30 + r() * 25 | 0; ctx.fillStyle = `rgba(${g},${g},${g + 3},0.6)`; ctx.fillRect(r() * W, r() * H, 1, 1); }
  }, [8, 8]);
}

function fabric() {
  return noiseTex('fabric', 256, 256, (ctx, W, H) => {
    ctx.fillStyle = '#34363b'; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    for (let i = 0; i < W; i += 4) { ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, H); ctx.stroke(); ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(W, i); ctx.stroke(); }
  }, [6, 6]);
}

// ---- material library -----------------------------------------------------
const std = (o) => new THREE.MeshStandardMaterial(o);
const phys = (o) => new THREE.MeshPhysicalMaterial(o);

export const M = {
  get alu() { return once('alu', () => std({ color: 0xb9bdc2, metalness: 0.9, roughness: 0.38, map: brushed() })); },
  get aluDark() { return once('aluDark', () => std({ color: 0x55595f, metalness: 0.85, roughness: 0.42, map: brushed() })); },
  get aluAnodBlack() { return once('aluBlack', () => std({ color: 0x1d1f22, metalness: 0.6, roughness: 0.5 })); },
  get steel() { return once('steel', () => std({ color: 0xcfd3d8, metalness: 1, roughness: 0.25 })); },
  get copper() { return once('copper', () => std({ color: 0xc8794a, metalness: 1, roughness: 0.3 })); },
  get gold() { return once('gold', () => std({ color: 0xe0b860, metalness: 1, roughness: 0.25 })); },
  get solder() { return once('solder', () => std({ color: 0xd9dbdc, metalness: 1, roughness: 0.2 })); },
  get plasticBlack() { return once('pBlack', () => std({ color: 0x17181a, metalness: 0, roughness: 0.55 })); },
  get plasticGrey() { return once('pGrey', () => std({ color: 0x5b5f66, metalness: 0, roughness: 0.6 })); },
  get plasticWhite() { return once('pWhite', () => std({ color: 0xe9eaea, metalness: 0, roughness: 0.45 })); },
  get rubber() { return once('rubber', () => std({ color: 0x111112, metalness: 0, roughness: 0.9 })); },
  get printBlack() { return once('print', () => std({ color: 0x1a1a1c, metalness: 0, roughness: 0.92, bumpMap: printLayers(), bumpScale: 0.6 })); },
  get flock() { return once('flock', () => std({ color: 0x050505, metalness: 0, roughness: 1 })); },     // matte-black absorber / baffles
  get whiteCavity() { return once('cavity', () => std({ color: 0xf6f6f2, metalness: 0, roughness: 0.95, side: THREE.DoubleSide })); },
  get pcbGreen() { return once('pcbG', () => std({ color: 0xffffff, map: pcb('#1f6b3a', '#2f8f52'), metalness: 0.1, roughness: 0.55 })); },
  get pcbBlack() { return once('pcbB', () => std({ color: 0xffffff, map: pcb('#141518', '#26282d'), metalness: 0.1, roughness: 0.5 })); },
  get pcbRed() { return once('pcbR', () => std({ color: 0xffffff, map: pcb('#a3202b', '#c2343e'), metalness: 0.1, roughness: 0.5 })); },
  get pcbBlue() { return once('pcbBl', () => std({ color: 0xffffff, map: pcb('#1e3f8a', '#3159b0'), metalness: 0.1, roughness: 0.5 })); },
  get pcbPurple() { return once('pcbP', () => std({ color: 0xffffff, map: pcb('#3b2a6b', '#5a46a0'), metalness: 0.1, roughness: 0.5 })); },
  get mcpcb() { return once('mcpcb', () => std({ color: 0xf2f2ef, metalness: 0.3, roughness: 0.4 })); },      // white aluminium LED star board
  get chip() { return once('chip', () => std({ color: 0x1b1c1f, metalness: 0.2, roughness: 0.35 })); },
  get ceramic() { return once('ceram', () => std({ color: 0xe8e3d6, metalness: 0, roughness: 0.4 })); },
  get phosphor() { return once('phos', () => std({ color: 0xffe7a3, emissive: 0x000000, metalness: 0, roughness: 0.3 })); },
  get glass() { return once('glass', () => phys({ color: 0xffffff, metalness: 0, roughness: 0.02, transmission: 0.96, thickness: 0.004, ior: 1.52, transparent: true, opacity: 0.25, side: THREE.DoubleSide, depthWrite: false })); },
  get windshield() { return once('ws', () => phys({ color: 0xdfeae6, metalness: 0, roughness: 0.03, transparent: true, opacity: 0.12, side: THREE.DoubleSide, depthWrite: false, envMapIntensity: 1.4, reflectivity: 0.5 })); },
  get irCut() { return once('ir', () => phys({ color: 0x7fe0f0, metalness: 0, roughness: 0.05, transparent: true, opacity: 0.45, side: THREE.DoubleSide, depthWrite: false })); },
  get diffuser() { return once('diff', () => phys({ color: 0xf4f4f4, metalness: 0, roughness: 0.9, transparent: true, opacity: 0.82, side: THREE.DoubleSide })); },
  get prismFilm() { return once('bef', () => phys({ color: 0xe7eef5, metalness: 0, roughness: 0.15, transparent: true, opacity: 0.55, side: THREE.DoubleSide, iridescence: 0.6, iridescenceIOR: 1.6, depthWrite: false })); },
  get polarizer() { return once('pol', () => phys({ color: 0x4a5b5e, metalness: 0, roughness: 0.2, transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false })); },
  get retarder() { return once('ret', () => phys({ color: 0xd8e6ff, metalness: 0, roughness: 0.1, transparent: true, opacity: 0.35, side: THREE.DoubleSide, iridescence: 1, iridescenceIOR: 1.8, depthWrite: false })); },
  get mirror() { return once('mirror', () => std({ color: 0xf2f4f6, metalness: 1, roughness: 0.04, envMapIntensity: 1.6 })); },
  get coldMirror() { return once('cold', () => phys({ color: 0xc7d9ff, metalness: 0.65, roughness: 0.06, iridescence: 1, iridescenceIOR: 2.0, iridescenceThicknessRange: [300, 700], transparent: true, opacity: 0.88 })); },
  get mirrorBack() { return once('mback', () => std({ color: 0x3b3e43, metalness: 0.1, roughness: 0.8 })); },
  get lcdGlass() { return once('lcd', () => phys({ color: 0x0a0c10, metalness: 0.1, roughness: 0.15, clearcoat: 1, clearcoatRoughness: 0.05 })); },
  get fpc() { return once('fpc', () => std({ color: 0xd38a2a, metalness: 0.2, roughness: 0.45, side: THREE.DoubleSide })); },
  get dash() { return once('dash', () => std({ color: 0xffffff, map: dashTex(), metalness: 0, roughness: 0.85 })); },
  get dashSoft() { return once('dashS', () => std({ color: 0x3a3c41, metalness: 0, roughness: 0.75 })); },
  get seat() { return once('seat', () => std({ color: 0xffffff, map: fabric(), metalness: 0, roughness: 0.95 })); },
  get leather() { return once('leather', () => std({ color: 0x1e1f22, metalness: 0, roughness: 0.6 })); },
  get carPaint() { return once('paint', () => phys({ color: 0x8c9aa6, metalness: 0.6, roughness: 0.35, clearcoat: 1, clearcoatRoughness: 0.08 })); },
  get tire() { return once('tire', () => std({ color: 0x151516, metalness: 0, roughness: 0.92 })); },
  get rim() { return once('rim', () => std({ color: 0xa8acb1, metalness: 0.9, roughness: 0.3 })); },
  get skin() { return once('skin', () => std({ color: 0xc69c7d, metalness: 0, roughness: 0.65 })); },
  get cloth() { return once('cloth', () => std({ color: 0x2d4a6b, metalness: 0, roughness: 0.9 })); },
  get asphalt() { return once('asph', () => std({ color: 0xffffff, map: asphalt(), metalness: 0, roughness: 0.95 })); },
  get grass() { return once('grass', () => std({ color: 0xffffff, map: grass(), metalness: 0, roughness: 1 })); },
  get paintWhite() { return once('pw', () => std({ color: 0xf2f2ee, metalness: 0, roughness: 0.6, polygonOffset: true, polygonOffsetFactor: -2 })); },
  get paintYellow() { return once('py', () => std({ color: 0xe8b828, metalness: 0, roughness: 0.6, polygonOffset: true, polygonOffsetFactor: -2 })); },
  get screenOff() { return once('scr', () => std({ color: 0x08090b, metalness: 0.2, roughness: 0.2 })); },
  get cableBlack() { return once('cblk', () => std({ color: 0x141416, metalness: 0, roughness: 0.6 })); },
  get cableRed() { return once('cred', () => std({ color: 0xb2242c, metalness: 0, roughness: 0.55 })); },
  get cableBlue() { return once('cblu', () => std({ color: 0x2c64c9, metalness: 0, roughness: 0.55 })); },
  get cableOrange() { return once('cora', () => std({ color: 0xe0782c, metalness: 0, roughness: 0.55 })); },
  get cableGreen() { return once('cgrn', () => std({ color: 0x2f9a5c, metalness: 0, roughness: 0.55 })); },
  get cableYellow() { return once('cyel', () => std({ color: 0xd8b42a, metalness: 0, roughness: 0.55 })); },
  get thermal() { return once('therm', () => std({ color: 0x9aa0a6, metalness: 0, roughness: 0.7 })); },  // thermal pad / paste
  get lens() { return once('lensG', () => phys({ color: 0x101824, metalness: 0.2, roughness: 0.02, clearcoat: 1, iridescence: 0.7, iridescenceIOR: 1.5 })); },
  get fresnel() { return once('fres', () => phys({ color: 0xf0f6ff, metalness: 0, roughness: 0.08, transparent: true, opacity: 0.35, side: THREE.DoubleSide, depthWrite: false })); },
  get beamsplitter() { return once('bs', () => phys({ color: 0xc8d4dc, metalness: 0.3, roughness: 0.02, transparent: true, opacity: 0.4, side: THREE.DoubleSide, depthWrite: false })); },
  // Parametric ones
  led(color = 0xfff4dd, intensity = 0) { return std({ color: 0xffffff, emissive: color, emissiveIntensity: intensity, metalness: 0, roughness: 0.3, toneMapped: intensity <= 1 }); },
  emissive(color, intensity = 1) { return new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(intensity), toneMapped: false }); },
  basic(color, opacity = 1) { return new THREE.MeshBasicMaterial({ color, transparent: opacity < 1, opacity, depthWrite: opacity >= 1, side: THREE.DoubleSide }); },
  color(color, rough = 0.6, metal = 0) { return std({ color, roughness: rough, metalness: metal }); },
};

// Semantic colours for rays, cables and overlays (hex numbers), used across modes.
export const C = {
  ray: 0xffb347,      // image light
  rayVirtual: 0xffd27a,
  sun: 0xff5a36,
  ir: 0xd2283c,
  power: 0xe0463c,
  usb: 0x3d8bff,
  hdmi: 0xff9b3d,
  eth: 0x3fbf7f,
  serial: 0xc78bff,
  hud: 0x5ec8ff,      // lane ribbon tint in diagrams
  ok: 0x4fd18b,
  warn: 0xffc04d,
  crit: 0xff5a5a,
};
