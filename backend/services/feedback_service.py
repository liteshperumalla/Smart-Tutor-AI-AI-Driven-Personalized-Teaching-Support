from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Literal

from backend.config import config


FeedbackCategory = Literal[
    "general",
    "feature",
    "content",
    "performance",
    "other",
]

BugSeverity = Literal["low", "medium", "high", "critical"]


class DuplicateFeedbackError(RuntimeError):
    """Raised when the same feedback or bug is submitted repeatedly."""


@dataclass
class FeedbackEntry:
    username: str
    name: str
    email: str
    category: FeedbackCategory
    message: str
    created_at: datetime


@dataclass
class BugReportEntry:
    username: str
    name: str
    email: str
    feature: str
    severity: BugSeverity
    description: str
    steps: str
    created_at: datetime


class FeedbackService:
    def __init__(self) -> None:
        logs_root = Path(getattr(config, "LOGS_DIR", "logs"))
        logs_root.mkdir(parents=True, exist_ok=True)
        self.feedback_file = logs_root / "feedback_log.txt"
        self.bug_file = logs_root / "bug_reports_log.txt"
        self.user_root = Path(config.USER_DATA_ROOT)
        self.user_root.mkdir(parents=True, exist_ok=True)

    def log_feedback(self, entry: FeedbackEntry) -> None:
        if self._has_duplicate_feedback(entry):
            raise DuplicateFeedbackError(
                "A matching feedback submission was already received recently."
            )
        with self.feedback_file.open("a", encoding="utf-8") as f:
            f.write(self._serialize_feedback(entry))
        self._append_user_entry(entry.username, "feedback", {
            "category": entry.category,
            "message": entry.message,
            "created_at": entry.created_at.isoformat(),
            "name": entry.name,
            "email": entry.email,
        })

    def log_bug_report(self, entry: BugReportEntry) -> None:
        if self._has_duplicate_bug(entry):
            raise DuplicateFeedbackError(
                "A matching bug report was already received recently."
            )
        with self.bug_file.open("a", encoding="utf-8") as f:
            f.write(self._serialize_bug(entry))
        self._append_user_entry(entry.username, "bug", {
            "feature": entry.feature,
            "severity": entry.severity,
            "description": entry.description,
            "steps": entry.steps,
            "created_at": entry.created_at.isoformat(),
            "name": entry.name,
            "email": entry.email,
        })

    def _serialize_feedback(self, entry: FeedbackEntry) -> str:
        lines = [
            "\n--- Feedback Entry ---",
            f"Timestamp: {entry.created_at.isoformat()}",
            f"Name: {entry.name or 'Anonymous'}",
            f"Email: {entry.email or 'Not provided'}",
            f"Category: {entry.category}",
            "Message:",
            entry.message,
            "--- End of Entry ---\n",
        ]
        return "\n".join(lines)

    def _serialize_bug(self, entry: BugReportEntry) -> str:
        lines = [
            "\n--- Bug Report Entry ---",
            f"Timestamp: {entry.created_at.isoformat()}",
            f"Reporter Name: {entry.name or 'Anonymous'}",
            f"Reporter Email: {entry.email or 'Not provided'}",
            f"Page/Feature: {entry.feature}",
            f"Severity: {entry.severity}",
            "Description:",
            entry.description,
        ]
        if entry.steps.strip():
            lines.extend(["Steps to Reproduce:", entry.steps])
        lines.append("--- End of Entry ---\n")
        return "\n".join(lines)

    def _user_feedback_dir(self, username: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in username)
        directory = self.user_root / safe / "feedback"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _append_user_entry(self, username: str, kind: str, data: Dict[str, object]) -> None:
        directory = self._user_feedback_dir(username)
        path = directory / f"{kind}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def _read_entries(self, username: str, kind: str) -> List[Dict[str, object]]:
        path = self._user_feedback_dir(username) / f"{kind}.jsonl"
        if not path.exists():
            return []
        entries: List[Dict[str, object]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        entries.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return entries

    def _has_duplicate_feedback(self, entry: FeedbackEntry) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        for existing in self._read_entries(entry.username, "feedback"):
            created_at = existing.get("created_at")
            try:
                created = datetime.fromisoformat(str(created_at))
            except Exception:
                continue
            if created < cutoff:
                break
            if (
                str(existing.get("category", "")).strip().lower() == entry.category.strip().lower()
                and str(existing.get("message", "")).strip().lower() == entry.message.strip().lower()
            ):
                return True
        return False

    def _has_duplicate_bug(self, entry: BugReportEntry) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        for existing in self._read_entries(entry.username, "bug"):
            created_at = existing.get("created_at")
            try:
                created = datetime.fromisoformat(str(created_at))
            except Exception:
                continue
            if created < cutoff:
                break
            if (
                str(existing.get("feature", "")).strip().lower() == entry.feature.strip().lower()
                and str(existing.get("description", "")).strip().lower() == entry.description.strip().lower()
                and str(existing.get("steps", "")).strip().lower() == entry.steps.strip().lower()
            ):
                return True
        return False

    def list_entries(self, username: str) -> Dict[str, List[Dict[str, object]]]:
        return {
            "feedback": self._read_entries(username, "feedback"),
            "bugs": self._read_entries(username, "bug"),
        }


_feedback_service: FeedbackService | None = None


def get_feedback_service() -> FeedbackService:
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = FeedbackService()
    return _feedback_service
