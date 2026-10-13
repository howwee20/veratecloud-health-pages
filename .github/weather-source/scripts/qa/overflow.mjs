// Developer utility: list elements that extend past the viewport. node scripts/qa/overflow.mjs <path> [width]
import { chromium } from '@playwright/test';
import { startServer } from './static-server.mjs';
const [route = '/', width = '320'] = process.argv.slice(2);
const server = await startServer();
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: Number(width), height: 800 } });
await page.goto(server.url + route, { waitUntil: 'networkidle' });
const out = await page.evaluate(() => {
  const vw = document.documentElement.clientWidth;
  const bad = [];
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.right > vw + 1 && r.width > 0) {
      let clipped = false;
      for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
        const o = getComputedStyle(p).overflowX;
        if (o === 'auto' || o === 'scroll' || o === 'hidden') { clipped = true; break; }
      }
      if (!clipped) bad.push(`${el.tagName.toLowerCase()}.${String(el.className.baseVal ?? el.className).replace(/\s+/g, '.')} right=${Math.round(r.right)} w=${Math.round(r.width)}`);
    }
  }
  return { vw, scrollWidth: document.documentElement.scrollWidth, bad: bad.slice(0, 15) };
});
console.log(JSON.stringify(out, null, 1));
await browser.close();
await server.close();
