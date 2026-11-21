#!/usr/bin/env python3
"""Compare two RAG evaluation runs: the Phase 2 quality gate.

Each input is the JSON that ``python -m backend.scripts.run_scheduled_evaluation``
prints. Run it once on the current stack (Bedrock + Titan, the baseline)
and once on the free stack (OpenRouter + local embeddings, the candidate),
with the same EVAL_JUDGE_PROVIDER for both so the scores are comparable.

Exits 1 if any metric drops by more than ``--max-drop`` (absolute, on the
0-1 scale), so it can gate a cutover in CI. Exits 2 if a run can't be
compared: a file holds no evaluation result or no quality_summary, or every
judge-scored metric is 0.

    python -m backend.scripts.compare_evaluations baseline.json candidate.json --max-drop 0.05
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

METRICS = (
    "avg_faithfulness",
    "avg_answer_relevance",
    "avg_context_recall",
    "avg_context_precision",
    "avg_correctness",
)
# Scored by the LLM judge; avg_context_precision is computed from retrieval
# scores without it, so it stays non-zero when the judge fails.
JUDGED_METRICS = tuple(m for m in METRICS if m != "avg_context_precision")


class UnusableRun(Exception):
    """An input file holds no evaluation result that can be compared."""


def load_summary(path: str) -> dict:
    text = Path(path).read_text()
    # The container also prints JSON log lines; the result is the last JSON
    # object that has the evaluation's keys.
    payload = None
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "quality_summary" in candidate or "total_evaluated" in candidate:
            payload = candidate
            break
    if payload is None:
        raise UnusableRun(f"{path}: no evaluation result found")
    summary = payload.get("quality_summary")
    if not summary:
        raise UnusableRun(f"{path}: no quality_summary ({payload.get('message') or payload.get('error') or 'empty run'})")
    return {**summary, "avg_latency": payload.get("avg_latency"), "judge_error": _judge_error(payload)}


def _judge_error(payload: dict) -> str | None:
    """The first per-question judge failure reason, if the run recorded one."""
    for result in payload.get("individual_results") or []:
        reasoning = str(result.get("reasoning") or "")
        if "failed" in reasoning.lower():
            return reasoning[:300]
    return None


def compare(baseline: dict, candidate: dict, max_drop: float) -> tuple[list[tuple], bool]:
    rows, ok = [], True
    for metric in METRICS:
        base, cand = baseline.get(metric), candidate.get(metric)
        if base is None or cand is None:
            # A metric that wasn't measured can't be shown to hold up.
            rows.append((metric, base, cand, None, "MISSING"))
            ok = False
            continue
        delta = cand - base
        passed = delta >= -max_drop
        ok = ok and passed
        rows.append((metric, base, cand, delta, "ok" if passed else "REGRESSED"))
    base_lat, cand_lat = baseline.get("avg_latency"), candidate.get("avg_latency")
    if base_lat is not None and cand_lat is not None:
        rows.append(("avg_latency (s)", base_lat, cand_lat, cand_lat - base_lat, "info"))
    return rows, ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    parser.add_argument("--max-drop", type=float, default=0.05, help="largest allowed drop per metric (default 0.05)")
    args = parser.parse_args(argv)

    try:
        baseline, candidate = load_summary(args.baseline), load_summary(args.candidate)
    except UnusableRun as exc:
        # Exit 2 (can't compare), not 1: an evaluation that produced no
        # result is not a metric regression.
        print(f"ERROR: {exc}; the run can't be compared.", file=sys.stderr)
        return 2
    for name, summary in (("baseline", baseline), ("candidate", candidate)):
        # evaluate_quality scores 0.0 when the judge call fails (no key, a
        # 429), so all judged metrics at 0 means the judge didn't run, not
        # bad answers.
        if all(not summary.get(metric) for metric in JUDGED_METRICS):
            reason = summary.get("judge_error")
            print(
                f"ERROR: every {name} judge-scored metric is 0 or missing; the judge most likely failed "
                f"(check EVAL_JUDGE_PROVIDER, its API key and rate limits) and the run can't be compared."
                + (f"\nFirst judge error: {reason}" if reason else ""),
                file=sys.stderr,
            )
            return 2
    rows, ok = compare(baseline, candidate, args.max_drop)

    print(f"{'metric':<24}{'baseline':>10}{'candidate':>11}{'change':>9}  result")
    for metric, base, cand, delta, result in rows:
        fmt = lambda v: f"{v:.3f}" if isinstance(v, (int, float)) else "-"  # noqa: E731
        change = f"{delta:+.3f}" if delta is not None else "-"
        print(f"{metric:<24}{fmt(base):>10}{fmt(cand):>11}{change:>9}  {result}")
    print(
        f"\nQuestions: baseline {baseline.get('evaluated_count')}, candidate {candidate.get('evaluated_count')}. "
        f"Allowed drop per metric: {args.max_drop:.2f}."
    )
    print("PASS: the free stack is within the allowed margin." if ok else "FAIL: at least one metric regressed.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
