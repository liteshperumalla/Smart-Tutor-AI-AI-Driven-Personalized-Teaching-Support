from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from backend.api.dependencies import get_current_session
from backend.services.evaluation_service import (
    EvaluationService,
    get_evaluation_service,
)
from backend.cost_tracking import get_cost_tracker
from backend.config import config

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


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
    session=Depends(get_current_session),
    service: EvaluationService = Depends(get_evaluation_service),
):
    return {"cases": service.list_cases(limit)}


@router.post("/run")
def run_evaluations(
    payload: EvaluationRunRequest,
    session=Depends(get_current_session),
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
    session=Depends(get_current_session),
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
        return {"error": str(e)}

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
    session=Depends(get_current_session),
    service: EvaluationService = Depends(get_evaluation_service),
):
    return {"summary": service.metrics_log_summary()}


@router.get("/realtime-metrics")
def get_realtime_rag_metrics(
    last_n: int = Query(default=100, ge=1, le=500),
    session=Depends(get_current_session),
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
        return {"realtime_metrics": {"status": "error", "message": str(e)}}

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

        if ret_metrics.get('retrieval_time_seconds'):
            retrieval_times.append(ret_metrics['retrieval_time_seconds'])
        if gen_metrics.get('generation_time_seconds'):
            generation_times.append(gen_metrics['generation_time_seconds'])
        if e2e_metrics.get('total_time_seconds'):
            total_times.append(e2e_metrics['total_time_seconds'])
        elif ret_metrics.get('retrieval_time_seconds') and gen_metrics.get('generation_time_seconds'):
            total_times.append(ret_metrics['retrieval_time_seconds'] + gen_metrics['generation_time_seconds'])
        if ret_metrics.get('avg_relevance_score'):
            relevance_scores.append(ret_metrics['avg_relevance_score'])
        if ret_metrics.get('num_retrieved'):
            num_retrieved_list.append(ret_metrics['num_retrieved'])
        if gen_metrics.get('response_length_words'):
            response_lengths.append(gen_metrics['response_length_words'])

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
            vals = [r.get(field, 0) for r in recs if r.get(field) is not None]
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
            "retrieval_time": ret_metrics.get('retrieval_time_seconds', 0),
            "generation_time": gen_metrics.get('generation_time_seconds', 0),
            "total_time": e2e_metrics.get('total_time_seconds', 0),
            "relevance_score": ret_metrics.get('avg_relevance_score', 0),
            "docs_retrieved": ret_metrics.get('num_retrieved', 0),
            "response_words": gen_metrics.get('response_length_words', 0),
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
    session=Depends(get_current_session),
    service: EvaluationService = Depends(get_evaluation_service),
):
    service.clear_logs()
    return {"status": "cleared"}


