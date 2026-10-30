// Build mode: the whole project from the ground up, one step at a time. The bench chapters assemble each part from its
// own pieces in build order; the car chapters install each part and route each cable; the last chapter brings the
// software up and calibrates it.
import * as THREE from 'three';
import * as GM from '../geom.js';
import { P, R } from '../params.js';
import { M, C } from '../mats.js';
import { polyline, DEG, textDecal, clamp, easeInOut, visibleBox } from '../util.js';
import { h, setPanel, hidePanel, btn, kv, tagFor, toast, section } from '../ui.js';
import { build, available, setExplode, REGISTRY } from '../registry.js';
import { Assembler } from './assembler.js';
import { MOUNTS } from '../install.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);
const price = (needle) => {
  const row = P.COST.find((r) => r[0].toLowerCase().includes(needle.toLowerCase()));
  if (!row) return null;
  return row[1] === row[2] ? `$${row[1].toLocaleString()}` : `$${row[1].toLocaleString()}–${row[2].toLocaleString()}`;
};

export class BuildMode {
  constructor(app) {
    this.app = app;
    this.g = app.garage;
    this.bench = new THREE.Group(); this.bench.name = 'bench';
    this.inst = {};            // bench instances
    this.extra = new THREE.Group(); this.extra.name = 'buildExtras';
    this.idx = 0;
    this.playing = false; this.playT = 0;
    this.steps = this.makeSteps();
  }

  // ---- bench helpers ----
  benchComp(id, x = 0, z = 0, opts = {}) {
    let c = this.inst[id];
    if (!c) {
      if (!available(id)) return null;
      c = build(id, opts);
      if (!c) return null;
      c.holder = new THREE.Group(); c.holder.add(c.group);
      c.holder.userData.pickId = id;
      this.inst[id] = c;
    }
    setExplode(c, 0);
    c.group.position.set(0, 0, 0);
    c.holder.position.set(0, 0, 0);
    c.holder.updateMatrixWorld(true);
    const b = visibleBox(c.group);
    const ctr = b.getCenter(new THREE.Vector3());
    c.group.position.set(-ctr.x, -b.min.y + 0.002, -ctr.z);
    c.holder.position.set(x, 0, z);
    if (c.holder.parent !== this.bench) this.bench.add(c.holder);
    c.holder.visible = true;
    return c;
  }
  hideBench() { for (const c of Object.values(this.inst)) if (c.holder) c.holder.visible = false; }

  // A step that walks through one component's own assembly list.
  assemblySteps(chapter, id, intro, { from = 0, working = false } = {}) {
    if (!available(id)) return [];
    const probe = build(id);
    const n = probe.assembly.length;
    const out = [];
    for (let i = from; i < n; i++) {
      const a = probe.assembly[i];
      out.push({
        chapter, scene: 'studio', title: a.title, text: a.text, sub: probe.name, intro: i === from ? intro : null,
        enter: (m) => {
          m.hideBench();
          const c = m.benchComp(id);
          if (!c) return;
          c.assembler = c.assembler || new Assembler(c);
          if (i === from && from > 0) c.assembler.setStep(from, false);
          c.assembler.setStep(i, true);
          c.setWorking(false);
          if (c.handles && c.handles.setCutaway) c.handles.setCutaway(0.85);   // see inside the shell while it is built
          m.focus = c;
          m.frame(c.holder, 1.2);
          m.partsInStep = a.parts.map((pid) => (c.parts.find((p) => p.id === pid) || {}).name).filter(Boolean);
        },
        update: (m, t, dt) => { const c = m.inst[id]; if (c && c.assembler) { c.assembler.update(dt); c.update(t, dt, { working: false, explode: 0 }); } },
      });
    }
    if (working) {
      out.push({
        chapter, scene: 'studio', title: `${probe.name}: power it on`, text: probe.working, sub: probe.name,
        enter: (m) => { m.hideBench(); const c = m.benchComp(id); if (!c) return; c.assembler && c.assembler.showAll(); c.setWorking(true); m.frame(c.holder, 1.6); m.partsInStep = []; },
        update: (m, t, dt) => { const c = m.inst[id]; if (c) c.update(t, dt, { working: true, explode: 0 }); },
        exit: (m) => { const c = m.inst[id]; if (c) c.setWorking(false); },
      });
    }
    return out;
  }

  // A step in the car: install components and cables (by id); everything from earlier car steps stays.
  carStep(chapter, title, text, { comps = [], cables = [], view = 'cabin', checks = [], need = [], extra = null } = {}) {
    return { chapter, scene: 'world', title, text, comps, cables, view, checks, need, extraFn: extra };
  }

