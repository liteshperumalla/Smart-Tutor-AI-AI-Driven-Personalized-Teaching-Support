"""
Event Bus Implementation
Supports AWS EventBridge, SNS, and SQS for event-driven architecture
"""

import json
import logging
import os
from typing import List, Optional, Callable, Dict, Any
from abc import ABC, abstractmethod
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False
    logger.warning("boto3 not installed. Event bus will use in-memory mode.")

from .event_schemas import BaseEvent


class EventBusBackend(ABC):
    """Abstract base class for event bus backends"""

    @abstractmethod
    def publish(self, event: BaseEvent) -> bool:
        """Publish event to bus"""
        pass

    @abstractmethod
    def publish_batch(self, events: List[BaseEvent]) -> Dict[str, Any]:
        """Publish multiple events"""
        pass


class InMemoryEventBus(EventBusBackend):
    """
    In-memory event bus for testing and development
    Stores events in memory and allows subscription
    """

    def __init__(self):
        self.events: List[BaseEvent] = []
        self.subscribers: Dict[str, List[Callable]] = {}
        self.dead_letter_queue: List[Dict[str, Any]] = []
        logger.info("Using in-memory event bus with Dead Letter Queue (DLQ) enabled")

    def publish(self, event: BaseEvent) -> bool:
        """Publish event to in-memory bus with DLQ routing on handler failures"""
        try:
            self.events.append(event)
            logger.info(f"Published event: {event.type} (id={event.id})")

            # Notify subscribers
            event_type = event.type
            if event_type in self.subscribers:
                for handler in self.subscribers[event_type]:
                    try:
                        handler(event)
                    except Exception as e:
                        logger.error(f"Event handler '{getattr(handler, '__name__', str(handler))}' failed: {e}", exc_info=True)
                        # Route unhandled handler failure to Dead Letter Queue
                        event_payload = (
                            event.model_dump() if hasattr(event, "model_dump")
                            else (event.to_dict() if hasattr(event, "to_dict") else getattr(event, "data", {}))
                        )
                        dlq_entry = {
                            "event_id": getattr(event, "id", None),
                            "event_type": event_type,
                            "source": getattr(event, "source", "in_memory_event_bus"),
                            "event": event_payload,
                            "handler": getattr(handler, "__name__", str(handler)),
                            "error": str(e),
                            "failed_at": datetime.now(timezone.utc).isoformat(),
                            "retry_count": 0,
                        }
                        self.dead_letter_queue.append(dlq_entry)
                        logger.warning(
                            "Event %s routed to InMemory Dead Letter Queue (DLQ depth=%d)",
                            getattr(event, "id", None), len(self.dead_letter_queue),
                        )

            return True

        except Exception as e:
            logger.error(f"Failed to publish event: {e}", exc_info=True)
            return False

    def publish_batch(self, events: List[BaseEvent]) -> Dict[str, Any]:
        """Publish multiple events"""
        successful = 0
        failed = 0

        for event in events:
            if self.publish(event):
                successful += 1
            else:
                failed += 1

        return {
            "successful": successful,
            "failed": failed,
        }

    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        logger.info(f"Subscribed to event type: {event_type}")

    def get_events(self, event_type: Optional[str] = None, limit: int = 100) -> List[BaseEvent]:
        """Get events from memory"""
        if event_type:
            return [e for e in self.events if e.type == event_type][:limit]
        return self.events[:limit]

    def get_dead_letter_events(
        self, event_type: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve failed events from Dead Letter Queue"""
        if event_type:
            return [
                entry for entry in self.dead_letter_queue
                if entry.get("event_type") == event_type
            ][:limit]
        return self.dead_letter_queue[:limit]

    def purge_dead_letter_queue(self) -> int:
        """Clear Dead Letter Queue and return number of purged entries"""
        count = len(self.dead_letter_queue)
        self.dead_letter_queue.clear()
        logger.info("Purged %d entries from Dead Letter Queue", count)
        return count

    def replay_dead_letter_events(self, limit: int = 100) -> Dict[str, int]:
        """
        Re-dispatch DLQ events to their registered subscribers.
        Removes successfully handled events from the DLQ.
        """
        replayed = 0
        still_failing = 0
        remaining = []

        candidates = self.dead_letter_queue[:limit]
        remaining_uninspected = self.dead_letter_queue[limit:]

        for item in candidates:
            event_type = item.get("event_type")
            raw_event = item.get("event", {})
            try:
                event_data = raw_event.get("data", raw_event) if isinstance(raw_event, dict) else raw_event
                event = BaseEvent(
                    id=item.get("event_id"),
                    source=item.get("source", "dlq_replay"),
                    type=event_type,
                    data=event_data,
                )
                success = True
                if event_type in self.subscribers:
                    for handler in self.subscribers[event_type]:
                        try:
                            handler(event)
                        except Exception as exc:
                            success = False
                            item["error"] = str(exc)
                            item["retry_count"] = item.get("retry_count", 0) + 1
                            item["failed_at"] = datetime.now(timezone.utc).isoformat()
                            break

                if success:
                    replayed += 1
                else:
                    still_failing += 1
                    remaining.append(item)
            except Exception as exc:
                still_failing += 1
                item["error"] = str(exc)
                item["retry_count"] = item.get("retry_count", 0) + 1
                item["failed_at"] = datetime.now(timezone.utc).isoformat()
                remaining.append(item)

        self.dead_letter_queue = remaining + remaining_uninspected
        logger.info(
            "DLQ Replay: %d replayed, %d still failing, %d remaining",
            replayed,
            still_failing,
            len(self.dead_letter_queue),
        )
        return {
            "replayed": replayed,
            "still_failing": still_failing,
            "remaining": len(self.dead_letter_queue),
        }

    def clear(self):
        """Clear all events and DLQ entries"""
        self.events.clear()
        self.dead_letter_queue.clear()
        logger.info("Cleared in-memory event bus and Dead Letter Queue")


class EventBridgeBackend(EventBusBackend):
    """
    AWS EventBridge backend for production
    """

    def __init__(self, event_bus_name: str, region: str = "us-east-1"):
        if not AWS_AVAILABLE:
            raise RuntimeError("boto3 not installed. Cannot use EventBridge backend.")

        self.event_bus_name = event_bus_name
        self.region = region
        self.client = boto3.client('events', region_name=region)

        logger.info(f"Using EventBridge: {event_bus_name} in {region}")

    def publish(self, event: BaseEvent) -> bool:
        """Publish event to EventBridge"""
        try:
            entry = event.to_eventbridge_entry(self.event_bus_name)

            response = self.client.put_events(Entries=[entry])

            # Check for failures
            if response.get('FailedEntryCount', 0) > 0:
                logger.error(f"Failed to publish event: {response}")
                return False

            logger.info(f"Published event to EventBridge: {event.type} (id={event.id})")
            return True

        except ClientError as e:
            logger.error(f"EventBridge client error: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Failed to publish event: {e}", exc_info=True)
            return False

    def publish_batch(self, events: List[BaseEvent]) -> Dict[str, Any]:
        """
        Publish multiple events to EventBridge
        EventBridge supports up to 10 events per batch
        """
        if not events:
            return {"successful": 0, "failed": 0}

        entries = [event.to_eventbridge_entry(self.event_bus_name) for event in events]

        # EventBridge batch limit is 10
        successful = 0
        failed = 0

        # Process in batches of 10
        for i in range(0, len(entries), 10):
            batch = entries[i:i+10]

            try:
                response = self.client.put_events(Entries=batch)

                failed_count = response.get('FailedEntryCount', 0)
                successful += len(batch) - failed_count
                failed += failed_count

                if failed_count > 0:
                    logger.error(f"Failed entries in batch: {response.get('Entries', [])}")

            except ClientError as e:
                logger.error(f"EventBridge batch error: {e}", exc_info=True)
                failed += len(batch)

        logger.info(f"Batch publish: {successful} successful, {failed} failed")

        return {
            "successful": successful,
            "failed": failed,
        }


class SNSBackend(EventBusBackend):
    """
    AWS SNS backend for pub/sub messaging
    """

    def __init__(self, topic_arn: str, region: str = "us-east-1"):
        if not AWS_AVAILABLE:
            raise RuntimeError("boto3 not installed. Cannot use SNS backend.")

        self.topic_arn = topic_arn
        self.region = region
        self.client = boto3.client('sns', region_name=region)

        logger.info(f"Using SNS topic: {topic_arn}")

    def publish(self, event: BaseEvent) -> bool:
        """Publish event to SNS topic"""
        try:
            message_data = event.to_sns_message()

            response = self.client.publish(
                TopicArn=self.topic_arn,
                **message_data,
            )

            logger.info(f"Published event to SNS: {event.type} (MessageId={response.get('MessageId')})")
            return True

        except ClientError as e:
            logger.error(f"SNS client error: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Failed to publish event: {e}", exc_info=True)
            return False

    def publish_batch(self, events: List[BaseEvent]) -> Dict[str, Any]:
        """Publish multiple events to SNS"""
        successful = 0
        failed = 0

        for event in events:
            if self.publish(event):
                successful += 1
            else:
                failed += 1

        return {
            "successful": successful,
            "failed": failed,
        }


class SQSConsumer:
    """
    AWS SQS consumer for async event processing with Dead Letter Queue (DLQ) support
    """

    def __init__(
        self,
        queue_url: str,
        region: str = "us-east-1",
        dlq_url: Optional[str] = None,
        max_receive_count: int = 3,
    ):
        if not AWS_AVAILABLE:
            raise RuntimeError("boto3 not installed. Cannot use SQS consumer.")

        self.queue_url = queue_url
        self.region = region
        self.client = boto3.client('sqs', region_name=region)
        self.dlq_url = dlq_url or os.getenv("SQS_DLQ_URL")
        self.max_receive_count = max_receive_count
        self._running = True

        logger.info(
            "SQS consumer created for queue: %s (dlq=%s, max_receive_count=%d)",
            queue_url, self.dlq_url, self.max_receive_count
        )

    def stop(self):
        """Signal the consumer loop to stop gracefully"""
        self._running = False
        logger.info("SQS consumer stopping...")

    def send_to_dlq(self, message: Dict[str, Any], error: str) -> bool:
        """Forward an unprocessable poison message to the Dead Letter Queue"""
        if not self.dlq_url:
            logger.warning(
                "DLQ not configured; cannot route failed message %s to DLQ",
                message.get("MessageId"),
            )
            return False

        try:
            self.client.send_message(
                QueueUrl=self.dlq_url,
                MessageBody=message.get("Body", "{}"),
                MessageAttributes={
                    "OriginalQueueUrl": {
                        "StringValue": self.queue_url,
                        "DataType": "String",
                    },
                    "OriginalMessageId": {
                        "StringValue": str(message.get("MessageId", "")),
                        "DataType": "String",
                    },
                    "ErrorReason": {
                        "StringValue": str(error)[:256],
                        "DataType": "String",
                    },
                    "FailedAt": {
                        "StringValue": datetime.now(timezone.utc).isoformat(),
                        "DataType": "String",
                    },
                },
            )
            logger.info(
                "Routed message %s to DLQ: %s (error=%s)",
                message.get("MessageId"), self.dlq_url, error,
            )
            self.delete_message(message["ReceiptHandle"])
            return True
        except Exception as exc:
            logger.error(
                "Failed sending message %s to DLQ: %s",
                message.get("MessageId"), exc, exc_info=True,
            )
            return False

    def receive_messages(
        self,
        max_messages: int = 10,
        wait_time_seconds: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Receive messages from SQS queue

        Args:
            max_messages: Max messages to receive (1-10)
            wait_time_seconds: Long polling wait time

        Returns:
            List of messages
        """
        try:
            response = self.client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=min(max_messages, 10),
                WaitTimeSeconds=wait_time_seconds,
                MessageAttributeNames=['All'],
                AttributeNames=['ApproximateReceiveCount'],
            )

            messages = response.get('Messages', [])
            logger.info(f"Received {len(messages)} messages from SQS")

            return messages

        except ClientError as e:
            logger.error(f"SQS receive error: {e}", exc_info=True)
            return []

    def delete_message(self, receipt_handle: str) -> bool:
        """Delete message from queue after processing"""
        try:
            self.client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle,
            )
            logger.debug("Deleted message from SQS")
            return True

        except ClientError as e:
            logger.error(f"SQS delete error: {e}", exc_info=True)
            return False

    def process_messages(self, handler: Callable[[BaseEvent], bool], batch_size: int = 10):
        """
        Process messages from queue with DLQ routing

        Args:
            handler: Function to process each event
            batch_size: Messages to receive per batch
        """
        while self._running:
            messages = self.receive_messages(max_messages=batch_size)

            if not messages:
                continue

            for message in messages:
                if not self._running:
                    break

                receive_count = 1
                attributes = message.get('Attributes', {})
                if 'ApproximateReceiveCount' in attributes:
                    try:
                        receive_count = int(attributes['ApproximateReceiveCount'])
                    except ValueError:
                        receive_count = 1

                # If receive count already exceeded limit, route to DLQ immediately
                if receive_count >= self.max_receive_count and self.dlq_url:
                    logger.warning(
                        "Message %s exceeded max_receive_count (%d/%d), routing to DLQ",
                        message.get("MessageId"), receive_count, self.max_receive_count,
                    )
                    self.send_to_dlq(message, error="Max receive count exceeded")
                    continue

                try:
                    # Parse event from message
                    body = json.loads(message['Body'])
                    event_data = json.loads(body.get('Message', '{}'))

                    # Reconstruct event
                    event = BaseEvent(**event_data)

                    # Process event
                    success = handler(event)

                    # Delete if successful
                    if success:
                        self.delete_message(message['ReceiptHandle'])
                    else:
                        logger.warning(f"Handler returned False for event: {event.id}")
                        if receive_count >= self.max_receive_count:
                            self.send_to_dlq(message, error="Handler returned False")

                except Exception as e:
                    logger.error(f"Failed to process message: {e}", exc_info=True)
                    if receive_count >= self.max_receive_count:
                        self.send_to_dlq(message, error=str(e))


