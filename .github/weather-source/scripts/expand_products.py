"""Capture linked agricultural weather products and public reference pages.
Bounded published URLs only, GET, one request per second per host. No scripts run.
"""
from pathlib import Path
import json,time,hashlib,os,re,html
from datetime import datetime,timezone
from urllib.parse import urlparse,urljoin,urldefrag
from bs4 import BeautifulSoup,Comment
import httpx
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'data/expanded';OUT.mkdir(exist_ok=True);CACHE=OUT/'products-responses';CACHE.mkdir(exist_ok=True)
file=OUT/'products.json';old=json.loads(file.read_text()) if file.exists() else {'pages':{},'assets':{}}
data={'pages':{},'assets':{},'failures':old.get('failures',[]) if os.environ.get('CAPTURE_OFFLINE') else []};last={};requests=0
client=httpx.Client(timeout=25,follow_redirects=True,headers={'User-Agent':'VerateCloudWeatherReview/1.0 (maintainer-authorized read-only refresh)'})
HOSTS={'www.agweather.geo.msu.edu','agweather.geo.msu.edu','climate.geo.msu.edu'}
def canonical(u):
 u=urldefrag(u)[0].replace('http://','https://').replace('https://agweather.geo.msu.edu','https://www.agweather.geo.msu.edu');u=u.replace('/semcog/sem/semcog/sem/','/semcog/sem/');return u

def key(u):return hashlib.sha256(u.encode()).hexdigest()[:16]
def route(u):return ('/climate/pages/' if urlparse(u).hostname=='climate.geo.msu.edu' else '/agricultural-weather/products/')+key(u)+'/'
save_count=0
def save(force=False):
 global save_count
 save_count+=1
 if not force and save_count%20:return
 tmp=file.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(file)
def fetch(url,previous=None):
 global requests
 host=urlparse(url).hostname
 assert host in HOSTS
 path=CACHE/(key(url)+'.bin')
 ttl=int(os.environ.get('CAPTURE_TTL','1800')) if any(x in url for x in ['report.asp','fcst.asp','/current/','/forecasts/','/images/maxtemp','/images/mintemp']) else 86400*30
 if previous and path.exists() and time.time()-datetime.fromisoformat(previous['retrievedAtUtc']).timestamp()<ttl:return path.read_bytes(),previous
 if requests>=1800:raise RuntimeError('Product capture ceiling')
 if os.environ.get('CAPTURE_OFFLINE'):
  return (path.read_bytes(),previous) if previous and path.exists() else (None,None)
 time.sleep(max(0,1.1-(time.monotonic()-last.get(host,0))));last[host]=time.monotonic();requests+=1
 if os.environ.get('CAPTURE_OFFLINE'):
  return (path.read_bytes(),previous) if previous and path.exists() else (None,None)
 try:
  res=client.get(url);res.raise_for_status()
  if not res.content:raise ValueError('Empty response')
  path.write_bytes(res.content)
  return res.content,{'url':url,'file':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(res.content).hexdigest(),'retrievedAtUtc':datetime.now(timezone.utc).isoformat(),'contentType':res.headers.get('content-type',''),'finalUrl':str(res.url)}
 except Exception as e:
  data['failures'].append({'url':url,'error':str(e),'retainedPrevious':bool(previous and path.exists())})
  if previous and path.exists():return path.read_bytes(),previous
  return None,None
ag=json.loads((ROOT/'data/normalized/agweather.json').read_text());cl=json.loads((ROOT/'data/normalized/climate.json').read_text())
queue=[]
for kind in ['current','forecasts']:
 for section in ag[kind]['sections']:
  for group in section['groups']:
   for l in group['links']:
    if urlparse(l['url']).hostname in HOSTS:queue.append((canonical(l['url']),l['label']+' — '+section['heading'],0))
for l in ag['home']['navigation']+cl['home']['navigation']:
 u=canonical(l['url'])
 if urlparse(u).hostname in HOSTS and urlparse(u).path not in ('/','/index.html','/info/','/current/','/forecasts/','/climate_maps.html'):queue.append((u,l['label'],0))
