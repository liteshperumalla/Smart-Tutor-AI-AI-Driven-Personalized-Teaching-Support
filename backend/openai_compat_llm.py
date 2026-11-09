"""LLM client for any OpenAI-compatible chat API.

One client covers the free providers in the AWS exit plan
(docs/plans/2026-11-08-aws-to-free-services-migration.md):

- ``openrouter``    OpenRouter: many models behind one key, https://openrouter.ai/api/v1
- ``groq``          Groq (Llama 3.x), https://api.groq.com/openai/v1
- ``gemini``        Google Gemini's OpenAI-compatible endpoint
- ``ollama``        a local Ollama server (``OLLAMA_BASE_URL``/v1)
- ``openai_compat`` anything else: set ``LLM_BASE_URL`` and ``LLM_API_KEY``

It has the same ``generate`` / ``stream_generate`` interface as
``BedrockLLM`` and reports tokens, latency and cost the same way.

When a call fails before any text is returned, the client tries, in order:
the provider's default model (if a different model was asked for), each
model in ``LLM_FALLBACK_MODELS`` on the same provider, then each provider in
``LLM_FALLBACK_PROVIDERS``. This covers free-tier rate limits (HTTP 429) and
free models that come and go.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional

from backend.config import config
from backend.llm_core import BaseLLMClient
from backend.logger import get_logger
from backend.model_usage import record_model_used

logger = get_logger(__name__)

OPENAI_COMPAT_PROVIDERS = ("openrouter", "groq", "gemini", "ollama", "openai_compat")

# Answer returned in place of the model's when the moderation model flags
# the prompt (the same role Bedrock Guardrails' blocked message plays).
BLOCKED_MESSAGE = (
    "I can't help with that request. Please ask a question about your course material."
)


@dataclass(frozen=True)
class Endpoint:
    """Where one provider lives and which model it uses by default."""

    provider: str
    base_url: str
    api_key: str
    default_model: str
    # Extra HTTP headers on every request (OpenRouter app attribution).
    headers: Optional[Dict[str, str]] = None
    # Retries the OpenAI SDK makes on 429/5xx before we fall back. OpenRouter
    # counts failed attempts against the free daily cap, so it gets none.
    max_retries: int = 2


def _sdk_retries(default: int) -> int:
    """LLM_SDK_MAX_RETRIES if set (>= 0), else the provider's default."""
    return config.LLM_SDK_MAX_RETRIES if config.LLM_SDK_MAX_RETRIES >= 0 else default


def resolve_endpoint(provider: str) -> Endpoint:
    """Build the endpoint for ``provider`` from config.

    ``LLM_BASE_URL`` / ``LLM_API_KEY`` override the base URL and key of the
    primary provider (``LLM_PROVIDER``) only, so a fallback provider always
    uses its own settings.
    """
    provider = provider.strip().lower()
    is_primary = provider == config.LLM_PROVIDER
    override_url = config.LLM_BASE_URL if is_primary else ""
    override_key = config.LLM_API_KEY if is_primary else ""
    override_model = config.LLM_MODEL_ID if is_primary else ""

    if provider == "openrouter":
        headers = {"X-Title": config.OPENROUTER_APP_NAME} if config.OPENROUTER_APP_NAME else {}
        if config.OPENROUTER_SITE_URL:
            headers["HTTP-Referer"] = config.OPENROUTER_SITE_URL
        return Endpoint(
            provider,
            override_url or "https://openrouter.ai/api/v1",
            override_key or config.OPENROUTER_API_KEY,
            override_model or config.OPENROUTER_MODEL_ID,
            headers=headers or None,
            max_retries=_sdk_retries(default=0),
        )
    if provider == "groq":
        return Endpoint(
            provider,
            override_url or "https://api.groq.com/openai/v1",
            override_key or config.GROQ_API_KEY,
            override_model or config.GROQ_MODEL_ID,
            max_retries=_sdk_retries(default=2),
        )
    if provider == "gemini":
        return Endpoint(
            provider,
            override_url or "https://generativelanguage.googleapis.com/v1beta/openai/",
            override_key or config.GEMINI_API_KEY,
            override_model or config.GEMINI_MODEL_ID,
            max_retries=_sdk_retries(default=2),
        )
    if provider == "ollama":
        return Endpoint(
            provider,
            override_url or config.OLLAMA_BASE_URL.rstrip("/") + "/v1",
            # Ollama ignores the key, but the OpenAI SDK requires one.
            override_key or "ollama",
            override_model or config.LLM_MODEL,
            max_retries=_sdk_retries(default=2),
        )
    if provider == "openai_compat":
        if not config.LLM_BASE_URL or not config.LLM_MODEL_ID:
            raise ValueError("LLM_PROVIDER=openai_compat needs LLM_BASE_URL and LLM_MODEL_ID")
        return Endpoint(
            provider,
            config.LLM_BASE_URL,
            config.LLM_API_KEY or "none",
            config.LLM_MODEL_ID,
            max_retries=_sdk_retries(default=2),
        )
    raise ValueError(
        f"Unknown OpenAI-compatible provider: {provider}. Supported: {OPENAI_COMPAT_PROVIDERS}"
    )


