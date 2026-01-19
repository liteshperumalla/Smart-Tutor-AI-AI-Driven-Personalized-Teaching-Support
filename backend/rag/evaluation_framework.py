"""
RAG Evaluation Framework
Comprehensive evaluation metrics and A/B testing for RAG systems

Metrics included:
- Retrieval metrics: Recall@K, Precision@K, MRR, nDCG@K
- Generation metrics: Faithfulness, Answer Relevance, Context Relevance
- End-to-end metrics: F1, Exact Match, BLEU, ROUGE
- Performance metrics: Latency (P50, P95, P99), Cost per query
"""

import time
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Single evaluation result"""
    query: str
    retrieved_docs: List[str]
    generated_answer: str
    ground_truth_answer: Optional[str] = None
    relevant_doc_ids: Optional[List[str]] = None

    # Retrieval metrics
    recall_at_k: Dict[int, float] = None
    precision_at_k: Dict[int, float] = None
    mrr: Optional[float] = None
    ndcg_at_k: Dict[int, float] = None

    # Generation metrics
    faithfulness: Optional[float] = None
    answer_relevance: Optional[float] = None
    context_relevance: Optional[float] = None

    # End-to-end metrics
    f1_score: Optional[float] = None
    exact_match: Optional[float] = None
    bleu_score: Optional[float] = None
    rouge_scores: Optional[Dict[str, float]] = None
    bertscore: Optional[Dict[str, float]] = None

    # Performance metrics
    latency_ms: Optional[float] = None
    retrieval_latency_ms: Optional[float] = None
    generation_latency_ms: Optional[float] = None
    cost: Optional[float] = None

    # Metadata
    timestamp: str = None
    variant: str = "default"  # For A/B testing

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


class RAGEvaluator:
    """
    Comprehensive RAG evaluation framework

    Supports:
    - Multiple evaluation metrics
    - A/B testing between variants
    - Real-time metric tracking
    - Batch evaluation on test sets
    """

    def __init__(
        self,
        output_dir: str = "evaluation_results",
        enable_logging: bool = True
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.enable_logging = enable_logging

        # Storage for results
        self.results: List[EvaluationResult] = []
        self.variant_results: Dict[str, List[EvaluationResult]] = defaultdict(list)

    # ========================================
    # Retrieval Metrics
    # ========================================

    def calculate_recall_at_k(
        self,
        retrieved_doc_ids: List[str],
        relevant_doc_ids: List[str],
        k_values: List[int] = [1, 3, 5, 10]
    ) -> Dict[int, float]:
        """
        Calculate Recall@K

        Recall@K = (Number of relevant docs in top-K) / (Total relevant docs)
        """
        if not relevant_doc_ids:
            return {k: 0.0 for k in k_values}

        recalls = {}
        for k in k_values:
            top_k_docs = set(retrieved_doc_ids[:k])
            relevant_in_top_k = len(top_k_docs.intersection(set(relevant_doc_ids)))
            recalls[k] = relevant_in_top_k / len(relevant_doc_ids)

        return recalls

    def calculate_precision_at_k(
        self,
        retrieved_doc_ids: List[str],
        relevant_doc_ids: List[str],
        k_values: List[int] = [1, 3, 5, 10]
    ) -> Dict[int, float]:
        """
        Calculate Precision@K

        Precision@K = (Number of relevant docs in top-K) / K
        """
        if not relevant_doc_ids:
            return {k: 0.0 for k in k_values}

        precisions = {}
        for k in k_values:
            top_k_docs = set(retrieved_doc_ids[:k])
            relevant_in_top_k = len(top_k_docs.intersection(set(relevant_doc_ids)))
            precisions[k] = relevant_in_top_k / k if k > 0 else 0.0

        return precisions

    def calculate_mrr(
        self,
        retrieved_doc_ids: List[str],
        relevant_doc_ids: List[str]
    ) -> float:
        """
        Calculate Mean Reciprocal Rank (MRR)

        MRR = 1 / (rank of first relevant document)
        """
        if not relevant_doc_ids:
            return 0.0

        relevant_set = set(relevant_doc_ids)
        for rank, doc_id in enumerate(retrieved_doc_ids, start=1):
            if doc_id in relevant_set:
                return 1.0 / rank

        return 0.0

    def calculate_ndcg_at_k(
        self,
        retrieved_doc_ids: List[str],
        relevant_doc_ids: List[str],
        relevance_scores: Optional[List[float]] = None,
        k_values: List[int] = [1, 3, 5, 10]
    ) -> Dict[int, float]:
        """
        Calculate Normalized Discounted Cumulative Gain (nDCG@K)

        nDCG@K = DCG@K / IDCG@K
        where DCG@K = sum(rel_i / log2(i+1)) for i in 1..K
        """
        if not relevant_doc_ids:
            return {k: 0.0 for k in k_values}

        # Create relevance mapping (binary or scored)
        if relevance_scores:
            rel_map = dict(zip(relevant_doc_ids, relevance_scores))
        else:
            rel_map = {doc_id: 1.0 for doc_id in relevant_doc_ids}

        def dcg_at_k(doc_ids: List[str], k: int) -> float:
            dcg = 0.0
            for i, doc_id in enumerate(doc_ids[:k], start=1):
                rel = rel_map.get(doc_id, 0.0)
                dcg += rel / np.log2(i + 1)
            return dcg

        ndcgs = {}
        # Ideal ranking (sort by relevance)
        ideal_docs = sorted(relevant_doc_ids, key=lambda x: rel_map.get(x, 0.0), reverse=True)

        for k in k_values:
            dcg = dcg_at_k(retrieved_doc_ids, k)
            idcg = dcg_at_k(ideal_docs, k)
            ndcgs[k] = dcg / idcg if idcg > 0 else 0.0

        return ndcgs

    # ========================================
    # Generation Metrics
    # ========================================

    def calculate_faithfulness(
        self,
        answer: str,
        context: str,
        llm_provider: Optional[Any] = None
    ) -> float:
        """
        Calculate faithfulness (is answer grounded in context?)

        Uses LLM to verify if all claims in answer are supported by context
        Returns score between 0 and 1
        """
        if not llm_provider:
            logger.warning("LLM provider not provided for faithfulness calculation")
            return 0.0

        prompt = f"""