  makeSteps() {
    const S = [];
    // ---------- Chapter 1: parts ----------
    S.push({
      chapter: 'Parts', scene: 'studio', title: 'Everything the plan buys and builds',
      text: `The parts on the bench, priced as last seen on 2026-10-21. The listed ranges total $${P.raw ? '' : ''}${(P.V.cost_low)}–${P.V.cost_high}. The mirror is a quote, not a price, and is ordered only after the ray trace with the chosen car's windshield.`,
      enter: (m) => m.layoutBom(), update: (m, t, dt) => { for (const c of m.bomList || []) c.update(t, dt, { working: false, explode: 0 }); },
    });
    // ---------- Chapter 2: picture generator ----------
    if (available('panelKit')) {
      S.push({
        chapter: 'Picture generator', scene: 'studio', title: 'The 5.5-inch kit as it arrives',
        text: `Wisecoco 5.5-inch 1920 × 1080 IPS panel with its HDMI board, ${price('Panels') || '$95'} for the set of panels. Stock edge-lit backlight: about 450 cd/m², far short of the ${Number(P.V.need_panel_day.replace(/,/g, '')).toLocaleString()} cd/m² the windshield path needs at noon. One kit stays stock for the bench; the other is taken apart.`,
        enter: (m) => { m.hideBench(); const c = m.benchComp('panelKit'); if (!c) return; c.assembler = c.assembler || new Assembler(c); c.assembler.showAll(); c.setWorking(true); m.frame(c.holder, 1.5); m.partsInStep = []; },
        update: (m, t, dt) => { const c = m.inst.panelKit; if (c) { c.assembler.apply(0); c.update(t, dt, { working: true, explode: 0 }); } },
        exit: (m) => { const c = m.inst.panelKit; if (c) c.setWorking(false); },
      });
      S.push({
        chapter: 'Picture generator', scene: 'studio', title: 'Tear down: keep the cell, set the stock backlight aside',
        text: 'Release the frame clips, lift the LCD cell with its polarisers, and remove the light guide, reflector sheet and LED strip. Measure first: stock luminance, then the stock backlight with the cell removed. Their ratio is the cell\'s transmittance, which replaces the 6% assumption (ASSUMED).',
        enter: (m) => { m.hideBench(); const c = m.benchComp('panelKit'); if (!c) return; c.assembler = c.assembler || new Assembler(c); c.assembler.showAll(); c.setWorking(false); m.teardown = 0; m.frame(c.holder, 1.9); m.partsInStep = c.parts.filter((p) => /back|light|guide|lgp|reflect|strip|stock|diffus|bef|sheet/i.test(p.id + p.name)).map((p) => p.name); },
        update: (m, t, dt) => {
          const c = m.inst.panelKit; if (!c) return;
          m.teardown = Math.min(1, (m.teardown || 0) + dt / 2.2);
          const k = easeInOut(m.teardown);
          for (const p of c.parts) {
            const isBL = /back|light|guide|lgp|reflect|strip|stock|diffus|bef|sheet/i.test(p.id + p.name) && !/cell|polar|glass|filter|lc|tft|front|rear pol/i.test(p.id);
            p.object.position.copy(p.base).addScaledVector(p.explode, k * 1.2);
            if (isBL) p.object.position.add(V(0, 0, 0.25 * k));
          }
        },
      });
    }
    S.push(...this.assemblySteps('Picture generator', 'backlight', 'Build the custom direct-lit backlight, bottom up, behind the 60 × 30 mm crop only.', { working: true }));
    if (available('pgu')) {
      const probe = build('pgu');
      const from = Math.max(0, probe.assembly.findIndex((a) => !a.parts.some((pid) => /backlight/i.test(pid))));
      S.push(...this.assemblySteps('Picture generator', 'pgu', 'Put the cell back on the new backlight and finish the PGU.', { from: from < 0 ? 0 : from, working: true }));
    }
    if (available('stage0Rig')) S.push({
      chapter: 'Picture generator', scene: 'studio', title: 'Stage 0: the bench rig (weeks 1–3)',
      text: 'Panel face-up under a 70/30 teleprompter beamsplitter at 45°. It makes a virtual image about 0.6 m away with no windshield and no relay, so the renderer, colours and latency instruments can be developed before any optics are bought.',
      enter: (m) => { m.hideBench(); const c = m.benchComp('stage0Rig'); if (!c) return; c.setWorking(true); m.frame(c.holder, 1.4); m.partsInStep = c.parts.map((p) => p.name); },
      update: (m, t, dt) => { const c = m.inst.stage0Rig; if (c) c.update(t, dt, { working: true, explode: 0 }); },
      exit: (m) => { const c = m.inst.stage0Rig; if (c) c.setWorking(false); },
    });
    // ---------- Chapter 3: optical housing ----------
    S.push(...this.assemblySteps('Optical housing', 'housing', 'Print the housing and build it from the ground up: body quarters with heat-set inserts, the sealed PGU bay, the mounts for the fold and the mirror, the lid and the shutter rails. Every printed piece fits a 250 mm printer (docs/arhud-cad).'));
    S.push(...this.assemblySteps('Optical housing', 'hudUnit', 'Assemble the optical train in its printed housing: panel, cold-mirror fold, concave mirror, shutter, dust cover.', { working: true }));
    S.push(...this.assemblySteps('Optical housing', 'controller', 'The HUD controller runs the backlight and the shutter on its own fail-safe rules.', { working: true }));
    if (available('stage1Rig')) S.push({
      chapter: 'Optical housing', scene: 'studio', title: 'Stage 1: Fresnel magnifier and combiner (weeks 4–8)',
      text: `Before the custom mirror arrives: the panel 280 mm below a 300 mm Fresnel lens (f = 300 mm) makes a virtual image ${(Math.abs(R.V1_mm) / 1000).toFixed(1)} m away, ×${R.M1.toFixed(0)}, 1.2 × 0.6 m, 16° × 8°, reflected by a free-standing 30% combiner above the dash. Night and overcast only; the demo fallback.`,
      enter: (m) => { m.hideBench(); const c = m.benchComp('stage1Rig'); if (!c) return; c.setWorking(true); m.frame(c.holder, 1.4); m.partsInStep = c.parts.map((p) => p.name); },
      update: (m, t, dt) => { const c = m.inst.stage1Rig; if (c) c.update(t, dt, { working: true, explode: 0 }); },
      exit: (m) => { const c = m.inst.stage1Rig; if (c) c.setWorking(false); },
    });
    // ---------- Chapter 4: in the car ----------
    S.push(this.carStep('Install in the car', 'Measure the car first', `The car sets the optics. Measure the windshield rake (the plan assumes ${R.RAKE}°), the laminate (assumed ${R.T_GLASS.toFixed(2)} mm) and the dash top, then run the ray trace that fixes the mirror's focal length and figure. The mirror is the critical path: car → ray trace → mirror order → lead time.`, { view: 'section', extra: 'rake', checks: ['Rake and look-down measured', 'Laminate thickness measured', 'Mirror quotes requested with the f-ratio stated (about f/1.1)'] }));
    S.push(this.carStep('Install in the car', 'Fused 12 V accessory feed', 'The only connection to the car: the accessory socket, through an inline fuse. No wire goes to the OBD port, CAN or any other vehicle bus.', { comps: ['fuseTap'], view: 'console', checks: ['Fuse in place', 'No connector to any vehicle bus'], need: ['DC-DC converter with ignition sense'] }));
    S.push(this.carStep('Install in the car', 'Ignition-sensed DC-DC converter', 'The Mini-Box DCDC-USB-200 sees the key-off, keeps the Jetson up for a configurable delay so it can shut down cleanly, and cuts off at 11.2 V to protect the car battery.', { comps: ['dcdc'], cables: ['p12'], view: 'console' }));
    S.push(this.carStep('Install in the car', 'Jetson in the passenger footwell', 'The reComputer J4012 is the only computer. It takes 9–19 V straight from the converter and runs at MAXN.', { comps: ['jetson'], cables: ['pJetson'], view: 'footwell' }));
    S.push(this.carStep('Install in the car', 'Road camera on the mirror stalk', `The ZED 2i clamps to the rear-view mirror stalk on the windshield centreline, about ${(GM.ROAD_CAM_BASELINE * 100).toFixed(0)} cm from the eye. Every registration error from range scales with this baseline, so the camera goes high and central, not on the dash. Its USB 3 cable runs along the headliner and down the A-pillar.`, { comps: ['zed2i'], cables: ['usbZed'], view: 'stalk', checks: ['Clamped, not bonded to the glass', 'Bracket rigid (mount drift moves every overlay)'], need: ['Stereolabs ZED 2i'] }));
    S.push(this.carStep('Install in the car', 'Driver camera on the column', 'The OAK-D Pro sits on the steering-column shroud aimed at the driver\'s face. It finds the face and the eye landmarks on its own processor and reports the eye midpoint, so head tracking costs the Jetson nothing. Its IR flood works at night.', { comps: ['oakdPro'], cables: ['usbOak'], view: 'column', need: ['Luxonis OAK-D Pro'] }));
    S.push(this.carStep('Install in the car', 'GNSS antenna and receiver', 'The antenna sits on the dash top near the glass; the ZED-F9R board beside the Jetson gives speed to 0.05 m/s and dead-reckons through outages. Its heading also feeds the sun-watch rule.', { comps: ['gnssAntenna', 'zedF9r'], cables: ['rfGnss', 'usbGnss'], view: 'passenger', need: ['u-blox ZED-F9R'] }));
    S.push(this.carStep('Install in the car', 'HUD unit onto the dash', 'The housing sits on a pad shaped to this dash, in front of the driver, with the dust cover under the glass. It comes off without tools. The LED driver mounts behind it.', { comps: ['hudUnit', 'ledDriver'], cables: ['pLed'], view: 'dash', checks: ['Removable without tools', 'Nothing bonded to the glass', 'Mirror top clear of the windshield'] }));
    S.push(this.carStep('Install in the car', 'HUD controller beside the housing', 'The RP2040 board carries the ambient-light sensor at the dust cover, the thermistor lead to the cell and the shutter servo. It talks to the Jetson over USB serial and keeps its own fail-safe rules if the Jetson goes quiet.', { comps: ['controller'], cables: ['serial'], view: 'dash' }));
    S.push(this.carStep('Install in the car', 'HDMI to the panel board', 'One HDMI 2.1 port on the J4012 drives the panel at 1920 × 1080, 60 Hz. Only the 946 × 473 px crop is drawn; the rest stays black.', { cables: ['hdmi'], view: 'dash' }));
    S.push(this.carStep('Install in the car', 'Audience view for the passengers', 'The Jetson streams the rendered frame, the driver camera and the live numbers as MJPEG over Ethernet to mini PC 2, which drives monitor 2 on the back of the passenger headrest. The J401 carrier has one HDMI, which is why the audience view is a stream.', { comps: ['ethSwitch', 'miniPC', 'monitor', 'pdCharger'], cables: ['eth', 'pdPC', 'video'], view: 'rear' }));
    S.push(this.carStep('Install in the car', 'Installation checklist, signed before each drive', 'Every part installed, every cable routed.', { view: 'cabin', checks: ['No connector to any vehicle bus', 'All mounts removable', 'Fuse in place', 'Nothing bonded to the glass', 'No polarised sunglasses (they block the s-polarised image)'] }));
    // ---------- Chapter 5: software and calibration ----------
    S.push({
      chapter: 'Software and calibration', scene: 'studio', title: 'Reflash the Jetson to JetPack 6.2',
      text: 'Seeed\'s JetPack 6.2 image (Ubuntu 22.04, Python 3.10, TensorRT 10). Check the board\'s current state first: it was last seen on JetPack 5.1.3. Run at MAXN, never MAXN SUPER on this carrier.',
      term: '# from the host, board in recovery mode (Seeed wiki: reComputer J4012 flash JetPack)\nsudo ./flash.sh ...          # Seeed image for J4012, JetPack 6.2\n# on the Jetson\ncat /etc/nv_tegra_release     # note the L4T release for the ZED SDK\nsudo nvpmodel -m 0            # MAXN',
      enter: (m) => { m.hideBench(); const j = m.benchComp('jetson', -0.25, 0); const s = m.benchComp('software', 0.35, 0); if (j) j.setWorking(true); if (s) s.setWorking(false); m.frame(m.bench, 1.2); m.partsInStep = []; },
      update: (m, t, dt) => { const j = m.inst.jetson; if (j) j.update(t, dt, { working: true, explode: 0 }); const s = m.inst.software; if (s) s.update(t, dt, { working: false, explode: 0 }); },
    });
    S.push({
      chapter: 'Software and calibration', scene: 'studio', title: 'ZED SDK and TensorRT engines',
      text: `Install the ZED SDK build that matches the reported L4T exactly. Export the networks to FP16 TensorRT engines: YOLO11s takes ${'7.9'} ms per 640-px frame on this board (Ultralytics); INT8 loses accuracy here. Then measure the GPU time of every job: the plan's budget is ${R.GPU_MIN}–${R.GPU_MAX} ms per frame against 33 ms at 30 Hz.`,
      term: './ZED_SDK_Tegra_L4T<release>_v5.x.run        # must match /etc/nv_tegra_release\nyolo export model=yolo11s.pt format=engine half=True\ntrtexec --onnx=ufldv2.onnx --fp16 --saveEngine=ufldv2.engine',
      enter: (m) => { m.hideBench(); const j = m.benchComp('jetson', -0.25, 0); const s = m.benchComp('software', 0.35, 0); if (j) j.setWorking(true); m.frame(m.bench, 1.2); m.partsInStep = P.GPU.map(([n, a, b]) => `${n}: ${a}–${b} ms`); },
      update: (m, t, dt) => { const j = m.inst.jetson; if (j) j.update(t, dt, { working: true, explode: 0 }); },
    });
    S.push({
      chapter: 'Software and calibration', scene: 'studio', title: 'Start the hud/ processes',
      text: 'One process per job, ZeroMQ PUB/SUB over ipc with msgpack messages. Every message carries the capture time of the sensor frame it came from, and empty messages are still published, so silence never looks like an empty road. The supervisor restarts a crashed process after 1 s and marks its topics stale.',
      term: 'python -m hud.supervisor     # planned package: roadd laned detectd egod headtrackd hudd controllerd logd audienced',
      enter: (m) => { m.hideBench(); const j = m.benchComp('jetson', -0.25, 0); const s = m.benchComp('software', 0.35, 0); if (s) s.setWorking(true); if (j) j.setWorking(true); m.frame(m.bench, 1.2); m.partsInStep = P.LAT.map(([n, a, b]) => `${n}: ${a}–${b} ms`); },
      update: (m, t, dt) => { for (const id of ['jetson', 'software']) { const c = m.inst[id]; if (c) c.update(t, dt, { working: true, explode: 0 }); } },
      exit: (m) => { const s = m.inst.software; if (s) s.setWorking(false); },
    });
    if (available('latencyProbe')) S.push({
      chapter: 'Software and calibration', scene: 'studio', title: 'Measure motion-to-photon latency',
      text: `An LED flashed in front of the road camera and a photodiode on the panel time the whole chain. The plan's budget is ${R.LAT_MIN}–${R.LAT_MAX} ms; the gate is 90 ms. Replay cannot measure this; only the photodiode can.`,
      enter: (m) => { m.hideBench(); const c = m.benchComp('latencyProbe'); if (c) { c.setWorking(true); m.frame(c.holder, 1.6); } m.partsInStep = []; },
      update: (m, t, dt) => { const c = m.inst.latencyProbe; if (c) c.update(t, dt, { working: true, explode: 0 }); },
      exit: (m) => { const c = m.inst.latencyProbe; if (c) c.setWorking(false); },
    });
    S.push(this.carStep('Software and calibration', 'Calibrate camera, car and eye with the 30 m target', 'Put the target board 30 m ahead on the car\'s centreline and a camera at the nominal eye point. The road camera\'s own detection of the board and the surveyed position separate perception error from optics error. The head tracker then adds a live offset to the nominal eye.', { view: 'target', extra: 'target', checks: ['Static registration at 30 m ≤ 0.5°', 'Calibration saved to the YAML file on the Jetson'] }));
    S.push(this.carStep('Software and calibration', 'Pre-distortion mesh from a photographed grid', 'Render a grid, photograph it from the eye point against a grid on the ground, and fit a 2-D mesh warp that cancels the keystone and curvature of the mirror and the windshield. hudd applies it as a final full-screen pass.', { view: 'cabinFwd', extra: 'grid' }));
    S.push(this.carStep('Software and calibration', 'Noon checks: luminance, contrast and ghost', `With the spot meter at the eye point: at least 1,500 cd/m² against the noon sky (ratio 1.15), 750 against sunlit road; the design gives about ${Math.round(R.L_PANEL_DESIGN * R.PATH_WS).toLocaleString()}. Photograph the ghost at three eye heights; it should be within twice the predicted ${R.GHOST_75.toFixed(1)}′.`, { view: 'cabin', extra: 'meter', checks: ['≥ 1,500 cd/m² at the eye against the sky', 'Night white ≤ 50 cd/m², unlit window ≤ 0.1 cd/m²', 'Ghost within 2× 1.4′'] }));
    S.push(this.carStep('Software and calibration', 'Ready to drive', 'Everything is installed and calibrated. Open the driver view to see the HUD on the road.', { view: 'cabinFwd', extra: 'go' }));
    return S;
  }

