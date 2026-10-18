"""
Tests for Dead Letter Queue (DLQ) in Event Bus and SQS Consumer
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from backend.events.event_bus import InMemoryEventBus, SQSConsumer
from backend.events.event_schemas import BaseEvent


def test_in_memory_event_bus_routes_failed_handler_to_dlq():
    bus = InMemoryEventBus()

    class CustomTestEvent(BaseEvent):
        pass

    def failing_handler(event: BaseEvent):
        raise ValueError("Handler crashed on processing")

    bus.subscribe("test.failure", failing_handler)

    test_event = CustomTestEvent(id="evt-123", source="test", type="test.failure", data={"message": "hello"})
    published = bus.publish(test_event)

    assert published is True
    # Verify DLQ captured the failed event
    dlq_entries = bus.get_dead_letter_events()
    assert len(dlq_entries) == 1
    entry = dlq_entries[0]
    assert entry["event_id"] == "evt-123"
    assert entry["event_type"] == "test.failure"
    assert "Handler crashed" in entry["error"]
    assert entry["retry_count"] == 0


def test_in_memory_event_bus_replays_dlq_events():
    bus = InMemoryEventBus()
    recovered = {"count": 0}

    # Handler fails initially, then succeeds
    should_fail = True

    def toggle_handler(event: BaseEvent):
        nonlocal should_fail
        if should_fail:
            raise RuntimeError("Temporary outage")
        recovered["count"] += 1

    bus.subscribe("test.replay", toggle_handler)

    event = BaseEvent(id="evt-replay-1", source="test", type="test.replay", data={"payload": 42})
    bus.publish(event)
    assert len(bus.get_dead_letter_events()) == 1

    # Replay while still failing
    result1 = bus.replay_dead_letter_events()
    assert result1["replayed"] == 0
    assert result1["still_failing"] == 1
    assert len(bus.get_dead_letter_events()) == 1
    assert bus.get_dead_letter_events()[0]["retry_count"] == 1

    # Fix outage and replay
    should_fail = False
    result2 = bus.replay_dead_letter_events()
    assert result2["replayed"] == 1
    assert result2["still_failing"] == 0
    assert len(bus.get_dead_letter_events()) == 0
    assert recovered["count"] == 1


def test_in_memory_event_bus_purge_dlq():
    bus = InMemoryEventBus()
    bus.subscribe("test.purge", lambda e: 1 / 0)

    bus.publish(BaseEvent(id="e1", source="test", type="test.purge", data={}))
    bus.publish(BaseEvent(id="e2", source="test", type="test.purge", data={}))
    assert len(bus.get_dead_letter_events()) == 2

    purged = bus.purge_dead_letter_queue()
    assert purged == 2
    assert len(bus.get_dead_letter_events()) == 0


def test_sqs_consumer_send_to_dlq():
    consumer = object.__new__(SQSConsumer)
    consumer.queue_url = "https://sqs.us-east-1.amazonaws.com/123/main-queue"
    consumer.dlq_url = "https://sqs.us-east-1.amazonaws.com/123/dlq-queue"
    consumer.max_receive_count = 3
    consumer.client = MagicMock()
    consumer.delete_message = MagicMock(return_value=True)

    fake_message = {
        "MessageId": "msg-101",
        "ReceiptHandle": "rh-101",
        "Body": '{"Message": "{\\"id\\": \\"e1\\", \\"type\\": \\"test\\"}"}',
    }

    sent = consumer.send_to_dlq(fake_message, error="Repeated processing failure")
    assert sent is True
    consumer.client.send_message.assert_called_once()
    call_kwargs = consumer.client.send_message.call_args[1]
    assert call_kwargs["QueueUrl"] == "https://sqs.us-east-1.amazonaws.com/123/dlq-queue"
    assert call_kwargs["MessageAttributes"]["ErrorReason"]["StringValue"] == "Repeated processing failure"
    consumer.delete_message.assert_called_once_with("rh-101")
