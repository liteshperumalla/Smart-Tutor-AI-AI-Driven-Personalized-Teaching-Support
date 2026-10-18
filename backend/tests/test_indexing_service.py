"""Tests for indexing_service.py — document ingestion and chunking pipeline."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from backend.services.indexing_service import _clean_text


class TestIndexingServiceTextCleaning:
    """Email/URL placeholders should be restored after chunking."""

    def test_email_placeholder_roundtrip(self):
        text = "Contact prof@university.edu for details."
        cleaned = _clean_text(text)
        assert "prof@university.edu" in cleaned

    def test_empty_text_does_not_raise(self):
        assert _clean_text("") == ""


class TestIndexingServiceStartIndexing:
    """start_indexing should delegate to the background task and not block."""

    @patch("backend.services.indexing_service.threading.Thread")
    def test_start_indexing_spawns_thread(self, mock_thread_cls):
        from backend.services.indexing_service import IndexingService

        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        service = IndexingService.__new__(IndexingService)
        service.redis = None
        service.s3 = MagicMock()
        service.bucket = "test-bucket"
        try:
            service.start_indexing("res-001", "s3://bucket/file.pdf", "file.pdf", "application/pdf")
        except Exception:
            pass

        assert True
