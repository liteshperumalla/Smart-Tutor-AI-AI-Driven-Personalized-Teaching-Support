"""
Event Bus Implementation
Supports AWS EventBridge, SNS, and SQS for event-driven architecture
"""

import json
import logging
from typing import List, Optional, Callable, Dict, Any
from abc import ABC, abstractmethod
from datetime import datetime

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
        logger.info("Using in-memory event bus")

    def publish(self, event: BaseEvent) -> bool:
        """Publish event to in-memory bus"""
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
                        logger.error(f"Event handler failed: {e}", exc_info=True)

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

    def clear(self):
        """Clear all events"""
        self.events.clear()
        logger.info("Cleared in-memory event bus")


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
    AWS SQS consumer for async event processing
    """

    def __init__(self, queue_url: str, region: str = "us-east-1"):
        if not AWS_AVAILABLE:
            raise RuntimeError("boto3 not installed. Cannot use SQS consumer.")

        self.queue_url = queue_url
        self.region = region
        self.client = boto3.client('sqs', region_name=region)

        logger.info(f"SQS consumer created for queue: {queue_url}")

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
            logger.debug(f"Deleted message from SQS")
            return True

        except ClientError as e:
            logger.error(f"SQS delete error: {e}", exc_info=True)
            return False

    def process_messages(self, handler: Callable[[BaseEvent], bool], batch_size: int = 10):
        """
        Process messages from queue

        Args:
            handler: Function to process each event
            batch_size: Messages to receive per batch
        """
        while True:
            messages = self.receive_messages(max_messages=batch_size)

            if not messages:
                continue

            for message in messages:
                try:
                    # Parse event from message
                    body = json.loads(message['Body'])
                    event_data = json.loads(body.get('Message', '{}'))

                    # Reconstruct event (simplified)
                    event = BaseEvent(**event_data)

                    # Process event
                    success = handler(event)

                    # Delete if successful
                    if success:
                        self.delete_message(message['ReceiptHandle'])
                    else:
                        logger.warning(f"Handler returned False for event: {event.id}")

                except Exception as e:
                    logger.error(f"Failed to process message: {e}", exc_info=True)


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
