"""
Event Handlers Registry
Allows services to subscribe to and handle events
"""

import logging
from typing import Callable, Dict, List, Any, Optional
from functools import wraps

from .event_schemas import BaseEvent, EventType
from backend.log_redaction import user_ref

logger = logging.getLogger(__name__)


class EventHandler:
    """
    Event handler wrapper

    Usage:
        @event_handler(EventType.USER_REGISTERED)
        def on_user_registered(event: UserRegisteredEvent):
            send_welcome_email(event.data['email'])
    """

    _handlers: Dict[str, List[Callable]] = {}

    @classmethod
    def register(cls, event_type: str, handler: Callable):
        """Register event handler"""
        if event_type not in cls._handlers:
            cls._handlers[event_type] = []

        cls._handlers[event_type].append(handler)
        logger.info(f"Registered handler '{handler.__name__}' for event '{event_type}'")

    @classmethod
    def handle(cls, event: BaseEvent) -> List[Dict[str, Any]]:
        """
        Handle event by calling all registered handlers

        Returns:
            List of results from handlers
        """
        event_type = event.type
        handlers = cls._handlers.get(event_type, [])

        if not handlers:
            logger.debug(f"No handlers registered for event type: {event_type}")
            return []

        results = []

        for handler in handlers:
            try:
                logger.debug(f"Calling handler '{handler.__name__}' for event '{event_type}'")
                result = handler(event)
                results.append({
                    "handler": handler.__name__,
                    "success": True,
                    "result": result,
                })
            except Exception as e:
                logger.error(
                    f"Handler '{handler.__name__}' failed for event '{event_type}': {e}",
                    exc_info=True
                )
                results.append({
                    "handler": handler.__name__,
                    "success": False,
                    "error": str(e),
                })

        return results

    @classmethod
    def get_handlers(cls, event_type: Optional[str] = None) -> Dict[str, List[Callable]]:
        """Get registered handlers"""
        if event_type:
            return {event_type: cls._handlers.get(event_type, [])}
        return cls._handlers

    @classmethod
    def clear_handlers(cls):
        """Clear all handlers (useful for testing)"""
        cls._handlers.clear()
        logger.info("Cleared all event handlers")


