"""
Prompt Registry — versioned prompt template management.

Implements the Prompt Versioning & A/B Testing pattern from LLMOps:
- Register named prompts with semantic versions (v1, v2, …)
- Retrieve a specific version or the latest
- Track per-version usage and user satisfaction votes

Storage Backend (selected via PROMPT_REGISTRY_BACKEND env var):
  - "redis"    : Redis hash (distributed, survives pod restarts)  ← production
  - "dynamodb" : DynamoDB item (serverless, durable)              ← serverless
  - "file"     : Local JSON file (dev / offline fallback)         ← default

Set PROMPT_REGISTRY_BACKEND=redis in .env / Secrets Manager to enable
distributed storage in production.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.logger import get_logger

logger = get_logger(__name__)

REGISTRY_FILE = Path("logs/prompt_registry.json")
_BACKEND = os.getenv("PROMPT_REGISTRY_BACKEND", "file").lower()
_REDIS_KEY = "smart_ai_tutor:prompt_registry"
_DYNAMO_TABLE = os.getenv("PROMPT_REGISTRY_DYNAMO_TABLE", "smart-tutor-prompt-registry")
_DYNAMO_PK = "prompt_registry_singleton"


# =============================================================================
# Storage backend implementations
# =============================================================================

class _FileBackend:
    """Local JSON file — dev/offline only. Not safe across multiple pods."""

    def load(self) -> Dict[str, Any]:
        REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        if REGISTRY_FILE.exists():
            try:
                return json.loads(REGISTRY_FILE.read_text())
            except Exception as exc:
                logger.warning("Prompt registry file load failed: %s", exc)
        return {}

    def save(self, data: Dict[str, Any]) -> None:
        try:
            REGISTRY_FILE.write_text(json.dumps(data, indent=2))
        except Exception as exc:
            logger.warning("Prompt registry file save failed: %s", exc)

    @property
    def name(self) -> str:
        return "file"


class _RedisBackend:
    """
    Redis HASH backend — distributed, survives pod restarts.
    Entire registry is stored as a single JSON string in a Redis key.
    Requires REDIS_HOST / REDIS_PORT / REDIS_PASSWORD to be configured.
    """

    def __init__(self) -> None:
        import redis as _redis
        from backend.config import config

        self._client = _redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            password=config.REDIS_PASSWORD or None,
            ssl=config.REDIS_SSL,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
        # Verify connection
        self._client.ping()
        logger.info("PromptRegistry: connected to Redis backend (%s:%s)", config.REDIS_HOST, config.REDIS_PORT)

    def load(self) -> Dict[str, Any]:
        try:
            raw = self._client.get(_REDIS_KEY)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.warning("PromptRegistry Redis load failed: %s", exc)
        return {}

    def save(self, data: Dict[str, Any]) -> None:
        try:
            self._client.set(_REDIS_KEY, json.dumps(data))
        except Exception as exc:
            logger.warning("PromptRegistry Redis save failed: %s", exc)

    @property
    def name(self) -> str:
        return "redis"


class _DynamoBackend:
    """
    DynamoDB backend — serverless, durable, strongly consistent.
    Requires AWS credentials and PROMPT_REGISTRY_DYNAMO_TABLE to be set.
    """

    def __init__(self) -> None:
        import boto3
        self._table = boto3.resource("dynamodb").Table(_DYNAMO_TABLE)
        logger.info("PromptRegistry: connected to DynamoDB backend (table=%s)", _DYNAMO_TABLE)

    def load(self) -> Dict[str, Any]:
        try:
            resp = self._table.get_item(Key={"pk": _DYNAMO_PK})
            item = resp.get("Item", {})
            if "data" in item:
                return json.loads(item["data"])
        except Exception as exc:
            logger.warning("PromptRegistry DynamoDB load failed: %s", exc)
        return {}

    def save(self, data: Dict[str, Any]) -> None:
        try:
            self._table.put_item(Item={"pk": _DYNAMO_PK, "data": json.dumps(data)})
        except Exception as exc:
            logger.warning("PromptRegistry DynamoDB save failed: %s", exc)

    @property
    def name(self) -> str:
        return "dynamodb"


def _build_backend() -> _FileBackend | _RedisBackend | _DynamoBackend:
    """Instantiate the configured storage backend, falling back to file on error."""
    if _BACKEND == "redis":
        try:
            return _RedisBackend()
        except Exception as exc:
            logger.warning(
                "PromptRegistry: Redis backend init failed (%s) — falling back to file backend", exc
            )
    elif _BACKEND == "dynamodb":
        try:
            return _DynamoBackend()
        except Exception as exc:
            logger.warning(
                "PromptRegistry: DynamoDB backend init failed (%s) — falling back to file backend", exc
            )
    if _BACKEND not in ("file", "redis", "dynamodb"):
        logger.warning("Unknown PROMPT_REGISTRY_BACKEND=%r — using file backend", _BACKEND)
    return _FileBackend()


# =============================================================================
# PromptRegistry
# =============================================================================

class PromptRegistry:
    """
    Thread-safe versioned prompt store with pluggable storage backend.

    Each prompt name maps to a list of version entries::

        {
          "rag_system": [
            {"name": "rag_system", "version": "v1", "template": "...", ...},
            {"name": "rag_system", "version": "v2", "template": "...", ...},
          ]
        }

    The last element in the list is always the 'latest' version.
    """

    def __init__(self) -> None:
        self._backend = _build_backend()
        self._lock = threading.Lock()
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._load()
        logger.info("PromptRegistry initialized (backend=%s)", self._backend.name)

    # ── Persistence ───────────────────────────────────────────────────

    def _load(self) -> None:
        self._data = self._backend.load()

    def _save(self) -> None:
        self._backend.save(self._data)

    # ── CRUD ──────────────────────────────────────────────────────────

    def register(
        self,
        name: str,
        template: str,
        description: str = "",
        variables: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Register a new version for *name*.  Versions are auto-numbered v1, v2, …"""
        with self._lock:
            versions = self._data.get(name, [])
            version = f"v{len(versions) + 1}"
            entry: Dict[str, Any] = {
                "name": name,
                "version": version,
                "template": template,
                "description": description,
                "variables": variables or [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "metrics": {"uses": 0, "thumbs_up": 0, "thumbs_down": 0},
            }
            versions.append(entry)
            self._data[name] = versions
            self._save()
            logger.info("Prompt '%s' registered as %s (backend=%s)", name, version, self._backend.name)
            return entry

    def get(self, name: str, version: str = "latest") -> Optional[Dict[str, Any]]:
        """Retrieve a prompt entry by name + version (default: latest)."""
        versions = self._data.get(name, [])
        if not versions:
            return None
        if version == "latest":
            return versions[-1]
        return next((v for v in versions if v["version"] == version), None)

    def format(self, name: str, version: str = "latest", **kwargs: str) -> Optional[str]:
        """Retrieve and format a prompt template with variables."""
        entry = self.get(name, version)
        if not entry:
            return None
        try:
            return entry["template"].format(**kwargs)
        except KeyError as exc:
            raise ValueError(f"Missing variable {exc} for prompt '{name}'") from exc

    def delete(self, name: str) -> bool:
        """Delete all versions of a prompt.  Returns True if it existed."""
        with self._lock:
            if name not in self._data:
                return False
            del self._data[name]
            self._save()
            return True

    # ── Listing ───────────────────────────────────────────────────────

    def list_prompts(self) -> List[Dict[str, Any]]:
        """Return a summary list (name, latest version, version count)."""
        result = []
        for name, versions in self._data.items():
            if versions:
                latest = versions[-1]
                result.append({
                    "name": name,
                    "latest_version": latest["version"],
                    "versions_count": len(versions),
                    "description": latest.get("description", ""),
                    "created_at": latest.get("created_at", ""),
                    "metrics": latest.get("metrics", {}),
                })
        return result

    def list_versions(self, name: str) -> List[Dict[str, Any]]:
        """Return all version entries for a prompt name."""
        return self._data.get(name, [])

    # ── Usage Tracking ────────────────────────────────────────────────

    def record_usage(
        self,
        name: str,
        version: str = "latest",
        vote: Optional[str] = None,
    ) -> None:
        """Increment uses counter and optional satisfaction vote."""
        with self._lock:
            versions = self._data.get(name, [])
            if not versions:
                return
            target = (
                versions[-1]
                if version == "latest"
                else next((v for v in versions if v["version"] == version), None)
            )
            if not target:
                return
            target["metrics"]["uses"] = target["metrics"].get("uses", 0) + 1
            if vote == "thumbs_up":
                target["metrics"]["thumbs_up"] = target["metrics"].get("thumbs_up", 0) + 1
            elif vote == "thumbs_down":
                target["metrics"]["thumbs_down"] = target["metrics"].get("thumbs_down", 0) + 1
            self._save()

    # ── Backend Info ──────────────────────────────────────────────────

    def backend_info(self) -> Dict[str, str]:
        return {"backend": self._backend.name}


# ── Singleton ─────────────────────────────────────────────────────────

_registry: Optional[PromptRegistry] = None


def get_prompt_registry() -> PromptRegistry:
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry
