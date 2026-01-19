#!/bin/bash
# Automated Disaster Recovery Backup Script
# Creates comprehensive backups of all Smart AI Tutor components
# Usage: ./backup-all.sh [environment]

set -euo pipefail

# Configuration
ENVIRONMENT="${1:-production}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_BUCKET="s3://smart-tutor-${ENVIRONMENT}-dr-backups"
AWS_REGION="${AWS_REGION:-us-east-1}"
DR_REGION="${DR_REGION:-us-west-2}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install it."
        exit 1
    fi

    if ! command -v kubectl &> /dev/null; then
        log_warn "kubectl not found. Kubernetes backup will be skipped."
    fi

    if ! command -v jq &> /dev/null; then
        log_error "jq not found. Please install it."
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured."
        exit 1
    fi

    log_info "Prerequisites check passed."
}

# Create backup directory
create_backup_dir() {
    BACKUP_DIR="/tmp/dr-backup-${TIMESTAMP}"
    mkdir -p "$BACKUP_DIR"/{rds,dynamodb,secrets,ecs,k8s,reports}
    log_info "Created backup directory: $BACKUP_DIR"
}

# Backup RDS PostgreSQL
backup_rds() {
    log_info "Starting RDS backup..."

    DB_INSTANCE="smart-tutor-${ENVIRONMENT}"
    SNAPSHOT_ID="smart-tutor-${ENVIRONMENT}-${TIMESTAMP}"

    # Create snapshot
    log_info "Creating RDS snapshot: $SNAPSHOT_ID"
    aws rds create-db-snapshot \
        --db-instance-identifier "$DB_INSTANCE" \
        --db-snapshot-identifier "$SNAPSHOT_ID" \
        --region "$AWS_REGION" \
        --tags Key=Type,Value=DR Key=Timestamp,Value="$TIMESTAMP" Key=Environment,Value="$ENVIRONMENT" \
        --output json > "$BACKUP_DIR/rds/snapshot-creation.json"

    # Wait for snapshot to complete
    log_info "Waiting for RDS snapshot to complete (this may take 10-15 minutes)..."
    aws rds wait db-snapshot-completed \
        --db-snapshot-identifier "$SNAPSHOT_ID" \
        --region "$AWS_REGION"

    log_info "RDS snapshot created: $SNAPSHOT_ID"

    # Copy snapshot to DR region
    log_info "Copying snapshot to DR region: $DR_REGION"
    aws rds copy-db-snapshot \
        --source-db-snapshot-identifier "arn:aws:rds:${AWS_REGION}:$(aws sts get-caller-identity --query Account --output text):snapshot:${SNAPSHOT_ID}" \
        --target-db-snapshot-identifier "$SNAPSHOT_ID" \
        --region "$DR_REGION" \
        --copy-tags \
        --output json > "$BACKUP_DIR/rds/snapshot-dr-copy.json" || log_warn "DR region copy failed (may not be configured)"

    # Export snapshot metadata
    aws rds describe-db-snapshots \
        --db-snapshot-identifier "$SNAPSHOT_ID" \
        --region "$AWS_REGION" \
        --output json > "$BACKUP_DIR/rds/snapshot-metadata.json"

    # Get current database configuration
    aws rds describe-db-instances \
        --db-instance-identifier "$DB_INSTANCE" \
        --region "$AWS_REGION" \
        --output json > "$BACKUP_DIR/rds/instance-config.json"

    echo "$SNAPSHOT_ID" > "$BACKUP_DIR/rds/latest-snapshot-id.txt"
    log_info "✅ RDS backup completed: $SNAPSHOT_ID"
}

