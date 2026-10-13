import fs from 'node:fs';
import path from 'node:path';
import AxeBuilder from '@axe-core/playwright';
import {test, expect, ROUTES, ROOT} from './helpers';
for(const route of [...ROUTES, '/404.html']) {
 for (const width of [1280,320]) test(`WCAG 2.2 AA and reflow ${width} ${route}`,async({page,audit},testInfo)=>{
  await page.setViewportSize({width,height:900});await page.goto(route);
  const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']).analyze();
  fs.mkdirSync(path.join(ROOT,'reports/axe'),{recursive:true});
  fs.writeFileSync(path.join(ROOT,'reports/axe',`${route.replace(/[^a-z0-9]/gi,'_')}-${width}.json`),JSON.stringify({route,width,engine:results.testEngine,timestamp:results.timestamp,violations:results.violations,incomplete:results.incomplete,passes:results.passes.map(r=>r.id)},null,2));
  expect(results.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))).toEqual([]);
  expect(await page.evaluate(()=>({width:document.documentElement.scrollWidth,inner:innerWidth,overflow:Array.from(document.querySelectorAll('body *')).filter(e=>e.scrollWidth>e.clientWidth+1 && !e.closest('.table-wrap')).slice(0,12).map(e=>({tag:e.tagName,cls:e.className,width:e.clientWidth,scroll:e.scrollWidth,text:e.textContent?.slice(0,80)}))}))).toEqual(expect.objectContaining({width:width}));
  await expect(page.locator('main')).toHaveCount(1);await expect(page.locator('h1')).toHaveCount(1);
  expect(audit.pageErrors).toEqual([]);expect(audit.consoleErrors).toEqual([]);expect(audit.badResponses).toEqual([]);expect(audit.externalRequests).toEqual([]);
 });
}
test('station map and complete directory retain real station destinations',async({page})=>{
 await page.goto('/weather-network/'); await expect(page.locator('.station-list a')).toHaveCount(119); await expect(page.locator('.picker-stations a')).toHaveCount(97);
 await expect(page.getByRole('link',{name:'Zoom to Southwest Region',exact:true})).toHaveAttribute('href','https://mawn.geo.msu.edu/mawn-sw.html');
 await expect(page.getByRole('link',{name:'Zoom to Northwest Region',exact:true})).toHaveAttribute('href','https://mawn.geo.msu.edu/mawn-nw.html');
 await page.locator('.station-list').getByRole('link',{name:'Benzonia',exact:true}).click();await expect(page.locator('h1')).toHaveText('benzonia');
 await page.getByRole('link',{name:'Hourly Data',exact:true}).click();await expect(page.locator('#hourly-table tbody tr:not([hidden])')).toHaveCount(JSON.parse(fs.readFileSync(path.join(ROOT,"data/normalized/bnz-hourly.json"),"utf8")).rows.length);
});
for(const id of ['bnz','swm']) for(const kind of ['hourly','daily']) test(`values and date filter ${id} ${kind}`,async({page})=>{
 const d=JSON.parse(fs.readFileSync(path.join(ROOT,`data/normalized/${id}-${kind}.json`),'utf8'));
 await page.goto(`/weather-network/stations/${id}/${kind}/`);
 await expect(page.locator('tbody tr:not([hidden])')).toHaveCount(d.rows.length);
 const cells=await page.locator('tbody tr').evaluateAll(rows=>rows.map(row=>Array.from(row.querySelectorAll('td')).map(td=>td.querySelector('[aria-hidden]')?.textContent??td.textContent)));
 expect(cells).toEqual(d.rows.map((r:any)=>d.columns.map((c:any)=>r.cells[c.key].raw)));
 const date=d.rows[0].isoDate;await page.getByLabel('Date:',{exact:true}).selectOption(date);
 await expect(page.locator('tbody tr:not([hidden])')).toHaveCount(d.rows.filter((r:any)=>r.isoDate===date).length);
 await page.getByLabel('Date:',{exact:true}).selectOption('all');await expect(page.locator('tbody tr:not([hidden])')).toHaveCount(d.rows.length);
 const download=page.waitForEvent('download');await page.getByRole('link',{name:'Download CSV'}).click();expect((await download).suggestedFilename()).toMatch(/\.csv$/);
});
test('keyboard skip link and custom report require explicit submit',async({page})=>{
 await page.goto('/weather-network/stations/swm/');await page.keyboard.press('Tab');await expect(page.getByRole('link',{name:'Skip to main content'})).toBeFocused();await page.keyboard.press('Enter');await expect(page.locator('main')).toBeFocused();
 await page.getByLabel('Select report type:').selectOption('60');await expect(page).toHaveURL(/stations\/swm\/(#main-content)?$/);
 await expect(page.locator('form')).toHaveAttribute('action','https://mawn.geo.msu.edu/station.asp');await expect(page.getByRole('button',{name:'Open report'})).toBeVisible();
});
test('all product links and climate images retained',async({page})=>{
 await page.goto('/agricultural-weather/current/');await expect(page.locator('.product-section a')).toHaveCount(75);
 await page.goto('/agricultural-weather/forecasts/');await expect(page.locator('.product-section a')).toHaveCount(34);
 await page.goto('/climate/maps/');await expect(page.locator('.climate-maps img')).toHaveCount(27); await expect(page.locator('.map-description')).toHaveCount(27); await page.locator('.map-description summary').first().click(); await expect(page.locator('.map-description').first()).toContainText('October 5–11, 2026');
});
test('no JavaScript retains all report data',async({browser,baseURL})=>{
 const context=await browser.newContext({javaScriptEnabled:false});const page=await context.newPage();await page.goto(baseURL+'/weather-network/stations/swm/hourly/');await expect(page.locator('tbody tr')).toHaveCount(JSON.parse(fs.readFileSync(path.join(ROOT,"data/normalized/swm-hourly.json"),"utf8")).rows.length);await context.close();
});
