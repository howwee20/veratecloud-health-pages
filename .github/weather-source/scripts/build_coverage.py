"""Publish explicit capture coverage without implying full backend equivalence."""
from pathlib import Path
import json,csv
ROOT=Path(__file__).resolve().parent.parent
network=json.loads((ROOT/'data/expanded/network.json').read_text())
products=json.loads((ROOT/'data/expanded/products.json').read_text())
out=ROOT/'reports/coverage';out.mkdir(parents=True,exist_ok=True)
with (out/'station-coverage.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['station_id','station_name','local_page','hourly_rows','daily_rows','maintenance_entries','hourly_saved_utc','daily_saved_utc'])
 for sid,s in sorted(network['stations'].items()):
  r=network['reports'][sid];w.writerow([sid,s['stationName'],'https://veratecloud.com/weather-network/stations/'+sid+'/',len(r['hourly']['rows']),len(r['daily']['rows']),len(r['maintenance']['entries']),r['hourly']['source'].get('retrievedAtUtc',''),r['daily']['source'].get('retrievedAtUtc','')])
with (out/'product-coverage.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['title','local_page','source_url','captured','source_saved_utc','document_needs_manual_review'])
 for url,p in sorted(products['pages'].items()):w.writerow([p['title'],'https://veratecloud.com'+p['path'],url,bool(p['source']) and not p.get('unavailable',False),(p['source'] or {}).get('retrievedAtUtc',''),p.get('documentNeedsReview',False)])
print('Coverage CSVs generated.')
