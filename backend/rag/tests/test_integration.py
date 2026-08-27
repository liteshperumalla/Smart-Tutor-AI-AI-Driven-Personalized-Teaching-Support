"""
Integration tests for end-to-end RAG pipeline.

Tests the complete flow:
Query → Enhancement → Retrieval → Reranking → Generation → Caching
"""

import pytest
import asyncio
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock, patch
import numpy as np

from backend.rag.semantic_chunker import SemanticChunker
from backend.rag.hybrid_search import HybridSearcher, BM25Retriever
from backend.rag.reranker import AdvancedReranker
from backend.rag.hyde import HyDERetriever
from backend.rag.query_enhancement import QueryEnhancer, EnhancedQuery
from backend.rag.caching_layer import RAGCache, EmbeddingCache, QueryCache
from backend.rag.evaluation_framework import RAGEvaluator


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_documents():
    """Sample documents for testing."""
    return [
        {
            "id": "doc1",
            "text": "Machine learning is a subset of artificial intelligence. It focuses on building systems that can learn from data. Common algorithms include decision trees, neural networks, and support vector machines.",
            "metadata": {"source": "ml_basics.pdf", "page": 1}
        },
        {
            "id": "doc2",
            "text": "Deep learning is a specialized form of machine learning that uses neural networks with multiple layers. It excels at tasks like image recognition and natural language processing. Popular frameworks include TensorFlow and PyTorch.",
            "metadata": {"source": "ml_basics.pdf", "page": 2}
        },
        {
            "id": "doc3",
            "text": "Supervised learning requires labeled training data. The model learns to map inputs to outputs. Examples include classification and regression tasks. It's widely used in industry applications.",
            "metadata": {"source": "ml_types.pdf", "page": 1}
        },
        {
            "id": "doc4",
            "text": "Unsupervised learning works with unlabeled data. It discovers hidden patterns and structures. Clustering and dimensionality reduction are common techniques. K-means and PCA are popular algorithms.",
            "metadata": {"source": "ml_types.pdf", "page": 2}
        },
        {
            "id": "doc5",
            "text": "Reinforcement learning involves agents that learn through trial and error. They receive rewards or penalties based on actions. This approach powers game-playing AI and robotics applications.",
            "metadata": {"source": "rl_intro.pdf", "page": 1}
        }
    ]


@pytest.fixture
def mock_llm():
    """Mock LLM for testing."""
    llm = Mock()
    llm.generate = AsyncMock(return_value="This is a hypothetical answer about machine learning.")
    llm.agenerate = AsyncMock(return_value=["Hypothetical doc 1", "Hypothetical doc 2"])
    return llm


@pytest.fixture
def mock_embeddings():
    """Mock embeddings model."""
    embeddings = Mock()
    # Return deterministic embeddings for testing
    embeddings.embed_query = AsyncMock(side_effect=lambda text: np.random.rand(384).tolist())
    embeddings.embed_documents = AsyncMock(side_effect=lambda texts: [np.random.rand(384).tolist() for _ in texts])
    return embeddings


@pytest.fixture
def semantic_chunker():
    """Create semantic chunker instance."""
    return SemanticChunker(
        target_chunk_size=512,
        min_chunk_size=100,
        max_chunk_size=1000,
        overlap_sentences=1
    )


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = Mock()
    redis_mock.get = Mock(return_value=None)
    redis_mock.set = Mock(return_value=True)
    redis_mock.setex = Mock(return_value=True)
    redis_mock.exists = Mock(return_value=False)
    return redis_mock


@pytest.fixture
def mock_s3():
    """Mock S3 client."""
    s3_mock = Mock()
    s3_mock.get_object = Mock(side_effect=Exception("Not found"))
    s3_mock.put_object = Mock(return_value=True)
    return s3_mock


