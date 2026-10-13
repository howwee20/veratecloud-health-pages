"""Refresh, parse, validate, build, and stage the weather demo. Any error stops deployment."""
from pathlib import Path
import os,subprocess,shutil,json
ROOT=Path(__file__).resolve().parent.parent
REPO=ROOT.parent.parent
os.chdir(ROOT)
def run(*args,**kwargs):subprocess.run(args,check=True,**kwargs)
run('python','-I','scripts/refresh_sources.py','--approved-by','Evan Howe','--robots-override-approved-by','Site maintainers, authorization confirmed by Evan Howe on 2026-10-13','--execute','--delay','2')
pack=max((ROOT/'data/source-snapshots').glob('refresh-*'),key=lambda p:p.name)
run('python','-I','scripts/refresh_additional.py')
run('python','-I','scripts/build_data.py',env={**os.environ,'SOURCE_PACK':str(pack)})
run('python','-I','scripts/build_additional.py')
# Reject incomplete or structurally changed weather reports before publication.
for sid in ['bnz','swm']:
 for kind in ['hourly','daily']:
  d=json.loads((ROOT/f'data/normalized/{sid}-{kind}.json').read_text())
  assert d['rows'] and d['columns'],f'Empty {sid} {kind}'
  assert all(set(r['cells'])=={c['key'] for c in d['columns']} for r in d['rows']), 'Column mismatch'
run('npm','run','build')
run('node','scripts/qa/check-links.mjs')
for p in (ROOT/'dist').rglob('*'):
 if p.is_file() and p.relative_to(ROOT/'dist').as_posix() not in ('index.html','404.html','favicon.svg'):
  dest=REPO/p.relative_to(ROOT/'dist');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
# Keep original EMR and tile pages intact. Only the public site goes into the artifact.
site=REPO/'_site';site.mkdir(exist_ok=True)
for p in REPO.iterdir():
 if p.name.startswith('.') and p.name!='.nojekyll':continue
 if p.name in ('_site','README.md'):continue
 if p.is_dir():shutil.copytree(p,site/p.name,dirs_exist_ok=True)
 else:shutil.copy2(p,site/p.name)
print('Validated weather refresh staged; EMR and tiles preserved.')
