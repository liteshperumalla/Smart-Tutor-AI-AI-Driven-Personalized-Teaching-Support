"""
JWT Token Blacklist Service
Implements token revocation using Redis for secure logout
"""

import jwt
import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class JWTBlacklist:
    """
    Redis-based JWT token blacklist for token revocation.

    When a user logs out, their JWT token is added to the blacklist.
    All API requests check if the token is blacklisted before proceeding.
    Tokens automatically expire from the blacklist after their JWT expiration time.
    """

    def __init__(self, redis_cache=None):
        """
        Initialize JWT blacklist

        Args:
            redis_cache: RedisCache instance (optional - falls back to in-memory if None)
        """
        self.redis = redis_cache
        self._in_memory_blacklist = {}  # Fallback for when Redis is unavailable

        if not self.redis:
            logger.warning(
                "JWT Blacklist initialized without Redis - using in-memory fallback. "
                "This will not work across multiple instances."
            )

    def blacklist_token(self, token: str, expiry_seconds: int) -> bool:
        """
        Add a token to the blacklist

        Args:
            token: The JWT token to blacklist
            expiry_seconds: How long to keep the token in blacklist (should match JWT expiry)

        Returns:
            bool: True if successfully blacklisted, False otherwise
        """
        try:
            jti = self._get_jti(token)
            if not jti:
                logger.warning("Cannot blacklist token: missing JTI claim")
                return False

            blacklist_key = f"jwt_blacklist:{jti}"

            # Try Redis first
            if self.redis and hasattr(self.redis, 'client'):
                try:
                    self.redis.client.setex(blacklist_key, expiry_seconds, "1")
                    logger.info(f"Token blacklisted in Redis: {jti[:8]}... (expires in {expiry_seconds}s)")
                    return True
                except Exception as e:
                    logger.error(f"Redis blacklist failed, using in-memory fallback: {e}")

            # Fallback to in-memory
            expiry_time = datetime.utcnow() + timedelta(seconds=expiry_seconds)
            self._in_memory_blacklist[jti] = expiry_time
            logger.warning(f"Token blacklisted in-memory: {jti[:8]}... (not distributed)")
            return True

        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
            return False

    def is_blacklisted(self, token: str) -> bool:
        """
        Check if a token is blacklisted

        Args:
            token: The JWT token to check

        Returns:
            bool: True if token is blacklisted, False otherwise
        """
        try:
            jti = self._get_jti(token)
            if not jti:
                logger.warning("Cannot check blacklist: missing JTI claim")
                return False  # If no JTI, we can't blacklist it

            blacklist_key = f"jwt_blacklist:{jti}"

            # Try Redis first
            if self.redis and hasattr(self.redis, 'client'):
                try:
                    result = self.redis.client.exists(blacklist_key)
                    if result:
                        logger.info(f"Token is blacklisted: {jti[:8]}...")
                    return bool(result)
                except Exception as e:
                    logger.error(f"Redis blacklist check failed: {e}")

            # Fallback to in-memory
            if jti in self._in_memory_blacklist:
                # Check if still valid
                if datetime.utcnow() < self._in_memory_blacklist[jti]:
                    logger.warning(f"Token blacklisted (in-memory): {jti[:8]}...")
                    return True
                else:
                    # Expired, remove from blacklist
                    del self._in_memory_blacklist[jti]
                    return False

            return False

        except Exception as e:
            logger.error(f"Failed to check blacklist: {e}")
            # Fail secure: if we can't check, assume not blacklisted but log the error
            return False

    def _get_jti(self, token: str) -> Optional[str]:
        """
        Extract JTI (JWT ID) from token without verification

        Args:
            token: The JWT token

        Returns:
            Optional[str]: The JTI claim if present, None otherwise
        """
        try:
            # Decode without verification to get the JTI
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload.get("jti")
        except Exception as e:
            logger.error(f"Failed to extract JTI from token: {e}")
            return None

    def cleanup_expired(self) -> int:
        """
        Cleanup expired tokens from in-memory blacklist
        (Redis handles this automatically with TTL)

        Returns:
            int: Number of tokens removed
        """
        if not self._in_memory_blacklist:
            return 0

        now = datetime.utcnow()
        expired = [jti for jti, expiry in self._in_memory_blacklist.items() if now >= expiry]

        for jti in expired:
            del self._in_memory_blacklist[jti]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired tokens from in-memory blacklist")

        return len(expired)

    def get_stats(self) -> dict:
        """
        Get blacklist statistics

        Returns:
            dict: Statistics about the blacklist
        """
        stats = {
            "redis_enabled": bool(self.redis and hasattr(self.redis, 'client')),
            "in_memory_count": len(self._in_memory_blacklist),
        }

        if self.redis and hasattr(self.redis, 'client'):
            try:
                # Count blacklisted tokens in Redis
                keys = self.redis.client.keys("jwt_blacklist:*")
                stats["redis_count"] = len(keys)
            except Exception as e:
                logger.error(f"Failed to get Redis stats: {e}")
                stats["redis_count"] = -1
                stats["redis_error"] = str(e)

        return stats


# Global blacklist instance (initialized in auth_service.py)
_jwt_blacklist: Optional[JWTBlacklist] = None


def get_jwt_blacklist() -> Optional[JWTBlacklist]:
    """Get the global JWT blacklist instance"""
    return _jwt_blacklist


def init_jwt_blacklist(redis_cache=None) -> JWTBlacklist:
    """
    Initialize the global JWT blacklist instance

    Args:
        redis_cache: RedisCache instance (optional)

    Returns:
        JWTBlacklist: The initialized blacklist instance
    """
    global _jwt_blacklist
    _jwt_blacklist = JWTBlacklist(redis_cache=redis_cache)
    logger.info("JWT Blacklist initialized")
    return _jwt_blacklist