  // Lay every buyable part out on the bench with its price.
  layoutBom() {
    const m = this;
    m.hideBench();
    const ids = ['panelKit', 'backlight', 'retarder', 'coldMirror', 'concaveMirror', 'dustCover', 'shutter', 'zed2i', 'oakdPro', 'zedF9r', 'gnssAntenna', 'jetson', 'controller', 'ledDriver', 'dcdc', 'fuseTap', 'pdCharger', 'ethSwitch', 'miniPC', 'monitor', 'latencyProbe', 'rangefinder'];
    const comps = [];
    for (const id of ids) { const c = m.benchComp(id); if (c) { c.setWorking(false); comps.push(c); } }
    // shelf-pack on the 2.4 x 1.6 m bench
    const sizes = comps.map((c) => visibleBox(c.holder).getSize(new THREE.Vector3()));
    let x = -1.12, z = -0.7, rowD = 0;
    comps.forEach((c, i) => {
      const s = sizes[i];
      if (x + s.x > 1.12) { x = -1.12; z += rowD + 0.06; rowD = 0; }
      c.holder.position.x = x + s.x / 2; c.holder.position.z = z + s.z / 2;
      x += s.x + 0.06; rowD = Math.max(rowD, s.z);
    });
    m.bomList = comps;
    m.app.flyTo(V(0, 2.5, 2.3), V(0, 0, 0.1), 1.2);
    m.partsInStep = P.COST.map(([n, lo, hi, tag]) => `${n}: $${lo.toLocaleString()}${hi !== lo ? '–' + hi.toLocaleString() : ''} (${tag})`);
    // name labels: a dot on each part, the name on hover
    m.app.clearLabels();
    for (const c of comps) {
      const b = visibleBox(c.holder);
      m.app.label(c.name, m.bench, V((b.min.x + b.max.x) / 2, b.max.y + 0.01, (b.min.z + b.max.z) / 2), { pickId: c.reg.id });
    }
  }

