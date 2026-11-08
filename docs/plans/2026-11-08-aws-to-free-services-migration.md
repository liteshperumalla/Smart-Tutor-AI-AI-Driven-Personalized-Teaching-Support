# Plan: Move off AWS to free services

**Date:** 2026-11-08 · **Status:** Phase 1 done (switches in place, AWS still the default) · **Scope:** backend runtime, CI/CD, infra code, scripts

## 1. What production uses today

Production is **one EC2 instance** (Elastic IP, Docker containers, reached through a
Cloudflare Tunnel) plus managed AWS services. The frontend is already on **Vercel** and
images are already on **GHCR**, so neither needs to move.

| # | AWS service | Used for | Where in the code |
|---|---|---|---|
| 1 | **EC2** + Elastic IP | Runs backend, worker, Redis, Neo4j, code runner, tunnel | `deploy-production.yml`, `rollback-production.yml`, `scripts/ci/resolve_ec2_target.sh`, `scripts/ci/revoke_ec2_ssh_ingress.sh`, `scripts/ci/deploy_code_runner.sh`, `monitoring/prometheus/prometheus-ec2.yml` |
| 2 | **EventBridge Scheduler** + GH cron | Start/stop EC2 on weekdays to save money | `ec2-schedule.yml`, `ec2-eventbridge-scheduler.yml`, `scripts/ci/setup_ec2_eventbridge_schedules.sh`, `terraform/modules/eventbridge` |
| 3 | **Bedrock (LLM)** | All chat, quiz, research, evaluation, HyDE, routing; Llama 3.x 70B + Claude models | `backend/bedrock_llm.py`, `bedrock_llamaindex.py`, `llm_provider.py`, `llm_router.py`, `chat_models.py`, `agents/llm_utils.py`, `services/{quiz,research,evaluation,rag_quality_evaluator}_service.py`, `api/routes/code.py` |
| 4 | **Bedrock (Titan embeddings v2, 1024-dim)** | RAG indexing + query embeddings | `backend/bedrock_embeddings.py`, `services/indexing_service.py`, `s3_retriever.py` |
| 5 | **Bedrock Guardrails** | Prompt-attack / content / PII filter (optional, `BEDROCK_GUARDRAIL_ID`) | `bedrock_llm.py:132`, deploy workflow |
| 6 | **Bedrock Knowledge Base** | Disabled by default (`BEDROCK_KB_ENABLED=false`) | `config.py:307` |
| 7 | **S3** | Course documents, uploads, pickled vector index, backups, research files | `cloud/object_storage.py`, `s3_vector_store.py`, `s3_retriever.py`, `services/{research,quiz,indexing,status}_service.py`, `api/routes/files.py`, `health.py`, `process_modules_to_s3.py`, `scripts/s3-vectors/*`, `scripts/migration/*s3*` |
| 8 | **RDS PostgreSQL** | Users, quiz results, workspaces, outbox | `services/storage/postgres.py`, `database.py`, `scripts/aws/setup_rds_postgres.sh`, `scripts/dr/restore/restore-rds.sh` |
| 9 | **DynamoDB** | Chat sessions (`STORAGE_BACKEND=hybrid`), prompt registry, Terraform locks | `services/storage/{dynamodb,hybrid}.py`, `prompt_registry.py`, `api/routes/evaluation.py`, `terraform/backend.tf` |
| 10 | **SQS** | Background job queue + DLQ (`JOBS_QUEUE_URL`) | `backend/jobs/{queue,worker}.py`, `scripts/replay_dlq.py`, `sqs-jobs-queue.yml`, `scripts/ci/setup_sqs_jobs_queue.sh` |
| 11 | **EventBridge / SNS / SQS** (event bus) | Optional backends; default is `inmemory` | `backend/events/event_bus.py` |
| 12 | **Secrets Manager** | Optional (`SECRETS_PROVIDER=aws`) secret loading + rotation | `cloud/secrets.py`, `config.py:33-52`, `health.py:198`, `scripts/aws/*secret*`, `scripts/auth/*` |
| 13 | **CloudWatch Logs + Alarms** | `awslogs` Docker log driver; error/latency alarms | deploy workflow (23 `awslogs` refs), `config.py:647`, `scripts/aws/setup_cloudwatch_*.sh`, `setup_error_alarms.sh` |
| 14 | **STS / Pricing / CloudWatch metrics API** | Health check identity, live Bedrock prices and usage in the eval dashboard | `health.py:102`, `api/routes/evaluation.py` |
| 15 | **IAM** | Access keys used by CI and the instance | repo secrets `AWS_ACCESS_KEY_ID/SECRET` |
| 16 | **Terraform-only** (probably never applied): ECS, ECR, ALB, CloudFront, Route53, Aurora Serverless, ElastiCache, API Gateway, App Mesh, VPC, VPC endpoints, S3 state bucket | `terraform/**`, `scripts/deploy-infrastructure.sh`, `scripts/deploy-frontend-s3.sh`, `scripts/cost-optimization/analyze-costs.py` |

