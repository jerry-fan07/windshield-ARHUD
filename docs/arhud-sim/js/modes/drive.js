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
  }

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
      keys(['Arrows', 'move your head'], ['Space', 'clutter mode'], ['L', 'lane filled / blank'], ['P', 'pause'], ['R', 'reset']),
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
        toggle({ id: 'autodim', label: 'Automatic dimming from the ambient sensor', checked: S.autoDim, onChange: (v) => { S.autoDim = v; } }),
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
      section('drive-motion', 'Motion and latency', false,
        chips({ id: 'comp', options: [['photon', 'Predict to photon time'], ['now', 'Predict to draw time (plan formula)'], ['off', 'No compensation']], value: S.compensation, onChange: (v) => { S.compensation = v; } }),
        h('div', { class: 'ctl' }, h('label', {}, h('span', {}, 'Motion-to-photon, whole chain'), latOut)), latDetails),
      section('drive-head', 'Head tracking', false,
        toggle({ id: 'track', label: 'Head tracker (OAK-D Pro) on', checked: S.headTracking, onChange: (v) => { S.headTracking = v; } }),
        toggle({ id: 'sway', label: 'Sway the head ±75 mm (acceptance test)', checked: this.head.sway, onChange: (v) => { this.head.sway = v; } }),
        this.headX, this.headY),
      section('drive-rules', 'Rules and faults', false,
        h('div', { class: 'row' }, btn('Clutter mode (10 s)', () => this.clutter()), btn('Reset head and view', () => { this.head.user.set(0, 0, 0); this.updateHeadSliders(); this.look.yaw = this.look.pitch = 0; })),
        toggle({ id: 'gnss', label: 'GNSS outage (speed shows a dash)', checked: S.gnssOutage, onChange: (v) => { S.gnssOutage = v; } }),
        toggle({ id: 'sunwatch', label: 'Sun-watch rule armed', checked: S.sunWatch, onChange: (v) => { S.sunWatch = v; } })),
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
      const st = hs.stats, lum = hs.lum, env = g.world.env || {};
      const lead = hs.lead;
      return [
        ['Speed (GNSS)', S.gnssOutage ? '–' : `${Math.round(g.ego.speed * MPH)} mph`],
        ['Lead gap', lead ? `${Math.max(0, lead.p.x - 2.45).toFixed(0)} m${g.ego.speed > 3 ? ` · ${(Math.max(0, lead.p.x - 2.45) / g.ego.speed).toFixed(1)} s` : ''}` : 'none in the ribbon'],
        ['Registration, lead', st.residualLead == null ? '– (chevron not in the window)' : `${st.residualLead.toFixed(2)}°${st.residualLeadFlat != null && Math.abs(st.residualLeadFlat - st.residualLead) > 0.02 ? ` (a plane model would say ${st.residualLeadFlat.toFixed(2)}°)` : ''}`, st.residualLead == null ? 'muted' : st.residualLead <= 0.3 ? 'good' : st.residualLead <= 0.5 ? 'warn' : 'bad'],
        ['Registration, lane 20 m', st.residualLane == null ? '– (not in the window)' : `${st.residualLane.toFixed(2)}°${st.residualLaneFlat != null && Math.abs(st.residualLaneFlat - st.residualLane) > 0.02 ? ` (plane model ${st.residualLaneFlat.toFixed(2)}°)` : ''}`, st.residualLane == null ? 'muted' : st.residualLane <= 0.3 ? 'good' : st.residualLane <= 0.5 ? 'warn' : 'bad'],
        ['Registration, window marks (16 and 24 m)', st.residualMarks == null ? '– (none in the window)' : `${(st.residualMarks * 60).toFixed(0)}′ worst of four`, st.residualMarks == null ? 'muted' : st.residualMarks <= 0.1 ? 'good' : st.residualMarks <= 0.3 ? 'warn' : 'bad'],
        ['Vergence conflict, lead marker', `${(st.binocularLead || 0).toFixed(0)}′ (lane ${(st.binocularLane || 0).toFixed(0)}′)`, (st.binocularLead || 0) <= 10 ? 'good' : (st.binocularLead || 0) <= 20 ? 'warn' : 'bad'],
        ['Age as drawn (lanes, objects)', `${Math.round(st.ageLanes * 1000)} ms`],
        ['Motion-to-photon', `${Math.round(hs.latency.total * 1000)} ms`, ok(hs.latency.total <= 0.09)],
        ['Backlight duty', `${(lum.duty * 100).toFixed(lum.duty < 0.1 ? 1 : 0)}%`],
        ['Panel luminance', `${Math.round(lum.Lpanel).toLocaleString()} cd/m²`],
        ['At the eye', `${Math.round(lum.Leye).toLocaleString()} cd/m²`, env.name === 'night' ? ok(lum.Leye <= 50.5) : ok(lum.Leye >= 1500)],
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
    setDock([
      { label: 'PGU frame', title: '946 × 473 px, as hudd draws it', el: g.hud.canvas, aspect: CROP_W / CROP_H },
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
    if (!this.paused) {
      e.speed += clamp(this.speedTarget - e.speed, -3 * dt, 2 * dt);
      e.s = (e.s + e.speed * dt) % w.road.length;
      e.wander = 0.12 * Math.sin(t * 0.7) + 0.05 * Math.sin(t * 1.9);
      e.offset = w.lanes.ego.center + e.wander;
    }
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
    const exposure = this.app.renderer.toneMappingExposure;
    const gain = hs.overlayGain(exposure);
    g.vimgMain.material.color.setScalar(gain);
    g.vimgGhost.material.color.setScalar(hs.settings.ghost ? gain : 0);
    const env = w.env || { L_adapt: 5000 };
    g.vimgBlack.material.color.setScalar(hs.lum.black / env.L_adapt * 0.18 / exposure * hs.shutter.open);
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
    }
    if (this.liveKey && (Math.floor(t * 8) !== Math.floor((t - dt) * 8))) { this.liveKey.refresh(); this.liveAll.refresh(); }
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
