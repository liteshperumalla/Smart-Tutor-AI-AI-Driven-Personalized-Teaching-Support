from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from backend.config import config
from backend.services.models import Appointment


def _sanitize_user_id(user_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in user_id)


class DuplicateAppointmentError(RuntimeError):
    """Raised when a user submits the same appointment request repeatedly."""


class AppointmentService:
    def __init__(self) -> None:
        self.root = Path(config.USER_DATA_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)

    def _user_dir(self, username: str) -> Path:
        safe = _sanitize_user_id(username)
        directory = self.root / safe / "appointments"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _iter_appointment_files(self):
        if not self.root.exists():
            return
        for user_dir in self.root.iterdir():
            if not user_dir.is_dir():
                continue
            directory = user_dir / "appointments"
            if not directory.exists():
                continue
            yield from directory.glob("*.json")

    def list_for_user(self, username: str) -> List[Appointment]:
        directory = self._user_dir(username)
        appointments: List[Appointment] = []
        for path in directory.glob("*.json"):
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                appointments.append(self._from_dict(data))
            except Exception:
                continue
        appointments.sort(key=lambda item: item.requested_at, reverse=True)
        return appointments

    def list_all(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 200,
    ) -> List[Appointment]:
        appointments: List[Appointment] = []
        for path in self._iter_appointment_files() or []:
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                appointment = self._from_dict(data)
            except Exception:
                continue
            if status and appointment.status != status:
                continue
            appointments.append(appointment)
        appointments.sort(key=lambda item: item.requested_at, reverse=True)
        return appointments[:limit]

    def update_status(self, appointment_id: str, new_status: str) -> Optional[Appointment]:
        for path in self._iter_appointment_files() or []:
            if path.stem != appointment_id:
                continue
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                return None
            data["status"] = new_status
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return self._from_dict(data)
        return None

    def _find_recent_duplicate(
        self,
        user_id: str,
        appointment_with: str,
        preferred_date: str,
        preferred_time: str,
        primary_reason: str,
        additional_details: str,
    ) -> Optional[Appointment]:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        normalized_details = additional_details.strip()
        for existing in self.list_for_user(user_id):
            if existing.requested_at < cutoff:
                break
            if (
                existing.appointment_with.strip().lower() == appointment_with.strip().lower()
                and existing.preferred_date == preferred_date
                and existing.preferred_time == preferred_time
                and existing.primary_reason.strip().lower() == primary_reason.strip().lower()
                and existing.additional_details.strip().lower() == normalized_details.lower()
                and existing.status in {"pending", "confirmed"}
            ):
                return existing
        return None

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
        duplicate = self._find_recent_duplicate(
            user_id=user_id,
            appointment_with=appointment_with,
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            primary_reason=primary_reason,
            additional_details=additional_details,
        )
        if duplicate:
            raise DuplicateAppointmentError(
                "A matching appointment request was already submitted recently."
            )

        appointment = Appointment(
            id=uuid.uuid4().hex,
            user_id=user_id,
            user_name=user_name.strip(),
            user_email=user_email.strip(),
            appointment_with=appointment_with.strip(),
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            primary_reason=primary_reason.strip(),
            additional_details=additional_details.strip(),
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
