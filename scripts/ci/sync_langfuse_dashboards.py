#!/usr/bin/env python3
"""Create (or recreate) the Smart AI Tutor dashboard in Langfuse.

Uses the Langfuse unstable dashboards API. Widgets this script owns carry
MARKER in their description; re-running deletes those and the dashboard of
the same name, then builds them again, so edits belong here, not in the UI.

Env: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
(e.g. https://us.cloud.langfuse.com).

Cost, token and model charts read the ``bedrock-generation`` observations
that backend/bedrock_llm.py emits; the LlamaIndex callback's generations
carry no model or usage.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

DASHBOARD_NAME = "Smart AI Tutor - Production LLM"
MARKER = "[managed-by:scripts/ci/sync_langfuse_dashboards.py]"

GEN = {"column": "name", "operator": "=", "value": "bedrock-generation", "type": "string"}
SPAN = {"column": "type", "operator": "=", "value": "SPAN", "type": "string"}
ERROR = {"column": "level", "operator": "=", "value": "ERROR", "type": "string"}

# (name, description, chartType, metrics, dimensions, filters, (x, y, w, h))
WIDGETS = [
    ("LLM spend (USD)", "Total Bedrock LLM cost.", "NUMBER",
     [{"measure": "totalCost", "agg": "sum"}], [], [GEN], (0, 0, 3, 4)),
    ("LLM calls", "Bedrock generations.", "NUMBER",
     [{"measure": "count", "agg": "count"}], [], [GEN], (3, 0, 3, 4)),
    ("LLM p95 latency (ms)", "95th-percentile time for a full model response.", "NUMBER",
     [{"measure": "latency", "agg": "p95"}], [], [GEN], (6, 0, 3, 4)),
    ("Failed LLM calls", "Generations that ended in an error.", "NUMBER",
     [{"measure": "count", "agg": "count"}], [], [GEN, ERROR], (9, 0, 3, 4)),
    ("Cost by model", "Daily LLM cost per model.", "BAR_TIME_SERIES",
     [{"measure": "totalCost", "agg": "sum"}], [{"field": "providedModelName"}], [GEN], (0, 4, 6, 6)),
    ("Calls by model", "Share of generations per model.", "PIE",
     [{"measure": "count", "agg": "count"}], [{"field": "providedModelName"}], [GEN], (6, 4, 6, 6)),
    ("Input tokens", "Prompt tokens per day.", "LINE_TIME_SERIES",
     [{"measure": "inputTokens", "agg": "sum"}], [{"field": "providedModelName"}], [GEN], (0, 10, 6, 6)),
    ("Output tokens", "Completion tokens per day.", "LINE_TIME_SERIES",
     [{"measure": "outputTokens", "agg": "sum"}], [{"field": "providedModelName"}], [GEN], (6, 10, 6, 6)),
    ("Latency by model (p50 / p95, ms)", "Response time per model.", "HORIZONTAL_BAR",
     [{"measure": "latency", "agg": "p50"}, {"measure": "latency", "agg": "p95"}],
     [{"field": "providedModelName"}], [GEN], (0, 16, 6, 6)),
    ("Pipeline step latency (p95, ms)", "Slowest steps in the agent and RAG pipeline.", "HORIZONTAL_BAR",
     [{"measure": "latency", "agg": "p95"}], [{"field": "name"}], [SPAN], (6, 16, 6, 6)),
    ("Traces by pipeline", "Requests per day by trace name.", "BAR_TIME_SERIES",
     [{"measure": "count", "agg": "count"}], [{"field": "traceName"}], [SPAN], (0, 22, 6, 6)),
    ("Errors by step", "Observations logged at ERROR level, by name.", "HORIZONTAL_BAR",
     [{"measure": "count", "agg": "count"}], [{"field": "name"}], [ERROR], (6, 22, 6, 6)),
]


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
    host = os.environ.get("LANGFUSE_HOST") or os.environ.get("LANGFUSE_BASE_URL", "")
    pk, sk = os.environ.get("LANGFUSE_PUBLIC_KEY", ""), os.environ.get("LANGFUSE_SECRET_KEY", "")
    if not (host and pk and sk):
        print("LANGFUSE_HOST / LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set; nothing to do.")
        return 0
    api = Api(host, pk, sk)

    try:
        # Dashboards first: a widget can't be deleted while it is placed.
        for dash in api.list_all("/dashboards"):
            if dash.get("name") == DASHBOARD_NAME:
                api.call("DELETE", f"/dashboards/{dash['id']}")
        for widget in api.list_all("/dashboard-widgets"):
            if MARKER in (widget.get("description") or ""):
                api.call("DELETE", f"/dashboard-widgets/{widget['id']}")

        dashboard = api.call("POST", "/dashboards", {
            "name": DASHBOARD_NAME,
            "description": f"Bedrock cost, tokens, latency and errors in production. {MARKER}",
        })
        for name, desc, chart, metrics, dims, filters, (x, y, w, h) in WIDGETS:
            widget = api.call("POST", "/dashboard-widgets", {
                "name": name, "description": f"{desc} {MARKER}", "view": "observations",
                "chartType": chart, "metrics": metrics, "dimensions": dims, "filters": filters,
            })
            api.call("POST", f"/dashboards/{dashboard['id']}/placements", {
                "type": "widget", "widgetId": widget["id"], "x": x, "y": y, "width": w, "height": h,
            })
            print(f"placed {name}")
    except urllib.error.HTTPError as exc:
        print(f"Langfuse API error: HTTP {exc.code} {exc.read().decode(errors='replace')[:500]}", file=sys.stderr)
        return 1

    print(f"Dashboard '{DASHBOARD_NAME}' ready ({dashboard['id']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
