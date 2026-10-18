"""
Ambassador Pattern Client Implementation (Pattern 130)
Routes outbound egress traffic through a co-located Envoy ambassador proxy container,
offloading mutual TLS, retries, circuit breaking, and network observability.
"""

import logging
import os
from typing import Any, Dict, Optional
import urllib.parse
import urllib.request
import json

logger = logging.getLogger(__name__)


class AmbassadorConfig:
    """Configuration settings for the Ambassador sidecar proxy."""

    def __init__(self):
        self.enabled = os.getenv("AMBASSADOR_ENABLED", "false").lower() in ("true", "1", "yes")
        self.llm_egress_base = os.getenv("AMBASSADOR_LLM_HOST", "http://127.0.0.1:9001").rstrip("/")
        self.vector_egress_base = os.getenv("AMBASSADOR_VECTOR_HOST", "http://127.0.0.1:9002").rstrip("/")
        self.admin_url = os.getenv("AMBASSADOR_ADMIN_URL", "http://127.0.0.1:9901").rstrip("/")
        self.connect_timeout_seconds = float(os.getenv("AMBASSADOR_TIMEOUT", "5.0"))


class AmbassadorClient:
    """
    Client adapter facilitating outbound calls through the co-located Envoy Ambassador container.
    Provides transparent failover when running in local development or unit testing.
    """

    def __init__(self, config: Optional[AmbassadorConfig] = None):
        self.config = config or AmbassadorConfig()

    @property
    def is_enabled(self) -> bool:
        """Check if Ambassador egress routing is active."""
        return self.config.enabled

    def get_egress_endpoint(self, service_type: str, path: str, direct_fallback_url: str) -> str:
        """
        Resolve target URL. When Ambassador is enabled, routes via localhost sidecar listener.
        When disabled, routes directly to target service.
        
        Args:
            service_type: 'llm', 'vector', or 'generic'
            path: Target request path (e.g. '/model/anthropic.claude-v2/invoke')
            direct_fallback_url: Direct external endpoint (e.g. 'https://bedrock-runtime.us-east-1.amazonaws.com/...')
        """
        if not self.config.enabled:
            return direct_fallback_url

        clean_path = "/" + path.lstrip("/")
        if service_type.lower() == "llm":
            return f"{self.config.llm_egress_base}{clean_path}"
        elif service_type.lower() == "vector":
            return f"{self.config.vector_egress_base}{clean_path}"
        return direct_fallback_url

    def check_health(self) -> Dict[str, Any]:
        """
        Query Envoy Ambassador sidecar admin /ready endpoint.
        Returns health dict or fallback info when disabled.
        """
        if not self.config.enabled:
            return {
                "status": "disabled",
                "message": "Ambassador proxy disabled (using direct egress)",
                "ready": True,
            }

        ready_url = f"{self.config.admin_url}/ready"
        try:
            req = urllib.request.Request(ready_url, headers={"User-Agent": "SmartAITutor-AmbassadorClient"})
            with urllib.request.urlopen(req, timeout=self.config.connect_timeout_seconds) as resp:
                status_text = resp.read().decode("utf-8").strip()
                is_live = resp.status == 200 and "LIVE" in status_text
                return {
                    "status": "healthy" if is_live else "degraded",
                    "details": status_text,
                    "ready": is_live,
                    "admin_url": ready_url,
                }
        except Exception as exc:
            logger.warning("Ambassador sidecar health check failed: %s", exc)
            return {
                "status": "unreachable",
                "error": str(exc),
                "ready": False,
                "admin_url": ready_url,
            }

    def fetch_egress_metrics(self) -> Optional[str]:
        """Fetch raw Prometheus metrics from the Ambassador sidecar admin socket."""
        if not self.config.enabled:
            return None

        metrics_url = f"{self.config.admin_url}/stats/prometheus"
        try:
            req = urllib.request.Request(metrics_url, headers={"User-Agent": "SmartAITutor-AmbassadorClient"})
            with urllib.request.urlopen(req, timeout=self.config.connect_timeout_seconds) as resp:
                return resp.read().decode("utf-8")
        except Exception as exc:
            logger.warning("Failed to fetch Ambassador metrics: %s", exc)
            return None


# Global singleton instance
_ambassador_client: Optional[AmbassadorClient] = None


def get_ambassador_client() -> AmbassadorClient:
    """Get global AmbassadorClient singleton."""
    global _ambassador_client
    if _ambassador_client is None:
        _ambassador_client = AmbassadorClient()
    return _ambassador_client
