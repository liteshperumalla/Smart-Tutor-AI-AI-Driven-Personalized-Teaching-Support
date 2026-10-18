"""Unit tests for Ambassador Pattern Client (Pattern 130)."""

import os
from unittest.mock import patch, MagicMock
import pytest

from backend.services.ambassador_client import AmbassadorClient, AmbassadorConfig, get_ambassador_client


def test_ambassador_disabled_by_default_in_local():
    """Verify Ambassador routes directly when disabled."""
    with patch.dict(os.environ, {"AMBASSADOR_ENABLED": "false"}):
        client = AmbassadorClient()
        assert not client.is_enabled

        direct_url = "https://bedrock-runtime.us-east-1.amazonaws.com/model/invoke"
        endpoint = client.get_egress_endpoint("llm", "/model/invoke", direct_fallback_url=direct_url)
        assert endpoint == direct_url


def test_ambassador_routes_through_localhost_when_enabled():
    """Verify Ambassador routes egress requests to co-located sidecar listeners when enabled."""
    with patch.dict(os.environ, {
        "AMBASSADOR_ENABLED": "true",
        "AMBASSADOR_LLM_HOST": "http://127.0.0.1:9001",
        "AMBASSADOR_VECTOR_HOST": "http://127.0.0.1:9002",
    }):
        config = AmbassadorConfig()
        client = AmbassadorClient(config)
        assert client.is_enabled

        # LLM egress route
        llm_endpoint = client.get_egress_endpoint(
            "llm",
            "/model/anthropic.claude-v2/invoke",
            direct_fallback_url="https://bedrock-runtime.us-east-1.amazonaws.com/model/anthropic.claude-v2/invoke"
        )
        assert llm_endpoint == "http://127.0.0.1:9001/model/anthropic.claude-v2/invoke"

        # Vector egress route
        vector_endpoint = client.get_egress_endpoint(
            "vector",
            "/v1/vectors/search",
            direct_fallback_url="http://redis.smart-ai-tutor:6379"
        )
        assert vector_endpoint == "http://127.0.0.1:9002/v1/vectors/search"


def test_ambassador_health_check_when_disabled():
    """Verify health check reports disabled status without error."""
    with patch.dict(os.environ, {"AMBASSADOR_ENABLED": "false"}):
        client = AmbassadorClient()
        health = client.check_health()
        assert health["status"] == "disabled"
        assert health["ready"] is True


def test_ambassador_health_check_when_live():
    """Verify health check queries Envoy admin endpoint when enabled."""
    with patch.dict(os.environ, {
        "AMBASSADOR_ENABLED": "true",
        "AMBASSADOR_ADMIN_URL": "http://127.0.0.1:9901"
    }):
        client = AmbassadorClient()

        # Mock urllib.request.urlopen returning 200 LIVE
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"LIVE\n"
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            health = client.check_health()
            assert health["status"] == "healthy"
            assert health["ready"] is True


def test_ambassador_metrics_fetching():
    """Verify metrics fetching contacts admin socket and returns Prometheus text."""
    with patch.dict(os.environ, {
        "AMBASSADOR_ENABLED": "true",
        "AMBASSADOR_ADMIN_URL": "http://127.0.0.1:9901"
    }):
        client = AmbassadorClient()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"# TYPE envoy_cluster_upstream_cx_total counter\nenvoy_cluster_upstream_cx_total 42\n"
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            metrics = client.fetch_egress_metrics()
            assert "envoy_cluster_upstream_cx_total 42" in metrics
