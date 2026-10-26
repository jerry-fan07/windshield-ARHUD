// Plays a component's assembly from the ground up: parts of finished steps sit in place, the current step's parts fly in
// from their explode direction, later steps are hidden. Shared by the Components and Build modes.
import * as THREE from 'three';
import { easeInOut, clamp } from '../util.js';

export class Assembler {
  constructor(comp) {
    this.c = comp;
    this.step = comp.assembly.length;   // fully assembled
    this.anim = 1;
    this.flyScale = 2.2;
  }
  partStep(id) { return this.c.assembly.findIndex((s) => s.parts.includes(id)); }
  setStep(i, animate = true) {
    this.step = clamp(i, -1, this.c.assembly.length);
    this.anim = animate ? 0 : 1;
    this.apply();
  }
  // explode (0..1) still applies on top of the assembly state
  apply(explode = this.c._explode || 0) {
    const k = easeInOut(this.anim);
    for (const p of this.c.parts) {
      const si = this.partStep(p.id);
      const base = p.base;
      if (si < this.step || this.step >= this.c.assembly.length) {
        p.object.visible = true;
        p.object.position.copy(base).addScaledVector(p.explode, explode);
      } else if (si === this.step) {
        p.object.visible = true;
        const dir = p.explode.lengthSq() > 1e-8 ? p.explode.clone() : new THREE.Vector3(0, 0.08, 0);
        const off = dir.multiplyScalar(this.flyScale * (1 - k) + explode);
        p.object.position.copy(base).add(off);
      } else {
        p.object.visible = false;
      }
    }
  }
  update(dt) {
    if (this.anim < 1) { this.anim = Math.min(1, this.anim + dt / 0.9); this.apply(); }
  }
  showAll() { this.step = this.c.assembly.length; this.anim = 1; this.apply(); }
}
