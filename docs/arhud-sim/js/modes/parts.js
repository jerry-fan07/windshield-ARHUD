// Components mode: every part of the HUD on the workbench, one at a time. Explode it, run it, step through how it is
// built, and read its numbers.
import * as THREE from 'three';
import { REGISTRY, CATEGORIES, available, build, setExplode } from '../registry.js';
import { h, setPanel, hidePanel, slider, toggle, chips, kv, btn, tagFor, section } from '../ui.js';
import { Assembler } from './assembler.js';
import { clamp, visibleBox } from '../util.js';

export class PartsMode {
  constructor(app) {
    this.app = app;
    this.cache = new Map();
    this.current = null;
    this.explode = 0; this.explodeTarget = 0;
    this.working = true;
    this.selectedPart = null;
    this.helper = null;
  }

  async enter() {
    const app = this.app;
    app.setScene(app.studio);
    app.controls.enabled = true;
    app.renderer.toneMappingExposure = 1.0;
    app.bloom.strength = 0.35;
    this.renderList();
    const wanted = this.pendingSelect || (this.current && this.current.id) || 'backlight';
    this.pendingSelect = null;
    this.select(available(wanted) ? wanted : (REGISTRY.find((r) => available(r.id)) || {}).id);
  }
  exit() {
    if (this.current) this.app.studio.remove(this.holder);
    if (this.helper) { this.helper.removeFromParent(); this.helper = null; }
    hidePanel('left'); hidePanel('right'); hidePanel('bottom');
  }

  renderList() {
    const groups = CATEGORIES.map(([cat, label]) => {
      const items = REGISTRY.filter((r) => r.cat === cat);
      if (!items.length) return null;
      return [h('h3', {}, label), h('div', { class: 'list' }, items.map((r) => {
        const ok = available(r.id);
        const b = h('button', { class: 'item', type: 'button', 'data-id': r.id, disabled: ok ? null : true, title: ok ? null : 'Module did not load' }, h('span', {}, r.name), ok ? null : h('small', {}, 'missing'));
        b.addEventListener('click', () => this.select(r.id));
        return b;
      }))];
    });
    setPanel('left', h('h2', {}, 'Components'), h('p', { class: 'hint' }, 'Every part of the plan, on the bench. Pick one, explode it, run it, and step through how it is built.'), ...groups.flat());
  }

  select(id) {
    if (!id) return;
    const app = this.app;
    if (this.current) { app.studio.remove(this.holder); this.current.setWorking(false); }
    if (this.helper) { this.helper.removeFromParent(); this.helper = null; }
    app.clearLabels();
    let c = this.cache.get(id);
    if (!c) { c = build(id); if (!c) return; this.cache.set(id, c); }
    this.current = c;
    this.selectedPart = null;
    // centre on the bench
    if (!this.holder) this.holder = new THREE.Group();
    this.holder.clear();
    this.holder.add(c.group);
    c.group.position.set(0, 0, 0);
    setExplode(c, 0);
    c.group.updateMatrixWorld(true);
    const b = visibleBox(c.group);
    const ctr = b.getCenter(new THREE.Vector3());
    c.group.position.set(-ctr.x, -b.min.y + 0.002, -ctr.z);
    app.studio.add(this.holder);
    this.holder.updateMatrixWorld(true);
    // part label anchors at each part's own centre
    for (const p of c.parts) {
      if (!p.anchor) {
        const pb = visibleBox(p.object);
        const wc = pb.isEmpty() ? p.object.getWorldPosition(new THREE.Vector3()) : pb.getCenter(new THREE.Vector3());
        p.anchor = p.object.worldToLocal(wc.clone());
      }
    }
    this.assembler = new Assembler(c);
    this.explode = this.explodeTarget = 0;
    c.setWorking(false);
    const b0 = visibleBox(this.holder);
    c.setWorking(this.working);
    const b1 = visibleBox(this.holder);
    // include the working visuals (pixel dioramas, ray fans) unless they are far bigger than the part itself
    const s0 = b0.getSize(new THREE.Vector3()).length(), s1 = b1.getSize(new THREE.Vector3()).length();
    const fb = s1 <= 2.5 * s0 ? b1 : b0;
    c.setWorking(false);
    app.frameObject(fb, { dir: new THREE.Vector3(1, 0.75, 1.3), pad: fb.getSize(new THREE.Vector3()).length() > 1 ? 1.15 : 1.4 });
    this.labels();
    c.setWorking(this.working);
    document.querySelectorAll('#left .item').forEach((el) => el.setAttribute('aria-current', String(el.dataset.id === id)));
    this.renderInfo();
    app.pickables = [this.holder];
    for (const p of c.parts) p.object.userData.pickId = p.id;
    app.onPick = (pid) => this.selectPart(pid);
  }

  // Every part has a label that shows when the part is under the pointer; the selected part stays labelled. The dots
  // (and the "All" texts) appear only once the part is exploded, since assembled parts share one spot.
  labels() {
    const app = this.app, c = this.current;
    app.clearLabels();
    for (const p of c.parts) {
      if (!p.name || p.id === 'note') continue;
      const sel = this.selectedPart === p.id;
      app.label(p.name, p.object, p.anchor, { pickId: p.id, pin: sel, cls: sel ? 'hl' : '', onClick: () => this.selectPart(p.id) });
    }
    this._compact = this.explodeTarget < 0.3;
    app.setLabelsCompact(this._compact);
  }

