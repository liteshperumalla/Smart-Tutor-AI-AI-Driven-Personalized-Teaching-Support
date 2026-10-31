# Smart Tutor AI

> An AI teaching assistant for **INFO 5731 (Computational Methods for Information Systems)** at the University of North Texas.
> It answers questions from the course's own lectures, notebooks and readings using Retrieval-Augmented Generation (RAG), and cites the source of every answer.

[![Live Demo](https://img.shields.io/badge/Live_Demo-Vercel-black?logo=vercel)](https://smart-ai-tutor.vercel.app)
[![Backend](https://img.shields.io/badge/Backend-AWS_EC2-orange?logo=amazon-aws)](http://52.2.3.101/health)
[![CI](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-blue?logo=github-actions)](https://github.com/liteshperumalla/Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support/actions)
[![RAG eval](https://img.shields.io/badge/RAG_eval-7%2F7_passing-brightgreen)](#results)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## Contents

- [Why](#why) · [Live demo](#live-demo) · [Architecture](#architecture) · [RAG pipeline](#rag-pipeline)
- [Results](#results) · [Features](#features) · [Tech stack](#tech-stack) · [Quick start](#quick-start)
- [Repository layout](#repository-layout) · [API](#api-reference) · [Security](#security) · [Deployment & operations](#deployment--operations)

---

## Why

General-purpose LLMs answer course questions confidently but often get the details wrong. They don't know what *this* course taught, which notebook covered a topic, or how the instructor framed it. Smart Tutor AI limits generation to the indexed INFO 5731 corpus:

- **Grounded:** every answer is built from retrieved course chunks, and each one cites its source file, page or slide.
- **Cheap to keep current:** there is no fine-tuning. When the syllabus changes, you re-index the new material.
- **Honest when unsure:** a self-check flags answers the retrieved context doesn't support, and a web-search fallback only runs when the course material has nothing relevant.

## Live demo

| | URL |
|---|---|
| **App** (Vercel) | https://smart-ai-tutor.vercel.app |
| **API health** | http://52.2.3.101/health |
| **API docs** (Swagger) | http://52.2.3.101/docs |

> To keep costs down, the backend runs **Mon–Fri, 09:00–17:00 US Central**. Outside those hours the app shows a maintenance notice instead of errors. Register an account to try it; the knowledge base covers all 11 INFO 5731 modules.

---

## Architecture

![Smart Tutor AI system architecture](docs/architecture/system-architecture.svg)

- **Frontend:** Next.js 16 on Vercel. Every API call goes through a same-origin proxy (`/api/backend/*`) to the backend.
- **Backend:** FastAPI on a single scheduled AWS EC2 instance (`t3a.medium`, Elastic IP). Postgres, Redis and the Prometheus/Grafana stack run beside it in Docker.
- **AI:** AWS Bedrock for generation (users can choose the model per message) and Titan embeddings. The vector index is stored in S3.
- **Observability:** Langfuse traces every RAG stage, PostHog tracks product and LLM events, Prometheus feeds Grafana Cloud, and alerts go to Slack.
- **Delivery:** GitHub Actions runs CI and security checks on every PR. When CI passes on `main`, a deploy rolls a new backend container onto EC2 by starting a candidate container, health-checking it, then swapping it in.

## RAG pipeline

![Smart Tutor AI RAG pipeline](docs/architecture/rag-pipeline.svg)

| Stage | What happens | Where |
|---|---|---|
| Ingestion | Parse slides, PDFs (with OCR), notebooks, HTML, CSV and YouTube transcripts → ~512-token chunks → Titan v2 embeddings → S3 | `scripts/s3-vectors/`, `backend/s3_vector_store.py` |
| Route | Greetings get a direct reply. When the `agent-system-enabled` flag is on, LangGraph agents (tutor, quiz helper, doubts, feedback, personalised) take over | `backend/services/chat_service.py`, `backend/agents/` |
| Answer cache *(flag)* | Redis fuzzy match (≥0.95 similarity, 1 h TTL) returns repeated questions instantly | `utils.py`, `backend/rag/caching_layer.py` |
| Query enhancement *(flag)* | Rewrites and expands the query for retrieval; the original question is still what goes to the LLM | `backend/rag/query_enhancement.py` |
| Retrieve | Cosine top-k over the S3 index, with optional cross-encoder rerank (`ms-marco-MiniLM-L-12`) | `backend/s3_retriever.py`, `backend/rag/reranker.py` |
| Web fallback | Only when course context is weak: SerpAPI, then DuckDuckGo | `utils.py` |
| Generate | Numbered `[Source n]` context → Bedrock LLM, streamed | `utils.py`, `backend/llm_provider.py`, `backend/llm_router.py` |
| Ground-check *(flag)* | Self-RAG checks support for the answer and appends a disclaimer if it isn't grounded | `backend/rag/self_rag.py` |
| Stream | SSE tokens + clickable citations back to the UI | `backend/api/routes/chat.py` |

A separate `/rag` endpoint (`backend/rag/service.py`) A/B tests an **enhanced** variant with BM25 + dense hybrid search (Reciprocal Rank Fusion) and HyDE against the baseline.

---

## Results

### Continuous RAG evaluation

The **Scheduled RAG Evaluation** workflow runs every weekday. It replays course questions from `Evaluation_files/evaluation_data.jsonl` (64 Q&A pairs) through the live production container, scores the answers with an LLM judge, and posts the results to Slack.

| Metric (runs #198–#204, Oct 13–21 2026, 5 questions per run) | Value |
|---|---|
| Quality gate | **7 / 7 runs passed** |
| Avg correctness (LLM judge, 0–1) | **0.68** (range 0.58–0.74) |
| Avg context recall (0–1) | **0.73** (range 0.60–0.80) |
| Latest run (#204, Oct 21) | correctness 0.70 · context recall 0.80 |

### Live traffic (PostHog)

| Metric | Value |
|---|---|
| Streamed responses, median latency | **11.0 s** |
| Streamed responses, p95 latency | **15.8 s** |
| Success rate | 5 / 5 |
| Avg answer length | ~580 tokens |

> These numbers come from a small sample (5 production responses on Oct 19 2026). The Feb 2026 benchmark below measured a p95 of 31.5 s on Claude 3 Haiku. Treat the comparison as directional until there is more traffic.

### Knowledge base

| Metric | Value |
|---|---|
| Coverage | All 11 INFO 5731 modules |
| Vector chunks | 12,669 |
| Embeddings | Amazon Titan Text v2, 1,024-dim |
| Index size | ~55 MB (`s3://smart-ai-tutor-docs/vector_index/`) |
| Ingestion success | 100% (including OCR for scanned PDFs) |

### Engineering

| Metric | Value |
|---|---|
| Backend tests | 186 (184 pass, 2 skipped) in CI |
| CI checks per PR | 22: unit, contract, e2e, migrations, SAST, Semgrep, CodeQL, DAST, dependency + secret scanning |
| Code review | CodeRabbit + an AI review workflow on every PR |

<details>
<summary>Historical baseline (Feb 2026)</summary>

Offline evaluation on 64 course question-answer pairs:

| Metric | Score |
|---|---|
| Response relevance ≥ 0.8 | 45.3% (29/64) |
| Median relevance score | 0.70 |
| Average retrieval similarity | 0.69 |

Live benchmark on 20 exam-style questions (Claude 3 Haiku): mean latency 23.5 s, p95 31.5 s, 13/20 successful. The failures came from a 60-message session limit, not from retrieval.

</details>

---

## Features

| Feature | Description |
|---|---|
| **RAG chat** | Course-grounded Q&A with streaming answers, source citations and a per-message model picker |
| **Code sandbox** | Generate, explain and debug code (Python / JS / Java) |
| **Quiz generator** | MCQ and open-ended quizzes from lecture material |
| **Agent system** | LangGraph routing to tutor, quiz-helper, doubts, feedback and personalised agents (feature-flagged) |
| **Knowledge graph** | Neo4j Aura concept graph and agent memory, auto-resumed when Aura pauses |
| **Research & resources** | Citation extraction, curated resources, office-hours appointments |
| **Sharing** | Shareable chat links with 24-hour expiry |
| **LLMOps dashboard** | Prompt versions, latency, cost and satisfaction for admins |
| **Cost-aware uptime** | Business-hours EC2 schedule with a graceful maintenance mode |

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, Tailwind CSS 4, Vercel |
| Backend | FastAPI, Python 3.11, Uvicorn, LlamaIndex, LangGraph |
| LLMs (AWS Bedrock) | Llama 3.3 70B (default), Claude 5.5 Sonnet, Claude 5.5 Haiku, Claude Opus 4, GPT 6 Luna, with a circuit breaker and complexity routing |
| Embeddings & vectors | Amazon Titan Text v2 (1,024-dim), custom S3 vector store |
| Data | PostgreSQL, Redis, Neo4j Aura, S3, DynamoDB (hybrid storage option) |
| Observability | Langfuse v4, PostHog, Prometheus, Grafana (+ Grafana Cloud), Alertmanager → Slack, CloudWatch Logs |
| Infra & delivery | Docker, AWS EC2, Vercel, Secrets Manager, GHCR, GitHub Actions. Terraform, Helm and Kubernetes manifests describe a planned cluster deployment that is not live. |

---

## Quick start

**Prerequisites:** Docker 24+ with Compose v2, AWS credentials with Bedrock access (Claude/Llama + Titan), and Node.js 20 (see `.nvmrc`) for frontend work.

```bash
git clone https://github.com/liteshperumalla/Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support.git
cd Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support
cp .env.example .env        # add AWS credentials and SECRET_KEY
docker compose up -d
```

| Service | URL |
|---|---|
| Frontend | http://localhost:4000 |
| Backend API / Swagger | http://localhost:8010 · http://localhost:8010/docs |
| Health / metrics | http://localhost:8010/health · http://localhost:8010/metrics |

Minimal `.env`:

```bash
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
SECRET_KEY=<random-64-char-string>
DATABASE_URL=postgresql://user:pass@localhost:5432/smart_tutor
REDIS_URL=redis://localhost:6380
```

RAG features such as `ENHANCED_RAG_ENABLED`, `RERANKING_ENABLED`, `ANSWER_CACHE_ENABLED` and `AGENT_SYSTEM_ENABLED` are off by default. `.env.example` documents every flag.

Common tasks: `make test` (all tests), `make lint`, `make typecheck`, `make security`, `make env-check`.

---

## Repository layout

```
.
├── backend/                 FastAPI app
│   ├── api/routes/          18 routers: auth, chat (SSE), code, quiz, rag, research, files, admin, health, …
│   ├── agents/              LangGraph multi-agent system + Neo4j client
│   ├── rag/                 hybrid search, HyDE, reranker, self-RAG, caching, query enhancement, eval
│   ├── services/ db/ cloud/ events/
│   ├── s3_vector_store.py   custom S3 vector store · s3_retriever.py LlamaIndex retriever
│   ├── llm_provider.py      Bedrock models · llm_router.py complexity routing · circuit_breaker.py
│   └── langfuse_setup.py    tracing · posthog_tracker.py · llmops.py · prompt_registry.py
├── frontend/                Next.js 16 app (pages, components, /api/backend proxy, Jest tests)
├── utils.py                 core RAG streaming pipeline used by chat (imported by backend services)
├── data/                    course modules, announcements, resources, drift baseline
├── Evaluation_files/        evaluation datasets (64 Q&A pairs) and human-evaluation results
├── e2e/                     Playwright end-to-end tests
├── scripts/                 ops, S3 vector index build, CI helpers, synthetic monitor
├── monitoring/              Prometheus rules, Grafana dashboards, Alertmanager, SLOs
├── terraform/ k8s/ helm/ gitops/   planned cluster deployment (reference, not live)
├── chaos-engineering/ compliance/  resilience experiments, compliance policies
├── docker/                  nginx, entrypoint, DB init · docker-compose*.yml at the root
├── docs/                    architecture (+ diagram sources), ADRs, runbooks, guides, reports
└── .github/workflows/       CI, deploys, schedules, monitoring, evaluation, security
```

The diagrams in this README are generated from code. To regenerate them:

```bash
python docs/architecture/src/rag_pipeline.py
python docs/architecture/src/system_architecture.py
```

---

## API reference

```bash
# Auth
POST /auth/signup                        # register (email verification)
POST /auth/login                         # HttpOnly JWT cookies

# Chat (SSE streaming)
POST /chat/sessions                      # create session
POST /chat/sessions/{id}/messages        # ask a question (streams tokens + sources)
POST /chat/sessions/{id}/share           # share link, 24 h expiry
GET  /chat/share/{share_id}              # public shared session

# Code sandbox
POST /code/generate | /code/explain | /code/debug | /code/chat

# Learning tools
POST /quiz/generate                      # quiz from course materials
POST /research/citations                 # citations for a query
GET  /resources                          # curated resources
GET  /appointments                       # office hours
POST /feedback                           # feedback
GET  /home/overview                      # landing-page status (public)

# Admin (admin role)
GET  /admin/llmops                       # LLMOps logs
GET  /admin/prompts                      # prompt versions
POST /admin/prompts/{name}               # create/update prompt
GET  /admin/agent-metrics                # agent analytics
GET  /admin/knowledge-graph-metrics      # Neo4j stats
```

Full interactive docs: `/docs` on any running backend.

## Security

- **Auth:** RS256 JWTs in HttpOnly cookies with refresh-token rotation.
- **CSRF:** double-submit cookie on every state-changing endpoint.
- **Rate limiting:** per user and per IP (SlowAPI, Redis-backed).
- **Input safety:** Pydantic validation, path-traversal checks, XSS sanitisation, file-type validation.
- **Code execution:** off by default; sandboxed with pattern detection when enabled.
- **Secrets:** AWS Secrets Manager in production, `.env` in development.
- **Supply chain:** CodeQL, Semgrep, SAST, DAST, Trivy, dependency and secret scanning in CI, plus a daily scheduled security scan.

---

## Deployment & operations

| Workflow | What it does |
|---|---|
| **CI Pipeline** | Every PR and push: tests, contract/e2e, migrations, security scans |
| **Production Deploy** | After CI passes on `main`: build + smoke-test images, push to GHCR, roll the backend onto EC2 (candidate → health check → swap), deploy the frontend to Vercel |
| **EC2 Schedule** | Starts/stops EC2 for Mon–Fri 09:00–17:00 CT (DST-aware), and never stops it mid-deploy |
| **Synthetic Production Monitor** | Probes the live API during business hours and alerts Slack on failure |
| **Scheduled RAG Evaluation** | Weekday LLM-judge quality gate against production |
| **Production Observability Bootstrap** | Deploys Prometheus, Grafana and Alertmanager on EC2 and checks Langfuse/PostHog |
| **Security scans · Neo4j Aura resume** | Daily scans; keeps the Aura graph from staying paused |

```bash
git push origin main                 # CI → Production Deploy
curl http://52.2.3.101/health        # health check
docker logs -f smart-tutor-backend   # on the instance
```

Runbooks are in [`docs/runbooks/`](docs/runbooks/) and [`docs/deployment/`](docs/deployment/). The full docs index is [`docs/INDEX.md`](docs/INDEX.md).

---

## Contributing

1. Create a branch: `git checkout -b feat/your-change`
2. Use conventional commits: `feat: …`, `fix: …`, `docs: …`
3. Open a PR. CodeRabbit and the CI suite review it automatically.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).

---

<sub>Built for INFO 5731 — Computational Methods for Information Systems · University of North Texas.</sub>
