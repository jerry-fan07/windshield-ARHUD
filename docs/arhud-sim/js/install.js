// The garage: one world, one car, every component installed at its mount point, the cable runs, the HUD software,
// and the virtual-image meshes. The Driver view, Vehicle and Build modes all share it.
import * as THREE from 'three';
import * as GM from './geom.js';
import { M, C } from './mats.js';
import { build, available, setExplode } from './registry.js';
import { tube, DEG } from './util.js';
import { HudSim, CROP_W, CROP_H } from './hud.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);

// Orientation that turns local +X toward dir, keeping +Y as close to up as possible.
function aim(dir, up = V(0, 1, 0)) {
  const x = dir.clone().normalize();
  const z = new THREE.Vector3().crossVectors(x, up).normalize();
  const y = new THREE.Vector3().crossVectors(z, x).normalize();
  return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(x, y, z));
}

// Where each component goes in the car. pos in the simulation car frame; quat optional.
export const MOUNTS = {
  hudUnit: { pos: V(0, 0, 0), note: 'dash top, in front of the driver, removable without tools' },
  zed2i: { pos: GM.ROAD_CAM.clone(), quat: new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0, -2 * DEG)), note: 'high on the windshield centreline, clamped to the mirror stalk' },
  oakdPro: { pos: GM.DRIVER_CAM.clone(), quat: aim(GM.EYE.clone().sub(GM.DRIVER_CAM)), note: 'column shroud, aimed at the driver' },
  gnssAntenna: { pos: GM.GNSS_ANT.clone(), note: 'dash top near the glass, passenger side' },
  zedF9r: { pos: GM.JETSON.clone().add(V(0.0, 0.0, -0.17)), quat: new THREE.Quaternion(), note: 'passenger footwell, beside the Jetson' },
  jetson: { pos: GM.JETSON.clone(), quat: new THREE.Quaternion().setFromEuler(new THREE.Euler(0, Math.PI / 2, 0)), note: 'passenger footwell bracket' },
  dcdc: { pos: GM.DCDC.clone(), note: 'under the dash, centre' },
  ethSwitch: { pos: GM.SWITCH.clone(), note: 'passenger footwell' },
  fuseTap: { pos: GM.ACC_SOCKET.clone(), quat: new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0, 0)), note: 'centre-console 12 V accessory socket, fused' },
  pdCharger: { pos: GM.ACC_SOCKET.clone().add(V(-0.08, 0.0, 0.12)), note: 'second accessory socket' },
  miniPC: { pos: GM.MINIPC2.clone(), quat: new THREE.Quaternion().setFromEuler(new THREE.Euler(0, Math.PI, 0)), note: 'behind the passenger seat' },
  monitor: { pos: GM.MONITOR2.clone(), quat: new THREE.Quaternion().setFromEuler(new THREE.Euler(0, Math.PI, 0)), note: 'back of the passenger headrest, for the audience' },
  controller: { pos: V(GM.HOUSING.xMin + 0.11, GM.HOUSING.floor + 0.004, GM.HOUSING.zMin - 0.06), quat: new THREE.Quaternion(), note: 'beside the housing, ambient sensor at the dust cover' },
  ledDriver: { pos: V(GM.HOUSING.xMin - 0.035, GM.HOUSING.floor + 0.004, 0.10), quat: new THREE.Quaternion(), note: 'behind the housing' },
};

