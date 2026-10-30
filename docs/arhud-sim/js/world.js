// The driving world: a closed road loop with painted lanes, scenery, traffic, people, signs, sky and four lighting
// environments. World axes: Y up, ground at y = 0, north = -Z, east = +X. Metres and seconds.
//
// The road is a reference line (the double-yellow centre line) built from straights and circular arcs joined by
// 60 m clothoid ramps, integrated from its curvature so that s is exact arc length. Two straights are re-solved so the
// loop closes. Offsets are measured to the right of the reference line; traffic drives on the right, so the ego's
// direction of travel (increasing s) uses the lanes at positive offsets.
import * as THREE from 'three';
import { Sky } from 'three/addons/objects/Sky.js';
import { M } from './mats.js';
import { rng, canvasTexture, DEG, clamp, lerp, smoothstep } from './util.js';

const UP = new THREE.Vector3(0, 1, 0);
const LR = 60;                                    // clothoid ramp length, m
const LANE = 3.7;
const ROAD_HALF = 2 * LANE + 1.5;                 // 8.9 m: two lanes and a 1.5 m shoulder each side
const EGO_FRONT = 2.45;                           // ego front bumper ahead of the ego car frame origin (car.js)

// Loop design: ['S', length] or ['C', turn angle in degrees (+ right), radius]. Straights 0 and 2 are re-solved for closure.
const DESIGN = [
  ['S', 539.1], ['C', 90, 400], ['S', 274.8], ['C', -30, 450], ['C', 30, 450], ['S', 120], ['C', 90, 350],
  ['S', 550], ['C', 45, 600], ['S', 150], ['C', 45, 400], ['S', 800], ['C', 90, 300], ['S', 200],
];
const TOWN_SEG = 7, RAIL_SEG = 12;

function profileOf(segs) {
  const prof = []; const info = []; let s = 0;
  for (const sg of segs) {
    const s0 = s;
    if (sg[0] === 'S') { prof.push({ s0: s, len: sg[1], k0: 0, k1: 0 }); s += sg[1]; }
    else {
      const k = Math.sign(sg[1]) / sg[2], Lc = Math.abs(sg[1]) * DEG * sg[2] - LR;
      prof.push({ s0: s, len: LR, k0: 0, k1: k }); s += LR;
      prof.push({ s0: s, len: Lc, k0: k, k1: k }); s += Lc;
      prof.push({ s0: s, len: LR, k0: k, k1: 0 }); s += LR;
    }
    info.push({ type: sg[0], s0, s1: s, angle: sg[0] === 'C' ? sg[1] : 0, radius: sg[0] === 'C' ? sg[2] : Infinity });
  }
  return { prof, length: s, info };
}

function curvatureFn(prof) {
  let j = 0;
  return (s) => {
    while (j < prof.length - 1 && s >= prof[j].s0 + prof[j].len) j++;
    while (j > 0 && s < prof[j].s0) j--;
    const p = prof[j]; const u = p.len > 0 ? clamp((s - p.s0) / p.len, 0, 1) : 0;
    return p.k0 + (p.k1 - p.k0) * u;
  };
}

function integrateEnd(prof, length, h = 0.25) {
  const k = curvatureFn(prof); let x = 0, z = 0, th = 0;
  const n = Math.ceil(length / h); const dh = length / n;
  for (let i = 0; i < n; i++) {
    const km = k((i + 0.5) * dh); const thm = th + km * dh / 2;
    x += Math.sin(thm) * dh; z -= Math.cos(thm) * dh; th += km * dh;
  }
  return { x, z, th };
}

function buildRoad() {
  const segs = DESIGN.map((s) => s.slice());
  for (let it = 0; it < 3; it++) {
    const { prof, length } = profileOf(segs);
    const e = integrateEnd(prof, length);
    // straight 0 heads north (0, -1); straight 2 heads east (1, 0)
    segs[0][1] += e.z; segs[2][1] -= e.x;
  }
  const { prof, length, info } = profileOf(segs);
  const N = Math.round(length), d = length / N;
  const X = new Float64Array(N + 1), Z = new Float64Array(N + 1), TH = new Float64Array(N + 1), K = new Float64Array(N + 1);
  const kf = curvatureFn(prof);
  let x = 0, z = 0, th = 0; const sub = 4, h = d / sub;
  K[0] = kf(0);
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < sub; j++) {
      const sm = i * d + (j + 0.5) * h, km = kf(sm), thm = th + km * h / 2;
      x += Math.sin(thm) * h; z -= Math.cos(thm) * h; th += km * h;
    }
    X[i + 1] = x; Z[i + 1] = z; TH[i + 1] = th; K[i + 1] = kf((i + 1) * d);
  }
  // distribute the tiny closure residual
  const ex = X[N], ez = Z[N];
  for (let i = 0; i <= N; i++) { X[i] -= ex * i / N; Z[i] -= ez * i / N; }
  return { length, N, d, X, Z, TH, K, info, segs };
}

// ------------------------------------------------------------------------------------------------------------
// Vehicle and people models (low-poly, local +X forward, origin at the centre of the footprint on the ground)
// ------------------------------------------------------------------------------------------------------------
const glassMat = new THREE.MeshPhysicalMaterial({ color: 0x1b242e, metalness: 0.2, roughness: 0.08, clearcoat: 1, envMapIntensity: 1.2 });
const trimMat = new THREE.MeshStandardMaterial({ color: 0x121315, roughness: 0.6 });
const chromeMat = new THREE.MeshStandardMaterial({ color: 0xd6d9dd, metalness: 1, roughness: 0.2 });
const rimMat = new THREE.MeshStandardMaterial({ color: 0x9da1a6, metalness: 0.9, roughness: 0.32 });
const tireMat = new THREE.MeshStandardMaterial({ color: 0x141415, roughness: 0.92 });

let glowTex = null;
function glowTexture() {
  if (!glowTex) glowTex = canvasTexture(64, 64, (ctx, W, H) => {
    const g = ctx.createRadialGradient(W / 2, H / 2, 0, W / 2, H / 2, W / 2);
    g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.25, 'rgba(255,255,255,0.55)'); g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  });
  return glowTex;
}
function glowSprite(color, size) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, toneMapped: false }));
  s.scale.setScalar(size); s.visible = false; s.renderOrder = 3;
  return s;
}

function extrudeSide(points, width, mat, bevel = 0.04) {
  const shape = new THREE.Shape(points.map(([x, y]) => new THREE.Vector2(x, y)));
  const g = new THREE.ExtrudeGeometry(shape, { depth: Math.max(0.01, width - 2 * bevel), bevelEnabled: bevel > 0, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 3, curveSegments: 8 });
  g.translate(0, 0, -(width - 2 * bevel) / 2);
  const m = new THREE.Mesh(g, mat); m.castShadow = true; m.receiveShadow = true;
  return m;
}

function makeWheel(r, w) {
  const g = new THREE.Group();
  const tire = new THREE.Mesh(new THREE.CylinderGeometry(r, r, w, 20), tireMat); tire.rotation.x = Math.PI / 2; tire.castShadow = true;
  const rim = new THREE.Mesh(new THREE.CylinderGeometry(r * 0.62, r * 0.62, w + 0.01, 14), rimMat); rim.rotation.x = Math.PI / 2;
  const hub = new THREE.Mesh(new THREE.CylinderGeometry(r * 0.16, r * 0.16, w + 0.03, 10), chromeMat); hub.rotation.x = Math.PI / 2;
  g.add(tire, rim, hub);
  for (let i = 0; i < 5; i++) {   // spokes so the rotation is visible
    const sp = new THREE.Mesh(new THREE.BoxGeometry(r * 0.12, r * 1.05, w + 0.02), trimMat);
    sp.rotation.z = (i / 5) * Math.PI; g.add(sp);
  }
  const pivot = new THREE.Group(); pivot.add(g);
  pivot.userData.spin = g; pivot.userData.r = r;
  return pivot;
}

const PAINTS = [0x8c1d24, 0x1f3f73, 0xe8e8e6, 0x2a2b2e, 0x6f7377, 0xb8bcc0, 0x3e5b3b, 0xc9a227, 0x5a2d6b, 0x0f5f6e];

