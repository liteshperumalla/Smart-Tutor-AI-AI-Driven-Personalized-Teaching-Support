"""
Cold-start warmup utilities.
"""

from __future__ import annotations

import asyncio
from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)


async def run_warmup() -> None:
    if not config.WARMUP_ENABLED:
        return

    logger.info("Warmup started")

    async def _warm():
        # Optionally load S3 index to reduce first-query latency.
        if config.WARMUP_LOAD_S3_INDEX:
            try:
                from backend.s3_retriever import S3Retriever
                retriever = S3Retriever()
                await asyncio.to_thread(retriever._ensure_index_loaded)
                logger.info("Warmup: S3 vector index loaded")
            except Exception as exc:
                logger.warning("Warmup: failed to load S3 index: %s", exc)

        # Optionally load cross-encoder reranker weights.
        if config.WARMUP_LOAD_RERANKER and config.RERANKING_ENABLED:
            try:
                from backend.s3_retriever import _get_cross_encoder
                await asyncio.to_thread(_get_cross_encoder)
                logger.info("Warmup: cross-encoder reranker loaded")
            except Exception as exc:
                logger.warning("Warmup: failed to load reranker: %s", exc)

        # Warm Redis cache with course metadata and frequent RAG queries
        try:
            if config.USE_REDIS_CACHE or config.REDIS_ENABLED:
                from backend.redis_cache import get_redis_cache
                import time

                cache = get_redis_cache()
                cache.set("warmup:status", {"ready": True, "timestamp": time.time()}, ttl=86400)
                cache.set("course_catalog:meta", {"status": "active", "version": "1.0"}, ttl=86400)

                # Seed RAG caching layer with frequent introductory Q&A
                try:
                    from backend.rag.caching_layer import get_caching_layer
                    caching_layer = get_caching_layer()
                    frequent_qa = [
                        (
                            "What is Smart AI Tutor?",
                            {"response": "Smart AI Tutor is an adaptive learning assistant designed to help students master complex subjects through personalized explanations, quizzes, and real-time guidance.", "confidence": 1.0},
                        ),
                        (
                            "Hello",
                            {"response": "Hello! I am your Smart AI Tutor. How can I help you learn today?", "confidence": 1.0},
                        ),
                        (
                            "How do I start a quiz?",
                            {"response": "You can start a quiz by navigating to the Quiz section from the sidebar and selecting your subject.", "confidence": 1.0},
                        ),
                    ]
                    for q, ans in frequent_qa:
                        caching_layer.put_query_result(q, ans, user_id=None)
                    logger.info("Warmup: Redis cache seeded with frequent queries and metadata")
                except Exception as rag_exc:
                    logger.warning("Warmup: failed to seed RAG cache: %s", rag_exc)
        except Exception as exc:
            logger.warning("Warmup: failed to warm Redis cache: %s", exc)

    try:
        await asyncio.wait_for(_warm(), timeout=config.WARMUP_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.warning("Warmup timed out or failed: %s", exc)
