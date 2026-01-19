# Scripts Directory

This directory contains standalone scripts for setup, migration, testing, and maintenance tasks.

## Directory Structure

```
scripts/
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

---

*Last updated: 2026-01-18*
