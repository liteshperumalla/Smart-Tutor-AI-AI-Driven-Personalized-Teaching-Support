"""Registered background jobs.

Keep each job safe to run twice: SQS delivers at least once, and a job
interrupted by a deploy runs again after its visibility timeout.
"""
from __future__ import annotations

from backend.jobs.queue import job
from backend.logger import get_logger

logger = get_logger(__name__)


@job("ping")
def ping(note: str = "") -> None:
    """End-to-end check for the queue and worker: ``python -m backend.jobs ping``."""
    logger.info(f"Jobs ping received{f': {note}' if note else ''}")
