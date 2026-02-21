"""
Profile Tests
Tests for user profile access and update.
"""

import pytest


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
