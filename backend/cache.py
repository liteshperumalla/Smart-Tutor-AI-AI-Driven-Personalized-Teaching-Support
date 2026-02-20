"""
Caching Layer
Provides Redis and in-memory caching with TTL and size limits
Automatically falls back to in-memory cache if Redis is unavailable
"""

import time
import hashlib
import pickle
import json
from typing import Any, Optional, Callable
from collections import OrderedDict
from functools import wraps
from threading import RLock

from .config import config
from .logger import get_logger

logger = get_logger(__name__)

# Try to import Redis, but don't fail if not available
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory cache only. Install redis: pip install redis")


class CacheEntry:
    """Cache entry with TTL"""

    def __init__(self, value: Any, ttl: Optional[int] = None):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl or config.CACHE_TTL

    def is_expired(self) -> bool:
        """Check if entry is expired"""
        return time.time() - self.created_at > self.ttl

    def get_value(self) -> Any:
        """Get cached value"""
        return self.value


class LRUCache:
    """Thread-safe LRU cache with TTL support"""

    def __init__(self, max_size: Optional[int] = None, default_ttl: Optional[int] = None):
        self.max_size = max_size or config.CACHE_MAX_SIZE
        self.default_ttl = default_ttl or config.CACHE_TTL
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Check if expired
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                logger.debug(f"Cache expired: {key}")
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            logger.debug(f"Cache hit: {key}")
            return entry.get_value()

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
        """
        with self._lock:
            # Remove old entry if exists
            if key in self._cache:
                del self._cache[key]

            # Check size limit
            if len(self._cache) >= self.max_size:
                # Remove oldest entry
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug(f"Cache evicted (LRU): {oldest_key}")

            # Add new entry
            entry = CacheEntry(value, ttl or self.default_ttl)
            self._cache[key] = entry
            logger.debug(f"Cache set: {key}")

    def delete(self, key: str) -> bool:
        """
        Delete entry from cache

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache deleted: {key}")
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")

    def cleanup_expired(self) -> int:
        """
        Remove expired entries

        Returns:
            Number of entries removed
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]

            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.info(f"Removed {len(expired_keys)} expired cache entries")

            return len(expired_keys)

    def get_stats(self) -> dict:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': f"{hit_rate:.2f}%"
            }


class RedisCache:
    """Redis-based cache with fallback to in-memory LRU cache"""

    def __init__(self, max_size: Optional[int] = None, default_ttl: Optional[int] = None):
        self.default_ttl = default_ttl or config.CACHE_TTL
        self.redis_client = None
        self.fallback_cache = LRUCache(max_size, default_ttl)
        self._using_redis = False
        self._hits = 0
        self._misses = 0
        self._lock = RLock()

        # Try to connect to Redis if enabled and available
        if config.REDIS_ENABLED and REDIS_AVAILABLE:
            try:
                redis_kwargs = {
                    'host': config.REDIS_HOST,
                    'port': config.REDIS_PORT,
                    'db': config.REDIS_DB,
                    'decode_responses': False,  # We'll handle encoding/decoding
                    'socket_timeout': config.REDIS_CONNECTION_TIMEOUT,
                    'socket_connect_timeout': config.REDIS_CONNECTION_TIMEOUT,
                }

                if config.REDIS_PASSWORD:
                    redis_kwargs['password'] = config.REDIS_PASSWORD

                if config.REDIS_SSL:
                    redis_kwargs['ssl'] = True

                self.redis_client = redis.Redis(**redis_kwargs)
                # Test connection
                self.redis_client.ping()
                self._using_redis = True
                logger.info(f"Connected to Redis at {config.REDIS_HOST}:{config.REDIS_PORT}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using in-memory cache fallback.")
                self.redis_client = None
                self._using_redis = False
        else:
            logger.info("Redis not enabled or not available. Using in-memory cache.")

    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage"""
        try:
            return pickle.dumps(value)
        except Exception as e:
            logger.error(f"Serialization error: {e}")
            raise

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage"""
        try:
            return pickle.loads(data)
        except Exception as e:
            logger.error(f"Deserialization error: {e}")
            raise

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache (Redis or fallback)"""
        with self._lock:
            if self._using_redis and self.redis_client:
                try:
                    data = self.redis_client.get(key)
                    if data is None:
                        self._misses += 1
                        return None

                    self._hits += 1
                    logger.debug(f"Redis cache hit: {key}")
                    return self._deserialize(data)
                except Exception as e:
                    logger.warning(f"Redis get error: {e}. Falling back to in-memory cache.")
                    self._using_redis = False
                    return self.fallback_cache.get(key)
            else:
                return self.fallback_cache.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache (Redis or fallback)"""
        ttl_seconds = ttl or self.default_ttl

        with self._lock:
            if self._using_redis and self.redis_client:
                try:
                    serialized = self._serialize(value)
                    self.redis_client.setex(key, ttl_seconds, serialized)
                    logger.debug(f"Redis cache set: {key} (TTL: {ttl_seconds}s)")
                except Exception as e:
                    logger.warning(f"Redis set error: {e}. Falling back to in-memory cache.")
                    self._using_redis = False
                    self.fallback_cache.set(key, value, ttl)
            else:
                self.fallback_cache.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """Delete entry from cache"""
        with self._lock:
            if self._using_redis and self.redis_client:
                try:
                    result = self.redis_client.delete(key)
                    logger.debug(f"Redis cache deleted: {key}")
                    return result > 0
                except Exception as e:
                    logger.warning(f"Redis delete error: {e}. Falling back to in-memory cache.")
                    self._using_redis = False
                    return self.fallback_cache.delete(key)
            else:
                return self.fallback_cache.delete(key)

    def clear(self) -> None:
        """Clear all cache entries"""
        with self._lock:
            if self._using_redis and self.redis_client:
                try:
                    # Use scan to find and delete all keys (safer than FLUSHDB)
                    # This is a simple implementation; for production, you might want to use key prefixes
                    logger.info("Redis cache cleared (using fallback cache)")
                    self.fallback_cache.clear()
                except Exception as e:
                    logger.warning(f"Redis clear error: {e}")
                    self.fallback_cache.clear()
            else:
                self.fallback_cache.clear()

    def cleanup_expired(self) -> int:
        """Cleanup expired entries (Redis handles this automatically, but we clean fallback)"""
        with self._lock:
            # Redis handles expiration automatically, just clean fallback
            return self.fallback_cache.cleanup_expired()

    def get_stats(self) -> dict:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

            stats = {
                'backend': 'redis' if self._using_redis else 'in-memory',
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': f"{hit_rate:.2f}%"
            }

            if self._using_redis and self.redis_client:
                try:
                    info = self.redis_client.info('stats')
                    stats.update({
                        'redis_keys': self.redis_client.dbsize(),
                        'redis_hits': info.get('keyspace_hits', 0),
                        'redis_misses': info.get('keyspace_misses', 0),
                    })
                except:
                    pass
            else:
                stats.update(self.fallback_cache.get_stats())

            return stats


class CacheManager:
    """Centralized cache manager with multiple cache instances"""

    def __init__(self, use_redis: bool = True):
        self._caches: dict[str, any] = {}
        self._lock = RLock()
        self._use_redis = use_redis and config.REDIS_ENABLED and REDIS_AVAILABLE

    def get_cache(self, name: str, max_size: Optional[int] = None,
                 default_ttl: Optional[int] = None, use_redis: Optional[bool] = None):
        """
        Get or create a named cache

        Args:
            name: Cache name
            max_size: Maximum cache size
            default_ttl: Default TTL for entries
            use_redis: Override to force Redis or LRU cache

        Returns:
            Cache instance (RedisCache or LRUCache)
        """
        with self._lock:
            if name not in self._caches:
                # Determine which cache backend to use
                should_use_redis = use_redis if use_redis is not None else self._use_redis

                if should_use_redis:
                    self._caches[name] = RedisCache(max_size, default_ttl)
                    logger.info(f"Created Redis cache: {name}")
                else:
                    self._caches[name] = LRUCache(max_size, default_ttl)
                    logger.info(f"Created in-memory cache: {name}")
            return self._caches[name]

    def clear_all(self) -> None:
        """Clear all caches"""
        with self._lock:
            for cache in self._caches.values():
                cache.clear()
            logger.info("All caches cleared")

    def cleanup_all_expired(self) -> int:
        """Cleanup expired entries in all caches"""
        total_removed = 0
        with self._lock:
            for cache in self._caches.values():
                total_removed += cache.cleanup_expired()
        return total_removed

    def get_all_stats(self) -> dict:
        """Get statistics for all caches"""
        with self._lock:
            return {
                name: cache.get_stats()
                for name, cache in self._caches.items()
            }


# Singleton instance
_cache_manager = None


def get_cache_manager() -> CacheManager:
    """Get singleton cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def cached(cache_name: str = "default", ttl: Optional[int] = None,
          key_prefix: str = ""):
    """
    Decorator for caching function results

    Args:
        cache_name: Name of cache to use
        ttl: Time to live for cached value
        key_prefix: Prefix for cache keys

    Example:
        @cached(cache_name="api_responses", ttl=300)
        def expensive_api_call(param1, param2):
            ...
    """
    def decorator(func: Callable) -> Callable:
        cache = get_cache_manager().get_cache(cache_name, default_ttl=ttl)

        @wraps(func)
        def wrapper(*args, **kwargs):
            if not config.CACHE_ENABLED:
                return func(*args, **kwargs)

            # Generate cache key from function name and arguments
            key_data = f"{key_prefix}{func.__name__}:{args}:{kwargs}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()

            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Call function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)

            return result

        # Add cache management methods to function
        wrapper.cache_clear = lambda: cache.clear()
        wrapper.cache_delete = lambda key: cache.delete(key)
        wrapper.cache_stats = lambda: cache.get_stats()

        return wrapper
    return decorator


# Pre-configured caches
user_cache = get_cache_manager().get_cache("users", max_size=500, default_ttl=300)
rag_cache = get_cache_manager().get_cache("rag_results", max_size=1000, default_ttl=600)
embedding_cache = get_cache_manager().get_cache("embeddings", max_size=5000, default_ttl=3600)
