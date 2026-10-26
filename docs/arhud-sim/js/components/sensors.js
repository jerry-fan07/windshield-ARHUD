// Sensors: the ZED 2i road camera with its stalk clamp, the OAK-D Pro driver camera, the ZED-F9R GNSS board and its antenna.
import * as THREE from 'three';
import { M } from '../mats.js';
import { rbox, box, cyl, cylX, cylZ, sphere, rng, DEG } from '../util.js';
import { makeComponent, addPart } from './contract.js';
import { R } from '../params.js';
import { MIRROR_STALK, ROAD_CAM, ROAD_CAM_BASELINE } from '../geom.js';
import { FONT, vec, put, mat, MX, cost, decal, instanced, smd, chip, glow, led, Port, jst, header, livePanel, panelBg, txt, cable } from './electronics.js';

// Bar with a rounded-rectangle front profile (Y by Z, corner radius r), extruded along X with a small bevel. Centred.
function roundedBar(dx, dy, dz, r, bevel, material) {
  const w = dz / 2 - bevel, h = dy / 2 - bevel, rr = Math.min(r, w, h);
  const sh = new THREE.Shape();
  sh.moveTo(-w + rr, -h); sh.lineTo(w - rr, -h); sh.quadraticCurveTo(w, -h, w, -h + rr); sh.lineTo(w, h - rr); sh.quadraticCurveTo(w, h, w - rr, h);
  sh.lineTo(-w + rr, h); sh.quadraticCurveTo(-w, h, -w, h - rr); sh.lineTo(-w, -h + rr); sh.quadraticCurveTo(-w, -h, -w + rr, -h);
  const g = new THREE.ExtrudeGeometry(sh, { depth: dx - 2 * bevel, bevelEnabled: bevel > 0, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 3, curveSegments: 12 });
  g.translate(0, 0, -(dx - 2 * bevel) / 2); g.rotateY(Math.PI / 2);
  const m = new THREE.Mesh(g, material); m.castShadow = true; m.receiveShadow = true;
  return m;
}

const lensRing = (r, t, m) => { const g = new THREE.Mesh(new THREE.TorusGeometry(r, t, 10, 40), m); g.rotation.y = Math.PI / 2; return g; };

// A camera lens facing +X at the origin: barrel, glass, aperture ring.
function lens(r, depth, glassMat = M.lens) {
  const g = new THREE.Group();
  put(g, cylX(r, depth, M.aluAnodBlack, 32), -depth / 2, 0, 0);
  put(g, cylX(r * 0.72, 0.0006, glassMat, 32), 0.0002, 0, 0);
  put(g, cylX(r * 0.30, 0.0004, M.flock, 24), 0.0006, 0, 0);
  const ring = lensRing(r * 0.86, r * 0.08, M.steel); ring.position.x = 0.0003; g.add(ring);
  return g;
}

function frustum(hDeg, vDeg, len, color) {
  const th = Math.tan(hDeg * DEG), tv = Math.tan(vDeg * DEG);
  const c = [[len, len * tv, len * th], [len, len * tv, -len * th], [len, -len * tv, -len * th], [len, -len * tv, len * th]];
  const pts = [];
  for (const p of c) pts.push(0, 0, 0, ...p);
  for (let i = 0; i < 4; i++) pts.push(...c[i], ...c[(i + 1) % 4]);
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  const l = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.7, depthWrite: false }));
  l.renderOrder = 6;
  return l;
}

