# Langfuse Dashboards

Five dashboards in Langfuse, defined in [`monitoring/langfuse/dashboards/`](../../monitoring/langfuse/dashboards/) and built by [`scripts/ci/sync_langfuse_dashboards.py`](../../scripts/ci/sync_langfuse_dashboards.py).

| Dashboard in Langfuse | Definition | Shows |
|---|---|---|
| **Smart AI Tutor - Home** | [`2-home-dashboard.json`](../../monitoring/langfuse/dashboards/2-home-dashboard.json) | Traces, active users, chat sessions, spend, failed generations, traffic by feature, model mix, p95 latency |
| **Smart AI Tutor - Cost** | [`3-cost-dashboard.json`](../../monitoring/langfuse/dashboards/3-cost-dashboard.json) | Spend in total, per day, by model and feature, input vs output, top users and chat sessions |
| **Smart AI Tutor - Latency** | [`4-latency-dashboard.json`](../../monitoring/langfuse/dashboards/4-latency-dashboard.json) | Response latency percentiles, time to first token, tokens per second, latency distribution, retrieval and pipeline steps |
| **Smart AI Tutor - Usage** | [`5-usage-management.json`](../../monitoring/langfuse/dashboards/5-usage-management.json) | Tokens per day, by feature and by user; user satisfaction from chat thumbs up/down |
| **Smart AI Tutor - Agents** | [`1-agent-dashboard.json`](../../monitoring/langfuse/dashboards/1-agent-dashboard.json) | Agent pipeline runs and users, run latency, latency per pipeline step, failed runs |

These replace the earlier single dashboard **Smart AI Tutor - Production LLM**, which the next sync deletes.

## How they are built

- Each widget's `query` in the JSON files is the exact `GET /api/public/v2/metrics` query it charts: view, metrics (measure and aggregation), breakdown dimensions, filters and time granularity.
- The sync runs in **Sync Dashboards To Langfuse** in `.github/workflows/observability-production.yml` when the definitions change on `main`, or manually with `python scripts/ci/sync_langfuse_dashboards.py` (`--dry-run` prints the widgets without calling Langfuse).
- It deletes and recreates the dashboards it manages, so change the JSON files, not the Langfuse UI.
- Every widget is limited to `environment = production`.
- `python scripts/langfuse/check_dashboards.py` runs every widget query against live data and fails on a query Langfuse rejects. `--environment development` points it at another environment.

## Where the data comes from

| Data | Source |
|---|---|
| Environment | `ENVIRONMENT`, set on the Langfuse client in `backend/langfuse_setup.py` |
| LLM generations (`bedrock-generation`) | `backend/bedrock_llm.py`: model, input/output tokens, input/output/total cost, latency, time to first token, `ERROR` level on failure |
| User, chat session, feature | Set per request in `backend/api/dependencies.py` and applied with `langfuse.propagate_attributes`. The user is a pseudonym (`u_` plus 12 hex characters, from `backend/log_redaction.user_ref`), the session is the chat session ID, and the feature (`chat`, `quiz`, `code`, `research`, `rag`) is the trace name and tag. |
| Agent runs (`agent-pipeline`) | `backend/agents/__init__.py`: root observation plus `load-student-profile`, `agent-rag-retrieval` and `log-interaction` steps; flagged `ERROR` when the LLM stream fails |
| Retrieval steps | LlamaIndex callback spans (`retrieve`, `LlamaIndex_query`, ...) |
| User satisfaction | Score `user_feedback` (1 = thumbs up, 0 = thumbs down) on the chat session, from `backend/api/routes/chat.py` |

To find one user in these dashboards, compute their reference with `backend.log_redaction.user_ref("<username>")`.

Rate limiting (HTTP 429), cache hit rate and infrastructure metrics live in Grafana, not Langfuse.