  frame(obj, pad = 1.5) { this.app.frameObject(obj, { dir: V(0.9, 0.75, 1.25), pad }); }

  // ---- car steps ----
  carState(i) {
    // everything installed by car steps up to and including i
    const comps = new Set(), cables = new Set();
    for (let k = 0; k <= i; k++) { const s = this.steps[k]; if (s.scene !== 'world') continue; (s.comps || []).forEach((c) => comps.add(c)); (s.cables || []).forEach((c) => cables.add(c)); }
    return { comps, cables };
  }

  enterCarStep(step, i) {
    const g = this.g;
    const st = this.carState(i);
    const firstCar = this.steps.findIndex((s) => s.scene === 'world');
    const lastInstallIdx = this.steps.findIndex((s) => s.title.startsWith('Installation checklist'));
    const all = i >= lastInstallIdx;
    for (const [id, v] of Object.entries(g.installed)) {
      const on = all || st.comps.has(id);
      v.holder.visible = on;
      v.flyIn = (step.comps || []).includes(id) && !all ? 0 : 1;
      v.comp.setWorking(all && i > lastInstallIdx);
    }
    for (const cab of g.cables) {
      const on = all || st.cables.has(cab.id);
      cab.mesh.visible = on;
      cab.grow = (step.cables || []).includes(cab.id) && !all ? 0 : 1;
      cab.mesh.geometry.setDrawRange(0, on ? (cab.grow >= 1 ? Infinity : 0) : 0);
    }
    // Every installed part answers to the pointer with its name; the parts this step installs get a dot and show
    // their names for a few seconds. The car's world matrices must be current first: on the first jump from the
    // bench into the car no frame has placed the car yet, and a stale chain puts the anchors off by the car's position.
    g.placeEgo(this.app.t);
    g.carGroup.updateMatrixWorld(true);
    for (const [id, v] of Object.entries(g.installed)) {
      if (!v.holder.visible) continue;
      const reg = REGISTRY.find((r) => r.id === id);
      const b = visibleBox(v.holder);
      const c = b.isEmpty() ? v.holder.getWorldPosition(new THREE.Vector3()) : b.getCenter(new THREE.Vector3());
      const inStep = (step.comps || []).includes(id) && !all;
      this.app.label(reg ? reg.name : id, v.holder, v.holder.worldToLocal(c.clone()), { pickId: id, dot: inStep, reveal: inStep ? 5 : 0 });
    }
    this.extra.clear();
    if (this.extra.parent !== g.carGroup) g.carGroup.add(this.extra);
    if (step.extraFn) this.buildExtra(step.extraFn);
    this.partsInStep = (step.comps || []).map((id) => (REGISTRY.find((r) => r.id === id) || {}).name).concat((step.cables || []).map((cid) => (g.cables.find((c) => c.id === cid) || {}).label)).filter(Boolean);
    this.carView(step.view);
  }

