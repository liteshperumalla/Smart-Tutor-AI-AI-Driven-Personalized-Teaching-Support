# Smart Tutor AI

> AI-driven personalized teaching companion for INFO 5731 at University of North Texas.
> Grounding LLM responses in course materials using Retrieval-Augmented Generation.

[![Live Demo](https://img.shields.io/badge/Live_Demo-Vercel-black?logo=vercel)](https://smart-ai-tutor.vercel.app)
[![Backend](https://img.shields.io/badge/Backend-AWS_EC2-orange?logo=amazon-aws)](http://52.2.3.101)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-blue?logo=github-actions)](https://github.com/liteshperumalla/Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support/actions)
[![Code Review](https://img.shields.io/badge/Code_Review-CodeRabbit_AI-green)](https://coderabbit.ai)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## Overview

Smart Tutor AI solves the problem of generic, hallucination-prone LLM responses by grounding answers in course-specific materials. Students in INFO 5731 (Computational Methods for Information Systems) can ask questions about any lecture, code demo, or reading — and receive answers directly sourced from the course corpus.

**The core problem:** Off-the-shelf LLMs confidently answer questions about course-specific content but frequently hallucinate or generalize. RAG constrains generation to indexed course materials, producing factually grounded responses.

---

## Live Demo

| Environment | URL |
|---|---|
| **Frontend (Vercel)** | https://smart-ai-tutor.vercel.app |
| **Backend API** | http://52.2.3.101/health |
| **API Docs** | http://52.2.3.101/docs |

> Register an account to try the tutor. The knowledge base covers all 11 modules of INFO 5731 Spring 2025.

---

## RAG Pipeline

The system implements a four-stage pipeline to eliminate hallucinations:

![RAG pipeline architecture](docs/architecture/RAG_architecture.png)

**Key design decision:** Rather than fine-tuning (costly, requires labeled data, drifts with syllabus updates), RAG allows zero-cost knowledge updates — just re-index new lecture slides.

---

## Results

### Knowledge Base

| Metric | Value |
|---|---|
| Source documents | INFO 5731 corpus across 11 course modules |
| Processing success rate | 100% (including OCR for scanned PDFs) |
| Total vector chunks | 12,669 |
| Embedding model | Amazon Titan (1,024-dim) |
| Vector index size | ~55 MB (`s3://smart-ai-tutor-docs/vector_index/`) |
| Supported formats | PDF, PPTX, DOCX, IPYNB, HTML, CSV, YouTube transcripts |

### Retrieval Quality

Evaluated on 64 course-specific question-answer pairs:

| Metric | Score |
|---|---|
| Response relevance ≥ 0.8 | 45.3% (29/64) |
| Median relevance score | 0.70 / 1.0 |
| Top cosine similarity score | 0.79 (Data Cascades query) |
| Average retrieval similarity | 0.69 across test queries |

### Live System Performance (Feb 2026)

Measured against 20 real INFO 5731 exam-style questions on the deployed system:

| Metric | Value |
|---|---|
| Response success rate | 13/20 (65%) |
| Mean response latency | 23.5s |
| Median latency | 22.2s |
| P95 latency | 31.5s |
| Average response length | 313 words |
| LLM backend | AWS Bedrock Claude 3 Haiku |

> **Note:** The 35% failure rate in this batch was caused by a session message-count limit (60 messages), not retrieval failure. Individual cold-start queries succeed consistently.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Vercel (Frontend)                           │
│            Next.js 16 · React 19 · Tailwind v4                  │
│      /api/backend/* proxy → graceful 503 on scheduled downtime  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS / streaming
┌───────────────────────────▼─────────────────────────────────────┐
│              FastAPI Backend (AWS EC2 · t3a.medium)              │
│          JWT Auth · Rate Limiting · CSRF Protection             │
└──────┬──────────┬──────────┬──────────┬──────────┬─────────────┘
       │          │          │          │          │
  ┌────▼────┐ ┌──▼──────┐ ┌─▼──────┐ ┌─▼──────┐ ┌▼──────────┐
  │   RAG   │ │  Code   │ │  Auth  │ │ Agent  │ │  LLMOps   │
  │Pipeline │ │Sandbox  │ │Service │ │ System │ │ + PostHog │
  └────┬────┘ └──┬──────┘ └─┬──────┘ └─┬──────┘ └───────────┘
       │         │          │          │
  ┌────▼─────────▼──────────▼──────────▼────────────────────────┐
  │                        Data Layer                           │
  │  S3 (vectors)  PostgreSQL  DynamoDB  Redis  Neo4j Aura      │
  └─────────────────────────────────────────────────────────────┘
                            │
  ┌─────────────────────────▼────────────────────────────────────┐
  │                    AWS Bedrock                               │
  │     Claude Haiku (chat)  ·  Titan Embeddings               │
  └──────────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Description |
|---|---|
| **RAG Chat** | Course-grounded Q&A with source citations, streaming responses |
| **Code Sandbox** | AI-powered code generation, explanation, and debugging (Python/JS/Java) |
| **Quiz Generator** | Automated MCQ and open-ended quiz generation from lecture materials |
| **Agent System** | Multi-agent routing (tutor, quiz helper, feedback, doubts, personalised agents) via LangGraph |
| **Knowledge Graph** | Neo4j Aura-backed concept relationship graph, with scheduled auto-resume of paused instances |
| **Collaborative Sharing** | Shareable chat links with 24-hour expiry |
| **LLMOps Dashboard** | Prompt versioning, latency tracking, satisfaction metrics |
| **PostHog Analytics** | Event taxonomy, LLM cost tracking, feature flags |
| **File Upload** | Direct document ingestion and indexing from the UI |
| **Prometheus Metrics** | `/metrics` endpoint with LLM request/latency/token counters |
| **Cost-optimized uptime** | EC2 scheduled to Mon–Fri 9–5 CT with a graceful in-app maintenance notice off-hours |

---

## Tech Stack

| Component | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, Tailwind CSS v4, Lucide React |
| Backend | FastAPI (Python 3.11), Uvicorn |
| LLM | AWS Bedrock (Claude Haiku, Llama 3) with circuit breaker + complexity routing |
| Embeddings | Amazon Titan (1,024-dim) |
| Vector Store | LlamaIndex + custom S3 vector store (`backend/s3_vector_store.py`) |
| Graph DB | Neo4j Aura (managed; Aura API auto-resume) |
| Relational DB | PostgreSQL (users, sessions) |
| Session Store | DynamoDB |
| Cache | Redis |
| Observability | Prometheus + Grafana, PostHog, Langfuse |
| Infrastructure | Docker, AWS EC2 (t3a.medium), Vercel, AWS Secrets Manager |
| CI/CD | GitHub Actions, CodeRabbit AI |

---

## Quick Start

### Prerequisites

- Docker 24+ and Docker Compose V2
- AWS credentials with Bedrock access (Claude + Titan Embeddings)
- Node.js 20 (`>=20.9.0 <21`, see `.nvmrc`) — frontend dev only

### Run Locally

```bash
git clone https://github.com/liteshperumalla/Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support.git
cd Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support
cp .env.example .env   # fill in AWS credentials and SECRET_KEY
docker compose up -d
```

### Access Points

| Service | URL |
|---|---|
| Frontend | http://localhost:4000 |
| Backend API | http://localhost:8010 |
| API Docs (Swagger) | http://localhost:8010/docs |
| Health Check | http://localhost:8010/health |
| Metrics | http://localhost:8010/metrics |

### Required Environment Variables

```bash
# AWS Bedrock
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# Application
SECRET_KEY=<random-64-char-string>
DATABASE_URL=postgresql://user:pass@localhost:5432/smart_tutor
REDIS_URL=redis://localhost:6380
```

---

## Project Structure

```
smart-tutor-ai/
├── backend/
│   ├── api/
│   │   ├── routes/             # 17 routers: auth, chat, code, quiz, admin, evaluation,
│   │   │                       #   research, resources, appointments, feedback, profile,
│   │   │                       #   files, home, health, rag, ws_chat
│   │   ├── dependencies.py     # auth, rate limiting, admin-session guards
│   │   └── main.py             # FastAPI app factory
│   ├── agents/                 # LangGraph multi-agent system
│   │   ├── graph.py, router.py # graph wiring + intent routing
│   │   ├── tutor_agent.py, doubts_agent.py, quiz_helper_agent.py,
│   │   │                       #   feedback_agent.py, personalised_agent.py
│   │   ├── neo4j_client.py     # Aura driver + auto-resume on connectivity errors
│   │   └── streaming.py        # __AGENT_META__ streaming protocol
│   ├── rag/                    # retrieval pipeline: hybrid_search, reranker, hyde,
│   │                           #   self_rag, semantic_chunker, query_enhancement, evaluation
│   ├── cloud/ · db/ · events/ · content/   # provider adapters, DB layer, events, static content
│   ├── config.py               # singleton config (env + AWS Secrets Manager)
│   ├── s3_vector_store.py      # custom S3 vector store (build/search/serialize)
│   ├── s3_retriever.py         # LlamaIndex-compatible S3 retriever (+ reranking)
│   ├── llm_provider.py · llm_router.py · circuit_breaker.py   # Bedrock + routing + resilience
│   ├── llmops.py · posthog_tracker.py · langfuse_setup.py     # observability
│   └── prompt_registry.py      # versioned prompt store
├── frontend/                   # Next.js 16 App Router
│   └── src/
│       ├── app/                # pages: chat, code, quiz, evaluation, admin, research,
│       │   │                   #   appointments, feedback, profile, resources, about, auth/*
│       │   └── api/backend/    # proxy route → EC2 backend (classified 503 on downtime)
│       ├── components/         # site-chrome, chat/*, maintenance-banner, page-hero, …
│       ├── context/ · hooks/ · types/
│       └── lib/                # api.ts, api-client.ts, auth.ts, maintenance.ts, events.ts
├── .github/workflows/          # CI, Production Deploy, ec2-schedule, neo4j-aura-resume
├── scripts/                    # ops + s3-vectors (index rebuild), aws, ci helpers
├── monitoring/                 # prometheus, grafana, alertmanager, slo, finops
├── terraform/ · k8s/ · helm/ · gitops/   # IaC, manifests, Helm chart, ArgoCD
├── chaos-engineering/ · e2e/   # chaos experiments, Playwright end-to-end tests
├── docs/                       # adr, architecture, deployment runbooks, development
├── docker/ · Dockerfile · docker-compose*.yml
└── Makefile · pyproject.toml · requirements.txt
```

---

## API Reference

```bash
# Authentication
POST /auth/signup            # Register (email verification required)
POST /auth/login             # Login → HttpOnly JWT cookies

# Chat (streaming SSE)
POST /chat/sessions                          # Create session
POST /chat/sessions/{id}/messages            # Send message (streaming)
POST /chat/sessions/{id}/share               # Share with 24h expiry
GET  /chat/share/{share_id}                  # Public shared session

# Code Sandbox
POST /code/generate          # Generate code from prompt
POST /code/explain           # Explain code snippet
POST /code/debug             # Debug with suggestions
POST /code/chat              # Coding assistant conversation

# Learning tools
POST /quiz/generate          # Generate a quiz from course materials
POST /research/citations     # Extract citations from a query
GET  /resources              # Curated learning resources
GET  /appointments           # Office-hours / appointment scheduling
POST /feedback               # Submit feedback
GET  /home/overview          # Landing-page system status (public)

# Admin (requires admin role)
GET  /admin/llmops                  # LLMOps logs
GET  /admin/prompts                 # List prompt versions
POST /admin/prompts/{name}          # Create/update prompt
GET  /admin/agent-metrics           # Agent system analytics (Neo4j-backed)
GET  /admin/knowledge-graph-metrics # Knowledge graph stats (Neo4j Aura)
```

> Interactive Swagger docs: `http://52.2.3.101/docs` (or `/docs` locally).

---

## Security

- **Authentication:** RS256 JWT tokens via HttpOnly cookies, refresh token rotation
- **CSRF Protection:** Double-submit cookie pattern on all state-changing endpoints
- **Rate Limiting:** Per-user and per-IP via SlowAPI, Redis-backed
- **Input Validation:** Pydantic models, path traversal prevention, XSS sanitization
- **Code Execution:** Disabled by default; sandboxed with pattern detection when enabled
- **Secrets Management:** AWS Secrets Manager in production, `.env` fallback in dev

---

## Deployment

The backend runs on AWS EC2 (`t3a.medium`, Elastic IP `52.2.3.101`); the frontend is on Vercel. Deploys are automated: a push to `main` runs the **CI Pipeline**, which on success triggers the **Production Deploy** workflow (`.github/workflows/deploy-production.yml`) to roll a new container onto EC2 over SSH.

```bash
# Trigger a deploy
git push origin main          # CI Pipeline → Production Deploy (GitHub Actions)

# Check service health
curl http://52.2.3.101/health

# View backend logs (on the instance)
docker logs -f smart-tutor-backend
```

**Cost-optimized scheduling.** To cut the always-on compute bill, the instance is stopped outside **Mon–Fri 09:00–17:00 America/Chicago** by `.github/workflows/ec2-schedule.yml` (DST-aware, with a `workflow_dispatch` manual start/stop override). The Elastic IP and `restart=unless-stopped` containers mean the stack auto-recovers on the morning boot; off-hours, the frontend shows a graceful maintenance notice instead of errors (`frontend/src/lib/maintenance.ts`).

See [`docs/deployment/`](docs/deployment/) for full production runbooks.

---

## Evaluation

RAG quality evaluation scripts are in `backend/rag/tests/`:

```bash
# Run comprehensive evaluation against live system
python backend/rag/tests/run_comprehensive_evaluation.py --variant production

# Baseline evaluation
python backend/rag/tests/run_evaluation.py
```

Evaluation data and results are in [`Evaluation_files/`](Evaluation_files/).

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/amazing-feature`
3. Commit with conventional commits: `git commit -m 'feat: add amazing feature'`
4. Open a Pull Request — every PR gets automatic CodeRabbit AI review

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built for INFO 5731 — Computational Methods for Information Systems · University of North Texas · Spring 2025*
