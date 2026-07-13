from __future__ import annotations

import logging
from typing import List, Optional, TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from backend.api.dependencies import get_current_session, get_rate_limiter_dep
from backend.config import config
from backend.rate_limiter import limiter, PerUserRateLimiter
from backend.validators import FileValidator
from backend.exceptions import InvalidFileError

if TYPE_CHECKING:
    from backend.services.research_service import ResearchService

router = APIRouter(prefix="/research", tags=["research"])


def get_research_service():
    from backend.services.research_service import get_research_service as _get_research_service

    return _get_research_service()


def get_knowledge_base_stats():
    from backend.services.status_service import (
        get_knowledge_base_stats as _get_knowledge_base_stats,
    )

    return _get_knowledge_base_stats()


# ==================== REQUEST MODELS ====================


class ResearchQueryRequest(BaseModel):
    query: str = Field(..., min_length=3)
    folders: Optional[List[str]] = None
    uploaded_only: Optional[bool] = False


class ResearchURLRequest(BaseModel):
    url: str


class ResearchYouTubeRequest(BaseModel):
    url: str


class WebSearchRequest(BaseModel):
    query: str = Field(..., min_length=3)
    max_results: int = Field(default=5, ge=1, le=20)


class AcademicSearchRequest(BaseModel):
    query: str = Field(..., min_length=3)
    sources: Optional[List[str]] = Field(default=["arxiv", "pubmed", "scholar"])
    max_results: int = Field(default=10, ge=1, le=50)


class CompareSourcesRequest(BaseModel):
    topic: str = Field(..., min_length=3)
    document_ids: Optional[List[str]] = None
    uploaded_only: bool = True


class CitationExtractionRequest(BaseModel):
    document_id: Optional[str] = None
    format_style: str = Field(default="apa", pattern="^(apa|mla|chicago|ieee)$")


class SummaryRequest(BaseModel):
    document_id: Optional[str] = None
    mode: str = Field(
        default="executive", pattern="^(executive|detailed|bullets|custom)$"
    )
    max_length: Optional[int] = Field(default=None, ge=50, le=2000)


class QuestionGenerationRequest(BaseModel):
    document_id: Optional[str] = None
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    question_types: Optional[List[str]] = Field(default=["mcq", "short_answer"])
    count: int = Field(default=5, ge=1, le=20)


class FactCheckRequest(BaseModel):
    claim: str = Field(..., min_length=10)
    uploaded_only: bool = True
    include_web: bool = False


# ==================== EXISTING ENDPOINTS ====================


@router.get("/folders")
def research_folders(
    session=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
):
    try:
        return {"folders": service.list_folders()}
    except RuntimeError as e:
        if "Knowledge base is not initialized" in str(e):
            return {"folders": []}
        raise


@router.get("/documents")
def research_documents(
    session=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
):
    try:
        return {"documents": service.list_documents()}
    except RuntimeError as e:
        if "Knowledge base is not initialized" in str(e):
            return {"documents": []}
        raise


@router.get("/uploads")
def research_uploads(
    session_data=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
):
    _, user = session_data
    try:
        return {"uploads": service.list_uploads(user["username"])}
    except RuntimeError as e:
        if "Knowledge base is not initialized" in str(e):
            return {"uploads": []}
        raise


@router.get("/stats")
def knowledge_base_stats(session=Depends(get_current_session)):
    """Expose persisted index metadata to the UI."""
    return {"stats": get_knowledge_base_stats()}


@router.post("/query")
@limiter.limit("60/hour")
async def run_research_query(
    request: Request,
    payload: ResearchQueryRequest,
    session=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    await rate_limiter.check_rate_limit(request, limit=30, window=3600, scope="research_query")
    await rate_limiter.check_model_rate_limit(request, config.BEDROCK_MODEL_ID)
    await rate_limiter.check_cost_budget(request, config.BEDROCK_MODEL_ID)
    if not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query cannot be empty",
        )
    result = service.query(
        payload.query,
        folders=payload.folders,
        uploaded_only=payload.uploaded_only,
    )
    return result


@router.post("/upload/file")
async def upload_research_file(
    session=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
    file: UploadFile = File(...),
):
    content = await file.read()
    try:
        sanitized_name = FileValidator.validate_file(
            file.filename or "uploaded-file", len(content)
        )
        preview = service.preview_file(content, sanitized_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except InvalidFileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"preview": preview}


@router.post("/upload/url")
def upload_research_url(
    payload: ResearchURLRequest,
    session=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
):
    try:
        preview = service.preview_url(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"preview": preview}


@router.post("/upload/youtube")
def upload_research_youtube(
    payload: ResearchYouTubeRequest,
    session=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
):
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"YouTube upload request for URL: {payload.url}")
    try:
        preview = service.preview_youtube(payload.url)
        logger.info(f"YouTube transcript extracted successfully")
        return {"preview": preview}
    except ValueError as exc:
        logger.error(f"YouTube upload ValueError: {exc}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(f"YouTube upload unexpected error: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch transcript: {str(exc)}",
        )


