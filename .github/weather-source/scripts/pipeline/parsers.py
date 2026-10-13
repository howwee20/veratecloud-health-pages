"""Parsers for the captured legacy pages.

Rules that every parser in this module follows:

* Source strings are kept verbatim in a ``raw`` field. Numbers are parsed
  next to them, never instead of them.
* Missing-value markers used by the source (``--``, ``---``, ``NA``) are
  preserved as markers. They are never converted to zero or dropped.
* When the source layout is not exactly what the parser expects, the parser
  raises instead of guessing. A failed build is better than a mislabelled
  column.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

MISSING_MARKERS = ("--", "---", "NA")
DECLARED_CHARSET = "iso-8859-1"  # every captured page declares this or is plain ASCII


class SourceFormatError(ValueError):
    """The captured source does not look the way the parser requires."""


def soup_of(data: bytes) -> BeautifulSoup:
    return BeautifulSoup(data.decode(DECLARED_CHARSET), "lxml")


def clean(text: str | None) -> str:
    """Collapse whitespace (including non-breaking spaces) for labels and prose."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def segments(element: Tag, page_url: str) -> list[dict]:
    """Prose with its inline links kept, as ``[{"text": ..., "url": ...|None}]``."""
    out: list[dict] = []

    def push(text: str, url: str | None) -> None:
        text = re.sub(r"\s+", " ", text.replace("\xa0", " "))
        if not text:
            return
        if out and out[-1]["url"] is None and url is None:
            out[-1]["text"] += text
        else:
            out.append({"text": text, "url": url})

    def walk(node, url):
        for child in node.children:
            if isinstance(child, Tag):
                if child.name == "br":
                    push(" ", url)
                elif child.name == "a" and child.get("href"):
                    walk(child, urljoin(page_url, child["href"]))
                else:
                    walk(child, url)
            elif type(child) is NavigableString:
                push(str(child), url)

    walk(element, None)
    # whitespace that sat just inside a link belongs to the surrounding prose
    for i, seg in enumerate(out):
        if seg["url"] is None:
            continue
        if seg["text"].endswith(" ") and i + 1 < len(out) and out[i + 1]["url"] is None:
            out[i + 1]["text"] = " " + out[i + 1]["text"]
        if seg["text"].startswith(" ") and i > 0 and out[i - 1]["url"] is None:
            out[i - 1]["text"] += " "
        seg["text"] = seg["text"].strip()
    for seg in out:
        if seg["url"] is None:
            seg["text"] = re.sub(r" +", " ", seg["text"])
    if out:
        out[0]["text"] = out[0]["text"].lstrip()
        out[-1]["text"] = out[-1]["text"].rstrip()
    return [seg for seg in out if seg["text"]]


def plain(segs: list[dict]) -> str:
    return clean("".join(seg["text"] if seg["url"] is None else f" {seg['text']} " for seg in segs)).replace(" ,", ",").replace(" .", ".").replace(" ;", ";")


def iso_from_mdy(raw: str) -> str | None:
    """``MM/DD/YY`` or ``MM/DD/YYYY`` -> ``YYYY-MM-DD``.

    Two-digit years are read as 20YY. Returns None for partial dates such as
    ``08/??/2001`` which the maintenance log uses.
    """
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{2}|\d{4})", raw)
    if not m:
        return None
    month, day, year = m.groups()
    if len(year) == 2:
        year = "20" + year
    return f"{year}-{month}-{day}"


# ---------------------------------------------------------------------------
# Cells
# ---------------------------------------------------------------------------

def num_cell(raw: str) -> dict:
    if raw in MISSING_MARKERS:
        return {"raw": raw, "value": None, "missing": True}
    try:
        value = float(raw)
    except ValueError as exc:  # pragma: no cover - guarded by tests on real data
        raise SourceFormatError(f"expected a number or a missing marker, got {raw!r}") from exc
    return {"raw": raw, "value": value, "missing": False}


def text_cell(raw: str) -> dict:
    if raw in MISSING_MARKERS:
        return {"raw": raw, "value": None, "missing": True}
    return {"raw": raw, "value": raw, "missing": False}


# ---------------------------------------------------------------------------
# MAWN pre-generated reports (report.asp?fileid=...)
# ---------------------------------------------------------------------------

