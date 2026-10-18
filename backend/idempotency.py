"""
Idempotency Middleware and Cache Layer
Provides HTTP Idempotency-Key support to prevent duplicate mutations on client retries
"""

import hashlib
import json
import logging
import re
import time
from typing import Any, Dict, Optional, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_409_CONFLICT

from backend.config import config
from backend.redis_cache import get_cache

logger = logging.getLogger(__name__)

# Allowed characters in Idempotency-Key: alphanumeric, hyphen, underscore
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_\-\.:]{1,128}$")
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Do not buffer real-time streaming responses in the idempotency response cache
STREAMING_MEDIA_TYPES = {"application/x-ndjson", "text/event-stream"}
DEFAULT_IDEMPOTENCY_TTL = 86400  # 24 hours
DEFAULT_LOCK_TTL = 60            # 60 seconds for in-flight processing


class IdempotencyStore:
    """Manages idempotency locks and cached responses via Redis or in-memory LRU"""

    def __init__(self, cache=None):
        if cache is not None:
            self._cache = cache
        else:
            try:
                self._cache = get_cache()
            except Exception as exc:
                logger.warning("Primary cache unavailable for IdempotencyStore (%s), falling back to in-memory LRU", exc)
                from backend.cache import get_cache_manager
                self._cache = get_cache_manager().get_cache("idempotency")

    def _lock_key(self, key: str) -> str:
        return f"idemp:lock:{key}"

    def _data_key(self, key: str) -> str:
        return f"idemp:data:{key}"

    def acquire_lock(self, key: str, ttl: int = DEFAULT_LOCK_TTL) -> bool:
        """
        Attempt to acquire an atomic lock for a given idempotency key.
        Returns True if acquired (request is new), False if already in-progress.
        """
        lock_key = self._lock_key(key)
        try:
            # If underlying cache has a redis client with set(..., nx=True)
            if hasattr(self._cache, "client") and hasattr(self._cache.client, "set"):
                acquired = self._cache.client.set(lock_key, "in_progress", nx=True, ex=ttl)
                return bool(acquired)
            # Fallback to general cache interface
            existing = self._cache.get(lock_key)
            if existing is not None:
                return False
            self._cache.set(lock_key, "in_progress", ttl=ttl)
            return True
        except Exception as exc:
            logger.warning("Idempotency lock acquisition error (%s), switching to in-memory fallback", exc)
            try:
                from backend.cache import get_cache_manager
                self._cache = get_cache_manager().get_cache("idempotency_fallback")
                existing = self._cache.get(lock_key)
                if existing is not None:
                    return False
                self._cache.set(lock_key, "in_progress", ttl=ttl)
                return True
            except Exception:
                return True

    def release_lock(self, key: str) -> None:
        """Release lock when a request fails with an unhandled error or 5xx"""
        lock_key = self._lock_key(key)
        try:
            if hasattr(self._cache, "delete"):
                self._cache.delete(lock_key)
            elif hasattr(self._cache, "client") and hasattr(self._cache.client, "delete"):
                self._cache.client.delete(lock_key)
        except Exception as exc:
            logger.warning("Failed to release idempotency lock for key %s: %s", key, exc)

    def get_response(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve previously cached response for an idempotency key"""
        data_key = self._data_key(key)
        try:
            raw = self._cache.get(data_key)
            if raw is None:
                return None
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")
            if isinstance(raw, str):
                return json.loads(raw)
            if isinstance(raw, dict):
                return raw
            return None
        except Exception as exc:
            logger.warning("Failed to read cached idempotency response for key %s: %s", key, exc)
            return None

    def save_response(
        self,
        key: str,
        status_code: int,
        headers: Dict[str, str],
        body: bytes,
        media_type: Optional[str] = None,
        ttl: int = DEFAULT_IDEMPOTENCY_TTL,
    ) -> None:
        """Store completed response and release in-progress lock"""
        data_key = self._data_key(key)
        payload = {
            "status_code": status_code,
            "headers": headers,
            "body": body.decode("latin1"),  # preserve binary/utf-8 safely
            "media_type": media_type,
            "saved_at": time.time(),
        }
        try:
            serialized = json.dumps(payload)
            self._cache.set(data_key, serialized, ttl=ttl)
        except Exception as exc:
            logger.warning("Failed to cache idempotency response for key %s: %s", key, exc)
        finally:
            self.release_lock(key)


_store: Optional[IdempotencyStore] = None


def get_idempotency_store() -> IdempotencyStore:
    global _store
    if _store is None:
        _store = IdempotencyStore()
    return _store


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces idempotency for mutating HTTP requests.

    When the client includes an `Idempotency-Key` or `X-Idempotency-Key` header:
    - If previously completed: returns cached response with `X-Idempotent-Replayed: true`.
    - If currently in flight: returns `409 Conflict` advising caller to wait.
    - If new: executes the handler, caches successful results, and returns response.
    """

    def __init__(self, app, store: Optional[IdempotencyStore] = None):
        super().__init__(app)
        self.store = store or get_idempotency_store()

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        # Check for Idempotency-Key or X-Idempotency-Key header
        raw_key = request.headers.get("idempotency-key") or request.headers.get("x-idempotency-key")
        if not raw_key:
            return await call_next(request)

        key_value = raw_key.strip()
        if not IDEMPOTENCY_KEY_PATTERN.match(key_value):
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={
                    "detail": "Invalid Idempotency-Key format. Must be 1-128 characters containing alphanumeric, hyphen, underscore, colon, or dot."
                },
            )

        # Scope key by caller to prevent cross-tenant/cross-user collisions
        caller_id = (
            request.cookies.get("access_token")
            or request.headers.get("authorization")
            or request.client.host
            if request.client
            else "anonymous"
        )
        caller_hash = hashlib.sha256(caller_id.encode("utf-8")).hexdigest()[:16]
        composite_key = f"{caller_hash}:{request.method}:{request.url.path}:{key_value}"

        # 1. Check if a completed response is already cached
        cached = self.store.get_response(composite_key)
        if cached:
            logger.info("Serving idempotent cached response for key: %s", key_value)
            body_bytes = cached["body"].encode("latin1")
            response_headers = dict(cached.get("headers", {}))
            response_headers["X-Idempotent-Replayed"] = "true"
            response_headers["X-Idempotency-Key"] = key_value
            # Remove transport-specific headers from cache
            response_headers.pop("content-length", None)

            return Response(
                content=body_bytes,
                status_code=cached["status_code"],
                headers=response_headers,
                media_type=cached.get("media_type") or "application/json",
            )

        # 2. Acquire in-flight lock to guard against concurrent duplicates
        if not self.store.acquire_lock(composite_key):
            logger.warning("Concurrent duplicate request detected for idempotency key: %s", key_value)
            return JSONResponse(
                status_code=HTTP_409_CONFLICT,
                content={
                    "detail": "A request with this idempotency key is currently being processed. Please retry shortly.",
                    "retry_after": 2,
                },
                headers={"Retry-After": "2", "X-Idempotency-Key": key_value},
            )

        # 3. Execute downstream handlers
        try:
            response = await call_next(request)
        except Exception:
            self.store.release_lock(composite_key)
            raise

        # If server returned 5xx, release lock so client can retry
        if response.status_code >= 500:
            self.store.release_lock(composite_key)
            response.headers["X-Idempotency-Key"] = key_value
            return response

        # If response is a streaming response, do not buffer it in memory
        media_type = response.media_type or ""
        if media_type in STREAMING_MEDIA_TYPES:
            self.store.release_lock(composite_key)
            response.headers["X-Idempotency-Key"] = key_value
            return response

        # 4. Read body chunks and store in idempotency cache
        body_chunks = []
        async for chunk in response.body_iterator:
            body_chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8"))
        full_body = b"".join(body_chunks)

        # Strip unneeded headers before caching
        safe_headers = {}
        for h_key, h_val in response.headers.items():
            if h_key.lower() not in {"content-length", "set-cookie", "date"}:
                safe_headers[h_key] = h_val

        self.store.save_response(
            key=composite_key,
            status_code=response.status_code,
            headers=safe_headers,
            body=full_body,
            media_type=response.media_type,
        )

        response.headers["X-Idempotency-Key"] = key_value
        return Response(
            content=full_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
