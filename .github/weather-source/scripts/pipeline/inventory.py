"""Build the legacy-site inventory from the captured pages and the link list.

An inventory entry is evidence that a URL was *referenced* by a captured page.
Only entries with ``captured: true`` were actually retrieved.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

LEGACY_HOSTS = {
    "mawn.geo.msu.edu": "mawn",
    "www.agweather.geo.msu.edu": "agweather",
    "agweather.geo.msu.edu": "agweather",
    "climate.geo.msu.edu": "climate",
}
SITE_NAMES = {
    "mawn": "Michigan Automated Weather Network (MAWN)",
    "agweather": "MSU Agricultural Weather Office",
    "climate": "Michigan State Climatologist's Office",
    "external": "External",
}
CANONICAL_HOST = {
    "mawn": "mawn.geo.msu.edu",
    "agweather": "www.agweather.geo.msu.edu",
    "climate": "climate.geo.msu.edu",
}

_JS_URL = re.compile(r"^javascript:\s*newWindow\('([^']+)'\)", re.I)
_ASSET_EXT = re.compile(r"\.(gif|jpe?g|png|ico|css|js)$", re.I)


def canonical(url: str) -> tuple[str, bool]:
    """Return (canonical URL, opened_via_javascript)."""
    via_js = False
    m = _JS_URL.match(url)
    if m:
        url, via_js = m.group(1), True
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    path = parts.path or "/"
    scheme = parts.scheme.lower()
    if host in LEGACY_HOSTS:
        scheme = "https"
        host = CANONICAL_HOST[LEGACY_HOSTS[host]]
    query = f"?{parts.query}" if parts.query else ""
    return f"{scheme}://{host}{path}{query}", via_js


def _rule(pattern_id, template, rtype, dynamic, treatment, new_url, purpose, limits, status):
    return {
        "patternId": pattern_id,
        "patternTemplate": template,
        "resourceType": rtype,
        "dynamic": dynamic,
        "treatment": treatment,
        "proposedNewUrl": new_url,
        "purpose": purpose,
        "limitations": limits,
        "prototypeStatus": status,
    }


NOT_CAPTURED = "Not in the source pack; content, format and update behaviour are unverified."


def classify(url: str) -> dict:
    """Assign a URL to a pattern and a modernization treatment."""
    parts = urlparse(url)
    host = parts.hostname or ""
    site = LEGACY_HOSTS.get(host, "external")
    path = parts.path
    query = parse_qs(parts.query)
    asset = _ASSET_EXT.search(path)

    if site == "mawn":
        if path == "/":
            return _rule("mawn-home", "https://mawn.geo.msu.edu/", "html-page", "yes", "REBUILD",
                         "/weather-network/", "Network home: introduction, station map, station tables, recent conditions.",
                         "Legacy image-map station picker is replaced by a searchable directory; the map image was not captured.", "rebuilt")
        if path == "/station.asp" and "id" in query and "rt" in query:
            return _rule("mawn-custom-report", "https://mawn.geo.msu.edu/station.asp?id={id}&rt={24|60|5|0}", "dynamic-query-form", "yes",
                         "NEEDS INVESTIGATION", None,
                         "Custom reports (data-on-demand): daily, hourly, five-minute and growing-degree-day data for a chosen station.",
                         "Requires a query backend or data API. The form was not exercised and its results were not captured.", "not-preserved")
        if path == "/station.asp" and "id" in query:
            sid = query["id"][0]
            return _rule("mawn-station", "https://mawn.geo.msu.edu/station.asp?id={id}", "dynamic-page", "yes", "REBUILD",
                         f"/weather-network/stations/{sid}/",
                         "Station page: identity, location, links to pre-generated reports and custom reports.",
                         "One shared template. Only stations whose page was captured have a rebuilt page.", "template")
        if path == "/report.asp" and "fileid" in query:
            fid = query["fileid"][0]
            kind = {"h": "hourly", "d": "daily", "m": "maintenance"}.get(fid[-1])
            if kind:
                return _rule(f"mawn-report-{kind}", "https://mawn.geo.msu.edu/report.asp?fileid={id}" + fid[-1], "dynamic-report", "yes", "REBUILD",
                             f"/weather-network/stations/{fid[:-1]}/{kind}/",
                             {"hourly": "Pre-generated hourly weather summary for one station.",
                              "daily": "Pre-generated daily weather summary for one station.",
                              "maintenance": "Station maintenance notes for one station."}[kind],
                             "One shared template per report type. Only captured reports have a rebuilt page.", "template")
        if path.startswith("/rawdata/"):
            if parts.query:
                return _rule("rawdata-sort-link", "https://mawn.geo.msu.edu/rawdata/{dir}/?C={col};O={order}", "directory-listing", "yes", "REDIRECT",
                             path, "Server-generated sort order for a directory listing.",
                             "Sorting is offered in the listing page itself; the query-string variants would redirect to the listing.", "redirect-planned")
            rest = path[len("/rawdata/"):]
            if rest == "":
                return _rule("rawdata-root", "https://mawn.geo.msu.edu/rawdata/", "directory-listing", "yes", "PRESERVE", "/rawdata/",
                             "Root of the public raw-data directory.", "Listing reflects the capture time; it is not live.", "rebuilt")
            if rest.endswith("/") and rest.count("/") == 1:
                return _rule("rawdata-directory", "https://mawn.geo.msu.edu/rawdata/{dir}/", "directory-listing", "yes", "PRESERVE",
                             f"/rawdata/{rest}", "Raw-data subdirectory listing.",
                             "Only the 3hr listing was captured; other subdirectories are known by name only.", "listed-only")
            if not rest.endswith("/"):
                return _rule("rawdata-file", "https://mawn.geo.msu.edu/rawdata/{dir}/{file}", "data-file", "yes", "PRESERVE",
                             f"/rawdata/{rest}", "Raw logger data file, possibly consumed by scripts.",
                             "Path and bytes must be preserved exactly. Only one file was captured.", "listed-only")
        if re.fullmatch(r"/mawn-\w+\.html", path):
            return _rule("mawn-regional-map", "https://mawn.geo.msu.edu/mawn-{region}.html", "html-page", "unknown", "NEEDS INVESTIGATION", None,
                         "Regional zoom of the station map.", NOT_CAPTURED, "not-preserved")
        if path.startswith("/images/stations/"):
            return _rule("mawn-station-photo", "https://mawn.geo.msu.edu/images/stations/{id}.jpg", "image", "no", "PRESERVE", None,
                         "Photograph of a station site.", "Not in the source pack; needs an approved copy and a text alternative.", "not-preserved")
        if asset or path.startswith(("/images/", "/icons/")):
            return _rule("mawn-layout-asset", "https://mawn.geo.msu.edu/{images|icons}/…, style.css, mawnicon.ico", "layout-asset", "no", "ARCHIVE", None,
                         "Legacy layout image, icon or stylesheet.", "Superseded by the new design system; not needed by the rebuild.", "superseded")

    if site == "agweather":
        if path == "/":
            return _rule("agweather-home", "https://www.agweather.geo.msu.edu/", "dynamic-page", "yes", "REBUILD", "/agricultural-weather/",
                         "Office home: navigation, data-feed status, news and notes, contact details.", "Feed status and news are a snapshot.", "rebuilt")
        if path == "/index.html":
            return _rule("agweather-index-alias", "https://www.agweather.geo.msu.edu/index.html", "html-page", "unknown", "REDIRECT", "/agricultural-weather/",
                         "Alias of the office home used by its navigation.", "Assumed to be the same page as /; not fetched.", "redirect-planned")
        if path == "/current/":
            return _rule("agweather-current", "https://www.agweather.geo.msu.edu/current/", "dynamic-page", "yes", "REBUILD", "/agricultural-weather/current/",
                         "Directory of current weather, statistics, summaries, growing-degree-day and normals products.",
                         "The directory is rebuilt; the products it links to were not captured.", "rebuilt")
        if path == "/forecasts/":
            return _rule("agweather-forecasts", "https://www.agweather.geo.msu.edu/forecasts/", "dynamic-page", "yes", "REBUILD", "/agricultural-weather/forecasts/",
                         "Directory of forecast products.", "The directory is rebuilt; the products it links to were not captured.", "rebuilt")
        if path in ("/info/", "/articles/", "/links/"):
            return _rule("agweather-section-index", "https://www.agweather.geo.msu.edu/{info|articles|links}/", "html-page", "unknown", "NEEDS INVESTIGATION", None,
                         "Section index: information, feature articles or other sites.", NOT_CAPTURED, "not-preserved")
        if path == "/current/report.asp":
            return _rule("agweather-current-report", "https://www.agweather.geo.msu.edu/current/report.asp?fileid={product}", "dynamic-report", "yes",
                         "NEEDS INVESTIGATION", None, "Text product: observations, statistics, summaries or growing-degree-day tables.",
                         "Report body not captured. Product identifiers resemble National Weather Service product IDs, which suggests a relayed feed; unverified.", "not-preserved")
        if path == "/current/normal.asp":
            return _rule("agweather-normals", "https://www.agweather.geo.msu.edu/current/normal.asp?fileid={place}", "dynamic-report", "yes",
                         "NEEDS INVESTIGATION", None, "Daily temperature and growing-degree-day normals for one location.",
                         "Report body not captured; likely a fixed climatological table but unverified.", "not-preserved")
        if path == "/forecasts/fcst.asp":
            return _rule("agweather-forecast-product", "https://www.agweather.geo.msu.edu/forecasts/fcst.asp?fileid={product}", "dynamic-report", "yes",
                         "NEEDS INVESTIGATION", None, "Forecast text product: state, zone, discussion, guidance or outlook.",
                         "Forecasts are time-critical and were not captured. A stale copy must never be shown as current.", "not-preserved")
        if path.endswith(".html"):
            return _rule("agweather-static-page", "https://www.agweather.geo.msu.edu/{section}/{page}.html", "html-page", "unknown", "NEEDS INVESTIGATION", None,
                         "Graphic or station-list page linked from a product directory.", NOT_CAPTURED, "not-preserved")
        if asset or path.startswith("/images/"):
            return _rule("agweather-layout-asset", "https://www.agweather.geo.msu.edu/images/…, style.css", "layout-asset", "no", "ARCHIVE", None,
                         "Legacy layout image or stylesheet.", "Superseded by the new design system; not needed by the rebuild.", "superseded")

    if site == "climate":
        if path == "/":
            return _rule("climate-home", "https://climate.geo.msu.edu/", "html-page", "no", "REBUILD", "/climate/",
                         "Office home: welcome text, navigation, map thumbnails.", "Thumbnails are externally hosted images and are not embedded.", "rebuilt")
        if path == "/index.html":
            return _rule("climate-index-alias", "https://climate.geo.msu.edu/index.html", "html-page", "no", "REDIRECT", "/climate/",
                         "Alias of the office home used by its navigation.", "Assumed to be the same page as /; not fetched.", "redirect-planned")
        if path == "/climate_maps.html":
            return _rule("climate-maps", "https://climate.geo.msu.edu/climate_maps.html", "html-page", "no", "REBUILD", "/climate/maps/",
                         "Directory of 27 Michigan Climate Watch maps (7, 30 and 90 days).", "Map images are hosted by MRCC and were not captured.", "rebuilt")
        if path in ("/about_us.html", "/semcog/sem/mainsem.html", "/climate_mi/index.html"):
            purpose = {"/about_us.html": "About the office.", "/semcog/sem/mainsem.html": "SEMCOG precipitation data.",
                       "/climate_mi/index.html": "Climate statistics: map linked to historical climatological summary tables."}[path]
            return _rule("climate-content-page", "https://climate.geo.msu.edu/{about_us.html|semcog/…|climate_mi/…}", "html-page", "unknown",
                         "NEEDS INVESTIGATION", None, purpose, NOT_CAPTURED, "not-preserved")
        if asset:
            return _rule("climate-layout-asset", "https://climate.geo.msu.edu/images/…, style.css", "layout-asset", "no", "ARCHIVE", None,
                         "Legacy layout image or stylesheet.", "Superseded by the new design system; not needed by the rebuild.", "superseded")

    if site == "external":
        if host == "mrcc.purdue.edu":
            return _rule("external-mrcc-map", "https://mrcc.purdue.edu/files/cliwatch/state_climatologists/michigan/{product}-{7|30|90}days.png", "image", "yes",
                         "EXTERNAL DEPENDENCY", None, "Climate Watch map image hosted by the Midwestern Regional Climate Center.",
                         "Hot-linked by the legacy page. Not captured; no text or table equivalent was found in the captured pages.", "link-out")
        if host.endswith("noaa.gov"):
            return _rule("external-noaa-cpc", "http://www.cpc.ncep.noaa.gov/products/predictions/{product}/", "html-page", "yes",
                         "EXTERNAL DEPENDENCY", None, "NOAA Climate Prediction Center outlook page.", "Authoritative external provider; link out rather than copy.", "link-out")
        return _rule("external-reference-link", "{external site}", "external-link", "unknown", "EXTERNAL DEPENDENCY", None,
                     "Outbound link to a partner, sponsor or related site.", "Target not checked; several are plain-http links.", "link-out")

    return _rule("unclassified", url, "unknown", "unknown", "NEEDS INVESTIGATION", None, "Not matched by any inventory rule.", NOT_CAPTURED, "not-preserved")


def site_of(url: str) -> str:
    return LEGACY_HOSTS.get(urlparse(url).hostname or "", "external")