  buildExtra(kind) {
    const g = this.g, x = this.extra;
    if (kind === 'rake') {
      // rake angle arc at the cowl and the glass line
      const base = V(GM.WS_BOTTOM_X, GM.COWL_Y, -0.35);
      const top = V(GM.WS_TOP_X, GM.ROOF_Y, -0.35);
      x.add(polyline([base, top], 0x5ec8ff, { opacity: 1 }));
      x.add(polyline([base, base.clone().add(V(-0.6, 0, 0))], 0x5ec8ff, { opacity: 0.7, dashed: true, dash: 0.03, gap: 0.02 }));
      const arc = []; for (let a = 0; a <= R.RAKE; a += 1) arc.push(base.clone().add(V(-0.3 * Math.cos(a * DEG), 0.3 * Math.sin(a * DEG), 0)));
      x.add(polyline(arc, 0xffc04d, { opacity: 1 }));
      this.app.label(`rake ${R.RAKE}° (ASSUMED until measured)`, g.carGroup, base.clone().add(V(-0.38, 0.1, 0)), { cls: 'cap', reveal: 6 });
      this.app.label(`laminate ${R.T_GLASS.toFixed(2)} mm (ASSUMED)`, g.carGroup, GM.G.clone().add(V(0.05, 0.05, -0.35)), { cls: 'cap', reveal: 6 });
      this.app.label('eye point', g.carGroup, GM.EYE.clone(), { cls: 'cap', reveal: 6 });
      x.add(polyline([GM.EYE, GM.G], 0xffb347, { opacity: 0.9 }));
    }
    if (kind === 'target' && available('targetBoard')) {
      if (!this.target) { this.target = build('targetBoard'); }
      this.target.group.position.set(30, 0, 0.37); this.target.group.rotation.y = Math.PI;
      x.add(this.target.group);
      x.add(polyline([GM.EYE, V(30, 1.0, 0.37)], 0xffb347, { opacity: 0.9, dashed: true, dash: 0.3, gap: 0.2 }));
      x.add(polyline([GM.ROAD_CAM, V(30, 1.0, 0.37)], 0x3d8bff, { opacity: 0.9, dashed: true, dash: 0.3, gap: 0.2 }));
      this.app.label('30 m target board', g.carGroup, V(30, 2.2, 0.37), { cls: 'cap', reveal: 6 });
      this.app.label('eye-point camera', g.carGroup, GM.EYE.clone().add(V(0, 0.06, 0)), { cls: 'cap', reveal: 6 });
    }
    if (kind === 'grid') {
      // keystoned image of a rendered grid vs the corrected rectangle, on the virtual image plane
      const c = GM.VIMG_C;
      const corner = (a, b, ks = 0) => c.clone().addScaledVector(GM.VIMG_RIGHT, a * GM.IMG_W / 2 * (1 + ks * b)).addScaledVector(GM.VIMG_UP, b * GM.IMG_H / 2);
      for (let i = -4; i <= 4; i++) {
        x.add(polyline([corner(i / 4, -1, -0.045), corner(i / 4, 1, -0.045)], 0xffc04d, { opacity: 0.8 }));
        x.add(polyline([corner(i / 4, -1), corner(i / 4, 1)], 0x5ec8ff, { opacity: 0.9 }));
      }
      for (let j = -2; j <= 2; j++) {
        x.add(polyline([corner(-1, j / 2, -0.045), corner(1, j / 2, -0.045)], 0xffc04d, { opacity: 0.8 }));
        x.add(polyline([corner(-1, j / 2), corner(1, j / 2)], 0x5ec8ff, { opacity: 0.9 }));
      }
      this.app.label('amber: grid as the mirror and glass bend it (keystone, about 9% from the trace)', g.carGroup, corner(0, 1.35), { cls: 'cap', reveal: 6 });
      this.app.label('blue: after the pre-distortion mesh', g.carGroup, corner(0, -1.4), { cls: 'cap', reveal: 6 });
    }
    if (kind === 'meter' && available('lumMeter')) {
      if (!this.meter) this.meter = build('lumMeter');
      this.meter.group.position.copy(GM.EYE).add(V(-0.25, -1.22 + 0.25, 0));
      x.add(this.meter.group); this.meter.setWorking(true);
      if (g.car.driver) g.car.driver.visible = false;
      this.hidDriver = true;
    }
    if (kind === 'go') {
      // nothing in the scene; the panel shows the button
    }
  }

