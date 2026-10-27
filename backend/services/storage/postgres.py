"""
PostgreSQL Storage Backend
Implements BaseStorageBackend using PostgreSQL for production-grade user data storage
Supports Read Replicas (Pattern 29) and Optimistic Locking (Pattern 36)
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from psycopg2.pool import SimpleConnectionPool
    from psycopg2 import sql  # SECURITY: For safe SQL identifier quoting
except ImportError:
    psycopg2 = None
    RealDictCursor = None
    SimpleConnectionPool = None
    sql = None
from contextlib import contextmanager
import re
import time

from backend.config import config
from backend.logger import get_logger
from backend.exceptions import OptimisticLockError
from backend.services.storage.base import BaseStorageBackend
from backend.services.models import ChatSession, QuizResult
from backend.log_redaction import user_ref

logger = get_logger(__name__)


def _record_db_duration(operation: str, seconds: float) -> None:
    """Feed db_query_duration_seconds (Grafana: RAG Retrieval & Database Latency)."""
    try:
        from backend.metrics import track_db_query
        track_db_query("postgres", operation, seconds)
    except Exception:  # metrics must never break a query
        pass


def _record_db_error(error_type: str) -> None:
    try:
        from backend.metrics import track_db_error
        track_db_error("postgres", error_type)
    except Exception:
        pass


class PostgresStorageBackend(BaseStorageBackend):
    """PostgreSQL implementation of storage backend with Read Replica and Optimistic Locking support"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "smart_tutor",
        user: str = "smart_tutor_user",
        password: str = "",
        min_connections: int = 2,
        max_connections: int = 10,
        reader_host: Optional[str] = None,
        reader_port: Optional[int] = None,
    ):
        from backend.config import config

        self.connection_params = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
            "sslmode": config.POSTGRES_SSL_MODE,
            "connect_timeout": 5,  # Fail fast if database is unreachable
            # Detect peers that went away (RDS restart, NAT/idle timeout) instead
            # of handing a half-open socket to the next request.
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
            # Bound how long a query on a dead socket (e.g. the stale-connection
            # ping in _checkout) can wait for an acknowledgement.
            "tcp_user_timeout": 5000,
        }
        # id(conn) -> monotonic time it was last returned to a pool
        self._conn_last_used: Dict[int, float] = {}

        # Add SSL root certificate if provided (for RDS)
        if config.POSTGRES_SSL_ROOT_CERT:
            self.connection_params["sslrootcert"] = config.POSTGRES_SSL_ROOT_CERT

        # Primary writer connection pool
        self.pool = SimpleConnectionPool(
            min_connections,
            max_connections,
            **self.connection_params
        )

        # Dedicated Read Replica pool (Pattern 29)
        effective_reader_host = reader_host or getattr(config, "POSTGRES_READER_HOST", "") or None
        effective_reader_port = reader_port or getattr(config, "POSTGRES_READER_PORT", port)

        if effective_reader_host and effective_reader_host != host:
            self.reader_connection_params = dict(self.connection_params)
            self.reader_connection_params["host"] = effective_reader_host
            self.reader_connection_params["port"] = effective_reader_port
            try:
                self.reader_pool = SimpleConnectionPool(
                    min_connections,
                    max_connections,
                    **self.reader_connection_params
                )
                logger.info(
                    f"Configured dedicated read-replica pool for {effective_reader_host}:{effective_reader_port} (pool: {min_connections}-{max_connections})"
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to initialize read-replica pool ({exc}); falling back to primary pool for reads"
                )
                self.reader_pool = self.pool
        else:
            self.reader_pool = self.pool

        # Chat sessions live in DynamoDB, lazily resolved so that environments
        # without AWS configured (unit tests, local-only dev) don't pay the
        # boto3 cost or trip credential lookups at backend-init time.
        self._chat_backend = None

        logger.info(
            f"PostgreSQL storage backend initialized (writer pool: {min_connections}-{max_connections})"
        )

    def _ensure_schema(self) -> None:
        """Ensure backward compatibility by auto-migrating core columns if missing."""
        try:
            with self._get_cursor(read_only=False) as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id UUID DEFAULT gen_random_uuid(),
                        username VARCHAR(255) PRIMARY KEY,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        full_name VARCHAR(255),
                        metadata JSONB,
                        version INTEGER DEFAULT 1,
                        is_locked BOOLEAN DEFAULT FALSE,
                        locked_until TIMESTAMP,
                        login_attempts INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP
                    );
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS is_locked BOOLEAN DEFAULT FALSE;
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP;
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS login_attempts INTEGER DEFAULT 0;
                """)
                logger.info("Verified PostgreSQL users schema columns")
        except Exception as exc:
            logger.warning(f"Could not auto-apply schema updates: {exc}")

    @property
    def chat_storage(self):
        """Lazy DynamoDB chat backend; raised exceptions surface on first use."""
        if self._chat_backend is None:
            from backend.services.storage.dynamodb import get_dynamodb_backend
            self._chat_backend = get_dynamodb_backend()
        return self._chat_backend

    @contextmanager
    def _get_connection(self, read_only: bool = False):
        """Get connection from primary or reader pool with health check and graceful fallback"""
        use_reader = read_only and self.reader_pool is not None and self.reader_pool is not self.pool
        target_pool = self.reader_pool if use_reader else self.pool
        conn = None
        started = time.monotonic()
        try:
            try:
                conn = self._checkout(target_pool)
            except Exception as exc:
                if not use_reader:
                    raise
                logger.warning(
                    f"Failed to obtain connection from read replica ({exc}); falling back to primary pool"
                )
                target_pool = self.pool
                conn = self._checkout(self.pool)
        except Exception as exc:
            # Query errors are recorded by _get_cursor; this covers the
            # requests that never got a connection.
            _record_db_error(type(exc).__name__)
            _record_db_duration("read" if read_only else "write", time.monotonic() - started)
            raise
        try:
            yield conn
        finally:
            if conn is not None:
                # Return broken connections to pool with close=True
                status_ready = psycopg2.extensions.STATUS_READY if psycopg2 and hasattr(psycopg2, "extensions") else 0
                if conn.closed or conn.status != status_ready:
                    self._conn_last_used.pop(id(conn), None)
                    target_pool.putconn(conn, close=True)
                else:
                    self._conn_last_used[id(conn)] = time.monotonic()
                    target_pool.putconn(conn)

    # Pooled connections idle longer than this are pinged before reuse.
    _IDLE_PING_SECONDS = 30.0
    # Give up looking for a live connection after this long.
    _CHECKOUT_BUDGET_SECONDS = 15.0

    def _checkout(self, pool):
        """Take a live connection from ``pool``.

        Pooled connections go stale while they sit idle — the database
        restarts, the EC2 instance comes back from its nightly stop, or a
        NAT/idle timeout drops the socket. Handing one of those out made the
        first query after downtime fail ("server closed the connection
        unexpectedly"), and because get_user() maps errors to "not found",
        the first login was rejected and /auth/me reported an expired session.
        Idle connections are pinged and dead ones replaced before use. Every
        idle connection may be stale after downtime, so up to pool size + 1
        are checked (the last one is a freshly opened connection); if none is
        live the database is down and that is raised, not a dead connection.
        """
        attempts = int(getattr(pool, "maxconn", 10) or 10) + 1
        deadline = time.monotonic() + self._CHECKOUT_BUDGET_SECONDS
        for _ in range(attempts):
            if time.monotonic() > deadline:
                break
            conn = pool.getconn()
            if self._is_alive(conn):
                return conn
            self._conn_last_used.pop(id(conn), None)
            try:
                pool.putconn(conn, close=True)
            except Exception:
                pass
        raise ConnectionError("PostgreSQL: no live connection available")

    def _is_alive(self, conn) -> bool:
        if conn.closed:
            return False
        last_used = self._conn_last_used.get(id(conn))
        if last_used is not None and time.monotonic() - last_used < self._IDLE_PING_SECONDS:
            return True
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            conn.rollback()
            return True
        except Exception as exc:
            logger.warning(f"Discarding stale PostgreSQL connection: {exc}")
            return False

    @staticmethod
    def _is_valid_field_name(field_name: str) -> bool:
        """
        Validate field name to prevent SQL injection.
        Only allows alphanumeric characters and underscores.
        """
        pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
        return bool(re.match(pattern, field_name))

    @contextmanager
    def _get_cursor(self, cursor_factory=RealDictCursor, read_only: bool = False):
        """Get cursor with automatic commit/rollback and read/write pool routing"""
        operation = "read" if read_only else "write"
        started = time.monotonic()
        with self._get_connection(read_only=read_only) as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
                if not read_only:
                    conn.commit()
            except Exception as e:
                if not read_only:
                    conn.rollback()
                logger.error(f"Database error: {e}", exc_info=True)
                _record_db_error(type(e).__name__)
                raise
            finally:
                cursor.close()
                _record_db_duration(operation, time.monotonic() - started)

    def check_health(self) -> None:
        """Raise when PostgreSQL cannot serve a simple query."""
        with self._get_cursor(read_only=True) as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

    def _enrich_user_dict(self, user_dict: dict) -> dict:
        """Extract role and profile fields from metadata into top-level keys."""
        for key, value in list(user_dict.items()):
            if isinstance(value, datetime):
                user_dict[key] = value.isoformat()
        metadata = user_dict.get("metadata") or {}
        if isinstance(metadata, dict):
            for key in ("display_name", "phone_number", "theme", "role"):
                if key not in user_dict and key in metadata:
                    user_dict[key] = metadata[key]
        # Default role when not set
        user_dict.setdefault("role", "User")
        # Ensure version exists
        user_dict["version"] = int(user_dict.get("version") or 1)
        return user_dict

    def get_user(self, username: str) -> Optional[dict]:
        """Get user by username (routed to read pool)"""
        try:
            with self._get_cursor(read_only=True) as cursor:
                try:
                    cursor.execute(
                        """
                        SELECT
                            username, email, password_hash, full_name,
                            created_at, last_login, login_attempts, locked_until, metadata,
                            COALESCE(version, 1) AS version
                        FROM users
                        WHERE username = %s
                        """,
                        (username,)
                    )
                    user = cursor.fetchone()
                except Exception as query_err:
                    if "version" in str(query_err).lower():
                        cursor.connection.rollback()
                        cursor.execute(
                            """
                            SELECT
                                username, email, password_hash, full_name,
                                created_at, last_login, login_attempts, locked_until, metadata
                            FROM users
                            WHERE username = %s
                            """,
                            (username,)
                        )
                        user = cursor.fetchone()
                        if user:
                            user = dict(user)
                            user["version"] = 1
                    else:
                        raise

                if user:
                    return self._enrich_user_dict(dict(user))

                return None

        except Exception as e:
            logger.error(f"Error getting user {user_ref(username)}: {e}")
            return None

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user by email (routed to read pool)"""
        if not email:
            return None
        try:
            with self._get_cursor(read_only=True) as cursor:
                try:
                    cursor.execute(
                        """
                        SELECT
                            username, email, password_hash, full_name,
                            created_at, last_login, login_attempts, locked_until, metadata,
                            COALESCE(version, 1) AS version
                        FROM users
                        WHERE email = %s
                        """,
                        (email,)
                    )
                    user = cursor.fetchone()
                except Exception as query_err:
                    if "version" in str(query_err).lower():
                        cursor.connection.rollback()
                        cursor.execute(
                            """
                            SELECT
                                username, email, password_hash, full_name,
                                created_at, last_login, login_attempts, locked_until, metadata
                            FROM users
                            WHERE email = %s
                            """,
                            (email,)
                        )
                        user = cursor.fetchone()
                        if user:
                            user = dict(user)
                            user["version"] = 1
                    else:
                        raise

                if user:
                    return self._enrich_user_dict(dict(user))
                return None
        except Exception as e:
            logger.error(f"Error getting user by email {user_ref(email)}: {e}")
            return None

    def create_user(self, username: str, password_hash: str, **extras) -> dict:
        """Create a new user (routed to writer pool)"""
        try:
            with self._get_cursor(read_only=False) as cursor:
                # Extract known fields from extras
                email = extras.get("email", username)
                full_name = extras.get("full_name", username)

                # Store role and extra profile fields in metadata JSONB
                metadata = {}
                for meta_key in ("role", "display_name", "phone_number", "theme"):
                    if meta_key in extras:
                        metadata[meta_key] = extras[meta_key]

                try:
                    cursor.execute(
                        """
                        INSERT INTO users (
                            username, email, password_hash, full_name, metadata, version
                        )
                        VALUES (%s, %s, %s, %s, %s, 1)
                        RETURNING
                            username, email, password_hash, full_name,
                            created_at, last_login, login_attempts, locked_until, metadata, version
                        """,
                        (username, email, password_hash, full_name,
                         psycopg2.extras.Json(metadata) if metadata else None)
                    )
                except Exception as insert_err:
                    if "version" in str(insert_err).lower():
                        cursor.connection.rollback()
                        cursor.execute(
                            """
                            INSERT INTO users (
                                username, email, password_hash, full_name, metadata
                            )
                            VALUES (%s, %s, %s, %s, %s)
                            RETURNING
                                username, email, password_hash, full_name,
                                created_at, last_login, login_attempts, locked_until, metadata
                            """,
                            (username, email, password_hash, full_name,
                             psycopg2.extras.Json(metadata) if metadata else None)
                        )
                    else:
                        raise

                user = cursor.fetchone()
                logger.info(f"Created user: {user_ref(username)}")
                return self._enrich_user_dict(dict(user))

        except psycopg2.IntegrityError:
            raise ValueError(f"User {username} already exists")
        except Exception as e:
            logger.error(f"Error creating user {user_ref(username)}: {e}")
            raise

    def increment_login_attempts(self, username: str) -> int:
        """
        Atomic counter bump via ``UPDATE … RETURNING`` on writer pool.
        """
        try:
            with self._get_cursor(read_only=False) as cursor:
                cursor.execute(
                    """
                    UPDATE users
                    SET login_attempts = COALESCE(login_attempts, 0) + 1
                    WHERE username = %s
                    RETURNING login_attempts
                    """,
                    (username,),
                )
                row = cursor.fetchone()
                if not row:
                    return 0
                return int(row["login_attempts"])
        except Exception as e:
            logger.error(f"Error incrementing login attempts for {user_ref(username)}: {e}")
            raise

    def update_user(self, username: str, updates: dict, expected_version: Optional[int] = None) -> dict:
        """
        Update user fields with optimistic locking support (Pattern 36).

        Args:
            username: Username of user to update
            updates: Dictionary of fields to modify
            expected_version: Optional expected version for concurrency detection

        Raises:
            OptimisticLockError: If expected_version does not match current version
            ValueError: If user does not exist or invalid field names
        """
        if not updates and expected_version is None:
            return self.get_user(username)

        try:
            # Build dynamic UPDATE query
            allowed_fields = {
                'email', 'password_hash', 'full_name',
                'locked_until', 'login_attempts', 'last_login', 'metadata'
            }
            profile_fields = {"display_name", "phone_number", "theme", "role"}
            metadata_updates = {
                key: value for key, value in updates.items()
                if key in profile_fields
            }

            if metadata_updates:
                current = self.get_user(username) or {}
                metadata = current.get("metadata") or {}
                if not isinstance(metadata, dict):
                    metadata = {}
                metadata.update(metadata_updates)
                updates = {k: v for k, v in updates.items() if k in allowed_fields}
                updates["metadata"] = metadata

            # SECURITY: Use psycopg2.sql.Identifier for safe column quoting
            sql_set_clauses = []
            values = []
            for key, value in updates.items():
                if key in allowed_fields:
                    if not self._is_valid_field_name(key):
                        logger.error(f"Invalid field name detected: {key}")
                        raise ValueError(f"Invalid field name: {key}")

                    if key == "metadata" and isinstance(value, dict):
                        value = psycopg2.extras.Json(value)
                    sql_set_clauses.append(
                        sql.SQL("{} = %s").format(sql.Identifier(key))
                    )
                    values.append(value)

            # Optimistic locking version bump (Pattern 36)
            sql_set_clauses.append(sql.SQL("version = COALESCE(version, 1) + 1"))

            # Build WHERE clause
            where_conditions = [sql.SQL("username = %s")]
            values.append(username)

            if expected_version is not None:
                where_conditions.append(sql.SQL("version = %s"))
                values.append(expected_version)

            with self._get_cursor(read_only=False) as cursor:
                query = sql.SQL("""
                    UPDATE users
                    SET {}
                    WHERE {}
                    RETURNING
                        username, email, password_hash, full_name,
                        created_at, last_login, login_attempts, locked_until, metadata, version
                """).format(
                    sql.SQL(", ").join(sql_set_clauses),
                    sql.SQL(" AND ").join(where_conditions)
                )

                cursor.execute(query, values)
                user = cursor.fetchone()

                if not user:
                    if expected_version is not None:
                        # Check if user exists to distinguish not-found from version mismatch
                        cursor.execute("SELECT version FROM users WHERE username = %s", (username,))
                        existing = cursor.fetchone()
                        if existing:
                            raise OptimisticLockError(
                                resource=f"user:{username}",
                                current_version=existing["version"],
                                expected_version=expected_version
                            )
                    raise ValueError(f"User {username} not found")

                logger.debug(f"Updated user: {user_ref(username)} (new version: {user['version']})")
                return self._enrich_user_dict(dict(user))

        except OptimisticLockError:
            raise
        except Exception as e:
            logger.error(f"Error updating user {user_ref(username)}: {e}")
            raise

    # Additional user methods (for auth_service compatibility)
    def get_user_safe(self, username: str) -> Optional[dict]:
        """Get user safely (alias for get_user)"""
        return self.get_user(username)

    def user_exists(self, username: str) -> bool:
        """Check if user exists"""
        return self.get_user(username) is not None

    def update_last_login(self, username: str) -> None:
        """Update last login timestamp and reset attempts"""
        self.update_user(username, {
            "last_login": datetime.now(timezone.utc).isoformat(),
            "login_attempts": 0
        })

    def reset_login_attempts(self, username: str) -> None:
        """Reset failed login attempts"""
        self.update_user(username, {"login_attempts": 0})

    def is_account_locked(self, username: str) -> bool:
        """Check if account is locked"""
        user = self.get_user(username)
        if not user:
            return False
        locked_until = user.get("locked_until")
        if not locked_until:
            return False
        try:
            unlock_time = (
                datetime.fromisoformat(locked_until)
                if isinstance(locked_until, str)
                else locked_until
            )
            return datetime.now(timezone.utc) < unlock_time
        except Exception:
            return False

    def list_chat_sessions(self, username: str) -> List[ChatSession]:
        """List chat sessions for a user (routed to DynamoDB)."""
        return self.chat_storage.list_chat_sessions(username)

    def load_chat_session(self, username: str, session_id: str) -> Optional[ChatSession]:
        """Load a chat session (routed to DynamoDB)."""
        return self.chat_storage.load_chat_session(username, session_id)

    def save_chat_session(self, username: str, session: ChatSession) -> None:
        """Persist a chat session (routed to DynamoDB)."""
        self.chat_storage.save_chat_session(username, session)

    def delete_chat_session(self, username: str, session_id: str) -> bool:
        """Delete a chat session (routed to DynamoDB)."""
        return self.chat_storage.delete_chat_session(username, session_id)

    def save_quiz_result(self, result: QuizResult) -> None:
        """Save quiz result to PostgreSQL (writer pool)"""
        try:
            with self._get_cursor(read_only=False) as cursor:
                cursor.execute(
                    """
                    INSERT INTO quiz_results (
                        username, quiz_id, score, total_questions,
                        answers, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        result.user_id,
                        result.id,
                        result.score,
                        result.total_questions,
                        psycopg2.extras.Json(result.metadata.get("responses", [])) if result.metadata else None,
                        psycopg2.extras.Json(result.metadata) if result.metadata else None,
                    )
                )
                logger.info(f"Saved quiz result for {user_ref(result.user_id)}: {result.id}")

        except Exception as e:
            logger.error(f"Error saving quiz result: {e}")
            raise

    def list_quiz_results(self, username: str) -> List[QuizResult]:
        """List quiz results for a user (routed to read pool)"""
        try:
            with self._get_cursor(read_only=True) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id, username, quiz_id, score, total_questions,
                        answers, metadata, created_at
                    FROM quiz_results
                    WHERE username = %s
                    ORDER BY created_at DESC
                    """,
                    (username,)
                )

                results = []
                for row in cursor.fetchall():
                    result = QuizResult(
                        id=row['quiz_id'],
                        user_id=row['username'],
                        score=row['score'],
                        total_questions=row['total_questions'],
                        percentage=(row['score'] / row['total_questions'] * 100.0) if row.get('total_questions') else 0.0,
                        metadata=row['metadata'] or {},
                        created_at=row['created_at']
                    )
                    results.append(result)

                return results

        except Exception as e:
            logger.error(f"Error listing quiz results for {user_ref(username)}: {e}")
            return []

    def list_users(self) -> List[dict]:
        """List all users (without passwords, routed to read pool)"""
        try:
            with self._get_cursor(read_only=True) as cursor:
                try:
                    cursor.execute(
                        """
                        SELECT
                            username, email, full_name,
                            created_at, last_login, login_attempts, locked_until, metadata,
                            COALESCE(version, 1) AS version
                        FROM users
                        ORDER BY created_at DESC
                        """
                    )
                except Exception as query_err:
                    if "version" in str(query_err).lower():
                        cursor.connection.rollback()
                        cursor.execute(
                            """
                            SELECT
                                username, email, full_name,
                                created_at, last_login, login_attempts, locked_until, metadata
                            FROM users
                            ORDER BY created_at DESC
                            """
                        )
                    else:
                        raise
                users = []
                for row in cursor.fetchall():
                    user_dict = self._enrich_user_dict(dict(row))
                    user_dict.pop("password_hash", None)
                    users.append(user_dict)
                return users
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []

    def delete_user(self, username: str) -> bool:
        """Delete a user by username (writer pool)"""
        try:
            with self._get_cursor(read_only=False) as cursor:
                cursor.execute("DELETE FROM users WHERE username = %s", (username,))
                if cursor.rowcount > 0:
                    logger.info(f"Deleted user: {user_ref(username)}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error deleting user {user_ref(username)}: {e}")
            return False

    def emit_outbox_event(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Atomically record an event into outbox_events table (Pattern 114)."""
        import uuid
        try:
            event_id = str(uuid.uuid4())
            with self._get_cursor(read_only=False) as cursor:
                cursor.execute(
                    """
                    INSERT INTO outbox_events (
                        id, event_type, aggregate_type, aggregate_id, payload, headers, status, retry_count
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'PENDING', 0)
                    """,
                    (
                        event_id,
                        event_type,
                        aggregate_type,
                        aggregate_id,
                        json.dumps(payload),
                        json.dumps(headers or {}),
                    ),
                )
                logger.info(f"Emitted outbox event {event_id} ({event_type}) for {aggregate_type}:{aggregate_id}")
                return True
        except Exception as e:
            logger.error(f"Error emitting outbox event: {e}")
            return False

    def get_pending_outbox_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch pending outbox events (Pattern 114)."""
        try:
            with self._get_cursor(read_only=True) as cursor:
                cursor.execute(
                    """
                    SELECT id, event_type, aggregate_type, aggregate_id, payload, headers, status, retry_count, created_at
                    FROM outbox_events
                    WHERE status = 'PENDING'
                    ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching pending outbox events: {e}")
            return []


    def close(self):
        """Close all connections in primary and reader pools"""
        if self.pool:
            self.pool.closeall()
            logger.info("PostgreSQL primary connection pool closed")
        if self.reader_pool and self.reader_pool is not self.pool:
            self.reader_pool.closeall()
            logger.info("PostgreSQL read-replica connection pool closed")


# Singleton instance
_postgres_backend = None


def get_postgres_backend() -> PostgresStorageBackend:
    """Get singleton PostgreSQL backend instance"""
    global _postgres_backend
    if _postgres_backend is None:
        host = config.POSTGRES_HOST
        port = int(config.POSTGRES_PORT)
        database = config.POSTGRES_DB
        user = config.POSTGRES_USER
        password = config.POSTGRES_PASSWORD

        _postgres_backend = PostgresStorageBackend(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            reader_host=config.POSTGRES_READER_HOST,
            reader_port=config.POSTGRES_READER_PORT,
        )
        _postgres_backend._ensure_schema()
    return _postgres_backend
