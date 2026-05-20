from datetime import datetime, timezone

import pytest

from backend.config import config
from backend.services.feedback_service import (
    BugReportEntry,
    DuplicateFeedbackError,
    FeedbackEntry,
    FeedbackService,
)


def test_feedback_service_rejects_recent_duplicate_feedback(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "USER_DATA_ROOT", str(tmp_path / "user_data"))
    monkeypatch.setattr(config, "LOGS_DIR", str(tmp_path / "logs"))
    service = FeedbackService()

    entry = FeedbackEntry(
        username="alice",
        name="Alice",
        email="alice@example.com",
        category="general",
        message="This dashboard flow is very helpful and clear.",
        created_at=datetime.now(timezone.utc),
    )

    service.log_feedback(entry)

    with pytest.raises(DuplicateFeedbackError):
        service.log_feedback(
            FeedbackEntry(
                username="alice",
                name="Alice",
                email="alice@example.com",
                category="general",
                message="This dashboard flow is very helpful and clear.",
                created_at=datetime.now(timezone.utc),
            )
        )


def test_feedback_service_rejects_recent_duplicate_bug(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "USER_DATA_ROOT", str(tmp_path / "user_data"))
    monkeypatch.setattr(config, "LOGS_DIR", str(tmp_path / "logs"))
    service = FeedbackService()

    entry = BugReportEntry(
        username="alice",
        name="Alice",
        email="alice@example.com",
        feature="Quiz",
        severity="high",
        description="Quiz generation fails after selecting a module.",
        steps="Open quiz, select topic, click generate.",
        created_at=datetime.now(timezone.utc),
    )

    service.log_bug_report(entry)

    with pytest.raises(DuplicateFeedbackError):
        service.log_bug_report(
            BugReportEntry(
                username="alice",
                name="Alice",
                email="alice@example.com",
                feature="Quiz",
                severity="high",
                description="Quiz generation fails after selecting a module.",
                steps="Open quiz, select topic, click generate.",
                created_at=datetime.now(timezone.utc),
            )
        )
