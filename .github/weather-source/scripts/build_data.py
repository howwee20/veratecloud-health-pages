#!/usr/bin/env python3
"""Turn the local source pack into versioned, structured data for the site.

    .venv/bin/python -I scripts/build_data.py

This script is offline. It reads ``data/source-snapshots/weather-source-pack``
and writes ``data/normalized``, ``data/site-inventory.json``,
``reports/url-inventory.csv``, ``deploy/legacy-url-map.csv`` and the
byte-preserved files under ``public``. It never opens a network connection.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline import inventory as inv  # noqa: E402
from pipeline import parsers as P  # noqa: E402

# SOURCE_PACK lets a reviewed refresh directory be built from instead (see scripts/refresh_sources.py).
PACK = Path(os.environ.get("SOURCE_PACK") or ROOT / "data" / "source-snapshots" / "weather-source-pack").resolve()
PACK_LABEL = str(PACK.relative_to(ROOT)) if PACK.is_relative_to(ROOT) else str(PACK)
OUT = ROOT / "data" / "normalized"
PUBLIC = ROOT / "public"
SCHEMA_VERSION = 1


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_sources() -> dict[str, dict]:
    """Read manifest.csv, verify every file against its recorded SHA-256."""
    receipts = {r["url"]: r for r in json.loads((PACK / "receipts" / "requests.json").read_text())}
    sources: dict[str, dict] = {}
    with (PACK / "manifest.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            data = (PACK / row["file"]).read_bytes()
            digest = sha256(data)
            if digest != row["sha256"] or len(data) != int(row["bytes"]):
                raise SystemExit(f"checksum or size mismatch for {row['file']}; refusing to build")
            headers = {k.lower(): v for k, v in receipts[row["url"]]["headers"].items()}
            source_id = row["file"].removeprefix("input/").replace("/", "-").removesuffix(".html")
            sources[source_id] = {
                "id": source_id,
                "url": row["url"],
                "file": row["file"],
                "packPath": f"{PACK_LABEL}/{row['file']}",
                "httpStatus": int(row["status"]),
                "bytes": len(data),
                "sha256": digest,
                "sha256Verified": True,
                "retrievedAtUtc": row["retrieved_at_utc"],
                "title": row["title"],
                "responseHeaders": {
                    k: headers.get(k.lower())
                    for k in ("Date", "Server", "Content-Type", "Last-Modified", "Cache-Control",
                              "X-Content-Type-Options", "X-Frame-Options", "Content-Security-Policy",
                              "Strict-Transport-Security", "Referrer-Policy", "Permissions-Policy")
                },
                "_data": data,
            }
    return sources


def public_source(source: dict) -> dict:
    return {k: v for k, v in source.items() if not k.startswith("_")}


def ref(source: dict) -> dict:
    return {k: source[k] for k in ("id", "url", "file", "sha256", "retrievedAtUtc")}


# ---------------------------------------------------------------------------
# Raw-file cross-check (an observation, not a schema)
# ---------------------------------------------------------------------------

COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
CONVERSIONS = [
    ("identity", "no conversion", lambda x: x),
    ("c-to-f", "°C to °F (x × 9/5 + 32)", lambda x: x * 9 / 5 + 32),
    ("ms-to-mph", "m/s to mph (x × 2.2369363)", lambda x: x * 2.2369363),
    ("kj-to-ly", "kJ/m² to langleys (x ÷ 41.84)", lambda x: x / 41.84),
    ("mm-to-in", "mm to inches (x ÷ 25.4)", lambda x: x / 25.4),
]


def crosscheck(raw: dict, hourly: dict) -> dict:
    """Compare 20-field raw records with the labelled hourly report.

    Working assumption being tested: fields 2, 3 and 4 are year, day of year
    and HHMM on the same clock the hourly report uses for its time labels.
    """
    by_key = {(row["isoDate"], row["hour"]): row for row in hourly["rows"]}
    pairs = []
    for record in raw["records"]:
        fields = record["fields"]
        if len(fields) != 20:
            continue
        year, doy, hhmm = int(fields[1]), int(fields[2]), int(fields[3])
        if hhmm % 100:
            continue
        iso = (date(year, 1, 1) + timedelta(days=doy - 1)).isoformat()
        row = by_key.get((iso, hhmm // 100))
        if row is not None:
            pairs.append((record, row))
    matches = []
    for index in range(4, 20):
        for column in hourly["columns"]:
            cells = [(rec, row["cells"][column["key"]], row) for rec, row in pairs]
            cells = [(rec, cell, row) for rec, cell, row in cells if not cell["missing"]]
            if not cells:
                continue
            if column["type"] == "text":
                if column["key"] != "windDir":
                    continue
                detail = []
                for rec, cell, row in cells:
                    degrees = float(rec["fields"][index])
                    if not 0 <= degrees <= 360:
                        detail = []
                        break
                    converted = COMPASS[int((degrees + 11.25) // 22.5) % 16]
                    detail.append({"line": rec["line"], "rawField": rec["fields"][index], "converted": converted,
                                   "reported": cell["raw"], "reportRow": f"{row['dateRaw']} {row['timeRaw']}",
                                   "agrees": converted == cell["raw"]})
                if detail and all(d["agrees"] for d in detail):
                    matches.append({"fieldPosition": index + 1, "reportColumn": column["sourceHeader"],
                                    "conversion": "degrees to 16-point compass", "recordsCompared": len(detail), "detail": detail})
                continue
            for conv_id, conv_label, fn in CONVERSIONS:
                detail = []
                for rec, cell, row in cells:
                    decimals = len(cell["raw"].split(".")[1]) if "." in cell["raw"] else 0
                    converted = fn(float(rec["fields"][index]))
                    agrees = abs(converted - cell["value"]) <= 0.5 * 10 ** -decimals + 1e-9
                    detail.append({"line": rec["line"], "rawField": rec["fields"][index],
                                   "converted": f"{converted:.{decimals + 2}f}", "reported": cell["raw"],
                                   "reportRow": f"{row['dateRaw']} {row['timeRaw']}", "agrees": agrees})
                if all(d["agrees"] for d in detail):
                    matches.append({"fieldPosition": index + 1, "reportColumn": column["sourceHeader"],
                                    "conversion": conv_label, "recordsCompared": len(detail), "detail": detail})
    matched_positions = sorted({m["fieldPosition"] for m in matches})
    return {
        "status": "observation only; no schema adopted",
        "assumptionTested": "In 20-field records, field 2 is the year, field 3 the day of year and field 4 HHMM on the clock used by the hourly report's time labels.",
        "method": "Each of fields 5 to 20 was compared with each hourly-report column under five fixed unit conversions. A pairing is listed only if every overlapping record rounds to the printed report value.",
        "overlappingRecords": len(pairs),
        "overlap": [{"line": rec["line"], "reportRow": f"{row['dateRaw']} {row['timeRaw']}"} for rec, row in pairs],
        "matches": matches,
        "matchedFieldPositions": matched_positions,
        "unmatchedFieldPositions": [i for i in range(5, 21) if i not in matched_positions],
        "tenFieldRecordsCompared": 0,
        "caveats": [
            f"Based on {len(pairs)} overlapping hourly records from one station on one afternoon.",
            "Agreement to printed precision does not establish units, sensor identity, quality flags or time zone.",
            "The 10-field records have no labelled counterpart in the source pack and were not compared.",
            "A data dictionary from the maintainers is required before any raw field is labelled.",
        ],
    }


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

def build_inventory(sources: dict[str, dict], stations: list[dict], station_details: dict, listing_3hr: dict, listing_root: dict) -> list[dict]:
    captured = {inv.canonical(s["url"])[0]: s for s in sources.values()}
    refs: dict[str, dict] = {}

    def add(url: str, found_on: str | None, element: str, label: str, raw_target: str | None = None) -> None:
        key, via_js = inv.canonical(url)
        entry = refs.setdefault(key, {"foundOn": set(), "elements": set(), "labels": [], "forms": set(), "viaJs": False})
        if found_on:
            entry["foundOn"].add(found_on)
        entry["elements"].add(element)
        if label and label not in entry["labels"]:
            entry["labels"].append(label)
        entry["forms"].add(raw_target or url)
        entry["viaJs"] = entry["viaJs"] or via_js

    with (PACK / "link-inventory.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            target = row["target_url"]
            if not target or target.startswith(("mailto:", "#")):
                continue
            add(target, row["found_on_url"], row["element"], row["label"], row["raw_target"])
    for url in captured:
        add(url, None, "named-url", "")
    for detail in station_details.values():
        for option in detail["customReportTypes"]:
            add(option["url"], detail["legacyUrl"], "option", option["label"])

    listing_times = {e["url"]: e for e in listing_3hr["entries"] + listing_root["entries"]}
    outgoing: dict[str, set] = defaultdict(set)
    for key, entry in refs.items():
        for page in entry["foundOn"]:
            outgoing[inv.canonical(page)[0]].add(key)
    station_names = {s["id"]: s["name"] for s in stations}

    records = []
    for key in sorted(refs):
        entry = refs[key]
        rule = inv.classify(key)
        site = inv.site_of(key)
        source = captured.get(key)
        query = parse_qs(urlparse(key).query)
        title, title_source = None, "none"
        if source:
            title, title_source = source["title"], "page title" if source["file"].endswith(".html") else "pack manifest"
        elif entry["labels"]:
            title, title_source = entry["labels"][0], "link label on referring page"
        if rule["patternId"] == "mawn-station" and query["id"][0] in station_names:
            title, title_source = f"Station: {station_names[query['id'][0]]}", "station table on MAWN home"
        last_modified, lm_source = None, None
        if source and source["responseHeaders"].get("Last-Modified"):
            last_modified, lm_source = source["responseHeaders"]["Last-Modified"], "HTTP Last-Modified header"
        elif key in listing_times:
            last_modified, lm_source = listing_times[key]["lastModifiedRaw"], "directory listing (server clock; zone not stated in listing)"
        status = rule["prototypeStatus"]
        new_url = rule["proposedNewUrl"]
        if status == "template":
            status = "rebuilt" if source else "template-only"
        if rule["patternId"] == "rawdata-file" and source:
            status = "bytes-preserved"
        if rule["patternId"] == "rawdata-directory" and source:
            status = "rebuilt"
        found_sites = sorted({inv.SITE_NAMES[inv.site_of(u)] for u in entry["foundOn"]})
        outgoing_keys = sorted(outgoing.get(key, ()))
        records.append(
            {
                "url": key,
                "sourceWebsite": inv.SITE_NAMES[site] if site != "external" else "External (referenced by: " + ", ".join(found_sites) + ")",
                "site": site,
                "host": urlparse(key).hostname,
                "title": title,
                "titleSource": title_source,
                "resourceType": rule["resourceType"],
                "patternId": rule["patternId"],
                "patternTemplate": rule["patternTemplate"],
                "httpStatus": source["httpStatus"] if source else None,
                "httpStatusNote": None if source else "not requested",
                "lastModified": last_modified,
                "lastModifiedSource": lm_source,
                "captured": bool(source),
                "capturedAtUtc": source["retrievedAtUtc"] if source else None,
                "localFile": source["packPath"] if source else None,
                "sha256": source["sha256"] if source else None,
                "bytes": source["bytes"] if source else None,
                "discoveredOn": sorted(entry["foundOn"]),
                "referencedAs": sorted(entry["forms"]),
                "openedViaJavascriptLink": entry["viaJs"],
                "outgoingLinkCount": len(outgoing_keys) if source else None,
                "importantOutgoingLinks": [u for u in outgoing_keys if inv.classify(u)["resourceType"] != "layout-asset"][:12] if source else [],
                "purpose": rule["purpose"],
                "dynamic": rule["dynamic"],
                "externallyDependent": site == "external" or rule["patternId"] in ("climate-home", "climate-maps", "agweather-current-report", "agweather-forecast-product"),
                "treatment": rule["treatment"],
                "proposedNewUrl": new_url,
                "prototypeStatus": status,
                "limitations": rule["limitations"],
            }
        )
    return records


INVENTORY_COLUMNS = [
    ("url", "Original URL"), ("sourceWebsite", "Source website"), ("title", "Page title or resource name"),
    ("titleSource", "Title source"), ("resourceType", "Resource type"), ("patternId", "URL pattern"),
    ("httpStatus", "HTTP status"), ("httpStatusNote", "HTTP status note"), ("lastModified", "Last modified"),
    ("lastModifiedSource", "Last modified source"), ("capturedAtUtc", "Date captured (UTC)"),
    ("importantOutgoingLinks", "Important outgoing links"), ("purpose", "Main purpose"),
    ("dynamic", "Contains dynamic content"), ("externallyDependent", "Appears externally dependent"),
    ("captured", "Content captured successfully"), ("treatment", "Recommended modernization treatment"),
    ("proposedNewUrl", "Proposed new URL"), ("prototypeStatus", "Prototype status"),
    ("limitations", "Known limitations"), ("discoveredOn", "Discovered on"), ("sha256", "SHA-256 of captured bytes"),
]


def summarise_inventory(records: list[dict]) -> dict:
    patterns: dict[str, dict] = {}
    for r in records:
        p = patterns.setdefault(r["patternId"], {
            "patternId": r["patternId"], "site": r["site"], "template": r["patternTemplate"], "resourceType": r["resourceType"],
            "treatment": r["treatment"], "purpose": r["purpose"], "limitations": r["limitations"], "dynamic": r["dynamic"],
            "urlCount": 0, "capturedCount": 0, "statuses": Counter(), "examples": [], "newUrlExample": None,
        })
        p["urlCount"] += 1
        p["capturedCount"] += int(r["captured"])
        p["statuses"][r["prototypeStatus"]] += 1
        if len(p["examples"]) < 3 or r["captured"]:
            p["examples"] = ([r["url"]] + p["examples"])[:3] if r["captured"] else p["examples"] + [r["url"]]
        if r["proposedNewUrl"] and (p["newUrlExample"] is None or r["captured"]):
            p["newUrlExample"] = r["proposedNewUrl"]
    for p in patterns.values():
        p["statuses"] = dict(p["statuses"])
    sites = {}
    for site in ("mawn", "agweather", "climate", "external"):
        rows = [r for r in records if r["site"] == site]
        sites[site] = {
            "name": inv.SITE_NAMES[site],
            "discoveredUrls": len(rows),
            "capturedUrls": sum(r["captured"] for r in rows),
            "byTreatment": dict(Counter(r["treatment"] for r in rows)),
            "byPrototypeStatus": dict(Counter(r["prototypeStatus"] for r in rows)),
            "byResourceType": dict(Counter(r["resourceType"] for r in rows)),
            "patternCount": len({r["patternId"] for r in rows}),
            "contentUrls": sum(1 for r in rows if r["resourceType"] != "layout-asset"),
        }
    return {
        "totalUrls": len(records),
        "capturedUrls": sum(r["captured"] for r in records),
        "legacyHostUrls": sum(1 for r in records if r["site"] != "external"),
        "externalUrls": sum(1 for r in records if r["site"] == "external"),
        "byTreatment": dict(Counter(r["treatment"] for r in records)),
        "byPrototypeStatus": dict(Counter(r["prototypeStatus"] for r in records)),
        "sites": sites,
        "patterns": sorted(patterns.values(), key=lambda p: (["mawn", "agweather", "climate", "external"].index(p["site"]), -p["urlCount"])),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    sources = load_sources()
    data = {sid: s["_data"] for sid, s in sources.items()}

    home = P.parse_mawn_home(data["mawn-home"], sources["mawn-home"]["url"])
    hourly = P.parse_hourly(data["mawn-report-bnzh"])
    daily = P.parse_daily(data["mawn-report-bnzd"])
    maintenance = P.parse_maintenance(data["mawn-report-bnzm"])
    listing_root = P.parse_apache_listing(data["rawdata-index"], sources["rawdata-index"]["url"])
    listing_3hr = P.parse_apache_listing(data["rawdata-3hr-index"], sources["rawdata-3hr-index"]["url"])
    raw_bnz = P.describe_raw_file(data["rawdata-3hr-benzonia"])
    ag_home = P.parse_agweather_home(data["agweather-home"], sources["agweather-home"]["url"])
    ag_current = P.parse_agweather_products(data["agweather-current"], sources["agweather-current"]["url"])
    ag_forecasts = P.parse_agweather_products(data["agweather-forecasts"], sources["agweather-forecasts"]["url"])
    cl_home = P.parse_climate_home(data["climate-home"], sources["climate-home"]["url"])
    cl_maps = P.parse_climate_maps(data["climate-climate_maps"], sources["climate-climate_maps"]["url"])

    listing_names = {e["name"]: e for e in listing_3hr["entries"]}
    station_details = {}
    for sid in ("bnz", "swm"):
        src = sources[f"mawn-station-{sid}"]
        detail = P.parse_station(src["_data"], src["url"])
        if detail["id"] != sid:
            raise SystemExit(f"station page for {sid} reports id {detail['id']}")
        detail["legacyUrl"] = src["url"]
        detail["source"] = ref(src)
        raw_entry = listing_names.get(detail["stationName"])
        detail["rawFile"] = (
            {"directory": "3hr", "name": raw_entry["name"], "listing": raw_entry,
             "basis": "The station page's \"Station\" field equals a file name in the captured /rawdata/3hr/ listing."}
            if raw_entry else None
        )
        station_details[sid] = detail
    station_details["bnz"]["reports"] = {
        "hourly": ref(sources["mawn-report-bnzh"]), "daily": ref(sources["mawn-report-bnzd"]), "maintenance": ref(sources["mawn-report-bnzm"]),
    }
    station_details["swm"]["reports"] = {}

    stations = home["stations"]
    for station in stations:
        sid = station["id"]
        detail = station_details.get(sid)
        station["capture"] = {
            "stationPage": detail is not None,
            "hourly": bool(detail and "hourly" in detail["reports"]),
            "daily": bool(detail and "daily" in detail["reports"]),
            "maintenance": bool(detail and "maintenance" in detail["reports"]),
            "rawFile": sid == "bnz",
        }
        station["captureLevel"] = "full" if station["capture"]["hourly"] else ("metadata" if detail else "listed")
        station["city"] = detail["city"] if detail else None
        station["prototypeUrl"] = f"/weather-network/stations/{sid}/" if detail else None
    if home["imageMapOnlyStations"]:
        raise SystemExit("image map lists stations that are missing from the station tables")

    raw_sha = sources["rawdata-3hr-benzonia"]["sha256"]
    check = crosscheck(raw_bnz, hourly)
    header_lm = sources["rawdata-3hr-benzonia"]["responseHeaders"]["Last-Modified"]
    listed_lm = listing_names["benzonia"]["lastModifiedRaw"]
    # The listing prints minutes only, so compare at minute precision.
    offset = parsedate_to_datetime(header_lm).replace(second=0, tzinfo=None) - datetime.strptime(listed_lm, "%Y-%m-%d %H:%M")
    offset_hours = offset.total_seconds() / 3600
    if offset_hours != int(offset_hours):
        raise SystemExit(f"listing clock offset is not a whole number of hours: {offset}")
    offset_hours = int(offset_hours)
    offset_words = {0: "the same as", 4: "four hours behind", 5: "five hours behind"}.get(offset_hours, f"{abs(offset_hours)} hours {'behind' if offset_hours > 0 else 'ahead of'}")

    # ---- inventory -------------------------------------------------------
    records = build_inventory(sources, stations, station_details, listing_3hr, listing_root)
    summary = summarise_inventory(records)
    write_json(ROOT / "data" / "site-inventory.json", {
        "schemaVersion": SCHEMA_VERSION,
        "description": "Legacy URLs referenced by the 14 captured responses. 'captured: false' means the URL was seen as a link only and was never requested.",
        "sourcePack": PACK_LABEL,
        "summary": {k: v for k, v in summary.items() if k != "patterns"},
        "patterns": summary["patterns"],
        "resources": records,
    })
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    with (reports / "url-inventory.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([label for _, label in INVENTORY_COLUMNS])
        for r in records:
            writer.writerow(["; ".join(v) if isinstance(v := r[key], list) else ("" if v is None else v) for key, _ in INVENTORY_COLUMNS])
    (PUBLIC / "downloads").mkdir(parents=True, exist_ok=True)
    deploy = ROOT / "deploy"
    deploy.mkdir(exist_ok=True)
    with (deploy / "legacy-url-map.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["legacy_url", "treatment", "proposed_new_url", "prototype_status", "pattern"])
        for r in records:
            if r["site"] != "external" and r["treatment"] in ("REBUILD", "PRESERVE", "REDIRECT"):
                writer.writerow([r["url"], r["treatment"], r["proposedNewUrl"] or "", r["prototypeStatus"], r["patternId"]])

    # ---- normalized data -------------------------------------------------
    for stale in OUT.glob("*.json"):
        if stale.name not in ("evidence.json", "dependency-audit.json", "additional-sources.json", "legacy-assets.json", "map-descriptions.json"):  # written by scripts/qa/*
            stale.unlink()
    write_json(OUT / "sources.json", {
        "schemaVersion": SCHEMA_VERSION,
        "pack": {
            "path": PACK_LABEL,
            "retrievedOn": max(s["retrievedAtUtc"] for s in sources.values())[:10],
            "scope": "The 14 URLs named in the project brief, requested once each. No recursive crawl, no linked assets.",
            "robots": "All three hosts publish 'User-agent: * / Disallow: /'. Copies are in the pack's receipts directory.",
        },
        "sources": [public_source(s) for s in sources.values()],
        "observedResponseHeaders": {
            "note": "Presence of selected headers in the 14 recorded responses. An observation of what the server sent, not a security assessment.",
            "responses": len(sources),
            "present": {
                header: sum(1 for s in sources.values() if s["responseHeaders"].get(header))
                for header in ("X-Content-Type-Options", "X-Frame-Options", "Content-Security-Policy",
                               "Strict-Transport-Security", "Referrer-Policy", "Permissions-Policy")
            },
        },
    })
    write_json(OUT / "stations.json", {
        "schemaVersion": SCHEMA_VERSION,
        "source": ref(sources["mawn-home"]),
        "counts": dict(Counter(s["group"] for s in stations)) | {"total": len(stations)},
        "captureCounts": dict(Counter(s["captureLevel"] for s in stations)),
        "stations": stations,
    })
    write_json(OUT / "station-details.json", {"schemaVersion": SCHEMA_VERSION, "stations": station_details})
    write_json(OUT / "network-home.json", {
        "schemaVersion": SCHEMA_VERSION,
        "source": ref(sources["mawn-home"]),
        "intro": home["intro"],
        "stationPickerInstruction": home["stationPickerInstruction"],
        "regionalMapLinks": home["regionalMapLinks"],
        "imageMapAreaCount": home["imageMapAreaCount"],
        "imageMapSize": home["imageMapSize"],
        "recentConditions": home["recentConditions"],
    })
    for name, payload, sid in (("bnz-hourly", hourly, "mawn-report-bnzh"), ("bnz-daily", daily, "mawn-report-bnzd"), ("bnz-maintenance", maintenance, "mawn-report-bnzm")):
        write_json(OUT / f"{name}.json", {
            "schemaVersion": SCHEMA_VERSION, "stationId": "bnz", "source": ref(sources[sid]),
            "parsing": {
                "method": "Fixed-width text block extracted from the captured HTML (td.courier2); rows split on whitespace after the header lines were matched exactly against the expected layout.",
                "transformations": [
                    "Non-breaking spaces and <br> converted to spaces and line breaks.",
                    "Dates given as MM/DD/YY also stored as ISO dates, reading the year as 20YY.",
                    "Numeric strings also stored as numbers; the original string is kept and is what the site displays.",
                ],
                "missingValues": "The markers --, --- and NA are kept as written. The source does not define them. They are never converted to zero.",
            },
            **payload,
        })
    write_json(OUT / "rawdata.json", {
        "schemaVersion": SCHEMA_VERSION,
        "root": {"source": ref(sources["rawdata-index"]), "legacyPath": "/rawdata/", **listing_root},
        "directories": {
            "3hr": {"source": ref(sources["rawdata-3hr-index"]), "legacyPath": "/rawdata/3hr/", **listing_3hr},
        },
        "listingClock": {
            "observation": f"The listing shows benzonia as modified {listed_lm}. The HTTP Last-Modified header recorded for the same file was {header_lm}. On that evidence the listing clock was {offset_words} UTC at capture.",
            "offsetHoursBehindUtc": offset_hours,
            "scope": "Established for this one file only. The listing itself does not state a time zone.",
        },
        "files": {
            "3hr/benzonia": {
                "source": ref(sources["rawdata-3hr-benzonia"]),
                "legacyPath": "/rawdata/3hr/benzonia",
                "localPath": "/rawdata/3hr/benzonia",
                "bytes": sources["rawdata-3hr-benzonia"]["bytes"],
                "sha256": raw_sha,
                "httpLastModified": header_lm,
                "stationId": "bnz",
                "stationBasis": station_details["bnz"]["rawFile"]["basis"],
                "structure": {k: v for k, v in raw_bnz.items() if k != "records"},
                "lines": [",".join(r["fields"]) for r in raw_bnz["records"]],
                "schemaStatus": "not established",
            }
        },
    })
    write_json(OUT / "raw-crosscheck.json", {"schemaVersion": SCHEMA_VERSION, "file": "3hr/benzonia", "comparedWith": ref(sources["mawn-report-bnzh"]), **check})
    write_json(OUT / "agweather.json", {
        "schemaVersion": SCHEMA_VERSION,
        "home": {"source": ref(sources["agweather-home"]), **ag_home},
        "current": {"source": ref(sources["agweather-current"]), **ag_current},
        "forecasts": {"source": ref(sources["agweather-forecasts"]), **ag_forecasts},
    })
    write_json(OUT / "climate.json", {
        "schemaVersion": SCHEMA_VERSION,
        "home": {"source": ref(sources["climate-home"]), **cl_home},
        "maps": {"source": ref(sources["climate-climate_maps"]), **cl_maps},
    })
    lookup = {r["url"]: {"t": r["treatment"], "n": r["proposedNewUrl"], "s": r["prototypeStatus"], "p": r["patternId"]} for r in records}
    write_json(OUT / "inventory-summary.json", {"schemaVersion": SCHEMA_VERSION, **summary})
    write_json(OUT / "inventory-records.json", {"schemaVersion": SCHEMA_VERSION, "records": records})
    write_json(OUT / "legacy-url-lookup.json", lookup)

    # ---- byte-preserved and derived public files -------------------------
    raw_target = PUBLIC / "rawdata" / "3hr" / "benzonia"
    raw_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PACK / "input" / "rawdata" / "3hr" / "benzonia", raw_target)
    if sha256(raw_target.read_bytes()) != raw_sha:
        raise SystemExit("raw file copy does not match its checksum")
    captured_dir = PUBLIC / "captured-source"
    if captured_dir.exists():
        shutil.rmtree(captured_dir)
    for source in sources.values():
        if source["file"].endswith(".html"):
            target = captured_dir / (source["id"] + ".html.txt")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source["_data"])
    downloads = PUBLIC / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    with (downloads / "benzonia-hourly.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", f"time_{hourly['timezoneLabel']}_as_labelled"] + [
            c["sourceHeader"] for c in hourly["columns"]])
        for row in hourly["rows"]:
            writer.writerow([row["dateRaw"], row["timeRaw"]] + [row["cells"][c["key"]]["raw"] for c in hourly["columns"]])
    with (downloads / "benzonia-daily.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date"] + [c["sourceHeader"] for c in daily["columns"]])
        for row in daily["rows"]:
            writer.writerow([row["dateRaw"]] + [row["cells"][c["key"]]["raw"] for c in daily["columns"]])
    (downloads / "benzonia-maintenance.txt").write_text(maintenance["rawText"] + "\n", encoding="utf-8")
    (reports / "downloads-provenance.txt").write_text(
        "Derived downloads from the Michigan Weather Continuity prototype\n"
        "=================================================================\n\n"
        "benzonia-hourly.csv, benzonia-daily.csv and benzonia-maintenance.txt were\n"
        "extracted from HTML report pages captured on 2026-10-12. Cell values are the\n"
        "strings printed by the source, including the missing-value markers --, ---\n"
        "and NA, which the source does not define and which are not zero.\n\n"
        + "".join(f"{name}\n  source: {sources[sid]['url']}\n  retrieved (UTC): {sources[sid]['retrievedAtUtc']}\n  source SHA-256: {sources[sid]['sha256']}\n\n"
                  for name, sid in (("benzonia-hourly.csv", "mawn-report-bnzh"), ("benzonia-daily.csv", "mawn-report-bnzd"), ("benzonia-maintenance.txt", "mawn-report-bnzm")))
        + "The unmodified raw logger file is served byte-for-byte at /rawdata/3hr/benzonia.\n"
        "These are snapshots, not live data.\n",
        encoding="utf-8",
    )

    print(f"sources verified: {len(sources)}")
    print(f"stations: {len(stations)} {dict(Counter(s['group'] for s in stations))}")
    print(f"hourly rows: {hourly['stats']['rowCount']}  daily rows: {daily['stats']['rowCount']}  maintenance entries: {maintenance['entryCount']}")
    print(f"inventory: {summary['totalUrls']} URLs, {summary['capturedUrls']} captured, {len(summary['patterns'])} patterns")
    print(f"raw cross-check: {check['overlappingRecords']} overlapping records, matched field positions {check['matchedFieldPositions']}")


if __name__ == "__main__":
    main()
