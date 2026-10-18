"""
Change Data Capture (CDC) Implementation (Pattern 115)
Captures granular database mutations and streams Debezium/CloudEvents compliant change records.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Type

from sqlalchemy import event, inspect
from sqlalchemy.orm import DeclarativeBase, Session

from backend.db.models import (
    Base,
    CourseMembershipRecord,
    CourseRecord,
    LearningObjectiveRecord,
    MasteryRecord,
    OutboxEventRecord,
    QuizResultRecord,
    UserRecord,
)
from backend.events.event_schemas import CDCEnvelope, CDCOperation, CDCSource, EventType
from backend.events.outbox import record_outbox_event

logger = logging.getLogger(__name__)

# Default entities monitored for Change Data Capture
DEFAULT_TRACKED_MODELS: Set[Type[DeclarativeBase]] = {
    UserRecord,
    QuizResultRecord,
    CourseRecord,
    CourseMembershipRecord,
    LearningObjectiveRecord,
    MasteryRecord,
}


def _record_to_dict(instance: Any, exclude_fields: Optional[Set[str]] = None) -> Dict[str, Any]:
    """Serialize a SQLAlchemy model instance to a JSON-safe dictionary."""
    exclude = exclude_fields or set()
    mapper = inspect(instance.__class__)
    data: Dict[str, Any] = {}
    for col in mapper.columns:
        if col.key in exclude:
            continue
        val = getattr(instance, col.key, None)
        if isinstance(val, datetime):
            data[col.key] = val.isoformat()
        elif hasattr(val, "__dict__") and not isinstance(val, (dict, list, str, int, float, bool, type(None))):
            data[col.key] = str(val)
        else:
            data[col.key] = val
    return data


def _get_primary_key(instance: Any) -> str:
    """Retrieve stringified primary key value(s) for a model instance."""
    mapper = inspect(instance.__class__)
    pk_vals = [str(getattr(instance, col.key, "")) for col in mapper.primary_key]
    return ":".join(pk_vals) if pk_vals else "unknown"


class CDCEngine:
    """
    Change Data Capture engine that intercepts entity lifecycle mutations and emits
    Debezium-compatible CDC events directly through the Transactional Outbox.
    """

    def __init__(self, tracked_models: Optional[Set[Type[DeclarativeBase]]] = None):
        self.tracked_models = tracked_models or set(DEFAULT_TRACKED_MODELS)
        self._hooks_registered = False

    def is_tracked(self, instance: Any) -> bool:
        """Check if an instance belongs to a monitored model class."""
        if isinstance(instance, OutboxEventRecord):
            return False  # Never track the outbox table itself to prevent recursion!
        return any(isinstance(instance, model_cls) for model_cls in self.tracked_models)

    def attach_session_hooks(self, session_or_cls: Any):
        """
        Register SQLAlchemy session hooks for CDC capture.
        Can be attached to a Session class or Session instance.
        """
        if self._hooks_registered:
            return

        @event.listens_for(session_or_cls, "before_flush")
        def _before_flush(session: Session, flush_context: Any, instances: Any):
            self.capture_flush_changes(session)

        self._hooks_registered = True
        logger.info("Attached CDC session hooks for %d tracked models", len(self.tracked_models))

    def capture_flush_changes(self, session: Session):
        """
        Examine session changes before flush and generate atomic outbox CDC records.
        """
        new_outbox_records: List[OutboxEventRecord] = []

        # 1. Capture INSERTs (op = 'c')
        for instance in list(session.new):
            if not self.is_tracked(instance):
                continue
            table_name = getattr(instance, "__tablename__", instance.__class__.__name__.lower())
            pk = _get_primary_key(instance)
            after_state = _record_to_dict(instance, exclude_fields={"password_hash"})

            cdc_envelope = CDCEnvelope(
                table=table_name,
                op=CDCOperation.CREATE,
                before=None,
                after=after_state,
                cdc_source=CDCSource(table=table_name),
            )

            record = record_outbox_event(
                session=session,
                event_type=EventType.CDC_RECORD_CHANGED.value,
                aggregate_type=table_name,
                aggregate_id=pk,
                payload=cdc_envelope.model_dump(mode="json"),
                headers={"cdc_op": "create", "table": table_name},
            )
            new_outbox_records.append(record)

        # 2. Capture UPDATEs (op = 'u')
        for instance in list(session.dirty):
            if not self.is_tracked(instance):
                continue
            if not session.is_modified(instance, include_collections=False):
                continue

            table_name = getattr(instance, "__tablename__", instance.__class__.__name__.lower())
            pk = _get_primary_key(instance)
            state = inspect(instance)

            before_state: Dict[str, Any] = {}
            after_state: Dict[str, Any] = _record_to_dict(instance, exclude_fields={"password_hash"})

            for attr in state.attrs:
                if attr.key in {"password_hash"}:
                    continue
                history = attr.history
                if history.has_changes():
                    old_val = history.deleted[0] if history.deleted else None
                    if isinstance(old_val, datetime):
                        before_state[attr.key] = old_val.isoformat()
                    else:
                        before_state[attr.key] = old_val
                else:
                    val = getattr(instance, attr.key, None)
                    if isinstance(val, datetime):
                        before_state[attr.key] = val.isoformat()
                    else:
                        before_state[attr.key] = val

            cdc_envelope = CDCEnvelope(
                table=table_name,
                op=CDCOperation.UPDATE,
                before=before_state,
                after=after_state,
                cdc_source=CDCSource(table=table_name),
            )

            record = record_outbox_event(
                session=session,
                event_type=EventType.CDC_RECORD_CHANGED.value,
                aggregate_type=table_name,
                aggregate_id=pk,
                payload=cdc_envelope.model_dump(mode="json"),
                headers={"cdc_op": "update", "table": table_name},
            )
            new_outbox_records.append(record)

        # 3. Capture DELETEs (op = 'd')
        for instance in list(session.deleted):
            if not self.is_tracked(instance):
                continue
            table_name = getattr(instance, "__tablename__", instance.__class__.__name__.lower())
            pk = _get_primary_key(instance)
            before_state = _record_to_dict(instance, exclude_fields={"password_hash"})

            cdc_envelope = CDCEnvelope(
                table=table_name,
                op=CDCOperation.DELETE,
                before=before_state,
                after=None,
                cdc_source=CDCSource(table=table_name),
            )

            record = record_outbox_event(
                session=session,
                event_type=EventType.CDC_RECORD_CHANGED.value,
                aggregate_type=table_name,
                aggregate_id=pk,
                payload=cdc_envelope.model_dump(mode="json"),
                headers={"cdc_op": "delete", "table": table_name},
            )
            new_outbox_records.append(record)


    @staticmethod
    def generate_postgres_trigger_sql(table_name: str) -> str:
        """
        Generate PostgreSQL PL/pgSQL function and trigger DDL to capture direct SQL
        mutations into the outbox_events table for non-ORM database modifications.
        """
        return f"""