class EventBus:
    """
    Unified event bus that supports multiple backends
    """

    def __init__(
        self,
        backend: EventBusBackend,
        enable_local_cache: bool = True,
    ):
        """
        Initialize event bus

        Args:
            backend: Backend implementation (InMemory, EventBridge, SNS)
            enable_local_cache: Cache events locally for debugging
        """
        self.backend = backend
        self.enable_local_cache = enable_local_cache
        self.local_cache: List[BaseEvent] = [] if enable_local_cache else None

    def publish(self, event: BaseEvent) -> bool:
        """Publish event"""
        success = self.backend.publish(event)

        if success and self.enable_local_cache:
            self.local_cache.append(event)

        return success

    def publish_batch(self, events: List[BaseEvent]) -> Dict[str, Any]:
        """Publish multiple events"""
        result = self.backend.publish_batch(events)

        if self.enable_local_cache and result.get('successful', 0) > 0:
            self.local_cache.extend(events)

        return result

    def get_cached_events(self, limit: int = 100) -> List[BaseEvent]:
        """Get locally cached events (for debugging)"""
        if not self.enable_local_cache:
            return []
        return self.local_cache[-limit:]

    def get_dead_letter_events(
        self, event_type: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve dead-letter queue entries if supported by active backend"""
        if hasattr(self.backend, "get_dead_letter_events"):
            return self.backend.get_dead_letter_events(event_type, limit)
        return []

    def purge_dead_letter_queue(self) -> int:
        """Purge dead-letter entries from active backend"""
        if hasattr(self.backend, "purge_dead_letter_queue"):
            return self.backend.purge_dead_letter_queue()
        return 0

    def replay_dead_letter_events(self, limit: int = 100) -> Dict[str, int]:
        """Replay dead-letter entries through active backend"""
        if hasattr(self.backend, "replay_dead_letter_events"):
            return self.backend.replay_dead_letter_events(limit)
        return {"replayed": 0, "still_failing": 0, "remaining": 0}


# Global event bus instance
_event_bus: Optional[EventBus] = None


def init_event_bus(
    backend_type: Optional[str] = None,
    event_bus_name: Optional[str] = None,
    topic_arn: Optional[str] = None,
    region: Optional[str] = None,
) -> EventBus:
    """
    Initialize global event bus

    Args:
        backend_type: "inmemory", "eventbridge", or "sns".
            Defaults to "inmemory" when CLOUD_PROVIDER=local, else "inmemory".
        event_bus_name: EventBridge event bus name
        topic_arn: SNS topic ARN
        region: AWS region (defaults to config.AWS_REGION)

    Returns:
        EventBus instance
    """
    import os

    global _event_bus

    if backend_type is None:
        backend_type = os.getenv("EVENT_BUS_BACKEND", "inmemory")
    if region is None:
        region = os.getenv("AWS_REGION", "us-east-1")

    if backend_type == "eventbridge":
        if not event_bus_name:
            raise ValueError("event_bus_name required for EventBridge backend")
        backend = EventBridgeBackend(event_bus_name, region)

    elif backend_type == "sns":
        if not topic_arn:
            raise ValueError("topic_arn required for SNS backend")
        backend = SNSBackend(topic_arn, region)

    else:
        # Default to in-memory (cloud-agnostic)
        backend = InMemoryEventBus()

    _event_bus = EventBus(backend, enable_local_cache=True)

    logger.info(f"Event bus initialized with {backend_type} backend")

    return _event_bus


def get_event_bus() -> EventBus:
    """Get global event bus instance"""
    global _event_bus

    if _event_bus is None:
        # Auto-initialize with in-memory backend
        _event_bus = init_event_bus()

    return _event_bus


# Convenience functions

def publish_event(event: BaseEvent) -> bool:
    """Publish event to global event bus"""
    bus = get_event_bus()
    return bus.publish(event)


def publish_events(events: List[BaseEvent]) -> Dict[str, Any]:
    """Publish multiple events to global event bus"""
    bus = get_event_bus()
    return bus.publish_batch(events)
