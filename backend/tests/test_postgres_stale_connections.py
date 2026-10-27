"""Stale pooled connections must not fail the first query after downtime.

Regression: after the database dropped idle connections (instance stop/start,
RDS restart, idle timeout), the first get_user() reused a dead pooled
connection, failed with "server closed the connection unexpectedly", and was
reported as "user not found" — rejecting the first login and making /auth/me
answer "Invalid or expired session".
"""

import sys
from unittest.mock import MagicMock, patch

try:  # use the real driver when installed; never shadow it for later tests
    import psycopg2  # noqa: F401
except ImportError:
    mock_psycopg = MagicMock()
    mock_psycopg.extensions.STATUS_READY = 0
    sys.modules["psycopg2"] = mock_psycopg
    sys.modules["psycopg2.extras"] = mock_psycopg.extras
    sys.modules["psycopg2.pool"] = mock_psycopg.pool
    sys.modules["psycopg2.sql"] = mock_psycopg.sql

from backend.services.storage import postgres as postgres_module
from backend.services.storage.postgres import PostgresStorageBackend


def _conn(alive: bool):
    conn = MagicMock()
    conn.closed = 0
    conn.status = postgres_module.psycopg2.extensions.STATUS_READY
    cursor = MagicMock()
    if not alive:
        cursor.execute.side_effect = Exception("server closed the connection unexpectedly")
    conn.cursor.return_value.__enter__.return_value = cursor
    return conn


def _backend(pool):
    with patch("backend.services.storage.postgres.SimpleConnectionPool", return_value=pool):
        return PostgresStorageBackend(host="localhost", reader_host=None)


def test_checkout_replaces_dead_idle_connection():
    dead, live = _conn(alive=False), _conn(alive=True)
    pool = MagicMock()
    pool.maxconn = 2
    pool.getconn.side_effect = [dead, live]
    backend = _backend(pool)

    assert backend._checkout(pool) is live
    pool.putconn.assert_called_once_with(dead, close=True)


def test_checkout_discards_closed_connection_without_ping():
    closed, live = _conn(alive=True), _conn(alive=True)
    closed.closed = 1
    pool = MagicMock()
    pool.maxconn = 2
    pool.getconn.side_effect = [closed, live]
    backend = _backend(pool)

    assert backend._checkout(pool) is live
    closed.cursor.assert_not_called()
    pool.putconn.assert_called_once_with(closed, close=True)


def test_recently_used_connection_is_not_pinged():
    conn = _conn(alive=True)
    pool = MagicMock()
    pool.getconn.return_value = conn
    backend = _backend(pool)

    with backend._get_connection():
        pass
    conn.cursor.reset_mock()

    assert backend._checkout(pool) is conn
    conn.cursor.assert_not_called()


def test_checkout_validates_every_connection_and_raises_when_none_is_live():
    pool = MagicMock()
    pool.maxconn = 2
    pool.getconn.side_effect = [_conn(alive=False) for _ in range(3)]
    backend = _backend(pool)

    try:
        backend._checkout(pool)
    except ConnectionError:
        pass
    else:
        raise AssertionError("a dead connection was handed out")
    assert pool.getconn.call_count == 3
