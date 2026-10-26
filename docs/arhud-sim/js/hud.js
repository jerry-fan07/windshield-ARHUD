// The HUD software in miniature: simulated perception (roadd/laned/detectd/egod/headtrackd), the hudd renderer with the
// plan's drawing rules, age compensation and eye projection, the controllerd dimming and thermal rules, and the sun-watch
// rule. It draws the PGU frame (946 x 473 px, the 60 x 30 mm crop) into a canvas, exactly what the panel would show
// before the pre-distortion warp, and computes the numbers the audience view shows.
//
// Frames: everything here is in the simulation car frame of geom.js (X forward, Y up, Z right, origin on the ground
// below the nominal eye). World poses come from the drive mode through pushPose().
import * as THREE from 'three';
import { P, R } from './params.js';
import * as GM from './geom.js';
import { buildLut, lutPanelPoint, lutNominalField } from './lut.js';
import { rayReaches } from './clip.js';
import { rng, gauss, clamp, lerp, smoothstep, DEG } from './util.js';

export const CROP_W = Math.round(R.CROP_PX_W);    // 946
export const CROP_H = Math.round(R.CROP_PX_H);    // 473
const PPD = R.PPD2;                                // 87 px per degree
const FRONT_BUMPER_X = 2.45;
const MPH = 2.236936;

// Latency stages in ms, from the plan's budget (P.LAT rows: name, min, max).
export const LAT_STAGES = P.LAT.map(([name, lo, hi]) => ({ name, lo, hi }));

export const PGU_SOURCES = [
  { key: 'stock', label: '5.5-inch kit, stock backlight', panel: 450 },
  { key: 'ind', label: 'Industrial sunlight-readable', panel: 1600 },
  { key: 'bl', label: 'Custom backlight (design)', panel: R.L_PANEL_DESIGN },
  { key: 'blc', label: 'Collimated backlight', panel: R.L_PANEL_DESIGN * R.GAIN_COLLIM, assumed: true },
  { key: 'hud', label: 'HUD-grade TFT', panel: 50000, unverified: true },
];

// Smooth deterministic noise in [-1, 1].
function snoise(x, seed) {
  return (Math.sin(x * 1.13 + seed * 7.1) * 0.5 + Math.sin(x * 0.47 + seed * 3.3) * 0.35 + Math.sin(x * 2.71 + seed * 1.7) * 0.15);
}

export class HudSim {
  constructor(world) {
    this.world = world;
    this.canvas = document.createElement('canvas');
    this.canvas.width = CROP_W; this.canvas.height = CROP_H;
    this.ctx = this.canvas.getContext('2d');
    this.texture = new THREE.CanvasTexture(this.canvas);
    this.texture.colorSpace = THREE.SRGBColorSpace;
    this.texture.minFilter = THREE.LinearMipmapLinearFilter;
    this.texture.anisotropy = 8;

    this.settings = {
      compensation: 'photon',       // 'photon' (predict to photon time), 'now' (plan's formula, to draw time), 'off'
      lat: LAT_STAGES.map((s) => (s.lo + s.hi) / 2),   // ms per stage
      cameraHz: 30,
      headTracking: true,
      trackerLatency: 40,          // ms (plan: 30-50)
      ghost: true,
      ghostScale: 1,               // exaggeration of the 3.1 mm ghost offset
      pgu: 'bl',
      bothSurfaces: false,
      autoDim: true,
      dimSteps: 0,                 // driver offset, +/- one step
      clutterUntil: -1,
      ribbon: 'fill',              // 'fill' (the plan's tinted lane) or 'blank' (lane still computed for the lead, not drawn)
      window: 'traced',            // 'traced' (what the hardware gives, Cycles-confirmed: 8.7 x 4.6 at 8.6 m) or 'spec' (the plan's 7.5 m, 10.8 x 5.4)
      sunWatch: true,
      surfaceAware: false,         // kept for the toggle; projection below is what counts
      projection: 'plane',         // how hudd places a symbol for the tracked eye: 'plane' (one distance, the plan), 'surface' (image-surface map), 'trace' (the optical model, eye to panel, exact), 'lut' (the same as a lookup table, as the Jetson would)
      gnssOutage: false,
      showStale: false,
    };
    this.hist = [];                // ego pose history
    this.t = 0;
    this.k = -1;                   // last processed capture index
    this.lineState = new Map();
    this.tracks = new Map();
    this.sign = { value: null, t: -1e9, cand: null, candCount: 0 };
    this.stats = { ageLanes: 0, ageObjects: 0, ageEgo: 0, ageEye: 0, render: 0, residual: 0, residualLane: 0, residualLead: 0, dropped: 0 };
    this.lum = { duty: 1, Leye: 0, Lpanel: 0, contrastSky: 1, contrastRoad: 1, black: 0, lux: 0 };
    this.thermal = { cell: 32, state: 'ok' };
    this.shutter = { open: 1, target: 1, reason: '' };
    this.sun = { inPatch: false, dAz: 0, dEl: 0, elev: 0 };
    // The sun-watch patch about the entry direction (degrees): the plan's figure until the Blender sun trace
    // (assets/cycles/sun_focus.json, loaded by install.js) replaces it with the directions that light the whole cell.
    this.sunPatch = { azHalf: R.PATCH_W / 2, elMin: -R.PATCH_H / 2, elMax: R.PATCH_H / 2, source: 'plan' };
    this.eye = { trueOffset: new THREE.Vector3(), tracked: new THREE.Vector3(), used: new THREE.Vector3(), nominal: false };
    this.eyeHist = [];
    this.lastDrawn = { lead: null, lanePt: null };
    this.frameCount = 0;
    const L = this.settings.lat;
    this.latency = { ageCapture: (L[0] + L[1] + L[2]) / 1000, dDisplay: (L[3] + L[4]) / 1000, total: L.reduce((a, b) => a + b, 0) / 1000 };
    this.setWindow('traced');
  }

