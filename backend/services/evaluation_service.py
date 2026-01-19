from __future__ import annotations

import json
import math
import re
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import config
from backend.rag_evaluation import RAGEvaluationMetrics, get_evaluator
from backend.s3_retriever import create_s3_retriever


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    pct = min(max(pct, 0.0), 1.0)
    sorted_vals = sorted(values)
    index = int(round(pct * (len(sorted_vals) - 1)))
    return sorted_vals[index]


def _compute_retrieval_metrics(
    documents: List[Dict[str, Any]],
    expected_topics: List[str],
) -> Dict[str, Any]:
    normalized_topics = [topic.lower() for topic in expected_topics]
    expected_topic_count = len(set(normalized_topics))
    doc_hits: List[int] = []
    doc_topic_sets: List[set] = []

    for doc in documents:
        text = (doc.get("text_excerpt") or "").lower()
        hits = {topic for topic in normalized_topics if topic in text}
        doc_topic_sets.append(hits)
        doc_hits.append(1 if hits else 0)

    def precision_at_k(k: int) -> float:
        if not doc_hits:
            return 0.0
        considered = doc_hits[:k]
        denom = min(k, len(doc_hits))
        return sum(considered) / denom if denom else 0.0

    def recall_at_k(k: int) -> float:
        if not normalized_topics:
            return 0.0
        topics_found = set()
        for hits in doc_topic_sets[:k]:
            topics_found.update(hits)
        return len(topics_found) / len(normalized_topics)

    def mean_reciprocal_rank() -> float:
        for idx, hit in enumerate(doc_hits):
            if hit:
                return 1.0 / (idx + 1)
        return 0.0

    def ndcg() -> float:
        if not doc_hits:
            return 0.0
        dcg = 0.0
        for idx, rel in enumerate(doc_hits):
            dcg += (2**rel - 1) / math.log2(idx + 2)
        ideal_hits = sorted(doc_hits, reverse=True)
        idcg = 0.0
        for idx, rel in enumerate(ideal_hits):
            idcg += (2**rel - 1) / math.log2(idx + 2)
        return dcg / idcg if idcg else 0.0

    total_topics_found = set().union(*doc_topic_sets) if doc_topic_sets else set()
    friendly_topics_found = sorted(
        {topic for topic in expected_topics if topic.lower() in total_topics_found}
    )
    missing_topics = [
        topic for topic in expected_topics if topic.lower() not in total_topics_found
    ]

    return {
        "precision_at_3": round(precision_at_k(3), 3),
        "precision_at_5": round(precision_at_k(5), 3),
        "recall_at_3": round(recall_at_k(3), 3),
        "recall_at_5": round(recall_at_k(5), 3),
        "mrr": round(mean_reciprocal_rank(), 3),
        "ndcg": round(ndcg(), 3),
        "topics_found": friendly_topics_found,
        "missing_topics": missing_topics,
        "retrieved_topic_coverage": round(
            len(total_topics_found) / expected_topic_count, 3
        )
        if expected_topic_count
        else 0.0,
        "relevant_doc_ratio": round(sum(doc_hits) / len(doc_hits), 3)
        if doc_hits
        else 0.0,
        "retrieval_success": recall_at_k(3) >= 0.5 or precision_at_k(3) >= 0.5,
    }


def _compute_generation_metrics(
    response_text: str, expected_topics: List[str]
) -> Dict[str, Any]:
    response_lower = response_text.lower()
    normalized_topics = [(topic, topic.lower()) for topic in expected_topics]
    covered_topics = [
        topic for topic, token in normalized_topics if token in response_lower
    ]
    coverage = len(covered_topics) / len(expected_topics) if expected_topics else 0.0

    words = [word for word in response_text.split() if word]
    sentences = [s for s in re.split(r"[.!?]+", response_text) if s.strip()]
    avg_sentence_length = len(words) / max(1, len(sentences))
    clarity_score = max(1.0, min(5.0, round(5.5 - 0.1 * avg_sentence_length, 2)))

    return {
        "topic_coverage": round(coverage, 3),
        "covered_topics": covered_topics,
        "missing_topics": [
            topic for topic, token in normalized_topics if token not in response_lower
        ],
        "relevance_score": round(min(5.0, max(1.0, coverage * 5)), 2),
        "completeness": coverage >= 0.75,
        "hallucination_flag": coverage < 0.6,
        "clarity_score": clarity_score,
        "response_length_chars": len(response_text),
        "response_length_words": len(words),
    }


