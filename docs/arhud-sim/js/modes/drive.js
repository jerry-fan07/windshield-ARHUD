// Driver view: sit at the driver's eye and drive the loop with the HUD on. The HUD is a real virtual image: the PGU
// frame drawn by the simulated hudd is shown as light on a plane 7.5 m ahead, so registration, parallax, latency,
// ghost, eye-box vignetting and brightness all come out of the geometry rather than being painted on the screen.
import * as THREE from 'three';
import * as GM from '../geom.js';
import { R } from '../params.js';
import { h, setPanel, hidePanel, slider, toggle, chips, liveKv, btn, toast, section, keys, setDock, hideDock } from '../ui.js';
import { PGU_SOURCES, LAT_STAGES, CROP_W, CROP_H } from '../hud.js';
import { loadCyclesResults, cyclesDockView } from '../cycles.js';
import { DEG, clamp, lerp } from '../util.js';

const MPH = 2.236936;
// Mirror figures and windshields the Driver view can combine (Mirror, windshield and focus blur). The curved glasses
// are illustrative radii (ASSUMED, lateral x vertical); 4 m x 8 m is the one the curved freeform was fitted for.
const MIRRORS = [
  ['sphere', 'Generic sphere, R 660 mm (the plan as written)'],
  ['toroid', 'Toroid fitted to flat glass'],
  ['freeform', 'Freeform fitted to flat glass (tilted panel)'],
  ['freeformCurved', 'Freeform fitted to the 4 m × 8 m glass'],
];
const GLASSES = { flat: [0, 0], gentle: [8, 20], design: [4, 8], strong: [3, 6] };
const GLASS_LABELS = [['flat', 'Flat (the plan)'], ['gentle', 'Gentle: 8 m × 20 m'], ['design', 'Typical: 4 m × 8 m'], ['strong', 'Strong: 3 m × 6 m']];

export class DriveMode {
  constructor(app) {
    this.app = app;
    this.g = app.garage;
    this.camera = new THREE.PerspectiveCamera(55, 1, 0.05, 20000);
    this.camera.layers.enable(1);   // layer 1: the components' explanatory sprites
    this.look = { yaw: 0, pitch: 0, fov: 55 };
    this.head = { user: new THREE.Vector3(), sway: false, swayAmp: 0.075 };
    this.speedTarget = 25;
    // The driver: follows the speed slider within the car's limits (ASSUMED: +2.5 m/s^2 throttle, -6 m/s^2 brake),
    // and, with keepGap, brakes to hold a time gap behind the lead. A manoeuvre forces the pedal for a while.
    this.driver = { keepGap: true, timeGap: 1.8, maxAccel: 2.5, maxBrake: 6 };
    this.manoeuvre = null;
    this.paused = false;
    this.env = 'day';
    this.timeOfDay = 12.0;
    this.keys = new Set();
    try { const r = localStorage.getItem('arhud.ribbon'); if (r === 'fill' || r === 'blank') this.g.hud.settings.ribbon = r; } catch (e) { /* private window */ }
    this.t = 0;
    this.vigT = 0; this.audT = 0;
    this.driverRT = new THREE.WebGLRenderTarget(320, 200);
    this.driverCam = new THREE.PerspectiveCamera(48, 320 / 200, 0.05, 30);
    this.driverCanvas = document.createElement('canvas'); this.driverCanvas.width = 320; this.driverCanvas.height = 200;
    this.driverPx = new Uint8Array(320 * 200 * 4);
    // The road camera's image (ZED 2i left lens, 72 x 44 deg, datasheet) with roadd's output drawn over it.
    this.roadRT = new THREE.WebGLRenderTarget(480, 270);
    this.roadCam = new THREE.PerspectiveCamera(44, 16 / 9, 0.3, 400);
    this.roadCanvas = document.createElement('canvas'); this.roadCanvas.width = 480; this.roadCanvas.height = 270;
    this.roadPx = new Uint8Array(480 * 270 * 4);
    this._onKey = (e) => this.onKey(e);
    this._onKeyUp = (e) => this.keys.delete(e.key.toLowerCase());
    this._wheel = (e) => { e.preventDefault(); this.look.fov = clamp(this.look.fov * Math.exp(e.deltaY * 0.0012), 2, 80); this.fovChips && this.fovChips.set(''); };
    this._down = (e) => { this.drag = [e.clientX, e.clientY, this.look.yaw, this.look.pitch]; };
    this._move = (e) => {
      if (!this.drag || !(e.buttons & 1)) return;
      const k = this.look.fov / 55 * 0.25;
      this.look.yaw = clamp(this.drag[2] - (e.clientX - this.drag[0]) * k, -100, 100);
      this.look.pitch = clamp(this.drag[3] - (e.clientY - this.drag[1]) * k, -50, 40);
    };
    this._up = () => { this.drag = null; };
  }

  async enter() {
    const app = this.app, g = this.g;
    if (this.camera.parent !== g.carGroup) g.carGroup.add(this.camera);
    app.setScene(g.scene, this.camera);
    app.controls.enabled = false;
    g.vimg.visible = true;
    g.car.setCutaway && g.car.setCutaway('none');
    if (g.car.driver && g.car.driver.head) g.car.driver.head.visible = false;   // the camera sits inside the head
    g.installGroup.visible = true;
    g.cableGroup.visible = true;
    this.applyEnv(this.env);
    if (g.ego.speed === 0 && !this.paused) g.ego.speed = 0.01;
    for (const v of Object.values(g.installed)) v.comp.setWorking(false);
    // Parts the driver cannot see from the seat are hidden while driving (they only cost draw calls).
    this.hiddenWhileDriving = [];
    for (const id of ['jetson', 'dcdc', 'ethSwitch', 'zedF9r', 'miniPC', 'pdCharger', 'monitor', 'fuseTap']) {
      const v = g.installed[id]; if (v && v.holder.visible) { v.holder.visible = false; this.hiddenWhileDriving.push(v.holder); }
    }
    for (const cab of g.cables) if (cab.id !== 'usbZed' && cab.mesh.visible) { cab.mesh.visible = false; this.hiddenWhileDriving.push(cab.mesh); }
    // Inside the closed housing only the mirror shows through the dust cover.
    const unitC = g.installed.hudUnit && g.installed.hudUnit.comp;
    if (unitC) for (const p of unitC.parts) if (['pgu', 'coldMirror', 'baffles'].includes(p.id) && p.object.visible) { p.object.visible = false; this.hiddenWhileDriving.push(p.object); }
    const unit = g.installed.hudUnit;
    if (unit) unit.comp.setWorking(false);
    const dom = app.renderer.domElement;
    window.addEventListener('keydown', this._onKey); window.addEventListener('keyup', this._onKeyUp);
    dom.addEventListener('wheel', this._wheel, { passive: false });
    dom.addEventListener('pointerdown', this._down); window.addEventListener('pointermove', this._move); window.addEventListener('pointerup', this._up);
    if (this.cycles === undefined) this.cycles = await loadCyclesResults();
    this.renderPanels();
    this.resize(dom.clientWidth, dom.clientHeight);
  }

  exit() {
    const dom = this.app.renderer.domElement;
    window.removeEventListener('keydown', this._onKey); window.removeEventListener('keyup', this._onKeyUp);
    dom.removeEventListener('wheel', this._wheel); dom.removeEventListener('pointerdown', this._down);
    window.removeEventListener('pointermove', this._move); window.removeEventListener('pointerup', this._up);
    this.g.vimg.visible = false;
    for (const o of this.hiddenWhileDriving || []) o.visible = true;
    this.hiddenWhileDriving = [];
    if (this.g.car.driver && this.g.car.driver.head) this.g.car.driver.head.visible = true;
    hideDock();
    hidePanel('left'); hidePanel('right'); hidePanel('bottom');
  }

  resize(w, hh) { this.camera.aspect = w / Math.max(1, hh); this.camera.updateProjectionMatrix(); }

