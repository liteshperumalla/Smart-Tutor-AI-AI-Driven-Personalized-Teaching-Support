import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

from backend.auth_service import AuthService, get_auth_service
from backend import posthog_tracker
from backend.exceptions import (
    EmailNotVerifiedError,
    UserAlreadyExistsError,
    PasswordValidationError,
    InvalidCredentialsError,
    TokenInvalidError,
)
from backend.api.dependencies import get_current_user, get_current_session
from backend.config import config
from backend.security_logger import SecurityLogger, get_client_ip, get_user_agent
from backend.rate_limiter import (
    limiter,
)  # Import from rate_limiter to avoid circular imports
from backend.csrf_protection import csrf_protect

router = APIRouter(prefix="/auth", tags=["auth"])


# SECURITY: Helper function to set secure HttpOnly cookies
def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """
    Set secure HttpOnly cookies for authentication tokens.

    Security features:
    - HttpOnly: Prevents JavaScript access (XSS protection)
    - Secure: Only sent over HTTPS in production
    - SameSite=Lax: CSRF protection while allowing OAuth redirects
    - Path specific: Cookies only sent to API endpoints
    """
    # staging is treated as production: Vercel is HTTPS and must NOT set
    # domain=localhost — browsers silently reject cookies whose Domain attribute
    # doesn't match the page origin (smart-ai-tutor.vercel.app ≠ localhost).
    is_production = config.ENVIRONMENT in ("production", "staging")

    # cookie_domain=None means the browser inherits the request host, which
    # works for localhost, Vercel, EC2, and any custom domain automatically.
    # Explicitly setting "localhost" is only safe for local Docker dev.
    if config.ENVIRONMENT == "test":
        cookie_domain = None
    elif is_production:
        cookie_domain = None  # Works on any host (Vercel, EC2, custom domain)
    else:
        cookie_domain = "localhost"  # Local Docker dev only

    # Set access token cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # XSS protection
        secure=is_production,  # HTTPS only in production
        samesite="lax",  # CSRF protection (Lax allows OAuth redirects)
        max_age=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 15 minutes
        path="/",
        domain=cookie_domain,
    )

    # Set refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_production,
        samesite="lax",
        max_age=config.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,  # 7 days
        path="/",
        domain=cookie_domain,
    )


def clear_auth_cookies(response: Response):
    """Clear authentication cookies on logout."""
    is_production = config.ENVIRONMENT in ("production", "staging")
    if config.ENVIRONMENT == "test":
        cookie_domain = None
    elif is_production:
        cookie_domain = None
    else:
        cookie_domain = "localhost"

    response.delete_cookie(key="access_token", path="/", domain=cookie_domain)
    response.delete_cookie(key="refresh_token", path="/", domain=cookie_domain)


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=12)
    confirm_password: str = Field(..., min_length=12)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=255)


class LoginRequest(BaseModel):
    username: str
    password: str


class GoogleAuthRequest(BaseModel):
    code: str
    redirect_uri: str
    state: str = Field(..., min_length=1)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    redirect_url: Optional[str] = None

    @validator("redirect_url")
    def validate_redirect_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        host = urlparse(v).netloc
        allowed = [d.strip() for d in config.ALLOWED_REDIRECT_DOMAINS if d.strip()]
        if allowed and host not in allowed:
            raise ValueError(
                f"redirect_url host '{host}' is not in the allowed redirect domains list"
            )
        return v


class PasswordResetConfirmRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=12)
    confirm_password: str = Field(..., min_length=12)


class EmailVerificationRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None


class EmailVerificationConfirmRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    code: str = Field(..., min_length=6, max_length=6)


class PasswordSetupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=12)
    confirm_password: str = Field(..., min_length=12)


@router.post("/signup")
@limiter.limit("5/hour")
def signup(
    payload: SignupRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        user = auth_service.register_user(
            username=payload.username,
            password=payload.password,
            confirm_password=payload.confirm_password,
            email=payload.email,
            full_name=payload.full_name,
        )

        # SECURITY: Log account creation
        SecurityLogger.log_account_created(
            username=payload.username, ip_address=get_client_ip(request)
        )

        return {
            "user": user,
            "verification_required": True,
            "message": "Verification code sent to email.",
        }
    except UserAlreadyExistsError as exc:
        logger.warning(f"Registration failed - username taken: {exc}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username is already taken. Please choose a different one.",
        )
    except PasswordValidationError as exc:
        logger.warning(f"Registration failed - weak password: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc) or "Password does not meet the requirements.",
        )
    except InvalidCredentialsError as exc:
        logger.warning(f"Registration failed - invalid input: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc) or "Invalid registration details.",
        )
    except Exception as exc:
        exc_str = str(exc).lower()
        if "unique" in exc_str and "email" in exc_str:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with that email already exists. Try signing in instead.",
            )
        logger.warning(f"Registration failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed. Please check your details and try again.",
        )


