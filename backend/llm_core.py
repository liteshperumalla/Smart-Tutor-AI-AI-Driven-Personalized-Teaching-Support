"""Provider-neutral pieces shared by every direct LLM client.

``BedrockLLM`` (AWS) and ``OpenAICompatLLM`` (Groq, Gemini, Ollama, any
OpenAI-compatible endpoint) both inherit from ``BaseLLMClient``. It owns the
parts that don't depend on the provider: Langfuse generations, Prometheus
usage metrics, cost accounting and ``get_stats``. Subclasses implement
``generate`` and ``stream_generate`` with the same signatures.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional

from backend.logger import get_logger

logger = get_logger(__name__)


class _LLMCall:
    """Timing and the Langfuse generation for one LLM call."""

    __slots__ = ("t0", "generation")

    def __init__(self, t0: float, generation: Any = None):
        self.t0 = t0
        self.generation = generation

    def first_token(self) -> None:
        """Mark time to first token on the Langfuse generation (TTFT charts)."""
        if self.generation is not None:
            try:
                self.generation.update(completion_start_time=datetime.now(timezone.utc))
            except Exception:  # tracing must never break streaming
                pass


class BaseLLMClient:
    """Shared tracing, metrics and cost logic for direct LLM clients."""

    # Price per 1K tokens, keyed by model ID. Models not listed cost $0.
    PRICING: Dict[str, Dict[str, float]] = {}
    # Name of the Langfuse generation and the cost-tracker service. Every
    # provider keeps the "bedrock-generation" name because the Langfuse
    # dashboards (monitoring/langfuse/dashboards) filter on it.
    TRACE_NAME = "bedrock-generation"
    COST_SERVICE = "bedrock_llm"

    model_id: str
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        raise NotImplementedError

    def stream_generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> Generator[str, None, None]:
        raise NotImplementedError

    def _begin_call(self, model_id: str, prompt: str) -> _LLMCall:
        """Start timing a call and open its Langfuse generation.

        The LlamaIndex callback's generations carry no model or usage, so
        this generation is what Langfuse cost, token and model charts read.
        """
        generation = None
        try:
            from backend.langfuse_setup import get_langfuse_client, request_trace_scope

            client = get_langfuse_client()
            if client is not None:
                # Tag the generation with the requesting user (pseudonym),
                # chat session and feature so Langfuse can group it.
                with request_trace_scope():
                    generation = client.start_observation(
                        name=self.TRACE_NAME,
                        as_type="generation",
                        model=model_id,
                        input=prompt[:4000] if isinstance(prompt, str) else None,
                    )
        except Exception as e:  # tracing must never break generation
            logger.debug(f"[LLM] Langfuse generation skipped: {e}")
        return _LLMCall(time.monotonic(), generation)

    def _record_usage(
        self,
        model_id: str,
        started: _LLMCall,
        input_tokens: int = 0,
        output_tokens: int = 0,
        status: str = "success",
    ) -> None:
        """Send one call's latency, tokens and cost to Prometheus and Langfuse."""
        input_cost, output_cost = self._cost_split(input_tokens, output_tokens, model_id)
        cost = input_cost + output_cost
        try:
            from backend.metrics import record_llm_usage

            record_llm_usage(
                model=model_id,
                latency_seconds=time.monotonic() - started.t0,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                status=status,
            )
        except Exception as e:  # metrics must never break generation
            logger.debug(f"[LLM] usage metrics skipped: {e}")
        if started.generation is not None:
            try:
                started.generation.update(
                    usage_details={"input": input_tokens, "output": output_tokens},
                    # Split so Langfuse can chart prompt vs completion cost.
                    cost_details={"input": input_cost, "output": output_cost, "total": cost},
                    level="ERROR" if status == "error" else "DEFAULT",
                    status_message=None if status == "success" else status,
                )
                started.generation.end()
            except Exception as e:
                logger.debug(f"[LLM] Langfuse generation update skipped: {e}")
            started.generation = None

    def _calculate_cost(self, input_tokens: int, output_tokens: int, model_id: Optional[str] = None) -> float:
        """Cost in USD for one call."""
        input_cost, output_cost = self._cost_split(input_tokens, output_tokens, model_id)
        return input_cost + output_cost

    def _cost_split(
        self, input_tokens: int, output_tokens: int, model_id: Optional[str] = None
    ) -> tuple:
        """(input_cost, output_cost) in USD for one call."""
        pricing = self.PRICING.get(model_id or self.model_id, {"input": 0, "output": 0})
        return (input_tokens / 1000) * pricing["input"], (output_tokens / 1000) * pricing["output"]

    def _add_totals(self, input_tokens: int, output_tokens: int, cost: float) -> None:
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost

    def _log_cost(
        self, input_tokens: int, output_tokens: int, cost: float, prompt_preview: str
    ):
        """Write one call to the cost tracker."""
        try:
            from backend.cost_tracking import get_cost_tracker

            tracker = get_cost_tracker()
            tracker.log_cost(
                service=self.COST_SERVICE,
                operation="generate",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                model_id=self.model_id,
                metadata={
                    "prompt_preview": prompt_preview,
                    "total_cost": self.total_cost,
                },
            )

        except Exception as e:
            logger.warning(f"Failed to log cost: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            "model": self.model_id,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": self.total_cost,
            "avg_cost_per_request": (
                self.total_cost
                / max(1, self.total_input_tokens + self.total_output_tokens)
            )
            * 1000,
        }
