#!/usr/bin/env python3
"""Independent audit: every cell in the built hourly and daily tables must equal
the text of the captured legacy report. Deliberately does not use the pipeline
parsers, so a parser bug cannot hide itself.

    .venv/bin/python -I scripts/qa/audit-tables.py [dist-dir]
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DIST = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "dist")
PACK = ROOT / "data" / "source-snapshots" / "weather-source-pack" / "input" / "mawn"


def source_rows(path: Path, columns: int) -> list[list[str]]:
    text = re.sub(r"<!--.*?-->", "", path.read_bytes().decode("latin-1"), flags=re.S)
    cell = re.search(r'<td class="courier2">(.*?)</td>', text, flags=re.S).group(1)
    lines = html.unescape(re.sub(r"<br\s*/?>", "\n", cell)).replace("\xa0", " ").split("\n")
    rows = [line.split() for line in lines if re.match(r"\s*\d\d/\d\d/\d\d\s", line)]
    assert all(len(row) == columns for row in rows), "unexpected column count in source"
    return rows


def built_rows(path: Path, table_id: str) -> list[list[str]]:
    table = re.search(rf'<table[^>]*id="{table_id}".*?</table>', path.read_text(), flags=re.S).group(0)
    rows = []
    for tr in re.findall(r"<tr[^>]*data-date.*?</tr>", table, flags=re.S):
        header = re.sub(r"<[^>]+>", "", re.search(r"<th[^>]*>(.*?)</th>", tr, flags=re.S).group(1)).split()
        cells = []
        for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S):
            td = re.sub(r'<span class="visually-hidden">.*?</span>', "", td, flags=re.S)
            cells.append(html.unescape(re.sub(r"<[^>]+>", "", td)).strip())
        rows.append(header + cells)
    return rows


failed = False
for name, source, page, table_id in (
    ("hourly", "report-bnzh.html", "weather-network/stations/bnz/hourly/index.html", "hourly-table"),
    ("daily", "report-bnzd.html", "weather-network/stations/bnz/daily/index.html", "daily-table"),
):
    expected = source_rows(PACK / source, 10)
    actual = built_rows(DIST / page, table_id)
    mismatches = [i for i, (a, b) in enumerate(zip(expected, actual)) if a != b]
    ok = len(expected) == len(actual) and not mismatches
    failed = failed or not ok
    print(f"{name}: {len(expected)} source rows, {len(actual)} built rows, {sum(map(len, expected))} cells compared, {len(mismatches)} mismatching rows -> {'OK' if ok else 'FAIL'}")
sys.exit(1 if failed else 0)