  carView(name) {
    const g = this.g, cg = g.carGroup;
    const W = (x, y, z) => cg.localToWorld(V(x, y, z));
    const views = {
      cabin: [W(0.2, 1.55, -1.6), W(0.75, 0.95, 0.1)],
      cabinFwd: [W(-0.35, 1.32, -0.05), W(4, 0.7, 0.2)],
      section: [W(0.8, 1.05, -1.6), W(0.8, 1.0, 0.0)],
      console: [W(0.0, 1.0, -0.7), W(0.45, 0.45, 0.37)],
      footwell: [W(0.05, 0.9, 0.15), W(0.6, 0.25, 0.85)],
      stalk: [W(-0.05, 1.22, 0.95), W(0.42, 1.31, 0.37)],
      column: [W(0.05, 1.1, -0.6), W(0.5, 0.88, 0.0)],
      passenger: [W(0.0, 1.35, 1.0), W(0.95, 0.75, 0.85)],
      dash: [W(-0.3, 1.42, -0.62), W(0.8, 0.95, 0.05)],
      rear: [W(-1.6, 1.3, 0.2), W(-0.4, 0.8, 0.75)],
      target: [W(-3.5, 3.0, -4.0), W(14, 0.8, 0.37)],
    };
    const [p, t] = views[name] || views.cabin;
    this.app.flyTo(p, t, 1.4);
  }

