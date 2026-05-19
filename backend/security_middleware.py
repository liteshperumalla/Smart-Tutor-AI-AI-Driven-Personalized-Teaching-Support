"""
Security Middleware for FastAPI
Provides additional security layers for API routes
"""

import ipaddress
import os
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Callable, Optional
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Timezone-aware UTC now (replaces deprecated datetime.utcnow())."""
    return datetime.now(timezone.utc)


def _parse_trusted_proxies() -> tuple:
    """Parse TRUSTED_PROXY_CIDRS env var into ip_network objects.

    Default to empty — XFF/X-Real-IP are ignored unless an operator explicitly
    declares the reverse proxies that send them. This prevents header spoofing
    by clients hitting the backend directly.
    """
    raw = os.getenv("TRUSTED_PROXY_CIDRS", "")
    networks = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            networks.append(ipaddress.ip_network(piece, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid TRUSTED_PROXY_CIDRS entry: %s", piece)
    return tuple(networks)


_TRUSTED_PROXY_NETWORKS = _parse_trusted_proxies()


def _client_ip_from_scope(scope) -> str:
    """Return the client IP, honoring proxy headers only when the TCP peer is
    a configured trusted proxy. Falls back to the raw TCP client IP otherwise.
    """
    tcp_client = (scope.get("client") or ("",))[0]
    if not _TRUSTED_PROXY_NETWORKS or not tcp_client:
        return tcp_client

    try:
        peer = ipaddress.ip_address(tcp_client)
    except ValueError:
        return tcp_client

    if not any(peer in net for net in _TRUSTED_PROXY_NETWORKS):
        return tcp_client

    # Peer is a known proxy — trust the leftmost forwarded entry.
    for header_name, header_value in scope.get("headers", []):
        if header_name == b"x-forwarded-for":
            forwarded = header_value.decode().split(",")[0].strip()
            if forwarded:
                return forwarded
        elif header_name == b"x-real-ip":
            forwarded = header_value.decode().strip()
            if forwarded:
                return forwarded
    return tcp_client


class SecurityHeadersMiddleware:
    """
    Add comprehensive security headers to all responses
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))

                # Add security headers
                security_headers = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"x-xss-protection", b"1; mode=block"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
                ]

                # Add headers if not already present
                existing_keys = {h[0].lower() for h in headers}
                for key, value in security_headers:
                    if key not in existing_keys:
                        headers.append((key, value))

                message["headers"] = headers

            await send(message)

        await self.app(scope, receive, send_wrapper)


