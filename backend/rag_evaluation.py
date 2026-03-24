"""
RAG Evaluation Framework - Phase 1
Tracks and logs RAG pipeline metrics for continuous improvement
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RAGEvaluationMetrics:
    """Collects and tracks RAG pipeline metrics"""

    def __init__(self, log_file: str = "logs/rag_evaluation.jsonl"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _append_record(self, metrics_record: Dict[str, Any]) -> None:
        """Persist one metrics record to the JSONL log."""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(metrics_record, ensure_ascii=False) + "\n")

    def log_runtime_metrics(
        self,
        *,
        query: str,
        response: str,
        retrieval_time: float,
        generation_time: float,
        metadata: Optional[Dict[str, Any]] = None,
        quality_metrics: Optional[Dict[str, Any]] = None,
        num_retrieved: int = 0,
        avg_relevance_score: Optional[float] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        context_passages: Optional[List[str]] = None,
    ) -> None:
        """Log a query when the caller already has raw runtime metrics."""
        try:
            metrics_record = {
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "response": response[:2000],
                "context_passages": (context_passages or [])[:5],
                "retrieval_metrics": {
                    "num_retrieved": num_retrieved,
                    "avg_relevance_score": round(avg_relevance_score, 4)
                    if avg_relevance_score is not None
                    else None,
                    "retrieval_time_seconds": round(retrieval_time, 3),
                    "min_score": round(min_score, 4) if min_score is not None else None,
                    "max_score": round(max_score, 4) if max_score is not None else None,
                },
                "generation_metrics": {
                    "generation_time_seconds": round(generation_time, 3),
                    "response_length_chars": len(response),
                    "response_length_words": len(response.split()),
                },
                "end_to_end_metrics": {
                    "total_time_seconds": round(retrieval_time + generation_time, 3),
                },
                "quality_metrics": quality_metrics,
                "metadata": metadata or {},
            }

            self._append_record(metrics_record)
            logger.info(
                "Logged runtime metrics: %s docs, %.2fs total",
                num_retrieved,
                retrieval_time + generation_time,
            )
        except Exception as e:
            logger.error(f"Failed to log runtime metrics: {e}")

    def log_query(
        self,
        query: str,
        retrieved_docs: List[Any],
        response: str,
        retrieval_time: float,
        generation_time: float,
        metadata: Optional[Dict[str, Any]] = None,
        quality_metrics: Optional[Dict[str, Any]] = None,
    ):
        """
        Log a complete query execution with metrics

        Args:
            query: The user query
            retrieved_docs: List of retrieved documents/nodes
            response: Generated response
            retrieval_time: Time taken for retrieval (seconds)
            generation_time: Time taken for response generation (seconds)
            metadata: Additional metadata (mode, web_search_used, etc.)
            quality_metrics: Optional LLM-as-judge quality scores
                (faithfulness, answer_relevance, context_recall, etc.)
        """
        try:
            # Calculate retrieval metrics
            num_retrieved = len(retrieved_docs)
            avg_score = sum(
                getattr(doc, 'score', 0) for doc in retrieved_docs
            ) / max(num_retrieved, 1)

            # Extract context passages for batch quality evaluation later
            context_passages = []
            for doc in retrieved_docs:
                node = getattr(doc, 'node', None)
                if node:
                    text = ""
                    if hasattr(node, 'get_text'):
                        text = node.get_text()
                    elif hasattr(node, 'text'):
                        text = node.text
                    if text:
                        context_passages.append(text[:500])

            self.log_runtime_metrics(
                query=query,
                response=response,
                retrieval_time=retrieval_time,
                generation_time=generation_time,
                metadata=metadata,
                quality_metrics=quality_metrics,
                num_retrieved=num_retrieved,
                avg_relevance_score=avg_score,
                min_score=min(
                    (getattr(doc, "score", 0) for doc in retrieved_docs), default=0
                ),
                max_score=max(
                    (getattr(doc, "score", 0) for doc in retrieved_docs), default=0
                ),
                context_passages=context_passages,
            )

        except Exception as e:
            logger.error(f"Failed to log metrics: {e}")

    def log_retrieval_only(
        self,
        query: str,
        retrieved_docs: List[Any],
        retrieval_time: float,
        query_expansion_used: bool = False,
        num_query_variations: int = 1
    ):
        """
        Log retrieval metrics only (without generation)
        Useful for isolated retrieval testing
        """
        try:
            num_retrieved = len(retrieved_docs)
            avg_score = sum(
                getattr(doc, 'score', 0) for doc in retrieved_docs
            ) / max(num_retrieved, 1)

            metrics_record = {
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "type": "retrieval_only",
                "retrieval_metrics": {
                    "num_retrieved": num_retrieved,
                    "avg_relevance_score": round(avg_score, 4),
                    "retrieval_time_seconds": round(retrieval_time, 3),
                    "query_expansion_used": query_expansion_used,
                    "num_query_variations": num_query_variations,
                    "scores": [round(getattr(doc, 'score', 0), 4) for doc in retrieved_docs]
                }
            }

            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(metrics_record, ensure_ascii=False) + '\n')

        except Exception as e:
            logger.error(f"Failed to log retrieval metrics: {e}")

    def get_summary_stats(self, last_n: int = 100) -> Dict[str, Any]:
        """
        Get summary statistics from the last N queries

        Returns:
            Dictionary with summary statistics
        """
        try:
            if not self.log_file.exists():
                return {"error": "No metrics logged yet"}

            records = []
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            # Take last N records
            records = records[-last_n:]

            if not records:
                return {"error": "No valid records found"}

            # Calculate summary statistics
            total_queries = len(records)

            def safe_metric(value: Any) -> float:
                try:
                    if value is None:
                        return 0.0
                    return float(value)
                except (TypeError, ValueError):
                    return 0.0

            avg_retrieval_time = sum(
                safe_metric(r.get('retrieval_metrics', {}).get('retrieval_time_seconds', 0))
                for r in records
            ) / total_queries

            avg_generation_time = sum(
                safe_metric(r.get('generation_metrics', {}).get('generation_time_seconds', 0))
                for r in records
            ) / total_queries

            avg_num_retrieved = sum(
                safe_metric(r.get('retrieval_metrics', {}).get('num_retrieved', 0))
                for r in records
            ) / total_queries

            avg_relevance_score = sum(
                safe_metric(r.get('retrieval_metrics', {}).get('avg_relevance_score', 0))
                for r in records
            ) / total_queries

            return {
                "total_queries_analyzed": total_queries,
                "avg_retrieval_time_seconds": round(avg_retrieval_time, 3),
                "avg_generation_time_seconds": round(avg_generation_time, 3),
                "avg_total_time_seconds": round(avg_retrieval_time + avg_generation_time, 3),
                "avg_num_retrieved": round(avg_num_retrieved, 2),
                "avg_relevance_score": round(avg_relevance_score, 4),
            }

        except Exception as e:
            logger.error(f"Failed to calculate summary stats: {e}")
            return {"error": str(e)}

    def clear_logs(self):
        """Clear all logged metrics"""
        try:
            if self.log_file.exists():
                self.log_file.unlink()
                logger.info(f"Cleared metrics log: {self.log_file}")
        except Exception as e:
            logger.error(f"Failed to clear logs: {e}")


class RAGEvaluationContext:
    """Context manager for timing RAG operations"""

    def __init__(self, operation_name: str = "operation"):
        self.operation_name = operation_name
        self.start_time = None
        self.elapsed_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed_time = time.time() - self.start_time
        logger.debug(f"{self.operation_name} took {self.elapsed_time:.3f} seconds")
        return False

    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds"""
        return self.elapsed_time if self.elapsed_time is not None else 0.0