def report_text(data: bytes) -> str:
    """Return the fixed-width report text exactly as the page lays it out.

    The legacy page builds its layout from ``&nbsp;`` and ``<br>`` inside one
    table cell. Ordinary whitespace in the HTML source is insignificant (as it
    is for a browser); non-breaking spaces and line breaks are significant.
    """
    cell = soup_of(data).find("td", class_="courier2")
    if cell is None:
        raise SourceFormatError("report block (td.courier2) not found")
    parts: list[str] = []
    for node in cell.descendants:
        if isinstance(node, Tag):
            if node.name == "br":
                parts.append("\n")
            continue
        if isinstance(node, NavigableString) and type(node) is NavigableString:
            parts.append(re.sub(r"[ \t\r\n]+", " ", str(node)))
    text = "".join(parts).strip(" ")
    # ordinary spaces that sit directly next to a line break are layout noise
    text = re.sub(r" *\n *", "\n", text)
    return text.replace("\xa0", " ")


def report_lines(data: bytes) -> list[str]:
    return [line.rstrip() for line in report_text(data).split("\n")]


_RULER = re.compile(r"^=+$")


def _split_blocks(lines: list[str], title: str) -> list[dict]:
    blocks: list[dict] = []
    state = None
    for line in lines:
        stripped = line.strip()
        if stripped == title:
            blocks.append({"pre": [], "rows": [], "foot": []})
            state = "pre"
            continue
        if state is None:
            if stripped:
                raise SourceFormatError(f"unexpected text before first {title!r}: {line!r}")
            continue
        block = blocks[-1]
        if state == "pre":
            if _RULER.match(stripped):
                state = "rows"
            else:
                block["pre"].append(line)
        elif state == "rows":
            if _RULER.match(stripped):
                state = "foot"
            elif stripped:
                block["rows"].append(line)
        else:
            block["foot"].append(line)
    if not blocks:
        raise SourceFormatError(f"no {title!r} block found")
    return blocks


def _footnotes(foot: list[str]) -> list[str]:
    notes: list[str] = []
    for line in foot:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            notes.append(stripped[2:].strip())
        elif notes:
            notes[-1] = f"{notes[-1]} {stripped}"
        else:
            raise SourceFormatError(f"footnote continuation without a footnote: {line!r}")
    return notes


def _header_lines(pre: list[str], count: int) -> tuple[list[str], list[str]]:
    non_blank = [clean(line) for line in pre if line.strip()]
    if len(non_blank) < count:
        raise SourceFormatError("report header is shorter than expected")
    return non_blank[:-count], non_blank[-count:]


HOURLY_TITLE = "HOURLY WEATHER SUMMARY"
HOURLY_HEADER = [
    "Air Rel Soil Leaf Wind Solar Total",
    "Time Temp Hum Temp Wetness Dir Speed Rad Precip",
    re.compile(r"Date \((E[SD]T)\) \(F\) \(%\) \(F\) Status \(mph\) \(ly\) \(in\)"),
]
HOURLY_COLUMNS = [
    {"key": "airTemp", "label": "Air temperature", "unit": "°F", "sourceHeader": "Air Temp (F)", "type": "number"},
    {"key": "relHum", "label": "Relative humidity", "unit": "%", "sourceHeader": "Rel Hum (%)", "type": "number"},
    {"key": "soilTemp", "label": "Soil temperature", "unit": "°F", "sourceHeader": "Soil Temp (F)", "type": "number"},
    {"key": "leafWetness", "label": "Leaf wetness status", "unit": None, "sourceHeader": "Leaf Wetness Status", "type": "text"},
    {"key": "windDir", "label": "Wind direction", "unit": None, "sourceHeader": "Wind Dir", "type": "text"},
    {"key": "windSpeed", "label": "Wind speed", "unit": "mph", "sourceHeader": "Wind Speed (mph)", "type": "number"},
    {"key": "solarRad", "label": "Solar radiation", "unit": "ly", "sourceHeader": "Solar Rad (ly)", "type": "number"},
    {"key": "precip", "label": "Total precipitation", "unit": "in", "sourceHeader": "Total Precip (in)", "type": "number"},
]


def _cells(tokens: list[str], columns: list[dict]) -> dict:
    return {
        col["key"]: (num_cell(tok) if col["type"] == "number" else text_cell(tok))
        for col, tok in zip(columns, tokens, strict=True)
    }