@router.delete("/uploads/clear")
def clear_research_uploads(
    session_data=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
):
    """Clear all uploaded documents from knowledge_uploads folder and index."""
    _, user = session_data
    try:
        result = service.clear_uploads(user["username"])
        return {"success": True, "deleted_count": result.get("deleted_count", 0)}
    except Exception as e:
        logger.warning(f"Failed to clear uploads: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to clear uploads"
        )


@router.post("/uploads/clear")
def clear_research_uploads_post(
    session_data=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
):
    """Clear all uploaded documents (POST version for sendBeacon API)."""
    _, user = session_data
    try:
        result = service.clear_uploads(user["username"])
        return {"success": True, "deleted_count": result.get("deleted_count", 0)}
    except Exception as e:
        logger.warning(f"Failed to clear uploads: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to clear uploads"
        )


# ==================== RESEARCH CAPABILITIES ENDPOINTS ====================


@router.post("/search/web")
@limiter.limit("40/hour")
async def search_web(
    request: Request,
    payload: WebSearchRequest,
    session=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """Search the web for supplementary information."""
    await rate_limiter.check_rate_limit(request, limit=20, window=3600, scope="research_search_web")
    try:
        result = service.search_web(payload.query, payload.max_results)
        return result
    except Exception as exc:
        logger.warning(f"Research error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred"
        )


@router.post("/search/academic")
@limiter.limit("40/hour")
async def search_academic(
    request: Request,
    payload: AcademicSearchRequest,
    session=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """Search academic databases (arXiv, PubMed, Google Scholar) for papers."""
    await rate_limiter.check_rate_limit(request, limit=20, window=3600, scope="research_search_academic")
    try:
        result = service.search_academic_papers(
            payload.query, payload.sources, payload.max_results
        )
        return result
    except Exception as exc:
        logger.warning(f"Research error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred"
        )


@router.post("/compare")
@limiter.limit("30/hour")
async def compare_sources(
    request: Request,
    payload: CompareSourcesRequest,
    session=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """Compare information across multiple documents on a topic."""
    await rate_limiter.check_rate_limit(request, limit=15, window=3600, scope="research_compare")
    await rate_limiter.check_model_rate_limit(request, config.BEDROCK_MODEL_ID)
    await rate_limiter.check_cost_budget(request, config.BEDROCK_MODEL_ID)
    try:
        result = service.compare_sources(
            payload.topic, payload.document_ids, payload.uploaded_only
        )
        return result
    except Exception as exc:
        logger.warning(f"Research error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred"
        )


@router.post("/citations")
@limiter.limit("40/hour")
async def extract_citations(
    request: Request,
    payload: CitationExtractionRequest,
    session=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """Extract and format citations from uploaded documents."""
    await rate_limiter.check_rate_limit(request, limit=20, window=3600, scope="research_citations")
    await rate_limiter.check_model_rate_limit(request, config.BEDROCK_MODEL_ID)
    await rate_limiter.check_cost_budget(request, config.BEDROCK_MODEL_ID)
    try:
        result = service.extract_citations(payload.document_id, payload.format_style)
        return result
    except Exception as exc:
        logger.warning(f"Research error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred"
        )


@router.post("/summary")
@limiter.limit("30/hour")
async def generate_summary(
    request: Request,
    payload: SummaryRequest,
    session=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """Generate document summary in specified mode (executive, detailed, bullets)."""
    await rate_limiter.check_rate_limit(request, limit=15, window=3600, scope="research_summary")
    await rate_limiter.check_model_rate_limit(request, config.BEDROCK_MODEL_ID)
    await rate_limiter.check_cost_budget(request, config.BEDROCK_MODEL_ID)
    try:
        result = service.generate_summary(
            payload.document_id, payload.mode, payload.max_length
        )
        return result
    except Exception as exc:
        logger.warning(f"Research error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred"
        )


@router.post("/questions")
@limiter.limit("30/hour")
async def generate_questions(
    request: Request,
    payload: QuestionGenerationRequest,
    session=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """Generate study questions from uploaded documents."""
    await rate_limiter.check_rate_limit(request, limit=15, window=3600, scope="research_questions")
    await rate_limiter.check_model_rate_limit(request, config.BEDROCK_MODEL_ID)
    await rate_limiter.check_cost_budget(request, config.BEDROCK_MODEL_ID)
    try:
        result = service.generate_questions(
            payload.document_id,
            payload.difficulty,
            payload.question_types,
            payload.count,
        )
        return result
    except Exception as exc:
        logger.warning(f"Research error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred"
        )


@router.post("/fact-check")
@limiter.limit("30/hour")
async def fact_check(
    request: Request,
    payload: FactCheckRequest,
    session=Depends(get_current_session),
    service: ResearchService = Depends(get_research_service),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """Cross-reference claims across sources and provide a verdict."""
    await rate_limiter.check_rate_limit(request, limit=15, window=3600, scope="research_fact_check")
    await rate_limiter.check_model_rate_limit(request, config.BEDROCK_MODEL_ID)
    await rate_limiter.check_cost_budget(request, config.BEDROCK_MODEL_ID)
    try:
        result = service.fact_check(
            payload.claim, payload.uploaded_only, payload.include_web
        )
        return result
    except Exception as exc:
        logger.warning(f"Research error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred"
        )
