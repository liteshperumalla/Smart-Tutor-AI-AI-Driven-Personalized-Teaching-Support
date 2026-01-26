"""
Message Feedback Service

Handles storage and retrieval of message feedback (likes, dislikes, reports)
using JSONL files for persistent storage.
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Literal, Optional
from pathlib import Path

from backend.config import Config


FeedbackType = Literal["thumbs_up", "thumbs_down", "report"]


@dataclass
class MessageFeedback:
    """Represents feedback on a specific chat message."""
    session_id: str
    message_index: int
    feedback_type: FeedbackType
    reason: Optional[str] = None
    created_at: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MessageFeedback":
        return cls(
            session_id=data["session_id"],
            message_index=data["message_index"],
            feedback_type=data["feedback_type"],
            reason=data.get("reason"),
            created_at=data.get("created_at"),
        )


class MessageFeedbackService:
    """Service for managing message feedback stored in JSONL files."""

    def __init__(self, user_data_root: str | None = None):
        self.user_data_root = Path(user_data_root or Config.USER_DATA_ROOT)

    def _get_feedback_dir(self, username: str) -> Path:
        """Get the feedback directory for a user."""
        return self.user_data_root / username / "message_feedback"

    def _get_feedback_file(self, username: str) -> Path:
        """Get the feedback JSONL file path for a user."""
        return self._get_feedback_dir(username) / "feedback.jsonl"

    def _ensure_dir(self, username: str) -> None:
        """Ensure the feedback directory exists."""
        feedback_dir = self._get_feedback_dir(username)
        feedback_dir.mkdir(parents=True, exist_ok=True)

    def save_feedback(self, username: str, feedback: MessageFeedback) -> MessageFeedback:
        """
        Save feedback to the user's JSONL file.

        If feedback for the same session_id and message_index already exists,
        it will be replaced (for like/dislike toggle behavior).
        """
        self._ensure_dir(username)
        feedback_file = self._get_feedback_file(username)

        # Load existing feedback
        existing_feedback = self.list_feedback(username)

        # Filter out any existing feedback for the same message
        # (allows toggling between thumbs_up and thumbs_down)
        filtered_feedback = [
            f for f in existing_feedback
            if not (f.session_id == feedback.session_id and
                   f.message_index == feedback.message_index and
                   f.feedback_type in ("thumbs_up", "thumbs_down") and
                   feedback.feedback_type in ("thumbs_up", "thumbs_down"))
        ]

        # Add the new feedback
        filtered_feedback.append(feedback)

        # Write all feedback back to file
        with open(feedback_file, "w") as f:
            for fb in filtered_feedback:
                f.write(json.dumps(fb.to_dict()) + "\n")

        return feedback

    def remove_feedback(
        self,
        username: str,
        session_id: str,
        message_index: int,
        feedback_type: Optional[FeedbackType] = None
    ) -> bool:
        """
        Remove feedback for a specific message.

        If feedback_type is specified, only removes that type.
        Otherwise, removes all thumbs_up/thumbs_down feedback for the message.
        """
        feedback_file = self._get_feedback_file(username)
        if not feedback_file.exists():
            return False

        existing_feedback = self.list_feedback(username)

        if feedback_type:
            # Remove specific type
            filtered = [
                f for f in existing_feedback
                if not (f.session_id == session_id and
                       f.message_index == message_index and
                       f.feedback_type == feedback_type)
            ]
        else:
            # Remove all thumbs up/down for this message
            filtered = [
                f for f in existing_feedback
                if not (f.session_id == session_id and
                       f.message_index == message_index and
                       f.feedback_type in ("thumbs_up", "thumbs_down"))
            ]

        if len(filtered) == len(existing_feedback):
            return False  # Nothing was removed

        # Write back
        with open(feedback_file, "w") as f:
            for fb in filtered:
                f.write(json.dumps(fb.to_dict()) + "\n")

        return True

    def list_feedback(self, username: str) -> list[MessageFeedback]:
        """List all feedback for a user."""
        feedback_file = self._get_feedback_file(username)
        if not feedback_file.exists():
            return []

        feedback_list = []
        with open(feedback_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        feedback_list.append(MessageFeedback.from_dict(data))
                    except json.JSONDecodeError:
                        continue  # Skip malformed lines

        return feedback_list

    def get_feedback_for_session(
        self,
        username: str,
        session_id: str
    ) -> list[MessageFeedback]:
        """Get all feedback for a specific session."""
        all_feedback = self.list_feedback(username)
        return [f for f in all_feedback if f.session_id == session_id]

    def get_feedback_for_message(
        self,
        username: str,
        session_id: str,
        message_index: int
    ) -> Optional[MessageFeedback]:
        """
        Get the current feedback (thumbs_up or thumbs_down) for a specific message.

        Returns the most recent like/dislike feedback, not reports.
        """
        session_feedback = self.get_feedback_for_session(username, session_id)

        # Find thumbs up/down feedback for this message
        for fb in reversed(session_feedback):  # Most recent first
            if (fb.message_index == message_index and
                fb.feedback_type in ("thumbs_up", "thumbs_down")):
                return fb

        return None

    def get_reports_for_session(
        self,
        username: str,
        session_id: str
    ) -> list[MessageFeedback]:
        """Get all reports for a specific session."""
        session_feedback = self.get_feedback_for_session(username, session_id)
        return [f for f in session_feedback if f.feedback_type == "report"]


# Singleton instance
_feedback_service: Optional[MessageFeedbackService] = None


def get_feedback_service() -> MessageFeedbackService:
    """Get the singleton feedback service instance."""
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = MessageFeedbackService()
    return _feedback_service