def _marker_stats(rows: list[dict]) -> dict:
    by_marker = {marker: 0 for marker in MISSING_MARKERS}
    total = 0
    for row in rows:
        for cell in row["cells"].values():
            total += 1
            if cell["missing"]:
                by_marker[cell["raw"]] += 1
    return {
        "rowCount": len(rows),
        "cellCount": total,
        "missingCellCount": sum(by_marker.values()),
        "missingByMarker": by_marker,
        "rowsWithAnyValue": sum(1 for r in rows if any(not c["missing"] for c in r["cells"].values())),
        "rowsEntirelyMissing": sum(1 for r in rows if all(c["missing"] for c in r["cells"].values())),
    }


def parse_hourly(data: bytes) -> dict:
    blocks = _split_blocks(report_lines(data), HOURLY_TITLE)
    rows: list[dict] = []
    footnotes: list[list[str]] = []
    locations: list[list[str]] = []
    timezones: set[str] = set()
    for block in blocks:
        location, header = _header_lines(block["pre"], 3)
        if header[0] != HOURLY_HEADER[0] or header[1] != HOURLY_HEADER[1]:
            raise SourceFormatError(f"hourly header changed: {header!r}")
        tz = HOURLY_HEADER[2].fullmatch(header[2])
        if not tz:
            raise SourceFormatError(f"hourly unit line changed: {header[2]!r}")
        timezones.add(tz.group(1))
        locations.append(location)
        for line in block["rows"]:
            tokens = line.split()
            if len(tokens) != 2 + len(HOURLY_COLUMNS):
                raise SourceFormatError(f"hourly row has {len(tokens)} fields: {line!r}")
            date_raw, time_raw = tokens[0], tokens[1]
            iso = iso_from_mdy(date_raw)
            hm = re.fullmatch(r"(\d{2}):(\d{2})", time_raw)
            if iso is None or hm is None:
                raise SourceFormatError(f"hourly row date/time not understood: {line!r}")
            rows.append(
                {
                    "dateRaw": date_raw,
                    "timeRaw": time_raw,
                    "isoDate": iso,
                    "hour": int(hm.group(1)),
                    "cells": _cells(tokens[2:], HOURLY_COLUMNS),
                }
            )
        footnotes.append(_footnotes(block["foot"]))
    if len(timezones) != 1:
        raise SourceFormatError(f"mixed time-zone labels in one report: {timezones}")
    if any(loc != locations[0] for loc in locations):
        raise SourceFormatError("location lines differ between blocks")
    return {
        "kind": "hourly",
        "rawText": report_text(data),
        "reportTitle": HOURLY_TITLE,
        "location": locations[0],
        "timezoneLabel": timezones.pop(),
        "columns": HOURLY_COLUMNS,
        "days": sorted({r["isoDate"] for r in rows}),
        "rows": rows,
        "footnotes": footnotes[0],
        "footnotesIdenticalAcrossBlocks": all(f == footnotes[0] for f in footnotes),
        "blockCount": len(blocks),
        "stats": _marker_stats(rows),
    }


DAILY_TITLE = "DAILY WEATHER SUMMARY"
DAILY_HEADER = [
    "Temperatures(F) Total Average Total Total Estimated",
    "Precip Relative Wind Solar PET",
    "Air Soil Humidity",
    "Date Max Min Max Min (in) (%) (mi/day) (ly/day) (in/day)",
]
DAILY_COLUMNS = [
    {"key": "airMax", "label": "Air temperature, maximum", "short": "Air max", "unit": "°F", "sourceHeader": "Temperatures(F) Air Max", "type": "number"},
    {"key": "airMin", "label": "Air temperature, minimum", "short": "Air min", "unit": "°F", "sourceHeader": "Temperatures(F) Air Min", "type": "number"},
    {"key": "soilMax", "label": "Soil temperature, maximum", "short": "Soil max", "unit": "°F", "sourceHeader": "Temperatures(F) Soil Max", "type": "number"},
    {"key": "soilMin", "label": "Soil temperature, minimum", "short": "Soil min", "unit": "°F", "sourceHeader": "Temperatures(F) Soil Min", "type": "number"},
    {"key": "precip", "label": "Total precipitation", "short": "Precip", "unit": "in", "sourceHeader": "Total Precip (in)", "type": "number"},
    {"key": "relHum", "label": "Average relative humidity", "short": "Avg RH", "unit": "%", "sourceHeader": "Average Relative Humidity (%)", "type": "number"},
    {"key": "wind", "label": "Total wind", "short": "Wind", "unit": "mi/day", "sourceHeader": "Total Wind (mi/day)", "type": "number"},
    {"key": "solar", "label": "Total solar", "short": "Solar", "unit": "ly/day", "sourceHeader": "Total Solar (ly/day)", "type": "number"},
    {"key": "pet", "label": "Estimated PET", "short": "PET", "unit": "in/day", "sourceHeader": "Estimated PET (in/day)", "type": "number"},
]


