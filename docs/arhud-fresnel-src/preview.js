// Screenshot each <figure data-name> of an HTML file to out/preview/<name>.png (figure QA).
const os = require('os'); const path = require('path'); const fs = require('fs');
const puppeteer = require('puppeteer-core');
(async () => {
  const [, , htmlPath, outDir] = process.argv;
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true, args: ['--no-sandbox', '--disable-gpu', `--user-data-dir=${path.join(os.tmpdir(), 'arhud-fresnel-prev')}`],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 760, height: 1200, deviceScaleFactor: 1.6 });
  await page.goto('file://' + htmlPath, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  const figs = await page.$$('figure[data-name]');
  for (const f of figs) {
    const name = await f.evaluate(e => e.dataset.name);
    await f.screenshot({ path: path.join(outDir, name + '.png') });
  }
  await browser.close();
  console.log('shots', figs.length);
})().catch(e => { console.error(e); process.exit(1); });
