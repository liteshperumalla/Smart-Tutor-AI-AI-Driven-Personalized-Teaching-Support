# Smart Tutor AI: AI-Driven Personalized Teaching Support

An AI-first course companion for INFO 5731 at University of North Texas. Leverages Retrieval-Augmented Generation (RAG) with Large Language Models to provide context-aware, personalized teaching support.

## Problem

Students struggle with personalized learning support, especially accessing relevant information from course materials. Traditional search engines and LLMs often return irrelevant or inaccurate results, creating gaps in learning comprehension and academic performance.

## Approach

Combines course-specific materials with advanced language modeling to eliminate LLM hallucinations and ensure factual, relevant responses through a multi-step pipeline including document parsing, vector embeddings, similarity search, and intelligent response generation.

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 16, Tailwind CSS, Lucide React Icons |
| **Backend** | FastAPI, Python 3.11 |
| **LLM Provider** | AWS Bedrock (Llama 3.2 11B/90B) |
| **Vector Store** | LlamaIndex with S3 storage (12,760+ chunks) |
| **Database** | PostgreSQL (user data), DynamoDB (chat sessions) |
| **Caching** | Redis |
| **Containerization** | Docker Compose |
| **Code Review** | CodeRabbit AI |

## Features

| Feature | Description |
|---------|-------------|
| **AI Chat** | Context-aware Q&A with course materials using RAG |
| **Code Sandbox** | Generate, explain, debug code with AWS Bedrock Llama 3.2 |
| **Quiz Generator** | Create assessments from course content |
| **Research Mode** | Multi-format document upload and indexing |
| **Shareable Chats** | Generate links to share conversations |
| **Code Review** | AI-powered code analysis and suggestions |

## Quickstart

### Prerequisites

- Docker & Docker Compose
- AWS Account with Bedrock access
- Node.js 18+ (for frontend)

### Run with Docker Compose

```bash
# Clone and enter directory
git clone https://github.com/liteshperumalla/Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support.git
cd Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support

# Start all services
docker compose up -d

# Access the application
Frontend: http://localhost:4000
Backend API: http://localhost:8010
Health Check: http://localhost:8010/health
```

### Services Running

| Service | Port | Status |
|---------|------|--------|
| Frontend (Next.js) | :4000 | ✓ Running |
| Backend (FastAPI) | :8010 | ✓ Running |
| Redis | :6380 | ✓ Running |
| PostgreSQL | :5432 | ✓ Running |
| DynamoDB Local | :8001 | ✓ Running |
| Prometheus | :9090 | ✓ Running |
| Grafana | :3001 | ✓ Running |

### Manual Frontend Setup

```bash
cd frontend
npm install
npm run dev -- --port 4000
# Open http://localhost:4000
```

## Code Sandbox

The `/code` page provides AI-powered coding assistance:

```bash
# API Endpoints
POST /code/generate  # Generate code from prompts
POST /code/explain   # Explain code functionality
POST /code/debug     # Debug and fix code issues
POST /code/chat      # Coding assistant chat
GET  /code/languages # Supported languages
```

**Safety Features:**
- Rate limiting (30 requests/min, 10 executions/hour)
- Code size limits (10KB input, 100KB output)
- Dangerous pattern detection (blocks unsafe imports)
- Per-language timeouts (Python: 5s, JavaScript: 10s, Java: 15s)

## Shareable Chat Links

Create shareable links for chat sessions:

```bash
# Create share link (expires in 24 hours)
POST /chat/sessions/{session_id}/share?expires_in_hours=24

# Access shared chat (no auth required)
GET /shared/{share_id}
```

## CodeRabbit AI Code Review

Automated AI-powered code reviews on every PR:

```bash
# View reviews on GitHub PRs
# https://github.com/liteshperumalla/Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support/pull/X
```

**Review Categories:**
- Security (secrets, injection risks)
- Performance (inefficient code)
- Best Practices (type hints, docstrings)
- Bugs (edge cases, null handling)
- Style (naming, organization)

## AWS Bedrock Models

| Model | Purpose |
|-------|---------|
| Llama 3.2 11B | Code generation/explanation |
| Llama 3.2 90B | Chat responses |
| Titan Embeddings | Vector search |

## Test Credentials

- **Username:** `testuser123`
- **Password:** `Test@12345678`

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Next.js Frontend                        │
│                    (localhost:4000)                          │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP/WebSocket
┌─────────────────────▼───────────────────────────────────────┐
│                      FastAPI Backend                         │
│                    (localhost:8010)                          │
├─────────────────────┬───────────────────────────────────────┼
│  ┌───────────────┐  │  ┌─────────────────────────────────┐  │
│  │ RAG Pipeline  │  │  │     Code Sandbox               │  │
│  │ - LlamaIndex  │  │  │     AWS Bedrock Llama 3.2      │  │
│  │ - S3 Vectors  │  │  │     Python/JS/Java Support     │  │
│  └───────────────┘  │  └─────────────────────────────────┘  │
├─────────────────────┴───────────────────────────────────────┤
│                     AWS Bedrock (Llama 3.2)                  │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL  │  Redis  │  DynamoDB  │  S3 Vector Store      │
└─────────────────────────────────────────────────────────────┘
```

## Development

```bash
# Rebuild backend after code changes
docker compose build backend --no-cache
docker compose up -d backend

# View logs
docker compose logs -f backend

# Check health
curl http://localhost:8010/health
```

## Security

- **Code execution** is DISABLED by default
- Set `ENABLE_CODE_EXECUTION=true` to enable (not recommended in production)
- Use isolated containers for production code execution
- HttpOnly cookies for authentication
- AWS Secrets Manager for credentials

## Results & Metrics

- **24/7 Availability**: Continuous student support
- **12,760+ Document Chunks**: Indexed from course materials
- **43 Sources**: PDFs, PPTX, Jupyter notebooks
- **Multi-format Processing**: PDF, DOCX, PPTX, IPYNB, HTML

---

*INFO 5731 - Computational Methods for Information Systems | University of North Texas*
