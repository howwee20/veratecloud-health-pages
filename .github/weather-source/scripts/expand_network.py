"""Maintainer-authorized, bounded GET capture of the published station directory.
At most one request per second on MAWN. Raw responses, hashes and failures persist.
No historical database, logger, or write endpoint is accessed.
"""
from pathlib import Path
import sys,json,time,hashlib,csv,os
from datetime import datetime,timezone
from urllib.parse import urlparse
import httpx
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'scripts'))
from pipeline import parsers as P
OUT=ROOT/'data/expanded'; OUT.mkdir(exist_ok=True)
CACHE=OUT/'responses';CACHE.mkdir(exist_ok=True)
idxfile=OUT/'network-receipts.json'
receipts=json.loads(idxfile.read_text()) if idxfile.exists() else {}
failures=[];last=0;requests=0
client=httpx.Client(timeout=25,follow_redirects=True,headers={'User-Agent':'VerateCloudWeatherReview/1.0 (maintainer-authorized read-only refresh)'})
def save(path,data):
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)
def immutable(raw,rec):
 if raw is None:return raw,rec
 digest=hashlib.sha256(raw).hexdigest();path=CACHE/('content-'+digest+'.bin')
 if not path.exists():path.write_bytes(raw)
 return raw,{**rec,'file':str(path.relative_to(ROOT)),'sha256':digest}
def get(url,asset=False):
 global last,requests
 assert urlparse(url).hostname=='mawn.geo.msu.edu'
 old=receipts.get(url);target=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.bin')
 ttl=86400*7 if asset else int(os.environ.get('CAPTURE_TTL','1800'))
 if old and target.exists() and time.time()-datetime.fromisoformat(old['retrievedAtUtc']).timestamp()<ttl:return immutable(target.read_bytes(),old)
 if os.environ.get('CAPTURE_OFFLINE'):
  return immutable(target.read_bytes(),old) if old and target.exists() else (None,{'url':url,'id':'unavailable','retrievedAtUtc':None,'file':'','sha256':''})
 if requests>=1100:raise RuntimeError('Bounded capture request ceiling reached')
 time.sleep(max(0,1.1-(time.monotonic()-last)));last=time.monotonic();requests+=1
 try:
  r=client.get(url);r.raise_for_status()
  if not r.content:raise ValueError('Empty response')
  rec={'id':'network-'+hashlib.sha256(url.encode()).hexdigest()[:12],'url':url,'file':str(target.relative_to(ROOT)),'sha256':hashlib.sha256(r.content).hexdigest(),'retrievedAtUtc':datetime.now(timezone.utc).isoformat()}
  target.write_bytes(r.content);receipts[url]=rec;save(idxfile,receipts)
  return immutable(r.content,rec)
 except Exception as e:
  failures.append({'url':url,'error':str(e),'retainedPrevious':bool(old and target.exists())})
  if old and target.exists():return immutable(target.read_bytes(),old)
  return None,{'url':url,'id':'unavailable','retrievedAtUtc':None,'file':'','sha256':''}
