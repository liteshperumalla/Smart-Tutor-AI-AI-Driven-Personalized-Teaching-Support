import json
from datetime import datetime, timezone

from backend.api.routes.evaluation import (
    _build_drift_summary,
    _load_dataset_questions,
    _model_keywords,
    _pricing_document_matches_model,
    _resolve_dataset_quality_file,
    get_metrics_history,
)
from backend.config import config


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