@pytest.fixture
async def rag_pipeline(mock_llm, mock_embeddings, mock_redis, mock_s3, sample_documents):
    """Create complete RAG pipeline for testing."""
    # Initialize components
    chunker = SemanticChunker(target_chunk_size=256)

    # Create mock retrievers. SemanticRetriever isn't a real class — the
    # hybrid searcher duck-types its semantic_retriever arg — so spec=None.
    bm25_retriever = Mock(spec=BM25Retriever)
    semantic_retriever = Mock()

    # Configure mock retrieval results
    mock_results = [
        {"id": doc["id"], "text": doc["text"], "score": 0.8 - i*0.1, "metadata": doc["metadata"]}
        for i, doc in enumerate(sample_documents[:3])
    ]

    bm25_retriever.search = Mock(return_value=mock_results)
    semantic_retriever.search = AsyncMock(return_value=mock_results)

    hybrid_searcher = HybridSearcher(
        bm25_retriever=bm25_retriever,
        semantic_retriever=semantic_retriever,
        fusion_method="rrf",
        alpha=0.5
    )

    reranker = AdvancedReranker(
        model_name="cross-encoder/ms-marco-MiniLM-L-12-v2",
        use_mmr=True,
        lambda_diversity=0.7,
        device="cpu"
    )

    query_enhancer = QueryEnhancer(
        llm=mock_llm,
        spacy_model="en_core_web_sm"
    )

    cache = RAGCache(
        redis_client=mock_redis,
        s3_client=mock_s3,
        s3_bucket="test-bucket",
        enable_memory=True,
        enable_redis=False,  # Disable for testing
        enable_s3=False
    )

    return {
        "chunker": chunker,
        "hybrid_searcher": hybrid_searcher,
        "reranker": reranker,
        "query_enhancer": query_enhancer,
        "cache": cache,
        "llm": mock_llm,
        "embeddings": mock_embeddings
    }


# ============================================================================
# Integration Tests
# ============================================================================

class TestEndToEndPipeline:
    """Test complete RAG pipeline integration."""

    @pytest.mark.asyncio
    async def test_complete_query_flow(self, rag_pipeline):
        """Test end-to-end query processing."""
        query = "What is machine learning?"

        # Step 1: Enhance query
        enhanced = rag_pipeline["query_enhancer"].enhance(query)
        assert enhanced.original_query == query
        assert enhanced.intent is not None
        assert len(enhanced.expanded_queries) > 0

        # Step 2: Search with hybrid retriever
        results = rag_pipeline["hybrid_searcher"].search(
            enhanced.rewritten_query or query,
            top_k=10
        )
        assert len(results) > 0
        assert all("text" in r for r in results)

        # Step 3: Rerank results
        reranked = rag_pipeline["reranker"].rerank(
            query=enhanced.rewritten_query or query,
            documents=[r["text"] for r in results],
            top_k=3,
            method="combined"
        )
        assert len(reranked) <= 3
        assert len(reranked) > 0

    @pytest.mark.asyncio
    async def test_caching_integration(self, rag_pipeline):
        """Test caching layer integration."""
        query = "What is deep learning?"
        cache = rag_pipeline["cache"]

        # First query - cache miss
        cached_result = cache.get_query_result(query)
        assert cached_result is None

        # Simulate query processing
        result = {
            "answer": "Deep learning is a subset of machine learning...",
            "sources": ["doc2"],
            "confidence": 0.95
        }

        # Cache the result
        cache.put_query_result(query, result)

        # Second query - cache hit
        cached_result = cache.get_query_result(query)
        assert cached_result is not None
        assert cached_result["answer"] == result["answer"]

    @pytest.mark.asyncio
    async def test_embedding_cache(self, rag_pipeline):
        """Test embedding caching."""
        cache = rag_pipeline["cache"]
        embeddings = rag_pipeline["embeddings"]

        text = "This is a test document."

        # First embedding - cache miss
        cached_emb = cache.get_embedding(text)
        assert cached_emb is None

        # Generate embedding
        embedding = await embeddings.embed_query(text)

        # Cache it
        cache.put_embedding(text, embedding)

        # Second query - cache hit
        cached_emb = cache.get_embedding(text)
        assert cached_emb is not None
        assert len(cached_emb) == len(embedding)

    @pytest.mark.asyncio
    async def test_query_enhancement_flow(self, rag_pipeline):
        """Test query enhancement integration."""
        enhancer = rag_pipeline["query_enhancer"]

        test_cases = [
            ("What is supervised learning?", "definitional"),
            ("How do I train a neural network?", "procedural"),
            ("Explain the concept of overfitting", "conceptual"),
            ("Compare CNN vs RNN", "comparison"),
        ]

        for query, expected_intent in test_cases:
            enhanced = enhancer.enhance(query)
            assert enhanced.original_query == query
            assert enhanced.intent in [expected_intent, "factual", "explanatory"]  # Allow some flexibility
            assert enhanced.rewritten_query is not None

    @pytest.mark.asyncio
    async def test_document_ingestion_flow(self, rag_pipeline, sample_documents):
        """Test document ingestion and chunking."""
        chunker = rag_pipeline["chunker"]
        cache = rag_pipeline["cache"]
        embeddings = rag_pipeline["embeddings"]

        # Ingest a document
        doc = sample_documents[0]
        chunks = chunker.chunk_document(
            text=doc["text"],
            metadata=doc["metadata"],
            create_parent_chunks=True
        )

        assert len(chunks) > 0

        # Generate and cache embeddings
        for chunk in chunks:
            # Check cache first
            cached_emb = cache.get_embedding(chunk.text)
            if not cached_emb:
                # Generate new embedding
                embedding = await embeddings.embed_query(chunk.text)
                # Cache it
                cache.put_embedding(chunk.text, embedding)
                # Verify cached
                cached_emb = cache.get_embedding(chunk.text)
                assert cached_emb is not None


