"""
Pytest Configuration and Fixtures
Shared test fixtures and configuration for the test suite
"""

import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "true"
os.environ["STORAGE_BACKEND"] = "filesystem"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["RATE_LIMIT_ENABLED"] = "false"  # Disable rate limiting in tests
os.environ["SMTP_SERVER"] = ""  # Disable email sending in tests

from backend.api.main import app
from backend.database import get_user_db
from backend.auth_service import get_auth_service


@pytest.fixture(scope="session")
def test_client():
    """Create a test client for the FastAPI app"""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
def auth_service():
    """Get auth service instance"""
    return get_auth_service()


@pytest.fixture(scope="function")
def test_user(auth_service):
    """Create a test user for authentication tests"""
    username = "testuser"
    password = "TestPass123!"
    email = "test@example.com"

    # Clean up if user exists
    user_db = get_user_db()
    if user_db.user_exists(username):
        user_db.delete_user(username)

    # Create test user
    user = auth_service.register_user(
        username=username,
        password=password,
        confirm_password=password,
        email=email
    )

    # Mark email as verified so tests can log in without SMTP
    user_record = user_db.get_user(username)
    metadata = user_record.get("metadata", {})
    metadata["email_verified"] = True
    user_db.update_user(username, {"metadata": metadata})

    yield {
        "username": username,
        "password": password,
        "email": email,
        "user": user
    }

    # Cleanup
    if user_db.user_exists(username):
        user_db.delete_user(username)


@pytest.fixture(scope="function")
def auth_token(test_client, test_user):
    """Get authentication token for test user.

    Tokens are set as HttpOnly cookies (not in JSON body).
    Extracts the access_token from the TestClient's cookie jar.
    """
    response = test_client.post(
        "/auth/login",
        json={
            "username": test_user["username"],
            "password": test_user["password"]
        }
    )
    assert response.status_code == 200
    # Tokens are HttpOnly cookies; parse from Set-Cookie response header
    import re
    match = re.search(r"access_token=([^;]+)", response.headers.get("set-cookie", ""))
    assert match, f"No access_token cookie in login response. Body: {response.json()}"
    return match.group(1)


@pytest.fixture(scope="function")
def auth_headers(auth_token):
    """Get authorization headers with token"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test"""
    yield
    # Cleanup code here if needed


@pytest.fixture(scope="session")
def mock_chat_data():
    """Mock chat data for testing"""
    return {
        "query": "What is machine learning?",
        "expected_response_contains": ["machine", "learning", "algorithm"]
    }


@pytest.fixture(scope="session")
def mock_quiz_data():
    """Mock quiz data for testing"""
    return {
        "folders": ["Module 1", "Module 2"],
        "num_questions": 5
    }
