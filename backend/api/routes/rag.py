"""
FastAPI routes for enhanced RAG service.
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from backend.rag.service import RAGService, RAGVariant
# Consolidated auth: supports both HttpOnly cookie (web clients) and Bearer
# header (server-to-server). Also enforces disabled-user check.
from backend.api.dependencies import get_current_user, get_rate_limiter_dep
from backend.config import config
from backend.rate_limiter import limiter, PerUserRateLimiter


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rag", tags=["RAG"])


# Global RAG service instance (initialized in main.py)
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Dependency to get RAG service instance."""
    if _rag_service is None:
        raise HTTPException(status_code=500, detail="RAG service not initialized")
    return _rag_service


def set_rag_service(service: RAGService):
    """Set global RAG service instance."""
    global _rag_service
    _rag_service = service


# Request/Response Models

class RAGQueryRequest(BaseModel):
    """RAG query request."""
    query: str = Field(..., min_length=1, max_length=1000, description="User query")
    variant: Optional[RAGVariant] = Field(None, description="RAG variant for A/B testing")
    top_k: int = Field(5, ge=1, le=20, description="Number of results to return")
    max_retrieval: int = Field(20, ge=5, le=100, description="Maximum documents to retrieve")


class RAGQueryResponse(BaseModel):
    """RAG query response."""
    answer: str
    sources: List[Dict[str, Any]]
    retrieved_docs: int
    final_docs: int
    confidence: float
    intent: Optional[str] = None
    metrics: Dict[str, Any]


class DocumentIngestionRequest(BaseModel):
    """Document ingestion request."""
    content: str = Field(..., min_length=1, description="Document content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class DocumentIngestionResponse(BaseModel):
    """Document ingestion response."""
    success: bool
    chunks_created: int
    embeddings_generated: int
    embeddings_cached: int
    processing_time_ms: float
    error: Optional[str] = None


class RAGStatsResponse(BaseModel):
    """RAG service statistics."""
    variant: str
    features: Dict[str, bool]
    cache: Optional[Dict[str, Any]] = None


# Routes

@router.post("/query", response_model=RAGQueryResponse)
@limiter.limit("60/hour")
async def rag_query(
    request: Request,
    payload: RAGQueryRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """
    Process a RAG query with enhanced retrieval.

    Features:
    - Query enhancement (intent classification, entity extraction)
    - Hybrid search (BM25 + semantic)
    - Cross-encoder reranking with MMR diversity
    - HyDE for conceptual queries
    - Multi-tier caching
    - A/B testing support

    Example:
    ```json
    {
        "query": "What is machine learning?",
        "variant": "enhanced",
        "top_k": 5
    }
    ```
    """
    await rate_limiter.check_rate_limit(request, limit=30, window=3600, scope="rag_query")
    await rate_limiter.check_model_rate_limit(request, config.BEDROCK_MODEL_ID)
    try:
        user_id = current_user.get("sub")  # User ID from JWT

        result = await rag_service.query(
            query=payload.query,
            user_id=user_id,
            variant=payload.variant,
            top_k=payload.top_k,
            max_retrieval=payload.max_retrieval
        )

        logger.info(f"RAG query processed for user {user_id}: {payload.query[:50]}...")

        return RAGQueryResponse(**result)

    except Exception as e:
        logger.error(f"Error in RAG query endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"RAG query failed: {str(e)}")


@router.post("/ingest", response_model=DocumentIngestionResponse)
@limiter.limit("30/hour")
async def ingest_document(
    request: Request,
    payload: DocumentIngestionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """
    Ingest a document into the RAG system.

    The document will be:
    1. Chunked using semantic chunker (sentence-aware, structure-preserving)
    2. Embedded using AWS Bedrock Titan Embeddings
    3. Cached for efficiency
    4. Stored in vector database

    Example:
    ```json
    {
        "content": "Machine learning is a subset of AI...",
        "metadata": {
            "source": "ml_basics.pdf",
            "page": 1,
            "author": "John Doe"
        }
    }
    ```
    """
    await rate_limiter.check_rate_limit(request, limit=15, window=3600, scope="rag_ingest")
    try:
        # Add user info to metadata
        metadata = payload.metadata.copy()
        metadata["uploaded_by"] = current_user.get("email")
        metadata["user_id"] = current_user.get("sub")

        result = await rag_service.ingest_document(
            content=payload.content,
            metadata=metadata
        )

        logger.info(f"Document ingested by user {current_user.get('email')}: {metadata.get('source', 'unknown')}")

        return DocumentIngestionResponse(**result)

    except Exception as e:
        logger.error(f"Error in document ingestion endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {str(e)}")


@router.get("/stats", response_model=RAGStatsResponse)
async def get_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service)
):
    """
    Get RAG service statistics.

    Returns:
    - Current variant configuration
    - Enabled features (caching, query enhancement, HyDE, MMR)
    - Cache statistics (if caching enabled)

    Requires authentication.
    """
    try:
        stats = rag_service.get_stats()
        logger.info(f"RAG stats requested by user {current_user.get('email')}")
        return RAGStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Error in RAG stats endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/health")
async def health_check():
    """
    Health check endpoint for RAG service.

    Does not require authentication.
    """
    try:
        if _rag_service is None:
            return {
                "status": "unhealthy",
                "message": "RAG service not initialized"
            }

        return {
            "status": "healthy",
            "message": "RAG service is running",
            "variant": _rag_service.default_variant
        }

    except Exception as e:
        logger.error(f"Error in RAG health check: {str(e)}", exc_info=True)
        return {
            "status": "unhealthy",
            "message": str(e)
        }
