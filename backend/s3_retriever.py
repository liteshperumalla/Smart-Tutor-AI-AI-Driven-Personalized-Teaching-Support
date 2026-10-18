"""
S3-based Retriever for LlamaIndex RAG Pipeline
Wraps S3VectorStore to work with LlamaIndex's retriever interface.

Supports optional cross-encoder reranking (controlled by config flags):
  RERANKING_ENABLED=true   → over-fetch, filter, rerank, return top results
  RERANKING_ENABLED=false  → original cosine-only retrieval
"""

from typing import Dict, List, Optional
import threading
import time
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, TextNode, QueryBundle
from backend.s3_vector_store import S3VectorStore
from backend.bedrock_embeddings import BedrockEmbeddings
from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)

# Lazy singleton for cross-encoder (loaded once, reused across requests)
_cross_encoder_reranker = None
_cross_encoder_lock = threading.Lock()

# Process-wide shared vector store and embeddings. The vector index (~14k
# vectors, ~56 MB download) and the embedding LRU cache are expensive to
# rebuild, so retrievers created without explicit dependencies share these
# instances instead of re-downloading the index from S3 on every request.
_shared_vector_store: Optional[S3VectorStore] = None
_shared_embeddings: Optional[BedrockEmbeddings] = None
_shared_lock = threading.Lock()


def get_shared_vector_store() -> S3VectorStore:
    """Return the process-wide S3VectorStore singleton (lazy, thread-safe)."""
    global _shared_vector_store
    if _shared_vector_store is None:
        with _shared_lock:
            if _shared_vector_store is None:
                _shared_vector_store = S3VectorStore()
    return _shared_vector_store


def get_shared_embeddings() -> BedrockEmbeddings:
    """Return the process-wide BedrockEmbeddings singleton (lazy, thread-safe)."""
    global _shared_embeddings
    if _shared_embeddings is None:
        with _shared_lock:
            if _shared_embeddings is None:
                _shared_embeddings = BedrockEmbeddings()
    return _shared_embeddings


def _get_cross_encoder():
    """Return a singleton CrossEncoderReranker (lazy init, thread-safe)."""
    global _cross_encoder_reranker
    if _cross_encoder_reranker is None:
        with _cross_encoder_lock:
            if _cross_encoder_reranker is None:
                from backend.rag.reranker import create_cross_encoder_reranker
                _cross_encoder_reranker = create_cross_encoder_reranker(
                    model_name=config.RERANK_MODEL
                )
                logger.info("Cross-encoder reranker loaded (singleton)")
    return _cross_encoder_reranker


