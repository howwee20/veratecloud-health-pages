// Local-only evidence for this build. Never contacts the original hosts.
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {ROOT,startServer} from './static-server.mjs';
const {url:origin,close}=await startServer();
const browser=await chromium.launch();
const out=path.join(ROOT,'reports/screenshots');fs.mkdirSync(out,{recursive:true});
const pages=[['mawn','/weather-network/'],['agweather','/agricultural-weather/'],['current-weather','/agricultural-weather/current/'],['climate','/climate/'],['climate-maps','/climate/maps/'],['swmrec','/weather-network/stations/swm/'],['daily','/weather-network/stations/bnz/daily/']];
const checks=[];
for (const width of [1280,320]) {
 const context=await browser.newContext({viewport:{width,height:900}});
 await context.route('**/*',r=>r.request().url().startsWith(origin)?r.continue():r.abort());
 const page=await context.newPage();
 for(const [name,route] of pages){
  await page.goto(origin+route);await page.locator('img').evaluateAll(imgs=>Promise.all(imgs.filter(i=>i.getBoundingClientRect().top<innerHeight).map(i=>i.decode().catch(()=>{}))));
  const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']).analyze();
  checks.push({route,width,timestamp:axe.timestamp,violations:axe.violations,incomplete:axe.incomplete,passes:axe.passes.map(r=>r.id)});
  await page.screenshot({path:path.join(out,`${name}-${width}.png`),fullPage:false});
 }
 await context.close();
}
fs.writeFileSync(path.join(ROOT,'reports/accessibility-results.json'),JSON.stringify({scope:'Seven representative routes at 1280 and 320 pixels; all 20 routes additionally checked in e2e-results.json',engine:'axe-core / Chromium',checks},null,2)+'\n');
await browser.close();await close();
console.log(`Saved ${checks.length} screenshots and accessibility checks; ${checks.reduce((n,c)=>n+c.violations.length,0)} automated violations.`);
if(checks.some(c=>c.violations.length)) process.exitCode=1;
