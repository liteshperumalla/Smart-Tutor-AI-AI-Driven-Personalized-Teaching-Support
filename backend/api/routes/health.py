from fastapi import APIRouter
from typing import Dict, Any
import time

router = APIRouter(prefix="/health", tags=["health"])

_last_rag_check = 0
_cached_rag_status = {"status": "checking", "latency_ms": 0}


@router.get("", summary="Health check", description="Verify API status")
async def health_check():
    return {"status": "ok"}


@router.get(
    "/rag", summary="RAG Pipeline Health", description="Check RAG pipeline components"
)
async def rag_health_check() -> Dict[str, Any]:
    """
    Comprehensive RAG pipeline health check
    """
    global _last_rag_check, _cached_rag_status
    start_time = time.time()

    status = {"status": "healthy", "components": {}, "latency_ms": 0}

    try:
        from backend.config import config
        from backend.s3_vector_store import S3VectorStore
        from backend.bedrock_embeddings import BedrockEmbeddings

        status["components"]["config"] = {
            "use_s3_vectors": config.USE_S3_VECTORS,
            "documents_bucket": config.S3_DOCUMENTS_BUCKET,
            "embedding_model": config.BEDROCK_EMBEDDING_MODEL_ID,
            "llm_model": config.BEDROCK_MODEL_ID,
        }

        if config.USE_S3_VECTORS:
            try:
                vs = S3VectorStore()
                vs.load_index()
                vs_stats = vs.get_stats()
                status["components"]["vector_store"] = {
                    "status": "healthy",
                    "total_vectors": vs_stats["total_vectors"],
                    "bucket": vs_stats["bucket"],
                    "index_cached": vs_stats["index_cached"],
                }
            except Exception as e:
                status["components"]["vector_store"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                status["status"] = "degraded"

        try:
            emb = BedrockEmbeddings()
            emb_stats = emb.get_stats()
            status["components"]["embeddings"] = {
                "status": "healthy",
                "model": emb_stats["model"],
                "dimension": emb_stats["dimension"],
                "total_requests": emb_stats["total_requests"],
                "cache_size": len(emb._embedding_cache)
                if hasattr(emb, "_embedding_cache")
                else 0,
            }
        except Exception as e:
            status["components"]["embeddings"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            status["status"] = "degraded"

    except Exception as e:
        status["status"] = "unhealthy"
        status["error"] = str(e)

    status["latency_ms"] = round((time.time() - start_time) * 1000, 2)
    _cached_rag_status = status
    _last_rag_check = time.time()

    return status


@router.get(
    "/status",
    summary="Detailed system status",
    description="Full system status including RAG",
)
async def detailed_status() -> Dict[str, Any]:
    """
    Get detailed system status
    """
    import boto3
    from backend.config import config

    system_status = {
        "timestamp": time.time(),
        "version": "1.0.0",
        "environment": config.ENVIRONMENT,
        "components": {},
    }

    try:
        s3 = boto3.client("s3")
        buckets = [config.S3_DOCUMENTS_BUCKET, config.S3_UPLOADS_BUCKET]
        for bucket in buckets:
            try:
                response = s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
                system_status["components"][bucket] = {
                    "status": "accessible",
                    "object_count": response.get("KeyCount", 0),
                }
            except Exception as e:
                system_status["components"][bucket] = {
                    "status": "error",
                    "error": str(e),
                }
    except Exception as e:
        system_status["components"]["s3"] = {"status": "error", "error": str(e)}

    try:
        redis_status = "unknown"
        try:
            import redis

            r = redis.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                password=config.REDIS_PASSWORD if config.REDIS_PASSWORD else None,
                ssl=config.REDIS_SSL,
                socket_timeout=5,
            )
            r.ping()
            redis_status = "healthy"
        except Exception:
            redis_status = "unhealthy"

        system_status["components"]["redis"] = {"status": redis_status}
    except Exception as e:
        system_status["components"]["redis"] = {"status": "error", "error": str(e)}

    system_status["rag"] = _cached_rag_status

    return system_status
