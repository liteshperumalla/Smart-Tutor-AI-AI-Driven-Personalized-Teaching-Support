"""The chat model selector: only offered models are accepted, and each answer
records the model that actually produced it (including Bedrock fallbacks)."""

import io
import json

import pytest

from backend import bedrock_llm, model_usage
from backend.api.dependencies import get_current_session, get_current_user, get_rate_limiter_dep
from backend.api.main import app
from backend.api.routes import chat as chat_routes
from backend.chat_models import ModelChoiceError, available_chat_models, validate_model_choice
from backend.config import config
from backend.csrf_protection import csrf_protect
from backend.services.models import ChatMessage, ChatSession

STUDENT = {"username": "model-tester", "role": "Student"}
SONNET = "us.anthropic.claude-5-5-sonnet-20261022-v1:0"
OPUS = "us.anthropic.claude-opus-4-20250514-v1:0"
LUNA = "openai.gpt-6-luna-2026"
LLAMA = "us.meta.llama3-3-70b-instruct-v1:0"


# ── Validation ──────────────────────────────────────────────────────────


def test_auto_and_offered_models_are_accepted(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    for model_id in (None, "", LLAMA, SONNET):
        validate_model_choice(model_id, is_admin=False)
    validate_model_choice(OPUS, is_admin=True)


@pytest.mark.parametrize(
    "model_id, is_admin, status",
    [
        ("anthropic.claude-anything", False, 400),  # not in the selector
        (OPUS, False, 403),  # admin-only
    ],
)
def test_other_models_are_rejected(model_id, is_admin, status):
    with pytest.raises(ModelChoiceError) as exc:
        validate_model_choice(model_id, is_admin)
    assert exc.value.status_code == status


def test_openai_model_needs_a_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ModelChoiceError):
        validate_model_choice(LUNA, is_admin=False)
    assert LUNA not in {m["model_id"] for m in available_chat_models(False)}
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    validate_model_choice(LUNA, is_admin=False)
    assert LUNA in {m["model_id"] for m in available_chat_models(False)}