def parse_daily(data: bytes) -> dict:
    blocks = _split_blocks(report_lines(data), DAILY_TITLE)
    rows: list[dict] = []
    footnotes: list[list[str]] = []
    locations: list[list[str]] = []
    for block in blocks:
        location, header = _header_lines(block["pre"], 4)
        if header != DAILY_HEADER:
            raise SourceFormatError(f"daily header changed: {header!r}")
        locations.append(location)
        for line in block["rows"]:
            tokens = line.split()
            if len(tokens) != 1 + len(DAILY_COLUMNS):
                raise SourceFormatError(f"daily row has {len(tokens)} fields: {line!r}")
            iso = iso_from_mdy(tokens[0])
            if iso is None:
                raise SourceFormatError(f"daily row date not understood: {line!r}")
            rows.append({"dateRaw": tokens[0], "isoDate": iso, "cells": _cells(tokens[1:], DAILY_COLUMNS)})
        footnotes.append(_footnotes(block["foot"]))
    if any(loc != locations[0] for loc in locations):
        raise SourceFormatError("location lines differ between blocks")
    return {
        "kind": "daily",
        "rawText": report_text(data),
        "reportTitle": DAILY_TITLE,
        "location": locations[0],
        "columns": DAILY_COLUMNS,
        "months": sorted({r["isoDate"][:7] for r in rows}),
        "rows": rows,
        "footnotes": footnotes[0],
        "footnotesIdenticalAcrossBlocks": all(f == footnotes[0] for f in footnotes),
        "blockCount": len(blocks),
        "stats": _marker_stats(rows),
    }


_ENTRY = re.compile(r"^(\d{2}/[\d?]{2}/\d{4}):\s*(.*)$")
_BRACKET = re.compile(r"\s*\[(\d{4})\]\s*$")


def _dedent(lines: list[str]) -> list[str]:
    while lines and not lines[0].strip():
        lines = lines[1:]
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    indents = [len(line) - len(line.lstrip(" ")) for line in lines if line.strip()]
    cut = min(indents) if indents else 0
    return [line[cut:] if line.strip() else "" for line in lines]


def parse_maintenance(data: bytes) -> dict:
    """Split the station-notes text into dated entries.

    The text itself is kept verbatim in ``rawText``. Entry bodies are the
    original lines with only their shared left indentation removed.
    """
    text = report_text(data)
    lines = [line.rstrip() for line in text.split("\n")]
    title = None
    entries: list[dict] = []
    current: dict | None = None
    section = 0
    for line in lines:
        stripped = line.strip()
        if _RULER.match(stripped):
            current = None
            section += 1
            continue
        if title is None and stripped.startswith("Station Notes"):
            title = stripped.rstrip(":")
            continue
        m = _ENTRY.match(stripped) if line[:1] != " " else None
        if m:
            heading = m.group(2)
            code = None
            b = _BRACKET.search(heading)
            if b:
                code = b.group(1)
                heading = heading[: b.start()]
            current = {
                "dateRaw": m.group(1),
                "isoDate": iso_from_mdy(m.group(1)),
                "heading": clean(heading).rstrip(":").strip() or None,
                "bracketCode": code,
                "section": section,
                "_body": [],
            }
            entries.append(current)
            continue
        if current is not None:
            current["_body"].append(line)
        elif stripped:
            raise SourceFormatError(f"maintenance text outside any entry: {line!r}")
    if title is None or not entries:
        raise SourceFormatError("maintenance notes not recognised")
    for entry in entries:
        entry["body"] = _dedent(entry.pop("_body"))
    dated = [e["isoDate"] for e in entries if e["isoDate"]]
    return {
        "kind": "maintenance",
        "title": title,
        "entries": entries,
        "entryCount": len(entries),
        "entriesWithPartialDate": sum(1 for e in entries if e["isoDate"] is None),
        "firstIsoDate": min(dated),
        "lastIsoDate": max(dated),
        "rawText": text,
    }


