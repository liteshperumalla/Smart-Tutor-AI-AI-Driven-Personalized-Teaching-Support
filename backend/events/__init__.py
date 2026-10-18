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
from .outbox import OutboxPublisher, get_outbox_publisher, record_outbox_event
from .cdc import CDCEngine, CDCStreamConsumer, get_cdc_engine, get_cdc_consumer
from .event_schemas import CDCEnvelope, CDCOperation, CDCSource

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
    'OutboxPublisher',
    'get_outbox_publisher',
    'record_outbox_event',
    'CDCEngine',
    'CDCStreamConsumer',
    'get_cdc_engine',
    'get_cdc_consumer',
    'CDCEnvelope',
    'CDCOperation',
    'CDCSource',
]

