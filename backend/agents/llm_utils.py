from __future__ import annotations

import logging
from typing import Generator, Optional

from backend.config import config


def extract_completion_text(llm_response: object) -> str:
    text = getattr(llm_response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    return str(llm_response).strip()


def _extract_delta(resp: object, previous_text: str = "") -> str:
    """Pull the incremental delta from a llama-index style CompletionResponse.

    ``BedrockLLM.stream_complete`` yields objects whose ``.delta`` is the new
    chunk. Some providers omit ``.delta`` and only update ``.text`` cumulatively.
    In the cumulative-text shape, returning the full ``.text`` every iteration
    would emit the whole response repeatedly; slice off the previously-seen
    prefix so callers only see the new suffix.
    """
    delta = getattr(resp, "delta", None)
    if isinstance(delta, str):
        return delta
    text = getattr(resp, "text", None)
    if isinstance(text, str):
        if previous_text and text.startswith(previous_text):
            return text[len(previous_text):]
        return text
    return ""


def stream_complete_with_model_fallback(
    *,
    prompt: str,
    logger: logging.Logger,
    model_id: Optional[str] = None,
) -> Generator[str, None, None]:
    """Stream LLM tokens with a one-shot fallback to the default model.

    The fallback only kicks in if the primary model raises *before* yielding
    any tokens. Once even a single delta has been emitted the partial response
    has already reached the user, so a mid-stream failure is re-raised rather
    than silently swapping models mid-flight.
    """
    from backend.llm_provider import get_llm

    def _stream(target_model_id: Optional[str]) -> Generator[str, None, None]:
        llm_kwargs = {}
        if target_model_id:
            llm_kwargs["model_id"] = target_model_id
        llm = get_llm(**llm_kwargs)
        # Track previously-emitted text so providers that send cumulative
        # .text instead of .delta don't replay the whole response each tick.
        seen = ""
        for resp in llm.stream_complete(prompt):
            chunk = _extract_delta(resp, seen)
            if chunk:
                seen += chunk
                yield chunk

    yielded_any = False
    primary_exc: Optional[Exception] = None
    try:
        for chunk in _stream(model_id):
            yielded_any = True
            yield chunk
    except Exception as exc:
        primary_exc = exc

    if not yielded_any:
        fallback_model_id = config.BEDROCK_MODEL_ID
        if model_id and model_id != fallback_model_id:
            logger.warning(
                "Primary streaming model %s failed (%s). Falling back to %s.",
                model_id,
                primary_exc,
                fallback_model_id,
            )
            yield from _stream(fallback_model_id)
        elif primary_exc is not None:
            raise primary_exc


def complete_with_model_fallback(
    *,
    prompt: str,
    logger: logging.Logger,
    model_id: Optional[str] = None,
) -> str:
    from backend.llm_provider import get_llm

    def _complete(target_model_id: Optional[str]) -> str:
        llm_kwargs = {}
        if target_model_id:
            llm_kwargs["model_id"] = target_model_id
        response = get_llm(**llm_kwargs).complete(prompt)
        response_text = extract_completion_text(response)
        if not response_text:
            raise ValueError("LLM returned an empty response")
        return response_text

    try:
        return _complete(model_id)
    except Exception as exc:
        fallback_model_id = config.BEDROCK_MODEL_ID
        if model_id and model_id != fallback_model_id:
            logger.warning(
                "Primary model %s failed (%s). Retrying with default model %s.",
                model_id,
                exc,
                fallback_model_id,
            )
            return _complete(fallback_model_id)
        raise
