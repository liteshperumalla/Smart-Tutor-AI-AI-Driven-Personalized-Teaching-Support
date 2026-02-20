"""
Chat API Tests
Tests for chat session management and message handling
"""

import pytest


class TestChatSessions:
    """Test chat session management"""

    def test_create_session(self, test_client, auth_headers):
        """Test creating a new chat session"""
        response = test_client.post(
            "/chat/sessions",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "session" in data
        assert "id" in data["session"]
        assert "title" in data["session"]

    def test_create_session_with_title(self, test_client, auth_headers):
        """Test creating session with custom title"""
        response = test_client.post(
            "/chat/sessions?title=My Custom Chat",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session"]["title"] == "My Custom Chat"

    def test_list_sessions(self, test_client, auth_headers):
        """Test listing user's chat sessions"""
        # Create a session first
        test_client.post("/chat/sessions", headers=auth_headers)

        # List sessions
        response = test_client.get("/chat/sessions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    def test_get_session(self, test_client, auth_headers):
        """Test getting a specific session"""
        # Create a session
        create_response = test_client.post("/chat/sessions", headers=auth_headers)
        session_id = create_response.json()["session"]["id"]

        # Get the session
        response = test_client.get(
            f"/chat/sessions/{session_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session"]["id"] == session_id

    def test_update_session_title(self, test_client, auth_headers):
        """Test updating session title"""
        # Create a session
        create_response = test_client.post("/chat/sessions", headers=auth_headers)
        session_id = create_response.json()["session"]["id"]

        # Update title
        response = test_client.patch(
            f"/chat/sessions/{session_id}",
            headers=auth_headers,
            json={"title": "Updated Title"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session"]["title"] == "Updated Title"

    def test_delete_session(self, test_client, auth_headers):
        """Test deleting a session"""
        # Create a session
        create_response = test_client.post("/chat/sessions", headers=auth_headers)
        session_id = create_response.json()["session"]["id"]

        # Delete the session
        response = test_client.delete(
            f"/chat/sessions/{session_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify session is deleted
        get_response = test_client.get(
            f"/chat/sessions/{session_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404


class TestChatMessages:
    """Test chat message handling"""

    def test_send_message_requires_auth(self, test_client):
        """Test sending message requires authentication"""
        response = test_client.post(
            "/chat/sessions/test-session/messages",
            json={"query": "Hello"}
        )
        assert response.status_code == 401

    def test_send_message_to_nonexistent_session(self, test_client, auth_headers):
        """Test sending message to nonexistent session"""
        response = test_client.post(
            "/chat/sessions/nonexistent-session/messages",
            headers=auth_headers,
            json={"query": "Hello"}
        )
        assert response.status_code == 404


class TestSessionIsolation:
    """Users must not access each other's sessions"""

    def test_user_cannot_access_other_users_session(self, test_client, auth_headers, auth_service):
        """User A's session must not be accessible by User B"""
        import re
        from backend.database import get_user_db

        user_db = get_user_db()
        username_b = "userb_isolation"

        # Cleanup if exists from a previous run
        if user_db.user_exists(username_b):
            user_db.delete_user(username_b)

        # Create user B
        auth_service.register_user(
            username=username_b,
            password="SecurePass123!",
            confirm_password="SecurePass123!",
            email="userb_isolation@example.com"
        )
        # Mark B's email as verified
        user_b_rec = user_db.get_user(username_b)
        meta_b = user_b_rec.get("metadata", {})
        meta_b["email_verified"] = True
        user_db.update_user(username_b, {"metadata": meta_b})

        # User A creates a session
        session_resp = test_client.post("/chat/sessions", headers=auth_headers)
        assert session_resp.status_code == 200
        session_id = session_resp.json()["session"]["id"]

        # User B logs in
        login_b = test_client.post("/auth/login", json={
            "username": username_b,
            "password": "SecurePass123!"
        })
        # Parse B's access token from Set-Cookie header
        match = re.search(r"access_token=([^;]+)", login_b.headers.get("set-cookie", ""))
        assert match, "No access_token cookie for user B"
        headers_b = {"Authorization": f"Bearer {match.group(1)}"}

        # User B tries to access User A's session — must be 403 or 404
        response = test_client.get(f"/chat/sessions/{session_id}", headers=headers_b)
        assert response.status_code in (403, 404)

        # Cleanup
        if user_db.user_exists(username_b):
            user_db.delete_user(username_b)

    def test_invalid_session_id_returns_404(self, test_client, auth_headers):
        """Non-existent session ID must return 404, not 500"""
        response = test_client.get("/chat/sessions/nonexistent-session-id-xyz", headers=auth_headers)
        assert response.status_code == 404
