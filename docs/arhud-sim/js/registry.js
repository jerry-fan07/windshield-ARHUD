// Every component in the simulation: where its builder lives, its category, and the name shown before it is built.
// Modules are loaded with dynamic import so one failing module does not take the rest down.
import { validateComponent } from './components/contract.js';

export const CATEGORIES = [
  ['pgu', 'Picture generator'],
  ['optics', 'Optics'],
  ['housing', 'Housing'],
  ['sensor', 'Sensors'],
  ['compute', 'Computer'],
  ['software', 'Software'],
  ['controller', 'HUD controller'],
  ['power', 'Power'],
  ['display', 'Displays'],
  ['network', 'Network'],
  ['stage', 'Stage 0 and 1 rigs'],
  ['instrument', 'Test instruments'],
  ['vehicle', 'Vehicle'],
];

export const REGISTRY = [
  { id: 'panelKit', mod: 'pgu', fn: 'buildPanelKit', cat: 'pgu', name: '5.5-inch 1080p HDMI panel kit (stock)' },
  { id: 'lcdCell', mod: 'pgu', fn: 'buildLcdCell', cat: 'pgu', name: 'LCD cell and the 60 × 30 mm crop' },
  { id: 'backlight', mod: 'pgu', fn: 'buildBacklight', cat: 'pgu', name: 'Custom direct-lit backlight' },
  { id: 'retarder', mod: 'pgu', fn: 'buildRetarder', cat: 'pgu', name: 'Half-wave retarder film' },
  { id: 'pgu', mod: 'pgu', fn: 'buildPgu', cat: 'pgu', name: 'Picture generation unit (assembled)' },
  { id: 'coldMirror', mod: 'optics', fn: 'buildColdMirror', cat: 'optics', name: 'Cold-mirror fold and IR absorber' },
  { id: 'concaveMirror', mod: 'optics', fn: 'buildConcaveMirror', cat: 'optics', name: 'Concave relay mirror, 300 × 200 mm' },
  { id: 'windshield', mod: 'glass', fn: 'buildWindshieldSection', cat: 'optics', name: 'Windshield: reflection and ghost' },
  { id: 'dustCover', mod: 'optics', fn: 'buildDustCover', cat: 'optics', name: 'Dust cover with s-pass polariser' },
  { id: 'shutter', mod: 'optics', fn: 'buildShutter', cat: 'optics', name: 'Sun shutter and servo' },
  { id: 'housing', mod: 'optics', fn: 'buildHousing', cat: 'housing', name: '3-D printed housing' },
  { id: 'hudUnit', mod: 'optics', fn: 'buildHudUnit', cat: 'housing', name: 'HUD unit, installed optical train' },
  { id: 'zed2i', mod: 'sensors', fn: 'buildZed2i', cat: 'sensor', name: 'Stereolabs ZED 2i road camera' },
  { id: 'oakdPro', mod: 'sensors', fn: 'buildOakdPro', cat: 'sensor', name: 'Luxonis OAK-D Pro driver camera' },
  { id: 'zedF9r', mod: 'sensors', fn: 'buildZedF9r', cat: 'sensor', name: 'u-blox ZED-F9R GNSS board' },
  { id: 'gnssAntenna', mod: 'sensors', fn: 'buildGnssAntenna', cat: 'sensor', name: 'GNSS antenna' },
  { id: 'jetson', mod: 'electronics', fn: 'buildJetson', cat: 'compute', name: 'Seeed reComputer J4012 (Orin NX 16 GB)' },
  { id: 'software', mod: 'electronics', fn: 'buildSoftware', cat: 'software', name: 'hud/ processes and topics' },
  { id: 'controller', mod: 'electronics', fn: 'buildController', cat: 'controller', name: 'HUD controller (RP2040)' },
  { id: 'ledDriver', mod: 'electronics', fn: 'buildLedDriver', cat: 'controller', name: 'Constant-current LED driver' },
  { id: 'dcdc', mod: 'electronics', fn: 'buildDcdc', cat: 'power', name: 'Mini-Box DCDC-USB-200' },
  { id: 'fuseTap', mod: 'electronics', fn: 'buildFuseTap', cat: 'power', name: '12 V plug and inline fuse' },
  { id: 'pdCharger', mod: 'electronics', fn: 'buildPdCharger', cat: 'power', name: 'USB-C PD car charger' },
  { id: 'ethSwitch', mod: 'electronics', fn: 'buildEthSwitch', cat: 'network', name: 'Gigabit Ethernet switch' },
  { id: 'miniPC', mod: 'electronics', fn: 'buildMiniPC', cat: 'display', name: 'ACEMAGIC mini PC (audience view)' },
  { id: 'monitor', mod: 'electronics', fn: 'buildMonitor', cat: 'display', name: 'YODOIT 16-inch monitor' },
  { id: 'stage0Rig', mod: 'optics', fn: 'buildStage0Rig', cat: 'stage', name: 'Stage 0 bench rig' },
  { id: 'stage1Rig', mod: 'optics', fn: 'buildStage1Rig', cat: 'stage', name: 'Stage 1 Fresnel and combiner' },
  { id: 'latencyProbe', mod: 'instruments', fn: 'buildLatencyProbe', cat: 'instrument', name: 'Latency probe (photodiode + LED)' },
  { id: 'lumMeter', mod: 'instruments', fn: 'buildLumMeter', cat: 'instrument', name: 'Spot luminance meter' },
  { id: 'targetBoard', mod: 'instruments', fn: 'buildTargetBoard', cat: 'instrument', name: '30 m target board' },
  { id: 'rangefinder', mod: 'instruments', fn: 'buildRangefinder', cat: 'instrument', name: 'Laser rangefinder' },
];

