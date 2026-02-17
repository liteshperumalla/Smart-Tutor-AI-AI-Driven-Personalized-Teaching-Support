"""
Cost Tracking Service
Tracks LLM API costs and stores them via the object storage abstraction.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path

from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)


class CostTracker:
    """Track and store LLM costs in object storage"""

    def __init__(
        self,
        s3_bucket: Optional[str] = None,
        s3_prefix: str = "cost_tracking/",
        local_backup: bool = True
    ):
        """
        Initialize cost tracker

        Args:
            s3_bucket: Bucket for cost logs (defaults to config.S3_DOCUMENTS_BUCKET)
            s3_prefix: Key prefix for cost logs
            local_backup: Whether to also write to local file
        """
        self.s3_bucket = s3_bucket or config.S3_DOCUMENTS_BUCKET
        self.s3_prefix = s3_prefix
        self.local_backup = local_backup
        self.local_file = Path(config.COST_LOG_FILE) if local_backup else None

        # Use cloud-agnostic object storage
        from backend.cloud.object_storage import get_object_storage
        self._storage = get_object_storage()

        # Ensure local directory exists if using backup
        if self.local_backup and self.local_file:
            self.local_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Cost tracker initialized (bucket: {self.s3_bucket}/{self.s3_prefix})")

    def log_cost(
        self,
        service: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        model_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log a cost entry

        Args:
            service: Service name (e.g., "bedrock_llm", "bedrock_embeddings")
            operation: Operation type (e.g., "chat", "embedding")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost_usd: Cost in USD
            model_id: Model identifier
            metadata: Additional metadata
        """
        timestamp = datetime.now(timezone.utc)

        # Create cost entry
        entry = {
            "timestamp": timestamp.isoformat(),
            "service": service,
            "operation": operation,
            "model_id": model_id,
            "tokens": {
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens
            },
            "cost_usd": round(cost_usd, 6),
            "metadata": metadata or {}
        }

        # Write to S3
        try:
            self._write_to_s3(entry, timestamp)
        except Exception as e:
            logger.error(f"Failed to write cost log to S3: {e}")
            # Continue - will still write to local backup

        # Write to local backup if enabled
        if self.local_backup and self.local_file:
            try:
                with open(self.local_file, 'a') as f:
                    f.write(json.dumps(entry) + '\n')
            except Exception as e:
                logger.error(f"Failed to write cost log to local file: {e}")

    def _write_to_s3(self, entry: Dict[str, Any], timestamp: datetime):
        """Write cost entry to object storage"""
        date_path = timestamp.strftime("%Y/%m/%d")
        time_str = timestamp.strftime("%H%M%S")

        import uuid
        key = f"{self.s3_prefix}{date_path}/{time_str}-{uuid.uuid4().hex[:8]}.json"

        self._storage.put_object(
            bucket=self.s3_bucket,
            key=key,
            body=json.dumps(entry, indent=2).encode(),
            content_type="application/json",
            metadata={
                "service": entry["service"],
                "operation": entry["operation"],
                "cost_usd": str(entry["cost_usd"]),
                "total_tokens": str(entry["tokens"]["total"]),
            },
        )

        logger.debug(f"Cost log written: {self.s3_bucket}/{key}")

    def get_daily_costs(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get cost summary for a specific date

        Args:
            date: Date in YYYY-MM-DD format (defaults to today)

        Returns:
            Dictionary with cost breakdown
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Parse date to get S3 prefix
        dt = datetime.strptime(date, "%Y-%m-%d")
        prefix = f"{self.s3_prefix}{dt.strftime('%Y/%m/%d')}/"

        # List objects for the day
        try:
            objects = self._storage.list_objects(
                bucket=self.s3_bucket,
                prefix=prefix,
            )

            if not objects:
                return {
                    "date": date,
                    "total_cost_usd": 0,
                    "total_tokens": 0,
                    "entries": 0
                }

            # Download and aggregate
            total_cost = 0
            total_tokens = 0
            entries = 0
            service_costs = {}

            for obj in objects:
                file_obj = self._storage.get_object(bucket=self.s3_bucket, key=obj.key)
                entry = json.loads(file_obj.read())

                total_cost += entry['cost_usd']
                total_tokens += entry['tokens']['total']
                entries += 1

                service = entry['service']
                service_costs[service] = service_costs.get(service, 0) + entry['cost_usd']

            return {
                "date": date,
                "total_cost_usd": round(total_cost, 6),
                "total_tokens": total_tokens,
                "entries": entries,
                "by_service": service_costs
            }

        except Exception as e:
            logger.error(f"Failed to get daily costs from S3: {e}")
            return {
                "date": date,
                "error": str(e)
            }


# Singleton instance
_cost_tracker = None


def get_cost_tracker() -> CostTracker:
    """Get singleton cost tracker instance"""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker
