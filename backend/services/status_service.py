"""System status helpers for FastAPI endpoints and UI widgets."""

from __future__ import annotations

import datetime
import json
import logging
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from backend.config import config

logger = logging.getLogger(__name__)

DOCSTORE_FILE = Path(config.PERSIST_DIR) / "docstore.json"
CHROMA_DB_PATH = Path(config.CHROMA_DB_PATH)
EVAL_DATASET_FILE = Path(config.EVALUATION_DATASET_FILE)
DEFAULT_OLLAMA_BASE_URL = config.OLLAMA_BASE_URL.rstrip("/")


def _directory_has_files(path: Path) -> bool:
    """Return True when the directory exists and contains at least one entry."""
    try:
        return path.exists() and any(path.iterdir())
    except OSError:
        return False


@lru_cache(maxsize=4)
def _load_docstore_stats_cached(docstore_mtime: int) -> Dict[str, Any]:
    """Read docstore metadata (cached by mtime so CLI rebuilds invalidate it)."""
    stats: Dict[str, Any] = {
        "document_count": 0,
        "source_count": 0,
        "sample_sources": [],
    }
    if not DOCSTORE_FILE.exists():
        return stats

    try:
        with open(DOCSTORE_FILE, "r", encoding="utf-8") as docstore_file:
            data = json.load(docstore_file)

        entries = data.get("docstore/data", {})
        file_paths = set()
        for entry in entries.values():
            payload = entry.get("__data__", entry)
            metadata = payload.get("metadata", {})
            file_path = metadata.get("file_path")
            if file_path:
                file_paths.add(file_path)

        stats["document_count"] = len(entries)
        stats["source_count"] = len(file_paths)
        stats["sample_sources"] = sorted(file_paths)[:5]
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to parse docstore statistics: %s", exc)
        stats["error"] = str(exc)

    return stats


def get_knowledge_base_stats() -> Dict[str, Any]:
    """Return persisted index insights consumed by dashboards."""
    if not DOCSTORE_FILE.exists():
        return {
            "ready": False,
            "document_count": 0,
            "source_count": 0,
            "sample_sources": [],
            "last_updated": None,
            "last_updated_display": None,
            "path": str(DOCSTORE_FILE),
        }

    docstore_mtime = int(DOCSTORE_FILE.stat().st_mtime)
    stats = _load_docstore_stats_cached(docstore_mtime).copy()
    stats["ready"] = stats.get("document_count", 0) > 0
    stats["path"] = str(DOCSTORE_FILE)

    last_dt = datetime.datetime.fromtimestamp(docstore_mtime)
    stats["last_updated"] = last_dt.isoformat()
    stats["last_updated_display"] = last_dt.strftime("%b %d, %I:%M %p")
    return stats


@lru_cache(maxsize=2)
def _load_eval_dataset_summary_cached(eval_mtime: int) -> Dict[str, Any]:
    """Read evaluation dataset metadata with caching."""
    summary: Dict[str, Any] = {"ready": False, "cases": 0}
    if not EVAL_DATASET_FILE.exists():
        return summary

    try:
        with open(EVAL_DATASET_FILE, "r", encoding="utf-8") as eval_file:
            data = json.load(eval_file)

        if isinstance(data, dict):
            cases = data.get("test_cases", [])
            summary["cases"] = len(cases) if isinstance(cases, list) else 0
        elif isinstance(data, list):
            summary["cases"] = len(data)
        summary["ready"] = summary["cases"] > 0
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to read evaluation dataset: %s", exc)
        summary["error"] = str(exc)

    return summary


def _get_eval_dataset_summary() -> Dict[str, Any]:
    """Attach timestamps to the cached evaluation dataset summary."""
    if not EVAL_DATASET_FILE.exists():
        return {
            "ready": False,
            "cases": 0,
            "path": str(EVAL_DATASET_FILE),
            "last_updated": None,
            "last_updated_display": None,
        }

    eval_mtime = int(EVAL_DATASET_FILE.stat().st_mtime)
    summary = _load_eval_dataset_summary_cached(eval_mtime).copy()
    summary["path"] = str(EVAL_DATASET_FILE)

    last_dt = datetime.datetime.fromtimestamp(eval_mtime)
    summary["last_updated"] = last_dt.isoformat()
    summary["last_updated_display"] = last_dt.strftime("%b %d, %I:%M %p")
    return summary


@lru_cache(maxsize=8)
def _cached_ollama_status(base_url: str, bucket: int) -> Dict[str, Any]:
    """Cache Ollama heartbeat responses for a short interval."""
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=2)
        if response.status_code == 200:
            payload = response.json()
            models = [model.get("name", "") for model in payload.get("models", [])]
            return {"ready": True, "models": models, "error": None}
        return {"ready": False, "models": [], "error": f"HTTP {response.status_code}"}
    except Exception as exc:  # pragma: no cover - network failures
        return {"ready": False, "models": [], "error": str(exc)}


def check_ollama_status(base_url: Optional[str] = None) -> Dict[str, Any]:
    """Ping the Ollama service (cached every 30 seconds) with Docker-friendly fallbacks."""
    bucket = int(time.time() // 30)

    configured = (base_url or os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    candidate_hosts = []

    def _push(endpoint: str) -> None:
        normalized = endpoint.rstrip("/")
        if normalized and normalized not in candidate_hosts:
            candidate_hosts.append(normalized)

    _push(configured)
    _push("http://host.docker.internal:11434")
    _push("http://127.0.0.1:11434")
    _push("http://localhost:11434")

    attempt_messages = []
    for endpoint in candidate_hosts:
        status = _cached_ollama_status(endpoint, bucket)
        status["base_url"] = endpoint
        status["attempted_endpoints"] = candidate_hosts
        if status["ready"]:
            status["active_endpoint"] = endpoint
            return status
        attempt_messages.append(f"{endpoint} -> {status.get('error') or 'unreachable'}")

    failure_detail = "; ".join(attempt_messages) if attempt_messages else "No endpoints attempted"
    return {
        "ready": False,
        "models": [],
        "error": failure_detail,
        "base_url": configured,
        "attempted_endpoints": candidate_hosts,
    }


def get_system_status() -> Dict[str, Any]:
    """Aggregate readiness across storage, evaluation assets, and LLM service."""
    kb_stats = get_knowledge_base_stats()
    chroma_ready = _directory_has_files(CHROMA_DB_PATH)
    eval_summary = _get_eval_dataset_summary()
    ollama_status = check_ollama_status()

    issues = []
    if not kb_stats.get("ready"):
        issues.append("Persisted index is empty or missing.")
    if not chroma_ready:
        issues.append("ChromaDB directory is empty.")
    if not eval_summary.get("ready"):
        issues.append("Evaluation dataset is missing or empty.")
    if not ollama_status.get("ready"):
        error_detail = ollama_status.get("error")
        issues.append(f"Ollama unavailable: {error_detail}" if error_detail else "Ollama service not reachable.")

    return {
        "knowledge_base": kb_stats,
        "vector_store_ready": kb_stats.get("ready", False),
        "chroma_ready": chroma_ready,
        "evaluation_ready": eval_summary.get("ready", False),
        "evaluation_cases": eval_summary.get("cases", 0),
        "evaluation": eval_summary,
        "ollama": ollama_status,
        "issues": issues,
    }


__all__ = [
    "get_system_status",
    "get_knowledge_base_stats",
    "check_ollama_status",
]
