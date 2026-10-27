#!/usr/bin/env python3
"""Create (or recreate) the Smart AI Tutor dashboards in Langfuse.

The dashboards are defined in monitoring/langfuse/dashboards/*.json; each
widget's ``query`` is the GET /api/public/v2/metrics query it charts, so the
same file is checked against live data by scripts/langfuse/check_dashboards.py.

Uses the Langfuse unstable dashboards API. Dashboards and widgets this script
owns carry MARKER in their description; re-running deletes them (and the
dashboards of the same names, plus the legacy single dashboard) and builds
them again, so edits belong in the JSON files, not in the UI.

Env: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
(e.g. https://us.cloud.langfuse.com).

    python scripts/ci/sync_langfuse_dashboards.py [--dry-run]

Every widget is scoped to environment=production (the backend sets the
Langfuse environment from ENVIRONMENT). Cost, token and model charts read the
``bedrock-generation`` observations that backend/bedrock_llm.py emits; the
LlamaIndex callback's generations carry no model or usage.
"""

from __future__ import annotations

import base64
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request

SPEC_GLOB = "monitoring/langfuse/dashboards/*.json"
MARKER = "[managed-by:scripts/ci/sync_langfuse_dashboards.py]"
# Replaced by the dashboards in SPEC_GLOB; deleted on the next sync.
LEGACY_DASHBOARDS = {"Smart AI Tutor - Production LLM"}


def load_specs() -> list[dict]:
    return [json.load(open(path)) for path in sorted(glob.glob(SPEC_GLOB))]


def widget_payload(widget: dict) -> dict:
    """Translate a spec widget (metrics-API query) into a dashboard widget."""
    query = widget["query"]
    return {
        "name": widget["title"],
        "description": f"{widget.get('description', '')} {MARKER}".strip(),
        "view": query["view"],
        "chartType": widget["chartType"],
        "chartConfig": {"type": widget["chartType"], **widget.get("chartConfig", {})},
        "metrics": [{"measure": m["measure"], "agg": m["aggregation"]} for m in query["metrics"]],
        "dimensions": query.get("dimensions", []),
        "filters": query.get("filters", []),
    }


class Api:
    def __init__(self, host: str, public_key: str, secret_key: str):
        self.base = host.rstrip("/") + "/api/public/unstable"
        token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        self.auth = f"Basic {token}"

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
        )
        req.add_header("Authorization", self.auth)
        req.add_header("Content-Type", "application/json")
        for attempt in range(6):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read()
                return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as exc:
                # The API allows ~30 requests a minute.
                if exc.code != 429 or attempt == 5:
                    raise
                time.sleep(float(exc.headers.get("Retry-After") or 5) + 1)
        raise AssertionError("unreachable")

    def list_all(self, path: str) -> list[dict]:
        items, page = [], 1
        while True:
            data = self.call("GET", f"{path}?limit=50&page={page}")
            items.extend(data.get("data", []))
            if page >= data.get("meta", {}).get("totalPages", 1):
                return items
            page += 1


def main() -> int:
    specs = load_specs()
    if "--dry-run" in sys.argv:
        for spec in specs:
            print(f"{spec['name']}: {len(spec['widgets'])} widgets")
            for widget in spec["widgets"]:
                print("  " + json.dumps({**widget_payload(widget), "layout": widget["layout"]}))
        return 0

    host = os.environ.get("LANGFUSE_HOST") or os.environ.get("LANGFUSE_BASE_URL", "")
    pk, sk = os.environ.get("LANGFUSE_PUBLIC_KEY", ""), os.environ.get("LANGFUSE_SECRET_KEY", "")
    if not (host and pk and sk):
        print("LANGFUSE_HOST / LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set; nothing to do.")
        return 0
    api = Api(host, pk, sk)
    managed_names = {spec["name"] for spec in specs} | LEGACY_DASHBOARDS

    try:
        # Dashboards first: a widget can't be deleted while it is placed.
        for dash in api.list_all("/dashboards"):
            if dash.get("name") in managed_names:
                api.call("DELETE", f"/dashboards/{dash['id']}")
        for widget in api.list_all("/dashboard-widgets"):
            if MARKER in (widget.get("description") or ""):
                api.call("DELETE", f"/dashboard-widgets/{widget['id']}")

        for spec in specs:
            dashboard = api.call("POST", "/dashboards", {
                "name": spec["name"],
                "description": f"{spec['description']} {MARKER}",
            })
            for widget in spec["widgets"]:
                created = api.call("POST", "/dashboard-widgets", widget_payload(widget))
                api.call("POST", f"/dashboards/{dashboard['id']}/placements", {
                    "type": "widget", "widgetId": created["id"], **widget["layout"],
                })
            print(f"Dashboard '{spec['name']}' ready ({dashboard['id']}, {len(spec['widgets'])} widgets).")
    except urllib.error.HTTPError as exc:
        print(f"Langfuse API error: HTTP {exc.code} {exc.read().decode(errors='replace')[:500]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
