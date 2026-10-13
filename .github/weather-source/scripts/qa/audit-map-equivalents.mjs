// Measure the actual map controls and all station-picker targets; no exceptions.
import fs from 'node:fs';
import path from 'node:path';
import {chromium} from '@playwright/test';
import {ROOT,startServer} from './static-server.mjs';
const {url,close}=await startServer();
const browser=await chromium.launch();
const checks=[];
for(const width of [320,1280]){
 const page=await browser.newPage({viewport:{width,height:900}});
 await page.route('**/*',r=>r.request().url().startsWith(url)?r.continue():r.abort());
 await page.goto(url+'/weather-network/');
 const controls=await page.locator('.station-map a').evaluateAll(es=>es.map(e=>{const r=e.getBoundingClientRect();return {name:e.getAttribute('aria-label'),width:r.width,height:r.height,qualifies:r.width>=24&&r.height>=24};}));
 await page.getByRole('button',{name:'Choose a Michigan weather station'}).click();
 checks.push({width,controls,stations:await page.evaluate(()=>{
  const links=[...document.querySelectorAll('.station-list a')];
  return [...document.querySelectorAll('.picker-stations a')].map(pin=>{
   const href=pin.getAttribute('href'),t=links.find(a=>a.getAttribute('href')===href),r=t?.getBoundingClientRect();
   const pr=pin.getBoundingClientRect();
   return {name:pin.textContent,href,width:pr.width,height:pr.height,equivalent:t?.textContent?.trim(),equivalentWidth:r?.width,equivalentHeight:r?.height,visible:!!pin.getClientRects().length,qualifies:pr.width>=24&&pr.height>=24&&!!r&&r.width>=24&&r.height>=24};
  });
 })});
 await page.close();
}
const result={standard:'WCAG 2.2 AA 2.5.8',reference:'https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html',reviewDisposition:'Original graphic preserved; crowded separate pin targets replaced by a full-map station chooser. Measured controls do not require target-size exceptions.',capturedAt:new Date().toISOString(),checks};
fs.writeFileSync(path.join(ROOT,'reports/silktide/map-target-controls.json'),JSON.stringify(result,null,2)+'\n');
await browser.close();await close();
const bad=checks.flatMap(c=>[...c.controls.filter(s=>!s.qualifies),...c.stations.filter(s=>!s.qualifies||!s.visible)]);
if(checks.some(c=>c.stations.length!==97))throw Error('Station inventory changed');
console.log(`${checks.map(c=>`${c.stations.length} stations at ${c.width}px`).join('; ')}; ${bad.length} missing or undersized equivalents.`);
if(bad.length)process.exitCode=1;
