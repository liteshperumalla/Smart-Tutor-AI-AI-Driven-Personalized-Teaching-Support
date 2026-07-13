"""
Per-User Rate Limiter
Implements rate limiting based on authenticated user (not just IP address)
Uses Redis for distributed rate limiting across multiple servers
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

import os

from .config import config
from .logger import get_logger
from .redis_cache import RedisCache

logger = get_logger(__name__)

# Global rate limiter instance (for slowapi decorators)
# This is defined here to avoid circular imports between main.py and routes
# Disabled in test environment so the test suite doesn't hit rate limits
_slowapi_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"
limiter = Limiter(key_func=get_remote_address, enabled=_slowapi_enabled)

# Model family mapping: substring in model ID → family tier
MODEL_FAMILY_MAP = {
    "llama": "default",
    "claude-3-haiku": "fast",
    "claude-3-5-sonnet": "pro",
    "claude-sonnet": "pro",
    "claude-opus": "admin",
}


def get_model_family(model_id: str) -> str:
    """Map a Bedrock model ID to a rate-limit family tier."""
    if not model_id:
        return "default"
    model_lower = model_id.lower()
    for pattern, family in MODEL_FAMILY_MAP.items():
        if pattern in model_lower:
            return family
    return "default"


def get_model_limit(family: str) -> int:
    """Get the per-user hourly request limit for a model family."""
    limits = {
        "default": config.MODEL_RATE_LIMIT_DEFAULT,
        "fast": config.MODEL_RATE_LIMIT_FAST,
        "pro": config.MODEL_RATE_LIMIT_PRO,
        "admin": config.MODEL_RATE_LIMIT_ADMIN,
    }
    return limits.get(family, config.MODEL_RATE_LIMIT_DEFAULT)


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
        _env_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"
        self.enabled = _env_enabled and config.USE_REDIS_CACHE and redis_cache is not None

        # Rate limit settings (requests per window)
        self.default_limit = config.RATE_LIMIT_PER_USER_REQUESTS
        self.window_seconds = config.RATE_LIMIT_PER_USER_WINDOW

        if self.enabled:
            logger.info(f"Per-user rate limiter initialized: {self.default_limit} requests per {self.window_seconds}s")
        else:
            logger.warning("Per-user rate limiter disabled (Redis not available)")

    def _get_username_from_token(self, request: Request) -> Optional[str]:
        """
        Extract a stable user identifier from a *validated* JWT for rate limiting.
        Checks both Authorization header and HttpOnly cookies.

        SECURITY: The JWT is decoded and its signature verified before use.
        This prevents attackers from rotating arbitrary strings to evade
        per-user rate limits.  We key on the JTI claim (unique per token)
        so that a user cannot bypass limits by re-logging in.
        """
        import jwt as pyjwt

        token = None

        # Check Authorization header first
        auth_header = request.headers.get("Authorization")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]

        # Fall back to HttpOnly cookie
        if not token:
            token = request.cookies.get("access_token")

        if not token:
            return None

        # Validate the JWT before trusting its claims
        try:
            # RS256 requires the RSA public key; HS256 uses the secret string
            if config.JWT_ALGORITHM == "RS256":
                from pathlib import Path
                key = Path(config.JWT_PUBLIC_KEY_PATH).read_text()
            else:
                key = config.JWT_SECRET_KEY

            payload = pyjwt.decode(
                token,
                key,
                algorithms=[config.JWT_ALGORITHM],
                audience=config.JWT_AUDIENCE,
                issuer=config.JWT_ISSUER,
            )
            # Prefer JTI (unique per token), fall back to sub (user id)
            jti = payload.get("jti")
            if jti:
                return f"jti_{jti}"
            sub = payload.get("sub")
            if sub:
                return f"sub_{sub}"
            return None
        except pyjwt.InvalidTokenError:
            # Invalid/expired/forged token — fall back to IP-based limiting
            return None

    def _get_rate_limit_key(
        self, username: str, endpoint: str, scope: Optional[str] = None
    ) -> str:
        """Generate Redis key for rate limiting"""
        suffix = f":{scope}" if scope else ""
        return f"rate_limit:user:{username}:{endpoint}{suffix}"

    async def check_rate_limit(
        self,
        request: Request,
        limit: Optional[int] = None,
        window: Optional[int] = None,
        scope: Optional[str] = None,
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
        # WebSocket connections (e.g. ws_chat.py) share Request's .headers/
        # .cookies/.url via the common HTTPConnection base class, but have
        # no .method. .url.path also isn't usable there since it embeds a
        # per-connection session_id -- keying on it would let a user bypass
        # the limit by opening a new session per burst. Collapse to a
        # literal "WS" identifier instead, so callers from that context
        # rely solely on the caller-supplied `scope` to differentiate.
        method = getattr(request, "method", None)
        endpoint = f"{method}:{request.url.path}" if method else "WS"

        # Generate rate limit key
        key = self._get_rate_limit_key(username, endpoint, scope=scope)

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
            logger.warning(f"Rate limiter error: {e}")
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

        # WebSocket connections (e.g. ws_chat.py) share Request's .headers/
        # .cookies/.url via the common HTTPConnection base class, but have
        # no .method. .url.path also isn't usable there since it embeds a
        # per-connection session_id -- keying on it would let a user bypass
        # the limit by opening a new session per burst. Collapse to a
        # literal "WS" identifier instead, so callers from that context
        # rely solely on the caller-supplied `scope` to differentiate.
        method = getattr(request, "method", None)
        endpoint = f"{method}:{request.url.path}" if method else "WS"
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
            logger.warning(f"Error getting rate limit status: {e}")
            return {"enabled": True, "error": "Rate limit status unavailable"}

    async def check_model_rate_limit(self, request: Request, model_id: str) -> None:
        """
        Check per-model rate limit for the authenticated user.

        Uses a separate Redis key per user+model-family so expensive models
        (Opus, Sonnet) have lower hourly quotas than cheap models (Haiku, Llama).
        """
        if not self.enabled:
            return

        username = self._get_username_from_token(request)
        if not username:
            return

        family = get_model_family(model_id)
        limit = get_model_limit(family)
        window_secs = config.MODEL_RATE_LIMIT_WINDOW
        key = f"rate_limit:model:{username}:{family}"

        try:
            redis_client = self.redis.client
            current_count = redis_client.eval(
                self._RATE_LIMIT_LUA_SCRIPT, 1, key, window_secs, limit
            )

            if current_count > limit:
                ttl = redis_client.ttl(key)
                retry_after = ttl if ttl > 0 else window_secs
                logger.warning(
                    f"Model rate limit exceeded for {username} on {family}: {current_count}/{limit}"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Model rate limit exceeded",
                        "model_family": family,
                        "retry_after": retry_after,
                        "limit": limit,
                        "remaining": 0,
                    },
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Model rate limiter error: {e}")

    async def get_all_model_limits(self, request: Request) -> dict:
        """Return rate-limit status for every model family for this user."""
        if not self.enabled:
            return {"enabled": False}

        username = self._get_username_from_token(request)
        if not username:
            return {"enabled": True, "authenticated": False}

        families = ["default", "fast", "pro", "admin"]
        window_secs = config.MODEL_RATE_LIMIT_WINDOW
        models: dict = {}

        try:
            redis_client = self.redis.client
            for family in families:
                key = f"rate_limit:model:{username}:{family}"
                limit = get_model_limit(family)
                hash_data = redis_client.hgetall(key)
                used = int(hash_data.get(b"count", 0))
                ttl = redis_client.ttl(key)
                models[family] = {
                    "limit": limit,
                    "used": used,
                    "remaining": max(0, limit - used),
                    "reset_in": ttl if ttl > 0 else window_secs,
                }
        except Exception as e:
            logger.warning(f"Error getting model limits: {e}")
            return {"enabled": True, "error": "Model limit status unavailable"}

        return {"enabled": True, "models": models}


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
                logger.warning(f"Failed to initialize per-user rate limiter with Redis: {e}")
                _rate_limiter = PerUserRateLimiter(None)
        else:
            _rate_limiter = PerUserRateLimiter(None)

    return _rate_limiter
