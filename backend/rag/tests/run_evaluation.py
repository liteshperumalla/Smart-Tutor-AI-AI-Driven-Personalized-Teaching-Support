#!/usr/bin/env python3
"""
Baseline RAG Evaluation Runner

Runs evaluation on test dataset and generates comprehensive metrics report.
"""

import json
import time
import asyncio
from typing import List, Dict, Any
from pathlib import Path
import sys
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.rag.evaluation_framework import RAGEvaluator


class EvaluationRunner:
    """Runs RAG evaluation on test dataset."""

    def __init__(self, test_dataset_path: str):
        """
        Initialize evaluation runner.

        Args:
            test_dataset_path: Path to test dataset JSON file
        """
        self.test_dataset_path = test_dataset_path
        self.evaluator = RAGEvaluator()
        self.results = {}

    def load_test_dataset(self) -> List[Dict[str, Any]]:
        """Load test dataset from JSON file."""
        with open(self.test_dataset_path, 'r') as f:
            dataset = json.load(f)
        return dataset['queries']

    async def run_single_query(self, query_data: Dict[str, Any], rag_pipeline) -> Dict[str, Any]:
        """
        Run a single query through the RAG pipeline and collect metrics.

        Args:
            query_data: Query information from test dataset
            rag_pipeline: RAG pipeline instance

        Returns:
            Dict with results and metrics
        """
        query = query_data['query']
        query_id = query_data['id']

        start_time = time.time()

        try:
            # Run query through RAG pipeline
            result = await rag_pipeline.process_query(query)

            latency = (time.time() - start_time) * 1000  # ms

            # Extract retrieved document IDs
            retrieved_doc_ids = result.get('retrieved_doc_ids', [])
            relevant_doc_ids = query_data.get('relevant_doc_ids', [])

            # Calculate retrieval metrics
            metrics = {
                'query_id': query_id,
                'query': query,
                'latency_ms': latency,
                'retrieved_docs': len(retrieved_doc_ids),
                'relevant_docs': len(relevant_doc_ids)
            }

            # Calculate Recall@K
            for k in [1, 3, 5, 10]:
                recall = self.evaluator.calculate_recall_at_k(
                    retrieved_doc_ids, relevant_doc_ids, k_values=[k]
                )
                metrics[f'recall@{k}'] = recall.get(k, 0.0)

            # Calculate Precision@K
            for k in [1, 3, 5, 10]:
                precision = self.evaluator.calculate_precision_at_k(
                    retrieved_doc_ids, relevant_doc_ids, k_values=[k]
                )
                metrics[f'precision@{k}'] = precision.get(k, 0.0)

            # Calculate MRR
            mrr = self.evaluator.calculate_mrr(retrieved_doc_ids, relevant_doc_ids)
            metrics['mrr'] = mrr

            # If we have relevance scores, calculate nDCG
            if 'relevance_scores' in result:
                ndcg = self.evaluator.calculate_ndcg_at_k(
                    result['relevance_scores'], k=5
                )
                metrics['ndcg@5'] = ndcg

            metrics['success'] = True
            metrics['error'] = None

        except Exception as e:
            metrics = {
                'query_id': query_id,
                'query': query,
                'success': False,
                'error': str(e),
                'latency_ms': (time.time() - start_time) * 1000
            }

        return metrics

    async def run_evaluation(self, rag_pipeline, max_queries: int = None) -> Dict[str, Any]:
        """
        Run evaluation on entire test dataset.

        Args:
            rag_pipeline: RAG pipeline instance to evaluate
            max_queries: Optional limit on number of queries to test

        Returns:
            Dict with aggregated results and metrics
        """
        print("Loading test dataset...")
        queries = self.load_test_dataset()

        if max_queries:
            queries = queries[:max_queries]

        print(f"Running evaluation on {len(queries)} queries...")

        all_metrics = []

        for i, query_data in enumerate(queries):
            if (i + 1) % 10 == 0:
                print(f"Progress: {i + 1}/{len(queries)} queries completed")

            metrics = await self.run_single_query(query_data, rag_pipeline)
            all_metrics.append(metrics)

            # Small delay to avoid overwhelming the system
            await asyncio.sleep(0.1)

        # Aggregate metrics
        results = self.aggregate_metrics(all_metrics)

        return results

    def aggregate_metrics(self, all_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate metrics across all queries."""
        successful_queries = [m for m in all_metrics if m.get('success', False)]
        failed_queries = [m for m in all_metrics if not m.get('success', False)]

        if not successful_queries:
            return {
                'error': 'No successful queries',
                'total_queries': len(all_metrics),
                'failed_queries': len(failed_queries)
            }

        # Calculate average metrics
        metrics_to_aggregate = [
            'recall@1', 'recall@3', 'recall@5', 'recall@10',
            'precision@1', 'precision@3', 'precision@5', 'precision@10',
            'mrr', 'ndcg@5', 'latency_ms'
        ]

        aggregated = {
            'total_queries': len(all_metrics),
            'successful_queries': len(successful_queries),
            'failed_queries': len(failed_queries),
            'success_rate': len(successful_queries) / len(all_metrics),
            'timestamp': datetime.now().isoformat()
        }

        for metric in metrics_to_aggregate:
            values = [m[metric] for m in successful_queries if metric in m]
            if values:
                aggregated[f'{metric}_mean'] = sum(values) / len(values)
                aggregated[f'{metric}_min'] = min(values)
                aggregated[f'{metric}_max'] = max(values)
                aggregated[f'{metric}_p50'] = sorted(values)[len(values) // 2]
                aggregated[f'{metric}_p95'] = sorted(values)[int(len(values) * 0.95)]

        # Group by intent type
        intent_metrics = {}
        for query in successful_queries:
            # Find original query data to get intent
            intent = 'unknown'  # Would need to match with original dataset
            if intent not in intent_metrics:
                intent_metrics[intent] = []
            intent_metrics[intent].append(query)

        aggregated['by_intent'] = {}
        for intent, queries in intent_metrics.items():
            aggregated['by_intent'][intent] = {
                'count': len(queries),
                'recall@3_mean': sum(q.get('recall@3', 0) for q in queries) / len(queries) if queries else 0,
                'precision@3_mean': sum(q.get('precision@3', 0) for q in queries) / len(queries) if queries else 0
            }

        # Calculate cost estimate
        # Assuming: $0.0001 per embedding, $0.0024 per LLM call
        embedding_cost_per_query = 0.0001
        llm_cost_per_query = 0.0024
        total_cost = len(successful_queries) * (embedding_cost_per_query + llm_cost_per_query)

        aggregated['cost_estimate'] = {
            'total_cost_usd': total_cost,
            'cost_per_query_usd': total_cost / len(successful_queries) if successful_queries else 0,
            'cost_per_1k_queries_usd': (total_cost / len(successful_queries)) * 1000 if successful_queries else 0
        }

        return aggregated

    def save_results(self, results: Dict[str, Any], output_path: str):
        """Save evaluation results to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {output_path}")

    def print_summary(self, results: Dict[str, Any]):
        """Print a summary of evaluation results."""
        print("\n" + "="*80)
        print("EVALUATION SUMMARY")
        print("="*80)

        print(f"\nQueries:")
        print(f"  Total: {results['total_queries']}")
        print(f"  Successful: {results['successful_queries']}")
        print(f"  Failed: {results['failed_queries']}")
        print(f"  Success Rate: {results['success_rate']*100:.2f}%")

        print(f"\nRetrieval Quality:")
        print(f"  Recall@3: {results.get('recall@3_mean', 0):.4f}")
        print(f"  Precision@3: {results.get('precision@3_mean', 0):.4f}")
        print(f"  MRR: {results.get('mrr_mean', 0):.4f}")
        if 'ndcg@5_mean' in results:
            print(f"  nDCG@5: {results['ndcg@5_mean']:.4f}")

        print(f"\nPerformance:")
        print(f"  Latency P50: {results.get('latency_ms_p50', 0):.2f} ms")
        print(f"  Latency P95: {results.get('latency_ms_p95', 0):.2f} ms")
        print(f"  Latency Mean: {results.get('latency_ms_mean', 0):.2f} ms")

        if 'cost_estimate' in results:
            print(f"\nCost Estimate:")
            print(f"  Total: ${results['cost_estimate']['total_cost_usd']:.4f}")
            print(f"  Per Query: ${results['cost_estimate']['cost_per_query_usd']:.6f}")
            print(f"  Per 1K Queries: ${results['cost_estimate']['cost_per_1k_queries_usd']:.4f}")

        print("\n" + "="*80 + "\n")


# Mock RAG Pipeline for demonstration
class MockRAGPipeline:
    """Mock RAG pipeline for testing the evaluation runner."""

    async def process_query(self, query: str) -> Dict[str, Any]:
        """Mock query processing."""
        import random

        # Simulate processing time
        await asyncio.sleep(random.uniform(0.1, 0.5))

        # Mock retrieved documents
        mock_doc_ids = [
            f"doc_{i:03d}" for i in range(1, random.randint(5, 15))
        ]

        return {
            'answer': f"Mock answer for: {query}",
            'retrieved_doc_ids': mock_doc_ids,
            'relevance_scores': [random.random() for _ in mock_doc_ids],
            'sources': ['mock_source.pdf']
        }


async def main():
    """Main evaluation entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Run RAG evaluation')
    parser.add_argument(
        '--dataset',
        default='test_dataset.json',
        help='Path to test dataset JSON file'
    )
    parser.add_argument(
        '--output',
        default='evaluation_results.json',
        help='Path to save results'
    )
    parser.add_argument(
        '--max-queries',
        type=int,
        default=None,
        help='Maximum number of queries to evaluate'
    )
    parser.add_argument(
        '--mock',
        action='store_true',
        help='Use mock RAG pipeline for testing'
    )

    args = parser.parse_args()

    # Initialize evaluation runner
    runner = EvaluationRunner(args.dataset)

    # Initialize RAG pipeline
    if args.mock:
        print("Using mock RAG pipeline for testing...")
        rag_pipeline = MockRAGPipeline()
    else:
        print("Loading production RAG pipeline...")
        # Import and initialize actual RAG pipeline
        # from backend.rag.pipeline import RAGPipeline
        # rag_pipeline = RAGPipeline()
        print("ERROR: Production pipeline not yet implemented. Use --mock flag.")
        return

    # Run evaluation
    results = await runner.run_evaluation(rag_pipeline, max_queries=args.max_queries)

    # Print summary
    runner.print_summary(results)

    # Save results
    runner.save_results(results, args.output)

    print(f"\nEvaluation complete! Results saved to {args.output}")


if __name__ == '__main__':
    asyncio.run(main())
