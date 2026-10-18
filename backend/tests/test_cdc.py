"""Unit tests for Change Data Capture (CDC) Pattern (Pattern 115)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, OutboxEventRecord, UserRecord, MasteryRecord, LearningObjectiveRecord, CourseRecord
from backend.events.cdc import CDCEngine, CDCStreamConsumer, get_cdc_engine
from backend.events.event_schemas import CDCEnvelope, CDCOperation, CDCSource, EventType


@pytest.fixture
def cdc_session_factory():
    """In-memory SQLite session factory with CDCEngine attached."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    
    # Instantiate clean CDCEngine and attach hooks
    cdc_engine = CDCEngine()
    cdc_engine.attach_session_hooks(Session)
    return Session


def test_cdc_captures_entity_create(cdc_session_factory):
    """Verify that committing a new entity generates a CDC 'c' (create) event in outbox."""
    with cdc_session_factory() as session:
        user = UserRecord(
            username="cdc_student",
            password_hash="secret_hash",
            email="student@tutor.edu",
            full_name="CDC Student",
        )
        session.add(user)
        session.commit()

    with cdc_session_factory() as session:
        outbox = session.query(OutboxEventRecord).filter_by(aggregate_id="cdc_student").first()
        assert outbox is not None
        assert outbox.event_type == EventType.CDC_RECORD_CHANGED
        assert outbox.payload["op"] == "c"
        assert outbox.payload["before"] is None
        assert outbox.payload["after"]["username"] == "cdc_student"
        assert outbox.payload["after"]["email"] == "student@tutor.edu"
        # SECURITY: password_hash excluded from CDC stream
        assert "password_hash" not in outbox.payload["after"]


def test_cdc_captures_entity_update(cdc_session_factory):
    """Verify that updating an entity records before/after state diff in CDC outbox."""
    with cdc_session_factory() as session:
        user = UserRecord(
            username="update_student",
            password_hash="secret_hash",
            email="initial@tutor.edu",
            full_name="Old Name",
        )
        session.add(user)
        session.commit()

    # Clear create event for clean assertion
    with cdc_session_factory() as session:
        session.query(OutboxEventRecord).delete()
        session.commit()

    # Perform update
    with cdc_session_factory() as session:
        user = session.query(UserRecord).filter_by(username="update_student").first()
        user.email = "updated@tutor.edu"
        user.full_name = "New Name"
        session.commit()

    with cdc_session_factory() as session:
        outbox = session.query(OutboxEventRecord).filter_by(aggregate_id="update_student").first()
        assert outbox is not None
        assert outbox.payload["op"] == "u"
        assert outbox.payload["before"]["email"] == "initial@tutor.edu"
        assert outbox.payload["after"]["email"] == "updated@tutor.edu"
        assert outbox.payload["after"]["full_name"] == "New Name"


def test_cdc_captures_entity_delete(cdc_session_factory):
    """Verify that deleting an entity generates a CDC 'd' (delete) record."""
    with cdc_session_factory() as session:
        user = UserRecord(
            username="delete_student",
            password_hash="secret_hash",
            email="delete@tutor.edu",
        )
        session.add(user)
        session.commit()

    with cdc_session_factory() as session:
        session.query(OutboxEventRecord).delete()
        session.commit()

    # Perform deletion
    with cdc_session_factory() as session:
        user = session.query(UserRecord).filter_by(username="delete_student").first()
        session.delete(user)
        session.commit()

    with cdc_session_factory() as session:
        outbox = session.query(OutboxEventRecord).filter_by(aggregate_id="delete_student").first()
        assert outbox is not None
        assert outbox.payload["op"] == "d"
        assert outbox.payload["before"]["username"] == "delete_student"
        assert outbox.payload["after"] is None


def test_cdc_envelope_debezium_compatibility():
    """Verify that CDCEnvelope outputs valid Debezium 2.x JSON structure."""
    envelope = CDCEnvelope(
        table="users",
        op=CDCOperation.CREATE,
        before=None,
        after={"username": "debezium_user", "email": "deb@test.com"},
        cdc_source=CDCSource(table="users", db="smart_tutor", schema_name="public"),
    )

    deb_dict = envelope.to_debezium_dict()
    assert "schema" in deb_dict
    assert "payload" in deb_dict
    assert deb_dict["schema"]["name"] == "smart_tutor.public.users.Envelope"
    assert deb_dict["payload"]["op"] == "c"
    assert deb_dict["payload"]["after"]["username"] == "debezium_user"
    assert deb_dict["payload"]["source"]["table"] == "users"


def test_cdc_stream_consumer_dispatch():
    """Verify CDCStreamConsumer routes events to global and table-specific handlers."""
    consumer = CDCStreamConsumer()
    received_global = []
    received_table = []

    consumer.register_handler(lambda env: received_global.append(env))
    consumer.register_handler(lambda env: received_table.append(env), table_name="users")

    envelope = CDCEnvelope(
        table="users",
        op=CDCOperation.UPDATE,
        before={"score": 50},
        after={"score": 80},
    )

    consumer.handle_event(envelope)
    assert len(received_global) == 1
    assert len(received_table) == 1
    assert received_table[0].cdc_source.table == "users"


def test_postgres_trigger_sql_generation():
    """Verify PL/pgSQL CDC trigger generation produces valid DDL."""
    ddl = CDCEngine.generate_postgres_trigger_sql("quiz_results")
    assert "CREATE OR REPLACE FUNCTION fn_cdc_capture_quiz_results()" in ddl
    assert "CREATE TRIGGER trg_cdc_quiz_results" in ddl
    assert "outbox_events" in ddl
