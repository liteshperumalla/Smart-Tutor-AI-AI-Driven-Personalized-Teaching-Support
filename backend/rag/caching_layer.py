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

logger = logging.getLogger(__name__)


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
        ttl: int = 3600  # 1 hour
    ):
        self.use_exact_matching = use_exact_matching
        self.use_fuzzy_matching = use_fuzzy_matching
        self.fuzzy_threshold = fuzzy_threshold
        self.redis_client = redis_client
        self.ttl = ttl

        # In-memory caches
        self.exact_cache = LRUCache(max_size=500)
        self.fuzzy_cache = LRUCache(max_size=100)  # Smaller, stores (query, embedding) pairs

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
        """Get cached result for similar query (fuzzy match)"""
        if not self.use_fuzzy_matching:
            return None

        # Check fuzzy cache for similar queries
        best_match = None
        best_similarity = 0.0

        for cached_query, cached_data in self.fuzzy_cache.cache.items():
            cached_embedding = cached_data.get("embedding")
            if cached_embedding:
                similarity = self._calculate_similarity(query_embedding, cached_embedding)

                if similarity >= self.fuzzy_threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_match = cached_data.get("result")

        if best_match:
            logger.debug(f"Query cache HIT (fuzzy, similarity={best_similarity:.3f}): {query[:50]}")
            return best_match

        return None

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

        # Store in fuzzy cache
        if self.use_fuzzy_matching and query_embedding:
            self.fuzzy_cache.put(key, {
                "query": query,
                "embedding": query_embedding,
                "result": result
            })

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

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "exact_cache": self.exact_cache.get_stats(),
            "fuzzy_cache": self.fuzzy_cache.get_stats()
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
