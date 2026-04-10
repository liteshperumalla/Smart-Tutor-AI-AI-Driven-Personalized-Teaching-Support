import json
from datetime import datetime, timezone

from backend.api.routes.evaluation import (
    _build_drift_summary,
    _load_dataset_entries,
    _load_dataset_questions,
    _model_keywords,
    _pricing_document_matches_model,
    _run_dataset_quality,
    _resolve_dataset_quality_file,
    get_metrics_history,
)
from backend.config import config
from backend.scripts.run_scheduled_evaluation import run_scheduled_evaluation


def test_resolve_dataset_quality_file_prefers_configured_path(monkeypatch, tmp_path):
    dataset_file = tmp_path / "custom-eval.jsonl"
    dataset_file.write_text('{"instruction":"What is RAG?"}\n', encoding="utf-8")

    monkeypatch.setattr(config, "EVALUATION_DATASET_FILE", str(dataset_file))

    assert _resolve_dataset_quality_file() == dataset_file


def test_load_dataset_questions_supports_jsonl_instruction_and_query(tmp_path):
    dataset_file = tmp_path / "evaluation.jsonl"
    dataset_file.write_text(
        '\n'.join(
            [
                json.dumps({"instruction": "Explain embeddings"}),
                json.dumps({"query": "What is a vector database?"}),
                json.dumps({"instruction": ""}),
            ]
        ),
        encoding="utf-8",
    )

    assert _load_dataset_questions(dataset_file) == [
        "Explain embeddings",
        "What is a vector database?",
    ]


