"""Record which LLM actually produced a response.

The Bedrock client falls back to other models when the requested one fails
(``us.`` prefix stripped, then the default model; OpenAI falls back to
Bedrock). Without this the chat would label a fallback answer with the model
the student picked. The chat route opens a tracker per request; the client
records each model that returned output, and the route reads the last one.

The tracker is a mutable dict held in a ContextVar: thread-pool workers and
streaming iterations run in copies of the request's context, and copies share
the same dict object, so a model recorded in a worker is visible to the route.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

_current: ContextVar[Optional[dict]] = ContextVar("model_usage", default=None)


def start_tracking() -> dict:
    usage: dict = {"model": None}
    _current.set(usage)
    return usage


def record_model_used(model_id: str) -> None:
    usage = _current.get()
    if usage is not None:
        usage["model"] = model_id


def activate(usage: dict) -> None:
    """Re-bind ``usage`` in the current context.

    Starlette pulls each chunk of a streaming response in a fresh copy of the
    context, so the route calls this before every pull to make sure the
    client's ``record_model_used`` lands in this request's tracker.
    """
    _current.set(usage)