# ---------------------------------------------------------------------------
# MAWN station page (station.asp?id=...)
# ---------------------------------------------------------------------------

def parse_station(data: bytes, page_url: str) -> dict:
    soup = soup_of(data)
    info: dict[str, str] = {}
    for label in soup.find_all("td", class_="infotablelabel"):
        key = clean(label.get_text()).rstrip(":")
        value_cell = label.find_next_sibling("td", class_="infotabledata")
        if key and value_cell is not None:
            info[key] = clean(value_cell.get_text())
    required = ["Station", "Station ID", "Location", "City", "Latitude", "Longitude", "Elevation"]
    missing = [k for k in required if k not in info]
    if missing:
        raise SourceFormatError(f"station page lacks fields: {missing}")

    def number(raw: str, pattern: str) -> float:
        m = re.fullmatch(pattern, raw)
        if not m:
            raise SourceFormatError(f"unexpected value {raw!r}")
        return float(m.group(1))

    reports = []
    for a in soup.find_all("a", href=True):
        if "report.asp" in a["href"]:
            url = urljoin(page_url, a["href"])
            reports.append({"label": clean(a.get_text()), "url": url, "fileid": parse_qs(urlparse(url).query)["fileid"][0]})
    custom = []
    select = soup.find("select", attrs={"name": "rtype"})
    if select is not None:
        for option in select.find_all("option"):
            url = urljoin(page_url, option.get("value", ""))
            rt = parse_qs(urlparse(url).query).get("rt")
            if rt:
                custom.append({"label": clean(option.get_text()), "url": url, "rt": rt[0]})
    note = soup.find("font", attrs={"color": "#FF0000"})
    photo = soup.find("img", src=re.compile(r"images/stations/"))
    return {
        "id": info["Station ID"],
        "stationName": info["Station"],
        "location": info["Location"],
        "city": info["City"],
        "latitude": {"raw": info["Latitude"], "value": number(info["Latitude"], r"(-?\d+\.\d+) deg\.")},
        "longitude": {"raw": info["Longitude"], "value": number(info["Longitude"], r"(-?\d+\.\d+) deg\.")},
        "elevation": {"raw": info["Elevation"], "value": number(info["Elevation"], r"(-?\d+(?:\.\d+)?) m"), "unit": "m"},
        "reportLinks": reports,
        "customReportTypes": custom,
        "customReportNotice": clean(note.find_parent("div").get_text()) if note is not None and note.find_parent("div") else None,
        "photoUrl": urljoin(page_url, photo["src"]) if photo is not None else None,
    }


# ---------------------------------------------------------------------------
# MAWN home page
# ---------------------------------------------------------------------------

_GROUPS = {
    "Michgan Tower (10m) Stations": "tower-10m",
    "Michgan Tower (20m) Stations": "tower-20m",
    "Retired Stations": "retired",
    "Michigan Stations": "michigan",
}


