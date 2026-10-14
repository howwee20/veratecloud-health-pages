import fs from 'node:fs';
import path from 'node:path';
import {test,expect,ROOT} from './helpers';
const network=JSON.parse(fs.readFileSync(path.join(ROOT,'data/expanded/network.json'),'utf8'));
test('all 119 station entries stay local and have meaningful report destinations',async({page,request})=>{
 await page.goto('/weather-network/');
 const links=await page.locator('.station-list a').evaluateAll(es=>es.map(a=>a.getAttribute('href')!));
 expect(links).toHaveLength(119);
 for(const href of links){expect(href).toMatch(/^\/weather-network\/stations\/[a-z0-9]+\/$/);expect((await request.get(href)).status()).toBe(200);}
});
for(const id of ['swm','bnz','alt','bat','ent','clx'])test(`local custom reports filter, validate and download ${id}`,async({page})=>{
 await page.goto(`/weather-network/stations/${id}/custom/?rt=60`);
 const d=network.reports[id].hourly;
 if(!d.rows.length){await expect(page.locator('main')).toContainText('No recent observation');return;}
 await expect(page.getByLabel('Report type:',{exact:true})).toHaveValue('hourly');
 const date=d.rows.at(-1).isoDate;
 await page.getByLabel('Start date:',{exact:true}).fill(date);await page.getByLabel('End date:',{exact:true}).fill(date);await page.getByRole('button',{name:'Generate report',exact:true}).click();
 const rows=d.rows.filter(r=>r.isoDate===date);
 await expect(page.getByRole('status')).toContainText(`Showing ${rows.length} hourly observations`);
 await expect(page.locator('#custom-hourly tbody tr:not([hidden])')).toHaveCount(rows.length);
 const downloadPromise=page.waitForEvent('download');await page.locator('[data-custom-report="hourly"] a').click();const file=await(await downloadPromise).path();const csv=fs.readFileSync(file!,'utf8');expect(csv.trim().split('\r\n')).toHaveLength(rows.length+1);
 expect(new URL(page.url()).pathname).toBe(`/weather-network/stations/${id}/custom/`);
});
test('maintenance dates and undated source warning are visible',async({page})=>{
 await page.goto('/weather-network/stations/ent/maintenance/');await expect(page.locator('main')).toContainText('center-pivot irrigator');
 await expect(page.locator('.maintenance-entry h2 time').first()).toHaveText(network.reports.ent.maintenance.entries[0].dateRaw);
});
test('agricultural source product destinations are local',async({page,request})=>{
 for(const kind of ['current','forecasts']){
  await page.goto(`/agricultural-weather/${kind}/`);
  const links=await page.locator('.product-section a').evaluateAll(es=>es.map(a=>a.getAttribute('href')!));
  expect(links.filter(u=>/agweather\.geo\.msu\.edu/.test(u))).toEqual([]);
  for(const href of new Set(links.filter(u=>u.startsWith('/'))))expect((await request.get(href)).status()).toBe(200);
 }
});