// ---- Stereolabs ZED 2i + stalk clamp ----------------------------------------------------
export function buildZed2i() {
  const c = makeComponent(THREE, {
    id: 'zed2i', name: 'Stereolabs ZED 2i (4 mm lenses) with mirror-stalk clamp', category: 'sensor',
    mount: 'LEFT lens optical centre (the plan\'s car-frame origin); X along the optical axis, right lens at +Z 0.12 m', size: [0.11, 0.09, 0.18],
  });
  const B = R.B_ST, BX = 0.043, BY = 0.030, BZ = 0.1752, cx = -0.0135, cz = B / 2;
  const body = new THREE.Group();
  put(body, roundedBar(BX, BY, BZ, 0.012, 0.0025, M.aluAnodBlack), cx, 0, cz);
  put(body, roundedBar(BX * 0.55, BY + 0.0006, BZ + 0.0006, 0.0123, 0.0, M.aluDark), cx - 0.006, 0, cz);
  put(body, cyl(0.0036, 0.0036, 0.0012, MX.brass, 20), cx, -BY / 2 - 0.0003, cz);
  put(body, cyl(0.0022, 0.0022, 0.0013, M.flock, 16), cx, -BY / 2 - 0.0004, cz);
  const slots = [];
  for (let i = 0; i < 12; i++) slots.push([cx - BX / 2 - 0.00005, -0.006 + (i % 3) * 0.006, cz - 0.035 + Math.floor(i / 3) * 0.02]);
  body.add(instanced(new THREE.BoxGeometry(0.0004, 0.0022, 0.012), M.flock, slots));
  const usb = put(body, new THREE.Group(), cx - BX / 2 - 0.0002, 0, cz + 0.055, 0, Math.PI, 0);
  put(usb, Port.usbC(), 0, 0, 0);
  for (const s of [-1, 1]) put(usb, cylX(0.0012, 0.0006, M.flock, 12), 0.0002, 0, s * 0.0085);
  put(body, decal('ZED 2i · 4 mm', 0.03, '+y', { color: '#9aa3ad', font: '600 48px ' + FONT }), cx + 0.014, BY / 2 + 0.0002, cz).rotation.z = Math.PI / 2;
  addPart(c, 'body', 'Aluminium body (IP66), USB-C with screw locks, 1/4-20 thread', body, vec(-0.05, 0, 0), 'Sealed aluminium enclosure; USB-C with screw locks on the back; tripod thread underneath.');

  const board = new THREE.Group();
  put(board, box(0.0016, 0.022, 0.16, M.pcbGreen), -0.006, 0, cz);
  for (const z of [0, B]) { put(board, box(0.002, 0.008, 0.008, M.chip), -0.0043, 0, z); put(board, box(0.0003, 0.005, 0.006, mat('sensorGlass', () => M.color(0x4a3a70, 0.1, 0.3))), -0.0031, 0, z); }
  put(board, box(0.0015, 0.004, 0.004, M.chip), -0.0045, -0.006, cz);
  put(board, decal('IMU', 0.004, '+x', { color: '#e6e9ee', font: '700 48px ' + FONT }), -0.0036, -0.006, cz);
  put(board, chip(0.009, 0.009, 0.0012, '', 0), -0.0068, 0.005, cz + 0.02).rotation.z = Math.PI / 2;
  addPart(c, 'board', 'Stereo sensor board and IMU', board, vec(0, 0.06, 0), 'Two rolling-shutter image sensors 120 mm apart and the 400 Hz IMU.');

  const front = new THREE.Group();
  put(front, roundedBar(0.0016, BY - 0.004, BZ - 0.006, 0.0102, 0, MX.darkGlass), 0.0082, 0, cz);
  put(front, decal('ZED 2i', 0.018, '+x', { color: '#f2f4f6', font: '600 64px ' + FONT }), 0.0093, 0.004, cz);
  const st = put(front, led(0x3d8bff, 0.0004, 0.0015, 0.0015), 0.0093, -0.007, cz);
  addPart(c, 'front', 'Front glass with polariser', front, vec(0.05, 0, 0), 'Front window with a built-in polariser.');
  const lL = lens(0.0085, 0.006); lL.position.set(0.0094, 0, 0);
  addPart(c, 'lensL', 'Left 4 mm lens (origin of the car frame)', lL, vec(0.07, 0.0, -0.03), 'The left lens centre is the origin of the plan\'s car frame: x forward, y right, z down.');
  const lR = lens(0.0085, 0.006); lR.position.set(0.0094, 0, B);
  addPart(c, 'lensR', 'Right 4 mm lens', lR, vec(0.07, 0.0, 0.03), '120 mm stereo baseline.');

  // clamp bracket around the mirror stalk
  const S = MIRROR_STALK.clone().sub(ROAD_CAM);
  const axis = vec(-0.6, -0.8, 0).normalize();
  const radial = vec(0.8, -0.6, 0);
  const plate = new THREE.Group();
  put(plate, rbox(0.032, 0.004, 0.04, 0.002, M.aluAnodBlack), cx, -BY / 2 - 0.0026, cz);
  put(plate, cyl(0.004, 0.004, 0.003, M.steel, 6), cx, -BY / 2 - 0.006, cz);
  addPart(c, 'plate', 'Quick-release plate on the 1/4-20 thread', plate, vec(0, -0.04, 0), 'Screws into the camera\'s tripod thread.');
  const arm = new THREE.Group();
  const ra = S.clone().addScaledVector(radial, 0.017);
  put(arm, cable([[cx - 0.016, -BY / 2 - 0.0026, cz], [-0.044, -0.014, cz], [-0.049, 0.008, cz], [-0.052, 0.032, cz], [ra.x, ra.y, ra.z]], 0.0035, M.aluAnodBlack), 0, 0, 0);
  addPart(c, 'arm', 'Rigid bracket arm', arm, vec(-0.04, 0, 0), 'Rigid so the camera cannot drift; registration depends on its pose (target check before demos).');
  const clamp = new THREE.Group();
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.0135, 0.0038, 12, 36), M.aluAnodBlack);
  ring.quaternion.setFromUnitVectors(vec(0, 0, 1), axis); ring.position.copy(S); clamp.add(ring);
  const pad = new THREE.Mesh(new THREE.TorusGeometry(0.0108, 0.0012, 8, 36), M.rubber); pad.quaternion.copy(ring.quaternion); pad.position.copy(S); clamp.add(pad);
  const ks = S.clone().add(vec(0, 0, 0.022));
  put(clamp, cylZ(0.0018, 0.012, M.steel, 12), S.x, S.y, S.z + 0.016);
  put(clamp, cylZ(0.006, 0.006, M.rubber, 18), ks.x, ks.y, ks.z);
  addPart(c, 'clamp', 'Mirror-stalk clamp with thumbscrew', clamp, vec(-0.03, 0.05, 0), 'Clamps the rear-view-mirror stalk with a rubber liner: nothing is bonded to the glass, and it comes off without tools.');
  const cab = new THREE.Group();
  const up = cz + 0.055;
  put(cab, rbox(0.012, 0.007, 0.016, 0.002, M.plasticBlack), cx - BX / 2 - 0.006, 0, up);
  put(cab, cable([[cx - BX / 2 - 0.012, 0, up], [-0.06, 0.005, up], [-0.075, 0.03, up + 0.01], [-0.085, 0.07, up + 0.02]], 0.0022, M.cableBlack), 0, 0, 0);
  addPart(c, 'cable', 'USB 3 cable (to the Jetson along the headliner)', cab, vec(-0.05, 0, 0.03), 'Runs along the headliner and A-pillar to the Jetson.');

  // working visuals
  const fx = new THREE.Group(); fx.visible = false; c.group.add(fx);
  fx.add(frustum(40, 26, 0.32, 0x5ec8ff));
  const fR = frustum(40, 26, 0.32, 0xff7bd5); fR.position.z = B; fx.add(fR);
  // road patch point cloud
  const rand = rng(17);
  const N = 260, pts = [], isIn = [];
  for (let i = 0; i < N; i++) {
    const x = 0.16 + rand() * 0.36, z = -0.10 + rand() * 0.32;
    if (i < 205) { pts.push(vec(x, -0.115 - 0.03 * (x - 0.16) + (rand() - 0.5) * 0.006, z)); isIn.push(true); }
    else if (i < 240) { pts.push(vec(0.38 + rand() * 0.06, -0.115 + rand() * 0.08, 0.08 + rand() * 0.07)); isIn.push(false); }
    else { pts.push(vec(x, -0.11 + rand() * 0.12, z)); isIn.push(false); }
  }
  const pg = new THREE.BufferGeometry().setFromPoints(pts);
  const cols = new Float32Array(N * 3); pg.setAttribute('color', new THREE.BufferAttribute(cols, 3));
  const cloud = new THREE.Points(pg, new THREE.PointsMaterial({ size: 0.006, vertexColors: true, sizeAttenuation: true, toneMapped: false }));
  fx.add(cloud);
  const planeMesh = new THREE.Mesh(new THREE.PlaneGeometry(0.42, 0.38), new THREE.MeshBasicMaterial({ color: 0x4fd18b, transparent: true, opacity: 0.18, side: THREE.DoubleSide, depthWrite: false }));
  fx.add(planeMesh);
  const picks = [0, 1, 2].map(() => { const s = sphere(0.005, M.emissive(0xffd27a, 1.5), 12); fx.add(s); return s; });
  const triGeo = new THREE.BufferGeometry().setFromPoints([vec(), vec(), vec(), vec()]);
  const tri = new THREE.Line(triGeo, new THREE.LineBasicMaterial({ color: 0xffd27a })); fx.add(tri);
  const imu = new THREE.Group(); imu.position.set(-0.004, -0.006, cz); fx.add(imu);
  const arrows = [[vec(1, 0, 0), 0xff5a5a], [vec(0, 1, 0), 0x4fd18b], [vec(0, 0, 1), 0x3d8bff]].map(([d, col]) => { const a = new THREE.ArrowHelper(d, vec(), 0.035, col, 0.008, 0.005); imu.add(a); return a; });
  const pnl = livePanel(760, 300, 0.20); pnl.obj.position.set(0.30, 0.08, 0.06); fx.add(pnl.obj);
  const rs = { iter: 0, best: -1, bestN: null, bestP: null, acc: 0, pick: [0, 1, 2] };
  const ransacStep = () => {
    let a, b, d;
    do { a = Math.floor(rand() * N); b = Math.floor(rand() * N); d = Math.floor(rand() * N); } while (a === b || b === d || a === d);
    rs.pick = [a, b, d];
    const n = new THREE.Vector3().crossVectors(pts[b].clone().sub(pts[a]), pts[d].clone().sub(pts[a]));
    if (n.lengthSq() < 1e-10) return;
    n.normalize(); if (n.y < 0) n.negate();
    let cnt = 0; for (const p of pts) if (Math.abs(p.clone().sub(pts[a]).dot(n)) < 0.005) cnt++;
    rs.iter++;
    if (cnt > rs.best) { rs.best = cnt; rs.bestN = n; rs.bestP = pts[a].clone(); }
  };
  const recolor = () => {
    for (let i = 0; i < N; i++) {
      const inl = rs.bestN && Math.abs(pts[i].clone().sub(rs.bestP).dot(rs.bestN)) < 0.005;
      const col = new THREE.Color(rs.bestN ? (inl ? 0x4fd18b : 0xff5a5a) : 0x9fb3c8);
      cols[i * 3] = col.r; cols[i * 3 + 1] = col.g; cols[i * 3 + 2] = col.b;
    }
    pg.attributes.color.needsUpdate = true;
    if (rs.bestN) {
      planeMesh.visible = true;
      const ctr = vec(0.34, 0, 0.06); ctr.y = rs.bestP.y - ((ctr.x - rs.bestP.x) * rs.bestN.x + (ctr.z - rs.bestP.z) * rs.bestN.z) / rs.bestN.y;
      planeMesh.position.copy(ctr); planeMesh.quaternion.setFromUnitVectors(vec(0, 0, 1), rs.bestN);
    } else planeMesh.visible = false;
    rs.pick.forEach((k, i) => picks[i].position.copy(pts[k]));
    const tp = triGeo.attributes.position; [0, 1, 2, 0].forEach((k, i) => tp.setXYZ(i, pts[rs.pick[k]].x, pts[rs.pick[k]].y, pts[rs.pick[k]].z)); tp.needsUpdate = true;
    pnl.draw((ctx, W, H) => {
      panelBg(ctx, W, H, 'roadd · RANSAC ground plane', 'own fit on the depth map\'s road region, every frame');
      txt(ctx, `iteration ${rs.iter} · inliers ${Math.max(0, rs.best)} of ${N}`, 22, 120, { size: 26, color: '#eef4fa', weight: 600 });
      const pitch = rs.bestN ? Math.atan2(rs.bestN.x, rs.bestN.y) / DEG : 0;
      txt(ctx, `plane pitch ${pitch.toFixed(2)}° · green inliers, red the car and clutter`, 22, 165, { size: 22 });
      txt(ctx, 'lane points = camera ray ∩ fitted plane; fallback: static plane + IMU pitch', 22, 205, { size: 20, color: '#8fa3b6' });
      txt(ctx, 'IMU 400 Hz · depth 1.0/1.5–35 m · 30 Hz', 22, 245, { size: 20, color: '#8fa3b6' });
    });
  };
  recolor();

  c.assembly = [
    { title: 'Sensor board', parts: ['board'], text: 'Two image sensors on a rigid board, 120 mm apart, with the IMU between them.' },
    { title: 'Body', parts: ['body'], text: 'The sealed aluminium body; USB-C with screw locks at the back.' },
    { title: 'Lenses and front glass', parts: ['lensL', 'lensR', 'front'], text: '4 mm lenses (narrower field, more pixels on the road ahead) behind the polarised front window.' },
    { title: 'Bracket', parts: ['plate', 'arm', 'clamp'], text: 'Quick-release plate on the tripod thread, a rigid arm, and a lined clamp on the mirror stalk.' },
    { title: 'Cable', parts: ['cable'], text: 'USB 3 along the headliner and A-pillar to the Jetson.' },
  ];
  const dz30 = 30 * 30 * R.D_DISP / (R.F_PX * R.B_ST);
  c.facts = [
    ['Lens', '4 mm: 80° × 52° (store page) vs 72° × 44° (datasheet), CONFLICT; f ≈ 1,144 px at 1080p from 80°'],
    ['Stereo', `baseline ${(R.B_ST * 1000).toFixed(0)} mm; depth 1.0/1.5–35 m; rolling shutter`],
    ['Depth error', `${dz30.toFixed(2)} m at 30 m for 0.25 px disparity (ASSUMED) → 0.047° at the eye`],
    ['IMU', '400 Hz; gyro gives egod a low-latency yaw rate'],
    ['Interface', 'USB 3; ZED SDK 5.5.1 supports JetPack 6.2.x (installer needs an exact L4T match)'],
    ['Mount', `high on the windshield centreline, clamped to the mirror stalk; camera-to-eye ${(ROAD_CAM_BASELINE * 100).toFixed(0)} cm in this layout (plan ASSUMED 45 cm; keep within ≈ 0.5 m)`],
    ['Ground plane', 'own RANSAC fit per frame (the SDK plane API needs tracking at ≈ 44% GPU)'],
    ['Cost', cost('Stereolabs')],
  ];
  c.desc = 'The road camera and the HUD\'s main sensor. Its left lens is the origin of every coordinate in the plan. roadd reads its stereo pair for depth, fits the road plane each frame, lifts the lane and object detections onto it, and streams its IMU to egod.';
  c.working = 'Both lens fields of view, a road-patch point cloud with a RANSAC plane fit choosing inliers over a car and clutter, and the IMU axes pulsing.';
  c.setWorking = (on) => { fx.visible = on; st.userData.set(on ? 1 : 0); };
  c.update = (t, dt, s) => {
    if (!s || !s.working) return;
    rs.acc += dt;
    if (rs.acc > 0.35) { rs.acc = 0; if (rs.iter >= 24) { rs.iter = 0; rs.best = -1; rs.bestN = null; } ransacStep(); recolor(); }
    const k = 1 + 0.12 * Math.sin(t * 25);
    arrows.forEach((a) => a.scale.setScalar(k));
  };
  return c;
}

