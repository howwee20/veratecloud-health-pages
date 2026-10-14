import {chromium,firefox,webkit} from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
const root=process.cwd();const base=process.env.AUDIT_URL||'http://127.0.0.1:4336';
const network=JSON.parse(fs.readFileSync('data/expanded/network.json','utf8'));
const products=JSON.parse(fs.readFileSync('data/expanded/products.json','utf8'));
const routes=['/weather-network/','/agricultural-weather/','/agricultural-weather/current/','/agricultural-weather/forecasts/','/climate/','/climate/maps/','/climate/maps/prcp-7days/','/climate/maps/tmean-30days/','/weather-network/regions/southwest/','/weather-network/regions/northwest/','/rawdata/','/rawdata/3hr/',...['swm','bnz','alt','ent','llu','clx','gde','stv'].flatMap(id=>['','hourly/','daily/','maintenance/','custom/'].map(k=>`/weather-network/stations/${id}/${k}`)),...Object.values(products.pages).filter(p=>p.text).slice(0,5).map(p=>p.path)];
const checks=[];
for(const [name,engine] of Object.entries({chromium,firefox,webkit})){
 const browser=await engine.launch();
 for(const width of [1280,320]){
 const context=await browser.newContext({viewport:{width,height:900}});const page=await context.newPage();let errors=[];page.on('pageerror',e=>errors.push(String(e)));page.on('response',r=>{if(r.status()>=400)errors.push(`${r.status()} ${r.url()}`)});
 for(const route of routes){
  errors=[];try{const r=await page.goto(base+route,{waitUntil:'load'});await page.locator('img').evaluateAll(async imgs=>{await Promise.all(imgs.map(async i=>{i.loading='eager';try{await i.decode()}catch{}}))});const state=await page.evaluate(()=>({title:document.title,h1:document.querySelectorAll('h1').length,overflow:document.documentElement.scrollWidth>innerWidth,images:[...document.images].filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.src)}));checks.push({engine:name,width,route,status:r.status(),...state,errors:[...errors]});}catch(e){checks.push({engine:name,width,route,errors:[String(e)]})}
 }
 await context.close();}
 await browser.close();console.log(name,'checked',checks.length);
}
fs.mkdirSync('reports/expanded',{recursive:true});fs.writeFileSync('reports/expanded/cross-browser.json',JSON.stringify({checkedAtUtc:new Date().toISOString(),base,checks},null,2));const bad=checks.filter(x=>x.errors.length||x.status!==200||x.h1!==1||x.overflow||x.images?.length);console.log(JSON.stringify({checks:checks.length,failures:bad},null,2));if(bad.length)process.exitCode=1;
