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

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

from backend.config import config

logger = logging.getLogger(__name__)

DOCSTORE_FILE = Path(config.PERSIST_DIR) / "docstore.json"
CHROMA_DB_PATH = Path(config.CHROMA_DB_PATH)
REPO_ROOT = Path(__file__).resolve().parents[2]
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
            # Check both file_path (ChromaDB) and source_file (S3)
            file_path = metadata.get("file_path") or metadata.get("source_file")
            if file_path:
                file_paths.add(file_path)

        stats["document_count"] = len(entries)
        stats["source_count"] = len(file_paths)
        stats["sample_sources"] = sorted(file_paths)[:5]
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to parse docstore statistics: %s", exc)
        stats["error"] = str(exc)

    return stats


_S3_KB_STATS_CACHE: Dict[str, Any] = {}
_S3_KB_STATS_TTL = 300  # Cache for 5 minutes


def _get_s3_knowledge_base_stats() -> Dict[str, Any]:
    """Get knowledge base stats from S3 when using S3-based vector storage.
    Cached for 5 minutes to avoid slow S3 pagination on every request.
    """
    now = time.time()
    cached = _S3_KB_STATS_CACHE.get("data")
    if cached and (now - _S3_KB_STATS_CACHE.get("ts", 0)) < _S3_KB_STATS_TTL:
        return cached

    stats: Dict[str, Any] = {
        "document_count": 0,
        "source_count": 0,
        "sample_sources": [],
        "last_updated": None,
        "last_updated_display": None,
        "path": config.S3_DOCUMENTS_BUCKET,
    }

    if not HAS_BOTO3:
        stats["error"] = "boto3 not installed"
        return stats

    try:
        s3_client = boto3.client("s3")
        bucket = config.S3_DOCUMENTS_BUCKET

        paginator = s3_client.get_paginator("list_objects_v2")
        source_files = set()
        total_objects = 0
        latest_mtime = 0

        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                total_objects += 1
                key = obj.get("Key", "")

                if key.startswith("chunks/") and key.endswith(".json"):
                    parts = key.split("/")
                    if len(parts) >= 3:
                        source_path = "/".join(parts[1:3])
                        source_files.add(source_path)

                mtime = obj.get("LastModified", obj.get("LastModified", 0))
                if isinstance(mtime, datetime.datetime):
                    mtime_ts = mtime.timestamp()
                else:
                    mtime_ts = 0
                if mtime_ts > latest_mtime:
                    latest_mtime = mtime_ts

        stats["document_count"] = total_objects
        stats["source_count"] = len(source_files)
        stats["sample_sources"] = sorted(list(source_files))[:5]
        stats["ready"] = total_objects > 0

        if latest_mtime > 0:
            last_dt = datetime.datetime.fromtimestamp(latest_mtime)
            stats["last_updated"] = last_dt.isoformat()
            stats["last_updated_display"] = last_dt.strftime("%b %d, %I:%M %p")

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "NoSuchBucket":
            stats["error"] = f"Bucket '{bucket}' does not exist"
        elif error_code == "AccessDenied":
            stats["error"] = f"Access denied to bucket '{bucket}'"
        else:
            stats["error"] = f"S3 error: {error_code}"
        stats["ready"] = False
    except Exception as exc:
        stats["error"] = str(exc)
        stats["ready"] = False

    _S3_KB_STATS_CACHE["data"] = stats
    _S3_KB_STATS_CACHE["ts"] = time.time()
    return stats


def get_knowledge_base_stats() -> Dict[str, Any]:
    """Return persisted index insights consumed by dashboards."""
    if config.USE_S3_VECTORS:
        return _get_s3_knowledge_base_stats()

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


def _resolve_eval_dataset_file() -> Path:
    configured = Path(config.EVALUATION_DATASET_FILE)

    candidates = [configured]
    if not configured.is_absolute():
        candidates.append(REPO_ROOT / configured)

    candidates.extend(
        [
            REPO_ROOT / "Evaluation_files/evaluation_data.jsonl",
            REPO_ROOT / "evaluation_dataset.json",
            REPO_ROOT / "backend/rag/tests/test_dataset.jsonl",
            REPO_ROOT / "backend/rag/tests/test_dataset.json",
        ]
    )

    seen = set()
    for candidate in candidates:
        normalized = candidate.resolve(strict=False)
        if normalized in seen:
            continue
        seen.add(normalized)
        if candidate.exists():
            return candidate
    return candidates[0]


