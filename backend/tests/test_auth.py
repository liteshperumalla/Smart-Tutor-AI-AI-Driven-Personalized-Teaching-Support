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
        """Test registration fails with weak password (422 Pydantic or 400 business rule)"""
        response = test_client.post(
            "/auth/signup",
            json={
                "username": "testuser3",
                "password": "weak",
                "confirm_password": "weak",
                "email": "test3@example.com"
            }
        )
        assert response.status_code in (400, 422)

    def test_registration_duplicate_username(self, test_client, test_user):
        """Test registration fails with duplicate username (400 or 409 Conflict)"""
        response = test_client.post(
            "/auth/signup",
            json={
                "username": test_user["username"],
                "password": "SecurePass123!",
                "confirm_password": "SecurePass123!",
                "email": "another@example.com"
            }
        )
        assert response.status_code in (400, 409)


class TestUserLogin:
    """Test user login functionality"""

    def test_successful_login(self, test_client, test_user):
        """Test successful login — tokens returned as HttpOnly cookies"""
        response = test_client.post(
            "/auth/login",
            json={
                "username": test_user["username"],
                "password": test_user["password"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "bearer"
        assert "user" in data
        # Tokens are set as HttpOnly cookies, not in JSON body
        set_cookie = response.headers.get("set-cookie", "")
        assert "access_token" in set_cookie
        assert "refresh_token" in set_cookie

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
        test_client.cookies.clear()
        response = test_client.get("/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data.get("user") is None

    def test_access_with_cookie_auth_returns_user(self, test_client, test_user):
        """Test /auth/me returns the logged-in user for cookie-based auth."""
        test_client.cookies.clear()
        login_response = test_client.post(
            "/auth/login",
            json={
                "username": test_user["username"],
                "password": test_user["password"]
            }
        )
        assert login_response.status_code == 200

        response = test_client.get("/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data.get("user") is not None
        assert data["user"]["username"] == test_user["username"]

        test_client.cookies.clear()

    def test_access_with_invalid_token(self, test_client):
        """Test accessing protected endpoint with invalid token"""
        test_client.cookies.clear()
        headers = {"Authorization": "Bearer invalid_token"}
        response = test_client.get("/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("user") is None

    def test_token_refresh(self, test_client, test_user):
        """Test token refresh functionality — tokens are HttpOnly cookies"""
        # Login to get tokens (sets cookies in TestClient jar)
        login_response = test_client.post(
            "/auth/login",
            json={
                "username": test_user["username"],
                "password": test_user["password"]
            }
        )
        assert login_response.status_code == 200
        # Refresh via cookie-based auth (refresh_token cookie sent automatically)
        response = test_client.post("/auth/refresh")
        assert response.status_code == 200
        # New access token is set in cookies
        set_cookie = response.headers.get("set-cookie", "")
        assert "access_token" in set_cookie


class TestLogout:
    """Test logout functionality"""

    def test_successful_logout(self, test_client, auth_token, auth_headers):
        """Test successful logout"""
        response = test_client.post("/auth/logout", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify token is blacklisted (optional auth returns user=None)
        me_response = test_client.get("/auth/me", headers=auth_headers)
        assert me_response.status_code == 200
        assert me_response.json().get("user") is None


class TestJWTSecurity:
    """Test JWT security edge cases"""

    def test_blacklisted_token_rejected_after_logout(self, test_client, test_user):
        """Token used after logout should return user=None for /auth/me"""
        import re
        # Login — tokens set as HttpOnly cookies
        login = test_client.post("/auth/login", json={
            "username": test_user["username"],
            "password": test_user["password"]
        })
        # Parse access_token from Set-Cookie response header (HttpOnly not in .cookies)
        match = re.search(r"access_token=([^;]+)", login.headers.get("set-cookie", ""))
        assert match, "No access_token cookie in login response"
        token = match.group(1)

        # Logout — clears the cookie and blacklists the token
        test_client.post("/auth/logout")

        # Try using the blacklisted token via Authorization header (no cookie present)
        response = test_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json().get("user") is None

    def test_expired_token_rejected(self, test_client):
        """A manually crafted expired token should return user=None for /auth/me"""
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone
        expired_token = pyjwt.encode(
            {
                "sub": "testuser",
                "email": "test@example.com",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
                "iat": datetime.now(timezone.utc) - timedelta(hours=2),
                "iss": "smart-ai-tutor",
                "aud": "smart-ai-tutor-api",
                "type": "access",
                "jti": "test-expired-jti"
            },
            "test-secret-key-for-testing-only",
            algorithm="HS256"
        )
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = test_client.get("/auth/me", headers=headers)
        assert response.status_code == 200
        assert response.json().get("user") is None

    def test_malformed_token_rejected(self, test_client):
        """Garbage token string should return user=None for /auth/me"""
        headers = {"Authorization": "Bearer not.a.valid.jwt.at.all"}
        response = test_client.get("/auth/me", headers=headers)
        assert response.status_code == 200
        assert response.json().get("user") is None

    def test_token_type_mismatch_rejected(self, test_client, test_user):
        """Using a refresh token as an access token should return user=None for /auth/me"""
        import re
        # Login — tokens set as HttpOnly cookies
        login = test_client.post("/auth/login", json={
            "username": test_user["username"],
            "password": test_user["password"]
        })
        # Parse refresh_token from Set-Cookie response header
        set_cookie = login.headers.get("set-cookie", "")
        match = re.search(r"refresh_token=([^;]+)", set_cookie)
        assert match, "No refresh_token found in login cookies"
        refresh_token = match.group(1)

        # Logout first — this clears auth cookies so Authorization header is used
        test_client.post("/auth/logout")

        # Using refresh token as access token must return 401
        # (Cookie is cleared so only the Authorization header is checked)
        response = test_client.get("/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})
        assert response.status_code == 200
        assert response.json().get("user") is None

    def test_refresh_token_revoked_after_logout(self, test_client, test_user):
        """A stolen refresh token must stop working the moment the user logs out,
        not just when it eventually expires up to 7 days later."""
        import re
        test_client.cookies.clear()
        login = test_client.post("/auth/login", json={
            "username": test_user["username"],
            "password": test_user["password"]
        })
        set_cookie = login.headers.get("set-cookie", "")
        match = re.search(r"refresh_token=([^;]+)", set_cookie)
        assert match, "No refresh_token found in login cookies"
        refresh_token = match.group(1)

        logout_response = test_client.post("/auth/logout")
        assert logout_response.status_code == 200

        # Replay the (now revoked) refresh token directly against /auth/refresh
        test_client.cookies.clear()
        response = test_client.post("/auth/refresh", cookies={"refresh_token": refresh_token})
        assert response.status_code == 401

        test_client.cookies.clear()

    def test_refresh_token_rotates_and_old_one_is_rejected(self, test_client, test_user):
        """Refresh tokens are single-use: once rotated, the pre-rotation token
        must be rejected even though it hasn't expired yet."""
        import re
        test_client.cookies.clear()
        login = test_client.post("/auth/login", json={
            "username": test_user["username"],
            "password": test_user["password"]
        })
        set_cookie = login.headers.get("set-cookie", "")
        match = re.search(r"refresh_token=([^;]+)", set_cookie)
        assert match, "No refresh_token found in login cookies"
        old_refresh_token = match.group(1)

        first_refresh = test_client.post("/auth/refresh")
        assert first_refresh.status_code == 200

        # Replaying the pre-rotation refresh token must now be rejected
        test_client.cookies.clear()
        replay = test_client.post("/auth/refresh", cookies={"refresh_token": old_refresh_token})
        assert replay.status_code == 401

        test_client.cookies.clear()
