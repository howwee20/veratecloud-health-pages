"""Offline tests of scripts/refresh_sources.py.

No network is used: the script is driven through httpx.MockTransport, which
answers from the local source pack. These tests prove the safeguards and that
a refresh writes a pack the pipeline can read. They do not, and must not,
contact the legacy hosts.
"""
import csv
import hashlib
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_data  # noqa: E402
import refresh_sources  # noqa: E402

PACK = ROOT / "data" / "source-snapshots" / "weather-source-pack"
ROWS = {row["url"]: row for row in csv.DictReader((PACK / "manifest.csv").open(newline="", encoding="utf-8"))}
DISALLOW_ALL = "User-agent: *\nDisallow: /\n"


class Recorder:
    def __init__(self, robots: str = DISALLOW_ALL, not_modified: bool = False):
        self.requests: list[httpx.Request] = []
        self.robots = robots
        self.not_modified = not_modified

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(200, text=self.robots)
        if self.not_modified and "if-modified-since" in request.headers:
            return httpx.Response(304)
        return httpx.Response(200, content=(PACK / ROWS[url]["file"]).read_bytes())


def run(args, recorder, tmp_path):
    return refresh_sources.main(args, transport=httpx.MockTransport(recorder), out_root=tmp_path, min_delay=0.0)


def test_refuses_without_approval(tmp_path, capsys):
    recorder = Recorder()
    assert run([], recorder, tmp_path) == 2
    assert recorder.requests == []
    assert "Nothing was requested" in capsys.readouterr().out


def test_dry_run_requests_nothing(tmp_path, capsys):
    recorder = Recorder()
    assert run(["--approved-by", "Test"], recorder, tmp_path) == 0
    assert recorder.requests == []
    assert list(tmp_path.iterdir()) == []
    assert "Dry run only" in capsys.readouterr().out


def test_stops_after_robots_when_disallowed_and_no_override(tmp_path):
    recorder = Recorder()
    assert run(["--approved-by", "Test", "--execute", "--delay", "0"], recorder, tmp_path) == 3
    assert [str(r.url).rsplit("/", 1)[1] for r in recorder.requests] == ["robots.txt"] * 3
    assert list(tmp_path.iterdir()) == [], "nothing may be written when robots.txt stops the run"


def test_requests_are_get_only_identified_and_limited_to_the_manifest(tmp_path):
    recorder = Recorder()
    code = run(["--approved-by", "Test", "--robots-override-approved-by", "Maintainer", "--execute", "--delay", "0"], recorder, tmp_path)
    assert code == 0
    named = [str(r.url) for r in recorder.requests if not str(r.url).endswith("/robots.txt")]
    assert sorted(named) == sorted(ROWS), "only the 14 manifest URLs may be requested, once each"
    assert {r.method for r in recorder.requests} == {"GET"}
    assert all("MichiganWeatherContinuity" in r.headers["user-agent"] for r in recorder.requests)
    assert all("authorization" not in r.headers and "cookie" not in r.headers for r in recorder.requests)


@pytest.mark.parametrize("not_modified", [False, True])
def test_refresh_writes_a_complete_pack_the_pipeline_can_read(tmp_path, monkeypatch, not_modified):
    recorder = Recorder(not_modified=not_modified)
    code = run(["--approved-by", "Test", "--robots-override-approved-by", "Maintainer", "--execute", "--delay", "0"], recorder, tmp_path)
    assert code == 0
    (out,) = list(tmp_path.iterdir())
    for row in ROWS.values():
        data = (out / row["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row["sha256"], row["file"]
    assert (out / "receipts" / "approval.json").exists()
    assert (out / "link-inventory.csv").exists()
    # The existing pack is untouched and the new directory is separate from it.
    assert out.parent == tmp_path
    monkeypatch.setattr(build_data, "PACK", out)
    monkeypatch.setattr(build_data, "PACK_LABEL", "refresh-under-test")
    sources = build_data.load_sources()
    assert len(sources) == 14
    assert all(s["sha256Verified"] for s in sources.values())
