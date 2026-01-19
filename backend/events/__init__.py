"""
Event-Driven Architecture Implementation
Supports EventBridge, SNS, and SQS for async messaging
"""

from .event_bus import EventBus, get_event_bus
from .event_schemas import (
    BaseEvent,
    UserRegisteredEvent,
    UserLoggedInEvent,
    UserLoggedOutEvent,
    ChatSessionCreatedEvent,
    MessageSentEvent,
    DocumentUploadedEvent,
    QuizGeneratedEvent,
    QuizSubmittedEvent,
    AppointmentScheduledEvent,
)
from .event_handlers import EventHandler, register_event_handler

__all__ = [
    'EventBus',
    'get_event_bus',
    'BaseEvent',
    'UserRegisteredEvent',
    'UserLoggedInEvent',
    'UserLoggedOutEvent',
    'ChatSessionCreatedEvent',
    'MessageSentEvent',
    'DocumentUploadedEvent',
    'QuizGeneratedEvent',
    'QuizSubmittedEvent',
    'AppointmentScheduledEvent',
    'EventHandler',
    'register_event_handler',
]