  // ---- window / virtual plane ---------------------------------------------------------
  setWindow(kind) {
    this.settings.window = kind;
    if (kind === 'stage1') {
      // Stage 1: 80 x 40 mm crop of the monitor, Fresnel f = 300 mm at u = 280 mm, virtual image 4.2 m, x15, via a 30% combiner.
      const dist = Math.abs(R.V1_mm) / 1000;
      this.plane = { dist, w: 0.080 * R.M1, h: 0.040 * R.M1 };
    } else if (kind === 'traced') {
      // The plan's hardware (f = 330, u = 316, 60 x 30 crop) with the eye 1.06 m from the mirror: the image sits 7.5 m
      // behind the mirror and the crop subtends a smaller field. Inscribed rectangle after the keystone is pre-distorted.
      const tr = tracedWindow();
      this.plane = { dist: tr.dist, w: tr.w, h: tr.h };
      this.traced = tr;
    } else {
      this.plane = { dist: GM.VID, w: GM.IMG_W, h: GM.IMG_H };
    }
    this.plane.c = GM.EYE.clone().addScaledVector(GM.LOOK, this.plane.dist);
    this.plane.fovW = 2 * Math.atan(this.plane.w / 2 / this.plane.dist) / DEG;
    this.plane.fovH = 2 * Math.atan(this.plane.h / 2 / this.plane.dist) / DEG;
  }

  // Project a car-frame point onto the virtual image as seen from eye e. Returns [px, py] in crop pixels, or null.
  // hudd as planned projects onto a plane at one distance; with surfaceAware it projects onto the image surface the
  // optics make (which the simulator draws), iterating the plane projection against the local image distance.
  project(p, e) {
    const flat = this.projectPlane(p, e);
    const mode = this.settings.projection || (this.settings.surfaceAware ? 'surface' : 'plane');
    if (!flat || mode === 'plane' || this.settings.window !== 'traced') return flat;
    if (mode === 'lut') {
      // the Jetson's way: the eye-position-to-panel table built from the trace, interpolated; rebuilt when the figure or the glass changes
      const key = GM.MIRROR.mode + ':' + GM.GLASS.Rh + ':' + GM.GLASS.Rv;
      if (!this.lut || this.lut.key !== key) { this.lut = buildLut(GM.MIRROR.mode); this.lut.key = key; }
      const d = p.clone().sub(e).normalize();
      const dl = d.dot(GM.LOOK); if (dl <= 1e-6) return flat;
      const tx = d.dot(GM.VIMG_RIGHT) / dl, ty = d.dot(GM.VIMG_UP) / dl;
      const off = e.clone().sub(GM.EYE);
      const pp = lutPanelPoint(this.lut, off.y, off.z, tx, ty);
      if (!pp) return flat;
      const ft = lutNominalField(this.lut, pp[0], pp[1]);
      if (!ft) return flat;
      return this.projectPlane(GM.EYE.clone().add(GM.fieldDir(Math.atan(ft[0]), Math.atan(ft[1]))), GM.EYE) || flat;
    }
    if (mode === 'trace') {
      // light the panel point the eye sees in the object's direction: trace from the tracked eye through the optics
      // to the panel, then the canvas pixel of that panel point (the canvas is the nominal eye's view, and the
      // pre-distortion to the panel is the nominal mapping, so invert it here)
      const tr = GM.traceFromEye(e, p.clone().sub(e).normalize());
      if (!tr) return flat;
      const sol = GM.panelPointField(GM.EYE, tr.panelZ, tr.panelX);
      if (!sol) return flat;
      return this.projectPlane(GM.EYE.clone().add(GM.fieldDir(sol.ax, sol.ay)), GM.EYE) || flat;
    }
    let px = flat[0], py = flat[1];
    for (let it = 0; it < 3; it++) {
      const sp = this.surfacePoint(px, py);
      const d = new THREE.Vector3().subVectors(p, e);
      const den = d.dot(GM.VIMG_N);
      if (den > -1e-6) return flat;
      const t = new THREE.Vector3().subVectors(sp, e).dot(GM.VIMG_N) / den;
      const q = e.clone().addScaledVector(d, t);
      const nom = this.projectPlane(q, GM.EYE);
      if (!nom) return flat;
      px = nom[0]; py = nom[1];
    }
    return [px, py];
  }

  // The point of the image surface behind crop pixel (px, py): on the nominal eye's ray, at the traced sagittal image
  // distance (the plane's point for the spec and stage-1 windows, or where the trace misses).
  surfacePoint(px, py) {
    const dir = this.pixelDir(px, py, GM.EYE);
    const pl = this.plane;
    let D = new THREE.Vector3().subVectors(pl.c, GM.EYE).dot(GM.VIMG_N) / dir.dot(GM.VIMG_N);
    if (this.settings.window === 'traced') {
      const d = GM.imageDistanceAlong(GM.EYE, dir);
      if (d != null && d > 1 && d < 500) D = d;
    }
    return GM.EYE.clone().addScaledVector(dir, D);
  }

  // Direction from eye e to the image-surface point behind a crop pixel (the image-surface model).
  surfaceDir(px, py, e) {
    return this.surfacePoint(px, py).sub(e).normalize();
  }

  // Direction in which eye e actually sees crop pixel (px, py): the pixel's panel point (the nominal eye's mapping,
  // which is how the frame reaches the panel), then the field direction from e whose ray lands on that panel point.
  // This is the pinhole-eye physics Cycles reproduces; the plane and surface models approximate it.
  traceDir(px, py, e) {
    if (this.settings.window !== 'traced') return this.pixelDir(px, py, e);
    const nom = GM.traceFromEye(GM.EYE, this.pixelDir(px, py, GM.EYE));
    if (!nom) return this.pixelDir(px, py, e);
    const sol = GM.panelPointField(e, nom.panelZ, nom.panelX);
    return sol ? GM.fieldDir(sol.ax, sol.ay) : this.surfaceDir(px, py, e);
  }

  projectPlane(p, e) {
    const pl = this.plane;
    const d = new THREE.Vector3().subVectors(p, e);
    const den = d.dot(GM.VIMG_N);
    if (den > -1e-6) return null;                    // behind the eye or parallel
    const t = new THREE.Vector3().subVectors(pl.c, e).dot(GM.VIMG_N) / den;
    if (t <= 0) return null;
    const q = e.clone().addScaledVector(d, t).sub(pl.c);
    const u = q.dot(GM.VIMG_RIGHT), v = q.dot(GM.VIMG_UP);
    return [(u / pl.w + 0.5) * CROP_W, (0.5 - v / pl.h) * CROP_H];
  }

  // Direction (unit) from eye e through crop pixel (px, py).
  pixelDir(px, py, e) {
    const pl = this.plane;
    const u = (px / CROP_W - 0.5) * pl.w, v = (0.5 - py / CROP_H) * pl.h;
    return pl.c.clone().addScaledVector(GM.VIMG_RIGHT, u).addScaledVector(GM.VIMG_UP, v).sub(e).normalize();
  }

