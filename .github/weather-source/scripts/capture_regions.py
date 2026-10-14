"""Capture the two region maps linked by the MAWN homepage, with named station links."""
import json,time,hashlib
from pathlib import Path
from urllib.parse import urljoin,urlparse,parse_qs
from datetime import datetime,timezone
import httpx
from bs4 import BeautifulSoup
R=Path(__file__).resolve().parent.parent
out={}
with httpx.Client(timeout=25,follow_redirects=True) as c:
 for region,slug in [('southwest','sw'),('northwest','nw')]:
  url=f'https://mawn.geo.msu.edu/mawn-{slug}.html';time.sleep(1.1);res=c.get(url);res.raise_for_status();s=BeautifulSoup(res.content,'lxml')
  areas=[a for a in s.find_all('area',href=True) if 'station.asp?' in a['href']]
  ids=[]
  for a in areas:
   sid=parse_qs(urlparse(urljoin(url,a['href'])).query).get('id',[None])[0]
   if sid and sid not in ids:ids.append(sid)
  station_map=areas[0].find_parent('map') if areas else None
  map_name=station_map.get('name') or station_map.get('id') if station_map else None
  img=next((x for x in s.find_all('img',src=True) if x.get('usemap','').lstrip('#')==map_name),None)
  if not img or not ids:raise ValueError('Region source map changed')
  src=urljoin(url,img['src']);time.sleep(1.1);data=c.get(src);data.raise_for_status()
  suffix='.jpg' if data.content.startswith(b'\xff\xd8') else '.gif' if data.content.startswith(b'GIF') else '.png'
  path=f'/media/region-{region}{suffix}';(R/'public'/path.lstrip('/')).write_bytes(data.content)
  out[region]={'url':url,'image':path,'stationIds':ids,'retrievedAtUtc':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(data.content).hexdigest()}
(R/'data/expanded/regions.json').write_text(json.dumps(out,indent=2)+'\n')
print('Captured regional maps:',{k:len(v['stationIds']) for k,v in out.items()})
