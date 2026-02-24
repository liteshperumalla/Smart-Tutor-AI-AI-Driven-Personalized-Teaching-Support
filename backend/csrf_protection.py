"""
CSRF (Cross-Site Request Forgery) Protection

Implements double-submit cookie pattern for CSRF protection.
This is used in addition to SameSite=Lax cookies for defense in depth.

NOTE: Currently not wired into routes because all authentication cookies
use SameSite=Lax, which prevents cross-site POST/PUT/DELETE requests from
sending cookies at the browser level. This module is available for
additional defense-in-depth if the cookie policy changes.

References:
- OWASP CSRF Prevention Cheat Sheet
- Double Submit Cookie pattern
"""

import secrets
import hashlib
from typing import Optional
from fastapi import Request, Response, HTTPException, status
import logging

logger = logging.getLogger(__name__)

# CSRF token length in bytes (32 bytes = 256 bits)
CSRF_TOKEN_LENGTH = 32

# Header name for CSRF token
CSRF_HEADER_NAME = "X-CSRF-Token"

# Cookie name for CSRF token
CSRF_COOKIE_NAME = "csrf_token"


class CSRFProtection:
    """
    CSRF Protection using double-submit cookie pattern.

    How it works:
    1. Server generates random CSRF token on first request
    2. Token is set in both a cookie and returned to client
    3. Client must send token in custom header for state-changing requests
    4. Server validates header token matches cookie token

    Security:
    - Random tokens prevent prediction attacks
    - Custom header requirement prevents simple form submissions
    - SameSite cookies provide additional protection
    """

    @staticmethod
    def generate_token() -> str:
        """
        Generate a cryptographically secure random CSRF token.

        Returns:
            str: URL-safe base64 encoded token
        """
        return secrets.token_urlsafe(CSRF_TOKEN_LENGTH)

    @staticmethod
    def set_csrf_cookie(response: Response, token: Optional[str] = None) -> str:
        """
        Set CSRF token in a cookie.

        Args:
            response: FastAPI Response object
            token: Optional existing token, generates new one if not provided

        Returns:
            str: The CSRF token that was set
        """
        if not token:
            token = CSRFProtection.generate_token()

        from backend.config import config
        is_production = config.ENVIRONMENT == "production"

        # Set CSRF token in regular cookie (NOT HttpOnly, so JavaScript can read it)
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=token,
            httponly=False,  # JavaScript needs to read this to send in header
            secure=is_production,  # HTTPS only in production (matches auth cookie behaviour)
            samesite="lax",  # CSRF protection
            max_age=3600,  # 1 hour
            path="/",
        )

        return token

    @staticmethod
    def get_token_from_cookie(request: Request) -> Optional[str]:
        """
        Get CSRF token from cookie.

        Args:
            request: FastAPI Request object

        Returns:
            Optional[str]: CSRF token or None if not found
        """
        return request.cookies.get(CSRF_COOKIE_NAME)

    @staticmethod
    def get_token_from_header(request: Request) -> Optional[str]:
        """
        Get CSRF token from request header.

        Args:
            request: FastAPI Request object

        Returns:
            Optional[str]: CSRF token or None if not found
        """
        return request.headers.get(CSRF_HEADER_NAME)

    @staticmethod
    def verify_token(request: Request) -> bool:
        """
        Verify CSRF token matches between cookie and header.

        Args:
            request: FastAPI Request object

        Returns:
            bool: True if tokens match, False otherwise
        """
        cookie_token = CSRFProtection.get_token_from_cookie(request)
        header_token = CSRFProtection.get_token_from_header(request)

        if not cookie_token or not header_token:
            return False

        # Constant-time comparison to prevent timing attacks
        return secrets.compare_digest(cookie_token, header_token)

    @staticmethod
    def require_csrf_token(request: Request):
        """
        Dependency function to require CSRF token validation.

        Use this as a FastAPI dependency on state-changing endpoints:
        @router.post("/something", dependencies=[Depends(require_csrf_token)])

        Args:
            request: FastAPI Request object

        Raises:
            HTTPException: 403 if CSRF validation fails
        """
        # Skip CSRF validation in test environment
        from backend.config import config
        if getattr(config, "ENVIRONMENT", "") == "test":
            return

        # Only validate CSRF for state-changing methods
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            if not CSRFProtection.verify_token(request):
                logger.warning(
                    f"CSRF validation failed for {request.method} {request.url.path}",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "client": request.client.host if request.client else "unknown"
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CSRF validation failed. Please refresh the page and try again."
                )


# Convenience function for getting CSRF token
def get_csrf_token(request: Request, response: Response) -> str:
    """
    Get or generate CSRF token for a request.

    This should be called on initial page load to set the CSRF token.

    Args:
        request: FastAPI Request object
        response: FastAPI Response object

    Returns:
        str: CSRF token
    """
    # Try to get existing token from cookie
    existing_token = CSRFProtection.get_token_from_cookie(request)

    if existing_token:
        return existing_token

    # Generate new token and set cookie
    new_token = CSRFProtection.set_csrf_cookie(response)
    return new_token


# FastAPI dependency for CSRF protection
async def csrf_protect(request: Request):
    """
    FastAPI dependency for CSRF protection.

    Usage:
        @router.post("/endpoint", dependencies=[Depends(csrf_protect)])
        async def endpoint():
            ...
    """
    CSRFProtection.require_csrf_token(request)
