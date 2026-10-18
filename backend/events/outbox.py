"""
Transactional Outbox Pattern Implementation (Pattern 114)
Ensures at-least-once, atomically consistent event delivery from PostgreSQL to EventBus/SQS.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.db.models import OutboxEventRecord
from backend.events.event_bus import get_event_bus
from backend.events.event_schemas import BaseEvent

logger = logging.getLogger(__name__)


def record_outbox_event(
    session: Session,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, Any]] = None,
) -> OutboxEventRecord:
    """
    Atomically record a domain event in the database outbox table.
    
    Must be called inside an active database transaction. If the transaction
    commits, the outbox event is guaranteed to be recorded. If the transaction
    rolls back, no phantom event is created.
    """
    event_id = str(uuid.uuid4())
    record = OutboxEventRecord(
        id=event_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        payload=payload,
        headers=headers or {},
        status="PENDING",
        retry_count=0,
        last_error=None,
        created_at=datetime.now(timezone.utc),
    )
    session.add(record)
    logger.debug(
        "Recorded outbox event %s (%s for %s:%s)",
        event_id, event_type, aggregate_type, aggregate_id
    )
    return record


class OutboxPublisher:
    """
    Background worker / poller that reads pending outbox events from PostgreSQL
    and publishes them to the message broker (EventBus / SQS / EventBridge).
    
    Uses SELECT ... FOR UPDATE SKIP LOCKED for high-throughput, concurrent
    multi-replica safe processing without duplicate delivery.
    """

    def __init__(
        self,
        batch_size: int = 50,
        max_retries: int = 5,
        poll_interval_seconds: float = 2.0,
    ):
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.poll_interval_seconds = poll_interval_seconds
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    def publish_pending(
        self,
        session_factory: Callable[[], Session],
        event_bus: Optional[Any] = None,
    ) -> Dict[str, int]:
        """
        Poll and publish a single batch of pending outbox events.
        
        Args:
            session_factory: Callable returning an active SQLAlchemy Session.
            event_bus: Optional EventBus instance (defaults to global event bus).
            
        Returns:
            Dictionary with counts: {"published": count, "failed": count, "total": count}
        """
        bus = event_bus or get_event_bus()
        published_count = 0
        failed_count = 0

        with session_factory() as session:
            try:
                # Query pending events ordered by creation time
                stmt = (
                    select(OutboxEventRecord)
                    .where(OutboxEventRecord.status == "PENDING")
                    .order_by(OutboxEventRecord.created_at.asc())
                    .limit(self.batch_size)
                )

                # Attempt SKIP LOCKED (supported on PostgreSQL, gracefully omitted on SQLite/others)
                try:
                    dialect_name = session.bind.dialect.name if session.bind else ""
                    if dialect_name == "postgresql":
                        stmt = stmt.with_for_update(skip_locked=True)
                except Exception:
                    pass

                pending_records: List[OutboxEventRecord] = list(session.scalars(stmt).all())

                if not pending_records:
                    return {"published": 0, "failed": 0, "total": 0}

                for record in pending_records:
                    try:
                        # Construct a CloudEvents compliant BaseEvent
                        event = BaseEvent(
                            id=record.id,
                            source=f"outbox.{record.aggregate_type.lower()}",
                            type=record.event_type,
                            subject=f"{record.aggregate_type}/{record.aggregate_id}",
                            data=record.payload,
                            metadata=record.headers or {},
                        )

                        # Publish to event bus / message broker
                        success = bus.publish(event)
                        if success:
                            record.status = "PUBLISHED"
                            record.processed_at = datetime.now(timezone.utc)
                            record.last_error = None
                            published_count += 1
                        else:
                            raise RuntimeError(f"EventBus returned False for outbox event {record.id}")

                    except Exception as exc:
                        failed_count += 1
                        record.retry_count += 1
                        record.last_error = str(exc)[:1000]
                        if record.retry_count >= self.max_retries:
                            record.status = "FAILED"
                            logger.error(
                                "Outbox event %s exceeded max retries (%d). Marked FAILED: %s",
                                record.id, self.max_retries, exc
                            )
                        else:
                            logger.warning(
                                "Outbox event %s failed to publish (attempt %d/%d): %s",
                                record.id, record.retry_count, self.max_retries, exc
                            )

                session.commit()
                logger.info(
                    "Outbox batch processed: %d published, %d failed out of %d total",
                    published_count, failed_count, len(pending_records)
                )
                return {
                    "published": published_count,
                    "failed": failed_count,
                    "total": len(pending_records),
                }

            except Exception as e:
                session.rollback()
                logger.error("Outbox processing transaction error: %s", e, exc_info=True)
                return {"published": 0, "failed": 0, "total": 0, "error": str(e)}

    def replay_failed(
        self,
        session_factory: Callable[[], Session],
        event_ids: Optional[List[str]] = None,
    ) -> int:
        """
        Reset failed outbox events back to PENDING for safe replay.
        """
        replayed_count = 0
        with session_factory() as session:
            stmt = select(OutboxEventRecord).where(OutboxEventRecord.status == "FAILED")
            if event_ids:
                stmt = stmt.where(OutboxEventRecord.id.in_(event_ids))

            records = list(session.scalars(stmt).all())
            for record in records:
                record.status = "PENDING"
                record.retry_count = 0
                record.last_error = f"Replay initiated at {datetime.now(timezone.utc).isoformat()}"
                replayed_count += 1

            session.commit()
            logger.info("Replayed %d failed outbox events", replayed_count)
            return replayed_count

    async def run_worker_loop(self, session_factory: Callable[[], Session]):
        """Continuous async worker loop for polling pending outbox events."""
        self._running = True
        logger.info("Started Transactional Outbox worker loop (interval=%.1fs)", self.poll_interval_seconds)
        while self._running:
            try:
                result = await asyncio.to_thread(self.publish_pending, session_factory)
                # If there were items processed, continue immediately; otherwise wait
                if result.get("total", 0) == 0:
                    await asyncio.sleep(self.poll_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Unexpected error in Outbox worker loop: %s", e, exc_info=True)
                await asyncio.sleep(self.poll_interval_seconds)
        logger.info("Outbox worker loop stopped")

    def start_background_worker(self, session_factory: Callable[[], Session]) -> asyncio.Task:
        """Launch the worker loop as an asyncio background task."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self.run_worker_loop(session_factory))
        return self._worker_task

    def stop_background_worker(self):
        """Signal the background worker to stop."""
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()


# Global Outbox Publisher singleton
_outbox_publisher: Optional[OutboxPublisher] = None


def get_outbox_publisher(
    batch_size: int = 50,
    max_retries: int = 5,
    poll_interval_seconds: float = 2.0,
) -> OutboxPublisher:
    """Get or initialize global OutboxPublisher instance."""
    global _outbox_publisher
    if _outbox_publisher is None:
        _outbox_publisher = OutboxPublisher(
            batch_size=batch_size,
            max_retries=max_retries,
            poll_interval_seconds=poll_interval_seconds,
        )
    return _outbox_publisher
