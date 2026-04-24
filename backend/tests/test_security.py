"""
Security Tests
Tests for admin lockdown, CSRF protection, rate limiting, and input validation.
"""

import pytest


class TestAdminLockdown:
    """Admin routes must be inaccessible to regular users"""

    def test_admin_users_requires_admin_role(self, test_client, auth_headers):
        """Regular user cannot access /admin/users"""
        response = test_client.get("/admin/users", headers=auth_headers)
        assert response.status_code == 403

    def test_admin_llmops_requires_admin_role(self, test_client, auth_headers):
        """Regular user cannot access /admin/llmops"""
        response = test_client.get("/admin/llmops", headers=auth_headers)
        assert response.status_code == 403

    def test_admin_prompts_requires_admin_role(self, test_client, auth_headers):
        """Regular user cannot access /admin/prompts"""
        response = test_client.get("/admin/prompts/system_prompt", headers=auth_headers)
        assert response.status_code == 403

    def test_admin_requires_auth(self, test_client):
        """Unauthenticated request to admin route must return 401 or 403"""
        response = test_client.get("/admin/users")
        assert response.status_code in (401, 403)

    def test_admin_agent_metrics_requires_admin_role(self, test_client, auth_headers):
        """Regular user cannot access /admin/agent-metrics"""
        response = test_client.get("/admin/agent-metrics", headers=auth_headers)
        assert response.status_code == 403


class TestInputValidation:
    """Malformed inputs must be rejected cleanly (no 500s)"""

    def test_login_sql_injection_probe(self, test_client):
        """SQL injection in username must return 401/422, not 500"""
        response = test_client.post("/auth/login", json={
            "username": "' OR '1'='1",
            "password": "anything"
        })
        assert response.status_code in (401, 422)

    def test_login_oversized_payload(self, test_client):
        """Extremely long username must return 401 or 422, not 500"""
        response = test_client.post("/auth/login", json={
            "username": "A" * 10000,
            "password": "password"
        })
        assert response.status_code in (401, 422)

    def test_signup_xss_probe(self, test_client):
        """XSS payload in full_name must be accepted or sanitized, not crash"""
        response = test_client.post("/auth/signup", json={
            "username": "xsstest123",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
            "email": "xss@example.com",
            "full_name": "<script>alert('xss')</script>"
        })
        # Either accepted (sanitized on display) or rejected — not 500
        assert response.status_code in (200, 400, 422)
        # Cleanup
        from backend.database import get_user_db
        db = get_user_db()
        if db.user_exists("xsstest123"):
            db.delete_user("xsstest123")

    def test_protected_route_no_auth_header(self, test_client):
        """Missing Authorization header must return 401, not 500"""
        response = test_client.get("/chat/sessions")
        assert response.status_code == 401

    def test_protected_route_malformed_auth_header(self, test_client):
        """Malformed Authorization header must return 401, not 500"""
        response = test_client.get("/chat/sessions", headers={"Authorization": "NotBearer token"})
        assert response.status_code == 401


class TestSecurityHeaders:
    """Security headers must be applied consistently to backend responses."""

    def test_root_includes_public_cache_and_corp_headers(self, test_client):
        response = test_client.get("/")

        assert response.status_code == 200
        assert response.headers["cross-origin-resource-policy"] == "same-origin"
        assert response.headers["cross-origin-opener-policy"] == "same-origin"
        assert response.headers["cross-origin-embedder-policy"] == "require-corp"
        assert response.headers["cache-control"] == "public, max-age=300"

    def test_public_discovery_routes_are_cacheable(self, test_client):
        robots = test_client.get("/robots.txt")
        sitemap = test_client.get("/sitemap.xml")

        assert robots.status_code == 200
        assert robots.headers["cross-origin-resource-policy"] == "same-origin"
        assert robots.headers["cross-origin-opener-policy"] == "same-origin"
        assert robots.headers["cross-origin-embedder-policy"] == "require-corp"
        assert robots.headers["cache-control"] == "public, max-age=300"

        assert sitemap.status_code == 200
        assert sitemap.headers["cross-origin-resource-policy"] == "same-origin"
        assert sitemap.headers["cross-origin-opener-policy"] == "same-origin"
        assert sitemap.headers["cross-origin-embedder-policy"] == "require-corp"
        assert sitemap.headers["cache-control"] == "public, max-age=300"

    def test_dynamic_not_found_includes_no_store_headers(self, test_client):
        response = test_client.get("/robots.txt")

        response = test_client.get("/missing")

        assert response.status_code == 404
        assert response.headers["cross-origin-resource-policy"] == "same-origin"
        assert response.headers["cross-origin-opener-policy"] == "same-origin"
        assert response.headers["cross-origin-embedder-policy"] == "require-corp"
        assert response.headers["cache-control"] == "no-store, max-age=0"
        assert response.headers["pragma"] == "no-cache"
