"""
Event Handlers Registry
Allows services to subscribe to and handle events
"""

import logging
from typing import Callable, Dict, List, Any
from functools import wraps

from .event_schemas import BaseEvent, EventType

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
    logger.info(f"New user registered: {email} (ID: {user_id})")


@event_handler(EventType.QUIZ_GRADED)
def notify_quiz_graded(event: BaseEvent):
    """Send notification when quiz is graded"""
    user_id = event.data.get('user_id')
    score = event.data.get('score')
    max_score = event.data.get('max_score')
    percentage = event.data.get('percentage')

    logger.info(f"Quiz graded for user {user_id}: {score}/{max_score} ({percentage}%)")

    # TODO: Send notification via notification service
    # from backend.services.notification_service import send_quiz_result_notification
    # send_quiz_result_notification(user_id, score, max_score, percentage)


@event_handler(EventType.APPOINTMENT_SCHEDULED)
def send_appointment_confirmation(event: BaseEvent):
    """Send appointment confirmation"""
    user_id = event.data.get('user_id')
    title = event.data.get('title')
    start_time = event.data.get('start_time')

    logger.info(f"Appointment scheduled for user {user_id}: {title} at {start_time}")

    # TODO: Send email confirmation
    # from backend.services.notification_service import send_appointment_email
    # send_appointment_email(user_id, title, start_time)


@event_handler(EventType.DOCUMENT_PROCESSED)
def update_user_index_stats(event: BaseEvent):
    """Update user's index statistics"""
    user_id = event.data.get('user_id')
    chunk_count = event.data.get('chunk_count')
    embedding_count = event.data.get('embedding_count')

    logger.info(
        f"Document processed for user {user_id}: "
        f"{chunk_count} chunks, {embedding_count} embeddings"
    )

    # TODO: Update user statistics in database
    # from backend.services.profile_service import update_index_stats
    # update_index_stats(user_id, chunk_count, embedding_count)


@event_handler(EventType.CIRCUIT_BREAKER_OPENED)
def alert_circuit_breaker_opened(event: BaseEvent):
    """Alert when circuit breaker opens"""
    service_name = event.data.get('service_name')
    failure_count = event.data.get('failure_count')

    logger.error(
        f"ALERT: Circuit breaker opened for {service_name} "
        f"after {failure_count} failures"
    )

    # TODO: Send alert to ops team
    # from backend.services.notification_service import send_alert
    # send_alert(f"Circuit breaker opened: {service_name}")


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