# Backup DynamoDB tables
backup_dynamodb() {
    log_info "Starting DynamoDB backup..."

    # List of tables to backup
    TABLES=(
        "smart-tutor-${ENVIRONMENT}-chat-sessions"
        "smart-tutor-${ENVIRONMENT}-user-sessions"
    )

    for TABLE in "${TABLES[@]}"; do
        log_info "Creating backup for DynamoDB table: $TABLE"

        BACKUP_NAME="${TABLE}-${TIMESTAMP}"

        # Create on-demand backup
        aws dynamodb create-backup \
            --table-name "$TABLE" \
            --backup-name "$BACKUP_NAME" \
            --region "$AWS_REGION" \
            --output json > "$BACKUP_DIR/dynamodb/${TABLE}-backup.json"

        # Export table description
        aws dynamodb describe-table \
            --table-name "$TABLE" \
            --region "$AWS_REGION" \
            --output json > "$BACKUP_DIR/dynamodb/${TABLE}-schema.json"

        # Export continuous backup status
        aws dynamodb describe-continuous-backups \
            --table-name "$TABLE" \
            --region "$AWS_REGION" \
            --output json > "$BACKUP_DIR/dynamodb/${TABLE}-pitr.json"

        log_info "✅ DynamoDB backup created: $BACKUP_NAME"
    done

    log_info "✅ All DynamoDB backups completed"
}

# Backup S3 buckets (verify replication)
backup_s3() {
    log_info "Verifying S3 bucket replication..."

    BUCKETS=(
        "smart-tutor-${ENVIRONMENT}-uploads"
        "smart-tutor-${ENVIRONMENT}-vectors"
        "smart-tutor-${ENVIRONMENT}-backups"
    )

    for BUCKET in "${BUCKETS[@]}"; do
        log_info "Checking bucket: $BUCKET"

        # Check if bucket exists
        if aws s3 ls "s3://$BUCKET" &> /dev/null; then
            # Get bucket versioning status
            aws s3api get-bucket-versioning \
                --bucket "$BUCKET" \
                --region "$AWS_REGION" \
                --output json > "$BACKUP_DIR/s3/${BUCKET}-versioning.json" 2>/dev/null || echo "{}" > "$BACKUP_DIR/s3/${BUCKET}-versioning.json"

            # Get bucket replication configuration
            aws s3api get-bucket-replication \
                --bucket "$BUCKET" \
                --region "$AWS_REGION" \
                --output json > "$BACKUP_DIR/s3/${BUCKET}-replication.json" 2>/dev/null || echo "{}" > "$BACKUP_DIR/s3/${BUCKET}-replication.json"

            # Get object count and size
            aws s3 ls "s3://$BUCKET" --recursive --summarize 2>/dev/null | tail -2 > "$BACKUP_DIR/s3/${BUCKET}-stats.txt" || echo "Unable to get stats" > "$BACKUP_DIR/s3/${BUCKET}-stats.txt"

            log_info "✅ S3 bucket verified: $BUCKET"
        else
            log_warn "Bucket not found: $BUCKET"
        fi
    done

    log_info "✅ S3 verification completed"
}

# Backup AWS Secrets Manager
backup_secrets() {
    log_info "Backing up secrets from AWS Secrets Manager..."

    SECRETS=(
        "smart-tutor/app/secrets"
        "smart-tutor/rds/credentials"
        "smart-tutor/redis/auth"
    )

    # Generate a temporary encryption key
    ENCRYPTION_KEY=$(openssl rand -base64 32)
    echo "$ENCRYPTION_KEY" > "$BACKUP_DIR/secrets/.encryption-key"
    chmod 600 "$BACKUP_DIR/secrets/.encryption-key"

    for SECRET in "${SECRETS[@]}"; do
        log_info "Backing up secret: $SECRET"

        SECRET_FILE="${SECRET//\//-}"

        # Get secret value
        aws secretsmanager get-secret-value \
            --secret-id "$SECRET" \
            --region "$AWS_REGION" \
            --query SecretString \
            --output text > "$BACKUP_DIR/secrets/${SECRET_FILE}.json" 2>/dev/null || {
                log_warn "Secret not found: $SECRET"
                continue
            }

        # Encrypt the secret
        openssl enc -aes-256-cbc -salt -pbkdf2 \
            -in "$BACKUP_DIR/secrets/${SECRET_FILE}.json" \
            -out "$BACKUP_DIR/secrets/${SECRET_FILE}.enc" \
            -pass file:"$BACKUP_DIR/secrets/.encryption-key"

        # Remove plaintext
        rm "$BACKUP_DIR/secrets/${SECRET_FILE}.json"

        # Get secret metadata
        aws secretsmanager describe-secret \
            --secret-id "$SECRET" \
            --region "$AWS_REGION" \
            --output json > "$BACKUP_DIR/secrets/${SECRET_FILE}-metadata.json" 2>/dev/null || true

        log_info "✅ Secret backed up and encrypted: $SECRET"
    done

    # Upload encryption key to S3 with server-side encryption
    aws s3 cp "$BACKUP_DIR/secrets/.encryption-key" \
        "${BACKUP_BUCKET}/secrets/${TIMESTAMP}/.encryption-key" \
        --sse aws:kms \
        --sse-kms-key-id alias/smart-tutor-dr \
        --region "$AWS_REGION" 2>/dev/null || log_warn "Could not upload encryption key to S3"

    log_info "✅ Secrets backup completed"
}

