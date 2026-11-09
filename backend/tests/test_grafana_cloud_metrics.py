"""Every metric a Grafana dashboard queries must be sent to Grafana Cloud.

Production Prometheus only forwards an allowlist of metrics to Grafana Cloud
(free tier: 10k active series), set in monitoring/prometheus/prometheus-ec2.yml.
A dashboard that starts using a metric missing from that list would show
"No data" in Grafana Cloud while working on the EC2 Grafana.
"""

import glob
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

# PromQL words that look like metric names but are functions, keywords or
# aggregations.
_NOT_METRICS = {
    "sum", "avg", "min", "max", "count", "rate", "irate", "increase", "delta",
    "by", "without", "on", "ignoring", "group_left", "group_right", "and", "or",
    "unless", "bool", "offset", "histogram_quantile", "topk", "bottomk",
    "clamp_min", "clamp_max", "abs", "round", "ceil", "floor", "vector",
    "scalar", "time", "absent", "label_values", "label_replace", "sort",
    "sort_desc", "avg_over_time", "max_over_time", "min_over_time",
    "sum_over_time", "count_over_time", "quantile_over_time", "e", "inf",
    "nan", "le", "prometheus", "query_result",
}


def _dashboard_exprs():
    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("expr", "query") and isinstance(value, str):
                    yield value
                else:
                    yield from walk(value)
        elif isinstance(node, list):
            for item in node:
                yield from walk(item)

    for path in glob.glob(str(ROOT / "monitoring/grafana/dashboards/*.json")):
        with open(path) as f:
            yield from walk(json.load(f))


def _metric_names(expr):
    labels = set()
    for group in re.findall(r"\b(?:by|without|on|ignoring|group_left|group_right)\s*\(([^)]*)\)", expr):
        labels |= {name.strip() for name in group.split(",")}
    stripped = re.sub(r'\{[^}]*\}|"[^"]*"|\[[^\]]*\]', "", expr)
    for token in re.findall(r"(?<![$\w.])[a-zA-Z_:][a-zA-Z0-9_:]*", stripped):
        if token.lower() not in _NOT_METRICS and token not in labels:
            yield token


def test_dashboard_metrics_are_forwarded_to_grafana_cloud():
    config = yaml.safe_load((ROOT / "monitoring/prometheus/prometheus-ec2.yml").read_text())
    keep = config["remote_write"][0]["write_relabel_configs"][0]
    assert keep["action"] == "keep" and keep["source_labels"] == ["__name__"]
    allowed = re.compile(f"^(?:{keep['regex']})$")

    used = {name for expr in _dashboard_exprs() for name in _metric_names(expr)}
    assert "http_requests_total" in used  # the extraction finds metrics at all
    missing = sorted(name for name in used if not allowed.match(name))
    assert not missing, f"add these to the remote_write allowlist in prometheus-ec2.yml: {missing}"


def test_grafana_cloud_allowlist_drops_unused_high_cardinality_metrics():
    config = yaml.safe_load((ROOT / "monitoring/prometheus/prometheus-ec2.yml").read_text())
    allowed = re.compile(f"^(?:{config['remote_write'][0]['write_relabel_configs'][0]['regex']})$")
    for name in ("container_cpu_usage_seconds_total", "prometheus_tsdb_head_series", "node_load1"):
        assert not allowed.match(name)
