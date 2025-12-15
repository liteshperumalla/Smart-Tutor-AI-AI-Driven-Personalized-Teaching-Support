from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, Field

from backend.api.dependencies import get_current_session
from backend.services.feedback_service import (
    FeedbackEntry,
    FeedbackService,
    BugReportEntry,
    get_feedback_service,
)


router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackPayload(BaseModel):
    category: Literal["general", "feature", "content", "performance", "other"]
    message: str = Field(..., min_length=10)
    name: str | None = None
    email: EmailStr | None = None


class BugReportPayload(BaseModel):
    feature: str = Field(..., min_length=3)
    severity: Literal["low", "medium", "high", "critical"]
    description: str = Field(..., min_length=10)
    steps: str | None = None
    name: str | None = None
    email: EmailStr | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
def submit_feedback(
    payload: FeedbackPayload,
    session=Depends(get_current_session),
    service: FeedbackService = Depends(get_feedback_service),
):
    _, user = session
    entry = FeedbackEntry(
        username=user["username"],
        name=payload.name or "",
        email=payload.email or "",
        category=payload.category,
        message=payload.message,
        created_at=datetime.utcnow(),
    )
    service.log_feedback(entry)
    return {"ok": True}


@router.post("/bug", status_code=status.HTTP_201_CREATED)
def submit_bug(
    payload: BugReportPayload,
    session=Depends(get_current_session),
    service: FeedbackService = Depends(get_feedback_service),
):
    _, user = session
    entry = BugReportEntry(
        username=user["username"],
        name=payload.name or "",
        email=payload.email or "",
        feature=payload.feature,
        severity=payload.severity,
        description=payload.description,
        steps=payload.steps or "",
        created_at=datetime.utcnow(),
    )
    service.log_bug_report(entry)
    return {"ok": True}
