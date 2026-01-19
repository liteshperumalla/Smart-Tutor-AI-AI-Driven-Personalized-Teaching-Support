#!/bin/bash
# RDS Restore Script
# Restores RDS database from snapshot
# Usage: ./restore-rds.sh <snapshot-id> [new-instance-id]

set -euo pipefail

# Configuration
SNAPSHOT_ID="${1:-}"
NEW_INSTANCE_ID="${2:-smart-tutor-prod-restored-$(date +%s)}"
AWS_REGION="${AWS_REGION:-us-east-1}"
ENVIRONMENT="${ENVIRONMENT:-production}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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
        log_error "AWS CLI not found"
        exit 1
    fi

    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured"
        exit 1
    fi

    if [ -z "$SNAPSHOT_ID" ]; then
        log_error "Usage: $0 <snapshot-id> [new-instance-id]"
        echo ""
        echo "Available snapshots:"
        aws rds describe-db-snapshots \
            --region "$AWS_REGION" \
            --query 'DBSnapshots[?contains(DBSnapshotIdentifier, `smart-tutor`)].{ID:DBSnapshotIdentifier,Created:SnapshotCreateTime,Status:Status}' \
            --output table
        exit 1
    fi
}

# Verify snapshot exists
verify_snapshot() {
    log_info "Verifying snapshot exists: $SNAPSHOT_ID"

    if ! aws rds describe-db-snapshots \
        --db-snapshot-identifier "$SNAPSHOT_ID" \
        --region "$AWS_REGION" &> /dev/null; then
        log_error "Snapshot not found: $SNAPSHOT_ID"
        exit 1
    fi

    # Get snapshot info
    SNAPSHOT_INFO=$(aws rds describe-db-snapshots \
        --db-snapshot-identifier "$SNAPSHOT_ID" \
        --region "$AWS_REGION" \
        --output json)

    SNAPSHOT_STATUS=$(echo "$SNAPSHOT_INFO" | jq -r '.DBSnapshots[0].Status')
    SNAPSHOT_ENGINE=$(echo "$SNAPSHOT_INFO" | jq -r '.DBSnapshots[0].Engine')
    SNAPSHOT_SIZE=$(echo "$SNAPSHOT_INFO" | jq -r '.DBSnapshots[0].AllocatedStorage')

    log_info "Snapshot Status: $SNAPSHOT_STATUS"
    log_info "Engine: $SNAPSHOT_ENGINE"
    log_info "Size: ${SNAPSHOT_SIZE}GB"

    if [ "$SNAPSHOT_STATUS" != "available" ]; then
        log_error "Snapshot is not available for restore (status: $SNAPSHOT_STATUS)"
        exit 1
    fi
}

# Get original instance configuration
get_original_config() {
    log_info "Getting original instance configuration..."

    # Try to get from the original instance
    ORIGINAL_INSTANCE=$(echo "$SNAPSHOT_ID" | grep -oP 'smart-tutor-\w+' | head -1)

    if aws rds describe-db-instances \
        --db-instance-identifier "$ORIGINAL_INSTANCE" \
        --region "$AWS_REGION" &> /dev/null 2>&1; then

        INSTANCE_INFO=$(aws rds describe-db-instances \
            --db-instance-identifier "$ORIGINAL_INSTANCE" \
            --region "$AWS_REGION" \
            --output json)

        INSTANCE_CLASS=$(echo "$INSTANCE_INFO" | jq -r '.DBInstances[0].DBInstanceClass')
        VPC_SECURITY_GROUPS=$(echo "$INSTANCE_INFO" | jq -r '.DBInstances[0].VpcSecurityGroups[].VpcSecurityGroupId' | tr '\n' ' ')
        DB_SUBNET_GROUP=$(echo "$INSTANCE_INFO" | jq -r '.DBInstances[0].DBSubnetGroup.DBSubnetGroupName')
        MULTI_AZ=$(echo "$INSTANCE_INFO" | jq -r '.DBInstances[0].MultiAZ')

        log_info "Using configuration from original instance: $ORIGINAL_INSTANCE"
    else
        # Use defaults
        INSTANCE_CLASS="db.r6g.xlarge"
        VPC_SECURITY_GROUPS=""
        DB_SUBNET_GROUP="smart-tutor-${ENVIRONMENT}"
        MULTI_AZ="true"

        log_warn "Original instance not found, using default configuration"
    fi
}

# Restore from snapshot
restore_snapshot() {
    log_info "=========================================="
    log_info "Starting RDS Restore"
    log_info "Snapshot: $SNAPSHOT_ID"
    log_info "New Instance: $NEW_INSTANCE_ID"
    log_info "Instance Class: $INSTANCE_CLASS"
    log_info "=========================================="

    # Confirmation
    read -p "Proceed with restore? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        log_warn "Restore cancelled"
        exit 0
    fi

    log_info "Restoring RDS instance from snapshot..."

    # Build restore command
    RESTORE_CMD="aws rds restore-db-instance-from-db-snapshot \
        --db-instance-identifier '$NEW_INSTANCE_ID' \
        --db-snapshot-identifier '$SNAPSHOT_ID' \
        --db-instance-class '$INSTANCE_CLASS' \
        --db-subnet-group-name '$DB_SUBNET_GROUP' \
        --publicly-accessible false \
        --storage-encrypted \
        --enable-cloudwatch-logs-exports postgresql \
        --deletion-protection \
        --region '$AWS_REGION'"

    # Add VPC security groups if available
    if [ -n "$VPC_SECURITY_GROUPS" ]; then
        for SG in $VPC_SECURITY_GROUPS; do
            RESTORE_CMD="$RESTORE_CMD --vpc-security-group-ids '$SG'"
        done
    fi

    # Add multi-AZ if enabled
    if [ "$MULTI_AZ" == "true" ]; then
        RESTORE_CMD="$RESTORE_CMD --multi-az"
    fi

    # Add tags
    RESTORE_CMD="$RESTORE_CMD --tags \
        Key=Environment,Value='${ENVIRONMENT}' \
        Key=RestoredFrom,Value='${SNAPSHOT_ID}' \
        Key=RestoredAt,Value='$(date -Iseconds)' \
        Key=ManagedBy,Value='Terraform'"

    # Execute restore
    eval $RESTORE_CMD > /tmp/restore-output.json

    log_info "Restore initiated successfully"
}

