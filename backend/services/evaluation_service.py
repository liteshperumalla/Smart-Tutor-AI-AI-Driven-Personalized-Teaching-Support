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
from backend.bedrock_llm import BedrockLLM
from backend.services.rag_quality_evaluator import (
    evaluate_quality,
    compute_context_precision,
)
from backend.retrieval_tuning import (
    build_grounded_answer_prompt,
    build_rag_recommendations,
    determine_retrieval_limit,
    select_diverse_items,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


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


def _semantic_topic_coverage(
    topics: List[str],
    sentences: List[str],
    sim_threshold: float,
) -> Optional[Dict[str, List[str]]]:
    """Cosine-similarity topic coverage using Bedrock Titan embeddings.

    Returns {"covered": [...], "missing": [...]} on success, or None if the
    embedding service is unavailable. Falling back to substring matching is
    handled by the caller — we only handle the success path here so the
    fallback stays a single code path.
    """
    if not topics or not sentences:
        return None
    try:
        from backend.bedrock_embeddings import get_bedrock_embeddings
        import numpy as np
    except ImportError:
        return None

    try:
        embedder = get_bedrock_embeddings()
        topic_vecs = np.array(embedder.embed_documents(list(topics)))
        sent_vecs = np.array(embedder.embed_documents(list(sentences)))
    except Exception as exc:
        # Embedding can fail (Bedrock outage, throttling, malformed input);
        # the caller treats None as "fall back to substring".
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "Semantic topic-coverage embed failed (%s); falling back to substring.", exc
        )
        return None

    # Normalize and compute pairwise cosine similarity.
    def _norm(m: "np.ndarray") -> "np.ndarray":
        n = np.linalg.norm(m, axis=1, keepdims=True)
        n[n == 0] = 1.0
        return m / n

    sims = _norm(topic_vecs) @ _norm(sent_vecs).T  # shape (topics, sentences)
    best_per_topic = sims.max(axis=1)
    covered = [topics[i] for i, s in enumerate(best_per_topic) if s >= sim_threshold]
    missing = [topics[i] for i, s in enumerate(best_per_topic) if s < sim_threshold]
    return {"covered": covered, "missing": missing}


def _compute_generation_metrics(
    response_text: str, expected_topics: List[str]
) -> Dict[str, Any]:
    response_lower = response_text.lower()
    normalized_topics = [(topic, topic.lower()) for topic in expected_topics]
    # Substring metric — kept on the response object even when semantic mode
    # is enabled, so existing dashboards / quality gates don't break.
    substring_covered = [
        topic for topic, token in normalized_topics if token in response_lower
    ]
    substring_coverage = (
        len(substring_covered) / len(expected_topics) if expected_topics else 0.0
    )

    sentences_text = [s.strip() for s in re.split(r"[.!?]+", response_text) if s.strip()]

    # Semantic coverage path — embeds topics + sentences and counts a topic
    # as covered when any sentence has cosine similarity >= threshold.
    # Catches synonyms like "ML" vs "machine learning" that substring misses.
    use_semantic = getattr(config, "EVAL_TOPIC_COVERAGE_MODE", "substring") == "semantic"
    semantic_result = None
    if use_semantic and expected_topics and sentences_text:
        semantic_result = _semantic_topic_coverage(
            expected_topics,
            sentences_text,
            sim_threshold=getattr(config, "EVAL_TOPIC_COVERAGE_SIM_THRESHOLD", 0.55),
        )

    if semantic_result is not None:
        covered_topics = semantic_result["covered"]
        missing_topics = semantic_result["missing"]
        coverage_method = "semantic"
    else:
        covered_topics = substring_covered
        missing_topics = [topic for topic, token in normalized_topics if token not in response_lower]
        coverage_method = "substring"

    coverage = len(covered_topics) / len(expected_topics) if expected_topics else 0.0

    words = [word for word in response_text.split() if word]
    avg_sentence_length = len(words) / max(1, len(sentences_text))
    clarity_score = max(1.0, min(5.0, round(5.5 - 0.1 * avg_sentence_length, 2)))

    return {
        "topic_coverage": round(coverage, 3),
        "topic_coverage_method": coverage_method,
        "topic_coverage_substring": round(substring_coverage, 3),
        "covered_topics": covered_topics,
        "missing_topics": missing_topics,
        "relevance_score": round(min(5.0, max(1.0, coverage * 5)), 2),
        "completeness": coverage >= 0.75,
        "hallucination_flag": coverage < 0.6,
        "clarity_score": clarity_score,
        "response_length_chars": len(response_text),
        "response_length_words": len(words),
    }