function makeVehicle(kind, rand) {
  const paint = new THREE.MeshPhysicalMaterial({ color: PAINTS[Math.floor(rand() * PAINTS.length)], metalness: 0.55, roughness: 0.35, clearcoat: 1, clearcoatRoughness: 0.1 });
  const tail = new THREE.MeshStandardMaterial({ color: 0x5a0a0a, emissive: 0xff1a1a, emissiveIntensity: 0.15 });
  const head = new THREE.MeshStandardMaterial({ color: 0xdedede, emissive: 0xfff1d6, emissiveIntensity: 0.1 });
  const g = new THREE.Group();
  const wheels = [];
  let L, W, H, r;
  const lights = { head: [], tail: [] };
  const addLamp = (mat, x, y, z, sx, sy, sz, list, glowCol, glowSize) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz), mat); m.position.set(x, y, z); g.add(m);
    const gs = glowSprite(glowCol, glowSize); gs.position.set(x + Math.sign(x) * 0.05, y, z); g.add(gs);
    list.push(gs);
  };
  if (kind === 'car' || kind === 'suv') {
    const suv = kind === 'suv';
    L = suv ? 4.8 : 4.6; W = suv ? 1.9 : 1.8; H = suv ? 1.75 : 1.45; r = suv ? 0.37 : 0.32;
    const hl = L / 2, belt = suv ? 1.05 : 0.86, base = suv ? 0.32 : 0.2;
    const body = [
      [-hl, base + 0.12], [-hl + 0.08, base], [hl - 0.12, base], [hl, base + 0.14], [hl, belt - 0.12],
      [hl - 0.25, belt - 0.02], [hl - 1.25, belt + 0.02], [-hl + 0.55, belt + 0.04], [-hl + 0.1, belt], [-hl, belt - 0.12],
    ];
    g.add(extrudeSide(body, W, paint, 0.06));
    const gh = suv
      ? [[hl - 1.3, belt], [hl - 1.95, H - 0.04], [-hl + 0.35, H - 0.03], [-hl + 0.12, belt + 0.02]]
      : [[hl - 1.3, belt], [hl - 2.05, H - 0.03], [-hl + 1.2, H - 0.03], [-hl + 0.62, belt + 0.03]];
    g.add(extrudeSide(gh, W - 0.2, glassMat, 0.05));
    const roof = suv
      ? [[hl - 1.9, H - 0.06], [-hl + 0.38, H - 0.06], [-hl + 0.38, H], [hl - 1.9, H]]
      : [[hl - 2.0, H - 0.06], [-hl + 1.25, H - 0.06], [-hl + 1.25, H], [hl - 2.0, H]];
    g.add(extrudeSide(roof, W - 0.24, paint, 0.03));
    const ax = hl - 0.9 - (suv ? 0.05 : 0);
    for (const [x, z] of [[ax, 1], [ax, -1], [-hl + 0.95, 1], [-hl + 0.95, -1]]) {
      const w = makeWheel(r, 0.22); w.position.set(x, r, z * (W / 2 - 0.12)); g.add(w); wheels.push(w);
    }
    for (const z of [-1, 1]) {
      addLamp(tail, -hl - 0.01, belt - 0.2, z * (W / 2 - 0.2), 0.04, 0.12, 0.32, lights.tail, 0xff2a2a, 0.9);
      addLamp(head, hl + 0.01, belt - 0.25, z * (W / 2 - 0.22), 0.04, 0.1, 0.3, lights.head, 0xfff4dc, 1.4);
    }
    const grille = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.14, W * 0.42), trimMat); grille.position.set(hl + 0.005, base + 0.32, 0); g.add(grille);
  } else if (kind === 'truck') {
    L = 7.4; W = 2.4; H = 3.3; r = 0.48;
    const hl = L / 2;
    const cab = new THREE.Mesh(new THREE.BoxGeometry(1.9, 2.2, W - 0.1), paint); cab.position.set(hl - 0.95, 0.45 + 1.1, 0); cab.castShadow = true; g.add(cab);
    const ws = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.8, W - 0.3), glassMat); ws.position.set(hl + 0.0, 1.95, 0); g.add(ws);
    const box = new THREE.Mesh(new THREE.BoxGeometry(5.3, 2.75, W), new THREE.MeshStandardMaterial({ color: 0xe9e9e6, roughness: 0.7 }));
    box.position.set(-hl + 2.65, 0.55 + 1.375, 0); box.castShadow = true; g.add(box);
    const chassis = new THREE.Mesh(new THREE.BoxGeometry(L - 0.2, 0.3, W - 0.6), trimMat); chassis.position.set(0, 0.55, 0); g.add(chassis);
    for (const [x, z] of [[hl - 1.1, 1], [hl - 1.1, -1], [-hl + 1.3, 1], [-hl + 1.3, -1], [-hl + 2.3, 1], [-hl + 2.3, -1]]) {
      const w = makeWheel(r, 0.3); w.position.set(x, r, z * (W / 2 - 0.2)); g.add(w); wheels.push(w);
    }
    for (const z of [-1, 1]) {
      addLamp(tail, -hl - 0.01, 0.9, z * (W / 2 - 0.15), 0.04, 0.2, 0.2, lights.tail, 0xff2a2a, 1.0);
      addLamp(head, hl + 0.01, 0.95, z * (W / 2 - 0.3), 0.04, 0.16, 0.3, lights.head, 0xfff4dc, 1.6);
    }
  } else if (kind === 'bus') {
    L = 12; W = 2.55; H = 3.15; r = 0.5;
    const hl = L / 2;
    const busPaint = new THREE.MeshPhysicalMaterial({ color: rand() < 0.5 ? 0xe2b33b : 0xdedfe0, roughness: 0.4, clearcoat: 0.6 });
    g.add(extrudeSide([[-hl, 0.35], [hl - 0.1, 0.35], [hl, 0.5], [hl, H - 0.2], [hl - 0.2, H], [-hl + 0.1, H], [-hl, H - 0.15]], W, busPaint, 0.08));
    const band = new THREE.Mesh(new THREE.BoxGeometry(L - 0.6, 1.0, W + 0.01), glassMat); band.position.set(0, 2.1, 0); g.add(band);
    const fw = new THREE.Mesh(new THREE.BoxGeometry(0.05, 1.5, W - 0.25), glassMat); fw.position.set(hl + 0.01, 1.95, 0); g.add(fw);
    for (const [x, z] of [[hl - 2.4, 1], [hl - 2.4, -1], [-hl + 2.6, 1], [-hl + 2.6, -1]]) {
      const w = makeWheel(r, 0.3); w.position.set(x, r, z * (W / 2 - 0.2)); g.add(w); wheels.push(w);
    }
    for (const z of [-1, 1]) {
      addLamp(tail, -hl - 0.01, 0.9, z * (W / 2 - 0.15), 0.04, 0.25, 0.18, lights.tail, 0xff2a2a, 1.0);
      addLamp(head, hl + 0.01, 0.8, z * (W / 2 - 0.3), 0.04, 0.16, 0.3, lights.head, 0xfff4dc, 1.6);
    }
  } else if (kind === 'motorcycle') {
    L = 2.1; W = 0.8; H = 1.3; r = 0.31;
    const front = makeWheel(r, 0.12); front.position.set(0.72, r, 0); g.add(front); wheels.push(front);
    const back = makeWheel(r, 0.16); back.position.set(-0.72, r, 0); g.add(back); wheels.push(back);
    const tank = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.22, 0.3), paint); tank.position.set(0.15, 0.85, 0); g.add(tank);
    const engine = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.32, 0.3), chromeMat); engine.position.set(0.05, 0.5, 0); g.add(engine);
    const seat = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.1, 0.28), trimMat); seat.position.set(-0.35, 0.88, 0); g.add(seat);
    const fork = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.75), chromeMat); fork.position.set(0.6, 0.65, 0); fork.rotation.z = 0.45; g.add(fork);
    const bar = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.7), chromeMat); bar.position.set(0.5, 1.02, 0); bar.rotation.x = Math.PI / 2; g.add(bar);
    addLamp(tail, -0.95, 0.85, 0, 0.04, 0.08, 0.14, lights.tail, 0xff2a2a, 0.7);
    addLamp(head, 0.85, 0.95, 0, 0.06, 0.12, 0.12, lights.head, 0xfff4dc, 1.2);
    const rider = makePerson(rand, true); rider.group.position.set(-0.3, 0.72, 0); g.add(rider.group);
    rider.pose('ride', 0, { bars: new THREE.Vector3(0.5, 1.02, 0).sub(new THREE.Vector3(-0.3, 0.72, 0)), pegs: new THREE.Vector3(-0.05, 0.4, 0).sub(new THREE.Vector3(-0.3, 0.72, 0)) });
  }
  g.traverse((o) => { if (o.isMesh) o.castShadow = true; });
  return { group: g, wheels, lights, L, W, H, tail, head, paint };
}

