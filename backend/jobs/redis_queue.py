"""Redis-backed jobs queue with the slice of the SQS API the worker uses.

``RedisJobsClient`` implements ``send_message``, ``receive_message``,
``delete_message`` and ``change_message_visibility`` with SQS semantics, so
``backend.jobs.worker.Worker`` runs unchanged on Redis: same heartbeats,
retry delays and dead-letter handling. It replaces SQS when moving off AWS
(``JOBS_BACKEND=redis``); Redis already runs next to the API.

Data model, for queue name ``q`` (``JOBS_REDIS_QUEUE``):

- ``q:pending``  sorted set of message id -> time it becomes visible
- ``q:body``     hash of message id -> JSON body
- ``q:receives`` hash of message id -> receive count
- ``q:dlq``      list of dead messages (JSON with id, body, receives, dead_at)

A receive claims the first visible message by moving its visible-at time
``VisibilityTimeout`` seconds ahead, in a WATCH/MULTI transaction so two
workers can't claim the same message. If the worker dies, the message
becomes visible again when that time passes, as with SQS. A message
received more than ``max_receives`` times moves to the DLQ (SQS's
``maxReceiveCount`` redrive). The receipt handle is the message id.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from backend.logger import get_logger

logger = get_logger(__name__)

# Sleep between checks while long-polling an empty queue.
POLL_INTERVAL_SECONDS = 1.0


class RedisJobsClient:
    def __init__(self, redis_client: Any, queue: str, *, max_receives: int = 5, clock: Any = time.time):
        self.redis = redis_client
        self.queue = queue
        self.max_receives = max_receives
        self._clock = clock
        self.pending_key = f"{queue}:pending"
        self.body_key = f"{queue}:body"
        self.receives_key = f"{queue}:receives"
        self.dlq_key = f"{queue}:dlq"

    # ── SQS-compatible API (QueueUrl is accepted and ignored) ───────────

    def send_message(self, QueueUrl: str = "", MessageBody: str = "", DelaySeconds: int = 0) -> dict:  # noqa: N803
        message_id = str(uuid.uuid4())
        pipe = self.redis.pipeline(transaction=True)
        pipe.hset(self.body_key, message_id, MessageBody)
        pipe.zadd(self.pending_key, {message_id: self._clock() + DelaySeconds})
        pipe.execute()
        return {"MessageId": message_id}

    def receive_message(
        self,
        QueueUrl: str = "",  # noqa: N803
        MaxNumberOfMessages: int = 1,  # noqa: N803
        WaitTimeSeconds: int = 0,  # noqa: N803
        VisibilityTimeout: int = 30,  # noqa: N803
        AttributeNames: Any = None,  # noqa: N803
    ) -> dict:
        deadline = self._clock() + WaitTimeSeconds
        messages: list[dict] = []
        while True:
            while len(messages) < MaxNumberOfMessages:
                message = self._claim(VisibilityTimeout)
                if message is None:
                    break
                messages.append(message)
            if messages or self._clock() >= deadline:
                return {"Messages": messages} if messages else {}
            time.sleep(min(POLL_INTERVAL_SECONDS, max(0.0, deadline - self._clock())))

    def delete_message(self, QueueUrl: str = "", ReceiptHandle: str = "") -> dict:  # noqa: N803
        pipe = self.redis.pipeline(transaction=True)
        pipe.zrem(self.pending_key, ReceiptHandle)
        pipe.hdel(self.body_key, ReceiptHandle)
        pipe.hdel(self.receives_key, ReceiptHandle)
        pipe.execute()
        return {}

    def change_message_visibility(
        self, QueueUrl: str = "", ReceiptHandle: str = "", VisibilityTimeout: int = 0  # noqa: N803
    ) -> dict:
        # xx: only update a message that is still queued (not deleted).
        self.redis.zadd(self.pending_key, {ReceiptHandle: self._clock() + VisibilityTimeout}, xx=True)
        return {}

    # ── extras ──────────────────────────────────────────────────────────

    def ping(self) -> bool:
        return bool(self.redis.ping())

    def approximate_counts(self) -> dict:
        return {
            "queued": int(self.redis.zcard(self.pending_key)),
            "dead": int(self.redis.llen(self.dlq_key)),
        }

    def dead_letters(self, limit: int = 100) -> list[dict]:
        return [json.loads(raw) for raw in self.redis.lrange(self.dlq_key, 0, limit - 1)]

    def redrive_dead_letters(self, limit: int = 100) -> int:
        """Move up to ``limit`` dead messages back onto the queue."""
        moved = 0
        for _ in range(limit):
            raw = self.redis.lpop(self.dlq_key)
            if raw is None:
                break
            self.send_message(MessageBody=json.loads(raw)["body"])
            moved += 1
        return moved

    # ── internals ───────────────────────────────────────────────────────

    def _claim(self, visibility_seconds: int) -> dict | None:
        """Claim the first visible message, or return None if there is none."""
        from redis.exceptions import WatchError

        while True:
            now = self._clock()
            with self.redis.pipeline(transaction=True) as pipe:
                try:
                    pipe.watch(self.pending_key)
                    visible = pipe.zrangebyscore(self.pending_key, "-inf", now, start=0, num=1)
                    if not visible:
                        pipe.unwatch()
                        return None
                    message_id = _text(visible[0])
                    pipe.multi()
                    pipe.zadd(self.pending_key, {message_id: now + visibility_seconds})
                    pipe.hincrby(self.receives_key, message_id, 1)
                    pipe.hget(self.body_key, message_id)
                    _, receives, body = pipe.execute()
                except WatchError:
                    continue  # another worker changed the queue; try again

            if body is None:
                # Deleted between the claim and the read; drop the stray entry.
                self.delete_message(ReceiptHandle=message_id)
                continue
            if receives > self.max_receives:
                self._dead_letter(message_id, _text(body), receives - 1)
                continue
            return {
                "MessageId": message_id,
                "ReceiptHandle": message_id,
                "Body": _text(body),
                "Attributes": {"ApproximateReceiveCount": str(receives)},
            }

    def _dead_letter(self, message_id: str, body: str, receives: int) -> None:
        logger.error(f"Job message {message_id} failed {receives} times; moving it to {self.dlq_key}")
        record = json.dumps(
            {"id": message_id, "body": body, "receives": receives, "dead_at": datetime.now(UTC).isoformat()}
        )
        pipe = self.redis.pipeline(transaction=True)
        pipe.rpush(self.dlq_key, record)
        pipe.zrem(self.pending_key, message_id)
        pipe.hdel(self.body_key, message_id)
        pipe.hdel(self.receives_key, message_id)
        pipe.execute()


def _text(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else value


def redis_jobs_client_from_config() -> RedisJobsClient:
    """Client for the queue named by config, on the app's Redis."""
    import redis

    from backend.config import config

    kwargs: dict[str, Any] = {
        "host": config.REDIS_HOST,
        "port": config.REDIS_PORT,
        "db": config.REDIS_DB,
        # Short timeouts so enqueue() falls back quickly when Redis is down.
        "socket_connect_timeout": 3,
        "socket_timeout": 10,
    }
    if config.REDIS_PASSWORD:
        kwargs["password"] = config.REDIS_PASSWORD
    if config.REDIS_SSL:
        kwargs["ssl"] = True
        kwargs["ssl_cert_reqs"] = "required"
    return RedisJobsClient(
        redis.Redis(**kwargs), config.JOBS_REDIS_QUEUE, max_receives=config.JOBS_MAX_RECEIVES
    )
