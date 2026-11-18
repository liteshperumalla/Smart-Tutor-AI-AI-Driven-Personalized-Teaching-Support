"""Research-mode sources (links, videos, files) are context for the chat answer."""

import pytest

from backend.api.dependencies import get_current_session, get_current_user, get_rate_limiter_dep
from backend.api.main import app
from backend.api.routes import chat as chat_routes
from backend.csrf_protection import csrf_protect
from backend.services.models import ChatSession

USER = {"username": "research-tester", "role": "Student"}


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

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class _FakeResearch:
    def __init__(self, chunks):
        self.chunks = chunks
        self.requested = None

    def get_chunks_by_file_ids(self, file_ids):
        self.requested = list(file_ids)
        return self.chunks


@pytest.fixture
def chat(monkeypatch):
    fake = _FakeChatService()
    research = _FakeResearch(
        [{"id": "c0", "text": "Transformers use self-attention.", "source_file": "Attention page", "chunk_index": 0}]
    )
    app.dependency_overrides[get_current_session] = lambda: ("token", USER)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[chat_routes.get_chat_service] = lambda: fake
    app.dependency_overrides[get_rate_limiter_dep] = lambda: _NoLimits()
    app.dependency_overrides[csrf_protect] = lambda: None
    monkeypatch.setattr(chat_routes, "get_research_service", lambda: research)
    yield fake, research
    app.dependency_overrides.clear()


def test_uploaded_sources_go_to_pipeline_as_context(test_client, chat):
    fake, research = chat
    response = test_client.post(
        "/chat/sessions/s1/messages",
        json={"query": "What does it use?", "uploaded_only": True, "uploaded_file_ids": ["url_ab12cd34"]},
    )
    assert response.status_code == 200, response.text
    assert research.requested == ["url_ab12cd34"]
    call = fake.calls[-1]
    # The question stays the question; the page's text is separate context.
    assert call["query"] == "What does it use?"
    assert call["uploaded_context"][0]["text"] == "Transformers use self-attention."


def test_no_uploaded_context_without_research_sources(test_client, chat):
    fake, _ = chat
    assert test_client.post("/chat/sessions/s1/messages", json={"query": "hi there"}).status_code == 200
    assert fake.calls[-1]["uploaded_context"] is None


def test_select_uploaded_context_keeps_short_sources_whole():
    chunks = [{"text": f"part {i}", "source_file": "a"} for i in range(3)] + [{"text": "  "}]
    assert [c["text"] for c in chat_routes.select_uploaded_context(chunks, "q")] == ["part 0", "part 1", "part 2"]


def test_select_uploaded_context_ranks_long_sources_by_question():
    chunks = [{"text": f"filler text number {i}", "source_file": "page", "chunk_index": i} for i in range(30)]
    chunks[20]["text"] = "gradient descent minimises the loss"
    picked = chat_routes.select_uploaded_context(chunks, "how does gradient descent work", limit=3)
    assert len(picked) == 3
    assert picked[0] is chunks[0]  # the source's intro is kept
    assert chunks[20] in picked
    # Document order is preserved.
    assert [c["chunk_index"] for c in picked] == sorted(c["chunk_index"] for c in picked)


def test_chat_service_passes_uploaded_context_to_rag(monkeypatch):
    from backend.services import chat_service as svc
    from backend import posthog_tracker

    seen = {}

    def fake_generate(query, **kwargs):
        seen.update(kwargs)
        return iter([]), []

    monkeypatch.setattr(svc, "generate_response_stream_and_sources", fake_generate)
    monkeypatch.setattr(posthog_tracker, "feature_enabled", lambda *a, **k: False)
    ctx = [{"text": "x"}]
    svc.ChatService().stream_response("q", user_id="u", uploaded_context=ctx)
    assert seen["uploaded_context"] is ctx


def test_chat_service_passes_uploaded_context_to_agents(monkeypatch):
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
    ctx = [{"text": "x"}]
    svc.ChatService().stream_response("q", user_id="u", uploaded_context=ctx)
    assert seen["uploaded_context"] is ctx


