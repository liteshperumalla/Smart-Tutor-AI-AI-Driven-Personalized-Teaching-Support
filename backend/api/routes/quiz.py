from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import get_current_session
from backend.services.quiz_service import (
    QuizGenerationError,
    get_quiz_service,
    QuizService,
)

router = APIRouter(prefix="/quiz", tags=["quiz"])


class QuizGenerateRequest(BaseModel):
    folders: List[str] = Field(..., min_items=1)
    num_questions: int = Field(..., ge=1, le=10)


class QuizSubmissionRequest(BaseModel):
    quiz_id: str
    selected_folders: List[str]
    questions: List[Dict[str, object]]
    answers: Dict[str, str]


@router.get("/folders")
def list_folders(
    session=Depends(get_current_session),
    quiz_service: QuizService = Depends(get_quiz_service),
):
    return {"folders": quiz_service.list_folders()}


@router.post("/generate")
def generate_quiz(
    payload: QuizGenerateRequest,
    session=Depends(get_current_session),
    quiz_service: QuizService = Depends(get_quiz_service),
):
    _, user = session
    try:
        quiz = quiz_service.generate_quiz(
            user_id=user["username"],
            selected_folders=payload.folders,
            num_questions=payload.num_questions,
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
    result = quiz_service.save_result(
        user_id=user["username"],
        quiz_id=payload.quiz_id,
        selected_folders=payload.selected_folders,
        questions=payload.questions,
        answers=payload.answers,
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
