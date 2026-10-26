// The Cycles reference: Blender's path tracer rendering the same optics (docs/arhud-blender/optics_check.py), set
// beside the analytic trace in geom.js. The Blender scene is built from layout.json, which dump_layout.mjs writes
// from geom.js, so the two see the same surfaces: the laminated windshield as a 4.96 mm glass slab, the concave mirror
// as a true sphere or toroid, the fold as a plane, the 60 x 30 mm crop as an emitter showing a dot grid. Everything
// compared here is geometric (positions, distances, what reaches the eye); Cycles' Fresnel is unpolarised, so its
// brightness ratios are reported but not compared with the plan's s-polarised figures.
import * as THREE from 'three';
import { P } from './params.js';
import * as GM from './geom.js';
import { R } from './params.js';
import { h, kv, section } from './ui.js';
import { DEG } from './util.js';
import { ASSET_BASE, fetchJson } from './assets.js';
import { tracedWindow } from './hud.js';
import { foldFrame, housingLayout } from './components/optics.js';

let resultsP = null, sunP = null;
export function loadSunFocus() {
  if (!sunP) sunP = fetchJson('cycles/sun_focus.json').catch((e) => { console.warn('sun focus results not available:', e.message); return null; });
  return sunP;
}
export function loadCyclesResults() {
  if (!resultsP) resultsP = fetchJson('cycles/results.json').catch((e) => { console.warn('Cycles results not available:', e.message); return null; });
  return resultsP;
}

// Field angles (ax right, ay up, radians, the pinhole convention: tan-linear about LOOK) whose ray from eye point e
// lands on the panel at (panelZ, panelX) metres from the crop centre. Newton on the trace, as tracedWindow() does.
export function fieldForPanelPoint(e, pz, px, mode = GM.MIRROR.mode) {
  let ax = pz / 0.06 * GM.FOV_W * 0.8, ay = -px / 0.03 * GM.FOV_H * 0.8;
  const f = (a, b) => { const r = GM.traceFromEye(e, GM.fieldDir(a, b), mode); return r ? [r.panelZ, r.panelX, r] : [NaN, NaN, null]; };
  let r = null;
  for (let it = 0; it < 25; it++) {
    const [z0, x0, r0] = f(ax, ay);
    r = r0;
    if (!r0) return null;
    const hh = 1e-4;
    const [z1, x1] = f(ax + hh, ay), [z2, x2] = f(ax, ay + hh);
    const J = [[(z1 - z0) / hh, (z2 - z0) / hh], [(x1 - x0) / hh, (x2 - x0) / hh]];
    const det = J[0][0] * J[1][1] - J[0][1] * J[1][0];
    if (!isFinite(det) || Math.abs(det) < 1e-12) return null;
    const ez = pz - z0, ex = px - x0;
    const dax = (J[1][1] * ez - J[0][1] * ex) / det, day = (-J[1][0] * ez + J[0][0] * ex) / det;
    ax += dax; ay += day;
    if (Math.abs(dax) < 1e-9 && Math.abs(day) < 1e-9) break;
  }
  const [, , rf] = f(ax, ay);
  return rf ? { ax, ay, trace: rf } : null;
}

import { reaches } from './clip.js';

// The analytic view of the Cycles dot pattern from an eye point: angles and reach for every dot.
export function analyticDots(results, mode, eyeOffset = new THREE.Vector3()) {
  const e = GM.EYE.clone().add(eyeOffset);
  const ff = foldFrame(mode);
  let hl = null;
  try { hl = housingLayout(mode); } catch (err) { hl = null; }
  const P = results.pattern;
  return P.dotV_mm.map((v) => P.dotU_mm.map((u) => {
    const s = fieldForPanelPoint(e, u / 1000, -v / 1000, mode);
    if (!s) return null;
    const rc = reaches(s.trace, ff, hl);
    return { ax: s.ax, ay: s.ay, lid: rc.lid, mirror: rc.mirror, fold: rc.fold, all: rc.lid && rc.mirror && rc.fold };
  }));
}

// Local Coddington at the mirror hit point of each dot's chief ray: the image distance from the eye for the sagittal
// and tangential pencils, field by field, with the surface's local curvatures, incidence and object distance.
export function fieldDistances(results, mode = GM.MIRROR.mode, eyeOffset = new THREE.Vector3()) {
  const e = GM.EYE.clone().add(eyeOffset);
  const P = results.pattern;
  return P.dotV_mm.map((v) => P.dotU_mm.map((u) => {
    const s = fieldForPanelPoint(e, u / 1000, -v / 1000, mode);
    if (!s) return null;
    const [eye, glass, hit, fold, panel] = s.trace.pts;
    const din = hit.clone().sub(glass).normalize();
    const cosI = Math.max(1e-6, -din.dot(s.trace.mirror.n));
    const uLocal = hit.distanceTo(fold) + fold.distanceTo(panel);
    const eyeToMirror = eye.distanceTo(glass) + glass.distanceTo(hit);
    const [cu, cv] = GM.mirrorCurv(s.trace.mirror.u, s.trace.mirror.v, mode);     // local curvatures at the hit
    const Rs = 1 / cu, Rt = 1 / cv;
    const ft = (Rt / 2) * cosI, fs = (Rs / 2) / cosI;
    const vOf = (f) => 1 / (1 / f - 1 / uLocal);
    return { sagittal: eyeToMirror - vOf(fs), tangential: eyeToMirror - vOf(ft), incDeg: Math.acos(cosI) / DEG, uLocal };
  }));
}