def parse_mawn_home(data: bytes, page_url: str) -> dict:
    soup = soup_of(data)
    stations: list[dict] = []
    seen: set[str] = set()
    for header in soup.find_all("td", class_="tableheader"):
        heading = clean(header.get_text())
        if heading not in _GROUPS:
            continue
        table = header.find_parent("table")
        for a in table.find_all("a", href=re.compile(r"station\.asp\?id=")):
            sid = parse_qs(urlparse(a["href"]).query)["id"][0]
            label = clean(a.get_text())
            entry = {
                "id": sid,
                "name": label,
                "listedAs": label,
                "group": _GROUPS[heading],
                "sourceGroupHeading": heading,
                "retiredDateRaw": None,
                "towerHeightRaw": None,
                "legacyUrl": urljoin(page_url, a["href"]),
            }
            if _GROUPS[heading] == "retired":
                m = re.fullmatch(r"(.*?)\s*\((\d{2}/\d{2}/\d{4})\)", label)
                if not m:
                    raise SourceFormatError(f"retired station without a date: {label!r}")
                entry["name"], entry["retiredDateRaw"] = m.group(1), m.group(2)
            tower = re.search(r"\[(\d+m)\]$", label)
            if tower:
                entry["towerHeightRaw"] = tower.group(1)
            if sid in seen:
                raise SourceFormatError(f"station id listed twice in tables: {sid}")
            seen.add(sid)
            stations.append(entry)

    image_map = soup.find("map", attrs={"name": "MawnMap"})
    areas = {}
    coords: dict[str, list[int]] = {}
    if image_map is not None:
        for area in image_map.find_all("area", href=re.compile(r"station\.asp\?id=")):
            sid = parse_qs(urlparse(area["href"]).query)["id"][0]
            areas[sid] = clean(area.get("alt"))
            coords[sid] = [float(v) for v in area.get("coords", "").split(",")[:2]]
    for station in stations:
        station["onLegacyImageMap"] = station["id"] in areas
        station["imageMapLabel"] = areas.get(station["id"])
        station["imageMapPixel"] = coords.get(station["id"])
    map_only = [{"id": sid, "imageMapLabel": label} for sid, label in areas.items() if sid not in seen]

    conditions = None
    wx_cells = soup.find_all("td", class_="wxtablelabel")
    if wx_cells:
        wx_table = wx_cells[0].find_parent("table")
        heading_cell = wx_table.find("td", class_=re.compile("tableheader"))
        if heading_cell is None:
            heading_cell = wx_table.find_previous("td", class_=re.compile("tableheader"))
        items = []
        for label in wx_cells:
            key = clean(label.get_text()).rstrip(":")
            value_cell = label.find_next_sibling("td")
            value = clean(value_cell.get_text()) if value_cell is not None else ""
            if key and value:
                items.append({"label": key, "raw": value})
        conditions = {"headingRaw": clean(heading_cell.get_text()) if heading_cell else None, "items": items}

    intro = [segments(p, page_url) for p in soup.find_all("p", class_=["textlarge", "textreg"]) if clean(p.get_text())]
    picker = [clean(p.get_text()) for p in soup.find_all("p", class_="textsmall") if clean(p.get_text())]
    regional = [
        {"label": clean(area.get("alt")) or None, "url": urljoin(page_url, area["href"])}
        for area in soup.find_all("area", href=re.compile(r"mawn-\w+\.html"))
    ]
    return {
        "stations": stations,
        "imageMapOnlyStations": map_only,
        "imageMapAreaCount": len(areas),
        "imageMapSize": [int(map_img["width"]), int(map_img["height"])] if (map_img := soup.find("img", usemap="#MawnMap")) else None,
        "recentConditions": conditions,
        "intro": intro,
        "stationPickerInstruction": picker,
        "regionalMapLinks": regional,
    }


# ---------------------------------------------------------------------------
# Raw-data directory listings and files
# ---------------------------------------------------------------------------

_LISTING_ROW = re.compile(
    r'<a href="(?P<href>[^"]+)">(?P<name>[^<]+)</a>\s+(?P<modified>\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s+(?P<size>\S+)'
)


def parse_apache_listing(data: bytes, page_url: str) -> dict:
    text = data.decode(DECLARED_CHARSET)
    title = re.search(r"<title>(.*?)</title>", text, flags=re.S)
    entries = []
    for m in _LISTING_ROW.finditer(text):
        name = m.group("name")
        is_dir = m.group("href").endswith("/")
        entries.append(
            {
                "name": name,
                "href": m.group("href"),
                "url": urljoin(page_url, m.group("href")),
                "type": "directory" if is_dir else "file",
                "lastModifiedRaw": m.group("modified"),
                "sizeRaw": m.group("size"),
            }
        )
    if not entries:
        raise SourceFormatError("no entries recognised in directory listing")
    return {"title": clean(title.group(1)) if title else None, "entries": entries}


def describe_raw_file(data: bytes) -> dict:
    """Describe a raw logger file structurally, without interpreting any field."""
    text = data.decode("ascii")  # raises if the file is not plain ASCII
    lines = text.split("\n")
    trailing_newline = lines[-1] == ""
    if trailing_newline:
        lines = lines[:-1]
    record_types: dict[str, dict] = {}
    records = []
    for number, line in enumerate(lines, start=1):
        fields = line.split(",")
        first = fields[0]
        info = record_types.setdefault(first, {"firstField": first, "lineCount": 0, "fieldCounts": set()})
        info["lineCount"] += 1
        info["fieldCounts"].add(len(fields))
        records.append({"line": number, "firstField": first, "fields": fields})
    for info in record_types.values():
        info["fieldCounts"] = sorted(info["fieldCounts"])
    return {
        "lineCount": len(lines),
        "endsWithNewline": trailing_newline,
        "lineEnding": "CRLF" if "\r\n" in text else "LF",
        "delimiter": ",",
        "hasHeaderRow": False,
        "recordTypes": sorted(record_types.values(), key=lambda r: r["firstField"]),
        "records": records,
    }


