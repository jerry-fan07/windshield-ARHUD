// Boot: build the app, load the component modules, the world and the car, then open the mode named in the URL hash.
import { App } from './app.js';
import { loadModules, loadErrors } from './registry.js';
import { PartsMode } from './modes/parts.js';
import { toast } from './ui.js';

window.addEventListener('error', (e) => toast('Error: ' + (e.message || e), 8000));
window.addEventListener('unhandledrejection', (e) => toast('Error: ' + (e.reason && e.reason.message || e.reason), 8000));
const app = new App();
window.__app = app;

async function boot() {
  const loading = document.getElementById('loading');
  await loadModules();
  app.addMode('parts', new PartsMode(app));
  // The world, the car and the installed HUD are shared by the three in-car modes.
  try {
    const { Garage } = await import('./install.js');
    app.garage = new Garage(app);
    await app.garage.init();
    const { DriveMode } = await import('./modes/drive.js');
    const { VehicleMode } = await import('./modes/vehicle.js');
    const { BuildMode } = await import('./modes/build.js');
    app.addMode('drive', new DriveMode(app));
    app.addMode('vehicle', new VehicleMode(app));
    app.addMode('build', new BuildMode(app));
  } catch (e) {
    console.error(e);
    loadErrors.push('world: ' + e.message);
  }
  document.querySelectorAll('#modes button').forEach((b) => {
    const ok = !!app.modes[b.dataset.mode];
    b.disabled = !ok;
    b.addEventListener('click', () => app.setMode(b.dataset.mode));
  });
  const [hashMode, ...flags] = (location.hash || '').replace('#', '').split('&');
  try { const GMm = await import('./geom.js'); window.__GM_EYE = GMm.EYE; } catch (e) { /* no world */ }
  const flag = (k) => { const f = flags.find((x) => x.startsWith(k + '=')); return f ? f.slice(k.length + 1) : null; };
  // Chrome: the label mode (hover / all / off) and the one-click "hide panels" (also the H key).
  const uiBtn = document.getElementById('uiBtn');
  const setUi = (hidden) => { document.body.classList.toggle('ui-hidden', hidden); uiBtn.setAttribute('aria-pressed', String(hidden)); uiBtn.textContent = hidden ? 'Show panels' : 'Hide panels'; };
  uiBtn.addEventListener('click', () => setUi(!document.body.classList.contains('ui-hidden')));
  // Full screen: the Fullscreen API on the whole document. Where the browser or the host page refuses it (an iframe
  // without allowfullscreen, a window that denies the request), the page-level version hides the top bar and lets the
  // stage fill the viewport instead. Escape or F leaves either.
  const fsBtn = document.getElementById('fsBtn'), fsExit = document.getElementById('fsExit'), root = document.documentElement;
  const fsApi = () => !!(document.fullscreenEnabled || document.webkitFullscreenEnabled);
  const fsOn = () => !!(document.fullscreenElement || document.webkitFullscreenElement);
  const immersive = () => document.body.classList.contains('immersive');
  const fsSync = () => { const on = fsOn() || immersive(); fsBtn.setAttribute('aria-pressed', String(on)); fsBtn.textContent = on ? 'Exit full screen' : 'Full screen'; };
  const setImmersive = (on) => { document.body.classList.toggle('immersive', on); app.resize(); fsSync(); };
  const fsToggle = async () => {
    if (fsOn()) { try { await (document.exitFullscreen ? document.exitFullscreen() : document.webkitExitFullscreen()); } catch (e) { /* already left */ } return; }
    if (immersive()) { setImmersive(false); return; }
    if (fsApi()) {
      try { await (root.requestFullscreen ? root.requestFullscreen({ navigationUI: 'hide' }) : root.webkitRequestFullscreen()); return; }
      catch (e) { /* refused: fall back to the page-level version */ }
    }
    setImmersive(true);
    toast('Full screen within the page: the browser did not allow the real thing here. Escape or F leaves it.', 3500);
  };
  fsBtn.addEventListener('click', fsToggle);
  fsExit.addEventListener('click', fsToggle);
  document.addEventListener('fullscreenchange', fsSync);
  document.addEventListener('webkitfullscreenchange', fsSync);
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && immersive()) { setImmersive(false); return; }
    const k = e.key.toLowerCase();
    if ((k !== 'h' && k !== 'f') || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.target && /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
    if (k === 'h') setUi(!document.body.classList.contains('ui-hidden'));
    else fsToggle();
  });
  document.querySelectorAll('#labelMode button').forEach((b) => b.addEventListener('click', () => app.setLabelMode(b.dataset.v)));
  let labelMode = 'hover';
  try { labelMode = localStorage.getItem('arhud.labels') || 'hover'; } catch (e) { /* private window */ }
  if (flag('labels')) labelMode = flag('labels');
  app.setLabelMode(['hover', 'all', 'off'].includes(labelMode) ? labelMode : 'hover');
  if (flags.includes('nopanels')) setUi(true);
  let want = hashMode;
  window.__debug = flags.includes('debug');
  if (want.startsWith('part-')) { app.modes.parts.pendingSelect = want.slice(5); want = 'parts'; }
  if (want.startsWith('build-') && app.modes.build) { app.modes.build.idx = Math.max(0, parseInt(want.slice(6), 10) - 1) || 0; want = 'build'; }
  if (want.startsWith('vehicle-') && app.modes.vehicle) { app.modes.vehicle.startView = want.slice(8); want = 'vehicle'; }
  if (!app.modes[want]) want = app.modes.drive ? 'drive' : 'parts';
  await app.setMode(want);
  // Development hook: #mode&warm=SECONDS runs the simulation that long before the first frame (for screenshots).
  if (flag('env') && app.mode && app.mode.applyEnv) app.mode.applyEnv(flag('env'));
  if (flag('strip') && app.mode && app.mode.setStrip) app.mode.setStrip(flag('strip'), { fly: false });
  if (flag('ribbon') && app.modes.drive) app.modes.drive.setRibbon(flag('ribbon'));
  // #drive&eye=DY,DZ puts the driver's head DY up and DZ right of the nominal eye (metres) before the warm-up, so the
  // tracker settles on it; &surf=1 makes hudd project onto the measured image surface (the Optics toggle).
  if (flag('eye') && app.modes.drive) { const [dy, dz] = flag('eye').split(',').map(parseFloat); app.modes.drive.head.user.y = dy || 0; app.modes.drive.head.user.z = dz || 0; }
  // #drive&mirror=toroid|sphere|freeform|freeformCurved picks the mirror figure before the warm-up (the tilted panel and
  // the image surface follow), so headless captures can be made for any figure.
  if (flag('mirror') && app.garage) { const GMm = await import('./geom.js'); const v = flag('mirror'); GMm.MIRROR.mode = v; GMm.setGlassForMode(v); app.garage.applyPanelPose && app.garage.applyPanelPose(v); app.garage.hud.setWindow(app.garage.hud.settings.window); app.garage.layoutVirtualImage(1); }
  // #drive&glass=RH,RV puts a curved windshield (radii in metres) into the trace for any figure (the car's glass is still drawn flat).
  if (flag('glass') && app.garage) { const GMm = await import('./geom.js'); const [rh, rv] = flag('glass').split(',').map(parseFloat); GMm.GLASS.Rh = rh || 0; GMm.GLASS.Rv = rv || 0; app.garage.hud.setWindow(app.garage.hud.settings.window); app.garage.layoutVirtualImage(1); }
  // #drive&blur=1 draws the eye's focus blur; &focus=image|road|infinity and &pupil=MM set where the eye focuses and
  // the pupil (0 = from the scene). &glass= and &mirror= above choose what it looks through.
  if (app.modes.drive && app.garage && app.garage.focus) {
    const dm = app.modes.drive;
    if (flag('focus') || flag('pupil')) dm.setFocus({ target: flag('focus') || undefined, pupilMm: flag('pupil') ? parseFloat(flag('pupil')) : undefined });
    if (flag('blur')) dm.setFocusBlur(flag('blur') !== '0');
    if (flag('mirror')) { dm.mirrorChips && dm.mirrorChips.set(flag('mirror')); }
    if (flag('glass') || flag('mirror')) { dm.glassChips && dm.glassChips.set(dm.glassKey()); }
  }
  if (flag('surf') && app.garage && app.garage.hud) { const hs = app.garage.hud.settings; hs.projection = ({ 0: 'plane', 1: 'surface', 2: 'trace', 3: 'lut' })[flag('surf')] || 'plane'; hs.surfaceAware = hs.projection === 'surface'; }
  const warm = parseFloat(flag('warm'));
  if (warm > 0 && app.mode && app.mode.update) { app.warming = true; for (let t = 0; t < warm; t += 1 / 30) app.step(1 / 30); app.warming = false; }
  if (flag('fov') && app.mode && app.mode.look) app.mode.look.fov = parseFloat(flag('fov'));
  // #mode&bare=1: no top bar and no panels, so the stage is the whole window (headless screenshots at a known size).
  if (flag('bare')) { setImmersive(true); setUi(true); }
  // #drive&pattern=white paints the HUD canvas white after every frame: the virtual image as a plain lit rectangle, for
  // the end-to-end check of the Driver view's drawing against the Cycles renders (docs/arhud-blender/README.md).
  // #drive&pattern=marks: after each frame, black out the HUD and draw a cross where hudd puts four fixed road points
  // (16 and 24 m ahead, 1 m left and right, on the ground) for the eye it draws for. Blender renders the same
  // points as discs on the road from the same eye; cross minus disc is the registration error through the real optics.
  if (flag('pattern') === 'marks' && app.garage && app.garage.hud) {
    const hud = app.garage.hud, orig = hud.draw.bind(hud);
    const pts = [[16, 0, 1.0], [16, 0, -1.0], [24, 0, 1.0], [24, 0, -1.0]];     // inside the traced window from the nominal eye
    hud.draw = (a, b) => {
      orig(a, b);
      const ctx = hud.ctx, eye = app.garage.hud.eye.used.clone().add(app.garage.hud.constructor.EYE || window.__GM_EYE);
      ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over'; ctx.fillStyle = '#000'; ctx.fillRect(0, 0, hud.canvas.width, hud.canvas.height);
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 5;
      for (const q of pts) { const px = hud.project(new (eye.constructor)(q[0], q[1], q[2]), eye); if (!px) continue; ctx.beginPath(); ctx.moveTo(px[0] - 14, px[1]); ctx.lineTo(px[0] + 14, px[1]); ctx.moveTo(px[0], px[1] - 14); ctx.lineTo(px[0], px[1] + 14); ctx.stroke(); }
    };
    if (app.mode && app.mode.update) { app.warming = true; app.step(1 / 30); app.warming = false; }   // one patched frame before a dump
  }
  if (flag('pattern') === 'white' && app.garage && app.garage.hud) {
    const hud = app.garage.hud, orig = hud.draw.bind(hud);
    hud.draw = (a, b) => { orig(a, b); hud.ctx.globalAlpha = 1; hud.ctx.globalCompositeOperation = 'source-over'; hud.ctx.fillStyle = '#fff'; hud.ctx.fillRect(0, 0, hud.canvas.width, hud.canvas.height); };
  }
  // #drive&warm=N&dump=pgu writes the PGU frame as a PNG data URL into <pre id="pguDump"> (the Blender beauty render
  // in docs/arhud-blender reads it from a headless --dump-dom).
  if (flag('dump') === 'pgu' && app.garage && app.garage.hud) {
    const pre = document.createElement('pre'); pre.id = 'pguDump'; pre.hidden = true;
    pre.textContent = app.garage.hud.canvas.toDataURL('image/png'); document.body.append(pre);
  }
  // #drive&...&dump=pgupanel writes the frame pre-distorted to the panel: what hudd must send so that, through the
  // keystoning optics, the nominal eye sees the canvas as drawn. The mapping (panel point -> field direction, by the
  // trace, cycles.js fieldForPanelPoint) is solved on an 8 px grid and interpolated; the Blender registration check
  // (beauty_render.py marks=1) uses this frame.
  if (flag('dump') === 'pgupanel' && app.garage && app.garage.hud) {
    const { fieldForPanelPoint } = await import('./cycles.js');
    const GMm = await import('./geom.js');
    const hud = app.garage.hud, W = hud.canvas.width, H = hud.canvas.height, step = 8;
    const nx = Math.ceil(W / step) + 1, ny = Math.ceil(H / step) + 1, map = new Float32Array(nx * ny * 2).fill(NaN);
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      const x = Math.min(W, i * step), y = Math.min(H, j * step);
      const pz = x / W * 0.06 - 0.03, px = (y / H - 0.5) * 0.03;        // panel: lateral, and fore-aft (top of the image at the rear edge)
      const sol = fieldForPanelPoint(GMm.EYE, pz, px);
      if (!sol) continue;
      const q = hud.projectPlane(GMm.EYE.clone().add(GMm.fieldDir(sol.ax, sol.ay)), GMm.EYE);
      if (q) { map[(j * nx + i) * 2] = q[0]; map[(j * nx + i) * 2 + 1] = q[1]; }
    }
    const src = hud.ctx.getImageData(0, 0, W, H).data;
    const out = document.createElement('canvas'); out.width = W; out.height = H;
    const octx = out.getContext('2d'), img = octx.createImageData(W, H), d = img.data;
    const g = (i, j, k) => map[(j * nx + i) * 2 + k];
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const fi = x / step, fj = y / step, i0 = Math.min(nx - 2, Math.floor(fi)), j0 = Math.min(ny - 2, Math.floor(fj)), tx = fi - i0, ty = fj - j0;
      const lerp2 = (k) => (1 - ty) * ((1 - tx) * g(i0, j0, k) + tx * g(i0 + 1, j0, k)) + ty * ((1 - tx) * g(i0, j0 + 1, k) + tx * g(i0 + 1, j0 + 1, k));
      const cx = lerp2(0), cy = lerp2(1), o = (y * W + x) * 4;
      d[o + 3] = 255;
      if (!isFinite(cx) || !isFinite(cy) || cx < 0 || cy < 0 || cx >= W || cy >= H) continue;
      const si = (Math.round(cy) * W + Math.round(cx)) * 4;
      d[o] = src[si]; d[o + 1] = src[si + 1]; d[o + 2] = src[si + 2];
    }
    octx.putImageData(img, 0, 0);
    const pre = document.createElement('pre'); pre.id = 'pguDump'; pre.hidden = true;
    pre.textContent = out.toDataURL('image/png'); document.body.append(pre);
  }
  // #mode&hover=ID shows ID's label as if the pointer were on it (screenshots of the hover state).
  if (flag('hover')) app.setHover(flag('hover'));
  app.start();
  loading.remove();
  if (loadErrors.length) toast('Some modules failed to load: ' + loadErrors.join('; '), 8000);
}

boot().catch((e) => {
  console.error(e);
  const l = document.getElementById('loading');
  if (l) l.textContent = 'Failed to start: ' + e.message;
});
