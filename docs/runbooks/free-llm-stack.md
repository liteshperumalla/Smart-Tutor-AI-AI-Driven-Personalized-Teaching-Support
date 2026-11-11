# Free LLM stack on staging (Phase 2 of the AWS exit)

This runbook moves **staging** from Bedrock + Titan to OpenRouter (answers),
Gemini (fallback) and a local embedding model (`BAAI/bge-small-en-v1.5`), then
checks answer quality against the Bedrock baseline. Production is untouched:
it keeps `LLM_PROVIDER=bedrock` until the quality gate passes.

Plan: [`docs/plans/2026-11-08-aws-to-free-services-migration.md`](../plans/2026-11-08-aws-to-free-services-migration.md).

## 1. Get the keys

| Key | Where | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | https://openrouter.ai/settings/keys | Free models (`:free`) allow 20 requests/min and 50/day. Buying $10 of credits once raises that to 1,000/day. Failed calls count. |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey | Free tier, used as the fallback provider and as the evaluation judge. |

Never paste keys into the repo, an issue, a PR or a chat.

## 2. Where to set them

### Staging (do this now)

GitHub → repository **Settings → Environments → `staging`**. The staging
deploy job runs in that environment, so values set here reach staging only.

**Environment secrets**

| Name | Value |
|---|---|
| `OPENROUTER_API_KEY` | your OpenRouter key |
| `GEMINI_API_KEY` | your Gemini key |

**Environment variables**

