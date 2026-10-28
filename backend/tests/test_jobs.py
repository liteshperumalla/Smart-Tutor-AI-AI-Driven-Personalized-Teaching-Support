"""Tests for backend/jobs: enqueue (SQS and in-process fallback) and the worker loop."""
from __future__ import annotations

import json
import os
import threading
from unittest.mock import MagicMock, patch

import pytest

from backend.config import config
from backend.jobs import queue
from backend.jobs.__main__ import main as jobs_cli
from backend.jobs.queue import UnknownJobError, build_message, enqueue, job
from backend.jobs.worker import Worker

QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/smart-tutor-jobs"
calls: list = []


@job("test.record")
def record(**kwargs):
    calls.append(kwargs)


@job("test.explode")
def explode(**kwargs):
    raise RuntimeError("boom")


@pytest.fixture(autouse=True)
def reset_calls():
    calls.clear()


@pytest.fixture
def with_queue(monkeypatch):
    monkeypatch.setattr(config, "JOBS_QUEUE_URL", QUEUE_URL)
    monkeypatch.setattr(config, "JOBS_REGION", "us-east-1")
    client = MagicMock()
    with patch.object(queue, "sqs_client", return_value=client):
        yield client


def message(name="test.record", args=None, attempt=1, **overrides):
    body = {**build_message(name, args or {}), **overrides}
    return {
        "MessageId": "m-1",
        "ReceiptHandle": "rh-1",
        "Body": json.dumps(body),
        "Attributes": {"ApproximateReceiveCount": str(attempt)},
    }


def wait_for_threads(prefix="job:"):
    for t in threading.enumerate():
        if t.name.startswith(prefix):
            t.join(timeout=5)


class TestEnqueue:
    def test_sends_a_versioned_message_to_sqs(self, with_queue):
        job_id = enqueue("test.record", resource_id="r1", count=2)

        kwargs = with_queue.send_message.call_args.kwargs
        assert kwargs["QueueUrl"] == QUEUE_URL
        body = json.loads(kwargs["MessageBody"])
        assert body["v"] == 1
        assert body["id"] == job_id
        assert body["job"] == "test.record"
        assert body["args"] == {"resource_id": "r1", "count": 2}
        assert calls == []  # the worker runs it, not this process

    def test_without_a_queue_runs_in_a_thread(self, monkeypatch):
        monkeypatch.setattr(config, "JOBS_QUEUE_URL", "")
        enqueue("test.record", resource_id="r1")
        wait_for_threads()
        assert calls == [{"resource_id": "r1"}]

    def test_falls_back_to_a_thread_when_sqs_fails(self, with_queue):
        with_queue.send_message.side_effect = RuntimeError("no route to sqs")
        enqueue("test.record", resource_id="r1")
        wait_for_threads()
        assert calls == [{"resource_id": "r1"}]

    def test_unknown_job_is_rejected_before_sending(self, with_queue):
        with pytest.raises(UnknownJobError):
            enqueue("does.not.exist")
        with_queue.send_message.assert_not_called()

    def test_unserialisable_args_are_rejected_before_sending(self, with_queue):
        with pytest.raises(TypeError):
            enqueue("test.record", when=object())
        with_queue.send_message.assert_not_called()

    def test_registering_a_different_function_under_a_taken_name_fails(self):
        with pytest.raises(ValueError):
            job("test.record")(lambda: None)


class TestSqsClient:
    def test_fails_fast_but_outlasts_the_long_poll(self):
        queue.sqs_client.cache_clear()
        try:
            cfg = queue.sqs_client("us-east-1").meta.config
        finally:
            queue.sqs_client.cache_clear()
        assert cfg.connect_timeout <= 5
        assert cfg.read_timeout > 20
        # botocore stores max_attempts (retries) as total_max_attempts (retries + 1).
        assert cfg.retries["total_max_attempts"] <= 3