  applyEnv(name) {
    this.env = name;
    const env = this.g.world.setEnvironment(name);
    if (name === 'day' && this.g.world.setTimeOfDay) this.g.world.setTimeOfDay(this.timeOfDay);
    if (env && env.exposure) this.app.renderer.toneMappingExposure = env.exposure;
    this.g.car.setHeadlights && this.g.car.setHeadlights(name === 'night' || name === 'dusk');
    this.app.bloom.strength = name === 'night' ? 0.3 : name === 'dusk' ? 0.3 : 0.2;
    if (this.g.focus && this.g.focus.on) this.g.updateFocusBlur();     // the automatic pupil follows the scene
  }

  // Mirror figure, windshield and the eye's focus blur. The figure switch does what the Vehicle mode's does (the panel
  // tilt, the image surface, the unit's mirror); the glass goes into the trace only (the car's glass is drawn flat).
  setMirror(v) {
    const g = this.g, hs = g.hud;
    GM.MIRROR.mode = v;
    const u = g.installed.hudUnit; u && u.comp.handles && u.comp.handles.setMirrorMode && u.comp.handles.setMirrorMode(v);
    g.applyPanelPose && g.applyPanelPose(v);
    hs.setWindow(hs.settings.window); g.layoutVirtualImage(this.ghostScale || 1);
    const veh = this.app.modes.vehicle; if (veh && veh.opts) veh.opts.mirror = v;
    this.mirrorChips && this.mirrorChips.set(v);
  }

  setGlass(key) {
    const r = GLASSES[key]; if (!r) return;
    GM.GLASS.Rh = r[0]; GM.GLASS.Rv = r[1];
    const hs = this.g.hud; hs.setWindow(hs.settings.window); this.g.layoutVirtualImage(this.ghostScale || 1);
    this.glassChips && this.glassChips.set(key);
  }

  glassKey() { return Object.keys(GLASSES).find((k) => GLASSES[k][0] === GM.GLASS.Rh && GLASSES[k][1] === GM.GLASS.Rv) || ''; }

  setFocusBlur(on) {
    this.g.focus.on = !!on; this.g.updateFocusBlur();
    this.blurToggle && this.blurToggle.set(on);
  }

  setFocus({ target, pupilMm } = {}) {
    const f = this.g.focus;
    if (target) f.target = target;
    if (pupilMm !== undefined) f.pupilMm = pupilMm;
    this.g.updateFocusBlur();
    this.focusChips && this.focusChips.set(f.target);
    this.pupilChips && this.pupilChips.set(String(f.pupilMm));
  }

  onKey(e) {
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT')) return;
    const k = e.key.toLowerCase();
    this.keys.add(k);
    if (k === ' ') { e.preventDefault(); this.clutter(); }
    if (k === 'p') { this.paused = !this.paused; toast(this.paused ? 'Paused' : 'Driving'); }
    if (k === 'r') { this.head.user.set(0, 0, 0); this.look.yaw = 0; this.look.pitch = 0; this.updateHeadSliders(); }
    if (k === 'l') this.setRibbon(this.g.hud.settings.ribbon === 'blank' ? 'fill' : 'blank', { say: true });
    if (k === 'b') this.brakeHard();
  }

  // Manoeuvres: the pedal is forced for a while so the body's pitch, the plane fit and the age compensation show.
  brakeHard() { this.manoeuvre = { accel: -6, until: this.t + 2.2, name: 'brake' }; toast('Hard brake: the nose dives, the ground plane tilts in the camera, watch the lane and the lead'); }
  floorIt() { this.manoeuvre = { accel: 3, until: this.t + 2.5, name: 'throttle' }; toast('Full throttle: the tail squats'); }

  // The lane ribbon: 'fill' is the plan's tinted lane, whose edges show any misalignment against the paint; 'blank'
  // draws only the lines and symbols. The lane is computed either way, because the lead chevron is chosen inside it.
  setRibbon(v, { say = false } = {}) {
    if (v !== 'fill' && v !== 'blank') return;
    this.g.hud.settings.ribbon = v;
    try { localStorage.setItem('arhud.ribbon', v); } catch (e) { /* private window */ }
    this.ribbonChips && this.ribbonChips.set(v);
    if (say) toast(v === 'blank' ? 'Lane blank: lines and symbols only' : 'Lane filled: its edges show misalignment against the paint');
  }

  clutter() { this.g.hud.settings.clutterUntil = this.g.hud.t + 10; toast('Clutter mode for 10 s: every line, every track, every gap'); }

