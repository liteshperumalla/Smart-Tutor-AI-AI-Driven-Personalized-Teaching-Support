from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from backend.api.dependencies import get_current_session, get_rate_limiter_dep
from backend.rate_limiter import limiter, PerUserRateLimiter
from backend.services.feedback_service import (
    FeedbackEntry,
    FeedbackService,
    BugReportEntry,
    DuplicateFeedbackError,
    get_feedback_service,
)
from backend.services.notification_service import notify_feedback_received


router = APIRouter(prefix="/feedback", tags=["feedback"])

_FEEDBACK_LIMIT = 12
_FEEDBACK_WINDOW = 3600


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
@limiter.limit("20/hour")
async def submit_feedback(
    request: Request,
    payload: FeedbackPayload,
    session=Depends(get_current_session),
    service: FeedbackService = Depends(get_feedback_service),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    await rate_limiter.check_rate_limit(
        request,
        limit=_FEEDBACK_LIMIT,
        window=_FEEDBACK_WINDOW,
        scope="feedback_submit",
    )
    _, user = session
    entry = FeedbackEntry(
        username=user["username"],
        name=payload.name or "",
        email=payload.email or "",
        category=payload.category,
        message=payload.message,
        created_at=datetime.utcnow(),
    )
    try:
        service.log_feedback(entry)
    except DuplicateFeedbackError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    notify_feedback_received(
        username=user["username"],
        entry_type="feedback",
        category_or_feature=entry.category,
        user_email=entry.email,
    )
    return {"ok": True}


@router.post("/bug", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour")
async def submit_bug(
    request: Request,
    payload: BugReportPayload,
    session=Depends(get_current_session),
    service: FeedbackService = Depends(get_feedback_service),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    await rate_limiter.check_rate_limit(
        request,
        limit=_FEEDBACK_LIMIT,
        window=_FEEDBACK_WINDOW,
        scope="bug_submit",
    )
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
    try:
        service.log_bug_report(entry)
    except DuplicateFeedbackError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    notify_feedback_received(
        username=user["username"],
        entry_type="bug",
        category_or_feature=entry.feature,
        user_email=entry.email,
    )
    return {"ok": True}
