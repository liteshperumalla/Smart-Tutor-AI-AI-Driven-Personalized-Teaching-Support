"""Command line for the jobs queue.

    python -m backend.jobs worker           run the jobs worker (the worker container's command)
    python -m backend.jobs ping [note]      queue a ping job to check the queue and worker end to end
    python -m backend.jobs healthcheck      exit 0 if the worker polled recently (container health check)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# Must match backend.jobs.worker.DEFAULT_ALIVE_FILE. Kept here so the health
# check, which Docker runs every 30 s, doesn't import the backend config.
ALIVE_FILE = "/tmp/jobs-worker-alive"  # noqa: S108  # nosec B108 - mtime-only liveness marker, never read
# A poll waits at most 20 s, and a running job touches the file every 30 s.
HEALTHY_WITHIN_SECONDS = 120


def main(argv: list[str]) -> int:
    command = argv[0] if argv else ""

    if command == "healthcheck":
        try:
            age = time.time() - Path(ALIVE_FILE).stat().st_mtime
        except OSError:
            return 1
        return 0 if age < HEALTHY_WITHIN_SECONDS else 1

    from backend.config import config

    from backend.jobs.queue import jobs_backend

    if command == "worker":
        from backend.jobs.queue import jobs_client, queue_address
        from backend.jobs.worker import Worker

        if jobs_backend() == "inline":
            print("No jobs queue configured (JOBS_QUEUE_URL or JOBS_BACKEND=redis); nothing to consume.", file=sys.stderr)
            return 2
        Worker(queue_address(), config.JOBS_REGION, client=jobs_client()).run_forever()
        return 0

    if command == "ping":
        if jobs_backend() == "inline":
            print("No jobs queue configured; the ping would only run in this process.", file=sys.stderr)
            return 2
        from backend.jobs.queue import send_to_queue

        # No in-process fallback here: the point is to prove the queue works.
        try:
            job_id = send_to_queue("ping", note=" ".join(argv[1:]))
        except Exception as exc:
            print(f"could not queue ping: {exc}", file=sys.stderr)
            return 1
        print(f"queued ping {job_id}")
        return 0

    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