  renderPanels() {
    const g = this.g, hs = g.hud, S = hs.settings;
    const fmtSpeed = (v) => `${Math.round(v * MPH)} mph · ${v.toFixed(0)} m/s`;
    const latTotal = () => S.lat.reduce((a, b) => a + b, 0);
    const latOut = h('b', {}, `${Math.round(latTotal())} ms`);
    const latSliders = LAT_STAGES.map((st, i) => slider({ id: 'lat' + i, label: st.name, min: st.lo, max: st.hi, step: 1, value: S.lat[i], fmt: (x) => `${x} ms`, onInput: (v) => { S.lat[i] = v; latOut.textContent = `${Math.round(latTotal())} ms`; } }));
    const latDetails = h('details', {}, h('summary', { class: 'muted', style: { cursor: 'pointer', fontSize: '12px' } }, 'Latency stages (plan budget ranges)'), ...latSliders);
    this.headX = slider({ id: 'headx', label: 'Head left–right', min: -150, max: 150, step: 1, value: this.head.user.z * 1000, fmt: (x) => `${x} mm`, onInput: (v) => { this.head.user.z = v / 1000; } });
    this.headY = slider({ id: 'heady', label: 'Head down–up', min: -80, max: 80, step: 1, value: this.head.user.y * 1000, fmt: (x) => `${x} mm`, onInput: (v) => { this.head.user.y = v / 1000; } });
    this.fovChips = chips({ id: 'fov', options: [['55', 'Wide'], ['16', 'HUD window'], ['5', 'Loupe'], ['1.2', 'Pixel loupe']], value: '55', onChange: (v) => { this.look.fov = parseFloat(v); if (v !== '55') { this.look.yaw = 0; this.look.pitch = 0; } } });
    const timeSl = slider({ id: 'tod', label: 'Time of day (June 21, 37° N)', min: 5, max: 20.5, step: 0.05, value: this.timeOfDay, fmt: (x) => `${Math.floor(x)}:${String(Math.round((x % 1) * 60)).padStart(2, '0')}`, onInput: (v) => { this.timeOfDay = v; if (this.env === 'day' && g.world.setTimeOfDay) g.world.setTimeOfDay(v); } });
    // The everyday controls sit in the open; the experiment groups start folded.
    setPanel('left',
      h('h2', {}, 'Driver view'),
      h('p', { class: 'hint' }, 'You sit at the driver\'s eye with the HUD running. Drag to look around, scroll to zoom.'),
      keys(['Arrows', 'move your head'], ['Space', 'clutter mode'], ['L', 'lane filled / blank'], ['B', 'brake hard'], ['P', 'pause'], ['R', 'reset']),
      slider({ id: 'speed', label: 'Speed', min: 0, max: 35, step: 0.5, value: this.speedTarget, fmt: fmtSpeed, onInput: (v) => { this.speedTarget = v; } }),
      h('h3', {}, 'View'), this.fovChips,
      h('h3', {}, 'Lane on the HUD'),
      this.ribbonChips = chips({ id: 'ribbon', options: [['fill', 'Filled: shows misalignment'], ['blank', 'Blank: lines and symbols only']], value: S.ribbon, onChange: (v) => this.setRibbon(v) }),
      h('h3', {}, 'Scene'),
      this.envChips = chips({ id: 'env', options: [['day', 'Sun'], ['overcast', 'Overcast'], ['dusk', 'Dusk'], ['night', 'Night']], value: this.env, onChange: (v) => this.applyEnv(v) }),
      (this.todSlider = timeSl),
      btn('Put the sun in the entry patch', () => this.sunScenario()),
      section('drive-pgu', 'Picture generator', false,
        chips({ id: 'pgu', options: PGU_SOURCES.map((s) => [s.key, `${s.label} · ${s.panel.toLocaleString()}`]), value: S.pgu, onChange: (v) => { S.pgu = v; } }),
        toggle({ id: 'both', label: 'Count both glass surfaces (wedge glass)', checked: S.bothSurfaces, onChange: (v) => { S.bothSurfaces = v; } }),
        h('div', { class: 'row' }, h('span', { class: 'muted', style: { fontSize: '12px' } }, 'Image polarisation at the glass'), chips({ id: 'pol', options: [['s', 's, as designed (23.6% reflected)'], ['p', 'p: retarder wrong (1.2%, ratio 19)']], value: S.polarisation, onChange: (v) => { S.polarisation = v; } })),
        h('div', { class: 'row' }, h('span', { class: 'muted', style: { fontSize: '12px' } }, 'Driver\'s eyewear'), chips({ id: 'eyewear', options: [['none', 'None'], ['polarised', 'Polarised sunglasses'], ['tinted', 'Tinted (neutral) sunglasses']], value: S.eyewear, onChange: (v) => { S.eyewear = v; } })),
        h('p', { class: 'hint' }, 'The image reaches the eye s-polarised (electric field horizontal); polarised sunglasses pass the vertical, so they take the scene down by half and the image to about 2%. The plan\'s demo rule: no polarised eyewear. A p-polarised image would pass the glasses but the glass reflects only 1.2% of it.'),
        toggle({ id: 'autodim', label: 'Automatic dimming from the ambient sensor', checked: S.autoDim, onChange: (v) => { S.autoDim = v; } }),
        h('div', { class: 'row' }, h('span', { class: 'muted', style: { fontSize: '12px' } }, 'Night ceiling at the eye'), chips({ id: 'nightFloor', options: [['50', '50 cd/m² (the plan)'], ['10', '10 cd/m²'], ['3', '3 cd/m² (TI\'s night figure)']], value: String(S.nightCeiling), onChange: (v) => { S.nightCeiling = parseFloat(v); } })),
        h('div', { class: 'row' }, h('span', { class: 'muted', style: { fontSize: '12px' } }, 'Driver offset'), btn('−1 step', () => { S.dimSteps = Math.max(-1, S.dimSteps - 1); }), btn('+1 step', () => { S.dimSteps = Math.min(1, S.dimSteps + 1); }))),
      section('drive-optics', 'Optics', false,
        chips({ id: 'win', options: [['traced', 'Stage 2 as the hardware gives it: 8.7° × 4.6° (traced, Cycles-confirmed)'], ['spec', 'Stage 2 as the plan specifies: 10.8° × 5.4° at 7.5 m (the optics do not reach it)'], ['stage1', 'Stage 1: Fresnel + combiner, 4.2 m']], value: S.window, onChange: (v) => { hs.setWindow(v); g.layoutVirtualImage(this.ghostScale || 1); } }),
        toggle({ id: 'ghost', label: 'Ghost from the outer glass surface', checked: S.ghost, onChange: (v) => { S.ghost = v; } }),
        h('div', { class: 'row' }, h('span', { class: 'muted', style: { fontSize: '12px' } }, 'hudd places a symbol for the tracked eye by'), chips({ id: 'proj', options: [['plane', 'a plane at one distance (the plan)'], ['surface', 'the image-surface map'], ['trace', 'the optical model, eye to panel (exact)'], ['lut', 'the optical model as a lookup table (the Jetson\'s way)']], value: S.projection || 'plane', onChange: (v) => { S.projection = v; S.surfaceAware = v === 'surface'; } })),
        chips({ id: 'ghostx', options: [['1', 'True size (1.4′)'], ['10', '×10'], ['40', '×40']], value: '1', onChange: (v) => { this.ghostScale = parseFloat(v); g.layoutVirtualImage(this.ghostScale); } })),
      section('drive-astig', 'Mirror, windshield and focus blur', false,
        h('p', { class: 'hint' }, 'The windshield is a curved mirror used at 65°, so it focuses more strongly top to bottom than side to side; the concave mirror must cancel that. Combine a mirror with a windshield and switch on the blur to see what the driver\'s eye sees.'),
        h('div', { class: 'row' }, h('span', { class: 'muted', style: { fontSize: '12px' } }, 'Concave mirror')),
        (this.mirrorChips = chips({ id: 'astigMirror', options: MIRRORS, value: GM.MIRROR.mode, onChange: (v) => { this.setMirror(v); this.setFocusBlur(true); } })),
        h('div', { class: 'row' }, h('span', { class: 'muted', style: { fontSize: '12px' } }, 'Windshield radii, lateral × vertical (ASSUMED)')),
        (this.glassChips = chips({ id: 'astigGlass', options: GLASS_LABELS, value: this.glassKey(), onChange: (v) => { this.setGlass(v); this.setFocusBlur(true); } })),
        (this.blurToggle = toggle({ id: 'focusBlur', label: 'Show the eye\'s focus blur (astigmatism and defocus)', checked: g.focus.on, onChange: (v) => this.setFocusBlur(v) })),
        h('div', { class: 'row' }, h('span', { class: 'muted', style: { fontSize: '12px' } }, 'The eye focuses on')),
        (this.focusChips = chips({ id: 'focusAt', options: [['image', 'the HUD (best focus at the centre)'], ['road', 'the road, 20 m'], ['infinity', 'infinity']], value: g.focus.target, onChange: (v) => this.setFocus({ target: v }) })),
        h('div', { class: 'row' }, h('span', { class: 'muted', style: { fontSize: '12px' } }, 'Pupil')),
        (this.pupilChips = chips({ id: 'pupil', options: [['0', 'From the scene'], ['2', '2 mm'], ['4', '4 mm'], ['6', '6 mm'], ['8', '8 mm']], value: String(g.focus.pupilMm), onChange: (v) => this.setFocus({ pupilMm: parseFloat(v) }) })),
        h('p', { class: 'hint' }, 'Each point of the window is traced through the glass, the mirror and the fold from eyes 10 mm apart: the parallax gives the image distance of the horizontal (sagittal) and the vertical (tangential) fan. A pupil focused at one distance sees each point as an ellipse, pupil × the dioptre error wide in each direction, and the HUD frame is blurred by it. Past infinity means the light converges toward the eye, which no eye can focus. Only the traced Stage 2 window has astigmatism; the spec and Stage 1 windows are planes.')),
      section('drive-body', 'Body motion and ground plane', false,
        h('p', { class: 'hint' }, 'The eye, the optics and the cameras ride on the body; the road does not. The suspension pitches the body under braking and rolls it in bends, and roadd must measure the ground plane in every frame, or every degree of pitch becomes a registration error.'),
        toggle({ id: 'dynOn', label: 'Body pitches and rolls on its suspension', checked: g.dyn.on, onChange: (v) => { g.dyn.on = v; } }),
        slider({ id: 'rough', label: 'Road texture', min: 0, max: 3, step: 0.1, value: g.dyn.roughness, fmt: (x) => (x === 0 ? 'glass smooth' : x <= 1 ? `${x.toFixed(1)} × fair highway` : `${x.toFixed(1)} × (worn)`), onInput: (v) => { g.dyn.roughness = v; } }),
        h('div', { class: 'row' }, btn('Brake hard (B)', () => this.brakeHard()), btn('Full throttle', () => this.floorIt())),
        h('h3', {}, 'Traffic'),
        h('div', { class: 'row' },
          btn('Car cuts in ahead', () => { g.world.startScenario('cutin', g.ego); toast('The adjacent car pulls into the lane 22 m ahead: the chevron must move to it after 3 confident frames'); }),
          btn('Lead brakes hard', () => { g.world.startScenario('brake', g.ego); toast('The lead brakes at 5.5 m/s²: brake lamps, the gap and the seconds shrink; the driver brakes behind it'); })),
        toggle({ id: 'keepGap', label: 'Driver brakes to keep 1.8 s behind the lead', checked: this.driver.keepGap, onChange: (v) => { this.driver.keepGap = v; } }),
        h('h3', {}, 'roadd ground plane'),
        chips({ id: 'plane', options: [['stereo', 'Stereo RANSAC fit every frame (the plan)'], ['imu', 'Static plane + IMU pitch (fallback)'], ['static', 'Calibrated static plane only']], value: S.plane, onChange: (v) => { S.plane = v; } }),
        toggle({ id: 'pitchComp', label: 'Age compensation undoes the body\'s pitch rate (IMU)', checked: S.pitchComp, onChange: (v) => { S.pitchComp = v; } }),
        h('p', { class: 'hint' }, 'The stereo fit fails on some frames (a close lead hides the road, night texture) and falls back to the IMU plane. The IMU plane carries a 0.3° calibration bias and leaks 0.12° per m/s² of braking, because an accelerometer cannot tell a dive from a deceleration (sim values, ASSUMED). The static plane is the plan\'s worst case: 1° of pitch moves a 20 m lane point to 15.7 m.')),
      section('drive-motion', 'Motion and latency', false,
        chips({ id: 'comp', options: [['photon', 'Predict to photon time'], ['now', 'Predict to draw time (plan formula)'], ['off', 'No compensation']], value: S.compensation, onChange: (v) => { S.compensation = v; } }),
        h('div', { class: 'ctl' }, h('label', {}, h('span', {}, 'Motion-to-photon, whole chain'), latOut)), latDetails,
        h('h3', {}, 'GPU (Orin NX, plan 5.6)'),
        h('div', { class: 'row' }, h('span', { class: 'muted', style: { fontSize: '12px' } }, 'ZED depth mode'), chips({ id: 'depth', options: [['light', 'NEURAL_LIGHT (8 ms)'], ['neural', 'NEURAL (20 ms)']], value: S.depthMode, onChange: (v) => { S.depthMode = v; } })),
        toggle({ id: 'faceJ', label: 'Face landmarks on the Jetson (not the OAK-D)', checked: S.faceOnJetson, onChange: (v) => { S.faceOnJetson = v; } }),
        h('div', { class: 'row' }, h('span', { class: 'muted', style: { fontSize: '12px' } }, 'Camera-rate topics'), chips({ id: 'camrate', options: [['auto', 'Auto (20 Hz when over budget)'], ['30', '30 Hz'], ['20', '20 Hz']], value: String(S.cameraRate), onChange: (v) => { S.cameraRate = v === 'auto' ? 'auto' : Number(v); } })),
        h('p', { class: 'hint' }, 'hudd draws for a 60 Hz vsync train and latches the topics late in the frame. When the GPU is busy with perception its pass overruns the budget (the render slider), the panel repeats a frame and the late frame goes out one vsync later. The age shown is the frame\'s own; the residual sawtooths with the 16.7 ms display hold.')),
      section('drive-head', 'Head tracking', false,
        toggle({ id: 'track', label: 'Head tracker (OAK-D Pro) on', checked: S.headTracking, onChange: (v) => { S.headTracking = v; } }),
        toggle({ id: 'sway', label: 'Sway the head ±75 mm (acceptance test)', checked: this.head.sway, onChange: (v) => { this.head.sway = v; } }),
        this.headX, this.headY,
        h('div', { class: 'row' }, btn('Tracker loses the face for 3 s', () => { hs.trackerDropout(3); toast('eyePose confidence drops: after 500 ms hudd falls back to the nominal eye and shows the glyph'); })),
        h('p', { class: 'hint' }, 'eyePose arrives at 30 Hz, 40 ms late (30 to 50 in the plan), with 3 mm of noise. Once the newest confident message is older than 500 ms, hudd draws for the nominal eye point and lights the glyph in the speed block.')),
      section('drive-rules', 'Rules and faults', false,
        h('div', { class: 'row' }, btn('Clutter mode (10 s)', () => this.clutter()), btn('Reset head and view', () => { this.head.user.set(0, 0, 0); this.updateHeadSliders(); this.look.yaw = this.look.pitch = 0; })),
        toggle({ id: 'gnss', label: 'GNSS outage (speed shows a dash)', checked: S.gnssOutage, onChange: (v) => { S.gnssOutage = v; } }),
        toggle({ id: 'sunwatch', label: 'Sun-watch rule armed', checked: S.sunWatch, onChange: (v) => { S.sunWatch = v; } }),
        toggle({ id: 'link', label: 'Jetson silent on the controller\'s USB (fail-safe after 5 s)', checked: S.linkLost, onChange: (v) => { S.linkLost = v; } }),
        h('h3', {}, 'Crash a process (the supervisor restarts it after 1 s)'),
        h('div', { class: 'row' },
          btn('roadd', () => { hs.crash('roadd'); toast('roadd crashed: lanes and objects go stale, fade at 250 ms, gone at 600 ms; back after the restart and 3 confident frames'); }),
          btn('headtrackd', () => { hs.crash('headtrackd'); toast('headtrackd crashed: nominal eye after 500 ms, glyph on'); }),
          btn('egod', () => { hs.crash('egod'); toast('egod crashed: prediction off at 200 ms, speed dash at 1 s'); }),
          btn('hudd', () => { hs.crash('hudd'); toast('hudd crashed: the panel goes black until the restart'); })),
        h('p', { class: 'hint' }, 'Every message carries its capture time and empty messages are still published, so hudd knows a topic has gone quiet and applies the stale rules rather than drawing an empty road.')),
    );
    const ok = (b) => (b ? 'good' : 'bad');
    const dist = (v) => (v > 1 / GM.FAR_IMAGE ? `${(1 / v).toFixed(1)} m` : v > 0 ? 'beyond 300 m' : `past infinity (${v.toFixed(2)} D)`);
    const focusRows = () => {
      const f = g.focusStats();
      const fig = (MIRRORS.find((m) => m[0] === GM.MIRROR.mode) || [0, GM.MIRROR.mode])[1];
      const glass = (GLASS_LABELS.find((x) => x[0] === this.glassKey()) || [0, `${GM.GLASS.Rh} m × ${GM.GLASS.Rv} m`])[1];
      return [
        ['Mirror and windshield', `${fig}; ${glass}`],
        ['Image distance, window centre', f.centre ? `sagittal ${dist(f.centre.Vs)}, tangential ${dist(f.centre.Vt)}` : '– (no ray)'],
        ['Astigmatism, worst in the window', `${f.astig.toFixed(2)} D${f.pastFrac > 0.005 ? ` · ${Math.round(f.pastFrac * 100)}% of the window past infinity` : ''}`, f.astig <= 0.25 ? 'good' : f.astig <= 0.5 ? 'warn' : 'bad'],
        [`Focus blur (${f.pupilMm.toFixed(0)} mm pupil, focused at ${f.A > 0 ? (1 / f.A).toFixed(1) + ' m' : 'infinity'})`, `${f.blurCentre == null ? '–' : f.blurCentre.toFixed(1)}′ centre, ${f.blurWorst.toFixed(1)}′ worst${g.focus.on ? '' : ' (not drawn)'}`, f.blurWorst <= 2 ? 'good' : f.blurWorst <= 5 ? 'warn' : 'bad'],
      ];
    };
    const rows = () => {
      const st = hs.stats, lum = hs.lum, env = g.world.env || {}, ps = hs.planeStats, tm = hs.timing;
      const lead = hs.lead;
      return [
        ['Speed (GNSS)', S.gnssOutage ? '–' : `${Math.round(g.ego.speed * MPH)} mph`],
        ['Lead gap', lead ? `${Math.max(0, lead.p.x - 2.45).toFixed(0)} m${g.ego.speed > 3 ? ` · ${(Math.max(0, lead.p.x - 2.45) / g.ego.speed).toFixed(1)} s` : ''}` : 'none in the ribbon'],
        ['Registration, lead', st.residualLead == null ? '– (chevron not in the window)' : `${st.residualLead.toFixed(2)}°${st.residualLeadFlat != null && Math.abs(st.residualLeadFlat - st.residualLead) > 0.02 ? ` (a plane model would say ${st.residualLeadFlat.toFixed(2)}°)` : ''}`, st.residualLead == null ? 'muted' : st.residualLead <= 0.3 ? 'good' : st.residualLead <= 0.5 ? 'warn' : 'bad'],
        ['Registration, lane 20 m', st.residualLane == null ? '– (not in the window)' : `${st.residualLane.toFixed(2)}°${st.residualLaneFlat != null && Math.abs(st.residualLaneFlat - st.residualLane) > 0.02 ? ` (plane model ${st.residualLaneFlat.toFixed(2)}°)` : ''}`, st.residualLane == null ? 'muted' : st.residualLane <= 0.3 ? 'good' : st.residualLane <= 0.5 ? 'warn' : 'bad'],
        ['Lane point 20 m, point-wise (range error shows)', st.residualLanePoint == null ? '–' : `${st.residualLanePoint.toFixed(2)}°`, st.residualLanePoint == null ? 'muted' : st.residualLanePoint <= 0.3 ? 'good' : st.residualLanePoint <= 0.5 ? 'warn' : 'bad'],
        ['Body pitch, roll', `${(g.ego.pitch / DEG).toFixed(2)}°, ${(g.ego.roll / DEG).toFixed(2)}° · ${g.ego.accel >= 0 ? '+' : ''}${g.ego.accel.toFixed(1)} m/s²`],
        ['Ground plane', `${({ stereo: 'stereo fit', imu: 'IMU fallback', static: 'static' })[ps.used] || ps.used}${ps.mode === 'stereo' ? ` · fit failed ${(ps.failRate * 100).toFixed(0)}% of frames` : ''}`],
        ['Plane error (pitch, roll)', `${(ps.pitchErr * 60).toFixed(1)}′, ${(ps.rollErr * 60).toFixed(1)}′`, Math.abs(ps.pitchErr) <= 0.15 ? 'good' : Math.abs(ps.pitchErr) <= 0.5 ? 'warn' : 'bad'],
        ['Registration, window marks (16 and 24 m)', st.residualMarks == null ? '– (none in the window)' : `${(st.residualMarks * 60).toFixed(0)}′ worst of four`, st.residualMarks == null ? 'muted' : st.residualMarks <= 0.1 ? 'good' : st.residualMarks <= 0.3 ? 'warn' : 'bad'],
        ['Vergence conflict, lead marker', `${(st.binocularLead || 0).toFixed(0)}′ (lane ${(st.binocularLane || 0).toFixed(0)}′)`, (st.binocularLead || 0) <= 10 ? 'good' : (st.binocularLead || 0) <= 20 ? 'warn' : 'bad'],
        ['Age as drawn (lanes, objects)', `${Math.round(st.ageLanes * 1000)} ms${st.ageLanes > 0.25 ? ' · stale, fading' : ''}`, st.ageLanes <= 0.25 ? 'good' : 'warn'],
        ['Motion-to-photon', `${Math.round(hs.latency.total * 1000)} ms budget · this frame ${Math.round((tm.photon - (hs.msg ? hs.msg.tc : tm.photon)) * 1000)} ms`, ok(hs.latency.total <= 0.09)],
        ['hudd frame', `${tm.renderMs.toFixed(1)} ms of ${S.lat[3]} ms${tm.late ? ' · late (frame dropped)' : ''} · ${st.dropped} dropped`, tm.late ? 'warn' : 'good'],
        ['GPU per frame', `${tm.gpuMs.toFixed(0)} ms serial · ${Math.round(tm.gpuLoad * 100)}% of the ${(1000 / tm.camHz).toFixed(0)} ms frame · camera topics ${tm.camHz} Hz`, tm.gpuLoad <= 1 ? 'good' : 'bad'],
        ['Processes', ['roadd', 'headtrackd', 'egod', 'hudd'].map((n) => `${n} ${hs.processState(n, tm.draw)}`).join(' · '), ['roadd', 'headtrackd', 'egod', 'hudd'].every((n) => hs.processState(n, tm.draw) === 'up') ? 'good' : 'bad'],
        ['ego topic age', `${Math.round(tm.egoAge * 1000)} ms${tm.egoAge > 1 ? ' · speed dashed' : tm.egoAge > 0.2 ? ' · prediction off' : ''}`, tm.egoAge <= 0.2 ? 'good' : 'bad'],
        ['eyePose', `${tm.eyeState} · ${tm.eyeAge < 5 ? Math.round(tm.eyeAge * 1000) + ' ms old' : 'none'} · confidence ${hs.eye.conf.toFixed(2)}`, tm.eyeState === 'tracking' ? 'good' : tm.eyeState === 'off' ? 'muted' : 'warn'],
        ['Backlight duty', `${(lum.duty * 100).toFixed(lum.duty < 0.1 ? 1 : 0)}%`],
        ['Panel luminance', `${Math.round(lum.Lpanel).toLocaleString()} cd/m²`],
        ['At the eye', `${Math.round(lum.Leye).toLocaleString()} cd/m²${S.eyewear !== 'none' ? ` · through the glasses ${Math.round(lum.Leye * hs.eyewear().image).toLocaleString()} (scene × ${hs.eyewear().scene.toFixed(2)})` : ''}`, env.name === 'night' ? ok(lum.Leye <= S.nightCeiling + 0.5) : ok(lum.Leye >= 1500)],
        ['Contrast vs sky', `${lum.contrastSky.toFixed(2)}`, ok(lum.contrastSky >= 1.15)],
        ['Contrast vs road', `${lum.contrastRoad.toFixed(2)}`, ok(lum.contrastRoad >= 1.15)],
        ['Black level at the eye', `${lum.black.toFixed(2)} cd/m²`, lum.black <= 0.1 ? 'good' : 'warn'],
        ['Scene', `${env.name || ''}: sky ${Math.round(env.L_sky || 0).toLocaleString()}, road ${Math.round(env.L_road || 0).toLocaleString()} cd/m²`],
        ['Cell temperature', `${hs.thermal.cell.toFixed(0)} °C (${hs.thermal.state})`, hs.thermal.state === 'ok' ? 'good' : 'bad'],
        ['Sun elevation', `${hs.sun.elev.toFixed(0)}°${hs.sun.elev > 0 ? ` · patch offset ${hs.sun.dAz.toFixed(0)}°, ${hs.sun.dEl.toFixed(0)}°` : ''}`],
        ['Shutter', hs.shutter.open > 0.5 ? 'open' : `closed: ${hs.shutter.reason}`, hs.shutter.open > 0.5 ? 'good' : 'warn'],
        ['Eye offset (true)', `${(hs.eye.trueOffset.z * 1000).toFixed(0)}, ${(hs.eye.trueOffset.y * 1000).toFixed(0)} mm`],
        ['Window visible', `${Math.round((this.vigFrac ?? 1) * 100)}%`, (this.vigFrac ?? 1) > 0.97 ? 'good' : 'warn'],
        ['Window', `${hs.plane.fovW.toFixed(1)}° × ${hs.plane.fovH.toFixed(1)}° at ${hs.plane.dist.toFixed(2)} m${g.vimgSurface ? ` (drawn on the image surface, ${g.vimgSurface.dmin.toFixed(1)} m to ${g.vimgSurface.dmax >= GM.FAR_IMAGE ? 'past infinity' : g.vimgSurface.dmax.toFixed(1) + ' m'})` : ''}`],
        ...focusRows(),
        ['Road covered (flat)', `${GM.ROAD_NEAR.toFixed(1)}–${GM.ROAD_FAR.toFixed(1)} m ahead`],
      ];
    };
    // The gates the plan sets stay in view; the rest of the readout folds away.
    const GATES = new Set(['Registration, lead', 'Registration, lane 20 m', 'Motion-to-photon', 'At the eye', 'Contrast vs sky', 'Contrast vs road', 'Shutter', 'Window visible']);
    this.liveKey = liveKv(() => rows().filter((r) => GATES.has(r[0])));
    this.liveAll = liveKv(() => rows().filter((r) => !GATES.has(r[0])));
    setPanel('right',
      h('h2', {}, 'Live numbers'),
      h('p', { class: 'hint' }, 'Against the plan\'s acceptance criteria; green meets the gate.'),
      this.liveKey,
      section('drive-more', 'All readouts', false, this.liveAll),
      section('drive-g1', 'Perception score (gate G1, plan 5.7)', false,
        h('p', { class: 'hint' }, 'Scored live against the world\'s truth over the last 300 captures, as the 300 hand-labelled frames of the demo course would score roadd.'),
        (this.liveG1 = liveKv(() => {
          const sc = hs.score, pct = (r) => (isFinite(r.mean) ? `${Math.round(r.mean * 100)}%` : '–'), m = (r) => (isFinite(r.mean) ? `${r.mean.toFixed(2)} m` : '–');
          const g = (r, th, pass) => (isFinite(r.mean) ? (pass(r.mean) ? 'good' : 'bad') : 'muted');
          return [
            ['Ego lane found (≥ 95%)', pct(sc.egoLane), g(sc.egoLane, 0.95, (v) => v >= 0.95)],
            ['Lane lateral error at 10 m (≤ 0.15 m)', m(sc.lat10), g(sc.lat10, 0.15, (v) => v <= 0.15)],
            ['Lane lateral error at 20 m (≤ 0.3 m)', m(sc.lat20), g(sc.lat20, 0.3, (v) => v <= 0.3)],
            ['Lane lateral error at 30 m (≤ 0.5 m)', m(sc.lat30), g(sc.lat30, 0.5, (v) => v <= 0.5)],
            ['Ego-lane vehicles within 50 m recalled (≥ 90%)', pct(sc.vehRecall), g(sc.vehRecall, 0.9, (v) => v >= 0.9)],
            ['Pedestrians within 30 m recalled (≥ 85%)', pct(sc.pedRecall), g(sc.pedRecall, 0.85, (v) => v >= 0.85)],
            ['Vehicle range error (≤ 10%)', isFinite(sc.rangeErr.mean) ? `${(sc.rangeErr.mean * 100).toFixed(1)}%` : '–', g(sc.rangeErr, 0.1, (v) => v <= 0.1)],
            ['Captures scored', `${Math.min(300, sc.frames)} of 300`],
          ];
        }))),
      section('drive-notes', 'What the simulation found', false,
        h('div', { class: 'note' }, 'The image is not at one distance: the toroid puts it on a surface from about 5 m at the top of the window outward (the trace, confirmed by Cycles), and the Driver view draws it there. In the ±75 mm sway test a hudd that projects onto a plane, as the plan has it, leaves the lead marker about 0.3° off; the image-surface map helps on one side only; projecting by the optical model from the tracked eye (Optics chips) registers within 2′, which Cycles confirmed end to end through the real optics at 60 and 75 mm. hudd needs the optical model, or a calibrated eye-to-panel map, on the Jetson; it costs ray tracing per symbol here, a lookup table there.'),
        h('div', { class: 'note' }, 'The lower edge of the eye box is the housing, not the optics: its lid rises to 1.10 m at the rear, and the line from the eye to the bottom of the window clears that edge by 43 mm at the nominal eye, 11 mm at the plan\'s lowest eye and nothing at 45 mm down (Cycles: half the window gone at 70 mm down). Twenty millimetres off the housing\'s rear height is twenty millimetres of eye box.'),
        h('div', { class: 'note' }, 'The eyes converge on a symbol at its image distance and on the car at the car\'s: with the lead marker near the top of the window, where the toroid\'s image is about 5 m away, that vergence conflict runs about 50′ for the lead car, well beyond the 10 to 20′ the eyes fuse (assumed limits), so the marker doubles when the driver looks at the car. The flat freeform image (7 to 12 m) brings it to about 19′, at the edge of fusion. A far-registered symbol needs a far image: a longer image distance, or symbols that do not pretend to sit on the car.'),
        h('div', { class: 'note' }, `Look-down ${R.LOOKDOWN}° with a ${R.FOV_H.toFixed(1)}° tall window covers the road only from ${GM.ROAD_NEAR.toFixed(0)} to ${GM.ROAD_FAR.toFixed(0)} m: a lead car farther than that sits above the window and gets no chevron.`),
        h('div', { class: 'note' }, `The ${R.FOV_W.toFixed(1)}° window is narrower than a 3.7 m lane closer than about ${(1.85 / Math.tan(R.FOV_W / 2 * Math.PI / 180)).toFixed(1)} m, so the ribbon fills the window's whole width low down; the lane edges enter it only near the top. That is the specified window, not a fault.`)));
    hidePanel('bottom');
    // mini views: the PGU frame and the audience view, one at a time in the dock under the readouts
    g.hud.canvas.style.width = '100%'; g.hud.canvas.style.height = '100%';
    g.audience.style.width = '100%'; g.audience.style.height = '100%';
    this.roadCanvas.style.width = '100%'; this.roadCanvas.style.height = '100%';
    setDock([
      { label: 'PGU frame', title: '946 × 473 px, as hudd draws it', el: g.hud.canvas, aspect: CROP_W / CROP_H },
      { label: 'Road camera', title: 'ZED 2i left image with roadd\'s lane points, tracks and ground plane', el: this.roadCanvas, aspect: 16 / 9 },
      { label: 'Audience view', title: 'Monitor 2 on the passenger headrest', el: g.audience, aspect: 960 / 600 },
      cyclesDockView(this.cycles),
    ].filter(Boolean));
  }

