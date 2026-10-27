"""Background jobs: ``enqueue`` work here, run it in the SQS worker container.

See backend/jobs/queue.py and docs/aws/SQS_JOBS_SETUP.md.
"""
__all__ = ["UnknownJobError", "enqueue", "job"]


def __getattr__(name):
    # Lazy, so ``python -m backend.jobs healthcheck`` doesn't load the config.
    if name in __all__:
        from backend.jobs import queue

        return getattr(queue, name)
    raise AttributeError(f"module 'backend.jobs' has no attribute {name!r}")
