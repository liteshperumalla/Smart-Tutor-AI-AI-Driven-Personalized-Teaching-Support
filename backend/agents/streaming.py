"""
Streaming Adapter for Agent Responses

Two flavours:

* :func:`stream_agent_response` wraps an already-completed string and emits
  fixed-size chunks for a "typing" effect. Used by agents that don't make an
  LLM call (e.g. ``feedback_agent``).

* :func:`stream_agent_tokens` wraps a live token generator coming from
  ``BedrockLLM.stream_complete`` (via
  :func:`backend.agents.llm_utils.stream_complete_with_model_fallback`).
  This is what cuts TTFT — the first delta reaches the client as soon as
  Bedrock emits it, instead of waiting for the full response.

Both prepend an ``__AGENT_META__`` JSON line so the frontend can split
metadata from the markdown body.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Generator, Iterable, Optional


AGENT_META_PREFIX = "__AGENT_META__"
CHUNK_SIZE = 50  # characters per streamed chunk (string-mode only)


def _format_meta(
    agent_name: str,
    route_reason: Optional[str],
    extra_meta: Optional[Dict[str, Any]],
) -> str:
    meta: Dict[str, Any] = {
        "agent": agent_name,
        "route_reason": route_reason or "",
    }
    if extra_meta:
        meta.update(extra_meta)
    return f"{AGENT_META_PREFIX}{json.dumps(meta)}\n"


def stream_agent_response(
    response_text: str,
    agent_name: str,
    route_reason: Optional[str] = None,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Generator[str, None, None]:
    """Yield a metadata line followed by fixed-size chunks of ``response_text``."""
    yield _format_meta(agent_name, route_reason, extra_meta)
    for i in range(0, len(response_text), CHUNK_SIZE):
        yield response_text[i : i + CHUNK_SIZE]


def stream_agent_tokens(
    token_iter: Iterable[str],
    agent_name: str,
    route_reason: Optional[str] = None,
    extra_meta: Optional[Dict[str, Any]] = None,
    on_complete: Optional[Callable[[str], None]] = None,
    on_error: Optional[Callable[[Exception], str]] = None,
) -> Generator[str, None, None]:
    """Yield a metadata line, then live tokens straight from the LLM.

    Parameters
    ----------
    token_iter:
        Iterator yielding incremental token strings. Typically a
        ``stream_complete_with_model_fallback`` generator.
    on_complete:
        Optional callback invoked with the *concatenated* response after the
        stream finishes (even on early generator close, via ``finally``).
        Use this for post-stream side effects like Neo4j logging.
    on_error:
        Optional callback that converts an exception raised inside the
        token iterator into a user-facing fallback string. If provided, the
        fallback string is yielded and the exception is suppressed.
    """
    yield _format_meta(agent_name, route_reason, extra_meta)

    collected: list[str] = []
    try:
        for tok in token_iter:
            if not tok:
                continue
            collected.append(tok)
            yield tok
    except Exception as exc:
        if on_error is not None:
            fallback = on_error(exc)
            if fallback:
                collected.append(fallback)
                yield fallback
        else:
            raise
    finally:
        if on_complete is not None:
            try:
                on_complete("".join(collected))
            except Exception:
                # Never let post-stream hooks bubble up — they're best-effort.
                pass
