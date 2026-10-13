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