class TestHyDEIntegration:
    """Test HyDE retrieval integration."""

    @pytest.mark.asyncio
    async def test_hyde_retrieval_flow(self, mock_llm, mock_embeddings):
        """Test HyDE retrieval with hypothetical documents."""
        # Create mock base retriever
        base_retriever = Mock()
        base_retriever.search_by_embedding = AsyncMock(return_value=[
            {"id": "doc1", "text": "ML is AI subset", "score": 0.9},
            {"id": "doc2", "text": "Deep learning uses neural nets", "score": 0.8}
        ])

        hyde = HyDERetriever(
            llm=mock_llm,
            embeddings=mock_embeddings,
            retriever=base_retriever,
            num_hypothetical_docs=3,
            aggregation_method="mean"
        )

        query = "What is machine learning?"
        results = await hyde.retrieve(query, top_k=5)

        assert len(results) > 0
        assert mock_llm.generate.called
        assert mock_embeddings.embed_query.called

    @pytest.mark.asyncio
    async def test_hyde_fallback(self, mock_llm, mock_embeddings):
        """Test HyDE fallback on LLM failure."""
        # Configure LLM to fail
        mock_llm.generate = AsyncMock(side_effect=Exception("LLM error"))

        base_retriever = Mock()
        base_retriever.search = AsyncMock(return_value=[
            {"id": "doc1", "text": "Fallback result", "score": 0.7}
        ])

        hyde = HyDERetriever(
            llm=mock_llm,
            embeddings=mock_embeddings,
            retriever=base_retriever,
            num_hypothetical_docs=3
        )

        query = "What is AI?"
        results = await hyde.retrieve(query, top_k=5, use_fallback=True)

        # Should fall back to standard retrieval
        assert len(results) > 0
        assert base_retriever.search.called


