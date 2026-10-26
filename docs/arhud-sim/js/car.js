// The ego car: a mid-size left-hand-drive sedan with a full interior, built in the simulation car frame of geom.js
// (X forward, Y up, Z right, metres, origin on the road directly below the driver's nominal eye). The windshield's
// inner surface is exactly the plane geom.js traces against, and the dash top under the HUD housing sits at 0.795 m,
// below geom.HOUSING.floor.
import * as THREE from 'three';
import * as G from './geom.js';
import { M } from './mats.js';
import { DEG, rbox, canvasTexture, clamp } from './util.js';

const CZ = G.CAR_CENTER_Z;           // car centreline
const HW = 0.905;                    // half-width of the lower body
const DASH_Y = 0.795;                // dash shelf height (under the HUD housing)
const FLOOR_Y = 0.135;               // cabin floor (carpet) height
const WHEEL_R = 0.33, WHEEL_W = 0.225, FRONT_AXLE = 1.55, REAR_AXLE = -1.30, TRACK = 0.80;
const WHEEL_C = new THREE.Vector3(0.36, 0.90, 0);               // steering wheel centre
const COL_ANG = 23 * DEG;                                        // steering column below horizontal
const COL_DIR = new THREE.Vector3(Math.cos(COL_ANG), -Math.sin(COL_ANG), 0);      // toward the dash
const COL_UP = new THREE.Vector3(Math.sin(COL_ANG), Math.cos(COL_ANG), 0);        // in the wheel plane, up
const STEER_RATIO = 15;

const V3 = (x, y, z) => new THREE.Vector3(x, y, z);
const _m = new THREE.Matrix4();

function mesh(geo, mat, cast = true, receive = true) { const m = new THREE.Mesh(geo, mat); m.castShadow = cast; m.receiveShadow = receive; return m; }

// Grid surface from fn(u, v) -> [x, y, z], u, v in [0, 1].
function gridSurface(nu, nv, fn) {
  const pos = [], uv = [], idx = [];
  for (let j = 0; j <= nv; j++) for (let i = 0; i <= nu; i++) {
    const p = fn(i / nu, j / nv); pos.push(p[0], p[1], p[2]); uv.push(i / nu, j / nv);
  }
  for (let j = 0; j < nv; j++) for (let i = 0; i < nu; i++) {
    const a = j * (nu + 1) + i, b = a + 1, c = a + nu + 1, d = c + 1;
    idx.push(a, c, b, b, c, d);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx); g.computeVertexNormals();
  return g;
}

// Extrude an (x, y) outline across Z from z0 to z1.
function extrudeXY(points, z0, z1, mat, bevel = 0) {
  const shape = new THREE.Shape(points.map(([x, y]) => new THREE.Vector2(x, y)));
  const depth = Math.max(0.001, (z1 - z0) - 2 * bevel);
  const g = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: bevel > 0, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 2, curveSegments: 12 });
  g.translate(0, 0, z0 + bevel);
  return mesh(g, mat);
}

// Capsule between two points.
function limb(a, b, r, mat) {
  const d = b.clone().sub(a), len = d.length();
  const m = mesh(new THREE.CapsuleGeometry(r, Math.max(0.001, len - 2 * r) + 2 * r * 0.2, 4, 12), mat);
  m.position.copy(a).addScaledVector(d, 0.5);
  m.quaternion.setFromUnitVectors(V3(0, 1, 0), d.normalize());
  return m;
}

// Thin flat ShapeGeometry in (x, y) mapped onto a surface z = zf(x, y).
function shapeOnSide(points, zf, mat, holes = []) {
  const shape = new THREE.Shape(points.map(([x, y]) => new THREE.Vector2(x, y)));
  for (const h of holes) shape.holes.push(new THREE.Path(h.map(([x, y]) => new THREE.Vector2(x, y))));
  const g = new THREE.ShapeGeometry(shape, 16);
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) p.setZ(i, zf(p.getX(i), p.getY(i)));
  g.computeVertexNormals();
  return mesh(g, mat);
}

function clusterTexture() {
  return canvasTexture(768, 256, (ctx, W, H) => {
    ctx.fillStyle = '#05070a'; ctx.fillRect(0, 0, W, H);
    const dial = (cx, label, val, max, unit) => {
      ctx.lineWidth = 10; ctx.strokeStyle = '#1b2430'; ctx.beginPath(); ctx.arc(cx, 140, 95, 0.8 * Math.PI, 2.2 * Math.PI); ctx.stroke();
      ctx.strokeStyle = '#4fb3ff'; ctx.beginPath(); ctx.arc(cx, 140, 95, 0.8 * Math.PI, (0.8 + 1.4 * val / max) * Math.PI); ctx.stroke();
      ctx.fillStyle = '#e8eef5'; ctx.textAlign = 'center'; ctx.font = '600 54px "Helvetica Neue", Helvetica, Arial, sans-serif'; ctx.fillText(label, cx, 152);
      ctx.fillStyle = '#7d8b9a'; ctx.font = '400 20px "Helvetica Neue", Helvetica, Arial, sans-serif'; ctx.fillText(unit, cx, 184);
    };
    dial(150, '56', 56, 140, 'mph'); dial(618, '2.1', 2.1, 8, 'rpm x1000');
    ctx.fillStyle = '#9fd9a8'; ctx.font = '500 22px "Helvetica Neue", Helvetica, Arial, sans-serif'; ctx.textAlign = 'center';
    ctx.fillText('D', 384, 110); ctx.fillStyle = '#7d8b9a'; ctx.fillText('72°F  ·  214 mi', 384, 150);
  });
}

function screenTexture() {
  return canvasTexture(512, 300, (ctx, W, H) => {
    ctx.fillStyle = '#e9e6dc'; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 14; ctx.beginPath(); ctx.moveTo(-10, 240); ctx.bezierCurveTo(160, 200, 260, 120, 530, 60); ctx.stroke();
    ctx.strokeStyle = '#d2cdbd'; ctx.lineWidth = 6; for (let i = 0; i < 6; i++) { ctx.beginPath(); ctx.moveTo(i * 100, 0); ctx.lineTo(i * 90 + 40, 300); ctx.stroke(); }
    ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 10; ctx.beginPath(); ctx.moveTo(250, 290); ctx.bezierCurveTo(250, 220, 300, 160, 420, 110); ctx.stroke();
    ctx.fillStyle = '#1d2733'; ctx.fillRect(0, 0, W, 40); ctx.fillStyle = '#e8eef5'; ctx.font = '500 20px "Helvetica Neue", Helvetica, Arial, sans-serif'; ctx.fillText('Navigation', 16, 27);
  });
}