// ---- Luxonis OAK-D Pro (driver camera) ----------------------------------------------------
export function buildOakdPro() {
  const c = makeComponent(THREE, {
    id: 'oakdPro', name: 'Luxonis OAK-D Pro (driver camera)', category: 'sensor',
    mount: 'centre (RGB) camera optical centre; X along the optical axis toward the driver', size: [0.05, 0.08, 0.10],
  });
  const BX = 0.0221, BY = 0.0295, BZ = 0.097, cx = 0.006 - BX / 2;
  const body = new THREE.Group();
  put(body, rbox(BX, BY, BZ, 0.004, M.aluDark, 3), cx, 0, 0);
  const fins = [];
  for (let i = 0; i < 16; i++) fins.push([cx - BX / 2 - 0.0012, 0, -0.04 + i * 0.0053]);
  body.add(instanced(new THREE.BoxGeometry(0.0024, BY - 0.006, 0.0016), M.aluDark, fins));
  put(body, cyl(0.0035, 0.0035, 0.0012, MX.brass, 20), cx, -BY / 2 - 0.0003, 0);
  const usb = put(body, new THREE.Group(), cx, 0, BZ / 2 + 0.0002, 0, -Math.PI / 2, 0);
  put(usb, Port.usbC(), 0, 0, 0, Math.PI / 2, 0, 0);
  put(body, decal('OAK-D Pro', 0.026, '+y', { color: '#c7ccd2', font: '600 48px ' + FONT }), cx, BY / 2 + 0.0002, 0);
  addPart(c, 'body', 'Aluminium body with heat-sink fins', body, vec(-0.05, 0, 0), 'Passively cooled; the RVC2 vision processor inside runs the face networks.');
  const brd = new THREE.Group();
  put(brd, box(0.0015, 0.024, 0.09, M.pcbBlack), -0.004, 0, 0);
  put(brd, chip(0.012, 0.012, 0.0015, 'RVC2', 0.009), -0.0058, 0, 0.022).rotation.z = Math.PI / 2;
  put(brd, chip(0.007, 0.007, 0.0012, 'BNO086', 0.0055), -0.0058, -0.006, -0.022).rotation.z = Math.PI / 2;
  addPart(c, 'board', 'Board: RVC2 vision processor, BNO086 IMU', brd, vec(0, 0.06, 0), 'On-device stereo depth and neural inference: head tracking costs the Jetson nothing.');
  const front = new THREE.Group();
  put(front, rbox(0.0016, BY - 0.004, BZ - 0.004, 0.003, MX.darkGlass, 3), 0.0055, 0, 0);
  addPart(c, 'front', 'Front window', front, vec(0.04, 0, 0), '');
  const optics = new THREE.Group();
  for (const z of [-0.0375, 0.0375]) put(optics, lens(0.0042, 0.005), 0.0064, 0, z);
  put(optics, lens(0.0055, 0.006), 0.0064, 0, 0);
  const dot = put(optics, new THREE.Group(), 0.0064, 0.0068, 0.0125);
  put(dot, cylX(0.0028, 0.003, M.aluAnodBlack, 20), -0.0015, 0, 0);
  const dotLens = put(dot, cylX(0.002, 0.0005, M.led(0xff3070, 0), 20), 0.0002, 0, 0);
  const flood = put(optics, new THREE.Group(), 0.0064, 0.0068, -0.0125);
  put(flood, box(0.003, 0.0045, 0.0045, M.aluAnodBlack), -0.0015, 0, 0);
  const floodLed = put(flood, box(0.0004, 0.0032, 0.0032, M.led(0xff3070, 0)), 0.0002, 0, 0);
  for (const [t, z] of [['L', -0.0375], ['IR', -0.0125], ['RGB', 0], ['DOT', 0.0125], ['R', 0.0375]]) put(optics, decal(t, t.length * 0.0024, '+x', { color: '#8a929b', font: '500 40px ' + FONT }), 0.0066, -0.0105, z);
  addPart(c, 'optics', 'Global-shutter stereo pair, RGB camera, IR dot projector and flood', optics, vec(0.06, 0, 0), 'Stereo pair 75 mm apart; the infrared dot projector and flood illuminator make it work at night.');
  const mount = new THREE.Group();
  put(mount, rbox(0.055, 0.004, 0.042, 0.004, M.rubber), cx, -0.046, 0);
  put(mount, cyl(0.004, 0.005, 0.016, M.aluAnodBlack, 16), cx, -0.036, 0);
  put(mount, sphere(0.0065, M.steel, 20), cx, -0.026, 0);
  put(mount, cyl(0.0045, 0.0045, 0.008, M.aluAnodBlack, 16), cx, -0.0195, 0);
  put(mount, cyl(0.0055, 0.0055, 0.0025, M.rubber, 16), cx, -0.0165, 0);
  addPart(c, 'mount', 'Column-shroud mount with ball head', mount, vec(0, -0.05, 0), 'On the steering-column shroud, aimed at the driver\'s face; removable.');

  // working: face with IR dots and landmarks
  const fx = new THREE.Group(); fx.visible = false; c.group.add(fx);
  const head = new THREE.Group(); fx.add(head);
  const HR = vec(0.085, 0.112, 0.072), HC = vec(0.36, 0.015, 0);
  const skull = sphere(1, M.skin, 40); skull.scale.copy(HR); head.add(skull);
  const nose = new THREE.Mesh(new THREE.ConeGeometry(0.012, 0.03, 16), M.skin); nose.rotation.z = Math.PI / 2; nose.position.set(-HR.x - 0.008, -0.005, 0); head.add(nose);
  for (const s of [-1, 1]) { put(head, sphere(0.0075, mat('eyeW', () => M.color(0xf2f2ee, 0.3)), 16), -HR.x * 0.86, 0.026, s * 0.031); put(head, sphere(0.0042, M.flock, 12), -HR.x * 0.86 - 0.006, 0.026, s * 0.031); }
  put(head, rbox(0.006, 0.006, 0.03, 0.003, mat('lips', () => M.color(0x9a5a50, 0.5))), -HR.x * 0.86, -0.045, 0);
  put(head, cyl(0.04, 0.045, 0.08, M.skin, 24), 0.0, -0.13, 0);
  const lmMat = M.emissive(0x4fd18b, 1.3);
  const lms = [[-0.9, 0.03, 0.045], [-0.92, 0.03, 0.018], [-0.92, 0.03, -0.018], [-0.9, 0.03, -0.045], [-1.1, -0.005, 0], [-0.97, -0.02, 0.012], [-0.97, -0.02, -0.012], [-0.9, -0.045, 0.02], [-0.9, -0.045, -0.02], [-0.8, -0.085, 0], [-0.72, -0.06, 0.05], [-0.72, -0.06, -0.05], [-0.88, 0.05, 0.035], [-0.88, 0.05, -0.035]];
  const lmObjs = [];
  for (const [x, y, z] of lms) lmObjs.push(put(head, sphere(0.0022, lmMat, 8), x * HR.x, y, z));
  const mid = new THREE.Group(); mid.position.set(-HR.x * 0.95, 0.026, 0); head.add(mid);
  const ym = M.emissive(0xffd27a, 2);
  put(mid, box(0.0015, 0.02, 0.0015, ym)); put(mid, box(0.0015, 0.0015, 0.02, ym));
  const ND = 520, rdirs = [], dr = rng(23);
  for (let i = 0; i < ND; i++) { const a = dr() * Math.PI * 2, r = Math.sqrt(dr()) * Math.tan(20 * DEG); rdirs.push(vec(1, Math.sin(a) * r, Math.cos(a) * r).normalize()); }
  const dg = new THREE.BufferGeometry(); dg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(ND * 3), 3));
  const dots = new THREE.Points(dg, new THREE.PointsMaterial({ color: 0xff3a8a, size: 0.005, sizeAttenuation: true, transparent: true, opacity: 0.95, toneMapped: false }));
  const hitFlag = new Uint8Array(ND);
  fx.add(dots);
  const cone = new THREE.Mesh(new THREE.ConeGeometry(0.16, 0.36, 32, 1, true), new THREE.MeshBasicMaterial({ color: 0xff3070, transparent: true, opacity: 0.06, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
  cone.rotation.z = Math.PI / 2; cone.position.set(0.18 + 0.0064, 0.0068, -0.0125); fx.add(cone);
  const sightG = new THREE.BufferGeometry().setFromPoints([vec(), vec()]);
  const sight = new THREE.Line(sightG, new THREE.LineDashedMaterial({ color: 0xffd27a, dashSize: 0.01, gapSize: 0.006 })); fx.add(sight);
  const pnl = livePanel(820, 420, 0.2); pnl.obj.position.set(0.24, 0.20, -0.05); fx.add(pnl.obj);
  const proj = vec(0.0064, 0.0068, 0.0125);
  const inv = new THREE.Matrix4(), o = vec(), d = vec(), tmp = vec();
  const updateDots = () => {
    head.updateMatrixWorld(true); fx.updateMatrixWorld(true);
    const hm = new THREE.Matrix4().compose(head.position, head.quaternion, new THREE.Vector3(1, 1, 1));
    inv.copy(hm).invert();
    const pos = dg.attributes.position;
    for (let i = 0; i < ND; i++) {
      o.copy(proj).applyMatrix4(inv); d.copy(rdirs[i]).transformDirection(inv);
      // unit-sphere intersection in scaled space
      const os = vec(o.x / HR.x, o.y / HR.y, o.z / HR.z), ds = vec(d.x / HR.x, d.y / HR.y, d.z / HR.z);
      const a = ds.dot(ds), b = 2 * os.dot(ds), cc = os.dot(os) - 1, disc = b * b - 4 * a * cc;
      let p;
      if (disc > 0) { const tt = (-b - Math.sqrt(disc)) / (2 * a); p = tmp.copy(o).addScaledVector(d, tt).applyMatrix4(hm); hitFlag[i] = 1; }
      else { p = tmp.set(0, 0, 0); hitFlag[i] = 0; }
      pos.setXYZ(i, p.x, p.y, p.z);
    }
    pos.needsUpdate = true;
    const em = mid.getWorldPosition(vec()); fx.worldToLocal(em);
    const sp = sightG.attributes.position; sp.setXYZ(0, 0.0064, 0, 0); sp.setXYZ(1, em.x, em.y, em.z); sp.needsUpdate = true; sight.computeLineDistances();
    return em;
  };
  head.position.copy(HC);
  const em0 = updateDots();
  const prj = (p, cxp, cyp, f) => [cxp + f * p.z / p.x, cyp - f * p.y / p.x];
  const drawPanel = (em) => pnl.draw((ctx, W, H) => {
    panelBg(ctx, W, H, 'headtrackd · eyePose 30 Hz', 'face detection + landmarks run on the camera');
    // what the camera sees (IR), projected through the RGB camera centre
    const vx = 22, vy = 80, vw = 330, vh = 320, f = 520, cxp = vx + vw / 2, cyp = vy + vh / 2;
    ctx.fillStyle = '#050608'; ctx.fillRect(vx, vy, vw, vh);
    ctx.save(); ctx.beginPath(); ctx.rect(vx, vy, vw, vh); ctx.clip();
    const pos = dg.attributes.position;
    ctx.fillStyle = '#ff5aa0';
    for (let i = 0; i < ND; i++) { if (!hitFlag[i]) continue; const [x, y] = prj(vec(pos.getX(i), pos.getY(i), pos.getZ(i)), cxp, cyp, f); ctx.fillRect(x - 1.5, y - 1.5, 3, 3); }
    ctx.fillStyle = '#4fd18b';
    for (const o of lmObjs) { const w = o.getWorldPosition(vec()); fx.worldToLocal(w); const [x, y] = prj(w, cxp, cyp, f); ctx.beginPath(); ctx.arc(x, y, 4, 0, 7); ctx.fill(); }
    const [ex, ey] = prj(em, cxp, cyp, f);
    ctx.strokeStyle = '#ffd27a'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(ex - 14, ey); ctx.lineTo(ex + 14, ey); ctx.moveTo(ex, ey - 14); ctx.lineTo(ex, ey + 14); ctx.stroke();
    ctx.restore();
    txt(ctx, 'camera view (IR)', vx + 8, vy + vh - 16, { size: 18, color: '#8fa3b6' });
    const tx0 = vx + vw + 24;
    txt(ctx, 'eye midpoint, camera frame', tx0, 112, { size: 21, color: '#8fa3b6' });
    txt(ctx, `${(em.x * 1000).toFixed(0)}, ${(em.y * 1000).toFixed(0)}, ${(em.z * 1000).toFixed(0)} mm`, tx0, 146, { size: 28, color: '#eef4fa', weight: 600 });
    txt(ctx, 'confidence 0.97', tx0, 196, { size: 22 });
    txt(ctx, 'latency 30–50 ms (estimate)', tx0, 232, { size: 22 });
    txt(ctx, 'pink: IR dots (depth)', tx0, 290, { size: 20, color: '#ff8abb' });
    txt(ctx, 'green: landmarks', tx0, 322, { size: 20, color: '#9fe6bd' });
    txt(ctx, 'yellow: eye midpoint', tx0, 354, { size: 20, color: '#ffd27a' });
  });
  drawPanel(em0);

  c.assembly = [
    { title: 'Board', parts: ['board'], text: 'Vision processor, IMU and the camera modules.' },
    { title: 'Body', parts: ['body'], text: 'Finned aluminium body; USB-C on the side.' },
    { title: 'Optics and window', parts: ['optics', 'front'], text: 'Stereo pair, RGB camera, IR projector and flood, behind the front window.' },
    { title: 'Mount', parts: ['mount'], text: 'Ball-head mount on the column shroud, aimed at the face; its pose is measured once.' },
  ];
  c.facts = [
    ['Cameras', 'global-shutter stereo pair (75 mm), RGB centre camera'],
    ['Illumination', 'IR flood + dot projector, for the head tracker at night'],
    ['Compute', 'on-device depth and NN inference (RVC2): face detection and landmarks; BNO086 IMU'],
    ['Output', 'eye midpoint in the car frame + confidence, 30 Hz (eyePose); nominal eye after 500 ms stale'],
    ['Why', `parallax for a 150 mm head shift: ${P_PAR(7.5)}° at 7.5 m, ${P_PAR(30)}° at 30 m`],
    ['Latency', '30–50 ms (parallax only)'],
    ['Note', 'MediaPipe is unsupported on Jetson; on-camera landmarks are primary, OpenSeeFace the CPU alternative'],
    ['Cost', cost('Luxonis')],
  ];
  c.desc = 'The driver camera. It finds the driver\'s face and eyes on its own processor and reports the eye midpoint, so hudd can re-project every graphic for where the eyes actually are; without it, a 150 mm head move shifts graphics by over a degree.';
  c.working = 'An infrared dot pattern and flood light a face; landmarks and the eye midpoint follow the head as it moves.';
  c.setWorking = (on) => { fx.visible = on; dotLens.material.emissiveIntensity = on ? 2 : 0; floodLed.material.emissiveIntensity = on ? 2 : 0; };
  let acc = 0;
  c.update = (t, dt, s) => {
    if (!s || !s.working) return;
    head.position.set(HC.x + 0.01 * Math.sin(t * 0.7), HC.y + 0.008 * Math.sin(t * 1.1), HC.z + 0.035 * Math.sin(t * 0.5));
    head.rotation.set(0.05 * Math.sin(t * 0.9), 0.18 * Math.sin(t * 0.5), 0);
    const em = updateDots();
    acc += dt; if (acc > 1 / 10) { acc = 0; drawPanel(em); }
  };
  return c;
}
const P_PAR = (dm) => { const r = Math.atan(0.150 / dm) / DEG; return r.toFixed(2); };

// ---- u-blox ZED-F9R (SparkFun breakout) -------------------------------------------------------
export function buildZedF9r() {
  const c = makeComponent(THREE, {
    id: 'zedF9r', name: 'u-blox ZED-F9R dead-reckoning GNSS (SparkFun breakout)', category: 'sensor',
    mount: 'centre of the board underside', size: [0.05, 0.01, 0.045],
  });
  const S = 0.0432;
  const pcb = new THREE.Group();
  put(pcb, box(S, 0.0016, S, M.pcbRed), 0, 0.0008, 0);
  const holes = [];
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) holes.push([sx * (S / 2 - 0.0028), 0.0008, sz * (S / 2 - 0.0028)]);
  pcb.add(instanced(new THREE.CylinderGeometry(0.0018, 0.0018, 0.00165, 16), M.gold, holes));
  const pth = [];
  for (let i = 0; i < 9; i++) pth.push([-0.012 + i * 0.00254, 0.0008, S / 2 - 0.0016], [-0.012 + i * 0.00254, 0.0008, -S / 2 + 0.0016]);
  pcb.add(instanced(new THREE.CylinderGeometry(0.0007, 0.0007, 0.00166, 10), M.gold, pth));
  put(pcb, smd(0.036, 0.03, 30, 61, 0.0016, [[0, 0, 0.024, 0.019]]), 0, 0, 0);
  put(pcb, cyl(0.0032, 0.0032, 0.0016, M.steel, 20), 0.014, 0.0024, -0.012);
  const ledP = put(pcb, led(0xff3030), 0.016, 0.0019, 0.012);
  const ledPPS = put(pcb, led(0x3d8bff), 0.016, 0.0019, 0.0155);
  put(pcb, decal('SparkFun · GPS-RTK Dead Reckoning · ZED-F9R', 0.034, '+y', { color: '#f4f4f4', font: '600 44px ' + FONT }), 0, 0.00165, -0.0185);
  addPart(c, 'pcb', 'Breakout board', pcb, vec(0, -0.02, 0), 'Red SparkFun breakout with headers, LEDs and a backup cell.');
  const mod = new THREE.Group();
  put(mod, box(0.022, 0.0024, 0.017, M.steel), 0, 0.0012, 0);
  put(mod, box(0.016, 0.0002, 0.011, MX.sticker), 0, 0.0025, 0);
  put(mod, decal('u-blox\nZED-F9R', 0.011, '+y', { color: '#1d2a44', font: '700 48px ' + FONT }), 0, 0.0027, 0);
  addPart(c, 'module', 'ZED-F9R module (GNSS + IMU, sensor fusion)', mod, vec(0, 0.03, 0), 'Multi-band GNSS with its own IMU: fused speed and heading, dead reckoning through outages.');
  mod.position.set(-0.002, 0.0016, 0);
  const conns = new THREE.Group();
  put(conns, Port.sma(), -S / 2 - 0.006, 0.0035, 0.0, 0, Math.PI, 0);
  put(conns, Port.usbC(), S / 2 + 0.0002, 0.0033, 0.006);
  put(conns, jst(4), 0.010, 0.0016, S / 2 + 0.0002, 0, -Math.PI / 2, 0);
  put(conns, jst(4), 0.010, 0.0016, -S / 2 - 0.0002, 0, Math.PI / 2, 0);
  addPart(c, 'connectors', 'SMA antenna jack, USB-C, Qwiic', conns, vec(0, 0.02, 0.02), 'SMA to the antenna; USB-C to the Jetson (serial to egod).');
  const cab = new THREE.Group();
  put(cab, cylX(0.0045, 0.01, MX.brass, 6), -S / 2 - 0.016, 0.0035, 0);
  put(cab, cable([[-S / 2 - 0.021, 0.0035, 0], [-0.05, 0.006, 0.005], [-0.065, 0.004, 0.02], [-0.08, 0.003, 0.03]], 0.0016, M.cableBlack), 0, 0, 0);
  addPart(c, 'cable', 'Antenna cable (to the dash antenna)', cab, vec(-0.03, 0, 0), '');

  const fx = new THREE.Group(); fx.visible = false; c.group.add(fx);
  const sats = [], sr = rng(31);
  for (let i = 0; i < 9; i++) {
    const g = new THREE.Group();
    put(g, box(0.008, 0.008, 0.008, M.gold));
    for (const s of [-1, 1]) put(g, box(0.0004, 0.006, 0.02, mat('solar', () => M.color(0x2a4aa0, 0.3, 0.4))), 0, 0, s * 0.015);
    const az = sr() * Math.PI * 2, el = (20 + sr() * 60) * DEG;
    g.userData = { az, el, r: 0.22 };
    fx.add(g); sats.push(g);
  }
  const lineG = new THREE.BufferGeometry(); lineG.setAttribute('position', new THREE.BufferAttribute(new Float32Array(sats.length * 6), 3));
  const lines = new THREE.LineSegments(lineG, new THREE.LineBasicMaterial({ color: 0x7fd3ff, transparent: true, opacity: 0.35 })); fx.add(lines);
  const pulses = sats.map(() => { const p = sphere(0.0022, M.emissive(0x7fd3ff, 2), 8); fx.add(p); return p; });
  const pnl = livePanel(720, 250, 0.16); pnl.obj.position.set(0, 0.10, -0.12); fx.add(pnl.obj);
  const ant = vec(-0.08, 0.004, 0.03);
  c.assembly = [
    { title: 'Breakout board', parts: ['pcb'], text: '' },
    { title: 'Module', parts: ['module'], text: 'The ZED-F9R: GNSS receiver and IMU with on-module fusion.' },
    { title: 'Connectors and antenna cable', parts: ['connectors', 'cable'], text: 'SMA to the dash antenna; USB-C to the Jetson.' },
  ];
  c.facts = [
    ['Output', 'fused speed, heading and position at ≤ 30 Hz'],
    ['Accuracy', 'velocity 0.05 m/s; heading 0.2°; dead reckoning ≈ 2% of distance'],
    ['Role', 'unbiased speed reference for age compensation; heading and time for the sun-watch rule'],
    ['Latency', 'unspecified by u-blox (≈ 12 ms reported by one user): measured with the LED test'],
    ['Fallback', 'NEO-M9N ($71, 25 Hz, no dead reckoning)'],
    ['Speed shown', 'within 1 m/s of a reference GNSS trace while moving; dash without a fix'],
    ['Cost', cost('u-blox')],
  ];
  c.desc = 'Satellite positioning with its own inertial unit. egod uses its Doppler speed as the unbiased reference, its heading and clock for the sun-watch rule, and its dead reckoning to ride through tunnels and tree cover. It is also the speed shown in the HUD\'s speed block.';
  c.working = 'Satellites in view send signals to the antenna; the board reports a fix, satellite count, speed and heading.';
  c.setWorking = (on) => { fx.visible = on; ledP.userData.set(on ? 1 : 0); if (!on) ledPPS.userData.set(0); };
  let acc = 1;
  c.update = (t, dt, s) => {
    if (!s || !s.working) return;
    const pos = lineG.attributes.position;
    sats.forEach((g, i) => {
      const { az, el, r } = g.userData; const a = az + t * 0.03;
      g.position.set(r * Math.cos(el) * Math.cos(a), 0.05 + r * Math.sin(el), r * Math.cos(el) * Math.sin(a)); g.rotation.y = a;
      pos.setXYZ(i * 2, g.position.x, g.position.y, g.position.z); pos.setXYZ(i * 2 + 1, ant.x, ant.y, ant.z);
      const u = (t * 0.8 + i * 0.13) % 1; pulses[i].position.copy(g.position).lerp(ant, u);
    });
    pos.needsUpdate = true;
    ledPPS.userData.set((t % 1) < 0.1 ? 1 : 0.05);
    acc += dt;
    if (acc > 0.2) {
      acc = 0;
      const v = s.live && typeof s.live.speed === 'number' ? s.live.speed : 27 + 2 * Math.sin(t * 0.3);
      pnl.draw((ctx, W, H) => {
        panelBg(ctx, W, H, 'ZED-F9R · fix 3D + DR', 'feeds egod over USB serial');
        txt(ctx, `${sats.length + 5} satellites · speed ${v.toFixed(2)} m/s (±0.05) · ${(v * 2.23694).toFixed(0)} mph`, 22, 120, { size: 24, color: '#eef4fa', weight: 600 });
        txt(ctx, `heading ${(312 + 3 * Math.sin(t * 0.2)).toFixed(1)}° (±0.2) · fused ≤ 30 Hz · PPS 1 Hz`, 22, 165, { size: 21 });
        txt(ctx, 'no fix → speed shows a dash, prediction off', 22, 205, { size: 20, color: '#8fa3b6' });
      });
    }
  };
  return c;
}

// ---- GNSS antenna ------------------------------------------------------------------------------
export function buildGnssAntenna() {
  const c = makeComponent(THREE, {
    id: 'gnssAntenna', name: 'Active multi-band GNSS antenna', category: 'sensor',
    mount: 'centre of the magnetic base underside (sits on the dash top near the glass)', size: [0.07, 0.02, 0.07],
  });
  const R0 = 0.033;
  const base = new THREE.Group();
  put(base, cyl(R0, R0 + 0.001, 0.005, M.plasticBlack, 48), 0, 0.0025, 0);
  put(base, cyl(R0 - 0.004, R0 - 0.004, 0.0008, M.rubber, 48), 0, 0.0002, 0);
  put(base, cyl(0.018, 0.018, 0.003, M.steel, 32), 0, 0.0035, 0);
  addPart(c, 'base', 'Magnetic base and ground plane', base, vec(0, -0.03, 0), 'A non-scratch pad goes under it on the dash; nothing is bonded.');
  const lna = new THREE.Group();
  put(lna, cyl(0.028, 0.028, 0.0012, M.pcbGreen, 40), 0, 0.0056, 0);
  put(lna, chip(0.004, 0.004, 0.0009, 'LNA', 0.003), 0.012, 0.0062, 0);
  put(lna, smd(0.03, 0.03, 12, 81, 0.0062, [[0, 0, 0.026, 0.026]]), 0, 0, 0);
  addPart(c, 'lna', 'Low-noise amplifier board', lna, vec(0, 0.02, 0), 'Amplifies the faint satellite signal before the cable.');
  const el = new THREE.Group();
  put(el, box(0.025, 0.004, 0.025, M.ceramic), 0, 0.0083, 0);
  put(el, box(0.019, 0.0003, 0.019, M.steel), 0, 0.0105, 0);
  put(el, cyl(0.0008, 0.0008, 0.0006, M.solder, 8), 0.004, 0.011, 0.004);
  addPart(c, 'element', 'Ceramic patch element (L1/L2)', el, vec(0, 0.04, 0), 'The receiving element.');
  const dome = new THREE.Group();
  const dm = new THREE.Mesh(new THREE.SphereGeometry(R0, 48, 16, 0, Math.PI * 2, 0, Math.PI / 2), M.plasticBlack);
  dm.scale.y = 0.38; dm.position.y = 0.005; dm.castShadow = true; dome.add(dm);
  put(dome, decal('GNSS L1/L2', 0.02, '+y', { color: '#8a929b', font: '600 48px ' + FONT }), 0, 0.0177, 0);
  addPart(c, 'radome', 'Radome', dome, vec(0, 0.07, 0), '');
  const cab = new THREE.Group();
  put(cab, cable([[-R0 + 0.002, 0.003, 0], [-0.05, 0.003, 0.0], [-0.07, 0.002, 0.02], [-0.09, 0.002, 0.045], [-0.11, 0.002, 0.05]], 0.0015, M.cableBlack), 0, 0, 0);
  put(cab, cylX(0.004, 0.009, MX.brass, 6), -0.115, 0.002, 0.05);
  put(cab, cylX(0.0025, 0.008, MX.brass, 16), -0.123, 0.002, 0.05);
  addPart(c, 'cable', 'RG-174 lead with SMA plug', cab, vec(-0.03, 0, 0), 'To the ZED-F9R board by the Jetson.');
  const fx = new THREE.Group(); fx.visible = false; c.group.add(fx);
  const rings = [0, 1, 2, 3].map(() => { const r = new THREE.Mesh(new THREE.TorusGeometry(1, 0.012, 6, 64), new THREE.MeshBasicMaterial({ color: 0x7fd3ff, transparent: true, opacity: 0.5, depthWrite: false, toneMapped: false })); r.rotation.x = Math.PI / 2; fx.add(r); return r; });
  c.assembly = [
    { title: 'Base', parts: ['base'], text: '' },
    { title: 'Amplifier and element', parts: ['lna', 'element'], text: '' },
    { title: 'Radome and lead', parts: ['radome', 'cable'], text: 'On the dash top near the glass, with a clear view of the sky.' },
  ];
  c.facts = [
    ['Bands', 'multi-band L1/L2, as the ZED-F9R needs'],
    ['Placement', 'dash top near the glass, passenger side; open-sky course preferred'],
    ['Mount', 'magnetic base on a pad: nothing bonded'],
    ['Cost', cost('u-blox')],
  ];
  c.desc = 'The antenna for the GNSS board. It sits on the dash under the windshield, where it sees most of the sky, and feeds the ZED-F9R through a thin coaxial lead.';
  c.working = 'Satellite signals arrive from above and converge on the patch element.';
  c.setWorking = (on) => { fx.visible = on; };
  c.update = (t, dt, s) => {
    if (!s || !s.working) return;
    rings.forEach((r, i) => { const u = (t * 0.5 + i / 4) % 1; const rad = 0.12 * (1 - u) + 0.02; r.scale.set(rad, rad, rad); r.position.y = 0.02 + 0.12 * (1 - u); r.material.opacity = 0.55 * Math.sin(u * Math.PI); });
  };
  return c;
}
