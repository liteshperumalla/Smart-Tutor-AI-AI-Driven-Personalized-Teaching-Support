"""
Prompt Registry — versioned prompt template management.

Implements the Prompt Versioning & A/B Testing pattern from LLMOps:
- Register named prompts with semantic versions (v1, v2, …)
- Retrieve a specific version or the latest
- Track per-version usage and user satisfaction votes

Storage: logs/prompt_registry.json  (plain JSON, easy to back up / export).
In production, swap _load/_save for a Redis hash or DynamoDB item.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.logger import get_logger

logger = get_logger(__name__)

REGISTRY_FILE = Path("logs/prompt_registry.json")


class PromptRegistry:
    """
    Thread-safe versioned prompt store.

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
        REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._load()

    # ── Persistence ───────────────────────────────────────────────────

    def _load(self) -> None:
        if REGISTRY_FILE.exists():
            try:
                self._data = json.loads(REGISTRY_FILE.read_text())
            except Exception as exc:
                logger.warning("Prompt registry load failed: %s", exc)
                self._data = {}

    def _save(self) -> None:
        try:
            REGISTRY_FILE.write_text(json.dumps(self._data, indent=2))
        except Exception as exc:
            logger.warning("Prompt registry save failed: %s", exc)

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
            logger.info("Prompt '%s' registered as %s", name, version)
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


# ── Singleton ─────────────────────────────────────────────────────────

_registry: Optional[PromptRegistry] = None


def get_prompt_registry() -> PromptRegistry:
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry
