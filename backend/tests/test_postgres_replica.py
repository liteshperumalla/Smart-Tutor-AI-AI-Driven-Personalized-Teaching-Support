"""Unit tests for PostgreSQL Read Replica routing and fallback (Pattern 29)."""

import sys
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

from backend.services.storage.postgres import PostgresStorageBackend
from backend.services.models import QuizResult


@pytest.fixture
def mock_pools():
    with patch("backend.services.storage.postgres.SimpleConnectionPool") as mock_pool_cls:
        writer_pool = MagicMock(name="writer_pool")
        reader_pool = MagicMock(name="reader_pool")
        # First call creates writer pool, second creates reader pool
        mock_pool_cls.side_effect = [writer_pool, reader_pool]
        yield writer_pool, reader_pool


def test_postgres_backend_initializes_reader_pool_when_host_different(mock_pools):
    writer_pool, reader_pool = mock_pools

    backend = PostgresStorageBackend(
        host="postgres-primary.internal",
        port=5432,
        reader_host="postgres-replica.internal",
        reader_port=5432,
    )

    assert backend.pool == writer_pool
    assert backend.reader_pool == reader_pool
    assert backend.reader_pool != backend.pool


def test_postgres_backend_shares_pool_when_no_reader_host():
    with patch("backend.services.storage.postgres.SimpleConnectionPool") as mock_pool_cls:
        single_pool = MagicMock(name="single_pool")
        mock_pool_cls.return_value = single_pool

        backend = PostgresStorageBackend(
            host="localhost",
            port=5432,
            reader_host=None,
        )

        assert backend.pool == single_pool
        assert backend.reader_pool == single_pool


def test_connection_routing_uses_reader_pool_for_read_only(mock_pools):
    writer_pool, reader_pool = mock_pools
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_conn.status = 0
    reader_pool.getconn.return_value = mock_conn

    backend = PostgresStorageBackend(
        host="postgres-primary.internal",
        reader_host="postgres-replica.internal",
    )

    with backend._get_connection(read_only=True) as conn:
        assert conn == mock_conn
        reader_pool.getconn.assert_called_once()
        writer_pool.getconn.assert_not_called()

    reader_pool.putconn.assert_called_once_with(mock_conn)


def test_connection_routing_uses_writer_pool_for_writes(mock_pools):
    writer_pool, reader_pool = mock_pools
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_conn.status = 0
    writer_pool.getconn.return_value = mock_conn

    backend = PostgresStorageBackend(
        host="postgres-primary.internal",
        reader_host="postgres-replica.internal",
    )

    with backend._get_connection(read_only=False) as conn:
        assert conn == mock_conn
        writer_pool.getconn.assert_called_once()
        reader_pool.getconn.assert_not_called()

    writer_pool.putconn.assert_called_once_with(mock_conn)


def test_read_replica_fallback_to_primary_on_error(mock_pools):
    writer_pool, reader_pool = mock_pools
    reader_pool.getconn.side_effect = Exception("Read replica connection refused")
    fallback_conn = MagicMock()
    fallback_conn.closed = False
    fallback_conn.status = 0
    writer_pool.getconn.return_value = fallback_conn

    backend = PostgresStorageBackend(
        host="postgres-primary.internal",
        reader_host="postgres-replica.internal",
    )

    with backend._get_connection(read_only=True) as conn:
        assert conn == fallback_conn
        # Should have attempted reader first, then fallen back to writer
        reader_pool.getconn.assert_called_once()
        writer_pool.getconn.assert_called_once()

    writer_pool.putconn.assert_called_once_with(fallback_conn)


def test_read_and_write_queries_route_correctly(mock_pools):
    writer_pool, reader_pool = mock_pools

    backend = PostgresStorageBackend(
        host="postgres-primary.internal",
        reader_host="postgres-replica.internal",
    )

    with patch.object(backend, "_get_cursor") as mock_get_cursor:
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__.return_value = mock_cursor

        # Read methods
        mock_cursor.fetchone.return_value = {"username": "alice", "version": 1}
        backend.get_user("alice")
        mock_get_cursor.assert_called_with(read_only=True)

        backend.get_user_by_email("alice@example.com")
        mock_get_cursor.assert_called_with(read_only=True)

        mock_cursor.fetchall.return_value = []
        backend.list_users()
        mock_get_cursor.assert_called_with(read_only=True)

        backend.list_quiz_results("alice")
        mock_get_cursor.assert_called_with(read_only=True)

        # Write methods
        mock_cursor.fetchone.return_value = {"username": "bob", "version": 1}
        backend.create_user("bob", "hash123")
        mock_get_cursor.assert_called_with(read_only=False)

        backend.update_user("bob", {"full_name": "Bob Smith"})
        mock_get_cursor.assert_called_with(read_only=False)

        mock_cursor.fetchone.return_value = {"login_attempts": 1}
        backend.increment_login_attempts("bob")
        mock_get_cursor.assert_called_with(read_only=False)

        test_result = QuizResult(id="q1", user_id="bob", score=10, total_questions=10, percentage=100.0)
        backend.save_quiz_result(test_result)
        mock_get_cursor.assert_called_with(read_only=False)