stations=json.loads((ROOT/'data/normalized/stations.json').read_text())['stations']
bundle={'stations':{},'reports':{},'failures':failures}
oldfile=OUT/'network.json'
oldbundle=json.loads(oldfile.read_text()) if oldfile.exists() else {'stations':{},'reports':{}}
bundle['stations']=dict(oldbundle['stations']);bundle['reports']=dict(oldbundle['reports'])
for n,entry in enumerate(stations):
 sid=entry['id'];raw,receipt=get(entry['legacyUrl']);d=None
 if raw:
  try:d=P.parse_station(raw,entry['legacyUrl'])
  except Exception as e:failures.append({'url':entry['legacyUrl'],'error':'Station parser: '+str(e)})
 if not d:
  previous=oldbundle['stations'].get(sid)
  if previous and not previous.get('unavailable'):receipt=previous['source']
  d=previous or {'id':sid,'stationName':entry['name'],'city':entry['name'],'location':'Not provided by source','latitude':{'raw':'Not provided'},'longitude':{'raw':'Not provided'},'elevation':{'raw':'Not provided'},'reportLinks':[],'customReportTypes':[],'photoUrl':None,'unavailable':True}
 d.update(legacyUrl=entry['legacyUrl'],source=receipt,group=entry['group'],retiredDateRaw=entry['retiredDateRaw'])
 if d.get('photoUrl'):
  photo,_=get(d['photoUrl'],True)
  if photo and photo[:3]==b'\xff\xd8\xff':
   dest=ROOT/f'public/media/station-{sid}.jpg';dest.write_bytes(photo);d['localPhoto']=f'/media/station-{sid}.jpg'
  else:d['localPhoto']=None
 rep={}
 for kind,suffix,parser in [('hourly','h',P.parse_hourly),('daily','d',P.parse_daily),('maintenance','m',P.parse_maintenance)]:
  link=next((l for l in d['reportLinks'] if l['fileid']==sid+suffix),None)
  content,rec=get(link['url']) if link else (None,receipt)
  parsed=None
  if content:
   try:parsed=parser(content)
   except Exception as e:
    soup=P.soup_of(content);main=soup.select_one('td.courier2') or soup.find('pre')
    text=main.get_text('\n',strip=True) if main else ''
    failures.append({'url':rec['url'],'error':'Report parser: '+str(e),'textPreserved':bool(text)})
    if text:parsed={'rawText':text,'unstructured':True}
  previous=oldbundle['reports'].get(sid,{}).get(kind)
  if (parsed is None or parsed.get('unstructured')) and previous and (previous.get('rows') or previous.get('entries')):
   parsed={**previous,'retainedPrevious':True};rec=previous['source']
  if parsed is None:parsed={'unavailable':True,'rawText':'No '+kind+' report was supplied by the source for this station.'}
  parsed={'source':rec,'rows':[],'columns':[],'entries':[],'footnotes':[],'location':[d['location'],d['city']],'timezoneLabel':'',**parsed}
  rep[kind]=parsed
  downloads=ROOT/'public/downloads';downloads.mkdir(exist_ok=True)
  if kind=='maintenance':(downloads/f'{sid}-maintenance.txt').write_text(parsed.get('rawText','')+'\n')
  elif parsed['rows']:
   with (downloads/f'{sid}-{kind}.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['date']+(['time_'+parsed['timezoneLabel']] if kind=='hourly' else [])+[c['sourceHeader'] for c in parsed['columns']])
    for row in parsed['rows']:w.writerow([row['dateRaw']]+([row['timeRaw']] if kind=='hourly' else [])+[row['cells'][c['key']]['raw'] for c in parsed['columns']])
 bundle['stations'][sid]=d;bundle['reports'][sid]=rep
 if (n+1)%10==0:save(oldfile,bundle)
 print(f"{n+1}/{len(stations)} {sid}: "+', '.join(f"{k}={len(v['rows']) or len(v['entries']) or ('text' if v.get('unstructured') else 'unavailable')}" for k,v in rep.items()),flush=True)
# Published recent raw files, exactly those linked in the captured 3hr directory.
rawindex=json.loads((ROOT/'data/normalized/rawdata.json').read_text())['directories']['3hr']['entries']
bundle['rawFiles']={}
for e in rawindex:
 if e['type']!='file':continue
 raw,rec=get(e['url'])
 if raw:
  name=e['name'];assert '/' not in name and name not in ('.','..')
  dest=ROOT/'public/downloads/raw-3hr'/f'{name}.txt';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
  bundle['rawFiles'][e['url']]={'path':f'/downloads/raw-3hr/{name}.txt','source':rec}
bundle['completedAtUtc']=datetime.now(timezone.utc).isoformat();save(oldfile,bundle)
print('Completed',len(bundle['stations']),'stations;',len(failures),'source/parser exceptions;',requests,'requests',flush=True)
