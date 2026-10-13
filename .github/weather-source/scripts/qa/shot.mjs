// Developer utility: node scripts/qa/shot.mjs <path> [width] [out.png] [--full]
import { chromium } from '@playwright/test';
import { startServer } from './static-server.mjs';
const [route = '/', width = '1280', out = 'shot.png'] = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const server = await startServer();
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: Number(width), height: 900 } });
const problems = [];
page.on('console', (m) => ['error', 'warning'].includes(m.type()) && problems.push(`${m.type()}: ${m.text()}`));
page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
page.on('requestfailed', (r) => problems.push(`requestfailed: ${r.url()}`));
await page.goto(server.url + route, { waitUntil: 'networkidle' });
const sel = process.argv.find((a) => a.startsWith('--sel='))?.slice(6);
if (sel) await page.locator(sel).first().screenshot({ path: out });
else await page.screenshot({ path: out, fullPage: process.argv.includes('--full') });
console.log(JSON.stringify({ title: await page.title(), scrollWidth: await page.evaluate(() => document.documentElement.scrollWidth), problems }));
await browser.close();
await server.close();