// Refine the mount points with the car's own anchors (shroud top, floor, headrest posts, socket axis).
function adjustMounts(car) {
  const a = car.anchors || {};
  const floorY = a.floor ? a.floor.y : 0.135;
  if (a.driverCam) {
    const p = a.driverCam.position.clone().addScaledVector(a.driverCam.up, 0.046);   // OAK-D origin is 46 mm above its base
    MOUNTS.oakdPro.pos = p;
    MOUNTS.oakdPro.quat = aim(GM.EYE.clone().sub(p), a.driverCam.up);
  }
  for (const id of ['jetson', 'dcdc', 'ethSwitch', 'zedF9r', 'miniPC']) MOUNTS[id].pos.y = floorY;
  if (a.monitor2) MOUNTS.monitor.pos = a.monitor2.position.clone().add(V(-0.035, -0.255, 0));
  if (a.gnssDash) MOUNTS.gnssAntenna.pos = a.gnssDash.position.clone();
  if (a.accSocket) {
    const n = a.accSocket.normal.clone().normalize();
    MOUNTS.fuseTap.pos = a.accSocket.position.clone();
    MOUNTS.fuseTap.quat = aim(n.clone().negate());               // plug tip (+X) goes into the socket
    MOUNTS.fuseTap.leadEnd = a.accSocket.position.clone().addScaledVector(n, 0.27);
  }
  MOUNTS.pdCharger.pos = V(-0.47, 0.42, GM.CAR_CENTER_Z);          // rear-console socket, ports facing the rear seats
  MOUNTS.pdCharger.quat = aim(V(1, 0, 0));
  const dy = car.dashTopY ? car.dashTopY(0.80, 0.24) : NaN;
  MOUNTS.ledDriver.pos = V(0.80, isFinite(dy) ? dy : GM.HOUSING.floor, 0.245);
  const cy = car.dashTopY ? car.dashTopY(0.76, -0.26) : NaN;
  MOUNTS.controller.pos = V(0.76, isFinite(cy) ? cy : GM.HOUSING.floor, -0.26);
}

