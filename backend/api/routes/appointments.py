from datetime import date, time
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from backend.api.dependencies import get_current_session, get_rate_limiter_dep
from backend.rate_limiter import limiter, PerUserRateLimiter

if TYPE_CHECKING:
    from backend.services.appointment_service import AppointmentService


router = APIRouter(prefix="/appointments", tags=["appointments"])

_APPOINTMENT_LIMIT = 6
_APPOINTMENT_WINDOW = 3600


def get_appointment_service():
    from backend.services.appointment_service import (
        get_appointment_service as _get_appointment_service,
    )

    return _get_appointment_service()


def notify_appointment_created(**kwargs):
    from backend.services.notification_service import (
        notify_appointment_created as _notify_appointment_created,
    )

    return _notify_appointment_created(**kwargs)


class AppointmentRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: EmailStr
    appointment_with: str = Field(
        ..., pattern=r"^(Professor|Teaching Assistant).*$"
    )
    preferred_date: date
    preferred_time: time
    primary_reason: str
    additional_details: str | None = ""


@router.get("")
def list_appointments(
    session=Depends(get_current_session),
    service: "AppointmentService" = Depends(get_appointment_service),
):
    _, user = session
    appointments = service.list_for_user(user["username"])
    return {"appointments": [a.to_dict() for a in appointments]}


@router.post("")
@limiter.limit("12/hour")
async def create_appointment(
    request: Request,
    payload: AppointmentRequest,
    session=Depends(get_current_session),
    service: "AppointmentService" = Depends(get_appointment_service),
    rate_limiter: PerUserRateLimiter = Depends(get_rate_limiter_dep),
):
    from backend.services.appointment_service import DuplicateAppointmentError

    await rate_limiter.check_rate_limit(
        request,
        limit=_APPOINTMENT_LIMIT,
        window=_APPOINTMENT_WINDOW,
        scope="appointments_create",
    )
    if payload.preferred_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Preferred date cannot be in the past",
        )
    _, user = session
    try:
        appointment = service.create(
            user_id=user["username"],
            user_name=payload.name,
            user_email=payload.email,
            appointment_with=payload.appointment_with,
            preferred_date=payload.preferred_date.isoformat(),
            preferred_time=payload.preferred_time.strftime("%H:%M"),
            primary_reason=payload.primary_reason,
            additional_details=payload.additional_details or "",
        )
    except DuplicateAppointmentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    notify_appointment_created(
        username=user["username"],
        appointment_with=appointment.appointment_with,
        preferred_date=appointment.preferred_date,
        preferred_time=appointment.preferred_time,
        primary_reason=appointment.primary_reason,
        user_email=appointment.user_email,
    )
    return {"appointment": appointment.to_dict()}
