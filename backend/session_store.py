"""
Session Store using Redis
Manages JWT refresh tokens and user sessions in Redis for scalability
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import json

from .config import config
from .logger import get_logger
from .redis_cache import get_redis_cache

logger = get_logger(__name__)


class RedisSessionStore:
    """Redis-backed session store for JWT refresh tokens"""

    def __init__(self):
        self.redis = get_redis_cache()
        self.session_prefix = "session:"
        self.refresh_token_prefix = "refresh_token:"
        self.user_sessions_prefix = "user_sessions:"

    def _session_key(self, token_id: str) -> str:
        """Generate session key"""
        return f"{self.session_prefix}{token_id}"

    def _refresh_token_key(self, token_id: str) -> str:
        """Generate refresh token key"""
        return f"{self.refresh_token_prefix}{token_id}"

    def _user_sessions_key(self, username: str) -> str:
        """Generate user sessions list key"""
        return f"{self.user_sessions_prefix}{username}"

    def store_refresh_token(
        self,
        token_id: str,
        username: str,
        token: str,
        ttl: int = None
    ) -> bool:
        """
        Store refresh token in Redis

        Args:
            token_id: Unique token identifier
            username: Username associated with token
            token: The refresh token
            ttl: Time-to-live in seconds (default: from config)

        Returns:
            True if successful
        """
        try:
            ttl = ttl or (config.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)

            token_data = {
                "token": token,
                "username": username,
                "created_at": datetime.utcnow().isoformat(),
            }

            key = self._refresh_token_key(token_id)
            success = self.redis.set(key, token_data, ttl=ttl)

            if success:
                # Add to user's session list
                user_key = self._user_sessions_key(username)
                self.redis.client.sadd(user_key, token_id)
                self.redis.expire(user_key, ttl)

                logger.debug(f"Stored refresh token for {username}")

            return success

        except Exception as e:
            logger.error(f"Error storing refresh token: {e}")
            return False

    def get_refresh_token(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        Get refresh token data

        Args:
            token_id: Token identifier

        Returns:
            Token data or None if not found
        """
        try:
            key = self._refresh_token_key(token_id)
            return self.redis.get(key)

        except Exception as e:
            logger.error(f"Error getting refresh token: {e}")
            return None

    def delete_refresh_token(self, token_id: str, username: str = None) -> bool:
        """
        Delete refresh token

        Args:
            token_id: Token identifier
            username: Username (optional, for cleanup)

        Returns:
            True if deleted
        """
        try:
            key = self._refresh_token_key(token_id)
            success = self.redis.delete(key)

            if success and username:
                # Remove from user's session list
                user_key = self._user_sessions_key(username)
                self.redis.client.srem(user_key, token_id)

                logger.debug(f"Deleted refresh token for {username}")

            return success

        except Exception as e:
            logger.error(f"Error deleting refresh token: {e}")
            return False

    def get_user_sessions(self, username: str) -> list:
        """
        Get all active session tokens for a user

        Args:
            username: Username

        Returns:
            List of token IDs
        """
        try:
            key = self._user_sessions_key(username)
            sessions = self.redis.client.smembers(key)
            return [s.decode() if isinstance(s, bytes) else s for s in sessions]

        except Exception as e:
            logger.error(f"Error getting user sessions: {e}")
            return []

    def revoke_all_user_sessions(self, username: str) -> int:
        """
        Revoke all sessions for a user

        Args:
            username: Username

        Returns:
            Number of sessions revoked
        """
        try:
            sessions = self.get_user_sessions(username)
            count = 0

            for token_id in sessions:
                if self.delete_refresh_token(token_id, username):
                    count += 1

            # Clear the user sessions set
            user_key = self._user_sessions_key(username)
            self.redis.delete(user_key)

            logger.info(f"Revoked {count} sessions for {username}")
            return count

        except Exception as e:
            logger.error(f"Error revoking user sessions: {e}")
            return 0

    def cleanup_expired_sessions(self) -> int:
        """
        Cleanup expired sessions
        Note: Redis handles this automatically with TTL

        Returns:
            0 (Redis auto-expires keys)
        """
        logger.debug("Redis automatically handles session expiration via TTL")
        return 0

    def get_session_count(self, username: str) -> int:
        """
        Get number of active sessions for a user

        Args:
            username: Username

        Returns:
            Number of active sessions
        """
        try:
            key = self._user_sessions_key(username)
            return self.redis.client.scard(key)

        except Exception as e:
            logger.error(f"Error getting session count: {e}")
            return 0

    def limit_user_sessions(self, username: str, max_sessions: int = 5) -> bool:
        """
        Enforce maximum number of concurrent sessions per user

        Args:
            username: Username
            max_sessions: Maximum allowed sessions

        Returns:
            True if within limit
        """
        try:
            count = self.get_session_count(username)

            if count >= max_sessions:
                logger.warning(f"User {username} has {count} sessions (max: {max_sessions})")
                # Get all sessions and remove oldest
                sessions = self.get_user_sessions(username)
                if sessions:
                    # Remove the first session (oldest)
                    oldest = sessions[0]
                    self.delete_refresh_token(oldest, username)
                    logger.info(f"Removed oldest session for {username}")

            return True

        except Exception as e:
            logger.error(f"Error limiting user sessions: {e}")
            return False


# Singleton instance
_session_store = None


def get_session_store() -> RedisSessionStore:
    """Get singleton session store instance"""
    global _session_store
    if _session_store is None:
        _session_store = RedisSessionStore()
    return _session_store
