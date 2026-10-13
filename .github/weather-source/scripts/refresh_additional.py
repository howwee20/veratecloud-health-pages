"""Refresh only the three existing SWMREC report captures; publish receipts after all succeed."""
from pathlib import Path
import hashlib,json,time
from datetime import datetime,timezone
import httpx
ROOT=Path(__file__).resolve().parent.parent
p=ROOT/'data/normalized/additional-sources.json'
receipts=json.loads(p.read_text()); staged=[]
with httpx.Client(timeout=30,follow_redirects=False,headers={'User-Agent':'VerateCloud-Weather-Demo/1.0 (authorized read-only refresh)'}) as client:
 for rec in receipts:
  if rec['file'] not in ['data/additional-sources/swmh.html','data/additional-sources/swmd.html','data/additional-sources/swmm.html']:continue
  time.sleep(2)
  response=client.get(rec['url']);response.raise_for_status()
  assert response.status_code==200 and len(response.content)>1000, 'Incomplete source response'
  staged.append((ROOT/rec['file'],response.content))
  rec.update(retrievedAtUtc=datetime.now(timezone.utc).isoformat(),status=200,bytes=len(response.content),sha256=hashlib.sha256(response.content).hexdigest(),contentType=response.headers.get('content-type'))
for target,raw in staged:target.write_bytes(raw)
p.write_text(json.dumps(receipts,indent=2)+'\n')
print('Refreshed three SWMREC reports with receipts.')
