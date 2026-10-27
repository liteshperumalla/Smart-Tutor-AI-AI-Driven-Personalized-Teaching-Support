"""LLM generations carry the requesting user (pseudonym), chat session and feature.

Regression: every Bedrock generation was opened as a bare root observation, so
Langfuse traces had no user_id, session_id or tags and every user/session/
feature view in Langfuse was empty.
"""

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

langfuse = pytest.importorskip("langfuse")

import backend.langfuse_setup as langfuse_setup
from backend.api.dependencies import _set_trace_attributes
from backend.bedrock_llm import BedrockLLM
from backend.log_redaction import user_ref


@pytest.fixture
def offline_langfuse(monkeypatch):
    # Unreachable host: spans are created locally and never exported.
    client = langfuse.Langfuse(public_key="pk-lf-test", secret_key="sk-lf-test", host="http://127.0.0.1:9")
    monkeypatch.setattr(langfuse_setup, "_langfuse_client", client)
    yield client


def _app(captured):
    async def fake_session(request: Request):
        _set_trace_attributes(request, "alice")
        return "token", {"username": "alice"}

    app = FastAPI()

    @app.post("/api/v1/chat/sessions/{session_id}/messages")
    async def send(session_id: str, _session=Depends(fake_session)):
        def body():
            # Opened lazily while the response streams, as in the real route.
            call = BedrockLLM._begin_call(BedrockLLM.__new__(BedrockLLM), "model-x", "hi")
            captured.update(call.generation._otel_span.attributes)
            call.generation.end()
            yield "ok"

        return StreamingResponse(body())

    return app


def test_streamed_generation_carries_user_session_and_feature(offline_langfuse):
    captured = {}
    TestClient(_app(captured)).post("/api/v1/chat/sessions/abc123/messages")

    assert captured["user.id"] == user_ref("alice")
    assert captured["session.id"] == "abc123"
    assert tuple(captured["langfuse.trace.tags"]) == ("chat",)
    assert captured["langfuse.trace.name"] == "chat"


def test_generation_outside_a_request_has_no_user(offline_langfuse):
    langfuse_setup._request_trace_attributes.set(None)
    call = BedrockLLM._begin_call(BedrockLLM.__new__(BedrockLLM), "model-x", "hi")
    attrs = dict(call.generation._otel_span.attributes)
    call.generation.end()
    assert "user.id" not in attrs
