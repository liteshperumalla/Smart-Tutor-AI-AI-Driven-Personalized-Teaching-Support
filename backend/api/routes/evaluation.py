from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import List, Literal, Optional, TYPE_CHECKING
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    get_current_session,
    get_admin_session,
    get_evaluation_cron_token,
)
from backend.services.evaluation_run_store import append_run, list_runs, get_latest_run
from backend.config import config
from backend.retrieval_tuning import (
    build_grounded_answer_prompt,
    build_rag_recommendations,
    determine_retrieval_limit,
    select_diverse_items,
)

if TYPE_CHECKING:
    from backend.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


def get_evaluation_service():
    from backend.services.evaluation_service import (
        get_evaluation_service as _get_evaluation_service,
    )

    return _get_evaluation_service()


def get_cost_tracker():
    from backend.cost_tracking import get_cost_tracker as _get_cost_tracker

    return _get_cost_tracker()


def _bedrock_embedding_dimension() -> int:
    from backend.bedrock_embeddings import BedrockEmbeddings

    return BedrockEmbeddings.EMBEDDING_DIMENSION

_AWS_REGION_LABELS = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)",
    "us-west-2": "US West (Oregon)",
    "eu-west-1": "Europe (Ireland)",
    "eu-west-2": "Europe (London)",
    "eu-central-1": "Europe (Frankfurt)",
    "ap-south-1": "Asia Pacific (Mumbai)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)",
    "ap-northeast-1": "Asia Pacific (Tokyo)",
}


