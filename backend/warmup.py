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

    try:
        await asyncio.wait_for(_warm(), timeout=config.WARMUP_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.warning("Warmup timed out or failed: %s", exc)
