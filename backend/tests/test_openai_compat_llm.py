"""OpenAI-compatible LLM client (Groq / Gemini / Ollama) and the provider switch."""

from types import SimpleNamespace

import pytest

from backend import model_usage
from backend import openai_compat_llm as compat
from backend.config import config
from backend.llm_provider import create_llm_client
from backend.openai_compat_llm import BLOCKED_MESSAGE, OpenAICompatLLM, resolve_endpoint


def _response(text, prompt_tokens=7, completion_tokens=3):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def _chunk(text=None, usage=None):
    choices = [SimpleNamespace(delta=SimpleNamespace(content=text))] if text is not None else []
    return SimpleNamespace(choices=choices, usage=usage)


class FakeClient:
    """One provider's fake ``openai.OpenAI``; fails for models in ``broken``."""

    def __init__(self, provider, log, broken=(), stream=("Hel", "lo"), fail_after=None, verdict="safe"):
        self.provider = provider
        self.log = log
        self.broken = set(broken)
        self.stream = stream
        self.fail_after = fail_after
        self.verdict = verdict
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **request):
        self.log.append((self.provider, request))
        model = request["model"]
        if model == config.LLM_MODERATION_MODEL:
            return _response(self.verdict)
        if model in self.broken or "*" in self.broken:
            raise RuntimeError(f"429 rate limited: {model}")
        if request.get("stream"):
            return self._stream()
        return _response(f"answer from {self.provider}/{model}")

    def _stream(self):
        for i, text in enumerate(self.stream):
            if self.fail_after is not None and i == self.fail_after:
                raise RuntimeError("connection reset")
            yield _chunk(text)
        yield _chunk(usage=SimpleNamespace(prompt_tokens=11, completion_tokens=2))


@pytest.fixture(autouse=True)
def groq_config(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(config, "GROQ_API_KEY", "gsk-test")
    monkeypatch.setattr(config, "GROQ_MODEL_ID", "llama-3.3-70b-versatile")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "gem-test")
    monkeypatch.setattr(config, "GEMINI_MODEL_ID", "gemini-2.5-flash")
    monkeypatch.setattr(config, "LLM_MODEL_ID", "llama-3.3-70b-versatile")
    monkeypatch.setattr(config, "LLM_BASE_URL", "")
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    monkeypatch.setattr(config, "LLM_FALLBACK_PROVIDERS", [])
    monkeypatch.setattr(config, "LLM_MODERATION_MODEL", "")
    monkeypatch.setattr(config, "ENABLE_COST_TRACKING", False)


def _llm(log, model_id=None, fallbacks=(), clients=None):
    clients = clients or {}

    def factory(endpoint):
        return clients.get(endpoint.provider) or FakeClient(endpoint.provider, log)

    return OpenAICompatLLM(model_id=model_id, fallback_providers=list(fallbacks), client_factory=factory)