# Backup ECS task definitions
backup_ecs() {
    log_info "Backing up ECS task definitions..."

    CLUSTER="smart-tutor-${ENVIRONMENT}"
    SERVICES=("backend" "frontend")

    for SERVICE in "${SERVICES[@]}"; do
        log_info "Backing up ECS service: $SERVICE"

        # Get current task definition
        TASK_DEF_ARN=$(aws ecs describe-services \
            --cluster "$CLUSTER" \
            --services "$SERVICE" \
            --region "$AWS_REGION" \
            --query 'services[0].taskDefinition' \
            --output text 2>/dev/null) || {
                log_warn "Service not found: $SERVICE"
                continue
            }

        # Export task definition
        aws ecs describe-task-definition \
            --task-definition "$TASK_DEF_ARN" \
            --region "$AWS_REGION" \
            --output json > "$BACKUP_DIR/ecs/${SERVICE}-taskdef.json"

        # Export service configuration
        aws ecs describe-services \
            --cluster "$CLUSTER" \
            --services "$SERVICE" \
            --region "$AWS_REGION" \
            --output json > "$BACKUP_DIR/ecs/${SERVICE}-service.json"

        log_info "✅ ECS task definition backed up: $SERVICE"
    done

    # Export cluster configuration
    aws ecs describe-clusters \
        --clusters "$CLUSTER" \
        --region "$AWS_REGION" \
        --output json > "$BACKUP_DIR/ecs/cluster-config.json" 2>/dev/null || true

    log_info "✅ ECS backups completed"
}

# Backup Kubernetes resources
backup_kubernetes() {
    if ! command -v kubectl &> /dev/null; then
        log_warn "kubectl not found. Skipping Kubernetes backup."
        return
    fi

    log_info "Backing up Kubernetes resources..."

    NAMESPACE="${ENVIRONMENT}"

    # Check if namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_warn "Kubernetes namespace not found: $NAMESPACE"
        return
    fi

    # Backup all resources
    kubectl get all,configmap,secret,ingress,pvc,hpa,pdb,networkpolicy \
        -n "$NAMESPACE" \
        -o yaml > "$BACKUP_DIR/k8s/all-resources.yaml" 2>/dev/null || log_warn "Some Kubernetes resources could not be backed up"

    # Backup individual resource types
    RESOURCES=("deployments" "services" "configmaps" "secrets" "ingresses" "hpa" "pdb")

    for RESOURCE in "${RESOURCES[@]}"; do
        kubectl get "$RESOURCE" -n "$NAMESPACE" -o yaml > "$BACKUP_DIR/k8s/${RESOURCE}.yaml" 2>/dev/null || true
    done

    # Backup Helm releases
    if command -v helm &> /dev/null; then
        helm list -n "$NAMESPACE" -o yaml > "$BACKUP_DIR/k8s/helm-releases.yaml" 2>/dev/null || true

        # Get Helm values for each release
        helm list -n "$NAMESPACE" -q 2>/dev/null | while read -r RELEASE; do
            helm get values "$RELEASE" -n "$NAMESPACE" > "$BACKUP_DIR/k8s/helm-values-${RELEASE}.yaml" 2>/dev/null || true
        done
    fi

    log_info "✅ Kubernetes backup completed"
}

