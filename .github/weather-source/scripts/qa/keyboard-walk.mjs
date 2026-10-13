// Developer utility: tab through a page and report the focus order and whether
// each focused element shows a visible outline. node scripts/qa/keyboard-walk.mjs <path> [count] [shot.png]
import { chromium } from '@playwright/test';
import { startServer } from './static-server.mjs';
const [route = '/', count = '14', shot] = process.argv.slice(2);
const server = await startServer();
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
await page.goto(server.url + route, { waitUntil: 'networkidle' });
const seen = [];
for (let i = 0; i < Number(count); i += 1) {
  await page.keyboard.press('Tab');
  seen.push(await page.evaluate(() => {
    const el = document.activeElement;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''} "${(el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 34)}" outline=${cs.outlineStyle}/${cs.outlineWidth} ${Math.round(r.width)}x${Math.round(r.height)} inView=${r.top >= 0 && r.bottom <= innerHeight}`;
  }));
  if (shot && i === 3) await page.screenshot({ path: shot, clip: { x: 0, y: 0, width: 1280, height: 260 } });
}
console.log(seen.join('\n'));
await browser.close();
await server.close();