def test_students_are_not_offered_admin_models(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    student = {m["model_id"] for m in available_chat_models(False)}
    admin = {m["model_id"] for m in available_chat_models(True)}
    assert OPUS not in student and OPUS in admin
    assert {LLAMA, SONNET} <= student


# ── Route ───────────────────────────────────────────────────────────────


class _NoLimits:
    async def check_model_rate_limit(self, *args, **kwargs):
        return None

    async def check_cost_budget(self, *args, **kwargs):
        return None


class _FallbackChatService:
    """Streams an answer that the Bedrock client produced with ``answered_by``."""

    def __init__(self, answered_by):
        self.answered_by = answered_by
        self.saved = []
        self.calls = []

    def load_session(self, username, session_id):
        return ChatSession(id=session_id, title="t", messages=[])

    def stream_response(self, query, **kwargs):
        self.calls.append(kwargs)

        def gen():
            # Recorded while the response streams, as the real client does.
            model_usage.record_model_used(self.answered_by)
            yield "Hello"

        return gen(), [], kwargs.get("model_id")

    def append_and_save(self, username, session_id, message):
        self.saved.append(message)


@pytest.fixture
def client_with(test_client):
    def make(service, user=STUDENT):
        app.dependency_overrides[get_current_session] = lambda: ("token", user)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[chat_routes.get_chat_service] = lambda: service
        app.dependency_overrides[get_rate_limiter_dep] = lambda: _NoLimits()
        app.dependency_overrides[csrf_protect] = lambda: None
        return test_client

    yield make
    app.dependency_overrides.clear()


def _assistant(service):
    return [m for m in service.saved if m.role == "assistant"][-1]


def test_answer_records_the_fallback_model(client_with):
    service = _FallbackChatService(answered_by=LLAMA)
    client = client_with(service)
    response = client.post("/chat/sessions/s1/messages", json={"query": "hi", "model_id": SONNET})
    assert response.status_code == 200, response.text
    assert service.calls[-1]["model_id"] == SONNET
    message = _assistant(service)
    assert message.model_requested == SONNET
    assert message.model_used == LLAMA  # not mislabelled as Sonnet


def test_answer_records_the_requested_model_when_it_answers(client_with):
    service = _FallbackChatService(answered_by=SONNET)
    client = client_with(service)
    assert client.post("/chat/sessions/s1/messages", json={"query": "hi", "model_id": SONNET}).status_code == 200
    assert _assistant(service).model_used == SONNET


def test_route_rejects_admin_model_for_students(client_with):
    service = _FallbackChatService(answered_by=OPUS)
    client = client_with(service)
    response = client.post("/chat/sessions/s1/messages", json={"query": "hi", "model_id": OPUS})
    assert response.status_code == 403
    assert service.calls == []  # never reached the LLM


def test_models_endpoint_lists_what_the_user_may_pick(client_with, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = client_with(_FallbackChatService(answered_by=LLAMA))
    ids = {m["model_id"] for m in client.get("/chat/models").json()["models"]}
    assert OPUS not in ids and LUNA not in ids and SONNET in ids


def test_model_fields_round_trip_through_storage():
    msg = ChatMessage(role="assistant", content="x", model_used=LLAMA, model_requested=SONNET)
    restored = ChatMessage.from_dict(msg.to_dict())
    assert (restored.model_used, restored.model_requested) == (LLAMA, SONNET)
    assert "model_used" not in ChatMessage(role="user", content="q").to_dict()


# ── Bedrock client ──────────────────────────────────────────────────────


class _FakeBedrock:
    """invoke_model fails for every model except ``works``."""

    def __init__(self, works):
        self.works = works
        self.tried = []

    def invoke_model(self, modelId, body, **kwargs):
        self.tried.append(modelId)
        if modelId != self.works:
            raise RuntimeError(f"{modelId} unavailable")
        if "llama" in modelId:
            payload = {"generation": "from llama"}
        else:
            payload = {"content": [{"text": "from claude"}], "usage": {}}
        return {"body": io.BytesIO(json.dumps(payload).encode())}


def _client(model_id, fake, monkeypatch):
    monkeypatch.setattr(bedrock_llm.boto3, "client", lambda *a, **k: fake)
    monkeypatch.setattr(config, "BEDROCK_MODEL_ID", LLAMA)
    monkeypatch.setattr(config, "ENABLE_COST_TRACKING", False, raising=False)
    return bedrock_llm.BedrockLLM(model_id=model_id)


def test_bedrock_fallback_is_recorded(monkeypatch):
    fake = _FakeBedrock(works=LLAMA)
    llm = _client(SONNET, fake, monkeypatch)
    usage = model_usage.start_tracking()
    assert llm.generate("q") == "from llama"
    assert fake.tried == [SONNET, SONNET[3:], LLAMA]
    assert usage["model"] == LLAMA


def test_bedrock_primary_model_is_recorded(monkeypatch):
    llm = _client(SONNET, _FakeBedrock(works=SONNET), monkeypatch)
    usage = model_usage.start_tracking()
    assert llm.generate("q") == "from claude"
    assert usage["model"] == SONNET


def test_openai_uses_configured_model_name(monkeypatch):
    sent = {}

    class _Completions:
        def create(self, **kwargs):
            sent.update(kwargs)
            msg = type("M", (), {"content": "from openai"})()
            return type("R", (), {"choices": [type("C", (), {"message": msg})()]})()

    class _OpenAI:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": _Completions()})()

    import sys
    import types

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=_OpenAI))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(config, "OPENAI_CHAT_MODEL", "gpt-6-luna")
    llm = _client(LUNA, _FakeBedrock(works=LLAMA), monkeypatch)
    usage = model_usage.start_tracking()
    assert llm.generate("q") == "from openai"
    assert sent["model"] == "gpt-6-luna"  # not the old hardcoded gpt-4o
    assert usage["model"] == LUNA
