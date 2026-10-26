// Tiny DOM helpers for the panels. Every control gets a stable id so state survives a republish.
export function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'html') el.innerHTML = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) el.append(k.nodeType ? k : document.createTextNode(String(k)));
  return el;
}

export const $ = (s, r = document) => r.querySelector(s);

// A panel is a header (the first h2, with a collapse chevron) over a scrolling body. Collapsed state is remembered per
// panel and mode, so a panel the user folded stays folded when the mode re-renders it.
const collapsed = {};
export function setPanel(id, ...kids) {
  const el = document.getElementById(id);
  const list = kids.flat().filter(Boolean);
  el.hidden = list.length === 0;
  if (el.hidden) { el.replaceChildren(); return el; }
  const head = list[0] && list[0].tagName === 'H2' ? list.shift() : null;
  const body = h('div', { class: 'pb' }, ...list);
  if (head) {
    const key = id + ':' + (document.body.dataset.mode || '');
    const chev = h('button', { class: 'chev', type: 'button', 'aria-label': 'Collapse panel', title: 'Collapse' });
    chev.addEventListener('click', () => { collapsed[key] = el.classList.toggle('collapsed'); });
    el.classList.toggle('collapsed', !!collapsed[key]);
    el.replaceChildren(h('div', { class: 'ph' }, head, chev), body);
  } else {
    el.classList.remove('collapsed');
    el.replaceChildren(body);
  }
  return el;
}
export function hidePanel(id) { const el = document.getElementById(id); el.replaceChildren(); el.hidden = true; }

// A folding group of controls inside a panel. `open` is the default; what the user did last wins after that.
const secState = {};
export function section(id, title, open, ...kids) {
  const isOpen = secState[id] === undefined ? !!open : secState[id];
  const summary = h('summary', {}, title);
  const d = h('details', { class: 'sec', id: 'sec-' + id, open: isOpen || null }, summary, h('div', { class: 'secb' }, ...kids.flat().filter(Boolean)));
  // Remember only what the user did: a details element also fires "toggle" when it is created open.
  summary.addEventListener('click', () => setTimeout(() => { secState[id] = d.open; }, 0));
  return d;
}

// The mini-view dock: one small view at a time, chosen by tab, with a chevron that folds it to the tab row.
let dockTab = 0, dockCollapsed = false;
export function setDock(views) {
  const el = document.getElementById('dock');
  const minis = views.map((v) => h('div', { class: 'mini', style: { aspectRatio: String(v.aspect || 2) } }, v.el));
  const tabs = views.map((v, i) => h('button', { class: 'dtab', type: 'button', 'aria-pressed': 'false', title: v.title || null }, v.label));
  const show = (i) => { dockTab = i; tabs.forEach((t, k) => t.setAttribute('aria-pressed', String(k === i))); minis.forEach((m, k) => { m.hidden = k !== i; }); };
  tabs.forEach((t, i) => t.addEventListener('click', () => show(i)));
  const chev = h('button', { class: 'chev', type: 'button', 'aria-label': 'Collapse the mini views', title: 'Collapse' });
  chev.addEventListener('click', () => { dockCollapsed = el.classList.toggle('collapsed'); });
  el.classList.toggle('collapsed', dockCollapsed);
  el.replaceChildren(h('div', { class: 'dh' }, ...tabs, chev), h('div', { class: 'db' }, ...minis));
  show(Math.min(dockTab, views.length - 1));
  el.hidden = false;
  return el;
}
export function hideDock() { const el = document.getElementById('dock'); el.replaceChildren(); el.hidden = true; }

export function slider({ id, label, min, max, step = 1, value, fmt = (x) => x, onInput }) {
  const out = h('b', {}, fmt(value));
  const inp = h('input', { type: 'range', id, min, max, step, value });
  inp.addEventListener('input', () => { const v = parseFloat(inp.value); out.textContent = fmt(v); onInput && onInput(v); });
  const wrap = h('div', { class: 'ctl' }, h('label', { for: id }, h('span', {}, label), out), inp);
  wrap.set = (v) => { inp.value = v; out.textContent = fmt(v); };
  return wrap;
}