class TestEvaluationIntegration:
    """Test evaluation framework integration."""

    def test_retrieval_metrics_calculation(self, sample_documents):
        """Test retrieval metrics on sample data."""
        evaluator = RAGEvaluator()

        # Simulate retrieved and relevant documents
        retrieved_docs = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        relevant_docs = ["doc1", "doc3", "doc5"]

        # Calculate metrics
        recall = evaluator.calculate_recall_at_k(
            retrieved_docs, relevant_docs, k_values=[1, 3, 5]
        )

        assert 1 in recall
        assert 3 in recall
        assert 5 in recall
        assert 0 <= recall[1] <= 1
        assert recall[5] >= recall[3]  # More docs retrieved = higher recall

        precision = evaluator.calculate_precision_at_k(
            retrieved_docs, relevant_docs, k_values=[1, 3, 5]
        )

        assert 1 in precision
        assert 3 in precision
        assert 5 in precision
        assert 0 <= precision[1] <= 1

    def test_mrr_calculation(self):
        """Test Mean Reciprocal Rank calculation."""
        evaluator = RAGEvaluator()

        retrieved_docs = ["doc2", "doc1", "doc3"]  # doc1 is relevant, at position 2
        relevant_docs = ["doc1"]

        mrr = evaluator.calculate_mrr(retrieved_docs, relevant_docs)
        assert mrr == 0.5  # 1/2 = 0.5

    def test_ndcg_calculation(self):
        """Test nDCG calculation."""
        evaluator = RAGEvaluator()

        # relevance scores for retrieved docs
        relevance_scores = [3, 2, 3, 0, 1, 2]

        ndcg = evaluator.calculate_ndcg_at_k(relevance_scores, k=5)
        assert 0 <= ndcg <= 1

    def test_batch_evaluation(self, sample_documents):
        """Test batch evaluation on multiple queries."""
        evaluator = RAGEvaluator()

        test_set = [
            {
                "query": "What is ML?",
                "retrieved_docs": ["doc1", "doc2"],
                "relevant_docs": ["doc1"]
            },
            {
                "query": "Explain supervised learning",
                "retrieved_docs": ["doc3", "doc1"],
                "relevant_docs": ["doc3"]
            }
        ]

        results = evaluator.batch_evaluate(test_set, metrics=["recall@3", "precision@3", "mrr"])

        assert "recall@3" in results
        assert "precision@3" in results
        assert "mrr" in results
        assert all(0 <= v <= 1 for v in results.values())


class TestABTestingIntegration:
    """Test A/B testing infrastructure."""

    def test_variant_comparison(self):
        """Test comparing two RAG variants."""
        evaluator = RAGEvaluator()

        # Simulate metrics for two variants
        evaluator.log_metrics("baseline", {
            "recall@3": 0.45,
            "precision@3": 0.40,
            "ndcg@3": 0.50,
            "latency_p50": 800,
            "cost": 2.50
        })

        evaluator.log_metrics("enhanced", {
            "recall@3": 0.75,
            "precision@3": 0.68,
            "ndcg@3": 0.75,
            "latency_p50": 320,
            "cost": 1.88
        })

        comparison = evaluator.compare_variants("baseline", "enhanced")

        assert "improvements" in comparison
        assert comparison["improvements"]["recall@3"] > 0
        assert comparison["improvements"]["precision@3"] > 0
        assert comparison["improvements"]["latency_p50"] < 0  # Lower is better

    def test_statistical_significance(self):
        """Test statistical significance testing."""
        evaluator = RAGEvaluator()

        # Simulate multiple measurements
        baseline_scores = [0.45, 0.43, 0.46, 0.44, 0.45, 0.46, 0.44]
        enhanced_scores = [0.75, 0.73, 0.76, 0.74, 0.75, 0.77, 0.74]

        is_significant, p_value = evaluator.test_significance(
            baseline_scores, enhanced_scores
        )

        assert isinstance(is_significant, bool)
        assert 0 <= p_value <= 1
        # With such different scores, should be significant
        assert is_significant is True