Given the following context and answer, determine if the answer is faithful to the context.
An answer is faithful if all claims made in the answer are supported by the context.

Context: {context}

Answer: {answer}

Is the answer faithful to the context? Respond with:
- FAITHFUL: if all claims are supported
- PARTIALLY_FAITHFUL: if some claims are supported
- NOT_FAITHFUL: if claims contradict or are not in context

Response (one word):"""

        try:
            response = llm_provider.generate(prompt, max_tokens=10)
            response_lower = response.lower()

            if "faithful" in response_lower and "not" not in response_lower and "partial" not in response_lower:
                return 1.0
            elif "partial" in response_lower:
                return 0.5
            else:
                return 0.0
        except Exception as e:
            logger.error(f"Error calculating faithfulness: {e}")
            return 0.0

    def calculate_answer_relevance(
        self,
        query: str,
        answer: str,
        llm_provider: Optional[Any] = None
    ) -> float:
        """
        Calculate answer relevance (does answer address the query?)

        Returns score between 0 and 1
        """
        if not llm_provider:
            logger.warning("LLM provider not provided for answer relevance calculation")
            return 0.0

        prompt = f"""
Given the following query and answer, rate how well the answer addresses the query.

Query: {query}

Answer: {answer}

Rate the relevance on a scale of 1-5:
5 = Perfectly answers the query
4 = Mostly answers the query
3 = Partially answers the query
2 = Barely addresses the query
1 = Does not answer the query

