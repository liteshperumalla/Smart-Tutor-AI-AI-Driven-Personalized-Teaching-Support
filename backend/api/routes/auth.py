from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

from backend.auth_service import AuthService, get_auth_service
from backend.api.dependencies import get_current_user, get_current_session
from backend.config import config
from backend.security_logger import SecurityLogger, get_client_ip, get_user_agent
from backend.rate_limiter import (
    limiter,
)  # Import from rate_limiter to avoid circular imports

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
    # Determine if we should use Secure flag
    is_production = config.ENVIRONMENT == "production"

    # Set cookie domain for cross-origin requests (e.g., frontend proxy)
    cookie_domain = "localhost" if not is_production else None

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
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class GoogleAuthRequest(BaseModel):
    code: str
    redirect_uri: str
    state: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    redirect_url: Optional[str] = None


class PasswordResetConfirmRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


@router.post("/signup")
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

        return {"user": user}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/login")
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

        # SECURITY: Log successful login
        SecurityLogger.log_login_success(
            username=payload.username,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )

        # Return user info only (tokens are in cookies)
        return {
            "user": user,
            "token_type": tokens["token_type"],
            "message": "Login successful. Tokens set in secure cookies.",
        }
    except Exception as exc:
        # SECURITY: Log failed login attempt
        SecurityLogger.log_login_failed(
            username=payload.username,
            ip_address=get_client_ip(request),
            reason="invalid_credentials",
            user_agent=get_user_agent(request),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


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
        tokens, user = auth_service.login_with_google(
            payload.code, payload.redirect_uri
        )

        # SECURITY: Set tokens in HttpOnly cookies
        set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])

        # Return user info only (tokens are in cookies)
        return {
            "user": user,
            "token_type": tokens["token_type"],
            "state": payload.state,
            "message": "Google login successful. Tokens set in secure cookies.",
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


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
        print(f"Error during password reset request: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process password reset request.",
        )
    return {"ok": True}


@router.post("/password/reset/confirm")
def confirm_password_reset(
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
        print(f"Error during password reset confirmation: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password reset request.",
        )
    return {"ok": True}


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}


@router.post("/logout")
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