  // ---- ego history ----------------------------------------------------------------------
  pushPose(pose) {
    this.hist.push(pose);
    while (this.hist.length > 2 && this.hist[0].t < pose.t - 3) this.hist.shift();
  }
  poseAt(t) {
    const h = this.hist; if (!h.length) return null;
    if (t <= h[0].t) return h[0];
    if (t >= h[h.length - 1].t) return h[h.length - 1];
    let lo = 0, hi = h.length - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (h[m].t <= t) lo = m; else hi = m; }
    const a = h[lo], b = h[hi], f = (t - a.t) / Math.max(1e-6, b.t - a.t);
    let dpsi = b.psi - a.psi; if (dpsi > Math.PI) dpsi -= 2 * Math.PI; if (dpsi < -Math.PI) dpsi += 2 * Math.PI;
    const psi = a.psi + dpsi * f;
    return {
      t, s: lerp(a.s, b.s, f), x: lerp(a.x, b.x, f), z: lerp(a.z, b.z, f), psi,
      speed: lerp(a.speed, b.speed, f), yawRate: lerp(a.yawRate, b.yawRate, f), offset: lerp(a.offset, b.offset, f),
    };
  }
  // World point -> car frame at pose.
  toCar(W, pose) {
    const dx = W.x - pose.x, dz = W.z - pose.z;
    const c = Math.cos(pose.psi), s = Math.sin(pose.psi);
    return new THREE.Vector3(dx * c + dz * s, W.y, -dx * s + dz * c);
  }

  // Dead-reckon from t0 to t1 with egod's noisy speed and yaw rate. Returns { dx, dz, dpsi } in the frame at t0.
  egoDelta(t0, t1, seed) {
    if (t1 <= t0) return { dx: 0, dz: 0, dpsi: 0 };
    const r = rng(seed);
    const bias = 0.03 * snoise(t0 * 0.2, 3);         // slow GNSS speed bias, m/s
    let psi = 0, dx = 0, dz = 0;
    const dt = 0.01;
    for (let t = t0; t < t1; t += dt) {
      const step = Math.min(dt, t1 - t);
      const p = this.poseAt(t);
      const vv = p.speed + bias + gauss(r) * 0.05;          // ZED-F9R velocity accuracy 0.05 m/s
      const w = p.yawRate + gauss(r) * 0.002;
      psi += w * step;
      dx += vv * Math.cos(psi) * step; dz += vv * Math.sin(psi) * step;
    }
    return { dx, dz, dpsi: psi };
  }
  static applyDelta(p, d) {
    const c = Math.cos(d.dpsi), s = Math.sin(d.dpsi);
    const x = p.x - d.dx, z = p.z - d.dz;
    return new THREE.Vector3(x * c + z * s, p.y, -x * s + z * c);
  }

  // ---- perception at capture index k ------------------------------------------------
  capture(k) {
    const W = this.world;
    const tc = k / this.settings.cameraHz;
    const pose = this.poseAt(tc);
    if (!pose) return null;
    const r = rng(1000 + k);
    const night = W.env && W.env.name === 'night';
    const dusk = W.env && W.env.name === 'dusk';
    const rangeScale = night ? 0.62 : dusk ? 0.85 : 1;
    // Lanes: ego lines and their neighbours.
    const ego = W.lanes.ego;
    const lines = W.lines.slice().sort((a, b) => a.offset - b.offset);
    const iL = lines.findIndex((l) => l.id === ego.left), iR = lines.findIndex((l) => l.id === ego.right);
    const pick = [[lines[iL], 'egoLeft'], [lines[iR], 'egoRight'], [lines[iL - 1], 'other'], [lines[iR + 1], 'other']].filter(([l]) => l);
    const lanes = [];
    for (const [line, type] of pick) {
      const pts = [];
      let lastConf = 0;
      for (let ds = -2; ds <= 72; ds += 2) {
        const s = pose.s + ds;
        const Wp = W.linePoint(line, s);
        const pc = this.toCar(Wp, pose);
        if (pc.x < 3 || pc.x > 72) continue;
        const sig = 0.02 + 0.004 * pc.x;
        const lat = sig * (0.65 * snoise(tc * 0.9 + pc.x * 0.05, line.id.length + type.length) + 0.35 * gauss(r));
        pc.z += lat;
        const painted = W.isPainted(line, s) || (line.style === 'dashed' && W.isPainted(line, s + 6));
        const worn = line.gaps && line.gaps.some(([a, b]) => s >= a && s <= b);
        let conf = (worn ? 0.22 : 0.93) * (1 - smoothstep(38 * rangeScale, 68 * rangeScale, pc.x));
        if (!painted && line.style !== 'dashed') conf *= 0.6;
        conf = clamp(conf + 0.04 * gauss(r), 0, 1);
        pts.push({ p: pc, conf });
      }
      const near = pts.filter((q) => q.p.x >= 6 && q.p.x <= 25);
      const lineConf = near.length ? near.reduce((a, q) => a + q.conf, 0) / near.length : 0;
      let last = 0;
      for (const q of pts) { if (q.conf > 0.5) last = q.p.x; else if (q.p.x > 8) break; }
      lanes.push({ id: line.id, type, line, pts, conf: lineConf, last });
      lastConf = lineConf;
    }
    // Objects: bearing exact from the road camera, range with stereo error.
    const cam = GM.ROAD_CAM;
    const objects = [];
    for (const a of W.agents) {
      const wp = a.worldPosition();
      const pc = this.toCar(wp, pose);
      if (pc.x < 2 || pc.x > 90) continue;
      const rel = pc.clone().sub(new THREE.Vector3(cam.x, 0, cam.z));
      const bearing = Math.atan2(rel.z, rel.x);
      if (Math.abs(bearing) > 36 * DEG) continue;
      const isPerson = a.kind === 'person' || a.kind === 'bicycle';
      const pdet = isPerson ? (pc.x < 30 * rangeScale ? 0.9 : 0.4) : (pc.x < 50 * rangeScale ? 0.97 : 0.75);
      if (r() > pdet) continue;
      const z = rel.length();
      const dz = z < 35 ? z * z * R.D_DISP / (R.F_PX * R.B_ST) : z * 0.05;
      const zMeas = z + dz * gauss(r) * 0.8;
      const scale = zMeas / z;
      const meas = new THREE.Vector3(cam.x, 0, cam.z).addScaledVector(rel, scale);
      // Heading of the agent in the car frame
      const hw = a.heading ? new THREE.Vector3(wp.x + a.heading.x, 0, wp.z + a.heading.z) : null;
      const hc = hw ? this.toCar(hw, pose).sub(pc) : new THREE.Vector3(1, 0, 0);
      objects.push({ id: a.id, kind: a.kind, p: meas, truth: pc, length: a.length, width: a.width, height: a.height, heading: hc.normalize(), speed: a.speed, conf: 0.6 + 0.35 * r() });
    }
    // Speed-limit signs: read when within 45 m and in front.
    let signRead = null;
    for (const sg of W.signs || []) {
      const pc = this.toCar(sg.position, pose);
      if (pc.x > 6 && pc.x < 45 * rangeScale && Math.abs(Math.atan2(pc.z, pc.x)) < 35 * DEG) {
        if (r() < 0.8) signRead = { value: sg.value, id: sg.id, p: pc, h: sg.height || 0.75, w: sg.width || 0.6 };
      }
    }
    return { k, tc, pose, lanes, objects, signRead };
  }

  // Apply the stateful drawing rules (3 consecutive frames, hysteresis, persistence) for each new capture.
  ingest(msg) {
    if (!msg) return;
    for (const ln of msg.lanes) {
      const st = this.lineState.get(ln.id) || { shown: false, above: 0, alpha: 0 };
      if (!st.shown) { st.above = ln.conf > 0.6 ? st.above + 1 : 0; if (st.above >= 3) st.shown = true; }
      else if (ln.conf < 0.3) { st.shown = false; st.above = 0; }
      st.alpha = st.shown ? smoothstep(0.3, 0.8, ln.conf) : 0;
      this.lineState.set(ln.id, st);
    }
    const seen = new Set();
    for (const o of msg.objects) {
      seen.add(o.id);
      const tr = this.tracks.get(o.id) || { id: o.id, count: 0, lastSeen: -1e9, firstSeen: msg.tc };
      tr.count = o.conf > 0.5 ? tr.count + 1 : tr.count;
      tr.lastSeen = msg.tc; tr.obj = o; tr.k = msg.k;
      this.tracks.set(o.id, tr);
    }
    for (const [id, tr] of this.tracks) {
      if (!seen.has(id)) { if (msg.tc - tr.lastSeen > 0.4) { tr.count = 0; } if (msg.tc - tr.lastSeen > 2) this.tracks.delete(id); }
    }
    if (msg.signRead) {
      const s = this.sign;
      if (s.cand === msg.signRead.value) s.candCount++; else { s.cand = msg.signRead.value; s.candCount = 1; }
      if (s.candCount >= 2) { s.value = msg.signRead.value; s.t = msg.tc; }
      s.box = msg.signRead;
      s.boxT = msg.tc;
    }
  }

  // ---- per-frame update ------------------------------------------------------------
  // t: sim time (s). env: world.env. sunDirCar: unit vector to the sun in the car frame. eyeOffset: true head offset.
  update(t, dt, { sunDirCar, eyeOffset, ambientLux }) {
    this.t = t;
    const S = this.settings;
    const lat = S.lat;
    const ageCapture = (lat[0] + lat[1] + lat[2]) / 1000;   // camera + inference + publish
    const dDisplay = (lat[3] + lat[4]) / 1000;               // render + scan-out
    this.latency = { ageCapture, dDisplay, total: ageCapture + dDisplay };
    const tDraw = t - dDisplay;                              // when hudd drew the frame now on the panel
    const kNow = Math.floor((tDraw - ageCapture) * S.cameraHz);
    if (this.k < 0) this.k = kNow - 1;
    // process new captures in order (cap the catch-up)
    for (let k = Math.max(this.k + 1, kNow - 8); k <= kNow; k++) { const m = this.capture(k); if (m) { this.ingest(m); this.msg = m; } }
    this.k = Math.max(this.k, kNow);

    // Head: true offset now; tracker reports it 40 ms late with 3 mm noise.
    this.eye.trueOffset.copy(eyeOffset);
    this.eyeHist.push({ t, o: eyeOffset.clone() });
    while (this.eyeHist.length > 2 && this.eyeHist[0].t < t - 1) this.eyeHist.shift();
    const tl = tDraw - S.trackerLatency / 1000;
    let tracked = this.eyeHist[0].o;
    for (const e of this.eyeHist) if (e.t <= tl) tracked = e.o;
    const r = rng(77 + this.frameCount);
    this.eye.tracked.copy(tracked).add(new THREE.Vector3(0, gauss(r) * 0.002, gauss(r) * 0.003));
    this.eye.nominal = !S.headTracking;
    this.eye.used.copy(S.headTracking ? this.eye.tracked : new THREE.Vector3());

    // Luminance and dimming (controllerd)
    this.updateLuminance(dt, ambientLux);
    // Sun-watch and shutter
    this.updateSun(dt, sunDirCar);
    // Thermal (cell) model
    this.updateThermal(dt);

    // Draw the frame
    const t0 = performance.now();
    this.draw(tDraw, t);
    this.stats.render = performance.now() - t0;
    this.texture.needsUpdate = true;
    this.frameCount++;
  }

  updateLuminance(dt, lux) {
    const S = this.settings;
    const stage1 = S.window === 'stage1';
    const src = stage1 ? { key: 'yod', label: 'YODOIT monitor via the 30% combiner', panel: 1200 } : (PGU_SOURCES.find((s) => s.key === S.pgu) || PGU_SOURCES[2]);
    const path = stage1 ? R.PATH_COMB : S.bothSurfaces ? R.PATH_WS_TWO : R.PATH_WS;
    const Lmax = src.panel * path;
    // Dimming curve: night ceiling (50 cd/m2 at the eye) at <= 10 lux, full at >= 10,000 lux, log-linear between.
    const nightDuty = Math.min(1, R.L_NIGHT_EYE / Lmax);
    const f = clamp((Math.log10(Math.max(lux, 1)) - 1) / 3, 0, 1);
    let target = S.autoDim ? Math.exp(lerp(Math.log(nightDuty), 0, f)) : 1;
    target = clamp(target * Math.pow(1.25, S.dimSteps), 0.002, 1);
    if (this.thermal.state === 'derate') target *= 0.5;
    if (this.thermal.state === 'cutoff') target = 0;
    // 1 s ramp
    const k = 1 - Math.exp(-dt / 0.35);
    this.lum.duty += (target - this.lum.duty) * k;
    this.lum.lux = lux;
    this.lum.path = path;
    this.lum.Lpanel = src.panel * this.lum.duty;
    this.lum.Leye = Lmax * this.lum.duty;
    const env = this.world.env || { L_sky: 10000, L_road: 5000 };
    this.lum.contrastSky = (this.lum.Leye + env.L_sky) / env.L_sky;
    this.lum.contrastRoad = (this.lum.Leye + env.L_road) / env.L_road;
    this.lum.black = this.lum.Leye / R.CR_PANEL;
    this.lum.src = src;
  }

  updateSun(dt, sunDirCar) {
    // The entry direction is the HUD ray continued through the glass: opposite of geom.TO_MIRROR (behind, 51 deg up).
    const entry = GM.TO_MIRROR.clone().negate();
    const s = this.sun;
    if (sunDirCar && sunDirCar.y > 0) {
      const el = Math.asin(clamp(sunDirCar.y, -1, 1)), elE = Math.asin(entry.y);
      const az = Math.atan2(sunDirCar.z, sunDirCar.x), azE = Math.atan2(entry.z, entry.x);
      let dAz = az - azE; if (dAz > Math.PI) dAz -= 2 * Math.PI; if (dAz < -Math.PI) dAz += 2 * Math.PI;
      s.dAz = dAz / DEG; s.dEl = (el - elE) / DEG; s.elev = el / DEG;
      const P = this.sunPatch;
      s.inPatch = Math.abs(s.dAz) * Math.cos(el) <= P.azHalf && s.dEl >= P.elMin && s.dEl <= P.elMax;
    } else { s.inPatch = false; s.elev = sunDirCar ? Math.asin(clamp(sunDirCar.y, -1, 1)) / DEG : -10; }
    const sh = this.shutter;
    sh.reason = '';
    sh.target = 1;
    if (this.settings.sunWatch && s.inPatch) { sh.target = 0; sh.reason = `sun-watch: sun inside the entry patch (${this.sunPatch.source})`; }
    if (this.thermal.state === 'cutoff') { sh.target = 0; sh.reason = 'cell over threshold 2'; }
    if (this.powerOff) { sh.target = 0; sh.reason = 'HUD off: fails closed'; }
    const rate = dt / 0.6;                                   // servo travel ~0.6 s
    sh.open += clamp(sh.target - sh.open, -rate, rate);
  }

  updateThermal(dt) {
    // Cell temperature: cabin 30 C + backlight absorption (about 3 W at full, ~+28 C) + focused sun when the shutter is open.
    const sunLoad = this.sun.inPatch ? this.shutter.open * (this.settings.sunWatch ? 1 : 1) * 95 : 0;
    const target = 30 + 24 * this.lum.duty * (this.lum.src ? Math.min(1, this.lum.src.panel / R.L_PANEL_DESIGN) : 1) + sunLoad;
    this.thermal.cell += (target - this.thermal.cell) * (1 - Math.exp(-dt / 20));
    const T1 = 60, T2 = 70;                                  // derate and cut-off thresholds (sim values, ASSUMED)
    this.thermal.T1 = T1; this.thermal.T2 = T2;
    this.thermal.state = this.thermal.cell > T2 ? 'cutoff' : this.thermal.cell > T1 ? 'derate' : 'ok';
  }

  // Scene-linear intensity for the virtual-image quad: the eye luminance relative to the luminance the driver is
  // adapted to, mapped onto the renderer's mid-grey.
  overlayGain(exposure) {
    const env = this.world.env || { L_adapt: 5000 };
    return (this.lum.Leye / env.L_adapt) * (0.18 / Math.max(1e-3, exposure)) * this.shutter.open;
  }

  // ---- hudd: draw the frame -------------------------------------------------------
  draw(tDraw, tNow) {
    const ctx = this.ctx, W = CROP_W, H = CROP_H, S = this.settings;
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
    const m = this.msg; if (!m) return;
    const clutter = S.clutterUntil > tNow;
    const age = tDraw - m.tc;
    this.stats.ageLanes = age; this.stats.ageObjects = age; this.stats.ageEye = S.trackerLatency / 1000 + (tNow - tDraw);
    this.stats.ageEgo = 0.01;
    // stale rule: fade over 300 ms once older than 250 ms, gone at 600 ms
    const staleA = age < 0.25 ? 1 : age > 0.6 ? 0 : 1 - smoothstep(0.25, 0.55, age);
    // compensation to the target time
    const tTarget = S.compensation === 'photon' ? tNow : tDraw;
    const delta = S.compensation === 'off' ? { dx: 0, dz: 0, dpsi: 0 } : this.egoDelta(m.tc, tTarget, 991 + m.k);
    const comp = (p) => HudSim.applyDelta(p, delta);
    const eye = GM.EYE.clone().add(this.eye.used);
    const proj = (p) => this.project(p, eye);

    // lanes
    const lanes = m.lanes.map((ln) => ({ ...ln, pts: ln.pts.map((q) => ({ p: comp(q.p), conf: q.conf })) }));
    const egoL = lanes.find((l) => l.type === 'egoLeft'), egoR = lanes.find((l) => l.type === 'egoRight');
    const stL = egoL && this.lineState.get(egoL.id), stR = egoR && this.lineState.get(egoR.id);
    const drawnL = egoL && (clutter || (stL && stL.shown)), drawnR = egoR && (clutter || (stR && stR.shown));

    // ribbon
    let ribbon = null;
    if ((drawnL || drawnR) && staleA > 0) {
      const far = Math.min(drawnL ? egoL.last : 99, drawnR ? egoR.last : 99, 60);
      const sideL = drawnL ? egoL.pts : null, sideR = drawnR ? egoR.pts : null;
      const xs = [];
      for (let x = 4; x <= far; x += 1.5) xs.push(x);
      const at = (pts, x) => { // interpolate z at x
        for (let i = 1; i < pts.length; i++) { const a = pts[i - 1].p, b = pts[i].p; if ((a.x - x) * (b.x - x) <= 0 && a.x !== b.x) { const f = (x - a.x) / (b.x - a.x); return lerp(a.z, b.z, f); } }
        return null;
      };
      const left = [], right = [];
      for (const x of xs) {
        let zl = sideL ? at(sideL, x) : null, zr = sideR ? at(sideR, x) : null;
        if (zl === null && zr !== null) zl = zr - 3.7;
        if (zr === null && zl !== null) zr = zl + 3.7;
        if (zl === null || zr === null) continue;
        left.push(new THREE.Vector3(x, 0, zl)); right.push(new THREE.Vector3(x, 0, zr));
      }
      if (left.length > 1) {
        const both = drawnL && drawnR;
        ribbon = { left, right, both, far };
        const poly = [...left.map(proj), ...right.slice().reverse().map(proj)].filter(Boolean);
        if (poly.length > 3 && S.ribbon !== 'blank') {
          const g = ctx.createLinearGradient(0, H, 0, 0);
          const a = (both ? 0.32 : 0.2) * staleA;
          g.addColorStop(0, `rgba(70,170,255,${a})`); g.addColorStop(0.75, `rgba(70,170,255,${a * 0.85})`); g.addColorStop(1, `rgba(70,170,255,${a * 0.5})`);
          ctx.fillStyle = g;
          ctx.beginPath(); poly.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.closePath(); ctx.fill();
        }
      }
    }
    this.ribbon = ribbon;

    // lane lines and road edges, faded by confidence
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    for (const ln of lanes) {
      const st = this.lineState.get(ln.id);
      const base = clutter ? 1 : st && st.shown ? st.alpha : 0;
      if (base <= 0.01 || staleA <= 0) continue;
      const egoLine = ln.type !== 'other';
      for (let i = 1; i < ln.pts.length; i++) {
        const a = ln.pts[i - 1], b = ln.pts[i];
        const c = clutter ? 1 : smoothstep(0.3, 0.8, Math.min(a.conf, b.conf));
        if (c <= 0.02) continue;
        const pa = proj(a.p), pb = proj(b.p);
        if (!pa || !pb) continue;
        ctx.strokeStyle = egoLine ? `rgba(225,240,255,${0.95 * base * c * staleA})` : `rgba(160,190,220,${0.6 * base * c * staleA})`;
        ctx.lineWidth = Math.max(6, (egoLine ? 0.18 : 0.12) * 1000 / Math.max(4, a.p.x) * 0.9);
        ctx.beginPath(); ctx.moveTo(pa[0], pa[1]); ctx.lineTo(pb[0], pb[1]); ctx.stroke();
      }
    }

    // tracked objects (persist 400 ms, fade in the last 200 ms; 3 consecutive detections)
    const tracks = [];
    for (const tr of this.tracks.values()) {
      const since = m.tc - tr.lastSeen;
      if (since > 0.4) continue;
      const vis = clutter ? 1 : tr.count >= 3 ? (since < 0.2 ? 1 : 1 - (since - 0.2) / 0.2) : 0;
      if (vis <= 0) continue;
      // advance by the track's own velocity over its age, then compensate ego motion
      const o = tr.obj;
      const adv = o.heading.clone().multiplyScalar((o.speed || 0) * (tTarget - tr.lastSeen) * (S.compensation === 'off' ? 0 : 1));
      const p = comp(o.p.clone().add(adv));
      tracks.push({ tr, o, p, vis: vis * staleA });
    }
    // lead: nearest vehicle whose base is inside the ribbon within 80 m
    let lead = null;
    if (ribbon) {
      for (const t of tracks) {
        if (!['car', 'suv', 'truck', 'bus', 'motorcycle'].includes(t.o.kind)) continue;
        const x = t.p.x; if (x > 80 || x < 3 || x > ribbon.far + 25) continue;
        const i = ribbon.left.findIndex((q) => q.x >= x);
        const L = i >= 0 ? ribbon.left[i] : ribbon.left[ribbon.left.length - 1];
        const Rr = i >= 0 ? ribbon.right[i] : ribbon.right[ribbon.right.length - 1];
        const zc = t.p.z;
        if (zc > L.z - 0.2 && zc < Rr.z + 0.2 && (!lead || x < lead.p.x)) lead = t;
      }
    }
    this.lead = lead;
    const egoPose = this.poseAt(tDraw) || { speed: 0 };
    const v = egoPose.speed;
    const drawChevron = (t, withText) => {
      const x = t.p.x, z = t.p.z;
      const pts = [[x - 2.6, z - 0.95], [x - 1.0, z], [x - 2.6, z + 0.95], [x - 3.3, z + 0.95], [x - 1.9, z], [x - 3.3, z - 0.95]]
        .map(([a, b]) => proj(new THREE.Vector3(a, 0, b))).filter(Boolean);
      if (pts.length < 6) return;
      ctx.fillStyle = `rgba(255,190,90,${0.95 * t.vis})`;
      ctx.beginPath(); pts.forEach(([a, b], i) => (i ? ctx.lineTo(a, b) : ctx.moveTo(a, b))); ctx.closePath(); ctx.fill();
      if (withText) {
        const gap = Math.max(0, x - FRONT_BUMPER_X);
        const txt = v > 3 ? `${gap.toFixed(0)} m · ${(gap / v).toFixed(1)} s` : `${gap.toFixed(0)} m`;
        const base = proj(new THREE.Vector3(x - 3.6, 0, z));
        if (base) {
          ctx.font = '700 30px "Helvetica Neue", Helvetica, Arial, sans-serif';
          ctx.textAlign = 'center'; ctx.textBaseline = 'top';
          ctx.fillStyle = `rgba(255,214,150,${t.vis})`;
          ctx.fillText(txt, base[0], Math.min(H - 34, base[1] + 4));
        }
      }
    };
    if (lead) drawChevron(lead, true);
    if (clutter) for (const t of tracks) if (t !== lead && ['car', 'suv', 'truck', 'bus', 'motorcycle'].includes(t.o.kind)) drawChevron(t, true);
    // hazards: pedestrians, cyclists (and every track in clutter mode)
    for (const t of tracks) {
      const isHaz = t.o.kind === 'person' || t.o.kind === 'bicycle';
      if (!isHaz && !clutter) continue;
      if (t === lead) continue;
      const box = projBox(t.p, t.o, proj);
      if (!box) continue;
      ctx.strokeStyle = isHaz ? `rgba(255,140,60,${t.vis})` : `rgba(200,220,255,${0.7 * t.vis})`;
      ctx.lineWidth = 6;
      roundRect(ctx, box[0] - 6, box[1] - 6, box[2] - box[0] + 12, box[3] - box[1] + 12, 8); ctx.stroke();
    }
    // speed-limit sign outline (informational)
    const sb = this.sign.box;
    if (sb && m.tc - this.sign.boxT < 0.4) {
      const c = comp(sb.p);
      const tl = proj(c.clone().add(new THREE.Vector3(0, sb.h / 2, -sb.w / 2))), br = proj(c.clone().add(new THREE.Vector3(0, -sb.h / 2, sb.w / 2)));
      if (tl && br) { ctx.strokeStyle = 'rgba(200,230,255,0.75)'; ctx.lineWidth = 6; roundRect(ctx, tl[0] - 6, tl[1] - 6, br[0] - tl[0] + 12, br[1] - tl[1] + 12, 6); ctx.stroke(); }
    }

    // speed block: fixed, non-conformal, low in the window
    this.drawSpeedBlock(ctx, tNow, v);

    // registration residuals (for the audience view): drawn vs true, seen from the true eye now
    this.computeResidual(tNow, lead, egoR, comp, proj);

    // clutter label
    if (clutter) {
      ctx.font = '700 22px "Helvetica Neue", Helvetica, Arial, sans-serif'; ctx.fillStyle = 'rgba(255,255,255,0.8)'; ctx.textAlign = 'right'; ctx.textBaseline = 'top';
      ctx.fillText('CLUTTER MODE (demo)', W - 16, 12);
    }
  }

  drawSpeedBlock(ctx, tNow, v) {
    const S = this.settings, H = CROP_H;
    const x = 26, y = H - 112, w = 300, h = 92;
    const fix = !S.gnssOutage;
    const speedMeas = fix ? Math.max(0, v + 0.05 * snoise(tNow * 3, 9)) : null;
    ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'left';
    ctx.fillStyle = 'rgba(255,255,255,0.97)';
    ctx.font = '800 64px "Helvetica Neue", Helvetica, Arial, sans-serif';
    const txt = speedMeas === null ? '–' : speedMeas < 1 ? '0' : String(Math.round(speedMeas * MPH));
    ctx.fillText(txt, x, y + 66);
    const tw = ctx.measureText(txt).width;
    ctx.font = '700 20px "Helvetica Neue", Helvetica, Arial, sans-serif';
    ctx.fillText('mph', x + tw + 8, y + 40);
    // fix glyph (satellite dot with arcs), dimmed when no fix
    ctx.strokeStyle = fix ? 'rgba(160,255,200,0.95)' : 'rgba(255,160,120,0.95)'; ctx.lineWidth = 4;
    const gx = x + tw + 22, gy = y + 60;
    ctx.beginPath(); ctx.arc(gx, gy, 4, 0, 7); ctx.stroke();
    ctx.beginPath(); ctx.arc(gx, gy, 12, -2.2, -0.9); ctx.stroke();
    if (!fix) { ctx.beginPath(); ctx.moveTo(gx - 12, gy + 8); ctx.lineTo(gx + 12, gy - 16); ctx.stroke(); }
    // last speed-limit value (10 min timeout)
    const lim = this.sign.value && tNow - this.sign.t < 600 ? this.sign.value : null;
    const lx = x + tw + 70, ly = y + 6;
    ctx.strokeStyle = 'rgba(255,255,255,0.95)'; ctx.lineWidth = 4;
    roundRect(ctx, lx, ly, 62, 72, 8); ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.95)'; ctx.textAlign = 'center';
    ctx.font = '700 11px "Helvetica Neue", Helvetica, Arial, sans-serif';
    ctx.fillText('SPEED', lx + 31, ly + 17); ctx.fillText('LIMIT', lx + 31, ly + 30);
    ctx.font = '800 30px "Helvetica Neue", Helvetica, Arial, sans-serif';
    ctx.fillText(lim ? String(lim) : '–', lx + 31, ly + 62);
    // status glyphs: head tracker on nominal eye
    if (this.eye.nominal || !this.settings.headTracking) {
      ctx.strokeStyle = 'rgba(255,200,120,0.95)'; ctx.lineWidth = 4;
      const ex = lx + 94, ey = ly + 36;
      ctx.beginPath(); ctx.ellipse(ex, ey, 16, 9, 0, 0, 7); ctx.stroke();
      ctx.beginPath(); ctx.arc(ex, ey, 4, 0, 7); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(ex - 18, ey + 14); ctx.lineTo(ex + 18, ey - 14); ctx.stroke();
    }
    ctx.textAlign = 'left';
  }

  computeResidual(tNow, lead, egoR, comp, proj) {
    // Truth now, from the true eye, against what was drawn.
    const poseNow = this.poseAt(tNow);
    const eyeTrue = GM.EYE.clone().add(this.eye.trueOffset);
    const errs = {};
    if (lead) {
      const a = this.world.agents.find((q) => q.id === lead.o.id);
      if (a) {
        const truth = this.toCar(a.worldPosition(), poseNow);
        const drawn = proj(lead.p);
        this.stats.drawnLead = drawn;
        const onCanvas = (q) => q && q[0] >= 0 && q[0] <= CROP_W && q[1] >= 0 && q[1] <= CROP_H;   // only a displayed symbol can be misregistered
        if (onCanvas(drawn)) {
          // what the eye sees: the drawn pixel through the optics from the true eye (the plane model kept beside it)
          const dDrawn = this.traceDir(drawn[0], drawn[1], eyeTrue);
          const dFlat = this.pixelDir(drawn[0], drawn[1], eyeTrue);
          const dTrue = truth.clone().sub(eyeTrue).normalize();
          errs.lead = Math.acos(clamp(dDrawn.dot(dTrue), -1, 1)) / DEG;
          errs.leadFlat = Math.acos(clamp(dFlat.dot(dTrue), -1, 1)) / DEG;
          errs.binLead = this.binocularConflict(drawn, truth, eyeTrue);
        }
      }
    }
    if (egoR) {
      // the lane point nearest 20 m
      const q = egoR.pts.reduce((b, c) => (Math.abs(c.p.x - 20) < Math.abs(b.p.x - 20) ? c : b), egoR.pts[0]);
      if (q) {
        const drawnP = comp(q.p);
        const drawn = proj(drawnP);
        this.stats.drawnLane = drawn;
        // truth: the line's world point at the station where it was drawn, now (along-line error is invisible)
        const s = poseNow.s + drawnP.x;
        const truth = this.toCar(this.world.linePoint(egoR.line, s), poseNow);
        if (drawn && drawn[0] >= 0 && drawn[0] <= CROP_W && drawn[1] >= 0 && drawn[1] <= CROP_H) {
          const dDrawn = this.traceDir(drawn[0], drawn[1], eyeTrue);
          const dFlat = this.pixelDir(drawn[0], drawn[1], eyeTrue);
          const dTrue = truth.clone().sub(eyeTrue).normalize();
          // lateral component only (along-line error on a straight line is invisible)
          errs.lane = Math.acos(clamp(dDrawn.dot(dTrue), -1, 1)) / DEG;
          errs.laneFlat = Math.acos(clamp(dFlat.dot(dTrue), -1, 1)) / DEG;
          errs.binLane = this.binocularConflict(drawn, truth, eyeTrue);
        }
      }
    }
    // the window marks: four fixed road points (16 and 24 m ahead, 1 m left and right, the Cycles check's marks), scored
    // whenever they are inside the window, so the sway test has a number that does not depend on the traffic
    const marks = [[16, 0, 1], [16, 0, -1], [24, 0, 1], [24, 0, -1]];
    let worst = null;
    for (const q of marks) {
      const P = new THREE.Vector3(q[0], q[1], q[2]);
      const d = proj(P);
      if (!(d && d[0] >= 0 && d[0] <= CROP_W && d[1] >= 0 && d[1] <= CROP_H)) continue;
      const e = Math.acos(clamp(this.traceDir(d[0], d[1], eyeTrue).dot(P.clone().sub(eyeTrue).normalize()), -1, 1)) / DEG;
      worst = worst === null ? e : Math.max(worst, e);
    }
    errs.marks = worst;
    const k = 0.15;
    if (errs.lead !== undefined) this.stats.residualLead = lerp(this.stats.residualLead || errs.lead, errs.lead, k); else this.stats.residualLead = null;
    if (errs.lane !== undefined) this.stats.residualLane = lerp(this.stats.residualLane || errs.lane, errs.lane, k); else this.stats.residualLane = null;
    if (errs.marks !== null) this.stats.residualMarks = lerp(this.stats.residualMarks || errs.marks, errs.marks, k); else this.stats.residualMarks = null;
    if (errs.binLead !== undefined) this.stats.binocularLead = lerp(this.stats.binocularLead || errs.binLead, errs.binLead, k);
    if (errs.binLane !== undefined) this.stats.binocularLane = lerp(this.stats.binocularLane || errs.binLane, errs.binLane, k);
    if (errs.leadFlat !== undefined) this.stats.residualLeadFlat = lerp(this.stats.residualLeadFlat || errs.leadFlat, errs.leadFlat, k);
    if (errs.laneFlat !== undefined) this.stats.residualLaneFlat = lerp(this.stats.residualLaneFlat || errs.laneFlat, errs.laneFlat, k);
    this.stats.residual = Math.max(this.stats.residualLead || 0, this.stats.residualLane || 0, this.stats.residualMarks || 0);
  }

  // Vergence conflict between a drawn symbol and the thing it marks, in arcminutes: the two eyes (65 mm apart,
  // centred on the true eye) converge on the symbol at its image-surface point and on the object at its distance;
  // the difference is the horizontal disparity the driver must fuse. Beyond Panum's area (about 10' for fine targets,
  // 20' coarse; ASSUMED limits) the symbol or the object doubles, whichever is not fixated.
  binocularConflict(drawnPx, truth, eyeTrue) {
    const half = new THREE.Vector3(0, 0, 0.0325);
    const eL = eyeTrue.clone().sub(half), eR = eyeTrue.clone().add(half);
    const vergSymbol = Math.acos(clamp(this.traceDir(drawnPx[0], drawnPx[1], eL).dot(this.traceDir(drawnPx[0], drawnPx[1], eR)), -1, 1));
    const vergObject = Math.acos(clamp(truth.clone().sub(eL).normalize().dot(truth.clone().sub(eR).normalize()), -1, 1));
    return Math.abs(vergSymbol - vergObject) / DEG * 60;
  }

  // Coarse eye-box vignette: which parts of the window reach the eye through the 300 x 200 mm mirror.
  vignette(eyeOffset, cols = 13, rows = 7) {
    const e = GM.EYE.clone().add(eyeOffset);
    const out = [];
    for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) {
      const px = (i + 0.5) / cols * CROP_W, py = (j + 0.5) / rows * CROP_H;
      const d = this.pixelDir(px, py, e);
      const r = GM.traceFromEye(e, d);
      out.push(r && rayReaches(r) ? 1 : 0);          // the mirror, the fold glass and the lid aperture, as Cycles sees them
    }
    return { cols, rows, data: out };
  }
}

