from fastapi import Depends, Header, HTTPException, Query, Request, status

from backend.auth_service import get_auth_service, AuthService
from backend.rate_limiter import get_rate_limiter, PerUserRateLimiter


def get_auth_service_dep() -> AuthService:
    return get_auth_service()


def get_rate_limiter_dep() -> PerUserRateLimiter:
    return get_rate_limiter()


def _resolve_token(
    authorization: str | None,
    allow_query_token: bool,
    query_token: str | None,
) -> str:
    if authorization:
        if not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header",
            )
        return authorization.split(" ", 1)[1].strip()

    if allow_query_token and query_token:
        return query_token.strip()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authorization token",
    )


async def get_current_session(
    request: Request,
    authorization: str | None = Header(None, alias="Authorization"),
    auth_service: AuthService = Depends(get_auth_service_dep),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """
    Extract the session token from the `Authorization: Bearer <token>` header,
    validate it, check per-user rate limits, and return (token, user_dict).
    """
    # Check per-user rate limit BEFORE authentication
    # This uses JWT token to identify user without full validation
    await rate_limiter.check_rate_limit(request)

    token = _resolve_token(authorization, allow_query_token=False, query_token=None)
    try:
        user = auth_service.validate_session(token)
        return token, user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )


async def get_session_with_optional_query_token(
    request: Request,
    authorization: str | None = Header(None, alias="Authorization"),
    token: str | None = Query(None),
    auth_service: AuthService = Depends(get_auth_service_dep),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    """
    Same as get_current_session but also accepts token via query parameter.
    Includes per-user rate limiting.
    """
    # Check per-user rate limit
    await rate_limiter.check_rate_limit(request)

    token_value = _resolve_token(
        authorization, allow_query_token=True, query_token=token
    )
    try:
        user = auth_service.validate_session(token_value)
        return token_value, user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )


async def get_current_user(session=Depends(get_current_session)):
    _, user = session
    return user
