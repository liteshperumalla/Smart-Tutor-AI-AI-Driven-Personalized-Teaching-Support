from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from backend.services.models import ChatSession, QuizResult


class BaseStorageBackend(ABC):
    """Abstract interface for user/chat/quiz storage."""

    @abstractmethod
    def get_user(self, username: str) -> Optional[dict]:
        ...

    @abstractmethod
    def create_user(self, username: str, password_hash: str, **extras) -> dict:
        ...

    @abstractmethod
    def update_user(self, username: str, updates: dict) -> dict:
        ...

    def increment_login_attempts(self, username: str) -> int:
        """
        Atomically increment the user's ``login_attempts`` counter and return
        the new value. The default implementation is a non-atomic
        read-modify-write fallback so existing tests keep passing; backends
        that can do this in one statement (Postgres ``UPDATE … RETURNING``,
        DynamoDB ``UpdateItem ADD``) MUST override this — under concurrent
        failed logins for the same account the fallback under-counts and
        breaks brute-force lockouts.
        """
        user = self.get_user(username)
        if not user:
            return 0
        attempts = (user.get("login_attempts") or 0) + 1
        self.update_user(username, {"login_attempts": attempts})
        return attempts

    @abstractmethod
    def list_chat_sessions(self, username: str) -> List[ChatSession]:
        ...

    @abstractmethod
    def load_chat_session(self, username: str, session_id: str) -> Optional[ChatSession]:
        ...

    @abstractmethod
    def save_chat_session(self, username: str, session: ChatSession) -> None:
        ...

    @abstractmethod
    def save_quiz_result(self, result: QuizResult) -> None:
        ...

    @abstractmethod
    def list_quiz_results(self, username: str) -> List[QuizResult]:
        ...
