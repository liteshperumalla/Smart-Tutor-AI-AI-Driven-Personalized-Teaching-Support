from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.config import config


def _log_file() -> Path:
    path = Path(config.EVALUATION_RUNS_LOG_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def append_run(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Persist a single evaluation run record to JSONL storage.
    Returns the normalized record that was stored.
    """
    payload = {
        "run_id": record.get("run_id") or str(uuid4()),
        "timestamp": record.get("timestamp")
        or datetime.now(timezone.utc).isoformat(),
        "source": record.get("source", "manual"),
        "run_type": record.get("run_type", "dataset_quality"),
        "dataset": record.get("dataset", "backend/rag/tests/test_dataset.json"),
        "params": record.get("params", {}),
        "summary": record.get("summary", {}),
        "sample_results": record.get("sample_results", []),
    }

    with _log_file().open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    return payload


def list_runs(limit: int = 20) -> List[Dict[str, Any]]:
    log_path = _log_file()
    if not log_path.exists():
        return []

    records: List[Dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if limit <= 0:
        return records
    return list(reversed(records[-limit:]))


def get_latest_run() -> Optional[Dict[str, Any]]:
    runs = list_runs(limit=1)
    if not runs:
        return None
    return runs[0]
