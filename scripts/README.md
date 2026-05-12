# Scripts Directory

This directory contains standalone scripts for setup, migration, testing, and maintenance tasks.

## Directory Structure

```
scripts/
├── _helpers.sh    — Shared functions for dev scripts
├── dev.sh         — Rebuild & restart services
├── health.sh      — Service health dashboard
├── logs.sh        — Smart log viewer
├── test.sh        — Unified test runner
├── db.sh          — Database operations
├── aws/           (13 scripts) - AWS infrastructure setup
├── s3-vectors/    (19 scripts) - S3 vector index management
├── migration/     (7 scripts)  - Data migration tools
├── testing/       (7 scripts)  - Testing and debugging
├── auth/          (4 scripts)  - Authentication setup
└── utils/         (1 script)   - Utility scripts
```

---

## AWS Setup Scripts (`aws/`)

Infrastructure setup and configuration for AWS services.

| Script | Purpose |
|--------|---------|
| `setup_aws_production.sh` | Full AWS production environment setup |
| `setup_aws_dynamodb.sh` | DynamoDB tables setup |
| `setup_rds_postgres.sh` | RDS PostgreSQL setup |
| `setup_secrets_manager.sh` | AWS Secrets Manager configuration |
| `setup_cloudwatch_alarms.sh` | CloudWatch alarms setup |
| `setup_cloudwatch_logs.sh` | CloudWatch logs configuration |
| `setup_error_alarms.sh` | Error alerting setup |
| `deploy_production.sh` | Production deployment script |
| `enable_dynamodb_pitr.sh` | Enable DynamoDB point-in-time recovery |
| `enable_secret_rotation.sh` | Enable secret rotation |
| `setup_secret_rotation.sh` | Configure secret rotation |
| `update_cors_production.sh` | Update CORS for production |
| `verify_rds_backups.sh` | Verify RDS backup configuration |

---

## S3 Vector Scripts (`s3-vectors/`)

Scripts for managing S3-based vector indices and document processing.

### Rebuild Scripts (use `rebuild_from_s3_docs.py` - most recent)

| Script | Status | Notes |
|--------|--------|-------|
| `rebuild_from_s3_docs.py` | **Recommended** | Latest rebuild script |
| `rebuild_s3_vector_index_final.py` | Legacy | Previous version |
| `rebuild_with_text_bedrock.py` | Legacy | Bedrock-specific |
| `rebuild_index_from_s3.py` | Legacy | Earlier version |
| `rebuild_s3_index.py` | Legacy | Earlier version |
| `rebuild_vector_index.py` | Legacy | Local version |
| `simple_rebuild_s3.py` | Legacy | Simplified version |
| `local_rebuild_s3.py` | Legacy | Local testing |

### Setup & Upload Scripts

| Script | Purpose |
|--------|---------|
| `create_s3_buckets.py/.sh` | Create S3 buckets |
| `create_s3_vector_index.py/.sh` | Create vector index |
| `setup_s3_vectors.py` | Configure S3 vectors |
| `generate_s3_embeddings.py` | Generate embeddings |
| `upload_to_s3_vector_bucket.py` | Upload to vector bucket |
| `parallel_upload_chunks.py` | Parallel chunk upload |
| `convert_to_s3_vector_format.py` | Convert to S3 format |
| `regenerate_chunks_for_s3_vector.py` | Regenerate chunks |
| `clean_s3_chunks.py` | Clean up S3 chunks |

---

## Migration Scripts (`migration/`)

Data migration and conversion tools.

| Script | Purpose |
|--------|---------|
| `migrate_chat_sessions.py` | Migrate chat sessions to DynamoDB |
| `migrate_to_postgres.py` | Migrate data to PostgreSQL |
| `upload_documents_to_s3.py` | Upload documents to S3 |
| `upload_to_s3.py` | General S3 upload |
| `process_modules_to_s3.py` | Process course modules to S3 |
| `process_renamed_files.py` | Process renamed files |
| `convert_ppt_files.sh` | Convert PPT files |

---

## Testing Scripts (`testing/`)

Testing, debugging, and validation tools.

