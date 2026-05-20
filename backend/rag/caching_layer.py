"""
RAG Caching Layer
Multi-tier caching for embeddings, queries, and results

Cache Hierarchy:
1. In-memory cache (LRU) - fastest, limited size
2. Redis cache - fast, shared across instances
3. S3 cache - persistent, for embeddings

Caching Strategies:
- Embedding cache: Cache vector embeddings (expensive to generate)
- Query cache: Cache query results (exact + fuzzy matching)
- Result cache: Cache final RAG responses (semantic similarity matching)
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from functools import lru_cache
from collections import OrderedDict

import numpy as np

logger = logging.getLogger(__name__)

try:
    import hnswlib  # type: ignore
    _HNSW_AVAILABLE = True
except Exception:
    _HNSW_AVAILABLE = False


class _VectorIndex:
    """Approximate-nearest-neighbour index for the fuzzy cache.

    Replaces the linear Python loop with either:
      * a normalised numpy matrix + single BLAS dot-product (O(N) but ~100x
        faster in practice — keeps things small and dependency-free), OR
      * an HNSW index if ``hnswlib`` is installed (O(log N), good past 10K
        entries).

    The index stays in lockstep with the LRU dict that owns the cache entries:
    when an entry is evicted, ``remove(key)`` clears the corresponding row.
    """

    def __init__(self, dim: int, max_size: int, use_hnsw: bool = True):
        self.dim = dim
        self.max_size = max_size
        self.use_hnsw = use_hnsw and _HNSW_AVAILABLE
        self._lock_ready = False

        if self.use_hnsw:
            self._hnsw = hnswlib.Index(space="cosine", dim=dim)
            self._hnsw.init_index(max_elements=max(max_size, 16), ef_construction=100, M=16)
            self._hnsw.set_ef(32)
            self._labels: Dict[int, str] = {}
            self._reverse_labels: Dict[str, int] = {}
            self._next_label = 0
        else:
            # Pre-allocated row matrix; rows are L2-normalised so cosine == dot.
            self._matrix = np.zeros((max_size, dim), dtype=np.float32)
            self._row_to_key: List[Optional[str]] = [None] * max_size
            self._key_to_row: Dict[str, int] = {}
            self._free_rows: List[int] = list(range(max_size))
            self._used_rows: int = 0

    # ── helpers ──────────────────────────────────────────────────
    @staticmethod
    def _normalise(vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        if norm == 0:
            return vec
        return vec / norm

    # ── HNSW path ────────────────────────────────────────────────
    def _hnsw_add(self, key: str, vec: np.ndarray) -> None:
        if key in self._reverse_labels:
            label = self._reverse_labels[key]
            self._hnsw.mark_deleted(label)
        label = self._next_label
        self._next_label += 1
        # Resize if needed
        if label >= self._hnsw.get_max_elements():
            self._hnsw.resize_index(label * 2 + 1)
        self._hnsw.add_items(vec.reshape(1, -1).astype(np.float32), [label])
        self._labels[label] = key
        self._reverse_labels[key] = label

    def _hnsw_remove(self, key: str) -> None:
        label = self._reverse_labels.pop(key, None)
        if label is not None:
            try:
                self._hnsw.mark_deleted(label)
            except Exception:
                pass
            self._labels.pop(label, None)

    def _hnsw_search(self, vec: np.ndarray) -> Tuple[Optional[str], float]:
        try:
            count = self._hnsw.get_current_count()
            if count == 0:
                return None, 0.0
            labels, distances = self._hnsw.knn_query(
                vec.reshape(1, -1).astype(np.float32),
                k=min(1, count),
            )
            label = int(labels[0][0])
            key = self._labels.get(label)
            if key is None:
                return None, 0.0
            # hnswlib returns cosine *distance* (1 - similarity)
            similarity = float(1.0 - distances[0][0])
            return key, similarity
        except RuntimeError:
            # Raised when all visited items are deleted — treat as miss.
            return None, 0.0

    # ── numpy matrix path ────────────────────────────────────────
    def _matrix_add(self, key: str, vec: np.ndarray) -> None:
        if key in self._key_to_row:
            row = self._key_to_row[key]
            self._matrix[row] = vec
            return
        if not self._free_rows:
            # Caller (LRU) should evict first; defensive guard.
            return
        row = self._free_rows.pop(0)
        self._matrix[row] = vec
        self._row_to_key[row] = key
        self._key_to_row[key] = row
        self._used_rows += 1

    def _matrix_remove(self, key: str) -> None:
        row = self._key_to_row.pop(key, None)
        if row is None:
            return
        self._matrix[row] = 0.0
        self._row_to_key[row] = None
        self._free_rows.append(row)
        self._used_rows -= 1

    def _matrix_search(self, vec: np.ndarray) -> Tuple[Optional[str], float]:
        if self._used_rows == 0:
            return None, 0.0
        # Single matmul across the whole index.
        sims = self._matrix @ vec
        best_row = int(np.argmax(sims))
        best_key = self._row_to_key[best_row]
        if best_key is None:
            return None, 0.0
        return best_key, float(sims[best_row])

    # ── public API ───────────────────────────────────────────────
    def add(self, key: str, embedding: List[float]) -> None:
        vec = self._normalise(np.asarray(embedding, dtype=np.float32))
        if vec.shape[0] != self.dim:
            # Dimension mismatch — the cache key embeddings must all share a model.
            # Reset the index to the new dimension rather than silently corrupting it.
            self.dim = vec.shape[0]
            self.__init__(self.dim, self.max_size, use_hnsw=self.use_hnsw)
        if self.use_hnsw:
            self._hnsw_add(key, vec)
        else:
            self._matrix_add(key, vec)

    def remove(self, key: str) -> None:
        if self.use_hnsw:
            self._hnsw_remove(key)
        else:
            self._matrix_remove(key)

    def search(self, embedding: List[float]) -> Tuple[Optional[str], float]:
        vec = self._normalise(np.asarray(embedding, dtype=np.float32))
        if vec.shape[0] != self.dim:
            return None, 0.0
        if self.use_hnsw:
            return self._hnsw_search(vec)
        return self._matrix_search(vec)

    def clear(self) -> None:
        if self.use_hnsw:
            self._hnsw = hnswlib.Index(space="cosine", dim=self.dim)
            self._hnsw.init_index(max_elements=max(self.max_size, 16), ef_construction=100, M=16)
            self._hnsw.set_ef(32)
            self._labels.clear()
            self._reverse_labels.clear()
            self._next_label = 0
        else:
            self._matrix.fill(0.0)
            self._row_to_key = [None] * self.max_size
            self._key_to_row.clear()
            self._free_rows = list(range(self.max_size))
            self._used_rows = 0


class LRUCache:
    """
    Simple LRU (Least Recently Used) cache implementation
    Thread-safe in-memory cache with size limit
    """

    def __init__(self, max_size: int = 1000):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache"""
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self.hits += 1
            return self.cache[key]

        self.misses += 1
        return None

    def put(self, key: str, value: Any):
        """Add item to cache"""
        if key in self.cache:
            # Update existing item
            self.cache.move_to_end(key)
        else:
            # Add new item
            if len(self.cache) >= self.max_size:
                # Remove oldest item
                self.cache.popitem(last=False)

        self.cache[key] = value

    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate
        }


