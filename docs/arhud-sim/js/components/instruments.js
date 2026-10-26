// Measurement instruments: the latency probe, the spot luminance meter, the 30 m target board and the laser rangefinder.
import * as THREE from 'three';
import { M } from '../mats.js';
import { rbox, box, cyl, cylX, sphere, canvasTexture, DEG } from '../util.js';
import { makeComponent, addPart } from './contract.js';
import { P, R } from '../params.js';
import { FONT, vec, put, mat, MX, cost, decal, glow, led, pico, livePanel, panelBg, txt, cable, roundRect } from './electronics.js';

// ---- Latency probe: LED at the road camera, photodiode on the panel, Pico timing ------------------
export function buildLatencyProbe() {
  const c = makeComponent(THREE, {
    id: 'latencyProbe', name: 'Latency probe (LED + photodiode + Pico)', category: 'instrument',
    mount: 'centre of the timing board underside', size: [0.12, 0.08, 0.22],
  });
  const brd = new THREE.Group();
  put(brd, box(0.06, 0.0016, 0.032, MX.fr4), 0, 0.0008, 0);
  put(brd, decal('LATENCY PROBE', 0.02, '+y', { color: '#2a1d10', font: '700 48px ' + FONT }), 0.017, 0.00165, -0.013);
  addPart(c, 'board', 'Timing board', brd, vec(0, -0.03, 0), '');
  const pi = pico(); pi.position.set(-0.004, 0.0045, 0);
  addPart(c, 'pico', 'Raspberry Pi Pico (timer)', pi, vec(0, 0.04, 0), 'Flashes the LED and timestamps the photodiode edge with microsecond resolution.');
  // LED head on a gooseneck, aimed at the road camera
  const ledHead = new THREE.Group();
  put(ledHead, cable([[0, 0.0, -0.08], [0.0, 0.03, -0.085], [0.02, 0.05, -0.09], [0.04, 0.055, -0.09]], 0.0025, M.plasticBlack), 0, 0, 0);
  put(ledHead, cylX(0.006, 0.02, M.aluAnodBlack, 20), 0.05, 0.055, -0.09);
  const lm = M.led(0xffffff, 0);
  put(ledHead, cylX(0.0042, 0.002, lm, 20), 0.0605, 0.055, -0.09);
  const lg = glow(0xffffff, 0.06, 0); lg.position.set(0.063, 0.055, -0.09); ledHead.add(lg);
  put(ledHead, rbox(0.016, 0.006, 0.02, 0.002, M.plasticBlack), 0, 0.0, -0.08);
  addPart(c, 'ledHead', 'Bright LED aimed at the road camera', ledHead, vec(0, 0.02, -0.05), 'Its flash is the "event" the whole chain must react to.');
  // photodiode on a suction cup, pressed on the panel
  const pd = new THREE.Group();
  put(pd, cable([[0, 0, 0.08], [0.0, 0.03, 0.085], [0.02, 0.05, 0.09], [0.035, 0.055, 0.09]], 0.0025, M.plasticBlack), 0, 0, 0);
  put(pd, cylX(0.009, 0.012, M.plasticBlack, 24), 0.043, 0.055, 0.09);
  const cup = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.010, 0.008, 32, 1, true), mat('cup', () => new THREE.MeshPhysicalMaterial({ color: 0xbfd6e6, transparent: true, opacity: 0.55, roughness: 0.2, side: THREE.DoubleSide })));
  cup.rotation.z = -Math.PI / 2; cup.position.set(0.053, 0.055, 0.09); pd.add(cup);
  const pdm = M.led(0x5ec8ff, 0);
  put(pd, box(0.0012, 0.0055, 0.0055, pdm), 0.0495, 0.055, 0.09);
  put(pd, rbox(0.016, 0.006, 0.02, 0.002, M.plasticBlack), 0, 0, 0.08);
  addPart(c, 'photodiode', 'Photodiode in a suction cup (on the panel)', pd, vec(0, 0.02, 0.05), 'Sees the panel change when the rendered marker flips.');
  const wires = new THREE.Group();
  put(wires, cable([[-0.02, 0.006, -0.01], [-0.02, 0.006, -0.05], [0, 0.0, -0.08]], 0.0012, M.cableRed), 0, 0, 0);
  put(wires, cable([[-0.02, 0.006, 0.01], [-0.02, 0.006, 0.05], [0, 0.0, 0.08]], 0.0012, M.cableBlue), 0, 0, 0);
  addPart(c, 'wires', 'Leads', wires, vec(-0.03, 0, 0), '');

  const fx = new THREE.Group(); fx.visible = false; c.group.add(fx);
  const pnl = livePanel(900, 420, 0.2); pnl.obj.position.set(0, 0.14, 0); fx.add(pnl.obj);
  const st = { cycle: -1, L: 60, stages: P.LAT.map(([, a]) => a) };
  c.assembly = [
    { title: 'Timing board', parts: ['board', 'pico'], text: 'A Pico times the chain; the controller\'s Pico can do this job.' },
    { title: 'LED and photodiode', parts: ['ledHead', 'photodiode', 'wires'], text: 'LED in front of the road camera; photodiode on the panel where hudd draws a test marker.' },
  ];
  c.facts = [
    ['Method', 'flash an LED at the road camera; time the panel change with a photodiode'],
    ['Target', `whole chain ≤ 90 ms; estimate ${R.LAT_MIN}–${R.LAT_MAX} ms uncompensated`],
    ['Bench mode', 'a synthetic lanes step measures renderer + panel alone'],
    ['Cross-check', 'the age hudd reports in hudStats'],
    ['Why', 'replay has no live latency: only this test measures the real chain'],
    ['Cost', cost('Latency probe')],
  ];
  c.desc = 'Measures motion-to-photon latency end to end. The Pico flashes an LED in front of the road camera; perception sees it, hudd flips a test marker, and a photodiode on the panel catches the change. The time between is the latency the age compensation must cover.';
  c.working = 'The LED flashes; after the measured delay the photodiode fires; the timeline (slowed 10×) shows each stage against the 90 ms target.';
  c.setWorking = (on) => { fx.visible = on; if (!on) { lm.emissiveIntensity = 0; lg.material.opacity = 0; pdm.emissiveIntensity = 0; } };
  c.update = (t, dt, s) => {
    if (!s || !s.working) return;
    const per = 2.4, k = Math.floor(t / per), ph = t - k * per;
    if (k !== st.cycle) {
      st.cycle = k;
      const r = (i) => 0.5 + 0.5 * Math.sin(k * 1.7 + i * 2.3);
      st.stages = P.LAT.map(([, a, b], i) => a + (b - a) * (0.25 + 0.5 * r(i)));
      st.L = st.stages.reduce((x, y) => x + y, 0);
    }
    const tl = ph * 100;               // ms, slowed 10x
    const flash = tl < 15;
    lm.emissiveIntensity = flash ? 6 : 0; lg.material.opacity = flash ? 1 : 0;
    const hit = tl >= st.L && tl < st.L + 40;
    pdm.emissiveIntensity = hit ? 4 : 0.1;
    pi.userData.led.userData.set(flash || hit ? 1 : 0.1);
    pnl.tick(dt, 20, (ctx, W, H) => {
      panelBg(ctx, W, H, 'Motion-to-photon latency', 'LED at the road camera → photodiode on the panel · timeline slowed 10×');
      const x0 = 30, w = W - 60, sc = w / 120, y = 150;
      let x = x0;
      const cols = ['#5ec8ff', '#4fd18b', '#c78bff', '#ffb347', '#ff7b7b'];
      const names = ['camera', 'perception', 'publish', 'render', 'scan-out'];
      st.stages.forEach((v, i) => { ctx.fillStyle = cols[i]; ctx.globalAlpha = tl > (x - x0) / sc ? 1 : 0.35; ctx.fillRect(x, y, v * sc, 36); ctx.globalAlpha = 1; txt(ctx, names[i], x + 2, i % 2 ? y - 16 : y + 56, { size: 17, color: cols[i] }); x += v * sc; });
      ctx.fillStyle = '#fff'; ctx.fillRect(x0 + 90 * sc - 1, y - 6, 3, 60); txt(ctx, '90 ms target', x0 + 90 * sc, y + 72, { size: 18, align: 'center' });
      const cur = Math.min(tl, 120); ctx.fillStyle = '#ffd27a'; ctx.fillRect(x0 + cur * sc - 2, y - 6, 4, 48);
      txt(ctx, flash ? 'LED flash' : tl < st.L ? `waiting… ${tl.toFixed(0)} ms` : `photodiode fired at ${st.L.toFixed(0)} ms`, x0, 280, { size: 28, weight: 600, color: tl >= st.L ? (st.L <= 90 ? '#9fe6bd' : '#ff8a8a') : '#eef4fa' });
      txt(ctx, `at 30 m/s the car moves ${(30 * st.L / 1000).toFixed(1)} m in that time; hudd compensates for the age`, x0, 330, { size: 21 });
      txt(ctx, 'stage values: plan §10 estimates, sampled inside their ranges', x0, 372, { size: 18, color: '#8fa3b6' });
    });
  };
  return c;
}

