#!/usr/bin/env python3
"""Optional, read-only refresh of the captured public sources.

THIS SCRIPT CONTACTS UNIVERSITY PRODUCTION SYSTEMS. It is not part of the
build, the tests or the demo, and it has never been run by this project.

    .venv/bin/python -I scripts/refresh_sources.py                       # explains and exits
    .venv/bin/python -I scripts/refresh_sources.py --approved-by "Name"  # dry run: lists what it would fetch
    .venv/bin/python -I scripts/refresh_sources.py --approved-by "Name" \
        --robots-override-approved-by "Name" --execute                   # actually fetches

Safeguards:

* Fetches only the URLs already listed in the source-pack manifest (14 named
  URLs). It does not follow links and has no crawl mode.
* Requires ``--approved-by`` naming the person who gave operational approval.
* Reads each host's robots.txt first. All three hosts currently disallow all
  automated access; while that is so, the script stops unless
  ``--robots-override-approved-by`` names the site maintainer who authorised
  an exception. Both names are written into the receipts.
* One request at a time, at least ``--delay`` seconds apart (default 2),
  20-second timeout, no retries, no redirects followed, GET only, no
  credentials, an identifying User-Agent, and ``If-Modified-Since`` where a
  previous Last-Modified is known.
* Writes a new dated directory next to the existing pack. It never overwrites
  the pack the site is built from; switching over is a separate, manual step.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "data" / "source-snapshots" / "weather-source-pack"
USER_AGENT = "MichiganWeatherContinuity-Prototype/0.1 (read-only refresh of 14 named URLs; contact: MSU Enviroweather staff)"


def named_sources() -> list[dict]:
    with (PACK / "manifest.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main(argv: list[str] | None = None, *, transport=None, out_root: Path | None = None, min_delay: float = 1.0) -> int:
    """``transport``, ``out_root`` and ``min_delay`` exist so the offline tests can
    exercise this function with a stub transport. Real runs use the defaults."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--approved-by", help="Name of the person who gave operational approval for this run.")
    parser.add_argument("--robots-override-approved-by", help="Name of the site maintainer who authorised fetching despite robots.txt.")
    parser.add_argument("--execute", action="store_true", help="Actually send requests. Without this flag the script only prints its plan.")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between requests (minimum 1).")
    args = parser.parse_args(argv)

    sources = named_sources()
    if not args.approved_by:
        print(__doc__)
        print("Refusing to run: no --approved-by given. Nothing was requested.")
        return 2
    delay = max(args.delay, min_delay)
    hosts = sorted({urlparse(s["url"]).netloc for s in sources})
    print(f"Approved by: {args.approved_by}")
    print(f"Plan: {len(hosts)} robots.txt requests, then {len(sources)} named URLs, one at a time, {delay:.1f}s apart.")
    for source in sources:
        print(f"  {source['url']}")
    if not args.execute:
        print("\nDry run only (no --execute). Nothing was requested.")
        return 0

    import httpx  # imported late so that the refusal paths need no third-party code

    previous = {r["url"]: r for r in json.loads((PACK / "receipts" / "requests.json").read_text())}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = (out_root or PACK.parent) / f"refresh-{stamp}"
    last_request = 0.0

    def fetch(client, url: str, kind: str):
        nonlocal last_request
        wait = delay - (time.monotonic() - last_request)
        if wait > 0:
            time.sleep(wait)
        headers = {}
        modified = previous.get(url, {}).get("headers", {}).get("Last-Modified")
        if modified and kind == "named-source":
            headers["If-Modified-Since"] = modified
        started = datetime.now(timezone.utc).isoformat()
        response = client.get(url, headers=headers)
        last_request = time.monotonic()
        receipt = {"url": url, "kind": kind, "requested_at_utc": started, "status": response.status_code,
                   "headers": dict(response.headers), "final_url": str(response.url), "bytes": len(response.content),
                   "sha256": hashlib.sha256(response.content).hexdigest(),
                   "completed_at_utc": datetime.now(timezone.utc).isoformat()}
        return response, receipt

    receipts: list[dict] = []
    robots_files: dict[str, bytes] = {}
    files: dict[str, bytes] = {}
    manifest: list[dict] = []
    old_manifest = {row["url"]: row for row in sources}
    client_options = {"headers": {"User-Agent": USER_AGENT}, "timeout": 20.0, "follow_redirects": False}
    if transport is not None:
        client_options["transport"] = transport
    with httpx.Client(**client_options) as client:
        rules: dict[str, RobotFileParser] = {}
        for host in hosts:
            response, receipt = fetch(client, f"https://{host}/robots.txt", "robots")
            site = host.removeprefix("www.").split(".")[0]
            receipt["file"] = f"receipts/robots-{site}.txt"
            robots_files[receipt["file"]] = response.content
            receipts.append(receipt)
            robot = RobotFileParser()
            robot.parse(response.text.splitlines() if response.status_code == 200 else [])
            rules[host] = robot
        blocked = [s["url"] for s in sources if not rules[urlparse(s["url"]).netloc].can_fetch(USER_AGENT, s["url"])]
        if blocked and not args.robots_override_approved_by:
            print(f"\nrobots.txt disallows {len(blocked)} of {len(sources)} URLs. Stopping after the robots.txt requests.")
            print("To proceed, obtain the maintainers' authorisation and pass --robots-override-approved-by with their name.")
            return 3
        failures = []
        for source in sources:
            response, receipt = fetch(client, source["url"], "named-source")
            receipt["file"] = source["file"]
            if response.status_code == 304:
                # Unchanged on the server: carry the existing copy and its original receipt forward.
                files[source["file"]] = (PACK / source["file"]).read_bytes()
                manifest.append(dict(old_manifest[source["url"]]))
                receipts.append({**previous[source["url"]], "revalidated_at_utc": receipt["requested_at_utc"], "revalidation_status": 304})
                print(f"  not modified  {source['url']} (existing copy carried forward)")
            elif response.status_code == 200:
                files[source["file"]] = response.content
                manifest.append({"url": source["url"], "file": source["file"], "status": 200, "bytes": receipt["bytes"],
                                 "sha256": receipt["sha256"], "retrieved_at_utc": receipt["completed_at_utc"], "title": source["title"]})
                receipts.append(receipt)
                print(f"  saved         {source['url']}")
            else:
                failures.append((response.status_code, source["url"]))
                print(f"  HTTP {response.status_code}      {source['url']}")
    if failures:
        print(f"\n{len(failures)} of {len(sources)} URLs did not return content. Nothing was written, so no incomplete pack exists.")
        return 4

    # Write a complete pack in the same shape as the original, so the pipeline can build from it.
    for relative, content in {**files, **robots_files}.items():
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (out / "receipts" / "requests.json").write_text(json.dumps(receipts, indent=2))
    (out / "receipts" / "approval.json").write_text(json.dumps(
        {"approved_by": args.approved_by, "robots_override_approved_by": args.robots_override_approved_by,
         "user_agent": USER_AGENT, "run_started_utc": stamp, "based_on_pack": PACK.name}, indent=2))
    with (out / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["url", "file", "status", "bytes", "sha256", "retrieved_at_utc", "title"])
        writer.writeheader()
        writer.writerows(manifest)
    (out / "link-inventory.csv").write_bytes((PACK / "link-inventory.csv").read_bytes())
    (out / "LINK-INVENTORY-NOTE.txt").write_text(
        "link-inventory.csv was carried forward unchanged from the previous pack.\n"
        "It lists the links found in that pack's pages. If the refreshed pages link to\n"
        "different URLs, regenerate it before relying on the URL inventory.\n")
    print(f"\nWrote a complete pack ({len(manifest)} files) to {out}.")
    print("The site still builds from the original pack. To build from this one after review:")
    print(f"  SOURCE_PACK={out} npm run data:build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
