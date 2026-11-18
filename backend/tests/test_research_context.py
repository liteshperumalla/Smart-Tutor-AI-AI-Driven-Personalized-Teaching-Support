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

    fetched = []
    replies = iter([_Resp(301, "https://example.com/page/"), _Resp(200, content=b"<p>hi</p>")])

    def fake_pinned_get(url, headers, timeout):
        fetched.append(url)
        return next(replies)

    monkeypatch.setattr(rs, "_pinned_get", fake_pinned_get)
    response = rs._fetch_public_url("http://example.com/page", headers={})
    assert response.status_code == 200
    # Every hop goes through the validating, pinned fetch.
    assert fetched == ["http://example.com/page", "https://example.com/page/"]


def test_fetch_refuses_redirect_to_internal_address(monkeypatch):
    from backend.services import research_service as rs

    def fake_resolve(url):
        if "169.254" in url:
            raise ValueError("URL resolves to a non-public address")
        return "https", "example.com", "93.184.216.34", None

    monkeypatch.setattr(rs, "_resolve_public_address", fake_resolve)
    monkeypatch.setattr(
        rs.requests.Session, "get", lambda self, url, **kw: _Resp(302, "http://169.254.169.254/latest/meta-data")
    )
    with pytest.raises(ValueError, match="non-public"):
        rs._fetch_public_url("https://example.com", headers={})


def test_fetch_http_error_is_a_readable_value_error(monkeypatch):
    from backend.services import research_service as rs

    monkeypatch.setattr(rs, "_pinned_get", lambda url, headers, timeout: _Resp(403))
    with pytest.raises(ValueError, match="HTTP 403"):
        rs._fetch_public_url("https://example.com", headers={})


@pytest.mark.parametrize(
    "addresses",
    [["10.0.0.5"], ["127.0.0.1"], ["169.254.169.254"], ["93.184.216.34", "192.168.1.1"], ["::1"]],
)
def test_resolve_rejects_any_non_public_address(monkeypatch, addresses):
    from backend.services import research_service as rs

    monkeypatch.setattr(
        rs.socket, "getaddrinfo", lambda host, port: [(0, 0, 0, "", (a, port)) for a in addresses]
    )
    with pytest.raises(ValueError, match="non-public"):
        rs._resolve_public_address("https://rebind.example/")


def test_resolve_rejects_other_schemes():
    from backend.services import research_service as rs

    with pytest.raises(ValueError, match="scheme"):
        rs._resolve_public_address("file:///etc/passwd")


def _serve(handler_cls, tls_context=None):
    import http.server
    import threading

    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    if tls_context is not None:
        server.socket = tls_context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _recording_handler(seen):
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append({"host": self.headers.get("Host"), "path": self.path})
            body = b"<html><title>ok</title><p>pinned</p></html>"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    return Handler


def test_pinned_get_connects_to_the_validated_ip(monkeypatch):
    """The request goes to the IP that was checked, not to a fresh lookup,
    and the site still sees its own hostname."""
    from backend.services import research_service as rs

    seen = []
    server = _serve(_recording_handler(seen))
    port = server.server_address[1]
    try:
        # The checked address; a second DNS lookup must not happen.
        monkeypatch.setattr(rs, "_resolve_public_address", lambda url: ("http", "site.example", "127.0.0.1", port))
        real_getaddrinfo = rs.socket.getaddrinfo

        def no_second_lookup(host, *args, **kwargs):
            assert host != "site.example", "hostname resolved again at connect time"
            return real_getaddrinfo(host, *args, **kwargs)

        monkeypatch.setattr(rs.socket, "getaddrinfo", no_second_lookup)
        response = rs._pinned_get(f"http://site.example:{port}/a/b?q=1", headers={}, timeout=5)
    finally:
        server.shutdown()
    assert response.status_code == 200
    assert seen == [{"host": f"site.example:{port}", "path": "/a/b?q=1"}]