// Articulated person: hips at the origin's height above the feet; local +X forward.
const SKIN = [0xc69c7d, 0x8d5a3b, 0xe0b899, 0x5b3a26, 0xb07b55];
const SHIRT = [0x2d4a6b, 0xa13b2b, 0x3e6b3e, 0xd9c27a, 0x4b4b52, 0xe6e6e6, 0x6b3e8a];
const PANTS = [0x23262d, 0x2f3d55, 0x5b4a3a, 0x3a3a3a];
function limbMesh(len, r, mat) {
  const m = new THREE.Mesh(new THREE.CapsuleGeometry(r, Math.max(0.001, len - 2 * r), 4, 8), mat);
  m.position.y = -len / 2; m.castShadow = true;
  const j = new THREE.Group(); j.add(m);
  return j;
}
function makePerson(rand, seated = false) {
  const s = 0.92 + rand() * 0.12;
  const skin = new THREE.MeshStandardMaterial({ color: SKIN[Math.floor(rand() * SKIN.length)], roughness: 0.65 });
  const shirt = new THREE.MeshStandardMaterial({ color: SHIRT[Math.floor(rand() * SHIRT.length)], roughness: 0.9 });
  const pants = new THREE.MeshStandardMaterial({ color: PANTS[Math.floor(rand() * PANTS.length)], roughness: 0.9 });
  const hair = new THREE.MeshStandardMaterial({ color: [0x1a1410, 0x3b2a1a, 0x6b4a2a, 0xa08860][Math.floor(rand() * 4)], roughness: 0.9 });
  const root = new THREE.Group();
  const body = new THREE.Group(); body.scale.setScalar(s); root.add(body);
  const hips = new THREE.Group(); hips.position.y = seated ? 0 : 0.92; body.add(hips);
  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.15, 0.32, 4, 10), shirt); torso.scale.set(0.75, 1, 1.15); torso.position.y = 0.28; torso.castShadow = true;
  const spine = new THREE.Group(); spine.add(torso); hips.add(spine);
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.05, 0.1, 8), skin); neck.position.y = 0.55; spine.add(neck);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.105, 14, 10), skin); head.scale.set(1, 1.15, 0.92); head.position.y = 0.68; head.castShadow = true; spine.add(head);
  const hairCap = new THREE.Mesh(new THREE.SphereGeometry(0.11, 14, 8, 0, Math.PI * 2, 0, Math.PI * 0.55), hair); hairCap.position.set(-0.01, 0.7, 0); hairCap.scale.set(1, 1.1, 0.95); spine.add(hairCap);
  const pelvis = new THREE.Mesh(new THREE.CapsuleGeometry(0.13, 0.12, 4, 8), pants); pelvis.rotation.x = Math.PI / 2; pelvis.scale.set(0.8, 1.05, 1); pelvis.position.y = 0.02; hips.add(pelvis);
  const legs = [], arms = [];
  for (const side of [-1, 1]) {
    const thigh = limbMesh(0.45, 0.075, pants); thigh.position.set(0, -0.02, side * 0.1); hips.add(thigh);
    const shin = limbMesh(0.45, 0.06, pants); shin.position.y = -0.45; thigh.add(shin);
    const foot = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.07, 0.1), new THREE.MeshStandardMaterial({ color: 0x1a1a1a, roughness: 0.8 }));
    foot.position.set(0.06, -0.46, 0); shin.add(foot);
    legs.push({ thigh, shin });
    const upper = limbMesh(0.3, 0.05, shirt); upper.position.set(0, 0.48, side * 0.2); spine.add(upper);
    const lower = limbMesh(0.28, 0.042, skin); lower.position.y = -0.3; upper.add(lower);
    arms.push({ upper, lower });
  }
  const p = {
    group: root, legs, arms, spine, scale: s,
    pose(mode, phase = 0, opts = {}) {
      if (mode === 'walk') {
        for (let i = 0; i < 2; i++) {
          const ph = phase + i * Math.PI;
          legs[i].thigh.rotation.z = 0.42 * Math.sin(ph);
          legs[i].shin.rotation.z = -0.55 * Math.max(0, Math.sin(ph + 1.2));
          arms[i].upper.rotation.z = -0.38 * Math.sin(ph);
          arms[i].lower.rotation.z = 0.35 + 0.2 * Math.sin(ph);
        }
        spine.rotation.z = -0.04; hips.position.y = 0.92 + 0.02 * Math.abs(Math.cos(phase));
      } else if (mode === 'stand') {
        for (let i = 0; i < 2; i++) { legs[i].thigh.rotation.z = 0; legs[i].shin.rotation.z = 0; arms[i].upper.rotation.z = 0.05; arms[i].lower.rotation.z = 0.1; }
      } else if (mode === 'ride' || mode === 'cycle') {
        spine.rotation.z = mode === 'cycle' ? -0.5 : -0.35;
        for (let i = 0; i < 2; i++) {
          const ph = phase + i * Math.PI;
          const k = mode === 'cycle' ? 0.35 * Math.sin(ph) : 0;
          legs[i].thigh.rotation.z = 1.25 + k;
          legs[i].shin.rotation.z = -1.35 - k * 0.6;
          arms[i].upper.rotation.z = mode === 'cycle' ? 1.05 : 0.95;
          arms[i].lower.rotation.z = 0.25;
        }
      }
    },
  };
  p.pose(seated ? 'ride' : 'stand');
  return p;
}

function makeBicycle(rand) {
  const g = new THREE.Group();
  const frameMat = new THREE.MeshStandardMaterial({ color: [0x1f6fd1, 0xc23b3b, 0x2a2a2a, 0x2f9a5c][Math.floor(rand() * 4)], metalness: 0.5, roughness: 0.4 });
  const wheels = [];
  for (const x of [0.52, -0.52]) {
    const w = new THREE.Group();
    const spin = new THREE.Group();
    const tire = new THREE.Mesh(new THREE.TorusGeometry(0.33, 0.018, 8, 28), tireMat); spin.add(tire);
    for (let i = 0; i < 6; i++) { const sp = new THREE.Mesh(new THREE.CylinderGeometry(0.003, 0.003, 0.64), chromeMat); sp.rotation.z = (i / 6) * Math.PI; spin.add(sp); }
    w.add(spin); w.userData.spin = spin; w.userData.r = 0.35; w.position.set(x, 0.35, 0); g.add(w); wheels.push(w);
  }
  const tube = (a, b, r = 0.016) => {
    const A = new THREE.Vector3(...a), B = new THREE.Vector3(...b), d = B.clone().sub(A);
    const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, d.length(), 8), frameMat);
    m.position.copy(A).addScaledVector(d, 0.5); m.quaternion.setFromUnitVectors(UP, d.normalize()); m.castShadow = true; g.add(m);
  };
  tube([-0.52, 0.35, 0], [0.0, 0.38, 0]); tube([0.0, 0.38, 0], [-0.12, 0.9, 0]); tube([-0.12, 0.9, 0], [0.42, 0.88, 0]);
  tube([0.0, 0.38, 0], [0.42, 0.88, 0]); tube([-0.52, 0.35, 0], [-0.12, 0.9, 0]); tube([0.42, 0.88, 0], [0.52, 0.35, 0]);
  tube([0.42, 0.88, 0], [0.38, 1.05, 0]); tube([0.38, 1.05, -0.25], [0.38, 1.05, 0.25], 0.012);
  const seat = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.05, 0.12), trimMat); seat.position.set(-0.14, 0.95, 0); g.add(seat);
  const crank = new THREE.Group(); crank.position.set(0, 0.38, 0); g.add(crank);
  const arm = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.34, 0.02), chromeMat); crank.add(arm);
  const rider = makePerson(rand, true); rider.group.position.set(-0.14, 0.98, 0); g.add(rider.group);
  const tail = new THREE.MeshStandardMaterial({ color: 0x5a0a0a, emissive: 0xff1a1a, emissiveIntensity: 0.2 });
  const tl = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.04, 0.05), tail); tl.position.set(-0.3, 0.9, 0); g.add(tl);
  const glow = glowSprite(0xff2a2a, 0.45); glow.position.set(-0.34, 0.9, 0); g.add(glow);
  return { group: g, wheels, crank, rider, L: 1.8, W: 0.6, H: 1.8, tail, lights: { head: [], tail: [glow] } };
}

// ------------------------------------------------------------------------------------------------------------
// World
// ------------------------------------------------------------------------------------------------------------
export class World {
  constructor() {
    this.rand = rng(20261021);
    this.scene = new THREE.Scene();
    this.time = 0;
    this._tmp = { p: new THREE.Vector3(), t: new THREE.Vector3(), n: new THREE.Vector3(), curvature: 0, heading: 0 };

    const R = buildRoad();
    this._R = R;
    this.road = {
      length: R.length,
      segments: R.info,
      sample: (s, out) => this.sample(s, out),
    };
    const town = R.info[TOWN_SEG];
    this.town = { s0: town.s0 + 25, s1: town.s1 - 25 };
    this.crosswalkS = this.town.s0 + 0.62 * (this.town.s1 - this.town.s0);

    // Lines (offset to the right of the reference line, metres). The ego drives on the right in the right-hand lane.
    const L = R.length;
    const w = (a, b) => [((a % L) + L) % L, ((b % L) + L) % L];
    this.lines = [
      { id: 'edgeL', offset: -2 * LANE, color: 'white', style: 'solid', width: 0.15, gaps: [] },
      { id: 'laneL', offset: -LANE, color: 'white', style: 'dashed', width: 0.15, dash: [3, 9], phase: 0, gaps: [] },
      { id: 'center', offset: 0, color: 'yellow', style: 'double', width: 0.1, sep: 0.22, gaps: [] },
      { id: 'laneR', offset: LANE, color: 'white', style: 'dashed', width: 0.15, dash: [3, 9], phase: 4.5, gaps: [w(1150, 1245), w(3700, 3760)] },
      { id: 'edgeR', offset: 2 * LANE, color: 'white', style: 'solid', width: 0.15, gaps: [w(640, 720), w(2350, 2395), w(2420, 2470), w(4620, 4720)] },
    ];
    this.lineById = Object.fromEntries(this.lines.map((l) => [l.id, l]));
    this.lanes = {
      width: LANE,
      ego: { left: 'laneR', right: 'edgeR', center: 1.5 * LANE },
      adjacent: { left: 'center', right: 'laneR', center: 0.5 * LANE },
      oncoming: [-0.5 * LANE, -1.5 * LANE],
    };

    this._buildLights();
    this._buildSky();
    this._buildGround();
    this._buildRoadMesh();
    this._buildLines();
    this._buildTown();
    this._buildRail();
    this._buildTrees();
    this._buildSigns();
    this._buildAgents();
    this.setEnvironment('day');
  }

  // ---- road sampling ---------------------------------------------------------------------------------------
  wrap(s) { const L = this._R.length; return ((s % L) + L) % L; }

  sample(s, out) {
    const R = this._R;
    s = this.wrap(s);
    const f = s / R.d; let i = Math.floor(f); if (i >= R.N) i = R.N - 1; const u = f - i;
    const x = R.X[i] + (R.X[i + 1] - R.X[i]) * u, z = R.Z[i] + (R.Z[i + 1] - R.Z[i]) * u;
    const th = R.TH[i] + (R.TH[i + 1] - R.TH[i]) * u, k = R.K[i] + (R.K[i + 1] - R.K[i]) * u;
    const o = out || { p: new THREE.Vector3(), t: new THREE.Vector3(), n: new THREE.Vector3() };
    o.p.set(x, 0, z); o.t.set(Math.sin(th), 0, -Math.cos(th)); o.n.set(Math.cos(th), 0, Math.sin(th));
    o.curvature = k; o.heading = th;
    return o;
  }

