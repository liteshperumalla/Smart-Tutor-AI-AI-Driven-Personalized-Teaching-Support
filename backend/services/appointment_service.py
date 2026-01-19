from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from backend.config import config
from backend.services.models import Appointment
def _sanitize_user_id(user_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in user_id)


class AppointmentService:
    def __init__(self) -> None:
        self.root = Path(config.USER_DATA_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)

    def _user_dir(self, username: str) -> Path:
        safe = _sanitize_user_id(username)
        directory = self.root / safe / "appointments"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def list_for_user(self, username: str) -> List[Appointment]:
        directory = self._user_dir(username)
        appointments: List[Appointment] = []
        for path in sorted(directory.glob("*.json"), reverse=True):
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                appointments.append(self._from_dict(data))
            except Exception:
                continue
        return appointments

    def create(
        self,
        user_id: str,
        user_name: str,
        user_email: str,
        appointment_with: str,
        preferred_date: str,
        preferred_time: str,
        primary_reason: str,
        additional_details: str,
    ) -> Appointment:
        appointment = Appointment(
            id=uuid.uuid4().hex,
            user_id=user_id,
            user_name=user_name,
            user_email=user_email,
            appointment_with=appointment_with,
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            primary_reason=primary_reason,
            additional_details=additional_details,
        )
        directory = self._user_dir(user_id)
        path = directory / f"{appointment.id}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(appointment.to_dict(), f, indent=2, ensure_ascii=False)
        return appointment

    def _from_dict(self, data: dict) -> Appointment:
        requested = data.get("requested_at")
        requested_at = (
            datetime.fromisoformat(requested) if requested else datetime.utcnow()
        )
        return Appointment(
            id=data.get("id", uuid.uuid4().hex),
            user_id=data.get("user_id", ""),
            user_name=data.get("user_name", ""),
            user_email=data.get("user_email", ""),
            appointment_with=data.get("appointment_with", ""),
            preferred_date=data.get("preferred_date", ""),
            preferred_time=data.get("preferred_time", ""),
            primary_reason=data.get("primary_reason", ""),
            additional_details=data.get("additional_details", ""),
            status=data.get("status", "pending"),
            requested_at=requested_at,
        )


_appointment_service: AppointmentService | None = None


def get_appointment_service() -> AppointmentService:
    global _appointment_service
    if _appointment_service is None:
        _appointment_service = AppointmentService()
    return _appointment_service
