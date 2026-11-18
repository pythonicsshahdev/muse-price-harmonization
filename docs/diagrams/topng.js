// node topng.js <file.html> <out.png> [scale]
// Renders the diagram with the skill's playwright-core and writes a PNG.
const os = require('os');
const path = require('path');
const { chromium } = require(path.join(os.homedir(),
  '.claude/skills/boomi-usecase-diagram/assets/node_modules/playwright-core'));

(async () => {
  const [, , file, out, scale = '2'] = process.argv;
  const b = await chromium.launch({ channel: 'chrome' });
  const p = await b.newPage({ viewport: { width: 2000, height: 1200 },
                              deviceScaleFactor: Number(scale) });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + path.resolve(file));
  await p.waitForTimeout(900);
  if (errs.length) { console.error('page errors:', errs); process.exit(1); }
  const h = await p.evaluate(() => document.querySelector('.sheet').getBoundingClientRect().height | 0);
  await p.setViewportSize({ width: 2000, height: h + 10 });
  await p.waitForTimeout(400);
  await p.screenshot({ path: out });
  console.log(`  ${2000 * scale} x ${(h + 10) * scale}`);
  await b.close();
})();