# ---------------------------------------------------------------------------
# Agricultural Weather Office
# ---------------------------------------------------------------------------

def _agweather_common(soup: BeautifulSoup, page_url: str) -> dict:
    nav = []
    for cell in soup.find_all("td", class_="navbarfont"):
        for a in cell.find_all("a", href=True):
            label = clean(a.get_text())
            if label:
                nav.append({"label": label, "url": urljoin(page_url, a["href"])})
    texts = [clean(c.get_text()) for c in soup.find_all("td", class_="navbarfont")]
    stamp = next((t for t in texts if re.fullmatch(r"\d{2}/\d{2}/\d{2} - \d{2}:\d{2}", t)), None)
    feeds = [t for t in texts if re.fullmatch(r"\w+ : \w+", t)]
    h1 = soup.find("h1")
    h2 = soup.find("h2")
    return {
        "siteTitle": clean(h1.get_text()) if h1 else None,
        "pageHeading": clean(h2.get_text()) if h2 else None,
        "navigation": nav,
        "pageStampRaw": stamp,
        "datafeedStatusRaw": feeds,
    }


def parse_agweather_products(data: bytes, page_url: str) -> dict:
    """Walk the product tables on /current/ and /forecasts/ in document order."""
    soup = soup_of(data)
    common = _agweather_common(soup, page_url)
    sections: list[dict] = []
    for row in soup.find_all("tr"):
        if row.find("table") is not None:
            continue  # layout wrapper, its inner rows are visited on their own
        header = row.find("td", class_="tableheader1")
        if header is not None:
            sections.append({"heading": clean(header.get_text()).rstrip(":"), "groups": [{"label": None, "links": []}]})
            continue
        if not sections:
            continue
        anchors = [a for a in row.find_all("a", href=True) if clean(a.get_text())]
        text = clean(row.get_text())
        if anchors:
            for a in anchors:
                label = clean(a.get_text())
                context = text if text != label else None
                sections[-1]["groups"][-1]["links"].append(
                    {"label": label, "url": urljoin(page_url, a["href"]), "rowText": context}
                )
        elif text and row.find("b") is not None:
            sections[-1]["groups"].append({"label": text.rstrip(":"), "links": []})
        elif not text and sections[-1]["groups"][-1]["links"]:
            sections[-1]["groups"].append({"label": None, "links": []})
    for section in sections:
        section["groups"] = [g for g in section["groups"] if g["links"]]
    sections = [s for s in sections if s["groups"]]
    if not sections:
        raise SourceFormatError("no product sections recognised")
    return {**common, "sections": sections}


def parse_agweather_home(data: bytes, page_url: str) -> dict:
    soup = soup_of(data)
    common = _agweather_common(soup, page_url)
    news = []
    news_header = soup.find("td", class_="tableheader0", string=re.compile("News"))
    if news_header is not None:
        cell = news_header.find_parent("table").find("td", class_="arial2")
        for bold in cell.find_all("b"):
            heading = clean(bold.get_text())
            m = re.fullmatch(r"(.+?) - (\d{2}/\d{2}/\d{4}):", heading)
            if not m:
                continue
            ul = bold.find_next("ul")
            item = ul.find("li") if ul else None
            link = item.find("a", href=True) if item else None
            kind = item.find("b") if item else None
            body = clean(item.get_text()) if item else ""
            kind_text = clean(kind.get_text()) if kind else ""
            news.append(
                {
                    "category": m.group(1),
                    "dateRaw": m.group(2),
                    "isoDate": iso_from_mdy(m.group(2)),
                    "kind": kind_text.rstrip(":") or None,
                    "text": clean(body[len(kind_text):]) if kind_text and body.startswith(kind_text) else body,
                    "link": {"label": clean(link.get_text()), "url": urljoin(page_url, link["href"])} if link else None,
                }
            )
    additions = []
    add_header = soup.find("td", class_="tableheader0", string=re.compile("New Enviro-Weather Stations"))
    coming_soon_text = None
    if add_header is not None:
        cell_text = add_header.find_parent("table").get_text("\n")
        for line in cell_text.split("\n"):
            m = re.fullmatch(r"(.+?) \[(\d{2}/\d{2}/\d{4})\]", clean(line))
            if m:
                additions.append({"name": m.group(1), "dateRaw": m.group(2), "isoDate": iso_from_mdy(m.group(2))})
        after = clean(cell_text.split("Coming Soon:")[-1]) if "Coming Soon:" in cell_text else None
        coming_soon_text = after or None
    prose = {}
    for cell in soup.find_all("td"):
        if cell.find("table") is not None:
            continue
        text = clean(cell.get_text())
        if text.startswith("Activities of the MSU Agricultural Weather Office"):
            prose["support"] = segments(cell, page_url)
        elif text.startswith("For more information - write or call"):
            parts = [clean(part) for part in cell.get_text("\n").split("\n") if clean(part)]
            while len(parts) > 1 and not parts[0].endswith(":"):
                parts[:2] = [f"{parts[0]} {parts[1]}"]
            prose["contactLines"] = parts
        elif text.startswith("Enviro-Weather :"):
            prose["enviroweatherBlurb"] = text
        elif "Wheat Harvest" in text and len(text) < 80:
            prose["photoCaption"] = text
    return {**common, "news": news, "recentAdditions": additions, "comingSoonText": coming_soon_text, **prose}


