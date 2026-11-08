"""Redis jobs queue: SQS-style semantics, so the SQS worker runs on it unchanged."""

import json
import threading

import fakeredis
import pytest

from backend.config import config
from backend.jobs import queue
from backend.jobs.queue import build_message, enqueue, job, jobs_backend
from backend.jobs.redis_queue import RedisJobsClient
from backend.jobs.worker import Worker

calls = []


@job("test.redis_record")
def _record(**kwargs):
    calls.append(kwargs)


@job("test.redis_fail")
def _fail(**kwargs):
    raise RuntimeError("boom")


class Clock:
    def __init__(self, now=1_000.0):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture(autouse=True)
def reset_calls():
    calls.clear()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def client(clock):
    return RedisJobsClient(fakeredis.FakeRedis(), "test:jobs", max_receives=3, clock=clock)


def body(name="test.redis_record", **args):
    return json.dumps(build_message(name, args))


class TestRedisJobsClient:
    def test_send_then_receive_returns_the_message(self, client):
        sent = client.send_message(MessageBody="hello")
        got = client.receive_message(VisibilityTimeout=60)["Messages"]
        assert len(got) == 1
        assert got[0]["MessageId"] == sent["MessageId"]
        assert got[0]["ReceiptHandle"] == sent["MessageId"]
        assert got[0]["Body"] == "hello"
        assert got[0]["Attributes"]["ApproximateReceiveCount"] == "1"

    def test_received_message_is_hidden_until_visibility_ends(self, client, clock):
        client.send_message(MessageBody="x")
        assert client.receive_message(VisibilityTimeout=60)
        assert client.receive_message() == {}
        clock.now += 61
        again = client.receive_message(VisibilityTimeout=60)["Messages"][0]
        assert again["Attributes"]["ApproximateReceiveCount"] == "2"

    def test_delete_removes_the_message(self, client, clock):
        client.send_message(MessageBody="x")
        receipt = client.receive_message(VisibilityTimeout=60)["Messages"][0]["ReceiptHandle"]
        client.delete_message(ReceiptHandle=receipt)
        clock.now += 120
        assert client.receive_message() == {}
        assert client.approximate_counts() == {"queued": 0, "dead": 0}

    def test_change_visibility_delays_redelivery(self, client, clock):
        client.send_message(MessageBody="x")
        receipt = client.receive_message(VisibilityTimeout=10)["Messages"][0]["ReceiptHandle"]
        client.change_message_visibility(ReceiptHandle=receipt, VisibilityTimeout=300)
        clock.now += 60
        assert client.receive_message() == {}
        clock.now += 300
        assert client.receive_message()["Messages"]

    def test_change_visibility_ignores_deleted_messages(self, client):
        client.send_message(MessageBody="x")
        receipt = client.receive_message(VisibilityTimeout=10)["Messages"][0]["ReceiptHandle"]
        client.delete_message(ReceiptHandle=receipt)
        client.change_message_visibility(ReceiptHandle=receipt, VisibilityTimeout=0)
        assert client.approximate_counts()["queued"] == 0

    def test_delay_seconds(self, client, clock):
        client.send_message(MessageBody="later", DelaySeconds=30)
        assert client.receive_message() == {}
        clock.now += 30
        assert client.receive_message()["Messages"][0]["Body"] == "later"

    def test_message_goes_to_dlq_after_max_receives(self, client, clock):
        client.send_message(MessageBody="poison")
        for _ in range(3):
            assert client.receive_message(VisibilityTimeout=0)["Messages"]
        # Fourth receive exceeds max_receives=3: redriven, not delivered.
        assert client.receive_message(VisibilityTimeout=0) == {}
        dead = client.dead_letters()
        assert [d["body"] for d in dead] == ["poison"]
        assert dead[0]["receives"] == 3
        assert client.approximate_counts() == {"queued": 0, "dead": 1}

    def test_redrive_puts_dead_letters_back(self, client):
        client.send_message(MessageBody="poison")
        for _ in range(4):
            client.receive_message(VisibilityTimeout=0)
        assert client.redrive_dead_letters() == 1
        got = client.receive_message()["Messages"][0]
        assert got["Body"] == "poison"
        assert got["Attributes"]["ApproximateReceiveCount"] == "1"

    def test_two_receivers_never_get_the_same_message(self):
        shared = fakeredis.FakeServer()
        clients = [RedisJobsClient(fakeredis.FakeRedis(server=shared), "race") for _ in range(4)]
        for i in range(40):
            clients[0].send_message(MessageBody=str(i))
        seen, lock = [], threading.Lock()

        def drain(c):
            while True:
                got = c.receive_message(VisibilityTimeout=600).get("Messages", [])
                if not got:
                    return
                with lock:
                    seen.append(got[0]["Body"])

        threads = [threading.Thread(target=drain, args=(c,)) for c in clients]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert sorted(seen, key=int) == [str(i) for i in range(40)]


