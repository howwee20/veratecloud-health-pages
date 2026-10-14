# Verate Cloud

Public site: https://veratecloud.com/

- `/`: title-only EMR and Enviroweather panels.
- `/emr/`: existing synthetic-data EMR demonstration; unchanged by this release.
- `/enviroweather/`: three weather-site panels.
- `/weather-network/`, `/agricultural-weather/`, `/climate/`: original-design accessibility previews.
- `/enviroweather/review/`: coverage, technology, validation and remaining acceptance work.

GitHub Pages uses the Actions workflow in `.github/workflows/pages.yml`. It builds
`.github/weather-source`, validates the result and publishes `_site`. Pushes use
reviewed cached data; the hourly schedule and manual dispatch perform authorized
read-only refreshes. The schedule is minute 17, subject to GitHub delays. Per-host
request starts are spaced at least 1.1 seconds apart. Current reports use a
30-minute cache, historical content up to 30 days, station photos seven days.

All 119 listed weather stations have local routes. Available reports include
115 hourly, 115 daily and 119 maintenance logs, plus 100 recent raw files. Local
custom reports filter captured daily/hourly dates and export CSV. Agricultural
products and climate reference pages are captured locally. All 27 current climate
maps refresh with matching dates, legends and approximate regional text samples.

Weather navigation does not link back to the three original hosts. Uncopied or
unavailable historical items show an explicit local notice. Separate NOAA,
Wisconsin and institutional services remain external. Source observation dates,
missing-value markers and retired-station limitations are retained.

This is not a complete historical database migration or an ADA certification.
Five-minute/GDD queries, full historical archives, complex document/chart
alternatives and institutional manual review remain acceptance work. See the
public review report and downloadable station/product coverage inventories.

Maintainership authorization for bounded read-only refreshes despite robots.txt
was confirmed by Evan on October 13, 2026 and is recorded in DECISIONS.md. Failed
validation stops deployment and leaves the previous public release available.
The climate refresh validates all 27 image/text pairs before replacing them.
`/downloads/release.json` identifies the deployed source commit and build time.

Keep the EMR, showcase tiles, CNAME, domain configuration and `.nojekyll` intact.
Rollback is a normal reviewed revert followed by the workflow; no history rewrite
or DNS change is needed. Baseline before this expanded release: b4c6c12.