function projBox(p, o, proj) {
  const hx = (o.kind === 'person' ? 0.3 : o.kind === 'bicycle' ? 0.9 : o.length / 2), hz = (o.width || 0.6) / 2, h = o.height || 1.7;
  const corners = [];
  for (const dx of [-hx, hx]) for (const dz of [-hz, hz]) for (const y of [0, h]) corners.push(new THREE.Vector3(p.x + dx, y, p.z + dz));
  const pts = corners.map(proj).filter(Boolean);
  if (pts.length < 8) return null;
  const xs = pts.map((q) => q[0]), ys = pts.map((q) => q[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

// The window the specified hardware actually produces: solve for the field angles that land on the crop corners.
export function tracedWindow() {
  const target = { tl: [-0.03, -0.015], tr: [0.03, -0.015], bl: [-0.03, 0.015], br: [0.03, 0.015] };   // [z, x] on the panel; image top lands at -x
  const res = {};
  for (const [k, [tz, tx]] of Object.entries(target)) {
    let ax = Math.sign(tz) * GM.FOV_W / 2 * 0.8, ay = (tx < 0 ? 1 : -1) * GM.FOV_H / 2 * 0.8;
    for (let it = 0; it < 30; it++) {
      const f = (a, b) => { const r = GM.traceFromEye(GM.EYE, GM.fieldDir(a, b)); return r ? [r.panelZ, r.panelX] : [NaN, NaN]; };
      const [z0, x0] = f(ax, ay);
      const h = 1e-4;
      const [z1, x1] = f(ax + h, ay), [z2, x2] = f(ax, ay + h);
      const J = [[(z1 - z0) / h, (z2 - z0) / h], [(x1 - x0) / h, (x2 - x0) / h]];
      const det = J[0][0] * J[1][1] - J[0][1] * J[1][0];
      const ez = tz - z0, ex = tx - x0;
      ax += (J[1][1] * ez - J[0][1] * ex) / det; ay += (-J[1][0] * ez + J[0][0] * ex) / det;
    }
    res[k] = [ax, ay];
  }
  const { vt, vs, eyeToMirror } = GM.mirrorImages();
  const dist = eyeToMirror - (vt + vs) / 2;                 // virtual image distance from the eye
  const halfW = Math.min(Math.abs(res.tl[0]), Math.abs(res.tr[0]), Math.abs(res.bl[0]), Math.abs(res.br[0]));
  const halfH = Math.min(Math.abs(res.tl[1]), Math.abs(res.bl[1]), Math.abs(res.tr[1]), Math.abs(res.br[1]));
  return {
    dist, corners: res,
    w: 2 * dist * Math.tan(halfW), h: 2 * dist * Math.tan(halfH),
    fovW: 2 * halfW / DEG, fovH: 2 * halfH / DEG,
    topW: (Math.abs(res.tl[0]) + Math.abs(res.tr[0])) / DEG, botW: (Math.abs(res.bl[0]) + Math.abs(res.br[0])) / DEG,
  };
}
