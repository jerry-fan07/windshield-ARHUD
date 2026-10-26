// Vehicle mode: the parked car in cutaway with everything installed. Overlays show the traced light path, the virtual
// image, the eye box, the wiring, the cameras' fields of view, what part of the road the window covers, and where the
// sun can get in.
import * as THREE from 'three';
import * as GM from '../geom.js';
import { R } from '../params.js';
import { M, C } from '../mats.js';
import { polyline, DEG, textDecal, clamp, visibleBox } from '../util.js';
import { h, setPanel, hidePanel, toggle, chips, btn, kv, tagFor, toast, section } from '../ui.js';
import { REGISTRY } from '../registry.js';
import { MOUNTS, CABLE_COLORS, CABLE_NAMES } from '../install.js';
import { tracedWindow } from '../hud.js';
import { loadCyclesResults, loadSunFocus, cyclesSection } from '../cycles.js';
import { loadScanInfo, scanSection } from '../scan.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);
const STRIPS = [['full', 'Whole car'], ['nodriver', 'No driver'], ['noseats', 'No driver or seats'], ['front', 'Front section only']];

export class VehicleMode {
  constructor(app) {
    this.app = app;
    this.g = app.garage;
    let strip = 'full';
    try { strip = localStorage.getItem('arhud.strip') || 'full'; } catch (e) { /* private window */ }
    if (!STRIPS.some(([k]) => k === strip)) strip = 'full';
    this.opts = { rays: true, vimg: true, eyebox: true, wiring: false, fov: false, coverage: true, sun: false, cutaway: 'side', strip, mirror: GM.MIRROR.mode };
    this.overlays = new THREE.Group(); this.overlays.name = 'vehicleOverlays';
    this.built = false;
    this.pulses = [];
  }

