import {chromium} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
const base=process.env.CLIMATE_URL||'http://127.0.0.1:4334';
const descriptions=JSON.parse(await fs.readFile(new URL('../../data/normalized/map-descriptions.json',import.meta.url),'utf8'));
const routes=['/climate/','/climate/maps/',...Object.keys(descriptions).map(name=>`/climate/maps/${name.replace('.png','')}/`)];
const results=[];const browser=await chromium.launch();
await fs.mkdir('reports/climate-refresh',{recursive:true});
for(const width of [1280,320]){
 const context=await browser.newContext({viewport:{width,height:900}}); const page=await context.newPage();
 for(const route of routes){
  const response=await page.goto(base+route,{waitUntil:'networkidle'});
  await page.evaluate(async()=>{for(const img of document.images)img.loading='eager';await Promise.allSettled([...document.images].map(img=>img.decode()));});
  const scan=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']).analyze();
  const checks=await page.evaluate(()=>({brokenImages:[...document.images].filter(i=>!i.complete||!i.naturalWidth).map(i=>i.src),overflow:document.documentElement.scrollWidth>innerWidth+1,regions:document.querySelectorAll('.map-values-table tbody tr').length,mainH1:document.querySelectorAll('main h1').length}));
  const result={route,width,status:response.status(),violations:scan.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),...checks};results.push(result);
  if(route==='/climate/maps/'||route==='/climate/maps/prcp-7days/')await page.screenshot({path:`reports/climate-refresh/${route.includes('prcp')?'detail':'gallery'}-${width}.png`,fullPage:true});
 }
 await page.goto(base+'/climate/maps/');
 const links=await page.locator('.climate-maps figure > a').evaluateAll(anchors=>anchors.map(a=>a.getAttribute('href')));
 if(links.length!==27||links.some(h=>!h.startsWith('/climate/maps/')))throw new Error('Non-local or missing map links');
 await page.locator('.climate-maps figure > a').first().click();
 if(!page.url().includes('/climate/maps/prcp-7days/'))throw new Error('Map navigation failed');
 await page.getByRole('link',{name:'All Michigan Climate Maps',exact:true}).first().click();
 if(!page.url().endsWith('/climate/maps/'))throw new Error('Map back navigation failed');
 await context.close();
}
await browser.close();
await fs.writeFile('reports/climate-refresh/browser-checks.json',JSON.stringify({base,results},null,2));
const failures=results.filter(r=>r.status!==200||r.violations.length||r.brokenImages.length||r.overflow||r.mainH1!==1||(r.route.split('/').filter(Boolean).length===3&&r.regions!==7));
console.log(JSON.stringify({checks:results.length,failures},null,2));
if(failures.length)process.exitCode=1;