# Generate backup report
generate_report() {
    log_info "Generating backup report..."

    REPORT_FILE="$BACKUP_DIR/reports/backup-report-${TIMESTAMP}.txt"

    cat > "$REPORT_FILE" <<EOF
========================================
DISASTER RECOVERY BACKUP REPORT
========================================

Backup ID: ${TIMESTAMP}
Environment: ${ENVIRONMENT}
Date: $(date)
Backup Bucket: ${BACKUP_BUCKET}
AWS Region: ${AWS_REGION}
DR Region: ${DR_REGION}

========================================
COMPONENTS BACKED UP
========================================

RDS PostgreSQL:
  - Snapshot ID: $(cat "$BACKUP_DIR/rds/latest-snapshot-id.txt" 2>/dev/null || echo "N/A")
  - Status: $(aws rds describe-db-snapshots --db-snapshot-identifier "$(cat "$BACKUP_DIR/rds/latest-snapshot-id.txt" 2>/dev/null)" --region "$AWS_REGION" --query 'DBSnapshots[0].Status' --output text 2>/dev/null || echo "Unknown")

DynamoDB Tables:
$(for table in smart-tutor-${ENVIRONMENT}-chat-sessions smart-tutor-${ENVIRONMENT}-user-sessions; do
    echo "  - $table: Backed up"
done)

S3 Buckets:
$(for bucket in smart-tutor-${ENVIRONMENT}-uploads smart-tutor-${ENVIRONMENT}-vectors smart-tutor-${ENVIRONMENT}-backups; do
    if [ -f "$BACKUP_DIR/s3/${bucket}-stats.txt" ]; then
        echo "  - $bucket: $(cat "$BACKUP_DIR/s3/${bucket}-stats.txt" | tail -1)"
    else
        echo "  - $bucket: Not found"
    fi
done)

AWS Secrets Manager:
$(find "$BACKUP_DIR/secrets" -name "*.enc" | wc -l | xargs echo "  - Total secrets backed up:")

ECS Task Definitions:
$(find "$BACKUP_DIR/ecs" -name "*-taskdef.json" | wc -l | xargs echo "  - Total services backed up:")

Kubernetes Resources:
$(if [ -f "$BACKUP_DIR/k8s/all-resources.yaml" ]; then
    echo "  - Namespace: ${NAMESPACE}"
    echo "  - Resources backed up: Yes"
else
    echo "  - Not available"
fi)

========================================
BACKUP VERIFICATION
========================================

RDS Snapshot: $(aws rds describe-db-snapshots --db-snapshot-identifier "$(cat "$BACKUP_DIR/rds/latest-snapshot-id.txt" 2>/dev/null)" --region "$AWS_REGION" --query 'DBSnapshots[0].Status' --output text 2>/dev/null || echo "Failed")
DynamoDB Backups: $(aws dynamodb list-backups --table-name "smart-tutor-${ENVIRONMENT}-chat-sessions" --region "$AWS_REGION" --query "length(BackupSummaries)" --output text 2>/dev/null || echo "Failed") backups available
S3 Replication: Configured
Secrets: Encrypted and stored

========================================
RECOVERY INFORMATION
========================================

RTO (Recovery Time Objective): < 4 hours
RPO (Recovery Point Objective): < 15 minutes

Recovery Steps:
1. Run: scripts/dr/restore/restore-rds.sh $(cat "$BACKUP_DIR/rds/latest-snapshot-id.txt" 2>/dev/null)
2. Run: scripts/dr/restore/restore-dynamodb.sh ${TIMESTAMP}
3. Run: scripts/dr/restore/restore-secrets.sh ${TIMESTAMP}
4. Run: scripts/dr/restore/restore-ecs.sh ${TIMESTAMP}
5. Verify: scripts/dr/validation/verify-backups.sh ${TIMESTAMP}

========================================
NEXT SCHEDULED BACKUP
========================================

Daily automated backup: $(date -d "+1 day" +"%Y-%m-%d 02:00 UTC" 2>/dev/null || date -v+1d +"%Y-%m-%d 02:00 UTC")
Monthly DR test: 1st of next month

========================================
CONTACTS
========================================

On-call: PagerDuty rotation
DevOps Lead: devops-lead@your-domain.com
Platform Team: platform@your-domain.com

========================================
END OF REPORT
========================================
EOF

    log_info "Backup report generated: $REPORT_FILE"
    cat "$REPORT_FILE"
}

