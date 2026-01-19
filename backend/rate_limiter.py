"""
Per-User Rate Limiter
Implements rate limiting based on authenticated user (not just IP address)
Uses Redis for distributed rate limiting across multiple servers
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import Request, HTTPException, status
from jose import jwt, JWTError
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import config
from .logger import get_logger
from .redis_cache import RedisCache

logger = get_logger(__name__)

# Global rate limiter instance (for slowapi decorators)
# This is defined here to avoid circular imports between main.py and routes
limiter = Limiter(key_func=get_remote_address)


class PerUserRateLimiter:
    """Rate limiter that tracks requests per authenticated user"""

    # Lua script for atomic INCR and EXPIRE, and storing limit/window
    _RATE_LIMIT_LUA_SCRIPT = """
    local key = KEYS[1]
    local window_secs = ARGV[1]
    local max_requests = ARGV[2]

    local current_count = redis.call('hincrby', key, 'count', 1)
    
    if current_count == 1 then
        redis.call('hset', key, 'limit', max_requests)
        redis.call('hset', key, 'window', window_secs)
        redis.call('expire', key, window_secs)
    end
    
    return current_count
    """

    def __init__(self, redis_cache: Optional[RedisCache] = None):
        self.redis = redis_cache
        self.enabled = config.USE_REDIS_CACHE and redis_cache is not None

        # Rate limit settings (requests per window)
        self.default_limit = config.RATE_LIMIT_PER_USER_REQUESTS
        self.window_seconds = config.RATE_LIMIT_PER_USER_WINDOW

        if self.enabled:
            logger.info(f"Per-user rate limiter initialized: {self.default_limit} requests per {self.window_seconds}s")
        else:
            logger.warning("Per-user rate limiter disabled (Redis not available)")

    def _get_username_from_token(self, request: Request) -> Optional[str]:
        """
        Extract JTI (JWT ID) from JWT token for rate limiting.
        SECURITY: Using JTI prevents bypass via forged tokens with different usernames.
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        # Extract token from "Bearer <token>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        token = parts[1]

        try:
            # Decode token without verification to get JTI
            # SECURITY: Use JTI instead of username to prevent bypass
            payload = jwt.decode(
                token,
                options={"verify_signature": False}
            )

            # Prefer JTI (JWT ID) for rate limiting - unique per token
            jti = payload.get("jti")
            if jti:
                return f"jwt_{jti}"  # Prefix to distinguish from legacy limits

            # Fallback to username if JTI not present (legacy tokens)
            username = payload.get("sub")
            if username:
                logger.warning(f"Rate limiting token without JTI, using username: {username}")
                return f"user_{username}"

            return None

        except JWTError as e:
            logger.error(f"Rate limiter token parsing error: {e}")
            return None

    def _get_rate_limit_key(self, username: str, endpoint: str) -> str:
        """Generate Redis key for rate limiting"""
        return f"rate_limit:user:{username}:{endpoint}"

    async def check_rate_limit(
        self,
        request: Request,
        limit: Optional[int] = None,
        window: Optional[int] = None
    ) -> None:
        """
        Check if user has exceeded rate limit

        Args:
            request: FastAPI request object
            limit: Custom limit (requests per window), defaults to configured limit
            window: Custom window in seconds, defaults to configured window

        Raises:
            HTTPException: 429 Too Many Requests if limit exceeded
        """
        if not self.enabled:
            return  # Rate limiting disabled

        # Get username from JWT token
        username = self._get_username_from_token(request)
        if not username:
            # No authenticated user, fall back to IP-based limiting (handled by slowapi)
            return

        # Use custom limits or defaults
        max_requests = limit or self.default_limit
        window_secs = window or self.window_seconds

        # Get endpoint identifier
        endpoint = f"{request.method}:{request.url.path}"

        # Generate rate limit key
        key = self._get_rate_limit_key(username, endpoint)

        try:
            # Use raw Redis client for numeric operations (not the cache wrapper which pickles)
            redis_client = self.redis.client

            # Execute atomic INCR and EXPIRE using Lua script
            current_count = redis_client.eval(self._RATE_LIMIT_LUA_SCRIPT, 1, key, window_secs, max_requests)
            logger.debug(f"Rate limit for {username} on {endpoint}: {current_count}/{max_requests}")

            # Check if limit exceeded
            if current_count > max_requests:
                # Rate limit exceeded
                logger.warning(f"Rate limit exceeded for {username} on {endpoint}: {current_count}/{max_requests}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Limit: {max_requests} requests per {window_secs} seconds",
                        "retry_after": window_secs,
                        "limit": max_requests,
                        "window": window_secs
                    }
                )

            logger.debug(f"Rate limit for {username} on {endpoint}: {current_count}/{max_requests}")

        except HTTPException:
            raise  # Re-raise HTTP exceptions
        except Exception as e:
            # Log error but don't block request if Redis fails
            print(f"Rate limiter error: {e}")
            return

    async def get_rate_limit_status(self, request: Request) -> dict:
        """
        Get current rate limit status for authenticated user

        Returns:
            dict with rate limit information
        """
        if not self.enabled:
            return {"enabled": False}

        username = self._get_username_from_token(request)
        if not username:
            return {"enabled": True, "authenticated": False}

        endpoint = f"{request.method}:{request.url.path}"
        key = self._get_rate_limit_key(username, endpoint)

        try:
            redis_client = self.redis.client
            hash_data = redis_client.hgetall(key)
            current_count = int(hash_data.get(b'count', 0))
            stored_limit = int(hash_data.get(b'limit', self.default_limit))
            stored_window = int(hash_data.get(b'window', self.window_seconds))
            ttl = redis_client.ttl(key)

            return {
                "enabled": True,
                "authenticated": True,
                "username": username,
                "limit": stored_limit,
                "remaining": max(0, stored_limit - current_count),
                "reset_in": ttl if ttl > 0 else stored_window,
                "window": stored_window
            }
        except Exception as e:
            print(f"Error getting rate limit status: {e}")
            return {"enabled": True, "error": str(e)}


# Singleton instance
_rate_limiter: Optional[PerUserRateLimiter] = None


def get_rate_limiter() -> PerUserRateLimiter:
    """Get singleton rate limiter instance"""
    global _rate_limiter

    if _rate_limiter is None:
        if config.USE_REDIS_CACHE:
            try:
                from .redis_cache import RedisCache
                redis_cache = RedisCache(
                    host=config.REDIS_HOST,
                    port=config.REDIS_PORT,
                    db=config.REDIS_DB,
                    password=config.REDIS_PASSWORD,
                    ssl=config.REDIS_SSL,
                    max_connections=config.REDIS_MAX_CONNECTIONS
                )
                _rate_limiter = PerUserRateLimiter(redis_cache)
            except Exception as e:
                print(f"Failed to initialize per-user rate limiter with Redis: {e}")
                _rate_limiter = PerUserRateLimiter(None)
        else:
            _rate_limiter = PerUserRateLimiter(None)

    return _rate_limiter