class TestWorker:
    def make_worker(self, client, **kwargs):
        return Worker(QUEUE_URL, "us-east-1", client=client, alive_file=None, **kwargs)

    def test_runs_the_job_and_deletes_the_message(self):
        client = MagicMock()
        assert self.make_worker(client).handle(message(args={"resource_id": "r1"})) is True
        assert calls == [{"resource_id": "r1"}]
        client.delete_message.assert_called_once_with(QueueUrl=QUEUE_URL, ReceiptHandle="rh-1")

    @pytest.mark.parametrize("attempt,delay", [(1, 30), (2, 60), (3, 120), (10, 900)])
    def test_failed_job_stays_queued_with_backoff(self, attempt, delay):
        client = MagicMock()
        assert self.make_worker(client).handle(message("test.explode", attempt=attempt)) is False
        client.delete_message.assert_not_called()
        client.change_message_visibility.assert_called_once_with(
            QueueUrl=QUEUE_URL, ReceiptHandle="rh-1", VisibilityTimeout=delay
        )

    @pytest.mark.parametrize(
        "msg",
        [
            message("does.not.exist"),
            message(v=99),
            {"MessageId": "m-1", "ReceiptHandle": "rh-1", "Body": "not json"},
            {"MessageId": "m-1", "ReceiptHandle": "rh-1", "Body": "[1]"},
            {"MessageId": "m-1", "ReceiptHandle": "rh-1", "Body": "123"},
            {"MessageId": "m-1", "ReceiptHandle": "rh-1", "Body": "null"},
            message(args=None, job=["test.record"]),
            {"MessageId": "m-1", "ReceiptHandle": "rh-1",
             "Body": json.dumps({"v": 1, "id": "j", "job": "test.record", "args": [1]})},
        ],
        ids=["unknown-job", "future-version", "malformed", "array", "number", "null", "job-not-str", "args-not-object"],
    )
    def test_unprocessable_messages_are_left_for_the_dlq(self, msg):
        client = MagicMock()
        assert self.make_worker(client).handle(msg) is False
        client.delete_message.assert_not_called()
        client.change_message_visibility.assert_called_once()

    def test_heartbeat_extends_visibility_during_a_long_job(self):
        client = MagicMock()
        release = threading.Event()

        @job("test.slow")
        def slow():
            release.wait(5)

        worker = self.make_worker(client, visibility_seconds=60, heartbeat_seconds=0.05)
        runner = threading.Thread(target=worker.handle, args=(message("test.slow"),))
        runner.start()
        threading.Event().wait(0.3)
        release.set()
        runner.join(timeout=5)

        extends = [
            c for c in client.change_message_visibility.call_args_list if c.kwargs["VisibilityTimeout"] == 60
        ]
        assert extends, "visibility was never extended"
        client.delete_message.assert_called_once()

    def test_poll_once_uses_long_polling_one_message_at_a_time(self):
        client = MagicMock()
        client.receive_message.return_value = {"Messages": [message(args={"n": 1})]}
        assert self.make_worker(client).poll_once() is True
        kwargs = client.receive_message.call_args.kwargs
        assert kwargs["MaxNumberOfMessages"] == 1
        assert kwargs["WaitTimeSeconds"] == 20
        assert calls == [{"n": 1}]

    def test_an_unexpected_error_in_handle_does_not_crash_the_loop(self):
        client = MagicMock()
        client.receive_message.return_value = {"Messages": [message()]}
        worker = self.make_worker(client)
        with patch.object(worker, "handle", side_effect=AttributeError("surprise")):
            assert worker.poll_once() is True
        client.change_message_visibility.assert_called_once_with(
            QueueUrl=QUEUE_URL, ReceiptHandle="rh-1", VisibilityTimeout=30
        )

    def test_receive_errors_do_not_crash_the_loop(self):
        client = MagicMock()
        client.receive_message.side_effect = RuntimeError("throttled")
        worker = self.make_worker(client)
        worker.stop()  # skip the 5 s back-off
        assert worker.poll_once() is False

    def test_poll_touches_the_alive_file(self, tmp_path):
        alive = tmp_path / "alive"
        client = MagicMock()
        client.receive_message.return_value = {}
        Worker(QUEUE_URL, "us-east-1", client=client, alive_file=str(alive)).poll_once()
        assert alive.exists()


class TestCli:
    def test_worker_refuses_to_start_without_a_queue(self, monkeypatch):
        monkeypatch.setattr(config, "JOBS_QUEUE_URL", "")
        assert jobs_cli(["worker"]) == 2

    def test_healthcheck_reads_the_file_the_worker_touches(self, tmp_path, monkeypatch):
        from backend.jobs import __main__ as cli
        from backend.jobs import worker

        assert cli.ALIVE_FILE == worker.DEFAULT_ALIVE_FILE
        alive = tmp_path / "alive"
        monkeypatch.setattr(cli, "ALIVE_FILE", str(alive))
        assert jobs_cli(["healthcheck"]) == 1  # worker never polled
        alive.touch()
        assert jobs_cli(["healthcheck"]) == 0
        old = alive.stat().st_mtime - 300
        os.utime(alive, (old, old))
        assert jobs_cli(["healthcheck"]) == 1  # stuck

    def test_ping_fails_when_sqs_is_unreachable(self, with_queue, capsys):
        with_queue.send_message.side_effect = RuntimeError("AccessDenied")
        assert jobs_cli(["ping"]) == 1
        assert "AccessDenied" in capsys.readouterr().err

    def test_ping_queues_a_ping_job(self, with_queue):
        assert jobs_cli(["ping", "hello"]) == 0
        body = json.loads(with_queue.send_message.call_args.kwargs["MessageBody"])
        assert body["job"] == "ping"
        assert body["args"] == {"note": "hello"}