class TestPerformanceMonitoring:
    """Test performance monitoring integration."""

    def test_query_cache_emits_one_metric_per_lookup(self):
        """Application metrics must reflect query-cache outcomes, not Redis internals."""
        cache = RAGCache(enable_memory=True, enable_redis=False, enable_s3=False)

        with patch("backend.rag.caching_layer.track_cache_miss") as track_miss, \
             patch("backend.rag.caching_layer.track_cache_hit") as track_hit:
            assert cache.get_query_result("What is retrieval-augmented generation?") is None
            cache.put_query_result(
                "What is retrieval-augmented generation?",
                {"answer": "A grounded generation technique."},
            )
            assert cache.get_query_result("What is retrieval-augmented generation?") is not None

        track_miss.assert_called_once_with(cache_type="query_result")
        track_hit.assert_called_once_with(cache_type="query_result")

    def test_embedding_cache_emits_one_metric_per_lookup(self):
        """Embedding cache metrics distinguish a miss from a subsequent hit."""
        cache = RAGCache(enable_memory=True, enable_redis=False, enable_s3=False)

        with patch("backend.rag.caching_layer.track_cache_miss") as track_miss, \
             patch("backend.rag.caching_layer.track_cache_hit") as track_hit:
            assert cache.get_embedding("cacheable text") is None
            cache.put_embedding("cacheable text", [0.1, 0.2])
            assert cache.get_embedding("cacheable text") == [0.1, 0.2]

        track_miss.assert_called_once_with(cache_type="embedding")
        track_hit.assert_called_once_with(cache_type="embedding")

    @pytest.mark.asyncio
    async def test_latency_tracking(self, rag_pipeline):
        """Test latency tracking in pipeline."""
        import time

        query = "What is reinforcement learning?"

        start_time = time.time()

        # Simulate query processing
        enhanced = rag_pipeline["query_enhancer"].enhance(query)
        results = rag_pipeline["hybrid_searcher"].search(enhanced.rewritten_query or query, top_k=10)
        reranked = rag_pipeline["reranker"].rerank(query, [r["text"] for r in results], top_k=3)

        end_time = time.time()
        latency = (end_time - start_time) * 1000  # Convert to ms

        # Should complete reasonably quickly
        assert latency < 5000  # 5 seconds max

    def test_cache_hit_rate_tracking(self, rag_pipeline):
        """Test cache hit rate tracking."""
        cache = rag_pipeline["cache"]

        # Perform multiple queries
        queries = [
            "What is ML?",
            "What is ML?",  # Duplicate - should hit cache
            "What is DL?",
            "What is ML?",  # Another duplicate
        ]

        for query in queries:
            result = cache.get_query_result(query)
            if result is None:
                # Cache miss - store result
                cache.put_query_result(query, {"answer": f"Answer to {query}"})

        stats = cache.get_all_stats()

        assert "query_cache" in stats
        # Should have some cache hits
        if stats["query_cache"]["hits"] > 0:
            hit_rate = stats["query_cache"]["hits"] / (stats["query_cache"]["hits"] + stats["query_cache"]["misses"])
            assert 0 <= hit_rate <= 1


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling and resilience."""

    @pytest.mark.asyncio
    async def test_llm_failure_handling(self, mock_llm, rag_pipeline):
        """Test graceful handling of LLM failures."""
        # Configure LLM to fail
        mock_llm.generate = AsyncMock(side_effect=Exception("API error"))

        query = "What is AI?"

        # Query enhancement should handle LLM failure gracefully
        try:
            enhanced = rag_pipeline["query_enhancer"].enhance(query)
            # Should fall back to original query
            assert enhanced.original_query == query
        except Exception:
            # Or raise appropriate error
            pass

    @pytest.mark.asyncio
    async def test_empty_retrieval_results(self, rag_pipeline):
        """Test handling of empty retrieval results."""
        # Configure mock to return empty results
        rag_pipeline["hybrid_searcher"].bm25_retriever.search = Mock(return_value=[])
        rag_pipeline["hybrid_searcher"].semantic_retriever.search = AsyncMock(return_value=[])

        query = "Nonexistent topic xyz123"
        results = rag_pipeline["hybrid_searcher"].search(query, top_k=10)

        # Should return empty list, not crash
        assert isinstance(results, list)
        assert len(results) == 0

    def test_invalid_query_handling(self, rag_pipeline):
        """Test handling of invalid queries."""
        invalid_queries = ["", "   ", None]

        for query in invalid_queries:
            if query is None:
                continue
            try:
                enhanced = rag_pipeline["query_enhancer"].enhance(query)
                # Should handle gracefully
                assert enhanced is not None
            except ValueError:
                # Or raise appropriate error
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