Rating (just the number):"""

        try:
            response = llm_provider.generate(prompt, max_tokens=5)
            # Extract numeric rating
            for char in response:
                if char.isdigit():
                    rating = int(char)
                    return rating / 5.0
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating answer relevance: {e}")
            return 0.0

    def calculate_context_relevance(
        self,
        query: str,
        context: str,
        llm_provider: Optional[Any] = None
    ) -> float:
        """
        Calculate context relevance (is retrieved context relevant to query?)

        Returns score between 0 and 1
        """
        if not llm_provider:
            return 0.5  # Neutral score

        # Simple keyword overlap heuristic as fallback
        query_words = set(query.lower().split())
        context_words = set(context.lower().split())
        overlap = len(query_words.intersection(context_words))

        if len(query_words) == 0:
            return 0.0

        return min(overlap / len(query_words), 1.0)

    # ========================================
    # End-to-End Metrics
    # ========================================

    def calculate_exact_match(
        self,
        predicted: str,
        ground_truth: str
    ) -> float:
        """
        Calculate exact match score

        Returns 1.0 if strings match (after normalization), 0.0 otherwise
        """
        def normalize(text: str) -> str:
            return text.lower().strip()

        return 1.0 if normalize(predicted) == normalize(ground_truth) else 0.0

    def calculate_f1_score(
        self,
        predicted: str,
        ground_truth: str
    ) -> float:
        """
        Calculate token-level F1 score

        F1 = 2 * (precision * recall) / (precision + recall)
        """
        pred_tokens = set(predicted.lower().split())
        gt_tokens = set(ground_truth.lower().split())

        if len(pred_tokens) == 0 or len(gt_tokens) == 0:
            return 0.0

        common = pred_tokens.intersection(gt_tokens)

        precision = len(common) / len(pred_tokens) if pred_tokens else 0.0
        recall = len(common) / len(gt_tokens) if gt_tokens else 0.0

        if precision + recall == 0:
            return 0.0

        return 2 * (precision * recall) / (precision + recall)

    def calculate_bleu(
        self,
        predicted: str,
        ground_truth: str
    ) -> float:
        """
        Calculate BLEU score for translation/generation quality

        BLEU measures n-gram overlap between predicted and reference text.
        Higher scores (closer to 1.0) indicate better quality.

        Returns:
            float: BLEU score between 0 and 1
        """
        try:
            from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction

            smoothie = SmoothingFunction().method4

            reference = [ground_truth.split()]
            hypothesis = predicted.split()

            score = sentence_bleu(
                reference,
                hypothesis,
                smoothing_function=smoothie
            )

            return score

        except ImportError:
            logger.warning("nltk not installed. Install with: pip install nltk")
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating BLEU: {e}")
            return 0.0

    def calculate_rouge(
        self,
        predicted: str,
        ground_truth: str
    ) -> Dict[str, float]:
        """
        Calculate ROUGE scores for summarization quality

        ROUGE measures recall-oriented n-gram overlap.
        Returns ROUGE-1, ROUGE-2, and ROUGE-L scores.

        Returns:
            dict: Dictionary with rouge1, rouge2, rougeL scores
        """
        try:
            from rouge_score import rouge_scorer

            scorer = rouge_scorer.RougeScorer(
                ['rouge1', 'rouge2', 'rougeL'],
                use_stemmer=True
            )

            scores = scorer.score(ground_truth, predicted)

            return {
                'rouge1': scores['rouge1'].fmeasure,
                'rouge2': scores['rouge2'].fmeasure,
                'rougeL': scores['rougeL'].fmeasure
            }

        except ImportError:
            logger.warning("rouge-score not installed. Install with: pip install rouge-score")
            return {'rouge1': 0.0, 'rouge2': 0.0, 'rougeL': 0.0}
        except Exception as e:
            logger.error(f"Error calculating ROUGE: {e}")
            return {'rouge1': 0.0, 'rouge2': 0.0, 'rougeL': 0.0}

    def calculate_bertscore(
        self,
        predicted: str,
        ground_truth: str
    ) -> Dict[str, float]:
        """
        Calculate BERTScore for semantic similarity

        BERTScore uses BERT embeddings to measure semantic similarity
        between predicted and reference text.

        Returns:
            dict: Dictionary with precision, recall, and f1 scores
        """
        try:
            from bert_score import score

            P, R, F1 = score(
                [predicted],
                [ground_truth],
                lang='en',
                verbose=False,
                model_type='microsoft/deberta-xlarge-mnli'
            )

            return {
                'precision': P.mean().item(),
                'recall': R.mean().item(),
                'f1': F1.mean().item()
            }

        except ImportError:
            logger.warning("bert-score not installed. Install with: pip install bert-score")
            return {'precision': 0.0, 'recall': 0.0, 'f1': 0.0}
        except Exception as e:
            logger.error(f"Error calculating BERTScore: {e}")
            return {'precision': 0.0, 'recall': 0.0, 'f1': 0.0}

    # ========================================
    # Evaluation Orchestration
    # ========================================

    def evaluate_single_query(
        self,
        query: str,
        retrieved_doc_ids: List[str],
        generated_answer: str,
        ground_truth_answer: Optional[str] = None,
        relevant_doc_ids: Optional[List[str]] = None,
        context: Optional[str] = None,
        llm_provider: Optional[Any] = None,
        retrieval_latency_ms: Optional[float] = None,
        generation_latency_ms: Optional[float] = None,
        cost: Optional[float] = None,
        variant: str = "default"
    ) -> EvaluationResult:
        """
        Evaluate a single query with all available metrics
        """
        result = EvaluationResult(
            query=query,
            retrieved_docs=retrieved_doc_ids,
            generated_answer=generated_answer,
            ground_truth_answer=ground_truth_answer,
            relevant_doc_ids=relevant_doc_ids,
            variant=variant
        )

        # Calculate retrieval metrics if we have ground truth
        if relevant_doc_ids:
            result.recall_at_k = self.calculate_recall_at_k(retrieved_doc_ids, relevant_doc_ids)
            result.precision_at_k = self.calculate_precision_at_k(retrieved_doc_ids, relevant_doc_ids)
            result.mrr = self.calculate_mrr(retrieved_doc_ids, relevant_doc_ids)
            result.ndcg_at_k = self.calculate_ndcg_at_k(retrieved_doc_ids, relevant_doc_ids)

        # Calculate generation metrics if we have context and LLM
        if context:
            result.faithfulness = self.calculate_faithfulness(generated_answer, context, llm_provider)
            result.answer_relevance = self.calculate_answer_relevance(query, generated_answer, llm_provider)
            result.context_relevance = self.calculate_context_relevance(query, context, llm_provider)

        # Calculate end-to-end metrics if we have ground truth
        if ground_truth_answer:
            result.exact_match = self.calculate_exact_match(generated_answer, ground_truth_answer)
            result.f1_score = self.calculate_f1_score(generated_answer, ground_truth_answer)
            result.bleu_score = self.calculate_bleu(generated_answer, ground_truth_answer)
            result.rouge_scores = self.calculate_rouge(generated_answer, ground_truth_answer)
            result.bertscore = self.calculate_bertscore(generated_answer, ground_truth_answer)

        # Add performance metrics
        result.retrieval_latency_ms = retrieval_latency_ms
        result.generation_latency_ms = generation_latency_ms
        result.latency_ms = (retrieval_latency_ms or 0) + (generation_latency_ms or 0)
        result.cost = cost

        # Store result
        self.results.append(result)
        self.variant_results[variant].append(result)

        # Log to file if enabled
        if self.enable_logging:
            self._log_result(result)

        return result

    def evaluate_batch(
        self,
        test_cases: List[Dict[str, Any]],
        rag_pipeline: Any,
        variant: str = "default"
    ) -> List[EvaluationResult]:
        """
        Evaluate a batch of test cases

        Each test case should have:
        - query: str
        - ground_truth_answer: Optional[str]
        - relevant_doc_ids: Optional[List[str]]
        """
        results = []

        for i, test_case in enumerate(test_cases):
            logger.info(f"Evaluating test case {i+1}/{len(test_cases)}")

            query = test_case["query"]

            # Run RAG pipeline and measure latency
            start_time = time.time()

            # This is a placeholder - you'll need to adapt to your actual RAG pipeline
            try:
                rag_result = rag_pipeline.run(query)

                latency_ms = (time.time() - start_time) * 1000

                result = self.evaluate_single_query(
                    query=query,
                    retrieved_doc_ids=rag_result.get("retrieved_doc_ids", []),
                    generated_answer=rag_result.get("answer", ""),
                    ground_truth_answer=test_case.get("ground_truth_answer"),
                    relevant_doc_ids=test_case.get("relevant_doc_ids"),
                    context=rag_result.get("context"),
                    llm_provider=rag_pipeline.llm_provider,
                    retrieval_latency_ms=rag_result.get("retrieval_latency_ms"),
                    generation_latency_ms=rag_result.get("generation_latency_ms"),
                    cost=rag_result.get("cost"),
                    variant=variant
                )

                results.append(result)
            except Exception as e:
                logger.error(f"Error evaluating test case {i+1}: {e}")

        return results

    # ========================================
    # Aggregation & Reporting
    # ========================================

    def aggregate_metrics(
        self,
        variant: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Aggregate metrics across all evaluated queries
        """
        # Select results to aggregate
        if variant:
            results = self.variant_results.get(variant, [])
        else:
            results = self.results

        if not results:
            return {}

        aggregated = {
            "total_queries": len(results),
            "variant": variant or "all"
        }

        # Aggregate retrieval metrics
        for k in [1, 3, 5, 10]:
            recall_values = [r.recall_at_k.get(k, 0) for r in results if r.recall_at_k]
            precision_values = [r.precision_at_k.get(k, 0) for r in results if r.precision_at_k]
            ndcg_values = [r.ndcg_at_k.get(k, 0) for r in results if r.ndcg_at_k]

            if recall_values:
                aggregated[f"avg_recall_at_{k}"] = np.mean(recall_values)
            if precision_values:
                aggregated[f"avg_precision_at_{k}"] = np.mean(precision_values)
            if ndcg_values:
                aggregated[f"avg_ndcg_at_{k}"] = np.mean(ndcg_values)

        mrr_values = [r.mrr for r in results if r.mrr is not None]
        if mrr_values:
            aggregated["avg_mrr"] = np.mean(mrr_values)

        # Aggregate generation metrics
        faithfulness_values = [r.faithfulness for r in results if r.faithfulness is not None]
        if faithfulness_values:
            aggregated["avg_faithfulness"] = np.mean(faithfulness_values)

        answer_relevance_values = [r.answer_relevance for r in results if r.answer_relevance is not None]
        if answer_relevance_values:
            aggregated["avg_answer_relevance"] = np.mean(answer_relevance_values)

        # Aggregate end-to-end metrics
        f1_values = [r.f1_score for r in results if r.f1_score is not None]
        if f1_values:
            aggregated["avg_f1_score"] = np.mean(f1_values)

        exact_match_values = [r.exact_match for r in results if r.exact_match is not None]
        if exact_match_values:
            aggregated["exact_match_rate"] = np.mean(exact_match_values)

        # Aggregate BLEU scores
        bleu_values = [r.bleu_score for r in results if r.bleu_score is not None]
        if bleu_values:
            aggregated["avg_bleu_score"] = np.mean(bleu_values)

        # Aggregate ROUGE scores
        rouge1_values = [r.rouge_scores['rouge1'] for r in results if r.rouge_scores is not None]
        rouge2_values = [r.rouge_scores['rouge2'] for r in results if r.rouge_scores is not None]
        rougeL_values = [r.rouge_scores['rougeL'] for r in results if r.rouge_scores is not None]

        if rouge1_values:
            aggregated["avg_rouge1"] = np.mean(rouge1_values)
        if rouge2_values:
            aggregated["avg_rouge2"] = np.mean(rouge2_values)
        if rougeL_values:
            aggregated["avg_rougeL"] = np.mean(rougeL_values)

        # Aggregate BERTScore
        bertscore_f1_values = [r.bertscore['f1'] for r in results if r.bertscore is not None]
        bertscore_precision_values = [r.bertscore['precision'] for r in results if r.bertscore is not None]
        bertscore_recall_values = [r.bertscore['recall'] for r in results if r.bertscore is not None]

        if bertscore_f1_values:
            aggregated["avg_bertscore_f1"] = np.mean(bertscore_f1_values)
        if bertscore_precision_values:
            aggregated["avg_bertscore_precision"] = np.mean(bertscore_precision_values)
        if bertscore_recall_values:
            aggregated["avg_bertscore_recall"] = np.mean(bertscore_recall_values)

        # Aggregate performance metrics
        latency_values = [r.latency_ms for r in results if r.latency_ms is not None]
        if latency_values:
            aggregated["avg_latency_ms"] = np.mean(latency_values)
            aggregated["p50_latency_ms"] = np.percentile(latency_values, 50)
            aggregated["p95_latency_ms"] = np.percentile(latency_values, 95)
            aggregated["p99_latency_ms"] = np.percentile(latency_values, 99)

        cost_values = [r.cost for r in results if r.cost is not None]
        if cost_values:
            aggregated["avg_cost_per_query"] = np.mean(cost_values)
            aggregated["total_cost"] = np.sum(cost_values)

        return aggregated

    def compare_variants(
        self,
        variant_a: str,
        variant_b: str
    ) -> Dict[str, Any]:
        """
        Compare metrics between two variants (for A/B testing)
        """
        metrics_a = self.aggregate_metrics(variant_a)
        metrics_b = self.aggregate_metrics(variant_b)

        comparison = {
            "variant_a": variant_a,
            "variant_b": variant_b,
            "metrics_a": metrics_a,
            "metrics_b": metrics_b,
            "improvements": {}
        }

        # Calculate improvements for common metrics
        for key in metrics_a:
            if key in metrics_b and isinstance(metrics_a[key], (int, float)):
                if "cost" in key or "latency" in key:
                    # Lower is better
                    improvement = (metrics_a[key] - metrics_b[key]) / metrics_a[key] * 100 if metrics_a[key] != 0 else 0
                else:
                    # Higher is better
                    improvement = (metrics_b[key] - metrics_a[key]) / metrics_a[key] * 100 if metrics_a[key] != 0 else 0

                comparison["improvements"][key] = improvement

        return comparison

    def compare_variants_with_stats(
        self,
        variant_a: str,
        variant_b: str,
        metric_name: str = "f1_score",
        alpha: float = 0.05
    ) -> Dict[str, Any]:
        """
        Compare two variants with statistical significance testing

        Performs:
        - Two-sample t-test for mean comparison
        - Cohen's d for effect size calculation
        - Confidence intervals

        Args:
            variant_a: Name of variant A
            variant_b: Name of variant B
            metric_name: Metric to compare (e.g., 'f1_score', 'bleu_score')
            alpha: Significance level (default 0.05 for 95% confidence)

        Returns:
            dict: Statistical test results including p-value, effect size, winner
        """
        try:
            from scipy import stats

            results_a = self.variant_results[variant_a]
            results_b = self.variant_results[variant_b]

            # Extract metric values
            def get_metric_values(results, metric):
                values = []
                for r in results:
                    value = getattr(r, metric, None)
                    if value is not None:
                        # Handle dict metrics (rouge_scores, bertscore)
                        if isinstance(value, dict):
                            # For rouge/bertscore, use f1 or first value
                            value = value.get('f1', value.get('rouge1', list(value.values())[0]))
                        values.append(value)
                return values

            values_a = get_metric_values(results_a, metric_name)
            values_b = get_metric_values(results_b, metric_name)

            if len(values_a) < 2 or len(values_b) < 2:
                return {
                    "error": "Insufficient data for statistical test",
                    "variant_a_n": len(values_a),
                    "variant_b_n": len(values_b),
                    "minimum_required": 2
                }

            # Calculate descriptive statistics
            mean_a = np.mean(values_a)
            mean_b = np.mean(values_b)
            std_a = np.std(values_a, ddof=1)
            std_b = np.std(values_b, ddof=1)

            # Two-sample t-test (independent samples)
            t_stat, p_value = stats.ttest_ind(values_a, values_b)

            # Cohen's d (effect size)
            pooled_std = np.sqrt(((len(values_a) - 1) * std_a**2 + (len(values_b) - 1) * std_b**2) / (len(values_a) + len(values_b) - 2))
            cohens_d = (mean_b - mean_a) / pooled_std if pooled_std > 0 else 0

            # Confidence intervals (95%)
            ci_a = stats.t.interval(1 - alpha, len(values_a) - 1, loc=mean_a, scale=std_a / np.sqrt(len(values_a)))
            ci_b = stats.t.interval(1 - alpha, len(values_b) - 1, loc=mean_b, scale=std_b / np.sqrt(len(values_b)))

            # Determine winner
            is_significant = p_value < alpha
            if is_significant:
                winner = "B" if mean_b > mean_a else "A"
            else:
                winner = "No significant difference"

            return {
                "metric": metric_name,
                "variant_a": {
                    "name": variant_a,
                    "n": len(values_a),
                    "mean": mean_a,
                    "std": std_a,
                    "ci_lower": ci_a[0],
                    "ci_upper": ci_a[1]
                },
                "variant_b": {
                    "name": variant_b,
                    "n": len(values_b),
                    "mean": mean_b,
                    "std": std_b,
                    "ci_lower": ci_b[0],
                    "ci_upper": ci_b[1]
                },
                "statistical_test": {
                    "t_statistic": t_stat,
                    "p_value": p_value,
                    "alpha": alpha,
                    "statistically_significant": is_significant,
                    "degrees_of_freedom": len(values_a) + len(values_b) - 2
                },
                "effect_size": {
                    "cohens_d": cohens_d,
                    "interpretation": self._interpret_cohens_d(cohens_d),
                    "absolute_difference": mean_b - mean_a,
                    "relative_improvement_pct": ((mean_b - mean_a) / mean_a * 100) if mean_a != 0 else 0
                },
                "conclusion": {
                    "winner": winner,
                    "confidence_level": f"{(1 - alpha) * 100}%",
                    "recommendation": self._get_ab_test_recommendation(
                        is_significant, cohens_d, mean_b > mean_a
                    )
                }
            }

        except ImportError:
            logger.error("scipy not installed. Install with: pip install scipy")
            return {"error": "scipy not installed"}
        except Exception as e:
            logger.error(f"Error in statistical comparison: {e}")
            return {"error": str(e)}

    def _interpret_cohens_d(self, d: float) -> str:
        """
        Interpret Cohen's d effect size

        Cohen's d interpretation:
        - < 0.2: negligible
        - 0.2 - 0.5: small
        - 0.5 - 0.8: medium
        - > 0.8: large
        """
        abs_d = abs(d)
        if abs_d < 0.2:
            return "negligible"
        elif abs_d < 0.5:
            return "small"
        elif abs_d < 0.8:
            return "medium"
        else:
            return "large"

    def _get_ab_test_recommendation(
        self,
        is_significant: bool,
        cohens_d: float,
        b_is_better: bool
    ) -> str:
        """Generate deployment recommendation based on A/B test results"""
        if not is_significant:
            return "No significant difference detected. Keep current variant (A) or conduct longer test."

        effect_size = self._interpret_cohens_d(cohens_d)
        winner = "B" if b_is_better else "A"

        if effect_size == "large":
            return f"✅ STRONG RECOMMENDATION: Deploy variant {winner} - Large, significant improvement detected."
        elif effect_size == "medium":
            return f"✅ RECOMMENDATION: Deploy variant {winner} - Medium, significant improvement detected."
        elif effect_size == "small":
            return f"⚠️ WEAK RECOMMENDATION: Variant {winner} shows small but significant improvement. Consider cost/benefit."
        else:
            return f"⚠️ CAUTION: Variant {winner} is statistically significant but effect size is negligible. Practical impact may be minimal."

    # ========================================
    # Logging & Export
    # ========================================

    def _log_result(self, result: EvaluationResult):
        """Log result to JSONL file"""
        log_file = self.output_dir / f"eval_results_{result.variant}.jsonl"

        with open(log_file, "a") as f:
            f.write(json.dumps(asdict(result)) + "\n")

    def export_results(
        self,
        filename: Optional[str] = None,
        variant: Optional[str] = None
    ):
        """Export results to JSON file"""
        if filename is None:
            filename = f"evaluation_summary_{variant or 'all'}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

        output_file = self.output_dir / filename

        summary = {
            "aggregated_metrics": self.aggregate_metrics(variant),
            "total_results": len(self.results),
            "variants": list(self.variant_results.keys()),
            "timestamp": datetime.utcnow().isoformat()
        }

        with open(output_file, "w") as f:
            json.dumps(summary, f, indent=2)

        logger.info(f"Results exported to {output_file}")
        return output_file


# Convenience function
def create_evaluator(output_dir: str = "evaluation_results") -> RAGEvaluator:
    """Create a RAG evaluator instance"""
    return RAGEvaluator(output_dir=output_dir)
