// The contract every component builder follows, and a checker the dev pages use.
//
// A builder is `export function buildX(opts = {}) -> Component`, where
//
//   Component = {
//     id: string,                 // stable id, e.g. 'jetson'
//     name: string,               // display name, e.g. 'Seeed reComputer J4012 (Jetson Orin NX 16 GB)'
//     category: 'pgu' | 'optics' | 'housing' | 'compute' | 'software' | 'sensor' | 'power' | 'controller'
//             | 'display' | 'network' | 'instrument' | 'stage' | 'vehicle',
//     group: THREE.Group,         // local frame X forward, Y up, Z right, metres
//     mount: string,              // where the local origin is ('centre of the base plate', 'car frame origin', ...)
//     size: [x, y, z],            // overall size in metres, approximate
//     parts: [{ id, name, object, explode: THREE.Vector3, desc }],
//                                 // object is a DIRECT child of group. explode is the offset in group-local metres at
//                                 // full explode. The explorer and the build stepper move part.object.position between
//                                 // its built position and built + explode, so update() must never set the position of
//                                 // a part object; animate its children instead.
//     assembly: [{ title, parts: [partId, ...], text }],
//                                 // build order from the ground up; every part id appears in exactly one step
//     facts: [[label, value], ...],   // 4-10 lines; plan numbers from params.js; tag ' (ASSUMED)' / ' (UNVERIFIED)' as the plan does
//     desc: string,               // 2-4 plain sentences: what it is and its job in this HUD
//     working: string,            // one sentence: what the working animation shows
//     setWorking(on): void,       // show or hide the visuals only the animation uses
//     update(t, dt, s): void,     // advance the animation; s = { working, explode, live } (live: optional sim state)
//     handles?: object,           // optional live controls, e.g. { setShutter(x), setBacklight(x), setPanelTexture(tex) }
//   }

export function validateComponent(c) {
  const errs = [];
  for (const k of ['id', 'name', 'category', 'group', 'mount', 'size', 'parts', 'assembly', 'facts', 'desc', 'working']) {
    if (c[k] === undefined) errs.push(`missing ${k}`);
  }
  if (typeof c.update !== 'function') errs.push('missing update()');
  if (typeof c.setWorking !== 'function') errs.push('missing setWorking()');
  const ids = new Set();
  for (const p of c.parts || []) {
    if (!p.id || !p.object) errs.push(`bad part ${p.id}`);
    if (ids.has(p.id)) errs.push(`duplicate part ${p.id}`);
    ids.add(p.id);
    if (p.object && p.object.parent !== c.group) errs.push(`part ${p.id} is not a direct child of group`);
    if (!p.explode || !p.explode.isVector3) errs.push(`part ${p.id} has no explode vector`);
  }
  const used = new Set();
  for (const s of c.assembly || []) for (const id of s.parts) {
    if (!ids.has(id)) errs.push(`assembly references unknown part ${id}`);
    if (used.has(id)) errs.push(`part ${id} appears in two assembly steps`);
    used.add(id);
  }
  for (const id of ids) if (!used.has(id)) errs.push(`part ${id} is in no assembly step`);
  return errs;
}

// Shared helper for builders: register a part (adds it to the group and to the parts list).
export function addPart(c, id, name, object, explode, desc = '') {
  object.name = id;
  c.group.add(object);
  c.parts.push({ id, name, object, explode, desc });
  return object;
}

// Empty component skeleton.
export function makeComponent(THREE, fields) {
  return {
    group: new THREE.Group(), parts: [], assembly: [], facts: [], desc: '', working: '',
    setWorking() {}, update() {}, ...fields,
  };
}