class TestEndpoints:
    def test_groq_defaults(self):
        endpoint = resolve_endpoint("groq")
        assert endpoint.base_url == "https://api.groq.com/openai/v1"
        assert endpoint.api_key == "gsk-test"
        assert endpoint.default_model == "llama-3.3-70b-versatile"

    def test_gemini_uses_its_openai_compatible_endpoint(self):
        endpoint = resolve_endpoint("gemini")
        assert "generativelanguage.googleapis.com" in endpoint.base_url
        assert endpoint.default_model == "gemini-2.5-flash"

    def test_ollama_appends_v1(self, monkeypatch):
        monkeypatch.setattr(config, "OLLAMA_BASE_URL", "http://ollama:11434/")
        monkeypatch.setattr(config, "LLM_MODEL", "llama3.1:8b")
        endpoint = resolve_endpoint("ollama")
        assert endpoint.base_url == "http://ollama:11434/v1"
        assert endpoint.default_model == "llama3.1:8b"

    def test_base_url_override_applies_to_the_primary_only(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_BASE_URL", "https://proxy.example/v1")
        assert resolve_endpoint("groq").base_url == "https://proxy.example/v1"
        assert "googleapis" in resolve_endpoint("gemini").base_url

    def test_openai_compat_requires_url_and_model(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_PROVIDER", "openai_compat")
        with pytest.raises(ValueError):
            resolve_endpoint("openai_compat")
        monkeypatch.setattr(config, "LLM_BASE_URL", "https://openrouter.ai/api/v1")
        monkeypatch.setattr(config, "LLM_MODEL_ID", "meta-llama/llama-3.3-70b-instruct:free")
        assert resolve_endpoint("openai_compat").default_model == "meta-llama/llama-3.3-70b-instruct:free"

    def test_unknown_provider(self):
        with pytest.raises(ValueError):
            resolve_endpoint("watsonx")


class TestGenerate:
    def test_sends_system_and_user_messages(self):
        log = []
        usage = model_usage.start_tracking()
        llm = _llm(log)
        assert llm.generate("q", system_prompt="be brief", temperature=0.2) == (
            "answer from groq/llama-3.3-70b-versatile"
        )
        request = log[-1][1]
        assert request["messages"] == [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "q"},
        ]
        assert request["temperature"] == 0.2
        assert usage["model"] == "llama-3.3-70b-versatile"
        assert (llm.total_input_tokens, llm.total_output_tokens) == (7, 3)
        assert llm.total_cost == 0.0  # free tier

    def test_requested_model_falls_back_to_provider_default(self):
        log = []
        groq = FakeClient("groq", log, broken={"llama-3.1-8b-instant"})
        llm = _llm(log, model_id="llama-3.1-8b-instant", clients={"groq": groq})
        assert llm.generate("q") == "answer from groq/llama-3.3-70b-versatile"
        assert [r["model"] for _, r in log] == ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]

    def test_rate_limited_provider_falls_back_to_next_provider(self):
        log = []
        groq = FakeClient("groq", log, broken={"*"})
        llm = _llm(log, fallbacks=["gemini"], clients={"groq": groq})
        assert llm.generate("q") == "answer from gemini/gemini-2.5-flash"
        assert [p for p, _ in log] == ["groq", "gemini"]

    def test_raises_when_every_option_fails(self):
        log = []
        clients = {"groq": FakeClient("groq", log, broken={"*"}), "gemini": FakeClient("gemini", log, broken={"*"})}
        with pytest.raises(RuntimeError, match="gemini-2.5-flash"):
            _llm(log, fallbacks=["gemini"], clients=clients).generate("q")

    def test_fallback_list_comes_from_config(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_FALLBACK_PROVIDERS", ["groq", "gemini"])
        llm = OpenAICompatLLM(client_factory=lambda e: None)
        assert llm.fallback_providers == ["gemini"]  # the primary isn't repeated


class TestStream:
    def test_streams_chunks_and_records_usage(self):
        log = []
        usage = model_usage.start_tracking()
        llm = _llm(log)
        assert list(llm.stream_generate("q")) == ["Hel", "lo"]
        assert log[-1][1]["stream"] is True
        assert log[-1][1]["stream_options"] == {"include_usage": True}
        assert usage["model"] == "llama-3.3-70b-versatile"
        assert (llm.total_input_tokens, llm.total_output_tokens) == (11, 2)

    def test_stream_falls_back_before_any_text(self):
        log = []
        groq = FakeClient("groq", log, broken={"*"})
        llm = _llm(log, fallbacks=["gemini"], clients={"groq": groq})
        assert "".join(llm.stream_generate("q")) == "Hello"
        assert [p for p, _ in log] == ["groq", "gemini"]

    def test_mid_stream_failure_is_not_retried(self):
        log = []
        groq = FakeClient("groq", log, fail_after=1)
        llm = _llm(log, fallbacks=["gemini"], clients={"groq": groq})
        out = []
        with pytest.raises(RuntimeError, match="connection reset"):
            for text in llm.stream_generate("q"):
                out.append(text)
        assert out == ["Hel"]
        assert [p for p, _ in log] == ["groq"]


class TestModeration:
    def test_off_by_default(self):
        log = []
        _llm(log).generate("q")
        assert len(log) == 1

    def test_unsafe_prompt_is_blocked(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_MODERATION_MODEL", "llama-guard")
        log = []
        groq = FakeClient("groq", log, verdict="unsafe\nS2")
        llm = _llm(log, clients={"groq": groq})
        assert llm.generate("bad") == BLOCKED_MESSAGE
        assert list(llm.stream_generate("bad")) == [BLOCKED_MESSAGE]
        assert all(r["model"] == "llama-guard" for _, r in log)

    def test_safe_prompt_goes_through(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_MODERATION_MODEL", "llama-guard")
        log = []
        llm = _llm(log, clients={"groq": FakeClient("groq", log, verdict="safe")})
        assert llm.generate("q").startswith("answer from groq")

    def test_moderation_errors_fail_open(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_MODERATION_MODEL", "llama-guard")
        log = []
        groq = FakeClient("groq", log, broken={"llama-guard"})
        groq.create_orig = groq.create

        def create(**request):
            if request["model"] == "llama-guard":
                raise RuntimeError("moderation down")
            return groq.create_orig(**request)

        groq.chat.completions.create = create
        assert _llm(log, clients={"groq": groq}).generate("q").startswith("answer from groq")


class TestFactory:
    def test_create_llm_client_returns_compat_client_off_bedrock(self, monkeypatch):
        monkeypatch.setattr(compat, "_openai_client", lambda endpoint: FakeClient(endpoint.provider, []))
        llm = create_llm_client()
        assert isinstance(llm, OpenAICompatLLM)
        assert llm.model_id == "llama-3.3-70b-versatile"

    def test_create_llm_client_keeps_bedrock_by_default(self, monkeypatch):
        from backend import bedrock_llm

        monkeypatch.setattr(config, "LLM_PROVIDER", "bedrock")
        monkeypatch.setattr(bedrock_llm.boto3, "client", lambda *a, **k: object())
        assert isinstance(create_llm_client(), bedrock_llm.BedrockLLM)

    def test_llamaindex_wrapper_uses_the_compat_client(self, monkeypatch):
        from backend.llm_provider import get_llm

        monkeypatch.setattr(compat, "_openai_client", lambda endpoint: FakeClient(endpoint.provider, []))
        llm = get_llm()
        assert llm.class_name() == "OpenAICompatLLM"
        assert llm.complete("q").text == "answer from groq/llama-3.3-70b-versatile"
        assert [r.delta for r in llm.stream_complete("q")] == ["Hel", "lo"]


class TestChatModelCatalog:
    def test_off_bedrock_students_see_the_provider_models(self, monkeypatch):
        from backend.chat_models import ModelChoiceError, available_chat_models, validate_model_choice

        monkeypatch.setattr(config, "LLM_ROUTING_SIMPLE_MODEL", "llama-3.1-8b-instant")
        monkeypatch.setattr(config, "LLM_ROUTING_COMPLEX_MODEL", "")
        ids = [m["model_id"] for m in available_chat_models(is_admin=True)]
        assert ids == ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
        validate_model_choice("llama-3.1-8b-instant", is_admin=False)
        with pytest.raises(ModelChoiceError):
            validate_model_choice("us.anthropic.claude-sonnet-5-5", is_admin=True)
