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
SONNET = "us.anthropic.claude-sonnet-5-5"
HAIKU = "us.anthropic.claude-haiku-5-5"
OPUS = "us.anthropic.claude-opus-4-20250514-v1:0"
LUNA = "us.openai.gpt-6-luna"
LLAMA = "us.meta.llama3-3-70b-instruct-v1:0"


# ── Validation ──────────────────────────────────────────────────────────


def test_auto_and_offered_models_are_accepted():
    for model_id in (None, "", LLAMA, SONNET, HAIKU, LUNA):
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


def test_retired_ids_are_rejected():
    # IDs the selector used before they were checked against the AWS model cards.
    for old in ("us.anthropic.claude-5-5-sonnet-20261022-v1:0", "openai.gpt-6-luna-2026"):
        with pytest.raises(ModelChoiceError):
            validate_model_choice(old, is_admin=False)


def test_students_are_not_offered_admin_models():
    student = {m["model_id"] for m in available_chat_models(False)}
    admin = {m["model_id"] for m in available_chat_models(True)}
    assert OPUS not in student and OPUS in admin
    assert student == {LLAMA, SONNET, HAIKU, LUNA}


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


def test_models_endpoint_lists_what_the_user_may_pick(client_with):
    client = client_with(_FallbackChatService(answered_by=LLAMA))
    ids = {m["model_id"] for m in client.get("/chat/models").json()["models"]}
    assert ids == {LLAMA, SONNET, HAIKU, LUNA}


def test_model_fields_round_trip_through_storage():
    msg = ChatMessage(role="assistant", content="x", model_used=LLAMA, model_requested=SONNET)
    restored = ChatMessage.from_dict(msg.to_dict())
    assert (restored.model_used, restored.model_requested) == (LLAMA, SONNET)
    assert "model_used" not in ChatMessage(role="user", content="q").to_dict()


# ── Bedrock client ──────────────────────────────────────────────────────


class _FakeBedrock:
    """invoke_model / converse fail for every model except ``works``."""

    def __init__(self, works, stream=("Hel", "lo")):
        self.works = works
        self.stream = stream
        self.tried = []
        self.bodies = []
        self.converse_calls = []

    def _check(self, model_id):
        self.tried.append(model_id)
        if model_id != self.works:
            raise RuntimeError(f"{model_id} unavailable")

    def invoke_model(self, modelId, body, **kwargs):
        self._check(modelId)
        self.bodies.append(json.loads(body))
        if "llama" in modelId:
            payload = {"generation": "from llama"}
        else:
            payload = {"content": [{"text": "from claude"}], "usage": {}}
        return {"body": io.BytesIO(json.dumps(payload).encode())}

    def converse(self, **request):
        self._check(request["modelId"])
        self.converse_calls.append(request)
        content = [{"reasoningContent": {"reasoningText": {"text": "thinking"}}}, {"text": "from converse"}]
        return {"output": {"message": {"content": content}}, "usage": {"inputTokens": 3, "outputTokens": 2}}

    def converse_stream(self, **request):
        self._check(request["modelId"])
        self.converse_calls.append(request)
        events = [{"contentBlockDelta": {"delta": {"reasoningContent": {"text": "thinking"}}}}]
        events += [{"contentBlockDelta": {"delta": {"text": t}}} for t in self.stream]
        return {"stream": events + [{"messageStop": {"stopReason": "end_turn"}}]}


def _client(model_id, fake, monkeypatch):
    monkeypatch.setattr(bedrock_llm.boto3, "client", lambda *a, **k: fake)
    monkeypatch.setattr(config, "BEDROCK_MODEL_ID", LLAMA)
    monkeypatch.setattr(config, "ENABLE_COST_TRACKING", False, raising=False)
    monkeypatch.setattr(config, "BEDROCK_GUARDRAIL_ID", "", raising=False)
    return bedrock_llm.BedrockLLM(model_id=model_id)


def test_bedrock_fallback_is_recorded(monkeypatch):
    fake = _FakeBedrock(works=LLAMA)
    llm = _client(SONNET, fake, monkeypatch)
    usage = model_usage.start_tracking()
    assert llm.generate("q") == "from llama"
    assert fake.tried == [SONNET, SONNET[3:], LLAMA]
    assert usage["model"] == LLAMA


@pytest.mark.parametrize("model_id", [SONNET, HAIKU])
def test_claude_request_sends_temperature_without_top_p(monkeypatch, model_id):
    fake = _FakeBedrock(works=model_id)
    llm = _client(model_id, fake, monkeypatch)
    usage = model_usage.start_tracking()
    assert llm.generate("q", temperature=0.3) == "from claude"
    body = fake.bodies[-1]
    assert body["temperature"] == 0.3 and "top_p" not in body
    assert usage["model"] == model_id


def test_luna_runs_on_bedrock_converse(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)  # not needed any more
    fake = _FakeBedrock(works=LUNA)
    llm = _client(LUNA, fake, monkeypatch)
    usage = model_usage.start_tracking()
    assert llm.generate("q", system_prompt="be brief") == "from converse"  # reasoning dropped
    request = fake.converse_calls[-1]
    assert request["modelId"] == LUNA
    assert request["system"] == [{"text": "be brief"}]
    assert "temperature" not in request["inferenceConfig"]
    assert usage["model"] == LUNA


@pytest.mark.parametrize("model_id", [LLAMA, LUNA])
def test_llama_and_luna_stream_token_by_token(monkeypatch, model_id):
    fake = _FakeBedrock(works=model_id)
    llm = _client(model_id, fake, monkeypatch)
    usage = model_usage.start_tracking()
    assert list(llm.stream_generate("q")) == ["Hel", "lo"]
    assert usage["model"] == model_id
    if model_id == LLAMA:  # Converse applies the chat template; keep the tutor persona
        assert fake.converse_calls[-1]["system"] == [{"text": bedrock_llm.BedrockLLM.LLAMA_SYSTEM_PROMPT}]


def test_failed_stream_falls_back_and_records_the_fallback(monkeypatch):
    fake = _FakeBedrock(works=LLAMA)
    llm = _client(LUNA, fake, monkeypatch)
    usage = model_usage.start_tracking()
    assert "".join(llm.stream_generate("q")) == "from llama"
    assert usage["model"] == LLAMA
