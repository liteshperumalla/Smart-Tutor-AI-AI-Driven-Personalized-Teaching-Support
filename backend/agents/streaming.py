"""
Streaming Adapter for Agent Responses
Converts a completed agent response into a chunked SSE-compatible generator
with an __AGENT_META__ prefix line for the frontend to parse.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Generator, Optional


AGENT_META_PREFIX = "__AGENT_META__"
CHUNK_SIZE = 50  # characters per streamed chunk


def stream_agent_response(
    response_text: str,
    agent_name: str,
    route_reason: Optional[str] = None,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Generator[str, None, None]:
    """Yield a metadata line followed by response chunks.

    The first yielded value is the JSON metadata prefixed with
    ``__AGENT_META__`` so the frontend can detect and strip it before
    rendering the markdown body.
    """
    meta: Dict[str, Any] = {
        "agent": agent_name,
        "route_reason": route_reason or "",
    }
    if extra_meta:
        meta.update(extra_meta)

    yield f"{AGENT_META_PREFIX}{json.dumps(meta)}\n"

    # Stream the body in small chunks to give a typing effect
    for i in range(0, len(response_text), CHUNK_SIZE):
        yield response_text[i : i + CHUNK_SIZE]
