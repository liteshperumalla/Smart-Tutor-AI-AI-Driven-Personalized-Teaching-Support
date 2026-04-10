from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional

from backend.api.routes.evaluation import _run_dataset_quality, _store_dataset_run

logger = logging.getLogger(__name__)


def run_scheduled_evaluation(limit: int, model_id: Optional[str], source: str) -> dict:
    result = _run_dataset_quality(limit=limit, model_id=model_id)
    record = _store_dataset_run(result, limit, model_id, source=source)
    return {**result, "run_record": record}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run scheduled RAG evaluation directly inside the backend container."
    )
    parser.add_argument("--limit", type=int, required=True)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--source", default="scheduled")
    args = parser.parse_args()

    try:
        payload = run_scheduled_evaluation(
            limit=args.limit,
            model_id=args.model_id,
            source=args.source,
        )
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        logger.exception("Scheduled evaluation CLI failed")
        payload = {
            "total_evaluated": 0,
            "quality_summary": None,
            "individual_results": [],
            "error": "cli_execution_failed",
            "message": f"Scheduled evaluation CLI failed: {exc}",
        }

    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
