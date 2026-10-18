"""
Tests for Idempotency Middleware and Store
"""

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from starlette.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_409_CONFLICT, HTTP_500_INTERNAL_SERVER_ERROR

from backend.idempotency import IdempotencyMiddleware, IdempotencyStore


class MemoryTestCache:
    """Mock cache for testing idempotency store"""
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, ttl=None):
        self.data[key] = value

    def delete(self, key):
        self.data.pop(key, None)


@pytest.fixture
def test_app():
    app = FastAPI()
    mock_store = IdempotencyStore(cache=MemoryTestCache())

    app.add_middleware(IdempotencyMiddleware, store=mock_store)

    call_count = {"count": 0}

    @app.post("/test/mutate")
    async def mutate_endpoint():
        call_count["count"] += 1
        return {"action": "created", "call_count": call_count["count"]}

    @app.post("/test/error")
    async def error_endpoint():
        raise RuntimeError("Internal explosion")

    @app.get("/test/read")
    async def read_endpoint():
        return {"read": True}

    return app, mock_store, call_count


def test_idempotency_ignores_get_requests(test_app):
    app, store, call_count = test_app
    client = TestClient(app)

    res = client.get("/test/read", headers={"Idempotency-Key": "test-key-1"})
    assert res.status_code == HTTP_200_OK
    assert "X-Idempotent-Replayed" not in res.headers


def test_idempotency_passes_through_without_header(test_app):
    app, store, call_count = test_app
    client = TestClient(app)

    res1 = client.post("/test/mutate")
    res2 = client.post("/test/mutate")
    assert res1.json()["call_count"] == 1
    assert res2.json()["call_count"] == 2


def test_idempotency_rejects_invalid_key_format(test_app):
    app, store, call_count = test_app
    client = TestClient(app)

    # Contains spaces or illegal chars
    res = client.post("/test/mutate", headers={"Idempotency-Key": "invalid key with spaces!"})
    assert res.status_code == HTTP_400_BAD_REQUEST
    assert "Invalid Idempotency-Key" in res.json()["detail"]


def test_idempotency_replays_cached_response(test_app):
    app, store, call_count = test_app
    client = TestClient(app)

    key = "idem-req-123"
    # First execution
    res1 = client.post("/test/mutate", headers={"Idempotency-Key": key})
    assert res1.status_code == HTTP_200_OK
    assert res1.json()["call_count"] == 1
    assert "X-Idempotent-Replayed" not in res1.headers
    assert res1.headers["X-Idempotency-Key"] == key

    # Second execution with same key — should replay cached result
    res2 = client.post("/test/mutate", headers={"Idempotency-Key": key})
    assert res2.status_code == HTTP_200_OK
    assert res2.json()["call_count"] == 1  # handler not called again
    assert res2.headers["X-Idempotent-Replayed"] == "true"
    assert res2.headers["X-Idempotency-Key"] == key


def test_idempotency_detects_concurrent_in_progress(test_app):
    import hashlib
    app, store, call_count = test_app
    client = TestClient(app)

    key = "idem-concurrent-1"
    auth_header = "Bearer user_token_123"
    caller_hash = hashlib.sha256(auth_header.encode("utf-8")).hexdigest()[:16]
    composite_key = f"{caller_hash}:POST:/test/mutate:{key}"
    store._cache.set(store._lock_key(composite_key), "in_progress")

    res = client.post("/test/mutate", headers={"Idempotency-Key": key, "Authorization": auth_header})
    assert res.status_code == HTTP_409_CONFLICT
    assert "currently being processed" in res.json()["detail"]


def test_idempotency_releases_lock_on_error(test_app):
    import hashlib
    app, store, call_count = test_app
    client = TestClient(app, raise_server_exceptions=False)

    key = "idem-error-key"
    auth_header = "Bearer error_test_user"
    res = client.post("/test/error", headers={"Idempotency-Key": key, "Authorization": auth_header})
    assert res.status_code == HTTP_500_INTERNAL_SERVER_ERROR

    # Verify lock was released so client can retry
    caller_hash = hashlib.sha256(auth_header.encode("utf-8")).hexdigest()[:16]
    composite_key = f"{caller_hash}:POST:/test/error:{key}"
    assert store._cache.get(store._lock_key(composite_key)) is None