// ---- Spot luminance meter on a tripod ---------------------------------------------------------
export function buildLumMeter() {
  const c = makeComponent(THREE, {
    id: 'lumMeter', name: 'Spot luminance meter (Konica Minolta LS-150 class) on a tripod', category: 'instrument',
    mount: 'centre of the tripod feet on the ground; the meter looks along +X at eye height', size: [0.9, 1.35, 0.9],
  });
  const EY = R.H_CAM;
  const tri = new THREE.Group();
  const hub = vec(0, EY - 0.17, 0);
  for (let i = 0; i < 3; i++) {
    const a = i * 2.094 + 0.5, foot = vec(0.42 * Math.cos(a), 0, 0.42 * Math.sin(a));
    const mid = hub.clone().lerp(foot, 0.5);
    const len = hub.distanceTo(foot);
    const leg = cyl(0.009, 0.007, len, M.aluAnodBlack, 12); leg.position.copy(mid); leg.quaternion.setFromUnitVectors(vec(0, 1, 0), hub.clone().sub(foot).normalize()); tri.add(leg);
    const low = cyl(0.006, 0.005, len * 0.45, M.alu, 12); low.position.copy(hub.clone().lerp(foot, 0.78)); low.quaternion.copy(leg.quaternion); tri.add(low);
    put(tri, sphere(0.012, M.rubber, 12), foot.x, 0.008, foot.z);
  }
  put(tri, cyl(0.022, 0.026, 0.05, M.aluAnodBlack, 20), 0, EY - 0.16, 0);
  put(tri, cyl(0.011, 0.011, 0.16, M.alu, 16), 0, EY - 0.10, 0);
  addPart(c, 'tripod', 'Tripod', tri, vec(0, -0.2, 0), 'Holds the meter at the design eye point.');
  const head = new THREE.Group();
  put(head, cyl(0.025, 0.025, 0.02, M.aluAnodBlack, 24), 0, EY - 0.075, 0);
  put(head, rbox(0.06, 0.012, 0.045, 0.004, M.aluAnodBlack), 0, EY - 0.06, 0);
  put(head, cylZ_(0.004, 0.08, M.plasticBlack), -0.02, EY - 0.065, 0.06);
  addPart(c, 'head', 'Pan-tilt head', head, vec(0, -0.08, 0), '');
  const body = new THREE.Group();
  const by = EY;
  put(body, rbox(0.16, 0.085, 0.079, 0.016, mat('lsBody', () => M.color(0xe8e8e4, 0.5))), -0.02, by, 0);
  put(body, rbox(0.05, 0.08, 0.04, 0.012, mat('lsGrip', () => M.color(0x2a2b2e, 0.7))), -0.03, by - 0.07, 0);
  put(body, cyl(0.004, 0.004, 0.012, M.plasticBlack, 12), 0.0, by - 0.05, 0.0).rotation.z = Math.PI / 2;
  const scrTex = canvasTexture(512, 256, (ctx, W, H) => drawLs(ctx, W, H, 1944, 'design at the eye'));
  const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.06, 0.03), new THREE.MeshBasicMaterial({ map: scrTex, toneMapped: false }));
  scr.position.set(-0.03, by + 0.012, 0.0397); body.add(scr);
  for (let i = 0; i < 4; i++) put(body, cyl(0.004, 0.004, 0.003, M.plasticGrey, 16), -0.065 + i * 0.012, by - 0.018, 0.0396).rotation.x = Math.PI / 2;
  put(body, decal('LS-150 class · 1° spot', 0.05, '+z', { color: '#444', font: '600 48px ' + FONT }), -0.02, by + 0.034, 0.0397);
  addPart(c, 'body', 'Meter body, display and grip', body, vec(0, 0.08, 0), '');
  const obj = new THREE.Group();
  put(obj, cylX(0.034, 0.06, M.plasticBlack, 40), 0.09, by, 0);
  put(obj, cylX(0.026, 0.002, M.lens, 40), 0.1205, by, 0);
  const fr = new THREE.Mesh(new THREE.TorusGeometry(0.03, 0.003, 10, 40), M.rubber); fr.rotation.y = Math.PI / 2; fr.position.set(0.12, by, 0); obj.add(fr);
  addPart(c, 'objective', 'Objective lens (focus 1 m to infinity)', obj, vec(0.12, 0, 0), 'Focuses on the 7.5 m virtual image.');
  const ep = new THREE.Group();
  put(ep, cylX(0.016, 0.03, M.plasticBlack, 24), -0.115, by + 0.012, 0);
  put(ep, cylX(0.019, 0.012, M.rubber, 24), -0.132, by + 0.012, 0);
  addPart(c, 'eyepiece', 'Viewfinder eyepiece with the 1° spot circle', ep, vec(-0.1, 0, 0), '');
  const fx = new THREE.Group(); fx.visible = false; c.group.add(fx);
  const spot = 1.2 * Math.tan(0.5 * DEG);
  const cone = new THREE.Mesh(new THREE.ConeGeometry(spot, 1.2, 24, 1, true), new THREE.MeshBasicMaterial({ color: 0xffd27a, transparent: true, opacity: 0.18, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending }));
  cone.rotation.z = Math.PI / 2; cone.position.set(0.12 + 0.6, by, 0); fx.add(cone);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(spot, 0.0015, 8, 40), M.emissive(0xffd27a, 1.5)); ring.rotation.y = Math.PI / 2; ring.position.set(1.32, by, 0); fx.add(ring);
  const pnl = livePanel(720, 220, 0.3); pnl.obj.position.set(0.7, by + 0.18, 0); fx.add(pnl.obj);
  pnl.draw((ctx, W, H) => { panelBg(ctx, W, H, '1° spot, aimed at the white patch'); txt(ctx, `spot at 7.5 m: ${(2 * 7500 * Math.tan(0.5 * DEG)).toFixed(0)} mm across; same direction as the background`, 22, 110, { size: 21 }); txt(ctx, 'a lux meter cannot measure a virtual image', 22, 155, { size: 21, color: '#8fa3b6' }); });
  c.assembly = [
    { title: 'Tripod', parts: ['tripod', 'head'], text: 'Set the head at the eye point.' },
    { title: 'Meter', parts: ['body', 'objective', 'eyepiece'], text: 'Focus on the virtual image; read the white patch, then the background in the same direction.' },
  ];
  const eyeDesign = R.L_PANEL_DESIGN * R.PATH_WS;
  c.facts = [
    ['Instrument', 'Konica Minolta LS-150: 1° spot, focus 1 m to ∞, ≈ $3,900 (assumed instrument)'],
    ['Budget option', 'Sekonic L-858D, $689, 1° spot, if it can focus on a virtual image (UNVERIFIED)'],
    ['Sky target', `≥ ${R.L_DAY_EYE.toLocaleString('en-US')} cd/m² at the eye at noon (contrast 1.15 vs 10,000)`],
    ['Road target', `≥ ${R.L_ROAD_EYE.toLocaleString('en-US')} cd/m² against sunlit asphalt (5,000 ASSUMED)`],
    ['Design', `${Math.round(eyeDesign).toLocaleString('en-US')} cd/m² at the eye: 10,000 at the panel × ${(R.PATH_WS * 100).toFixed(1)}% path`],
    ['Night', `white ≤ ${R.L_NIGHT_EYE} cd/m²; unlit window ≤ 0.1 cd/m²`],
    ['Last resort', 'a calibrated camera, within about 20% above 5,000 cd/m²'],
    ['Cost', cost('Luminance meter')],
  ];
  c.desc = 'Proves the contrast criterion. From the eye point it reads the luminance of a white patch in the virtual image and of the sky or road behind it; the ratio must reach 1.15 at noon.';
  c.working = 'The 1° measuring spot reaches out toward the image; the display alternates between the design value at the eye and the sky target.';
  c.setWorking = (on) => { fx.visible = on; };
  let last = '';
  c.update = (t, dt, s) => {
    if (!s || !s.working) return;
    const ph = (t % 8) / 8;
    const val = ph < 0.5 ? eyeDesign : R.L_DAY_EYE;
    const label = ph < 0.5 ? 'design at the eye' : 'sky target (minimum)';
    if (label !== last) { last = label; drawLs(scrTex.image.getContext('2d'), 512, 256, val, label); scrTex.needsUpdate = true; }
  };
  return c;
}
function cylZ_(r, h, m) { const x = cyl(r, r, h, m, 16); x.rotation.x = Math.PI / 2; return x; }
function drawLs(ctx, W, H, val, label) {
  ctx.fillStyle = '#b9c7a6'; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#1d2418'; ctx.font = `600 110px ${FONT}`; ctx.textAlign = 'right'; ctx.textBaseline = 'alphabetic';
  ctx.fillText(Math.round(val).toLocaleString('en-US'), W - 120, 150);
  ctx.font = `500 34px ${FONT}`; ctx.fillText('cd/m²', W - 16, 150);
  ctx.textAlign = 'left'; ctx.font = `500 30px ${FONT}`; ctx.fillText(label, 20, 215);
  ctx.fillText('1°', 20, 50);
}

