"""
Authentication Tests
Tests for user registration, login, logout, and token management
"""

import pytest
from datetime import datetime, timedelta


class TestUserRegistration:
    """Test user registration functionality"""

    def test_successful_registration(self, test_client):
        """Test successful user registration"""
        response = test_client.post(
            "/auth/signup",
            json={
                "username": "newuser123",
                "password": "SecurePass123!",
                "confirm_password": "SecurePass123!",
                "email": "newuser@example.com",
                "full_name": "New User"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert data["user"]["username"] == "newuser123"

        # Cleanup
        from backend.database import get_user_db
        get_user_db().delete_user("newuser123")

    def test_registration_password_mismatch(self, test_client):
        """Test registration fails with mismatched passwords"""
        response = test_client.post(
            "/auth/signup",
            json={
                "username": "testuser2",
                "password": "SecurePass123!",
                "confirm_password": "DifferentPass123!",
                "email": "test2@example.com"
            }
        )
        assert response.status_code == 400

    def test_registration_weak_password(self, test_client):
        """Test registration fails with weak password"""
        response = test_client.post(
            "/auth/signup",
            json={
                "username": "testuser3",
                "password": "weak",
                "confirm_password": "weak",
                "email": "test3@example.com"
            }
        )
        assert response.status_code == 400

    def test_registration_duplicate_username(self, test_client, test_user):
        """Test registration fails with duplicate username"""
        response = test_client.post(
            "/auth/signup",
            json={
                "username": test_user["username"],
                "password": "SecurePass123!",
                "confirm_password": "SecurePass123!",
                "email": "another@example.com"
            }
        )
        assert response.status_code == 400


class TestUserLogin:
    """Test user login functionality"""

    def test_successful_login(self, test_client, test_user):
        """Test successful login"""
        response = test_client.post(
            "/auth/login",
            json={
                "username": test_user["username"],
                "password": test_user["password"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data

    def test_login_invalid_credentials(self, test_client, test_user):
        """Test login fails with invalid credentials"""
        response = test_client.post(
            "/auth/login",
            json={
                "username": test_user["username"],
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, test_client):
        """Test login fails with nonexistent user"""
        response = test_client.post(
            "/auth/login",
            json={
                "username": "nonexistent",
                "password": "password123"
            }
        )
        assert response.status_code == 401


class TestTokenManagement:
    """Test JWT token management"""

    def test_access_protected_endpoint(self, test_client, auth_headers):
        """Test accessing protected endpoint with valid token"""
        response = test_client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "user" in data

    def test_access_without_token(self, test_client):
        """Test accessing protected endpoint without token"""
        response = test_client.get("/auth/me")
        assert response.status_code == 401

    def test_access_with_invalid_token(self, test_client):
        """Test accessing protected endpoint with invalid token"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = test_client.get("/auth/me", headers=headers)
        assert response.status_code == 401

    def test_token_refresh(self, test_client, test_user):
        """Test token refresh functionality"""
        # Login to get tokens
        login_response = test_client.post(
            "/auth/login",
            json={
                "username": test_user["username"],
                "password": test_user["password"]
            }
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh token
        response = test_client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


class TestLogout:
    """Test logout functionality"""

    def test_successful_logout(self, test_client, auth_token, auth_headers):
        """Test successful logout"""
        response = test_client.post("/auth/logout", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify token is blacklisted
        me_response = test_client.get("/auth/me", headers=auth_headers)
        assert me_response.status_code == 401