class EvaluationService:
    def __init__(self) -> None:
        self.dataset_path = self._resolve_dataset_path()
        self.dataset = self._load_dataset()
        self.evaluator: RAGEvaluationMetrics = get_evaluator(config.EVALUATION_LOG_FILE)
        self._retrievers: Dict[int, Any] = {}

    def _resolve_dataset_path(self) -> Path:
        configured = Path(config.EVALUATION_DATASET_FILE)

        candidates = [configured]
        if not configured.is_absolute():
            candidates.append(REPO_ROOT / configured)

        candidates.extend(
            [
                REPO_ROOT / "Evaluation_files/evaluation_data.jsonl",
                REPO_ROOT / "evaluation_dataset.json",
                REPO_ROOT / "backend/rag/tests/test_dataset.jsonl",
                REPO_ROOT / "backend/rag/tests/test_dataset.json",
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

    def _load_dataset(self) -> Dict[str, Any]:
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Evaluation dataset missing: {self.dataset_path}")

        if self.dataset_path.suffix.lower() == ".jsonl":
            cases: List[Dict[str, Any]] = []
            with self.dataset_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(record, dict):
                        cases.append(record)
            return {"test_cases": cases}

        with self.dataset_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return {"test_cases": data}
        if not isinstance(data, dict):
            raise ValueError("Evaluation dataset must be a dict or list of test cases")
        if isinstance(data.get("test_cases"), list):
            return data
        if isinstance(data.get("queries"), list):
            return {"test_cases": data.get("queries", [])}
        raise ValueError("Evaluation dataset missing 'test_cases' or 'queries'")

    def _load_index(self, similarity_top_k: int):
        similarity_top_k = max(1, similarity_top_k)
        if similarity_top_k not in self._retrievers:
            self._retrievers[similarity_top_k] = create_s3_retriever(
                similarity_top_k=similarity_top_k
            )
        return self._retrievers[similarity_top_k]

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
        enable_quality_eval: bool = False,
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
            result = self._run_single_case(case, enable_quality_eval=enable_quality_eval)
            if result:
                results.append(result)

        analysis = self._analyze_results(results)
        return {"analysis": analysis, "results": results}

    def _run_single_case(
        self, case: Dict[str, Any], enable_quality_eval: bool = False
    ) -> Dict[str, Any]:
        query = case.get("query")
        if not query:
            return {}
        expected_topics = case.get("expected_topics") or []
        if not isinstance(expected_topics, list):
            expected_topics = []
        start = time.time()
        top_k = determine_retrieval_limit(
            query,
            base_top_k=max(3, config.SIMILARITY_TOP_K),
            max_top_k=max(6, config.SIMILARITY_TOP_K + 2),
        )
        retriever = self._load_index(max(top_k, config.SIMILARITY_TOP_K))
        retrieved_nodes = retriever.retrieve(query)
        selected_nodes = select_diverse_items(
            retrieved_nodes,
            query=query,
            limit=top_k,
            max_per_source=2,
        )
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
                for node in selected_nodes
            ]
        }

        gen_start = time.time()
        llm = BedrockLLM()

        context_passages = [
            node.node.get_text() if hasattr(node.node, "get_text") else ""
            for node in selected_nodes[:5]
        ]
        prompt = build_grounded_answer_prompt(query, context_passages)
        response_text = llm.generate(prompt=prompt, max_tokens=512)
        generation_time = time.time() - gen_start

        retrieval_metrics = _compute_retrieval_metrics(
            diagnostics["documents"], expected_topics
        )
        generation_metrics = _compute_generation_metrics(response_text, expected_topics)
        total_time = retrieval_time + generation_time

        # LLM-as-judge quality evaluation (optional, on-demand)
        quality_metrics = None
        if enable_quality_eval:
            try:
                retrieval_scores = [
                    n.node.metadata.get("similarity_score", getattr(n, "score", 0))
                    for n in selected_nodes
                ]
                quality_metrics = evaluate_quality(
                    question=query,
                    context_passages=context_passages,
                    answer=response_text,
                )
                quality_metrics["context_precision"] = compute_context_precision(
                    retrieval_scores
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"Quality evaluation failed for case {case.get('id')}: {e}"
                )

        self.evaluator.log_query(
            query=query,
            retrieved_docs=selected_nodes,
            response=response_text,
            retrieval_time=retrieval_time,
            generation_time=generation_time,
            metadata={
                "mode": "evaluation",
                "case_id": case["id"],
                "category": case.get("category"),
                "retrieval_limit": top_k,
            },
            quality_metrics=quality_metrics,
        )

        result = {
            "test_id": case["id"],
            "query": query,
            "category": case.get("category"),
            "difficulty": case.get("difficulty"),
            "response": response_text,
            "response_length": len(response_text),
            "total_time": round(total_time, 3),
            "expected_topics": expected_topics,
            "retrieval_limit": top_k,
            "selected_sources": [
                doc["metadata"].get("source_file", "unknown")
                for doc in diagnostics["documents"]
            ],
            "retrieval_metrics": retrieval_metrics,
            "generation_metrics": generation_metrics,
        }
        if quality_metrics:
            result["quality_metrics"] = quality_metrics
        return result

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

        analysis = {
            "total_tests": len(results),
            "avg_response_time": round(statistics.mean(times), 3) if times else 0.0,
            "p95_response_time": round(_percentile(times, 0.95), 3) if times else 0.0,
            "avg_retrieval_limit": round(
                statistics.mean(
                    [r.get("retrieval_limit", config.SIMILARITY_TOP_K) for r in results]
                ),
                3,
            ),
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
            "weakest_cases": [
                {
                    "test_id": r.get("test_id"),
                    "query": r.get("query"),
                    "topic_coverage": r.get("generation_metrics", {}).get("topic_coverage", 0),
                    "context_recall": r.get("quality_metrics", {}).get("context_recall")
                    if r.get("quality_metrics")
                    else None,
                }
                for r in sorted(
                    results,
                    key=lambda item: (
                        item.get("quality_metrics", {}).get("correctness", 0)
                        if item.get("quality_metrics")
                        else item.get("generation_metrics", {}).get("topic_coverage", 0)
                    ),
                )[:5]
            ],
        }

        # Aggregate quality metrics if present
        quality_results = [
            r["quality_metrics"]
            for r in results
            if r.get("quality_metrics") and isinstance(r["quality_metrics"], dict)
        ]
        if quality_results:
            analysis["quality_summary"] = {
                "avg_faithfulness": avg_metric(quality_results, "faithfulness"),
                "avg_answer_relevance": avg_metric(quality_results, "answer_relevance"),
                "avg_context_recall": avg_metric(quality_results, "context_recall"),
                "avg_context_precision": avg_metric(quality_results, "context_precision"),
                "avg_correctness": avg_metric(quality_results, "correctness"),
                "evaluated_count": len(quality_results),
            }

        quality_summary = analysis.get("quality_summary") or {}
        analysis["recommendations"] = build_rag_recommendations(
            avg_context_recall=quality_summary.get("avg_context_recall"),
            avg_context_precision=quality_summary.get("avg_context_precision"),
            avg_correctness=quality_summary.get("avg_correctness"),
            avg_topic_coverage=analysis.get("avg_topic_coverage"),
            p95_response_time=analysis.get("p95_response_time"),
        )

        return analysis

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
