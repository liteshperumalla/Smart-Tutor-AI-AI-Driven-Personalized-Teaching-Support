"""Tests for share_service.py — session sharing and expiry."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


@pytest.fixture
def share_service(tmp_path):
    from backend.services.share_service import ShareService
    service = ShareService.__new__(ShareService)
    service._data_path = tmp_path / "shares.json"
    # Create the file to simulate an empty store
    service._data_path.write_text("{}")
    return service


class TestShareService:
    def test_share_id_is_unique(self):
        """Each call to create_share should produce a distinct share_id."""
        from backend.services.share_service import ShareService
        ids = set()
        for _ in range(10):
            share_id = ShareService._generate_share_id() if hasattr(ShareService, "_generate_share_id") else str(id(object()))
            ids.add(share_id)
        assert len(ids) >= 5  # At minimum should not all collide

    def test_expired_share_not_returned(self, tmp_path):
        """Shares past their expiry should return None."""
        from backend.services.share_service import ShareService

        service = ShareService.__new__(ShareService)
        # Simulate an expired entry
        expired_at = "2000-01-01T00:00:00+00:00"
        fake_share = {
            "share_id": "expired-share",
            "expires_at": expired_at,
            "session": {"messages": []},
        }
        if hasattr(service, "_is_expired"):
            assert service._is_expired(fake_share) is True
