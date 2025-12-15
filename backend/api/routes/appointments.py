from datetime import date, time
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from backend.api.dependencies import get_current_session
from backend.services.appointment_service import (
    get_appointment_service,
    AppointmentService,
)


router = APIRouter(prefix="/appointments", tags=["appointments"])


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
    service: AppointmentService = Depends(get_appointment_service),
):
    _, user = session
    appointments = service.list_for_user(user["username"])
    return {"appointments": [a.to_dict() for a in appointments]}


@router.post("")
def create_appointment(
    payload: AppointmentRequest,
    session=Depends(get_current_session),
    service: AppointmentService = Depends(get_appointment_service),
):
    _, user = session
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
    return {"appointment": appointment.to_dict()}
