from typing import Dict, List, TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.api.dependencies import get_current_session, get_rate_limiter_dep
from backend.csrf_protection import csrf_protect
from backend import posthog_tracker
from backend.config import config
from backend.rate_limiter import limiter, PerUserRateLimiter
from backend.services import get_storage_backend

if TYPE_CHECKING:
    from backend.services.quiz_service import QuizService

router = APIRouter(prefix="/quiz", tags=["quiz"], dependencies=[Depends(csrf_protect)])


def get_quiz_service():
    from backend.services.quiz_service import get_quiz_service as _get_quiz_service

    return _get_quiz_service()

# Quiz-specific rate limits
_QUIZ_GEN_LIMIT = 5      # max quiz generations per user per window
_QUIZ_GEN_WINDOW = 3600  # 1 hour


class QuizGenerateRequest(BaseModel):
    folders: List[str] = Field(..., min_items=1)
    num_questions: int = Field(..., ge=1, le=10)
    course_id: str | None = Field(default=None, max_length=64)
    objective_ids: List[str] | None = Field(default=None, max_length=10)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


class QuizSubmissionRequest(BaseModel):
    quiz_id: str
    answers: Dict[str, str]


@router.get("/folders")
def list_folders(
    course_id: str | None = None,
    session=Depends(get_current_session),
    quiz_service: "QuizService" = Depends(get_quiz_service),
):
    _, user = session
    if not course_id:
        return {"folders": quiz_service.list_folders()}
    from backend.services.learning_service import get_learning_service
    prefixes = get_learning_service().course_prefixes(user["username"], user, course_id)
    folders = [
        folder for folder in quiz_service.list_folders()
        if any(folder["path"].replace("\\", "/").startswith(prefix) for prefix in prefixes)
    ]
    return {"folders": folders}


@router.post("/generate")
@limiter.limit("10/hour")
async def generate_quiz(
    request: Request,
    payload: QuizGenerateRequest,
    session=Depends(get_current_session),
    quiz_service: "QuizService" = Depends(get_quiz_service),
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
    await rate_limiter.check_cost_budget(request, config.BEDROCK_MODEL_ID)
    _, user = session
    from backend.services.learning_service import get_learning_service
    learning = get_learning_service()
    course_id = payload.course_id or "info-5731"
    prefixes = learning.course_prefixes(user["username"], user, course_id)
    normalized_folders = [folder.replace("\\", "/") for folder in payload.folders]
    if prefixes and any(not any(folder.startswith(prefix) for prefix in prefixes) for folder in normalized_folders):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Selected resources are outside the active course")
    objective_ids = learning.validate_objectives(user["username"], user, course_id, payload.objective_ids)
    # Custom practice still contributes item-level evidence; when the learner
    # did not choose an objective, distribute questions over the active course
    # objectives instead of falling back to aggregate-only scoring.
    if not objective_ids:
        objective_ids = [item["id"] for item in learning.objectives(user["username"], user, course_id)]
    try:
        quiz = quiz_service.generate_quiz(
            user_id=user["username"],
            selected_folders=payload.folders,
            num_questions=payload.num_questions,
            course_id=course_id,
            objective_ids=objective_ids,
            difficulty=payload.difficulty,
        )
        learning.register_quiz_items(course_id, str(quiz["quiz_id"]), list(quiz.get("questions", [])))
        posthog_tracker.capture(
            distinct_id=user["username"],
            event="quiz_started",
            properties={
                "num_questions": payload.num_questions,
                "folders": payload.folders,
                "course_id": course_id,
                "objective_ids": objective_ids,
                "difficulty": payload.difficulty,
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
    quiz_service: "QuizService" = Depends(get_quiz_service),
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
    metadata = result.metadata or {}
    if metadata.get("course_id"):
        from backend.services.learning_service import get_learning_service
        get_learning_service().record_assessment(
            user["username"], metadata["course_id"], metadata.get("responses", []), metadata.get("difficulty", "medium")
        )
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
    course_id: str | None = None,
    session=Depends(get_current_session),
):
    _, user = session
    if course_id:
        from backend.services.learning_service import get_learning_service
        get_learning_service().require_access(user["username"], user, course_id)
    storage = get_storage_backend()
    history = [result.to_dict() for result in storage.list_quiz_results(user["username"])]
    if course_id:
        history = [result for result in history if (result.get("metadata") or {}).get("course_id") == course_id]
    return {"results": history}
