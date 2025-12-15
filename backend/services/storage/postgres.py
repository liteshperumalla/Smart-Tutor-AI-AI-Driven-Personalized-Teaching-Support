"""
PostgreSQL Storage Backend
Implements BaseStorageBackend using PostgreSQL for production-grade user data storage
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager

from backend.config import config
from backend.logger import get_logger
from backend.services.storage.base import BaseStorageBackend
from backend.services.models import ChatSession, QuizResult

logger = get_logger(__name__)


class PostgresStorageBackend(BaseStorageBackend):
    """PostgreSQL implementation of storage backend"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "smart_tutor",
        user: str = "smart_tutor_user",
        password: str = "dev_password_change_in_prod",
        min_connections: int = 2,
        max_connections: int = 10,
    ):
        self.connection_params = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
        }

        # Create connection pool for efficient connection management
        self.pool = SimpleConnectionPool(
            min_connections,
            max_connections,
            **self.connection_params
        )

        logger.info(f"PostgreSQL storage backend initialized (pool: {min_connections}-{max_connections})")

    @contextmanager
    def _get_connection(self):
        """Get connection from pool"""
        conn = self.pool.getconn()
        try:
            yield conn
        finally:
            self.pool.putconn(conn)

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
                print(f"Database error: {e}")
                raise
            finally:
                cursor.close()

    def get_user(self, username: str) -> Optional[dict]:
        """Get user by username"""
        try:
            with self._get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        username, email, hashed_password, display_name,
                        phone_number, role, theme, notes, profile_picture_path,
                        is_locked, locked_until, login_attempts,
                        created_at, updated_at, last_login
                    FROM users
                    WHERE username = %s
                    """,
                    (username,)
                )
                user = cursor.fetchone()

                if user:
                    # Convert RealDictRow to dict and handle datetime serialization
                    user_dict = dict(user)
                    for key, value in user_dict.items():
                        if isinstance(value, datetime):
                            user_dict[key] = value.isoformat()
                    return user_dict

                return None

        except Exception as e:
            logger.error(f"Error getting user {username}: {e}")
            return None

    def create_user(self, username: str, password_hash: str, **extras) -> dict:
        """Create a new user"""
        try:
            with self._get_cursor() as cursor:
                # Extract known fields
                email = extras.get("email", username)
                display_name = extras.get("display_name", username)
                phone_number = extras.get("phone_number", "")
                role = extras.get("role", "User")
                theme = extras.get("theme", "light")

                cursor.execute(
                    """
                    INSERT INTO users (
                        username, email, hashed_password, display_name,
                        phone_number, role, theme
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING
                        username, email, hashed_password, display_name,
                        phone_number, role, theme, notes, profile_picture_path,
                        is_locked, locked_until, login_attempts,
                        created_at, updated_at, last_login
                    """,
                    (username, email, password_hash, display_name, phone_number, role, theme)
                )

                user = cursor.fetchone()
                user_dict = dict(user)

                # Convert datetime to ISO format
                for key, value in user_dict.items():
                    if isinstance(value, datetime):
                        user_dict[key] = value.isoformat()

                logger.info(f"Created user: {username}")
                return user_dict

        except psycopg2.IntegrityError as e:
            # User already exists - this is expected in tests
            raise ValueError(f"User {username} already exists")
        except Exception as e:
            print(f"Error creating user {username}: {e}")
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
                'email', 'hashed_password', 'display_name', 'phone_number',
                'role', 'theme', 'notes', 'profile_picture_path',
                'is_locked', 'locked_until', 'login_attempts', 'last_login'
            }

            for key, value in updates.items():
                if key in allowed_fields:
                    set_clauses.append(f"{key} = %s")
                    values.append(value)

            if not set_clauses:
                return self.get_user(username)

            # Add username to values for WHERE clause
            values.append(username)

            with self._get_cursor() as cursor:
                query = f"""
                    UPDATE users
                    SET {', '.join(set_clauses)}
                    WHERE username = %s
                    RETURNING
                        username, email, hashed_password, display_name,
                        phone_number, role, theme, notes, profile_picture_path,
                        is_locked, locked_until, login_attempts,
                        created_at, updated_at, last_login
                """

                cursor.execute(query, values)
                user = cursor.fetchone()

                if not user:
                    raise ValueError(f"User {username} not found")

                user_dict = dict(user)
                for key, value in user_dict.items():
                    if isinstance(value, datetime):
                        user_dict[key] = value.isoformat()

                logger.debug(f"Updated user: {username}")
                return user_dict

        except Exception as e:
            logger.error(f"Error updating user {username}: {e}")
            raise

    def list_chat_sessions(self, username: str) -> List[ChatSession]:
        """
        List chat sessions for a user
        Note: Chat sessions are stored in DynamoDB, not PostgreSQL
        This is a placeholder that will be handled by DynamoDBStorageBackend
        """
        logger.warning("Chat sessions should be retrieved from DynamoDB, not PostgreSQL")
        return []

    def load_chat_session(self, username: str, session_id: str) -> Optional[ChatSession]:
        """
        Load a specific chat session
        Note: Chat sessions are stored in DynamoDB, not PostgreSQL
        """
        logger.warning("Chat sessions should be retrieved from DynamoDB, not PostgreSQL")
        return None

    def save_chat_session(self, username: str, session: ChatSession) -> None:
        """
        Save a chat session
        Note: Chat sessions are stored in DynamoDB, not PostgreSQL
        """
        logger.warning("Chat sessions should be saved to DynamoDB, not PostgreSQL")
        pass

    def save_quiz_result(self, result: QuizResult) -> None:
        """Save quiz result to PostgreSQL"""
        try:
            with self._get_cursor() as cursor:
                # Calculate correct answers from score if not in metadata
                correct_answers = result.score
                time_taken = result.metadata.get('time_taken', 0) if result.metadata else 0

                cursor.execute(
                    """
                    INSERT INTO quiz_results (
                        username, quiz_id, score, total_questions,
                        correct_answers, time_taken_seconds, quiz_data
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        result.user_id,  # username maps to user_id
                        result.id,  # quiz_id maps to id
                        result.percentage,  # score is percentage
                        result.total_questions,
                        correct_answers,
                        time_taken,
                        psycopg2.extras.Json(result.metadata) if result.metadata else None
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
                        correct_answers, time_taken_seconds, quiz_data,
                        created_at
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
                        score=row['correct_answers'],  # correct_answers maps to score
                        total_questions=row['total_questions'],
                        percentage=row['score'],  # score from DB is percentage
                        metadata=row['quiz_data'] or {},
                        created_at=row['created_at']
                    )
                    results.append(result)

                return results

        except Exception as e:
            logger.error(f"Error listing quiz results for {username}: {e}")
            return []

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
        host = config.get("POSTGRES_HOST", "localhost")
        port = int(config.get("POSTGRES_PORT", "5432"))
        database = config.get("POSTGRES_DB", "smart_tutor")
        user = config.get("POSTGRES_USER", "smart_tutor_user")
        password = config.get("POSTGRES_PASSWORD", "dev_password_change_in_prod")

        _postgres_backend = PostgresStorageBackend(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
    return _postgres_backend
