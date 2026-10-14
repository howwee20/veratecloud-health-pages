"""Real captured directory coverage and byte-to-row integrity, not fabricated observations."""
import json,hashlib,re
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from pipeline import parsers as P
def bundle():return json.loads((ROOT/'data/expanded/network.json').read_text())
def test_full_directory_has_local_station_records():
 d=bundle();ids={s['id'] for s in json.loads((ROOT/'data/normalized/stations.json').read_text())['stations']}
 assert set(d['stations'])==set(d['reports'])==ids
 assert len(ids)==119

def test_every_structured_report_preserves_all_source_rows_and_raw_cells():
 d=bundle()
 for sid,reports in d['reports'].items():
  for kind in ['hourly','daily']:
   r=reports[kind]
   if not r['rows']:continue
   raw=(ROOT/r['source']['file']).read_bytes()
   assert hashlib.sha256(raw).hexdigest()==r['source']['sha256']
   source_rows=[line.split() for line in P.report_lines(raw) if re.match(r'^\d{2}/\d{2}/\d{2}\s',line)]
   output=[[row['dateRaw']]+([row['timeRaw']] if kind=='hourly' else [])+[row['cells'][c['key']]['raw'] for c in r['columns']] for row in r['rows']]
   assert output==source_rows,(sid,kind)
   assert all(set(row['cells'])=={c['key'] for c in r['columns']} for row in r['rows'])

def test_partial_date_and_undated_irrigation_warning_are_preserved():
 d=bundle()
 assert any(e['dateRaw']=='??/??/2026' and e['isoDate'] is None for e in d['reports']['llu']['maintenance']['entries'])
 assert 'center-pivot irrigator' in ' '.join(d['reports']['ent']['maintenance']['preface'])

def test_explicit_unknown_elevation_and_central_time_are_preserved():
 d=bundle()
 assert d['stations']['clx']['elevation']['raw']=='N/A'
 assert d['stations']['clx']['elevation']['value'] is None
 assert d['reports']['alt']['hourly']['timezoneLabel']=='CDT'

def test_csv_files_match_data_row_counts():
 import csv
 for sid,reports in bundle()['reports'].items():
  for kind in ['hourly','daily']:
   r=reports[kind]
   if r['rows']:
    with (ROOT/f'public/downloads/{sid}-{kind}.csv').open() as f:rows=list(csv.reader(f))
    assert len(rows)==len(r['rows'])+1,(sid,kind)