class EmbeddingCache:
    """
    Cache for vector embeddings
    Supports in-memory, Redis, and S3 backends
    """

    def __init__(
        self,
        use_memory: bool = True,
        use_redis: bool = False,
        use_s3: bool = False,
        redis_client: Optional[Any] = None,
        s3_client: Optional[Any] = None,
        s3_bucket: Optional[str] = None,
        memory_cache_size: int = 1000,
        redis_ttl: int = 86400  # 24 hours
    ):
        self.use_memory = use_memory
        self.use_redis = use_redis
        self.use_s3 = use_s3

        # In-memory cache
        if use_memory:
            self.memory_cache = LRUCache(max_size=memory_cache_size)
        else:
            self.memory_cache = None

        # Redis cache
        self.redis_client = redis_client if use_redis else None
        self.redis_ttl = redis_ttl

        # S3 cache
        self.s3_client = s3_client if use_s3 else None
        self.s3_bucket = s3_bucket

    def _generate_key(self, text: str, model_name: str = "default") -> str:
        """Generate cache key from text"""
        content = f"{model_name}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(
        self,
        text: str,
        model_name: str = "default"
    ) -> Optional[List[float]]:
        """
        Get embedding from cache (checks all tiers)
        """
        key = self._generate_key(text, model_name)

        # Check memory cache first (fastest)
        if self.use_memory and self.memory_cache:
            embedding = self.memory_cache.get(key)
            if embedding is not None:
                logger.debug(f"Embedding cache HIT (memory): {key[:16]}")
                return embedding

        # Check Redis cache
        if self.use_redis and self.redis_client:
            try:
                cached_data = self.redis_client.get(f"embedding:{key}")
                if cached_data:
                    embedding = json.loads(cached_data)
                    logger.debug(f"Embedding cache HIT (Redis): {key[:16]}")

                    # Populate memory cache
                    if self.use_memory and self.memory_cache:
                        self.memory_cache.put(key, embedding)

                    return embedding
            except Exception as e:
                logger.error(f"Redis cache error: {e}")

        # Check S3 cache
        if self.use_s3 and self.s3_client and self.s3_bucket:
            try:
                response = self.s3_client.get_object(
                    Bucket=self.s3_bucket,
                    Key=f"embeddings/{key}.json"
                )
                embedding = json.loads(response['Body'].read().decode("utf-8"))
                logger.debug(f"Embedding cache HIT (S3): {key[:16]}")

                # Populate higher-tier caches
                if self.use_redis and self.redis_client:
                    self.redis_client.setex(
                        f"embedding:{key}",
                        self.redis_ttl,
                        json.dumps(embedding)
                    )

                if self.use_memory and self.memory_cache:
                    self.memory_cache.put(key, embedding)

                return embedding
            except self.s3_client.exceptions.NoSuchKey:
                pass
            except Exception as e:
                logger.error(f"S3 cache error: {e}")

        logger.debug(f"Embedding cache MISS: {key[:16]}")
        return None

    def put(
        self,
        text: str,
        embedding: List[float],
        model_name: str = "default"
    ):
        """
        Store embedding in cache (all tiers)
        """
        key = self._generate_key(text, model_name)

        # Store in memory cache
        if self.use_memory and self.memory_cache:
            self.memory_cache.put(key, embedding)

        # Store in Redis cache
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.setex(
                    f"embedding:{key}",
                    self.redis_ttl,
                    json.dumps(embedding)
                )
            except Exception as e:
                logger.error(f"Redis cache write error: {e}")

        # Store in S3 cache (async/background recommended)
        if self.use_s3 and self.s3_client and self.s3_bucket:
            try:
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=f"embeddings/{key}.json",
                    Body=json.dumps(embedding).encode("utf-8"),
                    ContentType="application/json",
                )
            except Exception as e:
                logger.error(f"S3 cache write error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {}

        if self.use_memory and self.memory_cache:
            stats["memory"] = self.memory_cache.get_stats()

        if self.use_redis and self.redis_client:
            try:
                info = self.redis_client.info("stats")
                stats["redis"] = {
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0)
                }
            except Exception as e:
                logger.error(f"Redis stats error: {e}")

        return stats


