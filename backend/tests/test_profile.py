"""
Profile Tests
Tests for user profile access and update.
"""

from datetime import date, datetime, timedelta
import json

import pytest

from backend.config import config
from backend.services.appointment_service import (
    AppointmentService,
    DuplicateAppointmentError,
)


class TestProfileEndpoints:
    """Test user profile endpoints"""

    def test_get_profile_requires_auth(self, test_client):
        """Profile endpoint without auth must return 401"""
        response = test_client.get("/profile")
        assert response.status_code == 401

    def test_get_own_profile(self, test_client, auth_headers):
        """Authenticated user can fetch their own profile"""
        response = test_client.get("/profile", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Response structure: {"profile": {"user": {...}, "notes": ...}}
        assert "profile" in data or "username" in data or "user" in data

    def test_update_profile_requires_auth(self, test_client):
        """Profile update without auth must return 401"""
        response = test_client.patch("/profile", json={"full_name": "Hacker"})
        assert response.status_code == 401

    def test_update_own_profile(self, test_client, auth_headers):
        """Authenticated user can update their own profile"""
        response = test_client.patch("/profile", headers=auth_headers, json={
            "full_name": "Updated Name"
        })
        assert response.status_code in (200, 204)

    def test_profile_history_requires_auth(self, test_client):
        """Profile quiz history without auth must return 401"""
        response = test_client.get("/profile/history/quizzes")
        assert response.status_code == 401

    def test_profile_history_with_auth(self, test_client, auth_headers):
        """Authenticated user can view their quiz history"""
        response = test_client.get("/profile/history/quizzes", headers=auth_headers)
        assert response.status_code in (200, 404)

    def test_appointment_request_rejects_past_date(self, test_client, auth_headers):
        response = test_client.post(
            "/appointments",
            headers=auth_headers,
            json={
                "name": "Test User",
                "email": "test@example.com",
                "appointment_with": "Professor (Dr. Chen)",
                "preferred_date": (date.today() - timedelta(days=1)).isoformat(),
                "preferred_time": "10:30",
                "primary_reason": "Discuss course material/concepts",
                "additional_details": "",
            },
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "Preferred date cannot be in the past"


def test_appointment_service_lists_most_recent_first(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "USER_DATA_ROOT", str(tmp_path))
    service = AppointmentService()
    directory = service._user_dir("alice")

    older = {
        "id": "older",
        "user_id": "alice",
        "user_name": "Alice",
        "user_email": "alice@example.com",
        "appointment_with": "Professor (Dr. Chen)",
        "preferred_date": "2026-03-28",
        "preferred_time": "09:00",
        "primary_reason": "Older request",
        "additional_details": "",
        "status": "pending",
        "requested_at": datetime(2026, 3, 20, 9, 0, 0).isoformat(),
    }
    newer = {
        "id": "newer",
        "user_id": "alice",
        "user_name": "Alice",
        "user_email": "alice@example.com",
        "appointment_with": "Teaching Assistant (TA)",
        "preferred_date": "2026-03-29",
        "preferred_time": "11:00",
        "primary_reason": "Newer request",
        "additional_details": "",
        "status": "pending",
        "requested_at": datetime(2026, 3, 21, 9, 0, 0).isoformat(),
    }

    (directory / "zzz.json").write_text(json.dumps(older), encoding="utf-8")
    (directory / "aaa.json").write_text(json.dumps(newer), encoding="utf-8")

    appointments = service.list_for_user("alice")

    assert [appointment.id for appointment in appointments] == ["newer", "older"]


def test_appointment_service_rejects_recent_duplicate(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "USER_DATA_ROOT", str(tmp_path))
    service = AppointmentService()

    service.create(
        user_id="alice",
        user_name="Alice",
        user_email="alice@example.com",
        appointment_with="Professor (Dr. Chen)",
        preferred_date="2026-03-30",
        preferred_time="10:00",
        primary_reason="Discuss course material/concepts",
        additional_details="Need help with week 5",
    )

    with pytest.raises(DuplicateAppointmentError):
        service.create(
            user_id="alice",
            user_name="Alice",
            user_email="alice@example.com",
            appointment_with="Professor (Dr. Chen)",
            preferred_date="2026-03-30",
            preferred_time="10:00",
            primary_reason="Discuss course material/concepts",
            additional_details="Need help with week 5",
        )
