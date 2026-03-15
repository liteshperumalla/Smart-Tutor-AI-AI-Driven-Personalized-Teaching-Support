"""
Compute drift baseline statistics from known query datasets.

Usage:
  python scripts/compute_drift_baseline.py --out ./drift_baseline.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List


def _iter_queries() -> Iterable[str]:
    # Primary test dataset
    test_dataset = Path("backend/rag/tests/test_dataset.json")
    if test_dataset.exists():
        data = json.loads(test_dataset.read_text())
        items = data.get("queries", []) if isinstance(data, dict) else data
        for item in items:
            q = item.get("query")
            if q:
                yield q

    # Optional JSONL evaluation datasets
    for path in [
        "Evaluation_files/evaluation_data.jsonl",
        "Evaluation_files/evaluation_1_data.jsonl",
    ]:
        p = Path(path)
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                q = obj.get("query") or obj.get("question")
                if q:
                    yield q
            except Exception:
                continue


def _compute_stats(values: List[int]) -> dict:
    if not values:
        return {"mean": 0.0, "std": 1.0}
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / max(len(values) - 1, 1)
    std = var ** 0.5 if var > 0 else 1.0
    return {"mean": mean, "std": std}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="./drift_baseline.json")
    args = parser.parse_args()

    queries = list(_iter_queries())
    lengths = [len(q) for q in queries]
    words = [len(q.split()) for q in queries]

    len_stats = _compute_stats(lengths)
    word_stats = _compute_stats(words)

    baseline = {
        "count": len(queries),
        "mean_len": round(len_stats["mean"], 3),
        "std_len": round(len_stats["std"], 3),
        "mean_words": round(word_stats["mean"], 3),
        "std_words": round(word_stats["std"], 3),
    }

    Path(args.out).write_text(json.dumps(baseline, indent=2))
    print(f"Wrote baseline to {args.out} with {baseline['count']} queries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
