"""Learner dashboard, recommendations, and confidence signals."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.dependencies import get_current_session
from backend.csrf_protection import csrf_protect

router = APIRouter(prefix="/learning", tags=["learning"], dependencies=[Depends(csrf_protect)])


def get_learning_service():
    from backend.services.learning_service import get_learning_service as factory
    return factory()


class ConfidenceRequest(BaseModel):
    course_id: str = Field(min_length=1, max_length=64)
    objective_id: str = Field(min_length=1, max_length=128)
    confidence: int = Field(ge=1, le=5)


@router.get("/dashboard")
def dashboard(course_id: str | None = None, session=Depends(get_current_session), service=Depends(get_learning_service)):
    _, user = session
    return service.dashboard(user["username"], user, course_id)


@router.get("/recommendation")
def recommendation(course_id: str, session=Depends(get_current_session), service=Depends(get_learning_service)):
    _, user = session
    return service.recommendation(user["username"], user, course_id)


@router.post("/confidence")
def set_confidence(payload: ConfidenceRequest, session=Depends(get_current_session), service=Depends(get_learning_service)):
    _, user = session
    return {"confidence": service.set_confidence(user["username"], user, payload.course_id, payload.objective_id, payload.confidence)}