class TestWorkerOnRedis:
    def make_worker(self, client):
        return Worker("test:jobs", "unused", client=client, wait_seconds=0, alive_file=None)

    def test_worker_runs_and_deletes_the_job(self, client):
        client.send_message(MessageBody=body(resource_id="r1"))
        assert self.make_worker(client).poll_once() is True
        assert calls == [{"resource_id": "r1"}]
        assert client.approximate_counts() == {"queued": 0, "dead": 0}

    def test_failed_job_retries_with_backoff_then_dead_letters(self, client, clock):
        worker = self.make_worker(client)
        client.send_message(MessageBody=body("test.redis_fail"))
        for _ in range(3):
            assert worker.poll_once() is True
            clock.now += 10_000  # past any retry delay
        assert worker.poll_once() is False
        assert client.approximate_counts() == {"queued": 0, "dead": 1}

    def test_retry_delay_hides_the_message(self, client, clock):
        worker = self.make_worker(client)
        client.send_message(MessageBody=body("test.redis_fail"))
        worker.poll_once()
        clock.now += 29
        assert worker.poll_once() is False  # first retry waits 30 s
        clock.now += 2
        assert worker.poll_once() is True


class TestBackendSelection:
    @pytest.mark.parametrize(
        "backend,url,expected",
        [
            ("", "", "inline"),
            ("", "https://sqs/q", "sqs"),
            ("redis", "", "redis"),
            ("redis", "https://sqs/q", "redis"),
            ("sqs", "", "inline"),
            ("inline", "https://sqs/q", "inline"),
            ("bogus", "https://sqs/q", "inline"),
        ],
    )
    def test_jobs_backend(self, monkeypatch, backend, url, expected):
        monkeypatch.setattr(config, "JOBS_BACKEND", backend)
        monkeypatch.setattr(config, "JOBS_QUEUE_URL", url)
        assert jobs_backend() == expected

    def test_enqueue_sends_to_redis(self, monkeypatch, client):
        monkeypatch.setattr(config, "JOBS_BACKEND", "redis")
        monkeypatch.setattr(queue, "_redis_client", client)
        job_id = enqueue("test.redis_record", resource_id="r9")
        message = client.receive_message()["Messages"][0]
        assert json.loads(message["Body"])["id"] == job_id
        assert calls == []  # the worker runs it, not this process

    def test_enqueue_falls_back_to_a_thread_when_redis_fails(self, monkeypatch):
        class Down:
            def send_message(self, **kwargs):
                raise ConnectionError("redis down")

        monkeypatch.setattr(config, "JOBS_BACKEND", "redis")
        monkeypatch.setattr(queue, "_redis_client", Down())
        enqueue("test.redis_record", resource_id="r2")
        for t in threading.enumerate():
            if t.name.startswith("job:"):
                t.join(timeout=5)
        assert calls == [{"resource_id": "r2"}]
