# Decisions — October 12, 2026

- EJ explicitly requested the original three site designs with accessibility remediation. The previous unified dashboard direction is superseded.
- The source of truth is the saved HTML plus bounded retrieval of directly referenced public images/CSS and SWMREC report URLs. Requests were read-only and at most one per second per host. No recursive crawl was performed. This does not assert site-maintainer authorization or a robots.txt override for a general crawl.
- Local-only delivery. The originals, their databases and production services were not changed.
- Accessibility target updated to WCAG 2.2 AA after verifying MSU's current technical guidelines, effective January 1, 2026: https://webaccess.msu.edu/policy/technical-guidelines. MSU uses Silktide plus manual review. Keith's exact mail requirements could not be verified; Outlook connector unavailable and Gmail searches had no match.
- Preserve original desktop identity; replace image navigation with keyboard-accessible HTML text, improve focus/contrast, reflow on small screens, and replace text-report columns with semantic data tables.
- Preserve every captured observation and missing marker. No interpolation, invented readings or current-data claim.
- Explicit GET submission opens original MAWN custom-report service. Changing a select value alone never navigates.
- Original product URLs without captured implementations remain external links. Full backend migration is outside the available public source material.
- Descriptive climate-map summaries are approximate readings of the saved images and need provider review. No point-level numeric data were reconstructed from pixels.
- Earlier Opus notes/screenshots are archived in the working folder and omitted from the final package. Current validation lives in reports/.

- WCAG 2.2 target-size findings were fixed through 24px minimum standalone link/control areas. Original map pin positions are retained, with verified equivalent full-size station-directory links on the same page. W3C documents the equivalent-control exception: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html.
- MSU-style text-spacing and focus checks led to mobile menu, station metadata and climate image-link fixes. A site map supplies an additional route to local pages.
- No proprietary MSU Silktide report was found publicly. An unchanged official MSU issue-tracking template is included, with its URL and SHA-256. It is not a completed institutional assessment.

- EJ approved installation of the official Silktide Accessibility Checker after
  being told about its terms and website-content access. Installed Chrome Web
  Store extension mpobacholfblmnpnfbiomjkecoojakah, publisher Silktide Ltd, listing
  version 3.0.9. Local scans use its WCAG 2.2 AA filter, rather than its default
  WCAG 2.1 AA setting. Raw UI findings and screenshots are in reports/silktide/.
- Silktide findings led to semantic lists for partner/footer navigation,
  consistent destinations for historic Enviro-weather/Project GREEEN aliases,
  contextual accessible names on current/forecast report links, and 24px support
  links. The original artwork, colors and typography remain in use.
- Keep the geographic map pins in their original positions. Do not remove map
  links, change stations' locations, or hide findings to obtain an empty scan.
  The remaining map-size warning is recorded for reviewer disposition under
  WCAG 2.5.8's equivalent-control and essential geographic-position exceptions.
  reports/silktide/map-equivalent-controls.json verifies every one of 97 station
  links at 320px and 1280px. MSU acceptance of this disposition is still required.
- November 15, 2026 is EJ's requested readiness date, not a verified statutory
  deadline or an approval already granted. Institutional scan, assistive-
  technology review, scientific-data review and staging/deployment checks must
  be completed before anyone represents the complete service as conformant.

- Final utility-page fixes: enlarged site-map link areas to 24 CSS pixels and distinguished original-site links from local demos through accessible names. These changes preserve visible text and source-site designs.

## October 13 — October 14 review handoff
- EJ requested fixing the remaining 93 map warnings and completing the remaining demo checks for October 14. This supersedes the earlier November 15 handoff date.
- Kept the original map raster and SVG rendering; replaced the 97 crowded direct pin links with one full-map chooser control and 97 large labeled station links. The two regional zoom links remain. No overlapping hit areas, rule suppression or warning exemptions are used.
- The chooser uses a native modal dialog, labeled search, live result count, Enter/Space, Close/Escape and focus return. Without JavaScript the map links to the complete permanent directory. This changes map interaction while preserving the idle appearance.
- Silktide found one semantic list issue after the first change; it was corrected. Browser tests found search-field Escape consumption; dialog Escape now closes immediately.
- Three idle homepages at 1280 x 900 compare with zero changed pixels to the previous delivery. The baseline archive SHA and evidence images are retained.
- All 20 routes received native Chrome 200% and 400% zoom geometry/screenshots, with browser zoom restored. Chromium, Firefox and WebKit checks, forced-colors emulation, all-route focus/reflow/text-spacing tests and open-modal axe checks passed.
- Native VoiceOver was attempted through keyboard and System Settings. No usable spoken-caption/rotor feedback was available through computer control; this is not counted as a pass. VoiceOver was restored off and its previously enabled caption preference was unchanged.
- MSU institutional scan/approval and independent spoken screen-reader/data-owner review remain pending. No production service or external audience was changed.

## October 13, 2026: approved read-only refresh
Evan Howe confirmed in chat: “Yes, maintainers authorize read-only refreshes” in response to the explicit question about fetching these hosts despite robots.txt. This authorizes bounded GET refreshes of the named public sources, with at least two seconds between requests, no credentials, no production writes, and recorded receipts. No claim of MSU accessibility approval follows from this authorization.

## October 13, 2026 — All-station expansion and recurring refresh

Evan confirmed: "Yes, maintainers authorize read-only refreshes." He then requested all station/report click-throughs on Verate Cloud and updating climate maps. This authorizes the bounded expansion beyond the original two-station demonstration. Captures use GET only, at least 1.1 seconds between request starts on each host (no more than one request per second); no database credentials, logger controls, original-site writes, or arbitrary historical-query crawling. Named climate archive links are followed within a bounded inventory. Broken duplicated SEMCOG relative-path prefixes are repaired before fetching. Supporting organizations and separate NOAA/Wisconsin services remain external links.

Station source values, timestamps, missing markers, explicit N/A fields, partial maintenance dates, and undated instrument warnings must be retained. Source availability failures are visible; unavailable records must never be replaced with invented measurements. Recurring builds retain previously validated data on individual source errors and keep the deployed release on failed validation. Image-derived climate regional samples are approximate color bands, not the underlying grid.

The local custom-report interface filters captured daily/hourly records. Full historical database queries, five-minute data, and the legacy GDD query engine are not represented as completed equivalents. Raw source archive directories beyond the recent three-hour files are inventoried but not mirrored. Review notes must distinguish this scope from complete production replacement and must not claim ADA certification or a new institutional Silktide score.

## 2026-10-13: Public presentation and separate review material

At Evan Howe's request, remove project/demo/AI-facing language from the three
weather sites. Keep original site content and functional data availability,
observation dates and map interpretation text. Remove the public meeting report
and capture-coverage CSVs; deliver those separately in outputs/meeting-release.
The publisher removes retired review artifacts on every build. Accessibility
help describes navigation only and makes no conformance or approval claim.
Verified successor URLs replace 12 dead legacy links to official weather and
climate services. Original link labels and layout are retained.
The source cache now retains core captures as well as expanded reports/maps so
subsequent design-only publications can retain the most recent successful data.
