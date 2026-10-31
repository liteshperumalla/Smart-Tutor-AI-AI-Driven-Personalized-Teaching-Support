"""Request bodies are capped as they stream in, not only by Content-Length."""

import io

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.testclient import TestClient

from backend.config import config
from backend.security_middleware import RequestSizeLimitMiddleware


def _app(max_size: int) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestSizeLimitMiddleware, max_size=max_size)

    @app.post("/raw")
    async def raw(request: Request):
        return {"size": len(await request.body())}

    @app.post("/form")
    async def form(file: UploadFile = File(...)):
        return {"size": len(await file.read())}

    return app


def _chunks(total: int, size: int = 256):
    sent = 0
    while sent < total:
        n = min(size, total - sent)
        sent += n
        yield b"x" * n


def test_chunked_body_without_content_length_is_cut_off():
    client = TestClient(_app(max_size=1024))

    response = client.post("/raw", content=_chunks(4096))

    assert response.status_code == 413


def test_multipart_upload_over_limit_is_rejected():
    client = TestClient(_app(max_size=1024))

    response = client.post("/form", files={"file": ("a.txt", io.BytesIO(b"x" * 4096), "text/plain")})

    assert response.status_code == 413


def test_body_within_limit_passes():
    client = TestClient(_app(max_size=1024))

    response = client.post("/raw", content=_chunks(512))

    assert response.status_code == 200
    assert response.json() == {"size": 512}


def test_chat_upload_over_limit_is_rejected(test_client, auth_headers, monkeypatch):
    monkeypatch.setattr(config, "MAX_UPLOAD_SIZE", 1024)
    files = {"file": ("big.pdf", io.BytesIO(b"%PDF-1.4\n" + b"x" * 4096), "application/pdf")}

    response = test_client.post("/chat/uploads", headers=auth_headers, files=files)

    assert response.status_code == 413