  // ---- mode plumbing ----
  async enter() {
    const app = this.app;
    app.controls.enabled = true;
    this.go(this.idx, true);
  }
  exit() {
    const step = this.steps[this.idx];
    if (step && step.exit) step.exit(this);
    this.leaveWorld();
    this.bench.removeFromParent();
    this.hideBench();
    if (this.pending) clearTimeout(this.pending);
    hidePanel('left'); hidePanel('right'); hidePanel('bottom');
  }
  leaveWorld() {
    const g = this.g;
    this.extra.removeFromParent();
    for (const v of Object.values(g.installed)) { v.holder.visible = true; v.flyIn = 1; v.holder.position.copy(v.home); }
    for (const cab of g.cables) { cab.mesh.visible = true; cab.mesh.geometry.setDrawRange(0, Infinity); }
    if (this.hidDriver && g.car.driver) g.car.driver.visible = true;
    this.hidDriver = false;
    g.workLights.visible = false;
    g.car.setCutaway && g.car.setCutaway('none');
  }

  go(i, force = false) {
    const prev = this.steps[this.idx];
    if (prev && prev.exit && (i !== this.idx || force)) prev.exit(this);
    this.idx = clamp(i, 0, this.steps.length - 1);
    const step = this.steps[this.idx];
    const app = this.app, g = this.g;
    app.clearLabels();
    app.pickables = step.scene === 'studio' ? [this.bench] : [g.installGroup, g.cableGroup];
    app.onPick = null;
    this.partsInStep = [];
    if (step.scene === 'studio') {
      this.leaveWorld();
      if (this.bench.parent !== app.studio) app.studio.add(this.bench);
      app.setScene(app.studio, app.camera);
      app.renderer.toneMappingExposure = 1;
      step.enter && step.enter(this);
    } else {
      this.bench.removeFromParent();
      app.setScene(g.scene, app.camera);
      app.renderer.toneMappingExposure = (g.world.env && g.world.env.exposure) || 1;
      g.vimg.visible = false;
      g.workLights.visible = true;
      g.car.setCutaway && g.car.setCutaway(step.view === 'target' || step.view === 'cabinFwd' ? 'none' : 'side');
      if (this.hidDriver && g.car.driver) { g.car.driver.visible = true; this.hidDriver = false; }
      this.enterCarStep(step, this.idx);
    }
    this.render();
  }