  updateHeadSliders() { this.headX && this.headX.set(Math.round(this.head.user.z * 1000)); this.headY && this.headY.set(Math.round(this.head.user.y * 1000)); }

  sunScenario() {
    // Choose a time and heading where the sun sits in the patch behind the car: elevation 51 deg. Find the time of day
    // with that elevation in the afternoon, then the road station whose heading points away from the sun.
    const w = this.g.world;
    if (!w.setTimeOfDay || !w.road) { toast('The world has no solar model'); return; }
    let best = null;
    for (let tod = 12; tod <= 18; tod += 0.02) {
      w.setTimeOfDay(tod);
      const el = Math.asin(w.sunDir.y) / DEG;
      if (Math.abs(el - (180 - R.SUN_ELEV)) < 0.6) { best = tod; break; }
    }
    if (best === null) best = 15.3;
    this.timeOfDay = best;
    this.applyEnv('day');
    this.envChips && this.envChips.set('day');
    const sun = w.sunDir.clone(); sun.y = 0; sun.normalize();
    let bestS = this.g.ego.s, bestDot = 2;
    for (let s = this.g.ego.s + 150; s < this.g.ego.s + 150 + w.road.length; s += 10) {
      const smp = w.road.sample(s);
      const d = smp.t.dot(sun);
      if (d < bestDot) { bestDot = d; bestS = s; }
    }
    this.g.ego.s = (bestS - 250 + w.road.length) % w.road.length;
    this.g.hud.hist.length = 0; this.g.hud.k = -1;
    this.todSlider && this.todSlider.set(best);
    toast('Sun at about 51° behind the car on the stretch ahead. Watch the shutter close.');
  }

