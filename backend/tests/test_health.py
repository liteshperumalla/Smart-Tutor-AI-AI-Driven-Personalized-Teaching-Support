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
        # /health returns 503 when a core dependency (database, redis,
        # bedrock, neo4j, s3) is genuinely unreachable, so deploy/rollback
        # gates can detect real failures instead of always seeing 200.
        # This test environment has no live AWS/Neo4j credentials, so 503
        # is an expected, correct outcome here -- the contract under test
        # is the response shape, not a specific dependency-health result.
        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert "environment" in data
        assert "version" in data

    def test_readiness_check(self, test_client):
        """Test the deploy/rollback readiness probe"""
        response = test_client.get("/ready")
        # Postgres and Redis are real service containers in this test
        # environment, so /ready (which checks only those two) should be
        # genuinely ready.
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "checks" in data
        assert set(data["checks"].keys()) == {"database", "redis"}

    def test_detailed_health_check(self, test_client):
        """Test detailed health check"""
        response = test_client.get("/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Response uses "checks" key (or "components" in some versions)
        assert "checks" in data or "components" in data
        checks = data.get("checks") or data.get("components")
        assert isinstance(checks, dict)