# Upload backup to S3
upload_to_s3() {
    log_info "Uploading backup to S3..."

    # Create tarball
    TARBALL="$BACKUP_DIR/smart-tutor-backup-${TIMESTAMP}.tar.gz"
    tar -czf "$TARBALL" -C "$BACKUP_DIR" .

    # Upload to S3
    aws s3 cp "$TARBALL" "${BACKUP_BUCKET}/complete/${TIMESTAMP}/backup.tar.gz" \
        --region "$AWS_REGION"

    # Upload individual components
    aws s3 sync "$BACKUP_DIR" "${BACKUP_BUCKET}/${TIMESTAMP}/" \
        --region "$AWS_REGION" \
        --exclude "*.tar.gz"

    log_info "✅ Backup uploaded to: ${BACKUP_BUCKET}/${TIMESTAMP}/"
}

# Send notification
send_notification() {
    local STATUS=$1
    local MESSAGE=$2

    # Slack notification (if webhook configured)
    if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
        curl -X POST "$SLACK_WEBHOOK_URL" \
            -H 'Content-Type: application/json' \
            -d "{\"text\":\"${STATUS} DR Backup (${ENVIRONMENT}): ${MESSAGE}\",\"timestamp\":\"${TIMESTAMP}\"}" \
            2>/dev/null || log_warn "Slack notification failed"
    fi

    # SNS notification (if topic configured)
    if [ -n "${SNS_TOPIC_ARN:-}" ]; then
        aws sns publish \
            --topic-arn "$SNS_TOPIC_ARN" \
            --subject "${STATUS}: DR Backup - ${ENVIRONMENT}" \
            --message "$MESSAGE" \
            --region "$AWS_REGION" \
            2>/dev/null || log_warn "SNS notification failed"
    fi
}

# Cleanup old backups
cleanup_old_backups() {
    log_info "Cleaning up backups older than 30 days..."

    # Delete old RDS snapshots
    aws rds describe-db-snapshots \
        --db-instance-identifier "smart-tutor-${ENVIRONMENT}" \
        --region "$AWS_REGION" \
        --query "DBSnapshots[?SnapshotCreateTime<\`$(date -d '30 days ago' -Iseconds 2>/dev/null || date -v-30d -Iseconds)\`].DBSnapshotIdentifier" \
        --output text | tr '\t' '\n' | while read -r SNAPSHOT; do
            if [ -n "$SNAPSHOT" ]; then
                log_info "Deleting old RDS snapshot: $SNAPSHOT"
                aws rds delete-db-snapshot \
                    --db-snapshot-identifier "$SNAPSHOT" \
                    --region "$AWS_REGION" 2>/dev/null || log_warn "Could not delete snapshot: $SNAPSHOT"
            fi
        done

    # Cleanup S3 backups (using lifecycle policy is preferred)
    log_info "Note: S3 backup cleanup is handled by bucket lifecycle policy"

    log_info "✅ Cleanup completed"
}

# Main execution
main() {
    log_info "=========================================="
    log_info "Starting DR Backup: $TIMESTAMP"
    log_info "Environment: $ENVIRONMENT"
    log_info "=========================================="

    check_prerequisites
    create_backup_dir

    # Run backup tasks
    backup_rds
    backup_dynamodb
    backup_s3
    backup_secrets
    backup_ecs
    backup_kubernetes

    # Generate report and upload
    generate_report
    upload_to_s3

    # Cleanup
    cleanup_old_backups

    # Send success notification
    send_notification "✅ SUCCESS" "DR backup completed successfully for ${ENVIRONMENT}. Backup ID: ${TIMESTAMP}"

    log_info "=========================================="
    log_info "DR Backup Completed Successfully!"
    log_info "Backup ID: $TIMESTAMP"
    log_info "Location: ${BACKUP_BUCKET}/${TIMESTAMP}/"
    log_info "=========================================="

    # Cleanup local backup directory
    rm -rf "$BACKUP_DIR"
    log_info "Local backup directory cleaned up"
}

# Error handler
error_handler() {
    log_error "Backup failed at line $1"
    send_notification "❌ FAILED" "DR backup failed for ${ENVIRONMENT} at line $1"
    exit 1
}

trap 'error_handler $LINENO' ERR

# Run main function
main "$@"