class S3Retriever(BaseRetriever):
    """LlamaIndex-compatible retriever using S3 vector storage"""

    def __init__(
        self,
        vector_store: Optional[S3VectorStore] = None,
        embeddings: Optional[BedrockEmbeddings] = None,
        similarity_top_k: int = 5,
        force_rebuild_index: bool = False,
    ):
        """
        Initialize S3 Retriever

        Args:
            vector_store: S3VectorStore instance (creates new if None)
            embeddings: BedrockEmbeddings instance (creates new if None)
            similarity_top_k: Number of top results to return
            force_rebuild_index: Whether to rebuild index from S3 on init
        """
        super().__init__()

        self.vector_store = vector_store or get_shared_vector_store()
        self.embeddings = embeddings or get_shared_embeddings()
        self.similarity_top_k = similarity_top_k
        self.force_rebuild_index = force_rebuild_index
        self._stats = {
            "total_retrievals": 0,
            "total_nodes_retrieved": 0,
            "total_latency_ms": 0,
            "errors": 0,
        }
        self._stats_lock = threading.Lock()

    def _ensure_index_loaded(self):
        """Ensure the (possibly shared) vector store has its index loaded.

        Load-once semantics live on the store itself, so many retriever
        instances can share one loaded index without re-downloading it.
        """
        try:
            self.vector_store.ensure_loaded(force_rebuild=self.force_rebuild_index)
            # A forced rebuild should only happen once per retriever, not on
            # every retrieval call.
            self.force_rebuild_index = False
        except Exception as e:
            logger.error(f"✗ Failed to load S3 vector index: {e}")
            raise

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        start_time = time.time()
        self._ensure_index_loaded()

        query_str = (
            query_bundle.query_str
            if hasattr(query_bundle, "query_str")
            else str(query_bundle)
        )

        try:
            query_embedding = self.embeddings.encode([query_str])[0]
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            with self._stats_lock:
                self._stats["errors"] += 1
            return []

        # Decide how many candidates to fetch
        use_reranking = config.RERANKING_ENABLED and self.similarity_top_k <= config.RETRIEVAL_FETCH_K
        fetch_k = config.RETRIEVAL_FETCH_K if use_reranking else self.similarity_top_k

        try:
            results = self.vector_store.search(
                query_embedding=query_embedding, top_k=fetch_k
            )
        except Exception as e:
            logger.error(f"Error searching S3 vectors: {e}")
            with self._stats_lock:
                self._stats["errors"] += 1
            return []

        raw_results = list(results)

        # ── Score filtering: drop low-relevance results ──────────
        min_score = config.MIN_RETRIEVAL_SCORE
        before_count = len(results)
        results = [(cid, sc, meta) for cid, sc, meta in results if sc >= min_score]
        if before_count > len(results):
            logger.info(
                f"Score filter: {before_count} → {len(results)} (min={min_score})"
            )
        if not results and raw_results:
            # Returning zero nodes causes the answering layer to hallucinate on
            # otherwise answerable questions. Fall back to the strongest raw
            # candidates when thresholding is too aggressive.
            fallback_count = min(self.similarity_top_k, len(raw_results))
            results = raw_results[:fallback_count]
            logger.warning(
                "Score filter removed all %s retrieval candidates for query '%s...'; "
                "falling back to top %s raw results",
                before_count,
                query_str[:50],
                fallback_count,
            )

        # Fetch chunk texts for all remaining candidates
        chunk_ids = [chunk_id for chunk_id, _, _ in results]
        try:
            chunk_texts = self.vector_store.get_chunk_texts(chunk_ids)
        except Exception as e:
            logger.warning(
                f"Error fetching chunk texts, continuing with metadata only: {e}"
            )
            chunk_texts = {}

        # ── Cross-encoder reranking ──────────────────────────────
        if use_reranking and len(results) > 0:
            try:
                reranker = _get_cross_encoder()
                # Build dicts the reranker expects
                rerank_input = []
                for chunk_id, score, metadata in results:
                    text = chunk_texts.get(chunk_id) or f"[Content from {metadata.get('source_file', 'unknown')}]"
                    rerank_input.append({
                        "chunk_id": chunk_id,
                        "text": text,
                        "score": score,
                        "metadata": metadata,
                    })

                return_k = min(self.similarity_top_k, len(rerank_input))
                ranked = reranker.rerank(query_str, rerank_input, top_k=return_k)

                # Convert RankedResult → NodeWithScore
                nodes_with_scores = []
                for r in ranked:
                    node = TextNode(
                        text=r.text,
                        id_=r.chunk_id,
                        metadata={
                            "source_file": r.metadata.get("source_file", "unknown"),
                            "chunk_index": r.metadata.get("chunk_index", 0),
                            "s3_key": r.metadata.get("s3_key", ""),
                            "similarity_score": round(r.original_score or 0, 4),
                            "rerank_score": round(r.score, 4),
                        },
                    )
                    nodes_with_scores.append(NodeWithScore(node=node, score=r.score))

                latency_ms = (time.time() - start_time) * 1000
                with self._stats_lock:
                    self._stats["total_retrievals"] += 1
                    self._stats["total_nodes_retrieved"] += len(nodes_with_scores)
                    self._stats["total_latency_ms"] += latency_ms

                logger.info(
                    f"Reranked {len(rerank_input)} → {len(nodes_with_scores)} nodes "
                    f"(latency: {latency_ms:.1f}ms) for query: '{query_str[:50]}...'"
                )
                return nodes_with_scores

            except Exception as e:
                logger.warning(f"Reranking failed, falling back to cosine: {e}")
                # Fall through to cosine-only path below

        # ── Cosine-only fallback (no reranking) ──────────────────
        nodes_with_scores = []
        for chunk_id, score, metadata in results[: self.similarity_top_k]:
            text = chunk_texts.get(chunk_id)
            if not text:
                text = f"[Content from {metadata.get('source_file', 'unknown')}]"

            node = TextNode(
                text=text,
                id_=chunk_id,
                metadata={
                    "source_file": metadata.get("source_file", "unknown"),
                    "chunk_index": metadata.get("chunk_index", 0),
                    "s3_key": metadata.get("s3_key", ""),
                    "similarity_score": round(score, 4),
                },
            )
            nodes_with_scores.append(NodeWithScore(node=node, score=score))

        latency_ms = (time.time() - start_time) * 1000
        with self._stats_lock:
            self._stats["total_retrievals"] += 1
            self._stats["total_nodes_retrieved"] += len(nodes_with_scores)
            self._stats["total_latency_ms"] += latency_ms

        if nodes_with_scores:
            logger.info(
                f"Retrieved {len(nodes_with_scores)} nodes (latency: {latency_ms:.1f}ms) for query: '{query_str[:50]}...'"
            )
        else:
            logger.warning(f"No nodes retrieved for query: '{query_str[:50]}...'")

        return nodes_with_scores

    def get_stats(self) -> Dict:
        """Get statistics about the retriever"""
        vector_stats = self.vector_store.get_stats()
        emb_stats = (
            self.embeddings.get_stats() if hasattr(self.embeddings, "get_stats") else {}
        )

        with self._stats_lock:
            avg_latency = self._stats["total_latency_ms"] / max(
                self._stats["total_retrievals"], 1
            )

        return {
            "vector_store": vector_stats,
            "embeddings": emb_stats,
            "retriever": {**self._stats, "avg_latency_ms": round(avg_latency, 2)},
        }


def create_s3_retriever(
    similarity_top_k: int = 5, force_rebuild: bool = False
) -> S3Retriever:
    """
    Factory function to create S3Retriever

    Args:
        similarity_top_k: Number of results to retrieve
        force_rebuild: Whether to force rebuild the index from S3

    Returns:
        S3Retriever instance
    """
    return S3Retriever(
        similarity_top_k=similarity_top_k, force_rebuild_index=force_rebuild
    )
