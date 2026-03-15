"""
Lightweight drift monitoring for query inputs.

Tracks simple statistics (query length, word count) and compares them to a
baseline distribution. Emits a drift score based on z-scores.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from backend.config import config
from backend.logger import get_logger
from backend.metrics import track_drift

logger = get_logger(__name__)


@dataclass
class BaselineStats:
    mean_len: float
    std_len: float
    mean_words: float
    std_words: float

    @staticmethod
    def from_dict(data: Dict[str, float]) -> "BaselineStats":
        return BaselineStats(
            mean_len=float(data.get("mean_len", 0.0)),
            std_len=float(data.get("std_len", 1.0) or 1.0),
            mean_words=float(data.get("mean_words", 0.0)),
            std_words=float(data.get("std_words", 1.0) or 1.0),
        )


class DriftMonitor:
    """Compute drift scores for queries compared to a stored baseline."""

    def __init__(self, baseline_path: str):
        self.baseline_path = Path(baseline_path)
        self.baseline: Optional[BaselineStats] = None
        self._load_baseline()

    def _load_baseline(self) -> None:
        if not self.baseline_path.exists():
            logger.warning(
                "Drift baseline not found at %s; drift scoring disabled.",
                self.baseline_path,
            )
            return
        try:
            data = json.loads(self.baseline_path.read_text())
            self.baseline = BaselineStats.from_dict(data)
            logger.info(
                "Loaded drift baseline from %s (mean_len=%.1f, mean_words=%.1f)",
                self.baseline_path,
                self.baseline.mean_len,
                self.baseline.mean_words,
            )
        except Exception as exc:
            logger.warning("Failed to load drift baseline: %s", exc)
            self.baseline = None

    def score(self, query: str) -> Optional[Dict[str, float]]:
        if not self.baseline:
            return None

        q_len = len(query)
        q_words = len(query.split())

        z_len = (q_len - self.baseline.mean_len) / max(self.baseline.std_len, 1e-6)
        z_words = (q_words - self.baseline.mean_words) / max(self.baseline.std_words, 1e-6)

        drift_score = max(abs(z_len), abs(z_words))

        track_drift(
            drift_score=drift_score,
            z_len=z_len,
            z_words=z_words,
        )

        return {
            "z_len": round(z_len, 3),
            "z_words": round(z_words, 3),
            "drift_score": round(drift_score, 3),
        }


_drift_monitor: Optional[DriftMonitor] = None


def get_drift_monitor() -> Optional[DriftMonitor]:
    if not config.DRIFT_MONITOR_ENABLED:
        return None
    global _drift_monitor
    if _drift_monitor is None:
        _drift_monitor = DriftMonitor(config.DRIFT_BASELINE_PATH)
    return _drift_monitor
