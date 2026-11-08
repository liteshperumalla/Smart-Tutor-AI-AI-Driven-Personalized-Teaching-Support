"""LlamaIndex LLM backed by ``OpenAICompatLLM`` (Groq, Gemini, Ollama, ...).

Reuses the Bedrock wrapper's ``complete`` / ``stream_complete`` / ``chat``
methods, which only call ``generate`` and ``stream_generate`` on the core
client, so RAG and agent code behave the same on every provider.
"""

from __future__ import annotations

from typing import Any, Optional

from llama_index.core.llms import LLM

from backend.bedrock_llamaindex import BedrockLLM
from backend.config import config
from backend.openai_compat_llm import OpenAICompatLLM


class OpenAICompatLlamaIndexLLM(BedrockLLM):
    """LlamaIndex-compatible wrapper for OpenAI-compatible providers."""

    _llm_type: str = "openai_compat"

    provider: str = ""

    def __init__(self, model_id: Optional[str] = None, provider: Optional[str] = None, **kwargs: Any):
        core = OpenAICompatLLM(model_id=model_id, provider=provider or config.LLM_PROVIDER)
        # Skip BedrockLLM.__init__, which builds a Bedrock client.
        LLM.__init__(self, model_id=core.model_id, region="", provider=core.provider, **kwargs)
        self._bedrock = core

    @classmethod
    def class_name(cls) -> str:
        return "OpenAICompatLLM"