# ---------------------------------------------------------------------------
# State Climatologist's Office
# ---------------------------------------------------------------------------

def _climate_common(soup: BeautifulSoup, page_url: str) -> dict:
    menu = soup.find("ul", class_="sidemenu")
    nav = [
        {"label": clean(a.get_text()), "url": urljoin(page_url, a["href"])}
        for a in (menu.find_all("a", href=True) if menu else [])
    ]
    footer = soup.find(id="footer_content")
    footer_text = clean(footer.get_text(" ")) if footer else None
    updated = re.search(r"Last updated: ([A-Za-z]+ \d{1,2}, \d{4})", footer_text or "")
    return {"navigation": nav, "footerText": footer_text, "lastUpdatedRaw": updated.group(1) if updated else None}


def parse_climate_home(data: bytes, page_url: str) -> dict:
    soup = soup_of(data)
    middle = soup.find(id="content_middle")
    if middle is None:
        raise SourceFormatError("climate home: content_middle not found")
    paragraphs = [segments(p, page_url) for p in middle.find_all("p") if clean(p.get_text())]
    heading = middle.find("h1")
    right = soup.find(id="content_right")
    thumbs = [
        {"alt": clean(img.get("alt")), "imageUrl": urljoin(page_url, img["src"])}
        for img in (right.find_all("img", src=True) if right else [])
    ]
    return {
        **_climate_common(soup, page_url),
        "heading": clean(heading.get_text()) if heading else None,
        "paragraphs": paragraphs,
        "sidebarThumbnails": thumbs,
    }


def parse_climate_maps(data: bytes, page_url: str) -> dict:
    soup = soup_of(data)
    middle = soup.find(id="page2_middle")
    if middle is None:
        raise SourceFormatError("climate maps: page2_middle not found")
    heading = middle.find("h1")
    intro_p = heading.find_next("p") if heading else None
    intro = [clean(part) for part in intro_p.get_text("\n").split("\n") if clean(part)] if intro_p else []
    groups = []
    for label in middle.find_all("p", class_="bg_shading"):
        table = label.find_next("table")
        maps = []
        images = table.find_all("img", src=True)
        captions = [clean(a.get_text()) for a in table.find_all("a") if clean(a.get_text())]
        if len(images) != len(captions):
            raise SourceFormatError(f"climate maps: {len(images)} images but {len(captions)} captions")
        for img, caption in zip(images, captions, strict=True):
            maps.append(
                {
                    "period": caption,
                    "sourceAlt": clean(img.get("alt")),
                    "imageUrl": urljoin(page_url, img["src"]),
                    "imageHost": urlparse(urljoin(page_url, img["src"])).hostname,
                    "declaredWidth": img.get("width"),
                    "declaredHeight": img.get("height"),
                }
            )
        groups.append({"title": clean(label.get_text()), "maps": maps})
    if not groups:
        raise SourceFormatError("climate maps: no map groups recognised")
    return {
        **_climate_common(soup, page_url),
        "heading": clean(heading.get_text()) if heading else None,
        "intro": intro,
        "groups": groups,
    }