  selectPart(pid) {
    const c = this.current; if (!c) return;
    const p = c.parts.find((q) => q.id === pid); if (!p) return;
    this.selectedPart = pid;
    if (this.helper) this.helper.removeFromParent();
    this.helper = new THREE.BoxHelper(p.object, 0x5ec8ff);
    this.helper.material.depthTest = false; this.helper.renderOrder = 10;
    this.app.studio.add(this.helper);
    this.labels();
    const info = document.getElementById('partInfo');
    if (info) info.replaceChildren(h('b', {}, p.name), h('p', { class: 'muted', style: { margin: '2px 0 0' } }, tagFor(p.desc || '')));
    document.querySelectorAll('#partList .item').forEach((el) => el.setAttribute('aria-current', String(el.dataset.id === pid)));
  }

  renderInfo() {
    const c = this.current;
    const explode = slider({ id: 'explode', label: 'Explode', min: 0, max: 1, step: 0.01, value: this.explodeTarget, fmt: (x) => `${Math.round(x * 100)}%`, onInput: (v) => { this.explodeTarget = v; } });
    const work = toggle({ id: 'working', label: 'Run it (working animation)', checked: this.working, onChange: (v) => { this.working = v; c.setWorking(v); } });
    const extra = (c.controls || []).map((ct) => {
      if (ct.type === 'toggle') return toggle({ id: 'cc-' + ct.id, label: ct.label, checked: ct.value, onChange: ct.onChange });
      if (ct.type === 'chips') return h('div', {}, h('div', { class: 'muted', style: { fontSize: '12px', margin: '6px 0 4px' } }, ct.label), chips({ id: 'cc-' + ct.id, options: ct.options, value: ct.value, onChange: ct.onChange }));
      if (ct.type === 'slider') return slider({ id: 'cc-' + ct.id, label: ct.label, min: ct.min, max: ct.max, step: ct.step, value: ct.value, fmt: ct.fmt, onInput: ct.onChange });
      return null;
    });
    const partList = h('div', { class: 'list', id: 'partList' }, c.parts.filter((p) => p.name).map((p) => {
      const b = h('button', { class: 'item', type: 'button', 'data-id': p.id }, h('span', {}, p.name));
      b.addEventListener('click', () => this.selectPart(p.id));
      return b;
    }));
    setPanel('right',
      h('h2', {}, c.name),
      h('p', { class: 'hint' }, tagFor(c.desc)),
      explode, work, ...extra,
      h('p', { style: { fontSize: '12px' } }, h('span', { class: 'muted' }, 'Working: '), tagFor(c.working)),
      h('div', { id: 'partInfo', style: { minHeight: '18px', fontSize: '12px', margin: '8px 0 2px' } }, h('span', { class: 'muted' }, 'Point at a part for its name; click it for details.')),
      section('parts-numbers', 'Numbers', true, h('div', { class: 'kv' }, c.facts.flatMap(([k, v]) => [h('span', {}, k), h('span', {}, tagFor(String(v)))]))),
      section('parts-list', `Parts (${c.parts.filter((p) => p.name).length})`, false, partList),
    );
    this.renderAssembly();
  }

  renderAssembly() {
    const c = this.current, A = this.assembler;
    const n = c.assembly.length;
    const stepIdx = A.step >= n ? n - 1 : A.step;
    const cur = c.assembly[clamp(stepIdx, 0, n - 1)];
    const done = A.step >= n;
    const bar = h('div', { class: 'progress' }, h('i', { style: { width: `${((done ? n : A.step) / n) * 100}%` } }));
    const play = btn(this.playing ? 'Pause' : (done ? 'Build it from the ground up' : 'Play'), () => {
      if (done && !this.playing) { A.setStep(0); this.playing = true; this.playT = 0; }
      else this.playing = !this.playing;
      this.renderAssembly();
    }, { primary: true });
    const prev = btn('Back', () => { this.playing = false; A.setStep(Math.max(0, (done ? n : A.step) - 1)); this.renderAssembly(); });
    const next = btn('Next', () => { this.playing = false; if (A.step < n) A.setStep(A.step + 1); this.renderAssembly(); });
    setPanel('bottom',
      h('div', { class: 'row', style: { justifyContent: 'space-between' } },
        h('div', { style: { minWidth: 0, flex: '1 1 260px' } },
          h('div', { class: 'muted', style: { fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em' } }, done ? `Assembled · ${n} steps` : `Step ${A.step + 1} of ${n}`),
          h('div', { style: { fontWeight: 700 } }, done ? c.name : cur.title),
          h('div', { class: 'muted', style: { fontSize: '12px' } }, done ? 'Press build to watch it go together from the first part.' : tagFor(cur.text))),
        h('div', { class: 'row' }, prev, play, next)),
      bar);
  }

  update(t, dt) {
    const c = this.current; if (!c) return;
    this.explode += (this.explodeTarget - this.explode) * Math.min(1, dt * 6);
    const compact = this.explodeTarget < 0.3;
    if (compact !== this._compact) { this._compact = compact; this.app.setLabelsCompact(compact); }
    c._explode = this.explode;
    if (this.playing) {
      this.playT += dt;
      if (this.playT > 2.6) {
        this.playT = 0;
        const A = this.assembler;
        if (A.step < c.assembly.length) { A.setStep(A.step + 1); }
        if (A.step >= c.assembly.length) this.playing = false;
        this.renderAssembly();
      }
    }
    this.assembler.update(dt);
    this.assembler.apply(this.explode);
    c.update(t, dt, { working: this.working, explode: this.explode, live: this.app.live || null });
    if (this.helper) this.helper.update();
  }
}