export function toggle({ id, label, checked, onChange, hint }) {
  const inp = h('input', { type: 'checkbox', id });
  inp.checked = !!checked;
  inp.addEventListener('change', () => onChange && onChange(inp.checked));
  const el = h('label', { class: 'toggle', for: id, title: hint || null }, h('span', {}, label), inp);
  el.set = (v) => { inp.checked = !!v; };
  return el;
}

export function chips({ options, value, onChange, id }) {
  const wrap = h('div', { class: 'chips', id, role: 'group' });
  const btns = options.map(([v, label]) => {
    const b = h('button', { class: 'chip', type: 'button', 'aria-pressed': String(v === value) }, label);
    b.addEventListener('click', () => { btns.forEach((x) => x.setAttribute('aria-pressed', 'false')); b.setAttribute('aria-pressed', 'true'); onChange && onChange(v); });
    b.dataset.v = v;
    return b;
  });
  wrap.append(...btns);
  wrap.set = (v) => btns.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === String(v))));
  return wrap;
}

export function kv(rows) {
  const el = h('div', { class: 'kv' });
  for (const r of rows) {
    if (!r) continue;
    const [k, v, cls] = r;
    el.append(h('span', {}, k), h('span', { class: cls || null }, v));
  }
  return el;
}

// A kv block whose values are refreshed by a function returning [[k, v, cls], ...].
export function liveKv(fn) {
  const el = h('div', { class: 'kv' });
  el.refresh = () => {
    const rows = fn().filter(Boolean);
    if (el.children.length !== rows.length * 2) {
      el.replaceChildren(...rows.flatMap(([k, v, c]) => [h('span', {}, k), h('span', { class: c || null }, v)]));
    } else {
      rows.forEach(([k, v, c], i) => {
        const a = el.children[i * 2], b = el.children[i * 2 + 1];
        if (a.textContent !== k) a.textContent = k;
        if (b.textContent !== String(v)) b.textContent = v;
        const cls = c || '';
        if (b.className !== cls) b.className = cls;
      });
    }
  };
  el.refresh();
  return el;
}

export function btn(label, onClick, { primary = false, id, pressed } = {}) {
  const b = h('button', { class: 'btn' + (primary ? ' primary' : ''), type: 'button', id, 'aria-pressed': pressed === undefined ? null : String(pressed) }, label);
  b.addEventListener('click', onClick);
  return b;
}

// Keyboard hints: keys(['Space', 'clutter mode'], ['P', 'pause']) -> a muted line of <kbd> pairs.
export function keys(...pairs) {
  return h('p', { class: 'keys' }, pairs.flatMap(([k, what], i) => [i ? ' · ' : null, h('kbd', {}, k), ' ' + what]));
}

let toastTimer = 0;
export function toast(msg, ms = 2200) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.style.opacity = 1;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.style.opacity = 0; }, ms);
}

export function tagFor(text) {
  // Render the plan's ASSUMED / UNVERIFIED / sim markers as tags.
  const frag = document.createDocumentFragment();
  const parts = String(text).split(/(\(ASSUMED\)|\(UNVERIFIED\)|\(sim\)|ASSUMED|UNVERIFIED)/);
  for (const p of parts) {
    if (!p) continue;
    if (/ASSUMED/.test(p)) frag.append(h('span', { class: 'tag assumed' }, 'assumed'));
    else if (/UNVERIFIED/.test(p)) frag.append(h('span', { class: 'tag unverified' }, 'unverified'));
    else if (p === '(sim)') frag.append(h('span', { class: 'tag sim' }, 'sim'));
    else frag.append(p);
  }
  return frag;
}
