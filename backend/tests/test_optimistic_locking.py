"""Unit tests for Optimistic Locking and version conflict detection (Pattern 36)."""

import sys
import tempfile
import os
from unittest.mock import MagicMock, patch
import pytest

# Ensure psycopg2 is mocked if not installed in the local test environment
if "psycopg2" not in sys.modules or sys.modules["psycopg2"] is None:
    mock_psycopg = MagicMock()
    mock_psycopg.extensions.STATUS_READY = 0
    sys.modules["psycopg2"] = mock_psycopg
    sys.modules["psycopg2.extras"] = mock_psycopg.extras
    sys.modules["psycopg2.pool"] = mock_psycopg.pool
    sys.modules["psycopg2.sql"] = mock_psycopg.sql

from backend.database import UserDatabase, UserManager
from backend.exceptions import OptimisticLockError
from backend.services.storage.postgres import PostgresStorageBackend


@pytest.fixture
def temp_user_database():
    """Create a temporary UserDatabase for testing."""
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        f.write("{}")
        temp_path = f.name
    try:
        db = UserDatabase(temp_path)
        yield db
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_user_database_optimistic_locking_lifecycle(temp_user_database):
    mgr = temp_user_database

    # 1. User created with initial version 1
    user = mgr.create_user(username="charlie", password_hash="secret123")
    assert user["version"] == 1

    # 2. Update with matching expected_version=1 succeeds and increments to 2
    updated = mgr.update_user("charlie", {"full_name": "Charlie Chaplin"}, expected_version=1)
    assert updated["full_name"] == "Charlie Chaplin"
    assert updated["version"] == 2

    # 3. Update with stale expected_version=1 fails with OptimisticLockError
    with pytest.raises(OptimisticLockError) as exc_info:
        mgr.update_user("charlie", {"full_name": "Stale Update"}, expected_version=1)
    assert exc_info.value.expected_version == 1
    assert exc_info.value.current_version == 2
    assert "charlie" in exc_info.value.resource

    # 4. Update with correct expected_version=2 succeeds and increments to 3
    updated2 = mgr.update_user("charlie", {"full_name": "Charlie C."}, expected_version=2)
    assert updated2["full_name"] == "Charlie C."
    assert updated2["version"] == 3


def test_user_database_update_without_expected_version_still_increments_version(temp_user_database):
    mgr = temp_user_database
    user = mgr.create_user(username="david", password_hash="secret123")
    assert user["version"] == 1

    updated = mgr.update_user("david", {"theme": "dark"})
    assert updated["version"] == 2


def test_postgres_backend_optimistic_locking_success():
    with patch("backend.services.storage.postgres.SimpleConnectionPool"):
        backend = PostgresStorageBackend(host="localhost")

    with patch.object(backend, "_get_cursor") as mock_get_cursor:
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        # Mock successful update returning version 2
        mock_cursor.fetchone.return_value = {
            "username": "elena",
            "email": "elena@example.com",
            "password_hash": "hash",
            "full_name": "Elena Rostova",
            "created_at": None,
            "last_login": None,
            "login_attempts": 0,
            "locked_until": None,
            "metadata": {},
            "version": 2,
        }

        result = backend.update_user("elena", {"full_name": "Elena Rostova"}, expected_version=1)
        assert result["version"] == 2
        assert result["full_name"] == "Elena Rostova"


def test_postgres_backend_optimistic_locking_conflict():
    with patch("backend.services.storage.postgres.SimpleConnectionPool"):
        backend = PostgresStorageBackend(host="localhost")

    with patch.object(backend, "_get_cursor") as mock_get_cursor:
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        # UPDATE query returns None (version mismatch), then SELECT query confirms user exists with version 2
        mock_cursor.fetchone.side_effect = [None, {"version": 2}]

        with pytest.raises(OptimisticLockError) as exc_info:
            backend.update_user("elena", {"full_name": "New Name"}, expected_version=1)

        assert exc_info.value.expected_version == 1
        assert exc_info.value.current_version == 2
