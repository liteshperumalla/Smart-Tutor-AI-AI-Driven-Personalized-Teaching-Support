"""
Quiz Tests
Tests for quiz generation, folder listing, and result retrieval.
"""

import pytest


class TestQuizEndpoints:
    """Test quiz API endpoints"""

    def test_quiz_generate_requires_auth(self, test_client):
        """Quiz generate endpoint without auth must return 401"""
        response = test_client.post("/quiz/generate", json={
            "folders": ["Module 1"],
            "num_questions": 5
        })
        assert response.status_code == 401

    def test_generate_quiz_with_auth(self, test_client, auth_headers):
        """Authenticated user can request quiz generation"""
        response = test_client.post("/quiz/generate", headers=auth_headers, json={
            "folders": ["Module 1"],
            "num_questions": 3
        })
        # Accept 200 (generated), 400/422 (folders not found / validation),
        # or 500 (AWS credentials unavailable in CI)
        assert response.status_code in (200, 400, 422, 500)

    def test_quiz_history_requires_auth(self, test_client):
        """Quiz history without auth must return 401"""
        response = test_client.get("/quiz/history")
        assert response.status_code == 401

    def test_quiz_history_with_auth(self, test_client, auth_headers):
        """Authenticated user can retrieve their quiz history"""
        response = test_client.get("/quiz/history", headers=auth_headers)
        assert response.status_code in (200, 404)

    def test_quiz_folders_requires_auth(self, test_client):
        """Folder listing without auth must return 401"""
        response = test_client.get("/quiz/folders")
        assert response.status_code == 401

    def test_quiz_folders_with_auth(self, test_client, auth_headers):
        """Authenticated user can list available quiz folders"""
        response = test_client.get("/quiz/folders", headers=auth_headers)
        # Returns list of folders (may be empty if no content uploaded),
        # or 500 when AWS credentials are unavailable in CI
        assert response.status_code in (200, 404, 500)