class IPWhitelistMiddleware:
    """
    Optional IP whitelist for sensitive endpoints
    """

    def __init__(self, app, whitelist: list = None, protected_paths: list = None):
        self.app = app
        self.whitelist = set(whitelist or [])
        self.protected_paths = protected_paths or ["/admin", "/internal"]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Check if path is protected
        is_protected = any(path.startswith(p) for p in self.protected_paths)

        if is_protected and self.whitelist:
            client_ip = _client_ip_from_scope(scope)

            if client_ip not in self.whitelist:
                logger.warning(f"Blocked access to {path} from non-whitelisted IP: {client_ip}")

                # Send 403 Forbidden
                response = JSONResponse(
                    status_code=403,
                    content={"detail": "Access forbidden"}
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


class RequestSizeLimitMiddleware:
    """
    Limit request body size to prevent DoS attacks
    """

    def __init__(self, app, max_size: int = 10 * 1024 * 1024):  # 10MB default
        self.app = app
        self.max_size = max_size

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check Content-Length header
        content_length = 0
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"content-length":
                try:
                    content_length = int(header_value.decode())
                except ValueError:
                    pass
                break

        if content_length > self.max_size:
            logger.warning(f"Request body too large: {content_length} bytes (max: {self.max_size})")

            response = JSONResponse(
                status_code=413,
                content={"detail": f"Request body too large (max: {self.max_size} bytes)"}
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


class SlowRequestDetectionMiddleware:
    """
    Detect and log slow requests for performance monitoring
    """

    def __init__(self, app, threshold_seconds: float = 5.0):
        self.app = app
        self.threshold = threshold_seconds

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        path = scope.get("path", "")
        method = scope.get("method", "")

        await self.app(scope, receive, send)

        duration = time.time() - start_time

        if duration > self.threshold:
            logger.warning(
                f"Slow request detected: {method} {path} took {duration:.2f}s "
                f"(threshold: {self.threshold}s)"
            )


class SuspiciousActivityDetectionMiddleware:
    """
    Detect suspicious patterns in requests.

    State is per-instance (not class-level) so each app instance has independent
    counters; entries are evicted lazily on access and aggressively when the
    tracking maps grow past `max_tracked_ips` to bound memory.
    """

    def __init__(
        self,
        app,
        max_failures: int = 10,
        block_duration: int = 900,
        enabled: bool = True,
        max_tracked_ips: int = 10_000,
    ):
        self.app = app
        self.max_failures = max_failures
        self.block_duration = block_duration  # seconds (15 minutes default)
        self.enabled = enabled
        self.max_tracked_ips = max_tracked_ips
        # Per-instance, not class-level: avoid silent state sharing across apps.
        self._failed_attempts: defaultdict[str, list] = defaultdict(list)
        self._blocked_ips: dict[str, datetime] = {}

    def _evict_if_needed(self) -> None:
        """Hard cap on tracked IPs to prevent unbounded memory growth under attack."""
        if len(self._failed_attempts) > self.max_tracked_ips:
            now = _utcnow()
            cutoff = now - timedelta(seconds=self.block_duration)
            self._failed_attempts = defaultdict(
                list,
                {
                    ip: [t for t in times if t > cutoff]
                    for ip, times in self._failed_attempts.items()
                    if any(t > cutoff for t in times)
                },
            )
            # If still over the cap after pruning, drop oldest IPs.
            while len(self._failed_attempts) > self.max_tracked_ips:
                self._failed_attempts.pop(next(iter(self._failed_attempts)), None)
        if len(self._blocked_ips) > self.max_tracked_ips:
            now = _utcnow()
            self._blocked_ips = {
                ip: until for ip, until in self._blocked_ips.items() if until > now
            }

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return

        client_ip = _client_ip_from_scope(scope)

        # Check if IP is blocked
        if client_ip in self._blocked_ips:
            block_until = self._blocked_ips[client_ip]
            if _utcnow() < block_until:
                logger.warning(f"Blocked suspicious IP: {client_ip}")

                response = JSONResponse(
                    status_code=429,
                    content={"detail": "Too many failed attempts. Please try again later."}
                )
                await response(scope, receive, send)
                return
            else:
                # Unblock expired blocks
                del self._blocked_ips[client_ip]
                if client_ip in self._failed_attempts:
                    del self._failed_attempts[client_ip]

        # Track suspicious patterns in response
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)

                # Track 401/403 responses (authentication failures)
                path = scope.get("path", "")
                if status_code in [401, 403] and "/auth/" in path:
                    now = _utcnow()
                    self._failed_attempts[client_ip].append(now)

                    # Clean old attempts (older than block duration)
                    cutoff = now - timedelta(seconds=self.block_duration)
                    self._failed_attempts[client_ip] = [
                        t for t in self._failed_attempts[client_ip] if t > cutoff
                    ]

                    # Check if should block
                    if len(self._failed_attempts[client_ip]) >= self.max_failures:
                        block_until = now + timedelta(seconds=self.block_duration)
                        self._blocked_ips[client_ip] = block_until
                        logger.error(
                            f"Blocking IP {client_ip} due to {len(self._failed_attempts[client_ip])} "
                            f"failed authentication attempts. Blocked until {block_until}"
                        )

                    self._evict_if_needed()

            await send(message)

        await self.app(scope, receive, send_wrapper)


def add_security_middleware(app, config=None):
    """
    Add all security middleware to FastAPI app

    Args:
        app: FastAPI application instance
        config: Optional configuration dict
    """
    import os
    config = config or {}

    # Add request size limit (default 10MB)
    max_request_size = config.get("max_request_size", 10 * 1024 * 1024)
    app.add_middleware(RequestSizeLimitMiddleware, max_size=max_request_size)

    # Add slow request detection (default 5 seconds)
    slow_threshold = config.get("slow_request_threshold", 5.0)
    app.add_middleware(SlowRequestDetectionMiddleware, threshold_seconds=slow_threshold)

    # Add suspicious activity detection (disabled in test environment via RATE_LIMIT_ENABLED=false)
    ip_blocking_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"
    app.add_middleware(
        SuspiciousActivityDetectionMiddleware,
        max_failures=config.get("max_auth_failures", 10),
        block_duration=config.get("block_duration", 900),
        enabled=ip_blocking_enabled,
    )

    # Add IP whitelist if configured
    whitelist = config.get("ip_whitelist", [])
    protected_paths = config.get("protected_paths", ["/admin", "/internal"])
    if whitelist:
        app.add_middleware(IPWhitelistMiddleware, whitelist=whitelist, protected_paths=protected_paths)

    logger.info("Security middleware initialized")
