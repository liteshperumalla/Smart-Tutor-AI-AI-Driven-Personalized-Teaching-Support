#!/usr/bin/env python3
"""Upload the repo's Grafana dashboards to a Grafana Cloud stack.

The EC2 Grafana gets these files through file provisioning; Grafana Cloud has
no access to the repo, so this pushes them through the HTTP API instead.

Env:
  GRAFANA_CLOUD_STACK_URL      e.g. https://<stack>.grafana.net
  GRAFANA_CLOUD_DASHBOARD_TOKEN  service-account token with dashboards:write
                                 and folders:write (Editor role is enough)
  GRAFANA_CLOUD_FOLDER         optional folder title (default "Smart AI Tutor")

Dashboards pick their Prometheus data source through the ``datasource``
template variable, so the same JSON works on both Grafanas.
"""

from __future__ import annotations

import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request

DASHBOARD_GLOB = "monitoring/grafana/dashboards/*.json"


# A Grafana Cloud stack that has been idle answers 502/503/504 while it
# resumes, which takes a few minutes; retry those (and 429) before failing.
RETRY_STATUSES = {429, 502, 503, 504}
RETRY_DELAYS = (10, 20, 30, 60, 60, 60)


def _request(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    for delay in (*RETRY_DELAYS, None):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRY_STATUSES or delay is None:
                raise
            reason = f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            if delay is None:
                raise
            reason = str(exc.reason)
        print(f"Grafana Cloud {method} {url} failed ({reason}); retrying in {delay}s.")
        time.sleep(delay)
    raise AssertionError("unreachable")


def _ensure_folder(base: str, token: str, title: str) -> str:
    for folder in _request("GET", f"{base}/api/folders?limit=1000", token):
        if folder.get("title") == title:
            return folder["uid"]
    return _request("POST", f"{base}/api/folders", token, {"title": title})["uid"]


def main() -> int:
    base = os.environ.get("GRAFANA_CLOUD_STACK_URL", "").rstrip("/")
    token = os.environ.get("GRAFANA_CLOUD_DASHBOARD_TOKEN", "")
    if not base or not token:
        print("::notice::GRAFANA_CLOUD_STACK_URL / GRAFANA_CLOUD_DASHBOARD_TOKEN not set; skipping Grafana Cloud dashboard sync.")
        return 0

    folder_uid = _ensure_folder(base, token, os.environ.get("GRAFANA_CLOUD_FOLDER", "Smart AI Tutor"))
    failures = 0
    for path in sorted(glob.glob(DASHBOARD_GLOB)):
        with open(path) as f:
            dashboard = json.load(f)
        dashboard.pop("id", None)
        try:
            result = _request("POST", f"{base}/api/dashboards/db", token, {
                "dashboard": dashboard,
                "folderUid": folder_uid,
                "overwrite": True,
                "message": f"Synced from {os.environ.get('GITHUB_SHA', 'local')[:12]}",
            })
            print(f"synced {path} -> {base}{result.get('url', '')}")
        except urllib.error.HTTPError as exc:
            failures += 1
            print(f"::error file={path}::Grafana Cloud rejected dashboard: HTTP {exc.code} {exc.read().decode(errors='replace')[:300]}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
