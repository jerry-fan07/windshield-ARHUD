// node dev/export-lut.mjs [mode] [glassRh glassRv]  -> assets/hudd_lut_<mode>.json: the calibration table hudd loads.
import { writeFileSync } from 'fs';
import * as GM from '../js/geom.js';
import { buildLut, lutToJson } from '../js/lut.js';
const mode = process.argv[2] || 'toroid';
GM.MIRROR.mode = mode; GM.setGlassForMode(mode);
if (process.argv[3]) { GM.GLASS.Rh = parseFloat(process.argv[3]); GM.GLASS.Rv = parseFloat(process.argv[4] || '0'); }
const t0 = Date.now();
const L = buildLut(mode);
const out = `assets/hudd_lut_${mode}${GM.GLASS.Rh ? `_glass${GM.GLASS.Rh}x${GM.GLASS.Rv}` : ''}.json`;
writeFileSync(out, JSON.stringify(lutToJson(L)));
console.log(`wrote ${out}: eye ${L.eyeNz} x ${L.eyeNy}, field ${L.fieldNx} x ${L.fieldNy}, ${L.misses} misses, ${Date.now() - t0} ms`);
