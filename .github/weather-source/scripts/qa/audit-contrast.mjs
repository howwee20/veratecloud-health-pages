// Supplement axe's indeterminate text-contrast checks using rendered CSS colors.
// This does not inspect image pixels or replace a human contrast review.
import fs from 'node:fs';
import path from 'node:path';
import {chromium} from '@playwright/test';
import {ROOT,startServer} from './static-server.mjs';
const {url,close}=await startServer();const browser=await chromium.launch();
const rows=[];
for(const file of fs.readdirSync(path.join(ROOT,'reports/axe'))){
 const scan=JSON.parse(fs.readFileSync(path.join(ROOT,'reports/axe',file),'utf8'));
 const nodes=scan.incomplete.filter(r=>r.id==='color-contrast').flatMap(r=>r.nodes);
 if(!nodes.length)continue;
 const page=await browser.newPage({viewport:{width:scan.width,height:900}});
 await page.route('**/*',r=>r.request().url().startsWith(url+'/')?r.continue():r.abort());await page.goto(url+scan.route);
 for(const node of nodes){
  const target=node.target[0];const data=await page.locator(target).evaluate(el=>{
   const rgb=s=>{const n=s.match(/[\d.]+/g)?.map(Number);return n?.length>=3?n:null;};
   const s=getComputedStyle(el),fg=rgb(s.color);let bg=null,image=false;
   for(let p=el;p;p=p.parentElement){const c=getComputedStyle(p),v=rgb(c.backgroundColor);if(c.backgroundImage!=='none')image=true;if(v && (v[3]??1)===1){bg=v;break;}}
   if(!bg)bg=[255,255,255];
   const luminance=c=>c.slice(0,3).map(x=>x/255).map(x=>x<=0.04045?x/12.92:((x+0.055)/1.055)**2.4).reduce((n,v,i)=>n+v*[0.2126,0.7152,0.0722][i],0);
   const a=luminance(fg),b=luminance(bg),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
   const size=parseFloat(s.fontSize),bold=parseInt(s.fontWeight)>=700,required=size>=24||(bold&&size>=18.66)?3:4.5;
   return {text:el.textContent?.trim().slice(0,80),foreground:fg,background:bg,ratio,required,backgroundImage:image,pass:!image&&ratio>=required};
  });rows.push({route:scan.route,width:scan.width,target,...data});
 }
 await page.close();
}
await browser.close();await close();
const result={timestamp:new Date().toISOString(),method:'CSS color calculations for axe incomplete text-contrast nodes; no image pixel or human review',count:rows.length,failures:rows.filter(r=>!r.pass),minimumRatio:Math.min(...rows.map(r=>r.ratio)),rows};
fs.writeFileSync(path.join(ROOT,'reports/contrast-supplement.json'),JSON.stringify(result,null,2)+'\n');console.log(`${rows.length} indeterminate nodes: ${result.failures.length} unresolved CSS contrast failures; minimum ratio ${result.minimumRatio.toFixed(2)}:1.`);
if(result.failures.length)process.exitCode=1;
