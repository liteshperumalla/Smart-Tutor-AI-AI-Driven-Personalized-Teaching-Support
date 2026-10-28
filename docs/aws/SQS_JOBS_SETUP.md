# SQS background jobs

Slow or retry-worthy work (document indexing, notification emails) can run
outside the request path through `backend/jobs`. Define the job in
`backend/jobs/tasks.py`:

```python
# backend/jobs/tasks.py
@job("example.send_digest")
def send_digest(user_id: str) -> None:
    ...
```

and queue it from wherever the work starts:

```python
from backend.jobs import enqueue

enqueue("example.send_digest", user_id="u-123")
```

The worker only knows the jobs that `backend/jobs/tasks.py` registers. A job
defined in some other module must be imported from `tasks.py`. Otherwise the
API can queue it, but the worker treats it as unknown, and the message retries
until it lands in the dead-letter queue.

| `JOBS_QUEUE_URL` | Where the job runs |
|---|---|
| unset (default; local dev, CI) | a daemon thread in the API process, as before |
| set | sent to SQS; the `smart-tutor-worker` container runs it |

If SQS can't be reached when a job is queued, `enqueue` logs a warning and
runs the job in a thread in the API process instead. **That fallback is best
effort:** if the API restarts before the thread finishes, the job is lost,
since no SQS message exists to retry it. Watch for `Could not queue job` in
the backend logs.

**Cost.** Within the always-free 1M SQS requests a month. An idle worker
long-polls about three times a minute: roughly 130k requests a month even
running 24/7, fewer while EC2 is stopped.

## Pieces

| Piece | Where |
|---|---|
| Queue `smart-tutor-jobs` + dead-letter queue `smart-tutor-jobs-dlq` | `scripts/ci/setup_sqs_jobs_queue.sh`, run by the **SQS Jobs Queue** workflow |
| IAM inline policy `smart-tutor-jobs-queue` on the EC2 instance role | same script |
| Job registry and `enqueue` | `backend/jobs/queue.py` |
| Worker loop | `backend/jobs/worker.py` (`python -m backend.jobs worker`) |
| Registered jobs | `backend/jobs/tasks.py` |
| Worker container | started by `deploy-production.yml` (and `rollback-production.yml`) after the API is healthy |

Queue settings: 15 min visibility timeout (the worker extends it while a job
runs), 20 s long polling, 14-day retention so jobs queued while the instance
is stopped are still there at start, SQS-managed encryption, and a move to the
DLQ after 5 failed receives.

## Turn it on

1. **Create the queues.** Actions → **SQS Jobs Queue** → *Run workflow*. It
   also runs on any push to `main` that changes the workflow or its script.
   The run summary shows the queue URL.

   The script finds the production instance the way **Production Deploy**
   does: from `EC2_INSTANCE_ID`, then the `EC2_INSTANCE_NAME` tag, then
   `EC2_HOST`. The lookup is read-only, so it never starts the instance. The
   script attaches the SQS policy to that instance's IAM role. If the instance
   has no instance profile, it prints a warning and the policy JSON instead.
   Then attach that JSON to whichever IAM identity the backend uses (the IAM
   user whose keys are in `~/smart-tutor.env`).

   If an AWS call fails, the run summary names the call and AWS's message.
   An `AccessDenied` there means the IAM user behind the repository's
   `AWS_ACCESS_KEY_ID` needs these permissions:
   - `sqs:GetQueueUrl`, `sqs:CreateQueue`, `sqs:SetQueueAttributes` and
     `sqs:GetQueueAttributes` on `smart-tutor-jobs*`.
   - `ec2:DescribeInstances`.
   - `iam:GetInstanceProfile`, plus `iam:PutRolePolicy` on the instance role.

2. **Set the switch.** Settings → Secrets and variables → Actions →
   *Variables* → `JOBS_QUEUE_URL` = the queue URL from step 1.

3. **Deploy.** Run **Production Deploy** (or merge to `main`). The deploy
   writes `JOBS_QUEUE_URL` into `~/smart-tutor.env`, restarts the API with it,
   and starts `smart-tutor-worker`. The step fails if the worker doesn't
   report healthy within a minute.

4. **Check it end to end** on the EC2 host:

   ```bash
   docker exec smart-tutor-backend python -m backend.jobs ping hello
   docker logs smart-tutor-worker --tail 20   # "Jobs ping received: hello" ... "done"
   ```

   `ping` sends straight to SQS with no in-process fallback. If it prints
   `could not queue ping: ...` and exits 1, the API can't reach the queue.
   Check the URL, the region and the role's permissions.

   The worker's logs also go to CloudWatch: log group `/smart-ai-tutor/backend`,
   stream `worker`.

## How a job is handled

- One message at a time. Success deletes it.
- A failure leaves it on the queue with a growing delay (30 s, 60 s, 120 s,
  up to 15 min). After 5 receives SQS moves it to the DLQ. Unknown job names,
  malformed bodies and unsupported message versions take the same path, so
  nothing is dropped silently.
- **Jobs must be safe to run twice.** SQS delivers at least once, and a job
  cut off by a deploy (the worker gets 120 s to finish after SIGTERM) runs
  again once its visibility timeout lapses.
- The container health check (`python -m backend.jobs healthcheck`) passes
  while the worker has polled, or a running job has checked in, within the
  last 2 minutes.

## Operating it

- **Queue depth / stuck work:** SQS console → `smart-tutor-jobs` →
  *Monitoring* (`ApproximateNumberOfMessagesVisible`,
  `ApproximateAgeOfOldestMessage`).
- **Failed jobs:** SQS console → `smart-tutor-jobs-dlq` → *Send and receive
  messages* → *Poll for messages* to read them. After fixing the cause, use
  *Start DLQ redrive* to send them back to `smart-tutor-jobs`.
- **Worker status:** `docker ps --filter name=smart-tutor-worker` shows
  `(healthy)`; `docker logs smart-tutor-worker`.

## Turn it off

Delete the `JOBS_QUEUE_URL` repository variable and deploy. The deploy removes
it from `~/smart-tutor.env` and stops the worker, and jobs go back to running
inside the API. Anything still on the queue stays there (for 14 days) until
the worker is turned back on.

## Not this

`backend/events` (`SQSConsumer`, the outbox, `SQS_QUEUE_URL`) is a separate,
unused domain-events path for SNS-delivered events. It doesn't read this
queue, and `SQS_QUEUE_URL` should stay unset.
