"""/metrics accepts the admin's session cookie (the admin evaluation dashboard
fetches it from the browser), and applies the same admin rule as the admin API.

Regression: the endpoint only read an Authorization header, so the dashboard's
cookie-authenticated request got 401 and its website-metrics cards never loaded.
"""

from backend.database import get_user_db


def _make_admin(username: str) -> None:
    db = get_user_db()
    metadata = db.get_user(username).get("metadata") or {}
    metadata["is_admin"] = True
    db.update_user(username, {"metadata": metadata})


def test_metrics_rejects_unauthenticated_requests(test_client):
    test_client.cookies.clear()
    assert test_client.get("/metrics").status_code == 401


def test_metrics_requires_admin_for_cookie_sessions(test_client, auth_token):
    test_client.cookies.set("access_token", auth_token)
    assert test_client.get("/metrics").status_code == 403


def test_metrics_serves_admin_cookie_session(test_client, test_user, auth_token):
    _make_admin(test_user["username"])
    test_client.cookies.set("access_token", auth_token)
    response = test_client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