@lru_cache(maxsize=6)
def _load_eval_dataset_summary_cached(dataset_path_str: str, eval_mtime: int) -> Dict[str, Any]:
    """Read evaluation dataset metadata with caching."""
    dataset_path = Path(dataset_path_str)
    summary: Dict[str, Any] = {"ready": False, "cases": 0}
    if not dataset_path.exists():
        return summary

    try:
        if dataset_path.suffix.lower() == ".jsonl":
            cases = 0
            with open(dataset_path, "r", encoding="utf-8") as eval_file:
                for line in eval_file:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    cases += 1
            summary["cases"] = cases
        else:
            with open(dataset_path, "r", encoding="utf-8") as eval_file:
                data = json.load(eval_file)

            if isinstance(data, dict):
                if isinstance(data.get("test_cases"), list):
                    summary["cases"] = len(data.get("test_cases", []))
                elif isinstance(data.get("queries"), list):
                    summary["cases"] = len(data.get("queries", []))
            elif isinstance(data, list):
                summary["cases"] = len(data)
        summary["ready"] = summary["cases"] > 0
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to read evaluation dataset: %s", exc)
        summary["error"] = str(exc)

    return summary


def _get_eval_dataset_summary() -> Dict[str, Any]:
    """Attach timestamps to the cached evaluation dataset summary."""
    eval_dataset_file = _resolve_eval_dataset_file()
    if not eval_dataset_file.exists():
        return {
            "ready": False,
            "cases": 0,
            "path": str(eval_dataset_file),
            "last_updated": None,
            "last_updated_display": None,
        }

    eval_mtime = int(eval_dataset_file.stat().st_mtime)
    summary = _load_eval_dataset_summary_cached(str(eval_dataset_file), eval_mtime).copy()
    summary["path"] = str(eval_dataset_file)

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

    configured = (
        base_url or os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL
    ).rstrip("/")
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

    failure_detail = (
        "; ".join(attempt_messages) if attempt_messages else "No endpoints attempted"
    )
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

    # Only check Ollama if it's the configured LLM provider
    llm_provider = config.LLM_PROVIDER.lower()
    ollama_status = None
    llm_status = {"ready": True, "provider": llm_provider}

    if llm_provider == "ollama":
        ollama_status = check_ollama_status()
        llm_status = {
            "ready": ollama_status.get("ready", False),
            "provider": "ollama",
            "models": ollama_status.get("models", []),
            "error": ollama_status.get("error"),
        }
    elif llm_provider == "bedrock":
        # Bedrock uses IAM credentials - check if configured
        if not HAS_BOTO3:
            llm_status = {
                "ready": False,
                "provider": "bedrock",
                "error": "boto3 not installed",
            }
        else:
            try:
                region = getattr(config, "BEDROCK_REGION", config.AWS_REGION)
                # Quick validation - don't actually call AWS to avoid timeouts
                llm_status = {
                    "ready": bool(region and config.BEDROCK_MODEL_ID),
                    "provider": "bedrock",
                    "region": region,
                    "model": config.BEDROCK_MODEL_ID,
                }
            except Exception as e:
                llm_status = {"ready": False, "provider": "bedrock", "error": str(e)}

    issues = []
    # Only check local indexes if NOT using S3 vectors
    if not config.USE_S3_VECTORS:
        if not kb_stats.get("ready"):
            issues.append("Persisted index is empty or missing.")
        if not chroma_ready:
            issues.append("ChromaDB directory is empty.")
    # If using S3 vectors, skip local index checks (they're not needed)

    if not eval_summary.get("ready"):
        issues.append("Evaluation dataset is missing or empty.")
    if not llm_status.get("ready"):
        error_detail = llm_status.get("error")
        provider_name = llm_status.get("provider", "LLM").upper()
        issues.append(
            f"{provider_name} unavailable: {error_detail}"
            if error_detail
            else f"{provider_name} service not reachable."
        )

    return {
        "knowledge_base": kb_stats,
        "vector_store_ready": kb_stats.get("ready", False),
        "chroma_ready": chroma_ready,
        "evaluation_ready": eval_summary.get("ready", False),
        "evaluation_cases": eval_summary.get("cases", 0),
        "evaluation": eval_summary,
        "llm": llm_status,
        "ollama": ollama_status,  # Keep for backward compatibility
        "issues": issues,
    }


__all__ = [
    "get_system_status",
    "get_knowledge_base_stats",
    "check_ollama_status",
]
