"""
Hybrid Storage Backend
Combines PostgreSQL (users, quiz results) with DynamoDB (chat sessions)
for optimal performance and scalability
"""

from typing import List, Optional

from backend.logger import get_logger
from backend.services.storage.base import BaseStorageBackend
from backend.services.storage.postgres import get_postgres_backend
from backend.services.storage.dynamodb import get_dynamodb_backend
from backend.services.models import ChatSession, QuizResult

logger = get_logger(__name__)


class HybridStorageBackend(BaseStorageBackend):
    """
    Hybrid storage backend that routes operations to appropriate databases:
    - PostgreSQL: User data, quiz results
    - DynamoDB: Chat sessions
    """

    def __init__(self):
        self.postgres = get_postgres_backend()
        self.dynamodb = get_dynamodb_backend()
        logger.info("Hybrid storage backend initialized (PostgreSQL + DynamoDB)")

    # User operations → PostgreSQL
    def get_user(self, username: str) -> Optional[dict]:
        """Get user from PostgreSQL"""
        return self.postgres.get_user(username)

    def create_user(self, username: str, password_hash: str, **extras) -> dict:
        """Create user in PostgreSQL"""
        return self.postgres.create_user(username, password_hash, **extras)

    def update_user(self, username: str, updates: dict) -> dict:
        """Update user in PostgreSQL"""
        return self.postgres.update_user(username, updates)

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user by email from PostgreSQL"""
        return self.postgres.get_user_by_email(email)

    # Additional user methods (for auth_service compatibility)
    def get_user_safe(self, username: str) -> Optional[dict]:
        """Get user safely (alias for get_user)"""
        return self.get_user(username)

    def user_exists(self, username: str) -> bool:
        """Check if user exists"""
        return self.get_user(username) is not None

    def update_last_login(self, username: str) -> None:
        """Update last login timestamp"""
        from datetime import datetime
        self.update_user(username, {'last_login': datetime.utcnow().isoformat()})

    def increment_login_attempts(self, username: str) -> int:
        """Increment failed login attempts"""
        user = self.get_user(username)
        if user:
            attempts = user.get('login_attempts', 0) + 1
            self.update_user(username, {'login_attempts': attempts})
            return attempts
        return 0

    def reset_login_attempts(self, username: str) -> None:
        """Reset failed login attempts"""
        self.update_user(username, {'login_attempts': 0})

    def lock_account(self, username: str, until) -> None:
        """Lock user account until specified time"""
        self.update_user(username, {'locked_until': until.isoformat() if hasattr(until, 'isoformat') else str(until)})

    def is_account_locked(self, username: str) -> bool:
        """Check if account is locked"""
        from datetime import datetime
        user = self.get_user(username)
        if not user:
            return False

        locked_until = user.get('locked_until')
        if not locked_until:
            return False

        try:
            from dateutil import parser
            unlock_time = parser.parse(locked_until) if isinstance(locked_until, str) else locked_until
            return datetime.utcnow() < unlock_time
        except:
            return False

    # Chat session operations → DynamoDB
    def list_chat_sessions(self, username: str) -> List[ChatSession]:
        """List chat sessions from DynamoDB"""
        return self.dynamodb.list_chat_sessions(username)

    def load_chat_session(self, username: str, session_id: str) -> Optional[ChatSession]:
        """Load chat session from DynamoDB"""
        return self.dynamodb.load_chat_session(username, session_id)

    def save_chat_session(self, username: str, session: ChatSession) -> None:
        """Save chat session to DynamoDB"""
        return self.dynamodb.save_chat_session(username, session)

    def delete_chat_session(self, username: str, session_id: str) -> bool:
        """Delete chat session from DynamoDB"""
        return self.dynamodb.delete_chat_session(username, session_id)

    # Quiz operations → PostgreSQL
    def save_quiz_result(self, result: QuizResult) -> None:
        """Save quiz result to PostgreSQL"""
        return self.postgres.save_quiz_result(result)

    def list_quiz_results(self, username: str) -> List[QuizResult]:
        """List quiz results from PostgreSQL"""
        return self.postgres.list_quiz_results(username)

    def close(self):
        """Close all database connections"""
        if hasattr(self.postgres, 'close'):
            self.postgres.close()
        logger.info("Hybrid storage backend connections closed")


# Singleton instance
_hybrid_backend = None


def get_hybrid_backend() -> HybridStorageBackend:
    """Get singleton hybrid backend instance"""
    global _hybrid_backend
    if _hybrid_backend is None:
        _hybrid_backend = HybridStorageBackend()
    return _hybrid_backend
