"""Tests for the offline data pipeline, run against the real source pack.

    .venv/bin/python -I -m pytest tests/python -q

Every expected value in this file was read from the captured files under
``data/source-snapshots/weather-source-pack/input`` (as text), not copied from
the pipeline's output. Where a whole table is checked, the expectation is
re-derived here with a plain regular expression so that the comparison does
not depend on the BeautifulSoup route the parsers take.

The tests are offline. Nothing here opens a network connection.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
# ``python -I`` ignores PYTHONPATH and the working directory, so make the
# pipeline importable explicitly.
sys.path.insert(0, str(ROOT / "scripts"))

from pipeline import inventory as inv  # noqa: E402
from pipeline import parsers as P  # noqa: E402

PACK = ROOT / "data" / "source-snapshots" / "weather-source-pack"
NORMALIZED = ROOT / "data" / "normalized"
MARKERS = ("--", "---", "NA")


# ---------------------------------------------------------------------------
# Helpers and fixtures
# ---------------------------------------------------------------------------

def pack_bytes(relative: str) -> bytes:
    return (PACK / relative).read_bytes()


@pytest.fixture(scope="module")
def manifest() -> list[dict]:
    with (PACK / "manifest.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def hourly_html() -> bytes:
    return pack_bytes("input/mawn/report-bnzh.html")


@pytest.fixture(scope="module")
def daily_html() -> bytes:
    return pack_bytes("input/mawn/report-bnzd.html")


@pytest.fixture(scope="module")
def maintenance_html() -> bytes:
    return pack_bytes("input/mawn/report-bnzm.html")


@pytest.fixture(scope="module")
def hourly(hourly_html) -> dict:
    return P.parse_hourly(hourly_html)


@pytest.fixture(scope="module")
def daily(daily_html) -> dict:
    return P.parse_daily(daily_html)


@pytest.fixture(scope="module")
def maintenance(maintenance_html) -> dict:
    return P.parse_maintenance(maintenance_html)


@pytest.fixture(scope="module")
def mawn_home() -> dict:
    return P.parse_mawn_home(pack_bytes("input/mawn/home.html"), "https://mawn.geo.msu.edu/")


def independent_report_text(data: bytes) -> str:
    """The report block as text, by regex only.

    In all three captured reports the block is one physical line inside
    ``<td class="courier2">`` built from ``&nbsp;`` and ``<br>`` and nothing
    else (checked below), so two string replacements reproduce the layout.
    """
    html = data.decode("iso-8859-1")
    blocks = re.findall(r'<td class="courier2">(.*?)</td>', html, flags=re.S)
    assert len(blocks) == 1, "expected exactly one live td.courier2 block"
    block = blocks[0].strip()
    assert "\n" not in block, "report block is expected to be one physical line"
    assert set(re.findall(r"&\w+;", block)) == {"&nbsp;"}
    assert set(re.findall(r"<[^>]+>", block)) == {"<br>"}
    return block.replace("<br>", "\n").replace("&nbsp;", " ")


def independent_rows(data: bytes) -> list[list[str]]:
    """Whitespace-split data rows (lines that start with MM/DD/YY)."""
    return [
        line.split()
        for line in independent_report_text(data).split("\n")
        if re.match(r"\d{2}/\d{2}/\d{2}\s", line)
    ]


def raws(row: dict) -> list[str]:
    return [cell["raw"] for cell in row["cells"].values()]


def mutate(data: bytes, old: bytes, new: bytes, count: int = -1) -> bytes:
    """Replace and insist that the fixture really changed."""
    assert old in data, f"mutation target {old!r} not present in fixture"
    changed = data.replace(old, new, count)
    assert changed != data
    return changed


def hourly_row(hourly: dict, date_raw: str, time_raw: str) -> dict:
    found = [r for r in hourly["rows"] if r["dateRaw"] == date_raw and r["timeRaw"] == time_raw]
    assert len(found) == 1, f"{date_raw} {time_raw}: {len(found)} rows"
    return found[0]


def daily_row(daily: dict, date_raw: str) -> dict:
    found = [r for r in daily["rows"] if r["dateRaw"] == date_raw]
    assert len(found) == 1, f"{date_raw}: {len(found)} rows"
    return found[0]


# ---------------------------------------------------------------------------
# Source pack integrity
# ---------------------------------------------------------------------------

def test_manifest_lists_the_14_named_urls(manifest):
    assert len(manifest) == 14
    assert len({row["url"] for row in manifest}) == 14
    assert len({row["file"] for row in manifest}) == 14
    assert {row["status"] for row in manifest} == {"200"}


def test_every_manifest_entry_matches_its_file(manifest):
    for row in manifest:
        data = pack_bytes(row["file"])
        assert len(data) == int(row["bytes"]), row["file"]
        assert hashlib.sha256(data).hexdigest() == row["sha256"], row["file"]


def test_input_directory_holds_only_manifest_files(manifest):
    on_disk = {p.relative_to(PACK).as_posix() for p in (PACK / "input").rglob("*") if p.is_file()}
    assert on_disk == {row["file"] for row in manifest}


def test_report_blocks_are_single_line_nbsp_and_br_only(hourly_html, daily_html, maintenance_html):
    # independent_report_text asserts the structure; this makes the assumption a test of its own.
    for data in (hourly_html, daily_html, maintenance_html):
        assert independent_report_text(data)


# ---------------------------------------------------------------------------
# Hourly report (report.asp?fileid=bnzh)
# ---------------------------------------------------------------------------

def test_hourly_shape(hourly):
    assert hourly["kind"] == "hourly"
    assert hourly["reportTitle"] == "HOURLY WEATHER SUMMARY"
    assert hourly["timezoneLabel"] == "EDT"
    assert hourly["location"] == ["Mick Farms", "Benzonia"]
    assert hourly["blockCount"] == 3
    assert hourly["days"] == ["2026-10-10", "2026-10-11", "2026-10-12"]
    assert len(hourly["rows"]) == 66
    assert hourly["stats"]["rowCount"] == 66
    assert Counter(r["isoDate"] for r in hourly["rows"]) == {"2026-10-10": 24, "2026-10-11": 24, "2026-10-12": 18}


def test_hourly_columns_follow_the_source_header(hourly):
    assert [c["key"] for c in hourly["columns"]] == [
        "airTemp", "relHum", "soilTemp", "leafWetness", "windDir", "windSpeed", "solarRad", "precip",
    ]
    assert [c["sourceHeader"] for c in hourly["columns"]] == [
        "Air Temp (F)", "Rel Hum (%)", "Soil Temp (F)", "Leaf Wetness Status",
        "Wind Dir", "Wind Speed (mph)", "Solar Rad (ly)", "Total Precip (in)",
    ]
    assert [c["type"] for c in hourly["columns"]] == ["number", "number", "number", "text", "text", "number", "number", "number"]


def test_hourly_header_lines_in_the_capture_are_the_ones_the_parser_requires(hourly_html):
    lines = [re.sub(r"\s+", " ", line).strip() for line in independent_report_text(hourly_html).split("\n")]
    assert lines.count("Air Rel Soil Leaf Wind Solar Total") == 3
    assert lines.count("Time Temp Hum Temp Wetness Dir Speed Rad Precip") == 3
    assert lines.count("Date (EDT) (F) (%) (F) Status (mph) (ly) (in)") == 3
    assert P.HOURLY_HEADER[0] == "Air Rel Soil Leaf Wind Solar Total"
    assert P.HOURLY_HEADER[1] == "Time Temp Hum Temp Wetness Dir Speed Rad Precip"


def test_hourly_latest_row_10_12_18_00(hourly):
    # input/mawn/report-bnzh.html: "10/12/26 18:00  74.8  62.2  68.4    DRY     SW   2.9     17.6     --"
    row = hourly_row(hourly, "10/12/26", "18:00")
    assert row is hourly["rows"][-1]
    assert row["isoDate"] == "2026-10-12" and row["hour"] == 18
    assert raws(row) == ["74.8", "62.2", "68.4", "DRY", "SW", "2.9", "17.6", "--"]
    cells = row["cells"]
    assert cells["airTemp"] == {"raw": "74.8", "value": 74.8, "missing": False}
    assert cells["relHum"]["value"] == 62.2
    assert cells["soilTemp"]["value"] == 68.4
    assert cells["leafWetness"] == {"raw": "DRY", "value": "DRY", "missing": False}
    assert cells["windDir"] == {"raw": "SW", "value": "SW", "missing": False}
    assert cells["windSpeed"]["value"] == 2.9
    assert cells["solarRad"]["value"] == 17.6
    assert cells["precip"] == {"raw": "--", "value": None, "missing": True}


def test_hourly_fully_missing_row(hourly):
    # "10/10/26 01:00   --    --    --     ---    ---   --       --      NA"
    row = hourly_row(hourly, "10/10/26", "01:00")
    assert raws(row) == ["--", "--", "--", "---", "---", "--", "--", "NA"]
    for cell in row["cells"].values():
        assert cell["missing"] is True
        assert cell["value"] is None


def test_hourly_other_rows_read_from_the_capture(hourly):
    assert raws(hourly_row(hourly, "10/11/26", "09:00")) == ["56.3", "77.4", "56.6", "DRY", "SSE", "4.0", "2.2", "--"]
    assert raws(hourly_row(hourly, "10/12/26", "16:00")) == ["75.9", "58.3", "67.9", "DRY", "WSW", "4.2", "38.5", "--"]
    assert raws(hourly_row(hourly, "10/10/26", "20:00")) == ["--", "--", "--", "---", "---", "--", "--", "NA"]
    # The source labels the last hour of a day 24:00; the label is kept as printed.
    last_of_day = hourly_row(hourly, "10/11/26", "24:00")
    assert last_of_day["hour"] == 24 and last_of_day["isoDate"] == "2026-10-11"
    # Trailing zeros are part of the printed value and must survive.
    assert hourly_row(hourly, "10/11/26", "09:00")["cells"]["windSpeed"] == {"raw": "4.0", "value": 4.0, "missing": False}


def test_hourly_low_humidity_on_10_10_is_preserved_not_dropped(hourly):
    # "10/10/26 09:00   --    0.4  55.1    DRY    ESE   2.6      2.7     --"
    row = hourly_row(hourly, "10/10/26", "09:00")
    assert raws(row) == ["--", "0.4", "55.1", "DRY", "ESE", "2.6", "2.7", "--"]
    assert row["cells"]["relHum"] == {"raw": "0.4", "value": 0.4, "missing": False}
    assert row["cells"]["airTemp"] == {"raw": "--", "value": None, "missing": True}
    low = [r["timeRaw"] for r in hourly["rows"] if r["isoDate"] == "2026-10-10" and r["cells"]["relHum"]["raw"] == "0.4"]
    assert low == ["09:00", "10:00", "11:00", "12:00", "19:00"]
    reported = [r["cells"]["relHum"]["raw"] for r in hourly["rows"] if r["isoDate"] == "2026-10-10" and not r["cells"]["relHum"]["missing"]]
    assert reported == ["0.4", "0.4", "0.4", "0.4", "0.5", "0.5", "0.5", "0.5", "0.5", "0.5", "0.4"]


def test_hourly_missing_markers_are_preserved_and_never_zero(hourly):
    seen = Counter()
    for row in hourly["rows"]:
        for cell in row["cells"].values():
            if cell["raw"] in MARKERS:
                seen[cell["raw"]] += 1
                assert cell["missing"] is True
                assert cell["value"] is None
                assert cell["value"] != 0
            else:
                assert cell["missing"] is False
                assert cell["value"] is not None
    assert dict(seen) == {"--": 213, "---": 68, "NA": 34}
    assert hourly["stats"]["missingByMarker"] == {"--": 213, "---": 68, "NA": 34}
    assert hourly["stats"]["cellCount"] == 528
    assert hourly["stats"]["missingCellCount"] == 315
    assert hourly["stats"]["rowsEntirelyMissing"] == 34
    assert hourly["stats"]["rowsWithAnyValue"] == 32


def test_hourly_has_no_zero_values_because_the_capture_prints_none(hourly, hourly_html):
    # The captured hourly report contains no cell printed as 0, 0.0 or 0.00 ...
    printed = [token for row in independent_rows(hourly_html) for token in row[2:]]
    assert not [t for t in printed if re.fullmatch(r"-?0+(\.0+)?", t)]
    # ... so any numeric zero in the parsed data would be a fabricated value.
    numeric = [c["value"] for r in hourly["rows"] for c in r["cells"].values() if isinstance(c["value"], float)]
    assert len(numeric) == 149  # 213 reported cells minus 32 x 2 text cells (leaf wetness, wind direction)
    assert 0 not in numeric
    assert min(numeric) == 0.4


def test_hourly_every_cell_equals_an_independent_regex_extraction(hourly, hourly_html):
    expected = independent_rows(hourly_html)
    assert len(expected) == 66
    assert all(len(tokens) == 10 for tokens in expected)
    got = [[r["dateRaw"], r["timeRaw"], *raws(r)] for r in hourly["rows"]]
    assert got == expected
    for row in hourly["rows"]:
        for column in hourly["columns"]:
            cell = row["cells"][column["key"]]
            if column["type"] == "number" and not cell["missing"]:
                assert cell["value"] == float(cell["raw"])


def test_hourly_footnotes(hourly):
    assert hourly["footnotesIdenticalAcrossBlocks"] is True
    assert hourly["footnotes"] == [
        "Air temperatures taken at a height of 5-ft.",
        "Soil temperatures taken at a depth of 2-in. (under bare soil)",
        "Leaf wetness and precipitation data may not be available during the winter months (i.e. Nov.1 - Feb.29)",
        "Data provided by the Michigan Automated Weather Network (MAWN) and Enviro-weather Program.",
    ]


# ---------------------------------------------------------------------------
# Daily report (report.asp?fileid=bnzd)
# ---------------------------------------------------------------------------

def test_daily_shape(daily):
    assert daily["kind"] == "daily"
    assert daily["reportTitle"] == "DAILY WEATHER SUMMARY"
    assert daily["location"] == ["Mick Farms", "Benzonia"]
    assert daily["blockCount"] == 3
    assert daily["months"] == ["2026-08", "2026-09", "2026-10"]
    assert len(daily["rows"]) == 72
    assert Counter(r["isoDate"][:7] for r in daily["rows"]) == {"2026-08": 31, "2026-09": 30, "2026-10": 11}
    assert daily["rows"][0]["dateRaw"] == "08/01/26" and daily["rows"][0]["isoDate"] == "2026-08-01"
    assert daily["rows"][-1]["dateRaw"] == "10/11/26" and daily["rows"][-1]["isoDate"] == "2026-10-11"
    assert [c["key"] for c in daily["columns"]] == ["airMax", "airMin", "soilMax", "soilMin", "precip", "relHum", "wind", "solar", "pet"]


def test_daily_header_lines_in_the_capture_are_the_ones_the_parser_requires(daily_html):
    lines = [re.sub(r"\s+", " ", line).strip() for line in independent_report_text(daily_html).split("\n")]
    for expected in P.DAILY_HEADER:
        assert lines.count(expected) == 3, expected
    assert P.DAILY_HEADER[3] == "Date Max Min Max Min (in) (%) (mi/day) (ly/day) (in/day)"


def test_daily_complete_row(daily):
    # "08/01/26  76.5  63.9  79.4  70.5   0.11    93.4     16.2    266.2     0.084"
    row = daily_row(daily, "08/01/26")
    assert raws(row) == ["76.5", "63.9", "79.4", "70.5", "0.11", "93.4", "16.2", "266.2", "0.084"]
    assert row["cells"]["precip"] == {"raw": "0.11", "value": 0.11, "missing": False}
    assert row["cells"]["pet"] == {"raw": "0.084", "value": 0.084, "missing": False}


def test_daily_partial_row_09_30_air_minimum_missing(daily):
    # "09/30/26  67.8   --   64.5  61.4   0.44    94.4     49.4     83.4     0.026"
    row = daily_row(daily, "09/30/26")
    assert raws(row) == ["67.8", "--", "64.5", "61.4", "0.44", "94.4", "49.4", "83.4", "0.026"]
    assert row["cells"]["airMin"] == {"raw": "--", "value": None, "missing": True}
    assert [k for k, c in row["cells"].items() if c["missing"]] == ["airMin"]
    assert row["cells"]["airMax"]["value"] == 67.8


def test_daily_partial_row_10_03(daily):
    # "10/03/26   --    --   63.6  53.4    --      0.4     35.1    342.3      ---"
    row = daily_row(daily, "10/03/26")
    assert raws(row) == ["--", "--", "63.6", "53.4", "--", "0.4", "35.1", "342.3", "---"]
    assert [k for k, c in row["cells"].items() if c["missing"]] == ["airMax", "airMin", "precip", "pet"]
    assert row["cells"]["relHum"] == {"raw": "0.4", "value": 0.4, "missing": False}
    assert row["cells"]["pet"] == {"raw": "---", "value": None, "missing": True}


def test_daily_other_partial_and_empty_rows(daily):
    # "09/10/26  73.0  53.3  79.1  64.6    --      --      ---     461.2      ---"
    assert raws(daily_row(daily, "09/10/26")) == ["73.0", "53.3", "79.1", "64.6", "--", "--", "---", "461.2", "---"]
    # "10/02/26   --    --   63.7  56.7    --      --      ---     270.8      ---"
    assert raws(daily_row(daily, "10/02/26")) == ["--", "--", "63.7", "56.7", "--", "--", "---", "270.8", "---"]
    # "09/09/26   --    --    --    --     NA      --      ---      ---       ---"
    empty = daily_row(daily, "09/09/26")
    assert raws(empty) == ["--", "--", "--", "--", "NA", "--", "---", "---", "---"]
    assert all(c["missing"] and c["value"] is None for c in empty["cells"].values())
    entirely_missing = [r["dateRaw"] for r in daily["rows"] if all(c["missing"] for c in r["cells"].values())]
    assert entirely_missing == [
        "09/09/26", "09/15/26", "09/16/26",
        "10/04/26", "10/05/26", "10/06/26", "10/07/26", "10/08/26", "10/09/26", "10/10/26", "10/11/26",
    ]


def test_daily_counts_by_marker(daily):
    seen = Counter()
    for row in daily["rows"]:
        for cell in row["cells"].values():
            if cell["raw"] in MARKERS:
                seen[cell["raw"]] += 1
                assert cell["missing"] is True and cell["value"] is None
            else:
                assert cell["missing"] is False and isinstance(cell["value"], float)
                assert cell["value"] == float(cell["raw"])
    assert dict(seen) == {"--": 101, "---": 42, "NA": 11}
    assert daily["stats"]["missingByMarker"] == {"--": 101, "---": 42, "NA": 11}
    assert daily["stats"]["cellCount"] == 648
    assert daily["stats"]["missingCellCount"] == 154
    assert daily["stats"]["rowsEntirelyMissing"] == 11
    assert daily["stats"]["rowsWithAnyValue"] == 61
    assert sum(1 for r in daily["rows"] if not any(c["missing"] for c in r["cells"].values())) == 22


def test_daily_precipitation_is_missing_not_zero(daily, daily_html):
    printed = [token for row in independent_rows(daily_html) for token in row[1:]]
    assert not [t for t in printed if re.fullmatch(r"-?0+(\.0+)?", t)]
    precip = [r["cells"]["precip"] for r in daily["rows"]]
    assert sum(1 for c in precip if not c["missing"]) == 24
    assert Counter(c["raw"] for c in precip if c["missing"]) == {"--": 37, "NA": 11}
    assert all(c["value"] is None for c in precip if c["missing"])
    assert 0 not in [c["value"] for r in daily["rows"] for c in r["cells"].values()]
    assert min(c["value"] for c in precip if not c["missing"]) == 0.01


def test_daily_every_cell_equals_an_independent_regex_extraction(daily, daily_html):
    expected = independent_rows(daily_html)
    assert len(expected) == 72
    assert all(len(tokens) == 10 for tokens in expected)
    assert [[r["dateRaw"], *raws(r)] for r in daily["rows"]] == expected


# ---------------------------------------------------------------------------
# Maintenance notes (report.asp?fileid=bnzm)
# ---------------------------------------------------------------------------

def test_maintenance_counts_and_dates(maintenance):
    assert maintenance["kind"] == "maintenance"
    assert maintenance["title"] == "Station Notes - Benzonia"
    assert maintenance["entryCount"] == 52
    assert len(maintenance["entries"]) == 52
    assert maintenance["entriesWithPartialDate"] == 2
    assert maintenance["firstIsoDate"] == "2001-09-06"
    assert maintenance["lastIsoDate"] == "2023-05-11"


def test_maintenance_partial_dates_are_kept_as_printed(maintenance):
    partial = [e for e in maintenance["entries"] if e["isoDate"] is None]
    assert [(e["dateRaw"], e["heading"]) for e in partial] == [
        ("08/??/2001", "Datalogger Program (MAWN1B) Activated"),
        ("08/??/2001", "Station Installed"),
    ]
    assert maintenance["entries"][-2:] == partial
    assert partial[1]["body"] == []
    assert partial[0]["body"][0] == "Data Logger Start Times:"
    assert P.iso_from_mdy("08/??/2001") is None


def test_maintenance_entries_match_dated_lines_in_the_capture(maintenance, maintenance_html):
    text = independent_report_text(maintenance_html)
    dated = re.findall(r"^(\d{2}/[\d?]{2}/\d{4}):", text, flags=re.M)
    assert len(dated) == 52
    assert [e["dateRaw"] for e in maintenance["entries"]] == dated
    assert dated[0] == "05/11/2023" and dated[-3] == "09/06/2001"
    # The source lists newest first; dated entries must stay in that order.
    iso = [e["isoDate"] for e in maintenance["entries"] if e["isoDate"]]
    assert iso == sorted(iso, reverse=True)
    assert len(iso) == 50


def test_maintenance_first_entry(maintenance):
    first = maintenance["entries"][0]
    assert first["dateRaw"] == "05/11/2023"
    assert first["isoDate"] == "2023-05-11"
    assert first["heading"] == "Station Maintenance"
    assert first["bracketCode"] == "1155"
    assert first["body"][0] == "- routine station maintenance, including:"
    assert "   - replaced tipping-bucket rain gauge" in first["body"]
    assert first["body"][-1] == '   * canopy: cherry trees at 40" height'


def test_maintenance_bracket_codes(maintenance, maintenance_html):
    text = independent_report_text(maintenance_html)
    with_code = re.findall(r"^\d{2}/[\d?]{2}/\d{4}:.*\[(\d{4})\] *$", text, flags=re.M)
    assert len(with_code) == 36
    assert [e["bracketCode"] for e in maintenance["entries"] if e["bracketCode"]] == with_code
    # Leading zeros in the bracketed code are significant ("[0001]").
    assert next(e for e in maintenance["entries"] if e["dateRaw"] == "08/10/2017")["bracketCode"] == "0001"


def test_maintenance_raw_text_is_retained_verbatim(maintenance, maintenance_html):
    expected = independent_report_text(maintenance_html)
    assert maintenance["rawText"] == expected
    lines = maintenance["rawText"].split("\n")
    assert len(lines) == 410
    assert lines[1] == "Station Notes - Benzonia: "
    assert lines[4] == "05/11/2023: Station Maintenance:" + " " * 40 + "[1155] "
    assert "            - replaced logger (CR1000 -> CR1000) " in lines
    assert "08/??/2001:  Station Installed: " in lines
    # Typos in the source stay as they are.
    assert "instrucment check" in maintenance["rawText"]
    for entry in maintenance["entries"]:
        assert f"\n{entry['dateRaw']}:" in maintenance["rawText"]
        for body_line in entry["body"]:
            assert body_line in maintenance["rawText"]


# ---------------------------------------------------------------------------
# Station pages (station.asp?id=...)
# ---------------------------------------------------------------------------

def test_station_bnz():
    s = P.parse_station(pack_bytes("input/mawn/station-bnz.html"), "https://mawn.geo.msu.edu/station.asp?id=bnz")
    assert s["id"] == "bnz"
    assert s["stationName"] == "benzonia"
    assert s["location"] == "Mick Farms"
    assert s["city"] == "Benzonia"
    assert s["latitude"] == {"raw": "44.5593 deg.", "value": 44.5593}
    assert s["longitude"] == {"raw": "-86.1172 deg.", "value": -86.1172}
    assert s["elevation"] == {"raw": "253 m", "value": 253.0, "unit": "m"}
    assert [(r["label"], r["fileid"], r["url"]) for r in s["reportLinks"]] == [
        ("Daily Data", "bnzd", "https://mawn.geo.msu.edu/report.asp?fileid=bnzd"),
        ("Hourly Data", "bnzh", "https://mawn.geo.msu.edu/report.asp?fileid=bnzh"),
        ("Maintenance Reports", "bnzm", "https://mawn.geo.msu.edu/report.asp?fileid=bnzm"),
    ]
    assert [(c["label"], c["rt"]) for c in s["customReportTypes"]] == [
        ("Daily Data", "24"), ("Hourly Data", "60"), ("Five-Minute Data", "5"), ("Growing Degree-Day Data", "0"),
    ]
    assert s["customReportTypes"][0]["url"] == "https://mawn.geo.msu.edu/station.asp?id=bnz&rt=24"
    assert s["photoUrl"] == "https://mawn.geo.msu.edu/images/stations/bnz.jpg"
    assert s["customReportNotice"].startswith("Note: Change has been made to date/time labels.")


def test_station_swm():
    s = P.parse_station(pack_bytes("input/mawn/station-swm.html"), "https://mawn.geo.msu.edu/station.asp?id=swm")
    assert s["id"] == "swm"
    assert s["stationName"] == "swmrec"
    assert s["location"] == "MSU Southwest Michigan Research and Extension Center"
    assert s["city"] == "Benton Harbor"
    assert s["latitude"] == {"raw": "42.0841 deg.", "value": 42.0841}
    # The printed trailing zero is kept in the raw string.
    assert s["longitude"] == {"raw": "-86.3570 deg.", "value": -86.357}
    assert s["elevation"] == {"raw": "220 m", "value": 220.0, "unit": "m"}
    assert [r["fileid"] for r in s["reportLinks"]] == ["swmd", "swmh", "swmm"]
    assert [c["rt"] for c in s["customReportTypes"]] == ["24", "60", "5", "0"]
    assert len(s["customReportTypes"]) == 4
    assert all(c["url"].startswith("https://mawn.geo.msu.edu/station.asp?id=swm&rt=") for c in s["customReportTypes"])


# ---------------------------------------------------------------------------
# MAWN home page
# ---------------------------------------------------------------------------

def test_mawn_home_station_counts(mawn_home):
    stations = mawn_home["stations"]
    assert len(stations) == 119
    assert Counter(s["group"] for s in stations) == {"michigan": 95, "tower-10m": 3, "tower-20m": 2, "retired": 19}
    ids = [s["id"] for s in stations]
    assert len(set(ids)) == 119, "duplicate station ids"
    # Independent count of station anchors in the captured HTML.
    html = pack_bytes("input/mawn/home.html").decode("iso-8859-1")
    assert len(re.findall(r'<a href="/station\.asp\?id=[a-z0-9]+">', html)) == 119


def test_mawn_home_group_members(mawn_home):
    by_id = {s["id"]: s for s in mawn_home["stations"]}
    assert [(s["id"], s["name"], s["towerHeightRaw"]) for s in mawn_home["stations"] if s["group"] == "tower-10m"] == [
        ("mht", "East Lansing (MSUHORT) [10m]", "10m"),
        ("gjn", "Grand Junction [10m]", "10m"),
        ("wct", "Hart (WCMREC) [10m]", "10m"),
    ]
    assert [(s["id"], s["name"], s["towerHeightRaw"]) for s in mawn_home["stations"] if s["group"] == "tower-20m"] == [
        ("spt", "Sparta [20m]", "20m"),
        ("wmt", "Williamsburg [20m]", "20m"),
    ]
    assert by_id["bnz"]["name"] == "Benzonia" and by_id["bnz"]["group"] == "michigan"
    assert by_id["swm"]["name"] == "Benton Harbor / SWMREC" and by_id["swm"]["group"] == "michigan"
    assert by_id["bnz"]["legacyUrl"] == "https://mawn.geo.msu.edu/station.asp?id=bnz"
    assert by_id["bnz"]["retiredDateRaw"] is None
    # The source's own spelling of the tower headings is kept for traceability.
    assert by_id["mht"]["sourceGroupHeading"] == "Michgan Tower (10m) Stations"


def test_mawn_home_retired_dates_are_parsed(mawn_home):
    retired = [s for s in mawn_home["stations"] if s["group"] == "retired"]
    assert len(retired) == 19
    for s in retired:
        assert re.fullmatch(r"\d{2}/\d{2}/\d{4}", s["retiredDateRaw"]), s
        assert "(" not in s["name"], s
        assert s["listedAs"] == f"{s['name']} ({s['retiredDateRaw']})"
    got = {s["id"]: (s["name"], s["retiredDateRaw"]) for s in retired}
    assert got["alt"] == ("Arlington", "06/09/2023")
    assert got["bat"] == ("Bath", "11/05/2014")
    assert got["gde"] == ("Goodells", "10/28/2006")
    assert got["nsw"] == ("Nasewaupee / S. Door County", "08/17/2023")
    assert got["wjp"] == ("West Jacksonport", "08/18/2023")
    assert all(s["retiredDateRaw"] is None for s in mawn_home["stations"] if s["group"] != "retired")


def test_mawn_home_image_map_and_conditions(mawn_home):
    assert mawn_home["imageMapAreaCount"] == 97
    assert mawn_home["imageMapOnlyStations"] == []
    assert mawn_home["imageMapSize"] == [308, 356]
    assert sum(1 for s in mawn_home["stations"] if s["onLegacyImageMap"]) == 97
    by_id = {s["id"]: s for s in mawn_home["stations"]}
    assert by_id["bnz"]["imageMapLabel"] == "Benzonia" and by_id["bnz"]["imageMapPixel"] == [155.0, 196.0]
    assert by_id["swm"]["imageMapLabel"] == "Benton Harbor" and by_id["swm"]["imageMapPixel"] == [144.0, 322.0]
    assert [link["url"] for link in mawn_home["regionalMapLinks"]] == [
        "https://mawn.geo.msu.edu/mawn-sw.html", "https://mawn.geo.msu.edu/mawn-nw.html",
    ]
    conditions = mawn_home["recentConditions"]
    assert conditions["headingRaw"] == "Recent Conditions: East Lansing, MI"
    items = {i["label"]: i["raw"] for i in conditions["items"]}
    assert items["Date/Time"] == "Mon, 10/12/26 - 07:30 PM"
    assert items["Air Temp"] == "75.3 (F)"
    assert items["Wind Dir"] == "SW"


# ---------------------------------------------------------------------------
# Apache directory listings and the raw logger file
# ---------------------------------------------------------------------------

def test_rawdata_root_listing():
    listing = P.parse_apache_listing(pack_bytes("input/rawdata/index.html"), "https://mawn.geo.msu.edu/rawdata/")
    assert listing["title"] == "Index of /rawdata"
    assert [e["name"] for e in listing["entries"]] == [
        "1wk/", "3hr/", "3mo/", "disabled/", "mcemo/", "meta/", "mrcc/", "nrcc/", "solar_fcsts/", "unl-soysim/",
    ]
    assert len(listing["entries"]) == 10
    assert {e["type"] for e in listing["entries"]} == {"directory"}
    assert {e["sizeRaw"] for e in listing["entries"]} == {"-"}
    three_hr = listing["entries"][1]
    assert three_hr["url"] == "https://mawn.geo.msu.edu/rawdata/3hr/"
    assert three_hr["lastModifiedRaw"] == "2026-05-08 16:28"


def test_rawdata_3hr_listing():
    data = pack_bytes("input/rawdata/3hr-index.html")
    listing = P.parse_apache_listing(data, "https://mawn.geo.msu.edu/rawdata/3hr/")
    assert listing["title"] == "Index of /rawdata/3hr"
    entries = listing["entries"]
    assert len(entries) == 100
    assert data.count(b'<img src="/icons/unknown.gif"') == 100  # independent count of file rows
    assert {e["type"] for e in entries} == {"file"}
    names = [e["name"] for e in entries]
    assert len(set(names)) == 100
    assert names[0] == "aetna" and names[-1] == "wmich"
    assert names == sorted(names)
    # Sort links and the parent-directory row are not entries.
    assert not [e for e in entries if e["href"].startswith("?") or e["name"] == "Parent Directory"]
    benzonia = [e for e in entries if e["name"] == "benzonia"]
    assert benzonia == [{
        "name": "benzonia",
        "href": "benzonia",
        "url": "https://mawn.geo.msu.edu/rawdata/3hr/benzonia",
        "type": "file",
        "lastModifiedRaw": "2026-10-12 18:08",
        "sizeRaw": "2.0K",
    }]


def test_raw_file_structure_and_byte_fidelity(manifest):
    data = pack_bytes("input/rawdata/3hr/benzonia")
    assert len(data) == 2001
    info = P.describe_raw_file(data)
    assert info["lineCount"] == 39
    assert info["endsWithNewline"] is True
    assert info["lineEnding"] == "LF"
    assert info["hasHeaderRow"] is False
    assert info["recordTypes"] == [
        {"firstField": "5", "lineCount": 36, "fieldCounts": [10]},
        {"firstField": "60", "lineCount": 3, "fieldCounts": [20]},
    ]
    assert len(info["records"]) == 39
    assert [r["line"] for r in info["records"]] == list(range(1, 40))
    assert [r["line"] for r in info["records"] if r["firstField"] == "60"] == [13, 26, 39]
    # Lines read from the file itself.
    assert info["records"][0]["fields"] == ["5", "2026", "285", "1505", "0", "267.7", "261.6", "1.98", "23.99", "59.38"]
    assert info["records"][6]["fields"][8] == "25"  # printed without decimals; must not become "25.0"
    assert info["records"][38]["fields"] == [
        "60", "2026", "285", "1800", "23.79", "62.24", "735.7343", "20.2", "19.17", "0.098",
        "0.234", "1.282", "225.5", "47.02", "3.5", "1714", "0", "0", "0", "12.96",
    ]
    # Reassembling the fields reproduces the original bytes exactly.
    rebuilt = "\n".join(",".join(r["fields"]) for r in info["records"]) + "\n"
    assert rebuilt.encode("ascii") == data
    row = next(r for r in manifest if r["file"] == "input/rawdata/3hr/benzonia")
    assert hashlib.sha256(rebuilt.encode("ascii")).hexdigest() == row["sha256"]


def test_public_raw_file_is_byte_identical_to_the_pack(manifest):
    manifest = built_manifest()
    public = (ROOT / "public" / "rawdata" / "3hr" / "benzonia").read_bytes()
    assert public == built_bytes("input/rawdata/3hr/benzonia")
    row = next(r for r in manifest if r["file"] == "input/rawdata/3hr/benzonia")
    assert hashlib.sha256(public).hexdigest() == row["sha256"]
    assert len(public) == int(row["bytes"])


# ---------------------------------------------------------------------------
# Layout changes must raise, not mislabel
# ---------------------------------------------------------------------------

def test_hourly_rejects_a_renamed_header_label(hourly_html):
    changed = mutate(hourly_html, b"Time&nbsp;&nbsp;&nbsp;Temp&nbsp;&nbsp;Hum", b"Time&nbsp;&nbsp;&nbsp;Temp&nbsp;&nbsp;Dew")
    with pytest.raises(P.SourceFormatError, match="hourly header changed"):
        P.parse_hourly(changed)


def test_hourly_rejects_reordered_header_columns(hourly_html):
    changed = mutate(hourly_html, b"Air&nbsp;&nbsp;&nbsp;Rel&nbsp;&nbsp;&nbsp;Soil", b"Rel&nbsp;&nbsp;&nbsp;Air&nbsp;&nbsp;&nbsp;Soil")
    with pytest.raises(P.SourceFormatError, match="hourly header changed"):
        P.parse_hourly(changed)


def test_hourly_rejects_a_dropped_header_column(hourly_html):
    changed = mutate(hourly_html, b"Solar&nbsp;&nbsp;&nbsp;Total", b"Total")
    with pytest.raises(P.SourceFormatError, match="hourly header changed"):
        P.parse_hourly(changed)


def test_hourly_rejects_a_changed_unit(hourly_html):
    changed = mutate(hourly_html, b"(mph)", b"(m/s)")
    with pytest.raises(P.SourceFormatError, match="hourly unit line changed"):
        P.parse_hourly(changed)


def test_hourly_rejects_an_unknown_time_zone_label(hourly_html):
    changed = mutate(hourly_html, b"(EDT)", b"(UTC)")
    with pytest.raises(P.SourceFormatError, match="hourly unit line changed"):
        P.parse_hourly(changed)


def test_hourly_rejects_mixed_time_zone_labels(hourly_html):
    changed = mutate(hourly_html, b"(EDT)", b"(EST)", 1)
    with pytest.raises(P.SourceFormatError, match="mixed time-zone labels"):
        P.parse_hourly(changed)


def test_hourly_accepts_est_label_when_consistent(hourly_html):
    # The parser reads the zone label from the report instead of assuming it.
    assert P.parse_hourly(mutate(hourly_html, b"(EDT)", b"(EST)"))["timezoneLabel"] == "EST"


def test_hourly_rejects_a_row_with_a_column_dropped(hourly_html):
    changed = mutate(hourly_html, b"74.8&nbsp;&nbsp;62.2&nbsp;&nbsp;68.4", b"74.8&nbsp;&nbsp;68.4")
    with pytest.raises(P.SourceFormatError, match="hourly row has 9 fields"):
        P.parse_hourly(changed)


def test_hourly_rejects_a_row_with_an_extra_column(hourly_html):
    changed = mutate(hourly_html, b"74.8&nbsp;&nbsp;62.2&nbsp;&nbsp;68.4", b"74.8&nbsp;&nbsp;62.2&nbsp;&nbsp;55.0&nbsp;&nbsp;68.4")
    with pytest.raises(P.SourceFormatError, match="hourly row has 11 fields"):
        P.parse_hourly(changed)


def test_hourly_rejects_an_unreadable_number(hourly_html):
    changed = mutate(hourly_html, b"74.8&nbsp;&nbsp;62.2", b"74,8&nbsp;&nbsp;62.2")
    with pytest.raises(P.SourceFormatError, match="expected a number or a missing marker"):
        P.parse_hourly(changed)


def test_hourly_rejects_an_unknown_missing_marker_in_a_number_column(hourly_html):
    # "n/a" is not one of the three markers the source uses; it must not be read as missing.
    changed = mutate(hourly_html, b"17.6&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;--&nbsp;", b"17.6&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;n/a&nbsp;")
    with pytest.raises(P.SourceFormatError):
        P.parse_hourly(changed)


def test_hourly_rejects_a_bad_date(hourly_html):
    changed = mutate(hourly_html, b"10/12/26&nbsp;18:00", b"2026-10-12&nbsp;18:00")
    with pytest.raises(P.SourceFormatError, match="date/time not understood"):
        P.parse_hourly(changed)


def test_reports_reject_a_page_without_the_report_block(hourly_html):
    changed = mutate(hourly_html, b'<td class="courier2">', b'<td class="report">')
    with pytest.raises(P.SourceFormatError, match="courier2"):
        P.parse_hourly(changed)
    with pytest.raises(P.SourceFormatError, match="courier2"):
        P.parse_daily(changed)
    with pytest.raises(P.SourceFormatError, match="courier2"):
        P.parse_maintenance(changed)


def test_report_parsers_reject_each_others_pages(hourly_html, daily_html, maintenance_html):
    with pytest.raises(P.SourceFormatError):
        P.parse_hourly(daily_html)
    with pytest.raises(P.SourceFormatError):
        P.parse_daily(hourly_html)
    with pytest.raises(P.SourceFormatError):
        P.parse_hourly(maintenance_html)
    with pytest.raises(P.SourceFormatError):
        P.parse_maintenance(hourly_html)


def test_daily_rejects_a_changed_header(daily_html):
    changed = mutate(daily_html, b"(mi/day)", b"(km/day)")
    with pytest.raises(P.SourceFormatError, match="daily header changed"):
        P.parse_daily(changed)
    changed = mutate(daily_html, b"Max&nbsp;&nbsp;&nbsp;Min&nbsp;&nbsp;&nbsp;Max&nbsp;&nbsp;&nbsp;Min", b"Min&nbsp;&nbsp;&nbsp;Max&nbsp;&nbsp;&nbsp;Max&nbsp;&nbsp;&nbsp;Min")
    with pytest.raises(P.SourceFormatError, match="daily header changed"):
        P.parse_daily(changed)


def test_daily_rejects_a_row_with_a_column_dropped(daily_html):
    changed = mutate(daily_html, b"08/01/26&nbsp;&nbsp;76.5&nbsp;&nbsp;63.9", b"08/01/26&nbsp;&nbsp;76.5")
    with pytest.raises(P.SourceFormatError, match="daily row has 9 fields"):
        P.parse_daily(changed)


def test_station_page_rejects_missing_or_reformatted_fields():
    data = pack_bytes("input/mawn/station-bnz.html")
    url = "https://mawn.geo.msu.edu/station.asp?id=bnz"
    with pytest.raises(P.SourceFormatError, match="Elevation"):
        P.parse_station(mutate(data, b"Elevation:", b"Height:"), url)
    with pytest.raises(P.SourceFormatError, match="unexpected value"):
        P.parse_station(mutate(data, b"  253 m", b"  830 ft"), url)
    with pytest.raises(P.SourceFormatError, match="unexpected value"):
        P.parse_station(mutate(data, b" 44.5593 deg.", b" 44 33 33 N"), url)


def test_mawn_home_rejects_retired_station_without_date_and_duplicate_ids():
    data = pack_bytes("input/mawn/home.html")
    url = "https://mawn.geo.msu.edu/"
    with pytest.raises(P.SourceFormatError, match="retired station without a date"):
        P.parse_mawn_home(mutate(data, b"Arlington (06/09/2023)", b"Arlington"), url)
    with pytest.raises(P.SourceFormatError, match="listed twice"):
        P.parse_mawn_home(mutate(data, b'<a href="/station.asp?id=alb">', b'<a href="/station.asp?id=aet">'), url)


def test_listing_and_directory_parsers_reject_unrecognised_pages():
    with pytest.raises(P.SourceFormatError, match="no entries"):
        P.parse_apache_listing(b"<html><body><h1>Index of /rawdata</h1><pre></pre></body></html>", "https://mawn.geo.msu.edu/rawdata/")
    with pytest.raises(P.SourceFormatError, match="no product sections"):
        P.parse_agweather_products(pack_bytes("input/agweather/home.html").replace(b"tableheader1", b"tableheaderX"), "https://www.agweather.geo.msu.edu/")
    maps = pack_bytes("input/climate/climate_maps.html")
    with pytest.raises(P.SourceFormatError, match="page2_middle"):
        P.parse_climate_maps(mutate(maps, b'id="page2_middle"', b'id="page3_middle"'), "https://climate.geo.msu.edu/climate_maps.html")
    with pytest.raises(P.SourceFormatError, match="no map groups"):
        P.parse_climate_maps(mutate(maps, b'class="bg_shading"', b'class="shading"'), "https://climate.geo.msu.edu/climate_maps.html")
    with pytest.raises(P.SourceFormatError, match="content_middle"):
        P.parse_climate_home(maps, "https://climate.geo.msu.edu/")


def test_climate_maps_rejects_an_image_without_a_caption():
    maps = pack_bytes("input/climate/climate_maps.html")
    changed = mutate(maps, b">Past 7 days</a>", b"></a>", 1)
    with pytest.raises(P.SourceFormatError, match="3 images but 2 captions"):
        P.parse_climate_maps(changed, "https://climate.geo.msu.edu/climate_maps.html")


def test_raw_file_rejects_non_ascii_bytes():
    with pytest.raises(UnicodeDecodeError):
        P.describe_raw_file(pack_bytes("input/rawdata/3hr/benzonia") + b"\xff\n")


def test_cells_keep_markers_and_refuse_garbage():
    for marker in MARKERS:
        assert P.num_cell(marker) == {"raw": marker, "value": None, "missing": True}
        assert P.text_cell(marker) == {"raw": marker, "value": None, "missing": True}
    assert P.num_cell("0.4") == {"raw": "0.4", "value": 0.4, "missing": False}
    assert P.num_cell("0.00") == {"raw": "0.00", "value": 0.0, "missing": False}  # a printed zero is a value
    assert P.text_cell("DRY") == {"raw": "DRY", "value": "DRY", "missing": False}
    with pytest.raises(P.SourceFormatError):
        P.num_cell("")
    with pytest.raises(P.SourceFormatError):
        P.num_cell("-")
    with pytest.raises(P.SourceFormatError):
        P.num_cell("N/A")


def test_iso_from_mdy():
    assert P.iso_from_mdy("10/12/26") == "2026-10-12"
    assert P.iso_from_mdy("05/11/2023") == "2023-05-11"
    assert P.iso_from_mdy("08/??/2001") is None
    assert P.iso_from_mdy("2026-10-12") is None
    assert P.iso_from_mdy("1/2/26") is None


# ---------------------------------------------------------------------------
# Inventory: canonical() and classify()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("url", "expected", "via_js"),
    [
        ("http://mawn.geo.msu.edu/station.asp?id=bnz", "https://mawn.geo.msu.edu/station.asp?id=bnz", False),
        ("https://mawn.geo.msu.edu/station.asp?id=bnz", "https://mawn.geo.msu.edu/station.asp?id=bnz", False),
        ("https://mawn.geo.msu.edu", "https://mawn.geo.msu.edu/", False),
        ("http://www.agweather.geo.msu.edu", "https://www.agweather.geo.msu.edu/", False),
        ("http://agweather.geo.msu.edu/current/", "https://www.agweather.geo.msu.edu/current/", False),
        ("http://climate.geo.msu.edu", "https://climate.geo.msu.edu/", False),
        ("HTTP://MAWN.GEO.MSU.EDU/rawdata/3hr/benzonia", "https://mawn.geo.msu.edu/rawdata/3hr/benzonia", False),
        ("https://mawn.geo.msu.edu/rawdata/3hr/?C=N;O=D", "https://mawn.geo.msu.edu/rawdata/3hr/?C=N;O=D", False),
        ("https://climate.geo.msu.edu/climate_maps.html#top", "https://climate.geo.msu.edu/climate_maps.html", False),
        ("http://www.msu.edu", "http://www.msu.edu/", False),
        ("http://www.cpc.ncep.noaa.gov/products/predictions/610day/", "http://www.cpc.ncep.noaa.gov/products/predictions/610day/", False),
        (
            "javascript:newWindow('https://mrcc.purdue.edu/files/cliwatch/state_climatologists/michigan/prcp-7days.png')",
            "https://mrcc.purdue.edu/files/cliwatch/state_climatologists/michigan/prcp-7days.png",
            True,
        ),
    ],
)
def test_canonical(url, expected, via_js):
    assert inv.canonical(url) == (expected, via_js)


@pytest.mark.parametrize(
    ("url", "pattern", "treatment", "new_url"),
    [
        ("https://mawn.geo.msu.edu/", "mawn-home", "REBUILD", "/weather-network/"),
        ("https://mawn.geo.msu.edu/station.asp?id=bnz", "mawn-station", "REBUILD", "/weather-network/stations/bnz/"),
        ("https://mawn.geo.msu.edu/station.asp?id=swm", "mawn-station", "REBUILD", "/weather-network/stations/swm/"),
        ("https://mawn.geo.msu.edu/station.asp?id=bnz&rt=24", "mawn-custom-report", "NEEDS INVESTIGATION", None),
        ("https://mawn.geo.msu.edu/report.asp?fileid=bnzh", "mawn-report-hourly", "REBUILD", "/weather-network/stations/bnz/hourly/"),
        ("https://mawn.geo.msu.edu/report.asp?fileid=bnzd", "mawn-report-daily", "REBUILD", "/weather-network/stations/bnz/daily/"),
        ("https://mawn.geo.msu.edu/report.asp?fileid=bnzm", "mawn-report-maintenance", "REBUILD", "/weather-network/stations/bnz/maintenance/"),
        ("https://mawn.geo.msu.edu/rawdata/", "rawdata-root", "PRESERVE", "/rawdata/"),
        ("https://mawn.geo.msu.edu/rawdata/3hr/", "rawdata-directory", "PRESERVE", "/rawdata/3hr/"),
        ("https://mawn.geo.msu.edu/rawdata/3hr/benzonia", "rawdata-file", "PRESERVE", "/rawdata/3hr/benzonia"),
        ("https://mawn.geo.msu.edu/rawdata/3hr/?C=N;O=D", "rawdata-sort-link", "REDIRECT", "/rawdata/3hr/"),
        ("https://mawn.geo.msu.edu/mawn-sw.html", "mawn-regional-map", "NEEDS INVESTIGATION", None),
        ("https://mawn.geo.msu.edu/images/stations/bnz.jpg", "mawn-station-photo", "PRESERVE", None),
        ("https://mawn.geo.msu.edu/style.css", "mawn-layout-asset", "ARCHIVE", None),
        ("https://mawn.geo.msu.edu/images/MAWNheader.gif", "mawn-layout-asset", "ARCHIVE", None),
        ("https://www.agweather.geo.msu.edu/", "agweather-home", "REBUILD", "/agricultural-weather/"),
        ("https://www.agweather.geo.msu.edu/index.html", "agweather-index-alias", "REDIRECT", "/agricultural-weather/"),
        ("https://www.agweather.geo.msu.edu/current/", "agweather-current", "REBUILD", "/agricultural-weather/current/"),
        ("https://www.agweather.geo.msu.edu/forecasts/", "agweather-forecasts", "REBUILD", "/agricultural-weather/forecasts/"),
        ("https://www.agweather.geo.msu.edu/current/report.asp?fileid=rwrmi", "agweather-current-report", "NEEDS INVESTIGATION", None),
        ("https://www.agweather.geo.msu.edu/current/normal.asp?fileid=houghton", "agweather-normals", "NEEDS INVESTIGATION", None),
        ("https://www.agweather.geo.msu.edu/forecasts/fcst.asp?fileid=fpus63kgrr", "agweather-forecast-product", "NEEDS INVESTIGATION", None),
        ("https://www.agweather.geo.msu.edu/info/", "agweather-section-index", "NEEDS INVESTIGATION", None),
        ("https://www.agweather.geo.msu.edu/current/maxtemp.html", "agweather-static-page", "NEEDS INVESTIGATION", None),
        ("https://climate.geo.msu.edu/", "climate-home", "REBUILD", "/climate/"),
        ("https://climate.geo.msu.edu/index.html", "climate-index-alias", "REDIRECT", "/climate/"),
        ("https://climate.geo.msu.edu/climate_maps.html", "climate-maps", "REBUILD", "/climate/maps/"),
        ("https://climate.geo.msu.edu/about_us.html", "climate-content-page", "NEEDS INVESTIGATION", None),
        ("https://mrcc.purdue.edu/files/cliwatch/state_climatologists/michigan/prcp-7days.png", "external-mrcc-map", "EXTERNAL DEPENDENCY", None),
        ("http://www.cpc.ncep.noaa.gov/products/predictions/610day/", "external-noaa-cpc", "EXTERNAL DEPENDENCY", None),
        ("http://www.msu.edu/", "external-reference-link", "EXTERNAL DEPENDENCY", None),
        ("https://mawn.geo.msu.edu/somewhere-new.asp", "unclassified", "NEEDS INVESTIGATION", None),
        ("https://mawn.geo.msu.edu/report.asp?fileid=bnzx", "unclassified", "NEEDS INVESTIGATION", None),
    ],
)
def test_classify(url, pattern, treatment, new_url):
    rule = inv.classify(url)
    assert rule["patternId"] == pattern
    assert rule["treatment"] == treatment
    assert rule["proposedNewUrl"] == new_url


def test_classify_covers_every_captured_url(manifest):
    for row in manifest:
        rule = inv.classify(inv.canonical(row["url"])[0])
        assert rule["patternId"] != "unclassified", row["url"]
        assert rule["treatment"] in ("REBUILD", "PRESERVE"), row["url"]
        assert rule["proposedNewUrl"], row["url"]
    assert inv.site_of("https://mawn.geo.msu.edu/") == "mawn"
    assert inv.site_of("https://agweather.geo.msu.edu/") == "agweather"
    assert inv.site_of("https://climate.geo.msu.edu/") == "climate"
    assert inv.site_of("https://mrcc.purdue.edu/x.png") == "external"


# ---------------------------------------------------------------------------
# Agricultural Weather Office
# ---------------------------------------------------------------------------

def shape(page: dict) -> list[tuple[str, list[tuple[str | None, int]]]]:
    return [(s["heading"], [(g["label"], len(g["links"])) for g in s["groups"]]) for s in page["sections"]]


def test_agweather_current_sections_groups_and_links():
    data = pack_bytes("input/agweather/current.html")
    page = P.parse_agweather_products(data, "https://www.agweather.geo.msu.edu/current/")
    assert page["siteTitle"] == "MSU Agricultural Weather Office"
    assert page["pageHeading"] == "Current Weather & Climatological Info"
    assert page["pageStampRaw"] == "10/12/26 - 19:46"
    assert page["datafeedStatusRaw"] == ["LDM : ok", "MAWN : ok"]
    assert shape(page) == [
        ("Recent Weather Observations", [(None, 4), (None, 3), (None, 1)]),
        ("NWS Regional Temp/Prec Summaries", [(None, 5)]),
        ("NWS Regional Climate Summaries", [(None, 17)]),
        ("Growing Degree Day (GDD) Products", [(None, 3)]),
        ("Daily Temperature and GDD Normals", [
            ("Western Upper Peninsula", 4), ("Eastern Upper Peninsula", 4), ("Northwest Lower Peninsula", 6),
            ("Northeast Lower Peninsula", 4), ("West Central Lower Peninsula", 5), ("Central Lower Peninsula", 3),
            ("East Central Lower Peninsula", 3), ("Southwest Lower Peninsula", 4), ("South Central Lower Peninsula", 4),
            ("Southeast Lower Peninsula", 5),
        ]),
    ]
    links = [link for s in page["sections"] for g in s["groups"] for link in g["links"]]
    assert len(links) == 75
    # Independent count: product anchors carry class="arial2" in the captured page.
    assert len(re.findall(rb'<a href="[^"]+" class="arial2">', data)) == 75
    assert len(re.findall(rb'<a href="\./normal\.asp\?fileid=', data)) == 42
    assert len(re.findall(rb'<a href="\./report\.asp\?fileid=', data)) == 30
    assert links[0] == {
        "label": "Michigan Hourly Weather Roundup",
        "url": "https://www.agweather.geo.msu.edu/current/report.asp?fileid=rwrmi",
        "rowText": None,
    }
    assert links[-1]["label"] == "Toldeo, OH"  # the source's own spelling
    assert links[-1]["url"] == "https://www.agweather.geo.msu.edu/current/normal.asp?fileid=toledo"
    external = [link["url"] for link in links if "agweather.geo.msu.edu" not in link["url"]]
    assert external == ["http://www.soils.wisc.edu/wimnext/et/miet.html"]


def test_agweather_forecasts_sections_groups_and_links():
    data = pack_bytes("input/agweather/forecasts.html")
    page = P.parse_agweather_products(data, "https://www.agweather.geo.msu.edu/forecasts/")
    assert page["pageHeading"] == "Forecast Products"
    assert shape(page) == [
        ("State Forecast", [(None, 1)]),
        ("Regional Zone Forecasts", [(None, 5)]),
        ("Regional Forecast Discussions", [(None, 5)]),
        ("Agricultural Forecast Products", [(None, 1)]),
        ("60-Hour Guidance Forecast", [(None, 15)]),
        ("Extended Forecasts", [(None, 7)]),
    ]
    links = [link for s in page["sections"] for g in s["groups"] for link in g["links"]]
    assert len(links) == 34
    assert len(re.findall(rb'<a href="[^"]+" class="arial2">', data)) == 33  # plus one unclassed "here" link
    assert len(re.findall(rb'<a href="\./fcst\.asp\?fileid=', data)) == 29
    guidance = page["sections"][4]["groups"][0]["links"]
    # The 15th link is the in-sentence "here"; its sentence is kept so the label can be made meaningful.
    assert guidance[-1] == {
        "label": "here",
        "url": "https://www.agweather.geo.msu.edu/forecasts/nbm_fcsts.html",
        "rowText": "(for complete list of stations, click here)",
    }
    noaa = [link["url"] for link in links if "noaa.gov" in link["url"]]
    assert len(noaa) == 4


def test_agweather_navigation_is_the_same_on_all_three_pages():
    pages = [
        P.parse_agweather_home(pack_bytes("input/agweather/home.html"), "https://www.agweather.geo.msu.edu/"),
        P.parse_agweather_products(pack_bytes("input/agweather/current.html"), "https://www.agweather.geo.msu.edu/current/"),
        P.parse_agweather_products(pack_bytes("input/agweather/forecasts.html"), "https://www.agweather.geo.msu.edu/forecasts/"),
    ]
    for page in pages:
        assert [n["label"] for n in page["navigation"]] == [
            "Main", "Information", "Current Weather", "Forecast Products", "Feature Articles", "Other Sites",
            "Michigan Automated Weather Network (MAWN)", "Enviro-Weather",
        ]
    assert pages[0]["navigation"][1]["url"] == "https://www.agweather.geo.msu.edu/info/"


def test_agweather_home_news_and_additions():
    home = P.parse_agweather_home(pack_bytes("input/agweather/home.html"), "https://www.agweather.geo.msu.edu/")
    assert home["siteTitle"] == "MSU Agricultural Weather Office"
    assert home["pageStampRaw"] == "10/12/26 - 19:46"
    assert home["datafeedStatusRaw"] == ["LDM : ok", "MAWN : ok"]
    assert [(n["category"], n["dateRaw"], n["isoDate"], n["link"]["label"]) for n in home["news"]] == [
        ("Network News", "03/08/2026", "2026-03-08", "Old Mission-South"),
        ("Network News", "03/02/2026", "2026-03-02", "Omena"),
        ("Network News", "02/25/2026", "2026-02-25", "Lake Leelanau"),
        ("Network News", "01/26/2026", "2026-01-26", "Hart (WCMREC) [10m]"),
    ]
    assert home["news"][0]["kind"] == "New Enviro-Weather Station"
    assert home["news"][0]["link"]["url"] == "https://mawn.geo.msu.edu/station.asp?id=omp"
    assert home["news"][0]["text"] == "Old Mission-South station added to EnviroWeather Weather Station Network."
    assert [(a["name"], a["dateRaw"]) for a in home["recentAdditions"]] == [
        ("Old Mission-South", "03/08/2026"),
        ("Omena", "03/02/2026"),
        ("Lake Leelanau", "02/25/2026"),
        ("Hart (WCMREC) [10m]", "01/26/2026"),
        ("Leland", "08/25/2025"),
        ("Grand Junction [10m]", "05/14/2025"),
        ("East Lansing (MSUHORT) [10m]", "05/05/2025"),
    ]
    # "Coming Soon" has only commented-out items in the capture; nothing may be invented for it.
    assert home["comingSoonText"] is None
    assert home["contactLines"] == [
        "For more information - write or call:",
        "Michigan Climatological Resources Program",
        "236 Geography Building",
        "East Lansing, MI U.S.A. 48824-1115",
        "Phone: (517) 432-6520",
    ]
    # Text inside HTML comments (old alerts, a commented-out e-mail address) must not leak into the data.
    dumped = json.dumps(home)
    assert "agwxinfo" not in dumped
    assert "Service Alert" not in dumped
    assert "Budget" not in dumped


# ---------------------------------------------------------------------------
# State Climatologist's Office
# ---------------------------------------------------------------------------

def test_climate_maps_nine_groups_of_three():
    data = pack_bytes("input/climate/climate_maps.html")
    page = P.parse_climate_maps(data, "https://climate.geo.msu.edu/climate_maps.html")
    assert page["heading"] == "Michigan Climate Maps"
    assert page["intro"] == ["Click on a map for larger version.", "All precipitation in inches. All temperatures in degrees F."]
    assert [(g["title"], len(g["maps"])) for g in page["groups"]] == [
        ("Total Precipitation", 3),
        ("Total Precipitation - Departure from Mean", 3),
        ("Total Precipitation - Percent of Mean", 3),
        ("Average High Temperature", 3),
        ("Average High Temperature - Departure from Mean", 3),
        ("Average Temperature", 3),
        ("Average Temperature - Departure from Mean", 3),
        ("Average Low Temperature", 3),
        ("Average Low Temperature - Departure from Mean", 3),
    ]
    maps = [m for g in page["groups"] for m in g["maps"]]
    assert len(maps) == 27
    assert len(re.findall(rb"<img src=\"https://mrcc\.purdue\.edu/[^\"]+\"", data)) == 27  # independent count
    assert len({m["imageUrl"] for m in maps}) == 27
    assert {m["imageHost"] for m in maps} == {"mrcc.purdue.edu"}
    for group in page["groups"]:
        assert [m["period"] for m in group["maps"]] == ["Past 7 days", "Past 30 days", "Past 90 days"]
        stems = {m["imageUrl"].rsplit("/", 1)[1].rsplit("-", 1)[0] for m in group["maps"]}
        assert len(stems) == 1, "the three maps of a group must be the same product"
        assert [m["imageUrl"].rsplit("-", 1)[1] for m in group["maps"]] == ["7days.png", "30days.png", "90days.png"]
    assert maps[0] == {
        "period": "Past 7 days",
        "sourceAlt": "Precip 7 days",
        "imageUrl": "https://mrcc.purdue.edu/files/cliwatch/state_climatologists/michigan/prcp-7days.png",
        "imageHost": "mrcc.purdue.edu",
        "declaredWidth": "450",
        "declaredHeight": "600",
    }
    assert page["lastUpdatedRaw"] == "June 15, 2009"


def test_climate_home():
    page = P.parse_climate_home(pack_bytes("input/climate/home.html"), "https://climate.geo.msu.edu/")
    assert page["heading"] == "Welcome"
    assert len(page["paragraphs"]) == 4
    assert [n["label"] for n in page["navigation"]] == [
        "Home", "About Us", "MSU Ag Weather Office", "Michigan Climate Maps", "SEMCOG Precip Data",
        "Climate Statistics: Normals & Statistics",
    ]
    assert page["navigation"][3]["url"] == "https://climate.geo.msu.edu/climate_maps.html"
    assert [t["alt"] for t in page["sidebarThumbnails"]] == ["Total Precip last 7 days", "Average Temperature last 7 days"]
    assert page["lastUpdatedRaw"] == "June 15, 2009"
    first = page["paragraphs"][0]
    assert first[0] == {"text": "The Michigan State Climatologist's Office is a service of the ", "url": None}
    assert [seg["url"] for seg in first if seg["url"]] == [
        "http://www.geo.msu.edu", "http://agbioresearch.msu.edu/", "http://msue.msu.edu/", "http://www.semcog.org",
    ]
    linked = [seg for paragraph in page["paragraphs"] for seg in paragraph if seg["url"]]
    assert len(linked) == 8


# ---------------------------------------------------------------------------
# The committed pipeline output must be what the parsers produce today
# ---------------------------------------------------------------------------

def load(name: str) -> dict:
    return json.loads((NORMALIZED / name).read_text(encoding="utf-8"))


def test_normalized_reports_are_current(hourly, daily, maintenance):
    hourly = P.parse_hourly(built_bytes("input/mawn/report-bnzh.html"))
    daily = P.parse_daily(built_bytes("input/mawn/report-bnzd.html"))
    maintenance = P.parse_maintenance(built_bytes("input/mawn/report-bnzm.html"))
    assert load("bnz-hourly.json")["rows"] == hourly["rows"]
    assert load("bnz-hourly.json")["stats"] == hourly["stats"]
    assert load("bnz-hourly.json")["timezoneLabel"] == "EDT"
    assert load("bnz-daily.json")["rows"] == daily["rows"]
    assert load("bnz-daily.json")["stats"] == daily["stats"]
    assert load("bnz-maintenance.json")["entries"] == maintenance["entries"]
    assert load("bnz-maintenance.json")["rawText"] == maintenance["rawText"]


def test_normalized_sources_match_the_manifest(manifest):
    manifest = built_manifest()
    sources = {s["url"]: s for s in load("sources.json")["sources"]}
    assert len(sources) == 14
    for row in manifest:
        source = sources[row["url"]]
        assert source["sha256"] == row["sha256"]
        assert source["bytes"] == int(row["bytes"])
        assert source["file"] == row["file"]
        assert source["retrievedAtUtc"] == row["retrieved_at_utc"]
    for name in ("bnz-hourly.json", "bnz-daily.json", "bnz-maintenance.json"):
        ref = load(name)["source"]
        assert sources[ref["url"]]["sha256"] == ref["sha256"]


def test_normalized_station_counts(mawn_home):
    stations = load("stations.json")
    assert stations["counts"] == {"tower-10m": 3, "tower-20m": 2, "retired": 19, "michigan": 95, "total": 119}
    assert [s["id"] for s in stations["stations"]] == [s["id"] for s in mawn_home["stations"]]
    # Only the two stations whose pages are in the pack may claim a prototype page.
    assert {s["id"] for s in stations["stations"] if s["prototypeUrl"]} == {"bnz", "swm"}
    assert {s["id"]: s["captureLevel"] for s in stations["stations"] if s["captureLevel"] != "listed"} == {"bnz": "full", "swm": "metadata"}
    details = load("station-details.json")["stations"]
    assert set(details) == {"bnz", "swm"}
    assert details["swm"]["reports"] == {}  # SWMREC reports were not downloaded


def test_inventory_marks_only_manifest_urls_as_captured(manifest):
    manifest = built_manifest()
    records = load("inventory-records.json")["records"]
    captured = {r["url"]: r for r in records if r["captured"]}
    assert set(captured) == {inv.canonical(row["url"])[0] for row in manifest}
    for row in manifest:
        record = captured[inv.canonical(row["url"])[0]]
        assert record["sha256"] == row["sha256"]
        assert record["httpStatus"] == 200
    for record in records:
        assert inv.canonical(record["url"])[0] == record["url"], "inventory keys must be canonical"
        if not record["captured"]:
            assert record["httpStatus"] is None
            assert record["httpStatusNote"] == "not requested"
            assert record["sha256"] is None
    lookup = load("legacy-url-lookup.json")
    assert set(lookup) == {r["url"] for r in records}
    assert lookup["https://mawn.geo.msu.edu/station.asp?id=bnz"] == {
        "t": "REBUILD", "n": "/weather-network/stations/bnz/", "s": "rebuilt", "p": "mawn-station",
    }
    assert lookup["https://mawn.geo.msu.edu/rawdata/3hr/benzonia"] == {
        "t": "PRESERVE", "n": "/rawdata/3hr/benzonia", "s": "bytes-preserved", "p": "rawdata-file",
    }
    # Nothing that still needs investigation, is external or is archived gets a new URL promised for it.
    for record in records:
        if record["treatment"] in ("NEEDS INVESTIGATION", "EXTERNAL DEPENDENCY", "ARCHIVE"):
            assert record["proposedNewUrl"] is None, record["url"]
        assert (record["site"] == "external") == (record["treatment"] == "EXTERNAL DEPENDENCY"), record["url"]
    # A station that is only listed must not be reported as rebuilt.
    assert lookup["https://mawn.geo.msu.edu/station.asp?id=aet"]["s"] == "template-only"
    assert lookup["https://mawn.geo.msu.edu/rawdata/3hr/aetna"]["s"] == "listed-only"


def test_listing_clock_observation_is_supported_by_the_receipts():
    """rawdata.json says the listing clock was four hours behind UTC; check it against the recorded header."""
    from datetime import datetime, timedelta, timezone
    from email.utils import parsedate_to_datetime

    receipts = json.loads((built_pack() / "receipts" / "requests.json").read_text(encoding="utf-8"))
    header = next(r for r in receipts if r["url"] == "https://mawn.geo.msu.edu/rawdata/3hr/benzonia")["headers"]
    header = {k.lower(): v for k, v in header.items()}["last-modified"]
    listing = P.parse_apache_listing(built_bytes("input/rawdata/3hr-index.html"), "https://mawn.geo.msu.edu/rawdata/3hr/")
    listed = next(e for e in listing["entries"] if e["name"] == "benzonia")["lastModifiedRaw"]
    listed_as_utc = datetime.strptime(listed, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    modified = parsedate_to_datetime(header).replace(second=0)
    assert modified - listed_as_utc == timedelta(hours=4)
    clock = load("rawdata.json")["listingClock"]
    assert header in clock["observation"]
    assert "four hours behind UTC" in clock["observation"]
    assert "this one file only" in clock["scope"]


def test_raw_crosscheck_is_reproducible_by_hand(hourly):
    """The cross-check is an observation, not a schema; its arithmetic must still be right."""
    from build_data import crosscheck
    check = crosscheck(P.describe_raw_file(pack_bytes("input/rawdata/3hr/benzonia")), hourly)
    current_check = crosscheck(P.describe_raw_file(built_bytes("input/rawdata/3hr/benzonia")), P.parse_hourly(built_bytes("input/mawn/report-bnzh.html")))
    assert all(load("raw-crosscheck.json")[k] == v for k, v in current_check.items())
    assert check["status"] == "observation only; no schema adopted"
    assert check["overlappingRecords"] == 3
    assert [o["reportRow"] for o in check["overlap"]] == ["10/12/26 16:00", "10/12/26 17:00", "10/12/26 18:00"]
    # Last line of input/rawdata/3hr/benzonia against the 10/12/26 18:00 report row
    # (74.8 F, 62.2 %, 68.4 F, SW, 2.9 mph, 17.6 ly), recomputed here.
    fields = "60,2026,285,1800,23.79,62.24,735.7343,20.2,19.17,0.098,0.234,1.282,225.5,47.02,3.5,1714,0,0,0,12.96".split(",")
    assert pack_bytes("input/rawdata/3hr/benzonia").decode("ascii").splitlines()[-1].split(",") == fields
    row = hourly_row(hourly, "10/12/26", "18:00")["cells"]
    assert round(float(fields[4]) * 9 / 5 + 32, 1) == row["airTemp"]["value"] == 74.8
    assert round(float(fields[5]), 1) == row["relHum"]["value"] == 62.2
    assert round(float(fields[6]) / 41.84, 1) == row["solarRad"]["value"] == 17.6
    assert round(float(fields[7]) * 9 / 5 + 32, 1) == row["soilTemp"]["value"] == 68.4
    assert round(float(fields[11]) * 2.2369363, 1) == row["windSpeed"]["value"] == 2.9
    assert 213.75 <= float(fields[12]) < 236.25 and row["windDir"]["value"] == "SW"  # the SW sector of a 16-point compass
    assert check["matchedFieldPositions"] == [5, 6, 7, 8, 12, 13]
    # Day 285 of 2026 is 12 October, the date of the report rows it was compared with.
    from datetime import date, timedelta
    assert date(2026, 1, 1) + timedelta(days=int(fields[2]) - 1) == date(2026, 10, 12)
    # Fields with no labelled counterpart stay unlabelled.
    assert check["unmatchedFieldPositions"] == [9, 10, 11, 14, 15, 16, 17, 18, 19, 20]
    assert load("rawdata.json")["files"]["3hr/benzonia"]["schemaStatus"] == "not established"


def test_download_csvs_hold_the_printed_strings(hourly_html, daily_html):
    hourly_html = built_bytes("input/mawn/report-bnzh.html")
    daily_html = built_bytes("input/mawn/report-bnzd.html")
    downloads = ROOT / "public" / "downloads"
    with (downloads / "benzonia-hourly.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == [
        "date", "time_EDT_as_labelled", "Air Temp (F)", "Rel Hum (%)", "Soil Temp (F)", "Leaf Wetness Status",
        "Wind Dir", "Wind Speed (mph)", "Solar Rad (ly)", "Total Precip (in)",
    ]
    assert rows[1:] == independent_rows(hourly_html)
    assert len(rows) == len(independent_rows(hourly_html)) + 1
    with (downloads / "benzonia-daily.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[1:] == independent_rows(daily_html)
    assert len(rows) == len(independent_rows(daily_html)) + 1
    assert (downloads / "benzonia-maintenance.txt").read_text(encoding="utf-8") == independent_report_text(
        built_bytes("input/mawn/report-bnzm.html")
    ) + "\n"


def built_pack():
    """Artifact assertions use the captured pack recorded in the build; parser fixtures stay frozen."""
    return ROOT / load("sources.json")["pack"]["path"]

def built_bytes(relative):
    return (built_pack() / relative).read_bytes()

def built_manifest():
    with (built_pack() / "manifest.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
