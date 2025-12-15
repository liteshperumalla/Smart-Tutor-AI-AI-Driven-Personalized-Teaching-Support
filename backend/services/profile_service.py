from __future__ import annotations

import base64
import shutil
from pathlib import Path
from typing import Dict

from backend.config import config
from backend.database import get_user_db
from backend.services import get_storage_backend
from backend.services.appointment_service import get_appointment_service
from backend.services.feedback_service import get_feedback_service


def _sanitize(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in value)


class ProfileService:
    def __init__(self) -> None:
        self.user_db = get_user_db()
        self.storage = get_storage_backend()
        self.appointments = get_appointment_service()
        self.feedback = get_feedback_service()
        self.user_root = Path(config.USER_DATA_ROOT)
        self.user_root.mkdir(parents=True, exist_ok=True)

    def _notes_path(self, username: str) -> Path:
        safe = _sanitize(username)
        directory = self.user_root / safe / "notes"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / "notes.txt"

    def _user_dir(self, username: str) -> Path:
        safe = _sanitize(username)
        directory = self.user_root / safe
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _profile_picture_path(self, username: str) -> Path | None:
        directory = self._user_dir(username)
        for ext in (".png", ".jpg", ".jpeg"):
            path = directory / f"profile_pic{ext}"
            if path.exists():
                return path
        return None

    def _profile_picture_data(self, username: str) -> str | None:
        path = self._profile_picture_path(username)
        if not path:
            return None
        data = path.read_bytes()
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        encoded = base64.b64encode(data).decode("utf-8")
        return f"data:{mime};base64,{encoded}"

    def _serialize_user(self, username: str, user: Dict[str, object]) -> Dict[str, object]:
        return {
            "username": username,
            "email": user.get("email", ""),
            "display_name": user.get("display_name", ""),
            "phone_number": user.get("phone_number", ""),
            "role": user.get("role", "User"),
            "last_login": user.get("last_login", ""),
            "theme": user.get("theme", "light"),
        }

    def get_profile(self, username: str) -> Dict[str, object]:
        user = self.user_db.get_user_safe(username)
        if not user:
            raise ValueError("User not found")
        notes = self._read_notes(username)
        recent_quizzes = [
            result.to_dict() for result in self.storage.list_quiz_results(username)[:5]
        ]
        appointments = [a.to_dict() for a in self.appointments.list_for_user(username)[:5]]
        return {
            "user": self._serialize_user(username, user),
            "notes": notes,
            "recent_quizzes": recent_quizzes,
            "recent_appointments": appointments,
            "profile_picture": self._profile_picture_data(username),
        }

    def update_profile(self, username: str, updates: Dict[str, str]) -> Dict[str, object]:
        allowed = {"display_name", "phone_number", "theme"}
        filtered = {k: v for k, v in updates.items() if k in allowed}
        if filtered:
            user = self.user_db.update_user(username, filtered)
        else:
            user = self.user_db.get_user(username)
        return self._serialize_user(username, user)

    def save_notes(self, username: str, content: str) -> None:
        path = self._notes_path(username)
        with path.open("w", encoding="utf-8") as f:
            f.write(content.strip())

    def _read_notes(self, username: str) -> str:
        path = self._notes_path(username)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def delete_account(self, username: str) -> None:
        deleted = self.user_db.delete_user(username)
        if not deleted:
            raise ValueError("User not found")
        user_dir = self.user_root / _sanitize(username)
        if user_dir.exists():
            shutil.rmtree(user_dir, ignore_errors=True)

    def save_profile_picture(self, username: str, content: bytes, filename: str) -> str:
        extension = Path(filename or "").suffix.lower()
        if extension not in {".png", ".jpg", ".jpeg"}:
            raise ValueError("Only PNG and JPG files are supported")
        directory = self._user_dir(username)
        # Remove previous pictures
        for ext in (".png", ".jpg", ".jpeg"):
            path = directory / f"profile_pic{ext}"
            if path.exists():
                path.unlink(missing_ok=True)
        target = directory / f"profile_pic{extension}"
        with target.open("wb") as f:
            f.write(content)
        return self._profile_picture_data(username) or ""

    def list_quiz_history(self, username: str):
        return [result.to_dict() for result in self.storage.list_quiz_results(username)]

    def list_appointment_history(self, username: str):
        return [appt.to_dict() for appt in self.appointments.list_for_user(username)]

    def list_feedback_history(self, username: str):
        return self.feedback.list_entries(username)


_profile_service: ProfileService | None = None


def get_profile_service() -> ProfileService:
    global _profile_service
    if _profile_service is None:
        _profile_service = ProfileService()
    return _profile_service
