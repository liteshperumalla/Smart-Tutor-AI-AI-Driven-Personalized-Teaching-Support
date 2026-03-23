import json

from backend.api.routes.evaluation import (
    _build_drift_summary,
    _load_dataset_questions,
    _resolve_dataset_quality_file,
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