const arcmin = (rad) => rad / DEG * 60;
const fmtD = (d) => (d == null ? '–' : `${d.D.toFixed(2)} m`);
const pct = (a, b) => `${((a / b - 1) * 100).toFixed(1)}%`;

function img(file, caption) {
  return h('figure', { style: { margin: '8px 0 4px' } },
    h('img', { src: ASSET_BASE + 'cycles/' + file, alt: caption, loading: 'lazy', style: { width: '100%', display: 'block', borderRadius: '6px', border: '1px solid var(--line-soft)' } }),
    h('figcaption', { class: 'muted', style: { fontSize: '11.5px', marginTop: '4px' } }, caption));
}

// The folding section for the Vehicle mode's optics panel.
export function cyclesSection(results, mode, sun = null) {
  if (!results) {
    return section('veh-cycles', 'Cycles reference', false,
      h('p', { class: 'hint' }, 'No Blender renders found. Run docs/arhud-blender/optics_check.py to produce assets/cycles/.'), sunFocusBlock(sun));
  }
  // the simulator's 'freeformCurved' figure is the Cycles run of the freeform with the curved glass
  const keyFor = (m) => (m === 'freeformCurved' ? Object.keys(results.modes).find((k) => k.startsWith('freeform_glass')) : m);
  const key = keyFor(mode);
  const M = (key && results.modes[key]) || results.modes.toroid;
  const modeName = key && results.modes[key] ? mode : 'toroid';
  const fileBase = modeName === 'freeformCurved' ? 'freeform_curved' : modeName;
  const im = GM.mirrorImages(modeName);
  // the freeform was fitted for a flat image at its target distance, so that is the trace's figure for it
  const target = (modeName === 'freeform' || modeName === 'freeformCurved') && M.imageDistance ? M.imageDistance.expectedSagittal : null;
  const Dsag = target || im.eyeToMirror - im.vs, Dtan = target || im.eyeToMirror - im.vt;
  const tr = tracedWindow();
  const rows = [];
  const near = (a, b, tol) => (a != null && Math.abs(a / b - 1) <= tol ? 'good' : 'warn');
  if (M.imageDistance) {
    const s = M.imageDistance.sagittal, t = M.imageDistance.tangential;
    rows.push(['Image from the eye, lateral parallax (sagittal)', `Cycles ${fmtD(s)} · trace ${Dsag.toFixed(2)} m${s ? ` (${pct(s.D, Dsag)})` : ''}`, s ? near(s.D, Dsag, 0.05) : 'warn']);
    rows.push(['Image from the eye, vertical parallax (tangential)', `Cycles ${fmtD(t)} · trace ${Dtan.toFixed(2)} m${t ? ` (${pct(t.D, Dtan)})` : ''}`, t ? near(t.D, Dtan, Dtan > 20 ? 0.3 : 0.05) : 'warn']);
  }
  // the image surface across the window: Cycles' per-dot parallax against local Coddington on the trace
  let fieldRows = null;
  if (M.distanceMap && M.distanceMap.sagittal) {
    const fd = fieldDistances(results, modeName);
    const ic = Math.floor(results.pattern.dotU_mm.length / 2);
    const pick = (grid, j, k) => { const r = grid[j]; return r && r[ic] != null ? (k ? r[ic][k] : r[ic]) : null; };
    const f1 = (x) => (x == null ? '–' : x.toFixed(1));
    const labels = ['top row', 'centre', 'bottom row'];
    const js = [0, Math.floor(fd.length / 2), fd.length - 1];
    fieldRows = js.map((j, k) => {
      const cs = pick(M.distanceMap.sagittal, j), ct = pick(M.distanceMap.tangential, j);
      const ts = pick(fd, j, 'sagittal'), tt = pick(fd, j, 'tangential');
      return [`Image distance, ${labels[k]} of the window`, `Cycles ${f1(cs)} / ${f1(ct)} m · trace ${f1(ts)} / ${f1(tt)} m (sagittal / tangential)`];
    });
  }
  if (results.simCheck && modeName === 'toroid') {
    const c = results.simCheck;
    rows.push(['Driver view, window as drawn', `${c.traced.drawnW.toFixed(2)}° × ${c.traced.drawnH.toFixed(2)}° rasterised (headless, ${c.pxPerDeg} px/°), trace ${c.traced.traceW.toFixed(2)}° × ${c.traced.traceH.toFixed(2)}°; the plan's spec window the view used to default to is ${c.spec.drawnW.toFixed(1)}° × ${c.spec.drawnH.toFixed(1)}°`, Math.abs(c.traced.drawnW - c.traced.traceW) < 0.02 && Math.abs(c.traced.drawnH - c.traced.traceH) < 0.02 ? 'good' : 'warn']);
  }
  if (M.field) {
    rows.push(['Window width, top edge', `Cycles ${M.field.topW.toFixed(2)}° · trace ${tr.topW.toFixed(2)}°`, near(M.field.topW, tr.topW, 0.03)]);
    rows.push(['Window width, bottom edge', `Cycles ${M.field.botW.toFixed(2)}° · trace ${tr.botW.toFixed(2)}°`, near(M.field.botW, tr.botW, 0.03)]);
    rows.push(['Window height', `Cycles ${M.field.height.toFixed(2)}° · trace ${tr.fovH.toFixed(2)}°`, near(M.field.height, tr.fovH, 0.05)]);
  }
  // dot-by-dot registration against the trace
  let reg = null;
  if (M.dots) {
    const an = analyticDots(results, modeName);
    const errs = [];
    M.dots.forEach((row, j) => row.forEach((d, i) => {
      const a = an[j] && an[j][i];
      if (!d || !a) return;
      errs.push(Math.hypot(d[0] * DEG - a.ax, d[1] * DEG - a.ay));
    }));
    if (errs.length) {
      const rms = Math.sqrt(errs.reduce((p, q) => p + q * q, 0) / errs.length);
      reg = { rms: arcmin(rms), max: arcmin(Math.max(...errs)), n: errs.length };
      rows.push(['Dot positions, Cycles vs trace', `rms ${reg.rms.toFixed(2)}′, max ${reg.max.toFixed(2)}′ over ${reg.n} dots (1 px ≈ ${(R.PPD2 ? 60 / R.PPD2 : 0.5).toFixed(2)}′)`, reg.max < 2 ? 'good' : 'warn']);
    }
  }
  if (M.ghost && !M.ghost.error) {
    const g = M.ghost;
    const expAtD = GM.VID && M.imageDistance && M.imageDistance.sagittal ? (R.GHOST_PERP / 1000) / M.imageDistance.sagittal.D / DEG * 60 : null;
    rows.push(['Ghost offset', `Cycles ${g.sepArcmin.toFixed(2)}′ ${g.dyArcmin > 0 ? 'above' : 'below'} · calc ${R.GHOST_75.toFixed(2)}′ at 7.5 m${expAtD ? `, ${expAtD.toFixed(2)}′ at the measured ${M.imageDistance.sagittal.D.toFixed(1)} m` : ''}`, expAtD ? near(g.sepArcmin, expAtD, 0.1) : 'warn']);
    rows.push(['Ghost brightness', `Cycles ${(g.brightnessRatioUnpolarised * 100).toFixed(0)}% unpolarised · plan ${((1 - R.RS65) ** 2 * 100).toFixed(0)}% s-polarised (not comparable)`]);
    // what the Driver view draws: a second copy of the image GHOST_PERP above it at the traced image plane
    try {
      const tw = tracedWindow();
      const drawn = (R.GHOST_PERP / 1000) / tw.dist / DEG * 60;
      rows.push(['Ghost as the Driver view draws it', `${drawn.toFixed(2)}′ above (${R.GHOST_PERP.toFixed(2)} mm at the traced ${tw.dist.toFixed(2)} m) · Cycles ${g.sepArcmin.toFixed(2)}′`, Math.abs(drawn - g.sepArcmin) < 0.1 ? 'good' : 'warn']);
    } catch (e) { /* no trace */ }
  }
  // a curved windshield (Cycles only: the trace assumes flat glass)
  const curvedKey = modeName === 'freeformCurved' ? null : Object.keys(results.modes).find((k) => k.startsWith(modeName + '_glass'));
  const curvedRows = [];
  if (curvedKey) {
    const Cm = results.modes[curvedKey];
    const g = Cm.glass || {};
    const sd = Cm.imageDistance && Cm.imageDistance.sagittal, td = Cm.imageDistance && Cm.imageDistance.tangential;
    const fmt = (d) => (d == null ? '–' : d.D < 0 ? `real image ${(-d.D).toFixed(1)} m ahead` : `${d.D.toFixed(1)} m`);
    curvedRows.push([`Image from the eye with the glass curved (${g.Rh} m lateral, ${g.Rv} m vertical radii)`, `${fmt(sd)} sagittal · ${fmt(td)} tangential · flat glass ${Dsag.toFixed(1)} m`, 'bad']);
    if (Cm.field) curvedRows.push(['Window with the curved glass', `${Cm.field.topW.toFixed(1)}° / ${Cm.field.botW.toFixed(1)}° wide, ${Cm.field.height.toFixed(1)}° tall`]);
    if (Cm.ghost && !Cm.ghost.error) curvedRows.push(['Ghost with the curved glass', `${Cm.ghost.sepArcmin.toFixed(2)}′`]);
    // the design refitted for that glass (freeform_mirror.py glassRh= glassRv=), if Cycles has checked it
    const refitKey = Object.keys(results.modes).find((k) => k.startsWith('freeform_glass'));
    const Rf = refitKey && results.modes[refitKey];
    if (Rf && Rf.imageDistance && Rf.imageDistance.sagittal) {
      const f = Rf.freeformFit || {};
      const all = (k) => Rf.distanceMap && Rf.distanceMap[k] ? Rf.distanceMap[k].flat().filter((x) => x != null) : [];
      const rng = (k) => { const a = all(k); return a.length ? `${Math.min(...a).toFixed(1)}–${Math.max(...a).toFixed(1)} m` : '–'; };
      curvedRows.push(['Freeform refitted for that glass: image across the window', `${rng('sagittal')} sagittal · ${rng('tangential')} tangential`, 'good']);
      if (f.vertexRadii) curvedRows.push(['Refitted mirror and panel', `vertex radii ${(f.vertexRadii.Rs * 1000).toFixed(0)} / ${(f.vertexRadii.Rt * 1000).toFixed(0)} mm, panel tilt ${(f.panelTiltDeg || 0).toFixed(1)}°, shift ${(f.panelShiftMm || 0).toFixed(0)} mm`]);
      if (Rf.field) curvedRows.push(['Window with the refit', `${Rf.field.topW.toFixed(1)}° / ${Rf.field.botW.toFixed(1)}° wide, ${Rf.field.height.toFixed(1)}° tall`]);
    }
  }
  // eye box
  const eyebox = [];
  if (M.eyebox) {
    for (const p of M.eyebox) {
      const an = analyticDots(results, modeName, new THREE.Vector3(0, p.dy_mm / 1000, p.dz_mm / 1000));
      const flat = an.flat().filter(Boolean);
      const mirrorOnly = flat.filter((d) => d.mirror).length, all = flat.filter((d) => d.all).length;
      const lidCut = flat.filter((d) => d.mirror && d.fold && !d.lid).length;
      eyebox.push([`Eye ${p.dz_mm >= 0 ? '+' : ''}${p.dz_mm.toFixed(0)} mm right, ${p.dy_mm >= 0 ? '+' : ''}${p.dy_mm.toFixed(0)} mm up`, `Cycles ${p.visible}/${p.of} · trace ${all}/${p.of} (mirror alone ${mirrorOnly}${lidCut ? `, lid aperture cuts ${lidCut}` : ''})`, Math.abs(p.visible - all) <= 2 ? 'good' : 'warn']);
    }
  }
  // luminance: a uniform white panel, the mean radiance over the window's interior as a fraction of the panel's
  const lumRows = [];
  const LU = results.luminance;
  if (LU && LU.modes && LU.modes[modeName]) {
    const E = LU.modes[modeName], T = LU.modes.toroid;
    const labels = { 0: 'Lambertian cell (as the plan assumes)', 1: 'IPS-like cell (cos θ falloff)', 2: 'TN-like cell (cos² θ falloff)' };
    if (E.chiefOffNormalDeg > 0.5) lumRows.push(['Chief ray off the cell\'s normal', `${E.chiefOffNormalDeg.toFixed(1)}° (the panel tilted ${E.panelTiltDeg.toFixed(1)}°)`, 'warn']);
    for (const k of Object.keys(E.byK)) {
      const r = E.byK[k], t = T && T.byK[k];
      const nom = r.nominal ? r.nominal.mean : 0;
      const rel = t && t.nominal ? nom / t.nominal.mean : 1;
      const vs = modeName === 'toroid' ? '' : rel >= 0.985 ? ' · same as the toroid' : ` · ${((1 - rel) * 100).toFixed(0)}% below the toroid`;
      lumRows.push([labels[k] || `cos^${k} falloff`, `${(nom * 100).toFixed(1)}% of the panel at the eye, ${(r.eyeboxMin * 100).toFixed(1)}–${(r.eyeboxMax * 100).toFixed(1)}% over the eye box${vs}`, rel > 0.9 ? 'good' : rel > 0.7 ? 'warn' : 'bad']);
    }
    // the windshield's share of that, against Fresnel and the plan's figure (Cycles is unpolarised)
    const fres = (deg) => { const n = P.raw.N_GLASS, t = deg * Math.PI / 180, st = Math.sin(t) / n, ct = Math.sqrt(1 - st * st), c = Math.cos(t); const Rs = ((c - n * ct) / (c + n * ct)) ** 2, Rp = ((n * c - ct) / (n * c + ct)) ** 2; return { Rs, Rp, Ru: (Rs + Rp) / 2 }; };
    const two = (R) => R + (1 - R) ** 2 * R;
    const k0 = T && T.byK[0] && T.byK[0].nominal ? T.byK[0].nominal.mean : null;
    if (k0 != null && LU.glassIncidenceDeg) {
      const f = fres(LU.glassIncidenceDeg), fp = fres(LU.planThetaDeg);
      lumRows.push(['Windshield, both surfaces, unpolarised', `Cycles ${(k0 * 100).toFixed(1)}% · Fresnel at the chief ray\'s ${LU.glassIncidenceDeg.toFixed(1)}°: ${(two(f.Ru) * 100).toFixed(1)}% (mirrors taken as perfect)`, Math.abs(k0 - two(f.Ru)) < 0.01 ? 'good' : 'warn']);
      lumRows.push(['The plan\'s path figure', `R_WS ${P.raw.R_WS} one surface, ${P.raw.R_WS_TWO} both: the s-polarised values at ${LU.planThetaDeg}° (${(fp.Rs * 100).toFixed(1)}% / ${(two(fp.Rs) * 100).toFixed(1)}%). The plan designs for s-polarised panel light (its §7.2: measure the panel\'s axis, often 45°, and orient it s to the windshield or add a half-wave retarder film), so the figure holds once the axis is set; left unpolarised, or at 45°, the path is ${(f.Ru * 100).toFixed(1)}% / ${(two(f.Ru) * 100).toFixed(1)}%, ${(f.Ru / P.raw.R_WS * 100).toFixed(0)}% of the plan\'s. The plan also notes polarised sunglasses block an s-polarised image (its demo rule: none worn).`, 'warn']);
      lumRows.push(['Incidence: the plan against its own geometry', `The plan\'s rake ${P.raw.RAKE}° and look-down ${P.raw.LOOKDOWN}° give ${LU.glassIncidenceDeg.toFixed(1)}° (its §7.2 prints that check), and the simulator\'s glass sits there; its reflectance and ghost figures use ${LU.planThetaDeg}°. At ${LU.glassIncidenceDeg.toFixed(1)}° the s-polarised path is ${(f.Rs * 100).toFixed(1)}% / ${(two(f.Rs) * 100).toFixed(1)}%, ${((f.Rs / fp.Rs - 1) * 100).toFixed(0)}% more than the plan counts.`, 'warn']);
    }
  }
  const S = results.settings;
  return section('veh-cycles', 'Cycles reference', false,
    h('p', { class: 'hint' }, `Blender ${results.blender} path-traced the installed optics from layout.json: the laminate as 4.96 mm of n = 1.52 glass, the ${modeName === 'sphere' ? 'spherical' : modeName === 'freeform' ? 'freeform (Blender-fitted polynomial)' : modeName === 'freeformCurved' ? 'freeform refitted for the curved windshield (4 m lateral, 8 m vertical radii, which the glass here has)' : 'toroidal'} mirror as a true ${S.surface === 'parabolic' ? 'paraboloid' : 'surface'}, the fold, and the crop emitting an 11 × 5 dot grid. ${S.samples} samples at ${S.res[0]} × ${S.res[1]}, pinhole eye.`),
    results.beauty ? h('div', {},
      img(results.beauty.file, `The driver's view, path-traced: the frame hudd drew, shown through the fold, the toroid and the laminate into the simulator's own car, with the ghost and the window's keystone as they come. Sun ${results.beauty.sunElevDeg}° up, ${results.beauty.samples} samples.`),
      img(results.beauty.hudOff, 'The same view with the panel dark.'),
      results.veil ? img(results.veil.file, `The daytime black level: the panel dark but real (diffuse ${(results.veil.panel.diffuse * 100).toFixed(0)}%, specular ${(results.veil.panel.specular * 100).toFixed(0)}%, assumed), lit by sky light through the aperture and imaged to the eye. The veil over the window is ${(results.veil.veilOverBehind * 100).toFixed(1)}% of the scene behind it, ${(results.veil.veilOverSky * 100).toFixed(2)}% of the sky: ${results.veil.veilOverBehind < 0.02 ? 'below the eye\'s threshold for a uniform patch, so the window does not show as a slab by day' : results.veil.veilOverBehind < 0.1 ? 'a faint slab a driver can notice against the road' : 'a visible slab over the road'}. Direct sun into the housing is a path no path tracer samples; the sun bundle covers it.`) : null,
      results.beautyNight ? img(results.beautyNight.file, `The same in deep twilight (sun 14° below the horizon, headlights on), the panel at a night gain of ${results.beautyNight.hudGain} against ${results.beauty.hudGain} by day: the window reads as a bright slab against the dim road, the plan's night-brightness defect made visible. An earlier version of this picture showed a second window above the image; that was the Cycles panel emitting from both faces, with the mirror seeing its back directly, not a stray path. With the cell one-sided, as a real LCD is, there is one window, and the stray survey below finds nothing else.`) : null) : null,
    kv(rows),
    fieldRows ? h('div', {}, h('h3', {}, 'Across the window'), kv(fieldRows), h('p', { class: 'muted', style: { fontSize: '11.5px', margin: '6px 0 0' } }, 'The panel sits 14 mm inside the focus, so the small change of incidence across the window moves the image a long way: the image surface is far from a flat plane at one distance.')) : null,
    img(`${fileBase}_eye.png`, `What Cycles sees from the nominal eye (${S.fovWideDeg}° wide): the dot grid with the keystone of the tilted glass. The bigger dot is the crop's top-left corner.`),
    img(`${fileBase}_parallax.png`, `Stereo parallax, eye ${(S.lateralBaseline * 1000).toFixed(0)} mm left (red) and right (cyan): the shift gives the image distance dot by dot.`),
    modeName === 'toroid' ? img('ghost.png', `The ghost: one ${(results.pattern.ghostDotR_mm * 2).toFixed(2)} mm dot seen through the laminate, main image and the outer surface's copy.`) : null,
    curvedRows.length ? h('div', {}, h('h3', {}, 'Curved windshield'), kv(curvedRows), h('p', { class: 'muted', style: { fontSize: '11.5px', margin: '6px 0 0' } }, 'The plan and the trace take the glass as flat. A real windshield wraps toward the pillars and the roof, so its inner surface is a weak concave mirror; with the panel 14 mm inside the focus that extra power dominates. The mirror has to be designed against the measured glass: scan it (Scanned car), fit its radii, rerun freeform_mirror.py and optics_check.py with glassRh and glassRv; the refit rows show that this recovers a flat image.')) : null,
    eyebox.length ? h('div', {}, h('h3', {}, 'Eye box'), kv(eyebox), img('eyebox.png', 'The nine eye-box points (left to right: 65 mm left, centre, 65 mm right; top to bottom: 35 mm up, centre, 35 mm down): what reaches the eye through the lid aperture, the 300 × 200 mm mirror and the fold.')) : null,
    results.regCheck && modeName === 'toroid' ? h('div', {}, h('h3', {}, 'Registration through the optics'),
      kv(results.regCheck.cases.map((c) => [c.label, `mean ${c.meanArcmin.toFixed(1)}′, max ${c.maxArcmin.toFixed(1)}′ over ${c.marks} marks`, c.maxArcmin < 5 ? 'good' : c.maxArcmin < 12 ? 'warn' : 'bad'])),
      h('p', { class: 'muted', style: { fontSize: '11.5px', margin: '6px 0 0' } }, `End to end: hudd draws crosses at four road points (16 and 24 m ahead, 1 m left and right) for the eye it tracks, the frame is pre-distorted to the panel by the trace, and Cycles renders it through the real optics from that eye over discs at the same points; cross minus disc is the error. A plane at one distance, as the plan has it, leaves up to ${Math.max(...results.regCheck.cases.filter((c) => c.key === 'plane').map((c) => c.maxArcmin)).toFixed(0)}′ at these marks with the eye 75 mm off centre, and more at the top of the window where the lead marker sits; the image-surface map fixes one side only; the optical model from the tracked eye registers like the nominal eye, for a vertical offset too, and for the freeform figure, whose flat image does not make the plane projection work (its tilted panel swims with the eye: 31′ at 75 mm). On the curved windshield with the mirror refitted for it, the plane projection is off by 1.5° at 75 mm while the optical model holds 4′. hudd needs the optical model, or a calibrated eye-position-to-panel map, on the Jetson, whatever the figure and the glass. The trace must also use the true mirror surface: as a paraboloid it was ${results.regCheck.traceSurfaces.paraboloidDotRms.toroid}′ rms and ${results.regCheck.traceSurfaces.paraboloidDotMax.toroid}′ max off Cycles at the nominal eye, ${results.regCheck.traceSurfaces.trueDotRms.toroid}′ and ${results.regCheck.traceSurfaces.trueDotMax.toroid}′ as the true toroid.${results.lutCheck ? ` The map hudd needs exists: a table of ${results.lutCheck.grid.eye.join(' × ')} eye positions by ${results.lutCheck.grid.field.join(' × ')} field directions, built from the trace, is within ${results.lutCheck.atTheEyeArcmin.toroid.max}′ of the exact projection on the toroid and ${results.lutCheck.atTheEyeArcmin.freeform.max}′ on the freeform (assets/hudd_lut_*.json, about ${(results.lutCheck.fileKB / 1024).toFixed(1)} MB each), and the Driver view's lookup projection runs at full frame rate with it.` : ''}`)) : null,
    results.eyeboxExtent && modeName === 'toroid' ? h('div', {}, h('h3', {}, 'Eye box, as measured'),
      kv([
        ['Plan', `±${results.eyeboxExtent.planHalf_mm[0].toFixed(0)} mm lateral, ±${results.eyeboxExtent.planHalf_mm[1].toFixed(0)} mm vertical`],
        ['Lateral', results.eyeboxExtent.lateral.map((q) => `${q.mm.toFixed(0)} mm: ${(q.fraction * 100).toFixed(0)}%`).join(' · '), results.eyeboxExtent.lateral.find((q) => q.mm === 80 && q.fraction > 0.97) ? 'good' : 'warn'],
        ['Up', results.eyeboxExtent.vertical.filter((q) => q.mm > 0).map((q) => `${q.mm.toFixed(0)} mm: ${(q.fraction * 100).toFixed(0)}%`).join(' · ')],
        ['Down', results.eyeboxExtent.vertical.filter((q) => q.mm < 0).map((q) => `${q.mm.toFixed(0)} mm: ${(q.fraction * 100).toFixed(0)}%`).join(' · ')],
        ...(results.eyeboxExtent_freeform ? [['Freeform figure, vertical', results.eyeboxExtent_freeform.vertical.map((q) => `${q.mm > 0 ? '+' : ''}${q.mm.toFixed(0)}: ${(q.fraction * 100).toFixed(0)}%`).join(' · ')]] : []),
        ...(results.eyeboxExtent.simVignette ? [['Driver view\'s vignette model', `lateral ${Object.entries(results.eyeboxExtent.simVignette.lateral).map(([k, v]) => `${k}: ${v}%`).join(' · ')}; vertical ${Object.entries(results.eyeboxExtent.simVignette.vertical).map(([k, v]) => `${k}: ${v}%`).join(' · ')}`]] : []),
      ]),
      h('p', { class: 'muted', style: { fontSize: '11.5px', margin: '6px 0 0' } }, 'The lit window\'s area from each eye position, relative to the nominal eye, with a uniform white panel. The window stays whole to about ±80 mm lateral and clips beyond (91% at 95 mm, 75% at 125 mm); vertically the area also changes with perspective (a lower eye sees a larger window), and clipping takes hold past about +55 and −50 mm. So the real eye box is roughly ±85 × ±50 mm against the plan\'s ±65 × ±35: 20 mm of lateral margin and 15 mm of vertical, with no dimming before the clip. The freeform figure\'s tilted panel is more tolerant vertically. What clips the window from a low eye is the housing itself: its lid rises to 1.10 m at the rear, and the line from the eye to the window\'s bottom passes that edge by 43 mm at the nominal eye, 11 mm at the plan\'s lowest eye (35 mm down) and 1 mm at 45 mm down. The lower limit of the eye box is the housing\'s rear height, not the optics; 20 mm off that edge would buy 20 mm of eye box. The Driver view\'s vignette, which drives its Window visible readout and the window\'s fade, now tests the housing\'s top, the lid aperture, the fold glass and the lit crop as well as the mirror, and matches Cycles in every direction within the grid\'s resolution.')) : null,
    results.stray ? h('div', {}, h('h3', {}, 'Stray light'), kv([
      [`Lit regions besides the image, ${results.stray.fovDeg}° view`, results.stray.strays.length ? results.stray.strays.map((t) => `${(t.ratio * 100).toFixed(1)}% of the image at ${t.offsetDeg[0].toFixed(1)}° / ${t.offsetDeg[1].toFixed(1)}°`).join(', ') : 'none above 0.1% of the image from the optics alone (white panel, one-sided cell, mirror and fold each hidden in turn to attribute any region)', results.stray.strays.length ? 'warn' : 'good'],
      ...(results.strayCover ? [[`With the dust cover (${results.strayCover.coverT_mm} mm uncoated glass across the lid aperture)`, `${results.strayCover.strays.length ? results.strayCover.strays.map((t) => `${(t.ratio * 100).toFixed(1)}% of the image at ${t.offsetDeg[0].toFixed(1)}° / ${t.offsetDeg[1].toFixed(1)}°`).join(', ') : 'still none above 0.1%: the cover\'s back-reflections reach no image path'}; the image itself at ${(results.strayCover.main.meanRadiance / results.stray.main.meanRadiance * 100).toFixed(0)}% of its bare value, the cover\'s two surfaces at the beam\'s incidence, which an anti-reflection coat would recover`, results.strayCover.strays.length ? 'warn' : 'good']] : []),
    ])) : null,
    lumRows.length ? h('div', {}, h('h3', {}, 'Luminance at the eye'), kv(lumRows), h('p', { class: 'muted', style: { fontSize: '11.5px', margin: '6px 0 0' } }, `A uniform white panel, ${LU.samples} samples: the mean radiance over the window's interior. Reflection leaves radiance unchanged except for the reflectance, so this is the luminance at the eye as a fraction of the panel's, independent of magnification or blur. The tilted panel of the freeform figures sends the chief ray to the mirror off the cell's normal, where a real LCD is dimmer: that is the price of the flat image, and the backlight budget for that figure must cover it.`)) : null,
    sunFocusBlock(sun),
    h('p', { class: 'muted', style: { fontSize: '11.5px', marginTop: '8px' } }, 'Rerun: node dump_layout.mjs, then Blender -b -P optics_check.py in docs/arhud-blender. Cycles finds the image by sampling the real reflections; the trace is paraxial at the mirror vertex, so a few percent of difference across the field is the mirror\'s own aberration, not an error.'),
  );
}

// The sun-focus block (docs/arhud-blender/sun_focus.py): a numeric ray bundle through the real aperture and mirror.
export function sunFocusBlock(S) {
  if (!S) return null;
  const n = S.nominal, p = S.plan, pt = S.patch;
  const rows = [
    ['Sun power the mirror collects', `trace ${n.collectedByMirrorW.toFixed(1)} W · plan ${p.collectedW} W (full mirror area)`],
    ['Power on the panel after cold mirror, IR cut, polariser', `trace ${n.powerW.toFixed(2)} W · plan ${p.afterFiltersW} W`],
    ['Spot on the panel (radius holding 50% / 90%)', `${n.r50_mm.toFixed(1)} / ${n.r90_mm.toFixed(1)} mm · plan r90 ${p.r90_mm.toFixed(1)} mm`],
    ['Peak irradiance (1 mm patch)', `${n.peak_kW_m2.toFixed(0)} kW/m² · TI production peak ${p.tiImagerPeak_kW_m2} kW/m²`, n.peak_kW_m2 > p.tiImagerPeak_kW_m2 ? 'bad' : 'good'],
    ['Spot centre on the crop (fore-aft, lateral)', `${n.centroid_mm[0].toFixed(1)}, ${n.centroid_mm[1].toFixed(1)} mm`],
  ];
  if (pt && pt.sizeDeg) rows.push(['Sun directions that light the crop', `${pt.sizeDeg[0].toFixed(0)}° wide × ${pt.sizeDeg[1].toFixed(0)}° tall, elevation ${pt.cropHot.elevation[0].toFixed(0)}–${pt.cropHot.elevation[1].toFixed(0)}° · plan patch ${p.patchDeg[0].toFixed(0)}° × ${p.patchDeg[1].toFixed(0)}°`]);
  if (pt && pt.cellSizeDeg) rows.push(['Sun directions that light the cell at all', `${pt.cellSizeDeg[0].toFixed(0)}° × ${pt.cellSizeDeg[1].toFixed(0)}°, elevation ${pt.cellHot.elevation[0].toFixed(0)}–${pt.cellHot.elevation[1].toFixed(0)}°`, pt.cellSizeDeg[0] > p.patchDeg[0] || pt.cellSizeDeg[1] > p.patchDeg[1] ? 'warn' : 'good']);
  return h('div', {},
    h('h3', {}, 'Sun focus (numeric trace)'),
    h('p', { class: 'hint' }, `Parallel sunlight with its 0.53° disc, through the laminate, the lid aperture, the ${S.mode} mirror and the fold to the panel plane; the plan's transmission chain scales the power.`),
    kv(rows),
    img('sun_spot.png', 'Irradiance on the panel plane for the nominal sun (51° behind the car): 80 × 120 mm, rear at the top. The off-axis mirror makes a comatic spot, a hot core with two wings, not the plan\'s disc.'),
    img('sun_patch.png', 'Sun directions (elevation up, azimuth across, 1.5° steps): bright where focused light lands on the 60 × 30 mm crop, dim where it lands elsewhere on the cell.'),
    h('p', { class: 'muted', style: { fontSize: '11.5px', marginTop: '6px' } }, 'A path tracer cannot render this (a reflective caustic of a delta light), so it is a ray bundle in numpy against the same layout.json.'));
}

// A static view for the Driver view's dock.
export function cyclesDockView(results) {
  if (!results) return null;
  const b = results.beauty;
  const file = b ? b.file : 'toroid_eye.png';
  const el = h('img', { src: ASSET_BASE + 'cycles/' + file, alt: 'Cycles render from the eye', style: { width: '100%', height: '100%', display: 'block', objectFit: 'cover' } });
  const title = b ? `Blender path trace of the driver's view: the real PGU frame through the real optics into the car (sun ${b.sunElevDeg}° up)` : 'Blender path trace of the same optics from the nominal eye: the crop as a dot grid';
  const aspect = b ? b.res[0] / b.res[1] : results.settings.res[0] / results.settings.res[1];
  return { label: 'Cycles', title, el, aspect };
}