known=set();i=0
while i<len(queue):
 url,title,depth=queue[i];i+=1
 if url in known:continue
 known.add(url)
 raw,rec=fetch(url,old['pages'].get(url,{}).get('source'))
 page={'path':route(url),'title':title,'source':rec,'section':'climate' if urlparse(url).hostname=='climate.geo.msu.edu' else 'agweather','html':'','text':'','images':[]}
 if raw is None:
  page['unavailable']=True;data['pages'][url]=page;save();continue
 if 'image/' in rec['contentType']:
  ext=Path(urlparse(url).path).suffix or '.png';dest='/media/products/'+key(url)+ext;p=ROOT/'public'/dest.lstrip('/');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
  page['html']='<img src="'+dest+'" alt="'+html.escape(title,quote=True)+'"/>';page['images']=[dest];data['pages'][url]=page;save();continue
 if 'text/plain' in rec['contentType']:
  page['text']=raw.decode('utf-8',errors='replace');data['pages'][url]=page;save();continue
 if 'pdf' in rec['contentType']:
  dest='/downloads/products/'+key(url)+'.pdf';p=ROOT/'public'/dest.lstrip('/');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
  page['download']=dest;page['documentNeedsReview']=True;data['pages'][url]=page;save();continue
 if any(t in rec['contentType'] for t in ['msword','ms-excel','officedocument','octet-stream']):
  ext=Path(urlparse(url).path).suffix or '.bin';dest='/downloads/products/'+key(url)+ext;p=ROOT/'public'/dest.lstrip('/');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
  page['download']=dest;page['documentNeedsReview']=True;data['pages'][url]=page;save();continue
 base_url=rec.get('finalUrl',url)
 if re.search(r'/climate_mi/stations/\d{4}$',base_url):base_url+='/'
 soup=BeautifulSoup(raw,'lxml',from_encoding='iso-8859-1')
 for x in soup.find_all(string=lambda t:isinstance(t,Comment)):x.extract()
 for x in soup.select('script,style,iframe,object,embed,form,link,meta'):x.decompose()
 textblock=soup.select_one('td.courier2') or soup.find('pre')
 if textblock:
  for br in textblock.find_all('br'):br.replace_with('\n')
  page['text']=textblock.get_text().replace('\xa0',' ').strip()
 else:
  main=soup.select_one('#page2_middle') or soup.find('td',attrs={'width':'635'}) or soup.find('main') or soup.body or soup
  # Replace coordinate-only county image maps with the exact same named destinations.
  areas=main.find_all('area',href=True)
  if areas:
   ul=soup.new_tag('ul');seen=set()
   for area in areas:
    dest=urljoin(base_url,area['href'])
    if dest in seen:continue
    seen.add(dest);li=soup.new_tag('li');a=soup.new_tag('a',href=dest);a.string=area.get('alt') or area.get('title') or Path(urlparse(dest).path).stem;li.append(a);ul.append(li)
   main.append(ul)
  if page['section']=='agweather':
   for h in main.find_all(['h1','h2']):
    if h.get_text(strip=True) in ['MSU Agricultural Weather Office','Current Weather & Climatological Info','Forecast Products']:h.decompose()
  for img in list(main.find_all('img')):
   if not img.get('src'):img.decompose();continue
   src=canonical(urljoin(base_url,img['src']))
   if any(x in src.lower() for x in ['msulogo','grnbar','header','spacer','wordmark','logo']):img.decompose();continue
   if urlparse(src).hostname not in HOSTS:
    # Never hotlink a third-party resource or invent a local capture.
    img.replace_with(soup.new_string('[External image: '+(img.get('alt') or title)+']'));continue
   if src not in data['assets']:
    content,ar=fetch(src,old['assets'].get(src,{}).get('source'))
    if content and any(content.startswith(p) for p in (b'\x89PNG',b'\xff\xd8\xff',b'GIF87a',b'GIF89a')):
     ext='.png' if content.startswith(b'\x89PNG') else '.jpg' if content.startswith(b'\xff') else '.gif'
     local='/media/products/'+key(src)+ext;p=ROOT/'public'/local.lstrip('/');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content);data['assets'][src]={'path':local,'source':ar}
   asset=data['assets'].get(src)
   if not asset:img.replace_with(soup.new_string('[Image unavailable from source]'));continue
   img.attrs={'src':asset['path'],'alt':img.get('alt') or title,'loading':'lazy'};page['images'].append(asset['path'])
  for a in main.find_all('a',href=True):
   if a.get_text(strip=True)=='/':a.unwrap();continue
   dest=canonical(urljoin(base_url,a['href']))
   if not dest.startswith(('https://','mailto:','tel:')):a.unwrap();continue
   a['href']=dest
   if urlparse(dest).hostname in HOSTS and depth<5 and len(queue)<1200 and dest not in known and urlparse(dest).path not in ('/','/index.html','/info/','/current/','/forecasts/','/climate_maps.html'):
    queue.append((dest,a.get_text(' ',strip=True) or title,depth+1))
  for tag in list(main.find_all(True)):
   if tag.name not in ('a','p','div','span','strong','b','i','em','br','hr','ul','ol','li','dl','dt','dd','table','thead','tbody','tr','th','td','caption','img','pre','h1','h2','h3','h4','h5','h6','sup','sub','blockquote','center','font'):
    tag.unwrap();continue
   if tag.name in ('font','center'):tag.name='span'
   if tag.name=='h1':tag.name='h2'
   tag.attrs={k:v for k,v in tag.attrs.items() if k in ('href','src','alt','loading','colspan','rowspan')}
   if tag.name=='table':tag['role']='presentation'
   if tag.name=='a' and not tag.get_text(strip=True) and not tag.find('img'):tag.decompose()
  # The SEMCOG year/month matrix is a data/navigation table, not a layout table.
  for table in main.find_all('table'):
   rows=table.find_all('tr');first=rows[0].find_all(['th','td'],recursive=False) if rows else []
   if first and first[0].get_text(strip=True).upper()=='YEAR':
    table.attrs.pop('role',None);headers=[x.get_text(' ',strip=True) for x in first]
    for cell in first:cell.name='th';cell['scope']='col'
    for row in rows[1:]:
     cells=row.find_all(['td','th'],recursive=False)
     if not cells:continue
     year=cells[0].get_text(' ',strip=True);cells[0].name='th';cells[0]['scope']='row'
     for index,cell in enumerate(cells[1:],1):
      for a in cell.find_all('a'):
       kind={'Dly':'Daily precipitation','Hrly':'Hourly precipitation','Map':'Precipitation map'}.get(a.get_text(strip=True),a.get_text(strip=True))
       a['aria-label']=kind+' — '+(headers[index] if index<len(headers) else '')+' '+year
    caption=soup.new_tag('caption');caption.string='SEMCOG precipitation by year and month';table.insert(0,caption)
    wrap=soup.new_tag('div',attrs={'class':'table-wrap','role':'region','aria-label':'SEMCOG year and month table','tabindex':'0'});table.wrap(wrap)
  # Large legacy growing-season spreadsheets: explicit county/metric row headers
  # and month/statistic column headers, preserving every source numeric cell.
  for table in list(main.find_all('table')):
   if table.find('table'):continue
   rows=table.find_all('tr');data_rows=[];months=[]
   for row in rows:
    cells=row.find_all(['td','th'],recursive=False);texts=[c.get_text(' ',strip=True) for c in cells]
    if 'OBS' in texts and 'NORM' in texts:continue
    if 'MAY' in texts and 'SEASON' in texts:months=[t for t in texts if t in ['MAY','JUNE','JULY','AUGUST','SEPTEMBER','SEASON']]
    metric=next((j for j,t in enumerate(texts[:3]) if t in ['TEMP','PPT','GDD']),None)
    if metric is not None:
     values=[t for t in texts[metric+1:] if t]
     data_rows.append((texts[:metric],texts[metric],values))
   if len(months)==6 and data_rows and len(data_rows)%3==0 and all(r[1]==['TEMP','PPT','GDD'][j%3] and len(r[2])==18 for j,r in enumerate(data_rows)):
    rebuilt=soup.new_tag('table');caption=soup.new_tag('caption');caption.string=title;rebuilt.append(caption)
    head=soup.new_tag('tr');th=soup.new_tag('th',scope='col');th.string='County / variable';head.append(th)
    for month in months:
     for stat in ['Observed','Normal','Departure']:
      th=soup.new_tag('th',scope='col');th.string=month+' '+stat;head.append(th)
    thead=soup.new_tag('thead');thead.append(head);rebuilt.append(thead);body=soup.new_tag('tbody')
    for j,(prefix,metric,values) in enumerate(data_rows):
     group=data_rows[(j//3)*3:(j//3)*3+3];county=next((t for r in group for t in r[0] if t),'County not supplied')
     row=soup.new_tag('tr');th=soup.new_tag('th',scope='row');th.string=county+' / '+metric;row.append(th)
     for value in values:td=soup.new_tag('td');td.string=value;row.append(td)
     body.append(row)
    rebuilt.append(body);table.replace_with(rebuilt)
  table_ids={id(t) for t in main.find_all('table')}
  for table in list(main.find_all('table')):
   if id(table.find_parent('table')) not in table_ids and not (table.parent.get('class')==['table-wrap']):
    wrap=soup.new_tag('div',attrs={'class':'table-wrap','role':'region','aria-label':'Source table','tabindex':'0'});table.wrap(wrap)
  for dl in main.find_all('dl'):
   if not dl.find(['dt','dd'],recursive=False):dl.name='div'
  for listing in main.find_all(['ul','ol']):
   for child in list(listing.children):
    if getattr(child,'name',None)=='li':continue
    if not getattr(child,'name',None) and not str(child).strip():continue
    if getattr(child,'name',None)=='br':child.extract();continue
    previous=child.find_previous_sibling('li')
    if getattr(child,'name',None) in ['ul','ol'] and previous:previous.append(child.extract())
    else:
     item=soup.new_tag('li');child.replace_with(item);item.append(child)
  for item in main.find_all('li'):
   if item.parent.name not in ['ul','ol']:item.name='p'
  for heading in list(main.find_all(['h2','h3','h4','h5','h6'])):
   if not heading.get_text(strip=True):heading.decompose()
  page['html']=''.join(str(x) for x in main.contents)
 if 'page that you selected does not exist' in page['html'].lower():page['unavailable']=True
 data['pages'][url]=page;save();print(f"{len(data['pages'])} {url} text={len(page['text'])} images={len(page['images'])}",flush=True)
data['completedAtUtc']=datetime.now(timezone.utc).isoformat();save(True);print('Complete',len(data['pages']),'pages',len(data['assets']),'assets',len(data['failures']),'exceptions',flush=True)
