// The garage: one world, one car, every component installed at its mount point, the cable runs, the HUD software,
// and the virtual-image meshes. The Driver view, Vehicle and Build modes all share it.
import * as THREE from 'three';
import * as GM from './geom.js';
import { M, C } from './mats.js';
import { build, available, setExplode } from './registry.js';
import { tube, DEG } from './util.js';
import { HudSim, CROP_W, CROP_H } from './hud.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);

// The virtual image's grid: 24 x 12 cells over the window.
const VIMG_NX = 24, VIMG_NY = 12;
// 32 taps filling the unit disk evenly (a Vogel spiral): the uniform ellipse that a defocused, astigmatic eye makes of
// a point is the unit disk scaled by the two blur semi-axes.
const BLUR_TAPS = Array.from({ length: 32 }, (_, i) => { const r = Math.sqrt((i + 0.5) / 32), t = i * 2.3999632; return `vec2(${(r * Math.cos(t)).toFixed(5)}, ${(r * Math.sin(t)).toFixed(5)})`; }).join(', ');

// The HUD frame's material on the virtual-image grid: texture coordinates from the nominal eye's ray through each
// fragment onto the window plane (uC, uRight, uUp, uW, uH; the ghost first undoes its offset), and, when uBlurOn,
// the eye's focus blur as a 32-tap ellipse whose semi-axes (texture units) arrive per vertex in aBlur.
function hudImageMaterial(mat, shared, off) {
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, shared, { uOff: off });
    sh.vertexShader = sh.vertexShader
      .replace('void main() {', 'attribute vec2 aBlur;\nvarying vec3 vCarPos;\nvarying vec2 vBlur;\nvoid main() {')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\n  vCarPos = position;\n  vBlur = aBlur;');
    sh.fragmentShader = sh.fragmentShader
      .replace('void main() {', `uniform vec3 uEye, uC, uRight, uUp, uN, uOff;
uniform float uW, uH, uBlurOn;
varying vec3 vCarPos;
varying vec2 vBlur;
const vec2 HUD_TAPS[32] = vec2[32](${BLUR_TAPS});
vec2 hudUv() {
  vec3 dir = vCarPos - uOff - uEye;
  vec3 P = uEye + dir * (dot(uC - uEye, uN) / dot(dir, uN));
  return vec2(dot(P - uC, uRight) / uW + 0.5, dot(P - uC, uUp) / uH + 0.5);
}
void main() {
  vec2 huv = hudUv();
  vec2 hdx = dFdx(huv), hdy = dFdy(huv);`)
      .replace('#include <map_fragment>', `#ifdef USE_MAP
  vec4 sampledDiffuseColor;
  if (uBlurOn > 0.5 && vBlur.x + vBlur.y > 1e-5) {
    vec4 acc = vec4(0.0);
    vec2 gx = hdx + vec2(0.35 * vBlur.x, 0.0), gy = hdy + vec2(0.0, 0.35 * vBlur.y);   // prefilter to the tap spacing
    for (int i = 0; i < 32; i++) acc += textureGrad(map, huv + HUD_TAPS[i] * vBlur, gx, gy);
    sampledDiffuseColor = acc / 32.0;
  } else {
    sampledDiffuseColor = textureGrad(map, huv, hdx, hdy);
  }
  diffuseColor *= sampledDiffuseColor;
#endif`)
      .replace('#include <alphamap_fragment>', '#ifdef USE_ALPHAMAP\n  diffuseColor.a *= texture2D(alphaMap, huv).g;\n#endif');
  };
  mat.customProgramCacheKey = () => 'hudImage';
  return mat;
}

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

  // The virtual image: the HUD frame on the image surface in front of the eye (additive light), its ghost, and the
  // cell's black-level glow over the whole window. All three are grids in the car frame: the traced window's vertices
  // sit on the image surface the optics make, the spec and Stage 1 windows' on their planes.
  makeVirtualImage() {
    const g = this.vimg = new THREE.Group(); g.name = 'virtualImage';
    // The HUD frame's texture coordinates come from the nominal eye's ray through each fragment, not from the grid: the
    // surface's vertices lie at very different depths (5 m at the top of the toroid's window to past infinity in its
    // lower corners), and perspective-correct interpolation of grid UVs across such a cell stretches the frame toward
    // its near corner, which smeared the speed block. Projected from the eye, the frame lands where hudd drew it.
    this.vimgUniforms = {
      uEye: { value: GM.EYE.clone() }, uC: { value: new THREE.Vector3() }, uRight: { value: GM.VIMG_RIGHT.clone() },
      uUp: { value: GM.VIMG_UP.clone() }, uN: { value: GM.VIMG_N.clone() }, uW: { value: 1 }, uH: { value: 1 },
      uBlurOn: { value: 0 },
    };
    this.vimgGhostOff = { value: new THREE.Vector3() };
    const mk = (opacity, ghost) => hudImageMaterial(new THREE.MeshBasicMaterial({ map: this.hud.texture, transparent: true, opacity, blending: THREE.AdditiveBlending, depthTest: false, depthWrite: false, toneMapped: true, color: 0xffffff }), this.vimgUniforms, ghost ? this.vimgGhostOff : { value: new THREE.Vector3() });
    const NX = VIMG_NX, NY = VIMG_NY;
    const grid = () => { const geo = new THREE.PlaneGeometry(1, 1, NX, NY); geo.setAttribute('aBlur', this.vimgBlurAttr); return geo; };
    this.vimgBlurAttr = new THREE.BufferAttribute(new Float32Array((NX + 1) * (NY + 1) * 2), 2);
    this.vimgMain = new THREE.Mesh(grid(), mk(1, false));
    this.vimgGhost = new THREE.Mesh(grid(), mk((1 - 0.2357) ** 2, true));
    this.vimgBlack = new THREE.Mesh(grid(), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, blending: THREE.AdditiveBlending, depthTest: false, depthWrite: false }));
    // eye-box vignette as an alpha map
    this.vigCanvas = document.createElement('canvas'); this.vigCanvas.width = 13; this.vigCanvas.height = 7;
    this.vigTex = new THREE.CanvasTexture(this.vigCanvas); this.vigTex.magFilter = THREE.LinearFilter; this.vigTex.minFilter = THREE.LinearFilter;
    for (const m of [this.vimgMain, this.vimgGhost, this.vimgBlack]) { m.material.alphaMap = this.vigTex; m.renderOrder = 50; m.frustumCulled = false; g.add(m); }
    this.vimgBlack.renderOrder = 49;
    // The eye's focus blur (Driver view, Mirror and windshield): off until asked for.
    this.focus = { on: false, target: 'image', pupilMm: 0 };
    this.carGroup.add(g);
    g.visible = false;
    this.layoutVirtualImage();
  }

  layoutVirtualImage(ghostScale = 1) {
    const pl = this.hud.plane;
    this._ghostScale = ghostScale;
    // The traced window is drawn on the image surface the optics make, not on a plane: for each grid point of the
    // window, the sagittal image distance along the nominal eye's ray (local Coddington at the mirror hit, as the
    // Cycles section computes it and Cycles confirmed across the toroid's window). From the nominal eye the picture is
    // identical; when the head moves, each part of the image swims against the road by its own distance, as it does
    // in the car. The spec and stage-1 windows stay the planes they are defined as.
    const NX = VIMG_NX, NY = VIMG_NY;
    const traced = this.hud.settings.window === 'traced';
    const surf = this.imageSurface(pl, NX, NY, traced);
    this.vimgSurface = traced ? surf : null;
    const ghostOff = GM.VIMG_UP.clone().multiplyScalar((3.1137 / 1000) * ghostScale);
    this.vimgGhostOff.value.copy(ghostOff);
    const U = this.vimgUniforms;
    U.uC.value.copy(pl.c); U.uW.value = pl.w; U.uH.value = pl.h;
    // the black-level glow is the whole lit crop, which the optics keystone (wider at the bottom); the content stays
    // on the inscribed rectangle hudd draws into. Map the crop's edges through the trace for the glow's outline.
    const cropSurf = traced ? this.cropSurface(NX, NY) : null;
    for (const m of [this.vimgMain, this.vimgGhost, this.vimgBlack]) {
      const pos = m.geometry.attributes.position;
      const off = m === this.vimgGhost ? ghostOff : null;
      const pts = (m === this.vimgBlack && cropSurf) ? cropSurf.points : surf.points;
      for (let k = 0; k < pos.count; k++) { const pt = pts[k]; pos.setXYZ(k, pt.x + (off ? off.x : 0), pt.y + (off ? off.y : 0), pt.z + (off ? off.z : 0)); }
      pos.needsUpdate = true;
      m.geometry.computeBoundingSphere();
      m.quaternion.identity(); m.scale.set(1, 1, 1); m.position.set(0, 0, 0);
    }
    this.vimgVerg = null;                                   // the vergences belong to the figure, the glass and the window
    if (this.focus && this.focus.on) this.updateFocusBlur();
  }

  // The window's grid points: PlaneGeometry(1, 1, NX, NY) vertex order (rows from the top, x left to right), each on
  // the nominal eye's ray through its window point; on the traced window at the traced sagittal image distance (held
  // continuous past infinity, see GM.surfaceDistance), otherwise on the plane.
  imageSurface(pl, NX, NY, traced = true) {
    const points = [];
    let dmin = Infinity, dmax = -Infinity, misses = 0;
    for (let j = 0; j <= NY; j++) {
      const y = (0.5 - j / NY) * pl.h;
      for (let i = 0; i <= NX; i++) {
        const x = (i / NX - 0.5) * pl.w;
        const P = pl.c.clone().addScaledVector(GM.VIMG_RIGHT, x).addScaledVector(GM.VIMG_UP, y);
        const dir = P.clone().sub(GM.EYE).normalize();
        let D = GM.EYE.distanceTo(P);
        if (traced) {
          const d = this.imageDistanceAlong(GM.EYE, dir);
          if (d == null) misses++;
          D = GM.surfaceDistance(d, D);
        }
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
        points.push(GM.EYE.clone().addScaledVector(dir, GM.surfaceDistance(d, this.hud.plane.dist)));
      }
    }
    return { points };
  }

  // Sagittal image distance from the eye along a viewing direction: the trace to the mirror, then the local
  // Coddington equation at the hit (the same as cycles.js fieldDistances). Null when the ray misses the optics.
  imageDistanceAlong(eye, dir, mode = GM.MIRROR.mode) {
    return GM.imageDistanceAlong(eye, dir, mode);
  }

  // Both image vergences at every grid vertex of the window, from the nominal eye, through the whole trace (curved
  // glass included): GM.fieldVergences. The spec and Stage 1 windows are planes, one vergence everywhere. Cached until
  // the figure, the glass or the window changes (about 0.1 to 0.3 s to compute).
  vergences() {
    if (this.vimgVerg) return this.vimgVerg;
    const pl = this.hud.plane, NX = VIMG_NX, NY = VIMG_NY;
    const traced = this.hud.settings.window === 'traced';
    const Vs = new Float32Array((NX + 1) * (NY + 1)), Vt = new Float32Array(Vs.length), ok = new Uint8Array(Vs.length);
    for (let j = 0; j <= NY; j++) for (let i = 0; i <= NX; i++) {
      const k = j * (NX + 1) + i;
      const x = (i / NX - 0.5) * pl.w, y = (0.5 - j / NY) * pl.h;
      if (!traced) { const D = Math.hypot(pl.dist, x, y); Vs[k] = Vt[k] = 1 / D; ok[k] = 1; continue; }
      const r = GM.fieldVergences(GM.EYE, Math.atan(x / pl.dist), Math.atan(y / pl.dist));
      if (r) { Vs[k] = r.Vs; Vt[k] = r.Vt; ok[k] = 1; }
    }
    // Where no ray from a displaced eye reaches the panel point (strong glass on a mismatched mirror), take the mean of
    // the neighbours, so the blur stays continuous; those vertices are left out of the readouts (ok = 0).
    const have = Uint8Array.from(ok);
    for (let pass = 0; pass < 60; pass++) {
      let left = 0;
      for (let j = 0; j <= NY; j++) for (let i = 0; i <= NX; i++) {
        const k = j * (NX + 1) + i; if (have[k]) continue;
        let n = 0, ss = 0, st = 0;
        for (const [di, dj] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
          const ii = i + di, jj = j + dj; if (ii < 0 || jj < 0 || ii > NX || jj > NY) continue;
          const q = jj * (NX + 1) + ii; if (have[q] === 1) { n++; ss += Vs[q]; st += Vt[q]; }
        }
        if (n) { Vs[k] = ss / n; Vt[k] = st / n; have[k] = 2; } else left++;
      }
      for (let k = 0; k < have.length; k++) if (have[k] === 2) have[k] = 1;
      if (!left) break;
    }
    this.vimgVerg = { Vs, Vt, ok, filled: have, key: GM.MIRROR.mode + ':' + GM.GLASS.Rh + ':' + GM.GLASS.Rv + ':' + this.hud.settings.window };
    return this.vimgVerg;
  }

  // Pupil diameter (m): the Driver view's choice, or a typical value for the scene's adaptation luminance (ASSUMED:
  // about 3 mm in sun, 4 overcast, 5 at dusk, 6 at night).
  pupil() {
    if (this.focus.pupilMm > 0) return this.focus.pupilMm / 1000;
    const n = (this.world.env && this.world.env.name) || 'day';
    return ({ day: 3, overcast: 4, dusk: 5, night: 6 })[n] / 1000 || 0.003;
  }

  // Where the eye focuses (dioptres). 'image': best focus on the HUD at the window centre (the mean of the two
  // vergences, the circle of least confusion), 'road': 20 m, 'infinity'. An eye cannot focus past infinity, so the
  // accommodation never goes below 0.
  accommodation() {
    const f = this.focus.target;
    if (f === 'road') return 1 / 20;
    if (f === 'infinity') return 0;
    const v = this.vergences(), k = (VIMG_NY / 2) * (VIMG_NX + 1) + VIMG_NX / 2;
    return v.ok[k] ? Math.max(0, (v.Vs[k] + v.Vt[k]) / 2) : 0;
  }

  // The eye's blur over the window: a pupil p focused at A sees a point whose two vergences are Vs, Vt as a uniform
  // ellipse p|Vs - A| wide (horizontal, the sagittal fan) by p|Vt - A| tall (vertical, the tangential fan), in radians.
  // The shader convolves the HUD frame with that ellipse, per vertex, as semi-axes in texture units.
  updateFocusBlur() {
    const U = this.vimgUniforms, a = this.vimgBlurAttr.array;
    U.uBlurOn.value = this.focus.on ? 1 : 0;
    if (!this.focus.on) return;
    const v = this.vergences(), A = this.accommodation(), p = this.pupil(), pl = this.hud.plane;
    for (let k = 0; k < v.Vs.length; k++) {
      if (!v.filled[k]) { a[2 * k] = a[2 * k + 1] = 0; continue; }
      a[2 * k] = 0.5 * p * Math.abs(v.Vs[k] - A) * pl.dist / pl.w;
      a[2 * k + 1] = 0.5 * p * Math.abs(v.Vt[k] - A) * pl.dist / pl.h;
    }
    this.vimgBlurAttr.needsUpdate = true;
  }

  // Readouts for the Driver view: the two image distances at the window centre, the worst astigmatism over the window,
  // and the blur (arcmin, the larger axis) at the centre and at its worst, for the current pupil and focus.
  focusStats() {
    const v = this.vergences(), A = this.accommodation(), p = this.pupil();
    const k0 = (VIMG_NY / 2) * (VIMG_NX + 1) + VIMG_NX / 2;
    const am = (dv) => p * Math.abs(dv) / DEG * 60;
    let astig = 0, blur = 0, n = 0, past = 0;
    for (let k = 0; k < v.Vs.length; k++) {
      if (!v.ok[k]) continue;
      n++;
      astig = Math.max(astig, Math.abs(v.Vs[k] - v.Vt[k]));
      blur = Math.max(blur, am(v.Vs[k] - A), am(v.Vt[k] - A));
      if (v.Vs[k] < 0 || v.Vt[k] < 0) past++;
    }
    const c = v.ok[k0] ? { Vs: v.Vs[k0], Vt: v.Vt[k0] } : null;
    return { centre: c, astig, blurWorst: blur, blurCentre: c ? Math.max(am(c.Vs - A), am(c.Vt - A)) : null, A, pupilMm: p * 1000, pastFrac: n ? past / n : 0, traced: n };
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