  render() {
    const step = this.steps[this.idx];
    const chapters = [...new Set(this.steps.map((s) => s.chapter))];
    // One folding section per chapter; the chapter in progress is open.
    let current = null;
    const list = chapters.map((ch) => section('build-' + ch.toLowerCase().replace(/[^a-z0-9]+/g, '-'), ch, ch === step.chapter, h('div', { class: 'list' }, this.steps.map((s, k) => s.chapter === ch ? (() => {
      const b = h('button', { class: 'item', type: 'button', 'aria-current': String(k === this.idx) }, h('span', {}, s.title), h('small', {}, String(k + 1)));
      b.addEventListener('click', () => { this.playing = false; this.go(k); });
      if (k === this.idx) current = b;
      return b;
    })() : null).filter(Boolean))));
    setPanel('left', h('h2', {}, 'Build it'), h('p', { class: 'hint' }, `${this.steps.length} steps from the parts on the bench to the first drive. Play runs them in order; point at a part for its name.`), ...list);
    if (current) current.scrollIntoView({ block: 'nearest' });
    const need = (step.need || []).map((n) => price(n) ? `${n}: ${price(n)}` : n);
    setPanel('right',
      h('div', { class: 'muted', style: { fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em' } }, `${step.chapter} · step ${this.idx + 1} of ${this.steps.length}`),
      h('div', { class: 'step-title' }, step.title),
      step.intro ? h('p', { class: 'muted' }, step.intro) : null,
      step.sub ? h('p', { class: 'muted', style: { fontSize: '12px' } }, step.sub) : null,
      h('p', {}, tagFor(step.text || '')),
      step.term ? h('div', { class: 'term' }, step.term) : null,
      this.partsInStep && this.partsInStep.length ? [h('h3', {}, step.scene === 'world' ? 'Installed in this step' : 'In this step'), h('div', { class: 'list' }, this.partsInStep.map((p) => h('div', { style: { fontSize: '12px', padding: '2px 0' } }, tagFor(p))))] : null,
      need.length ? [h('h3', {}, 'Cost'), ...need.map((n) => h('div', { style: { fontSize: '12px' } }, n))] : null,
      step.checks && step.checks.length ? [h('h3', {}, 'Check'), ...step.checks.map((c) => h('label', { class: 'toggle' }, h('span', {}, c), h('input', { type: 'checkbox' })))] : null,
      step.extraFn === 'go' ? h('div', { style: { marginTop: '10px' } }, btn('Open the driver view', () => this.app.setMode('drive'), { primary: true })) : null,
    );
    const pct = ((this.idx + 1) / this.steps.length) * 100;
    setPanel('bottom',
      h('div', { class: 'row', style: { justifyContent: 'space-between' } },
        h('div', { style: { minWidth: 0, flex: '1 1 240px' } }, h('div', { style: { fontWeight: 700 } }, step.title), h('div', { class: 'muted', style: { fontSize: '12px' } }, step.chapter)),
        h('div', { class: 'row' },
          btn('Back', () => { this.playing = false; this.go(this.idx - 1); }),
          btn(this.playing ? 'Pause' : 'Play', () => { this.playing = !this.playing; this.playT = 0; this.render(); }, { primary: true }),
          btn('Next', () => { this.playing = false; this.go(this.idx + 1); }))),
      h('div', { class: 'progress' }, h('i', { style: { width: pct + '%' } })));
  }

  update(t, dt) {
    const step = this.steps[this.idx];
    const g = this.g;
    if (step.scene === 'world') {
      g.updateDynamics(0, 0, 0, 0);                     // parked: the body sits level
      g.placeEgo(t);
      const sunDirCar = g.world.sunDir ? g.toCarDir(g.world.sunDir) : null;
      g.hud.update(t, dt, { sunDirCar, eyeOffset: new THREE.Vector3(), ambientLux: g.ambientLux() });
      // fly-in of this step's parts, growth of this step's cables
      for (const v of Object.values(g.installed)) {
        if (!v.holder.visible) continue;
        if (v.flyIn < 1) {
          v.flyIn = Math.min(1, v.flyIn + dt / 1.4);
          const k = easeInOut(v.flyIn);
          v.holder.position.copy(v.home).add(V(0, 0.45 * (1 - k), 0));
        }
        v.comp.update(t, dt, { working: true, explode: 0, live: g.hud });
      }
      for (const cab of g.cables) {
        if (!cab.mesh.visible || cab.grow >= 1) continue;
        cab.grow = Math.min(1, cab.grow + dt / 2.0);
        cab.mesh.geometry.setDrawRange(0, Math.floor(cab.count * easeInOut(cab.grow) / 6) * 6);
      }
      const unit = g.installed.hudUnit;
      if (unit && unit.comp.handles) { unit.comp.handles.setBacklight && unit.comp.handles.setBacklight(this.idx >= this.steps.length - 4 ? g.hud.lum.duty : 0); unit.comp.handles.setShutter && unit.comp.handles.setShutter(this.idx >= this.steps.length - 4 ? 1 : 0); }
      if (this.meter && this.meter.group.parent) this.meter.update(t, dt, { working: true, explode: 0 });
    } else if (step.update) step.update(this, t, dt);
    if (this.playing) {
      this.playT += dt;
      const hold = step.scene === 'world' ? 4.5 : 3.2;
      if (this.playT > hold) {
        this.playT = 0;
        if (this.idx < this.steps.length - 1) this.go(this.idx + 1); else { this.playing = false; this.render(); }
      }
    }
  }
}
