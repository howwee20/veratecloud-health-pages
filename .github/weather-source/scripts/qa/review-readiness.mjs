// Supplemental local checks. Browser-engine/forced-colors emulation is named
// explicitly; it is not a claim of NVDA, Windows, or institutional approval.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {chromium,firefox,webkit} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {ROOT,startServer} from './static-server.mjs';
const dir=path.join(ROOT,'reports/oct14-review');fs.mkdirSync(dir,{recursive:true});
const walk=d=>fs.readdirSync(d,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(path.join(d,e.name)):e.name.endsWith('.html')?[path.join(d,e.name)]:[]);
const routes=walk(path.join(ROOT,'dist')).map(f=>'/'+path.relative(path.join(ROOT,'dist'),f).replaceAll(path.sep,'/').replace(/index.html$/,''));
const {url,close}=await startServer();
const report={capturedUTC:new Date().toISOString(),scope:routes,engines:[],pickerAxe:[],forcedColors:[],noJavaScript:null};
const homes=['/weather-network/','/agricultural-weather/','/climate/'];
try{
 for(const [name,engine] of Object.entries({chromium,firefox,webkit})){
  const browser=await engine.launch();
  const context=await browser.newContext();
  await context.route('**/*',r=>r.request().url().startsWith(url)?r.continue():r.abort());
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const entry={name,version:browser.version(),pages:[],picker:null};
  for(const route of routes){
   await page.goto(url+route);const checks=[];
   for(const width of [320,1280]){
    await page.setViewportSize({width,height:900});
    const geometry=await page.evaluate(()=>({width:innerWidth,document:document.documentElement.scrollWidth,title:document.title,language:document.documentElement.lang,main:document.querySelectorAll('main').length,h1:document.querySelectorAll('h1').length}));
    assert.equal(geometry.document,width,`${name} ${route} ${width}: page overflow`);assert.equal(geometry.main,1);assert.equal(geometry.h1,1);assert.equal(geometry.language,'en');
    checks.push(geometry);
    if(homes.includes(route))await page.screenshot({path:path.join(dir,`${name}-${route.split('/')[1]}-${width}.png`)});
   }
   if(name==='chromium')fs.writeFileSync(path.join(dir,`structure-${route.replace(/[^a-z0-9]/gi,'_')}.txt`),await page.locator('body').ariaSnapshot());
   entry.pages.push({route,checks});
  }
  await page.goto(url+'/weather-network/');
  for(const width of [320,1280]){
   await page.setViewportSize({width,height:900});
   const launch=page.getByRole('button',{name:'Choose a Michigan weather station'});await launch.focus();await page.keyboard.press('Space');
   const dialog=page.getByRole('dialog',{name:'Choose a weather station'});assert(await dialog.isVisible());
   assert.equal(await dialog.getByRole('link').count(),97);
   assert.equal(await page.getByLabel('Find a station').evaluate(e=>e===document.activeElement),true);
   const targets=await dialog.getByRole('link').evaluateAll(es=>es.map(e=>{const r=e.getBoundingClientRect();return {name:e.textContent,width:r.width,height:r.height};}));
   assert(targets.every(t=>t.width>=24&&t.height>=24));
   const ax=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']).analyze();
   report.pickerAxe.push({engine:name,width,violations:ax.violations,incomplete:ax.incomplete});assert.equal(ax.violations.length,0,`${name} picker axe ${width}`);
   await page.getByLabel('Find a station').fill('benzonia');assert.equal(await dialog.getByRole('link').count(),1);
   await page.keyboard.press('Escape');assert.equal(await dialog.isVisible(),false);assert.equal(await launch.evaluate(e=>e===document.activeElement),true);
   await page.keyboard.press('Enter');assert(await dialog.isVisible());await dialog.getByRole('button',{name:'Close',exact:true}).click();assert.equal(await dialog.isVisible(),false);
  }
  entry.picker='97 reachable station links; minimum target sizes; search; Enter/Space; Escape/Close; focus return';
  assert.equal(errors.length,0,`${name} script errors: ${errors.join(',')}`);
  report.engines.push(entry);console.log(`${name}: ${routes.length} routes and station chooser passed.`);
  if(name==='chromium'){
   await page.emulateMedia({forcedColors:'active',reducedMotion:'reduce'});
   for(const route of routes){
    await page.goto(url+route);await page.setViewportSize({width:320,height:900});
    await page.keyboard.press('Tab');const focus=await page.evaluate(()=>{const e=document.activeElement,r=e.getBoundingClientRect(),s=getComputedStyle(e);return {forcedColors:matchMedia('(forced-colors:active)').matches,outline:s.outlineStyle,outlineWidth:parseFloat(s.outlineWidth),visible:r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth};});
    assert(focus.forcedColors&&focus.visible&&focus.outlineWidth>=2);report.forcedColors.push({route,focus});
    await page.screenshot({path:path.join(dir,`forced-colors-${route.replace(/[^a-z0-9]/gi,'_')}.png`)});
   }
   const nojs=await browser.newContext({javaScriptEnabled:false});const np=await nojs.newPage();await np.goto(url+'/weather-network/');
   const link=np.getByRole('link',{name:'Choose a Michigan weather station'});await link.click();assert(new URL(np.url()).hash==='#station-directory');assert.equal(await np.locator('.station-list a').count(),119);report.noJavaScript='Map links to the complete permanent station directory';await nojs.close();
  }
  await browser.close();
 }
}catch(e){report.failure=e.stack;throw e;}finally{fs.writeFileSync(path.join(dir,'readiness-checks.json'),JSON.stringify(report,null,2)+'\n');await close();}
console.log('Supplemental review checks passed; raw evidence saved to reports/oct14-review/.');