# Wait for instance to be available
wait_for_availability() {
    log_info "Waiting for instance to be available (this may take 10-20 minutes)..."

    aws rds wait db-instance-available \
        --db-instance-identifier "$NEW_INSTANCE_ID" \
        --region "$AWS_REGION"

    log_info "✅ Instance is now available"
}

# Get new endpoint
get_endpoint() {
    log_info "Getting new instance endpoint..."

    ENDPOINT_INFO=$(aws rds describe-db-instances \
        --db-instance-identifier "$NEW_INSTANCE_ID" \
        --region "$AWS_REGION" \
        --output json)

    NEW_ENDPOINT=$(echo "$ENDPOINT_INFO" | jq -r '.DBInstances[0].Endpoint.Address')
    NEW_PORT=$(echo "$ENDPOINT_INFO" | jq -r '.DBInstances[0].Endpoint.Port')

    log_info "New Endpoint: $NEW_ENDPOINT:$NEW_PORT"

    # Save to file
    cat > "/tmp/rds-restore-${NEW_INSTANCE_ID}.txt" <<EOF
RDS Restore Complete
====================

Snapshot ID: $SNAPSHOT_ID
New Instance ID: $NEW_INSTANCE_ID
Endpoint: $NEW_ENDPOINT
Port: $NEW_PORT
Instance Class: $INSTANCE_CLASS
Multi-AZ: $MULTI_AZ

Connection String:
postgresql://smart_tutor_user@${NEW_ENDPOINT}:${NEW_PORT}/smart_tutor

Next Steps:
1. Update Secrets Manager with new endpoint
2. Update application configuration
3. Run validation tests
4. Switch traffic to new instance
5. Delete old instance after validation

Validation Command:
psql -h $NEW_ENDPOINT -U smart_tutor_user -d smart_tutor -c 'SELECT COUNT(*) FROM users;'
EOF

    cat "/tmp/rds-restore-${NEW_INSTANCE_ID}.txt"
}

# Update Secrets Manager
update_secrets_manager() {
    log_info "Updating Secrets Manager with new endpoint..."

    read -p "Update Secrets Manager? (yes/no): " UPDATE_SM
    if [ "$UPDATE_SM" != "yes" ]; then
        log_warn "Skipping Secrets Manager update"
        return
    fi

    # Get current secret
    CURRENT_SECRET=$(aws secretsmanager get-secret-value \
        --secret-id "smart-tutor/rds/credentials" \
        --region "$AWS_REGION" \
        --query SecretString \
        --output text)

    # Update host field
    UPDATED_SECRET=$(echo "$CURRENT_SECRET" | jq --arg host "$NEW_ENDPOINT" '.host = $host')

    # Update secret
    aws secretsmanager update-secret \
        --secret-id "smart-tutor/rds/credentials" \
        --secret-string "$UPDATED_SECRET" \
        --region "$AWS_REGION"

    log_info "✅ Secrets Manager updated"
}

# Validate restore
validate_restore() {
    log_info "Validating restored database..."

    # Test connection
    log_info "Testing database connection..."

    # Get credentials from Secrets Manager
    CREDS=$(aws secretsmanager get-secret-value \
        --secret-id "smart-tutor/rds/credentials" \
        --region "$AWS_REGION" \
        --query SecretString \
        --output text)

    DB_USER=$(echo "$CREDS" | jq -r '.username')
    DB_PASS=$(echo "$CREDS" | jq -r '.password')
    DB_NAME=$(echo "$CREDS" | jq -r '.database')

    # Run validation query
    PGPASSWORD="$DB_PASS" psql -h "$NEW_ENDPOINT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT version();" > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        log_info "✅ Database connection successful"

        # Check table counts
        USER_COUNT=$(PGPASSWORD="$DB_PASS" psql -h "$NEW_ENDPOINT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM users;" 2>/dev/null | tr -d ' ')

        log_info "Users table count: $USER_COUNT"
    else
        log_error "Database connection failed"
        log_error "Please check credentials and network connectivity"
    fi
}

# Main execution
main() {
    log_info "=========================================="
    log_info "RDS Restore Script"
    log_info "=========================================="

    check_prerequisites
    verify_snapshot
    get_original_config
    restore_snapshot
    wait_for_availability
    get_endpoint
    update_secrets_manager
    validate_restore

    log_info "=========================================="
    log_info "RDS Restore Complete!"
    log_info "Instance ID: $NEW_INSTANCE_ID"
    log_info "Endpoint: $NEW_ENDPOINT"
    log_info "Info saved to: /tmp/rds-restore-${NEW_INSTANCE_ID}.txt"
    log_info "=========================================="
}

# Error handler
error_handler() {
    log_error "Restore failed at line $1"
    log_error "Check logs for details"
    exit 1
}

trap 'error_handler $LINENO' ERR

# Run main
main "$@"
