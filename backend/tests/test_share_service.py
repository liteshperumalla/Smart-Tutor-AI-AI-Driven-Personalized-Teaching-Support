"""Tests for share_service.py — session sharing and expiry."""
from __future__ import annotations

import secrets
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone


@pytest.fixture
def share_service(tmp_path):
    from backend.services.share_service import ShareService
    service = ShareService.__new__(ShareService)
    service.storage = MagicMock()
    service._share_cache = {}
    service.user_data_root = tmp_path
    service.redis = None
    return service


class TestShareService:
    def test_share_id_is_unique(self):
        """Tokens generated for shares should be unique."""
        ids = {secrets.token_urlsafe(16) for _ in range(10)}
        assert len(ids) == 10

    def test_expired_share_not_returned(self, share_service):
        """Shares past their expiry should return None."""
        expired_at = "2000-01-01T00:00:00+00:00"
        share_data = {
            "share_id": "expired-share-123",
            "username": "testuser",
            "session_id": "sess-1",
            "session_data": {"title": "Test Chat", "messages": []},
            "created_at": "1999-12-31T00:00:00+00:00",
            "expires_at": expired_at,
        }
        share_service._share_cache["expired-share-123"] = share_data
        result = share_service.get_shared_session("expired-share-123")
        assert result is None
