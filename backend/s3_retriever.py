"""
S3-based Retriever for LlamaIndex RAG Pipeline
Wraps S3VectorStore to work with LlamaIndex's retriever interface
"""

from typing import Dict, List, Optional
import threading
import time
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, TextNode, QueryBundle
from backend.s3_vector_store import S3VectorStore
from backend.bedrock_embeddings import BedrockEmbeddings
from backend.logger import get_logger

logger = get_logger(__name__)


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

        self.vector_store = vector_store or S3VectorStore()
        self.embeddings = embeddings or BedrockEmbeddings()
        self.similarity_top_k = similarity_top_k
        self.force_rebuild_index = force_rebuild_index

        self._index_loaded = False
        self._index_load_lock = threading.Lock()
        self._stats = {
            "total_retrievals": 0,
            "total_nodes_retrieved": 0,
            "total_latency_ms": 0,
            "errors": 0,
        }
        self._stats_lock = threading.Lock()

    def _ensure_index_loaded(self):
        """Load index if not already loaded."""
        if not self._index_loaded:
            with self._index_load_lock:
                if not self._index_loaded:
                    logger.info("Loading S3 vector index...")
                    try:
                        self.vector_store.load_index(
                            force_rebuild=self.force_rebuild_index
                        )
                        stats = self.vector_store.get_stats()
                        logger.info(
                            f"✓ S3 Retriever ready with {stats['total_vectors']} vectors"
                        )
                        self._index_loaded = True
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

        try:
            results = self.vector_store.search(
                query_embedding=query_embedding, top_k=self.similarity_top_k
            )
        except Exception as e:
            logger.error(f"Error searching S3 vectors: {e}")
            with self._stats_lock:
                self._stats["errors"] += 1
            return []

        nodes_with_scores = []
        chunk_ids = [chunk_id for chunk_id, _, _ in results]

        try:
            chunk_texts = self.vector_store.get_chunk_texts(chunk_ids)
        except Exception as e:
            logger.warning(
                f"Error fetching chunk texts, continuing with metadata only: {e}"
            )
            chunk_texts = {}

        for chunk_id, score, metadata in results:
            text = chunk_texts.get(chunk_id)

            if not text:
                logger.debug(f"No text found for chunk {chunk_id}, using metadata")
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

            node_with_score = NodeWithScore(node=node, score=score)
            nodes_with_scores.append(node_with_score)

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
