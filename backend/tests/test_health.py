"""
Health Check Tests
Tests for health and monitoring endpoints
"""

import pytest


class TestHealthEndpoints:
    """Test health check endpoints"""

    def test_root_endpoint(self, test_client):
        """Test root endpoint"""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data

    def test_health_check(self, test_client):
        """Test basic health check"""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "environment" in data
        assert "version" in data

    def test_detailed_health_check(self, test_client):
        """Test detailed health check"""
        response = test_client.get("/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert isinstance(data["components"], dict)
