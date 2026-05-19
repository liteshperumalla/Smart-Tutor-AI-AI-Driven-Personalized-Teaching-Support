"""
Event Schemas for Event-Driven Architecture
Defines all domain events following CloudEvents specification
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class EventType(str, Enum):
    """Event types"""
    # User events
    USER_REGISTERED = "user.registered"
    USER_LOGGED_IN = "user.logged_in"
    USER_LOGGED_OUT = "user.logged_out"
    USER_PROFILE_UPDATED = "user.profile_updated"

    # Chat events
    CHAT_SESSION_CREATED = "chat.session_created"
    CHAT_SESSION_ENDED = "chat.session_ended"
    MESSAGE_SENT = "chat.message_sent"

    # Content events
    DOCUMENT_UPLOADED = "content.document_uploaded"
    DOCUMENT_PROCESSED = "content.document_processed"
    INDEX_UPDATED = "content.index_updated"

    # Quiz events
    QUIZ_GENERATED = "quiz.generated"
    QUIZ_SUBMITTED = "quiz.submitted"
    QUIZ_GRADED = "quiz.graded"

    # Research events
    RESEARCH_QUERY_EXECUTED = "research.query_executed"

    # Appointment events
    APPOINTMENT_SCHEDULED = "appointment.scheduled"
    APPOINTMENT_CANCELLED = "appointment.cancelled"
    APPOINTMENT_REMINDER = "appointment.reminder"

    # Notification events
    NOTIFICATION_SENT = "notification.sent"
    NOTIFICATION_FAILED = "notification.failed"

    # System events
    HEALTH_CHECK_FAILED = "system.health_check_failed"
    CIRCUIT_BREAKER_OPENED = "system.circuit_breaker_opened"


class BaseEvent(BaseModel):
    """
    Base event following CloudEvents specification
    https://cloudevents.io/
    """

    # CloudEvents required fields
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str  # Service that generated the event
    spec_version: str = Field(default="1.0", alias="specversion")
    type: str  # Event type

    # CloudEvents optional fields
    data_content_type: Optional[str] = Field(default="application/json", alias="datacontenttype")
    data_schema: Optional[str] = Field(default=None, alias="dataschema")
    subject: Optional[str] = None  # Resource the event is about
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Custom fields
    data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    def to_eventbridge_entry(self, event_bus_name: str) -> Dict[str, Any]:
        """Convert to EventBridge PutEvents entry format"""
        return {
            "Source": self.source,
            "DetailType": self.type,
            "Detail": self.model_dump_json(),
            "EventBusName": event_bus_name,
            "Time": self.time,
        }

    def to_sns_message(self) -> Dict[str, Any]:
        """Convert to SNS message format"""
        return {
            "Message": self.model_dump_json(),
            "Subject": self.type,
            "MessageAttributes": {
                "event_type": {
                    "DataType": "String",
                    "StringValue": self.type,
                },
                "source": {
                    "DataType": "String",
                    "StringValue": self.source,
                },
            },
        }


# User Events

class UserRegisteredEvent(BaseEvent):
    """User registration event"""
    type: str = EventType.USER_REGISTERED
    source: str = "auth-service"

    def __init__(self, user_id: str, email: str, **kwargs):
        super().__init__(
            subject=f"user/{user_id}",
            data={
                "user_id": user_id,
                "email": email,
            },
            **kwargs
        )


class UserLoggedInEvent(BaseEvent):
    """User login event"""
    type: str = EventType.USER_LOGGED_IN
    source: str = "auth-service"

    def __init__(self, user_id: str, session_id: str, **kwargs):
        super().__init__(
            subject=f"user/{user_id}",
            data={
                "user_id": user_id,
                "session_id": session_id,
            },
            **kwargs
        )


class UserLoggedOutEvent(BaseEvent):
    """User logout event"""
    type: str = EventType.USER_LOGGED_OUT
    source: str = "auth-service"

    def __init__(self, user_id: str, session_id: str, **kwargs):
        super().__init__(
            subject=f"user/{user_id}",
            data={
                "user_id": user_id,
                "session_id": session_id,
            },
            **kwargs
        )


class UserProfileUpdatedEvent(BaseEvent):
    """User profile update event"""
    type: str = EventType.USER_PROFILE_UPDATED
    source: str = "auth-service"

    def __init__(self, user_id: str, updated_fields: Dict[str, Any], **kwargs):
        super().__init__(
            subject=f"user/{user_id}",
            data={
                "user_id": user_id,
                "updated_fields": updated_fields,
            },
            **kwargs
        )


# Chat Events

class ChatSessionCreatedEvent(BaseEvent):
    """Chat session creation event"""
    type: str = EventType.CHAT_SESSION_CREATED
    source: str = "chat-service"

    def __init__(self, session_id: str, user_id: str, title: str = "New Chat", **kwargs):
        super().__init__(
            subject=f"chat/{session_id}",
            data={
                "session_id": session_id,
                "user_id": user_id,
                "title": title,
            },
            **kwargs
        )


class ChatSessionEndedEvent(BaseEvent):
    """Chat session ended event"""
    type: str = EventType.CHAT_SESSION_ENDED
    source: str = "chat-service"

    def __init__(self, session_id: str, user_id: str, message_count: int, **kwargs):
        super().__init__(
            subject=f"chat/{session_id}",
            data={
                "session_id": session_id,
                "user_id": user_id,
                "message_count": message_count,
            },
            **kwargs
        )


class MessageSentEvent(BaseEvent):
    """Message sent event"""
    type: str = EventType.MESSAGE_SENT
    source: str = "chat-service"

    def __init__(
        self,
        session_id: str,
        user_id: str,
        message_id: str,
        role: str,
        content: str,
        **kwargs
    ):
        super().__init__(
            subject=f"chat/{session_id}/message/{message_id}",
            data={
                "session_id": session_id,
                "user_id": user_id,
                "message_id": message_id,
                "role": role,
                "content": content[:500],  # Truncate long content
            },
            **kwargs
        )


# Content Events

class DocumentUploadedEvent(BaseEvent):
    """Document upload event"""
    type: str = EventType.DOCUMENT_UPLOADED
    source: str = "content-service"

    def __init__(
        self,
        document_id: str,
        user_id: str,
        filename: str,
        file_type: str,
        file_size: int,
        s3_key: str,
        **kwargs
    ):
        super().__init__(
            subject=f"document/{document_id}",
            data={
                "document_id": document_id,
                "user_id": user_id,
                "filename": filename,
                "file_type": file_type,
                "file_size": file_size,
                "s3_key": s3_key,
            },
            **kwargs
        )


class DocumentProcessedEvent(BaseEvent):
    """Document processing complete event"""
    type: str = EventType.DOCUMENT_PROCESSED
    source: str = "content-service"

    def __init__(
        self,
        document_id: str,
        user_id: str,
        chunk_count: int,
        embedding_count: int,
        processing_time_ms: float,
        **kwargs
    ):
        super().__init__(
            subject=f"document/{document_id}",
            data={
                "document_id": document_id,
                "user_id": user_id,
                "chunk_count": chunk_count,
                "embedding_count": embedding_count,
                "processing_time_ms": processing_time_ms,
            },
            **kwargs
        )


class IndexUpdatedEvent(BaseEvent):
    """Index update event"""
    type: str = EventType.INDEX_UPDATED
    source: str = "content-service"

    def __init__(self, user_id: str, document_count: int, **kwargs):
        super().__init__(
            subject=f"index/{user_id}",
            data={
                "user_id": user_id,
                "document_count": document_count,
            },
            **kwargs
        )


# Quiz Events

class QuizGeneratedEvent(BaseEvent):
    """Quiz generation event"""
    type: str = EventType.QUIZ_GENERATED
    source: str = "quiz-service"

    def __init__(
        self,
        quiz_id: str,
        user_id: str,
        question_count: int,
        topic: str,
        **kwargs
    ):
        super().__init__(
            subject=f"quiz/{quiz_id}",
            data={
                "quiz_id": quiz_id,
                "user_id": user_id,
                "question_count": question_count,
                "topic": topic,
            },
            **kwargs
        )


class QuizSubmittedEvent(BaseEvent):
    """Quiz submission event"""
    type: str = EventType.QUIZ_SUBMITTED
    source: str = "quiz-service"

    def __init__(
        self,
        quiz_id: str,
        user_id: str,
        submission_id: str,
        **kwargs
    ):
        super().__init__(
            subject=f"quiz/{quiz_id}/submission/{submission_id}",
            data={
                "quiz_id": quiz_id,
                "user_id": user_id,
                "submission_id": submission_id,
            },
            **kwargs
        )


class QuizGradedEvent(BaseEvent):
    """Quiz grading complete event"""
    type: str = EventType.QUIZ_GRADED
    source: str = "quiz-service"

    def __init__(
        self,
        quiz_id: str,
        user_id: str,
        submission_id: str,
        score: float,
        max_score: float,
        percentage: float,
        **kwargs
    ):
        super().__init__(
            subject=f"quiz/{quiz_id}/submission/{submission_id}",
            data={
                "quiz_id": quiz_id,
                "user_id": user_id,
                "submission_id": submission_id,
                "score": score,
                "max_score": max_score,
                "percentage": percentage,
            },
            **kwargs
        )


# Research Events

class ResearchQueryExecutedEvent(BaseEvent):
    """Research query executed event"""
    type: str = EventType.RESEARCH_QUERY_EXECUTED
    source: str = "research-service"

    def __init__(
        self,
        query_id: str,
        user_id: str,
        query: str,
        result_count: int,
        **kwargs
    ):
        super().__init__(
            subject=f"research/{query_id}",
            data={
                "query_id": query_id,
                "user_id": user_id,
                "query": query,
                "result_count": result_count,
            },
            **kwargs
        )


# Appointment Events

class AppointmentScheduledEvent(BaseEvent):
    """Appointment scheduled event"""
    type: str = EventType.APPOINTMENT_SCHEDULED
    source: str = "appointment-service"

    def __init__(
        self,
        appointment_id: str,
        user_id: str,
        title: str,
        start_time: datetime,
        end_time: datetime,
        **kwargs
    ):
        super().__init__(
            subject=f"appointment/{appointment_id}",
            data={
                "appointment_id": appointment_id,
                "user_id": user_id,
                "title": title,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
            },
            **kwargs
        )


class AppointmentCancelledEvent(BaseEvent):
    """Appointment cancelled event"""
    type: str = EventType.APPOINTMENT_CANCELLED
    source: str = "appointment-service"

    def __init__(
        self,
        appointment_id: str,
        user_id: str,
        reason: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            subject=f"appointment/{appointment_id}",
            data={
                "appointment_id": appointment_id,
                "user_id": user_id,
                "reason": reason,
            },
            **kwargs
        )


# Notification Events

class NotificationSentEvent(BaseEvent):
    """Notification sent event"""
    type: str = EventType.NOTIFICATION_SENT
    source: str = "notification-service"

    def __init__(
        self,
        notification_id: str,
        user_id: str,
        channel: str,  # email, push, sms
        subject: str,
        **kwargs
    ):
        super().__init__(
            subject=f"notification/{notification_id}",
            data={
                "notification_id": notification_id,
                "user_id": user_id,
                "channel": channel,
                "subject": subject,
            },
            **kwargs
        )


class NotificationFailedEvent(BaseEvent):
    """Notification failed event"""
    type: str = EventType.NOTIFICATION_FAILED
    source: str = "notification-service"

    def __init__(
        self,
        notification_id: str,
        user_id: str,
        channel: str,
        error: str,
        **kwargs
    ):
        super().__init__(
            subject=f"notification/{notification_id}",
            data={
                "notification_id": notification_id,
                "user_id": user_id,
                "channel": channel,
                "error": error,
            },
            **kwargs
        )


# System Events

class HealthCheckFailedEvent(BaseEvent):
    """Health check failed event"""
    type: str = EventType.HEALTH_CHECK_FAILED
    source: str = "system"

    def __init__(
        self,
        service_name: str,
        check_name: str,
        error: str,
        **kwargs
    ):
        super().__init__(
            subject=f"health/{service_name}",
            data={
                "service_name": service_name,
                "check_name": check_name,
                "error": error,
            },
            **kwargs
        )


class CircuitBreakerOpenedEvent(BaseEvent):
    """Circuit breaker opened event"""
    type: str = EventType.CIRCUIT_BREAKER_OPENED
    source: str = "system"

    def __init__(
        self,
        service_name: str,
        failure_count: int,
        **kwargs
    ):
        super().__init__(
            subject=f"circuit-breaker/{service_name}",
            data={
                "service_name": service_name,
                "failure_count": failure_count,
            },
            **kwargs
        )
