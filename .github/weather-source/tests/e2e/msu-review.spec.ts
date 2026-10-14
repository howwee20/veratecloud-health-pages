import { test, expect, ROUTES } from './helpers';

const allRoutes=[...ROUTES,'/404.html'];
// These are browser geometry/interaction checks, not a human or screen-reader sign-off.
for (const route of allRoutes) {
 test(`MSU reflow and text-spacing geometry ${route}`,async({page})=>{
  await page.goto(route);
  for(const size of [{width:320,height:256},{width:683,height:384},{width:768,height:1024},{width:1280,height:900}]){
   await page.setViewportSize(size);
   expect(await page.evaluate(()=>document.documentElement.scrollWidth),`${size.width}px document width`).toBe(size.width);
  }
  for(const width of [320,1280]){
   await page.setViewportSize({width,height:900});
   await page.evaluate(()=>{
    for(const el of document.querySelectorAll<HTMLElement>('body *')){
     if(el.closest('svg') || el.classList.contains('visually-hidden'))continue;
     el.style.setProperty('line-height','1.5','important');
     el.style.setProperty('letter-spacing','0.12em','important');
     el.style.setProperty('word-spacing','0.16em','important');
     if(el.tagName==='P')el.style.setProperty('margin-bottom','2em','important');
    }
   });
   const issues=await page.evaluate(()=>Array.from(document.querySelectorAll<HTMLElement>('body *')).filter(el=>{
    if(el.closest('.table-wrap,.map-values-table,svg,.visually-hidden')||el.classList.contains('skip-link')||!el.clientWidth)return false;
    const s=getComputedStyle(el);return s.display!=='inline' && el.scrollWidth>el.clientWidth+2;
   }).map(el=>({tag:el.tagName,cls:el.className,text:el.textContent?.slice(0,70),width:el.clientWidth,scroll:el.scrollWidth})));
   expect(issues,`text spacing at ${width}px`).toEqual([]);
  }
 });
}

for(const route of allRoutes){
 test(`keyboard focus remains visible at 320x256 ${route}`,async({page})=>{
  test.setTimeout(60000);
  await page.setViewportSize({width:320,height:256});await page.goto(route);
  const count=await page.locator('a[href],button,select,input,summary,[tabindex="0"]').evaluateAll(es=>es.filter(e=>e.getClientRects().length && getComputedStyle(e).visibility!=='hidden' && (!e.closest('details:not([open])') || e.tagName==='SUMMARY')).length);
  for(let i=0;i<count;i++){
   await page.keyboard.press('Tab');
   const focus=await page.evaluate(()=>{
    const e=document.activeElement as HTMLElement, r=e.getBoundingClientRect(),s=getComputedStyle(e);
    return {tag:e.tagName,name:e.getAttribute('aria-label')||e.textContent?.trim().slice(0,60),visible:r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth,outline:parseFloat(s.outlineWidth),url:location.pathname};
   });
   expect(focus.url).toBe(route);expect(focus.tag).not.toBe('BODY');expect(focus.visible,JSON.stringify(focus)).toBe(true);expect(focus.outline,JSON.stringify(focus)).toBeGreaterThanOrEqual(2);
  }
  await page.keyboard.press('Shift+Tab');expect(await page.evaluate(()=>document.activeElement?.tagName)).not.toBe('BODY');
 });
}

test('station chooser is keyboard operable and all map stations have usable links',async({page})=>{
 await page.goto('/weather-network/');
 const launch=page.getByRole('button',{name:'Choose a Michigan weather station'});
 await launch.focus(); await page.keyboard.press('Space');
 const dialog=page.getByRole('dialog',{name:'Choose a weather station'});
 await expect(dialog).toBeVisible();
 await expect(page.getByLabel('Find a station')).toBeFocused();
 await expect(dialog.locator('.picker-stations a')).toHaveCount(97);
 const bad=await dialog.locator('.picker-stations a').evaluateAll(es=>es.filter(e=>{const r=e.getBoundingClientRect();return r.width<24||r.height<24;}).map(e=>e.textContent));
 expect(bad).toEqual([]);
 // Each map station still has its matching permanent text link outside the dialog.
 expect(await page.evaluate(()=>{
  const links=[...document.querySelectorAll<HTMLAnchorElement>('.station-list a')];
  return [...document.querySelectorAll<HTMLAnchorElement>('.picker-stations a')].filter(a=>!links.some(t=>t.getAttribute('href')===a.getAttribute('href'))).map(a=>a.textContent);
 })).toEqual([]);
 await page.getByLabel('Find a station').fill('benzonia');
 await expect(dialog.getByRole('link')).toHaveCount(1);
 await expect(dialog.getByRole('status')).toHaveText('1 station');
 await page.getByLabel('Find a station').fill('no-such-station');
 await expect(dialog.getByRole('status')).toContainText('No stations found');
 await page.keyboard.press('Escape');await expect(dialog).not.toBeVisible();await expect(launch).toBeFocused();
 await page.keyboard.press('Enter');await expect(dialog).toBeVisible();
 await page.getByLabel('Find a station').fill('benzonia');
 await dialog.getByRole('link',{name:'Benzonia',exact:true}).click();
 await expect(page).toHaveURL(/\/weather-network\/stations\/bnz\/$/);
});