def event_handler(event_type: str):
    """
    Decorator to register event handler

    Usage:
        @event_handler(EventType.USER_REGISTERED)
        def handle_user_registration(event: UserRegisteredEvent):
            print(f"New user: {event.data['email']}")
    """
    def decorator(func: Callable) -> Callable:
        EventHandler.register(event_type, func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


def register_event_handler(event_type: str, handler: Callable):
    """Programmatically register event handler"""
    EventHandler.register(event_type, handler)


# Example handlers for common events

@event_handler(EventType.USER_REGISTERED)
def log_user_registration(event: BaseEvent):
    """Log user registration"""
    user_id = event.data.get('user_id')
    email = event.data.get('email')
    logger.info(f"New user registered: {user_ref(email)} (ID: {user_ref(user_id)})")


@event_handler(EventType.QUIZ_GRADED)
def notify_quiz_graded(event: BaseEvent):
    """Update mastery evidence and emit structured log for monitoring."""
    user_id = event.data.get('user_id')
    score = event.data.get('score')
    max_score = event.data.get('max_score')
    percentage = event.data.get('percentage')
    course_id = event.data.get('course_id')
    responses = event.data.get('responses', [])
    difficulty = event.data.get('difficulty', 'medium')

    logger.info(
        "Quiz graded for user %s: %s/%s (%.1f%%)",
        user_id, score, max_score, percentage or 0,
    )

    # Update per-objective mastery from item-level evidence (best-effort)
    if course_id and responses:
        try:
            from backend.services.learning_service import get_learning_service
            get_learning_service().record_assessment(user_id, course_id, responses, difficulty)
        except Exception as exc:
            logger.warning("quiz_graded mastery update failed: %s", exc)


@event_handler(EventType.APPOINTMENT_SCHEDULED)
def send_appointment_confirmation(event: BaseEvent):
    """Emit structured log for appointment; notification service hooks in when available."""
    user_id = event.data.get('user_id')
    title = event.data.get('title')
    start_time = event.data.get('start_time')

    logger.info(
        "Appointment scheduled | user=%s title=%r start=%s",
        user_id, title, start_time,
    )
    # Structured log is picked up by Loki/Prometheus for dashboard display.
    # Email/push notification can be wired here once a notification provider is configured:
    # from backend.services.notification_service import NotificationService
    # NotificationService().send(recipient=user_id, subject=f'Appointment: {title}', body=...)


@event_handler(EventType.DOCUMENT_PROCESSED)
def update_user_index_stats(event: BaseEvent):
    """Update user's index statistics in profile metadata (best-effort)."""
    user_id = event.data.get('user_id')
    chunk_count = event.data.get('chunk_count')
    embedding_count = event.data.get('embedding_count')

    logger.info(
        "Document processed for user %s: %s chunks, %s embeddings",
        user_id, chunk_count, embedding_count,
    )

    # Store cumulative indexing stats in user profile JSONB metadata
    try:
        from backend.services.profile_service import get_profile_service
        svc = get_profile_service()
        profile = svc.get_profile(user_id)
        user_meta = (profile.get("user", {}).get("metadata") or {}).copy()
        index_stats = user_meta.get("index_stats", {"total_chunks": 0, "total_embeddings": 0, "documents_processed": 0})
        index_stats["total_chunks"] = index_stats.get("total_chunks", 0) + (chunk_count or 0)
        index_stats["total_embeddings"] = index_stats.get("total_embeddings", 0) + (embedding_count or 0)
        index_stats["documents_processed"] = index_stats.get("documents_processed", 0) + 1
        user_meta["index_stats"] = index_stats
        svc.update_profile(user_id, {"metadata": user_meta})
    except Exception as exc:
        logger.warning("update_user_index_stats failed for user %s: %s", user_ref(user_id), exc)


@event_handler(EventType.CIRCUIT_BREAKER_OPENED)
def alert_circuit_breaker_opened(event: BaseEvent):
    """Emit a critical-severity structured log when a circuit breaker opens.

    Alertmanager scrapes this via the backend /metrics endpoint; a Prometheus
    alerting rule on ``smart_tutor_circuit_breaker_open`` triggers PagerDuty.
    """
    service_name = event.data.get('service_name')
    failure_count = event.data.get('failure_count')

    logger.critical(
        "CIRCUIT_BREAKER_OPEN service=%s failures=%s",
        service_name, failure_count,
    )

    # Increment Prometheus counter if available (best-effort)
    try:
        from backend.monitoring import circuit_breaker_open_total
        circuit_breaker_open_total.labels(service=service_name).inc()
    except Exception:
        pass  # Monitoring not initialised; the log entry is sufficient


# Async event handler support

import asyncio
from typing import Awaitable


class AsyncEventHandler:
    """Async event handler for async operations"""

    _handlers: Dict[str, List[Callable[..., Awaitable]]] = {}

    @classmethod
    def register(cls, event_type: str, handler: Callable[..., Awaitable]):
        """Register async event handler"""
        if event_type not in cls._handlers:
            cls._handlers[event_type] = []

        cls._handlers[event_type].append(handler)
        logger.info(f"Registered async handler '{handler.__name__}' for event '{event_type}'")

    @classmethod
    async def handle(cls, event: BaseEvent) -> List[Dict[str, Any]]:
        """Handle event asynchronously"""
        event_type = event.type
        handlers = cls._handlers.get(event_type, [])

        if not handlers:
            return []

        results = []

        for handler in handlers:
            try:
                logger.debug(f"Calling async handler '{handler.__name__}' for event '{event_type}'")
                result = await handler(event)
                results.append({
                    "handler": handler.__name__,
                    "success": True,
                    "result": result,
                })
            except Exception as e:
                logger.error(
                    f"Async handler '{handler.__name__}' failed for event '{event_type}': {e}",
                    exc_info=True
                )
                results.append({
                    "handler": handler.__name__,
                    "success": False,
                    "error": str(e),
                })

        return results


def async_event_handler(event_type: str):
    """
    Decorator for async event handlers

    Usage:
        @async_event_handler(EventType.MESSAGE_SENT)
        async def process_message(event: MessageSentEvent):
            await analyze_sentiment(event.data['content'])
    """
    def decorator(func: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        AsyncEventHandler.register(event_type, func)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator
