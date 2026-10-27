"""
Centralized Langfuse Tracing Setup (Langfuse v4 Architecture)

Provides idempotent initialization for both the OpenTelemetry-native
Langfuse v4 client, LlamaIndex callback handler, and safe observation helpers.

Supports:
  1. Langfuse v4 Observations-First Data Model: Correlating attributes
     (user_id, session_id, tags, metadata) propagate to all child observations
     via propagate_attributes().
  2. OpenTelemetry span management via start_as_current_observation() and @observe.
  3. Seamless backward compatibility for existing create_trace / traced_span calls.

Every public function is wrapped in try/except and returns None/no-op when
tracing is disabled or Langfuse is unavailable.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Dict, List, Optional

from backend.config import config
from backend.log_redaction import user_ref

logger = logging.getLogger(__name__)

# ── Module-level singletons ──────────────────────────────────────────
_langfuse_client = None
_langfuse_handler = None
_initialized = False
_init_error: Optional[str] = None


# ── Initialization / Shutdown ────────────────────────────────────────

def init_langfuse(force: bool = False) -> bool:
    """Idempotent Langfuse v4 initialization.

    Sets up:
      1. The Langfuse v4 client (OpenTelemetry-native observations model).
      2. The LlamaIndex callback handler (Settings.callback_manager),
         so all LlamaIndex operations (retrieve, synthesize) are auto-traced.

    Returns ``True`` if initialization succeeded, ``False`` otherwise.
    """
    global _langfuse_client, _langfuse_handler, _initialized, _init_error

    if _initialized and not force:
        return _langfuse_client is not None

    if not config.LANGFUSE_ENABLED:
        logger.info("Langfuse tracing is disabled (LANGFUSE_ENABLED=false)")
        return False

    public_key = getattr(config, "LANGFUSE_PUBLIC_KEY", "") or ""
    secret_key = getattr(config, "LANGFUSE_SECRET_KEY", "") or ""
    host = getattr(config, "LANGFUSE_HOST", "https://cloud.langfuse.com") or "https://cloud.langfuse.com"

    if isinstance(public_key, str):
        public_key = public_key.strip().strip("'\"")
    if isinstance(secret_key, str):
        secret_key = secret_key.strip().strip("'\"")
    if isinstance(host, str):
        host = host.strip().strip("'\"")

    if not public_key or not secret_key:
        _init_error = "API keys missing or empty in configuration"
        logger.warning(
            "Langfuse is enabled but keys are missing — tracing will be disabled"
        )
        return False

    # 1. Direct v4 client
    try:
        import os
        os.environ["LANGFUSE_INGESTION_VERSION"] = getattr(config, "LANGFUSE_INGESTION_VERSION", "4")
        if public_key:
            os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
        if secret_key:
            os.environ["LANGFUSE_SECRET_KEY"] = secret_key
        if host:
            os.environ["LANGFUSE_HOST"] = host
            os.environ["LANGFUSE_BASE_URL"] = host

        from langfuse import Langfuse

        try:
            client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                base_url=host,
            )
        except (TypeError, ValueError):
            client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )

        _langfuse_client = client
        _initialized = True
        _init_error = None
        logger.info("Langfuse v4 client initialized (host=%s, ingestion_version=4)", host)
    except Exception as exc:
        _init_error = f"{type(exc).__name__}: {exc}"
        logger.error("Failed to initialize Langfuse client: %s", exc)
        _langfuse_client = None
        _initialized = False

    # 2. LlamaIndex callback handler
    try:
        from llama_index.callbacks.langfuse import (
            langfuse_callback_handler as create_langfuse_handler,
        )
        from llama_index.core import Settings
        from llama_index.core.callbacks import CallbackManager

        handler = create_langfuse_handler(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
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
        logger.info("Langfuse v4 tracing ready (host=%s)", host)
    return ok


def shutdown_langfuse() -> None:
    """Flush any pending Langfuse events. Safe to call even if not initialized."""
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


def get_client():
    """Langfuse v4 standard alias for get_langfuse_client()."""
    return _langfuse_client


def get_langfuse_handler():
    """Return the LlamaIndex callback handler singleton (or None)."""
    return _langfuse_handler


# ── Langfuse v4 Observations-First Context Helpers ───────────────────

@contextmanager
def propagate_attributes(
    *,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
):
    """Langfuse v4 context manager to propagate observation attributes downward.

    In v4, attributes set here automatically cascade to all child observations
    and spans created within this scope.
    """
    if _langfuse_client is None:
        yield None
        return

    # In SDK 4.x propagate_attributes is a module-level function, not a
    # client method; the old hasattr(client, ...) check made this a no-op.
    try:
        from langfuse import propagate_attributes as _propagate

        cm = _propagate(
            # Langfuse traces/sessions show user_id; send a pseudonym only.
            user_id=user_ref(user_id) if user_id else None,
            session_id=session_id,
            metadata=metadata,
            tags=tags,
        )
    except Exception as exc:
        logger.debug("propagate_attributes failed: %s", exc)
        yield None
        return
    with cm as ctx:
        yield ctx


# ── Request-scoped trace attributes ──────────────────────────────────
#
# LLM generations are opened deep inside the Bedrock client, far from the
# route that knows who is asking. The authenticated request records its
# user / chat session / feature here (get_current_session), and
# request_trace_scope() applies them when a generation is created, so
# Langfuse can group traces by user and session and split them by feature.

_request_trace_attributes: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "langfuse_request_trace_attributes", default=None
)


def set_request_trace_attributes(
    *,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    feature: Optional[str] = None,
) -> None:
    attrs: Dict[str, Any] = {}
    if user_id:
        attrs["user_id"] = user_ref(user_id)
    if session_id:
        attrs["session_id"] = str(session_id)[:200]
    if feature:
        attrs["tags"] = [feature]
        attrs["trace_name"] = feature
    _request_trace_attributes.set(attrs or None)


@contextmanager
def request_trace_scope():
    """Apply the current request's trace attributes to spans opened inside."""
    attrs = _request_trace_attributes.get()
    if not attrs or _langfuse_client is None:
        yield
        return
    try:
        from langfuse import propagate_attributes as _propagate

        cm = _propagate(**attrs)
    except Exception as exc:
        logger.debug("request_trace_scope failed: %s", exc)
        yield
        return
    with cm:
        yield


