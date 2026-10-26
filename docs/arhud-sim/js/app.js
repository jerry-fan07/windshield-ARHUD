// The application core: renderer and post-processing, the studio scene used on the bench, the world scene with the
// car, label overlay, picking, camera tweening, and the mode switcher.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { M } from './mats.js';
import { canvasTexture, easeInOut, clamp, rbox, box, visibleBox } from './util.js';
import { h } from './ui.js';

export class App {
  constructor() {
    this.stage = document.getElementById('stage');
    const r = this.renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: 'high-performance' });
    r.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    r.outputColorSpace = THREE.SRGBColorSpace;
    r.toneMapping = THREE.ACESFilmicToneMapping;
    r.toneMappingExposure = 1;
    r.shadowMap.enabled = true;
    r.shadowMap.type = THREE.PCFSoftShadowMap;
    r.localClippingEnabled = true;   // the car's section cut (Vehicle mode, front section only)
    r.domElement.className = 'gl';
    this.stage.prepend(r.domElement);

    this.camera = new THREE.PerspectiveCamera(45, 1, 0.005, 6000);
    this.camera.layers.enable(1);   // layer 1: the components' explanatory sprites (hidden when labels are off)
    this.camera.position.set(0.6, 0.4, 0.8);
    this.controls = new OrbitControls(this.camera, r.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.screenSpacePanning = true;

    const rt = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, samples: 4 });
    this.composer = new EffectComposer(r, rt);
    this.renderPass = new RenderPass(new THREE.Scene(), this.camera);
    this.composer.addPass(this.renderPass);
    this.bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.35, 0.5, 0.9);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());

    this.labelEl = document.getElementById('labels');
    this.labelRenderer = new CSS2DRenderer({ element: this.labelEl });
    // Labels: every label is a dot at its anchor; its text shows on hover (of the dot or of the part under the
    // pointer), while selected, for a few seconds after a reveal, or always in "all" mode.
    this.labelMode = 'hover';
    this.hoverId = null;
    this._hoverEvt = null; this._hoverT = 0;

    this.pmrem = new THREE.PMREMGenerator(r);
    this.roomEnv = this.pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    this.studio = this.makeStudio();
    this.labels = new Set();
    this.modes = {};
    this.mode = null;
    this.clock = new THREE.Clock();
    this.t = 0;
    this.tween = null;
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.pickables = [];
    this.onPick = null;
    this.fpsEl = document.getElementById('fps');
    this.frames = 0; this.fpsT = 0;

    window.addEventListener('resize', () => this.resize());
    // Hover is read on the stage, not the canvas: a label under the pointer must not clear the hover that showed it.
    this.stage.addEventListener('pointermove', (e) => {
      const t = e.target;
      const lbl = t && t.closest && t.closest('.lbl');
      if (lbl) { if (lbl.__pickId) this.setHover(lbl.__pickId); return; }
      if (t && t.closest && t.closest('.panel, #dock, #toast')) { this._hoverEvt = null; this.setHover(null); return; }
      this._hoverEvt = e;
    });
    this.stage.addEventListener('pointerleave', () => { this._hoverEvt = null; this.setHover(null); });
    r.domElement.addEventListener('pointerdown', (e) => { this._down = [e.clientX, e.clientY]; });
    r.domElement.addEventListener('pointerup', (e) => {
      if (!this._down) return;
      const moved = Math.hypot(e.clientX - this._down[0], e.clientY - this._down[1]);
      this._down = null;
      if (moved < 5) this.pick(e);
    });
    this.resize();
  }

  makeStudio() {
    const s = new THREE.Scene();
    s.environment = this.roomEnv;
    s.environmentIntensity = 0.7;
    // dark backdrop with a soft vertical gradient
    s.background = canvasTexture(4, 256, (ctx, W, H) => {
      const g = ctx.createLinearGradient(0, 0, 0, H);
      g.addColorStop(0, '#1b222b'); g.addColorStop(0.55, '#10151b'); g.addColorStop(1, '#0a0d11');
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    });
    s.add(new THREE.HemisphereLight(0xdfe8ff, 0x1a1c20, 0.6));
    const key = new THREE.DirectionalLight(0xffffff, 2.2);
    key.position.set(1.2, 2.2, 1.4);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    const sc = key.shadow.camera; sc.left = -1.2; sc.right = 1.2; sc.top = 1.2; sc.bottom = -1.2; sc.near = 0.1; sc.far = 6;
    key.shadow.bias = -0.0004; key.shadow.normalBias = 0.01;
    s.add(key);
    const rim = new THREE.DirectionalLight(0x9cc8ff, 0.8); rim.position.set(-1.5, 1.0, -1.2); s.add(rim);
    // workbench: dark ESD mat on a bench top, with a millimetre grid
    const mat = new THREE.MeshStandardMaterial({
      color: 0xffffff, roughness: 0.92, metalness: 0,
      map: canvasTexture(1024, 1024, (ctx, W, H) => {
        ctx.fillStyle = '#20262c'; ctx.fillRect(0, 0, W, H);
        ctx.strokeStyle = 'rgba(120,150,170,0.10)'; ctx.lineWidth = 1;
        for (let i = 0; i <= W; i += W / 40) { ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, H); ctx.stroke(); ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(W, i); ctx.stroke(); }
        ctx.strokeStyle = 'rgba(120,150,170,0.22)'; ctx.lineWidth = 2;
        for (let i = 0; i <= W; i += W / 8) { ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, H); ctx.stroke(); ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(W, i); ctx.stroke(); }
      }),
    });
    const top = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.04, 1.6), [M.color(0x3a3530, 0.8), M.color(0x3a3530, 0.8), mat, M.color(0x3a3530, 0.8), M.color(0x3a3530, 0.8), M.color(0x3a3530, 0.8)]);
    top.position.y = -0.02; top.receiveShadow = true;
    s.add(top);
    const floor = new THREE.Mesh(new THREE.CircleGeometry(12, 64), M.color(0x0c0f13, 1));
    floor.rotation.x = -Math.PI / 2; floor.position.y = -0.9; floor.receiveShadow = true;
    s.add(floor);
    for (const [x, z] of [[-1.1, -0.7], [1.1, -0.7], [-1.1, 0.7], [1.1, 0.7]]) { const leg = box(0.05, 0.86, 0.05, M.aluDark); leg.position.set(x, -0.47, z); s.add(leg); }
    s.userData.bench = top;
    return s;
  }

  resize() {
    const w = this.stage.clientWidth, h2 = this.stage.clientHeight;
    this.renderer.setSize(w, h2, false);
    this.composer.setSize(w, h2);
    this.labelRenderer.setSize(w, h2);
    this.bloom.setSize(w, h2);
    this.camera.aspect = w / Math.max(1, h2);
    this.camera.updateProjectionMatrix();
    if (this.mode && this.mode.resize) this.mode.resize(w, h2);
  }

  addMode(name, mode) { this.modes[name] = mode; }

  async setMode(name) {
    if (this.modeName === name) return;
    if (this.mode && this.mode.exit) this.mode.exit();
    this.clearLabels();
    this.pickables = []; this.onPick = null;
    this.modeName = name;
    this.mode = this.modes[name];
    document.body.dataset.mode = name;
    document.querySelectorAll('#modes button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.mode === name)));
    try { history.replaceState(null, '', '#' + name); } catch (e) { /* sandboxed */ }
    if (this.mode.enter) await this.mode.enter();
  }

  setScene(scene, camera = this.camera) {
    this.scene = scene;
    // The world needs near >= 0.05 (the grass bleeds through the road otherwise); the bench needs a small near.
    const near = scene === this.studio ? 0.005 : 0.05, far = scene === this.studio ? 200 : 20000;
    if (camera.near !== near || camera.far !== far) { camera.near = near; camera.far = far; camera.updateProjectionMatrix(); }
    this.renderPass.scene = scene;
    this.renderPass.camera = camera;
    this.activeCamera = camera;
    this.applyLabelLayer(camera);
  }
  applyLabelLayer(camera) { if (!camera) return; if (this.labelMode === 'off') camera.layers.disable(1); else camera.layers.enable(1); }

  // ---- labels ----
  // text: the label. obj/pos: what it follows. pickId: the part it names (hovering that part shows it). pin: always
  // shown (the selection). dot: draw the anchor dot (captions on overlays use dot: false and show on reveal only).
  // group: a key the mode can reveal or hold together. reveal: seconds to show it right away.
  label(text, obj, pos = new THREE.Vector3(), { cls = '', onClick = null, title = null, pickId = null, pin = false, dot = true, group = null, reveal = 0 } = {}) {
    const el = h('div', { class: ['lbl', cls, dot ? '' : 'nodot', onClick ? 'click' : ''].filter(Boolean).join(' '), title }, h('i', { class: 'dot' }), h('span', { class: 'txt' }, text));
    if (onClick) el.addEventListener('pointerdown', (e) => { e.stopPropagation(); onClick(); });
    el.__pickId = pickId;
    const o = new CSS2DObject(el);
    o.position.copy(pos);
    obj.add(o);
    this.labels.add(o);
    o.userData.pickId = pickId; o.userData.pin = pin; o.userData.group = group; o.userData.held = false; o.userData.revealUntil = 0;
    if (reveal > 0) this.reveal(o, reveal); else this.applyLabel(o);
    return o;
  }
  applyLabel(o) {
    const u = o.userData;
    const on = u.pin || u.held || (u.pickId !== null && u.pickId === this.hoverId) || u.revealUntil > performance.now();
    o.element.classList.toggle('show', !!on);
  }
  reveal(o, secs = 4) {
    const u = o.userData;
    u.revealUntil = performance.now() + secs * 1000;
    this.applyLabel(o);
    clearTimeout(u.revealT);
    u.revealT = setTimeout(() => { if (this.labels.has(o)) this.applyLabel(o); }, secs * 1000 + 30);
  }
  revealGroup(group, secs = 4) { for (const o of this.labels) if (o.userData.group === group) this.reveal(o, secs); }
  holdGroup(group, on) { for (const o of this.labels) if (o.userData.group === group) { o.userData.held = on; this.applyLabel(o); } }
  setHover(id) {
    if (id === this.hoverId) return;
    this.hoverId = id;
    for (const o of this.labels) this.applyLabel(o);
  }
  setLabelMode(m) {
    this.labelMode = m;
    this.labelEl.classList.toggle('all', m === 'all');
    this.labelEl.classList.toggle('off', m === 'off');
    this.applyLabelLayer(this.camera); this.applyLabelLayer(this.activeCamera);
    document.querySelectorAll('#labelMode button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === m)));
    try { localStorage.setItem('arhud.labels', m); } catch (e) { /* private window */ }
  }
  // compact: hide every dot and the "all" texts (a component that is not exploded would stack them on one spot)
  setLabelsCompact(on) { this.labelEl.classList.toggle('compact', !!on); }
  clearLabels() {
    for (const o of this.labels) { clearTimeout(o.userData.revealT); o.removeFromParent(); o.element.remove(); }
    this.labels.clear();
    this.hoverId = null;
    this.labelEl.classList.remove('compact');
  }

  // ---- picking ----
  // The pickId under a pointer event, or null. A hit counts only if every ancestor is visible (the raycaster itself
  // ignores visibility, and hidden parts sit in front of visible ones in cutaways and part-by-part builds).
  pickIdAt(e) {
    if (!this.pickables.length) return null;
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.pointer.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
    this.raycaster.setFromCamera(this.pointer, this.activeCamera || this.camera);
    const hits = this.raycaster.intersectObjects(this.pickables, true);
    for (const hit of hits) {
      let o = hit.object, id = null, shown = true;
      while (o) { if (o.visible === false) { shown = false; break; } if (id === null && o.userData.pickId) id = o.userData.pickId; o = o.parent; }
      if (!shown) continue;
      return id;
    }
    return null;
  }
  pick(e) {
    if (!this.onPick) return;
    const id = this.pickIdAt(e);
    if (id) this.onPick(id);
  }
  hoverStep() {
    if (!this._hoverEvt || this.t - this._hoverT < 0.08) return;
    this._hoverT = this.t;
    const e = this._hoverEvt; this._hoverEvt = null;
    const id = e.buttons === 0 && this.labelMode !== 'off' ? this.pickIdAt(e) : null;
    this.setHover(id);
    this.renderer.domElement.style.cursor = id && this.onPick ? 'pointer' : '';
  }

  // ---- camera tween (orbit modes) ----
  flyTo(pos, target, dur = 1.2) {
    this.tween = { p0: this.camera.position.clone(), t0: this.controls.target.clone(), p1: pos.clone(), t1: target.clone(), s: 0, dur };
  }
  frameObject(obj, { dir = new THREE.Vector3(1, 0.7, 1.2), pad = 1.35, dur = 1.0, minDist = 0.12 } = {}) {
    const b = obj.isBox3 ? obj : visibleBox(obj);
    if (b.isEmpty()) return;
    const c = b.getCenter(new THREE.Vector3());
    const r = b.getSize(new THREE.Vector3()).length() / 2;
    const fov = this.camera.fov * Math.PI / 180;
    const dist = Math.max(minDist, (r * pad) / Math.sin(fov / 2));
    const p = c.clone().add(dir.clone().normalize().multiplyScalar(dist));
    if (dur <= 0) { this.camera.position.copy(p); this.controls.target.copy(c); this.controls.update(); }
    else this.flyTo(p, c, dur);
  }

  // Advance the simulation one step without drawing (the render loop and the warm-up hook both use it).
  step(dt) {
    this.t += dt;
    if (this.tween) {
      const tw = this.tween; tw.s = Math.min(1, tw.s + dt / tw.dur);
      const k = easeInOut(tw.s);
      this.camera.position.lerpVectors(tw.p0, tw.p1, k);
      this.controls.target.lerpVectors(tw.t0, tw.t1, k);
      if (tw.s >= 1) this.tween = null;
    }
    if (this.controls.enabled) this.controls.update();
    if (this.mode && this.mode.update) this.mode.update(this.t, dt);
    this.hoverStep();
  }

  start() {
    const loop = () => {
      requestAnimationFrame(loop);
      const dt = Math.min(0.05, this.clock.getDelta());
      this.step(dt);
      if (this.scene) {
        this.composer.render();
        this.labelRenderer.render(this.scene, this.activeCamera || this.camera);
      }
      this.frames++;
      if (this.t - this.fpsT > 1) { this.fpsEl.textContent = `${this.frames} fps`; this.frames = 0; this.fpsT = this.t; }
    };
    loop();
  }
}
