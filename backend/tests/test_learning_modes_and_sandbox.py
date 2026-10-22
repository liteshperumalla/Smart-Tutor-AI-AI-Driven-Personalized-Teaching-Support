"""Chat learning modes reach the generator; code sandbox forwards to the runner."""

import pytest

from backend.api.dependencies import get_current_session, get_current_user, get_rate_limiter_dep
from backend.api.main import app
from backend.api.routes import chat as chat_routes
from backend.api.routes import code as code_routes
from backend.csrf_protection import csrf_protect
from backend.services.models import ChatSession

USER = {"username": "mode-tester", "role": "Student"}


class _NoLimits:
    async def check_rate_limit(self, *args, **kwargs):
        return None

    async def check_model_rate_limit(self, *args, **kwargs):
        return None

    async def check_cost_budget(self, *args, **kwargs):
        return None


class _FakeChatService:
    def __init__(self):
        self.calls = []

    def load_session(self, username, session_id):
        return ChatSession(id=session_id, title="t", messages=[])

    def stream_response(self, query, **kwargs):
        self.calls.append({"query": query, **kwargs})
        return iter(["ok"]), [], "test-model"

    def __getattr__(self, name):  # persistence helpers used after streaming
        return lambda *args, **kwargs: None


@pytest.fixture
def overrides():
    fake = _FakeChatService()
    app.dependency_overrides[get_current_session] = lambda: ("token", USER)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[chat_routes.get_chat_service] = lambda: fake
    app.dependency_overrides[get_rate_limiter_dep] = lambda: _NoLimits()
    app.dependency_overrides[csrf_protect] = lambda: None
    yield fake
    app.dependency_overrides.clear()


@pytest.mark.parametrize("mode", ["learn", "practice", "review"])
def test_learning_mode_instructions_reach_generator(test_client, overrides, mode):
    response = test_client.post(
        "/chat/sessions/s1/messages",
        json={"query": "What is TF-IDF?", "learning_mode": mode},
    )
    assert response.status_code == 200, response.text
    call = overrides.calls[-1]
    assert call["answer_instructions"] == chat_routes.LEARNING_MODE_INSTRUCTIONS[mode]
    assert f"Mode: {mode.upper()}" in call["answer_instructions"]
    # Instructions go to generation only; the retrieval query stays the question.
    assert "Mode:" not in call["query"]


def test_ask_mode_and_default_add_no_instructions(test_client, overrides):
    for body in ({"query": "What is TF-IDF?"}, {"query": "What is TF-IDF?", "learning_mode": "ask"}):
        assert test_client.post("/chat/sessions/s1/messages", json=body).status_code == 200
        assert overrides.calls[-1]["answer_instructions"] is None


def test_unknown_learning_mode_is_rejected(test_client, overrides):
    response = test_client.post(
        "/chat/sessions/s1/messages", json={"query": "hi", "learning_mode": "cheat"}
    )
    assert response.status_code == 422


def test_chat_service_passes_instructions_to_rag(monkeypatch):
    from backend.services import chat_service as svc

    seen = {}

    def fake_generate(query, **kwargs):
        seen.update(query=query, **kwargs)
        return iter([]), []

    monkeypatch.setattr(svc, "generate_response_stream_and_sources", fake_generate)
    from backend import posthog_tracker

    monkeypatch.setattr(posthog_tracker, "feature_enabled", lambda *a, **k: False)
    svc.ChatService().stream_response("q", user_id="u", answer_instructions="Mode: REVIEW. x")
    assert seen["query"] == "q"
    assert seen["answer_instructions"] == "Mode: REVIEW. x"


def test_agent_path_keeps_instructions_out_of_retrieval(monkeypatch):
    from backend.services import chat_service as svc
    from backend import agents, posthog_tracker

    seen = {}

    def fake_pipeline(**kwargs):
        seen.update(kwargs)
        return iter([]), []

    monkeypatch.setattr(agents, "run_agent_pipeline", fake_pipeline)
    monkeypatch.setattr(
        posthog_tracker, "feature_enabled", lambda _user, flag, default=False: flag == "agent-system-enabled"
    )
    svc.ChatService().stream_response("what is recursion?", user_id="u", answer_instructions="Mode: LEARN. x")
    # Retrieval and routing see the student's question; the mode goes to the prompt.
    assert seen["query"] == "what is recursion?"
    assert seen["answer_instructions"] == "Mode: LEARN. x"


# ── Code sandbox ─────────────────────────────────────────────────────────


def test_execute_requires_sign_in(test_client):
    app.dependency_overrides.clear()
    response = test_client.post("/code/execute", json={"code": "print(1)", "language": "python"})
    assert response.status_code == 401


def test_execute_disabled_without_runner(test_client, overrides, monkeypatch):
    from backend.config import config

    monkeypatch.setattr(config, "ENABLE_CODE_EXECUTION", True)
    monkeypatch.setattr(config, "CODE_RUNNER_URL", "")
    response = test_client.post("/code/execute", json={"code": "print(1)", "language": "python"})
    assert response.status_code == 503
    assert "isn't available" in response.json()["detail"]


def test_execute_forwards_to_runner_for_students(test_client, overrides, monkeypatch):
    from backend.config import config

    monkeypatch.setattr(config, "ENABLE_CODE_EXECUTION", True)
    monkeypatch.setattr(config, "CODE_RUNNER_URL", "http://runner:8080")
    sent = {}

    def fake_run(code, language):
        sent.update(code=code, language=language)
        return code_routes._format_runner_result(
            {"stdout": "42\n", "stderr": "", "exit_code": 0, "timed_out": False, "truncated": False}
        )

    monkeypatch.setattr(code_routes, "_run_in_sandbox", fake_run)
    response = test_client.post("/code/execute", json={"code": "print(6*7)", "language": "python"})
    assert response.status_code == 200, response.text
    assert response.json() == {"output": "42", "success": True, "error": None}
    assert sent == {"code": "print(6*7)", "language": "python"}


def test_execute_rejects_languages_runner_lacks(test_client, overrides, monkeypatch):
    from backend.config import config

    monkeypatch.setattr(config, "ENABLE_CODE_EXECUTION", True)
    monkeypatch.setattr(config, "CODE_RUNNER_URL", "http://runner:8080")
    response = test_client.post("/code/execute", json={"code": "int main(){}", "language": "cpp"})
    assert response.status_code == 400


@pytest.mark.parametrize(
    "result, success, expected",
    [
        ({"stdout": "", "stderr": "boom", "exit_code": 1}, False, "Error:\nboom"),
        ({"stdout": "", "stderr": "x.java:1: error", "exit_code": 1, "stage": "compile"}, False, "Compilation Error"),
        ({"stdout": "partial", "stderr": "", "exit_code": -9, "timed_out": True}, False, "10-second limit"),
        ({"stdout": "", "stderr": "", "exit_code": -9}, False, "CPU, memory or output limit"),
        ({"stdout": "x" * 10, "stderr": "", "exit_code": -9, "truncated": True}, False, "truncated at 64 KB"),
        ({"stdout": "", "stderr": "", "exit_code": 0}, True, "(no output)"),
    ],
)
def test_runner_result_formatting(result, success, expected):
    output, ok = code_routes._format_runner_result(result)
    assert ok is success
    assert expected in output