def observe(*args, **kwargs) -> Callable:
    """Langfuse v4 @observe decorator re-export with safe no-op fallback."""
    try:
        from langfuse.decorators import observe as _observe
        return _observe(*args, **kwargs)
    except Exception:
        def _decorator(func):
            return func
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return _decorator


@contextmanager
def start_as_current_observation(name: str, as_type: str = "span", **kwargs):
    """Langfuse v4 OpenTelemetry observation context manager with fallback."""
    if _langfuse_client is not None and hasattr(_langfuse_client, "start_as_current_observation"):
        try:
            with _langfuse_client.start_as_current_observation(name=name, as_type=as_type, **kwargs) as obs:
                yield obs
            return
        except Exception as exc:
            logger.debug("start_as_current_observation failed: %s", exc)
    yield None


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
    """Open the root observation of a new trace.  Returns ``None`` if tracing is disabled.

    SDK 4.x has no ``client.trace()`` (the old call raised and was swallowed,
    so these traces never reached Langfuse). The root is an "agent"
    observation; user (pseudonym), session, tags and trace name are attached
    through ``langfuse.propagate_attributes`` and re-applied to child spans.
    The root must be closed with ``update_trace`` (which ends it) or it is
    never exported.
    """
    if _langfuse_client is None:
        return None
    attrs: Dict[str, Any] = {"trace_name": name}
    if user_id:
        attrs["user_id"] = user_ref(user_id)
    if session_id:
        attrs["session_id"] = str(session_id)[:200]
    if tags:
        attrs["tags"] = list(tags)
    try:
        from langfuse import propagate_attributes as _propagate

        with _propagate(**attrs):
            root = _langfuse_client.start_observation(
                name=name, as_type="agent", input=input, metadata=metadata
            )
        _TRACE_ATTRS[id(root)] = attrs
        return root
    except Exception as exc:
        logger.debug("create_trace failed: %s", exc)
        return None


# Trace attributes of open roots, re-applied when their children are created.
_TRACE_ATTRS: Dict[int, Dict[str, Any]] = {}


def update_trace(trace, *, output=None, metadata=None, level=None, end: bool = True) -> None:
    """Record the trace's output/metadata on its root and (by default) end it."""
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
        if kwargs:
            trace.update(**kwargs)
        if end:
            _TRACE_ATTRS.pop(id(trace), None)
            trace.end()
    except Exception as exc:
        logger.debug("update_trace failed: %s", exc)


# ── Span helpers ─────────────────────────────────────────────────────

def create_span(trace, name: str, *, input: Optional[Any] = None):
    """Create a child span on *trace*.  Returns ``None`` if tracing is disabled."""
    if trace is None:
        return None
    try:
        attrs = _TRACE_ATTRS.get(id(trace))
        if attrs:
            from langfuse import propagate_attributes as _propagate

            with _propagate(**attrs):
                return trace.start_observation(name=name, as_type="span", input=input)
        return trace.start_observation(name=name, as_type="span", input=input)
    except Exception as exc:
        logger.debug("create_span failed: %s", exc)
        return None