  update(t, dt) {
    const g = this.g, w = g.world, hs = g.hud;
    this.t = t;
    // drive
    const e = g.ego;
    let accel = 0;
    if (!this.paused && dt > 0) {
      const D = this.driver;
      let want = this.speedTarget;
      // keep a time gap behind the lead the HUD has (a driver reacting to the car ahead), braking as needed
      const lead = hs.lead;
      let brakeLimit = 2.5;                       // comfort braking; the full 6 m/s^2 only when the gap closes fast
      if (D.keepGap && lead && lead.o) {
        const gap = Math.max(0, lead.p.x - 2.45), vLead = Math.max(0, lead.o.speed != null ? lead.o.speed : e.speed);
        const vGap = clamp(vLead + (gap - D.timeGap * e.speed - 3) / 2.5, 0, 99);
        want = Math.min(want, vGap);
        const closing = e.speed - vLead, ttc = closing > 0.3 ? gap / closing : 99;
        if (ttc < 2.5 || gap < 0.6 * e.speed) brakeLimit = D.maxBrake;
        else if (ttc < 5) brakeLimit = 4;
      }
      let a = clamp((want - e.speed) / 1.0, -brakeLimit, D.maxAccel);
      if (this.manoeuvre) { if (t < this.manoeuvre.until && (this.manoeuvre.accel > 0 ? e.speed < 36 : e.speed > 0.5)) a = this.manoeuvre.accel; else this.manoeuvre = null; }
      const v0 = e.speed;
      e.speed = clamp(e.speed + a * dt, 0, 40);
      accel = (e.speed - v0) / dt;
      e.s = (e.s + e.speed * dt) % w.road.length;
      e.wander = 0.12 * Math.sin(t * 0.7) + 0.05 * Math.sin(t * 1.9);
      e.offset = w.lanes.ego.center + e.wander;
    }
    g.updateDynamics(this.paused ? 0 : dt, e.speed, accel, w.road.sample(e.s).curvature || 0);
    const pose = g.placeEgo(t);
    w.update(this.paused ? 0 : dt, { s: e.s, offset: e.offset, speed: this.paused ? 0 : e.speed });
    w.followTarget && w.followTarget(g.carGroup.position);
    g.car.update && g.car.update(dt, this.paused ? 0 : e.speed, Math.atan(2.85 * (pose.curvature || 0)));
    // head
    const k = 0.25 * dt;
    if (this.keys.has('arrowleft')) this.head.user.z = clamp(this.head.user.z - k, -0.15, 0.15);
    if (this.keys.has('arrowright')) this.head.user.z = clamp(this.head.user.z + k, -0.15, 0.15);
    if (this.keys.has('arrowup')) this.head.user.y = clamp(this.head.user.y + k, -0.08, 0.08);
    if (this.keys.has('arrowdown')) this.head.user.y = clamp(this.head.user.y - k, -0.08, 0.08);
    if (this.keys.size) this.updateHeadSliders();
    const sway = this.head.sway ? this.head.swayAmp * Math.sin(t * 2 * Math.PI / 4) : 0;
    const bob = (e.speed > 1 ? 0.0025 : 0) * Math.sin(t * 2 * Math.PI * 1.7);
    const eyeOff = new THREE.Vector3(0, this.head.user.y + bob, this.head.user.z + sway);
    g.car.driver && g.car.driver.setHeadOffset && g.car.driver.setHeadOffset(eyeOff);
    // HUD software
    const sunDirCar = w.sunDir ? g.toCarDir(w.sunDir) : null;
    hs.update(t, dt, { sunDirCar, eyeOffset: eyeOff, ambientLux: g.ambientLux() });
    // virtual image light
    // the scene through the driver's eyewear (the renderer's exposure), and the image through it (its polarisation)
    const ew = hs.eyewear();
    const envExp = (w.env && w.env.exposure) || 1;
    if (Math.abs(this.app.renderer.toneMappingExposure - envExp * ew.scene) > 1e-6) this.app.renderer.toneMappingExposure = envExp * ew.scene;
    const exposure = this.app.renderer.toneMappingExposure;
    const gain = hs.overlayGain(exposure) * ew.image;
    g.vimgMain.material.color.setScalar(gain);
    g.vimgGhost.material.color.setScalar(hs.settings.ghost ? gain : 0);
    const env = w.env || { L_adapt: 5000 };
    g.vimgBlack.material.color.setScalar(hs.lum.black / env.L_adapt * 0.18 / exposure * hs.shutter.open * ew.image);
    // the panel's pixels show in the loupe views (87 px per degree; the ghost sits 2.1 px away)
    const nearest = this.look.fov < 8;
    const want = nearest ? THREE.NearestFilter : THREE.LinearFilter;
    if (hs.texture.magFilter !== want) { hs.texture.magFilter = want; hs.texture.needsUpdate = true; }
    // eye-box vignette (10 Hz)
    if (t - this.vigT > 0.1) { this.vigT = t; this.vigFrac = g.updateVignette(eyeOff); }
    // camera at the true eye
    this.camera.position.copy(GM.EYE).add(eyeOff);
    const dir = GM.LOOK.clone();
    dir.applyAxisAngle(new THREE.Vector3(0, 1, 0), -this.look.yaw * DEG);
    const right = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0)).normalize();
    dir.applyAxisAngle(right, this.look.pitch * DEG);
    const zoomed = this.look.fov < 20;
    // zoomed views look at the window centre
    const lookDir = zoomed && Math.abs(this.look.yaw) < 1e-3 && Math.abs(this.look.pitch) < 1e-3 ? GM.LOOK.clone() : dir;
    const target = this.camera.position.clone().add(lookDir);
    // lookAt works in world space; the camera is a child of the car, so convert the car-frame target
    const worldTarget = g.carGroup.localToWorld(target.clone());
    this.camera.up.copy(new THREE.Vector3(0, 1, 0).applyQuaternion(g.carGroup.quaternion));
    this.camera.lookAt(worldTarget);
    if (Math.abs(this.camera.fov - this.look.fov) > 0.01) { this.camera.fov = this.look.fov; this.camera.updateProjectionMatrix(); }
    // audience view (5 Hz): render the driver camera's view of the driver
    if (t - this.audT > 0.2 && !this.app.warming) {
      this.audT = t;
      this.renderDriverCam();
      g.drawAudience(this.driverCanvas);
      this.renderRoadCam();
    }
    if (this.liveKey && (Math.floor(t * 8) !== Math.floor((t - dt) * 8))) { this.liveKey.refresh(); this.liveAll.refresh(); this.liveG1 && this.liveG1.refresh(); }
  }

  // The ZED 2i's left image at 5 Hz with what roadd published for the newest capture drawn over it: lane points by
  // confidence, tracks with class, range and age, the lead, and the fitted ground plane as a grid; a stamp when
  // roadd is down. The projection is the camera's own pinhole (72 x 44 deg), not the HUD's.
  renderRoadCam() {
    const g = this.g, r = this.app.renderer, hs = g.hud, W = 480, H = 270;
    const cam = this.roadCam;
    if (cam.parent !== g.carGroup) g.carGroup.add(cam);
    cam.position.copy(GM.ROAD_CAM);
    const aimL = g.carGroup.localToWorld(GM.ROAD_CAM.clone().add(new THREE.Vector3(Math.cos(2 * DEG), -Math.sin(2 * DEG), 0)));
    cam.up.copy(new THREE.Vector3(0, 1, 0).applyQuaternion(g.carGroup.quaternion));
    cam.lookAt(aimL);
    cam.updateMatrixWorld(true);
    const vis = g.vimg.visible; g.vimg.visible = false;
    const zed = g.installed.zed2i; if (zed) zed.holder.visible = false;
    r.setRenderTarget(this.roadRT);
    r.render(g.scene, cam);
    r.readRenderTargetPixels(this.roadRT, 0, 0, W, H, this.roadPx);
    r.setRenderTarget(null);
    g.vimg.visible = vis; if (zed) zed.holder.visible = true;
    const ctx = this.roadCanvas.getContext('2d');
    const img = ctx.createImageData(W, H), px = this.roadPx, d = img.data;
    // the render target is linear light; a camera's response: exposure, a soft shoulder, gamma
    const exp = 1.6;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const si = ((H - 1 - y) * W + x) * 4, di = (y * W + x) * 4;
      for (let c = 0; c < 3; c++) { const l = px[si + c] / 255 * exp; d[di + c] = 255 * Math.pow(l / (1 + l), 1 / 2.2); }
      d[di + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
    const m = hs.msg, down = hs.processDown('roadd', hs.timing.draw);
    const proj = (p) => {                         // body-frame point -> image pixel through this camera
      const w = g.carGroup.localToWorld(p.clone()).project(cam);
      if (w.z > 1) return null;
      return [(w.x * 0.5 + 0.5) * W, (-w.y * 0.5 + 0.5) * H];
    };
    ctx.font = '600 11px "Helvetica Neue", Helvetica, Arial, sans-serif'; ctx.textBaseline = 'top'; ctx.textAlign = 'left';
    ctx.fillStyle = 'rgba(0,0,0,0.45)'; ctx.fillRect(0, 0, W, 18);
    ctx.fillStyle = '#dfe6ee';
    ctx.fillText(`ZED 2i left · ${hs.timing.camHz} Hz · roadd ${down ? 'DOWN' : 'up'}${m ? ` · capture ${m.k} · ${hs.planeStats.used} plane, pitch ${(Math.atan2(m.plane.n.x, m.plane.n.y) / DEG).toFixed(2)}°` : ''}`, 6, 4);
    if (!m || down) { ctx.fillStyle = 'rgba(255,107,107,0.9)'; ctx.font = '700 20px "Helvetica Neue", Helvetica, Arial, sans-serif'; ctx.fillText(down ? 'roadd down: no lanes, no objects' : 'no capture yet', 12, 30); return; }
    // the fitted ground plane as a grid (n . p = d)
    ctx.strokeStyle = 'rgba(80,220,140,0.35)'; ctx.lineWidth = 1;
    const onPlane = (x, z) => new THREE.Vector3(x, (m.plane.d - m.plane.n.x * x - m.plane.n.z * z) / m.plane.n.y, z);
    for (let x = 6; x <= 46; x += 5) { const a = proj(onPlane(x, -7)), b = proj(onPlane(x, 7)); if (a && b) { ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); } }
    for (let z = -7; z <= 7; z += 2) { const a = proj(onPlane(6, z)), b = proj(onPlane(46, z)); if (a && b) { ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); } }
    // the 35 m stereo range limit
    { const a = proj(onPlane(35, -8)), b = proj(onPlane(35, 8)); if (a && b) { ctx.strokeStyle = 'rgba(255,192,77,0.6)'; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); ctx.setLineDash([]); ctx.fillStyle = 'rgba(255,192,77,0.9)'; ctx.fillText('35 m: stereo range; beyond, the plane', b[0] - 150, b[1] - 13); } }
    // lane points, coloured by confidence
    for (const ln of m.lanes) {
      for (const q of ln.pts) {
        const s = proj(q.p); if (!s) continue;
        const c = q.conf;
        ctx.fillStyle = c > 0.6 ? `rgba(94,200,255,${0.5 + 0.5 * c})` : `rgba(255,120,120,${0.4 + 0.6 * c})`;
        ctx.beginPath(); ctx.arc(s[0], s[1], ln.type === 'other' ? 1.6 : 2.4, 0, 7); ctx.fill();
      }
      const first = ln.pts.find((q) => q.p.x > 8 && q.p.x < 14);
      if (first) { const s = proj(first.p); if (s) { ctx.fillStyle = '#9fd3ff'; ctx.fillText(`${ln.type} ${ln.conf.toFixed(2)}`, s[0] + 4, s[1] - 12); } }
    }
    // tracks: boxes with class, range and track age; the lead in amber
    for (const tr of hs.tracks.values()) {
      const o = tr.obj; if (!o || m.tc - tr.lastSeen > 0.4) continue;
      const hx = o.kind === 'person' ? 0.3 : o.kind === 'bicycle' ? 0.9 : o.length / 2, hz = (o.width || 0.6) / 2, hh = o.height || 1.7;
      const pts = [];
      for (const dx of [-hx, hx]) for (const dz of [-hz, hz]) for (const dy of [0, hh]) { const s = proj(new THREE.Vector3(o.p.x + dx, (o.p.y || 0) + dy, o.p.z + dz)); if (s) pts.push(s); }
      if (pts.length < 8) continue;
      const xs = pts.map((q) => q[0]), ys = pts.map((q) => q[1]);
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
      const isLead = hs.lead && hs.lead.o.id === o.id, haz = o.kind === 'person' || o.kind === 'bicycle';
      ctx.strokeStyle = isLead ? 'rgba(255,190,90,0.95)' : haz ? 'rgba(255,140,60,0.9)' : tr.count >= 3 ? 'rgba(200,220,255,0.85)' : 'rgba(200,220,255,0.35)';
      ctx.lineWidth = isLead ? 2 : 1;
      ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
      const range = o.p.clone().sub(new THREE.Vector3(GM.ROAD_CAM.x, 0, GM.ROAD_CAM.z)).length();
      ctx.fillStyle = ctx.strokeStyle;
      ctx.fillText(`${o.kind} ${range.toFixed(0)} m${range > 35 ? ' (plane)' : ''} · ${tr.count < 3 ? `${tr.count}/3` : 'track'}${isLead ? ' · LEAD' : ''}`, x0, Math.max(20, y0 - 12));
    }
  }

  renderDriverCam() {
    const g = this.g, r = this.app.renderer;
    if (this.driverCam.parent !== g.carGroup) g.carGroup.add(this.driverCam);
    this.driverCam.position.copy(GM.DRIVER_CAM).add(new THREE.Vector3(0.0, 0.0, 0));
    const tgt = g.carGroup.localToWorld(GM.EYE.clone().add(this.g.hud.eye.trueOffset));
    this.driverCam.up.copy(new THREE.Vector3(0, 1, 0).applyQuaternion(g.carGroup.quaternion));
    this.driverCam.lookAt(tgt);
    const vis = g.vimg.visible; g.vimg.visible = false;
    const oak = g.installed.oakdPro; if (oak) oak.holder.visible = false;
    const head = g.car.driver && g.car.driver.head; if (head) head.visible = true;
    const prevTM = r.toneMapping;
    r.setRenderTarget(this.driverRT);
    r.render(g.scene, this.driverCam);
    r.readRenderTargetPixels(this.driverRT, 0, 0, 320, 200, this.driverPx);
    r.setRenderTarget(null);
    r.toneMapping = prevTM;
    g.vimg.visible = vis; if (oak) oak.holder.visible = true; if (head) head.visible = false;
    const ctx = this.driverCanvas.getContext('2d');
    const img = ctx.createImageData(320, 200);
    // flip vertically, monochrome IR look
    for (let y = 0; y < 200; y++) for (let x = 0; x < 320; x++) {
      const si = ((199 - y) * 320 + x) * 4, di = (y * 320 + x) * 4;
      // the render target holds linear light: tone-map and gamma-encode it like a camera would
      const lin = (this.driverPx[si] * 0.3 + this.driverPx[si + 1] * 0.59 + this.driverPx[si + 2] * 0.11) / 255 * 2.2;
      const l = 255 * Math.pow(lin / (1 + lin), 1 / 2.2);
      img.data[di] = l; img.data[di + 1] = l; img.data[di + 2] = l; img.data[di + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
    // eye point marker from the tracker
    const eyeW = g.carGroup.localToWorld(GM.EYE.clone().add(this.g.hud.eye.tracked));
    const p = eyeW.project(this.driverCam);
    const px = (p.x * 0.5 + 0.5) * 320, py = (-p.y * 0.5 + 0.5) * 200;
    ctx.strokeStyle = '#5ec8ff'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(px, py, 7, 0, 7); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(px - 12, py); ctx.lineTo(px + 12, py); ctx.moveTo(px, py - 12); ctx.lineTo(px, py + 12); ctx.stroke();
  }
}
