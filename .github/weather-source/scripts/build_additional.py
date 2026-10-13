#!/usr/bin/env python3
"""Rebuild SWMREC reports offline from the captured responses; verify SHA-256."""
from pathlib import Path
import sys,json,hashlib,csv
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'scripts'))
from pipeline import parsers as P
receipts=json.loads((ROOT/'data/normalized/additional-sources.json').read_text())
for kind,suffix,parser in [('hourly','h',P.parse_hourly),('daily','d',P.parse_daily),('maintenance','m',P.parse_maintenance)]:
 rec=next(r for r in receipts if r['file']==f'data/additional-sources/swm{suffix}.html')
 raw=(ROOT/rec['file']).read_bytes()
 assert hashlib.sha256(raw).hexdigest()==rec['sha256'], 'Captured response changed'
 doc={'schemaVersion':1,'source':{'id':f'mawn-report-swm{suffix}',**{k:rec[k] for k in ['url','file','sha256','retrievedAtUtc']}},**parser(raw)}
 (ROOT/f'data/normalized/swm-{kind}.json').write_text(json.dumps(doc,indent=2,ensure_ascii=False)+'\n')
 (ROOT/f'public/captured-source/mawn-report-swm{suffix}.html.txt').write_bytes(raw)
 if kind=='maintenance': (ROOT/'public/downloads/swmrec-maintenance.txt').write_text(doc['rawText']+'\n')
 else:
  with (ROOT/f'public/downloads/swmrec-{kind}.csv').open('w',newline='') as f:
   w=csv.writer(f);w.writerow(['date']+([f"time_{doc['timezoneLabel']}_as_labelled"] if kind=='hourly' else [])+[c['sourceHeader'] for c in doc['columns']])
   for row in doc['rows']:w.writerow([row['dateRaw']]+([row['timeRaw']] if kind=='hourly' else [])+[row['cells'][c['key']]['raw'] for c in doc['columns']])
 print(f"SWMREC {kind}: rebuilt from verified capture")