Services that are **not AWS** and stay: Vercel, GHCR, Cloudflare Tunnel, Neo4j (container or Aura Free), Redis
(container), Langfuse, PostHog, Grafana Cloud, Google OAuth.

## 2. Free replacements

| AWS service | Replace with | Free tier (check current limits before cutover) | Why this one |
|---|---|---|---|
| EC2 | **Oracle Cloud Always Free Ampere A1** (up to 4 OCPU / 24 GB RAM ARM, 200 GB block storage) | Always free | `scripts/setup-oracle-vm.sh` already exists; enough RAM for backend + Postgres + Redis + Neo4j + local embeddings. |
| Elastic IP | **Cloudflare Tunnel** (already used) + Cloudflare DNS | Free | No inbound ports or static IP needed. |
| EventBridge Scheduler / EC2 start-stop | **Delete** | — | An always-free VM doesn't need to be stopped to save money. |
| Bedrock LLM | **OpenRouter** (one key, many models; `LLM_PROVIDER=openrouter`) as primary; **Google Gemini API** free tier as fallback provider; **Ollama** on the VM as last-resort offline fallback. Groq also supported. | Free models (`:free`): 20 req/min and **50 req/day**, or **1,000 req/day after a one-time $10 credit purchase**; failed calls count. Gemini/Groq free tiers have their own limits. | OpenRouter gives students a choice of models (`LLM_CHAT_MODELS`) and same-provider fallback across free models (`LLM_FALLBACK_MODELS`). 50/day is too low for real use, so buy the $10 once or lean on the Gemini fallback. One OpenAI-compatible adapter covers all of these. |
| Claude models via Bedrock | **Remove from `chat_models.py`** (or keep behind a paid `ANTHROPIC_API_KEY` flag) | No free option | No free hosted Claude access exists. |
| Titan embeddings | **Local `sentence-transformers`** — `BAAI/bge-base-en-v1.5` (768-dim) or `bge-small-en-v1.5` (384-dim) on CPU | Free (runs on the VM) | `LLMFactory._create_huggingface_embeddings` already exists. No rate limits and no network calls per query. |
| Bedrock Guardrails | **Llama Guard** (via OpenRouter/Groq, or local) + the existing regex/PII redaction in `log_redaction.py` | Free | Same job: prompt-attack and unsafe-content checks. |
| Bedrock KB | **Drop** | — | Already disabled. |
| S3 | **Cloudflare R2** (S3-compatible API, 10 GB storage, no egress fees) — or the VM's disk via the existing `LocalFileStorage` | Free up to 10 GB | Works with boto3 by adding `endpoint_url`, so almost no code changes. Presigned URLs still work. |
| Vector index (pickle in S3) | Keep the same pickled index, stored in R2 or on local disk. **Later option:** `pgvector` in Postgres | Free | Smallest change. pgvector would remove a moving part, but it's a separate project. |
| RDS PostgreSQL | **Postgres 15 container on the Oracle VM** (already in `docker-compose.yml`), nightly `pg_dump` to R2. Alternatives: Neon free (0.5 GB) or Supabase free (500 MB, pauses when idle) | Free | No size cap or auto-pause. You manage backups yourself, and the existing DR scripts can be adapted. |
| DynamoDB (chat sessions) | **Postgres** — set `STORAGE_BACKEND=postgres` (backend already implements chat sessions, `postgres.py:620-632`) | Free | One fewer database. |
| DynamoDB (prompt registry) | A Postgres table (new Alembic migration) or versioned YAML in the repo | Free | Small, rarely written data. |
| DynamoDB (Terraform locks) | Goes away along with Terraform state in S3 | — | — |
| SQS jobs queue + DLQ | **Redis** (already running): a reliable list queue (`LMOVE` to a processing list, a separate DLQ list), or a library such as **arq**/**RQ** | Free | Redis is already deployed and `USE_REDIS_CACHE` is wired up. |
| EventBridge/SNS event bus | Keep `inmemory` (current default); add a **Redis Streams** backend only if you need it across processes | Free | Production doesn't use the AWS backends today. |
| Secrets Manager | **`SECRETS_PROVIDER=env`** (already the default): GitHub Actions secrets written to `~/smart-tutor.env` (mode 600) on deploy. Optional: Infisical or Doppler free tier | Free | Already supported. Secret rotation becomes a manual script. |
| CloudWatch Logs | **Grafana Cloud Free** (Loki logs, Prometheus metrics, alerting), shipped by Promtail or Grafana Alloy; Docker `json-file` driver with rotation locally | Free (50 GB logs/month on the free tier) | Grafana Cloud is already partly set up (`grafana-cloud-token.example`, `sync_grafana_cloud_dashboards.py`, promtail configs). |
| CloudWatch Alarms | **Grafana Cloud alerting** + existing `synthetic-monitor.yml` / UptimeRobot (free) | Free | — |
| STS / Pricing / CloudWatch metrics API | **Remove**; use a static price table in `cost_tracking.py` (free models = $0) and token counts from Langfuse/Prometheus | — | These calls only exist because of AWS. |
| IAM keys | **Delete** after cutover | — | — |
| Terraform AWS modules | **Archive or delete** after confirming nothing is deployed from them | — | — |

## 3. Code changes

### 3.1 LLM provider (largest change)
1. Add `backend/openai_compatible_llm.py` that implements the same interface as `BedrockLLM`
   (`generate`, streaming, token-usage reporting for `model_usage.py` / Langfuse / Prometheus)
   using the `openai` SDK with a configurable `base_url`.
2. Extend `LLMProvider` in `llm_provider.py` with `GROQ`, `GEMINI`, `OPENAI_COMPAT`, and route
   `LLM_PROVIDER` to it. New config: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_ID`,
   `LLM_FALLBACK_PROVIDERS` (e.g. `groq,gemini,ollama`).
3. Replace the direct Bedrock imports in `bedrock_llamaindex.py`, `agents/llm_utils.py`,
   `agents/streaming.py`, `quiz_service.py`, `research_service.py`, `evaluation_service.py`,
   `rag_quality_evaluator.py`, `rag/hyde.py`, `api/routes/code.py`, and `circuit_breaker.py`/`metrics.py`
   labels so they call the provider factory.
4. Update `chat_models.py` and `llm_router.py` with the new model IDs (for example
   a larger free model for complex queries and a small fast one for simple queries; on OpenRouter pick them from the current `:free` list).
   Remove the Claude entries or gate them behind a flag.
5. Rate limits: use the existing `circuit_breaker.py` and `retry_policy.py` so that on HTTP 429 the
   app falls back to the next provider. Lower `LLM_MAX_CONCURRENT`. Cache answers in Redis
   (`rag/caching_layer.py`) to save quota.
6. Guardrails: replace `_guardrail_kwargs` / `_check_guardrail_intervention` with a pre/post
   moderation hook (Llama Guard) controlled by a flag.

### 3.2 Embeddings + re-index
1. Set `EMBEDDING_PROVIDER=huggingface` and `EMBEDDING_MODEL=BAAI/bge-base-en-v1.5`. Remove the hard-coded
   `1024` dimension (`bedrock_embeddings.py:53`) and read the dimension from the model.
2. **Rebuild the whole vector index.** Titan vectors can't be mixed with the new ones. Merge the ~17
   scripts in `scripts/s3-vectors/` into one `scripts/rag/rebuild_index.py`.
3. Run the RAG evaluation suite (`rag-evaluation-scheduled.yml`, `backend/rag/tests/run_evaluation.py`)
   before and after, and re-tune `retrieval_tuning.py` thresholds and the abstention scores. These
   change with the embedding model.
4. Pre-download the model in `backend/Dockerfile.prod` so cold starts don't fetch it.

### 3.3 Object storage → R2 / local
1. Add `S3_ENDPOINT_URL` (and `S3_REGION=auto`) to `config.py` and pass it as `endpoint_url` in
   `cloud/aws_helpers.get_boto3_client("s3")`. R2 then works with no other changes.
2. Move the **direct** `boto3.client("s3")` calls onto `get_object_storage()` or the helper:
   `s3_vector_store.py`, `services/indexing_service.py`, `services/status_service.py`,
   `services/research_service.py` (`boto3.resource`), `process_modules_to_s3.py`,
   `api/routes/evaluation.py`.
3. Rename `cloud/aws_helpers.py` → `cloud/s3_compat.py` and drop the AWS-specific naming.
4. Copy the data: `rclone sync s3:<bucket> r2:<bucket>` for the documents, uploads and backups buckets.

### 3.4 Databases
1. Switch to `STORAGE_BACKEND=postgres`. Write `scripts/migration/dynamodb_to_postgres.py`
   (scan the chat-sessions table, then call `save_chat_session`). The existing `migrate_chat_sessions.py`
   goes the other way (filesystem → DynamoDB).
2. Move `prompt_registry.py` from DynamoDB to Postgres (new Alembic migration).
3. Delete `services/storage/{dynamodb,hybrid}.py`, `tests/test_dynamodb_consistent_reads.py`, the
   `dynamodb-local` service in `docker-compose.yml`, and the DynamoDB variables.
4. Move RDS: `pg_dump` from RDS, then `pg_restore` into the VM's Postgres, then `alembic upgrade head` and a row-count check.
   Change `scripts/dr/*` to run `pg_dump` to R2 on a cron (keep 7 daily and 4 weekly backups) and practise a
   restore once (`docs/runbooks/backup-restore-drill.md`).

### 3.5 Jobs queue → Redis
1. Add a `RedisQueue` to `backend/jobs/queue.py` with the same `enqueue` / `receive` / `ack` / DLQ methods,
   chosen with `JOBS_BACKEND=redis|sqs|inline`.
2. Change `worker.py` (blocking `BLMOVE` plus visibility-timeout recovery) and `scripts/replay_dlq.py`.
3. Rewrite `tests/test_jobs.py` and `tests/test_dlq.py` to use `fakeredis`.
4. Delete `sqs-jobs-queue.yml` and `scripts/ci/setup_sqs_jobs_queue.sh`.

### 3.6 Secrets, logging, health, cost
1. Fix `SECRETS_PROVIDER=env`. Remove `AWSSecretsBackend` and the Secrets Manager branch in `config.py`.
   Change `scripts/auth/*` to update GitHub secrets (`gh secret set`) instead of Secrets Manager.
2. Change the `awslogs` driver lines in the deploy workflow to `json-file` with `max-size`/`max-file`,
   and add a Grafana Alloy (or Promtail) container that ships logs to Grafana Cloud Loki. Remove
   `CLOUDWATCH_*` config.
3. `health.py`: drop the STS and Secrets Manager checks. Make the S3 check work against R2/local. Add a
   check that the LLM provider is reachable.
4. `api/routes/evaluation.py` and `cost_tracking.py`: remove the Pricing, CloudWatch and STS calls and
   use a static per-model price table.

### 3.7 CI/CD and infra
1. `deploy-production.yml` / `rollback-production.yml`: remove the AWS key and EC2 resolution steps.
   Deploy over SSH to the Oracle VM (`ORACLE_HOST`, `ORACLE_USER`, `ORACLE_SSH_KEY`), or skip SSH
   entirely by having the tunnel and a pull-based updater (e.g. Watchtower watching GHCR) do it.
2. **Build images for ARM64:** `docker/build-push-action` with `platforms: linux/amd64,linux/arm64`
   (backend, code runner). Check that every Python wheel in `requirements.txt` exists for aarch64
   (torch, faiss, etc.).
3. Delete `ec2-schedule.yml`, `ec2-eventbridge-scheduler.yml`, `scripts/ci/*ec2*`, `scripts/aws/`,
   `scripts/deploy-frontend-s3.sh`, `scripts/cost-optimization/analyze-costs.py`, `scripts/testing/list_bedrock_models.py`,
   `scripts/testing/test_llama_direct.py`, `monitoring/prometheus/prometheus-ec2.yml`.
4. Terraform: run `terraform state list` against the S3 backend. If it's empty or the resources are already
   gone, move `terraform/` to `docs/archive/` or delete it. If anything is deployed, `terraform destroy` it
   in Phase 5 first.
5. Update `.env.example`, `helm/`, `k8s/` configmaps, `README.md`, `docs/guides/ENV_SETUP.md`,
   and archive `docs/aws/`. Add an ADR (`docs/adr/0002-move-off-aws.md`).
6. Remove `boto3`/`botocore` from `requirements.in` once nothing imports them, except the S3 client
   for R2. That one still uses boto3, which is fine.

## 4. Phased rollout

Every phase uses env flags, so each step can be undone by changing an env value until Phase 5.

| Phase | Work | Exit criteria |
|---|---|---|
| **0. Prep** (½ day) | Create Oracle, Cloudflare R2, OpenRouter (buy the one-time $10 for 1,000 free requests/day), Gemini and Grafana Cloud accounts. Back up everything: `pg_dump` RDS, export DynamoDB to JSON, `aws s3 sync` all buckets to local disk. | Backups restore locally. |
| **1. Abstractions** (2–3 days) | §3.1 provider adapter, §3.3 endpoint override, §3.5 Redis queue, §3.6 health/cost cleanup. AWS stays the default. | CI green; tests cover both paths. |
| **2. LLM + embeddings** (2–3 days) | Switch dev/staging to OpenRouter and bge. Re-index. Run the RAG eval before/after and re-tune thresholds. | Faithfulness, answer relevance and recall within an agreed margin of the Bedrock baseline. |
| **3. Oracle VM** (1–2 days) | Run `setup-oracle-vm.sh`, build multi-arch images, start Postgres, Redis, Neo4j, backend, worker and tunnel. Restore the Postgres dump, migrate DynamoDB sessions, rclone S3 to R2. Point a **staging** tunnel hostname at it. | Smoke tests (`post-deploy-smoke.yml`, e2e) pass against staging. |
| **4. Cutover** (½ day, low-traffic window) | Final DB delta sync, point the production tunnel/`BACKEND_API_BASE_URL` at the VM, and keep EC2 stopped (not terminated) for 1–2 weeks. | Synthetic monitor green for 7 days; error rate and latency SLOs met. |
| **5. Decommission** (1 day) | Terminate EC2, release the Elastic IP, delete RDS (keep a final snapshot exported to R2), DynamoDB, SQS, buckets, schedules, guardrail, IAM keys. Delete the AWS code, workflows and Terraform (§3.7). | AWS bill $0; `grep -ri boto3` only matches the R2 client. |

### Phase 1 status (done)

All new behaviour is opt-in through env vars; with none set the app runs on AWS exactly as before.

| Switch | Values | What it does |
|---|---|---|
| `LLM_PROVIDER` | `bedrock` (default), `openrouter`, `groq`, `gemini`, `ollama`, `openai_compat` | `backend/openai_compat_llm.py` — one client for every OpenAI-compatible API, with the same tracing/metrics/cost as Bedrock (shared code moved to `backend/llm_core.py`). All direct `BedrockLLM()` call sites now use `llm_provider.create_llm_client()`. |
| `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_ID` | — | Provider keys/endpoints. `config.LLM_MODEL_ID` is now the app-wide default model (equals `BEDROCK_MODEL_ID` on Bedrock). |
| `LLM_FALLBACK_MODELS` | e.g. two other `:free` model IDs | Other models on the primary provider, tried before the fallback providers. |
| `LLM_FALLBACK_PROVIDERS` | e.g. `gemini,ollama` | Tried in order when the primary fails before answering (rate limits). |
| `LLM_CHAT_MODELS` | `id=Label,...` (`!admin` suffix = admin-only) | The chat model picker off Bedrock. |
| `LLM_MODERATION_MODEL` | e.g. a Llama Guard model | Optional pre-check that replaces Bedrock Guardrails; fails open. |
| `S3_ENDPOINT_URL`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | R2 / MinIO | Every S3 client now goes through `cloud/aws_helpers.get_s3_client()`. |
| `JOBS_BACKEND` | `sqs`, `redis`, `inline` | `backend/jobs/redis_queue.py` gives Redis the SQS calls the worker uses (visibility timeout, retries, DLQ at `JOBS_MAX_RECEIVES`). Deploy/rollback workflows start the worker for `redis` (repo variable `JOBS_BACKEND`). |
| `CLOUD_PROVIDER` | `aws` (default), anything else | Off AWS, `/evaluation/aws-metrics` skips the Pricing, CloudWatch and STS calls. |
| `SECRETS_PROVIDER`, `OBJECT_STORAGE_PROVIDER` | existing | Health checks now skip Secrets Manager unless `aws`, and check the local disk for `local`. |

Also: health reports an OpenAI-compatible provider under the existing `bedrock` key (so deploy gates don't change), and the chat model picker lists the provider's own models off Bedrock.

Not done in Phase 1, carried forward: verifying the ARM64 image build (needs Docker/buildx in CI, do it at the start of Phase 3), renaming `cloud/aws_helpers.py` (Phase 5), and Langfuse dashboards still filter on the `bedrock-generation` trace name, which every provider keeps using.

## 5. Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Oracle A1 capacity**: "Out of host capacity" errors when creating the instance in popular regions | Retry, pick a less busy home region, or start with a smaller shape (e.g. 2 OCPU / 12 GB). Upgrading the account to Pay-As-You-Go usually gets capacity and you still pay nothing if you stay inside the Always Free limits. |
| **Oracle reclaims idle Always Free instances** (low CPU/network/memory over 7 days) | Pay-As-You-Go accounts are exempt; the background worker and health checks also keep it from looking idle. |
| **Free LLM rate limits / quota** (requests per minute, tokens per day) | Fall back to other free models, then another provider (OpenRouter → Gemini → Ollama), cache answers in Redis, lower concurrency, and use the small model for simple queries (`llm_router.py`). |
| **Answer quality changes** (no Claude; different embeddings) | Run the RAG eval before/after (Phase 2), re-tune thresholds, and keep the old Bedrock path behind a flag until Phase 5. |
| **Free-tier terms change** | Everything is behind OpenAI-compatible / S3-compatible interfaces, so switching provider is a config change. |
| **Self-managed Postgres** (backups and upgrades are now on you) | Nightly `pg_dump` to R2, a monthly restore drill, pinned image tags with Dependabot, or move to Neon if you'd rather it be managed. |
| **ARM64 builds**: some wheels (torch, faiss) may be missing or slow to build | Test the multi-arch build in Phase 1, use the CPU-only torch index, and check `faiss-cpu` aarch64 wheels. |
| **Privacy**: free LLM tiers may log prompts | Check each provider's data-use policy and keep `log_redaction.py` on. Ollama is fully local if needed. |

## 6. Summary

- **Already free, or ready to switch with no code:** frontend (Vercel), images (GHCR), tunnel and DNS (Cloudflare),
  secrets (`SECRETS_PROVIDER=env`), event bus (`inmemory`), chat sessions in Postgres
  (`STORAGE_BACKEND=postgres`), local embeddings (`EMBEDDING_PROVIDER=huggingface`).
- **Small code changes:** S3 → R2 (`endpoint_url`), SQS → Redis, CloudWatch → Grafana Cloud, remove STS/Pricing.
- **Real work:** Bedrock LLM → OpenRouter/Gemini adapter, re-indexing with new embeddings plus a quality check, and the
  EC2/RDS → Oracle VM move with ARM64 images.
- **Estimated effort:** about 8–12 working days for one developer, then 1–2 weeks with AWS kept as a fallback.
