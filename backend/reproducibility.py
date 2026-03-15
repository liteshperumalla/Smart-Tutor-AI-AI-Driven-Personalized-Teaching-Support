"""
Reproducibility manifest generation.
Captures environment, model config, and key file hashes for traceability.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from backend.config import config
from backend.logger import get_logger
from backend.utils import FileUtils

logger = get_logger(__name__)


def _run_git_cmd(args: List[str]) -> str:
    try:
        out = subprocess.check_output(args, stderr=subprocess.DEVNULL, timeout=2)
        return out.decode("utf-8").strip()
    except Exception:
        return ""


def _collect_file_hashes(paths: List[str]) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for path in paths:
        p = Path(path)
        if not p.exists():
            continue
        try:
            hashes[str(p)] = FileUtils.get_file_hash(str(p), algorithm="sha256")
        except Exception as exc:
            logger.warning("Failed to hash %s: %s", p, exc)
    return hashes


def generate_manifest() -> Dict[str, Any]:
    git_commit = _run_git_cmd(["git", "rev-parse", "HEAD"])
    git_dirty = bool(_run_git_cmd(["git", "status", "--porcelain"]))

    config_snapshot = config.to_dict(include_secrets=False)
    config_json = json.dumps(config_snapshot, sort_keys=True).encode("utf-8")
    config_hash = FileUtils.get_file_hash_from_bytes(config_json)

    key_files = [
        "backend/requirements.txt",
        "frontend/package.json",
        "backend/rag/tests/test_dataset.json",
        "Evaluation_files/evaluation_data.jsonl",
        "Evaluation_files/evaluation_1_data.jsonl",
    ]

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": config.ENVIRONMENT,
        "git": {
            "commit": git_commit or None,
            "dirty": git_dirty,
        },
        "models": {
            "llm_provider": config.LLM_PROVIDER,
            "bedrock_model_id": config.BEDROCK_MODEL_ID,
            "bedrock_embedding_model_id": config.BEDROCK_EMBEDDING_MODEL_ID,
            "embedding_model": config.EMBEDDING_MODEL,
            "rerank_model": config.RERANK_MODEL,
        },
        "config_hash": config_hash,
        "file_hashes": _collect_file_hashes(key_files),
    }


def write_manifest(path: str) -> Dict[str, Any]:
    manifest = generate_manifest()
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2))
    return manifest
