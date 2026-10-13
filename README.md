# Verate Cloud showcase

Public site: https://veratecloud.com/

- `/`: Medical records and Enviroweather project panels.
- `/emr/`: Existing Health Records entry point, unchanged. Original assets, OCR files, Supabase integration, CNAME, and HTTPS configuration are preserved.
- `/enviroweather/`: Three weather-site previews and review details.
- `/weather-network/`, `/agricultural-weather/`, `/climate/`: Original-design weather accessibility previews.

GitHub Pages publishes the root of `main`. No build is required. `.nojekyll` must remain.

Weather content is an October 12, 2026 snapshot. The 95 imported files are byte-identical to the tested local weather build. The local duplicate root page and 404 are replaced by showcase pages, and the original domain favicon is preserved. Automated results do not establish institutional approval or full ADA/WCAG conformance. See `/enviroweather/review/` for scope and test limits.

The EMR is a synthetic-data demonstration. Account access and its backend are not changed by this showcase deployment.

Prior deployment: e1ba062fce2c1802205c7c0e00bcc1b4d9a15a99. Roll back using a normal reviewed revert; do not rewrite branch history. Domain and DNS changes are unnecessary.

## Authorized weather refresh (October 13, 2026)

Evan confirmed maintainer authorization for bounded read-only refreshes despite robots.txt. `.github/workflows/pages.yml` refreshes the 14 named sources plus the three SWMREC report captures hourly, at minute 17 (GitHub scheduling may be delayed), and on deployment. Requests are serial, throttled two seconds apart, with timeouts and recorded hashes. Failed fetching, parsing, validation, or builds stop deployment and leave the previous public release intact. EMR assets and tile pages are preserved. Source code is in `.github/weather-source`; only the staged `_site` is deployed.

This refresh covers East Lansing recent conditions, Benzonia/SWMREC reports, raw Benzonia data and the agricultural indexes. Other stations and products continue opening their original MSU services. The 27 climate images and their matching text descriptions remain the dated October 12 capture; their current source is linked. No claim of complete migration, continuous real-time delivery, or institutional accessibility certification is made.