@router.post("/login")
@limiter.limit("20/minute")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Login endpoint - sets secure HttpOnly cookies for authentication.

    SECURITY: Tokens are stored in HttpOnly cookies to prevent XSS attacks.
    Frontend should NOT store tokens in localStorage.
    """
    try:
        tokens, user = auth_service.login(payload.username, payload.password)

        # SECURITY: Set tokens in HttpOnly cookies
        set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])

        # Set CSRF token cookie for subsequent state-changing requests
        from backend.csrf_protection import CSRFProtection
        CSRFProtection.set_csrf_cookie(response)

        # SECURITY: Log successful login
        SecurityLogger.log_login_success(
            username=payload.username,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )

        posthog_tracker.capture(
            distinct_id=payload.username,
            event="login",
            properties={"method": "password"},
        )

        # Return user info only (tokens are in cookies)
        return {
            "user": user,
            "token_type": tokens["token_type"],
            "message": "Login successful. Tokens set in secure cookies.",
        }
    except EmailNotVerifiedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except Exception as exc:
        # SECURITY: Log failed login attempt
        SecurityLogger.log_login_failed(
            username=payload.username,
            ip_address=get_client_ip(request),
            reason="invalid_credentials",
            user_agent=get_user_agent(request),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password. Please check your details or create an account.",
        )


@router.post("/google/callback")
def google_callback(
    payload: GoogleAuthRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Google OAuth callback - sets secure HttpOnly cookies for authentication.

    SECURITY: Tokens are stored in HttpOnly cookies to prevent XSS attacks.
    """
    try:
        tokens, user, setup_token = auth_service.login_with_google(
            payload.code, payload.redirect_uri
        )

        if setup_token and not tokens:
            return JSONResponse(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                content={
                    "requires_password_setup": True,
                    "username": user.get("username"),
                    "email": user.get("email"),
                    "password_setup_token": setup_token,
                    "message": "Password setup required.",
                },
            )

        # SECURITY: Set tokens in HttpOnly cookies
        set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])

        # Set CSRF token cookie (required for state-changing requests like delete/rename)
        from backend.csrf_protection import CSRFProtection
        CSRFProtection.set_csrf_cookie(response)

        # Return user info only (tokens are in cookies)
        return {
            "user": user,
            "token_type": tokens["token_type"],
            "state": payload.state,
            "message": "Google login successful. Tokens set in secure cookies.",
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google authentication failed")


@router.post("/verify/request")
@limiter.limit("5/hour")
def request_email_verification(
    request: Request,
    payload: EmailVerificationRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    if not payload.username and not payload.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide username or email",
        )
    try:
        auth_service.request_email_verification(
            username=payload.username,
            email=payload.email,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification request failed")
    return {"ok": True}


@router.post("/verify/confirm")
@limiter.limit("10/hour")
def confirm_email_verification(
    request: Request,
    payload: EmailVerificationConfirmRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        auth_service.confirm_email_verification(payload.username, payload.code)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification failed")
    return {"ok": True}


@router.post("/password/setup")
@limiter.limit("5/hour")
def setup_password(
    request: Request,
    payload: PasswordSetupRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        user = auth_service.complete_password_setup(
            payload.username,
            payload.token,
            payload.new_password,
            payload.confirm_password,
        )

        login_username = user.get("username") or payload.username
        tokens, _ = auth_service.login(login_username, payload.new_password)
        set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
        from backend.csrf_protection import CSRFProtection
        CSRFProtection.set_csrf_cookie(response)

        return {"user": user, "message": "Password set successfully."}
    except PasswordValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except TokenInvalidError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except EmailNotVerifiedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except Exception as exc:
        logger.warning("Password setup failed for %s: %s", payload.username, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password setup failed")


@router.post("/refresh")
def refresh_token(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Refresh access token using refresh token from cookie.

    SECURITY: Reads refresh token from HttpOnly cookie.
    """
    try:
        # SECURITY: Get refresh token from HttpOnly cookie
        refresh_token_value = request.cookies.get("refresh_token")

        if not refresh_token_value:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No refresh token found. Please login again.",
            )

        tokens = auth_service.refresh_token(refresh_token_value)

        # SECURITY: Set new access token in HttpOnly cookie
        # Note: Refresh token stays the same
        response.set_cookie(
            key="access_token",
            value=tokens["access_token"],
            httponly=True,
            secure=config.ENVIRONMENT == "production",
            samesite="lax",
            max_age=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
        )

        # Renew CSRF cookie so it doesn't expire while the user is still logged in
        from backend.csrf_protection import CSRFProtection
        existing_csrf = request.cookies.get("csrf_token")
        CSRFProtection.set_csrf_cookie(response, token=existing_csrf or None)

        return {
            "message": "Token refreshed successfully",
            "token_type": tokens["token_type"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )


@router.post("/password/reset/request")
@limiter.limit("3/hour")  # SECURITY: Rate limit to prevent abuse
def request_password_reset(
    request: Request,  # Required for rate limiting
    payload: PasswordResetRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    if not payload.username and not payload.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide username or email",
        )
    try:
        auth_service.request_password_reset(
            username=payload.username,
            email=payload.email,
            redirect_url=payload.redirect_url,
        )
    except Exception as exc:
        # Log the full exception for debugging, but don't expose it to the client
        # In a real app, you would use a proper logger
        logger.warning(f"Password reset request error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process password reset request.",
        )
    return {"ok": True}


@router.post("/password/reset/confirm")
@limiter.limit("10/hour")
def confirm_password_reset(
    request: Request,
    payload: PasswordResetConfirmRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )
    try:
        auth_service.reset_password(
            payload.username, payload.new_password, payload.token
        )
    except Exception as exc:
        # Log the full exception for debugging
        logger.warning(f"Password reset confirmation error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password reset request.",
        )
    return {"ok": True}


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}


@router.post("/logout", dependencies=[Depends(csrf_protect)])
def logout(
    request: Request,
    response: Response,
    session=Depends(get_current_session),
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Logout endpoint - clears authentication cookies.

    SECURITY: Removes HttpOnly cookies to prevent token reuse.
    """
    token, user = session
    auth_service.logout(token)

    # SECURITY: Log logout
    SecurityLogger.log_logout(
        username=user.get("username", "unknown"), ip_address=get_client_ip(request)
    )

    # SECURITY: Clear authentication cookies
    clear_auth_cookies(response)

    return {"success": True, "message": "Logged out successfully. Cookies cleared."}
