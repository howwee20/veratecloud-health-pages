# Hosting reference files

These are examples for a future deployment, not installed MSU configuration.
These untested examples need MSU IT security review and institutional approval
before production use.
Static hosting cannot rewrite query strings by itself; legacy ASP report URLs
need a routing layer that interprets their parameters.
The delivered demos are served locally using `scripts/qa/static-server.mjs`.
No public host, DNS record, backend or production redirect has been changed.

`security-headers.json` is the header source used by the local QA server. Its
Content-Security-Policy permits local assets and explicit form submission to
`https://mawn.geo.msu.edu`; it blocks remote embeds and inline scripts. The
nginx, Apache and `_headers` examples mirror those headers; unit tests check
that their values stay aligned. They have not been validated on the intended
hosting platform after this revision.

`legacy-url-map.csv` and redirect examples are preliminary migration references
inherited from the source pipeline. They do not implement a complete migration
of the three hosts. In particular, the delivered SWMREC report pages now exist,
but the earlier redirect examples still only map the Benzonia report URLs.
Do not use those examples as a production cutover configuration.

A future host needs routing for the distinct legacy domains, live data/backend
integration, correct raw-file content types, review of uncaptured URLs, and
accessibility checks against the resulting deployed pages. See `../MSU-REVIEW.txt`.
