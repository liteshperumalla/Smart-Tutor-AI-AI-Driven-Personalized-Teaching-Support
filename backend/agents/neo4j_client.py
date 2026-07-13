"""
Neo4j Knowledge Graph Client
Singleton driver for the Neo4j graph database used by the agent system.
Provides read/write query helpers with automatic session management.
Includes auto-resume for paused Neo4j Aura instances.
"""

from __future__ import annotations

import logging
import time
import threading
from typing import Any, Dict, List, Optional

CONNECTIVITY_ERROR_HINTS = (
    "dns",
    "resolve",
    "connect",
    "refused",
    "unavailable",
    "service",
    "routing",
    "defunct",
    "connection reset",
    "failed to establish",
)

AURA_RESUMABLE_STATES = {"paused", "resuming", "stopped", "starting"}

from backend.config import config

logger = logging.getLogger(__name__)

# ── Aura API helpers ──────────────────────────────────────────────

AURA_API_BASE = "https://api.neo4j.io"
_aura_token_cache: Dict[str, Any] = {"token": None, "expires_at": 0}
_resume_lock = threading.Lock()


def _get_aura_token() -> Optional[str]:
    """Get an OAuth bearer token for the Neo4j Aura API (cached for 50 min)."""
    if not config.NEO4J_AURA_API_CLIENT_ID or not config.NEO4J_AURA_API_CLIENT_SECRET:
        return None

    now = time.time()
    if _aura_token_cache["token"] and now < _aura_token_cache["expires_at"]:
        return _aura_token_cache["token"]

    import requests

    try:
        resp = requests.post(
            f"{AURA_API_BASE}/oauth/token",
            auth=(config.NEO4J_AURA_API_CLIENT_ID, config.NEO4J_AURA_API_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        _aura_token_cache["token"] = token
        _aura_token_cache["expires_at"] = now + expires_in - 600  # refresh 10 min early
        return token
    except Exception as exc:
        logger.warning("Failed to get Aura API token: %s", exc)
        return None


def _get_instance_status() -> Optional[str]:
    """Check Neo4j Aura instance status (running, paused, resuming, etc.)."""
    if not config.NEO4J_AURA_INSTANCE_ID:
        return None

    token = _get_aura_token()
    if not token:
        return None

    import requests

    try:
        resp = requests.get(
            f"{AURA_API_BASE}/v1/instances/{config.NEO4J_AURA_INSTANCE_ID}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        instance = data.get("data", data)
        status = str(instance.get("status") or instance.get("state") or "unknown").lower()
        logger.info("Aura instance %s status: %s", config.NEO4J_AURA_INSTANCE_ID, status)
        return status
    except Exception as exc:
        logger.warning("Failed to get Aura instance status: %s", exc)
        return None


def _resume_aura_instance(max_wait: int = 20) -> bool:
    """Trigger an Aura resume and do a brief best-effort check -- WITHOUT
    blocking for anywhere near the full resume duration.

    Real Aura resume takes 7-12 minutes (the dedicated Neo4j Aura Resume
    Guard workflow's poll timeout was deliberately bumped to 900s after a
    real run measured 420s) -- far longer than any request should ever
    block for. The old 120s default couldn't succeed on a genuine cold
    pause either, it just wasted two minutes finding that out. This
    fires the resume request and polls briefly (default 20s) purely to
    catch the fast case where the instance was already resuming when we
    got here; on the much more common cold-pause case, callers get a
    quick "not ready yet" and should degrade gracefully -- see
    profile.py's _graph_profile, which already falls back to an empty
    profile on any exception here -- rather than hang. Keeping the
    instance warm in steady state is the scheduled resume-guard
    workflow's job, not this in-request path's.

    Uses a lock to prevent multiple concurrent resume attempts.
    Returns True if the instance is running, False otherwise.
    """
    if not config.NEO4J_AURA_INSTANCE_ID:
        return False

    with _resume_lock:
        status = _get_instance_status()
        if status == "running":
            return True
        if status not in AURA_RESUMABLE_STATES:
            logger.warning("Aura instance in unexpected state: %s", status)
            return False

        if status in {"paused", "stopped"}:
            token = _get_aura_token()
            if not token:
                return False

            import requests

            try:
                resp = requests.post(
                    f"{AURA_API_BASE}/v1/instances/{config.NEO4J_AURA_INSTANCE_ID}/resume",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={},
                    timeout=10,
                )
                resp.raise_for_status()
                logger.info("Aura resume request sent for %s (status=%s)", config.NEO4J_AURA_INSTANCE_ID, status)
            except Exception as exc:
                logger.warning("Failed to resume Aura instance: %s", exc)
                return False

        # Poll until running or timeout
        start = time.time()
        while time.time() - start < max_wait:
            time.sleep(10)
            status = _get_instance_status()
            if status == "running":
                logger.info("Aura instance is now running (waited %.0fs)", time.time() - start)
                return True
            logger.info("Aura instance status: %s (waiting...)", status)

        logger.warning("Aura instance did not resume within %ds", max_wait)
        return False


# ── Neo4j Client ──────────────────────────────────────────────────

class Neo4jClient:
    """Thread-safe singleton wrapper around the Neo4j Python driver."""

    _instance: Optional[Neo4jClient] = None

    def __init__(self) -> None:
        from neo4j import GraphDatabase

        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
            connection_timeout=5,           # Fail fast if server unreachable
            max_transaction_retry_time=5,    # Don't retry for 30s+ on failures
        )
        logger.info("Neo4j driver initialised (%s)", config.NEO4J_URI)

    # ── Query helpers ─────────────────────────────────────────────

    def execute_write(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        return self._execute_with_resume(is_write=True, query=query, params=params)

    def execute_read(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        return self._execute_with_resume(is_write=False, query=query, params=params)

    def _execute_with_resume(
        self, is_write: bool, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a query, auto-resuming Aura if the first attempt fails."""
        try:
            return self._execute(is_write, query, params)
        except Exception as first_err:
            # Check if this looks like a connectivity failure (paused instance)
            err_str = str(first_err).lower()
            if any(k in err_str for k in CONNECTIVITY_ERROR_HINTS):
                logger.info("Neo4j connection failed, attempting Aura auto-resume...")
                if _resume_aura_instance():
                    # Recreate the driver after resume
                    self._reconnect()
                    return self._execute(is_write, query, params)
            raise

    def _execute(
        self, is_write: bool, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            if is_write:
                return session.execute_write(
                    lambda tx: tx.run(query, params or {}).data()
                )
            else:
                return session.execute_read(
                    lambda tx: tx.run(query, params or {}).data()
                )

    def _reconnect(self) -> None:
        """Close and recreate the driver (after Aura resumes, DNS changes)."""
        from neo4j import GraphDatabase

        try:
            self.driver.close()
        except Exception:
            pass
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
            connection_timeout=5,
            max_transaction_retry_time=5,
        )
        logger.info("Neo4j driver reconnected")

    # ── Lifecycle ─────────────────────────────────────────────────

    def verify_connectivity(self) -> bool:
        try:
            self.driver.verify_connectivity()
            return True
        except Exception as exc:
            logger.warning("Neo4j connectivity check failed: %s", exc)
            if any(k in str(exc).lower() for k in CONNECTIVITY_ERROR_HINTS):
                logger.info("Neo4j connectivity check triggering Aura auto-resume...")
                if _resume_aura_instance():
                    self._reconnect()
                    try:
                        self.driver.verify_connectivity()
                        return True
                    except Exception as retry_exc:
                        logger.warning("Neo4j connectivity still failing after Aura resume: %s", retry_exc)
            return False

    def close(self) -> None:
        self.driver.close()
        logger.info("Neo4j driver closed")


def get_neo4j_client() -> Neo4jClient:
    """Return (or create) the singleton Neo4jClient."""
    if Neo4jClient._instance is None:
        Neo4jClient._instance = Neo4jClient()
    return Neo4jClient._instance
