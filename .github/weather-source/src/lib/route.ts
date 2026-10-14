import climateDescriptions from '../../data/normalized/map-descriptions.json';
import expanded from '../../data/expanded/network.json';
import products from '../../data/expanded/products.json';
export function localHref(url: string): string {
 const u = new URL(url, 'https://mawn.geo.msu.edu/');
 u.protocol='https:';
 if(u.hostname==='agweather.geo.msu.edu')u.hostname='www.agweather.geo.msu.edu';
 const map=Object.entries(climateDescriptions).find(([_,d])=>d.sourceUrl===u.href);
 if(map)return '/climate/maps/'+map[0].replace('.png','')+'/';
 const pages=products.pages as Record<string,any>;
 const page=pages[u.href.split('#')[0]]||pages[decodeURI(u.href.split('#')[0])];
 if(page)return page.path;
 if (['enviroweather.msu.edu','www.enviroweather.msu.edu'].includes(u.hostname) && u.pathname === '/') return 'https://enviroweather.msu.edu/';
 if (['greeen.msu.edu','www.greeen.msu.edu'].includes(u.hostname) && u.pathname === '/') return 'https://www.canr.msu.edu/project-greeen/';
 if (['maes.msu.edu','www.maes.msu.edu'].includes(u.hostname)) return 'https://www.canr.msu.edu/research/';
 if (['msue.msu.edu','www.msue.msu.edu'].includes(u.hostname)) return 'https://www.canr.msu.edu/outreach/';
 if (u.hostname === 'mawn.geo.msu.edu') {
  if (['/','/index.html','/index.asp'].includes(u.pathname)) return '/weather-network/';
  const id=u.searchParams.get('id');
  if (u.pathname === '/station.asp' && id && /^[a-z0-9]+$/i.test(id)) return `/weather-network/stations/${id}/${u.searchParams.has('rt')?'custom/?rt='+encodeURIComponent(u.searchParams.get('rt')!):''}`;
  if (u.pathname === '/report.asp') { const f=u.searchParams.get('fileid')||''; const kind:Record<string,string>={h:'hourly',d:'daily',m:'maintenance'}; if (/^[a-z0-9]+[hdm]$/.test(f)) return `/weather-network/stations/${f.slice(0,-1)}/${kind[f.slice(-1)]}/`; }
  if(u.pathname==='/mawn-sw.html')return '/weather-network/regions/southwest/';
  if(u.pathname==='/mawn-nw.html')return '/weather-network/regions/northwest/';
  const raw=(expanded as any).rawFiles?.[u.href];if(raw)return raw.path;
  if (['/rawdata/','/rawdata/3hr/','/rawdata/3hr/benzonia'].includes(u.pathname)) return u.pathname;
 }
 if (u.hostname==='www.agweather.geo.msu.edu') {
  if (['/','/index.html'].includes(u.pathname)) return '/agricultural-weather/';
  if (['/current/','/forecasts/','/info/'].includes(u.pathname)) return '/agricultural-weather'+u.pathname;
 }
 if (u.hostname === 'climate.geo.msu.edu') {
  if (['/','/index.html'].includes(u.pathname)) return '/climate/';
  if (u.pathname === '/climate_maps.html') return '/climate/maps/';
 }
 if(['mawn.geo.msu.edu','www.agweather.geo.msu.edu','climate.geo.msu.edu'].includes(u.hostname))return '/source-unavailable/?source='+encodeURIComponent(u.href);
 return url;
}
