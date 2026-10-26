# Documentation Index

This directory contains all project documentation organized by category.

## Quick Links

| Category | Description | Key Documents |
|----------|-------------|---------------|
| [Guides](./guides/) | Getting started and reference guides | [Quick Start](./guides/QUICK_START.md), [How to Run](./guides/HOW_TO_RUN.md) |
| [AWS](./aws/) | AWS infrastructure and migration | [AWS Deployment](./aws/COMPLETE_AWS_DEPLOYMENT.md) |
| [Deployment](./deployment/) | Deployment guides and checklists | [Deployment Guide](./deployment/DEPLOYMENT_GUIDE.md) |
| [Security](./security/) | Security implementation docs | [Security Overview](./security/README-SECURITY.md) |
| [Architecture](./architecture/) | System design and diagrams | [System diagram](./architecture/system-architecture.svg), [RAG pipeline](./architecture/rag-pipeline.svg) |
| [RAG](./rag/) | RAG pipeline and LLM evaluation | [RAG Architecture](./rag/RAG_ARCHITECTURE_ANALYSIS.md) |
| [Development](./development/) | Phase-by-phase improvements | [Phase 1](./development/PHASE1_IMPROVEMENTS.md) |

---

## Directory Structure

```
docs/
├── INDEX.md                 # This file
├── guides/                  # Getting started guides
│   ├── QUICK_START.md
│   ├── HOW_TO_RUN.md
│   ├── ENV_SETUP.md
│   ├── COMMAND_REFERENCE.md
│   └── CODERABBIT.md
├── aws/                     # AWS infrastructure
│   ├── COMPLETE_AWS_DEPLOYMENT.md
│   ├── AWS_INFRASTRUCTURE_COMPLETE.md
│   ├── AWS_MIGRATION_STATUS.md
│   ├── AWS_PRODUCTION_STATUS.md
│   ├── AWS_TEST_REPORT.md
│   ├── SQS_JOBS_SETUP.md
│   ├── FIX_AWS_ISSUES.md
│   └── aws_migration_plan.md
├── deployment/              # Deployment & operations
│   ├── DEPLOYMENT_GUIDE.md
│   ├── DEPLOYMENT_CHECKLIST.md
│   ├── PRODUCTION_DEPLOYMENT_GUIDE.md
│   ├── PRODUCTION_HARDENING_COMPLETE.md
│   ├── PRODUCTION_READY_SUMMARY.md
│   ├── HTTPS_SETUP_GUIDE.md
│   ├── HELM_CHARTS_COMPLETE.md
│   └── K8S_DEPLOYMENT_COMPLETE.md
├── security/                # Security documentation
│   ├── README-SECURITY.md
│   ├── BACKEND_SECURITY_COMPLETE.md
│   ├── CICD_SECURITY_ENHANCEMENT_COMPLETE.md
│   ├── HTTPONLY_COOKIES_MIGRATION.md
│   ├── SECRETS_MANAGER_IMPLEMENTATION.md
│   └── SECURITY_IMPLEMENTATION_COMPLETE.md
├── architecture/            # System architecture
│   ├── FINAL_ARCHITECTURE_DELIVERABLES.md
│   ├── DESIGN_SYSTEM_SUMMARY.md
│   ├── MICROSERVICES_ARCHITECTURE_ANALYSIS.md
│   ├── MICROSERVICES_IMPLEMENTATION_SUMMARY.md
│   ├── PLATFORM_ENGINEERING_AUDIT.md
│   ├── PLATFORM_ENGINEERING_COMPLETE_SUMMARY.md
│   ├── BACKEND_IMPROVEMENTS.md
│   ├── system-architecture.svg   # README diagram (generated)
│   ├── rag-pipeline.svg          # README diagram (generated)
│   └── src/                      # diagram generators: python docs/architecture/src/*.py
├── rag/                     # RAG & LLM documentation
│   ├── RAG_ARCHITECTURE_ANALYSIS.md
│   ├── RAG_COMPLETE_IMPLEMENTATION.md
│   ├── RAG_ENHANCEMENTS_FINAL_SUMMARY.md
│   ├── LLM_EVALUATION_GUIDE.md
│   ├── LLM_EVALUATION_ANALYSIS.md
│   ├── LANGFUSE_INTEGRATION.md
│   ├── FINE_TUNING_GUIDE.md
│   ├── TESTING_AND_TUNING.md
│   └── evaluation_metrics_report.md
├── development/             # Development phases
│   ├── PHASE1_IMPROVEMENTS.md
│   ├── PHASE2_IMPROVEMENTS.md
│   ├── PHASE3_IMPROVEMENTS.md
│   └── PHASE4_AWS_BEDROCK_MIGRATION.md
├── runbooks/                # Operational runbooks
├── reports/                 # Project report (PDF)
│   └── smart-tutor-ai-project-report.pdf
└── archive/                 # Archived documentation, old status reports, v1 RAG diagram
```

---

## Getting Started

1. **New to the project?** Start with [Quick Start](./guides/QUICK_START.md)
2. **Setting up locally?** See [How to Run](./guides/HOW_TO_RUN.md)
3. **Deploying to AWS?** Check [AWS Deployment](./aws/COMPLETE_AWS_DEPLOYMENT.md)
4. **Understanding the RAG pipeline?** Read [RAG Architecture](./rag/RAG_ARCHITECTURE_ANALYSIS.md)

---

*Last updated: 2026-01-18*