const MODULE_PATHS = {
  pgu: './components/pgu.js', optics: './components/optics.js', sensors: './components/sensors.js',
  electronics: './components/electronics.js', instruments: './components/instruments.js', glass: './components/glass.js',
};
const modules = {};
export const loadErrors = [];

export async function loadModules() {
  await Promise.all(Object.entries(MODULE_PATHS).map(async ([k, p]) => {
    try { modules[k] = await import(p); } catch (e) { loadErrors.push(`${k}: ${e.message}`); console.error('module', k, e); }
  }));
  return modules;
}

export function available(id) {
  const r = REGISTRY.find((x) => x.id === id);
  return !!(r && modules[r.mod] && typeof modules[r.mod][r.fn] === 'function');
}

export function build(id, opts = {}) {
  const r = REGISTRY.find((x) => x.id === id);
  if (!r) throw new Error('unknown component ' + id);
  const m = modules[r.mod];
  if (!m || typeof m[r.fn] !== 'function') return null;
  const c = m[r.fn](opts);
  const errs = validateComponent(c);
  if (errs.length) console.warn('component', id, errs);
  // remember each part's built position for exploding
  for (const p of c.parts) p.base = p.object.position.clone();
  c.reg = r;
  addHandleControls(c);
  return c;
}

export function setExplode(c, x) {
  for (const p of c.parts) p.object.position.copy(p.base).addScaledVector(p.explode, x);
  c._explode = x;
}

// Surface each component's live handles as controls in the Components panel.
function addHandleControls(c) {
  const h = c.handles || {};
  const ctl = c.controls ? [...c.controls] : [];
  const pct = (x) => `${Math.round(x * 100)}%`;
  if (h.setMode) ctl.push({ id: 'mode', type: 'chips', label: 'Mirror figure', value: h.getMode ? h.getMode() : 'toroid', options: [['toroid', 'Toroid (corrected)'], ['sphere', 'Sphere (plan as written)'], ['freeform', 'Freeform + tilted panel'], ['freeformCurved', 'Freeform, curved glass']], onChange: (v) => h.setMode(v) });
  if (h.setMirrorMode) ctl.push({ id: 'mmode', type: 'chips', label: 'Mirror figure', value: 'toroid', options: [['toroid', 'Toroid (corrected)'], ['sphere', 'Sphere (plan as written)'], ['freeform', 'Freeform + tilted panel'], ['freeformCurved', 'Freeform, curved glass']], onChange: (v) => h.setMirrorMode(v) });
  if (h.setOpen) ctl.push({ id: 'open', type: 'slider', label: 'Shutter command', min: 0, max: 1, step: 0.01, value: 1, fmt: pct, onChange: (v) => h.setOpen(v) });
  if (h.setShutter) ctl.push({ id: 'shut', type: 'slider', label: 'Shutter', min: 0, max: 1, step: 0.01, value: 1, fmt: pct, onChange: (v) => h.setShutter(v) });
  if (h.setLevel) ctl.push({ id: 'level', type: 'slider', label: 'LED drive', min: 0, max: 1, step: 0.01, value: 1, fmt: pct, onChange: (v) => h.setLevel(v) });
  if (h.setBacklight) ctl.push({ id: 'bl', type: 'slider', label: 'Backlight', min: 0, max: 1, step: 0.01, value: 1, fmt: pct, onChange: (v) => h.setBacklight(v) });
  if (h.setCutaway) ctl.push({ id: 'cut', type: 'slider', label: 'See through the housing', min: 0, max: 1, step: 0.01, value: 0, fmt: pct, onChange: (v) => h.setCutaway(v) });
  if (ctl.length) c.controls = ctl;
}