// Cable runs, in the car frame. kind: power, usb, hdmi, eth, serial, rf.
function cableRuns() {
  const cz = GM.CAR_CENTER_Z;
  const J = MOUNTS.jetson.pos.clone();
  const jIn = (dx = 0, dy = 0.03) => J.clone().add(V(dx, dy, -0.07));   // I/O face toward the console
  const pillarTop = V(GM.WS_TOP_X - 0.02, GM.ROOF_Y - 0.03, cz + 0.70);
  const pillarBot = V(GM.WS_BOTTOM_X - 0.12, GM.COWL_Y + 0.02, cz + 0.74);
  const zedEnd = GM.ROAD_CAM.clone().add(V(-0.02, 0.0, 0.15));
  return [
    { id: 'usbZed', kind: 'usb', label: 'ZED 2i USB 3 to the Jetson', pts: [zedEnd, V(GM.ROAD_CAM.x - 0.08, GM.ROOF_Y - 0.02, cz + 0.25), V(GM.WS_TOP_X - 0.06, GM.ROOF_Y - 0.03, cz + 0.55), pillarTop, V((pillarTop.x + pillarBot.x) / 2, (pillarTop.y + pillarBot.y) / 2, cz + 0.73), pillarBot, V(0.95, 0.55, cz + 0.70), V(0.75, 0.30, cz + 0.62), jIn(0.04)] },
    { id: 'usbOak', kind: 'usb', label: 'OAK-D Pro USB 3 to the Jetson', pts: [MOUNTS.oakdPro.pos.clone().add(V(0.03, -0.02, 0)), V(0.55, 0.74, 0.0), V(0.60, 0.55, 0.06), V(0.62, 0.32, 0.25), V(0.62, 0.22, cz + 0.20), jIn(-0.02)] },
    { id: 'rfGnss', kind: 'rf', label: 'GNSS antenna coax to the ZED-F9R', pts: [MOUNTS.gnssAntenna.pos.clone(), V(MOUNTS.gnssAntenna.pos.x - 0.08, MOUNTS.gnssAntenna.pos.y - 0.03, MOUNTS.gnssAntenna.pos.z + 0.1), V(1.0, 0.62, cz + 0.62), V(0.80, 0.30, cz + 0.42), MOUNTS.zedF9r.pos.clone().add(V(0, 0.02, 0))] },
    { id: 'usbGnss', kind: 'usb', label: 'ZED-F9R USB to the Jetson', pts: [MOUNTS.zedF9r.pos.clone().add(V(-0.02, 0.02, 0.02)), V(J.x - 0.02, J.y + 0.06, J.z - 0.10), jIn(-0.06)] },
    { id: 'hdmi', kind: 'hdmi', label: 'HDMI, Jetson to the panel board (1920 × 1080 at 60 Hz)', pts: [jIn(0.0, 0.05), V(0.55, 0.38, cz + 0.12), V(0.62, 0.62, 0.10), V(GM.HOUSING.xMin - 0.02, GM.HOUSING.floor - 0.02, 0.06), V(GM.HOUSING.xMin + 0.02, GM.HOUSING.floor + 0.03, 0.06)] },
    { id: 'serial', kind: 'serial', label: 'USB serial, Jetson to the HUD controller', pts: [jIn(0.02, 0.06), V(0.55, 0.40, cz + 0.05), V(0.62, 0.66, -0.10), V(MOUNTS.controller.pos.x - 0.06, GM.HOUSING.floor - 0.02, MOUNTS.controller.pos.z), MOUNTS.controller.pos.clone().add(V(-0.03, 0.01, 0))] },
    { id: 'p12', kind: 'power', label: '12 V accessory feed, fused, to the DC-DC converter', pts: [(MOUNTS.fuseTap.leadEnd || GM.ACC_SOCKET).clone(), V(GM.ACC_SOCKET.x - 0.05, 0.30, GM.ACC_SOCKET.z + 0.06), V(MOUNTS.dcdc.pos.x - 0.05, MOUNTS.dcdc.pos.y + 0.02, MOUNTS.dcdc.pos.z - 0.04), MOUNTS.dcdc.pos.clone().add(V(-0.04, 0.01, 0))] },
    { id: 'pJetson', kind: 'power', label: 'Converter output to the Jetson (9–19 V input)', pts: [MOUNTS.dcdc.pos.clone().add(V(0.04, 0.01, 0)), V(MOUNTS.dcdc.pos.x + 0.06, 0.18, MOUNTS.dcdc.pos.z + 0.12), jIn(0.05, 0.0)] },
    { id: 'pLed', kind: 'power', label: 'Converter output to the LED driver', pts: [MOUNTS.dcdc.pos.clone().add(V(0.0, 0.03, -0.03)), V(0.55, 0.45, 0.20), V(0.62, 0.70, 0.12), MOUNTS.ledDriver.pos.clone().add(V(-0.02, 0.01, 0))] },
    { id: 'eth', kind: 'eth', label: 'Ethernet, Jetson to the switch to mini PC 2 (audience stream)', pts: [jIn(-0.03, 0.05), V(MOUNTS.ethSwitch.pos.x + 0.04, MOUNTS.ethSwitch.pos.y + 0.02, MOUNTS.ethSwitch.pos.z), V(0.0, 0.12, cz + 0.55), V(-0.40, 0.14, cz + 0.45), MOUNTS.miniPC.pos.clone().add(V(0.06, 0.0, 0))] },
    { id: 'pdPC', kind: 'power', label: 'USB-C PD to mini PC 2 and monitor 2', pts: [MOUNTS.pdCharger.pos.clone(), V(0.1, 0.3, cz + 0.12), V(-0.3, 0.18, cz + 0.25), MOUNTS.miniPC.pos.clone().add(V(0.06, 0.02, -0.03))] },
    { id: 'video', kind: 'usb', label: 'USB-C video, mini PC 2 to monitor 2', pts: [MOUNTS.miniPC.pos.clone().add(V(0, 0.03, 0)), V(-0.50, 0.65, cz + 0.40), MOUNTS.monitor.pos.clone().add(V(0.02, -0.12, 0))] },
  ];
}

