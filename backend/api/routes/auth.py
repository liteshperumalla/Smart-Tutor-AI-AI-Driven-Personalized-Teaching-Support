from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

from backend.auth_service import AuthService, get_auth_service
from backend.api.dependencies import get_current_user, get_current_session

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)
    email: Optional[EmailStr] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class GoogleAuthRequest(BaseModel):
    code: str
    redirect_uri: str
    state: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post("/signup")
def signup(payload: SignupRequest, auth_service: AuthService = Depends(get_auth_service)):
    try:
        user = auth_service.register_user(
            username=payload.username,
            password=payload.password,
            confirm_password=payload.confirm_password,
            email=payload.email,
        )
        return {"user": user}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/login")
def login(payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)):
    """Login endpoint - returns access_token and refresh_token"""
    try:
        tokens, user = auth_service.login(payload.username, payload.password)
        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": tokens["token_type"],
            "user": user,
            # Include legacy 'token' field for backward compatibility
            "token": tokens["access_token"]
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.post("/google/callback")
def google_callback(payload: GoogleAuthRequest, auth_service: AuthService = Depends(get_auth_service)):
    """Google OAuth callback - returns access_token and refresh_token"""
    try:
        tokens, user = auth_service.login_with_google(payload.code, payload.redirect_uri)
        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": tokens["token_type"],
            "user": user,
            "state": payload.state,
            # Include legacy 'token' field for backward compatibility
            "token": tokens["access_token"]
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/refresh")
def refresh_token(payload: RefreshTokenRequest, auth_service: AuthService = Depends(get_auth_service)):
    """Refresh access token using refresh token"""
    try:
        tokens = auth_service.refresh_token(payload.refresh_token)
        return {
            "access_token": tokens["access_token"],
            "token_type": tokens["token_type"]
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}


@router.post("/logout")
def logout(
    session=Depends(get_current_session),
    auth_service: AuthService = Depends(get_auth_service),
):
    token, _ = session
    auth_service.logout(token)
    return {"success": True}