class EvaluationService:
    def __init__(self) -> None:
        self.dataset_path = Path(config.EVALUATION_DATASET_FILE)
        self.dataset = self._load_dataset()
        self.evaluator: RAGEvaluationMetrics = get_evaluator(config.EVALUATION_LOG_FILE)
        self._index = None

    def _load_dataset(self) -> Dict[str, Any]:
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Evaluation dataset missing: {self.dataset_path}")
        with self.dataset_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {"test_cases": data}
        if not isinstance(data, dict):
            raise ValueError("Evaluation dataset must be a dict or list of test cases")
        if "test_cases" not in data:
            raise ValueError("Evaluation dataset missing 'test_cases'")
        return data

    def _load_index(self):
        if self._index is None:
            # Use S3 retriever instead of local index
            self._index = create_s3_retriever(similarity_top_k=10)
        return self._index

    def list_cases(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        cases = self.dataset.get("test_cases", [])
        data = [
            {
                "id": case.get("id"),
                "query": case.get("query"),
                "category": case.get("category"),
                "difficulty": case.get("difficulty"),
                "expected_topics": case.get("expected_topics", []),
            }
            for case in cases
        ]
        if limit:
            data = data[:limit]
        return data

    def run_tests(
        self,
        limit: Optional[int] = None,
        categories: Optional[List[str]] = None,
        difficulties: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        cases = self.dataset.get("test_cases", [])
        if categories:
            cases = [case for case in cases if case.get("category") in set(categories)]
        if difficulties:
            cases = [
                case for case in cases if case.get("difficulty") in set(difficulties)
            ]
        if limit:
            cases = cases[:limit]

        results = []
        for case in cases:
            result = self._run_single_case(case)
            if result:
                results.append(result)

        analysis = self._analyze_results(results)
        return {"analysis": analysis, "results": results}

    def _run_single_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        query = case.get("query")
        if not query:
            return {}
        expected_topics = case.get("expected_topics") or []
        if not isinstance(expected_topics, list):
            expected_topics = []
        start = time.time()
        top_k = case.get("expected_retrieval_count") or config.SIMILARITY_TOP_K
        # Always use S3 retriever
        retriever = create_s3_retriever(similarity_top_k=top_k)
        retrieved_nodes = retriever.retrieve(query)
        retrieval_time = time.time() - start

        diagnostics = {
            "documents": [
                {
                    "text_excerpt": node.node.get_text()[:400]
                    if hasattr(node.node, "get_text")
                    else "",
                    "metadata": node.node.metadata,
                    "score": getattr(node, "score", 0),
                }
                for node in retrieved_nodes
            ]
        }
        synth = get_response_synthesizer(response_mode="compact")
        gen_start = time.time()
        response_obj = synth.synthesize(query=query, nodes=retrieved_nodes)
        response_text = str(response_obj)
        generation_time = time.time() - gen_start

        retrieval_metrics = _compute_retrieval_metrics(
            diagnostics["documents"], expected_topics
        )
        generation_metrics = _compute_generation_metrics(response_text, expected_topics)
        total_time = retrieval_time + generation_time

        self.evaluator.log_query(
            query=query,
            retrieved_docs=retrieved_nodes,
            response=response_text,
            retrieval_time=retrieval_time,
            generation_time=generation_time,
            metadata={
                "mode": "evaluation",
                "case_id": case["id"],
                "category": case.get("category"),
            },
        )

        return {
            "test_id": case["id"],
            "query": query,
            "category": case.get("category"),
            "difficulty": case.get("difficulty"),
            "response": response_text,
            "response_length": len(response_text),
            "total_time": round(total_time, 3),
            "expected_topics": expected_topics,
            "retrieval_metrics": retrieval_metrics,
            "generation_metrics": generation_metrics,
        }

    def _analyze_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not results:
            return {"error": "No evaluation results"}

        times = [r["total_time"] for r in results]
        coverages = [r["generation_metrics"]["topic_coverage"] for r in results]

        def avg_metric(lst: List[Dict[str, Any]], key: str) -> float:
            values = [
                item.get(key)
                for item in lst
                if key in item and item.get(key) is not None
            ]
            return round(statistics.mean(values), 3) if values else 0.0

        retrieval_metrics = [
            r["retrieval_metrics"] for r in results if r.get("retrieval_metrics")
        ]
        generation_metrics = [
            r["generation_metrics"] for r in results if r.get("generation_metrics")
        ]

        return {
            "total_tests": len(results),
            "avg_response_time": round(statistics.mean(times), 3) if times else 0.0,
            "p95_response_time": round(_percentile(times, 0.95), 3) if times else 0.0,
            "avg_topic_coverage": round(statistics.mean(coverages), 3)
            if coverages
            else 0.0,
            "coverage_above_80": sum(1 for c in coverages if c >= 0.8) / len(coverages)
            if coverages
            else 0.0,
            "coverage_above_60": sum(1 for c in coverages if c >= 0.6) / len(coverages)
            if coverages
            else 0.0,
            "retrieval_summary": {
                "precision_at_3": avg_metric(retrieval_metrics, "precision_at_3"),
                "precision_at_5": avg_metric(retrieval_metrics, "precision_at_5"),
                "recall_at_3": avg_metric(retrieval_metrics, "recall_at_3"),
                "recall_at_5": avg_metric(retrieval_metrics, "recall_at_5"),
                "mrr": avg_metric(retrieval_metrics, "mrr"),
                "ndcg": avg_metric(retrieval_metrics, "ndcg"),
            },
            "generation_summary": {
                "avg_relevance_score": avg_metric(
                    generation_metrics, "relevance_score"
                ),
                "avg_clarity_score": avg_metric(generation_metrics, "clarity_score"),
                "hallucination_rate": sum(
                    1 for m in generation_metrics if m.get("hallucination_flag")
                )
                / len(generation_metrics)
                if generation_metrics
                else 0.0,
            },
        }

    def metrics_log_summary(self) -> Dict[str, Any]:
        return self.evaluator.get_summary_stats(last_n=200)

    def clear_logs(self) -> None:
        self.evaluator.clear_logs()


_evaluation_service: Optional[EvaluationService] = None


def get_evaluation_service() -> EvaluationService:
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = EvaluationService()
    return _evaluation_service
