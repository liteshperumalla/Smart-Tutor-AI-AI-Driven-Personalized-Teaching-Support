#!/usr/bin/env python3
"""
RAG Pipeline Testing & Benchmarking Tool
Tests Phase 1 & 2 improvements with evaluation dataset
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import statistics

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from backend.rag_evaluation import get_evaluator, RAGEvaluationMetrics
    EVALUATION_AVAILABLE = True
except ImportError:
    EVALUATION_AVAILABLE = False
    print("⚠️ Evaluation framework not available")


class RAGTester:
    """Test RAG pipeline with evaluation dataset"""

    def __init__(self, dataset_path: str = "evaluation_dataset.json"):
        self.dataset_path = dataset_path
        self.results = []
        self.dataset = None
        self.load_dataset()

    def load_dataset(self):
        """Load evaluation dataset"""
        try:
            with open(self.dataset_path, 'r') as f:
                self.dataset = json.load(f)
            print(f"✅ Loaded {len(self.dataset['test_cases'])} test cases")
        except FileNotFoundError:
            print(f"❌ Dataset not found: {self.dataset_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in dataset: {e}")
            sys.exit(1)

    def run_test_query(self, test_case: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single test query"""
        query = test_case['query']
        test_id = test_case['id']

        print(f"\n{'='*60}")
        print(f"Test {test_id}: {query}")
        print(f"Category: {test_case['category']} | Difficulty: {test_case['difficulty']}")
        print(f"{'='*60}")

        start_time = time.time()

        try:
            # Import here to allow for config changes
            from Tutor_chat import (
                RAGQueryEngine,
                load_index_from_storage,
                StorageContext,
                get_response_synthesizer
            )
            from llama_index.retrievers.bm25 import BM25Retriever
            from sentence_transformers import CrossEncoder

            # Load index
            persist_dir = "./persisted_index"
            if not os.path.exists(persist_dir):
                print(f"❌ Index not found at {persist_dir}")
                print("   Please run Data_parsing.py first to create the index")
                return None

            storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
            index = load_index_from_storage(storage_context)

            # Create retrievers
            vector_retriever = index.as_retriever(similarity_top_k=6)
            bm25_retriever = BM25Retriever.from_defaults(
                index=index,
                similarity_top_k=6
            )

            # Create hybrid retriever (simplified for testing)
            retriever = vector_retriever  # Use vector retriever for simplicity

            # Create response synthesizer
            response_synthesizer = get_response_synthesizer(response_mode="compact")

            # Create query engine
            query_engine = RAGQueryEngine(
                retriever=retriever,
                response_synthesizer=response_synthesizer,
                mode="chat"
            )

            # Run query
            response = query_engine.custom_query(query)

            total_time = time.time() - start_time

            # Analyze response
            result = {
                "test_id": test_id,
                "query": query,
                "category": test_case['category'],
                "difficulty": test_case['difficulty'],
                "response": response,
                "response_length": len(response),
                "total_time": round(total_time, 3),
                "expected_topics": test_case['expected_topics'],
                "config": config.copy(),
                "timestamp": datetime.now().isoformat()
            }

            # Check topic coverage
            response_lower = response.lower()
            covered_topics = []
            for topic in test_case['expected_topics']:
                if topic.lower() in response_lower:
                    covered_topics.append(topic)

            result['covered_topics'] = covered_topics
            result['topic_coverage'] = len(covered_topics) / len(test_case['expected_topics'])

            print(f"\n📊 Results:")
            print(f"   Time: {total_time:.2f}s")
            print(f"   Response length: {len(response)} chars")
            print(f"   Topic coverage: {result['topic_coverage']*100:.1f}% ({len(covered_topics)}/{len(test_case['expected_topics'])})")
            print(f"   Covered: {', '.join(covered_topics[:3])}{'...' if len(covered_topics) > 3 else ''}")

            return result

        except Exception as e:
            print(f"❌ Error running test: {e}")
            import traceback
            traceback.print_exc()
            return {
                "test_id": test_id,
                "query": query,
                "error": str(e),
                "config": config.copy()
            }

    def run_all_tests(self, config: Dict[str, Any], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Run all test cases"""
        test_cases = self.dataset['test_cases']
        if limit:
            test_cases = test_cases[:limit]

        print(f"\n🚀 Running {len(test_cases)} test cases...")
        print(f"Configuration: {json.dumps(config, indent=2)}\n")

        results = []
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n[{i}/{len(test_cases)}]", end=" ")
            result = self.run_test_query(test_case, config)
            if result:
                results.append(result)
            time.sleep(0.5)  # Brief pause between tests

        self.results = results
        return results

    def analyze_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze test results and compute metrics"""
        if not results:
            return {"error": "No results to analyze"}

        valid_results = [r for r in results if 'error' not in r]

        if not valid_results:
            return {"error": "No valid results"}

        # Compute metrics
        times = [r['total_time'] for r in valid_results]
        coverages = [r['topic_coverage'] for r in valid_results]
        response_lengths = [r['response_length'] for r in valid_results]

        by_difficulty = {}
        for r in valid_results:
            diff = r['difficulty']
            if diff not in by_difficulty:
                by_difficulty[diff] = []
            by_difficulty[diff].append(r['topic_coverage'])

        by_category = {}
        for r in valid_results:
            cat = r['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(r['topic_coverage'])

        analysis = {
            "total_tests": len(results),
            "successful_tests": len(valid_results),
            "failed_tests": len(results) - len(valid_results),
            "avg_response_time": round(statistics.mean(times), 3),
            "median_response_time": round(statistics.median(times), 3),
            "p95_response_time": round(sorted(times)[int(len(times) * 0.95)], 3) if len(times) > 1 else times[0],
            "avg_topic_coverage": round(statistics.mean(coverages), 3),
            "median_topic_coverage": round(statistics.median(coverages), 3),
            "coverage_above_80": sum(1 for c in coverages if c >= 0.8) / len(coverages),
            "coverage_above_60": sum(1 for c in coverages if c >= 0.6) / len(coverages),
            "avg_response_length": round(statistics.mean(response_lengths), 1),
            "by_difficulty": {
                k: {
                    "avg_coverage": round(statistics.mean(v), 3),
                    "count": len(v)
                }
                for k, v in by_difficulty.items()
            },
            "by_category": {
                k: {
                    "avg_coverage": round(statistics.mean(v), 3),
                    "count": len(v)
                }
                for k, v in sorted(by_category.items(), key=lambda x: statistics.mean(x[1]), reverse=True)[:5]
            }
        }

        return analysis

    def save_results(self, results: List[Dict[str, Any]], analysis: Dict[str, Any], filename: str):
        """Save results to JSON file"""
        output = {
            "timestamp": datetime.now().isoformat(),
            "dataset": self.dataset_path,
            "analysis": analysis,
            "results": results
        }

        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\n💾 Results saved to: {filename}")

    def print_summary(self, analysis: Dict[str, Any]):
        """Print summary of results"""
        print(f"\n{'='*60}")
        print("📊 TEST RESULTS SUMMARY")
        print(f"{'='*60}")

        print(f"\n✅ Test Execution:")
        print(f"   Total tests: {analysis['total_tests']}")
        print(f"   Successful: {analysis['successful_tests']}")
        print(f"   Failed: {analysis['failed_tests']}")

        print(f"\n⏱️  Performance:")
        print(f"   Avg response time: {analysis['avg_response_time']}s")
        print(f"   Median response time: {analysis['median_response_time']}s")
        print(f"   P95 response time: {analysis['p95_response_time']}s")

        print(f"\n🎯 Quality Metrics:")
        print(f"   Avg topic coverage: {analysis['avg_topic_coverage']*100:.1f}%")
        print(f"   Median topic coverage: {analysis['median_topic_coverage']*100:.1f}%")
        print(f"   Coverage ≥80%: {analysis['coverage_above_80']*100:.1f}%")
        print(f"   Coverage ≥60%: {analysis['coverage_above_60']*100:.1f}%")
        print(f"   Avg response length: {analysis['avg_response_length']:.0f} chars")

        print(f"\n📈 By Difficulty:")
        for diff, stats in sorted(analysis['by_difficulty'].items()):
            print(f"   {diff:12} {stats['avg_coverage']*100:5.1f}%  (n={stats['count']})")

        print(f"\n📂 Top Categories by Coverage:")
        for cat, stats in list(analysis['by_category'].items())[:5]:
            print(f"   {cat:20} {stats['avg_coverage']*100:5.1f}%  (n={stats['count']})")

        print(f"\n{'='*60}")


def compare_configurations(dataset_path: str = "evaluation_dataset.json"):
    """Compare different configurations"""
    print("\n🔬 RAG CONFIGURATION COMPARISON")
    print("="*60)

    configs = [
        {
            "name": "Baseline (Phase 1 only)",
            "settings": {
                "QUERY_REWRITING_ENABLED": "false",
                "SELF_RAG_ENABLED": "false",
                "QUERY_EXPANSION_ENABLED": "true"
            }
        },
        {
            "name": "Phase 1 + 2 (All features)",
            "settings": {
                "QUERY_REWRITING_ENABLED": "true",
                "SELF_RAG_ENABLED": "true",
                "QUERY_EXPANSION_ENABLED": "true",
                "CRAG_QUALITY_THRESHOLD": "0.5"
            }
        },
        {
            "name": "Conservative CRAG (threshold=0.7)",
            "settings": {
                "QUERY_REWRITING_ENABLED": "true",
                "SELF_RAG_ENABLED": "true",
                "CRAG_QUALITY_THRESHOLD": "0.7"
            }
        },
        {
            "name": "Aggressive CRAG (threshold=0.3)",
            "settings": {
                "QUERY_REWRITING_ENABLED": "true",
                "SELF_RAG_ENABLED": "true",
                "CRAG_QUALITY_THRESHOLD": "0.3"
            }
        }
    ]

    all_results = []

    for config in configs:
        print(f"\n\n{'='*60}")
        print(f"Testing: {config['name']}")
        print(f"{'='*60}")

        # Set environment variables
        for key, value in config['settings'].items():
            os.environ[key] = value

        # Run tests
        tester = RAGTester(dataset_path)
        results = tester.run_all_tests(config['settings'], limit=5)  # Limit to 5 for quick testing
        analysis = tester.analyze_results(results)

        tester.print_summary(analysis)

        # Save results
        filename = f"test_results_{config['name'].replace(' ', '_').lower()}.json"
        tester.save_results(results, analysis, filename)

        all_results.append({
            "config": config,
            "analysis": analysis
        })

    # Print comparison
    print(f"\n\n{'='*60}")
    print("📊 CONFIGURATION COMPARISON")
    print(f"{'='*60}\n")

    print(f"{'Configuration':<35} {'Avg Time':>10} {'Coverage':>10} {'80%+':>8}")
    print("-" * 65)

    for result in all_results:
        name = result['config']['name']
        analysis = result['analysis']
        print(f"{name:<35} {analysis['avg_response_time']:>9.2f}s {analysis['avg_topic_coverage']*100:>9.1f}% {analysis['coverage_above_80']*100:>7.1f}%")


def main():
    parser = argparse.ArgumentParser(description="RAG Pipeline Testing Tool")
    parser.add_argument(
        '--mode',
        choices=['single', 'compare', 'full'],
        default='single',
        help='Testing mode: single config, compare configs, or full evaluation'
    )
    parser.add_argument(
        '--dataset',
        default='evaluation_dataset.json',
        help='Path to evaluation dataset'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of test cases'
    )
    parser.add_argument(
        '--output',
        default='test_results.json',
        help='Output file for results'
    )

    args = parser.parse_args()

    if args.mode == 'compare':
        compare_configurations(args.dataset)
    else:
        # Single configuration test
        tester = RAGTester(args.dataset)

        # Get current config
        config = {
            "QUERY_REWRITING_ENABLED": os.getenv("QUERY_REWRITING_ENABLED", "true"),
            "SELF_RAG_ENABLED": os.getenv("SELF_RAG_ENABLED", "true"),
            "QUERY_EXPANSION_ENABLED": os.getenv("QUERY_EXPANSION_ENABLED", "true"),
            "CRAG_QUALITY_THRESHOLD": os.getenv("CRAG_QUALITY_THRESHOLD", "0.5")
        }

        # Run tests
        results = tester.run_all_tests(config, limit=args.limit)
        analysis = tester.analyze_results(results)

        # Print summary
        tester.print_summary(analysis)

        # Save results
        tester.save_results(results, analysis, args.output)


if __name__ == "__main__":
    main()
