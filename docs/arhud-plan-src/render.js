// Print an HTML file to PDF with system Chrome: Letter, page-number footer, PDF outline.
const os = require('os');
const path = require('path');
const puppeteer = require('puppeteer-core');
(async () => {
  const [, , htmlPath, pdfPath, title] = process.argv;
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-gpu', '--no-first-run',
           `--user-data-dir=${path.join(os.tmpdir(), 'arhud-plan-chrome')}`],
  });
  try {
    const page = await browser.newPage();
    await page.goto('file://' + htmlPath, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    const footer = `<div style="width:100%;padding:0 18mm;box-sizing:border-box;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;font-size:7.5pt;color:#898781;display:flex;justify-content:space-between;">
      <span>${title}</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`;
    await page.pdf({
      path: pdfPath, format: 'Letter', printBackground: true, outline: true,
      margin: { top: '16mm', bottom: '20mm', left: '18mm', right: '18mm' },
      displayHeaderFooter: true, headerTemplate: '<span></span>', footerTemplate: footer,
    });
  } finally {
    await browser.close();
  }
  console.log('wrote', pdfPath);
})().catch(e => { console.error(e); process.exit(1); });
