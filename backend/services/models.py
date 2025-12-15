from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal, Optional


RoleType = Literal["user", "assistant", "system"]


@dataclass
class ChatMessage:
    role: RoleType
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sources: Optional[List[dict]] = None

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "sources": self.sources or [],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        timestamp = data.get("timestamp")
        ts = datetime.fromisoformat(timestamp) if timestamp else datetime.utcnow()
        return cls(
            role=data.get("role", "assistant"),
            content=data.get("content", ""),
            timestamp=ts,
            sources=data.get("sources"),
        )


@dataclass
class ChatSession:
    id: str
    title: str
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        # Handle both ChatMessage objects and dicts (from DynamoDB)
        messages_list = []
        for m in self.messages:
            if isinstance(m, dict):
                messages_list.append(m)
            else:
                messages_list.append(m.to_dict())

        return {
            "id": self.id,
            "title": self.title,
            "messages": messages_list,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }


@dataclass
class QuizResult:
    id: str
    user_id: str
    score: int
    total_questions: int
    percentage: float
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "score": self.score,
            "total_questions": self.total_questions,
            "percentage": self.percentage,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class Appointment:
    id: str
    user_id: str
    user_name: str
    user_email: str
    appointment_with: str
    preferred_date: str
    preferred_time: str
    primary_reason: str
    additional_details: str
    status: str = "pending"
    requested_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "user_email": self.user_email,
            "appointment_with": self.appointment_with,
            "preferred_date": self.preferred_date,
            "preferred_time": self.preferred_time,
            "primary_reason": self.primary_reason,
            "additional_details": self.additional_details,
            "status": self.status,
            "requested_at": self.requested_at.isoformat(),
        }
