from __future__ import annotations

import threading
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
        from backend.config import config as app_config
        import logging
        _logger = logging.getLogger(__name__)

        # Pre-flight circuit breaker check — fast-fail before building generator
        from backend.circuit_breaker import bedrock_circuit_breaker, CircuitBreakerOpenError
        if bedrock_circuit_breaker.state.value == "open":
            raise CircuitBreakerOpenError("bedrock", bedrock_circuit_breaker.recovery_timeout)

        routed_model_id = model_id

        # LLM Complexity Routing: select model based on query complexity
        if not model_id and app_config.LLM_ROUTING_ENABLED:
            from backend.llm_router import classify_query_complexity, select_model_for_complexity
            tier, confidence = classify_query_complexity(query)
            routed_model_id = select_model_for_complexity(tier)
            _logger.info(f"LLM routing: {tier} (conf={confidence:.2f}) -> {routed_model_id}")

        if app_config.AGENT_SYSTEM_ENABLED:
            from backend.agents import run_agent_pipeline
            generator, sources = run_agent_pipeline(
                query=query, user_id=user_id,
                session_id=session_id, model_id=routed_model_id,
            )
            return generator, sources, routed_model_id

        generator, sources = generate_response_stream_and_sources(
            query, user_id=user_id, session_id=session_id, model_id=routed_model_id
        )
        return generator, sources, routed_model_id

    def get_session(self, username: str, session_id: str) -> Optional[ChatSession]:
        return self.load_session(username, session_id)


_chat_service = None


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


_llm_semaphore: threading.Semaphore | None = None


def get_llm_semaphore() -> threading.Semaphore:
    """Return the module-level semaphore that caps concurrent LLM synthesis calls."""
    global _llm_semaphore
    if _llm_semaphore is None:
        from backend.config import config as app_config
        _llm_semaphore = threading.Semaphore(app_config.LLM_MAX_CONCURRENT)
    return _llm_semaphore
