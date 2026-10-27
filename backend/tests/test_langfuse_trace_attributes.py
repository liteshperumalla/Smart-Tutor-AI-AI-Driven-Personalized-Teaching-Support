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


def test_agent_trace_root_and_children_are_v4_observations(offline_langfuse):
    """create_trace/traced_span used the removed v2 client.trace() API, so the
    agent pipeline's traces never reached Langfuse."""
    root = langfuse_setup.create_trace(
        "agent-pipeline", user_id="alice", session_id="s-1", tags=["agent"], input={"query": "q"}
    )
    assert root is not None
    with langfuse_setup.traced_span(root, "agent-rag-retrieval", input={"query": "q"}) as child:
        assert child is not None
    langfuse_setup.update_trace(root, output={"ok": True})

    root_span, child_span = root._otel_span, child._otel_span
    assert child_span.parent.span_id == root_span.context.span_id
    for span in (root_span, child_span):
        assert span.attributes["user.id"] == user_ref("alice")
        assert span.attributes["session.id"] == "s-1"
        assert tuple(span.attributes["langfuse.trace.tags"]) == ("agent",)
        assert span.end_time is not None  # only ended spans are exported


def test_update_trace_can_flag_without_ending(offline_langfuse):
    root = langfuse_setup.create_trace("agent-pipeline", user_id="alice")
    langfuse_setup.update_trace(root, level="ERROR", end=False)
    assert root._otel_span.end_time is None
    langfuse_setup.update_trace(root, output={"done": True})
    assert root._otel_span.end_time is not None


def test_session_feedback_becomes_a_langfuse_score(offline_langfuse, monkeypatch):
    calls = []
    monkeypatch.setattr(offline_langfuse, "create_score", lambda **kw: calls.append(kw))

    assert langfuse_setup.score_session_feedback("s-1", "thumbs_up")
    assert langfuse_setup.score_session_feedback("s-1", "thumbs_down")
    assert not langfuse_setup.score_session_feedback("s-1", "meh")

    assert [c["value"] for c in calls] == [1.0, 0.0]
    assert all(c["name"] == "user_feedback" and c["session_id"] == "s-1" for c in calls)


def test_first_token_sets_completion_start_time(offline_langfuse):
    """Langfuse derives time-to-first-token from completion_start_time."""
    call = BedrockLLM._begin_call(BedrockLLM.__new__(BedrockLLM), "model-x", "hi")
    call.first_token()
    attrs = dict(call.generation._otel_span.attributes)
    call.generation.end()
    assert any("completion_start_time" in key for key in attrs), attrs
