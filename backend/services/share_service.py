from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
import secrets

from backend.services import get_storage_backend
from backend.services.models import ChatSession


class ShareService:
    def __init__(self):
        self.storage = get_storage_backend()
        self._share_cache: dict[str, dict] = {}  # In-memory cache for shares

    def create_share_link(
        self,
        username: str,
        session_id: str,
        expires_in_hours: int = 168,  # Default 7 days
    ) -> dict:
        """Create a share link for a chat session."""
        # Load the session
        session = self.storage.load_chat_session(username, session_id)
        if session is None:
            raise ValueError("Session not found")

        # Generate unique share ID
        share_id = secrets.token_urlsafe(16)

        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

        # Create share record
        share_data = {
            "share_id": share_id,
            "username": username,
            "session_id": session_id,
            "session_data": session.to_dict(),
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        # Store in cache (in production, use DynamoDB)
        self._share_cache[share_id] = share_data

        return {
            "share_id": share_id,
            "share_url": f"/shared/{share_id}",
            "expires_at": expires_at.isoformat(),
        }

    def get_shared_session(self, share_id: str) -> Optional[dict]:
        """Get a shared session by share ID."""
        # Check cache first
        if share_id in self._share_cache:
            share_data = self._share_cache[share_id]

            # Check if expired
            expires_at = datetime.fromisoformat(share_data["expires_at"])
            if expires_at < datetime.utcnow():
                del self._share_cache[share_id]
                return None

            return share_data

        return None

    def revoke_share(self, share_id: str) -> bool:
        """Revoke a share link."""
        if share_id in self._share_cache:
            del self._share_cache[share_id]
            return True
        return False

    def cleanup_expired_shares(self) -> int:
        """Remove expired share links from cache."""
        expired_ids = [
            sid
            for sid, data in self._share_cache.items()
            if datetime.fromisoformat(data["expires_at"]) < datetime.utcnow()
        ]
        for sid in expired_ids:
            del self._share_cache[sid]
        return len(expired_ids)


# Global share service instance
_share_service: Optional[ShareService] = None


def get_share_service() -> ShareService:
    global _share_service
    if _share_service is None:
        _share_service = ShareService()
    return _share_service
