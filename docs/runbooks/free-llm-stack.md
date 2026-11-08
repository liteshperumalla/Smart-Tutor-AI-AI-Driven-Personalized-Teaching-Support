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
building this one leaves the Titan index production uses untouched. On the
server:

```bash
docker exec smart-tutor-staging-backend python -m backend.scripts.rebuild_index --dry-run
```

```bash
docker exec smart-tutor-staging-backend python -m backend.scripts.rebuild_index
```

It re-embeds every chunk's text on CPU. Expect minutes for the ~14k course
chunks. Until it finishes, staging's first RAG query would build the index
itself, so run this before testing.

If staging ever loads an index made by another model, it refuses with
`IndexModelMismatchError` instead of returning wrong results. Rebuild, or
point `VECTOR_INDEX_KEY` at the right file.

## 5. Quality gate

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

Delete the staging environment variables, or set `LLM_PROVIDER=bedrock` and
`EMBEDDING_PROVIDER=bedrock`, and redeploy. The Titan index was never
touched.