  linePoint(line, s, target) {
    const l = typeof line === 'string' ? this.lineById[line] : line;
    const sm = this.sample(s, this._tmp);
    return (target || new THREE.Vector3()).copy(sm.p).addScaledVector(sm.n, l.offset);
  }

  isPainted(line, s) {
    const l = typeof line === 'string' ? this.lineById[line] : line;
    s = this.wrap(s);
    for (const [a, b] of l.gaps) if (a <= b ? (s >= a && s <= b) : (s >= a || s <= b)) return false;
    if (Math.abs(s - this.crosswalkS) < 2.2) return false;     // crosswalk bars replace the lines there
    if (l.style === 'dashed') { const per = l.dash[0] + l.dash[1]; return ((s + l.phase) % per + per) % per < l.dash[0]; }
    return true;
  }

  egoPose(s, offset, out) {
    const sm = this.sample(s, this._tmp);
    const o = out || { position: new THREE.Vector3(), quaternion: new THREE.Quaternion() };
    o.position.copy(sm.p).addScaledVector(sm.n, offset);
    _m4.makeBasis(sm.t, UP, sm.n); o.quaternion.setFromRotationMatrix(_m4);
    return o;
  }

  // ---- lights, sky, environment ---------------------------------------------------------------------------
  _buildLights() {
    const sun = new THREE.DirectionalLight(0xfff4e6, 3);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    const c = sun.shadow.camera; c.left = -45; c.right = 45; c.top = 45; c.bottom = -45; c.near = 5; c.far = 700;
    sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.03; sun.shadow.radius = 2;
    this.sun = sun; this.scene.add(sun); this.scene.add(sun.target);
    this.hemi = new THREE.HemisphereLight(0xbcd7f5, 0x6a6550, 0.8); this.scene.add(this.hemi);
    this.ambient = new THREE.AmbientLight(0xffffff, 0); this.scene.add(this.ambient);
    this.sunDir = new THREE.Vector3(0.3, 0.8, 0.5).normalize();
    this._target = new THREE.Vector3();
    // Street lights near the ego at night: a fixed pool moved to the nearest town poles.
    this.streetLights = [];
    for (let i = 0; i < 6; i++) {
      const l = new THREE.PointLight(0xfff0dc, 0, 40, 2); l.castShadow = false;
      this.scene.add(l); this.streetLights.push(l);
    }
  }

