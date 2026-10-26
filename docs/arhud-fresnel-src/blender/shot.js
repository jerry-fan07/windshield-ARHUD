// Screenshot the test frame SVG to a PNG at exact pixel size.
const os = require('os'); const path = require('path');
const puppeteer = require('puppeteer-core');
(async () => {
  const [, , html, out] = process.argv;
  const b = await puppeteer.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true,
    args: ['--no-sandbox', `--user-data-dir=${path.join(os.tmpdir(), 'arhud-fresnel-shot')}`] });
  const p = await b.newPage();
  await p.setViewport({ width: 1262, height: 631, deviceScaleFactor: 1 });
  await p.goto('file://' + html, { waitUntil: 'load' });
  const el = await p.$('#f');
  await el.screenshot({ path: out });
  await b.close();
})().catch(e => { console.error(e); process.exit(1); });
