"""Imported source tables retain numbers when adding accessible headers."""
import json
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[2]
def test_growing_season_table_values_survive_semantic_conversion():
 pages=json.loads((ROOT/'data/expanded/products.json').read_text())['pages']
 checked=0
 for p in pages.values():
  if 'Growing Season Weather Summary - Table' not in p['title']:continue
  source=BeautifulSoup((ROOT/p['source']['file']).read_bytes(),'lxml')
  expected=[]
  for row in source.find_all('tr'):
   cells=row.find_all(['td','th'],recursive=False)
   if any(c.find('table') for c in cells):continue
   texts=[c.get_text(' ',strip=True) for c in cells]
   metric=next((j for j,t in enumerate(texts[:3]) if t in ['TEMP','PPT','GDD']),None)
   if metric is not None:expected.extend(t for t in texts[metric+1:] if t)
  local=BeautifulSoup(p['html'],'lxml')
  actual=[c.get_text(' ',strip=True) for row in local.select('tbody tr') for c in row.find_all('td',recursive=False)]
  assert actual==expected and expected,p['source']['url']
  assert local.select('th[scope="row"]') and local.select('th[scope="col"]')
  assert local.select('.table-wrap[tabindex="0"]')
  checked+=1
 assert checked==3
