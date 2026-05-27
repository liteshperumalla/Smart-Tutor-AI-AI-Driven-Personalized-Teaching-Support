"""
PostgreSQL Storage Backend
Implements BaseStorageBackend using PostgreSQL for production-grade user data storage
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from psycopg2 import sql  # SECURITY: For safe SQL identifier quoting
from contextlib import contextmanager
import re

from backend.config import config
from backend.logger import get_logger
from backend.services.storage.base import BaseStorageBackend
from backend.services.storage.filesystem import FileSystemStorageBackend
from backend.services.models import ChatSession, QuizResult  # Fixed import path

logger = get_logger(__name__)


class PostgresStorageBackend(BaseStorageBackend):
    """PostgreSQL implementation of storage backend"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "smart_tutor",
        user: str = "smart_tutor_user",
        password: str = "",
        min_connections: int = 2,
        max_connections: int = 10,
    ):
        # SECURITY: Add SSL configuration
        from backend.config import config

        self.connection_params = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
            "sslmode": config.POSTGRES_SSL_MODE,
            "connect_timeout": 5,  # Fail fast if database is unreachable
        }

        # Add SSL root certificate if provided (for RDS)
        if config.POSTGRES_SSL_ROOT_CERT:
            self.connection_params["sslrootcert"] = config.POSTGRES_SSL_ROOT_CERT

        # Create connection pool for efficient connection management
        self.pool = SimpleConnectionPool(
            min_connections,
            max_connections,
            **self.connection_params
        )
        self.chat_storage = FileSystemStorageBackend()

        logger.info(f"PostgreSQL storage backend initialized (pool: {min_connections}-{max_connections})")

    @contextmanager
    def _get_connection(self):
        """Get connection from pool with health check on return"""
        conn = self.pool.getconn()
        try:
            yield conn
        finally:
            # Return broken connections to pool with close=True
            if conn.closed or conn.status != psycopg2.extensions.STATUS_READY:
                self.pool.putconn(conn, close=True)
            else:
                self.pool.putconn(conn)

    @staticmethod
    def _is_valid_field_name(field_name: str) -> bool:
        """
        Validate field name to prevent SQL injection.
        Only allows alphanumeric characters and underscores.

        Args:
            field_name: The field name to validate

        Returns:
            bool: True if valid, False otherwise
        """
        # Field names must be alphanumeric with underscores only
        # Must start with letter or underscore
        pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
        return bool(re.match(pattern, field_name))

    @contextmanager
    def _get_cursor(self, cursor_factory=RealDictCursor):
        """Get cursor with automatic commit/rollback"""
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Database error: {e}", exc_info=True)
                raise
            finally:
                cursor.close()

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
        return user_dict

    def get_user(self, username: str) -> Optional[dict]:
        """Get user by username"""
        try:
            with self._get_cursor() as cursor:
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
                    return self._enrich_user_dict(dict(user))

                return None

        except Exception as e:
            logger.error(f"Error getting user {username}: {e}")
            return None

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user by email"""
        if not email:
            return None
        try:
            with self._get_cursor() as cursor:
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
                    return self._enrich_user_dict(dict(user))
                return None
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None

    def create_user(self, username: str, password_hash: str, **extras) -> dict:
        """Create a new user"""
        try:
            with self._get_cursor() as cursor:
                # Extract known fields from extras
                email = extras.get("email", username)
                full_name = extras.get("full_name", username)

                # Store role and extra profile fields in metadata JSONB
                metadata = {}
                for meta_key in ("role", "display_name", "phone_number", "theme"):
                    if meta_key in extras:
                        metadata[meta_key] = extras[meta_key]

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

                user = cursor.fetchone()
                logger.info(f"Created user: {username}")
                return self._enrich_user_dict(dict(user))

        except psycopg2.IntegrityError:
            raise ValueError(f"User {username} already exists")
        except Exception as e:
            logger.error(f"Error creating user {username}: {e}")
            raise

    def increment_login_attempts(self, username: str) -> int:
        """
        Atomic counter bump via ``UPDATE … RETURNING``. Two concurrent failed
        logins for the same account each see their own pre-incremented value,
        so brute-force lockouts can't be defeated by parallel requests.
        Returns 0 when the user does not exist.
        """
        try:
            with self._get_cursor() as cursor:
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
            logger.error(f"Error incrementing login attempts for {username}: {e}")
            raise

    def update_user(self, username: str, updates: dict) -> dict:
        """Update user fields"""
        if not updates:
            return self.get_user(username)

        try:
            # Build dynamic UPDATE query
            set_clauses = []
            values = []

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

            if not sql_set_clauses:
                return self.get_user(username)

            # Add username to values for WHERE clause
            values.append(username)

            with self._get_cursor() as cursor:
                query = sql.SQL("""
                    UPDATE users
                    SET {}
                    WHERE username = %s
                    RETURNING
                        username, email, password_hash, full_name,
                        created_at, last_login, login_attempts, locked_until, metadata
                """).format(sql.SQL(", ").join(sql_set_clauses))

                cursor.execute(query, values)
                user = cursor.fetchone()

                if not user:
                    raise ValueError(f"User {username} not found")

                logger.debug(f"Updated user: {username}")
                return self._enrich_user_dict(dict(user))

        except Exception as e:
            logger.error(f"Error updating user {username}: {e}")
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

    def increment_login_attempts(self, username: str) -> int:
        """Increment failed login attempts atomically using a single SQL statement."""
        with self._get_cursor() as cursor:
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
            return int(row["login_attempts"]) if row else 0

    def reset_login_attempts(self, username: str) -> None:
        """Reset failed login attempts"""
        self.update_user(username, {"login_attempts": 0})

    def lock_account(self, username: str, until) -> None:
        """Lock user account until specified time"""
        locked_until = until.isoformat() if hasattr(until, "isoformat") else str(until)
        self.update_user(username, {"locked_until": locked_until})

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
        """
        List chat sessions for a user
        Note: Chat sessions are stored in DynamoDB, not PostgreSQL
        This is a placeholder that will be handled by DynamoDBStorageBackend
        """
        logger.warning("Chat sessions are stored in filesystem for postgres backend")
        return self.chat_storage.list_chat_sessions(username)

    def load_chat_session(self, username: str, session_id: str) -> Optional[ChatSession]:
        """
        Load a specific chat session
        Note: Chat sessions are stored in DynamoDB, not PostgreSQL
        """
        logger.warning("Chat sessions are stored in filesystem for postgres backend")
        return self.chat_storage.load_chat_session(username, session_id)

    def save_chat_session(self, username: str, session: ChatSession) -> None:
        """
        Save a chat session
        Note: Chat sessions are stored in DynamoDB, not PostgreSQL
        """
        logger.warning("Chat sessions are stored in filesystem for postgres backend")
        self.chat_storage.save_chat_session(username, session)

    def save_quiz_result(self, result: QuizResult) -> None:
        """Save quiz result to PostgreSQL"""
        try:
            with self._get_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO quiz_results (
                        username, quiz_id, score, total_questions,
                        answers, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        result.user_id,  # username maps to user_id
                        result.id,  # quiz_id maps to id
                        result.score,
                        result.total_questions,
                        psycopg2.extras.Json(result.metadata.get("responses", [])) if result.metadata else None,
                        psycopg2.extras.Json(result.metadata) if result.metadata else None,
                    )
                )
                logger.info(f"Saved quiz result for {result.user_id}: {result.id}")

        except Exception as e:
            logger.error(f"Error saving quiz result: {e}")
            raise

    def list_quiz_results(self, username: str) -> List[QuizResult]:
        """List quiz results for a user"""
        try:
            with self._get_cursor() as cursor:
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
                    # Map database fields to QuizResult model
                    result = QuizResult(
                        id=row['quiz_id'],  # quiz_id from DB maps to id
                        user_id=row['username'],  # username from DB maps to user_id
                        score=row['score'],
                        total_questions=row['total_questions'],
                        percentage=(row['score'] / row['total_questions'] * 100.0) if row.get('total_questions') else 0.0,
                        metadata=row['metadata'] or {},
                        created_at=row['created_at']
                    )
                    results.append(result)

                return results

        except Exception as e:
            logger.error(f"Error listing quiz results for {username}: {e}")
            return []

    def list_users(self) -> List[dict]:
        """List all users (without passwords)"""
        try:
            with self._get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        username, email, full_name,
                        created_at, last_login, login_attempts, locked_until, metadata
                    FROM users
                    ORDER BY created_at DESC
                    """
                )
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
        """Delete a user by username"""
        try:
            with self._get_cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE username = %s", (username,))
                if cursor.rowcount > 0:
                    logger.info(f"Deleted user: {username}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error deleting user {username}: {e}")
            return False

    def close(self):
        """Close all connections in pool"""
        if self.pool:
            self.pool.closeall()
            logger.info("PostgreSQL connection pool closed")


# Singleton instance
_postgres_backend = None


def get_postgres_backend() -> PostgresStorageBackend:
    """Get singleton PostgreSQL backend instance"""
    global _postgres_backend
    if _postgres_backend is None:
        # Read from environment or config
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
            password=password
        )
    return _postgres_backend
