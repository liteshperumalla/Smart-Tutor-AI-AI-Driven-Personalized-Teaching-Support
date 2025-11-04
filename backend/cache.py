"""
Caching Layer
Provides in-memory caching with TTL and size limits
"""

import time
import hashlib
import pickle
from typing import Any, Optional, Callable
from collections import OrderedDict
from functools import wraps
from threading import RLock

from .config import config
from .logger import get_logger

logger = get_logger(__name__)


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


class CacheManager:
    """Centralized cache manager with multiple cache instances"""

    def __init__(self):
        self._caches: dict[str, LRUCache] = {}
        self._lock = RLock()

    def get_cache(self, name: str, max_size: Optional[int] = None,
                 default_ttl: Optional[int] = None) -> LRUCache:
        """
        Get or create a named cache

        Args:
            name: Cache name
            max_size: Maximum cache size
            default_ttl: Default TTL for entries

        Returns:
            LRUCache instance
        """
        with self._lock:
            if name not in self._caches:
                self._caches[name] = LRUCache(max_size, default_ttl)
                logger.info(f"Created cache: {name}")
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
