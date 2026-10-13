export function localHref(url: string): string {
 const u = new URL(url, 'https://mawn.geo.msu.edu/');
 // Resolve historical aliases consistently with the shared navigation.
 if (['enviroweather.msu.edu','www.enviroweather.msu.edu'].includes(u.hostname) && u.pathname === '/') return 'https://enviroweather.msu.edu/';
 if (['greeen.msu.edu','www.greeen.msu.edu'].includes(u.hostname) && u.pathname === '/') return 'https://www.canr.msu.edu/project-greeen/';
 if (['maes.msu.edu','www.maes.msu.edu'].includes(u.hostname)) return 'https://www.canr.msu.edu/research/';
 if (['msue.msu.edu','www.msue.msu.edu'].includes(u.hostname)) return 'https://www.canr.msu.edu/outreach/';
 if (u.hostname === 'mawn.geo.msu.edu') {
  if (['/','/index.html','/index.asp'].includes(u.pathname)) return '/weather-network/';
  if (u.pathname === '/station.asp' && ['bnz','swm'].includes(u.searchParams.get('id') || '') && !u.searchParams.has('rt')) return `/weather-network/stations/${u.searchParams.get('id')}/`;
  if (u.pathname === '/report.asp') { const f=u.searchParams.get('fileid')||''; const kind:Record<string,string>={h:'hourly',d:'daily',m:'maintenance'}; if (/^(bnz|swm)[hdm]$/.test(f)) return `/weather-network/stations/${f.slice(0,3)}/${kind[f.slice(-1)]}/`; }
  if (['/rawdata/','/rawdata/3hr/','/rawdata/3hr/benzonia'].includes(u.pathname)) return u.pathname;
 }
 if (['www.agweather.geo.msu.edu','agweather.geo.msu.edu'].includes(u.hostname)) {
  if (['/','/index.html'].includes(u.pathname)) return '/agricultural-weather/';
  if (['/current/','/forecasts/','/info/'].includes(u.pathname)) return '/agricultural-weather'+u.pathname;
 }
 if (u.hostname === 'climate.geo.msu.edu') {
  if (['/','/index.html'].includes(u.pathname)) return '/climate/';
  if (u.pathname === '/climate_maps.html') return '/climate/maps/';
 }
 return url;
}
