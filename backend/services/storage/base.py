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
