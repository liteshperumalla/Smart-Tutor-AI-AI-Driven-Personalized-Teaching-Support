# Smart Tutor AI

> AI-driven personalized teaching companion for INFO 5731 at University of North Texas.
> Grounding LLM responses in course materials using Retrieval-Augmented Generation.

[![Live Demo](https://img.shields.io/badge/Live_Demo-Vercel-black?logo=vercel)](https://frontend-iota-cyan-70.vercel.app)
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
| **Frontend (Vercel)** | https://frontend-iota-cyan-70.vercel.app |
| **Backend API** | http://52.2.3.101/health |
| **API Docs** | http://52.2.3.101/docs |

> Register an account or use a guest session to try the tutor. The knowledge base covers all 11 modules of INFO 5731 Spring 2025.

---

## RAG Pipeline

The system implements a four-stage pipeline to eliminate hallucinations:

```
  Course Materials               Query
  (PDF, PPTX, DOCX,         ┌─────────┐
   IPYNB, HTML, Video)  ───▶│  Parse  │
                             └────┬────┘
                                  │  Semantic chunks
                             ┌────▼────┐
         Amazon Titan   ───▶│  Embed  │ 1,024-dim vectors
         Embeddings          └────┬────┘
                                  │  FAISS / S3 index
                             ┌────▼────┐
         Student query  ───▶│Retrieve │ Top-k similarity search
                             └────┬────┘
                                  │  Retrieved context
                             ┌────▼──────────────────┐
                             │  Generate (Bedrock)    │
                             │  Claude 3 Haiku/Llama  │
                             └────────────────────────┘
```

**Key design decision:** Rather than fine-tuning (costly, requires labeled data, drifts with syllabus updates), RAG allows zero-cost knowledge updates — just re-index new lecture slides.

---

## Results

### Knowledge Base

| Metric | Value |
|---|---|
| Documents processed | 85 across 11 course modules |
| Processing success rate | 100% (including OCR for scanned PDFs) |
| Total vector chunks | 14,049 |
| Embedding model | Amazon Titan (1,024-dim) |
| Vector index size | 56.5 MB |
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
│                Next.js 14 · Tailwind CSS                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS / SSE streaming
┌───────────────────────────▼─────────────────────────────────────┐
│                    FastAPI Backend (AWS EC2)                     │
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
  │  S3 (vectors)  PostgreSQL  DynamoDB  Redis  Neo4j           │
  └─────────────────────────────────────────────────────────────┘
                            │
  ┌─────────────────────────▼────────────────────────────────────┐
  │                    AWS Bedrock                               │
  │     Claude 3 Haiku (chat)  ·  Titan Embeddings              │
  └──────────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Description |
|---|---|
| **RAG Chat** | Course-grounded Q&A with source citations, streaming responses |
| **Code Sandbox** | AI-powered code generation, explanation, and debugging (Python/JS/Java) |
| **Quiz Generator** | Automated MCQ and open-ended quiz generation from lecture materials |
| **Agent System** | Multi-agent routing (tutor, quiz helper, feedback, doubts agents) |
| **Knowledge Graph** | Neo4j-backed concept relationship graph built from interactions |
| **Collaborative Sharing** | Shareable chat links with 24-hour expiry |
| **LLMOps Dashboard** | Prompt versioning, latency tracking, satisfaction metrics |
| **PostHog Analytics** | Event taxonomy, LLM cost tracking, feature flags |
| **File Upload** | Direct document ingestion and indexing from the UI |
| **Prometheus Metrics** | `/metrics` endpoint with LLM request/latency/token counters |

---

## Tech Stack

| Component | Technology |
|---|---|
| Frontend | Next.js 14, Tailwind CSS, Lucide React |
| Backend | FastAPI (Python 3.11), Uvicorn |
| LLM | AWS Bedrock (Claude 3 Haiku, Llama 3.2 11B/90B) |
| Embeddings | Amazon Titan (1,024-dim) |
| Vector Store | LlamaIndex + S3 persistence |
| Graph DB | Neo4j Community (knowledge graph) |
| Relational DB | PostgreSQL (users, sessions) |
| Session Store | DynamoDB |
| Cache | Redis |
| Observability | Prometheus + Grafana, PostHog, Langfuse |
| Infrastructure | Docker Compose, AWS EC2, Vercel, AWS Secrets Manager |
| CI/CD | GitHub Actions, CodeRabbit AI |

---

## Quick Start

### Prerequisites

- Docker 24+ and Docker Compose V2
- AWS credentials with Bedrock access (Claude 3 + Titan Embeddings)
- Node.js 18+ (frontend dev only)

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
│   │   ├── routes/          # auth, chat, code, quiz, admin
│   │   ├── dependencies.py  # auth, rate limiting middleware
│   │   └── main.py
│   ├── agents/              # multi-agent system (tutor, quiz, feedback, doubts)
│   ├── rag/                 # retrieval pipeline, chunking, evaluation
│   ├── config.py            # singleton config (env + AWS Secrets Manager)
│   ├── llm_provider.py      # Bedrock / Ollama abstraction
│   ├── llmops.py            # LLMOps logging + Prometheus metrics
│   ├── prompt_registry.py   # versioned prompt store
│   └── s3_retriever.py      # S3-backed vector retrieval
├── frontend/
│   └── src/
│       ├── app/             # chat, code, quiz, admin, evaluation pages
│       ├── components/      # site-chrome, chat, knowledge-base-widget
│       └── lib/             # API client, auth utilities
├── monitoring/              # Prometheus, Grafana, SLO definitions
├── e2e/                     # end-to-end test suite
├── docs/                    # architecture docs, runbooks, design plans
└── docker-compose.yml
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

# Admin (requires admin role)
GET  /admin/llmops            # LLMOps logs
GET  /admin/prompts           # List prompt versions
POST /admin/prompts/{name}    # Create/update prompt
GET  /admin/agent-metrics     # Agent system analytics
```

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

The system is deployed on AWS EC2 (t2.micro) with frontend on Vercel:

```bash
# Production rebuild
docker compose -f docker-compose.yml up -d --build backend frontend

# Check service health
curl http://52.2.3.101/health

# View logs
docker compose logs -f backend
```

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