def _normalize_pricing_text(value: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _compact_pricing_text(value: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _model_keywords(model_id: Optional[str]) -> List[str]:
    raw = str(model_id or "").strip()
    if not raw:
        return []

    variants: set[str] = set()

    def add_variant(value: str):
        normalized = _normalize_pricing_text(value)
        if normalized:
            variants.add(normalized)

    raw_no_region = re.sub(r"^[a-z]{2}\.", "", raw, flags=re.IGNORECASE)
    tail = raw_no_region.split(".", 1)[-1]
    unversioned = re.sub(r"[-_: ]?v\d+(?:[:.]\d+)?$", "", tail, flags=re.IGNORECASE)
    expanded = re.sub(r"([a-z])([0-9])", r"\1 \2", unversioned, flags=re.IGNORECASE)
    expanded = re.sub(r"([0-9])([a-z])", r"\1 \2", expanded, flags=re.IGNORECASE)

    for candidate in (raw, raw_no_region, tail, unversioned, expanded):
        add_variant(candidate)

    if "llama" in raw.lower():
        major_minor = None
        if "llama3-1" in raw.lower() or "llama 3 1" in _normalize_pricing_text(raw):
            major_minor = "3.1"
        elif "llama3" in raw.lower() or "llama 3" in _normalize_pricing_text(raw):
            major_minor = "3"

        size_match = re.search(r"(\d+)\s*b", _normalize_pricing_text(raw))
        size_token = f"{size_match.group(1)}b" if size_match else ""
        instruction_suffix = " instruct" if "instruct" in raw.lower() else ""
        if major_minor:
            for prefix in ("", "meta "):
                add_variant(f"{prefix}llama {major_minor} {size_token}{instruction_suffix}".strip())
                if size_match:
                    add_variant(
                        f"{prefix}llama {major_minor} {size_match.group(1)} b{instruction_suffix}".strip()
                    )

    if "titan" in raw.lower() and "embed" in raw.lower():
        version_match = re.search(r"v\s*(\d+)", _normalize_pricing_text(raw))
        version = version_match.group(1) if version_match else ""
        suffix = f" v{version}" if version else ""
        for candidate in (
            f"amazon titan text embeddings{suffix}",
            f"titan text embeddings{suffix}",
            f"amazon titan embeddings{suffix}",
            f"titan embeddings{suffix}",
            f"titan embed text{suffix}",
        ):
            add_variant(candidate)

    return sorted(variants, key=len, reverse=True)


def _pricing_document_matches_model(pricing_document: dict, model_id: Optional[str]) -> bool:
    haystack = _normalize_pricing_text(json.dumps(pricing_document or {}, sort_keys=True))
    compact_haystack = _compact_pricing_text(haystack)
    haystack_tokens = set(haystack.split())

    for keyword in _model_keywords(model_id):
        if keyword in haystack:
            return True

        compact_keyword = _compact_pricing_text(keyword)
        if compact_keyword and compact_keyword in compact_haystack:
            return True

        keyword_tokens = set(keyword.split())
        if keyword_tokens and keyword_tokens.issubset(haystack_tokens):
            return True

    return False


def _coerce_metric_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_metric_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _aws_region_label(region_code: Optional[str]) -> Optional[str]:
    if not region_code:
        return None
    return _AWS_REGION_LABELS.get(region_code, region_code)


class EvaluationRunRequest(BaseModel):
    limit: Optional[int] = Field(default=None, ge=1, le=100)
    categories: Optional[List[str]] = Field(default=None, min_items=1)
    difficulties: Optional[List[str]] = Field(default=None, min_items=1)
    enable_quality_eval: bool = Field(default=False, description="Run LLM-as-judge quality evaluation on each test case")


class BatchQualityRequest(BaseModel):
    last_n: int = Field(default=20, ge=1, le=100, description="Number of recent queries to evaluate")
    model_id: Optional[str] = Field(default=None, description="Optional Bedrock model ID for judging")


@router.get("/cases")
def list_evaluation_cases(
    limit: Optional[int] = Query(default=None, ge=1, le=200),
    session=Depends(get_admin_session),
    service: EvaluationService = Depends(get_evaluation_service),
):
    return {"cases": service.list_cases(limit)}


@router.post("/run")
def run_evaluations(
    payload: EvaluationRunRequest,
    session=Depends(get_admin_session),
    service: EvaluationService = Depends(get_evaluation_service),
):
    return service.run_tests(
        limit=payload.limit,
        categories=payload.categories,
        difficulties=payload.difficulties,
        enable_quality_eval=payload.enable_quality_eval,
    )


@router.post("/batch-quality")
def run_batch_quality_evaluation(
    payload: BatchQualityRequest,
    session=Depends(get_admin_session),
):
    """
    Run LLM-as-judge quality evaluation on the last N logged queries.

    Reads recent queries from the JSONL log, runs the LLM judge on each
    (using the stored query + response), then returns aggregated quality scores.
    """
    import json
    from pathlib import Path
    from backend.services.rag_quality_evaluator import evaluate_batch

    log_file = Path(config.EVALUATION_LOG_FILE)
    if not log_file.exists():
        return {
            "total_evaluated": 0,
            "quality_summary": None,
            "individual_results": [],
            "message": "No queries logged yet. Start chatting to generate data!",
        }

    # Read recent records from JSONL
    records = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to read evaluation log: {e}")
        return {"error": "Failed to read evaluation log file"}

    # Take last N records that have both query and a response
    recent = records[-payload.last_n:]

    # Build evaluation batch from log entries
    eval_entries = []
    for r in recent:
        query_text = r.get("query", "")
        gen_metrics = r.get("generation_metrics", {})
        ret_metrics = r.get("retrieval_metrics", {})
        metadata = r.get("metadata", {})

        # We need the response text — check if it's stored
        # The log stores response_length but not full response,
        # so we'll use what we can reconstruct or evaluate what's there
        response_text = r.get("response", "")

        # If response isn't directly stored, skip
        # (older log entries may not have it)
        if not query_text:
            continue

        # Build context passages from metadata if available
        context_passages = r.get("context_passages", [])

        retrieval_scores = []
        if ret_metrics.get("min_score") and ret_metrics.get("max_score"):
            avg = ret_metrics.get("avg_relevance_score", 0)
            retrieval_scores = [avg] * ret_metrics.get("num_retrieved", 1)

        eval_entries.append({
            "query": query_text,
            "context_passages": context_passages,
            "answer": response_text,
            "retrieval_scores": retrieval_scores,
        })

    if not eval_entries:
        return {
            "total_evaluated": 0,
            "quality_summary": None,
            "individual_results": [],
            "message": "No evaluable queries found in recent logs.",
        }

    result = evaluate_batch(eval_entries, model_id=payload.model_id)
    return result


@router.get("/summary")
def evaluation_summary(
    session=Depends(get_admin_session),
    service: EvaluationService = Depends(get_evaluation_service),
):
    return {"summary": service.metrics_log_summary()}


@router.get("/realtime-metrics")
def get_realtime_rag_metrics(
    last_n: int = Query(default=100, ge=1, le=500),
    session=Depends(get_admin_session),
):
    """
    Get real-time RAG pipeline metrics from actual chat queries.

    Returns comprehensive metrics including:
    - Summary statistics (averages, counts)
    - Recent query details
    - Performance breakdown
    """
    import json
    from pathlib import Path

    log_file = Path(config.EVALUATION_LOG_FILE)

    if not log_file.exists():
        return {
            "realtime_metrics": {
                "status": "no_data",
                "message": "No RAG queries logged yet. Start chatting to see metrics!",
                "summary": None,
                "recent_queries": [],
                "performance": None,
            }
        }

    # Read and parse log file
    records = []
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to read metrics log: {e}")
        return {"realtime_metrics": {"status": "error", "message": "Failed to read metrics log file"}}

    if not records:
        return {
            "realtime_metrics": {
                "status": "no_data",
                "message": "No valid RAG queries logged yet.",
                "summary": None,
                "recent_queries": [],
                "performance": None,
            }
        }

    # Take last N records
    records = records[-last_n:]
    total_queries = len(records)

    # Calculate summary statistics
    retrieval_times = []
    generation_times = []
    total_times = []
    relevance_scores = []
    num_retrieved_list = []
    response_lengths = []

    for r in records:
        ret_metrics = r.get('retrieval_metrics', {})
        gen_metrics = r.get('generation_metrics', {})
        e2e_metrics = r.get('end_to_end_metrics', {})

        retrieval_time = _coerce_metric_float(ret_metrics.get('retrieval_time_seconds'))
        generation_time = _coerce_metric_float(gen_metrics.get('generation_time_seconds'))
        total_time = _coerce_metric_float(e2e_metrics.get('total_time_seconds'))
        relevance_score = ret_metrics.get('avg_relevance_score')
        docs_retrieved = ret_metrics.get('num_retrieved')
        response_length = gen_metrics.get('response_length_words')

        if retrieval_time > 0:
            retrieval_times.append(retrieval_time)
        if generation_time > 0:
            generation_times.append(generation_time)
        if total_time > 0:
            total_times.append(total_time)
        elif retrieval_time > 0 or generation_time > 0:
            total_times.append(retrieval_time + generation_time)
        if relevance_score is not None:
            relevance_scores.append(_coerce_metric_float(relevance_score))
        if docs_retrieved is not None:
            num_retrieved_list.append(_coerce_metric_int(docs_retrieved))
        if response_length is not None:
            response_lengths.append(_coerce_metric_int(response_length))

    def safe_avg(lst):
        return round(sum(lst) / len(lst), 3) if lst else 0

    def safe_percentile(lst, pct):
        if not lst:
            return 0
        sorted_lst = sorted(lst)
        idx = int(pct * (len(sorted_lst) - 1))
        return round(sorted_lst[idx], 3)

    # Build summary
    summary = {
        "total_queries_analyzed": total_queries,
        "avg_retrieval_time_seconds": safe_avg(retrieval_times),
        "avg_generation_time_seconds": safe_avg(generation_times),
        "avg_total_time_seconds": safe_avg(total_times),
        "p50_total_time_seconds": safe_percentile(total_times, 0.5),
        "p95_total_time_seconds": safe_percentile(total_times, 0.95),
        "p99_total_time_seconds": safe_percentile(total_times, 0.99),
        "avg_relevance_score": safe_avg(relevance_scores),
        "min_relevance_score": round(min(relevance_scores), 3) if relevance_scores else 0,
        "max_relevance_score": round(max(relevance_scores), 3) if relevance_scores else 0,
        "avg_docs_retrieved": safe_avg(num_retrieved_list),
        "avg_response_length_words": safe_avg(response_lengths),
    }

    # Performance breakdown
    fast_queries = sum(1 for t in total_times if t < 2.0)
    medium_queries = sum(1 for t in total_times if 2.0 <= t < 5.0)
    slow_queries = sum(1 for t in total_times if t >= 5.0)

    high_relevance = sum(1 for s in relevance_scores if s >= 0.7)
    medium_relevance = sum(1 for s in relevance_scores if 0.4 <= s < 0.7)
    low_relevance = sum(1 for s in relevance_scores if s < 0.4)

    performance = {
        "latency_distribution": {
            "fast_under_2s": fast_queries,
            "medium_2_to_5s": medium_queries,
            "slow_over_5s": slow_queries,
            "fast_percentage": round(fast_queries / len(total_times) * 100, 1) if total_times else 0,
        },
        "relevance_distribution": {
            "high_above_0_7": high_relevance,
            "medium_0_4_to_0_7": medium_relevance,
            "low_below_0_4": low_relevance,
            "high_relevance_percentage": round(high_relevance / len(relevance_scores) * 100, 1) if relevance_scores else 0,
        },
    }

    # Aggregate quality metrics from records that have them
    quality_records = [
        r["quality_metrics"]
        for r in records
        if r.get("quality_metrics") and isinstance(r.get("quality_metrics"), dict)
    ]
    quality_summary = None
    if quality_records:
        def safe_avg_field(recs, field):
            vals = [_coerce_metric_float(r.get(field)) for r in recs if r.get(field) is not None]
            return round(sum(vals) / len(vals), 4) if vals else 0

        quality_summary = {
            "avg_faithfulness": safe_avg_field(quality_records, "faithfulness"),
            "avg_answer_relevance": safe_avg_field(quality_records, "answer_relevance"),
            "avg_context_recall": safe_avg_field(quality_records, "context_recall"),
            "avg_context_precision": safe_avg_field(quality_records, "context_precision"),
            "avg_correctness": safe_avg_field(quality_records, "correctness"),
            "evaluated_count": len(quality_records),
        }

    # Recent queries (last 10)
    recent_queries = []
    for r in records[-10:][::-1]:  # Reverse to show newest first
        ret_metrics = r.get('retrieval_metrics', {})
        gen_metrics = r.get('generation_metrics', {})
        e2e_metrics = r.get('end_to_end_metrics', {})
        metadata = r.get('metadata', {})
        qm = r.get('quality_metrics')

        entry = {
            "timestamp": r.get('timestamp'),
            "query": r.get('query', '')[:100] + ('...' if len(r.get('query', '')) > 100 else ''),
            "retrieval_time": _coerce_metric_float(ret_metrics.get('retrieval_time_seconds')),
            "generation_time": _coerce_metric_float(gen_metrics.get('generation_time_seconds')),
            "total_time": _coerce_metric_float(e2e_metrics.get('total_time_seconds'))
            or (
                _coerce_metric_float(ret_metrics.get('retrieval_time_seconds'))
                + _coerce_metric_float(gen_metrics.get('generation_time_seconds'))
            ),
            "relevance_score": ret_metrics.get('avg_relevance_score')
            if ret_metrics.get('avg_relevance_score') is not None
            else None,
            "docs_retrieved": _coerce_metric_int(ret_metrics.get('num_retrieved')),
            "response_words": _coerce_metric_int(gen_metrics.get('response_length_words')),
            "mode": metadata.get('mode', 'chat'),
        }
        if qm and isinstance(qm, dict):
            entry["quality_scores"] = {
                "faithfulness": qm.get("faithfulness"),
                "answer_relevance": qm.get("answer_relevance"),
                "context_recall": qm.get("context_recall"),
                "correctness": qm.get("correctness"),
            }
        recent_queries.append(entry)

    return {
        "realtime_metrics": {
            "status": "ok",
            "summary": summary,
            "performance": performance,
            "quality_summary": quality_summary,
            "recent_queries": recent_queries,
        }
    }


@router.post("/logs/clear", status_code=status.HTTP_200_OK)
def clear_evaluation_logs(
    session=Depends(get_admin_session),
    service: EvaluationService = Depends(get_evaluation_service),
):
    service.clear_logs()
    return {"status": "cleared"}


@router.get("/metrics-history")
def get_metrics_history(
    hours: int = Query(default=24, ge=1, le=168),  # 1 hour to 7 days
    granularity: str = Query(default="hour", regex="^(minute|hour|day)$"),
    session=Depends(get_admin_session),
):
    """
    Get historical metrics aggregated by time buckets.

    Returns time-series data for charting:
    - Latency trends
    - Relevance scores over time
    - Query volumes
    """
    import json
    from pathlib import Path
    from collections import defaultdict

    log_file = Path(config.EVALUATION_LOG_FILE)

    if not log_file.exists():
        return {
            "history": {
                "status": "no_data",
                "message": "No metrics history available yet.",
                "data_points": [],
            }
        }

    # Read all records
    records = []
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to read metrics history: {e}")
        return {"history": {"status": "error", "message": "Failed to read metrics history", "data_points": []}}

    if not records:
        return {
            "history": {
                "status": "no_data",
                "message": "No valid metrics found.",
                "data_points": [],
            }
        }

    # Filter by time range
    cutoff = datetime.now(timezone.utc) - __import__('datetime').timedelta(hours=hours)
    filtered_records = []
    for r in records:
        try:
            ts = datetime.fromisoformat(r.get('timestamp', '').replace('Z', '+00:00'))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                filtered_records.append((ts, r))
        except Exception as e:
            logger.debug(f"Skipping record with unparseable timestamp: {e}")
            continue

    if not filtered_records:
        return {
            "history": {
                "status": "no_data",
                "message": f"No metrics in the last {hours} hours.",
                "data_points": [],
            }
        }

    # Aggregate by time bucket
    def get_bucket_key(ts):
        if granularity == "minute":
            return ts.strftime("%Y-%m-%d %H:%M")
        elif granularity == "hour":
            return ts.strftime("%Y-%m-%d %H:00")
        else:  # day
            return ts.strftime("%Y-%m-%d")

    buckets = defaultdict(lambda: {
        "count": 0,
        "total_latency": 0,
        "retrieval_latency": 0,
        "generation_latency": 0,
        "relevance_sum": 0,
        "docs_retrieved": 0,
    })

    for ts, r in filtered_records:
        key = get_bucket_key(ts)
        ret_metrics = r.get('retrieval_metrics', {})
        gen_metrics = r.get('generation_metrics', {})
        e2e_metrics = r.get('end_to_end_metrics', {})
        retrieval_time = _coerce_metric_float(ret_metrics.get('retrieval_time_seconds'))
        generation_time = _coerce_metric_float(gen_metrics.get('generation_time_seconds'))
        total_time = _coerce_metric_float(e2e_metrics.get('total_time_seconds'))
        relevance_score = _coerce_metric_float(ret_metrics.get('avg_relevance_score'))
        docs_retrieved = _coerce_metric_int(ret_metrics.get('num_retrieved'))

        buckets[key]["count"] += 1
        buckets[key]["total_latency"] += total_time or (retrieval_time + generation_time)
        buckets[key]["retrieval_latency"] += retrieval_time
        buckets[key]["generation_latency"] += generation_time
        buckets[key]["relevance_sum"] += relevance_score
        buckets[key]["docs_retrieved"] += docs_retrieved

    # Convert to sorted list
    data_points = []
    for key in sorted(buckets.keys()):
        b = buckets[key]
        count = b["count"]
        data_points.append({
            "timestamp": key,
            "query_count": count,
            "avg_latency": round(b["total_latency"] / count, 3) if count else 0,
            "avg_retrieval_latency": round(b["retrieval_latency"] / count, 3) if count else 0,
            "avg_generation_latency": round(b["generation_latency"] / count, 3) if count else 0,
            "avg_relevance": round(b["relevance_sum"] / count, 3) if count else 0,
            "avg_docs_retrieved": round(b["docs_retrieved"] / count, 2) if count else 0,
        })

    return {
        "history": {
            "status": "ok",
            "hours": hours,
            "granularity": granularity,
            "total_queries": len(filtered_records),
            "data_points": data_points,
        }
    }


class DatasetQualityRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=64, description="Number of dataset questions to evaluate")
    model_id: Optional[str] = Field(default=None, description="Optional Bedrock model ID for judging")


def _resolve_dataset_quality_file() -> Path:
    configured = Path(config.EVALUATION_DATASET_FILE)

    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(Path(__file__).resolve().parents[3] / configured)

    candidates.extend(
        [
            Path(__file__).resolve().parents[3] / "Evaluation_files/evaluation_data.jsonl",
            Path(__file__).resolve().parents[3] / "evaluation_dataset.json",
            Path(__file__).resolve().parents[3] / "backend/rag/tests/test_dataset.jsonl",
            Path(__file__).resolve().parents[3] / "backend/rag/tests/test_dataset.json",
        ]
    )

    seen = set()
    for candidate in candidates:
        normalized = candidate.resolve(strict=False)
        if normalized in seen:
            continue
        seen.add(normalized)
        if candidate.exists():
            return candidate
    return candidates[0]


def _load_dataset_entries(dataset_file: Path) -> List[dict]:
    entries: List[dict] = []

    def append_entry(raw_entry: dict):
        if not isinstance(raw_entry, dict):
            return
        question = (raw_entry.get("instruction") or raw_entry.get("query") or "").strip()
        if not question:
            return
        reference_answer = (
            raw_entry.get("output")
            or raw_entry.get("ground_truth_answer")
            or raw_entry.get("expected_answer")
            or ""
        )
        source_input = raw_entry.get("input") or raw_entry.get("context") or ""
        entries.append(
            {
                "question": question,
                "reference_answer": str(reference_answer).strip(),
                "source_input": str(source_input).strip(),
            }
        )

    if dataset_file.suffix.lower() == ".jsonl":
        with open(dataset_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue
                append_entry(entry)
        return entries

    with open(dataset_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, list):
        raw_entries = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("test_cases"), list):
            raw_entries = payload.get("test_cases", [])
        elif isinstance(payload.get("queries"), list):
            raw_entries = payload.get("queries", [])
        else:
            raw_entries = []
    else:
        raw_entries = []

    for entry in raw_entries:
        append_entry(entry)

    return entries
def _load_dataset_questions(dataset_file: Path) -> List[str]:
    return [entry["question"] for entry in _load_dataset_entries(dataset_file)]


def _build_drift_summary(drift_records: List[dict], enabled: bool) -> dict:
    drift_scores = [
        record.get("drift_score")
        for record in drift_records
        if isinstance(record.get("drift_score"), (int, float))
    ]
    high_drift_threshold = 2.0
    high_drift_count = sum(1 for score in drift_scores if score >= high_drift_threshold)

    return {
        "enabled": enabled,
        "baseline_path": str(Path(config.DRIFT_BASELINE_PATH)),
        "scored_count": len(drift_scores),
        "avg_drift_score": round(sum(drift_scores) / len(drift_scores), 4) if drift_scores else None,
        "max_drift_score": round(max(drift_scores), 4) if drift_scores else None,
        "high_drift_threshold": high_drift_threshold,
        "high_drift_count": high_drift_count,
        "high_drift_percentage": round(high_drift_count / len(drift_scores) * 100, 1) if drift_scores else 0.0,
    }


def _run_dataset_quality(limit: int, model_id: Optional[str]) -> dict:
    import time
    from backend.s3_retriever import create_s3_retriever
    from backend.bedrock_llm import BedrockLLM
    from backend.drift_monitor import get_drift_monitor
    from backend.services.rag_quality_evaluator import (
        evaluate_quality,
        compute_context_precision,
    )

    dataset_file = _resolve_dataset_quality_file()

    if not dataset_file.exists():
        return {
            "total_evaluated": 0,
            "quality_summary": None,
            "individual_results": [],
            "dataset_path": str(dataset_file),
            "message": f"Evaluation dataset not found at {dataset_file}",
        }

    dataset_entries = _load_dataset_entries(dataset_file)

    if not dataset_entries:
        return {
            "total_evaluated": 0,
            "quality_summary": None,
            "individual_results": [],
            "dataset_path": str(dataset_file),
            "message": "No questions found in evaluation dataset.",
        }

    # Limit the number of questions
    dataset_entries = dataset_entries[:limit]

    # Initialize retrieval and generation components before iterating through
    # the dataset so failures are reported as structured JSON instead of
    # bubbling up as an unhandled request error.
    try:
        retriever = create_s3_retriever(
            similarity_top_k=max(6, config.SIMILARITY_TOP_K + 2)
        )
        llm = BedrockLLM(model_id=model_id or config.BEDROCK_MODEL_ID)
        drift_monitor = get_drift_monitor()
    except Exception as exc:
        logging.getLogger(__name__).exception(
            "Failed to initialize dataset evaluation pipeline"
        )
        return {
            "total_evaluated": 0,
            "total_dataset_questions": len(dataset_entries),
            "avg_latency": 0,
            "quality_summary": None,
            "individual_results": [],
            "dataset_path": str(dataset_file),
            "drift_summary": _build_drift_summary([], enabled=False),
            "recommendations": [],
            "error": "initialization_failed",
            "message": f"Failed to initialize evaluation pipeline: {exc}",
        }

    individual_results = []
    faithfulness_sum = 0.0
    answer_relevance_sum = 0.0
    context_recall_sum = 0.0
    context_precision_sum = 0.0
    correctness_sum = 0.0
    total_latency = 0.0
    evaluated_count = 0
    drift_records = []

    for entry in dataset_entries:
        question = entry["question"]
        reference_answer = entry.get("reference_answer") or None
        drift = None
        try:
            drift = drift_monitor.score(question) if drift_monitor else None
            if drift:
                drift_records.append(drift)

            # 1. Retrieve context
            t0 = time.time()
            retrieval_limit = determine_retrieval_limit(
                question,
                base_top_k=max(3, config.SIMILARITY_TOP_K),
                max_top_k=max(6, config.SIMILARITY_TOP_K + 2),
            )
            retrieved_nodes = select_diverse_items(
                retriever.retrieve(question),
                query=question,
                limit=retrieval_limit,
                max_per_source=2,
            )
            retrieval_time = time.time() - t0

            context_passages = [
                node.node.get_text() if hasattr(node.node, "get_text") else ""
                for node in retrieved_nodes
            ]
            # Use original cosine similarity for context_precision (0-1 scale)
            # After reranking, node.score is the cross-encoder logit; the
            # original cosine score is stored in metadata.similarity_score.
            retrieval_scores = [
                node.node.metadata.get("similarity_score", getattr(node, "score", 0.0))
                for node in retrieved_nodes
            ]
            # 2. Generate response
            t1 = time.time()
            prompt = build_grounded_answer_prompt(question, context_passages)
            response_text = llm.generate(prompt=prompt, max_tokens=512)
            generation_time = time.time() - t1

            # 3. LLM-as-judge quality evaluation
            scores = evaluate_quality(
                question=question,
                context_passages=context_passages,
                answer=response_text,
                reference_answer=reference_answer,
                model_id=model_id,
            )
            ctx_precision = compute_context_precision(retrieval_scores)
            scores["context_precision"] = ctx_precision

            latency = round(retrieval_time + generation_time, 3)
            total_latency += latency

            individual_results.append({
                "query": question[:120],
                "faithfulness": scores["faithfulness"],
                "answer_relevance": scores["answer_relevance"],
                "context_recall": scores["context_recall"],
                "context_precision": ctx_precision,
                "correctness": scores["correctness"],
                "reasoning": scores.get("reasoning", ""),
                "latency": latency,
                "docs_retrieved": len(retrieved_nodes),
                "retrieval_limit": retrieval_limit,
                "drift_score": drift.get("drift_score") if drift else None,
                "has_reference_answer": bool(reference_answer),
                "avg_retrieval_score": round(
                    sum(retrieval_scores) / len(retrieval_scores), 4
                ) if retrieval_scores else 0,
            })

            faithfulness_sum += scores["faithfulness"]
            answer_relevance_sum += scores["answer_relevance"]
            context_recall_sum += scores["context_recall"]
            context_precision_sum += ctx_precision
            correctness_sum += scores["correctness"]
            evaluated_count += 1

        except Exception as e:
            logging.getLogger(__name__).error(
                f"Dataset eval failed for question: {question[:80]}: {e}"
            )
            individual_results.append({
                "query": question[:120],
                "faithfulness": 0,
                "answer_relevance": 0,
                "context_recall": 0,
                "context_precision": 0,
                "correctness": 0,
                "reasoning": "Evaluation failed for this question",
                "latency": 0,
                "docs_retrieved": 0,
                "drift_score": drift.get("drift_score") if drift else None,
                "has_reference_answer": bool(reference_answer),
                "avg_retrieval_score": 0,
            })

    if evaluated_count == 0:
        return {
            "total_evaluated": 0,
            "quality_summary": None,
            "individual_results": individual_results,
            "dataset_path": str(dataset_file),
            "drift_summary": _build_drift_summary(drift_records, drift_monitor is not None),
            "message": "All evaluations failed.",
        }

    avg_latency = round(total_latency / evaluated_count, 3)
    quality_summary = {
        "avg_faithfulness": round(faithfulness_sum / evaluated_count, 4),
        "avg_answer_relevance": round(answer_relevance_sum / evaluated_count, 4),
        "avg_context_recall": round(context_recall_sum / evaluated_count, 4),
        "avg_context_precision": round(context_precision_sum / evaluated_count, 4),
        "avg_correctness": round(correctness_sum / evaluated_count, 4),
        "evaluated_count": evaluated_count,
    }

    return {
        "total_evaluated": evaluated_count,
        "total_dataset_questions": len(dataset_entries),
        "avg_latency": avg_latency,
        "dataset_path": str(dataset_file),
        "drift_summary": _build_drift_summary(drift_records, drift_monitor is not None),
        "quality_summary": quality_summary,
        "recommendations": build_rag_recommendations(
            avg_context_recall=quality_summary.get("avg_context_recall"),
            avg_context_precision=quality_summary.get("avg_context_precision"),
            avg_correctness=quality_summary.get("avg_correctness"),
            p95_response_time=max((item.get("latency", 0) for item in individual_results), default=0),
        ),
        "individual_results": individual_results,
    }


def _store_dataset_run(result: dict, limit: int, model_id: Optional[str], source: str) -> None:
    individual = result.get("individual_results") or []
    sample = sorted(
        individual,
        key=lambda item: item.get("correctness", 0),
    )[:5]
    previous = get_latest_run()
    previous_summary = (previous or {}).get("summary") or {}
    previous_quality = (previous_summary.get("quality_summary") or {}) if previous_summary else {}
    current_quality = result.get("quality_summary") or {}
    previous_drift = (previous_summary.get("drift_summary") or {}) if previous_summary else {}
    current_drift = result.get("drift_summary") or {}

    def delta_metric(key: str) -> Optional[float]:
        current = current_quality.get(key)
        prev = previous_quality.get(key)
        if current is None or prev is None:
            return None
        return round(current - prev, 4)

    def delta_drift_metric(key: str) -> Optional[float]:
        current = current_drift.get(key)
        prev = previous_drift.get(key)
        if current is None or prev is None:
            return None
        return round(current - prev, 4)

    delta = {
        "avg_faithfulness": delta_metric("avg_faithfulness"),
        "avg_answer_relevance": delta_metric("avg_answer_relevance"),
        "avg_context_recall": delta_metric("avg_context_recall"),
        "avg_context_precision": delta_metric("avg_context_precision"),
        "avg_correctness": delta_metric("avg_correctness"),
        "avg_drift_score": delta_drift_metric("avg_drift_score"),
        "avg_latency": None,
    }
    if previous_summary and previous_summary.get("avg_latency") is not None and result.get("avg_latency") is not None:
        delta["avg_latency"] = round(result.get("avg_latency", 0) - previous_summary.get("avg_latency", 0), 4)

    return append_run(
        {
            "source": source,
            "run_type": "dataset_quality",
            "dataset": result.get("dataset_path") or str(_resolve_dataset_quality_file()),
            "params": {"limit": limit, "model_id": model_id},
            "summary": {
                "total_evaluated": result.get("total_evaluated", 0),
                "total_dataset_questions": result.get("total_dataset_questions", 0),
                "avg_latency": result.get("avg_latency", 0),
                "drift_summary": result.get("drift_summary"),
                "quality_summary": result.get("quality_summary"),
                "delta": delta,
            },
            "sample_results": sample,
        }
    )


@router.post("/run-dataset-quality")
def run_dataset_quality_evaluation(
    payload: DatasetQualityRequest,
    session=Depends(get_admin_session),
):
    """
    Run the evaluation dataset questions through the current RAG pipeline.

    For each question:
    1. Retrieve context from S3 vector index
    2. Generate response with Bedrock LLM
    3. Score with LLM-as-judge (faithfulness, answer_relevance, context_recall)

    Returns aggregated quality scores + individual results.
    """
    result = _run_dataset_quality(payload.limit, payload.model_id)
    record = _store_dataset_run(result, payload.limit, payload.model_id, source="manual")
    return {**result, "run_record": record}


@router.post("/run-scheduled")
def run_scheduled_dataset_quality_evaluation(
    payload: DatasetQualityRequest,
    token=Depends(get_evaluation_cron_token),
):
    result = _run_dataset_quality(payload.limit, payload.model_id)
    record = _store_dataset_run(result, payload.limit, payload.model_id, source="scheduled")
    return {**result, "run_record": record}


class ProductionSampleRequest(BaseModel):
    # Sampling knobs
    sample_size: Optional[int] = Field(
        default=None, ge=1, le=200,
        description="Number of production query/answer pairs to evaluate. Defaults to EVAL_PRODUCTION_SAMPLE_SIZE.",
    )
    lookback_hours: Optional[int] = Field(
        default=None, ge=1, le=720,
        description="Only sample sessions updated within this many hours. Defaults to EVAL_PRODUCTION_SAMPLE_LOOKBACK_HOURS.",
    )
    # Reproducibility
    seed: Optional[int] = Field(
        default=None,
        description="Optional RNG seed for repeatable samples (omit for true random).",
    )
    # Judge config
    judge_mode: Optional[Literal["combined", "split"]] = Field(
        default=None,
        description="`combined` (1 LLM call/query) or `split` (4 calls/query, anti-halo). Defaults to EVAL_JUDGE_MODE.",
    )
    model_id: Optional[str] = Field(
        default=None,
        description="Optional Bedrock model ID for the judge.",
    )


@router.post("/sample-production")
def sample_production_evaluation(
    payload: ProductionSampleRequest,
    token=Depends(get_evaluation_cron_token),
):
    """Monte Carlo sample of real production traffic, then LLM-judge it.

    Unlike `/run-dataset-quality` which evaluates against the static
    `test_dataset.json`, this samples N random user-question / assistant-
    answer pairs from the live chat store and scores them with the same
    judge. Designed for continuous quality auditing: spot drift, sudden
    regression in real conditions, etc.
    """
    from backend.services.production_sampler import run_production_sample_evaluation
    try:
        return run_production_sample_evaluation(
            n=payload.sample_size,
            since_hours=payload.lookback_hours,
            judge_mode=payload.judge_mode,
            model_id=payload.model_id,
            rng_seed=payload.seed,
        )
    except RuntimeError as exc:
        # Misconfiguration (e.g. storage backend without list_users()): surface
        # the message verbatim so the scheduled workflow's Slack alert shows
        # the operator exactly what to fix.
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/runs")
def list_evaluation_runs(
    limit: int = Query(default=20, ge=1, le=100),
    session=Depends(get_admin_session),
):
    return {"runs": list_runs(limit=limit)}


@router.get("/export")
def export_all_metrics(
    format: str = Query(default="json", regex="^(json|csv)$"),
    session=Depends(get_admin_session),
    service: EvaluationService = Depends(get_evaluation_service),
):
    """
    Export all evaluation metrics in JSON or CSV format.
    """
    import json
    import csv
    import io
    from pathlib import Path
    from fastapi.responses import StreamingResponse

    log_file = Path(config.EVALUATION_LOG_FILE)

    if not log_file.exists():
        return {"error": "No metrics data available"}

    # Read all records
    records = []
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if format == "json":
        # Return JSON array
        output = io.StringIO()
        json.dump(records, output, indent=2)
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=rag_metrics_export.json"}
        )
    else:
        # Return CSV
        output = io.StringIO()
        if records:
            # Flatten records for CSV
            flat_records = []
            for r in records:
                flat = {
                    "timestamp": r.get("timestamp", ""),
                    "query": r.get("query", ""),
                    "retrieval_time": r.get("retrieval_metrics", {}).get("retrieval_time_seconds", 0),
                    "generation_time": r.get("generation_metrics", {}).get("generation_time_seconds", 0),
                    "total_time": r.get("end_to_end_metrics", {}).get("total_time_seconds", 0),
                    "relevance_score": r.get("retrieval_metrics", {}).get("avg_relevance_score", 0),
                    "docs_retrieved": r.get("retrieval_metrics", {}).get("num_retrieved", 0),
                    "response_words": r.get("generation_metrics", {}).get("response_length_words", 0),
                    "mode": r.get("metadata", {}).get("mode", ""),
                }
                flat_records.append(flat)

            writer = csv.DictWriter(output, fieldnames=flat_records[0].keys())
            writer.writeheader()
            writer.writerows(flat_records)

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=rag_metrics_export.csv"}
        )