def test_pinned_https_checks_the_certificate_against_the_hostname(monkeypatch, tmp_path):
    """Over HTTPS the pinned connection still verifies the site's
    certificate for its hostname, and refuses a certificate for another."""
    import datetime
    import ssl

    import requests
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    from backend.services import research_service as rs

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "site.example")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("site.example")]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_file = tmp_path / "cert.pem"
    key_file = tmp_path / "key.pem"
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_file, key_file)

    seen = []
    server = _serve(_recording_handler(seen), tls_context=context)
    port = server.server_address[1]
    # Trust the test certificate as the CA bundle for these sessions.
    original_init = requests.Session.__init__

    def init_with_test_ca(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.verify = str(cert_file)

    monkeypatch.setattr(requests.Session, "__init__", init_with_test_ca)
    try:
        monkeypatch.setattr(rs, "_resolve_public_address", lambda url: ("https", "site.example", "127.0.0.1", port))
        response = rs._pinned_get(f"https://site.example:{port}/", headers={}, timeout=5)
        assert response.status_code == 200
        assert seen[-1]["host"] == f"site.example:{port}"

        # Same server, but the link names another host: the certificate
        # doesn't match, so the request fails.
        monkeypatch.setattr(rs, "_resolve_public_address", lambda url: ("https", "other.example", "127.0.0.1", port))
        with pytest.raises(requests.exceptions.SSLError):
            rs._pinned_get(f"https://other.example:{port}/", headers={}, timeout=5)
    finally:
        server.shutdown()


def test_preview_url_returns_id_for_chat(monkeypatch):
    from backend.services import research_service as rs

    monkeypatch.setattr(rs, "_validate_url_not_internal", lambda url: None)
    monkeypatch.setattr(
        rs, "_pinned_get",
        lambda url, headers, timeout: _Resp(200, content=b"<html><title>Attention</title><body><p>Self-attention.</p></body></html>"),
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


# ── End to end: every kind of research source reaches the chat ──────────


class _MemoryS3:
    """Just enough of the S3 client for the research uploads."""

    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.objects[Key] = Body if isinstance(Body, bytes) else str(Body).encode()

    def get_object(self, Bucket, Key):
        import io

        if Key not in self.objects:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def upload_fileobj(self, fileobj, Bucket, Key, **kwargs):
        self.objects[Key] = fileobj.read()

    def get_paginator(self, name):
        store = self

        class _Paginator:
            def paginate(self, Bucket, Prefix):
                yield {"Contents": [{"Key": k} for k in sorted(store.objects) if k.startswith(Prefix)]}

        return _Paginator()


@pytest.fixture
def research_store(monkeypatch):
    from backend.services import research_service as rs

    s3 = _MemoryS3()
    monkeypatch.setattr(rs, "S3Retriever", lambda **kw: None)
    monkeypatch.setattr(rs, "get_boto3_client", lambda name: s3)
    monkeypatch.setattr(rs.ResearchService, "_ensure_bucket_exists", lambda self: None)
    service = rs.ResearchService()
    service._s3_uploads = s3
    service._uploads_bucket = "bucket"
    return service


def test_every_source_kind_comes_back_as_chat_context(research_store, monkeypatch):
    from backend.services import research_service as rs

    svc = research_store
    # A text file.
    file_preview = svc.preview_file(b"Backpropagation computes gradients layer by layer.", "notes.txt")
    # A web page.
    monkeypatch.setattr(rs, "_validate_url_not_internal", lambda url: None)
    monkeypatch.setattr(
        rs, "_pinned_get",
        lambda url, headers, timeout: _Resp(200, content=b"<html><title>Attention Paper</title><p>Self-attention relates tokens.</p></html>"),
    )
    url_preview = svc.preview_url("https://example.com/attention")
    # A YouTube video.
    monkeypatch.setattr(rs.ResearchService, "_fetch_youtube_transcript", lambda self, vid: [{"text": "Gradient descent"}, {"text": "minimises loss."}])
    monkeypatch.setattr(rs.ResearchService, "_youtube_title", lambda self, vid: "Intro to Optimisation")
    yt_preview = svc.preview_youtube("https://youtube.com/shorts/dQw4w9WgXcQ")

    ids = [file_preview["id"], url_preview["id"], yt_preview["id"]]
    assert all(ids)
    chunks = svc.get_chunks_by_file_ids(ids)
    by_source = {c["source_file"]: c["text"] for c in chunks}
    # Each source comes back under a readable name with its text.
    assert "Backpropagation" in by_source["notes.txt"]
    assert "Self-attention" in by_source["Attention Paper"]
    assert "Gradient descent minimises loss." in by_source["Intro to Optimisation"]


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?t=10",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
    ],
)
def test_youtube_link_formats(research_store, url):
    assert research_store._extract_video_id(url) == "dQw4w9WgXcQ"


def test_youtube_falls_back_to_another_language(research_store, monkeypatch):
    from backend.services import research_service as rs

    class _Transcript:
        def fetch(self):
            return [{"text": "Hola"}]

    class _Api:
        def __init__(self, proxy_config=None):
            pass

        def fetch(self, video_id, languages):
            raise rs.NoTranscriptFound(video_id, languages, [])

        def list(self, video_id):
            return [_Transcript()]

    monkeypatch.setattr(rs, "YouTubeTranscriptApi", _Api)
    assert research_store._fetch_youtube_transcript("dQw4w9WgXcQ") == [{"text": "Hola"}]


def test_youtube_blocked_gives_an_actionable_message(research_store, monkeypatch):
    from backend.services import research_service as rs

    class _Api:
        def __init__(self, proxy_config=None):
            pass

        def fetch(self, video_id, languages):
            raise rs.RequestBlocked(video_id)

    monkeypatch.setattr(rs, "YouTubeTranscriptApi", _Api)
    with pytest.raises(ValueError, match="blocking transcript requests"):
        research_store._fetch_youtube_transcript("dQw4w9WgXcQ")