def test_agent_context_uses_uploaded_sources_when_course_has_nothing():
    from backend.agents import NO_COURSE_MATERIAL, _merge_uploaded_context

    ctx, sources = _merge_uploaded_context(
        [{"text": "Self-attention weighs tokens.", "source_file": "Attention page"}], NO_COURSE_MATERIAL, []
    )
    assert NO_COURSE_MATERIAL not in ctx
    assert "[Uploaded source 1: Attention page]" in ctx
    assert sources[0]["file_name"] == "Attention page" and sources[0]["is_uploaded"]


def test_agent_context_puts_uploaded_sources_before_course_material():
    from backend.agents import _merge_uploaded_context

    course = [{"file_name": "lecture.pdf"}]
    ctx, sources = _merge_uploaded_context([{"text": "mine", "source_file": "notes"}], "[Source 1: lecture.pdf]\ncourse", course)
    assert ctx.index("mine") < ctx.index("course")
    assert [s["file_name"] for s in sources] == ["notes", "lecture.pdf"]


def test_rag_nodes_from_uploaded_context():
    import utils

    nodes = utils._uploaded_context_nodes([{"id": "c1", "text": "hello", "source_file": "page"}, {"text": ""}])
    assert len(nodes) == 1
    assert nodes[0].node.get_text() == "hello"
    assert nodes[0].node.metadata["is_uploaded"] is True


# ── Fetching a link ──────────────────────────────────────────────────────


class _Resp:
    def __init__(self, status, location=None, content=b""):
        self.status_code = status
        self.headers = {"Location": location} if location else {}
        self.is_redirect = status in (301, 302, 303, 307, 308) and bool(location)
        self.content = content


def test_fetch_follows_redirects_and_checks_each_hop(monkeypatch):
    from backend.services import research_service as rs

    checked, fetched = [], []
    monkeypatch.setattr(rs, "_validate_url_not_internal", checked.append)
    replies = iter([_Resp(301, "https://example.com/page/"), _Resp(200, content=b"<p>hi</p>")])

    def fake_get(url, **kwargs):
        fetched.append(url)
        assert kwargs["allow_redirects"] is False
        return next(replies)

    monkeypatch.setattr(rs.requests, "get", fake_get)
    response = rs._fetch_public_url("http://example.com/page", headers={})
    assert response.status_code == 200
    assert fetched == ["http://example.com/page", "https://example.com/page/"]
    assert checked == fetched


def test_fetch_refuses_redirect_to_internal_address(monkeypatch):
    from backend.services import research_service as rs

    def validate(url):
        if "169.254" in url:
            raise ValueError("URL resolves to a non-public address")

    monkeypatch.setattr(rs, "_validate_url_not_internal", validate)
    monkeypatch.setattr(rs.requests, "get", lambda url, **kw: _Resp(302, "http://169.254.169.254/latest/meta-data"))
    with pytest.raises(ValueError, match="non-public"):
        rs._fetch_public_url("https://example.com", headers={})


def test_fetch_http_error_is_a_readable_value_error(monkeypatch):
    from backend.services import research_service as rs

    monkeypatch.setattr(rs, "_validate_url_not_internal", lambda url: None)
    monkeypatch.setattr(rs.requests, "get", lambda url, **kw: _Resp(403))
    with pytest.raises(ValueError, match="HTTP 403"):
        rs._fetch_public_url("https://example.com", headers={})


def test_preview_url_returns_id_for_chat(monkeypatch):
    from backend.services import research_service as rs

    monkeypatch.setattr(rs, "_validate_url_not_internal", lambda url: None)
    monkeypatch.setattr(
        rs.requests, "get",
        lambda url, **kw: _Resp(200, content=b"<html><title>Attention</title><body><p>Self-attention.</p></body></html>"),
    )

    class _S3:
        def put_object(self, **kwargs):
            pass

    monkeypatch.setattr(rs, "S3Retriever", lambda **kw: None)
    svc = rs.ResearchService()
    svc._s3_uploads = _S3()
    svc._uploads_bucket = "b"
    monkeypatch.setattr(rs.ResearchService, "_ensure_bucket_exists", lambda self: None)
    preview = svc.preview_url("https://example.com/a")
    assert preview["id"].startswith("url_")
    assert preview["file_name"] == "Attention"