const CABLE_MAT = { power: () => M.cableRed, usb: () => M.cableBlue, hdmi: () => M.cableOrange, eth: () => M.cableGreen, serial: () => M.color(0x8a5cc9, 0.55), rf: () => M.cableBlack };
export const CABLE_COLORS = { power: C.power, usb: C.usb, hdmi: C.hdmi, eth: C.eth, serial: C.serial, rf: 0x9aa3ad };
export const CABLE_NAMES = { power: '12 V and DC power', usb: 'USB', hdmi: 'HDMI video', eth: 'Ethernet', serial: 'USB serial', rf: 'GNSS coax' };

export class Garage {
  constructor(app) { this.app = app; }

  async init() {
    const { World } = await import('./world.js');
    const { buildEgoCar } = await import('./car.js');
    this.world = new World();
    this.scene = this.world.scene;
    // Image-based lighting baked by Blender (docs/arhud-blender/bake_sky.py). Without the maps the world keeps its
    // analytic lights only.
    if (!/[#&]noibl\b/.test(location.hash)) {                 // &noibl on the hash shows the analytic lights alone
      try {
        const { SkyIBL } = await import('./assets.js');
        this.world.ibl = new SkyIBL(this.app.renderer);
        if (await this.world.ibl.load()) this.world.applyIBL();
      } catch (e) { console.warn('sky IBL unavailable:', e); }
    }
    this.car = buildEgoCar();
    // The Blender-baked copy of the car's static parts (docs/arhud-blender/car_bake.py): smoothed, with ambient
    // occlusion in vertex colours. Each part replaces its procedural twin only while the two still match; &noglb
    // on the hash keeps the procedural car.
    if (!/[#&]noglb\b/.test(location.hash)) {
      try {
        const { applyBakedCar, applyBodyShell } = await import('./car-glb.js');
        const st = await applyBakedCar(this.car);
        console.info('baked car:', st.replaced, 'parts replaced,', st.skipped, 'skipped', st.reasons);
        // the body shell modelled from scratch in Blender (car_body.py) over the procedural exterior
        try { const sh = await applyBodyShell(this.car); console.info('body shell:', sh.halves, 'halves,', sh.hidden, 'procedural parts hidden'); } catch (e) { console.warn('body shell unavailable:', e && e.message ? e.message : e); }
      } catch (e) { console.warn('baked car unavailable:', e && e.message ? e.message : e); }
    }
    this.carGroup = this.car.group;
    this.scene.add(this.carGroup);
    adjustMounts(this.car);
    this.installed = {};
    this.installGroup = new THREE.Group(); this.installGroup.name = 'installed';
    this.carGroup.add(this.installGroup);
    for (const [id, m] of Object.entries(MOUNTS)) {
      if (!available(id)) continue;
      let comp;
      try { comp = build(id, { installed: true }); } catch (e) { console.error('install', id, e); continue; }
      if (!comp) continue;
      const holder = new THREE.Group(); holder.name = 'mount:' + id;
      holder.position.copy(m.pos);
      if (m.quat) holder.quaternion.copy(m.quat);
      holder.add(comp.group);
      holder.userData.pickId = id;
      this.installGroup.add(holder);
      comp.setWorking(false);
      this.installed[id] = { comp, holder, mount: m, home: holder.position.clone() };
    }
    // Inspection lights for the cutaway views (off while driving)
    this.workLights = new THREE.Group(); this.workLights.name = 'workLights';
    const wl1 = new THREE.PointLight(0xffffff, 0.5, 4, 1.6); wl1.position.set(0.2, 1.3, -0.2);
    const wl2 = new THREE.PointLight(0xdfe8ff, 0.35, 4, 1.6); wl2.position.set(0.9, 1.0, 0.6);
    const wl3 = new THREE.PointLight(0xffffff, 0.25, 3, 1.6); wl3.position.set(0.3, 0.45, 0.6);
    this.workLights.add(wl1, wl2, wl3); this.workLights.visible = false;
    this.carGroup.add(this.workLights);
    // Cables
    this.cables = [];
    this.cableGroup = new THREE.Group(); this.cableGroup.name = 'cables';
    this.carGroup.add(this.cableGroup);
    for (const run of cableRuns()) {
      const mesh = tube(run.pts, run.kind === 'hdmi' ? 0.0042 : run.kind === 'power' ? 0.0035 : 0.003, CABLE_MAT[run.kind](), 120);
      mesh.userData.pickId = 'cable:' + run.id;
      this.cableGroup.add(mesh);
      const count = mesh.geometry.index.count;
      this.cables.push({ ...run, mesh, curve: mesh.userData.curve, count, length: mesh.userData.curve.getLength() });
    }
    // Installed parts are small and inside the cabin: their shadows are invisible but cost a draw call each.
    for (const v of Object.values(this.installed)) v.holder.traverse((o) => { if (o.isMesh) o.castShadow = false; });
    for (const cab of this.cables) cab.mesh.castShadow = false;
    // HUD software and the virtual image
    this.hud = new HudSim(this.world);
    // The sun-watch patch: the plan's figure, or the wider set of sun directions that the Blender sun trace found
    // lighting the whole cell (assets/cycles/sun_focus.json), when it is available.
    try {
      const { loadSunFocus } = await import('./cycles.js');
      const sf = await loadSunFocus();
      const c = sf && sf.patch && sf.patch.cellHot;
      if (c && c.elevation && c.azimuth) {
        this.hud.sunPatch = { azHalf: Math.max(Math.abs(c.azimuth[0]), Math.abs(c.azimuth[1])), elMin: c.elevation[0] - sf.nominalElevationDeg, elMax: c.elevation[1] - sf.nominalElevationDeg, source: 'Blender sun trace, whole cell' };
      }
    } catch (e) { /* the plan's patch stays */ }
    this.makeVirtualImage();
    // Driving state
    this.ego = { s: 140, offset: this.world.lanes.ego.center, speed: 0, wander: 0 };
    this.placeEgo(0);
    // live panel texture on the PGU, audience view on monitor 2
    const unit = this.installed.hudUnit;
    if (unit && unit.comp.handles && unit.comp.handles.setPanelTexture) unit.comp.handles.setPanelTexture(this.hud.texture);
    this.audience = document.createElement('canvas'); this.audience.width = 960; this.audience.height = 600;
    this.audienceTex = new THREE.CanvasTexture(this.audience); this.audienceTex.colorSpace = THREE.SRGBColorSpace;
    const mon = this.installed.monitor;
    if (mon && mon.comp.handles && mon.comp.handles.setScreenTexture) mon.comp.handles.setScreenTexture(this.audienceTex);
  }

  // The virtual image: the HUD frame on a plane in front of the eye (additive light), its ghost, and the cell's
  // black-level glow over the whole window.
  makeVirtualImage() {
    const g = this.vimg = new THREE.Group(); g.name = 'virtualImage';
    const mk = (opacity) => new THREE.MeshBasicMaterial({ map: this.hud.texture, transparent: true, opacity, blending: THREE.AdditiveBlending, depthTest: false, depthWrite: false, toneMapped: true, color: 0xffffff });
    this.vimgMain = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mk(1));
    this.vimgGhost = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mk((1 - 0.2357) ** 2));
    this.vimgBlack = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, blending: THREE.AdditiveBlending, depthTest: false, depthWrite: false }));
    // eye-box vignette as an alpha map
    this.vigCanvas = document.createElement('canvas'); this.vigCanvas.width = 13; this.vigCanvas.height = 7;
    this.vigTex = new THREE.CanvasTexture(this.vigCanvas); this.vigTex.magFilter = THREE.LinearFilter; this.vigTex.minFilter = THREE.LinearFilter;
    for (const m of [this.vimgMain, this.vimgGhost, this.vimgBlack]) { m.material.alphaMap = this.vigTex; m.renderOrder = 50; m.frustumCulled = false; g.add(m); }
    this.vimgBlack.renderOrder = 49;
    this.carGroup.add(g);
    g.visible = false;
    this.layoutVirtualImage();
  }

  layoutVirtualImage(ghostScale = 1) {
    const pl = this.hud.plane;
    this._ghostScale = ghostScale;
    const basis = new THREE.Matrix4().makeBasis(GM.VIMG_RIGHT, GM.VIMG_UP, GM.VIMG_N);
    const q = new THREE.Quaternion().setFromRotationMatrix(basis);
    // The traced window is drawn on the image surface the optics make, not on a plane: for each grid point of the
    // window, the sagittal image distance along the nominal eye's ray (local Coddington at the mirror hit, as the
    // Cycles section computes it and Cycles confirmed: 6 to 19 m across the toroid's window). From the nominal eye
    // the picture is identical; when the head moves, each part of the image swims against the road by its own
    // distance, as it does in the car. The spec and stage-1 windows stay the planes they are defined as.
    const NX = 24, NY = 12;
    const surf = this.hud.settings.window === 'traced' ? this.imageSurface(pl, NX, NY) : null;
    this.vimgSurface = surf;
    const ghostOff = GM.VIMG_UP.clone().multiplyScalar((3.1137 / 1000) * ghostScale);
    // the black-level glow is the whole lit crop, which the optics keystone (wider at the bottom); the content stays
    // on the inscribed rectangle hudd draws into. Map the crop's edges through the trace for the glow's outline.
    const cropSurf = surf ? this.cropSurface(NX, NY) : null;
    for (const m of [this.vimgMain, this.vimgGhost, this.vimgBlack]) {
      if (surf) {
        if (!m.userData.grid) { m.geometry.dispose(); m.geometry = new THREE.PlaneGeometry(1, 1, NX, NY); m.userData.grid = true; }
        const pos = m.geometry.attributes.position;
        const off = m === this.vimgGhost ? ghostOff : null;
        const pts = (m === this.vimgBlack && cropSurf) ? cropSurf.points : surf.points;
        for (let k = 0; k < pos.count; k++) { const pt = pts[k]; pos.setXYZ(k, pt.x + (off ? off.x : 0), pt.y + (off ? off.y : 0), pt.z + (off ? off.z : 0)); }
        pos.needsUpdate = true;
        m.geometry.computeBoundingSphere();
        m.quaternion.identity(); m.scale.set(1, 1, 1); m.position.set(0, 0, 0);
      } else {
        if (m.userData.grid) { m.geometry.dispose(); m.geometry = new THREE.PlaneGeometry(1, 1); m.userData.grid = false; }
        m.quaternion.copy(q);
        m.scale.set(pl.w, pl.h, 1);
        m.position.copy(pl.c);
      }
    }
    // ghost: the outer-surface copy, offset 3.1 mm in the plane of incidence (upward), parallel
    if (!surf) this.vimgGhost.position.add(ghostOff);
  }

  // The image surface over the window: PlaneGeometry(1, 1, NX, NY) vertex order (rows from the top, x left to right),
  // each vertex on the nominal eye's ray through its window point, at the traced sagittal image distance.
  imageSurface(pl, NX, NY) {
    const points = [];
    let dmin = Infinity, dmax = -Infinity, misses = 0;
    for (let j = 0; j <= NY; j++) {
      const y = (0.5 - j / NY) * pl.h;
      for (let i = 0; i <= NX; i++) {
        const x = (i / NX - 0.5) * pl.w;
        const P = pl.c.clone().addScaledVector(GM.VIMG_RIGHT, x).addScaledVector(GM.VIMG_UP, y);
        const dir = P.clone().sub(GM.EYE).normalize();
        let D = GM.EYE.distanceTo(P);
        const d = this.imageDistanceAlong(GM.EYE, dir);
        if (d != null && d > 1 && d < 500) D = d; else misses++;
        dmin = Math.min(dmin, D); dmax = Math.max(dmax, D);
        points.push(GM.EYE.clone().addScaledVector(dir, D));
      }
    }
    return { points, dmin, dmax, misses, nx: NX, ny: NY };
  }

  // The lit crop's image: PlaneGeometry(1, 1, NX, NY) vertex order over the crop (60 x 30 mm, the top of the image at
  // the panel's rear edge), each vertex where the nominal eye sees that panel point, at the image surface's distance.
  // Falls back to the window surface where the trace finds no ray to a panel point.
  cropSurface(NX, NY) {
    const points = [];
    const fallback = this.vimgSurface ? this.vimgSurface.points : null;
    for (let j = 0; j <= NY; j++) {
      const px = (j / NY - 0.5) * 0.03;                   // top row (j = 0) at px = -15 mm, the rear edge
      for (let i = 0; i <= NX; i++) {
        const pz = (i / NX - 0.5) * 0.06;
        const sol = GM.panelPointField(GM.EYE, pz, px);
        const k = j * (NX + 1) + i;
        if (!sol) { points.push(fallback ? fallback[k].clone() : GM.EYE.clone()); continue; }
        const dir = GM.fieldDir(sol.ax, sol.ay);
        const d = GM.imageDistanceAlong(GM.EYE, dir);
        points.push(GM.EYE.clone().addScaledVector(dir, d != null && d > 1 && d < 500 ? d : this.hud.plane.dist));
      }
    }
    return { points };
  }

  // Sagittal image distance from the eye along a viewing direction: the trace to the mirror, then the local
  // Coddington equation at the hit (the same as cycles.js fieldDistances). Null when the ray misses the optics.
  imageDistanceAlong(eye, dir, mode = GM.MIRROR.mode) {
    return GM.imageDistanceAlong(eye, dir, mode);
  }

  updateVignette(eyeOffset) {
    const v = this.hud.vignette(eyeOffset, 13, 7);
    const ctx = this.vigCanvas.getContext('2d');
    const img = ctx.createImageData(13, 7);
    for (let i = 0; i < v.data.length; i++) { const a = v.data[i] * 255; img.data[i * 4] = a; img.data[i * 4 + 1] = a; img.data[i * 4 + 2] = a; img.data[i * 4 + 3] = 255; }
    ctx.putImageData(img, 0, 0);
    this.vigTex.needsUpdate = true;
    return v.data.reduce((a, b) => a + b, 0) / v.data.length;
  }

  placeEgo(t) {
    const w = this.world, e = this.ego;
    const pose = w.egoPose(e.s, e.offset);
    this.carGroup.position.copy(pose.position);
    this.carGroup.quaternion.copy(pose.quaternion);
    const smp = w.road.sample(e.s);
    const fwd = new THREE.Vector3(1, 0, 0).applyQuaternion(pose.quaternion);
    const psi = Math.atan2(fwd.z, fwd.x);
    const yawRate = e.speed * (smp.curvature || 0);
    this.lastPose = { t, s: e.s, x: pose.position.x, z: pose.position.z, psi, speed: e.speed, yawRate, offset: e.offset, curvature: smp.curvature || 0 };
    this.hud.pushPose(this.lastPose);
    return this.lastPose;
  }

  // The installed PGU follows the mirror figure's panel pose: the freeform design tilts the panel about the lateral axis
  // through the crop centre and shifts it along the fold-to-panel leg (geom.panelPose); the other figures keep it flat.
  // The part object's rotation and a position offset from its built position are used, so exploding still works.
  applyPanelPose(mode = GM.MIRROR.mode) {
    const unit = this.installed.hudUnit;
    if (!unit) return null;
    const part = unit.comp.parts.find((p) => p.id === 'pgu');
    if (!part) return null;
    const pp = GM.panelPose(mode);
    part.object.rotation.set(0, 0, pp.tiltDeg * DEG);
    if (!part.base) part.base = part.object.position.clone();
    part.base.set(part.base.x, GM.PANEL_C.y - pp.shiftMm / 1000, part.base.z);
    part.object.position.copy(part.base);
    unit.comp.panelPose = pp;
    if (this.vimg) this.layoutVirtualImage(this._ghostScale || 1);     // the image surface belongs to the figure
    return pp;
  }

  // World direction -> car frame
  toCarDir(d) {
    const q = this.carGroup.quaternion.clone().invert();
    return d.clone().applyQuaternion(q);
  }

  // Ambient lux at the dust cover for each environment (sensor input to the dimming curve).
  ambientLux() {
    const n = this.world.env ? this.world.env.name : 'day';
    return { day: 100000, overcast: 10000, dusk: 150, night: 5 }[n] ?? 50000;
  }

  // Draw the audience view: HUD frame, driver camera with the eye point, live numbers against their targets.
  drawAudience(driverImg) {
    const c = this.audience, ctx = c.getContext('2d'), hs = this.hud;
    const W = c.width, H = c.height;
    ctx.fillStyle = '#0b0f14'; ctx.fillRect(0, 0, W, H);
    ctx.font = '700 22px "Helvetica Neue", Helvetica, Arial, sans-serif'; ctx.fillStyle = '#e7eaee'; ctx.textBaseline = 'top';
    ctx.fillText('AR HUD · audience view', 24, 18);
    ctx.font = '500 15px "Helvetica Neue", Helvetica, Arial, sans-serif'; ctx.fillStyle = '#8d97a5';
    ctx.fillText('rendered PGU frame (what the panel shows, before pre-distortion)', 24, 50);
    const fw = 560, fh = fw * CROP_H / CROP_W;
    ctx.drawImage(hs.canvas, 24, 74, fw, fh);
    ctx.strokeStyle = '#2b3440'; ctx.strokeRect(24, 74, fw, fh);
    if (driverImg) { ctx.drawImage(driverImg, 610, 74, 326, 200); ctx.strokeRect(610, 74, 326, 200); ctx.fillStyle = '#8d97a5'; ctx.fillText('driver camera · eye point', 610, 50); }
    const st = hs.stats, lum = hs.lum;
    const rows = [
      ['registration (lead, lane at 20 m)', `${(st.residual || 0).toFixed(2)}°`, '≤ 0.5° static, ≤ 0.3° head motion', (st.residual || 0) <= 0.3],
      ['age of lanes/objects as drawn', `${Math.round(st.ageLanes * 1000)} ms`, 'fade after 250 ms', st.ageLanes < 0.25],
      ['motion-to-photon', `${Math.round(hs.latency.total * 1000)} ms`, '≤ 90 ms', hs.latency.total <= 0.09],
      ['luminance at the eye', `${Math.round(lum.Leye).toLocaleString()} cd/m²`, '≥ 1,500 (noon sky)', lum.Leye >= 1500],
      ['contrast vs sky / road', `${lum.contrastSky.toFixed(2)} / ${lum.contrastRoad.toFixed(2)}`, '≥ 1.15', lum.contrastSky >= 1.15],
      ['cell temperature', `${hs.thermal.cell.toFixed(0)} °C`, `derate ${hs.thermal.T1}, off ${hs.thermal.T2} (sim)`, hs.thermal.state === 'ok'],
      ['shutter', hs.shutter.open > 0.5 ? 'open' : 'closed', hs.shutter.reason || 'sun-watch armed', hs.shutter.open > 0.5],
    ];
    let y = 74 + fh + 26;
    ctx.font = '500 16px "Helvetica Neue", Helvetica, Arial, sans-serif';
    for (const [k, v, tgt, ok] of rows) {
      ctx.fillStyle = '#8d97a5'; ctx.fillText(k, 24, y);
      ctx.fillStyle = ok ? '#4fd18b' : '#ffc04d'; ctx.font = '700 16px "Helvetica Neue", Helvetica, Arial, sans-serif'; ctx.fillText(v, 330, y);
      ctx.fillStyle = '#5b6573'; ctx.font = '500 14px "Helvetica Neue", Helvetica, Arial, sans-serif'; ctx.fillText(tgt, 520, y + 1);
      ctx.font = '500 16px "Helvetica Neue", Helvetica, Arial, sans-serif';
      y += 27;
    }
    this.audienceTex.needsUpdate = true;
  }
}
