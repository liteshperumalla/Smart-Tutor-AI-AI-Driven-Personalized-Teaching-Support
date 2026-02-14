"""
Centralized Langfuse Tracing Setup

Provides idempotent initialization for both the LlamaIndex callback handler
and the direct Langfuse client, plus safe helpers for trace/span lifecycle.

Every public function is wrapped in try/except and returns None/no-op when
tracing is disabled or Langfuse is unavailable, following the _safe_write()
pattern from the agent system.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from backend.config import config

logger = logging.getLogger(__name__)

# ── Module-level singletons ──────────────────────────────────────────
_langfuse_client = None
_langfuse_handler = None
_initialized = False


# ── Initialization / Shutdown ────────────────────────────────────────

def init_langfuse() -> bool:
    """Idempotent Langfuse initialization.

    Sets up:
      1. The direct ``Langfuse`` client (for manual traces/spans).
      2. The LlamaIndex callback handler (``Settings.callback_manager``),
         so all LlamaIndex operations (retrieve, synthesize) are auto-traced.

    Returns ``True`` if initialization succeeded, ``False`` otherwise.
    """
    global _langfuse_client, _langfuse_handler, _initialized

    if _initialized:
        return _langfuse_client is not None

    _initialized = True  # Mark as attempted even if it fails

    if not config.LANGFUSE_ENABLED:
        logger.info("Langfuse tracing is disabled (LANGFUSE_ENABLED=false)")
        return False

    if not config.LANGFUSE_PUBLIC_KEY or not config.LANGFUSE_SECRET_KEY:
        logger.warning(
            "Langfuse is enabled but keys are missing — tracing will be disabled"
        )
        return False

    # 1. Direct client
    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=config.LANGFUSE_PUBLIC_KEY,
            secret_key=config.LANGFUSE_SECRET_KEY,
            host=config.LANGFUSE_HOST,
        )
        logger.info("Langfuse client initialized")
    except Exception as exc:
        logger.error("Failed to initialize Langfuse client: %s", exc)
        _langfuse_client = None

    # 2. LlamaIndex callback handler
    try:
        from llama_index.callbacks.langfuse import (
            langfuse_callback_handler as create_langfuse_handler,
        )
        from llama_index.core import Settings
        from llama_index.core.callbacks import CallbackManager

        handler = create_langfuse_handler(
            public_key=config.LANGFUSE_PUBLIC_KEY,
            secret_key=config.LANGFUSE_SECRET_KEY,
            host=config.LANGFUSE_HOST,
        )
        Settings.callback_manager = CallbackManager([handler])
        _langfuse_handler = handler
        logger.info("LlamaIndex Langfuse callback handler wired into Settings")
    except ImportError:
        logger.warning(
            "llama-index-callbacks-langfuse not installed — "
            "automatic LlamaIndex tracing unavailable"
        )
    except Exception as exc:
        logger.error("Failed to initialize LlamaIndex Langfuse handler: %s", exc)

    ok = _langfuse_client is not None
    if ok:
        logger.info("Langfuse tracing ready (host=%s)", config.LANGFUSE_HOST)
    return ok


def shutdown_langfuse() -> None:
    """Flush any pending Langfuse events.  Safe to call even if not initialized."""
    global _langfuse_client
    if _langfuse_client is None:
        return
    try:
        _langfuse_client.flush()
        logger.info("Langfuse events flushed")
    except Exception as exc:
        logger.error("Error flushing Langfuse: %s", exc)


# ── Singleton accessors ──────────────────────────────────────────────

def get_langfuse_client():
    """Return the Langfuse client singleton (or None if disabled)."""
    return _langfuse_client


def get_langfuse_handler():
    """Return the LlamaIndex callback handler singleton (or None)."""
    return _langfuse_handler


# ── Trace helpers ────────────────────────────────────────────────────

def create_trace(
    name: str,
    *,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    input: Optional[Any] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Create a root Langfuse trace.  Returns ``None`` if tracing is disabled."""
    if _langfuse_client is None:
        return None
    try:
        kwargs: Dict[str, Any] = {"name": name}
        if user_id:
            kwargs["user_id"] = user_id
        if session_id:
            kwargs["session_id"] = session_id
        if input is not None:
            kwargs["input"] = input
        if tags:
            kwargs["tags"] = tags
        if metadata:
            kwargs["metadata"] = metadata
        return _langfuse_client.trace(**kwargs)
    except Exception as exc:
        logger.debug("create_trace failed: %s", exc)
        return None


def update_trace(trace, *, output=None, metadata=None, level=None) -> None:
    """Safely update a trace with output/metadata."""
    if trace is None:
        return
    try:
        kwargs: Dict[str, Any] = {}
        if output is not None:
            kwargs["output"] = output
        if metadata is not None:
            kwargs["metadata"] = metadata
        if level is not None:
            kwargs["level"] = level
        trace.update(**kwargs)
    except Exception as exc:
        logger.debug("update_trace failed: %s", exc)


# ── Span helpers ─────────────────────────────────────────────────────

def create_span(trace, name: str, *, input: Optional[Any] = None):
    """Create a child span on *trace*.  Returns ``None`` if tracing is disabled."""
    if trace is None:
        return None
    try:
        kwargs: Dict[str, Any] = {"name": name}
        if input is not None:
            kwargs["input"] = input
        return trace.span(**kwargs)
    except Exception as exc:
        logger.debug("create_span failed: %s", exc)
        return None


def end_span(span, *, output: Optional[Any] = None) -> None:
    """End (close) a span with optional output."""
    if span is None:
        return
    try:
        kwargs: Dict[str, Any] = {}
        if output is not None:
            kwargs["output"] = output
        span.end(**kwargs)
    except Exception as exc:
        logger.debug("end_span failed: %s", exc)


@contextmanager
def traced_span(trace, name: str, *, input: Optional[Any] = None):
    """Context manager that auto-times and auto-ends a span.

    Usage::

        with traced_span(main_trace, "rag-retrieval", input={"query": q}) as span:
            nodes = retriever.retrieve(q)
            # ... span is auto-ended on exit with duration_ms in output
    """
    span = create_span(trace, name, input=input)
    t0 = time.time()
    try:
        yield span
    finally:
        elapsed_ms = int((time.time() - t0) * 1000)
        end_span(span, output={"duration_ms": elapsed_ms})


# ── Health check ─────────────────────────────────────────────────────

def get_langfuse_health() -> Dict[str, Any]:
    """Return a status dict suitable for admin/health endpoints."""
    if not config.LANGFUSE_ENABLED:
        return {"status": "disabled", "message": "LANGFUSE_ENABLED=false"}

    if not config.LANGFUSE_PUBLIC_KEY or not config.LANGFUSE_SECRET_KEY:
        return {"status": "misconfigured", "message": "API keys missing"}

    if _langfuse_client is None:
        return {"status": "unhealthy", "message": "Client not initialized"}

    # Attempt a lightweight auth check
    try:
        _langfuse_client.auth_check()
        return {
            "status": "healthy",
            "host": config.LANGFUSE_HOST,
            "callback_handler": _langfuse_handler is not None,
        }
    except Exception as exc:
        return {"status": "unhealthy", "message": str(exc)}
