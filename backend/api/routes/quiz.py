from __future__ import annotations

from typing import Dict, List, TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.api.dependencies import get_current_session, get_rate_limiter_dep
from backend import posthog_tracker
from backend.config import config
from backend.rate_limiter import limiter, PerUserRateLimiter

if TYPE_CHECKING:
    from backend.services.quiz_service import QuizService

router = APIRouter(prefix="/quiz", tags=["quiz"])


def get_quiz_service():
    from backend.services.quiz_service import get_quiz_service as _get_quiz_service

    return _get_quiz_service()

# Quiz-specific rate limits
_QUIZ_GEN_LIMIT = 5      # max quiz generations per user per window
_QUIZ_GEN_WINDOW = 3600  # 1 hour


class QuizGenerateRequest(BaseModel):
    folders: List[str] = Field(..., min_items=1)
    num_questions: int = Field(..., ge=1, le=10)


class QuizSubmissionRequest(BaseModel):
    quiz_id: str
    answers: Dict[str, str]


@router.get("/folders")
def list_folders(
    session=Depends(get_current_session),
    quiz_service: QuizService = Depends(get_quiz_service),
):
    return {"folders": quiz_service.list_folders()}


@router.post("/generate")
@limiter.limit("10/hour")
async def generate_quiz(
    request: Request,
    payload: QuizGenerateRequest,
    session=Depends(get_current_session),
    quiz_service: QuizService = Depends(get_quiz_service),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    from backend.services.quiz_service import QuizGenerationError

    await rate_limiter.check_rate_limit(
        request,
        limit=_QUIZ_GEN_LIMIT,
        window=_QUIZ_GEN_WINDOW,
        scope="quiz_generate",
    )
    await rate_limiter.check_model_rate_limit(request, config.BEDROCK_MODEL_ID)
    _, user = session
    try:
        quiz = quiz_service.generate_quiz(
            user_id=user["username"],
            selected_folders=payload.folders,
            num_questions=payload.num_questions,
        )
        posthog_tracker.capture(
            distinct_id=user["username"],
            event="quiz_started",
            properties={
                "num_questions": payload.num_questions,
                "folders": payload.folders,
            },
        )
        return quiz
    except QuizGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.post("/submit")
def submit_quiz(
    payload: QuizSubmissionRequest,
    session=Depends(get_current_session),
    quiz_service: QuizService = Depends(get_quiz_service),
):
    token, user = session
    try:
        result = quiz_service.save_result(
            user_id=user["username"],
            quiz_id=payload.quiz_id,
            answers=payload.answers,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    posthog_tracker.capture(
        distinct_id=user["username"],
        event="quiz_completed",
        properties={
            "quiz_id": payload.quiz_id,
            "score": result.to_dict().get("score"),
        },
    )
    return {"result": result.to_dict()}


@router.get("/history")
def quiz_history(
    session=Depends(get_current_session),
    quiz_service: QuizService = Depends(get_quiz_service),
):
    _, user = session
    history = quiz_service.list_results(user["username"])
    return {"results": history}
