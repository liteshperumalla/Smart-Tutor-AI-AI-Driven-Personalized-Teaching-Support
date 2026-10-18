"""Unit and integration tests for Transactional Outbox Pattern (Pattern 114)."""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, OutboxEventRecord, UserRecord
from backend.events.event_bus import InMemoryEventBus
from backend.events.outbox import OutboxPublisher, record_outbox_event


@pytest.fixture
def db_session_factory():
    """In-memory SQLite session factory for testing outbox."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session


def test_record_outbox_event_in_session(db_session_factory):
    """Verify that record_outbox_event attaches record to active session and commits."""
    with db_session_factory() as session:
        user = UserRecord(
            username="test_outbox_user",
            password_hash="hashed_secret",
            email="outbox@test.com",
            full_name="Outbox User",
        )
        session.add(user)

        # Atomically record outbox event within the same transaction
        outbox_entry = record_outbox_event(
            session=session,
            event_type="user.registered",
            aggregate_type="User",
            aggregate_id=user.username,
            payload={"email": user.email, "username": user.username},
            headers={"trace_id": "test-trace-123"},
        )
        session.commit()

        assert outbox_entry.id is not None
        assert outbox_entry.status == "PENDING"
        assert outbox_entry.retry_count == 0

    # Read back from database
    with db_session_factory() as session:
        saved_record = session.query(OutboxEventRecord).filter_by(aggregate_id="test_outbox_user").first()
        assert saved_record is not None
        assert saved_record.event_type == "user.registered"
        assert saved_record.payload["email"] == "outbox@test.com"
        assert saved_record.headers["trace_id"] == "test-trace-123"


def test_transactional_rollback_preserves_consistency(db_session_factory):
    """
    CRITICAL: Verify atomic rollback guarantee.
    If database transaction rolls back, outbox event MUST NOT be saved (no phantom events).
    """
    with db_session_factory() as session:
        user = UserRecord(
            username="rollback_user",
            password_hash="secret",
            email="rollback@test.com",
        )
        session.add(user)

        record_outbox_event(
            session=session,
            event_type="user.registered",
            aggregate_type="User",
            aggregate_id="rollback_user",
            payload={"email": "rollback@test.com"},
        )

        # Explicit rollback simulating an unhandled error/constraint violation
        session.rollback()

    with db_session_factory() as session:
        saved_user = session.query(UserRecord).filter_by(username="rollback_user").first()
        saved_outbox = session.query(OutboxEventRecord).filter_by(aggregate_id="rollback_user").first()
        assert saved_user is None
        assert saved_outbox is None


def test_outbox_publisher_publishes_pending_events(db_session_factory):
    """Verify that OutboxPublisher polls PENDING records, publishes to bus, and marks PUBLISHED."""
    # Seed 3 pending events
    with db_session_factory() as session:
        for i in range(3):
            record_outbox_event(
                session=session,
                event_type=f"event.{i}",
                aggregate_type="Item",
                aggregate_id=str(i),
                payload={"index": i},
            )
        session.commit()

    bus = InMemoryEventBus()
    publisher = OutboxPublisher(batch_size=10, max_retries=3)

    result = publisher.publish_pending(session_factory=db_session_factory, event_bus=bus)
    assert result["published"] == 3
    assert result["failed"] == 0
    assert result["total"] == 3
    assert len(bus.events) == 3
    assert bus.events[0].type == "event.0"

    # Verify database state has transitioned to PUBLISHED
    with db_session_factory() as session:
        records = session.query(OutboxEventRecord).all()
        for r in records:
            assert r.status == "PUBLISHED"
            assert r.processed_at is not None
            assert r.last_error is None

    # Next poll should find 0 pending
    second_poll = publisher.publish_pending(session_factory=db_session_factory, event_bus=bus)
    assert second_poll["published"] == 0
    assert second_poll["total"] == 0


def test_outbox_publisher_error_handling_and_retry(db_session_factory):
    """Verify retry counting and transition to FAILED when EventBus fails."""
    with db_session_factory() as session:
        record_outbox_event(
            session=session,
            event_type="failing.event",
            aggregate_type="Faulty",
            aggregate_id="err-1",
            payload={"fail": True},
        )
        session.commit()

    # Mock failing event bus
    mock_bus = MagicMock()
    mock_bus.publish.return_value = False  # Simulates broker failure

    publisher = OutboxPublisher(batch_size=10, max_retries=2)

    # Attempt 1
    publisher.publish_pending(session_factory=db_session_factory, event_bus=mock_bus)
    with db_session_factory() as session:
        r = session.query(OutboxEventRecord).first()
        assert r.status == "PENDING"
        assert r.retry_count == 1
        assert "EventBus returned False" in r.last_error

    # Attempt 2 -> hits max_retries
    publisher.publish_pending(session_factory=db_session_factory, event_bus=mock_bus)
    with db_session_factory() as session:
        r = session.query(OutboxEventRecord).first()
        assert r.status == "FAILED"
        assert r.retry_count == 2

    # Replay failed events
    replayed = publisher.replay_failed(session_factory=db_session_factory)
    assert replayed == 1
    with db_session_factory() as session:
        r = session.query(OutboxEventRecord).first()
        assert r.status == "PENDING"
        assert r.retry_count == 0
