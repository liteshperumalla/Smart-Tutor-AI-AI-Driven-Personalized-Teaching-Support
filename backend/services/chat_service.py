from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from backend.services import get_storage_backend
from backend.services.models import ChatMessage, ChatSession
from utils import (
    generate_response_stream_and_sources,
    sanitize_filename,
    make_session_title,
)


class ChatService:
    def __init__(self):
        self.storage = get_storage_backend()

    def list_sessions(self, username: str):
        return self.storage.list_chat_sessions(username)

    def load_session(self, username: str, session_id: str) -> Optional[ChatSession]:
        return self.storage.load_chat_session(username, session_id)

    def save_session(self, username: str, session: ChatSession) -> None:
        session.updated_at = datetime.utcnow()
        self.storage.save_chat_session(username, session)

    def create_session(self, username: str, title: Optional[str] = None) -> ChatSession:
        session_id = sanitize_filename(title or f"{username}-{datetime.utcnow().timestamp()}")
        default_title = title.strip() if isinstance(title, str) and title.strip() else "New chat"
        session = ChatSession(
            id=session_id,
            title=default_title,
            messages=[],
        )
        self.save_session(username, session)
        return session

    def append_message(self, session: ChatSession, message: ChatMessage) -> None:
        session.messages.append(message)
        session.updated_at = datetime.utcnow()
        if message.role == "assistant":
            title = make_session_title([[msg.role, msg.content] for msg in session.messages])
            if title and title != session.title:
                session.title = title

    def delete_session(self, username: str, session_id: str) -> bool:
        return self.storage.delete_chat_session(username, session_id)

    def rename_session(self, username: str, session_id: str, title: str) -> Optional[ChatSession]:
        session = self.load_session(username, session_id)
        if not session:
            return None
        session.title = title
        self.save_session(username, session)
        return session

    def update_session(self, username: str, session_id: str, updates: dict) -> Optional[ChatSession]:
        """Update session with provided fields (title, is_pinned, is_archived)."""
        session = self.load_session(username, session_id)
        if not session:
            return None

        if "title" in updates:
            session.title = updates["title"]
        if "is_pinned" in updates:
            session.is_pinned = updates["is_pinned"]
        if "is_archived" in updates:
            session.is_archived = updates["is_archived"]

        self.save_session(username, session)
        return session

    def stream_response(
        self, query: str, user_id: str, session_id: Optional[str] = None, model_id: Optional[str] = None
    ):
        generator, sources = generate_response_stream_and_sources(
            query, user_id=user_id, session_id=session_id, model_id=model_id
        )
        return generator, sources

    def get_session(self, username: str, session_id: str) -> Optional[ChatSession]:
        return self.load_session(username, session_id)


_chat_service = None


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
