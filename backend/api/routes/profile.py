from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from backend.api.dependencies import get_current_session
from backend.auth_service import AuthService, get_auth_service
from backend.exceptions import InvalidCredentialsError, PasswordValidationError
from backend.services.profile_service import ProfileService, get_profile_service


router = APIRouter(prefix="/profile", tags=["profile"])

MAX_PROFILE_PICTURE_SIZE = 5 * 1024 * 1024  # 5 MB


class ProfileUpdatePayload(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    phone_number: str | None = Field(None, max_length=20)
    theme: str | None = Field(None, pattern=r"^(light|dark)$")


class NotesPayload(BaseModel):
    content: str = Field("", max_length=5000)


class PasswordChangePayload(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


class DeleteAccountPayload(BaseModel):
    confirm_username: str = Field(..., min_length=3, max_length=50)


@router.get("")
def fetch_profile(
    session=Depends(get_current_session),
    service: ProfileService = Depends(get_profile_service),
):
    _, user = session
    try:
        profile = service.get_profile(user["username"])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {"profile": profile}


@router.patch("")
def update_profile(
    payload: ProfileUpdatePayload,
    session=Depends(get_current_session),
    service: ProfileService = Depends(get_profile_service),
):
    _, user = session
    updates = payload.dict(exclude_none=True)
    if not updates:
        return {"user": service.get_profile(user["username"])["user"]}
    updated = service.update_profile(user["username"], updates)
    return {"user": updated}


@router.post("/notes")
def save_notes(
    payload: NotesPayload,
    session=Depends(get_current_session),
    service: ProfileService = Depends(get_profile_service),
):
    _, user = session
    service.save_notes(user["username"], payload.content)
    return {"notes": payload.content.strip()}


@router.post("/password")
def change_password(
    payload: PasswordChangePayload,
    session=Depends(get_current_session),
    auth_service: AuthService = Depends(get_auth_service),
):
    _, user = session
    try:
        auth_service.change_password(user["username"], payload.current_password, payload.new_password)
        return {"success": True}
    except (InvalidCredentialsError, PasswordValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("")
def delete_account(
    payload: DeleteAccountPayload,
    session=Depends(get_current_session),
    service: ProfileService = Depends(get_profile_service),
    auth_service: AuthService = Depends(get_auth_service),
):
    token, user = session
    if payload.confirm_username.strip() != user["username"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username confirmation does not match",
        )
    try:
        service.delete_account(user["username"])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    auth_service.logout(token)
    return {"success": True}


@router.post("/picture")
async def upload_profile_picture(
    session=Depends(get_current_session),
    service: ProfileService = Depends(get_profile_service),
    file: UploadFile = File(...),
):
    _, user = session
    # Read with size guard — read one byte beyond the limit to detect oversized files
    content = await file.read(MAX_PROFILE_PICTURE_SIZE + 1)
    if len(content) > MAX_PROFILE_PICTURE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 5 MB.",
        )
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided")
    try:
        picture = service.save_profile_picture(user["username"], content, file.filename or "upload.png")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"profile_picture": picture}


@router.get("/history/quizzes")
def full_quiz_history(
    session=Depends(get_current_session),
    service: ProfileService = Depends(get_profile_service),
):
    _, user = session
    return {"results": service.list_quiz_history(user["username"])}


@router.get("/history/appointments")
def full_appointment_history(
    session=Depends(get_current_session),
    service: ProfileService = Depends(get_profile_service),
):
    _, user = session
    return {"appointments": service.list_appointment_history(user["username"])}


@router.get("/history/feedback")
def feedback_history(
    session=Depends(get_current_session),
    service: ProfileService = Depends(get_profile_service),
):
    _, user = session
    return service.list_feedback_history(user["username"])