// ---- 30 m registration target board -----------------------------------------------------------------
export function buildTargetBoard() {
  const c = makeComponent(THREE, {
    id: 'targetBoard', name: '30 m registration target board', category: 'instrument',
    mount: 'ground centre under the board; the target face looks toward -X (the car)', size: [0.5, 1.3, 1.3],
  });
  const BW = 1.2, BH = 0.9, BY = 0.85;
  const feet = new THREE.Group();
  for (const s of [-1, 1]) put(feet, box(0.5, 0.03, 0.06, M.aluAnodBlack), 0, 0.015, s * 0.5);
  addPart(c, 'feet', 'Feet', feet, vec(0, -0.2, 0), '');
  const legs = new THREE.Group();
  for (const s of [-1, 1]) put(legs, box(0.04, BY + BH / 2 - 0.03, 0.04, M.alu), 0.03, (BY + BH / 2) / 2 + 0.015, s * 0.5);
  put(legs, box(0.03, 0.03, 1.04, M.alu), 0.03, 0.3, 0);
  addPart(c, 'legs', 'Uprights and crossbar', legs, vec(0.2, 0, 0), '');
  const tex = canvasTexture(1200, 900, (ctx, W, H) => {
    ctx.fillStyle = '#f4f4f0'; ctx.fillRect(0, 0, W, H);
    const sq = 50;
    for (let i = 0; i < W / sq; i++) for (const y of [0, H - sq]) if (i % 2 === (y ? 1 : 0)) { ctx.fillStyle = '#111'; ctx.fillRect(i * sq, y, sq, sq); }
    for (let j = 1; j < H / sq - 1; j++) for (const x of [0, W - sq]) if (j % 2 === (x ? 0 : 1)) { ctx.fillStyle = '#111'; ctx.fillRect(x, j * sq, sq, sq); }
    ctx.strokeStyle = '#111'; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(W / 2, 90); ctx.lineTo(W / 2, H - 90); ctx.moveTo(90, H / 2); ctx.lineTo(W - 90, H / 2); ctx.stroke();
    ctx.lineWidth = 2; for (let x = 100; x < W - 90; x += 25) { ctx.beginPath(); ctx.moveTo(x, H / 2 - (x % 100 ? 10 : 22)); ctx.lineTo(x, H / 2 + (x % 100 ? 10 : 22)); ctx.stroke(); }
    ctx.fillStyle = '#111'; ctx.font = `700 46px ${FONT}`; ctx.textAlign = 'center'; ctx.fillText('30 m · REGISTRATION TARGET', W / 2, 112);
    ctx.font = `500 30px ${FONT}`; ctx.fillText('surveyed with the laser rangefinder; ticks every 25 mm', W / 2, H - 110);
  });
  const board = new THREE.Group();
  put(board, box(0.02, BH, BW, mat('boardEdge', () => M.color(0xdedcd6, 0.8))), 0, BY, 0);
  const face = new THREE.Mesh(new THREE.PlaneGeometry(BW, BH), new THREE.MeshStandardMaterial({ map: tex, roughness: 0.85 }));
  face.rotation.y = -Math.PI / 2; face.position.set(-0.0102, BY, 0); board.add(face);
  addPart(c, 'board', 'Target panel', board, vec(-0.15, 0, 0), 'Matte panel with a checker border and a ruled centre cross.');
  const ringTex = canvasTexture(256, 256, (ctx, W, H) => {
    for (let r = 128, k = 0; r > 8; r -= 18, k++) { ctx.beginPath(); ctx.arc(128, 128, r, 0, 7); ctx.fillStyle = k % 2 ? '#f4f4f0' : '#111'; ctx.fill(); }
    ctx.fillStyle = '#e8332a'; ctx.beginPath(); ctx.arc(128, 128, 9, 0, 7); ctx.fill();
  });
  const targets = new THREE.Group();
  const tpos = [[0.4, 0.2], [-0.4, 0.2], [0.4, -0.2], [-0.4, -0.2], [0, 0]];
  for (const [z, y] of tpos) {
    const d = new THREE.Mesh(new THREE.CircleGeometry(0.09, 48), new THREE.MeshStandardMaterial({ map: ringTex, roughness: 0.6 }));
    d.rotation.y = -Math.PI / 2; d.position.set(-0.014, BY + y, z); targets.add(d);
  }
  addPart(c, 'targets', 'Ring targets', targets, vec(-0.3, 0, 0), 'Each centre is surveyed; the road camera detects them too, which separates perception error from optics error.');
  const fx = new THREE.Group(); fx.visible = false; c.group.add(fx);
  const frame = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(0.03, BH + 0.04, BW + 0.04)), new THREE.LineBasicMaterial({ color: 0x5ec8ff, toneMapped: false }));
  frame.position.set(0, BY, 0); fx.add(frame);
  const marks = [];
  tpos.forEach(([z, y], i) => {
    for (const [col, dz] of [[0x4fd18b, 0.0], [0xffd27a, 0.012 * Math.cos(i * 1.3)]]) {
      const g = new THREE.Group(); g.position.set(-0.03, BY + y + 0.01 * Math.sin(i), z + dz);
      const m = M.emissive(col, 1.6);
      put(g, box(0.002, 0.07, 0.004, m)); put(g, box(0.002, 0.004, 0.07, m));
      fx.add(g); marks.push(g);
    }
  });
  const pnl = livePanel(720, 220, 0.6); pnl.obj.position.set(-0.1, BY + BH / 2 + 0.25, 0); fx.add(pnl.obj);
  pnl.draw((ctx, W, H) => { panelBg(ctx, W, H, 'Static registration at 30 m: ≤ 0.5°'); txt(ctx, 'green: the road camera\'s own detection · yellow: the survey', 22, 110, { size: 21 }); txt(ctx, `0.5° at 30 m = ${(30000 * Math.tan(0.5 * DEG)).toFixed(0)} mm`, 22, 155, { size: 21, color: '#8fa3b6' }); });
  c.assembly = [
    { title: 'Stand', parts: ['feet', 'legs'], text: '' },
    { title: 'Panel and targets', parts: ['board', 'targets'], text: 'Set at 30 m on the car\'s axis; survey each target with the rangefinder.' },
  ];
  c.facts = [
    ['Use', 'refines the nominal eye point (calibration step 1) and checks static registration'],
    ['Criterion', 'static registration at 30 m ≤ 0.5°; ≤ 0.3° under ±75 mm head motion'],
    ['Method', 'camera at the eye point vs the surveyed board; marker from the road camera\'s detection and from the survey'],
    ['Before demos', 'target check for camera-mount drift'],
    ['Cost', cost('Latency probe')],
  ];
  c.desc = 'A surveyed target set 30 m in front of the car. The road camera detects its rings while a camera at the eye point photographs the rendered markers over them; the difference is the registration error.';
  c.working = 'Detected and surveyed markers sit over each ring target; their gap is what the calibration removes.';
  c.setWorking = (on) => { fx.visible = on; };
  c.update = (t, dt, s) => { if (!s || !s.working) return; frame.material.color.setHSL(0.55, 0.8, 0.5 + 0.2 * Math.sin(t * 3)); marks.forEach((m, i) => m.scale.setScalar(1 + 0.08 * Math.sin(t * 4 + i))); };
  return c;
}

