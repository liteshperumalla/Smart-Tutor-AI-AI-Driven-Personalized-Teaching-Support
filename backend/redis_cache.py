"""
Redis Cache Implementation
Production-grade distributed caching using Redis
"""

import json
import time
from typing import Any, Optional
from threading import RLock

import redis
from redis.connection import ConnectionPool

from .config import config
from .logger import get_logger

logger = get_logger(__name__)


class RedisCache:
    """Redis-backed cache with TTL support"""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        password: Optional[str] = None,
        ssl: Optional[bool] = None,
        max_connections: Optional[int] = None,
        default_ttl: int = 300,
    ):
        """
        Initialize Redis cache

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password (if required)
            ssl: Use SSL/TLS connection
            max_connections: Maximum number of connections in pool
            default_ttl: Default time-to-live in seconds
        """
        self.default_ttl = default_ttl
        self._hits = 0
        self._misses = 0
        self._lock = RLock()

        # Use config values if not provided
        host = host or config.REDIS_HOST
        port = port or config.REDIS_PORT
        db = db if db is not None else config.REDIS_DB
        # Only use password if explicitly provided and non-empty
        password = password if password else (config.REDIS_PASSWORD if config.REDIS_PASSWORD else None)
        ssl = ssl if ssl is not None else config.REDIS_SSL
        max_connections = max_connections or config.REDIS_MAX_CONNECTIONS

        # Create connection pool
        pool_kwargs = {
            "host": host,
            "port": port,
            "db": db,
            "max_connections": max_connections,
            "decode_responses": False,  # We'll handle serialization
        }

        if password:
            pool_kwargs["password"] = password

        if ssl:
            pool_kwargs["ssl"] = True
            pool_kwargs["ssl_cert_reqs"] = "required"

        self.pool = ConnectionPool(**pool_kwargs)
        self.client = redis.Redis(connection_pool=self.pool)

        # Test connection
        try:
            self.client.ping()
            logger.info(f"Redis cache connected: {host}:{port} (db={db})")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage using JSON (safe, no arbitrary code execution)"""
        return json.dumps(value).encode("utf-8")

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage using JSON"""
        return json.loads(data.decode("utf-8"))

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        try:
            data = self.client.get(key)

            if data is None:
                with self._lock:
                    self._misses += 1
                logger.debug(f"Cache miss: {key}")
                return None

            with self._lock:
                self._hits += 1

            logger.debug(f"Cache hit: {key}")
            return self._deserialize(data)

        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            data = self._serialize(value)
            expire_time = ttl if ttl is not None else self.default_ttl

            if expire_time > 0:
                self.client.setex(key, expire_time, data)
            else:
                self.client.set(key, data)

            logger.debug(f"Cache set: {key} (ttl={expire_time}s)")
            return True

        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete entry from cache

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        try:
            result = self.client.delete(key)
            if result > 0:
                logger.debug(f"Cache deleted: {key}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Error checking cache key {key}: {e}")
            return False

    def clear(self, pattern: str = "*") -> int:
        """
        Clear cache entries matching pattern

        Args:
            pattern: Key pattern (default: all keys)

        Returns:
            Number of keys deleted
        """
        try:
            keys = self.client.keys(pattern)
            if keys:
                count = self.client.delete(*keys)
                logger.info(f"Cleared {count} cache entries matching '{pattern}'")
                return count
            return 0

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0

    def get_ttl(self, key: str) -> int:
        """
        Get remaining time-to-live for a key

        Args:
            key: Cache key

        Returns:
            TTL in seconds, -1 if no TTL, -2 if key doesn't exist
        """
        try:
            return self.client.ttl(key)
        except Exception as e:
            logger.error(f"Error getting TTL for {key}: {e}")
            return -2

    def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration time for a key

        Args:
            key: Cache key
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        try:
            return bool(self.client.expire(key, ttl))
        except Exception as e:
            logger.error(f"Error setting expiration for {key}: {e}")
            return False

    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment a counter
        Note: The key must not already contain a pickled value

        Args:
            key: Cache key
            amount: Amount to increment

        Returns:
            New value or None on error
        """
        try:
            return self.client.incrby(key, amount)
        except Exception as e:
            print(f"Error incrementing {key}: {e}")
            return None

    def get_stats(self) -> dict:
        """Get cache statistics"""
        try:
            with self._lock:
                total_requests = self._hits + self._misses
                hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

            info = self.client.info("stats")

            return {
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': f"{hit_rate:.2f}%",
                'total_keys': self.client.dbsize(),
                'used_memory': info.get('used_memory_human', 'N/A'),
                'connected_clients': info.get('connected_clients', 0),
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

    def ping(self) -> bool:
        """Test Redis connection"""
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    def close(self):
        """Close Redis connection"""
        try:
            self.client.close()
            logger.info("Redis cache connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")


# Singleton instance
_redis_cache = None


def get_redis_cache() -> RedisCache:
    """Get singleton Redis cache instance"""
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisCache(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            password=config.REDIS_PASSWORD if config.REDIS_PASSWORD else None,
            ssl=config.REDIS_SSL,
            max_connections=config.REDIS_MAX_CONNECTIONS,
            default_ttl=config.CACHE_TTL,
        )
    return _redis_cache


def get_cache():
    """
    Get cache instance - returns Redis or in-memory based on configuration

    Returns:
        RedisCache if USE_REDIS_CACHE is True, otherwise LRUCache
    """
    if config.USE_REDIS_CACHE:
        return get_redis_cache()
    else:
        from .cache import get_cache_manager
        return get_cache_manager().get_cache("default")
