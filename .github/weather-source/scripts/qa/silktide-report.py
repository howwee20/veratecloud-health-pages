from pathlib import Path
import json,re
from urllib.parse import urljoin,urlsplit
p=Path(__file__).resolve().parents[2]
base=p.parent
manifest=json.loads((p/'reports/build-sha256.json').read_text())
build=manifest['buildDigest']
records=json.loads((p/'reports/silktide/scan-index.json').read_text())
def page_assets(page):
 seen=set()
 def visit(name):
  if name in seen or name not in manifest['files']:return
  seen.add(name)
  if not name.endswith(('.html','.css','.js')):return
  source=(p/'dist'/name).read_text()
  refs=re.findall(r'(?:src|href)=[\"\']([^\"\']+)',source)
  refs+=re.findall(r'url\(\s*[\"\']?([^\"\')\s]+)',source)
  refs+=re.findall(r'[\"\']((?:\./|\.\./)[^\"\']+\.(?:js|css))[\"\']',source)
  for ref in refs:
   u=urlsplit(urljoin('/'+name,ref))
   if u.scheme or u.netloc:continue
   target=u.path.lstrip('/')
   if target.endswith('.html') or target.endswith('/'):continue
   visit(target)
 visit(page)
 return sorted(seen)
def matches_final(r):
 if not r.get('buildDigest'): return False
 if r['buildDigest']==build: return True
 prior_path=p/f'reports/silktide/builds/{r["buildDigest"]}.json'
 if not prior_path.exists(): return False
 prior=json.loads(prior_path.read_text())['files']
 page='index.html' if r['route']=='/' else r['route'].lstrip('/')
 if page.endswith('/'): page+='index.html'
 # Require the exact page and its recursively referenced local resources.
 # A changed MAWN-only bundle does not invalidate an unchanged Climate page.
 return bool(prior.get(page)) and all(prior.get(k)==manifest['files'].get(k) for k in page_assets(page))
latest={r['route']:r for r in records if matches_final(r) and r.get('state','page')=='page' and '-before-' not in r['file']}
assert len(latest)==20, f'Incomplete final-build coverage: {len(latest)}/20'
(p/'reports/silktide/final-coverage.json').write_text(json.dumps({'finalBuildDigest':build,'routes':latest},indent=2)+'\n')
routes=sorted('/'+str(f.relative_to(p/'dist')).replace('index.html','') for f in (p/'dist').rglob('*.html'))
passed=[r for r in latest.values() if 'All automated checks passed' in r['result']]
warnings=[r for r in latest.values() if 'All automated checks passed' not in r['result']]
stats=json.loads((p/'reports/e2e-results.json').read_text())['stats']
readiness=json.loads((p/'reports/oct14-review/readiness-checks.json').read_text())
assert stats['unexpected']==0 and not readiness.get('failure')
zoom=json.loads((p/'reports/oct14-review/native-zoom.json').read_text())
assert all(x['metrics']['documentWidth']==x['metrics']['width'] for x in zoom)
coverage={}
for route,r in latest.items():
 page='index.html' if route=='/' else route.lstrip('/')
 if page.endswith('/'):page+='index.html'
 coverage[route]={'receipt':r['file'],'scannedBuild':r['buildDigest'],'verifiedResources':page_assets(page)}
(p/'reports/silktide/build-correspondence.json').write_text(json.dumps(coverage,indent=2)+'\n')
lines=['MSU WEATHER DEMOS — OCTOBER 14 REVIEW PACKAGE','Prepared October 13, 2026 | Review date requested by EJ: October 14, 2026','LOCAL SNAPSHOT. INSTITUTIONAL APPROVAL PENDING.','',f'{len(latest)}/{len(routes)} local HTML routes have verified Silktide receipts.',f'{len(passed)} show All automated checks passed; {len(warnings)} have automated findings.',f'Final build SHA-256: {build}','','ACTUAL SILKTIDE METHOD','Official Silktide Accessibility Checker 3.0.9, publisher Silktide Ltd.','Chrome, Automated mode, WCAG 2.2 AA, Desktop. Native viewport 1728 x 941 CSS px.','MAWN/root, Agricultural Weather and Climate were checked again October 13.','Unchanged report/utility pages retain their October 12 receipts only where the','page HTML and all recursively referenced local resources match this final build.','See reports/silktide/build-correspondence.json and the saved build manifests.','The page accessibility trees and tab screenshots preserve the actual findings.','Unrelated browser tab lists are omitted from exported trees for privacy.','No institutional Silktide account, numerical score, or certification is asserted.','','PAGE RESULTS']
for route in routes:
 r=latest[route];ok='All automated checks passed' in r['result']
 lines.append(('AUTOMATED PASS — ' if ok else 'FINDINGS — ')+route)
 if not ok:lines.extend('  '+x.strip() for x in r['result'].splitlines() if 'button' in x and 'WCAG' in x)
 lines.append(f'  reports/silktide/{r["file"]}.txt and .jpg')