// ---- Laser rangefinder --------------------------------------------------------------------------------
export function buildRangefinder() {
  const c = makeComponent(THREE, {
    id: 'rangefinder', name: 'Handheld laser rangefinder', category: 'instrument',
    mount: 'centre of the body; it looks along +X', size: [0.12, 0.05, 0.045],
  });
  const body = new THREE.Group();
  put(body, rbox(0.105, 0.045, 0.038, 0.012, mat('rfBody', () => M.color(0x2f3a2c, 0.75))), 0, 0, 0);
  put(body, rbox(0.06, 0.047, 0.04, 0.01, M.rubber), -0.01, 0, 0);
  for (let i = 0; i < 2; i++) put(body, cyl(0.004, 0.004, 0.003, mat('btn', () => M.color(0xd8d8d0, 0.5)), 16), -0.01 + i * 0.016, 0.024, 0);
  put(body, decal('RANGE', 0.02, '+z', { color: '#c8ccc0', font: '700 48px ' + FONT }), 0.01, 0.0, 0.0195);
  addPart(c, 'body', 'Body with buttons', body, vec(0, 0.04, 0), '');
  const opt = new THREE.Group();
  put(opt, cylX(0.013, 0.012, M.plasticBlack, 32), 0.058, 0.004, -0.003);
  put(opt, cylX(0.010, 0.001, M.lens, 32), 0.0645, 0.004, -0.003);
  put(opt, cylX(0.005, 0.006, M.plasticBlack, 20), 0.056, -0.013, 0.010);
  const em = M.led(0xff2020, 0);
  put(opt, cylX(0.0035, 0.001, em, 20), 0.0595, -0.013, 0.010);
  addPart(c, 'optics', 'Objective and laser emitter', opt, vec(0.05, 0, 0), '');
  const ep = new THREE.Group();
  put(ep, cylX(0.011, 0.016, M.rubber, 24), -0.06, 0.006, 0);
  addPart(c, 'eyepiece', 'Eyepiece with in-view display', ep, vec(-0.05, 0, 0), '');
  const fx = new THREE.Group(); fx.visible = false; c.group.add(fx);
  const beamLen = 0.9;
  const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.0008, 0.0008, beamLen, 8), M.emissive(0xff2020, 2));
  beam.rotation.z = Math.PI / 2; beam.position.set(0.0595 + beamLen / 2, -0.013, 0.010); fx.add(beam);
  const dot = glow(0xff2020, 0.04, 1); dot.position.set(0.0595 + beamLen, -0.013, 0.010); fx.add(dot);
  const pnl = livePanel(520, 160, 0.14); pnl.obj.position.set(0.35, 0.08, 0); fx.add(pnl.obj);
  pnl.draw((ctx, W, H) => { panelBg(ctx, W, H, '30.00 m'); txt(ctx, 'eye point → target board centre', 22, 100, { size: 22 }); });
  c.assembly = [
    { title: 'Body', parts: ['body'], text: '' },
    { title: 'Optics', parts: ['optics', 'eyepiece'], text: 'Survey the target board and the nominal eye point.' },
  ];
  c.facts = [
    ['Use', 'surveys the 30 m target board and range checks for the stereo depth'],
    ['Plan check', 'range within 10% of the stereo median (Phase 1 score)'],
    ['Cost', cost('Latency probe')],
  ];
  c.desc = 'Surveys distances for calibration: the target board at 30 m and the reference ranges the stereo depth is scored against.';
  c.working = 'The laser spot lands on the target and the range reads out.';
  c.setWorking = (on) => { fx.visible = on; em.emissiveIntensity = on ? 3 : 0; };
  c.update = (t, dt, s) => { if (s && s.working) dot.material.opacity = 0.7 + 0.3 * Math.sin(t * 9); };
  return c;
}
