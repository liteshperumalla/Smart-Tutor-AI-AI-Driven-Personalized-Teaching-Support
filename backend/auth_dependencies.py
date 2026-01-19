"""
Authentication Dependencies for FastAPI
Provides dependency injection for JWT token validation with blacklist checking
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from typing import Dict, Any

from .jwt_service import get_jwt_service
from .jwt_blacklist import get_jwt_blacklist
from .logger import get_logger
from .exceptions import SessionExpiredError

logger = get_logger(__name__)

# HTTP Bearer token scheme for FastAPI
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get the current authenticated user.
    Validates JWT token and checks if it's blacklisted.

    Args:
        credentials: HTTP Bearer credentials from request header

    Returns:
        Dict containing user information from JWT payload

    Raises:
        HTTPException: If token is invalid, expired, or blacklisted
    """
    token = credentials.credentials

    try:
        # Check if token is blacklisted (logged out)
        jwt_blacklist = get_jwt_blacklist()
        if jwt_blacklist and jwt_blacklist.is_blacklisted(token):
            logger.warning("Attempt to use blacklisted (logged out) token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify token signature and expiration
        jwt_service = get_jwt_service()
        payload = jwt_service.verify_token(token, token_type="access")

        # Extract user information
        username = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing username",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {
            "username": username,
            "email": payload.get("email", ""),
            "token": token,
            "payload": payload
        }

    except SessionExpiredError:
        logger.warning("Expired token used")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get current active user (can be extended to check if user is active/enabled)

    Args:
        current_user: Current user from get_current_user dependency

    Returns:
        Dict containing user information
    """
    # TODO: Add database check to verify user is still active
    # from .database import get_user_db
    # user_db = get_user_db()
    # user = user_db.get_user(current_user["username"])
    # if user.get("disabled"):
    #     raise HTTPException(status_code=400, detail="Inactive user")

    return current_user


async def get_optional_user(
    credentials: HTTPAuthCredentials = Depends(HTTPBearer(auto_error=False))
) -> Dict[str, Any] | None:
    """
    Optional authentication - returns user if token is valid, None otherwise.
    Useful for endpoints that work both authenticated and unauthenticated.

    Args:
        credentials: Optional HTTP Bearer credentials

    Returns:
        Dict containing user information if authenticated, None otherwise
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