class OpenAICompatLLM(BaseLLMClient):
    """Direct client for an OpenAI-compatible chat completions API."""

    # Free tiers cost nothing. Add entries here for a paid endpoint.
    PRICING: Dict[str, Dict[str, float]] = {}

    def __init__(
        self,
        model_id: Optional[str] = None,
        provider: Optional[str] = None,
        fallback_providers: Optional[List[str]] = None,
        client_factory: Any = None,
        fallback_models: Optional[List[str]] = None,
        strict: bool = False,
    ):
        self.provider = (provider or config.LLM_PROVIDER).lower()
        self.endpoint = resolve_endpoint(self.provider)
        self.model_id = model_id or self.endpoint.default_model
        if fallback_providers is None:
            fallback_providers = config.LLM_FALLBACK_PROVIDERS
        self.fallback_providers = [p for p in fallback_providers if p and p != self.provider]
        # LLM_FALLBACK_MODELS name models of the primary provider only.
        if fallback_models is None:
            fallback_models = config.LLM_FALLBACK_MODELS if self.provider == config.LLM_PROVIDER else []
        self.fallback_models = list(fallback_models)
        # strict: only ever call model_id (e.g. an evaluation judge).
        self.strict = strict
        # Tests pass a factory; production builds openai.OpenAI clients.
        self._client_factory = client_factory or _openai_client
        self._clients: Dict[str, Any] = {}

        self.total_cost = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        logger.info(f"✓ LLM initialized: {self.provider} / {self.model_id}")

    # ── public API ──────────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        if self._is_blocked(prompt):
            return BLOCKED_MESSAGE
        last_exc: Optional[Exception] = None
        for endpoint, model in self._attempts():
            try:
                return self._complete(endpoint, model, prompt, max_tokens, temperature, top_p, system_prompt)
            except Exception as exc:
                last_exc = exc
                logger.warning(f"[LLM] {endpoint.provider}/{model} failed ({exc}); trying next option")
        assert last_exc is not None
        raise last_exc

    def stream_generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> Generator[str, None, None]:
        if self._is_blocked(prompt):
            yield BLOCKED_MESSAGE
            return
        last_exc: Optional[Exception] = None
        for endpoint, model in self._attempts():
            yielded = False
            try:
                for text in self._stream(endpoint, model, prompt, max_tokens, temperature, system_prompt):
                    yielded = True
                    yield text
                return
            except Exception as exc:
                # Once text reached the user, switching models would splice
                # two different answers together.
                if yielded:
                    raise
                last_exc = exc
                logger.warning(f"[LLM] stream {endpoint.provider}/{model} failed ({exc}); trying next option")
        assert last_exc is not None
        raise last_exc

    # ── internals ───────────────────────────────────────────────────────

    def _attempts(self) -> List[tuple]:
        """(endpoint, model) pairs to try, in order."""
        attempts = [(self.endpoint, self.model_id)]
        if self.strict:
            return attempts
        for model in [self.endpoint.default_model, *self.fallback_models]:
            if model and all(model != m for _, m in attempts):
                attempts.append((self.endpoint, model))
        for provider in self.fallback_providers:
            try:
                endpoint = resolve_endpoint(provider)
            except ValueError as exc:
                logger.warning(f"[LLM] skipping fallback provider {provider}: {exc}")
                continue
            attempts.append((endpoint, endpoint.default_model))
        return attempts

    def _client(self, endpoint: Endpoint) -> Any:
        client = self._clients.get(endpoint.provider)
        if client is None:
            client = self._client_factory(endpoint)
            self._clients[endpoint.provider] = client
        return client

    @staticmethod
    def _messages(prompt: str, system_prompt: Optional[str]) -> List[Dict[str, str]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _complete(
        self,
        endpoint: Endpoint,
        model: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        system_prompt: Optional[str],
    ) -> str:
        started = self._begin_call(model, prompt)
        try:
            response = self._client(endpoint).chat.completions.create(
                model=model,
                messages=self._messages(prompt, system_prompt),
                max_tokens=max_tokens,
                # top_p isn't sent: some models (e.g. Claude) reject it next
                # to temperature, and the stream path never sent it.
                temperature=temperature,
            )
        except Exception:
            self._record_usage(model, started, status="error")
            raise
        text = (response.choices[0].message.content or "") if response.choices else ""
        input_tokens, output_tokens = _usage(getattr(response, "usage", None))
        self._finish(model, started, prompt, input_tokens, output_tokens)
        return text

    def _stream(
        self,
        endpoint: Endpoint,
        model: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system_prompt: Optional[str],
    ) -> Generator[str, None, None]:
        started = self._begin_call(model, prompt)
        tokens = (0, 0)
        status = "cancelled"  # stays so only if the client stops reading
        try:
            stream = self._client(endpoint).chat.completions.create(
                model=model,
                messages=self._messages(prompt, system_prompt),
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                # The final chunk then carries the real token counts.
                stream_options={"include_usage": True},
            )
            first = True
            for chunk in stream:
                if getattr(chunk, "usage", None):
                    tokens = _usage(chunk.usage)
                if not chunk.choices:
                    continue
                text = chunk.choices[0].delta.content
                if text:
                    if first:
                        record_model_used(model)
                        started.first_token()
                        first = False
                    yield text
            status = "success"
        except Exception:
            status = "error"
            raise
        finally:
            # Also runs when the client disconnects mid-stream (GeneratorExit).
            self._record_usage(model, started, tokens[0], tokens[1], status=status)
            if status == "success":
                self._add_totals(tokens[0], tokens[1], self._calculate_cost(tokens[0], tokens[1], model))

    def _finish(self, model: str, started, prompt: str, input_tokens: int, output_tokens: int) -> None:
        cost = self._calculate_cost(input_tokens, output_tokens, model)
        self._add_totals(input_tokens, output_tokens, cost)
        if config.ENABLE_COST_TRACKING:
            self._log_cost(input_tokens, output_tokens, cost, prompt[:100])
        self._record_usage(model, started, input_tokens, output_tokens)
        record_model_used(model)

    def _is_blocked(self, prompt: str) -> bool:
        """Ask the moderation model (e.g. Llama Guard) whether to refuse.

        Off unless ``LLM_MODERATION_MODEL`` is set. Fails open: if the
        moderation call itself errors, the prompt goes through and a warning
        is logged, as with a guardrail that isn't provisioned.
        """
        moderation_model = config.LLM_MODERATION_MODEL
        if not moderation_model:
            return False
        try:
            response = self._client(self.endpoint).chat.completions.create(
                model=moderation_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=20,
                temperature=0,
            )
            verdict = (response.choices[0].message.content or "").strip().lower()
        except Exception as exc:
            logger.warning(f"[LLM] moderation check failed, allowing prompt: {exc}")
            return False
        if verdict.startswith("unsafe"):
            logger.warning(f"[LLM] Moderation blocked prompt ({verdict!r}): {prompt[:100]!r}")
            return True
        return False


def _usage(usage: Any) -> tuple:
    if usage is None:
        return 0, 0
    return int(getattr(usage, "prompt_tokens", 0) or 0), int(getattr(usage, "completion_tokens", 0) or 0)


def _openai_client(endpoint: Endpoint) -> Any:
    from openai import OpenAI

    return OpenAI(
        base_url=endpoint.base_url,
        api_key=endpoint.api_key or "missing",
        timeout=config.LLM_REQUEST_TIMEOUT,
        # The SDK retries 429/5xx with backoff before we fall back.
        max_retries=endpoint.max_retries,
        default_headers=endpoint.headers,
    )
