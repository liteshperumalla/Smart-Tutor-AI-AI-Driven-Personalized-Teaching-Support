import sys
import types

from backend.agents import neo4j_client


class _FakeResponse:
    def raise_for_status(self):
        return None


def test_resume_aura_instance_resumes_stopped_instance(monkeypatch):
    statuses = iter(["stopped", "running"])
    post_calls = []

    monkeypatch.setattr(neo4j_client.config, "NEO4J_AURA_INSTANCE_ID", "instance-123")
    monkeypatch.setattr(neo4j_client, "_get_aura_token", lambda: "token")
    monkeypatch.setattr(neo4j_client, "_get_instance_status", lambda: next(statuses))

    fake_requests = types.SimpleNamespace(
        post=lambda *args, **kwargs: post_calls.append((args, kwargs)) or _FakeResponse()
    )
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setattr(neo4j_client.time, "sleep", lambda _seconds: None)

    assert neo4j_client._resume_aura_instance(max_wait=1) is True
    assert len(post_calls) == 1
    assert post_calls[0][0][0].endswith("/resume")


def test_verify_connectivity_retries_after_aura_resume(monkeypatch):
    class FailingDriver:
        def verify_connectivity(self):
            raise RuntimeError("Service unavailable while Aura instance is paused")

    class HealthyDriver:
        def verify_connectivity(self):
            return None

    client = neo4j_client.Neo4jClient.__new__(neo4j_client.Neo4jClient)
    client.driver = FailingDriver()

    reconnects = []
    monkeypatch.setattr(neo4j_client, "_resume_aura_instance", lambda: True)

    def fake_reconnect():
        reconnects.append(True)
        client.driver = HealthyDriver()

    monkeypatch.setattr(client, "_reconnect", fake_reconnect)

    assert client.verify_connectivity() is True
    assert reconnects == [True]