@router.get("/aws-metrics")
def get_aws_metrics(
    date: Optional[str] = Query(default=None, description="Date in YYYY-MM-DD format"),
    session=Depends(get_admin_session),
):
    """
    Get comprehensive AWS service metrics and costs.

    Returns metrics for all AWS services: Bedrock, S3, DynamoDB, etc.
    """
    import boto3
    import json as json_module
    from botocore.exceptions import ClientError

    def build_aws_client(service_name: str, *, pricing: bool = False):
        kwargs = dict(client_kwargs)
        if pricing:
            kwargs["region_name"] = "us-east-1"
        return boto3.client(service_name, **kwargs)

    def unavailable_pricing() -> dict:
        return {
            "input_per_1k": None,
            "output_per_1k": None,
            "storage_per_gb_month": None,
            "get_per_1k": None,
            "put_per_1k": None,
            "read_per_million": None,
            "write_per_million": None,
            "source": "AWS Price List API",
        }

    def pricing_value_from_dimension(dimension: dict) -> Optional[float]:
        try:
            usd = (dimension or {}).get("pricePerUnit", {}).get("USD")
            if usd in (None, ""):
                return None
            return float(usd)
        except (TypeError, ValueError):
            return None

    def fetch_pricing_products(service_code: str, filters: List[dict]) -> List[dict]:
        pricing = build_aws_client("pricing", pricing=True)
        paginator = pricing.get_paginator("get_products")
        filter_sets: List[List[dict]] = [filters]

        if filters:
            without_location = [f for f in filters if f.get("Field") != "location"]
            if without_location != filters:
                filter_sets.append(without_location)
            filter_sets.append([])

        for current_filters in filter_sets:
            products: List[dict] = []
            for page in paginator.paginate(
                ServiceCode=service_code,
                Filters=current_filters,
                FormatVersion="aws_v1",
                PaginationConfig={"MaxItems": 100, "PageSize": 100},
            ):
                for entry in page.get("PriceList", []):
                    try:
                        products.append(json_module.loads(entry))
                    except (TypeError, json_module.JSONDecodeError):
                        continue
            if products:
                return products

        return []

    def extract_price(products: List[dict], *, product_match=None, dimension_match=None) -> Optional[float]:
        for product in products:
            attributes = (product.get("product") or {}).get("attributes") or {}
            if product_match and not product_match(product, attributes):
                continue
            terms = (product.get("terms") or {}).get("OnDemand") or {}
            for term in terms.values():
                for dimension in ((term or {}).get("priceDimensions") or {}).values():
                    if dimension_match and not dimension_match(dimension, product, attributes):
                        continue
                    value = pricing_value_from_dimension(dimension)
                    if value is not None:
                        return value
        return None

    region_label = _aws_region_label(config.AWS_REGION)

    def fetch_live_pricing_snapshot() -> dict:
        snapshot = {
            "bedrock": {
                "llm": {"input_per_1k": None, "output_per_1k": None},
                "embedding": {"input_per_1k": None},
                "source": "AWS Price List API",
            },
            "s3": {
                "storage_per_gb_month": None,
                "get_per_1k": None,
                "put_per_1k": None,
                "source": "AWS Price List API",
            },
            "dynamodb": {
                "read_per_million": None,
                "write_per_million": None,
                "storage_per_gb_month": None,
                "source": "AWS Price List API",
            },
        }

        try:
            bedrock_filters = [
                {"Type": "TERM_MATCH", "Field": "location", "Value": region_label},
            ] if region_label else []
            bedrock_products = fetch_pricing_products("AmazonBedrock", bedrock_filters)
            snapshot["bedrock"]["llm"]["input_per_1k"] = extract_price(
                bedrock_products,
                product_match=lambda product, attributes: _pricing_document_matches_model(
                    {"product": product.get("product"), "attributes": attributes},
                    config.BEDROCK_MODEL_ID,
                ),
                dimension_match=lambda dimension, *_: "input"
                in ((dimension.get("description") or "").lower()),
            )
            snapshot["bedrock"]["llm"]["output_per_1k"] = extract_price(
                bedrock_products,
                product_match=lambda product, attributes: _pricing_document_matches_model(
                    {"product": product.get("product"), "attributes": attributes},
                    config.BEDROCK_MODEL_ID,
                ),
                dimension_match=lambda dimension, *_: "output"
                in ((dimension.get("description") or "").lower()),
            )
            snapshot["bedrock"]["embedding"]["input_per_1k"] = extract_price(
                bedrock_products,
                product_match=lambda product, attributes: _pricing_document_matches_model(
                    {"product": product.get("product"), "attributes": attributes},
                    config.BEDROCK_EMBEDDING_MODEL_ID,
                ),
            )
        except Exception as pricing_error:
            logging.getLogger(__name__).warning("Bedrock pricing lookup failed: %s", pricing_error)

        try:
            s3_filters = [
                {"Type": "TERM_MATCH", "Field": "location", "Value": region_label},
            ] if region_label else []
            s3_products = fetch_pricing_products("AmazonS3", s3_filters)
            snapshot["s3"]["storage_per_gb_month"] = extract_price(
                s3_products,
                product_match=lambda product, attributes: (
                    product.get("product", {}).get("productFamily") == "Storage"
                    and any(
                        marker in _normalize_pricing_text(json_module.dumps(attributes))
                        for marker in ["general purpose", "standard"]
                    )
                ),
            )
            snapshot["s3"]["get_per_1k"] = extract_price(
                s3_products,
                product_match=lambda product, attributes: product.get("product", {}).get("productFamily") == "API Request",
                dimension_match=lambda dimension, *_: "get" in ((dimension.get("description") or "").lower()),
            )
            snapshot["s3"]["put_per_1k"] = extract_price(
                s3_products,
                product_match=lambda product, attributes: product.get("product", {}).get("productFamily") == "API Request",
                dimension_match=lambda dimension, *_: any(
                    keyword in ((dimension.get("description") or "").lower())
                    for keyword in ["put", "copy", "post", "list"]
                ),
            )
        except Exception as pricing_error:
            logging.getLogger(__name__).warning("S3 pricing lookup failed: %s", pricing_error)

        try:
            dynamodb_filters = [
                {"Type": "TERM_MATCH", "Field": "location", "Value": region_label},
            ] if region_label else []
            dynamodb_products = fetch_pricing_products("AmazonDynamoDB", dynamodb_filters)
            snapshot["dynamodb"]["read_per_million"] = extract_price(
                dynamodb_products,
                dimension_match=lambda dimension, *_: "read request units" in ((dimension.get("description") or "").lower()),
            )
            snapshot["dynamodb"]["write_per_million"] = extract_price(
                dynamodb_products,
                dimension_match=lambda dimension, *_: "write request units" in ((dimension.get("description") or "").lower()),
            )
            snapshot["dynamodb"]["storage_per_gb_month"] = extract_price(
                dynamodb_products,
                product_match=lambda product, *_: product.get("product", {}).get("productFamily") == "Database Storage",
            )
        except Exception as pricing_error:
            logging.getLogger(__name__).warning("DynamoDB pricing lookup failed: %s", pricing_error)

        return snapshot

    metrics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "region": config.AWS_REGION,
        "services": {},
        "costs": {},
        "errors": [],
    }

    # AWS Client setup
    client_kwargs = {"region_name": config.AWS_REGION}
    if config.AWS_ACCESS_KEY_ID and config.AWS_SECRET_ACCESS_KEY:
        client_kwargs["aws_access_key_id"] = config.AWS_ACCESS_KEY_ID
        client_kwargs["aws_secret_access_key"] = config.AWS_SECRET_ACCESS_KEY
        if config.AWS_SESSION_TOKEN:
            client_kwargs["aws_session_token"] = config.AWS_SESSION_TOKEN

    live_pricing = fetch_live_pricing_snapshot()

    # 1. BEDROCK METRICS
    try:
        metrics["services"]["bedrock"] = {
            "status": "active",
            "models": {
                "llm": {
                    "model_id": config.BEDROCK_MODEL_ID,
                    "pricing": {
                        "input_per_1k": live_pricing["bedrock"]["llm"]["input_per_1k"],
                        "output_per_1k": live_pricing["bedrock"]["llm"]["output_per_1k"],
                        "source": live_pricing["bedrock"]["source"],
                    },
                },
                "embedding": {
                    "model_id": config.BEDROCK_EMBEDDING_MODEL_ID,
                    "pricing": {
                        "input_per_1k": live_pricing["bedrock"]["embedding"]["input_per_1k"],
                        "source": live_pricing["bedrock"]["source"],
                    },
                    "dimension": _bedrock_embedding_dimension(),
                },
            },
            "available_models": [
                {"id": config.BEDROCK_MODEL_ID, "name": "Active LLM Model", "type": "llm"},
                {"id": config.BEDROCK_EMBEDDING_MODEL_ID, "name": "Active Embedding Model", "type": "embedding"},
            ],
        }
    except Exception as e:
        logging.getLogger(__name__).error(f"Bedrock metrics error: {e}")
        metrics["errors"].append("Bedrock: service unavailable")
        metrics["services"]["bedrock"] = {"status": "error", "error": "Service unavailable"}

    # 2. S3 METRICS
    try:
        s3 = boto3.client("s3", **client_kwargs)
        bucket_name = config.S3_DOCUMENTS_BUCKET

        # Get bucket stats
        try:
            # List objects to count
            paginator = s3.get_paginator('list_objects_v2')
            total_size = 0
            total_objects = 0

            for page in paginator.paginate(Bucket=bucket_name, PaginationConfig={'MaxItems': 1000}):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        total_size += obj.get('Size', 0)
                        total_objects += 1

            metrics["services"]["s3"] = {
                "status": "active",
                "bucket": bucket_name,
                "total_objects": total_objects,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "index_prefix": "faiss_index/",
                "documents_prefix": "modules/",
                "pricing": {
                    **live_pricing["s3"],
                },
            }
        except ClientError as e:
            logging.getLogger(__name__).error(f"S3 bucket access error: {e}")
            metrics["services"]["s3"] = {
                "status": "limited",
                "bucket": bucket_name,
                "error": "Access denied or bucket not found",
            }
    except Exception as e:
        logging.getLogger(__name__).error(f"S3 metrics error: {e}")
        metrics["errors"].append("S3: service unavailable")
        metrics["services"]["s3"] = {"status": "error", "error": "Service unavailable"}

    # 3. DYNAMODB METRICS
    try:
        dynamodb = boto3.client("dynamodb", **client_kwargs)
        table_name = config.DYNAMODB_TABLE_CHAT_SESSIONS

        try:
            table_info = dynamodb.describe_table(TableName=table_name)
            table = table_info.get("Table", {})

            metrics["services"]["dynamodb"] = {
                "status": "active",
                "table_name": table_name,
                "item_count": table.get("ItemCount", 0),
                "size_bytes": table.get("TableSizeBytes", 0),
                "size_mb": round(table.get("TableSizeBytes", 0) / (1024 * 1024), 2),
                "billing_mode": table.get("BillingModeSummary", {}).get("BillingMode"),
                "table_status": table.get("TableStatus", "UNKNOWN"),
                "pricing": {
                    **live_pricing["dynamodb"],
                },
            }
        except ClientError as e:
            logging.getLogger(__name__).error(f"DynamoDB table access error: {e}")
            metrics["services"]["dynamodb"] = {
                "status": "limited",
                "table_name": table_name,
                "error": "Access denied or table not found",
            }
    except Exception as e:
        logging.getLogger(__name__).error(f"DynamoDB metrics error: {e}")
        metrics["errors"].append("DynamoDB: service unavailable")
        metrics["services"]["dynamodb"] = {"status": "error", "error": "Service unavailable"}

    # 4. COST TRACKING
    try:
        tracker = get_cost_tracker()
        daily_costs = tracker.get_daily_costs(date)
        metrics["costs"] = {
            "daily": daily_costs,
            "tracking_enabled": config.ENABLE_COST_TRACKING,
        }
    except Exception as e:
        logging.getLogger(__name__).error(f"Cost tracking error: {e}")
        metrics["errors"].append("Cost Tracking: service unavailable")
        metrics["costs"] = {
            "daily": {
                "date": date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "total_cost_usd": None,
                "total_tokens": None,
                "entries": None,
                "error": "Cost tracking unavailable",
            },
            "tracking_enabled": False,
        }

    # 5. STS (Identity verification)
    try:
        sts = boto3.client("sts", **client_kwargs)
        identity = sts.get_caller_identity()
        metrics["services"]["sts"] = {
            "status": "active",
            "account_id": identity.get("Account", "")[-4:].rjust(12, "*"),  # Mask account
            "arn_suffix": identity.get("Arn", "").split("/")[-1] if identity.get("Arn") else "",
        }
    except Exception as e:
        logging.getLogger(__name__).error(f"STS identity error: {e}")
        metrics["errors"].append("STS: service unavailable")
        metrics["services"]["sts"] = {"status": "error", "error": "Service unavailable"}

    # 6. CLOUDWATCH METRICS (if available)
    try:
        cloudwatch = boto3.client("cloudwatch", **client_kwargs)

        # Determine date range: use the requested date or today
        if date:
            query_dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            start_time = query_dt
            end_time = query_dt + timedelta(days=1)
        else:
            end_time = datetime.now(timezone.utc)
            start_time = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
            # If less than 1 hour into the day, look at yesterday + today to avoid empty windows
            if (end_time - start_time).total_seconds() < 3600:
                start_time = start_time - timedelta(days=1)

        try:
            cw_metrics = {}
            for metric_name in ["Invocations", "InputTokenCount", "OutputTokenCount", "InvocationLatency"]:
                response = cloudwatch.get_metric_statistics(
                    Namespace="AWS/Bedrock",
                    MetricName=metric_name,
                    Dimensions=[],  # aggregate across all models
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,
                    Statistics=["Sum"],
                )
                datapoints = response.get("Datapoints", [])
                cw_metrics[metric_name] = int(sum(d.get("Sum", 0) for d in datapoints))

            metrics["services"]["cloudwatch"] = {
                "status": "active",
                "period_start": start_time.strftime("%Y-%m-%d"),
                "period_end": end_time.strftime("%Y-%m-%d"),
                "bedrock_invocations": cw_metrics["Invocations"],
                "bedrock_input_tokens": cw_metrics["InputTokenCount"],
                "bedrock_output_tokens": cw_metrics["OutputTokenCount"],
                "bedrock_invocation_latency_ms": cw_metrics["InvocationLatency"],
            }
        except ClientError:
            metrics["services"]["cloudwatch"] = {
                "status": "limited",
                "note": "Metrics may require additional permissions",
                "bedrock_invocations": None,
                "bedrock_input_tokens": None,
                "bedrock_output_tokens": None,
                "bedrock_invocation_latency_ms": None,
            }
    except Exception as e:
        metrics["services"]["cloudwatch"] = {
            "status": "unavailable",
            "bedrock_invocations": None,
            "bedrock_input_tokens": None,
            "bedrock_output_tokens": None,
            "bedrock_invocation_latency_ms": None,
        }

    # Summary
    active_services = sum(1 for s in metrics["services"].values() if s.get("status") == "active")
    metrics["summary"] = {
        "total_services": len(metrics["services"]),
        "active_services": active_services,
        "has_errors": len(metrics["errors"]) > 0,
    }

    return {"aws_metrics": metrics}
