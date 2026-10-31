"""SQS worker: receive one job at a time, run it, delete it on success.

Runs in its own container (``python -m backend.jobs worker``) from the
backend image, so API deploys and restarts don't kill running jobs.

- **Long polling.** Each receive waits up to 20 s, so an idle worker makes
  about three requests a minute.
- **Heartbeat.** While a job runs, its visibility timeout is extended every
  ``heartbeat_seconds`` so a long job isn't handed to another receiver.
- **Retries.** A failed job is left on the queue with a growing delay
  (30 s, 60 s, 120 s, ...). After the queue's ``maxReceiveCount`` receives,
  SQS moves it to the dead-letter queue. Unknown or malformed messages take
  the same path, so nothing is silently dropped.
- **Shutdown.** SIGTERM stops polling; a job already running is allowed to
  finish (give the container a ``--stop-timeout`` long enough for that). If
  it's killed anyway, the message reappears after its visibility timeout.
- **Liveness.** ``alive_file`` is touched on every poll, and every 30 s
  while a job runs, so the container health check can tell a stuck worker
  from an idle or busy one.
"""
from __future__ import annotations

import json
import signal
import threading
import time
from pathlib import Path
from typing import Any

from backend.jobs.queue import MESSAGE_VERSION, UnknownJobError, get_job, sqs_client
from backend.logger import get_logger

logger = get_logger(__name__)

DEFAULT_ALIVE_FILE = "/tmp/jobs-worker-alive"  # noqa: S108  # nosec B108 - mtime-only liveness marker, never read
MAX_RETRY_DELAY = 900
ALIVE_TICK_SECONDS = 30


class Worker:
    def __init__(
        self,
        queue_url: str,
        region: str,
        *,
        client: Any = None,
        wait_seconds: int = 20,
        visibility_seconds: int = 900,
        heartbeat_seconds: int | None = None,
        alive_file: str | None = DEFAULT_ALIVE_FILE,
    ):
        self.queue_url = queue_url
        self.client = client or sqs_client(region)
        self.wait_seconds = wait_seconds
        self.visibility_seconds = visibility_seconds
        self.heartbeat_seconds = heartbeat_seconds or max(1, visibility_seconds // 3)
        self.alive_file = Path(alive_file) if alive_file else None
        self._stop = threading.Event()

    def stop(self, *_: Any) -> None:
        if not self._stop.is_set():
            logger.info("Jobs worker stopping after the current job")
        self._stop.set()

    def run_forever(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        logger.info(f"Jobs worker polling {self.queue_url}")
        while not self._stop.is_set():
            self.poll_once()
        logger.info("Jobs worker stopped")

    def poll_once(self) -> bool:
        """Receive and handle at most one message. Returns True if one arrived."""
        self._touch_alive()
        try:
            response = self.client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=self.wait_seconds,
                VisibilityTimeout=self.visibility_seconds,
                AttributeNames=["ApproximateReceiveCount"],
            )
        except Exception as exc:
            logger.error(f"SQS receive failed: {exc}")
            self._stop.wait(5)
            return False

        messages = response.get("Messages", [])
        for message in messages:
            try:
                self.handle(message)
            except Exception as exc:
                # handle() shouldn't raise; if it does, keep the worker alive and
                # let the message retry towards the DLQ instead of crash-looping.
                logger.error(f"Unexpected error handling message {message.get('MessageId')}: {exc!r}", exc_info=True)
                if "ReceiptHandle" in message:
                    self._retry_later(message["ReceiptHandle"], _attempt(message))
        return bool(messages)

    def handle(self, message: dict[str, Any]) -> bool:
        """Run one message's job. Deletes it and returns True on success."""
        receipt = message["ReceiptHandle"]
        attempt = _attempt(message)

        try:
            payload = json.loads(message["Body"])
            if not isinstance(payload, dict):
                raise TypeError(f"message body is {type(payload).__name__}, not an object")
            if payload.get("v") != MESSAGE_VERSION:
                raise ValueError(f"unsupported message version {payload.get('v')!r}")
            name, job_id, args = payload["job"], payload["id"], payload.get("args") or {}
            if not isinstance(name, str) or not isinstance(args, dict):
                raise TypeError("job must be a string and args an object")
            func = get_job(name)
        except (ValueError, KeyError, TypeError, UnknownJobError) as exc:
            logger.error(f"Unprocessable job message {message.get('MessageId')} (attempt {attempt}): {exc!r}")
            self._retry_later(receipt, attempt)
            return False

        started = time.monotonic()
        stop_heartbeat = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat, args=(receipt, stop_heartbeat), name=f"heartbeat:{job_id}", daemon=True
        )
        heartbeat.start()
        try:
            func(**args)
        except Exception as exc:
            logger.error(f"Job {name} ({job_id}) failed on attempt {attempt}: {exc}", exc_info=True)
            stop_heartbeat.set()
            heartbeat.join()
            self._retry_later(receipt, attempt)
            return False
        stop_heartbeat.set()
        heartbeat.join()

        try:
            self.client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt)
        except Exception as exc:
            # The job ran; the message will come back and run again, which jobs must tolerate.
            logger.warning(f"Job {name} ({job_id}) finished but could not be deleted: {exc}")
        logger.info(f"Job {name} ({job_id}) done in {time.monotonic() - started:.1f}s (attempt {attempt})")
        return True

    def _heartbeat(self, receipt: str, done: threading.Event) -> None:
        # Wake often enough to keep the liveness file fresh during a long job;
        # extend visibility every heartbeat_seconds.
        tick = min(self.heartbeat_seconds, ALIVE_TICK_SECONDS)
        last_extend = time.monotonic()
        while not done.wait(tick):
            self._touch_alive()
            if time.monotonic() - last_extend < self.heartbeat_seconds:
                continue
            last_extend = time.monotonic()
            try:
                self.client.change_message_visibility(
                    QueueUrl=self.queue_url, ReceiptHandle=receipt, VisibilityTimeout=self.visibility_seconds
                )
            except Exception as exc:
                logger.warning(f"Could not extend job visibility: {exc}")

    def _retry_later(self, receipt: str, attempt: int) -> None:
        delay = min(30 * 2 ** (attempt - 1), MAX_RETRY_DELAY)
        try:
            self.client.change_message_visibility(
                QueueUrl=self.queue_url, ReceiptHandle=receipt, VisibilityTimeout=delay
            )
        except Exception as exc:
            logger.warning(f"Could not set retry delay: {exc}")

    def _touch_alive(self) -> None:
        if self.alive_file:
            try:
                self.alive_file.touch()
            except OSError:
                pass


def _attempt(message: dict[str, Any]) -> int:
    try:
        return int(message.get("Attributes", {}).get("ApproximateReceiveCount", "1"))
    except (TypeError, ValueError):
        return 1
