from fastapi import Depends, Header, HTTPException, Query, Request, status

from backend.auth_service import get_auth_service, AuthService
from backend.rate_limiter import get_rate_limiter, PerUserRateLimiter
from backend.config import config


def get_auth_service_dep() -> AuthService:
    return get_auth_service()


def get_rate_limiter_dep() -> PerUserRateLimiter:
    return get_rate_limiter()


def _resolve_token(
    request: Request,
    authorization: str | None,
) -> str:
    """
    Resolve authentication token with priority:
    1. HttpOnly cookie (most secure)
    2. Authorization header (for backward compatibility)

    SECURITY: Query string tokens are NO LONGER SUPPORTED.
    """
    # SECURITY: First, try to get token from HttpOnly cookie
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token.strip()

    # Fallback to Authorization header for backward compatibility
    if authorization:
        if not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header",
            )
        return authorization.split(" ", 1)[1].strip()

    # SECURITY: Query string tokens are NOT accepted (removed for security)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authorization token. Please login again.",
    )


async def get_current_session(
    request: Request,
    authorization: str | None = Header(None, alias="Authorization"),
    auth_service: AuthService = Depends(get_auth_service_dep),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """
    Extract session token with priority:
    1. HttpOnly cookie (most secure)
    2. Authorization header (backward compatibility)

    Validates token, checks per-user rate limits, and returns (token, user_dict).

    SECURITY: Query string tokens are NO LONGER SUPPORTED.
    """
    # Check per-user rate limit BEFORE authentication
    # This uses JWT token to identify user without full validation
    await rate_limiter.check_rate_limit(request)

    # SECURITY: Get token from cookie or header (no query string)
    token = _resolve_token(request, authorization)
    try:
        user = auth_service.validate_session(token)
        return token, user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )


async def get_current_user(session=Depends(get_current_session)):
    _, user = session
    return user


async def get_admin_session(session=Depends(get_current_session)):
    """Require the authenticated user to have Admin role or is_admin flag."""
    token, user = session
    # Check role or is_admin flag in metadata
    is_admin = user.get("role") == "Admin" or user.get("metadata", {}).get("is_admin", False)
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return token, user


async def get_evaluation_cron_token(
    x_evaluation_token: str | None = Header(None, alias="X-Evaluation-Token"),
    authorization: str | None = Header(None, alias="Authorization"),
):
    """
    Validate a static evaluation token for scheduled CI runs.
    Accepts either X-Evaluation-Token or Authorization: Bearer <token>.
    """
    expected = config.EVALUATION_CRON_TOKEN
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Evaluation cron token is not configured",
        )

    token = None
    if x_evaluation_token:
        token = x_evaluation_token.strip()
    elif authorization:
        if not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header",
            )
        token = authorization.split(" ", 1)[1].strip()

    if not token or token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid evaluation token",
        )

    return token