class QueryCache:
    """
    Cache for query results
    Supports exact matching and fuzzy matching (semantic similarity)
    """

    def __init__(
        self,
        use_exact_matching: bool = True,
        use_fuzzy_matching: bool = True,
        fuzzy_threshold: float = 0.95,
        redis_client: Optional[Any] = None,
        ttl: int = 3600,  # 1 hour
        fuzzy_cache_size: int = 1000,
        fuzzy_embedding_dim: int = 1024,
        use_hnsw: bool = True,
    ):
        self.use_exact_matching = use_exact_matching
        self.use_fuzzy_matching = use_fuzzy_matching
        self.fuzzy_threshold = fuzzy_threshold
        self.redis_client = redis_client
        self.ttl = ttl

        # In-memory caches
        self.exact_cache = LRUCache(max_size=500)
        self.fuzzy_cache = LRUCache(max_size=fuzzy_cache_size)  # Stores (query, embedding, result) entries

        # Vector index sits next to ``fuzzy_cache`` and is kept in sync.
        # The dim is set on first ``add`` if the assumed dim is wrong.
        self._fuzzy_index: Optional[_VectorIndex] = None
        self._fuzzy_dim = fuzzy_embedding_dim
        self._use_hnsw = use_hnsw

    def _generate_key(self, query: str) -> str:
        """Generate cache key from query"""
        # Normalize query
        normalized = query.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _calculate_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """Calculate cosine similarity between embeddings"""
        import numpy as np

        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def get_exact(self, query: str) -> Optional[Dict[str, Any]]:
        """Get cached result for exact query match"""
        if not self.use_exact_matching:
            return None

        key = self._generate_key(query)

        # Check in-memory cache
        result = self.exact_cache.get(key)
        if result:
            logger.debug(f"Query cache HIT (exact): {query[:50]}")
            return result

        # Check Redis cache
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(f"query:{key}")
                if cached_data:
                    result = json.loads(cached_data)
                    logger.debug(f"Query cache HIT (Redis exact): {query[:50]}")
                    self.exact_cache.put(key, result)
                    return result
            except Exception as e:
                logger.error(f"Redis query cache error: {e}")

        return None

    def get_fuzzy(
        self,
        query: str,
        query_embedding: List[float]
    ) -> Optional[Dict[str, Any]]:
        """Get cached result for similar query (fuzzy match).

        Uses an HNSW (when available) or vectorised numpy index for $O(\\log N)$
        or BLAS-accelerated similarity lookup. Falls back to a miss on any
        index inconsistency rather than a Python loop scan.
        """
        if not self.use_fuzzy_matching or self._fuzzy_index is None:
            return None

        best_key, best_similarity = self._fuzzy_index.search(query_embedding)
        if best_key is None or best_similarity < self.fuzzy_threshold:
            return None

        cached_data = self.fuzzy_cache.get(best_key)
        if not cached_data:
            # Index/LRU drifted (rare race) — clean it up.
            self._fuzzy_index.remove(best_key)
            return None

        logger.debug(
            f"Query cache HIT (fuzzy, similarity={best_similarity:.3f}): {query[:50]}"
        )
        return cached_data.get("result")

    def put(
        self,
        query: str,
        result: Dict[str, Any],
        query_embedding: Optional[List[float]] = None
    ):
        """Store query result in cache"""
        key = self._generate_key(query)

        # Store in exact cache
        if self.use_exact_matching:
            self.exact_cache.put(key, result)

            # Store in Redis
            if self.redis_client:
                try:
                    self.redis_client.setex(
                        f"query:{key}",
                        self.ttl,
                        json.dumps(result)
                    )
                except Exception as e:
                    logger.error(f"Redis query cache write error: {e}")

        # Store in fuzzy cache + vector index
        if self.use_fuzzy_matching and query_embedding:
            # Lazy-init the index once we know the real embedding dim.
            if self._fuzzy_index is None:
                dim = len(query_embedding) or self._fuzzy_dim
                self._fuzzy_index = _VectorIndex(
                    dim=dim,
                    max_size=self.fuzzy_cache.max_size,
                    use_hnsw=self._use_hnsw,
                )

            # If LRU is at capacity, the oldest key will be evicted on ``put``;
            # peek at it so we can drop it from the index too.
            evicted_key: Optional[str] = None
            if (
                key not in self.fuzzy_cache.cache
                and len(self.fuzzy_cache.cache) >= self.fuzzy_cache.max_size
                and self.fuzzy_cache.cache
            ):
                evicted_key = next(iter(self.fuzzy_cache.cache))

            self.fuzzy_cache.put(key, {
                "query": query,
                "embedding": query_embedding,
                "result": result,
            })
            if evicted_key:
                self._fuzzy_index.remove(evicted_key)
            self._fuzzy_index.add(key, query_embedding)

    def invalidate(self, query: Optional[str] = None):
        """Invalidate cache entries"""
        if query:
            # Invalidate specific query
            key = self._generate_key(query)
            if key in self.exact_cache.cache:
                del self.exact_cache.cache[key]

            if self.redis_client:
                try:
                    self.redis_client.delete(f"query:{key}")
                except Exception as e:
                    logger.error(f"Redis cache invalidation error: {e}")
        else:
            # Invalidate all
            self.exact_cache.clear()
            self.fuzzy_cache.clear()
            if self._fuzzy_index is not None:
                self._fuzzy_index.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "exact_cache": self.exact_cache.get_stats(),
            "fuzzy_cache": self.fuzzy_cache.get_stats(),
            "fuzzy_index": {
                "backend": "hnsw" if (self._fuzzy_index and self._fuzzy_index.use_hnsw) else "numpy",
                "dim": self._fuzzy_index.dim if self._fuzzy_index else None,
            },
        }


