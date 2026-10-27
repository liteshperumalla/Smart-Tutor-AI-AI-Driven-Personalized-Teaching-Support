#!/usr/bin/env python3
"""Run every widget query in monitoring/langfuse/dashboards against Langfuse.

Each widget in those files is an exact GET /api/public/v2/metrics query. This
script runs them all for a recent window and reports, per widget, whether
Langfuse rejected the query (INVALID), returned no rows (EMPTY) or returned
data (OK). It exits 1 if any query is invalid, so the dashboard definitions
cannot silently drift from the metrics API. One run makes one request per
widget; Langfuse Cloud limits the metrics API per day (100 on the current
plan), and quota errors are reported as LIMITED, not as invalid.

Env: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST (or LANGFUSE_BASE_URL)

    python scripts/langfuse/check_dashboards.py [--days 7] [--environment production]

--environment replaces the dashboards' environment filter, e.g. to check
the widgets against "development" data.
"""

from __future__ import annotations

import argparse
import base64
import glob
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

DASHBOARD_GLOB = "monitoring/langfuse/dashboards/*.json"


def _run(host: str, auth: str, query: dict) -> tuple[str, str]:
    url = f"{host}/api/public/v2/metrics?" + urllib.parse.urlencode({"query": json.dumps(query)})
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read() or b"{}").get("data", [])
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        if exc.code == 429:
            return "LIMITED", "metrics API quota reached; try again after it resets"
        return ("INVALID" if exc.code == 400 else f"HTTP {exc.code}"), detail
    if not rows or all(all(v in (None, 0, []) for k, v in r.items() if k != "time_dimension") for r in rows):
        return "EMPTY", ""
    return "OK", f"{len(rows)} row(s)"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--environment", help="override the environment filter")
    args = parser.parse_args()

    host = (os.environ.get("LANGFUSE_HOST") or os.environ.get("LANGFUSE_BASE_URL") or "").rstrip("/")
    pk, sk = os.environ.get("LANGFUSE_PUBLIC_KEY", ""), os.environ.get("LANGFUSE_SECRET_KEY", "")
    if not (host and pk and sk):
        print("Set LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY.", file=sys.stderr)
        return 2
    auth = base64.b64encode(f"{pk}:{sk}".encode()).decode()

    now = datetime.now(timezone.utc)
    window = {
        "fromTimestamp": (now - timedelta(days=args.days)).isoformat().replace("+00:00", "Z"),
        "toTimestamp": now.isoformat().replace("+00:00", "Z"),
    }

    invalid = limited = 0
    for path in sorted(glob.glob(DASHBOARD_GLOB)):
        dashboard = json.load(open(path))
        print(f"\n{dashboard['name']} ({os.path.basename(path)})")
        for widget in dashboard["widgets"]:
            query = {**widget["query"], **window}
            if args.environment:
                query["filters"] = [
                    {**flt, "value": args.environment} if flt.get("column") == "environment" else flt
                    for flt in query["filters"]
                ]
            status, detail = _run(host, auth, query)
            invalid += status not in ("OK", "EMPTY", "LIMITED")
            limited += status == "LIMITED"
            print(f"  {status:<8} {widget['title']}" + (f"  - {detail}" if detail else ""))
    if invalid:
        print(f"\n{invalid} invalid query(ies).")
    elif limited:
        print(f"\nNo invalid queries; {limited} not checked (metrics API quota).")
    else:
        print("\nAll queries valid.")
    return 1 if invalid else 0


if __name__ == "__main__":
    sys.exit(main())
