from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import json
import secrets

from backend.config import config
from backend.logger import get_logger
from backend.redis_cache import get_redis_cache
from backend.services import get_storage_backend

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.utcnow()

class ShareService:
    def __init__(self):
        self.storage = get_storage_backend()
        self._share_cache: dict[str, dict] = {}
        self.user_data_root = Path(config.USER_DATA_ROOT)
        try:
            self.redis = get_redis_cache()
        except Exception as exc:
            logger.warning("Share service using in-memory fallback; Redis unavailable: %s", exc)
            self.redis = None

    def _share_key(self, share_id: str) -> str:
        return f"chat_share:{share_id}"

    def _share_history_file(self, username: str) -> Path:
        return self.user_data_root / username / "share_history" / "shares.jsonl"

    def _persist_share(self, share_data: dict, ttl_seconds: int) -> None:
        share_id = share_data["share_id"]
        self._share_cache[share_id] = share_data
        if self.redis is not None:
            self.redis.set(self._share_key(share_id), share_data, ttl=ttl_seconds)

    def _load_share(self, share_id: str) -> Optional[dict]:
        cached = self._share_cache.get(share_id)
        if cached is not None:
            return cached
        if self.redis is None:
            return None
        share_data = self.redis.get(self._share_key(share_id))
        if isinstance(share_data, dict):
            self._share_cache[share_id] = share_data
            return share_data
        return None

    def _delete_share(self, share_id: str) -> None:
        self._share_cache.pop(share_id, None)
        if self.redis is not None:
            self.redis.delete(self._share_key(share_id))

    def _append_share_history(self, username: str, payload: dict) -> None:
        history_file = self._share_history_file(username)
        history_file.parent.mkdir(parents=True, exist_ok=True)
        with history_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

    def create_share_link(
        self,
        username: str,
        session_id: str,
        expires_in_hours: int = 168,  # Default 7 days
    ) -> dict:
        """Create a share link for a chat session."""
        session = self.storage.load_chat_session(username, session_id)
        if session is None:
            raise ValueError("Session not found")

        share_id = secrets.token_urlsafe(16)
        created_at = _utcnow()
        expires_at = created_at + timedelta(hours=expires_in_hours)
        ttl_seconds = max(1, int((expires_at - created_at).total_seconds()))
        share_data = {
            "share_id": share_id,
            "username": username,
            "session_id": session_id,
            "session_data": session.to_dict(),
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        self._persist_share(share_data, ttl_seconds)
        self._append_share_history(
            username,
            {
                "share_id": share_id,
                "session_id": session_id,
                "channel": "link_created",
                "created_at": created_at.isoformat(),
                "expires_at": expires_at.isoformat(),
            },
        )

        return {
            "share_id": share_id,
            "share_url": f"/shared/{share_id}",
            "expires_at": expires_at.isoformat(),
        }

    def get_shared_session(self, share_id: str) -> Optional[dict]:
        """Get a shared session by share ID."""
        share_data = self._load_share(share_id)
        if share_data is None:
            return None

        expires_at = datetime.fromisoformat(share_data["expires_at"])
        if expires_at < _utcnow():
            self._delete_share(share_id)
            return None

        return share_data

    def get_shared_session_info(self, share_id: str) -> Optional[dict]:
        share_data = self.get_shared_session(share_id)
        if share_data is None:
            return None

        session_data = share_data.get("session_data") or {}
        messages = session_data.get("messages") or []
        return {
            "title": session_data.get("title") or "Shared chat",
            "message_count": len(messages) if isinstance(messages, list) else 0,
            "created_at": share_data.get("created_at") or session_data.get("created_at"),
            "expires_at": share_data["expires_at"],
        }

    def revoke_share(self, share_id: str, username: str) -> bool:
        """Revoke a share link. Only the owner may revoke their own share."""
        share_data = self._load_share(share_id)
        if share_data is None:
            return False
        if share_data["username"] != username:
            return False
        self._delete_share(share_id)
        return True

    def log_share_action(
        self,
        *,
        username: str,
        session_id: str,
        channel: str,
        share_id: Optional[str] = None,
    ) -> None:
        self._append_share_history(
            username,
            {
                "share_id": share_id,
                "session_id": session_id,
                "channel": channel,
                "created_at": _utcnow().isoformat(),
            },
        )

    def cleanup_expired_shares(self) -> int:
        """Remove expired share links from cache."""
        expired_ids = [
            sid
            for sid, data in self._share_cache.items()
            if datetime.fromisoformat(data["expires_at"]) < _utcnow()
        ]
        for sid in expired_ids:
            self._delete_share(sid)
        return len(expired_ids)


# Global share service instance
_share_service: Optional[ShareService] = None


def get_share_service() -> ShareService:
    global _share_service
    if _share_service is None:
        _share_service = ShareService()
    return _share_service