def test_load_dataset_questions_supports_json_test_cases(tmp_path):
    dataset_file = tmp_path / "evaluation.json"
    dataset_file.write_text(
        json.dumps(
            {
                "test_cases": [
                    {"query": "Summarize transformers"},
                    {"instruction": "Define chunking"},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert _load_dataset_questions(dataset_file) == [
        "Summarize transformers",
        "Define chunking",
    ]


def test_load_dataset_entries_extracts_reference_answers(tmp_path):
    dataset_file = tmp_path / "evaluation.json"
    dataset_file.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "query": "What is machine learning?",
                        "ground_truth_answer": "A field of AI focused on learning from data.",
                    },
                    {
                        "instruction": "Define chunking",
                        "output": "Chunking splits documents into smaller pieces.",
                        "input": "Some source context",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    assert _load_dataset_entries(dataset_file) == [
        {
            "question": "What is machine learning?",
            "reference_answer": "A field of AI focused on learning from data.",
            "source_input": "",
        },
        {
            "question": "Define chunking",
            "reference_answer": "Chunking splits documents into smaller pieces.",
            "source_input": "Some source context",
        },
    ]


def test_build_drift_summary_reports_average_and_thresholds():
    summary = _build_drift_summary(
        [
            {"drift_score": 1.2},
            {"drift_score": 2.4},
            {"drift_score": 3.0},
        ],
        enabled=True,
    )

    assert summary["enabled"] is True
    assert summary["scored_count"] == 3
    assert summary["avg_drift_score"] == 2.2
    assert summary["max_drift_score"] == 3.0
    assert summary["high_drift_count"] == 2
    assert summary["high_drift_percentage"] == 66.7


def test_model_keywords_include_human_readable_bedrock_aliases():
    old_llama_keywords = _model_keywords("meta.llama3-70b-instruct-v1:0")
    new_llama_keywords = _model_keywords("us.meta.llama3-1-70b-instruct-v1:0")
    titan_keywords = _model_keywords("amazon.titan-embed-text-v2:0")

    assert "meta llama 3 70b instruct" in old_llama_keywords
    assert "meta llama 3 1 70b instruct" in new_llama_keywords
    assert "amazon titan text embeddings v2" in titan_keywords


def test_pricing_document_matches_bedrock_model_aliases():
    llama_document = {
        "product": {
            "attributes": {
                "group": "Meta Llama 3 70B Instruct",
                "operation": "InvokeModel",
            }
        }
    }
    titan_document = {
        "product": {
            "attributes": {
                "group": "Amazon Titan Text Embeddings V2",
                "operation": "InvokeModel",
            }
        }
    }

    assert _pricing_document_matches_model(
        llama_document, "meta.llama3-70b-instruct-v1:0"
    ) is True
    assert _pricing_document_matches_model(
        titan_document, "amazon.titan-embed-text-v2:0"
    ) is True


def test_metrics_history_ignores_nullable_log_fields(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    first_ts = now.replace(minute=0, second=0, microsecond=0)
    second_ts = first_ts.replace(minute=15)
    log_file = tmp_path / "metrics.jsonl"
    log_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": first_ts.isoformat(),
                        "retrieval_metrics": {
                            "retrieval_time_seconds": None,
                            "avg_relevance_score": None,
                            "num_retrieved": None,
                        },
                        "generation_metrics": {"generation_time_seconds": 1.2},
                        "end_to_end_metrics": {"total_time_seconds": None},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": second_ts.isoformat(),
                        "retrieval_metrics": {
                            "retrieval_time_seconds": 0.4,
                            "avg_relevance_score": 0.9,
                            "num_retrieved": 3,
                        },
                        "generation_metrics": {"generation_time_seconds": None},
                        "end_to_end_metrics": {"total_time_seconds": 1.0},
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(config, "EVALUATION_LOG_FILE", str(log_file))

    payload = get_metrics_history(hours=24, granularity="hour", session=("admin", {}))
    history = payload["history"]

    assert history["status"] == "ok"
    assert history["total_queries"] == 2
    assert len(history["data_points"]) == 1
    assert history["data_points"][0]["query_count"] == 2
    assert history["data_points"][0]["avg_latency"] == 1.1
    assert history["data_points"][0]["avg_relevance"] == 0.45
    assert history["data_points"][0]["avg_docs_retrieved"] == 1.5


def test_run_dataset_quality_returns_structured_error_on_init_failure(
    monkeypatch, tmp_path
):
    import backend.s3_retriever as s3_retriever

    dataset_file = tmp_path / "evaluation.jsonl"
    dataset_file.write_text(
        json.dumps({"instruction": "Explain retrieval-augmented generation"}) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(config, "EVALUATION_DATASET_FILE", str(dataset_file))

    def broken_retriever(*args, **kwargs):
        raise RuntimeError("bedrock init failed")

    monkeypatch.setattr(s3_retriever, "create_s3_retriever", broken_retriever)

    result = _run_dataset_quality(limit=1, model_id=None)

    assert result["total_evaluated"] == 0
    assert result["total_dataset_questions"] == 1
    assert result["quality_summary"] is None
    assert result["error"] == "initialization_failed"
    assert "bedrock init failed" in result["message"]


def test_run_scheduled_evaluation_wraps_result_and_record(monkeypatch):
    expected_result = {"total_evaluated": 2, "quality_summary": {"avg_correctness": 0.8}}
    expected_record = {"id": "run-123"}

    monkeypatch.setattr(
        "backend.scripts.run_scheduled_evaluation._run_dataset_quality",
        lambda limit, model_id: {**expected_result, "limit": limit, "model_id": model_id},
    )
    monkeypatch.setattr(
        "backend.scripts.run_scheduled_evaluation._store_dataset_run",
        lambda result, limit, model_id, source: {
            **expected_record,
            "source": source,
            "limit": limit,
            "model_id": model_id,
            "result_total": result["total_evaluated"],
        },
    )

    payload = run_scheduled_evaluation(limit=5, model_id="model-x", source="scheduled")

    assert payload["total_evaluated"] == 2
    assert payload["run_record"]["id"] == "run-123"
    assert payload["run_record"]["source"] == "scheduled"
    assert payload["run_record"]["limit"] == 5
    assert payload["run_record"]["model_id"] == "model-x"
