# 📊 Langfuse v4 Dashboards & Analytics Specification

This document details the configuration, underlying metrics, aggregation rules, and operational visualization for the five primary Langfuse dashboards deployed in Smart AI Tutor.

> **Live dashboard.** The JSON files below are design specs; Langfuse cannot import them. The dashboard that exists in Langfuse is **Smart AI Tutor - Production LLM**, built through the Langfuse dashboards API by `scripts/ci/sync_langfuse_dashboards.py` (re-run it after changing its widget list). Its cost, token and model charts read the `bedrock-generation` observations that `backend/bedrock_llm.py` emits for every Bedrock call.

---

## 🧭 Dashboard Architecture & Index

| # | Dashboard | JSON Definition | Key Primary Metrics | Target Audience |
|---|---|---|---|---|
| 1 | **Langfuse Agent Dashboard** | [`1-agent-dashboard.json`](file:///Users/liteshperumalla/Projects/Smart%20AI%20Tutor/monitoring/langfuse/dashboards/1-agent-dashboard.json) | Multi-step sessions, tool execution distribution, turn depth, agent error & fallback rates | AI Engineers, Core Agent Devs |
| 2 | **Langfuse Home** | [`2-home-dashboard.json`](file:///Users/liteshperumalla/Projects/Smart%20AI%20Tutor/monitoring/langfuse/dashboards/2-home-dashboard.json) | Gross trace volume, request QPS, DAU/MAU, global success rate, model traffic share | Engineering Leads, Executives |
| 3 | **Langfuse Cost Dashboard** | [`3-cost-dashboard.json`](file:///Users/liteshperumalla/Projects/Smart%20AI%20Tutor/monitoring/langfuse/dashboards/3-cost-dashboard.json) | Cumulative spend ($ USD), burn rate, prompt vs completion spend, cost by model & feature | FinOps, Product Owners |
| 4 | **Langfuse Latency Dashboard** | [`4-latency-dashboard.json`](file:///Users/liteshperumalla/Projects/Smart%20AI%20Tutor/monitoring/langfuse/dashboards/4-latency-dashboard.json) | P50, P90, P95, P99 e2e latency, TTFT per model, vector/graph/web sub-step timings | SREs, Performance Engineers |
| 5 | **Langfuse Usage Management** | [`5-usage-management.json`](file:///Users/liteshperumalla/Projects/Smart%20AI%20Tutor/monitoring/langfuse/dashboards/5-usage-management.json) | Gross token volume, tier quotas, 429 throttling events, top consuming users, cache hit ratio | Platform Ops, Security & Billing |

---

## 1. 🤖 Langfuse Agent Dashboard
Tracks complex multi-step reasoning, tool invocations, and autonomous agent behavior.

### Tracked Metrics
* **Total Agent Sessions**: Unique interactive sessions executing multi-step agent graphs.
* **Agent Success Rate**: Percentage of agent executions that complete successfully without unhandled tool errors or aborted synthesis (`target >= 99.0%`).
* **Tool Call Breakdown**: Distribution of tool executions across:
  * `rag-retrieval` (Dense vector retrieval in ChromaDB)
  * `graph-retrieval` (Knowledge graph traversal in Neo4j)
  * `web-search-decision` (Evaluating whether live internet grounding is required)
  * `web-search-execution` (SerpAPI external live web queries)
  * `llm-synthesis` (Final streaming response generation)
  * `code-sandbox-eval` (Python execution in container sandbox)
  * `quiz-generation-pipeline` (Bloom's taxonomy adaptive quiz generation)
* **Reasoning Steps per Session**: Turn count and re-planning iterations per session.
* **Tool Latency (P50, P90, P95, P99)**: Latency distribution per tool invocation.
* **Agent Fallback Rate**: Percentage of queries triggering re-planning or recovery fallbacks.

---

## 2. 🏠 Langfuse Home
The mission control overview for executive health, throughput, and active user adoption.

### Tracked Metrics
* **Total Ingested Traces**: 24-hour and hourly throughput of full request lifecycles.
* **Request Throughput (QPS / RPM)**: Ingestion speed of queries processed per minute.
* **Daily Active Users (DAU)**: Unique `user_id` count generating telemetry.
* **System Error Rate**: Percentage of traces with `level = 'ERROR'` (`target < 1.0%`).
* **Model Traffic Share**: Volume split between:
  * **Claude 5.5 Sonnet** (`anthropic.claude-v5-5-sonnet`)
  * **Claude 5.5 Haiku** (`anthropic.claude-v5-5-haiku`)
  * **GPT-6 Luna** (`us.openai.gpt-6-luna`)
  * **Llama 3.3 70B** (`meta.llama-3-3-70b-instruct`)
* **P95 Global Latency**: High-percentile end-to-end response time.
* **Total Spend ($ USD)**: Real-time spend counter across all LLM inference.

---

## 3. 💰 Langfuse Cost Dashboard
Provides FinOps governance, unit economics, and token expenditure accounting.

### Pricing Model Reference
| Model | Input ($/M tokens) | Output ($/M tokens) | Primary Role |
|---|---|---|---|
| **Claude 5.5 Sonnet** | $3.00 | $15.00 | Complex reasoning & deep coding |
| **Claude 5.5 Haiku** | $0.80 | $4.00 | High-velocity chat & flash QA |
| **GPT-6 Luna** | $2.00 | $8.00 | Creative synthesis & multi-turn dialog |
| **Llama 3.3 70B** | $0.72 | $0.72 | Open-source bedrock reasoning |
| **Titan Embed Text v2** | $0.02 | $0.00 | ChromaDB vector embeddings |

### Tracked Metrics
* **Cumulative Spend**: Total dollar expenditure across selected billing cycles.
* **Daily Burn Rate**: Projected 24-hour cost based on trailing traffic.
* **Cost by Model**: Spend per model architecture.
* **Prompt vs Completion Split**: Ingestion token expense vs generation token expense.
* **Cost by Feature**: Spend tagged by feature (`chat-assistant`, `code-sandbox`, `quiz-generator`, `document-indexing`).
* **Unit Economics**: Average cost per student session ($/session).
* **Top Consuming Users**: Leaderboard of top 10 user accounts by total cost.

---

## 4. ⚡ Langfuse Latency Dashboard
Tracks performance percentiles, token streaming speed, and sub-component bottlenecks.

### Tracked Metrics
* **E2E Latency Percentiles**: P50 (median), P75, P90, P95, and P99 tail latency.
* **Time to First Token (TTFT)**: 90th percentile streaming TTFT by model (`target < 600ms`).
* **Tokens Generated per Second (TPS)**: Synthesis streaming throughput.
* **Vector Retrieval Latency**: ChromaDB similarity search duration (`target < 250ms`).
* **Graph Retrieval Latency**: Neo4j multi-hop query execution (`target < 150ms`).
* **External Web Search Latency**: SerpAPI network call duration (`target < 1200ms`).
* **SLA Breaches**: Feed of traces exceeding the 3000ms response threshold.

---

## 5. 🛡️ Langfuse Usage Management
Manages multi-tenant quotas, context saturation, rate limits, and caching efficiency.

### User Tier Quotas
* **Free Tier**: 50,000 tokens/day, 10 requests/min
* **Student Tier**: 250,000 tokens/day, 30 requests/min
* **Pro Tier**: 1,000,000 tokens/day, 60 requests/min

### Tracked Metrics
* **Gross Token Volume**: Hourly prompt, completion, and total token counters.
* **Tier Quota Utilization**: Percentage of allocated quota consumed across tiers.
* **Rate Limit Breaches (HTTP 429)**: Frequency of throttled or rejected requests.
* **Top 10 Active Users**: Heaviest accounts ranked by token consumption.
* **Context Window Saturation**: Percentage of model context window used per prompt.
* **Semantic Cache Hit Ratio**: Percentage of queries served via Redis cache, saving LLM tokens.

---

## 🔗 Viewing Dashboards

1. **In Langfuse Cloud**:
   - Access: [https://us.cloud.langfuse.com](https://us.cloud.langfuse.com) (or self-hosted instance).
   - Navigate to **Dashboards** > **New Dashboard** > **Import Configuration** and upload the corresponding JSON from [`monitoring/langfuse/dashboards/`](file:///Users/liteshperumalla/Projects/Smart%20AI%20Tutor/monitoring/langfuse/dashboards/).

2. **In Grafana / Grafana Cloud**:
   - Provisioned automatically via [`monitoring/grafana/dashboards/langfuse-observability.json`](file:///Users/liteshperumalla/Projects/Smart%20AI%20Tutor/monitoring/grafana/dashboards/langfuse-observability.json).
   - Connected via Prometheus `remote_write` to Grafana Cloud Hosted Metrics.
