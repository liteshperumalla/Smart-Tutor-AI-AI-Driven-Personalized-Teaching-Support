from __future__ import annotations

import logging
from typing import Optional

from backend.config import config


def extract_completion_text(llm_response: object) -> str:
    text = getattr(llm_response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    return str(llm_response).strip()


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