def end_span(span, *, output: Optional[Any] = None) -> None:
    """End (close) a span with optional output."""
    if span is None:
        return
    try:
        if output is not None:
            span.update(output=output)
        span.end()
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


# ── Langfuse v4 Observation Scoring & OTLP Helpers ───────────────────

def score_observation(
    observation_id: str,
    name: str,
    value: float,
    *,
    comment: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> bool:
    """Langfuse v4: Attach score directly to an observation or span.

    Replaces legacy trace-level scoring joins with observation-level scores
    targeting the unified ClickHouse wide table (/api/public/v3/scores).
    """
    if _langfuse_client is None:
        return False
    try:
        kwargs: Dict[str, Any] = {
            "name": name,
            "value": value,
        }
        if observation_id:
            kwargs["observation_id"] = observation_id
        if trace_id:
            kwargs["trace_id"] = trace_id
        if comment:
            kwargs["comment"] = comment

        # SDK 4.x: create_score (client.score no longer exists).
        _langfuse_client.create_score(**kwargs)
        return True
    except Exception as exc:
        logger.debug("score_observation failed: %s", exc)
        return False


def score_session_feedback(session_id: str, vote: str, *, comment: Optional[str] = None) -> bool:
    """Record a user's thumbs up/down on a chat session as a Langfuse score.

    Scored per session (the conversation the user rated), as ``user_feedback``
    = 1 for thumbs_up and 0 for thumbs_down, so Langfuse can chart
    satisfaction next to cost and latency.
    """
    if _langfuse_client is None or not session_id or vote not in ("thumbs_up", "thumbs_down"):
        return False
    try:
        _langfuse_client.create_score(
            name="user_feedback",
            value=1.0 if vote == "thumbs_up" else 0.0,
            session_id=str(session_id)[:200],
            data_type="NUMERIC",
            comment=comment,
        )
        return True
    except Exception as exc:
        logger.debug("score_session_feedback failed: %s", exc)
        return False


def get_otel_ingestion_headers() -> Dict[str, str]:
    """Return Langfuse v4 OpenTelemetry ingestion headers with v4 schema flag."""
    import base64
    creds = f"{config.LANGFUSE_PUBLIC_KEY}:{config.LANGFUSE_SECRET_KEY}".encode()
    return {
        "Authorization": f"Basic {base64.b64encode(creds).decode()}",
        "x-langfuse-ingestion-version": "4",
        "Content-Type": "application/json",
    }


# ── Health check ─────────────────────────────────────────────────────

def get_langfuse_health() -> Dict[str, Any]:
    """Return a status dict suitable for admin/health endpoints."""
    global _init_error
    if not config.LANGFUSE_ENABLED:
        return {"status": "disabled", "message": "LANGFUSE_ENABLED=false"}

    public_key = getattr(config, "LANGFUSE_PUBLIC_KEY", "") or ""
    secret_key = getattr(config, "LANGFUSE_SECRET_KEY", "") or ""
    if isinstance(public_key, str):
        public_key = public_key.strip().strip("'\"")
    if isinstance(secret_key, str):
        secret_key = secret_key.strip().strip("'\"")

    if not public_key or not secret_key:
        return {"status": "misconfigured", "message": "API keys missing"}

    if _langfuse_client is None:
        init_langfuse(force=True)

    if _langfuse_client is None:
        return {
            "status": "unhealthy",
            "message": f"Client not initialized: {_init_error or 'Unknown initialization error'}",
            "version": "v4",
            "host": getattr(config, "LANGFUSE_HOST", "https://cloud.langfuse.com"),
        }

    # Attempt a lightweight auth check (non-blocking for overall health)
    auth_ok = True
    auth_msg = None
    try:
        if hasattr(_langfuse_client, "auth_check"):
            auth_ok = bool(_langfuse_client.auth_check())
    except Exception as exc:
        auth_ok = False
        auth_msg = str(exc)
        logger.debug("Langfuse auth_check failed: %s", exc)

    result = {
        "status": "healthy",
        "version": "v4",
        "host": config.LANGFUSE_HOST,
        "observations_first": True,
        "ingestion_version": "4",
        "data_model": "clickhouse_wide_table",
        "callback_handler": _langfuse_handler is not None,
        "authenticated": auth_ok,
    }
    if auth_msg:
        result["auth_message"] = auth_msg
    return result

