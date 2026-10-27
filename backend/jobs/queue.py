"""Job registry and ``enqueue``.

A job is a plain function registered with ``@job("name")``. Its keyword
arguments must be JSON-serialisable, since they travel in the SQS message.

With ``config.JOBS_QUEUE_URL`` set, ``enqueue`` sends the job to SQS and the
worker container (``python -m backend.jobs worker``) runs it. Without it, or
if SQS can't be reached, the job runs in a daemon thread in this process,
which is how background work ran before the queue existed.

SQS delivers at least once, so a job may run more than once: jobs must be
safe to repeat.
"""
from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)

MESSAGE_VERSION = 1

JobFunc = Callable[..., Any]
_REGISTRY: dict[str, JobFunc] = {}


class UnknownJobError(KeyError):
    """No job is registered under this name."""


def job(name: str) -> Callable[[JobFunc], JobFunc]:
    """Register ``func`` as the job called ``name``."""

    def decorator(func: JobFunc) -> JobFunc:
        if name in _REGISTRY and _REGISTRY[name] is not func:
            raise ValueError(f"Job {name!r} is already registered")
        _REGISTRY[name] = func
        return func

    return decorator


def get_job(name: str) -> JobFunc:
    _load_tasks()
    try:
        return _REGISTRY[name]
    except KeyError:
        raise UnknownJobError(name) from None


def _load_tasks() -> None:
    # Importing the module runs its @job decorators.
    from backend.jobs import tasks  # noqa: F401


@lru_cache(maxsize=4)
def sqs_client(region: str):
    import boto3

    return boto3.client("sqs", region_name=region)


def build_message(name: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    return {
        "v": MESSAGE_VERSION,
        "id": str(uuid.uuid4()),
        "job": name,
        "args": kwargs,
        "enqueued_at": datetime.now(UTC).isoformat(),
    }


def enqueue(name: str, **kwargs: Any) -> str:
    """Run job ``name`` in the background and return the job id.

    Raises ``UnknownJobError`` for an unregistered name, and ``TypeError`` if
    the arguments can't be serialised, before anything is sent.
    """
    func = get_job(name)
    message = build_message(name, kwargs)
    body = json.dumps(message)

    if config.JOBS_QUEUE_URL:
        try:
            sqs_client(config.JOBS_REGION).send_message(QueueUrl=config.JOBS_QUEUE_URL, MessageBody=body)
            logger.info(f"Queued job {name} ({message['id']})")
            return message["id"]
        except Exception as exc:
            # Don't lose the work because the queue is unreachable.
            logger.warning(f"Could not queue job {name} ({message['id']}), running it in-process: {exc}")

    _run_in_thread(func, name, message["id"], kwargs)
    return message["id"]


def _run_in_thread(func: JobFunc, name: str, job_id: str, kwargs: dict[str, Any]) -> None:
    def target() -> None:
        try:
            func(**kwargs)
        except Exception as exc:
            logger.error(f"In-process job {name} ({job_id}) failed: {exc}", exc_info=True)

    threading.Thread(target=target, name=f"job:{name}", daemon=True).start()
