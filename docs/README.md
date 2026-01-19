# Smart Tutor AI

> AI-driven personalized teaching companion for INFO 5731 at University of North Texas. Built with a modern tech stack featuring Next.js 16, FastAPI, and AWS Bedrock.

[![CI/CD](https://img.shields.io/badge/CI/CD-GitHub_Actions-blue)](https://github.com/liteshperumalla/Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support/actions)
[![Code Review](https://img.shields.io/badge/Code_Review-CodeRabbit_AI-green)](https://coderabbit.ai)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## Overview

Smart Tutor AI solves the problem of generic, hallucination-prone AI responses by grounding answers in course-specific materials using Retrieval-Augmented Generation (RAG). Students receive accurate, context-aware responses from verified course content.

### Key Capabilities

- **Conversational AI**: Context-aware Q&A using RAG with 12,760+ indexed chunks
- **Code Sandbox**: AI-powered code generation, explanation, and debugging
- **Assessment Tools**: Automated quiz generation from course materials
- **Research Mode**: Multi-format document ingestion and indexing
- **Collaboration**: Shareable chat links for study groups

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Next.js 16, Tailwind CSS, Lucide React Icons |
| Backend | FastAPI (Python 3.11), Uvicorn |
| LLM | AWS Bedrock (Llama 3.2 11B/90B) |
| Vector Store | LlamaIndex with S3 persistence |
| Database | PostgreSQL (users), DynamoDB (sessions) |
| Cache | Redis |
| Infrastructure | Docker Compose, AWS Secrets Manager |
| Code Review | CodeRabbit AI |

## Quick Start

### Prerequisites

- Docker 24+ and Docker Compose V2
- Node.js 18+ (frontend development)
- AWS credentials with Bedrock access

### Launch All Services

```bash
git clone https://github.com/liteshperumalla/Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support.git
cd Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support
docker compose up -d
```

### Access Points

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:4000 | Next.js application |
| Backend API | http://localhost:8010 | FastAPI endpoints |
| Health Check | http://localhost:8010/health | Service status |
| Grafana | http://localhost:3001 | Monitoring dashboards |

## Project Structure

```
smart-tutor-ai/
├── backend/                    # FastAPI backend
│   ├── api/
│   │   ├── routes/            # API endpoints (auth, chat, code, etc.)
│   │   ├── dependencies.py    # Auth, rate limiting
│   │   └── main.py            # Application entry
│   ├── config.py              # Configuration management
│   ├── bedrock_llm.py         # AWS Bedrock adapter
│   └── Dockerfile
├── frontend/                   # Next.js 16 application
│   ├── src/
│   │   ├── app/               # App Router pages
│   │   ├── components/        # React components
│   │   ├── hooks/             # Custom hooks (useAuthToken)
│   │   └── lib/               # API utilities
│   └── Dockerfile
├── data/
│   └── modules/               # Chunked course materials
├── .github/
│   └── workflows/             # CI/CD pipelines
├── docker-compose.yml
└── docs/
    └── README.md
```

## API Reference

### Authentication

```bash
# Login
POST /auth/login
Content-Type: application/json
{"username": "testuser123", "password": "Test@12345678"}

# HttpOnly cookies set automatically
```

### Code Sandbox

```bash
# Generate code
POST /code/generate
{"prompt": "Python function to calculate factorial", "language": "python"}

# Explain code
POST /code/explain
{"code": "def add(a, b): return a + b", "language": "python"}

# Debug code
POST /code/debug
{"code": "def div(a, b): return a / b", "language": "python"}
```

### Chat with Sharing

```bash
# Create session
POST /chat/sessions
{"title": "RAG Pipeline Discussion", "model_id": "bedrock"}

# Share session
POST /chat/sessions/{id}/share?expires_in_hours=24

# Access shared (no auth required)
GET /shared/{share_id}
```

## Configuration

### Required Environment Variables

```bash
# AWS Bedrock
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# Application
SECRET_KEY=...
DATABASE_URL=...
REDIS_URL=...
```

### Code Execution Safety

Code execution is **disabled by default** for security. To enable locally:

```bash
export ENABLE_CODE_EXECUTION=true
```

Safety measures include:
- Rate limiting: 30 requests/min, 10 executions/hour per user
- Code size limits: 10KB input, 100KB output
- Dangerous pattern detection (blocks `os`, `subprocess`, `eval`, etc.)
- Per-language timeouts: Python (5s), JavaScript (10s), Java (15s)

## Code Quality

### CodeRabbit AI Reviews

Every PR automatically receives AI-powered reviews covering:

- **Security**: Secrets exposure, injection vulnerabilities
- **Performance**: Inefficient patterns, resource leaks
- **Best Practices**: Type hints, docstrings, context managers
- **Bug Detection**: Edge cases, null handling
- **Style**: Naming conventions, code organization

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

## Deployment

### Development

```bash
# Rebuild and restart backend
docker compose build backend --no-cache
docker compose up -d backend

# View logs
docker compose logs -f backend
```

### Production Considerations

1. **Code Execution**: Never enable in production without proper sandboxing (Docker, gVisor, or AWS Lambda)
2. **Secrets**: Use AWS Secrets Manager or a secrets vault
3. **Scaling**: Stateless backend allows horizontal scaling
4. **Monitoring**: Prometheus metrics + Grafana dashboards included

## Architecture

```
                    ┌─────────────────────┐
                    │   Next.js Frontend  │
                    │   (localhost:4000)  │
                    └──────────┬──────────┘
                               │
                    HTTP/WebSocket │
                               ▼
                    ┌─────────────────────┐
                    │    FastAPI Backend  │
                    │  (localhost:8010)   │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │  RAG Pipeline│ │ Code Sandbox │ │  Auth Layer  │
    │ LlamaIndex   │ │ Bedrock Llama│ │  JWT/Cookies │
    │ S3 Vectors   │ │ 3.2 (11B)    │ │              │
    └──────────────┘ └──────────────┘ └──────────────┘
              │                │
              └────────────────┼────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
         ┌──────────────────┐  ┌──────────────────┐
         │  AWS Bedrock     │  │  Data Stores     │
         │  Llama 3.2 90B   │  │  PostgreSQL      │
         │                  │  │  Redis           │
         └──────────────────┘  │  DynamoDB        │
                               └──────────────────┘
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

All PRs receive automatic CodeRabbit reviews. Address feedback before merging.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Built for INFO 5731 - Computational Methods for Information Systems at University of North Texas*