  _buildSky() {
    const sky = new Sky(); sky.scale.setScalar(9000); sky.frustumCulled = false;
    this.sky = sky; this.scene.add(sky);
    const domeMat = new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false,
      uniforms: { top: { value: new THREE.Color(0xa9b0b8) }, horizon: { value: new THREE.Color(0xcfd3d7) }, bottom: { value: new THREE.Color(0x8c9196) } },
      vertexShader: 'varying vec3 vP; void main(){ vP = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
      fragmentShader: 'uniform vec3 top; uniform vec3 horizon; uniform vec3 bottom; varying vec3 vP; void main(){ float h = vP.y; vec3 c = h > 0.0 ? mix(horizon, top, pow(clamp(h,0.0,1.0),0.6)) : mix(horizon, bottom, clamp(-h*4.0,0.0,1.0)); gl_FragColor = vec4(c,1.0); }',
    });
    this.dome = new THREE.Mesh(new THREE.SphereGeometry(8800, 32, 16), domeMat); this.dome.frustumCulled = false; this.dome.renderOrder = -10;
    this.scene.add(this.dome);
    // stars
    const r = rng(77); const pos = [];
    for (let i = 0; i < 1800; i++) { const u = r(), v = r() * 0.95; const th = 2 * Math.PI * u, ph = Math.acos(1 - v); pos.push(8500 * Math.sin(ph) * Math.cos(th), 8500 * Math.cos(ph), 8500 * Math.sin(ph) * Math.sin(th)); }
    const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    this.stars = new THREE.Points(sg, new THREE.PointsMaterial({ color: 0xffffff, size: 1.6, sizeAttenuation: false, fog: false, transparent: true, opacity: 0.85, depthWrite: false }));
    this.stars.frustumCulled = false; this.scene.add(this.stars);
    this.scene.fog = new THREE.Fog(0xc4d6e8, 300, 3000);
  }

  setSun(elevationDeg, azimuthDeg) {
    const e = elevationDeg * DEG, b = azimuthDeg * DEG;
    this.sunElevation = elevationDeg; this.sunAzimuth = azimuthDeg;
    this.sunDir.set(Math.cos(e) * Math.sin(b), Math.sin(e), -Math.cos(e) * Math.cos(b)).normalize();
    this.sky.material.uniforms.sunPosition.value.copy(this.sunDir);
    this._placeSun();
    this.applyIBL();
    return this.sunDir;
  }

  // Blender-baked sky as image-based lighting (assets/sky via assets.js): the map nearest the sun's elevation,
  // turned to the sun's azimuth. Nothing happens without the maps. With image light in the scene the hemisphere
  // light carries less of the ambient.
  applyIBL() {
    if (!this.ibl || !this.ibl.ok || !this.envName) return;
    const intensity = { day: 0.45, overcast: 0.6, dusk: 0.3, night: 0.05 }[this.envName] ?? 0.45;
    this.iblEntry = this.ibl.apply(this.scene, this.envName, this.sunElevation ?? 30, this.sunAzimuth ?? 0, intensity);
    if (this._hemiBase != null) this.hemi.intensity = this._hemiBase * (this.iblEntry ? 0.55 : 1);
  }

  // Standard solar-position approximation (declination from day of year; local solar time).
  setTimeOfDay(hours, latitudeDeg = 37, dayOfYear = 172) {
    const decl = 23.44 * DEG * Math.sin(2 * Math.PI * (284 + dayOfYear) / 365);
    const H = (hours - 12) * 15 * DEG, phi = latitudeDeg * DEG;
    const el = Math.asin(Math.sin(phi) * Math.sin(decl) + Math.cos(phi) * Math.cos(decl) * Math.cos(H));
    const az = Math.atan2(Math.sin(H), Math.cos(H) * Math.sin(phi) - Math.tan(decl) * Math.cos(phi)) + Math.PI;
    this.timeOfDay = { hours, latitudeDeg, dayOfYear };
    return this.setSun(el / DEG, ((az / DEG) + 360) % 360);
  }

  followTarget(pos) {
    this._target.copy(pos);
    this._placeSun();
    this.sky.position.copy(pos); this.dome.position.copy(pos); this.stars.position.copy(pos);
  }

  _placeSun() {
    const t = this._target;
    // snap the shadow camera to texels so shadows do not shimmer while driving
    const snap = 90 / 2048;
    const tx = Math.round(t.x / snap) * snap, tz = Math.round(t.z / snap) * snap;
    this.sun.target.position.set(tx, 0, tz);
    this.sun.position.set(tx, 0, tz).addScaledVector(this.sunDir.y > 0.02 ? this.sunDir : _down.set(0.2, 1, 0.2).normalize(), 350);
    this.sun.target.updateMatrixWorld();
  }

  setEnvironment(name) {
    const E = {
      day: { L_sky: 10000, L_road: 5000, L_adapt: 5000, exposure: 0.5, hours: 14.6 },
      overcast: { L_sky: 1000, L_road: 700, L_adapt: 700, exposure: 0.62, hours: 13 },
      dusk: { L_sky: 100, L_road: 20, L_adapt: 40, exposure: 0.85, hours: 19.05 },
      night: { L_sky: 0.005, L_road: 1.5, L_adapt: 1.5, exposure: 1.5, hours: 23.5 },
    }[name];
    if (!E) throw new Error('unknown environment ' + name);
    this.envName = name;
    this.setTimeOfDay(E.hours);
    const sk = this.sky.material.uniforms;
    const fog = this.scene.fog;
    const night = name === 'night', dusk = name === 'dusk', over = name === 'overcast';
    this.sky.visible = name === 'day' || dusk;
    this.dome.visible = over || night;
    this.stars.visible = night;
    if (name === 'day') {
      sk.turbidity.value = 1.8; sk.rayleigh.value = 2.0; sk.mieCoefficient.value = 0.004; sk.mieDirectionalG.value = 0.8;
      this.sun.color.set(0xfff3e2); this.sun.intensity = 3.4; this.sun.castShadow = true;
      this.hemi.color.set(0xbcd7f5); this.hemi.groundColor.set(0x6c6650); this.hemi.intensity = 0.9;
      fog.color.set(0xc7d9ea); fog.near = 350; fog.far = 3400;
    } else if (over) {
      const d = this.dome.material.uniforms; d.top.value.set(0x9aa2ab); d.horizon.value.set(0xc9ced3); d.bottom.value.set(0x8e9398);
      this.sun.color.set(0xe8eef5); this.sun.intensity = 0.55; this.sun.castShadow = true; this.sun.shadow.radius = 8;
      this.hemi.color.set(0xd5dbe2); this.hemi.groundColor.set(0x5e6052); this.hemi.intensity = 2.3;
      fog.color.set(0xc4c9ce); fog.near = 120; fog.far = 1500;
    } else if (dusk) {
      sk.turbidity.value = 5; sk.rayleigh.value = 2.6; sk.mieCoefficient.value = 0.006; sk.mieDirectionalG.value = 0.86;
      this.sun.color.set(0xffa36a); this.sun.intensity = 1.1; this.sun.castShadow = true; this.sun.shadow.radius = 3;
      this.hemi.color.set(0x7f8fb8); this.hemi.groundColor.set(0x3d3a3a); this.hemi.intensity = 0.55;
      fog.color.set(0x8d8a9a); fog.near = 200; fog.far = 2200;
    } else {
      const d = this.dome.material.uniforms; d.top.value.set(0x010309); d.horizon.value.set(0x0a1222); d.bottom.value.set(0x020305);
      this.sun.color.set(0x8fa6d8); this.sun.intensity = 0.06; this.sun.castShadow = false;
      this.hemi.color.set(0x1a2440); this.hemi.groundColor.set(0x050505); this.hemi.intensity = 0.25;
      fog.color.set(0x05080f); fog.near = 60; fog.far = 900;
    }
    if (name === 'day') this.sun.shadow.radius = 2;
    // emissive scenery
    const lampOn = night ? 1 : dusk ? 0.6 : 0;
    this._lampMat.emissiveIntensity = night ? 6 : dusk ? 3 : 0.0;
    this._windowMats.forEach((m) => { m.emissiveIntensity = night ? 1.3 : dusk ? 0.6 : 0; });
    this.streetLights.forEach((l) => { l.userData.on = lampOn; });
    for (const a of this.agents) this._setAgentLights(a);
    // image-based lighting strength, used when the integrator sets scene.environment (e.g. a RoomEnvironment PMREM)
    this.scene.environmentIntensity = { day: 0.6, overcast: 0.7, dusk: 0.25, night: 0.03 }[name];
    this._hemiBase = this.hemi.intensity;
    this.applyIBL();
    this.env = { name, L_sky: E.L_sky, L_road: E.L_road, L_adapt: E.L_adapt, exposure: E.exposure, environmentIntensity: this.scene.environmentIntensity };
    return this.env;
  }

  // ---- static geometry --------------------------------------------------------------------------------------
  _buildGround() {
    const R = this._R; let minX = 1e9, maxX = -1e9, minZ = 1e9, maxZ = -1e9;
    for (let i = 0; i <= R.N; i++) { minX = Math.min(minX, R.X[i]); maxX = Math.max(maxX, R.X[i]); minZ = Math.min(minZ, R.Z[i]); maxZ = Math.max(maxZ, R.Z[i]); }
    this.bounds = { minX, maxX, minZ, maxZ };
    const cx = (minX + maxX) / 2, cz = (minZ + maxZ) / 2, size = Math.max(maxX - minX, maxZ - minZ) + 3000;
    const g = new THREE.PlaneGeometry(size, size, 1, 1); g.rotateX(-Math.PI / 2);
    const uv = g.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * size / 7, uv.getY(i) * size / 7);
    const grassMat = M.grass.clone(); grassMat.map = M.grass.map; grassMat.color.set(0xd6e0c4);
    // pushed back in depth so it never wins a depth tie against the road, verge or kerbs at long range
    grassMat.polygonOffset = true; grassMat.polygonOffsetFactor = 4; grassMat.polygonOffsetUnits = 16;
    const ground = new THREE.Mesh(g, grassMat); ground.position.set(cx, -0.06, cz); ground.receiveShadow = true;
    this.scene.add(ground); this.ground = ground;
  }

  _strip(fnLeft, fnRight, s0, s1, step, y, uvScale = 6) {
    // generic ribbon between two offsets along s (offsets may be functions of s)
    const pos = [], uv = [], idx = [];
    const n = Math.max(1, Math.ceil((s1 - s0) / step));
    for (let i = 0; i <= n; i++) {
      const s = s0 + (s1 - s0) * i / n, sm = this.sample(s, this._tmp);
      const oL = typeof fnLeft === 'function' ? fnLeft(s) : fnLeft, oR = typeof fnRight === 'function' ? fnRight(s) : fnRight;
      const yL = typeof y === 'function' ? y(s, oL) : y, yR = typeof y === 'function' ? y(s, oR) : y;
      pos.push(sm.p.x + sm.n.x * oL, yL, sm.p.z + sm.n.z * oL, sm.p.x + sm.n.x * oR, yR, sm.p.z + sm.n.z * oR);
      uv.push(oL / uvScale, s / uvScale, oR / uvScale, s / uvScale);
      if (i < n) { const a = 2 * i; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    g.setIndex(idx); g.computeVertexNormals();
    return g;
  }

  _buildRoadMesh() {
    const L = this._R.length;
    const asph = M.asphalt.clone(); asph.map = M.asphalt.map; asph.color.set(0x9a9a9c); asph.roughness = 0.92;
    const road = new THREE.Mesh(this._strip(-ROAD_HALF, ROAD_HALF, 0, L, 2, 0, 5), asph); road.receiveShadow = true;
    this.scene.add(road); this.roadMesh = road;
    // gravel verge outside town
    const verge = new THREE.MeshStandardMaterial({ color: 0x7a7060, roughness: 1, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 4 });
    const t0 = this.town.s0 - 5, t1 = this.town.s1 + 5;
    for (const [a, b] of [[t1, L + t0]]) {
      for (const side of [-1, 1]) {
        const m = new THREE.Mesh(this._strip(side * ROAD_HALF, side * (ROAD_HALF + 1.1), a, b, 4, -0.01), verge);
        m.receiveShadow = true; this.scene.add(m);
      }
    }
  }

  _buildLines() {
    const L = this._R.length;
    const geo = { white: [], yellow: [] };
    const step = 0.25;
    const emitRun = (l, off, a, b) => {
      const arr = geo[l.color];
      const n = Math.max(1, Math.ceil((b - a) / 1.0));
      const base = arr.length / 3;
      for (let i = 0; i <= n; i++) {
        const s = a + (b - a) * i / n, sm = this.sample(s, this._tmp);
        for (const o of [off - l.width / 2, off + l.width / 2]) arr.push(sm.p.x + sm.n.x * o, 0.006, sm.p.z + sm.n.z * o);
      }
      (arr.idx || (arr.idx = []));
      for (let i = 0; i < n; i++) { const k = base + 2 * i; arr.idx.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
    };
    for (const l of this.lines) {
      const offs = l.style === 'double' ? [l.offset - l.sep / 2, l.offset + l.sep / 2] : [l.offset];
      let runStart = null;
      for (let s = 0; s <= L + 1e-6; s += step) {
        const on = s < L && this.isPainted(l, s);
        if (on && runStart === null) runStart = s;
        if ((!on || s + step > L) && runStart !== null) { for (const o of offs) emitRun(l, o, runStart, Math.min(s, L)); runStart = null; }
      }
    }
    for (const [col, mat] of [['white', M.paintWhite], ['yellow', M.paintYellow]]) {
      const arr = geo[col]; if (!arr.length) continue;
      const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(arr, 3)); g.setIndex(arr.idx); g.computeVertexNormals();
      const m = new THREE.Mesh(g, mat); m.receiveShadow = true; this.scene.add(m);
    }
    // crosswalk: continental bars across all four lanes
    const bars = [];
    const sm = this.sample(this.crosswalkS, this._tmp);
    const cw = new THREE.Group();
    for (let o = -8.1; o <= 8.1 + 1e-6; o += 1.2) {
      const b = new THREE.Mesh(new THREE.PlaneGeometry(3.0, 0.6), M.paintWhite); b.rotation.x = -Math.PI / 2;
      b.position.set(o, 0.006, 0); b.rotation.z = 0; cw.add(b); bars.push(b);
    }
    // local frame of the crosswalk group: X along t, Z along n
    _m4.makeBasis(sm.t, UP, sm.n); cw.quaternion.setFromRotationMatrix(_m4); cw.position.copy(sm.p);
    cw.children.forEach((b) => { const o = b.position.x; b.position.set(0, 0.006, o); });
    this.scene.add(cw);
    // stop bars before the crosswalk in both directions
    for (const [ds, o0, o1] of [[-3.2, 0.15, 7.4], [3.2, -7.4, -0.15]]) {
      const g = this._strip(o0, o1, this.crosswalkS + ds - 0.3, this.crosswalkS + ds + 0.3, 0.6, 0.006);
      this.scene.add(new THREE.Mesh(g, M.paintWhite));
    }
  }

  _buildTown() {
    const { s0, s1 } = this.town;
    const concrete = new THREE.MeshStandardMaterial({ color: 0xb4b1a9, roughness: 0.9 });
    const kerbMat = new THREE.MeshStandardMaterial({ color: 0xc9c6bf, roughness: 0.8 });
    const SW0 = ROAD_HALF + 0.15, SW1 = ROAD_HALF + 2.6, H = 0.15;
    for (const side of [-1, 1]) {
      const top = new THREE.Mesh(this._strip(side * ROAD_HALF, side * SW1, s0, s1, 4, (s, o) => (Math.abs(o) > ROAD_HALF + 0.01 ? H : H)), concrete);
      top.receiveShadow = true; this.scene.add(top);
      const face = new THREE.Mesh(this._strip(side * ROAD_HALF, side * ROAD_HALF, s0, s1, 4, 0), kerbMat);
      // kerb face: vertical strip
      const pos = []; const idx = []; const n = Math.ceil((s1 - s0) / 4);
      for (let i = 0; i <= n; i++) {
        const sm = this.sample(s0 + (s1 - s0) * i / n, this._tmp);
        const x = sm.p.x + sm.n.x * side * ROAD_HALF, z = sm.p.z + sm.n.z * side * ROAD_HALF;
        pos.push(x, 0, z, x, H, z);
        if (i < n) { const a = 2 * i; idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
      }
      face.geometry.dispose();
      const fg = new THREE.BufferGeometry(); fg.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); fg.setIndex(idx); fg.computeVertexNormals();
      face.geometry = fg; face.material = kerbMat.clone(); face.material.side = THREE.DoubleSide; this.scene.add(face);
    }
    this.sidewalk = { inner: SW0, outer: SW1, height: H, center: (ROAD_HALF + SW1) / 2 + 0.3 };

    // buildings
    this._windowMats = [];
    const facades = [];
    for (let v = 0; v < 4; v++) {
      const base = ['#b9a58c', '#8f8a84', '#a0715a', '#c8c2b5'][v];
      const map = canvasTexture(128, 128, (ctx, W, Hh) => {
        ctx.fillStyle = base; ctx.fillRect(0, 0, W, Hh);
        ctx.fillStyle = '#2c3440'; for (let x = 0; x < 2; x++) for (let y = 0; y < 2; y++) ctx.fillRect(14 + x * 64, 16 + y * 64, 38, 40);
        ctx.fillStyle = 'rgba(255,255,255,0.08)'; ctx.fillRect(0, 60, W, 4);
      }, { repeat: [1, 1] });
      const em = canvasTexture(128, 128, (ctx, W, Hh) => {
        const r = rng(31 + v); ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, Hh);
        for (let x = 0; x < 2; x++) for (let y = 0; y < 2; y++) if (r() < 0.55) { ctx.fillStyle = r() < 0.5 ? '#ffd38a' : '#fff1c9'; ctx.fillRect(14 + x * 64, 16 + y * 64, 38, 40); }
      }, { repeat: [1, 1] });
      const mat = new THREE.MeshStandardMaterial({ map, emissiveMap: em, emissive: 0xffffff, emissiveIntensity: 0, roughness: 0.85 });
      this._windowMats.push(mat); facades.push(mat);
    }
    const roofMat = new THREE.MeshStandardMaterial({ color: 0x4a4a4c, roughness: 0.9 });
    const r = rng(404);
    for (const side of [-1, 1]) {
      let s = s0 + 5;
      while (s < s1 - 12) {
        const w = 10 + r() * 14, d = 10 + r() * 10, h = 5 + r() * 14, off = side * (SW1 + 3 + d / 2 + r() * 4);
        const sm = this.sample(s + w / 2, this._tmp);
        const g = new THREE.BoxGeometry(w, h, d);
        const uv = g.attributes.uv;
        // tile the facade 4 m x 3.5 m per texture repeat (faces: +x, -x, +y, -y, +z, -z; 4 verts each)
        for (let f = 0; f < 6; f++) {
          const sx = f < 2 ? d / 4 : w / 4, sy = h / 3.5;
          for (let k = 0; k < 4; k++) { const i = f * 4 + k; uv.setXY(i, uv.getX(i) * sx, uv.getY(i) * sy); }
        }
        const fm = facades[Math.floor(r() * facades.length)];
        const m = new THREE.Mesh(g, [fm, fm, roofMat, roofMat, fm, fm]);
        _m4.makeBasis(sm.t, UP, sm.n); m.quaternion.setFromRotationMatrix(_m4);
        m.position.copy(sm.p).addScaledVector(sm.n, off); m.position.y = h / 2 + H;
        m.castShadow = true; m.receiveShadow = true; this.scene.add(m);
        s += w + 3 + r() * 6;
      }
    }

    // light poles, both sides every 36 m, instanced
    const poles = [];
    for (const side of [-1, 1]) for (let s = s0 + 8; s < s1; s += 36) poles.push({ s: side > 0 ? s : s + 18, side });
    const poleMat = new THREE.MeshStandardMaterial({ color: 0x5d6168, metalness: 0.6, roughness: 0.5 });
    this._lampMat = new THREE.MeshStandardMaterial({ color: 0xfff2d8, emissive: 0xffd9a0, emissiveIntensity: 0 });
    const poleGeo = new THREE.CylinderGeometry(0.07, 0.11, 8, 8); poleGeo.translate(0, 4, 0);
    const armGeo = new THREE.BoxGeometry(0.08, 0.08, 1.9); armGeo.translate(0, 7.9, -0.95);
    const headGeo = new THREE.BoxGeometry(0.35, 0.12, 0.6); headGeo.translate(0, 7.82, -1.75);
    const poleI = new THREE.InstancedMesh(poleGeo, poleMat, poles.length), armI = new THREE.InstancedMesh(armGeo, poleMat, poles.length), headI = new THREE.InstancedMesh(headGeo, this._lampMat, poles.length);
    this.poles = [];
    poles.forEach((pl, i) => {
      const sm = this.sample(pl.s, this._tmp);
      const pos = sm.p.clone().addScaledVector(sm.n, pl.side * (ROAD_HALF + 0.7)); pos.y = H;
      // arm points toward the road: local -Z toward the road centre
      const toRoad = sm.n.clone().multiplyScalar(-pl.side);
      const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, -1), toRoad);
      _m4.compose(pos, q, _one);
      poleI.setMatrixAt(i, _m4); armI.setMatrixAt(i, _m4); headI.setMatrixAt(i, _m4);
      this.poles.push({ s: pl.s, lamp: pos.clone().addScaledVector(toRoad, 1.75).setY(7.7 + H) });
    });
    for (const im of [poleI, armI, headI]) { im.castShadow = true; im.computeBoundingSphere(); this.scene.add(im); }
  }

  _buildRail() {
    const seg = this._R.info[RAIL_SEG];
    const s0 = seg.s0 - 20, s1 = seg.s1 + 20;
    const railMat = new THREE.MeshStandardMaterial({ color: 0xb8bcc0, metalness: 0.8, roughness: 0.35, side: THREE.DoubleSide });
    for (const side of [-1, 1]) {
      const off = side * (ROAD_HALF + 0.9);
      // W-beam as two slanted faces
      const pos = [], idx = []; const n = Math.ceil((s1 - s0) / 2);
      for (let i = 0; i <= n; i++) {
        const sm = this.sample(s0 + (s1 - s0) * i / n, this._tmp);
        for (const [o, y] of [[0, 0.55], [-side * 0.06, 0.66], [0, 0.75], [-side * 0.06, 0.82]]) pos.push(sm.p.x + sm.n.x * (off + o), y, sm.p.z + sm.n.z * (off + o));
        if (i < n) for (let k = 0; k < 3; k++) { const a = 4 * i + k; idx.push(a, a + 4, a + 1, a + 1, a + 4, a + 5); }
      }
      const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals();
      const m = new THREE.Mesh(g, railMat); m.castShadow = true; this.scene.add(m);
      const count = Math.floor((s1 - s0) / 2);
      const post = new THREE.InstancedMesh(new THREE.BoxGeometry(0.1, 0.8, 0.15).translate(0, 0.4, 0), new THREE.MeshStandardMaterial({ color: 0x8a8e93, metalness: 0.6, roughness: 0.5 }), count);
      for (let i = 0; i < count; i++) {
        const sm = this.sample(s0 + i * 2, this._tmp);
        const p = sm.p.clone().addScaledVector(sm.n, off + side * 0.12);
        _m4.compose(p, new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(sm.t, UP, sm.n)), _one); post.setMatrixAt(i, _m4);
      }
      post.castShadow = true; post.computeBoundingSphere(); this.scene.add(post);
    }
  }

  _buildTrees() {
    const R = this._R; const r = rng(99);
    // spatial hash of road points
    const cell = 25, hash = new Map();
    for (let i = 0; i <= R.N; i += 4) {
      const k = Math.floor(R.X[i] / cell) + ',' + Math.floor(R.Z[i] / cell);
      if (!hash.has(k)) hash.set(k, []); hash.get(k).push([R.X[i], R.Z[i]]);
    }
    const nearRoad = (x, z, d) => {
      const cx = Math.floor(x / cell), cz = Math.floor(z / cell);
      for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) {
        const l = hash.get((cx + a) + ',' + (cz + b)); if (!l) continue;
        for (const [px, pz] of l) if ((px - x) ** 2 + (pz - z) ** 2 < d * d) return true;
      }
      return false;
    };
    const townPts = []; for (let s = this.town.s0 - 40; s < this.town.s1 + 40; s += 10) { const sm = this.sample(s, this._tmp); townPts.push([sm.p.x, sm.p.z]); }
    const nearTown = (x, z) => townPts.some(([px, pz]) => (px - x) ** 2 + (pz - z) ** 2 < 55 * 55);
    const trees = [];
    let tries = 0;
    while (trees.length < 2400 && tries < 40000) {
      tries++;
      let x, z;
      if (r() < 0.7) {
        const sm = this.sample(r() * R.length, this._tmp); const side = r() < 0.5 ? -1 : 1;
        const d = ROAD_HALF + 5 + Math.pow(r(), 1.6) * 120;
        x = sm.p.x + sm.n.x * side * d; z = sm.p.z + sm.n.z * side * d;
      } else {
        x = this.bounds.minX - 500 + r() * (this.bounds.maxX - this.bounds.minX + 1000);
        z = this.bounds.minZ - 500 + r() * (this.bounds.maxZ - this.bounds.minZ + 1000);
      }
      if (nearRoad(x, z, ROAD_HALF + 5) || nearTown(x, z)) continue;
      trees.push({ x, z, kind: r() < 0.45 ? 0 : 1, s: 0.75 + r() * 0.6, hue: r() });
    }
    this.treeCount = trees.length;
    const trunkGeo = new THREE.CylinderGeometry(0.14, 0.22, 3, 6); trunkGeo.translate(0, 1.5, 0);
    const coneGeo = new THREE.ConeGeometry(2.1, 7, 8); coneGeo.translate(0, 6, 0);
    const ballGeo = new THREE.IcosahedronGeometry(2.8, 1); ballGeo.scale(1, 0.85, 1); ballGeo.translate(0, 5.2, 0);
    const trunkMat = new THREE.MeshStandardMaterial({ color: 0x5a4330, roughness: 1 });
    const leafMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.95, flatShading: true });
    const trunks = new THREE.InstancedMesh(trunkGeo, trunkMat, trees.length);
    const cones = new THREE.InstancedMesh(coneGeo, leafMat, trees.filter((t) => t.kind === 0).length);
    const balls = new THREE.InstancedMesh(ballGeo, leafMat, trees.filter((t) => t.kind === 1).length);
    let ic = 0, ib = 0; const col = new THREE.Color();
    trees.forEach((t, i) => {
      _m4.compose(_v.set(t.x, -0.02, t.z), _q.setFromAxisAngle(UP, t.hue * 6.28), _sc.setScalar(t.s));
      trunks.setMatrixAt(i, _m4);
      if (t.kind === 0) { cones.setMatrixAt(ic, _m4); cones.setColorAt(ic++, col.setHSL(0.31 + t.hue * 0.05, 0.42, 0.2 + t.hue * 0.08)); }
      else { balls.setMatrixAt(ib, _m4); balls.setColorAt(ib++, col.setHSL(0.22 + t.hue * 0.1, 0.45, 0.27 + t.hue * 0.1)); }
    });
    for (const im of [trunks, cones, balls]) { im.castShadow = true; im.receiveShadow = false; im.computeBoundingSphere(); this.scene.add(im); }
  }

  _signTexture(value) {
    return canvasTexture(240, 300, (ctx, W, H) => {
      ctx.fillStyle = '#f4f4f0'; ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = '#111'; ctx.lineWidth = 8; ctx.strokeRect(12, 12, W - 24, H - 24);
      ctx.fillStyle = '#111'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.font = '700 44px "Helvetica Neue", Helvetica, Arial, sans-serif';
      ctx.fillText('SPEED', W / 2, 62); ctx.fillText('LIMIT', W / 2, 112);
      ctx.font = '700 118px "Helvetica Neue", Helvetica, Arial, sans-serif';
      ctx.fillText(String(value), W / 2, 205);
    });
  }

  _buildSigns() {
    this.signs = [];
    const L = this._R.length;
    const backMat = new THREE.MeshStandardMaterial({ color: 0x8d9196, metalness: 0.6, roughness: 0.5 });
    const postMat = new THREE.MeshStandardMaterial({ color: 0x9a9ea3, metalness: 0.7, roughness: 0.4 });
    const mats = {};
    const zoneValue = (s) => {
      if (s > this.town.s0 - 150 && s < this.town.s1) return 35;
      const seg = this._R.info.find((g) => s >= g.s0 && s < g.s1);
      return seg && seg.type === 'S' && seg.s1 - seg.s0 > 700 ? 65 : 55;
    };
    let s = 120, i = 0;
    while (s < L - 60) {
      if (Math.abs(s - this.crosswalkS) < 40) s += 50;
      const value = zoneValue(s + 60);
      const inTown = s > this.town.s0 && s < this.town.s1;
      const off = inTown ? ROAD_HALF + 1.6 : ROAD_HALF + 1.4;
      const sm = this.sample(s, this._tmp);
      const g = new THREE.Group();
      _m4.makeBasis(sm.t, UP, sm.n); g.quaternion.setFromRotationMatrix(_m4);
      g.position.copy(sm.p).addScaledVector(sm.n, off); g.position.y = inTown ? 0.15 : 0;
      const post = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 2.3, 8), postMat); post.position.y = 1.15; post.castShadow = true; g.add(post);
      if (!mats[value]) mats[value] = new THREE.MeshStandardMaterial({ map: this._signTexture(value), roughness: 0.5, emissive: 0xffffff, emissiveMap: null, emissiveIntensity: 0 });
      // face toward approaching traffic: plane normal = -X (local)
      const face = new THREE.Mesh(new THREE.PlaneGeometry(0.61, 0.76), mats[value]); face.rotation.y = -Math.PI / 2; face.position.set(-0.02, 2.2, 0); g.add(face);
      const back = new THREE.Mesh(new THREE.BoxGeometry(0.015, 0.76, 0.61), backMat); back.position.set(0, 2.2, 0); back.castShadow = true; g.add(back);
      this.scene.add(g);
      const pos = g.position.clone(); pos.y += 2.2;
      this.signs.push({ id: 'sign' + (i++), s, offset: off, value, position: pos.addScaledVector(sm.t, -0.02), normal: sm.t.clone().negate(), size: [0.61, 0.76], object: g });
      s += 600 + rng(s | 0)() * 300;
    }
    this._signMats = mats;
  }

  // ---- agents ------------------------------------------------------------------------------------------------
  _buildAgents() {
    const r = rng(2024);
    this.agents = [];
    let id = 0;
    const add = (kind, model, fields) => {
      const a = {
        id: kind + (id++), kind, object: model.group, model, s: 0, offset: 0, speed: 0, dir: 1, y: 0,
        length: model.L, width: model.W, height: model.H, heading: new THREE.Vector3(1, 0, 0), _pos: new THREE.Vector3(),
        worldPosition() { return this.kind === 'person' ? this._pos.clone() : this._pos.clone().addScaledVector(this.heading, -this.length / 2); },
        ...fields,
      };
      this.scene.add(a.object); this.agents.push(a); return a;
    };
    this.lead = add('car', makeVehicle('car', r), { role: 'lead', offset: this.lanes.ego.center, accel: 0, braking: false });
    this.lead.model.paint.color.set(0x8c1d24);
    for (let i = 0; i < 2; i++) add(i ? 'suv' : 'car', makeVehicle(i ? 'suv' : 'car', r), { role: 'adjacent', offset: this.lanes.adjacent.center, rel: i ? -45 : 70, dv: i ? 2.5 : -1.5 });
    const onc = ['car', 'truck', 'suv', 'bus', 'car', 'motorcycle'];
    onc.forEach((k, i) => add(k, makeVehicle(k, r), { role: 'oncoming', dir: -1, offset: this.lanes.oncoming[i % 2], rel: 80 + i * 90, cruise: 22 + r() * 6 }));
    const bike = makeBicycle(r);
    this.cyclist = add('bicycle', bike, { role: 'cyclist', offset: 2 * LANE + 0.85, rel: 140, speed: 5.5 });
    const tc = (this.town.s0 + this.town.s1) / 2, tl = this.town.s1 - this.town.s0;
    for (let i = 0; i < 10; i++) {
      const p = makePerson(r);
      const side = i % 2 ? 1 : -1;
      add('person', { group: p.group, L: 0.5, W: 0.45, H: 1.75 * p.scale, person: p }, {
        role: 'walker', offset: side * (this.sidewalk.center + (r() - 0.5) * 1.2), s: this.town.s0 + r() * tl, dir: r() < 0.5 ? 1 : -1,
        speed: 1.1 + r() * 0.5, phase: r() * 6.28, y: this.sidewalk.height,
      });
    }
    const cp = makePerson(r);
    this.crosser = add('person', { group: cp.group, L: 0.5, W: 0.45, H: 1.75 * cp.scale, person: cp }, {
      role: 'crosser', s: this.crosswalkS - 0.6, offset: -this.sidewalk.center, speed: 1.4, phase: 0, y: this.sidewalk.height, state: 'wait', crossing: false,
    });
    void tc;
    this._initialised = false;
  }

  _setAgentLights(a) {
    const m = a.model; if (!m || !m.lights) return;
    const night = this.envName === 'night', dusk = this.envName === 'dusk';
    const on = night || dusk;
    if (m.tail) m.tail.emissiveIntensity = (on ? 2.2 : 0.15) + (a.braking ? 4 : 0);
    if (m.head) m.head.emissiveIntensity = on ? 3 : 0.1;
    for (const s of m.lights.tail) { s.visible = on || a.braking; s.material.opacity = a.braking ? 1 : 0.6; }
    for (const s of m.lights.head) s.visible = on && a.dir < 0;
  }

  _placeAgent(a) {
    const sm = this.sample(a.s, this._tmp);
    a._pos.copy(sm.p).addScaledVector(sm.n, a.offset); a._pos.y = a.y;
    a.heading.copy(sm.t).multiplyScalar(a.dir >= 0 ? 1 : -1);
    _side.crossVectors(a.heading, UP);
    _m4.makeBasis(a.heading, UP, _side);
    a.object.quaternion.setFromRotationMatrix(_m4);
    a.object.position.copy(a._pos);
    a.inEgoLane = a.dir > 0 && Math.abs(a.offset - this.lanes.ego.center) < LANE / 2;
  }

  _spinWheels(a, dist) {
    for (const w of a.model.wheels || []) w.userData.spin.rotation.z -= dist / w.userData.r;
  }

  // Scripted traffic for the HUD's drawing rules. 'cutin': the adjacent car pulls into the ego lane 22 m ahead, holds
  // there, then leaves (the lead chevron must move to it and back, through the 3-frame and 400 ms rules). 'brake': the
  // lead brakes hard (brake lamps, the gap and the seconds shrink; the driver model brakes behind it).
  startScenario(name, ego) {
    const t = this.time;
    if (name === 'cutin') {
      const a = this.agents.find((q) => q.role === 'adjacent' && q.kind === 'car') || this.agents.find((q) => q.role === 'adjacent');
      if (!a) return null;
      a.scn = { name, t0: t, phase: 'approach', v: ego.speed + 1.5 };
      a.s = this.wrap(ego.s + EGO_FRONT + 22 + a.length / 2); a.offset = this.lanes.adjacent.center; a.braking = false; this._setAgentLights(a);
      if (this.lead) this.lead.minGap = 48;
      return a;
    }
    if (name === 'brake') {
      const a = this.lead; if (!a) return null;
      a.scn = { name, t0: t, phase: 'brake', v: a.speed || ego.speed, sOwn: a.s };
      return a;
    }
    return null;
  }

  update(dt, ego = { s: 0, offset: this.lanes.ego.center, speed: 25 }) {
    this.time += dt;
    const t = this.time, L = this._R.length, r = this.rand;
    const rel = (s) => { let d = this.wrap(s) - this.wrap(ego.s); if (d > L / 2) d -= L; if (d < -L / 2) d += L; return d; };
    for (const a of this.agents) {
      const prevS = a.s;
      if (a.scn) {
        const sc = a.scn, age = t - sc.t0;
        if (sc.name === 'cutin') {
          const egoC = this.lanes.ego.center, adjC = this.lanes.adjacent.center;
          if (sc.phase === 'approach' && age > 1.2) { sc.phase = 'merge'; sc.t1 = t; }
          if (sc.phase === 'merge') { const f = smoothstep(0, 3.2, t - sc.t1); a.offset = lerp(adjC, egoC, f); if (f >= 1) { sc.phase = 'hold'; sc.t1 = t; sc.v = ego.speed - 0.8; } }
          if (sc.phase === 'hold') { sc.v = lerp(sc.v, ego.speed - 0.8, clamp(dt * 0.5, 0, 1)); if (t - sc.t1 > 11) { sc.phase = 'leave'; sc.t1 = t; } }
          if (sc.phase === 'leave') { const f = smoothstep(0, 3.0, t - sc.t1); a.offset = lerp(egoC, adjC, f); sc.v += 2.0 * dt; if (f >= 1) { a.scn = null; a.dv = sc.v - ego.speed; if (this.lead) this.lead.minGap = 0; } }
          a.speed = Math.max(0, sc.v);
          a.s = this.wrap(a.s + a.speed * dt);
          a.inCutIn = true;
        } else if (sc.name === 'brake') {
          if (sc.phase === 'brake') { sc.v = Math.max(2, sc.v - 5.5 * dt); a.accel = -5.5; if (age > 2.6) { sc.phase = 'hold'; sc.t1 = t; } }
          else if (sc.phase === 'hold') { a.accel = 0; if (t - sc.t1 > 1.5) { sc.phase = 'resume'; } }
          else { sc.v += 2.2 * dt; a.accel = 2.2; }
          a.speed = sc.v;
          a.s = this.wrap(a.s + a.speed * dt);
          const was = a.braking; a.braking = a.accel < -0.6; if (was !== a.braking) this._setAgentLights(a);
          // back to the formula once the lead has reached the gap it calls for (or after 25 s)
          const gapNow = rel(a.s) - EGO_FRONT - a.length / 2;
          const gapWant = clamp(42.5 + 27.5 * (0.62 * Math.sin(0.11 * t) + 0.38 * Math.sin(0.237 * t + 1.7)), 15, 70);
          a.gap = gapNow;
          if ((sc.phase === 'resume' && gapNow >= gapWant) || age > 25) { a.scn = null; }
        }
        this._placeAgent(a);
        if (a.kind !== 'person') this._spinWheels(a, a.speed * dt);
        continue;
      }
      if (a.role === 'lead') {
        const gap = Math.max(a.minGap || 0, clamp(42.5 + 27.5 * (0.62 * Math.sin(0.11 * t) + 0.38 * Math.sin(0.237 * t + 1.7)), 15, 70));
        a.gap = gap;
        const s = ego.s + EGO_FRONT + gap + a.length / 2;
        const v = this._initialised && dt > 0 ? rel(s - prevS + ego.s) / dt : ego.speed;
        a.accel = this._initialised && dt > 0 ? (v - a.speed) / dt : 0;
        a.speed = this._initialised ? lerp(a.speed, v, clamp(dt * 4, 0, 1)) : v;
        a.s = this.wrap(s);
        a.offset = this.lanes.ego.center + 0.12 * Math.sin(0.3 * t);
        const was = a.braking; a.braking = a.accel < -0.6;
        if (was !== a.braking) this._setAgentLights(a);
      } else if (a.role === 'adjacent') {
        a.dv += (r() - 0.5) * dt * 0.6; a.dv = clamp(a.dv, -4, 4);
        a.speed = Math.max(0, ego.speed + a.dv);
        if (!this._initialised) a.s = this.wrap(ego.s + a.rel);
        a.s = this.wrap(a.s + a.speed * dt);
        const d = rel(a.s);
        if (d > 170) { a.s = this.wrap(ego.s - 70 - r() * 20); a.dv = 2 + r() * 2; }
        if (d < -90) { a.s = this.wrap(ego.s + 150 + r() * 30); a.dv = -2 - r() * 2; }
      } else if (a.role === 'oncoming') {
        a.speed = a.cruise;
        if (!this._initialised) a.s = this.wrap(ego.s + a.rel);
        a.s = this.wrap(a.s - a.speed * dt);
        if (rel(a.s) < -70) a.s = this.wrap(ego.s + 260 + r() * 260);
      } else if (a.role === 'cyclist') {
        if (!this._initialised) a.s = this.wrap(ego.s + a.rel);
        a.s = this.wrap(a.s + a.speed * dt);
        const d = rel(a.s);
        if (d < -40 || d > 600) a.s = this.wrap(ego.s + 180 + r() * 220);
        a.model.crank.rotation.z -= a.speed * dt / 0.35 * 0.4;
        a.model.rider.pose('cycle', -a.model.crank.rotation.z);
      } else if (a.role === 'walker') {
        a.s += a.dir * a.speed * dt;
        if (a.s > this.town.s1) { a.s = this.town.s1; a.dir = -1; }
        if (a.s < this.town.s0) { a.s = this.town.s0; a.dir = 1; }
        a.phase += a.speed * dt * 3.6; a.model.person.pose('walk', a.phase);
      } else if (a.role === 'crosser') {
        const d = rel(this.crosswalkS) - EGO_FRONT;
        if (a.state === 'wait' && d > 0 && d < 62 && ego.speed > 0.5) { a.state = 'cross'; }
        if (a.state === 'cross') {
          a.offset += a.speed * dt;
          a.phase += a.speed * dt * 3.6; a.model.person.pose('walk', a.phase);
          if (a.offset >= this.sidewalk.center) { a.offset = this.sidewalk.center; a.state = 'done'; a.model.person.pose('stand'); }
        }
        if (a.state === 'done' && Math.abs(d) > 300) { a.state = 'wait'; a.offset = -this.sidewalk.center; }
        a.crossing = a.state === 'cross';
        a.y = Math.abs(a.offset) > ROAD_HALF + 0.05 ? this.sidewalk.height : 0;
        // face across the road while crossing, along it while waiting
        a.dir = 1;
      }
      this._placeAgent(a);
      if (a.role === 'crosser' && a.state === 'cross') {
        const sm = this.sample(a.s, this._tmp);
        _m4.makeBasis(sm.n, UP, _side.copy(sm.n).cross(UP)); a.object.quaternion.setFromRotationMatrix(_m4); a.heading.copy(sm.n);
      }
      if (a.kind !== 'person') {
        const dist = a.role === 'lead' ? a.speed * dt : a.speed * dt;
        this._spinWheels(a, dist);
      }
    }
    this._initialised = true;
    // street lights: move the pool to the nearest poles
    if (this.envName === 'night' || this.envName === 'dusk') {
      const near = this.poles.map((p) => ({ p, d: Math.abs(rel(p.s) - 25) })).sort((a, b) => a.d - b.d).slice(0, this.streetLights.length);
      this.streetLights.forEach((l, i) => {
        const n = near[i]; if (!n || n.d > 160) { l.intensity = 0; return; }
        l.position.copy(n.p.lamp); l.intensity = 45 * (l.userData.on || 0);
      });
    } else this.streetLights.forEach((l) => { l.intensity = 0; });
  }

  // Convenience for the HUD: agents within a range ahead of the ego, nearest first.
  agentsNear(ego, ahead = 120, behind = 10) {
    const L = this._R.length;
    const out = [];
    for (const a of this.agents) {
      let d = this.wrap(a.s) - this.wrap(ego.s); if (d > L / 2) d -= L; if (d < -L / 2) d += L;
      if (d > -behind && d < ahead) out.push({ agent: a, ds: d });
    }
    return out.sort((x, y) => x.ds - y.ds);
  }
}

const _m4 = new THREE.Matrix4();
const _v = new THREE.Vector3(), _q = new THREE.Quaternion(), _sc = new THREE.Vector3(), _one = new THREE.Vector3(1, 1, 1);
const _side = new THREE.Vector3(), _down = new THREE.Vector3();
export { EGO_FRONT, LANE, ROAD_HALF };
