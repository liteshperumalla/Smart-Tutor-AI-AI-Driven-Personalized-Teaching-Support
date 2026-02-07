# AWS Migration Plan

This document tracks the detailed migration of **Smart AI Tutor** from the local Next.js/FastAPI stack to AWS-managed services.

## 1. Current Architecture Snapshot
- **UI:** Next.js app served locally (port 4000) via `frontend/`.
- **Auth & Profile:** JSON files under `users.json`, `user_data/`, `previous_chats/`, `quiz_results/`.
- **Retrieval:** LlamaIndex + ChromaDB persisted on disk (`persisted_index/`, `chroma_db/`), recursive chunking pipeline defined in `Data_parsing.py`.
- **LLM / Embeddings:** Ollama (llama3.2) for generation, HuggingFace `BAAI/bge-small-en-v1.5` for embeddings.
- **Observability:** Langfuse SaaS plus local logs in `logs/`.
- **Automation:** Manual execution (local dev commands), no CI/CD.

## 2. Target AWS Architecture
| Concern | AWS Service | Notes |
| --- | --- | --- |
| Document storage | Amazon S3 (versioned bucket) | Mirrors `Modules/`, `data/`; triggers Bedrock knowledge base ingestion. |
| Chunking & embeddings | Amazon Bedrock Knowledge Bases | Hierarchical chunking (parent 1024 tokens overlap 200; child 256 tokens overlap 50). Embedding model: Titan Text Embeddings v2 (floating point, 1024 dims). |
| LLM inference | Amazon Bedrock (Claude 3.5 Sonnet / Llama 3.1) | Replace Ollama calls with `InvokeModel`. |
| Vector store | Managed by Bedrock KB or Amazon OpenSearch Serverless (optional). |
| Backend API | FastAPI app running on AWS App Runner or ECS Fargate (ASGI/Uvicorn). |
| Frontend UI | Next.js (React + TypeScript) deployed via AWS Amplify or S3/CloudFront; consumes FastAPI APIs. |
| Authentication/state | DynamoDB tables: `Users`, `ChatSessions`, `QuizResults`. File uploads stored in S3 prefixes. |
| Secrets/config | AWS Secrets Manager (for `SECRET_KEY`, OAuth credentials) + Systems Manager Parameter Store for non-sensitive settings. |
| Observability | CloudWatch Logs & Metrics + Langfuse (via internet). CloudWatch Alarms for latency/CPU. |
| Delivery pipeline | GitHub Actions → CodeBuild/CodePipeline → ECR (FastAPI) + Amplify build (Next.js). |

## 3. Migration Phases & Tasks
1. **Foundation**
   - [ ] Enable Bedrock + necessary models in chosen region (e.g., us-east-2).
   - [ ] Create S3 buckets: `smart-ai-tutor-docs`, `smart-ai-tutor-uploads`, enable versioning & lifecycle policies.
   - [ ] Set up IAM roles for Bedrock invocation, S3, DynamoDB, CloudWatch.
   - [ ] Push Langfuse keys into Secrets Manager.
2. **Data Plane**
   - [ ] Upload course materials to S3 with organized prefixes (module/week).
   - [ ] Configure Bedrock knowledge base using hierarchical chunking parameters (parent 1024/overlap 200, child 256/overlap 50). Run initial ingestion + evaluation.
   - [ ] Define DynamoDB schemas and write migration script to move `users.json`, `previous_chats`, `quiz_results`.
3. **Application Refactor**
   - [ ] Abstract storage layer to support DynamoDB/S3.
   - [ ] Replace Chroma/Ollama calls with Bedrock APIs (use boto3; keep feature flags for local fallback).
   - [ ] Externalize configuration loading (read from environment variables or AWS Parameter Store).
4. **FastAPI / Next.js Implementation**
   - [ ] Scaffold FastAPI backend (auth, chat, quiz, research, profile routes) + SSE/WebSocket support for streaming.
   - [ ] Build Next.js (React + TypeScript) frontend consuming FastAPI APIs.
   - [ ] Integrate authentication (JWT or Cognito) between FastAPI and Next.js.
5. **Containerization & Deployment**
   - [ ] Containerize FastAPI backend (Dockerfile, Uvicorn entrypoint) and publish image to Amazon ECR.
   - [ ] Deploy backend on App Runner or ECS Fargate (ALB + ACM cert) with IAM role for Bedrock/S3/DynamoDB.
   - [ ] Deploy Next.js frontend via AWS Amplify or S3/CloudFront (CI/CD pipeline for automatic builds).
   - [ ] Configure GitHub Actions/CodePipeline for backend + frontend deployments.
5. **Testing & Cutover**
   - [ ] Run `test_rag_pipeline.py` pointed at Bedrock backend for regression metrics.
   - [ ] Conduct end-to-end UAT (auth, chat, quiz, research mode).
   - [ ] Switch DNS / user entry point to AWS-hosted URL.
   - [ ] Monitor CloudWatch/Langfuse; rollback by pointing DNS back to local environment if issues arise.

## 4. Immediate Next Actions
1. ✅ Add Dockerfile (+ `.dockerignore` and entrypoint) for FastAPI backend.
2. Write infra bootstrap scripts (CloudFormation/Terraform skeleton) for S3, IAM roles, Bedrock access policies.
3. Draft DynamoDB table definitions + migration scripts.
4. Remodel UI stack: ✅ FastAPI backend skeleton + Next.js frontend scaffolding (initial routes, shared auth).

This file will evolve as each phase completes. Update checklist items and add links to Terraform templates, deployment scripts, and runbooks as they are created.
