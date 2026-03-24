import json

from backend.config import config
from backend.rag_evaluation import RAGEvaluationMetrics
from backend.services.admin_service import AdminService


def test_log_runtime_metrics_persists_real_chat_record(tmp_path):
    log_file = tmp_path / "rag_metrics.jsonl"
    evaluator = RAGEvaluationMetrics(str(log_file))

    evaluator.log_runtime_metrics(
        query="What is RAG?",
        response="RAG combines retrieval with generation.",
        retrieval_time=0.125,
        generation_time=1.375,
        metadata={
            "mode": "chat",
            "agent": "standard_rag",
            "user_id": "alice",
            "query_type": "rag",
        },
        num_retrieved=3,
        avg_relevance_score=0.82,
        min_score=0.71,
        max_score=0.92,
        context_passages=["passage one", "passage two"],
    )

    payload = json.loads(log_file.read_text(encoding="utf-8").strip())
    assert payload["query"] == "What is RAG?"
    assert payload["metadata"]["agent"] == "standard_rag"
    assert payload["retrieval_metrics"]["num_retrieved"] == 3
    assert payload["retrieval_metrics"]["avg_relevance_score"] == 0.82
    assert payload["generation_metrics"]["response_length_words"] > 0


def test_agent_metrics_fallback_uses_runtime_logs(monkeypatch, tmp_path):
    log_file = tmp_path / "rag_metrics.jsonl"
    monkeypatch.setattr(config, "EVALUATION_LOG_FILE", str(log_file))

    evaluator = RAGEvaluationMetrics(str(log_file))
    evaluator.log_runtime_metrics(
        query="Explain embeddings",
        response="Embeddings map text to vectors.",
        retrieval_time=0.2,
        generation_time=1.0,
        metadata={
            "mode": "chat",
            "agent": "standard_rag",
            "user_id": "alice",
            "query_type": "rag",
            "sentiment": "positive",
        },
        num_retrieved=2,
    )
    evaluator.log_runtime_metrics(
        query="Summarize transformers",
        response="Transformers use attention.",
        retrieval_time=0.3,
        generation_time=1.4,
        metadata={
            "mode": "agent_chat",
            "agent": "tutor_agent",
            "user_id": "bob",
            "query_type": "general_tutoring",
            "sentiment": "negative",
        },
        num_retrieved=4,
    )

    import backend.agents.neo4j_client as neo4j_client

    def raise_neo4j_error():
        raise RuntimeError("neo4j unavailable")

    monkeypatch.setattr(neo4j_client, "get_neo4j_client", raise_neo4j_error)

    metrics = AdminService().get_agent_metrics()

    assert metrics["source"] == "runtime_logs"
    assert metrics["total_agent_interactions"] == 2
    assert metrics["unique_users"] == 2
    assert metrics["agent_distribution"]["standard_rag"] == 1
    assert metrics["agent_distribution"]["tutor_agent"] == 1
    assert metrics["routing_accuracy"]["positive_after_route"] == 50.0
    assert metrics["routing_accuracy"]["negative_after_route"] == 50.0


def test_agent_metrics_handles_null_feedback_aggregates(monkeypatch):
    class StubNeo4jClient:
        def execute_read(self, query: str):
            if "COUNT(ai) AS total" in query:
                return [{"total": 2, "unique_users": 2, "avg_rt": 840.5}]
            if "RETURN ai.agent AS agent, COUNT(*) AS cnt" in query:
                return [{"agent": "tutor_agent", "cnt": 2}]
            if "avg(ai.response_time_ms) AS avg_rt" in query:
                return [{"agent": "tutor_agent", "avg_rt": 840.5}]
            if "COUNT(DISTINCT s.username) AS unique_users" in query:
                return [{"date": "2026-03-23", "count": 2, "unique_users": 2}]
            if "COALESCE(ai.query_type, 'unknown')" in query:
                return [{"type": "general_tutoring", "count": 2}]
            if "SUM(CASE WHEN ai.sentiment = 'positive'" in query:
                return [{"pos": None, "neg": None}]
            return []

    import backend.agents.neo4j_client as neo4j_client

    monkeypatch.setattr(neo4j_client, "get_neo4j_client", lambda: StubNeo4jClient())

    metrics = AdminService().get_agent_metrics()

    assert metrics["total_agent_interactions"] == 2
    assert metrics["unique_users"] == 2
    assert metrics["avg_response_time_ms"] == 840
    assert metrics["routing_accuracy"]["positive_after_route"] == 0
    assert metrics["routing_accuracy"]["negative_after_route"] == 0


def test_summary_stats_ignore_nullable_metric_values(tmp_path):
    log_file = tmp_path / "rag_metrics.jsonl"
    log_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "retrieval_metrics": {
                            "retrieval_time_seconds": None,
                            "num_retrieved": None,
                            "avg_relevance_score": None,
                        },
                        "generation_metrics": {"generation_time_seconds": 1.5},
                    }
                ),
                json.dumps(
                    {
                        "retrieval_metrics": {
                            "retrieval_time_seconds": 0.5,
                            "num_retrieved": 4,
                            "avg_relevance_score": 0.8,
                        },
                        "generation_metrics": {"generation_time_seconds": None},
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    summary = RAGEvaluationMetrics(str(log_file)).get_summary_stats(last_n=10)

    assert summary["total_queries_analyzed"] == 2
    assert summary["avg_retrieval_time_seconds"] == 0.25
    assert summary["avg_generation_time_seconds"] == 0.75
    assert summary["avg_num_retrieved"] == 2.0
    assert summary["avg_relevance_score"] == 0.4
