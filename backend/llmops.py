"""
LLMOps Observability Logger

Tracks every LLM generation call: model, latency, approximate tokens,
success/failure, and user context.  Writes structured JSONL to
logs/llmops.jsonl and increments Prometheus metrics defined in metrics.py.

Every public function swallows exceptions so it never breaks the critical
path.  Wire via record_llm_call() from chat route finally-blocks.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.logger import get_logger

logger = get_logger(__name__)

LOG_FILE = Path("logs/llmops.jsonl")


# ── Data Models ───────────────────────────────────────────────────────

@dataclass
class LLMCallRecord:
    """Structured record for a single LLM generation call."""
    request_id: str
    timestamp: str
    model: str
    user_id: Optional[str]
    session_id: Optional[str]
    latency_ms: float
    output_chars: int
    output_tokens_approx: int   # ~4 chars per token heuristic
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Logger Singleton ──────────────────────────────────────────────────

class LLMOpsLogger:
    """
    Records LLM call telemetry to a rotating JSONL log file and
    increments Prometheus counters/histograms.

    Design choices:
    - JSONL for easy tail/grep and future export to BigQuery or S3.
    - Output tokens approximated from character count (no Bedrock SDK
      dependency here; real token counts come from cost_tracking.py).
    - All writes are best-effort: failures are logged as warnings but
      never propagated to the caller.
    """

    def __init__(self) -> None:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        model: str,
        latency_ms: float,
        output_chars: int,
        success: bool,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Append one LLM call record to the JSONL log and update metrics."""
        rec = LLMCallRecord(
            request_id=uuid.uuid4().hex,
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=model or "unknown",
            user_id=user_id,
            session_id=session_id,
            latency_ms=round(latency_ms, 1),
            output_chars=output_chars,
            output_tokens_approx=max(1, output_chars // 4),
            success=success,
            error=error,
        )

        # JSONL append
        try:
            with open(LOG_FILE, "a") as fh:
                fh.write(json.dumps(asdict(rec)) + "\n")
        except Exception as exc:
            logger.warning("LLMOps JSONL write failed: %s", exc)

        # Prometheus
        try:
            from backend.metrics import track_llm_call
            track_llm_call(
                model=rec.model,
                latency_seconds=latency_ms / 1000,
                output_chars=output_chars,
                status="success" if success else "error",
            )
        except Exception as exc:
            logger.warning("LLMOps Prometheus update failed: %s", exc)

    def get_stats(self, last_n: int = 200) -> Dict[str, Any]:
        """
        Read the last *last_n* records from the JSONL log and return
        aggregated statistics suitable for the /admin/llmops endpoint.
        """
        records: List[Dict] = []
        try:
            if LOG_FILE.exists():
                lines = LOG_FILE.read_text().strip().splitlines()
                for line in lines[-last_n:]:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except Exception as exc:
            logger.warning("LLMOps stats read failed: %s", exc)
            return {"error": str(exc), "total_requests": 0}

        if not records:
            return {"total_requests": 0, "recent_records": []}

        latencies = [r["latency_ms"] for r in records]
        successes = sum(1 for r in records if r["success"])
        total_tokens = sum(r["output_tokens_approx"] for r in records)

        # Per-model breakdown
        model_counts: Dict[str, int] = {}
        for r in records:
            model_counts[r["model"]] = model_counts.get(r["model"], 0) + 1

        # Latency percentiles
        sorted_lat = sorted(latencies)
        n = len(sorted_lat)
        p50 = sorted_lat[n // 2] if n else 0
        p95 = sorted_lat[min(int(n * 0.95), n - 1)] if n else 0

        return {
            "total_requests": n,
            "success_rate_pct": round(successes / n * 100, 1) if n else 0,
            "error_count": n - successes,
            "latency_ms": {
                "p50": round(p50, 1),
                "p95": round(p95, 1),
                "avg": round(sum(latencies) / n, 1) if n else 0,
            },
            "tokens": {
                "total_approx": total_tokens,
                "avg_per_request": round(total_tokens / n) if n else 0,
            },
            "by_model": model_counts,
            "recent_records": records[-20:],   # Last 20 for the UI table
        }


# ── Singleton ─────────────────────────────────────────────────────────

_llmops_logger: Optional[LLMOpsLogger] = None


def get_llmops_logger() -> LLMOpsLogger:
    global _llmops_logger
    if _llmops_logger is None:
        _llmops_logger = LLMOpsLogger()
    return _llmops_logger


def record_llm_call(**kwargs) -> None:
    """Fire-and-forget convenience wrapper — safe to call from any context."""
    try:
        get_llmops_logger().record(**kwargs)
    except Exception as exc:
        logger.warning("record_llm_call failed: %s", exc)
