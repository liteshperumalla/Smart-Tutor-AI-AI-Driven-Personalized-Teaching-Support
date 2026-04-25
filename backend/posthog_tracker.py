"""
PostHog event tracking helper.

Thin wrapper around the PostHog Python SDK so routes never import
posthog directly.  All calls are best-effort — exceptions are logged
as warnings and never propagated to callers.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlparse

from backend.logger import get_logger

logger = get_logger(__name__)

_initialized = False


def _init() -> bool:
    global _initialized
    if _initialized:
        return True
    try:
        from backend.config import Config
        if not (Config.POSTHOG_ENABLED and Config.POSTHOG_API_KEY):
            return False
        import posthog
        posthog.api_key = Config.POSTHOG_API_KEY
        posthog.host = Config.POSTHOG_HOST
        _initialized = True
        return True
    except Exception as exc:
        logger.warning("PostHog init failed: %s", exc)
        return False


def get_posthog_health() -> Dict[str, Any]:
    """Return a lightweight PostHog health snapshot for admin/health endpoints."""
    try:
        from backend.config import Config

        if not Config.POSTHOG_ENABLED:
            return {"status": "disabled", "message": "POSTHOG_ENABLED=false"}

        if not Config.POSTHOG_API_KEY:
            return {"status": "misconfigured", "message": "API key missing"}

        parsed_host = urlparse(Config.POSTHOG_HOST)
        if not parsed_host.scheme or not parsed_host.netloc:
            return {
                "status": "misconfigured",
                "message": "POSTHOG_HOST must be a valid absolute URL",
            }

        try:
            import posthog  # noqa: F401
        except ImportError:
            return {
                "status": "unhealthy",
                "message": "PostHog SDK not installed. Install with: pip install posthog",
            }

        if not _init():
            return {
                "status": "unhealthy",
                "message": "PostHog SDK initialization failed",
                "host": Config.POSTHOG_HOST,
            }

        return {
            "status": "healthy",
            "host": Config.POSTHOG_HOST,
            "sdk_initialized": True,
        }
    except Exception as exc:
        logger.warning("PostHog health check failed: %s", exc)
        return {"status": "unhealthy", "message": str(exc)}


def capture(
    distinct_id: str,
    event: str,
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    """Fire-and-forget PostHog event capture."""
    try:
        if not _init():
            return
        import posthog
        posthog.capture(
            distinct_id=distinct_id or "anonymous",
            event=event,
            properties=properties or {},
        )
    except Exception as exc:
        logger.warning("PostHog capture(%s) failed: %s", event, exc)


def feature_enabled(
    distinct_id: str,
    flag_name: str,
    default: bool = False,
) -> bool:
    """
    Check a PostHog boolean feature flag for a specific user.

    Falls back to `default` when PostHog is disabled, the flag doesn't
    exist, or any network/SDK error occurs — ensuring the caller always
    gets a usable boolean without try/except boilerplate.

    Usage:
        use_agents = feature_enabled(user_id, "agent-system-enabled",
                                     default=config.AGENT_SYSTEM_ENABLED)
    """
    try:
        if not _init():
            return default
        import posthog
        result = posthog.feature_enabled(flag_name, distinct_id or "anonymous")
        return bool(result) if result is not None else default
    except Exception as exc:
        logger.warning("PostHog feature_enabled(%s) failed: %s", flag_name, exc)
        return default


def get_flag_payload(
    distinct_id: str,
    flag_name: str,
    default: Optional[Any] = None,
) -> Optional[Any]:
    """
    Return the payload/variant of a multivariate PostHog feature flag.

    Useful when a flag carries a value (e.g. model name, threshold) rather
    than just on/off.  Returns `default` on any failure.
    """
    try:
        if not _init():
            return default
        import posthog
        payload = posthog.get_feature_flag_payload(flag_name, distinct_id or "anonymous")
        return payload if payload is not None else default
    except Exception as exc:
        logger.warning("PostHog get_flag_payload(%s) failed: %s", flag_name, exc)
        return default