  buildOverlays() {
    const o = this.overlays; o.clear();
    // ---- light path: eye-back traces from three eye-box points through the window corners and centre ----
    this.rayGroup = new THREE.Group(); o.add(this.rayGroup);
    this.buildRays();
    // ---- virtual image planes ----
    this.vimgGroup = new THREE.Group(); o.add(this.vimgGroup);
    const basis = new THREE.Matrix4().makeBasis(GM.VIMG_RIGHT, GM.VIMG_UP, GM.VIMG_N);
    const q = new THREE.Quaternion().setFromRotationMatrix(basis);
    const frame = (dist, w, hh, color, opacity, dashed) => {
      const c = GM.EYE.clone().addScaledVector(GM.LOOK, dist);
      const pts = [[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]].map(([a, b]) => c.clone().addScaledVector(GM.VIMG_RIGHT, a * w / 2).addScaledVector(GM.VIMG_UP, b * hh / 2));
      const l = polyline(pts, color, { opacity, dashed, dash: 0.05, gap: 0.04 });
      return { l, c };
    };
    const spec = frame(GM.VID, GM.IMG_W, GM.IMG_H, 0x5ec8ff, 0.95, false);
    this.vimgGroup.add(spec.l);
    const img = new THREE.Mesh(new THREE.PlaneGeometry(GM.IMG_W, GM.IMG_H), new THREE.MeshBasicMaterial({ map: this.g.hud.texture, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, toneMapped: false }));
    img.position.copy(spec.c); img.quaternion.copy(q); this.vimgGroup.add(img);
    const tr = tracedWindow();
    const trf = frame(tr.dist, tr.w, tr.h, 0xffc04d, 0.8, true);
    this.vimgGroup.add(trf.l);
    // eye rays out to the spec plane corners (dashed: light does not travel there; the eye sees it there)
    for (const [a, b] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      const p = spec.c.clone().addScaledVector(GM.VIMG_RIGHT, a * GM.IMG_W / 2).addScaledVector(GM.VIMG_UP, b * GM.IMG_H / 2);
      this.vimgGroup.add(polyline([GM.EYE, p], 0x5ec8ff, { opacity: 0.35, dashed: true, dash: 0.06, gap: 0.05 }));
    }
    this.vimgLabels = [
      ['Virtual image (spec): 7.5 m, 10.8° × 5.4°, 1.42 × 0.71 m', spec.c.clone().addScaledVector(GM.VIMG_UP, GM.IMG_H / 2 + 0.08)],
      [`As traced: ${tr.dist.toFixed(2)} m, ${tr.fovW.toFixed(1)}° × ${tr.fovH.toFixed(1)}°`, trf.c.clone().addScaledVector(GM.VIMG_UP, -tr.h / 2 - 0.1)],
    ];
    // ---- eye box ----
    this.eyeboxGroup = new THREE.Group(); o.add(this.eyeboxGroup);
    const eb = new THREE.Mesh(new THREE.BoxGeometry(0.004, GM.EYEBOX_H, GM.EYEBOX_W), new THREE.MeshBasicMaterial({ color: 0x5ec8ff, transparent: true, opacity: 0.18, depthWrite: false }));
    eb.position.copy(GM.EYE); this.eyeboxGroup.add(eb);
    const ebe = new THREE.LineSegments(new THREE.EdgesGeometry(eb.geometry), new THREE.LineBasicMaterial({ color: 0x5ec8ff })); ebe.position.copy(GM.EYE); this.eyeboxGroup.add(ebe);
    // ---- road coverage on flat ground ----
    this.coverGroup = new THREE.Group(); o.add(this.coverGroup);
    const near = GM.ROAD_NEAR, far = GM.ROAD_FAR;
    const halfAt = (x) => Math.hypot(x, GM.EYE_H) * Math.tan(GM.FOV_W / 2);
    const cov = new THREE.Shape([new THREE.Vector2(near, -halfAt(near)), new THREE.Vector2(far, -halfAt(far)), new THREE.Vector2(far, halfAt(far)), new THREE.Vector2(near, halfAt(near))]);
    const covMesh = new THREE.Mesh(new THREE.ShapeGeometry(cov), new THREE.MeshBasicMaterial({ color: 0x5ec8ff, transparent: true, opacity: 0.22, depthWrite: false, side: THREE.DoubleSide }));
    covMesh.rotation.x = Math.PI / 2; covMesh.position.y = 0.03;
    this.coverGroup.add(covMesh);
    for (const x of [near, far]) this.coverGroup.add(polyline([V(x, 0.04, -halfAt(x)), V(x, 0.04, halfAt(x))], 0x5ec8ff, { opacity: 0.9 }));
    // sight lines from the eye to the near and far edges
    this.coverGroup.add(polyline([GM.EYE, V(near, 0, 0)], 0x5ec8ff, { opacity: 0.4, dashed: true, dash: 0.2, gap: 0.15 }));
    this.coverGroup.add(polyline([GM.EYE, V(far, 0, 0)], 0x5ec8ff, { opacity: 0.4, dashed: true, dash: 0.2, gap: 0.15 }));
    this.coverLabels = [[`Window covers the road ${near.toFixed(1)}–${far.toFixed(1)} m ahead (look-down ${R.LOOKDOWN}°)`, V((near + far) / 2, 0.3, 0)]];
    // ---- camera fields of view ----
    this.fovGroup = new THREE.Group(); o.add(this.fovGroup);
    const frustum = (origin, dir, up, hfov, vfov, len, color) => {
      const x = dir.clone().normalize(), z = new THREE.Vector3().crossVectors(x, up).normalize(), y = new THREE.Vector3().crossVectors(z, x);
      const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([a, b]) => origin.clone().addScaledVector(x, len).addScaledVector(z, a * len * Math.tan(hfov / 2)).addScaledVector(y, b * len * Math.tan(vfov / 2)));
      const g = new THREE.Group();
      for (const c of corners) g.add(polyline([origin, c], color, { opacity: 0.6 }));
      g.add(polyline([...corners, corners[0]], color, { opacity: 0.6 }));
      const geo = new THREE.BufferGeometry().setFromPoints([origin, corners[0], corners[1], origin, corners[1], corners[2], origin, corners[2], corners[3], origin, corners[3], corners[0]]);
      g.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.06, depthWrite: false, side: THREE.DoubleSide })));
      return g;
    };
    const zedDir = new THREE.Vector3(Math.cos(2 * DEG), -Math.sin(2 * DEG), 0);
    this.fovGroup.add(frustum(GM.ROAD_CAM.clone().add(V(0, 0, 0.06)), zedDir, V(0, 1, 0), 72 * DEG, 44 * DEG, 35, 0x3d8bff));
    this.fovGroup.add(frustum(GM.DRIVER_CAM, GM.EYE.clone().sub(GM.DRIVER_CAM), V(0, 1, 0), 72 * DEG, 50 * DEG, 0.9, 0xc78bff));
    this.fovLabels = [['ZED 2i, 72° × 44° (datasheet; store page says 80° × 52°), depth to 35 m', V(20, 4, 0.37)], ['OAK-D Pro, aimed at the eye', GM.DRIVER_CAM.clone().add(V(-0.25, 0.25, 0))]];
    // ---- sun entry ----
    this.sunGroup = new THREE.Group(); o.add(this.sunGroup);
    const entry = GM.TO_MIRROR.clone().negate();
    const ez = new THREE.Vector3(0, 0, 1), ey = new THREE.Vector3().crossVectors(ez, entry).normalize();
    const L = 1.6, pw = R.PATCH_W * DEG / 2, ph = R.PATCH_H * DEG / 2;
    const pc = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([a, b]) => GM.G.clone().addScaledVector(entry, L).addScaledVector(ez, a * L * Math.tan(pw)).addScaledVector(ey, b * L * Math.tan(ph)));
    const sgeo = new THREE.BufferGeometry().setFromPoints([GM.G, pc[0], pc[1], GM.G, pc[1], pc[2], GM.G, pc[2], pc[3], GM.G, pc[3], pc[0], pc[0], pc[1], pc[2], pc[0], pc[2], pc[3]]);
    this.sunGroup.add(new THREE.Mesh(sgeo, new THREE.MeshBasicMaterial({ color: 0xff7a3d, transparent: true, opacity: 0.16, depthWrite: false, side: THREE.DoubleSide })));
    this.sunGroup.add(polyline([...pc, pc[0]], 0xff7a3d, { opacity: 0.9 }));
    this.sunGroup.add(polyline([GM.G, GM.MIRROR_C, GM.FOLD_C, GM.PANEL_C], 0xff5a36, { opacity: 0.9 }));
    this.sunNow = polyline([GM.G, GM.G.clone().add(V(1, 1, 0))], 0xffe066, { opacity: 1 }); this.sunGroup.add(this.sunNow);
    this.sunLabels = [[`Sun entry patch: ${R.PATCH_W.toFixed(0)}° × ${R.PATCH_H.toFixed(0)}° of sky at ${(180 - R.SUN_ELEV).toFixed(0)}° elevation behind the car`, GM.G.clone().addScaledVector(entry, L + 0.1)]];
    // ---- wiring pulses ----
    this.pulses = [];
    for (const cab of this.g.cables) {
      for (let i = 0; i < 3; i++) {
        const s = new THREE.Mesh(new THREE.SphereGeometry(0.009, 10, 8), M.emissive(CABLE_COLORS[cab.kind], 2.2));
        s.userData = { cab, f: i / 3 };
        this.pulses.push(s); o.add(s);
      }
    }
    this.built = true;
  }

  buildRays() {
    const g = this.rayGroup; g.clear();
    const eyes = [V(0, 0, 0), V(0, 0, -GM.EYEBOX_W / 2), V(0, 0, GM.EYEBOX_W / 2)];
    const fields = [[0, 0], [-1, -1], [1, -1], [1, 1], [-1, 1]];
    for (const eo of eyes) for (const [fx, fy] of fields) {
      const e = GM.EYE.clone().add(eo);
      const r = GM.traceFromEye(e, GM.fieldDir(fx * GM.FOV_W / 2, fy * GM.FOV_H / 2), this.opts.mirror);
      if (!r) continue;
      const centre = eo.lengthSq() === 0;
      g.add(polyline(r.pts.slice().reverse(), C.ray, { opacity: centre ? 0.95 : 0.4 }));
    }
  }

  async enter() {
    const app = this.app, g = this.g;
    if (!this.built) this.buildOverlays();
    g.carGroup.add(this.overlays);
    app.setScene(g.scene, app.camera);
    app.controls.enabled = true;
    g.vimg.visible = false;
    g.installGroup.visible = true;
    g.cableGroup.visible = true;
    g.car.setCutaway && g.car.setCutaway(this.opts.cutaway);
    this.applyStrip();
    g.workLights.visible = true;
    const unit = g.installed.hudUnit;
    if (unit) { unit.comp.setWorking(this.opts.rays); unit.comp.handles && unit.comp.handles.setMirrorMode && unit.comp.handles.setMirrorMode(this.opts.mirror); }
    for (const id of ['jetson', 'controller', 'ledDriver', 'dcdc', 'ethSwitch', 'miniPC', 'zedF9r', 'gnssAntenna']) { const c = g.installed[id]; if (c) c.comp.setWorking(true); }
    this.savedSpeed = g.ego.speed; g.ego.speed = 0;
    app.renderer.toneMappingExposure = (g.world.env && g.world.env.exposure) || 1;
    this.applyVisibility('*');
    this.renderPanels();
    this.view(this.startView || 'dash', 0);
    app.pickables = [g.installGroup, g.cableGroup];
    app.onPick = (id) => this.select(id);
  }

  exit() {
    const g = this.g;
    this.overlays.removeFromParent();
    g.workLights.visible = false;
    g.car.setCutaway && g.car.setCutaway('none');
    g.car.setStrip && g.car.setStrip('full');
    for (const v of Object.values(g.installed)) v.comp.setWorking(false);
    g.ego.speed = this.savedSpeed || 0;
    hidePanel('left'); hidePanel('right'); hidePanel('bottom');
  }

  // changed: the overlay key just switched (its caption is revealed for a few seconds), or '*' on entry.
  applyVisibility(changed = null) {
    const o = this.opts;
    // the HUD unit traces and animates its own light path; draw ours only if it is missing
    const unit = this.g.installed.hudUnit;
    if (unit) unit.comp.setWorking(o.rays);
    this.rayGroup.visible = o.rays && !unit;
    this.vimgGroup.visible = o.vimg;
    this.eyeboxGroup.visible = o.eyebox;
    this.coverGroup.visible = o.coverage;
    this.fovGroup.visible = o.fov;
    this.sunGroup.visible = o.sun;
    for (const p of this.pulses) p.visible = o.wiring;
    for (const cab of this.g.cables) {
      cab.mesh.material = cab.mesh.material; // keep
      cab.mesh.scale.setScalar(1);
    }
    this.labels(changed);
  }

  // How much of the car to take out so the installed parts show: see car.setStrip. "Front section only" flies to the
  // view through the cut unless fly is false.
  setStrip(level, { fly = true } = {}) {
    if (!STRIPS.some(([k]) => k === level)) return;
    const was = this.opts.strip;
    this.opts.strip = level;
    try { localStorage.setItem('arhud.strip', level); } catch (e) { /* private window */ }
    this.stripChips && this.stripChips.set(level);
    this.applyStrip();
    if (fly && level === 'front' && was !== 'front') this.view('behind');
  }
  applyStrip() {
    const g = this.g;
    if (!g.car.setStrip) return;
    g.car.setStrip(this.opts.strip, { cutX: this.cutX(), keepHeadrest: !!g.installed.monitor });
  }
  // The section cut sits 0.2 m behind the rearmost installed part or cable (mini PC 2, behind the passenger seat), so
  // every part keeps the floor and trim it is fixed to. Boxes are taken in the car frame.
  cutX() {
    const g = this.g, cg = g.carGroup;
    cg.updateMatrixWorld(true);
    const inv = cg.matrixWorld.clone().invert(), m = new THREE.Matrix4(), b = new THREE.Box3(), tmp = new THREE.Box3();
    for (const root of [...Object.values(g.installed).map((v) => v.holder), g.cableGroup]) {
      root.traverseVisible((o) => {
        if (!o.isMesh || !o.geometry) return;
        if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
        tmp.copy(o.geometry.boundingBox).applyMatrix4(m.multiplyMatrices(inv, o.matrixWorld));
        if (isFinite(tmp.min.x)) b.union(tmp);
      });
    }
    return b.isEmpty() ? -0.8 : b.min.x - 0.2;
  }

  // Part labels show on hover (or all at once in "All" mode); the selected part stays labelled. Overlay captions
  // have no dot: they show while their toggle is hovered, for a few seconds after it is switched, or in "All" mode.
  labels(changed = null) {
    const app = this.app, g = this.g;
    app.clearLabels();
    g.scene.updateMatrixWorld(true);
    for (const [id, v] of Object.entries(g.installed)) {
      const reg = REGISTRY.find((r) => r.id === id);
      const b = visibleBox(v.holder);
      const c = b.isEmpty() ? v.holder.getWorldPosition(new THREE.Vector3()) : b.getCenter(new THREE.Vector3());
      this._anchors = this._anchors || {};
      let anchor = this._anchors[id];
      if (!anchor) { anchor = new THREE.Object3D(); this._anchors[id] = anchor; }
      anchor.position.copy(g.carGroup.worldToLocal(c.clone()));
      if (anchor.parent !== g.carGroup) g.carGroup.add(anchor);
      const sel = this.selected === id;
      app.label(reg ? reg.name : id, anchor, new THREE.Vector3(), { pickId: id, pin: sel, cls: sel ? 'hl' : '', onClick: () => this.select(id) });
    }
    const cap = (text, pos, key) => app.label(text, g.carGroup, pos, { cls: 'cap', dot: false, group: key, reveal: changed === key || changed === '*' ? 4 : 0 });
    const addTexts = (list, key) => { if (!this.opts[key]) return; for (const [t, p] of list) cap(t, p, key); };
    addTexts(this.vimgLabels, 'vimg');
    addTexts(this.coverLabels, 'coverage');
    addTexts(this.fovLabels, 'fov');
    addTexts(this.sunLabels, 'sun');
    if (this.opts.eyebox) cap('Eye box 130 × 70 mm', GM.EYE.clone().add(V(0, 0.07, 0)), 'eyebox');
    if (window.__debug) {
      const pre = document.getElementById('dbg') || document.body.appendChild(Object.assign(document.createElement('pre'), { id: 'dbg' }));
      pre.textContent = JSON.stringify(Object.fromEntries(Object.entries(this._anchors || {}).map(([k, a]) => [k, [a.position.x, a.position.y, a.position.z, g.installed[k].holder.position.toArray(), g.installed[k].holder.quaternion.toArray()]])));
    }
  }

  select(id) {
    const g = this.g;
    if (id.startsWith('cable:')) {
      const cab = g.cables.find((c) => 'cable:' + c.id === id);
      if (!cab) return;
      this.selected = id;
      setPanel('right', h('h2', {}, cab.label), kv([['Kind', CABLE_NAMES[cab.kind]], ['Length (as routed)', `${cab.length.toFixed(2)} m`]]), h('p', { class: 'muted', style: { marginTop: '8px' } }, 'No wire reaches the car\'s buses. The 12 V feed is the only connection to the vehicle.'));
      return;
    }
    const v = g.installed[id]; if (!v) return;
    this.selected = id;
    const c = v.comp;
    setPanel('right',
      h('h2', {}, c.name),
      h('p', { class: 'muted' }, h('b', {}, 'Mounted: '), (MOUNTS[id] && MOUNTS[id].note) || ''),
      h('p', {}, tagFor(c.desc)),
      h('div', { class: 'kv' }, c.facts.flatMap(([k, val]) => [h('span', {}, k), h('span', {}, tagFor(String(val)))])),
      h('div', { class: 'row', style: { marginTop: '10px' } },
        btn('Open in Components', () => { this.app.modes.parts.pendingSelect = id; this.app.setMode('parts'); }, { primary: true }),
        btn('Fly to it', () => this.app.frameObject(v.holder, { dir: V(-0.6, 0.55, -1), pad: 2.2 }))),
    );
    this.labels();
  }

  renderPanels() {
    const o = this.opts;
    const set = (k) => (v) => { o[k] = v; this.applyVisibility(k); };
    // Hovering an overlay's toggle holds its caption on screen.
    const ov = (key, label) => {
      const t = toggle({ id: 'o-' + key, label, checked: o[key], onChange: set(key) });
      t.addEventListener('pointerenter', () => this.app.holdGroup(key, true));
      t.addEventListener('pointerleave', () => this.app.holdGroup(key, false));
      return t;
    };
    const legend = h('div', { class: 'legend' }, Object.entries(CABLE_NAMES).map(([k, n]) => h('span', {}, h('i', { style: { background: '#' + CABLE_COLORS[k].toString(16).padStart(6, '0') } }), n)));
    setPanel('left',
      h('h2', {}, 'Vehicle'),
      h('p', { class: 'hint' }, 'The car parked with everything installed. Orbit with the mouse. Point at a part for its name, click it for its numbers.'),
      h('h3', {}, 'Camera'),
      h('div', { class: 'chips' }, [['cabin', 'Cabin'], ['dash', 'HUD unit'], ['section', 'Side section'], ['behind', 'Through the cut'], ['passenger', 'Passenger side'], ['top', 'From above'], ['ahead', 'From the road'], ['sun', 'Sun and glass'], ['wiring', 'Footwell']].map(([k, l]) => h('button', { class: 'chip', type: 'button', onclick: () => this.view(k) }, l))),
      h('h3', {}, 'Strip the car'),
      (this.stripChips = chips({ id: 'strip', options: STRIPS, value: o.strip, onChange: (v) => this.setStrip(v) })),
      section('veh-overlays', 'Overlays', true,
        ov('rays', 'Traced light path'),
        ov('vimg', 'Virtual image and eye rays'),
        ov('eyebox', 'Eye box'),
        ov('coverage', 'Road the window covers'),
        ov('fov', 'Camera fields of view'),
        ov('sun', 'Sun entry patch'),
        ov('wiring', 'Wiring signal flow'),
        legend),
      section('veh-body', 'Body', false,
        this.cutChips = chips({ id: 'cut', options: [['side', 'Driver side open'], ['passenger', 'Passenger side open'], ['both', 'Both sides open'], ['xray', 'X-ray'], ['none', 'Closed']], value: o.cutaway, onChange: (v) => { o.cutaway = v; this.g.car.setCutaway && this.g.car.setCutaway(v); } })),
      section('veh-mirror', 'Concave mirror', false,
        chips({ id: 'mm', options: [['toroid', 'Toroid (corrected)'], ['sphere', 'Sphere (plan as written)'], ['freeform', 'Freeform + tilted panel (flat image, Blender-fitted)'], ['freeformCurved', 'Freeform for a curved windshield (4 m × 8 m radii)']], value: o.mirror, onChange: (v) => { o.mirror = v; GM.MIRROR.mode = v; GM.setGlassForMode(v); this.buildRays(); const u = this.g.installed.hudUnit; u && u.comp.handles && u.comp.handles.setMirrorMode && u.comp.handles.setMirrorMode(v); this.g.applyPanelPose && this.g.applyPanelPose(v); this.renderOptics(); } })),
    );
    this.renderOptics();
    hidePanel('bottom');
  }

  renderOptics() {
    const L = GM.LAYOUT_SUMMARY();
    const im = GM.mirrorImages(this.opts.mirror);
    const tr = tracedWindow();
    const d = (v) => `${(v.x * 1000).toFixed(0)}, ${(v.y * 1000).toFixed(0)}`;
    setPanel('right',
      h('h2', {}, 'Optical layout, as installed'),
      h('p', { class: 'hint' }, 'Side-view positions in millimetres (forward, up) from the ground under the eye.'),
      kv([
        ['Eye point', d(GM.EYE)],
        ['Glass point (look-down 5°, 750 mm)', d(GM.G)],
        ['Concave mirror centre', d(GM.MIRROR_C)],
        ['Cold-mirror fold', d(GM.FOLD_C)],
        ['Panel crop centre', d(GM.PANEL_C)],
        ['Mirror incidence', `${L.mirrorIncDeg.toFixed(1)}°`],
        ['Fold incidence', `${L.foldIncDeg.toFixed(1)}°`],
        ['Eye to mirror path', `${(L.eyeToMirror * 1000).toFixed(0)} mm (plan 1,000, ASSUMED)`],
        ['Panel to mirror (u)', `${R.U2.toFixed(0)} mm, f ${R.F2} mm`],
        // paraxial foci at the vertex; the freeform is judged by its parallax-measured image (Cycles reference), not these
        ['Tangential image', `${(-im.vt).toFixed(2)} m behind the mirror${this.opts.mirror === 'freeform' ? ' (vertex)' : ''}`, Math.abs(im.vt + 7.5) < 0.2 ? 'good' : this.opts.mirror === 'freeform' ? 'warn' : 'bad'],
        ['Sagittal image', `${(-im.vs).toFixed(2)} m behind the mirror${this.opts.mirror === 'freeform' ? ' (vertex)' : ''}`, Math.abs(im.vs + 7.5) < 0.2 ? 'good' : this.opts.mirror === 'freeform' ? 'warn' : 'bad'],
        ['Image from the eye, traced', `${tr.dist.toFixed(2)} m (spec 7.5 m)`],
        ['Window, traced, after keystone fix', `${tr.fovW.toFixed(1)}° × ${tr.fovH.toFixed(1)}° (spec 10.8° × 5.4°)`],
        ['Road camera to eye baseline', `${(L.baseline * 100).toFixed(0)} cm (plan 45 cm, ASSUMED)`],
      ].map(([k, v, c]) => [k, tagFor(v), c]).map(([k, v, c]) => [k, v, c])),
      section('veh-notes', 'What the trace found', false,
        h('div', { class: 'note' }, tagFor(GM.SIM_NOTES[0].text)),
        h('div', { class: 'note' }, `A sphere used ${L.mirrorIncDeg.toFixed(0)}° off-axis with the panel ${(R.F2 - R.U2).toFixed(0)} mm inside focus splits the image into ${(-GM.mirrorImages('sphere').vt).toFixed(1)} m and ${(-GM.mirrorImages('sphere').vs).toFixed(1)} m. A toroid with Rt = ${(GM.R_T_CORR * 1000).toFixed(0)} mm and Rs = ${(GM.R_S_CORR * 1000).toFixed(0)} mm brings both to 7.5 m; the ray trace with the real windshield sets the final figure.`)),
      h('div', { id: 'cyclesSlot' }),
      h('div', { id: 'scanSlot' }),
    );
    // The scanned car (assets/scan.*), when a scan has been aligned with docs/arhud-blender/import_scan.py.
    loadScanInfo().then((meta) => {
      const slot = document.getElementById('scanSlot');
      if (slot) slot.replaceWith(scanSection(meta, this.g));
    });
    // The Blender path-traced reference (assets/cycles) drops in once its results have loaded.
    Promise.all([loadCyclesResults(), loadSunFocus()]).then(([res, sun]) => {
      const slot = document.getElementById('cyclesSlot');
      if (slot) slot.replaceWith(cyclesSection(res, this.opts.mirror, sun));
    });
  }

  view(name, dur = 1.2) {
    const g = this.g, cg = g.carGroup;
    const W = (x, y, z) => cg.localToWorld(V(x, y, z));
    const views = {
      cabin: [W(0.2, 1.55, -1.6), W(0.75, 0.95, 0.1)],
      dash: [W(-0.3, 1.42, -0.62), W(0.8, 0.95, 0.05)],
      section: [W(0.8, 1.05, -1.25), W(0.8, 0.98, 0.0)],
      top: [W(0.7, 3.2, 0.37), W(0.7, 0.9, 0.37)],
      ahead: [W(14, 3.0, -3.5), W(3, 0.8, 0.37)],
      sun: [W(-1.8, 2.6, -2.2), W(0.8, 1.0, 0.1)],
      wiring: [W(0.1, 1.0, 1.6), W(0.5, 0.35, 0.7)],
      passenger: [W(0.3, 1.45, 2.35), W(0.75, 0.75, 0.75)],   // from outside the passenger door: dash end, GNSS antenna, Jetson in the footwell
      behind: [W(-1.45, 1.32, 0.12), W(0.62, 0.6, 0.45)],
    };
    // Looking in through the cut needs the cut.
    if (name === 'behind' && this.opts.strip !== 'front') this.setStrip('front', { fly: false });
    const [p, t] = views[name] || views.cabin;
    if (dur <= 0) { this.app.camera.position.copy(p); this.app.controls.target.copy(t); this.app.controls.update(); }
    else this.app.flyTo(p, t, dur);
    if (name === 'sun' && !this.opts.sun) { this.opts.sun = true; document.getElementById('o-sun') && (document.getElementById('o-sun').checked = true); this.applyVisibility('sun'); }
    if (name === 'wiring' && !this.opts.wiring) { this.opts.wiring = true; document.getElementById('o-wiring') && (document.getElementById('o-wiring').checked = true); this.applyVisibility('wiring'); }
    // the passenger-side view opens that side of the car too (the driver's side stays as it is)
    if (name === 'passenger' && (this.opts.cutaway === 'side' || this.opts.cutaway === 'none')) {
      this.opts.cutaway = this.opts.cutaway === 'side' ? 'both' : 'passenger';
      this.g.car.setCutaway && this.g.car.setCutaway(this.opts.cutaway);
      this.cutChips && this.cutChips.set(this.opts.cutaway);
    }
  }

  update(t, dt) {
    const g = this.g;
    const pose = g.placeEgo(t);
    g.car.updateSection && g.car.updateSection();
    // keep the HUD software running so the panel shows a live frame
    const sunDirCar = g.world.sunDir ? g.toCarDir(g.world.sunDir) : null;
    g.hud.update(t, dt, { sunDirCar, eyeOffset: new THREE.Vector3(), ambientLux: g.ambientLux() });
    for (const v of Object.values(g.installed)) v.comp.update(t, dt, { working: true, explode: 0, live: g.hud });
    const unit = g.installed.hudUnit;
    if (unit && unit.comp.handles) {
      unit.comp.handles.setShutter && unit.comp.handles.setShutter(g.hud.shutter.open);
      unit.comp.handles.setBacklight && unit.comp.handles.setBacklight(g.hud.lum.duty);
    }
    if (this.opts.wiring) {
      for (const p of this.pulses) {
        const cab = p.userData.cab;
        const speed = cab.kind === 'power' ? 0.25 : 0.6;
        const f = (p.userData.f + t * speed / Math.max(0.5, cab.length)) % 1;
        p.position.copy(cab.curve.getPointAt(f));
      }
    }
    if (this.opts.sun && g.world.sunDir) {
      const d = g.toCarDir(g.world.sunDir);
      const arr = this.sunNow.geometry.attributes.position.array;
      const end = GM.G.clone().addScaledVector(d, 1.6);
      arr[3] = end.x; arr[4] = end.y; arr[5] = end.z; this.sunNow.geometry.attributes.position.needsUpdate = true;
    }
    if (g.drawAudience && Math.floor(t * 4) !== Math.floor((t - dt) * 4)) g.drawAudience(null);
  }
}
