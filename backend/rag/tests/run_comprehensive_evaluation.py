#!/usr/bin/env python3
"""
Comprehensive RAG Evaluation Runner

This script runs a full evaluation of the RAG system using the test dataset,
calculating all available metrics (retrieval, generation, end-to-end, performance).

Usage:
    python run_comprehensive_evaluation.py --variant production
    python run_comprehensive_evaluation.py --variant production --test-file custom_tests.jsonl
    python run_comprehensive_evaluation.py --compare variant_a variant_b
"""

import json
import logging
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag.evaluation_framework import RAGEvaluator, create_evaluator
from llm_provider import LLMFactory
from logger import get_logger

logger = get_logger(__name__)


class RAGEvaluationRunner:
    """
    Orchestrates comprehensive RAG evaluation
    """

    def __init__(
        self,
        test_dataset_path: str = "backend/rag/tests/test_dataset.jsonl",
        output_dir: str = "evaluation_results"
    ):
        """
        Initialize evaluation runner

        Args:
            test_dataset_path: Path to JSONL test dataset
            output_dir: Directory for evaluation results
        """
        self.test_dataset_path = Path(test_dataset_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize evaluator
        self.evaluator = create_evaluator(str(self.output_dir))

        # Initialize LLM for LLM-as-Judge metrics
        try:
            self.llm_provider = LLMFactory.create_llm()
            logger.info("✓ LLM provider initialized for faithfulness evaluation")
        except Exception as e:
            logger.warning(f"Could not initialize LLM provider: {e}")
            logger.warning("LLM-as-Judge metrics will be skipped")
            self.llm_provider = None

    def load_test_dataset(self) -> List[Dict[str, Any]]:
        """
        Load test cases from JSONL file

        Returns:
            list: Test cases
        """
        if not self.test_dataset_path.exists():
            raise FileNotFoundError(f"Test dataset not found: {self.test_dataset_path}")

        test_cases = []
        with open(self.test_dataset_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    test_case = json.loads(line.strip())
                    test_cases.append(test_case)
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing line {line_num}: {e}")

        logger.info(f"✓ Loaded {len(test_cases)} test cases from {self.test_dataset_path}")
        return test_cases

    def run_evaluation(
        self,
        variant: str = "default",
        limit: int = None
    ) -> Dict[str, Any]:
        """
        Run evaluation on test dataset

        Args:
            variant: Variant name for A/B testing
            limit: Limit number of test cases (for quick testing)

        Returns:
            dict: Aggregated evaluation results
        """
        logger.info(f"🚀 Starting evaluation for variant: {variant}")

        # Load test cases
        test_cases = self.load_test_dataset()

        if limit:
            test_cases = test_cases[:limit]
            logger.info(f"⚠️  Limited to {limit} test cases for quick evaluation")

        # TODO: Initialize your RAG pipeline here
        # For now, we'll use a mock RAG pipeline
        # Replace this with your actual RAG implementation
        from rag.service import RAGService

        try:
            rag_service = RAGService()
            logger.info("✓ RAG service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            logger.warning("Using mock RAG pipeline for demonstration")
            rag_service = MockRAGPipeline()

        # Run evaluation on each test case
        results = []
        for i, test_case in enumerate(test_cases, 1):
            logger.info(f"Evaluating test case {i}/{len(test_cases)}: {test_case['query'][:50]}...")

            try:
                # Get RAG response
                response = rag_service.query(test_case['query'])

                # Evaluate
                result = self.evaluator.evaluate_single_query(
                    query=test_case['query'],
                    retrieved_doc_ids=response.get('retrieved_doc_ids', []),
                    generated_answer=response.get('answer', ''),
                    ground_truth_answer=test_case.get('ground_truth_answer'),
                    context=response.get('context'),
                    llm_provider=self.llm_provider,
                    retrieval_latency_ms=response.get('retrieval_latency_ms'),
                    generation_latency_ms=response.get('generation_latency_ms'),
                    cost=response.get('cost'),
                    variant=variant
                )

                results.append(result)

            except Exception as e:
                logger.error(f"Error evaluating test case {i}: {e}")
                continue

        # Aggregate metrics
        aggregated = self.evaluator.aggregate_metrics(variant)

        logger.info(f"✅ Evaluation complete for variant: {variant}")

        return aggregated

    def compare_variants(
        self,
        variant_a: str,
        variant_b: str,
        metric: str = "f1_score"
    ) -> Dict[str, Any]:
        """
        Compare two variants with statistical testing

        Args:
            variant_a: First variant name
            variant_b: Second variant name
            metric: Metric to compare

        Returns:
            dict: Statistical comparison results
        """
        logger.info(f"📊 Comparing {variant_a} vs {variant_b} on metric: {metric}")

        # Run basic comparison
        basic_comparison = self.evaluator.compare_variants(variant_a, variant_b)

        # Run statistical comparison
        stats_comparison = self.evaluator.compare_variants_with_stats(
            variant_a, variant_b, metric
        )

        # Combine results
        comparison = {
            "basic_comparison": basic_comparison,
            "statistical_analysis": stats_comparison,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Save comparison report
        report_file = self.output_dir / f"comparison_{variant_a}_vs_{variant_b}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(comparison, f, indent=2)

        logger.info(f"✓ Comparison report saved to: {report_file}")

        return comparison

    def print_results(self, results: Dict[str, Any], variant: str):
        """
        Print formatted evaluation results

        Args:
            results: Aggregated evaluation results
            variant: Variant name
        """
        print("\n" + "=" * 80)
        print(f" EVALUATION RESULTS - Variant: {variant}")
        print("=" * 80 + "\n")

        # Retrieval Metrics
        print("📚 RETRIEVAL METRICS")
        print("-" * 80)
        for k in [1, 3, 5, 10]:
            if f"avg_recall_at_{k}" in results:
                print(f"  Recall@{k}:     {results[f'avg_recall_at_{k}']:.4f}")
        for k in [1, 3, 5, 10]:
            if f"avg_precision_at_{k}" in results:
                print(f"  Precision@{k}:  {results[f'avg_precision_at_{k}']:.4f}")
        if "avg_mrr" in results:
            print(f"  MRR:            {results['avg_mrr']:.4f}")
        for k in [1, 3, 5, 10]:
            if f"avg_ndcg_at_{k}" in results:
                print(f"  nDCG@{k}:       {results[f'avg_ndcg_at_{k}']:.4f}")

        # Generation Metrics
        print("\n✨ GENERATION METRICS")
        print("-" * 80)
        if "avg_faithfulness" in results:
            print(f"  Faithfulness:       {results['avg_faithfulness']:.4f}")
        if "avg_answer_relevance" in results:
            print(f"  Answer Relevance:   {results['avg_answer_relevance']:.4f}")

        # End-to-End Metrics
        print("\n🎯 END-TO-END METRICS")
        print("-" * 80)
        if "avg_f1_score" in results:
            print(f"  F1 Score:           {results['avg_f1_score']:.4f}")
        if "exact_match_rate" in results:
            print(f"  Exact Match Rate:   {results['exact_match_rate']:.4f}")
        if "avg_bleu_score" in results:
            print(f"  BLEU Score:         {results['avg_bleu_score']:.4f}")
        if "avg_rouge1" in results:
            print(f"  ROUGE-1:            {results['avg_rouge1']:.4f}")
        if "avg_rouge2" in results:
            print(f"  ROUGE-2:            {results['avg_rouge2']:.4f}")
        if "avg_rougeL" in results:
            print(f"  ROUGE-L:            {results['avg_rougeL']:.4f}")
        if "avg_bertscore_f1" in results:
            print(f"  BERTScore F1:       {results['avg_bertscore_f1']:.4f}")

        # Performance Metrics
        print("\n⚡ PERFORMANCE METRICS")
        print("-" * 80)
        if "avg_latency_ms" in results:
            print(f"  Average Latency:    {results['avg_latency_ms']:.2f} ms")
        if "p50_latency_ms" in results:
            print(f"  P50 Latency:        {results['p50_latency_ms']:.2f} ms")
        if "p95_latency_ms" in results:
            print(f"  P95 Latency:        {results['p95_latency_ms']:.2f} ms")
        if "p99_latency_ms" in results:
            print(f"  P99 Latency:        {results['p99_latency_ms']:.2f} ms")
        if "avg_cost_per_query" in results:
            print(f"  Avg Cost/Query:     ${results['avg_cost_per_query']:.4f}")
        if "total_cost" in results:
            print(f"  Total Cost:         ${results['total_cost']:.2f}")

        print("\n" + "=" * 80 + "\n")


class MockRAGPipeline:
    """
    Mock RAG pipeline for testing
    Replace with your actual RAG implementation
    """

    def query(self, query: str) -> Dict[str, Any]:
        """Mock query method"""
        return {
            "answer": "This is a mock answer for testing the evaluation framework.",
            "context": "Mock context from retrieved documents.",
            "retrieved_doc_ids": ["doc1", "doc2", "doc3"],
            "retrieval_latency_ms": 50.0,
            "generation_latency_ms": 150.0,
            "cost": 0.001
        }


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Run RAG evaluation")
    parser.add_argument(
        "--variant",
        type=str,
        default="default",
        help="Variant name for evaluation"
    )
    parser.add_argument(
        "--test-file",
        type=str,
        default="backend/rag/tests/test_dataset.jsonl",
        help="Path to test dataset"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of test cases (for quick testing)"
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("VARIANT_A", "VARIANT_B"),
        help="Compare two variants (requires running both first)"
    )
    parser.add_argument(
        "--metric",
        type=str,
        default="f1_score",
        help="Metric to use for statistical comparison"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="evaluation_results",
        help="Output directory for results"
    )

    args = parser.parse_args()

    # Initialize runner
    runner = RAGEvaluationRunner(
        test_dataset_path=args.test_file,
        output_dir=args.output_dir
    )

    # Run evaluation or comparison
    if args.compare:
        # Compare two variants
        variant_a, variant_b = args.compare
        comparison = runner.compare_variants(variant_a, variant_b, args.metric)

        # Print statistical results
        if "statistical_analysis" in comparison:
            stats = comparison["statistical_analysis"]
            print("\n📊 STATISTICAL COMPARISON")
            print("=" * 80)
            print(f"Metric: {stats.get('metric')}")
            print(f"\nVariant A ({stats['variant_a']['name']}):")
            print(f"  Mean:  {stats['variant_a']['mean']:.4f}")
            print(f"  Std:   {stats['variant_a']['std']:.4f}")
            print(f"  95% CI: [{stats['variant_a']['ci_lower']:.4f}, {stats['variant_a']['ci_upper']:.4f}]")
            print(f"\nVariant B ({stats['variant_b']['name']}):")
            print(f"  Mean:  {stats['variant_b']['mean']:.4f}")
            print(f"  Std:   {stats['variant_b']['std']:.4f}")
            print(f"  95% CI: [{stats['variant_b']['ci_lower']:.4f}, {stats['variant_b']['ci_upper']:.4f}]")
            print(f"\nStatistical Test:")
            print(f"  t-statistic: {stats['statistical_test']['t_statistic']:.4f}")
            print(f"  p-value:     {stats['statistical_test']['p_value']:.4f}")
            print(f"  Significant: {stats['statistical_test']['statistically_significant']}")
            print(f"\nEffect Size:")
            print(f"  Cohen's d:        {stats['effect_size']['cohens_d']:.4f}")
            print(f"  Interpretation:   {stats['effect_size']['interpretation']}")
            print(f"  Improvement:      {stats['effect_size']['relative_improvement_pct']:.2f}%")
            print(f"\nConclusion:")
            print(f"  Winner: {stats['conclusion']['winner']}")
            print(f"  Recommendation: {stats['conclusion']['recommendation']}")
            print("=" * 80 + "\n")

    else:
        # Run evaluation
        results = runner.run_evaluation(args.variant, args.limit)
        runner.print_results(results, args.variant)


if __name__ == "__main__":
    main()