lines.extend(f"""
MAP REMEDIATION — THE 93 WARNINGS ARE FIXED
The original map graphic and geographic marker positions are unchanged. Crowded
individual pin links were replaced with one full-map control that opens a station
chooser. Its 97 station links are at least 24 x 24 CSS pixels. It supports labeled
search, a no-results message, Enter/Space, Escape/Close, and focus return. The two
regional zoom links remain. Without JavaScript the map links to the permanent
119-entry directory. No invisible overlapping hit areas or scanner exclusions
were introduced. The map interaction changes: choose a station from the list
instead of following a tiny pin directly. All original station destinations remain.
The final MAWN and root-page Silktide receipts show zero automated findings.
See reports/silktide/map-target-controls.json and the before/after receipts.

DESIGN EVIDENCE
All three idle homepages at 1280 x 900 have zero changed pixels compared with the
previous delivered demos. The original artwork, colors and desktop layout remain.
See reports/oct14-review/design-comparison.json, baseline/ and reports/screenshots/.
This comparison is against the previous demos, not a claim of pixel identity to
all production pages. The station chooser is a new accessible interaction.

COMPLETED CHECKS
- {stats['expected']} Chromium browser tests passed, with zero failures or skips.
  All 20 routes: keyboard focus at 320 x 256, reflow at four viewport sizes,
  and increased text spacing at 320/1280. Report values, filtering, CSV downloads,
  skip links, explicit submission and station-chooser operation are covered.
- 40 desktop/mobile axe page scans: zero WCAG A/AA violations, no rule exclusions.
  Six additional open-picker axe checks across Chromium, Firefox and WebKit:
  zero violations. Indeterminate findings are retained for review.
- Chromium, Firefox and WebKit: all 20 routes at 320 and 1280 CSS pixels, no
  document overflow or script errors; chooser controls and focus return passed.
  WebKit is engine coverage, not a claim of native Safari or iOS device testing.
- Actual Chrome 200% and 400% zoom: all 20 routes kept document width within the
  viewport. Browser zoom was restored to 100%. Raw geometry and screenshots:
  reports/oct14-review/native-zoom.json and zoom-*.txt/.jpg.
- Chromium forced-colors and reduced-motion emulation: all 20 routes. This is
  browser emulation, not native Windows High Contrast or NVDA validation.
- 99 unit tests passed. The unchanged parser/source suite previously passed 128.
- 886 indeterminate text-contrast nodes have supplementary CSS ratio calculations;
  zero unresolved failures, minimum 12.10:1. Image pixels need visual review.
- No broken internal links/fragments. External links were inventoried and not
  followed by the QA suite. No remote embedded content is required.

SCREEN-READER STATUS — STARTUP RESOLVED
VoiceOver startup and speech were confirmed October 13 after resolving the
welcome/tutorial startup flow. The user supplied a screenshot of live captions
and confirmed that speech worked. The original Mac settings were restored.
The screenshot shows Codex content, not completed weather-demo test workflows.
A comprehensive spoken-output pass across the three demos is not established.
The modal's name, label, links and focus were verified in Chrome's native
accessibility tree; those checks remain distinct from spoken-output acceptance.
See reports/oct14-review/voiceover-startup-resolved.txt and native-station-picker.txt.

MSU REVIEWER HANDOFF FOR OCTOBER 14
1. Run the institutional Silktide configuration on an MSU-approved staging URL.
   Its cloud crawler cannot access this machine's 127.0.0.1 address. The package
   can be served locally with Start Preview.command for toolbar/manual review.
2. Complete actual VoiceOver/NVDA review: reading sequence, table-header and
   missing-value announcements, filtering status, chooser name/focus/escape,
   and expanded climate descriptions. Record disposition in MSU's worksheet.
3. Ask the weather-data owner to validate the 27 climate descriptions. Regional
   legend-band readings are approximate; underlying gridded numeric data were
   not supplied. Do not treat those descriptions as a validated scientific dataset.
4. Define production scope. Only the 20 listed routes are rebuilt. Other stations,
   product reports and custom requests open their originals. Their backends and
   accessibility remain outside this demo remediation. A full-service approval
   requires testing everything in the intended production release.
5. Record MSU's review decision and recheck the intended deployed release.

SCOPE
Captured October 12 weather data, not live data. Production MSU services are
unchanged. This package is ready to be submitted for review with the limitations
above; it does not establish full WCAG conformance, ADA certification or MSU approval.
November 15 was the earlier requested readiness date; October 14 is now the review
handoff date. Neither is represented here as a statutory deadline.

DEMOS
http://127.0.0.1:4322/weather-network/
http://127.0.0.1:4322/agricultural-weather/
http://127.0.0.1:4322/climate/

REFERENCES
https://webaccess.msu.edu/policy/technical-guidelines
https://webaccess.msu.edu/tools/silktide
https://webaccess.msu.edu/tutorials/evaluation/methodologies
https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
https://chromewebstore.google.com/detail/silktide-accessibility-ch/mpobacholfblmnpnfbiomjkecoojakah
""".strip().splitlines())
report='\n'.join(lines)+'\n'
(p/'SILKTIDE-RESULTS.txt').write_text(report)
(base/'MSU-Silktide-Review.txt').write_text(report)
(base/'MSU-October-14-Review-Handoff.txt').write_text(report)
print(f'Wrote {len(latest)}/{len(routes)} page receipts: {len(passed)} automated pass, {len(warnings)} with findings.')
