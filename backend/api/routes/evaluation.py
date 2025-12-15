from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from backend.api.dependencies import get_current_session
from backend.services.evaluation_service import (
    EvaluationService,
    get_evaluation_service,
)

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


class EvaluationRunRequest(BaseModel):
    limit: Optional[int] = Field(default=None, ge=1, le=100)
    categories: Optional[List[str]] = Field(default=None, min_items=1)
    difficulties: Optional[List[str]] = Field(default=None, min_items=1)


@router.get("/cases")
def list_evaluation_cases(
    limit: Optional[int] = Query(default=None, ge=1, le=200),
    session=Depends(get_current_session),
    service: EvaluationService = Depends(get_evaluation_service),
):
    return {"cases": service.list_cases(limit)}


@router.post("/run")
def run_evaluations(
    payload: EvaluationRunRequest,
    session=Depends(get_current_session),
    service: EvaluationService = Depends(get_evaluation_service),
):
    return service.run_tests(
        limit=payload.limit,
        categories=payload.categories,
        difficulties=payload.difficulties,
    )


@router.get("/summary")
def evaluation_summary(
    session=Depends(get_current_session),
    service: EvaluationService = Depends(get_evaluation_service),
):
    return {"summary": service.metrics_log_summary()}


@router.post("/logs/clear", status_code=status.HTTP_200_OK)
def clear_evaluation_logs(
    session=Depends(get_current_session),
    service: EvaluationService = Depends(get_evaluation_service),
):
    service.clear_logs()
    return {"status": "cleared"}