# Global evaluator instance
_evaluator = None


def get_evaluator(log_file: Optional[str] = None) -> RAGEvaluationMetrics:
    """Get or create global evaluator instance"""
    global _evaluator
    if _evaluator is None:
        try:
            from backend.config import config
            log_file = log_file or config.EVALUATION_LOG_FILE
        except:
            log_file = log_file or "logs/rag_evaluation.jsonl"
        _evaluator = RAGEvaluationMetrics(log_file)
    return _evaluator


# Example usage:
if __name__ == "__main__":
    # Example: Log a query
    evaluator = RAGEvaluationMetrics("logs/test_evaluation.jsonl")

    # Simulate a query execution
    from types import SimpleNamespace

    mock_docs = [
        SimpleNamespace(score=0.85, node_id="doc1"),
        SimpleNamespace(score=0.72, node_id="doc2"),
        SimpleNamespace(score=0.68, node_id="doc3"),
    ]

    evaluator.log_query(
        query="What is Python?",
        retrieved_docs=mock_docs,
        response="Python is a high-level programming language...",
        retrieval_time=0.123,
        generation_time=1.456,
        metadata={"mode": "chat", "web_search_used": False}
    )

    # Get summary stats
    stats = evaluator.get_summary_stats(last_n=10)
    print("\nSummary Statistics:")
    print(json.dumps(stats, indent=2))