| Script | Purpose |
|--------|---------|
| `test_frontend_integration.sh` | Test frontend integration |
| `test_jwt_flow.sh` | Test JWT authentication flow |
| `test_llama_direct.py` | Test Llama model directly |
| `demo_test_results.py` | Demo test results |
| `Chromadb_viewer.py` | View ChromaDB contents |
| `list_bedrock_models.py` | List available Bedrock models |
| `monitor_processing.py` | Monitor document processing |

---

## Auth Scripts (`auth/`)

Authentication and OAuth setup.

| Script | Purpose |
|--------|---------|
| `setup_google_oauth.sh` | Set up Google OAuth |
| `setup_oauth_consent.sh` | Configure OAuth consent screen |
| `add_google_oauth_to_secrets.sh` | Add OAuth credentials to Secrets Manager |
| `rotate_jwt_secret.sh` | Rotate JWT signing secret |

---

## Utility Scripts (`utils/`)

| Script | Purpose |
|--------|---------|
| `manage_services.sh` | Start/stop/restart services |
| `resume_neo4j_aura.py` | Resume a paused Neo4j Aura instance via the Aura API |

---

## Development Automation Scripts

Daily-use scripts for building, testing, debugging, and managing the local Docker environment. All share a common `_helpers.sh` library for consistent output and dependency checks.

```
scripts/
├── _helpers.sh    — Shared functions (colors, Docker checks, wait helpers)
├── dev.sh         — Rebuild & restart services
├── health.sh      — Service health dashboard
├── logs.sh        — Smart log viewer with filtering
├── test.sh        — Unified test runner (backend + frontend)
└── db.sh          — Database operations (shell, backup, restore, reset)
```

### Quick Reference

| Script | Common Usage | Description |
|--------|-------------|-------------|
| `dev.sh` | `./scripts/dev.sh` | Rebuild & restart backend + frontend |
| `dev.sh` | `./scripts/dev.sh --all` | Rebuild all 12 services |
| `dev.sh` | `./scripts/dev.sh backend` | Rebuild backend only |
| `health.sh` | `./scripts/health.sh` | One-shot health dashboard |
| `health.sh` | `./scripts/health.sh --watch` | Live-updating dashboard (5s) |
| `logs.sh` | `./scripts/logs.sh -f` | Follow backend + frontend logs |
| `logs.sh` | `./scripts/logs.sh --errors --all` | Errors across all services |
| `logs.sh` | `./scripts/logs.sh -f backend --grep "query"` | Filter backend logs |
| `test.sh` | `./scripts/test.sh` | Run all tests (backend + frontend) |
| `test.sh` | `./scripts/test.sh --backend -m unit` | Backend unit tests only |
| `test.sh` | `./scripts/test.sh --lint` | Frontend lint only |
| `db.sh` | `./scripts/db.sh shell` | Open psql prompt |
| `db.sh` | `./scripts/db.sh tables` | List tables with row counts |
| `db.sh` | `./scripts/db.sh backup` | Dump DB to `backups/` |
| `db.sh` | `./scripts/db.sh restore dump.sql --force` | Restore from backup |
| `db.sh` | `./scripts/db.sh reset --force` | Drop all tables & re-run init-db.sql |

Every script supports `--help` for full option details.

### Typical Workflow

```bash
# 1. Make code changes, then rebuild
./scripts/dev.sh

# 2. Check everything came up healthy
./scripts/health.sh

# 3. Watch logs while testing
./scripts/logs.sh -f --grep "ERROR"

# 4. Run tests
./scripts/test.sh

# 5. Backup before a schema change
./scripts/db.sh backup pre-migration.sql
```

---

## Usage Examples

```bash
# Rebuild vector index from S3 documents
python scripts/s3-vectors/rebuild_from_s3_docs.py

# Set up AWS production environment
./scripts/aws/setup_aws_production.sh

# Test JWT authentication flow
./scripts/testing/test_jwt_flow.sh

# Rotate JWT secret
./scripts/auth/rotate_jwt_secret.sh
```

---

## Notes

- Most scripts require AWS credentials configured
- Shell scripts may need `chmod +x` to execute
- Legacy rebuild scripts are kept for reference but `rebuild_from_s3_docs.py` is recommended
- Always test scripts in development before running in production
- Dev automation scripts (`dev.sh`, `health.sh`, etc.) require Docker and docker compose

---

*Last updated: 2026-02-10*