@router.get("/metrics-history")
def get_metrics_history(
    hours: int = Query(default=24, ge=1, le=168),  # 1 hour to 7 days
    granularity: str = Query(default="hour", regex="^(minute|hour|day)$"),
    session=Depends(get_current_session),
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
        return {"history": {"status": "error", "message": str(e), "data_points": []}}

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
        except:
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

        buckets[key]["count"] += 1
        buckets[key]["total_latency"] += e2e_metrics.get('total_time_seconds', 0) or (
            ret_metrics.get('retrieval_time_seconds', 0) + gen_metrics.get('generation_time_seconds', 0)
        )
        buckets[key]["retrieval_latency"] += ret_metrics.get('retrieval_time_seconds', 0)
        buckets[key]["generation_latency"] += gen_metrics.get('generation_time_seconds', 0)
        buckets[key]["relevance_sum"] += ret_metrics.get('avg_relevance_score', 0)
        buckets[key]["docs_retrieved"] += ret_metrics.get('num_retrieved', 0)

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


@router.get("/export")
def export_all_metrics(
    format: str = Query(default="json", regex="^(json|csv)$"),
    session=Depends(get_current_session),
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
    session=Depends(get_current_session),
):
    """
    Get comprehensive AWS service metrics and costs.

    Returns metrics for all AWS services: Bedrock, S3, DynamoDB, etc.
    """
    import boto3
    from botocore.exceptions import ClientError

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

    # 1. BEDROCK METRICS
    try:
        metrics["services"]["bedrock"] = {
            "status": "active",
            "models": {
                "llm": {
                    "model_id": config.BEDROCK_MODEL_ID,
                    "pricing": {
                        "input_per_1k": 0.00099,  # Llama 3.1 70B
                        "output_per_1k": 0.00099,
                    },
                },
                "embedding": {
                    "model_id": config.BEDROCK_EMBEDDING_MODEL_ID,
                    "pricing": {
                        "input_per_1k": 0.0001,  # Titan Embed v2
                    },
                    "dimension": 1024,
                },
            },
            "available_models": [
                {"id": "meta.llama3-1-70b-instruct-v1:0", "name": "Llama 3.1 70B", "type": "llm"},
                {"id": "anthropic.claude-3-5-sonnet-20241022-v2:0", "name": "Claude 3.5 Sonnet", "type": "llm"},
                {"id": "amazon.titan-embed-text-v2:0", "name": "Titan Embed v2", "type": "embedding"},
            ],
        }
    except Exception as e:
        metrics["errors"].append(f"Bedrock: {str(e)}")
        metrics["services"]["bedrock"] = {"status": "error", "error": str(e)}

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
                    "storage_per_gb_month": 0.023,
                    "get_per_1k": 0.0004,
                    "put_per_1k": 0.005,
                },
            }
        except ClientError as e:
            metrics["services"]["s3"] = {
                "status": "limited",
                "bucket": bucket_name,
                "error": str(e),
            }
    except Exception as e:
        metrics["errors"].append(f"S3: {str(e)}")
        metrics["services"]["s3"] = {"status": "error", "error": str(e)}

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
                "billing_mode": table.get("BillingModeSummary", {}).get("BillingMode", "PAY_PER_REQUEST"),
                "table_status": table.get("TableStatus", "UNKNOWN"),
                "pricing": {
                    "read_per_million": 0.25,
                    "write_per_million": 1.25,
                    "storage_per_gb_month": 0.25,
                },
            }
        except ClientError as e:
            metrics["services"]["dynamodb"] = {
                "status": "limited",
                "table_name": table_name,
                "error": str(e),
            }
    except Exception as e:
        metrics["errors"].append(f"DynamoDB: {str(e)}")
        metrics["services"]["dynamodb"] = {"status": "error", "error": str(e)}

    # 4. COST TRACKING
    try:
        tracker = get_cost_tracker()
        daily_costs = tracker.get_daily_costs(date)
        metrics["costs"] = {
            "daily": daily_costs,
            "tracking_enabled": config.ENABLE_COST_TRACKING,
        }
    except Exception as e:
        metrics["errors"].append(f"Cost Tracking: {str(e)}")
        metrics["costs"] = {
            "daily": {
                "date": date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "total_cost_usd": 0,
                "total_tokens": 0,
                "entries": 0,
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
        metrics["errors"].append(f"STS: {str(e)}")
        metrics["services"]["sts"] = {"status": "error", "error": str(e)}

    # 6. CLOUDWATCH METRICS (if available)
    try:
        cloudwatch = boto3.client("cloudwatch", **client_kwargs)

        # Get Bedrock invocation metrics for today
        end_time = datetime.now(timezone.utc)
        start_time = end_time.replace(hour=0, minute=0, second=0, microsecond=0)

        try:
            response = cloudwatch.get_metric_statistics(
                Namespace="AWS/Bedrock",
                MetricName="Invocations",
                Dimensions=[],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=["Sum"],
            )
            datapoints = response.get("Datapoints", [])
            total_invocations = sum(d.get("Sum", 0) for d in datapoints)

            metrics["services"]["cloudwatch"] = {
                "status": "active",
                "bedrock_invocations_today": int(total_invocations),
            }
        except ClientError:
            metrics["services"]["cloudwatch"] = {
                "status": "limited",
                "note": "Metrics may require additional permissions",
            }
    except Exception as e:
        metrics["services"]["cloudwatch"] = {"status": "unavailable"}

    # Summary
    active_services = sum(1 for s in metrics["services"].values() if s.get("status") == "active")
    metrics["summary"] = {
        "total_services": len(metrics["services"]),
        "active_services": active_services,
        "has_errors": len(metrics["errors"]) > 0,
    }

    return {"aws_metrics": metrics}