| Name | Value |
|---|---|
| `LLM_PROVIDER` | `openrouter` |
| `LLM_FALLBACK_PROVIDERS` | `gemini` |
| `EMBEDDING_PROVIDER` | `huggingface` |
| `EVAL_JUDGE_PROVIDER` | `gemini` |
| `LLM_CHAT_MODELS` *(optional)* | e.g. `nvidia/nemotron-3-ultra-550b-a55b:free=Nemotron 3 Ultra,nvidia/nemotron-3.5-super-vl:free=Nemotron 3.5 Super` (check https://openrouter.ai/models?q=free first; the list changes) |
| `LLM_FALLBACK_MODELS` *(optional)* | other `:free` model IDs to try before Gemini |
| `STAGING_MEMORY_LIMIT` | `2g`. The local embedding model needs a few hundred MB more than the 1 GB default. |

On the next staging deploy, `deploy-staging.yml` writes each value that is set
into `~/smart-tutor-staging.env` on the server (mode 600). Values you leave
unset keep whatever the file already has.

If that file doesn't exist yet (the first staging deploy), the workflow
creates it with isolated settings:
- `ENVIRONMENT=staging` and `SECRETS_PROVIDER=env`, so staging never loads
  production's Secrets Manager entry or its database credentials;
- its own generated `SECRET_KEY` and `JWT_SECRET_KEY`;
- `STORAGE_BACKEND=filesystem`, so users are stored in the staging data
  directory rather than a database;
- `USE_REDIS_CACHE=false` and `JOBS_BACKEND=inline`;
- the `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` and
  `S3_DOCUMENTS_BUCKET` lines only, copied from `~/smart-tutor.env`, to read
  the course chunks.

It never edits an existing file beyond the LLM settings above.

> **Don't set `LLM_PROVIDER` or `EMBEDDING_PROVIDER` as repository variables
> yet.** The production deploy reads repository-level variables, so that
> would switch production too. Repository-level *secrets* (the keys) are
> harmless while production's `LLM_PROVIDER` is `bedrock`.

### Production (later, at cutover)

Same names under **Settings → Secrets and variables → Actions** (repository
level). `deploy-production.yml` writes them into `~/smart-tutor.env` the same
way.

### Local development

Put the same names in `.env` at the repository root. It is git-ignored and is
loaded by `backend/config.py` and `docker-compose.yml`; see `.env.example`.

## 3. Deploy staging

Add the `deploy:staging` label to the PR (or run **Staging Deploy** with
`workflow_dispatch`). Check the logs for
`Synced: OPENROUTER_API_KEY GEMINI_API_KEY LLM_PROVIDER ...`, then:

```bash
curl -s http://localhost:8110/health/detailed | jq '.checks.bedrock'
```

You should see `"provider": "openrouter"` and `"status": "healthy"`. The key
is still `bedrock` for compatibility with existing deploy gates.

## 4. Build the free vector index

Each embedding model has its own index file (`vector_index/<model>.idx`), so
building this one leaves the Titan index production uses untouched.

**It is slow.** Re-embedding the ~12.7k course chunks on one CPU runs at about
1.2 chunks/s, so about **3 hours**. The rebuild therefore:

- saves its progress to a checkpoint every two minutes and resumes from it
  when run again, so an interruption costs minutes, not hours;
- runs, when started from the **Staging Evaluation** workflow, in its own
  container (`smart-tutor-staging-reindex`), which keeps going after the
  workflow stops waiting. Re-run the workflow later and it picks up the
  result (or waits for the rebuild still in progress).

Its CPU and memory come from the `staging` environment variables
`STAGING_REINDEX_CPUS` (default `1.0`) and `STAGING_REINDEX_MEMORY` (default
`1500m`). The workflow prints the host's CPU count. Production runs on the
same instance, so raise the CPUs only if the host has cores to spare: `2.0`
roughly halves the time.

By hand on the server:

```bash
docker exec smart-tutor-staging-backend python -m backend.scripts.rebuild_index --check
```

```bash
docker exec smart-tutor-staging-backend python -m backend.scripts.rebuild_index
```

`--check` exits 0 when the index exists and 3 when it doesn't. Don't query the
free stack before the index exists: the first RAG query would start the
multi-hour build inside the staging backend. The evaluation workflow checks
this and stops instead.

If staging ever loads an index made by another model, it refuses with
`IndexModelMismatchError` instead of returning wrong results. Rebuild, or
point `VECTOR_INDEX_KEY` at the right file.

## 5. Quality gate

### From GitHub (no server login)

**Actions → Staging Evaluation → Run workflow.** Tick *Rebuild the free
stack's vector index* on the first run (step 4), keep *limit* at 10 unless
you bought the OpenRouter credit, and leave *Also run the AWS baseline* on.

The first run waits up to *rebuild_wait_minutes* (default 150) for the
index. If the rebuild isn't done by then, the run ends with "still running"
and the rebuild carries on on the server; run the workflow again later. The
box can stay ticked: a finished index is not rebuilt, and a running rebuild
is waited for rather than started twice.

The job summary shows the provider check and the PASS/FAIL table; the raw
JSON is in the run's `staging-evaluation-<n>` artifact. It shares the
staging deploy's concurrency group, so it waits for a running deploy.

### On the server

Run the same evaluation twice in the staging container, scored by the same
judge (Gemini), first on the current AWS stack and then on the free stack:

```bash
docker exec -e LLM_PROVIDER=bedrock -e EMBEDDING_PROVIDER=bedrock smart-tutor-staging-backend \
  python -m backend.scripts.run_scheduled_evaluation --limit 30 --source phase2-baseline > baseline.json
```

```bash
docker exec smart-tutor-staging-backend \
  python -m backend.scripts.run_scheduled_evaluation --limit 30 --source phase2-free > candidate.json
```

```bash
docker run --rm -v "$PWD:/w" --entrypoint python "$(docker inspect -f '{{.Config.Image}}' smart-tutor-staging-backend)" \
  -m backend.scripts.compare_evaluations /w/baseline.json /w/candidate.json --max-drop 0.05
```

The baseline run needs the staging env file's AWS credentials, which it
already has today. Each run costs about four judge calls per question, and the
free run also makes about one OpenRouter call per question. 30 questions fit
in the free daily caps if you bought the $10 of OpenRouter credits. Without
them, use `--limit 10`.

**Pass:** no metric (faithfulness, answer relevance, context recall, context
precision, correctness) drops by more than 0.05. If retrieval metrics drop,
re-tune the retrieval thresholds (`backend/retrieval_tuning.py`; the
abstention scores shift with a new embedding model) and run it again. You can
also try `EMBEDDING_MODEL=BAAI/bge-base-en-v1.5` (768 dims, slower) and
rebuild.

## 6. Rolling back

Set `LLM_PROVIDER=bedrock` and `EMBEDDING_PROVIDER=bedrock` in the `staging`
environment variables and redeploy. Deleting a variable is not enough: the
deploy only writes values that are set, so the old line stays in
`~/smart-tutor-staging.env`. To remove a setting entirely, also delete its
line from that file on the server. The Titan index was never touched.