export function buildEgoCar() {
  const group = new THREE.Group(); group.name = 'egoCar';
  const body = new THREE.Group(); body.name = 'body'; group.add(body);
  const interior = new THREE.Group(); interior.name = 'interior'; group.add(interior);
  const leftSide = new THREE.Group(); leftSide.name = 'leftSide'; body.add(leftSide);    // hidden in the driver-side cutaway
  const rightSide = new THREE.Group(); rightSide.name = 'rightSide'; body.add(rightSide);  // hidden in the passenger-side cutaway

  const paint = new THREE.MeshPhysicalMaterial({ color: 0x3a536b, metalness: 0.6, roughness: 0.32, clearcoat: 1, clearcoatRoughness: 0.06, side: THREE.DoubleSide });
  const black = new THREE.MeshStandardMaterial({ color: 0x0d0e10, roughness: 0.55, side: THREE.DoubleSide });
  const chrome = new THREE.MeshStandardMaterial({ color: 0xd8dbdf, metalness: 1, roughness: 0.18 });
  const sideGlass = new THREE.MeshPhysicalMaterial({ color: 0x1e2a33, metalness: 0.1, roughness: 0.05, transparent: true, opacity: 0.45, side: THREE.DoubleSide, depthWrite: false });
  const wsGlass = M.windshield.clone();
  wsGlass.color.set(0x0c100f); wsGlass.opacity = 0.14; wsGlass.roughness = 0.02; wsGlass.metalness = 0.1;   // mostly specular, so street lights do not tint the view
  const trim = new THREE.MeshStandardMaterial({ color: 0x24262a, roughness: 0.75, side: THREE.DoubleSide });
  const trimLight = new THREE.MeshStandardMaterial({ color: 0x6d6a64, roughness: 0.9, side: THREE.DoubleSide });
  const headliner = new THREE.MeshStandardMaterial({ color: 0xb9b4aa, roughness: 0.95, side: THREE.DoubleSide });
  const carpet = new THREE.MeshStandardMaterial({ color: 0x1c1d20, roughness: 1 });
  const dashMat = M.dash;
  const bodyMats = [paint, sideGlass, black, chrome];
  const xrayState = new Map();

  // ---------------------------------------------------------------------------------------------- lower body
  const sideOutline = (() => {
    const s = new THREE.Shape();
    s.moveTo(-2.29, 0.36); s.lineTo(-2.26, 0.24); s.lineTo(REAR_AXLE - 0.375, 0.22);
    s.absarc(REAR_AXLE, 0.33, 0.39, Math.PI + 0.274, -0.274, true);
    s.lineTo(FRONT_AXLE - 0.375, 0.22);
    s.absarc(FRONT_AXLE, 0.33, 0.39, Math.PI + 0.274, -0.274, true);
    s.lineTo(2.29, 0.24); s.lineTo(2.31, 0.34); s.lineTo(2.31, 0.55); s.lineTo(2.30, 0.70); s.lineTo(2.27, 0.765);
    s.lineTo(1.90, 0.785); s.lineTo(1.50, 0.80); s.lineTo(1.40, 0.81); s.lineTo(1.25, 0.92); s.lineTo(1.0, 0.94);
    s.lineTo(-0.40, 0.97); s.lineTo(-1.30, 0.995); s.lineTo(-1.75, 1.0); s.lineTo(-2.20, 0.985); s.lineTo(-2.29, 0.93);
    s.lineTo(-2.30, 0.70); s.lineTo(-2.30, 0.50);
    return s;
  })();
  for (const side of [-1, 1]) {
    const g = new THREE.ExtrudeGeometry(sideOutline, { depth: 0.03, bevelEnabled: true, bevelThickness: 0.012, bevelSize: 0.012, bevelSegments: 2, curveSegments: 20 });
    g.translate(0, 0, -0.015);
    const m = mesh(g, paint); m.position.z = CZ + side * (HW - 0.02);
    const grp = side < 0 ? leftSide : rightSide; grp.add(m);
    // door seams and handles
    for (const [x0, y0, x1, y1] of [[1.16, 0.26, 1.16, 0.94], [-0.42, 0.22, -0.42, 0.97], [-1.06, 0.6, -1.06, 0.99]]) {
      const len = Math.hypot(x1 - x0, y1 - y0);
      const seam = mesh(new THREE.BoxGeometry(0.006, len, 0.004), black, false); seam.position.set((x0 + x1) / 2, (y0 + y1) / 2, CZ + side * (HW + 0.0));
      grp.add(seam);
    }
    for (const x of [0.62, -0.88]) { const h = rbox(0.16, 0.03, 0.025, 0.01, chrome); h.position.set(x, 0.86, CZ + side * (HW + 0.005)); grp.add(h); }
    // side mirror
    const mir = new THREE.Group();
    const housing = rbox(0.20, 0.12, 0.09, 0.03, paint); mir.add(housing);
    const face = mesh(new THREE.PlaneGeometry(0.17, 0.09), M.mirror); face.rotation.y = -Math.PI / 2; face.position.x = -0.046; mir.add(face);
    const arm = rbox(0.07, 0.04, 0.08, 0.01, black); arm.position.set(0.02, -0.04, -side * 0.07); mir.add(arm);
    mir.position.set(1.12, 1.0, CZ + side * (HW + 0.09)); grp.add(mir);
  }

  // hood
  const hood = mesh(gridSurface(16, 20, (u, v) => {
    const x = 1.50 + 0.83 * u, w = 2 * v - 1;
    const y = 0.80 - 0.04 * u - 0.03 * Math.pow(u, 6) + 0.025 * (1 - w * w);
    return [x, y, CZ + w * 0.875];
  }), paint);
  body.add(hood);
  // cowl panel between the windshield base and the hood
  const cowl = mesh(gridSurface(2, 8, (u, v) => [G.WS_BOTTOM_X - 0.01 + 0.10 * u, 0.80 + 0.004 * u, CZ + (2 * v - 1) * 0.88]), black);
  body.add(cowl);
  // front fascia
  const fasciaX = (u, v) => { const w = 2 * u - 1; return 2.30 + (0.16 - 0.12 * v * v) * (1 - Math.pow(Math.abs(w), 4)); };
  const fascia = mesh(gridSurface(24, 10, (u, v) => [fasciaX(u, v), 0.30 + 0.46 * v, CZ + (2 * u - 1) * 0.90]), paint);
  body.add(fascia);
  const grille = rbox(0.06, 0.13, 0.62, 0.03, black); grille.position.set(fasciaX(0.5, 0.42) - 0.02, 0.495, CZ); body.add(grille);
  const intake = rbox(0.06, 0.07, 0.95, 0.03, black); intake.position.set(fasciaX(0.5, 0.1) - 0.02, 0.36, CZ); body.add(intake);
  const plateF = rbox(0.01, 0.12, 0.30, 0.005, M.plasticWhite); plateF.position.set(fasciaX(0.5, 0.2) + 0.005, 0.40, CZ); body.add(plateF);
  // rear: trunk lid and fascia
  const trunk = mesh(gridSurface(10, 20, (u, v) => {
    const x = -1.72 - 0.58 * u, w = 2 * v - 1;
    return [x, 1.0 - 0.015 * u - 0.02 * Math.pow(u, 5) + 0.02 * (1 - w * w), CZ + w * 0.86];
  }), paint);
  body.add(trunk);
  const rearX = (u, v) => { const w = 2 * u - 1; return -2.29 - 0.09 * Math.sin(Math.PI * (0.15 + 0.75 * v)) * (1 - Math.pow(Math.abs(w), 4)); };
  const rear = mesh(gridSurface(24, 10, (u, v) => [rearX(u, v), 0.32 + 0.645 * v, CZ + (2 * u - 1) * 0.90]), paint);
  body.add(rear);
  const plateR = rbox(0.01, 0.15, 0.30, 0.005, M.plasticWhite); plateR.position.set(rearX(0.5, 0.5) - 0.005, 0.62, CZ); body.add(plateR);
  const diffuser = rbox(0.12, 0.08, 1.4, 0.02, black); diffuser.position.set(-2.25, 0.32, CZ); body.add(diffuser);

  // underbody and wheel-arch liners
  const under = rbox(4.5, 0.03, 1.72, 0.01, black); under.position.set(0.05, 0.17, CZ); body.add(under);
  for (const x of [FRONT_AXLE, REAR_AXLE]) for (const side of [-1, 1]) {
    const lg = new THREE.CylinderGeometry(0.385, 0.385, 0.26, 24, 1, true, Math.PI / 2, Math.PI);
    const liner = mesh(lg, black); liner.rotation.x = Math.PI / 2; liner.position.set(x, 0.33, CZ + side * (TRACK - 0.02));
    body.add(liner);
  }

  // lights
  const headLens = new THREE.MeshStandardMaterial({ color: 0xe8edf2, emissive: 0xfff3dd, emissiveIntensity: 0.15, roughness: 0.1, metalness: 0.2 });
  const tailLens = new THREE.MeshStandardMaterial({ color: 0x5a0b0d, emissive: 0xff1c1c, emissiveIntensity: 0.15, roughness: 0.2 });
  const headlights = [];
  for (const side of [-1, 1]) {
    const hl = new THREE.Group();
    const housingH = rbox(0.10, 0.09, 0.34, 0.03, black); hl.add(housingH);
    const lens = rbox(0.02, 0.07, 0.30, 0.02, headLens); lens.position.x = 0.045; hl.add(lens);
    const drl = rbox(0.015, 0.012, 0.30, 0.005, headLens); drl.position.set(0.05, -0.05, 0); hl.add(drl);
    hl.position.set(fasciaX(0.5 + side * 0.36, 0.83) - 0.03, 0.68, CZ + side * 0.66); hl.rotation.y = -side * 0.18;
    body.add(hl);
    const tl = rbox(0.06, 0.07, 0.36, 0.02, tailLens); tl.position.set(rearX(0.5 + side * 0.39, 0.9) + 0.01, 0.90, CZ + side * 0.70); tl.rotation.y = side * 0.15;
    body.add(tl);
    const spot = new THREE.SpotLight(0xf1f5ff, 0, 160, 0.42, 0.55, 2);   // LED white: a warm tint reads as olive on grey asphalt after tone mapping
    spot.position.set(2.32, 0.68, CZ + side * 0.62);
    spot.target.position.set(34, 0, CZ + side * 0.9);
    spot.castShadow = false;
    group.add(spot); group.add(spot.target);
    headlights.push(spot);
  }

  // wheels
  const wheels = [];
  const tire = new THREE.MeshStandardMaterial({ color: 0x141416, roughness: 0.9 });
  const rimMat = new THREE.MeshStandardMaterial({ color: 0xa9adb3, metalness: 0.9, roughness: 0.28 });
  const discMat = new THREE.MeshStandardMaterial({ color: 0x8c8f93, metalness: 0.8, roughness: 0.5 });
  const caliperMat = new THREE.MeshStandardMaterial({ color: 0xb8262c, roughness: 0.5 });
  for (const [x, front] of [[FRONT_AXLE, true], [REAR_AXLE, false]]) for (const side of [-1, 1]) {
    const pivot = new THREE.Group(); pivot.position.set(x, WHEEL_R, CZ + side * TRACK);
    const spin = new THREE.Group(); pivot.add(spin);
    const t = mesh(new THREE.CylinderGeometry(WHEEL_R, WHEEL_R, WHEEL_W, 32, 1, true), tire); t.rotation.x = Math.PI / 2; spin.add(t);
    for (const zz of [-1, 1]) { const wall = mesh(new THREE.RingGeometry(0.205, WHEEL_R - 0.01, 32), tire); wall.position.z = zz * (WHEEL_W / 2 - 0.004); wall.rotation.y = zz > 0 ? 0 : Math.PI; spin.add(wall); }
    for (const zz of [-1, 1]) { const sw = mesh(new THREE.TorusGeometry(WHEEL_R - 0.035, 0.035, 8, 32), tire); sw.position.z = zz * (WHEEL_W / 2 - 0.02); spin.add(sw); }
    const barrel = mesh(new THREE.CylinderGeometry(0.215, 0.215, WHEEL_W - 0.02, 28, 1, true), rimMat); barrel.rotation.x = Math.PI / 2; spin.add(barrel);
    const face = new THREE.Group(); face.position.z = side * (WHEEL_W / 2 - 0.03); spin.add(face);
    const hub = mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.03, 16), rimMat); hub.rotation.x = Math.PI / 2; face.add(hub);
    for (let i = 0; i < 5; i++) {
      const sp = rbox(0.045, 0.19, 0.025, 0.008, rimMat); sp.position.y = 0.11; const a = new THREE.Group(); a.rotation.z = i * 2 * Math.PI / 5; a.add(sp); face.add(a);
    }
    const disc = mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.02, 24), discMat); disc.rotation.x = Math.PI / 2; disc.position.z = side * 0.01; pivot.add(disc);
    const cal = rbox(0.08, 0.10, 0.05, 0.01, caliperMat); cal.position.set(front ? -0.12 : 0.12, 0.06, side * 0.03); pivot.add(cal);
    body.add(pivot);
    wheels.push({ pivot, spin, front });
  }

  // ---------------------------------------------------------------------------------------------- greenhouse
  // Windshield: flat laminate whose inner face is the traced plane (through G, normal GLASS_N).
  const WS_LS = (G.ROOF_Y - G.COWL_Y) / Math.sin(G.RAKE);
  const wsHalf = (a) => 0.765 - 0.115 * (a / WS_LS);
  const wsBase = V3(G.WS_BOTTOM_X, G.COWL_Y, CZ);
  const wsPoint = (a, b, n = 0) => wsBase.clone().addScaledVector(G.GLASS_UP, a).add(V3(0, 0, b)).addScaledVector(G.GLASS_N, n);
  const wsBasis = new THREE.Matrix4().makeBasis(G.GLASS_UP, G.GLASS_N, V3(0, 0, 1)); // local X up the glass, Y outward, Z right
  // build in glass-local coordinates (x = a along the glass, z = b lateral, y = thickness outward)
  const wsOutline = (inset = 0) => {
    const pts = []; const r = 0.06;
    const corner = (cx, cz, a0) => { for (let i = 0; i <= 6; i++) { const t = a0 + (i / 6) * Math.PI / 2; pts.push([cx + r * Math.cos(t), cz + r * Math.sin(t)]); } };
    const hb = wsHalf(0) - inset, ht = wsHalf(WS_LS) - inset;
    corner(inset + r, -hb + r, Math.PI); corner(WS_LS - inset - r, -ht + r, 1.5 * Math.PI);
    corner(WS_LS - inset - r, ht - r, 0); corner(inset + r, hb - r, 0.5 * Math.PI);
    return pts;
  };
  {
    const sh = new THREE.Shape(wsOutline().map(([a, b]) => new THREE.Vector2(a, b)));
    const g = new THREE.ExtrudeGeometry(sh, { depth: G.GLASS_T, bevelEnabled: false, curveSegments: 6 });
    // shape is in (a, b) = (x, y); extrusion along +Z. Map: shape x -> a (local X), shape y -> b (local Z), extrusion -> thickness (local Y)
    g.applyMatrix4(new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1));
    g.applyMatrix4(wsBasis); g.translate(wsBase.x, wsBase.y, wsBase.z);
    const ws = new THREE.Mesh(g, wsGlass); ws.renderOrder = 8; ws.name = 'windshield';
    body.add(ws);
    // black ceramic frit on the inner surface: outer outline minus the clear area, plus the mirror-mount patch
    const frit = new THREE.Shape(wsOutline().map(([a, b]) => new THREE.Vector2(a, b)));
    const clear = []; const hb = wsHalf(0), ht = wsHalf(WS_LS);
    const fb = 0.075, fs = 0.022, ft = 0.085, pw = 0.11, pd = 0.12;
    clear.push([fb, -hb + fs], [WS_LS - ft, -ht + fs], [WS_LS - ft, -pw], [WS_LS - pd, -pw * 0.7], [WS_LS - pd, pw * 0.7], [WS_LS - ft, pw], [WS_LS - ft, ht - fs], [fb, hb - fs]);
    frit.holes.push(new THREE.Path(clear.map(([a, b]) => new THREE.Vector2(a, b))));
    const fg = new THREE.ShapeGeometry(frit, 6);
    fg.applyMatrix4(new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1));
    fg.applyMatrix4(wsBasis); fg.translate(wsBase.x, wsBase.y, wsBase.z);
    fg.translate(-G.GLASS_N.x * 0.0008, -G.GLASS_N.y * 0.0008, 0);
    const fm = new THREE.Mesh(fg, new THREE.MeshStandardMaterial({ color: 0x050506, roughness: 0.4, side: THREE.DoubleSide }));
    body.add(fm);
  }

  // roof and headliner
  const roofY = (x) => (x >= -0.35 ? 1.43 - 0.042 * ((x + 0.35) / 0.645) ** 2 : 1.43 - 0.022 * ((x + 0.35) / 0.63) ** 2);
  const roofX0 = G.WS_TOP_X - 0.005, roofX1 = -0.98;
  const roofHalf = (x) => 0.655 - 0.015 * (roofX0 - x) / (roofX0 - roofX1);
  const roof = mesh(gridSurface(20, 16, (u, v) => {
    const x = roofX0 + (roofX1 - roofX0) * u, w = 2 * v - 1;
    return [x, roofY(x) - 0.028 * Math.pow(Math.abs(w), 3) + 0.004, CZ + w * roofHalf(x)];
  }), paint);
  body.add(roof);
  const liner = mesh(gridSurface(20, 16, (u, v) => {
    const x = roofX0 - 0.01 + (roofX1 + 0.04 - roofX0) * u, w = 2 * v - 1;
    return [x, roofY(x) - 0.04 - 0.028 * Math.pow(Math.abs(w), 3), CZ + w * (roofHalf(x) - 0.02)];
  }), headliner);
  interior.add(liner);
  // windshield header between the glass top and the roof
  const header = mesh(gridSurface(2, 12, (u, v) => {
    const w = 2 * v - 1; const p = wsPoint(WS_LS - 0.01, w * wsHalf(WS_LS), 0.004);
    return [p.x - 0.03 * u, G.ROOF_Y + 0.004 + 0.02 * u, p.z];
  }), paint);
  body.add(header);

  // side greenhouse plane: z as a function of height (tumblehome), per side
  const sideZ = (side) => (x, y) => CZ + side * (0.90 - (clamp(y, 0.9, 1.45) - 0.95) * (0.25 / 0.43));
  const xA = (y) => G.WS_BOTTOM_X - (y - G.COWL_Y) / Math.tan(G.RAKE);          // A-pillar line in side view
  const railY = (x) => roofY(x) - 0.03;
  for (const side of [-1, 1]) {
    const grp = side < 0 ? leftSide : rightSide;
    const zf = sideZ(side);
    const yTop = 1.375, xTop = xA(yTop) - 0.04;
    const xF = (y) => xA(y) + 0.06 - 0.10 * (y - 0.945) / (yTop - 0.945);   // side glass front edge, close to the windshield edge
    const frontWin = [[xF(0.945), 0.945], [xF(yTop), yTop - 0.01], [-0.40, railY(-0.40) - 0.005], [-0.40, 0.972]];
    const rearWin = [[-0.47, 0.972], [-0.47, railY(-0.47) - 0.005], [-0.78, railY(-0.78) - 0.01], [-1.20, 0.995]];
    const sail = [[-0.80, railY(-0.80)], [roofX1, railY(roofX1)], [-1.73, 1.0], [-1.20, 0.995]];
    const bPillar = [[-0.40, 0.972], [-0.40, railY(-0.40)], [-0.47, railY(-0.47)], [-0.47, 0.972]];
    grp.add(shapeOnSide(frontWin, zf, sideGlass));
    grp.add(shapeOnSide(rearWin, zf, sideGlass));
    grp.add(shapeOnSide(sail, (x, y) => zf(x, y) + side * 0.003, paint));
    grp.add(shapeOnSide(bPillar, (x, y) => zf(x, y) + side * 0.002, black));
    // window surround (black) along the roof rail
    const rail = mesh(gridSurface(16, 1, (u, v) => { const x = xTop + (roofX1 - xTop) * u; const y = railY(x) + 0.015 * v; return [x, y, zf(x, y) + side * 0.002]; }), black);
    grp.add(rail);
    // A-pillar skin: from the windshield side edge to the side window's front edge
    const ap = mesh(gridSurface(1, 14, (u, v) => {
      const y = 0.86 + (G.ROOF_Y - 0.86) * v;
      const a = (y - G.COWL_Y) / Math.sin(G.RAKE);
      const pw = wsPoint(a, side * (wsHalf(a) + 0.005), 0.006);
      const ps = [xA(y) + 0.06 - 0.10 * clamp((y - 0.945) / (1.375 - 0.945), 0, 1) + 0.004, y, zf(0, y)];
      return u < 0.5 ? [pw.x, pw.y, pw.z] : ps;
    }), paint);
    grp.add(ap);
    const apIn = mesh(gridSurface(1, 14, (u, v) => {
      const y = 0.86 + (G.ROOF_Y - 0.86) * v;
      const a = (y - G.COWL_Y) / Math.sin(G.RAKE);
      const pw = wsPoint(a, side * (wsHalf(a) - 0.03), -0.012);
      const ps = [xA(y) + 0.04 - 0.10 * clamp((y - 0.945) / (1.375 - 0.945), 0, 1), y, zf(0, y) - side * 0.02];
      return u < 0.5 ? [pw.x, pw.y, pw.z] : ps;
    }), trim);
    (side < 0 ? leftSide : rightSide).add(apIn);
  }
  // rear window
  const rw = mesh(gridSurface(8, 12, (u, v) => {
    const x = roofX1 - 0.005 + (-1.725 - roofX1) * u; const y = lerpN(railY(roofX1) + 0.02, 1.0, u); const w = 2 * v - 1;
    return [x, y + 0.02 * (1 - w * w) * (1 - u), CZ + w * lerpN(0.63, 0.80, u)];
  }), sideGlass);
  body.add(rw);

  // ---------------------------------------------------------------------------------------------- interior
  // floor, tunnel, toe board, firewall
  const floor = mesh(new THREE.BoxGeometry(2.9, 0.02, 1.72), carpet); floor.position.set(-0.52, FLOOR_Y - 0.01, CZ); interior.add(floor);
  const toe = mesh(gridSurface(2, 2, (u, v) => [0.93 + 0.24 * u, FLOOR_Y + 0.27 * u, CZ + (2 * v - 1) * 0.86]), carpet); interior.add(toe);
  const fw = mesh(gridSurface(2, 2, (u, v) => [1.17 + 0.03 * u, 0.40 + 0.18 * u, CZ + (2 * v - 1) * 0.86]), carpet); interior.add(fw);
  const tunnel = rbox(1.5, 0.18, 0.26, 0.05, carpet); tunnel.position.set(0.30, FLOOR_Y + 0.08, CZ); interior.add(tunnel);

  // dashboard: one cross-section extruded across the cabin
  const dashProfile = [
    [1.405, DASH_Y], [0.66, DASH_Y], [0.62, 0.79], [0.597, 0.776], [0.585, 0.75], [0.598, 0.70], [0.66, 0.62],
    [0.72, 0.56], [0.78, 0.52], [1.0, 0.515], [1.17, 0.56], [1.20, 0.70], [1.40, 0.783],
  ];
  const dash = extrudeXY(dashProfile, CZ - 0.86, CZ + 0.86, dashMat);
  dash.name = 'dashboard'; interior.add(dash);
  // defrost slot and speaker grilles on the dash top
  const grilleMat = new THREE.MeshStandardMaterial({ color: 0x08080a, roughness: 0.95 });
  const defrost = rbox(0.05, 0.004, 1.1, 0.002, grilleMat); defrost.position.set(1.32, DASH_Y + 0.002, CZ); interior.add(defrost);
  for (const s of [-1, 1]) { const sp = rbox(0.10, 0.004, 0.16, 0.002, grilleMat); sp.position.set(1.15, DASH_Y + 0.002, CZ + s * 0.72); interior.add(sp); }
  // vents on the dash face
  const ventMat = new THREE.MeshStandardMaterial({ color: 0x0a0b0c, roughness: 0.6 });
  for (const z of [-0.38, CZ + 0.75]) {
    const v = rbox(0.03, 0.06, 0.14, 0.012, ventMat); v.position.set(0.598, 0.735, z); interior.add(v);
    for (let i = 0; i < 3; i++) { const s = rbox(0.005, 0.004, 0.12, 0.001, chrome); s.position.set(0.583, 0.72 + i * 0.015, z); interior.add(s); }
  }
  // glovebox
  const glove = rbox(0.02, 0.12, 0.50, 0.01, dashMat); glove.position.set(0.635, 0.645, CZ + 0.50); glove.rotation.z = Math.atan2(0.08, 0.06) - Math.PI / 2 + 0.25; interior.add(glove);

  // cluster hood (visor) in front of the driver, rear of the HUD housing
  const visorProfile = [[0.47, 0.935], [0.485, 0.95], [0.56, 0.957], [0.635, 0.945], [0.635, 0.79], [0.615, 0.79], [0.615, 0.925], [0.495, 0.928]];
  const visor = extrudeXY(visorProfile, -0.21, 0.21, dashMat); visor.name = 'clusterHood'; interior.add(visor);
  for (const s of [-1, 1]) {
    const cheek = extrudeXY([[0.47, 0.935], [0.635, 0.945], [0.635, 0.79], [0.59, 0.79]], s * 0.21 - 0.006, s * 0.21 + 0.006, dashMat);
    interior.add(cheek);
  }
  const clusterMat = new THREE.MeshStandardMaterial({ map: clusterTexture(), emissive: 0xffffff, emissiveMap: null, emissiveIntensity: 0, roughness: 0.3 });
  clusterMat.emissiveMap = clusterMat.map; clusterMat.emissiveIntensity = 0.85;
  const cluster = mesh(new THREE.PlaneGeometry(0.33, 0.085), clusterMat, false);
  cluster.position.set(0.613, 0.888, 0); cluster.rotation.y = -Math.PI / 2; cluster.rotateX(-8 * DEG); cluster.name = 'cluster';
  interior.add(cluster);

  // centre stack with the infotainment screen and the 12 V accessory socket
  const stackProfile = [[0.62, 0.79], [0.585, 0.75], [0.54, 0.62], [0.447, 0.527], [0.418, 0.497], [0.414, 0.47], [0.42, 0.36], [0.55, 0.36], [0.80, 0.52], [0.66, 0.79]];
  const stack = extrudeXY(stackProfile, CZ - 0.13, CZ + 0.13, dashMat); stack.name = 'centreStack'; interior.add(stack);
  const scrMat = new THREE.MeshStandardMaterial({ map: screenTexture(), emissive: 0xffffff, emissiveIntensity: 0.6, roughness: 0.25 });
  scrMat.emissiveMap = scrMat.map;
  const scr = mesh(new THREE.PlaneGeometry(0.22, 0.125), scrMat, false);
  const faceAng = Math.atan2(0.75 - 0.62, 0.585 - 0.54);      // stack upper face slope
  scr.position.set(0.5615 - 0.004, 0.685, CZ); scr.rotation.y = -Math.PI / 2; scr.rotateX(-(Math.PI / 2 - faceAng));
  interior.add(scr);
  for (const s of [-1, 1]) { const v = rbox(0.025, 0.035, 0.09, 0.01, ventMat); v.position.set(0.60, 0.765, CZ + s * 0.06); interior.add(v); }
  // 12 V socket on the lower face, opening rearward and up
  const sockN = V3(-(0.50 - 0.47), (0.43 - 0.455), 0); sockN.set(-0.025, 0.025, 0).normalize();   // face normal (rear, up)
  const sock = new THREE.Group(); sock.name = 'accSocket';
  const bezel = mesh(new THREE.TorusGeometry(0.0155, 0.004, 8, 20), chrome); sock.add(bezel);
  const bore = mesh(new THREE.CylinderGeometry(0.0115, 0.0115, 0.03, 16, 1, true), black); bore.rotation.x = Math.PI / 2; bore.position.z = -0.012; sock.add(bore);
  const cap = mesh(new THREE.CircleGeometry(0.0115, 16), black); cap.position.z = -0.026; sock.add(cap);
  sock.position.copy(G.ACC_SOCKET); sock.quaternion.setFromUnitVectors(V3(0, 0, 1), sockN);
  interior.add(sock);

  // console between the seats
  const console_ = rbox(0.9, 0.40, 0.22, 0.04, dashMat); console_.position.set(-0.02, FLOOR_Y + 0.20, CZ); interior.add(console_);
  const arm = rbox(0.34, 0.06, 0.24, 0.03, M.leather); arm.position.set(-0.30, 0.565, CZ); interior.add(arm);
  const shifter = rbox(0.05, 0.08, 0.04, 0.015, M.leather); shifter.position.set(0.22, 0.585, CZ); interior.add(shifter);
  const shiftBase = rbox(0.12, 0.01, 0.10, 0.005, chrome); shiftBase.position.set(0.22, 0.54, CZ); interior.add(shiftBase);

  // steering column, shroud and wheel
  const colEnd = WHEEL_C.clone().addScaledVector(COL_DIR, 0.48);
  const column = limb(WHEEL_C.clone().addScaledVector(COL_DIR, 0.04), colEnd, 0.022, M.steel); interior.add(column);
  const shroud = rbox(0.18, 0.085, 0.11, 0.03, dashMat);
  shroud.position.copy(WHEEL_C).addScaledVector(COL_DIR, 0.165); shroud.rotation.z = -COL_ANG; shroud.name = 'columnShroud';
  interior.add(shroud);
  const steeringWheel = new THREE.Group(); steeringWheel.name = 'steeringWheel';
  steeringWheel.position.copy(WHEEL_C);
  steeringWheel.quaternion.setFromRotationMatrix(_m.makeBasis(V3(0, 0, 1), COL_UP, COL_DIR.clone().negate()));
  const wheelSpin = new THREE.Group(); steeringWheel.add(wheelSpin);
  const rim = mesh(new THREE.TorusGeometry(0.185, 0.017, 12, 56), M.leather); wheelSpin.add(rim);
  const hubW = mesh(new THREE.CylinderGeometry(0.065, 0.07, 0.06, 24), M.leather); hubW.rotation.x = Math.PI / 2; hubW.position.z = 0.01; wheelSpin.add(hubW);
  const badge = mesh(new THREE.CircleGeometry(0.018, 20), chrome); badge.position.z = 0.0405; wheelSpin.add(badge);
  for (const ang of [0, Math.PI, -Math.PI / 2]) {
    const sp = rbox(0.12, 0.035, 0.018, 0.008, M.leather); sp.position.set(Math.cos(ang) * 0.12, Math.sin(ang) * 0.12, 0.0); sp.rotation.z = ang;
    wheelSpin.add(sp);
  }
  interior.add(steeringWheel);

  // pedals
  const pedalMat = new THREE.MeshStandardMaterial({ color: 0x2a2b2e, metalness: 0.5, roughness: 0.5 });
  const brake = rbox(0.03, 0.09, 0.10, 0.01, pedalMat); brake.position.set(0.94, 0.31, 0.01); brake.rotation.z = -0.5; interior.add(brake);
  const gas = rbox(0.02, 0.18, 0.07, 0.008, pedalMat); gas.position.set(0.98, 0.27, 0.13); gas.rotation.z = -0.62; interior.add(gas);
  const rest = rbox(0.02, 0.16, 0.08, 0.008, pedalMat); rest.position.set(0.97, 0.25, -0.17); rest.rotation.z = -0.62; interior.add(rest);

  // seats
  const seats = new THREE.Group(); seats.name = 'seats'; interior.add(seats);
  // The passenger headrest and its posts are a group of their own: monitor 2 hangs from them, so they can stay when
  // the seats are taken out.
  const headrestMount = new THREE.Group(); headrestMount.name = 'passengerHeadrest'; interior.add(headrestMount);
  const recline = 25 * DEG;
  const backDir = V3(-Math.sin(recline), Math.cos(recline), 0), backRear = V3(-Math.cos(recline), -Math.sin(recline), 0);
  const addSeat = (z, headParent = null) => {
    const s = new THREE.Group();
    const cushion = rbox(0.52, 0.11, 0.50, 0.04, M.seat); cushion.position.set(0.15, 0.415, z); cushion.rotation.z = 10 * DEG; s.add(cushion);
    for (const k of [-1, 1]) { const b = rbox(0.48, 0.07, 0.07, 0.03, M.leather); b.position.set(0.15, 0.475, z + k * 0.235); b.rotation.z = 10 * DEG; s.add(b); }
    const B0 = V3(0.04, 0.50, z);
    const back = rbox(0.12, 0.66, 0.50, 0.05, M.seat); back.position.copy(B0).addScaledVector(backDir, 0.32).addScaledVector(backRear, 0.06); back.rotation.z = recline; s.add(back);
    for (const k of [-1, 1]) { const b = rbox(0.10, 0.52, 0.07, 0.03, M.leather); b.position.copy(B0).addScaledVector(backDir, 0.28).addScaledVector(backRear, 0.02); b.position.z = z + k * 0.24; b.rotation.z = recline; s.add(b); }
    const hp = headParent || s;
    const head = rbox(0.10, 0.20, 0.27, 0.045, M.seat); head.position.set(-0.255, 1.25, z); head.rotation.z = 8 * DEG; hp.add(head);
    for (const k of [-1, 1]) { const post = limb(V3(-0.30, 1.10, z + k * 0.07), V3(-0.27, 1.17, z + k * 0.07), 0.006, chrome); hp.add(post); }
    const rail = rbox(0.6, 0.04, 0.42, 0.01, black); rail.position.set(0.1, 0.30, z); s.add(rail);
    seats.add(s);
    return s;
  };
  addSeat(0); addSeat(2 * CZ, headrestMount);
  const rearCushion = rbox(0.50, 0.12, 1.30, 0.05, M.seat); rearCushion.position.set(-0.98, 0.43, CZ); rearCushion.rotation.z = 8 * DEG; seats.add(rearCushion);
  const rearBack = rbox(0.12, 0.62, 1.30, 0.05, M.seat); rearBack.position.set(-1.33, 0.76, CZ); rearBack.rotation.z = 28 * DEG; seats.add(rearBack);
  const shelf = rbox(0.32, 0.02, 1.45, 0.01, trim); shelf.position.set(-1.58, 0.99, CZ); interior.add(shelf);

  // door trims (the driver's side ones go with the cutaway)
  for (const side of [-1, 1]) {
    const grp = side < 0 ? leftSide : rightSide;
    const z = CZ + side * 0.855;
    for (const [x0, x1] of [[1.12, -0.41], [-0.43, -1.05]]) {
      const p = rbox(x0 - x1, 0.70, 0.04, 0.02, trim); p.position.set((x0 + x1) / 2, 0.60, z); grp.add(p);
      const armr = rbox((x0 - x1) * 0.6, 0.04, 0.08, 0.015, trimLight); armr.position.set((x0 + x1) / 2 - 0.05, 0.66, z - side * 0.05); grp.add(armr);
      const spk = mesh(new THREE.CircleGeometry(0.065, 20), black); spk.position.set(x0 - 0.2, 0.36, z - side * 0.021); spk.rotation.y = side > 0 ? Math.PI : 0; grp.add(spk);
    }
    const cap = rbox(1.55, 0.03, 0.06, 0.012, trimLight); cap.position.set(0.35, 0.955, z); grp.add(cap);
  }
  // sun visors folded against the headliner
  for (const z of [0.0, 2 * CZ]) { const sv = rbox(0.17, 0.02, 0.34, 0.01, headliner); sv.position.set(0.24, roofY(0.24) - 0.06, z); sv.rotation.z = 0.12; interior.add(sv); }

  // rear-view mirror on its stalk (the road camera is clamped to the stalk by the integrator)
  const mirrorPivot = V3(0.30, 1.318, CZ);
  const stalk = limb(G.MIRROR_STALK.clone().add(V3(0.004, 0, 0)), mirrorPivot, 0.007, black); interior.add(stalk);
  const button = mesh(new THREE.CylinderGeometry(0.014, 0.014, 0.006, 16), black); button.position.copy(G.MIRROR_STALK); button.quaternion.setFromUnitVectors(V3(0, 1, 0), G.GLASS_N); interior.add(button);
  const rvm = new THREE.Group(); rvm.name = 'rearViewMirror';
  const rvmBody = rbox(0.035, 0.07, 0.26, 0.02, black); rvm.add(rvmBody);
  const rvmFace = mesh(new THREE.PlaneGeometry(0.245, 0.058), M.mirror); rvmFace.rotation.y = -Math.PI / 2; rvmFace.position.x = -0.0185; rvm.add(rvmFace);
  rvm.position.set(0.285, 1.30, CZ); rvm.rotation.y = -25 * DEG; interior.add(rvm);

  // ---------------------------------------------------------------------------------------------- driver
  const driver = new THREE.Group(); driver.name = 'driver'; interior.add(driver);
  const skin = M.skin, shirt = new THREE.MeshStandardMaterial({ color: 0x2f4f6f, roughness: 0.9 }), pants = new THREE.MeshStandardMaterial({ color: 0x23252b, roughness: 0.9 });
  const shoe = new THREE.MeshStandardMaterial({ color: 0x151515, roughness: 0.7 });
  const pelvis = rbox(0.24, 0.16, 0.36, 0.07, pants); pelvis.position.set(0.12, 0.56, 0); pelvis.rotation.z = 0.2; driver.add(pelvis);
  const torso = mesh(new THREE.CapsuleGeometry(0.14, 0.26, 6, 14), shirt); torso.scale.set(0.82, 1, 1.32);
  { const a = V3(0.11, 0.62, 0), b = V3(-0.055, 0.99, 0); torso.position.copy(a).add(b).multiplyScalar(0.5); torso.quaternion.setFromUnitVectors(V3(0, 1, 0), b.clone().sub(a).normalize()); }
  driver.add(torso);
  const neck = limb(V3(-0.065, 1.03, 0), V3(-0.07, 1.16, 0), 0.048, skin); driver.add(neck);
  const headG = new THREE.Group(); headG.name = 'head'; headG.position.copy(G.EYE); driver.add(headG);
  const skull = mesh(new THREE.SphereGeometry(0.1, 24, 18), skin); skull.scale.set(1.0, 1.18, 0.82); skull.position.set(-0.085, 0.03, 0); headG.add(skull);
  const hair = mesh(new THREE.SphereGeometry(0.104, 24, 12, 0, Math.PI * 2, 0, Math.PI * 0.52), new THREE.MeshStandardMaterial({ color: 0x2a1d14, roughness: 0.9 }));
  hair.scale.set(1.04, 1.12, 0.86); hair.position.set(-0.095, 0.055, 0); hair.rotation.z = 0.25; headG.add(hair);
  const eyeWhite = new THREE.MeshStandardMaterial({ color: 0xf2f2f2, roughness: 0.3 }), iris = new THREE.MeshStandardMaterial({ color: 0x3b2a1f, roughness: 0.3 });
  for (const s of [-1, 1]) {
    const e = mesh(new THREE.SphereGeometry(0.012, 12, 8), eyeWhite, false); e.position.set(0, 0, s * 0.032); headG.add(e);
    const ir = mesh(new THREE.SphereGeometry(0.006, 10, 6), iris, false); ir.position.set(0.009, 0, s * 0.032); headG.add(ir);
    const ear = mesh(new THREE.SphereGeometry(0.025, 10, 8), skin); ear.scale.set(0.6, 1.2, 0.4); ear.position.set(-0.085, -0.005, s * 0.083); headG.add(ear);
  }
  const nose = mesh(new THREE.ConeGeometry(0.014, 0.04, 8), skin); nose.rotation.z = -Math.PI / 2 + 0.3; nose.position.set(0.03, -0.028, 0); headG.add(nose);
  // arms to the wheel at about 9 and 3 o'clock
  const handAt = (k) => WHEEL_C.clone().add(V3(0, 0, k * 0.182)).addScaledVector(COL_UP, 0.03);
  for (const k of [-1, 1]) {
    const sh = V3(-0.07, 1.0, k * 0.19), el = V3(0.13, 0.82, k * 0.245), wr = handAt(k).add(V3(-0.02, 0, -k * 0.005));
    driver.add(limb(sh, el, 0.048, shirt)); driver.add(limb(el, wr, 0.038, skin));
    const shoulder = mesh(new THREE.SphereGeometry(0.06, 14, 10), shirt); shoulder.position.copy(sh); driver.add(shoulder);
    const hand = rbox(0.05, 0.09, 0.04, 0.018, skin); hand.position.copy(handAt(k)); hand.quaternion.copy(steeringWheel.quaternion); driver.add(hand);
  }
  // legs: right foot on the accelerator, left on the rest
  for (const [k, knee, ankle] of [[1, V3(0.54, 0.64, 0.11), V3(0.89, 0.29, 0.12)], [-1, V3(0.53, 0.63, -0.13), V3(0.88, 0.27, -0.16)]]) {
    const hip = V3(0.14, 0.55, k * 0.09);
    driver.add(limb(hip, knee, 0.068, pants)); driver.add(limb(knee, ankle, 0.052, pants));
    const kneeCap = mesh(new THREE.SphereGeometry(0.06, 12, 10), pants); kneeCap.position.copy(knee); driver.add(kneeCap);
    const foot = rbox(0.24, 0.07, 0.09, 0.03, shoe); foot.position.copy(ankle).add(V3(0.09, -0.01, 0)); foot.rotation.z = 0.55; driver.add(foot);
  }
  driver.setHeadOffset = (v) => { headG.position.copy(G.EYE).add(v); };
  driver.head = headG;

  // ---------------------------------------------------------------------------------------------- behaviour
  for (const m of [...body.children]) m.traverse?.((o) => { if (o.isMesh) o.userData.bodyPart = true; });
  // The car gets its own copies of the shared materials (M.*): the section cut puts a clipping plane on every car
  // material, and on a shared one it would also clip the parts and world objects using it behind the cut. The
  // materials the functions below change in place stay the same instances.
  const xrayMats = [paint, black, chrome, sideGlass, headLens, tailLens, trim, trimLight, headliner];
  const own = new Set([...xrayMats, tire, clusterMat, wsGlass]);
  const copies = new Map();
  const ownCopy = (m) => { if (own.has(m)) return m; if (!copies.has(m)) copies.set(m, m.clone()); return copies.get(m); };
  const carMats = new Set();
  group.traverse((o) => {
    if (!o.isMesh) return;
    o.material = Array.isArray(o.material) ? o.material.map(ownCopy) : ownCopy(o.material);
    [].concat(o.material).forEach((m) => carMats.add(m));
  });

  // Section cut: every part of the car behind x = sectionX (car frame) is clipped away. The plane lives in world
  // space, so whoever moves the car calls updateSection() after placing it.
  const sectionPlane = new THREE.Plane();
  let sectionX = null;
  function updateSection() {
    if (sectionX === null) return;
    group.updateWorldMatrix(true, false);
    sectionPlane.set(V3(1, 0, 0), -sectionX).applyMatrix4(group.matrixWorld);
  }
  function setSection(x) {
    sectionX = x ?? null;
    for (const m of carMats) { m.clippingPlanes = sectionX === null ? null : [sectionPlane]; m.clipShadows = sectionX !== null; m.needsUpdate = true; }
    updateSection();
  }
  // Strip levels for seeing the installed parts: 'full'; 'nodriver'; 'noseats' (the driver and every seat out, the
  // passenger headrest kept as monitor 2's mount when keepHeadrest); 'front' (as 'noseats', and the car cut away
  // behind cutX).
  let strip = 'full';
  function setStrip(level, { cutX = -0.8, keepHeadrest = true } = {}) {
    strip = level;
    driver.visible = level === 'full';
    const seatsIn = level === 'full' || level === 'nodriver';
    seats.visible = seatsIn;
    headrestMount.visible = seatsIn || keepHeadrest;
    setSection(level === 'front' ? cutX : null);
  }

  let cutaway = 'none';
  // mode: 'none' | 'side' (driver's side open) | 'passenger' | 'both' | 'xray'
  function setCutaway(mode) {
    cutaway = mode;
    leftSide.visible = mode !== 'side' && mode !== 'both';
    rightSide.visible = mode !== 'passenger' && mode !== 'both';
    const xr = mode === 'xray';
    for (const mat of xrayMats) {
      if (xr) {
        if (!xrayState.has(mat)) xrayState.set(mat, { t: mat.transparent, o: mat.opacity, d: mat.depthWrite });
        mat.transparent = true; mat.opacity = mat === sideGlass ? 0.08 : 0.14; mat.depthWrite = false;
      } else if (xrayState.has(mat)) {
        const s = xrayState.get(mat); mat.transparent = s.t; mat.opacity = s.o; mat.depthWrite = s.d;
      }
      mat.needsUpdate = true;
    }
    tire.transparent = xr; tire.opacity = xr ? 0.25 : 1; tire.depthWrite = !xr; tire.needsUpdate = true;
  }
  function setHeadlights(on) {
    headlights.forEach((l) => { l.intensity = on ? 260 : 0; });
    headLens.emissiveIntensity = on ? 4 : 0.15;
    tailLens.emissiveIntensity = on ? 2.4 : 0.15;
    clusterMat.emissiveIntensity = on ? 1.1 : 0.85;
  }
  function update(dt, speed = 0, steerAngle = 0) {
    for (const w of wheels) {
      w.spin.rotation.z -= speed * dt / WHEEL_R;
      if (w.front) w.pivot.rotation.y = -steerAngle;
    }
    wheelSpin.rotation.z = -steerAngle * STEER_RATIO;
  }
  // Height of the top-most dash surface at (x, z), NaN outside the dash.
  function dashTopY(x, z) {
    if (Math.abs(z - CZ) > 0.86) return NaN;
    if (Math.abs(z) <= 0.21 && x >= 0.47 && x <= 0.635) {
      const t = (x - 0.47) / 0.165; return t < 0.55 ? 0.935 + 0.022 * Math.sin(t / 0.55 * Math.PI / 2) : 0.957 - 0.012 * (t - 0.55) / 0.45;
    }
    if (x >= 0.66 && x <= 1.405) return DASH_Y;
    if (x >= 0.585 && x < 0.66) { for (let i = 1; i < 5; i++) { const [xa, ya] = dashProfile[i], [xb, yb] = dashProfile[i + 1]; if ((x - xa) * (x - xb) <= 0) return ya + (yb - ya) * (x - xa) / (xb - xa); } }
    return NaN;
  }

  const anchors = {
    // On the steering-column shroud top at geom.DRIVER_CAM's x (the shroud top is higher than DRIVER_CAM.y = 0.86).
    driverCam: { position: (() => { const p = WHEEL_C.clone().addScaledVector(COL_DIR, (G.DRIVER_CAM.x - WHEEL_C.x) / COL_DIR.x); return p.addScaledVector(COL_UP, 0.0425); })(), up: COL_UP.clone() },
    // Back of the passenger headrest posts; a monitor hangs from here facing the rear seat (-X).
    monitor2: { position: V3(-0.32, 1.13, 2 * CZ), facing: V3(-1, 0, 0) },
    floor: { y: FLOOR_Y },
    jetsonFloor: { position: V3(G.JETSON.x, FLOOR_Y, G.JETSON.z) },
    accSocket: { position: G.ACC_SOCKET.clone(), normal: sockN.clone() },
    mirrorStalk: { mount: G.MIRROR_STALK.clone(), pivot: mirrorPivot.clone(), mirror: rvm.position.clone() },
    gnssDash: { position: V3(G.GNSS_ANT.x, DASH_Y, G.GNSS_ANT.z) },
    dashShelfY: DASH_Y,
    wheelCentre: WHEEL_C.clone(), columnDir: COL_DIR.clone(),
    frontBumperX: 2.46, rearBumperX: -2.38,
  };

  setCutaway('none');

  return {
    group, body, interior, wheels, steeringWheel, driver, seats, headrestMount, headlights, leftSide, anchors,
    windshieldMaterial: wsGlass,
    dims: { length: 4.84, width: 2 * HW + 0.04, height: 1.435, frontX: 2.46, rearX: -2.38, centerZ: CZ, wheelbase: FRONT_AXLE - REAR_AXLE },
    setCutaway, setStrip, updateSection, setHeadlights, update, dashTopY,
    get cutaway() { return cutaway; },
    get strip() { return strip; },
  };
}

function lerpN(a, b, t) { return a + (b - a) * t; }