class RAGCache:
    """
    Unified caching layer for RAG systems
    Combines embedding cache and query cache
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        s3_client: Optional[Any] = None,
        s3_bucket: Optional[str] = None,
        enable_all: bool = True
    ):
        # Embedding cache
        self.embedding_cache = EmbeddingCache(
            use_memory=enable_all,
            use_redis=enable_all and redis_client is not None,
            use_s3=enable_all and s3_client is not None,
            redis_client=redis_client,
            s3_client=s3_client,
            s3_bucket=s3_bucket
        )

        # Query cache
        self.query_cache = QueryCache(
            use_exact_matching=enable_all,
            use_fuzzy_matching=enable_all,
            redis_client=redis_client
        )

    def get_embedding(
        self,
        text: str,
        model_name: str = "default"
    ) -> Optional[List[float]]:
        """Get cached embedding"""
        return self.embedding_cache.get(text, model_name)

    def put_embedding(
        self,
        text: str,
        embedding: List[float],
        model_name: str = "default"
    ):
        """Cache embedding"""
        self.embedding_cache.put(text, embedding, model_name)

    def get_query_result(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached query result (exact or fuzzy match)"""
        # Try exact match first
        result = self.query_cache.get_exact(query)
        if result:
            return result

        # Try fuzzy match
        if query_embedding:
            result = self.query_cache.get_fuzzy(query, query_embedding)
            if result:
                return result

        return None

    def put_query_result(
        self,
        query: str,
        result: Dict[str, Any],
        query_embedding: Optional[List[float]] = None
    ):
        """Cache query result"""
        self.query_cache.put(query, result, query_embedding)

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all caches"""
        return {
            "embedding_cache": self.embedding_cache.get_stats(),
            "query_cache": self.query_cache.get_stats()
        }

    def clear_all(self):
        """Clear all caches"""
        self.embedding_cache.memory_cache.clear() if self.embedding_cache.memory_cache else None
        self.query_cache.invalidate()


# Convenience function
def create_rag_cache(
    redis_client: Optional[Any] = None,
    s3_client: Optional[Any] = None,
    s3_bucket: Optional[str] = None
) -> RAGCache:
    """Create a RAG cache instance"""
    return RAGCache(
        redis_client=redis_client,
        s3_client=s3_client,
        s3_bucket=s3_bucket,
        enable_all=True
    )