-- CDC Outbox Capture Trigger for {table_name}
CREATE OR REPLACE FUNCTION fn_cdc_capture_{table_name}()
RETURNS TRIGGER AS $$
DECLARE
    v_event_id VARCHAR(64) := gen_random_uuid()::text;
    v_op VARCHAR(8);
    v_before JSONB := NULL;
    v_after JSONB := NULL;
    v_agg_id VARCHAR(255) := '';
BEGIN
    IF (TG_OP = 'INSERT') THEN
        v_op := 'c';
        v_after := to_jsonb(NEW);
        v_agg_id := COALESCE(NEW.id::text, NEW.username::text, 'unknown');
    ELSIF (TG_OP = 'UPDATE') THEN
        v_op := 'u';
        v_before := to_jsonb(OLD);
        v_after := to_jsonb(NEW);
        v_agg_id := COALESCE(NEW.id::text, NEW.username::text, OLD.id::text, 'unknown');
    ELSIF (TG_OP = 'DELETE') THEN
        v_op := 'd';
        v_before := to_jsonb(OLD);
        v_agg_id := COALESCE(OLD.id::text, OLD.username::text, 'unknown');
    END IF;

    INSERT INTO outbox_events (
        id, event_type, aggregate_type, aggregate_id, payload, headers, status, retry_count, created_at
    ) VALUES (
        v_event_id,
        'cdc.record_changed',
        '{table_name}',
        v_agg_id,
        jsonb_build_object(
            'op', v_op,
            'before', v_before,
            'after', v_after,
            'source', jsonb_build_object('table', '{table_name}', 'db', current_database()),
            'ts_ms', (extract(epoch from clock_timestamp()) * 1000)::bigint
        ),
        jsonb_build_object('source', 'pg_trigger', 'table', '{table_name}'),
        'PENDING',
        0,
        clock_timestamp()
    );

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_cdc_{table_name} ON {table_name};
CREATE TRIGGER trg_cdc_{table_name}
AFTER INSERT OR UPDATE OR DELETE ON {table_name}
FOR EACH ROW EXECUTE FUNCTION fn_cdc_capture_{table_name}();
"""


class CDCStreamConsumer:
    """
    Consumer dispatcher for CDC change streams.
    Routes entity change events to read-model projections (CQRS),
    cache invalidation routines, and multi-region synchronization buffers.
    """

    def __init__(self):
        self.table_handlers: Dict[str, List[Callable[[CDCEnvelope], None]]] = {}
        self.global_handlers: List[Callable[[CDCEnvelope], None]] = []

    def register_handler(
        self,
        handler: Callable[[CDCEnvelope], None],
        table_name: Optional[str] = None,
    ):
        """Register a callback for CDC events (for a specific table or all tables)."""
        if table_name:
            self.table_handlers.setdefault(table_name, []).append(handler)
        else:
            self.global_handlers.append(handler)

    def handle_event(self, envelope: CDCEnvelope):
        """Process an incoming CDC event and notify registered subscribers."""
        table = envelope.cdc_source.table
        logger.debug("Dispatching CDC event %s on table %s (op=%s)", envelope.id, table, envelope.op)

        # 1. Global listeners
        for handler in self.global_handlers:
            try:
                handler(envelope)
            except Exception as e:
                logger.error("Global CDC handler failed for event %s: %s", envelope.id, e, exc_info=True)

        # 2. Table-specific listeners
        if table in self.table_handlers:
            for handler in self.table_handlers[table]:
                try:
                    handler(envelope)
                except Exception as e:
                    logger.error("CDC table handler for %s failed on event %s: %s", table, envelope.id, e, exc_info=True)


# Global CDC instances
_cdc_engine: Optional[CDCEngine] = None
_cdc_consumer: Optional[CDCStreamConsumer] = None


def get_cdc_engine() -> CDCEngine:
    """Get or initialize global CDCEngine."""
    global _cdc_engine
    if _cdc_engine is None:
        _cdc_engine = CDCEngine()
    return _cdc_engine


def get_cdc_consumer() -> CDCStreamConsumer:
    """Get or initialize global CDCStreamConsumer."""
    global _cdc_consumer
    if _cdc_consumer is None:
        _cdc_consumer = CDCStreamConsumer()
    return _cdc_consumer
